---
name: metaform-tester-readme-build
description: Use when editing the tester README the build generates.
category: development
---
# The tester README is generated, not written

`src/metaform/build_readme.py` writes the README into every project, installer and full build. Change the generator, never a pasted copy. It reads the version and Python requirement from `_build_info`, module summaries, `docs.COMMANDS` usage, the MCP server command, the installer's tool table, and the web port setting.

- A command the README names that is no longer declared stops the build on purpose. Rename a command only together with its line in `build_readme.py`.
- A command that another change may add is included only while declared, with its own help text. Test that with and without the declaration.
- `build_readme.WELCOME` and `DISCORD` are kept verbatim; `tests/test_build.py` checks the README's third line equals WELCOME.
- `metaform --version` prints `cli.VERSION`, and the README quotes that constant. Do not hard-code the version string.
- Wheel builds write `metaform-<version>-<kind>.zip` beside the wheel. The wheel stays there because install registers it as `last_build`.
- Verify a README change by following it as a tester; see `verify-install-steps-in-scratch-home`.
- Spec changes go in as dated amendments (`metaform-spec-amendments`), never as edits to a record's original sentences.
