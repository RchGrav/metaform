//! STAND-IN, to be replaced by Marcus's `specification.rs` from branch `specification-layer-core`.
//! It provides the agreed interface (`LAYER`, `MAX_LEVEL`, `Block`, `blocks`) so that
//! `markdown.rs` and `check.rs` build and test before the merge. The block rules here follow the
//! agreed shape: `{"level": 1-4, "title": str, "text": str}`, and one optional first block
//! `{"text": non-empty}` with no level and no title.

use serde_json::{Map as JsonMap, Value, json};

use crate::refusal::{Code, Refusal};

/// The field that holds the specification layer at an element.
pub const LAYER: &str = "specification";

/// The deepest block level relative to its container heading.
pub const MAX_LEVEL: u8 = 4;

/// One block of the specification layer.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Block {
    /// The heading level relative to its container, 1 to `MAX_LEVEL`; `None` for the intro.
    pub level: Option<u8>,
    /// A key unique across the map's specification, so text can refer to the block; titled
    /// blocks only.
    pub code: Option<String>,
    /// The heading; `None` for the intro.
    pub title: Option<String>,
    /// The Markdown under the heading. It holds no heading of its own.
    pub text: String,
}

impl Block {
    /// The block as the layer stores it.
    pub fn to_json(&self) -> Value {
        let mut out = JsonMap::new();
        if let (Some(level), Some(title)) = (self.level, &self.title) {
            out.insert("level".into(), json!(level));
            if let Some(code) = &self.code {
                out.insert("code".into(), json!(code));
            }
            out.insert("title".into(), json!(title));
        }
        out.insert("text".into(), json!(self.text));
        Value::Object(out)
    }
}

/// Read and check the layer's value at an element.
pub fn blocks(value: &Value) -> Result<Vec<Block>, Refusal> {
    let refuse = |reason: String| Refusal::new(Code::FieldMismatch, reason, None);
    let Value::Array(items) = value else {
        return Err(refuse("the specification layer must be a list of blocks".into()));
    };
    let mut out = Vec::with_capacity(items.len());
    let mut previous: Option<u8> = None;
    for (index, item) in items.iter().enumerate() {
        let at = format!("block {}", index + 1);
        let Some(fields) = item.as_object() else {
            return Err(refuse(format!("{at} must be an object with level, title and text")));
        };
        let text = fields.get("text").and_then(Value::as_str).unwrap_or("").to_string();
        if let Some(line) = heading_in_text(&text) {
            return Err(refuse(format!("{at}: line {line} of the text is a Markdown heading")));
        }
        match (fields.get("level").and_then(Value::as_u64), fields.get("title").and_then(Value::as_str)) {
            (None, None) if index == 0 && !text.is_empty() && !fields.contains_key("code") => {
                out.push(Block { level: None, code: None, title: None, text })
            }
            (Some(level), Some(title)) if (1..=u64::from(MAX_LEVEL)).contains(&level) => {
                let level = level as u8;
                if level > previous.map_or(1, |p| p + 1) {
                    return Err(refuse(format!("{at}: level {level} skips a heading level")));
                }
                previous = Some(level);
                if title.starts_with('`') {
                    return Err(refuse(format!("{at}: a title must not start with a code span; put the key in code")));
                }
                let code = match fields.get("code") {
                    None => None,
                    Some(Value::String(code)) if is_code(code) => Some(code.clone()),
                    Some(_) => return Err(refuse(format!("{at}: code must be a letter and then up to 31 letters, digits, '.', '_' or '-'"))),
                };
                if let Some(code) = &code
                    && out.iter().any(|b: &Block| b.code.as_ref().is_some_and(|c| c.eq_ignore_ascii_case(code)))
                {
                    return Err(refuse(format!("{at}: code '{code}' is already used")));
                }
                out.push(Block { level: Some(level), code, title: Some(title.to_string()), text });
            }
            _ => return Err(refuse(format!("{at} breaks the block shape"))),
        }
    }
    Ok(out)
}

/// A block code: a letter, then up to 31 letters, digits, `.`, `_` or `-`.
pub fn is_code(code: &str) -> bool {
    let mut chars = code.chars();
    chars.next().is_some_and(|c| c.is_ascii_alphabetic())
        && code.len() <= 32
        && chars.all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | '-'))
}

/// The first line of `text`, from 1, that Markdown reads as a heading outside fenced code.
pub fn heading_in_text(text: &str) -> Option<usize> {
    let mut fence: Option<(char, usize)> = None;
    let mut previous_blank = true;
    for (number, line) in text.lines().enumerate() {
        if let Some((mark, length)) = fence {
            if crate::markdown::closes_fence(line, mark, length) {
                fence = None;
            }
        } else if let Some(opened) = crate::markdown::opens_fence(line) {
            fence = Some(opened);
        } else if crate::markdown::atx_level(line).is_some()
            || (!previous_blank && crate::markdown::is_setext_underline(line))
        {
            return Some(number + 1);
        }
        previous_blank = line.trim().is_empty();
    }
    None
}
