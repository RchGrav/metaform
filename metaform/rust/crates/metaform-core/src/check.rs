//! `metaform specification export --check`: TASTE reports on the specification layer's text.
//! The rules and their wording are the proposal in `metaform/docs/designs/specification-layer.md`.
//! A report asks for a judgement; it is not an error, because TASTE treats length and wording as
//! conditional targets. The tool itself refuses only what breaks export and import.
//!
//! What the check reads: block text, and titles for `BLACKLIST` and `CAPITAL_MODAL` only. It skips
//! inline code spans, fenced code, URLs and table rows. Text in double quotation marks is skipped
//! by the word checks (`CAPITAL_MODAL`, `SHALL`, `BLACKLIST`, `VAGUE_WORD`, `OPENING`) but still
//! counts toward sentence length.

use std::collections::{BTreeMap, BTreeSet};


use crate::markdown::{closes_fence, document_addresses, opens_fence};
use crate::model::Map;
use crate::specification::{self, Block, LAYER};

/// The check codes, in the order the summary lists them.
pub const CODES: [&str; 11] = [
    "CAPITAL_MODAL",
    "SHALL",
    "SENTENCE_LENGTH",
    "PARAGRAPH_LENGTH",
    "BLACKLIST",
    "VAGUE_WORD",
    "OPENING",
    "START_PRONOUN",
    "ABBREVIATION",
    "REPEATED_SENTENCE",
    "EMPTY_SECTION",
];

const SENTENCE_WORDS: usize = 25;
const PARAGRAPH_SENTENCES: usize = 6;
const REPEAT_MIN_WORDS: usize = 6;

/// Capital modals that lowercase fixes. A capital SHALL gets the `SHALL` report instead, because
/// lowercase "shall" is still not a TASTE modal.
const CAPITAL_MODALS: [&str; 4] = ["MUST", "SHOULD", "MAY", "REQUIRED"];

/// The project blacklist (TASTE.md): the words to avoid and the preferred term.
const BLACKLIST: [(&str, &str); 16] = [
    ("launch", "start"),
    ("initiate", "start"),
    ("begin", "start"),
    ("utilize", "use"),
    ("leverage", "use"),
    ("modify", "adjust"),
    ("tweak", "adjust"),
    ("change", "adjust"),
    ("alter", "adjust"),
    ("execute", "perform"),
    ("run", "perform"),
    ("fulfill", "perform"),
    ("terminate", "end"),
    ("kill", "end"),
    ("stop", "end"),
    ("abort", "end"),
];

/// Irregular forms of blacklisted words.
const IRREGULAR: [(&str, &str); 3] = [("ran", "run"), ("began", "begin"), ("begun", "begin")];

const VAGUE: [&str; 15] = [
    "simple", "simply", "easy", "easily", "robust", "clean", "seamless", "seamlessly", "powerful",
    "intuitive", "efficient", "fast", "flexible", "elegant", "best",
];

const OPENINGS: [&str; 8] = [
    "This section",
    "This block",
    "In this section",
    "Note that",
    "It is important",
    "It should be noted",
    "As mentioned",
    "Basically",
];

const DEMONSTRATIVES: [&str; 4] = ["This", "That", "These", "Those"];
const PRONOUN_VERBS: [&str; 11] = [
    "is", "are", "was", "were", "means", "lets", "allows", "makes", "has", "have", "does",
];

const KNOWN_ABBREVIATIONS: [&str; 11] = [
    "JSON", "CLI", "MCP", "URL", "HTTP", "API", "ID", "UI", "OS", "CI", "TASTE",
];

/// Words that end a sentence-like token without ending the sentence.
const NOT_SENTENCE_ENDS: [&str; 4] = ["e.g.", "i.e.", "etc.", "vs."];

/// One report.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Report {
    pub address: String,
    /// The block's position within its element, from 1.
    pub block: usize,
    pub title: Option<String>,
    pub code: &'static str,
    pub message: String,
}

impl Report {
    /// `<address> block <n> ("<title>"): <CODE>: <message>`
    pub fn line(&self) -> String {
        let title = self
            .title
            .as_ref()
            .map_or(String::new(), |title| format!(" (\"{title}\")"));
        format!("{} block {}{title}: {}: {}", self.address, self.block, self.code, self.message)
    }
}

/// The line after the reports.
pub fn summary(reports: &[Report]) -> String {
    if reports.is_empty() {
        return "check: no reports.".into();
    }
    let blocks: BTreeSet<(&str, usize)> = reports.iter().map(|r| (r.address.as_str(), r.block)).collect();
    let counts: Vec<String> = CODES
        .iter()
        .filter_map(|code| {
            let n = reports.iter().filter(|r| r.code == *code).count();
            (n > 0).then(|| format!("{code} {n}"))
        })
        .collect();
    let plural = |n: usize, word: &str| format!("{n} {word}{}", if n == 1 { "" } else { "s" });
    format!(
        "check: {} in {} ({}). Reports are TASTE targets, not errors.",
        plural(reports.len(), "report"),
        plural(blocks.len(), "block"),
        counts.join(", ")
    )
}

// ---- Reading text ----

/// A word: the token as written, and whether it lies inside double quotation marks.
#[derive(Clone, Debug)]
struct Word {
    text: String,
    quoted: bool,
}

impl Word {
    /// The word without surrounding punctuation.
    fn bare(&self) -> &str {
        self.text.trim_matches(|c: char| !c.is_alphanumeric())
    }
}

#[derive(Clone, Debug, Default)]
struct Sentence {
    words: Vec<Word>,
}

impl Sentence {
    fn normalized(&self) -> String {
        self.words.iter().map(|w| w.text.to_lowercase()).collect::<Vec<_>>().join(" ")
    }
}

#[derive(Clone, Debug, Default)]
struct Paragraph {
    sentences: Vec<Sentence>,
}

/// Replace inline code spans with one placeholder word, and URLs with another.
fn mask_code_and_urls(line: &str) -> String {
    let mut out = String::new();
    let chars: Vec<char> = line.chars().collect();
    let mut i = 0;
    while i < chars.len() {
        if chars[i] == '`' {
            let run = chars[i..].iter().take_while(|c| **c == '`').count();
            let mut j = i + run;
            let mut closed = None;
            while j < chars.len() {
                if chars[j] == '`' {
                    let other = chars[j..].iter().take_while(|c| **c == '`').count();
                    if other == run {
                        closed = Some(j + other);
                        break;
                    }
                    j += other;
                } else {
                    j += 1;
                }
            }
            if let Some(end) = closed {
                out.push_str("codespan");
                i = end;
                continue;
            }
            out.extend(&chars[i..i + run]);
            i += run;
            continue;
        }
        out.push(chars[i]);
        i += 1;
    }
    out.split(' ')
        .map(|token| {
            let bare = token.trim_start_matches(['(', '<', '[']);
            if bare.starts_with("http://") || bare.starts_with("https://") {
                "url"
            } else {
                token
            }
        })
        .collect::<Vec<_>>()
        .join(" ")
}

fn is_list_item(line: &str) -> bool {
    let trimmed = line.trim_start();
    let bullet = ["- ", "* ", "+ "].iter().any(|m| trimmed.starts_with(m));
    let digits = trimmed.chars().take_while(char::is_ascii_digit).count();
    let numbered = digits > 0 && matches!(trimmed[digits..].chars().next(), Some('.' | ')'))
        && trimmed[digits + 1..].starts_with(' ');
    bullet || numbered
}

/// The text's paragraphs, after removing fenced code and table rows. A list is one paragraph,
/// and each list item is at least one sentence.
fn paragraphs(text: &str) -> Vec<Paragraph> {
    let mut groups: Vec<Vec<Vec<String>>> = Vec::new(); // paragraph -> items -> lines
    let mut current: Vec<Vec<String>> = Vec::new();
    let mut fence: Option<(char, usize)> = None;
    let flush = |current: &mut Vec<Vec<String>>, groups: &mut Vec<Vec<Vec<String>>>| {
        if !current.is_empty() {
            groups.push(std::mem::take(current));
        }
    };
    for line in text.lines() {
        if let Some((mark, length)) = fence {
            if closes_fence(line, mark, length) {
                fence = None;
            }
            continue;
        }
        if let Some(opened) = opens_fence(line) {
            fence = Some(opened);
            continue;
        }
        if line.trim().is_empty() {
            flush(&mut current, &mut groups);
            continue;
        }
        if line.trim_start().starts_with('|') {
            continue;
        }
        let masked = mask_code_and_urls(line);
        if is_list_item(&masked) || current.is_empty() {
            let content = if is_list_item(&masked) {
                let trimmed = masked.trim_start();
                trimmed.split_once(' ').map_or("", |(_, rest)| rest).to_string()
            } else {
                masked
            };
            current.push(vec![content]);
        } else {
            current.last_mut().expect("not empty").push(masked);
        }
    }
    flush(&mut current, &mut groups);
    groups
        .into_iter()
        .map(|items| Paragraph {
            sentences: items.iter().flat_map(|lines| sentences(&lines.join(" "))).collect(),
        })
        .collect()
}

/// Split text into sentences at `.`, `?` or `!` (and any closing quotation mark or bracket)
/// followed by a space or the end, but not after `e.g.`, `i.e.`, `etc.` or `vs.`. Marks words
/// that lie inside double quotation marks.
fn sentences(text: &str) -> Vec<Sentence> {
    let mut out = Vec::new();
    let mut current = Sentence::default();
    let mut quoted = false;
    for token in text.split_whitespace() {
        let opens = token.starts_with(['"', '“']);
        let in_quote = quoted || opens;
        let quote_marks = token.chars().filter(|c| matches!(c, '"' | '“' | '”')).count();
        if token.chars().any(char::is_alphanumeric) {
            current.words.push(Word { text: token.to_string(), quoted: in_quote });
        }
        if quote_marks % 2 == 1 {
            quoted = !quoted;
        }
        let core = token.trim_end_matches(['"', '\'', '”', '’', ')', ']']);
        let ends = core.ends_with(['.', '?', '!'])
            && !NOT_SENTENCE_ENDS.contains(&core.trim_start_matches(['(', '[']).to_lowercase().as_str());
        if ends && !current.words.is_empty() {
            out.push(std::mem::take(&mut current));
        }
    }
    if !current.words.is_empty() {
        out.push(current);
    }
    out
}

// ---- Word checks ----

/// Whether a lowercase word is a form of a blacklisted base word.
fn inflects(word: &str, base: &str) -> bool {
    if word == base || IRREGULAR.iter().any(|(form, of)| *form == word && *of == base) {
        return true;
    }
    let stem = base.strip_suffix('e').unwrap_or(base);
    let last = base.chars().last().unwrap_or_default();
    let doubled = format!("{base}{last}");
    ["s", "es", "d", "ed", "ing"].iter().any(|ending| {
        word == format!("{base}{ending}")
            || word == format!("{stem}{ending}")
            || (matches!(*ending, "ed" | "ing") && word == format!("{doubled}{ending}"))
            || (base.ends_with('y') && word == format!("{}ies", &base[..base.len() - 1]))
            || (base.ends_with('y') && word == format!("{}ied", &base[..base.len() - 1]))
    })
}

/// The word reports for a run of words. Each distinct word is reported once per block: `seen`
/// is shared by the block's title and text. Titles get `CAPITAL_MODAL`, `SHALL` and `BLACKLIST`;
/// text also gets `VAGUE_WORD`.
fn word_reports(
    words: &[Word],
    in_text: bool,
    seen: &mut BTreeSet<(&'static str, String)>,
    out: &mut Vec<(&'static str, String)>,
) {
    let mut push = |code: &'static str, key: String, message: String, out: &mut Vec<(&'static str, String)>| {
        if seen.insert((code, key)) {
            out.push((code, message));
        }
    };
    for (index, word) in words.iter().enumerate() {
        if word.quoted {
            continue;
        }
        let bare = word.bare();
        let lower = bare.to_lowercase();
        let next = words.get(index + 1).filter(|w| !w.quoted).map(Word::bare);
        if CAPITAL_MODALS.contains(&bare) {
            let shown = if matches!(bare, "MUST" | "SHOULD") && next == Some("NOT") {
                format!("{bare} NOT")
            } else {
                bare.to_string()
            };
            push("CAPITAL_MODAL", shown.clone(), format!("uses \"{shown}\"; TASTE writes must, should, may, can and might in lowercase."), out);
        } else if lower == "shall" {
            push("SHALL", lower.clone(), "uses \"shall\"; TASTE uses must for a requirement.".into(), out);
        }
        if inflects(&lower, "kick") && next.is_some_and(|n| n.eq_ignore_ascii_case("off")) {
            let shown = format!("{bare} {}", next.unwrap_or_default());
            push("BLACKLIST", shown.to_lowercase(), format!("uses \"{shown}\"; use \"start\" if it keeps the meaning."), out);
        }
        if let Some((_, preferred)) = BLACKLIST.iter().find(|(base, _)| inflects(&lower, base)) {
            push("BLACKLIST", lower.clone(), format!("uses \"{bare}\"; use \"{preferred}\" if it keeps the meaning."), out);
        }
        if in_text && VAGUE.contains(&lower.as_str()) {
            push("VAGUE_WORD", lower.clone(), format!("uses \"{bare}\"; state the behavior or a measurement instead."), out);
        }
    }
}

fn starts_with_phrase(text: &str, phrase: &str) -> bool {
    // By bytes with `get`, so text that starts with a multi-byte character cannot split it.
    text.get(..phrase.len()).is_some_and(|head| head.eq_ignore_ascii_case(phrase))
        && text[phrase.len()..].chars().next().is_none_or(|c| !c.is_alphanumeric())
}

fn first_text(paragraph: &Paragraph) -> String {
    paragraph
        .sentences
        .first()
        .map(|s| s.words.iter().map(|w| w.text.as_str()).collect::<Vec<_>>().join(" "))
        .unwrap_or_default()
}

// ---- The check ----

/// Every report for the map's specification layer, in document order.
pub fn check(map: &Map) -> Vec<Report> {
    let mut reports = Vec::new();
    let mut abbreviations_seen: BTreeSet<String> = BTreeSet::new();
    let mut sentences_seen: BTreeMap<String, (String, usize, usize)> = BTreeMap::new();
    for address in document_addresses(map) {
        let element = map.element(address).expect("listed from the map");
        let Some(Ok(blocks)) = element.fields.get(LAYER).map(|value| specification::blocks(address, value)) else {
            continue;
        };
        for (index, block) in blocks.iter().enumerate() {
            let n = index + 1;
            let mut found: Vec<(&'static str, String)> = Vec::new();
            let title_words: Vec<Word> = block
                .title
                .iter()
                .flat_map(|title| sentences(&mask_code_and_urls(title)))
                .flat_map(|s| s.words)
                .collect();
            block_reports(address, n, block, &blocks, &title_words, &mut found, &mut abbreviations_seen, &mut sentences_seen);
            reports.extend(found.into_iter().map(|(code, message)| Report {
                address: address.to_string(),
                block: n,
                title: block.title.clone(),
                code,
                message,
            }));
        }
    }
    reports
}

#[allow(clippy::too_many_arguments)]
fn block_reports(
    address: &str,
    n: usize,
    block: &Block,
    blocks: &[Block],
    title_words: &[Word],
    found: &mut Vec<(&'static str, String)>,
    abbreviations_seen: &mut BTreeSet<String>,
    sentences_seen: &mut BTreeMap<String, (String, usize, usize)>,
) {
    if let Some(level) = block.level
        && block.text.is_empty()
        && blocks.get(n).is_none_or(|next| next.level.is_none_or(|next| next <= level))
    {
        found.push(("EMPTY_SECTION", "has a heading with no text under it; remove the block or add its text.".into()));
    }
    let paragraphs = paragraphs(&block.text);
    let all_words: Vec<Word> = paragraphs
        .iter()
        .flat_map(|p| p.sentences.iter().flat_map(|s| s.words.clone()))
        .collect();
    let mut seen = BTreeSet::new();
    word_reports(title_words, false, &mut seen, found);
    word_reports(&all_words, true, &mut seen, found);

    let mut opened = false;
    for (p_index, paragraph) in paragraphs.iter().enumerate() {
        let start = first_text(paragraph);
        if let Some(phrase) = OPENINGS.iter().find(|phrase| starts_with_phrase(&start, phrase))
            && !paragraph.sentences.first().and_then(|s| s.words.first()).is_some_and(|w| w.quoted)
        {
            found.push(("OPENING", format!("starts with \"{phrase}\"; start with the content.")));
            opened |= p_index == 0;
        }
        if paragraph.sentences.len() > PARAGRAPH_SENTENCES {
            found.push(("PARAGRAPH_LENGTH", format!(
                "paragraph {} has {} sentences; the limit is six. Split it by topic.",
                p_index + 1,
                paragraph.sentences.len()
            )));
        }
    }
    if !opened && let Some(first) = paragraphs.first().and_then(|p| p.sentences.first()) {
        // The part before an apostrophe, so "It's" and "They're" count as "It" and "They".
        let word = |i: usize| {
            let bare = first.words.get(i).map(Word::bare).unwrap_or_default();
            bare.split(['\'', '’']).next().unwrap_or_default()
        };
        let pronoun = matches!(word(0), "It" | "They")
            || (DEMONSTRATIVES.contains(&word(0)) && PRONOUN_VERBS.contains(&word(1)));
        if pronoun && first.words.first().is_some_and(|w| !w.text.starts_with(['"', '“'])) {
            found.push(("START_PRONOUN", format!(
                "starts with \"{}\"; a block is often read alone, so name the element or field.",
                word(0)
            )));
        }
    }

    for (s_index, sentence) in paragraphs.iter().flat_map(|p| p.sentences.iter()).enumerate() {
        let i = s_index + 1;
        if sentence.words.len() > SENTENCE_WORDS {
            found.push(("SENTENCE_LENGTH", format!(
                "sentence {i} has {} words; the target is 25 or fewer. Split it if that keeps its conditions and reasons.",
                sentence.words.len()
            )));
        }
        if sentence.words.len() >= REPEAT_MIN_WORDS {
            let key = sentence.normalized();
            match sentences_seen.get(&key) {
                Some((first_address, first_block, first_i)) => found.push(("REPEATED_SENTENCE", format!(
                    "repeats sentence {first_i} of {first_address} block {first_block}; state each point once."
                ))),
                None => {
                    sentences_seen.insert(key, (address.to_string(), n, i));
                }
            }
        }
    }

    // A title can define an abbreviation, such as "Network card (NIC)". Titles get no
    // ABBREVIATION report, so an undefined one in a title is neither reported nor marked as seen.
    for (index, word) in title_words.iter().enumerate() {
        let raw = word.text.as_str();
        let defined_here = raw.starts_with('(') && raw.trim_end_matches(['.', ',', ';', ':']).ends_with(')');
        let expanded_after = title_words.get(index + 1).is_some_and(|next| next.text.starts_with('('));
        let bare = word.bare();
        if (defined_here || expanded_after) && (2..=6).contains(&bare.len()) && bare.chars().all(|c| c.is_ascii_uppercase()) {
            abbreviations_seen.insert(bare.to_string());
        }
    }
    for (index, word) in all_words.iter().enumerate() {
        let raw = word.text.as_str();
        let defined_here = raw.starts_with('(') && raw.trim_end_matches(['.', ',', ';', ':']).ends_with(')');
        let bare = word.bare();
        let abbreviation = bare.strip_suffix('s').filter(|b| b.len() >= 2 && b.chars().all(|c| c.is_ascii_uppercase())).unwrap_or(bare);
        let is_abbreviation = (2..=6).contains(&abbreviation.len())
            && abbreviation.chars().all(|c| c.is_ascii_uppercase())
            && !KNOWN_ABBREVIATIONS.contains(&abbreviation)
            && !CAPITAL_MODALS.contains(&abbreviation)
            && !matches!(abbreviation, "NOT" | "SHALL");
        if !is_abbreviation || !abbreviations_seen.insert(abbreviation.to_string()) {
            continue;
        }
        let expanded_after = all_words.get(index + 1).is_some_and(|next| next.text.starts_with('('));
        if !defined_here && !expanded_after {
            found.push(("ABBREVIATION", format!("uses \"{abbreviation}\" before defining it; spell it out at first use.")));
        }
    }
}

#[cfg(test)]
mod tests {
    use serde_json::{Value, json};

    use super::*;

    fn reports_for(blocks: Value) -> Vec<Report> {
        let map = Map::from_tree(&json!({
            "code": {"technical_name": "code", "name": "Lab", "role": "Definitive", "specification": blocks}
        }))
        .unwrap();
        check(&map)
    }

    fn codes(reports: &[Report]) -> Vec<&'static str> {
        reports.iter().map(|r| r.code).collect()
    }

    #[test]
    fn clean_text_has_no_reports() {
        let reports = reports_for(json!([
            {"text": "The lab records frames from the network card (NIC) and keeps them for a week."},
            {"level": 1, "title": "Storage", "text": "The store writes each frame to disk. The `frame_store` field holds the path, e.g. `/var/lab`."}
        ]));
        assert_eq!(reports, Vec::new());
        assert_eq!(summary(&reports), "check: no reports.");
    }

    #[test]
    fn each_check_reports_its_case() {
        let long = vec!["word"; 26].join(" ");
        let reports = reports_for(json!([
            {"text": "It MUST NOT launch a fast job. The system shall keep the RTP stream. \"Users MUST wait\" is a quote."},
            {"level": 1, "title": "Kick off and stop", "text": format!("Note that the store keeps frames. {long}.")},
            {"level": 1, "title": "Empty", "text": ""},
            {"level": 1, "title": "Repeat", "text": "The store writes each frame to disk at once. The store writes each frame to disk at once."},
            {"level": 1, "title": "Long", "text": "A. B. C. D. E. F. G."}
        ]));
        let found = codes(&reports);
        for code in ["CAPITAL_MODAL", "SHALL", "SENTENCE_LENGTH", "PARAGRAPH_LENGTH", "BLACKLIST", "VAGUE_WORD", "OPENING", "START_PRONOUN", "ABBREVIATION", "REPEATED_SENTENCE", "EMPTY_SECTION"] {
            assert!(found.contains(&code), "{code} missing from {found:?}");
        }
        let lines: Vec<String> = reports.iter().map(Report::line).collect();
        assert!(lines.contains(&"code block 1: CAPITAL_MODAL: uses \"MUST NOT\"; TASTE writes must, should, may, can and might in lowercase.".to_string()), "{lines:#?}");
        assert!(lines.contains(&"code block 2 (\"Kick off and stop\"): BLACKLIST: uses \"Kick off\"; use \"start\" if it keeps the meaning.".to_string()), "{lines:#?}");
        assert!(lines.contains(&"code block 1: ABBREVIATION: uses \"RTP\" before defining it; spell it out at first use.".to_string()), "{lines:#?}");
        assert!(lines.contains(&"code block 4 (\"Repeat\"): REPEATED_SENTENCE: repeats sentence 1 of code block 4; state each point once.".to_string()), "{lines:#?}");
        // The quoted MUST is skipped: one CAPITAL_MODAL only.
        assert_eq!(found.iter().filter(|c| **c == "CAPITAL_MODAL").count(), 1);
        assert!(summary(&reports).starts_with(&format!("check: {} reports in 5 blocks (CAPITAL_MODAL 1, SHALL 1,", reports.len())));
    }

    #[test]
    fn code_tables_and_urls_are_skipped() {
        let reports = reports_for(json!([
            {"level": 1, "title": "Use", "text": "The CLI prints `launch MUST` to the screen.\n\n```text\nThis section MUST launch.\n```\n\n| launch | MUST |\n|---|---|\n\nSee https://example.com/launch-fast for details."}
        ]));
        assert_eq!(reports, Vec::new());
    }

    #[test]
    fn review_cases_from_matthew() {
        let reports = reports_for(json!([
            {"text": "Überblick über die Daten, e.g. frames (e.g. raw frames) and more."},
            {"level": 1, "title": "SHALL change", "text": "The store SHALL change frames."},
            {"level": 1, "title": "Network card (NIC)", "text": "It's the NIC that delivers frames."}
        ]));
        let lines: Vec<String> = reports.iter().map(Report::line).collect();
        assert!(lines.contains(&"code block 2 (\"SHALL change\"): SHALL: uses \"shall\"; TASTE uses must for a requirement.".to_string()), "{lines:#?}");
        assert_eq!(reports.iter().filter(|r| r.block == 2 && r.code == "BLACKLIST").count(), 1, "title and text share one report: {lines:#?}");
        assert!(!reports.iter().any(|r| r.code == "CAPITAL_MODAL" || r.code == "ABBREVIATION"), "{lines:#?}");
        assert!(lines.iter().any(|l| l.contains("START_PRONOUN: starts with \"It\"")), "{lines:#?}");
        assert_eq!(reports.iter().filter(|r| r.block == 1).count(), 0, "{lines:#?}");
    }

    #[test]
    fn blacklist_matches_inflected_forms() {
        for (word, base) in [("launched", "launch"), ("running", "run"), ("ran", "run"), ("stopped", "stop"), ("initiating", "initiate"), ("modifies", "modify"), ("began", "begin"), ("utilized", "utilize")] {
            assert!(inflects(word, base), "{word} is a form of {base}");
        }
        assert!(!inflects("rune", "run"));
        assert!(!inflects("stoppage", "stop"));
    }
}
