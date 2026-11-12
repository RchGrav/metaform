//! The intake procedure, served one section at a time.
//!
//! The procedure is a folder of Markdown files, `metaform/intake/procedure/`: one file for each
//! section (`goal.md`, `core_concepts.md`, `namespace_rules.md`, `method.md` and the others), and
//! `sections.md`, which names the sections in reading order and marks the required ones. The
//! sections follow the organization of the founder's XML procedure; the files hold no XML.
//! `build.rs` reads the folder when the server is built, so the server reads no file while it
//! runs. This file names no section and knows nothing of what a section holds, so a change to
//! the procedure is a change to that folder.
//!
//! No test or check reads the content of that folder: not the names of the sections, not which
//! are required, and not their text. The founder edits the procedure, and an earlier project
//! became impossible to edit after agents wrote tests against its prompt text. Keep it so.
//!
//! The reason for sections: an agent that performs an intake reads all of them once, and an
//! agent that does other work reads only the one it needs, such as the namespace rules before it
//! adds an element. No agent is sent the whole procedure without asking (founder, 2026-11-12).

include!(concat!(env!("OUT_DIR"), "/sections.rs"));

/// One section of the procedure: its name, its Markdown, and whether it is required reading.
#[derive(Clone, Debug, PartialEq)]
pub struct Section {
    pub name: &'static str,
    pub text: &'static str,
    pub required: bool,
}

/// The sections of the intake procedure, in reading order.
pub fn sections() -> Vec<Section> {
    SECTIONS
        .iter()
        .map(|(name, required, text)| Section { name, text: text.trim(), required: *required })
        .collect()
}

/// The section with this name, if the procedure has one.
pub fn section(name: &str) -> Option<Section> {
    sections().into_iter().find(|section| section.name == name)
}
