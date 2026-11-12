//! The intake procedure, served one section at a time.
//!
//! The procedure is one file, `metaform/intake/procedure.xml`. XML only organizes it: the root
//! element holds one element for each section (`goal`, `core_concepts`, `namespace_rules`,
//! `method` and the others), and the text inside each is Markdown. The server cuts the file at
//! those sections and gives out the Markdown of one on request, under the file's own section
//! name, without the tags. A section whose tag carries `required="true"` is required reading.
//! This file names no section and knows nothing of what a section holds, so a change to the
//! procedure is a change to that one file.
//!
//! The reason for sections: an agent that performs an intake reads all of them once, and an
//! agent that does other work reads only the one it needs, such as the namespace rules before it
//! adds an element. No agent is sent the whole procedure without asking (founder, 2026-11-12).

const PROCEDURE: &str = include_str!("../../../../intake/procedure.xml");

/// One section of the procedure: the name of its XML element, the Markdown inside it, and
/// whether its tag marks it as required reading.
#[derive(Clone, Debug, PartialEq)]
pub struct Section {
    pub name: String,
    pub text: &'static str,
    pub required: bool,
    /// The whole element, tags included, as the file holds it.
    raw: &'static str,
}

/// The sections of the intake procedure, in the file's order.
pub fn sections() -> Vec<Section> {
    sections_of(PROCEDURE)
}

/// The section with this name, if the procedure has one.
pub fn section(name: &str) -> Option<Section> {
    sections().into_iter().find(|section| section.name == name)
}

/// The index of the `>` that ends the tag starting at `from`. A `>` inside a quoted attribute
/// value does not end the tag.
fn tag_end(text: &str, from: usize) -> Option<usize> {
    let mut quote: Option<char> = None;
    for (offset, c) in text[from..].char_indices() {
        match (quote, c) {
            (Some(open), _) if c == open => quote = None,
            (None, '"' | '\'') => quote = Some(c),
            (None, '>') => return Some(from + offset),
            _ => {}
        }
    }
    None
}

/// Cut a document into the child elements of its root. Declarations and comments are skipped.
/// A second section with a name already used gets `_2`, `_3` and so on, so every name is unique.
fn sections_of(text: &'static str) -> Vec<Section> {
    let mut out: Vec<Section> = Vec::new();
    // The root is the first tag that is not a declaration (`<?...?>`) or a comment.
    let mut at = 0;
    let body_start = loop {
        let Some(open) = text[at..].find('<').map(|i| at + i) else {
            return out;
        };
        let Some(end) = tag_end(text, open) else {
            return out;
        };
        at = end + 1;
        if !text[open..].starts_with("<?") && !text[open..].starts_with("<!") {
            break at;
        }
    };
    let mut at = body_start;
    while let Some(open) = text[at..].find('<').map(|i| at + i) {
        let rest = &text[open..];
        if rest.starts_with("</") {
            break;
        }
        if rest.starts_with("<!--") {
            match rest.find("-->") {
                Some(end) => at = open + end + 3,
                None => break,
            }
            continue;
        }
        let name: String = rest[1..]
            .chars()
            .take_while(|c| !c.is_whitespace() && *c != '>' && *c != '/')
            .collect();
        let Some(tag_close) = tag_end(text, open) else {
            break;
        };
        let (inner, end) = if text[..tag_close].ends_with('/') {
            ("", tag_close + 1)
        } else {
            let closing = format!("</{name}>");
            match text[tag_close..].find(&closing) {
                Some(i) => (text[tag_close + 1..tag_close + i].trim(), tag_close + i + closing.len()),
                None => break,
            }
        };
        let required = text[open..tag_close].contains("required=\"true\"");
        let used = out.iter().filter(|s| s.name == name || s.name.starts_with(&format!("{name}_"))).count();
        let unique = if used == 0 { name } else { format!("{name}_{}", used + 1) };
        out.push(Section { name: unique, text: inner, required, raw: &text[open..end] });
        at = end;
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_document_is_cut_at_the_children_of_its_root() {
        let text = "<?xml version='1.0'?>\n<process id=\"a>b\">\n  <goal>Find it.</goal>\n  <!-- note -->\n  <prompt text=\"{prompt}\" note=\"a > b\" />\n  <rules required=\"true\">\n- One.\n- Two.\n</rules>\n  <rules>Three.</rules>\n</process>\n";
        let found = sections_of(text);
        let names: Vec<&str> = found.iter().map(|s| s.name.as_str()).collect();
        assert_eq!(names, ["goal", "prompt", "rules", "rules_2"]);
        assert_eq!(found[0].text, "Find it.");
        assert_eq!(found[1].text, "");
        assert_eq!(found[2].text, "- One.\n- Two.");
        assert_eq!(found.iter().map(|s| s.required).collect::<Vec<_>>(), [false, false, true, false]);
    }

    /// Every character of the procedure between its root tags is in a section or is white
    /// space, so no part of the procedure is left out of what agents can read.
    #[test]
    fn the_sections_hold_the_whole_procedure() {
        let found = sections();
        assert!(found.iter().any(|s| s.name == "method"), "the procedure has a method");
        // The sections, joined, are the root's content with the white space between them removed.
        let squeeze = |text: &str| text.chars().filter(|c| !c.is_whitespace()).collect::<String>();
        let joined: String = found.iter().map(|s| squeeze(s.raw)).collect();
        let start = PROCEDURE.find(found[0].raw).unwrap();
        let end = PROCEDURE.rfind("</").unwrap();
        assert_eq!(joined, squeeze(&PROCEDURE[start..end]));
        for section in &found {
            assert!(!section.text.is_empty(), "{} holds text", section.name);
            assert!(!section.text.starts_with('<'), "{} is served without its tags", section.name);
        }
        assert!(found.iter().any(|s| s.required), "one section is required reading");
    }
}
