//! Reads the intake procedure's folder, `metaform/intake/procedure/`, and writes the list of its
//! sections for `src/procedure.rs`. The folder holds one Markdown file for each section and
//! `sections.md`, which names the sections in reading order and marks the required ones. The
//! build does not stop when the list and the files disagree; it warns and serves what is there.

use std::fmt::Write as _;
use std::path::PathBuf;

const INDEX: &str = "sections.md";

fn main() {
    let folder = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap()).join("../../../intake/procedure");
    let folder = folder.canonicalize().unwrap_or_else(|e| panic!("{}: {e}", folder.display()));
    println!("cargo:rerun-if-changed={}", folder.display());
    let index = std::fs::read_to_string(folder.join(INDEX)).unwrap_or_else(|e| panic!("{INDEX}: {e}"));
    // A section line is "- name" or "- name (required)".
    let mut listed: Vec<(String, bool)> = Vec::new();
    for line in index.lines() {
        let Some(entry) = line.strip_prefix("- ") else {
            continue;
        };
        let required = entry.trim_end().ends_with("(required)");
        let name = entry.trim_end().trim_end_matches("(required)").trim().to_string();
        listed.push((name, required));
    }
    // The build never stops because of how the folder is edited. A file that the list does not
    // name is served after the listed sections, in name order. A name with no file is left out,
    // with a warning.
    let mut files: Vec<String> = std::fs::read_dir(&folder)
        .unwrap()
        .filter_map(|entry| entry.ok()?.file_name().into_string().ok())
        .filter(|name| name.ends_with(".md") && name != INDEX)
        .map(|name| name.trim_end_matches(".md").to_string())
        .collect();
    files.sort();
    listed.retain(|(name, _)| {
        let found = files.contains(name);
        if !found {
            println!("cargo:warning={INDEX} names the section {name}, but {name}.md is not in the folder; it is left out");
        }
        found
    });
    for name in files {
        if !listed.iter().any(|(known, _)| *known == name) {
            println!("cargo:warning={name}.md is not named in {INDEX}; it is served after the listed sections");
            listed.push((name, false));
        }
    }
    let mut code = String::from("/// Each section: its name, whether it is required reading, and its Markdown.\npub(crate) const SECTIONS: &[(&str, bool, &str)] = &[\n");
    for (name, required) in &listed {
        let path = folder.join(format!("{name}.md"));
        println!("cargo:rerun-if-changed={}", path.display());
        writeln!(code, "    ({name:?}, {required}, include_str!({:?})),", path.display().to_string()).unwrap();
    }
    code.push_str("];\n");
    let out = PathBuf::from(std::env::var("OUT_DIR").unwrap()).join("sections.rs");
    std::fs::write(out, code).unwrap();
}
