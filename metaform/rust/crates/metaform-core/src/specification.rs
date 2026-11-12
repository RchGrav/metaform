//! Layers defined in the map, and the specification layer (R-6.24 to R-6.28).
//!
//! Every layer works the same way (owner decision, 2026-11-09). A layer is defined by an element
//! beneath the `layer` root scope that has an `instruction` field. Its data sits on the receiving
//! elements as a field named after the definition's last segment, as a list of records:
//! `layer.document.specification` defines the field `specification`. Every defined layer follows
//! the same rules: records only on skeleton elements (R-3.20), listed by `goto` with the
//! definition's instruction, and read by naming the layer.
//!
//! A definition may declare `format: "markdown_blocks"`. Its records are then blocks of prose,
//! `{"level": 1-4, "title": "...", "text": "..."}`, and the first block may be `{"text": "..."}`
//! alone, an intro with no heading. Levels are relative to the element's own heading in the
//! export, so the same rule holds at every address, and the tool enforces them so the prose can
//! be exported as Markdown and imported again without loss. The tool refuses only what would
//! break that round trip or put records before the skeleton; the TASTE targets are reported by
//! `metaform specification export --check`, not refused (R-5.20, TASTE rule 4).
//!
//! The specification layer is one such layer: prose that the skeleton leaves out on purpose.

use serde_json::{Map as JsonMap, Value, json};

use crate::model::{Element, Fields, Map};
use crate::names::{ROOT, ROOT_SCOPES};
use crate::reads::is_project_defining;
use crate::refusal::{Code, Refusal};

/// The system layers (R-6.15): defined in code, shared by every project, written by agents at an
/// address without a definition in the map.
pub const SYSTEM_LAYERS: [&str; 3] = ["skills", "memory", "sources"];

/// The root scope that holds layer definitions (R-3.3, R-6.24).
pub const LAYER_SCOPE: &str = "layer";

/// The specification layer's field name at a receiving element.
pub const LAYER: &str = "specification";

/// Where the specification layer is defined in each main map. Its last segment is `LAYER`.
pub const DEFINITION_ADDRESS: &str = "layer.document.specification";

/// The record format whose records are Markdown blocks with enforced heading levels.
pub const MARKDOWN_BLOCKS: &str = "markdown_blocks";

/// The deepest relative level. Element headings are `##` in the export, so level 4 is `######`,
/// the deepest Markdown heading (R-6.25).
pub const MAX_LEVEL: u8 = 4;

/// The specification layer's writing guidance: the short form of `TASTE.md` prepared for this
/// layer by the TASTE auditor (metaform-38), used as written.
pub const INSTRUCTION: &str = "Write each block in TASTE: Technically Accurate, Simple, Transparent English. A block adds what the map leaves out on purpose; do not repeat what the element's fields and dependencies already say.
- Start with what the element does or holds. Then give the detail that explains it.
- Name the element, field or command instead of starting with \"it\", \"this\" or \"they\". A block is often read alone.
- Use the project's terms and exact identifiers. Use one term for one thing. Put identifiers in backticks.
- Write one claim per sentence. Aim for 25 words or fewer per sentence and six sentences or fewer per paragraph. Never cut a condition, an exception or a reason to meet a length target.
- Use lowercase must, should, may, can and might with their TASTE meanings. Do not write SHALL or capitalized MUST.
- Say whether something is built, proposed or planned. Do not describe planned behavior as if it exists.
- Replace words such as simple, robust or fast with the behavior or a measurement.
- Define an abbreviation at its first use. Keep noun clusters to three nouns.
- Leave out openings such as \"This section describes\", repeated points, analogies and promotion.
- Prefer start, use, adjust, perform and end over kick off/launch/begin, utilize/leverage, modify/change/alter, execute/run and terminate/stop/abort, when the meaning stays the same.
- Do not put Markdown heading lines in the text. Set the block's level and title instead.";

/// How records of the `markdown_blocks` format are written through the tool (R-6.25, R-6.26).
/// `goto` delivers it before the definition's own instruction. `{layer}` is the field name.
const MARKDOWN_FORM: &str = "The {layer} field is a list of blocks: {\"level\": 1-4, \"title\": \"...\", \"text\": \"...\"}. A titled block may also carry \"code\", a key that other text can cite; it is unique in the layer across the map, ignoring case. The first block may be {\"text\": \"...\"} alone, as an intro under the element's heading. The first titled block is level 1, and each level is at most one more than the level before it. update replaces every block at the address and is safe to repeat; add appends blocks; if an answer is lost, a retried add appends them twice. Read them with {\"<address>\": {\"{layer}\": {}}}. The root's blocks are in the raw dump {\".\": {}}, because a key that starts with a period is a raw dump. Blocks are accepted at an element that has technical_name, name and role, and at . once the map has a Definitive element.";

/// The fields of the specification layer's definition element at `DEFINITION_ADDRESS`. The store
/// writes it into each main map, so the export and `goto` always find the layer (R-6.24).
pub fn definition() -> Fields {
    let mut fields = Fields::new();
    for (key, value) in [
        ("technical_name", "specification document layer"),
        ("name", "Specification"),
        ("role", "SE"),
        (
            "description",
            "Prose that the skeleton leaves out on purpose: what each element does, how it behaves and why, as blocks with Markdown heading levels.",
        ),
        ("template", "{title}: {text}"),
        ("format", MARKDOWN_BLOCKS),
        ("instruction", INSTRUCTION),
    ] {
        fields.insert(key.into(), Value::String(value.into()));
    }
    fields
}

/// One layer definition found in the map.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Definition {
    /// The field name at receiving elements: the definition's last address segment.
    pub layer: String,
    /// The definition element's address.
    pub address: String,
    /// The record format, such as `markdown_blocks`, if the definition declares one.
    pub format: Option<String>,
    /// The writing guidance for the layer.
    pub instruction: String,
}

impl Definition {
    /// The guidance `goto` delivers: the format's rules, then the definition's own instruction.
    pub fn guidance(&self) -> String {
        match self.format.as_deref() {
            Some(MARKDOWN_BLOCKS) => format!(
                "{}\n{}",
                MARKDOWN_FORM.replace("{layer}", &self.layer),
                self.instruction
            ),
            _ => self.instruction.clone(),
        }
    }
}

/// Every layer defined in the map, by field name. A write cannot create two definitions with the
/// same last segment; if stored data has them, the definition whose address sorts first wins.
pub fn definitions(map: &Map) -> Vec<Definition> {
    let mut out: Vec<Definition> = Vec::new();
    for (address, element) in map.elements() {
        if !is_beneath_layer_scope(address) {
            continue;
        }
        let Some(instruction) = element.fields.get("instruction").and_then(Value::as_str) else {
            continue;
        };
        let layer = address.rsplit('.').next().unwrap_or_default().to_string();
        if out.iter().any(|d| d.layer == layer) {
            continue;
        }
        out.push(Definition {
            layer,
            address: address.to_string(),
            format: element
                .fields
                .get("format")
                .and_then(Value::as_str)
                .map(str::to_string),
            instruction: instruction.to_string(),
        });
    }
    out
}

/// The definition of one layer, if the map defines it.
pub fn definition_of(map: &Map, layer: &str) -> Option<Definition> {
    definitions(map).into_iter().find(|d| d.layer == layer)
}

/// Whether an address is the `layer` root scope or beneath it, where layer definitions live,
/// outside the functional skeleton (R-3.20).
pub fn in_layer_scope(address: &str) -> bool {
    address == LAYER_SCOPE || is_beneath_layer_scope(address)
}

fn is_beneath_layer_scope(address: &str) -> bool {
    address
        .strip_prefix(LAYER_SCOPE)
        .is_some_and(|rest| rest.starts_with('.'))
}

/// One block of a `markdown_blocks` layer.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Block {
    /// The relative heading level, 1 to `MAX_LEVEL`. `None` only for an intro block.
    pub level: Option<u8>,
    /// The heading text. `None` only for an intro block.
    pub title: Option<String>,
    /// Markdown body text, with no heading lines. Stored with LF line ends and trimmed.
    pub text: String,
    /// An optional key that other text can cite, unique within the layer across the whole map,
    /// ignoring case (owner decision, 2026-11-09). Only a titled block has one.
    pub code: Option<String>,
}

impl Block {
    /// A block with a heading.
    pub fn titled(level: u8, title: &str, text: &str) -> Block {
        Block {
            level: Some(level),
            title: Some(title.to_string()),
            text: text.to_string(),
            code: None,
        }
    }

    /// The block with a key.
    pub fn with_code(mut self, code: &str) -> Block {
        self.code = Some(code.to_string());
        self
    }

    /// An intro block: text under the element's heading, before any block heading.
    pub fn intro(text: &str) -> Block {
        Block {
            level: None,
            title: None,
            text: text.to_string(),
            code: None,
        }
    }

    pub fn is_intro(&self) -> bool {
        self.title.is_none()
    }

    /// The block as the tool stores and returns it.
    pub fn to_json(&self) -> Value {
        match (&self.level, &self.title) {
            (Some(level), Some(title)) => {
                let mut out = JsonMap::new();
                out.insert("level".into(), json!(level));
                if let Some(code) = &self.code {
                    out.insert("code".into(), Value::String(code.clone()));
                }
                out.insert("title".into(), Value::String(title.clone()));
                out.insert("text".into(), Value::String(self.text.clone()));
                Value::Object(out)
            }
            _ => json!({"text": self.text}),
        }
    }
}

/// The blocks as the tool stores them.
pub fn to_json(blocks: &[Block]) -> Value {
    Value::Array(blocks.iter().map(Block::to_json).collect())
}

/// An element is part of the skeleton when intake has given it every mandatory field (R-3.4):
/// `technical_name`, `name` and `role`. Only then may it hold layer records (R-6.26).
pub fn is_skeleton(element: &Element) -> bool {
    ["technical_name", "name", "role"].iter().all(|key| {
        element
            .fields
            .get(*key)
            .and_then(Value::as_str)
            .is_some_and(|text| !text.trim().is_empty())
    })
}

/// Whether layer records may sit at an address: a skeleton element outside the `layer` scope, or
/// the root once the map has a Defining Element (R-6.26). This holds for every defined layer.
pub fn records_allowed(map: &Map, address: &str) -> bool {
    if address == ROOT {
        map.elements()
            .any(|(at, element)| is_project_defining(at, element.fields.get("role")))
    } else {
        address != LAYER_SCOPE
            && !is_beneath_layer_scope(address)
            && map.element(address).is_some_and(is_skeleton)
    }
}

/// Whether the specification layer applies at an address: the map defines it, and records are
/// allowed there.
pub fn applies(map: &Map, address: &str) -> bool {
    definition_of(map, LAYER).is_some() && records_allowed(map, address)
}

/// The export's element order (R-6.28): root scopes in R-3.3's order, then a pre-order walk of the
/// tree. Comparing segment lists keeps every child right after its parent, which a plain string
/// sort does not (`a-b` sorts between `a` and `a.b`). The root sorts first.
pub fn scope_order(address: &str) -> (usize, Vec<String>) {
    if address == ROOT {
        return (0, Vec::new());
    }
    let segments: Vec<String> = address.split('.').map(str::to_string).collect();
    let scope = ROOT_SCOPES
        .iter()
        .position(|scope| *scope == segments[0])
        .map_or(ROOT_SCOPES.len() + 1, |i| i + 1);
    (scope, segments)
}

/// The kind of heading line found in block text.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum HeadingLine {
    /// A line such as `## Title`.
    Atx,
    /// A line of `=` or `-` directly under a paragraph line, which turns that line into a heading.
    Setext,
}

/// The first Markdown heading line in `text` outside fenced code, as a 0-based line index and its
/// kind. For a setext heading the index is the underline's; the heading text is the line before.
pub fn heading_in_text(text: &str) -> Option<(usize, HeadingLine)> {
    let mut fence: Option<(char, usize)> = None;
    let mut previous: Option<&str> = None;
    for (index, line) in text.lines().enumerate() {
        let indent = line.len() - line.trim_start_matches(' ').len();
        let body = &line[indent.min(line.len())..];
        if indent <= 3
            && let Some((mark, run)) = fence_mark(body)
        {
            match fence {
                None => fence = Some((mark, run)),
                Some((open, length))
                    if open == mark
                        && run >= length
                        && body.trim_end().chars().all(|c| c == mark) =>
                {
                    fence = None
                }
                Some(_) => {}
            }
            previous = None;
            continue;
        }
        if fence.is_some() {
            continue;
        }
        if indent <= 3 && is_atx(body) {
            return Some((index, HeadingLine::Atx));
        }
        if indent <= 3 && is_underline(body) && previous.is_some_and(is_paragraph_line) {
            return Some((index, HeadingLine::Setext));
        }
        previous = Some(line);
    }
    None
}

/// A fence opener or closer: three or more backticks or tildes.
fn fence_mark(body: &str) -> Option<(char, usize)> {
    let mark = body.chars().next().filter(|c| *c == '`' || *c == '~')?;
    let run = body.chars().take_while(|c| *c == mark).count();
    (run >= 3).then_some((mark, run))
}

fn is_atx(body: &str) -> bool {
    let hashes = body.chars().take_while(|c| *c == '#').count();
    (1..=6).contains(&hashes)
        && body[hashes..]
            .chars()
            .next()
            .is_none_or(|c| c == ' ' || c == '\t')
}

fn is_underline(body: &str) -> bool {
    let body = body.trim_end();
    !body.is_empty() && (body.chars().all(|c| c == '=') || body.chars().all(|c| c == '-'))
}

/// A line that a setext underline would turn into a heading: non-blank, not indented as code, and
/// not a list item, table row or heading.
fn is_paragraph_line(line: &str) -> bool {
    let indent = line.len() - line.trim_start_matches(' ').len();
    let body = line.trim();
    if body.is_empty()
        || indent > 3
        || body.starts_with('|')
        || body.starts_with('>')
        || is_atx(body)
    {
        return false;
    }
    let list = body.starts_with("- ") || body.starts_with("* ") || body.starts_with("+ ") || {
        let digits = body.chars().take_while(char::is_ascii_digit).count();
        digits > 0 && (body[digits..].starts_with(". ") || body[digits..].starts_with(") "))
    };
    !list
}

/// Whether a title has the form the export reserves for element headings: it ends with an address
/// in backticks inside parentheses, such as "Name (`code.engine`)".
pub fn is_element_heading_form(title: &str) -> bool {
    let title = title.trim_end();
    title.ends_with("`)") && title.contains("(`")
}

/// An example of valid blocks, given as the remediation of a malformed block.
fn example(layer: &str, address: &str) -> Value {
    json!({"update": {address: {layer: [
        {"text": "<intro prose, optional>"},
        {"level": 1, "title": "<heading>", "text": "<prose>"},
        {"level": 2, "title": "<subheading>", "text": "<prose>"}
    ]}}})
}

/// Read and normalize the blocks of a `specification` value (see `blocks_of`).
pub fn blocks(address: &str, value: &Value) -> Result<Vec<Block>, Refusal> {
    blocks_of(LAYER, address, value)
}

/// Read and normalize the blocks of a `markdown_blocks` layer value. The value must be a list;
/// each block must have the block shape. Line ends become LF and title and text are trimmed, so
/// the stored form is the form the export writes and the import reads back.
pub fn blocks_of(layer: &str, address: &str, value: &Value) -> Result<Vec<Block>, Refusal> {
    let mismatch = |why: String| {
        Refusal::new(
            Code::FieldMismatch,
            format!("'{address}': {layer}: {why}"),
            Some(example(layer, address)),
        )
    };
    let Value::Array(items) = value else {
        return Err(mismatch("must be a list of blocks".into()));
    };
    let mut out = Vec::with_capacity(items.len());
    for (index, item) in items.iter().enumerate() {
        let n = index + 1;
        let Value::Object(object) = item else {
            return Err(mismatch(format!("block {n} must be an object")));
        };
        if let Some(key) = object
            .keys()
            .find(|key| !["level", "title", "text", "code"].contains(&key.as_str()))
        {
            return Err(mismatch(format!("block {n} does not take: {key}")));
        }
        let text = match object.get("text") {
            None => String::new(),
            Some(Value::String(text)) => normalize(text),
            Some(_) => return Err(mismatch(format!("block {n}: text must be a string"))),
        };
        let title = match object.get("title") {
            None => None,
            Some(Value::String(title)) => Some(normalize(title)),
            Some(_) => return Err(mismatch(format!("block {n}: title must be a string"))),
        };
        let level = match object.get("level") {
            None => None,
            Some(level) => match level.as_u64() {
                Some(level) => Some(level),
                None => {
                    return Err(mismatch(format!(
                        "block {n}: level must be a whole number from 1 to {MAX_LEVEL}"
                    )));
                }
            },
        };
        let code = match object.get("code") {
            None => None,
            Some(Value::String(code)) if is_code(code) => Some(code.clone()),
            Some(_) => {
                return Err(mismatch(format!(
                    "block {n}: code must be one token of 1 to 32 letters, digits, '.', '_' or '-', starting with a letter and ending with a letter or digit, such as R-1.2"
                )));
            }
        };
        if code.is_some() && title.is_none() {
            return Err(mismatch(format!(
                "block {n}: only a block with a level and title can have a code"
            )));
        }
        match (level, title) {
            (None, None) => {
                if index > 0 {
                    return Err(mismatch(format!(
                        "block {n} has no level and title; only the first block may be an intro"
                    )));
                }
                if text.is_empty() {
                    return Err(mismatch("block 1 is an intro with no text".into()));
                }
                out.push(Block::intro(&text));
            }
            (Some(level), Some(title)) => {
                if title.is_empty() || title.contains('\n') {
                    return Err(mismatch(format!(
                        "block {n}: title must be one line of text"
                    )));
                }
                if title.starts_with('`') {
                    return Err(mismatch(format!(
                        "block {n}: title must not start with a backtick; the export writes the block's code there"
                    )));
                }
                if title.starts_with('#') {
                    return Err(mismatch(format!(
                        "block {n}: title must not start with '#'; the level sets the heading"
                    )));
                }
                if is_element_heading_form(&title) {
                    return Err(mismatch(format!(
                        "block {n}: title must not end with an address in backticks inside parentheses; the export uses that form for element headings"
                    )));
                }
                let level = u8::try_from(level).unwrap_or(u8::MAX);
                out.push(Block {
                    level: Some(level),
                    title: Some(title),
                    text,
                    code,
                });
            }
            _ => {
                return Err(mismatch(format!(
                    "block {n} needs both level and title, or neither for an intro"
                )));
            }
        }
    }
    Ok(out)
}

/// A block code: a letter, then up to 31 letters, digits, `.`, `_` or `-`, ending with a letter or
/// digit. It has no spaces or backticks, so it survives the Markdown export.
pub fn is_code(code: &str) -> bool {
    let bytes = code.as_bytes();
    (1..=32).contains(&bytes.len())
        && bytes[0].is_ascii_alphabetic()
        && bytes[bytes.len() - 1].is_ascii_alphanumeric()
        && bytes
            .iter()
            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'.' | b'_' | b'-'))
}

/// Refuse a code in `blocks` (just written at `address`) that another block of the same layer
/// already holds, anywhere in the map after the write, ignoring case. The remediation is the
/// same update with that block's code removed.
pub fn check_codes(map: &Map, address: &str, layer: &str, blocks: &[Block]) -> Result<(), Refusal> {
    let mut held: Vec<(String, String, usize)> = Vec::new();
    for (holder, element) in map.elements() {
        if holder == address {
            continue;
        }
        // Read codes from the stored JSON, not parsed blocks, so a holder whose blocks predate
        // the rules still counts.
        let stored = element.fields.get(layer).and_then(Value::as_array);
        for (index, record) in stored.into_iter().flatten().enumerate() {
            if let Some(code) = record.get("code").and_then(Value::as_str) {
                held.push((code.to_ascii_lowercase(), holder.to_string(), index + 1));
            }
        }
    }
    for (index, block) in blocks.iter().enumerate() {
        let Some(code) = &block.code else { continue };
        let key = code.to_ascii_lowercase();
        let earlier = blocks[..index]
            .iter()
            .position(|b| {
                b.code
                    .as_ref()
                    .is_some_and(|c| c.to_ascii_lowercase() == key)
            })
            .map(|i| (address.to_string(), i + 1));
        let elsewhere = held
            .iter()
            .find(|(k, _, _)| *k == key)
            .map(|(_, holder, n)| (holder.clone(), *n));
        if let Some((holder, n)) = earlier.or(elsewhere) {
            let mut fixed = blocks.to_vec();
            fixed[index].code = None;
            return Err(Refusal::new(
                Code::CodeNotUnique,
                format!(
                    "'{address}': {layer} block {} has code {code}, which '{holder}' block {n} already holds; a code is unique in the {layer} layer, ignoring case",
                    index + 1
                ),
                Some(json!({"update": {address: {layer: to_json(&fixed)}}})),
            ));
        }
    }
    Ok(())
}

fn normalize(text: &str) -> String {
    text.replace("\r\n", "\n")
        .replace('\r', "\n")
        .trim()
        .to_string()
}

/// The blocks with each level brought into the rules: the first titled block at 1, each next block
/// at most one deeper, and none beyond `MAX_LEVEL`.
fn clamp_levels(blocks: &[Block]) -> Vec<Block> {
    let mut previous = 0u8;
    blocks
        .iter()
        .map(|block| {
            let mut block = block.clone();
            if let Some(level) = block.level {
                let fixed = level.clamp(1, (previous + 1).min(MAX_LEVEL));
                block.level = Some(fixed);
                previous = fixed;
            }
            block
        })
        .collect()
}

/// The blocks with each heading line in a text moved out into a block of its own, one level
/// deeper than the block it was in. This is the remediation for `HEADING_IN_TEXT`.
fn split_headings(blocks: &[Block]) -> Vec<Block> {
    let mut out = Vec::new();
    for block in blocks {
        let mut rest = block.clone();
        loop {
            let Some((index, kind)) = heading_in_text(&rest.text) else {
                out.push(rest);
                break;
            };
            let source = rest.text.clone();
            let lines: Vec<&str> = source.lines().collect();
            let (title_line, body_from) = match kind {
                HeadingLine::Atx => (index, index + 1),
                HeadingLine::Setext => (index - 1, index + 1),
            };
            let title = lines[title_line]
                .trim()
                .trim_start_matches('#')
                .trim()
                .trim_end_matches('#')
                .trim();
            let level = rest.level.map_or(1, |level| (level + 1).min(MAX_LEVEL));
            let before = lines[..title_line].join("\n").trim().to_string();
            let after = lines[body_from..].join("\n").trim().to_string();
            rest.text = before;
            if !(rest.is_intro() && rest.text.is_empty()) {
                out.push(rest);
            }
            let title = if title.is_empty() {
                "<heading>".to_string()
            } else {
                title.to_string()
            };
            rest = Block::titled(level, &title, &after);
        }
    }
    clamp_levels(&out)
}

/// The refusal for a layer value that is not a list. The remediation is the same write with the
/// value as the one record of a list.
pub(crate) fn not_a_list(verb: &str, layer: &str, address: &str, value: &Value) -> Refusal {
    Refusal::new(
        Code::FieldMismatch,
        format!("'{address}': {layer}: a layer's value must be a list of records"),
        Some(json!({verb: {address: {layer: [value]}}})),
    )
}

/// The records of any defined layer: the value must be a list (R-6.24).
pub fn records<'v>(layer: &str, address: &str, value: &'v Value) -> Result<&'v [Value], Refusal> {
    value
        .as_array()
        .map(Vec::as_slice)
        .ok_or_else(|| not_a_list("update", layer, address, value))
}

/// Refuse records of any layer at an address where records are not allowed (R-6.26). `map` is
/// the map after the write.
pub fn check_allowed(map: &Map, address: &str, layer: &str) -> Result<(), Refusal> {
    if !records_allowed(map, address) {
        // No command lets a layer definition hold records, so that refusal has no remediation.
        let remediation = if address == ROOT {
            Some(json!({"update": {"<address of a Defining Element>": {"role": "DE"}}}))
        } else if in_layer_scope(address) {
            None
        } else {
            let element = map.element(address);
            let mut fix = JsonMap::new();
            for key in ["technical_name", "name", "role"] {
                let present = element
                    .and_then(|e| e.fields.get(key))
                    .and_then(Value::as_str)
                    .is_some_and(|t| !t.trim().is_empty());
                if !present {
                    fix.insert(key.into(), json!(format!("<{key}>")));
                }
            }
            Some(json!({"update": {address: fix}}))
        };
        let reason = if address == ROOT {
            format!("'.': {layer} records at the root need a Defining Element (role DE) in the map first")
        } else if in_layer_scope(address) {
            format!("'{address}': {layer} records do not go on layer definitions")
        } else {
            format!(
                "'{address}': {layer} records need an element with technical_name, name and role; intake has not placed it in the skeleton yet"
            )
        };
        return Err(Refusal::new(
            Code::ElementNotInSkeleton,
            reason,
            remediation,
        ));
    }
    Ok(())
}

/// Check the blocks of a `markdown_blocks` layer written at an address (R-6.25).
pub fn check_blocks(address: &str, layer: &str, blocks: &[Block]) -> Result<(), Refusal> {
    let mut previous = 0u8;
    for (index, block) in blocks.iter().enumerate() {
        let Some(level) = block.level else { continue };
        let allowed = (previous + 1).min(MAX_LEVEL);
        if level < 1 || level > allowed {
            let why = if !(1..=MAX_LEVEL).contains(&level) {
                format!("level {level} is outside 1 to {MAX_LEVEL}")
            } else if previous == 0 {
                format!("level {level}; the first titled block is level 1")
            } else {
                format!(
                    "level {level} follows level {previous}; a level is at most one more than the level before it"
                )
            };
            return Err(Refusal::new(
                Code::HeadingLevelInvalid,
                format!(
                    "'{address}': {layer} block {} (\"{}\"): {why}",
                    index + 1,
                    block.title.as_deref().unwrap_or_default()
                ),
                Some(json!({"update": {address: {layer: to_json(&clamp_levels(blocks))}}})),
            ));
        }
        previous = level;
    }
    for (index, block) in blocks.iter().enumerate() {
        if let Some((line, kind)) = heading_in_text(&block.text) {
            let what = match kind {
                HeadingLine::Atx => "a Markdown heading line",
                HeadingLine::Setext => {
                    "a line of = or - under a paragraph line, which Markdown reads as a heading"
                }
            };
            return Err(Refusal::new(
                Code::HeadingInText,
                format!(
                    "'{address}': {layer} block {}: text line {} is {what}; set a block's level and title instead",
                    index + 1,
                    line + 1
                ),
                Some(json!({"update": {address: {layer: to_json(&split_headings(blocks))}}})),
            ));
        }
    }
    Ok(())
}

/// The blocks stored at an element, read leniently: stored data passed `blocks` when written.
pub fn stored(element: &Element) -> Vec<Block> {
    element
        .fields
        .get(LAYER)
        .and_then(|value| blocks("", value).ok())
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn finds_atx_and_setext_headings_outside_fences() {
        assert_eq!(heading_in_text("one\n## two"), Some((1, HeadingLine::Atx)));
        assert_eq!(heading_in_text("one\n---"), Some((1, HeadingLine::Setext)));
        assert_eq!(
            heading_in_text("one\n\n---"),
            None,
            "a rule after a blank line is not a heading"
        );
        assert_eq!(
            heading_in_text("- item\n---"),
            None,
            "a rule after a list item is not a heading"
        );
        assert_eq!(heading_in_text("```\n# comment\n```"), None);
        assert_eq!(heading_in_text("~~~~\n```\n# still code\n~~~~\n#tag"), None);
        assert_eq!(heading_in_text("#hashtag and #42"), None);
        assert_eq!(heading_in_text("    # indented code"), None);
    }

    #[test]
    fn splits_a_heading_out_of_text() {
        let blocks = [Block::titled(
            1,
            "Writes",
            "Intro.\n### Retry\nAfter a lost answer.",
        )];
        assert_eq!(
            split_headings(&blocks),
            vec![
                Block::titled(1, "Writes", "Intro."),
                Block::titled(2, "Retry", "After a lost answer.")
            ]
        );
    }

    #[test]
    fn clamps_levels() {
        let blocks = [
            Block::titled(2, "a", ""),
            Block::titled(4, "b", ""),
            Block::titled(9, "c", ""),
        ];
        let levels: Vec<_> = clamp_levels(&blocks).iter().map(|b| b.level).collect();
        assert_eq!(levels, [Some(1), Some(2), Some(3)]);
    }

    #[test]
    fn orders_children_after_parents() {
        let mut addresses = vec![
            "downstream.x",
            "code.a.b",
            "code.a-b",
            "code.a",
            ".",
            "document.d",
        ];
        addresses.sort_by_key(|a| scope_order(a));
        assert_eq!(
            addresses,
            [
                ".",
                "code.a",
                "code.a.b",
                "code.a-b",
                "document.d",
                "downstream.x"
            ]
        );
    }
}
