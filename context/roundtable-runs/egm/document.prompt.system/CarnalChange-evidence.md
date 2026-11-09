# CarnalChange — evidence boundaries and key corrections

Only four source files are supplied locally. After the group identified sibling copies, I independently checked `../collection.workspace.shared/source/crates/roundtable/src/engine.rs` and `config.rs`: engine initialization, objective fallback, default-disabled topics, prompt-content transport, resumed-session initialization, and final-message consumption are now confirmed. Earlier local-snapshot-only reservations are superseded.

The most consequential corrections are directly inspectable:

- `source/crates/roundtable/src/turn.rs:125–145`: contribution limits block the entire message before judging. They do not truncate it.
- `source/crates/roundtable/src/turn.rs:148–167,199–203`: accepted/shared contributions can be unjudged; both common templates promise evaluation without these exceptions.
- `source/crates/roundtable/src/turn.rs:37–87`: the common composition depends on `seat.first`, including special prompts, and that flag is cleared on commit.
- `source/crates/roundtable/src/turn.rs:57–59`: later topic headers require both active topics and an unseen topic index.
- `source/crates/roundtable/src/turn.rs:320–324` and `source/crates/roundtable/src/prompts.rs:85–86`: topic proposals have a separately announced limit and are truncated.

These distinctions support documentation/comment corrections while preserving the owner's recorded verbatim-template decision. A map name mismatch alone does not prove a wrong URI, and an undefined `name_length` does not establish that its value should be a word count.

Additional verified qualifications: sibling `engine.rs:402–404` canonicalizes the workspace with fallback to the original path on failure. Sibling `config.rs:154–158` makes the base contribution limit optional, defaulting to no limit; the hidden-limit concern applies when a limit is configured. Sibling `../code.rating.peer/source/crates/roundtable/resources/feedback/too_long.md` explicitly gives the rejected message's length and limit. The identity profile resource says “profile score”; it does not identify that score as an average.
