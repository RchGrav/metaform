//! The specification document (R-1.2): the map's skeleton and its specification layer rendered as
//! one Markdown document, and a document read back into the layer. Render, parse and render again
//! give the same document. The CLI calls this; it is not an MCP command (R-5.14 to R-5.16).
//!
//! ```text
//! # <project>
//!
//! <root intro>
//!
//! ## <root block, level 1>          root blocks: Markdown level = block level + 1
//!
//! ## <name> (`<address>`)            one heading for each element, in tree order
//!
//! Role: <role>. Technical name: <technical name>. Status: <status>.
//!
//! - `<address>` (<name>) requires `<other>` (<other name>) in order to <why>, which <how>.
//!
//! <intro>
//!
//! ### <element block, level 1>       element blocks: Markdown level = block level + 2
//! ```
//!
//! The role line and the wants are the skeleton facts. They come from the map, so a parse
//! regenerates them from the current map and removes them. A document whose facts differ from the
//! map is stale, and the parse refuses it, because the skeleton changes through intake, not
//! through the prose.

use std::cmp::Ordering;
use std::collections::BTreeMap;

use serde_json::Value;

use crate::model::{Element, Map};
use crate::names::{ROOT, ROOT_SCOPES};
use crate::specification::{self, Block, LAYER};

/// Markdown levels: the project heading, and each element heading.
const PROJECT_HASHES: usize = 1;
const ELEMENT_HASHES: usize = 2;

// ---- Markdown line rules (CommonMark block starts) ----

/// A line with at most three leading spaces, which Markdown still reads as a block start.
fn unindented(line: &str) -> Option<&str> {
    let spaces = line.len() - line.trim_start_matches(' ').len();
    (spaces <= 3).then(|| &line[spaces..])
}

/// The level of an ATX heading line (`#` to `######`), or `None` for any other line.
pub(crate) fn atx_level(line: &str) -> Option<usize> {
    let rest = unindented(line)?;
    let hashes = rest.len() - rest.trim_start_matches('#').len();
    let after = rest[hashes..].chars().next();
    ((1..=6).contains(&hashes) && after.is_none_or(|c| c == ' ' || c == '\t')).then_some(hashes)
}

/// The heading text of an ATX heading line, without its hashes or a closing `#` sequence.
fn atx_text(line: &str) -> String {
    let rest = unindented(line).unwrap_or(line).trim_start_matches('#').trim();
    let without_closing = rest.trim_end_matches('#');
    if without_closing.len() < rest.len() && (without_closing.is_empty() || without_closing.ends_with(' ')) {
        without_closing.trim_end().to_string()
    } else {
        rest.to_string()
    }
}

/// A line of only `=` or only `-`, which makes the line above it a heading.
pub(crate) fn is_setext_underline(line: &str) -> bool {
    let Some(rest) = unindented(line) else {
        return false;
    };
    let rest = rest.trim_end();
    !rest.is_empty() && (rest.chars().all(|c| c == '=') || rest.chars().all(|c| c == '-'))
}

/// The mark and length of a line that opens a code fence.
pub(crate) fn opens_fence(line: &str) -> Option<(char, usize)> {
    let rest = unindented(line)?;
    let mark = rest.chars().next().filter(|c| *c == '`' || *c == '~')?;
    let length = rest.len() - rest.trim_start_matches(mark).len();
    (length >= 3).then_some((mark, length))
}

/// Whether a line closes a fence opened with `mark` repeated `length` times.
pub(crate) fn closes_fence(line: &str, mark: char, length: usize) -> bool {
    let Some(rest) = unindented(line) else {
        return false;
    };
    let run = rest.len() - rest.trim_start_matches(mark).len();
    run >= length && rest[run..].trim().is_empty()
}

/// The address at the end of an element heading's text, `Name (`code.api`)`.
fn heading_address(text: &str) -> Option<&str> {
    let rest = text.strip_suffix("`)")?;
    let start = rest.rfind("(`")?;
    let address = &rest[start + 2..];
    (!address.is_empty() && !address.contains('`')).then_some(address)
}

// ---- The document's content ----

/// Order addresses as a tree: the root first, then the root scopes in R-3.3 order, and each
/// element directly before what is beneath it.
fn tree_order(a: &str, b: &str) -> Ordering {
    let key = |address: &str| {
        let scope = address.split('.').next().unwrap_or_default();
        let rank = ROOT_SCOPES.iter().position(|s| *s == scope).unwrap_or(ROOT_SCOPES.len());
        (address != ROOT, rank)
    };
    key(a)
        .cmp(&key(b))
        .then_with(|| a.split('.').cmp(b.split('.')))
}

fn has_blocks(element: &Element) -> bool {
    element
        .fields
        .get(LAYER)
        .and_then(Value::as_array)
        .is_some_and(|blocks| !blocks.is_empty())
}

/// An element is in the document if it is part of the skeleton (R-3.4's mandatory fields) or
/// still holds blocks.
fn in_document(element: &Element) -> bool {
    let skeleton = ["technical_name", "name", "role"]
        .iter()
        .all(|key| element.fields.contains_key(*key));
    skeleton || has_blocks(element)
}

fn text_field<'a>(element: &'a Element, key: &str) -> Option<&'a str> {
    element
        .fields
        .get(key)
        .and_then(Value::as_str)
        .filter(|text| !text.trim().is_empty())
}

/// The name an element heading shows: `name`, else `technical_name`, else the address.
fn display_name<'a>(map: &'a Map, address: &'a str) -> &'a str {
    map.element(address)
        .and_then(|element| text_field(element, "name").or_else(|| text_field(element, "technical_name")))
        .unwrap_or(address)
}

fn element_heading(map: &Map, address: &str) -> String {
    format!("{} {} (`{address}`)", "#".repeat(ELEMENT_HASHES), display_name(map, address))
}

/// A stored `why` or `how` fitted into the wants sentence: no trailing full stop, and a first
/// capital lowered when the next letter is lower case, so "Receive" becomes "receive" while "ACP"
/// stays as written.
fn fragment(text: &str) -> String {
    let trimmed = text.trim().trim_end_matches('.');
    let mut chars = trimmed.chars();
    match (chars.next(), chars.next()) {
        (Some(first), Some(second)) if first.is_uppercase() && second.is_lowercase() => {
            first.to_lowercase().chain(trimmed.chars().skip(1)).collect()
        }
        _ => trimmed.to_string(),
    }
}

/// The skeleton facts of an element as document paragraphs: the role line, then the wants as a
/// list, each want as the sentence of R-6.17. The root has none.
fn skeleton_facts(map: &Map, address: &str) -> Vec<String> {
    let Some(element) = map.element(address).filter(|_| address != ROOT) else {
        return Vec::new();
    };
    let mut paragraphs = Vec::new();
    let details: Vec<String> = [("role", "Role"), ("technical_name", "Technical name"), ("status", "Status")]
        .iter()
        .filter_map(|(key, label)| text_field(element, key).map(|value| format!("{label}: {value}.")))
        .collect();
    if !details.is_empty() {
        paragraphs.push(details.join(" "));
    }
    let name = display_name(map, address);
    let wants: Vec<String> = element
        .wants
        .iter()
        .map(|(other, record)| {
            let field = |key: &str| fragment(record.get(key).and_then(Value::as_str).unwrap_or(""));
            format!(
                "- `{address}` ({name}) requires `{other}` ({}) in order to {}, which {}.",
                display_name(map, other),
                field("why"),
                field("how"),
            )
        })
        .collect();
    if !wants.is_empty() {
        paragraphs.push(wants.join("\n"));
    }
    paragraphs
}

/// The Markdown level a block's heading takes under its container.
fn container_hashes(address: &str) -> usize {
    if address == ROOT { PROJECT_HASHES } else { ELEMENT_HASHES }
}

/// An element's blocks as document paragraphs. A value that breaks the layer's rules is shown as
/// written in a code block, so the document loses nothing; such a document does not parse back.
fn block_paragraphs(address: &str, element: &Element) -> Vec<String> {
    let Some(value) = element.fields.get(LAYER) else {
        return Vec::new();
    };
    match specification::blocks(value) {
        Ok(blocks) => blocks
            .iter()
            .flat_map(|block| {
                let heading = match (block.level, &block.title) {
                    (Some(level), Some(title)) => Some(format!(
                        "{} {title}",
                        "#".repeat(container_hashes(address) + usize::from(level))
                    )),
                    _ => None,
                };
                heading.into_iter().chain((!block.text.is_empty()).then(|| block.text.clone()))
            })
            .collect(),
        Err(refusal) => vec![
            format!("The specification layer at `{address}` breaks a rule: {}.", refusal.reason),
            format!("```json\n{}\n```", serde_json::to_string_pretty(value).unwrap_or_default()),
        ],
    }
}

/// The addresses the document holds, in document order: the root first if it holds blocks.
pub(crate) fn document_addresses(map: &Map) -> Vec<&str> {
    let mut addresses: Vec<&str> = map
        .elements()
        .filter(|(address, element)| {
            if *address == ROOT { has_blocks(element) } else { in_document(element) }
        })
        .map(|(address, _)| address)
        .collect();
    addresses.sort_by(|a, b| tree_order(a, b));
    addresses
}

/// The map's specification as one Markdown document.
pub fn render(map: &Map, project: &str) -> String {
    let mut parts = vec![format!("{} {project}", "#".repeat(PROJECT_HASHES))];
    for address in document_addresses(map) {
        let element = map.element(address).expect("listed from the map");
        if address != ROOT {
            parts.push(element_heading(map, address));
            parts.extend(skeleton_facts(map, address));
        }
        parts.extend(block_paragraphs(address, element));
    }
    let mut document = parts.join("\n\n");
    document.push('\n');
    document
}

// ---- Reading a document back ----

/// A problem reading a document back into the layer.
#[derive(Debug, PartialEq, Eq, thiserror::Error)]
#[error("line {line}: {reason}")]
pub struct ParseError {
    pub line: usize,
    pub reason: String,
}

fn parse_error(line: usize, reason: impl Into<String>) -> ParseError {
    ParseError { line, reason: reason.into() }
}

/// One container in the document: the root, or an element, with its body lines.
struct Section<'a> {
    address: String,
    heading_line: usize,
    body: Vec<(usize, &'a str)>,
}

/// Read a document made by `render` back into specification blocks, keyed by address. The map
/// supplies the skeleton: every element heading must name one of its elements, exactly as `render`
/// writes it, followed by that element's skeleton facts. The result holds every section in the
/// document, with an empty list for a section that has no blocks. The caller writes each list as
/// the element's `specification` field, which replaces what was there.
pub fn parse(document: &str, map: &Map, project: &str) -> Result<BTreeMap<String, Vec<Block>>, ParseError> {
    let lines: Vec<&str> = document.lines().collect();
    let title = format!("{} {project}", "#".repeat(PROJECT_HASHES));
    let first = lines.iter().position(|line| !line.trim().is_empty());
    match first {
        Some(at) if lines[at] == title => {}
        at => {
            return Err(parse_error(
                at.map_or(1, |at| at + 1),
                format!("the document must start with the project heading '{title}'"),
            ));
        }
    }
    let start = first.expect("matched above") + 1;

    let mut sections = vec![Section { address: ROOT.to_string(), heading_line: start, body: Vec::new() }];
    let mut fence: Option<(char, usize)> = None;
    for (index, line) in lines.iter().enumerate().skip(start) {
        let line_at = index + 1;
        if let Some((mark, length)) = fence {
            if closes_fence(line, mark, length) {
                fence = None;
            }
        } else if let Some(opened) = opens_fence(line) {
            fence = Some(opened);
        } else if atx_level(line) == Some(ELEMENT_HASHES)
            && let Some(address) = heading_address(&atx_text(line))
        {
            if map.element(address).is_none() {
                return Err(parse_error(line_at, format!("'{address}' is not an element of the map; add it through intake first")));
            }
            if sections.iter().any(|section| section.address == address) {
                return Err(parse_error(line_at, format!("'{address}' has a second section")));
            }
            let expected = element_heading(map, address);
            if *line != expected {
                return Err(parse_error(line_at, format!("the heading for '{address}' must read '{expected}'; names change through intake, not through the prose")));
            }
            sections.push(Section { address: address.to_string(), heading_line: line_at, body: Vec::new() });
            continue;
        }
        sections.last_mut().expect("the root section is first").body.push((line_at, line));
    }
    if fence.is_some() {
        return Err(parse_error(lines.len(), "a code fence is opened and not closed"));
    }

    let mut out = BTreeMap::new();
    for section in sections {
        let body = strip_facts(map, &section)?;
        let blocks = read_blocks(&section.address, section.heading_line, &body)?;
        if section.address == ROOT && blocks.is_empty() && !has_blocks(map.element(ROOT).expect("a map has a root")) {
            continue;
        }
        out.insert(section.address, blocks);
    }
    Ok(out)
}

/// Remove a section's skeleton facts, and refuse a section whose facts differ from the map's.
fn strip_facts<'a>(map: &Map, section: &Section<'a>) -> Result<Vec<(usize, &'a str)>, ParseError> {
    let expected: Vec<String> = skeleton_facts(map, &section.address)
        .iter()
        .flat_map(|paragraph| paragraph.lines().map(str::to_string).collect::<Vec<_>>())
        .collect();
    let mut rest = section.body.iter().filter(|(_, line)| !line.trim().is_empty()).peekable();
    let mut consumed_to = section.heading_line;
    for fact in &expected {
        match rest.next() {
            Some((line_at, line)) if line == fact => consumed_to = *line_at,
            Some((line_at, line)) => {
                return Err(parse_error(*line_at, format!(
                    "'{}' must show its skeleton facts as the map holds them: expected '{fact}', found '{line}'. The skeleton changes through intake, not through the prose",
                    section.address
                )));
            }
            None => {
                return Err(parse_error(consumed_to, format!("'{}' is missing the skeleton fact '{fact}'", section.address)));
            }
        }
    }
    Ok(section.body.iter().filter(|(line_at, _)| *line_at > consumed_to).copied().collect())
}

/// Read a section's body, after its skeleton facts, as blocks, and check them with the layer's
/// write rules, so a document that parses can be written.
fn read_blocks(address: &str, heading_line: usize, body: &[(usize, &str)]) -> Result<Vec<Block>, ParseError> {
    struct Open<'a> {
        level: Option<u8>,
        title: Option<String>,
        text: Vec<&'a str>,
    }
    let base = container_hashes(address);
    let mut blocks = Vec::new();
    let mut open: Option<Open> = None;
    let mut fence: Option<(char, usize)> = None;
    let close = |open: Option<Open>, blocks: &mut Vec<Block>| {
        if let Some(open) = open {
            let text = open.text.join("\n").trim().to_string();
            if open.level.is_some() || !text.is_empty() {
                blocks.push(Block { level: open.level, title: open.title, text });
            }
        }
    };
    for &(line_at, line) in body {
        let heading = if fence.is_none() { atx_level(line) } else { None };
        if let Some((mark, length)) = fence {
            if closes_fence(line, mark, length) {
                fence = None;
            }
        } else if let Some(opened) = opens_fence(line) {
            fence = Some(opened);
        }
        match heading {
            Some(hashes) if hashes > base && hashes - base <= usize::from(specification::MAX_LEVEL) => {
                close(open.take(), &mut blocks);
                open = Some(Open { level: Some((hashes - base) as u8), title: Some(atx_text(line)), text: Vec::new() });
            }
            Some(hashes) => {
                let allowed = format!("{} to {}", "#".repeat(base + 1), "#".repeat(base + usize::from(specification::MAX_LEVEL)));
                let element_form = if hashes == ELEMENT_HASHES { "; an element heading ends with its address, such as (`code.api`)" } else { "" };
                return Err(parse_error(line_at, format!("a heading under '{address}' must use {allowed}{element_form}")));
            }
            None => match open.as_mut() {
                Some(open) => open.text.push(line),
                None => open = Some(Open { level: None, title: None, text: vec![line] }),
            },
        }
    }
    close(open, &mut blocks);
    let value = Value::Array(blocks.iter().map(Block::to_json).collect());
    specification::blocks(&value).map_err(|refusal| {
        parse_error(body.first().map_or(heading_line, |(line_at, _)| *line_at), format!("'{address}': {}", refusal.reason))
    })
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;

    fn map() -> Map {
        Map::from_tree(&json!({
            "specification": [
                {"text": "Packet Lab records network traffic for later study."},
                {"level": 1, "title": "Scope", "text": "Packet Lab covers capture only."},
                {"level": 2, "title": "Out of scope", "text": "Replay."}
            ],
            "code": {
                "technical_name": "code",
                "name": "Packet Lab",
                "role": "Definitive",
                "pipeline": {
                    "technical_name": "pipeline code",
                    "name": "Packet Pipeline",
                    "role": "Supportive",
                    "status": "un_built",
                    "wants": {"code.store": {"why": "Keep frames.", "how": "holds frames on disk", "direction": "outbound"}},
                    "specification": [
                        {"level": 1, "title": "Purpose", "text": "The pipeline moves frames.\n\n```text\n## not a heading (`code.x`)\n```"},
                        {"level": 2, "title": "Limits", "text": "- At most 10 Gbit/s."},
                        {"level": 1, "title": "Errors", "text": ""}
                    ]
                },
                "pipeline-tools": {"technical_name": "pipeline-tools code", "name": "Pipeline Tools", "role": "Notable"},
                "store": {"technical_name": "store code", "name": "Frame Store", "role": "Supportive"}
            },
            "upstream": {"nic": {"technical_name": "nic upstream", "name": "Network Card", "role": "Supportive"}}
        }))
        .unwrap()
    }

    /// The map with each parsed list written as its element's `specification` field.
    fn write_back(map: &Map, parsed: &BTreeMap<String, Vec<Block>>) -> Map {
        let mut elements: BTreeMap<String, Element> =
            map.elements().map(|(a, e)| (a.to_string(), e.clone())).collect();
        for (address, blocks) in parsed {
            let element = elements.get_mut(address).unwrap();
            element.fields.remove(LAYER);
            if !blocks.is_empty() {
                element.fields.insert(LAYER.into(), Value::Array(blocks.iter().map(Block::to_json).collect()));
            }
        }
        Map::from_elements(elements)
    }

    #[test]
    fn render_parse_render_gives_the_same_document() {
        let map = map();
        let first = render(&map, "packet-lab");
        let parsed = parse(&first, &map, "packet-lab").unwrap();
        let again = write_back(&map, &parsed);
        assert_eq!(again, map);
        assert_eq!(render(&again, "packet-lab"), first);
        assert!(first.starts_with("# packet-lab\n\nPacket Lab records network traffic for later study.\n\n## Scope\n\n"));
        assert!(first.contains("### Out of scope"));
        assert!(first.contains("## Packet Pipeline (`code.pipeline`)\n\nRole: Supportive. Technical name: pipeline code. Status: un_built.\n\n- `code.pipeline` (Packet Pipeline) requires `code.store` (Frame Store) in order to keep frames, which holds frames on disk.\n\n### Purpose"));
        assert!(first.contains("#### Limits"));
    }

    #[test]
    fn elements_follow_tree_order_with_scopes_in_r_3_3_order() {
        let document = render(&map(), "packet-lab");
        let at = |text: &str| document.find(text).unwrap_or_else(|| panic!("{text} missing"));
        assert!(at("(`code`)") < at("(`code.pipeline`)"));
        assert!(at("(`code.pipeline`)") < at("(`code.pipeline-tools`)"));
        assert!(at("(`code.store`)") < at("(`upstream.nic`)"));
    }

    #[test]
    fn an_edited_document_parses_into_new_blocks() {
        let map = map();
        let edited = render(&map, "packet-lab").replace(
            "### Purpose\n\nThe pipeline moves frames.",
            "### Purpose\n\nThe pipeline moves frames from the card to the store.",
        );
        let parsed = parse(&edited, &map, "packet-lab").unwrap();
        assert_eq!(parsed["code.pipeline"][0].text.lines().next(), Some("The pipeline moves frames from the card to the store."));
        assert_eq!(parsed["code.store"], Vec::<Block>::new());
    }

    #[test]
    fn parse_refuses_a_stale_or_foreign_document() {
        let map = map();
        let document = render(&map, "packet-lab");
        let cases = [
            (document.replace("Role: Supportive. Technical name: pipeline code", "Role: Notable. Technical name: pipeline code"), "skeleton facts"),
            (format!("{document}\n## Ghost (`code.ghost`)\n"), "not an element"),
            (document.replace("## Frame Store (`code.store`)", "## Store (`code.store`)"), "must read"),
            (document.replace("#### Limits", "##### Limits"), "skips a heading level"),
            (document.replace("# packet-lab", "# other"), "project heading"),
            (format!("{document}\n## Loose heading\n"), "element heading ends with its address"),
        ];
        for (text, expected) in cases {
            let error = parse(&text, &map, "packet-lab").unwrap_err();
            assert!(error.reason.contains(expected), "expected '{expected}': {error}");
        }
    }
}
