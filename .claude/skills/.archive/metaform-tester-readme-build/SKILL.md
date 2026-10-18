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
- The installer's module list is `build.installer_default()`: the modules on at home plus the chain `start` and `demo` run (map, intake, mcp, web, dispatch), so dispatch, which ships off, is packed for those commands. The README names `metaform demo` and `metaform start` only when `build.carries_onboarding(ids)` holds; test the README with and without the modules.
- The README's Node.js line comes from the literal `NODE` in `modules/dispatch/__init__.py`, read by AST so an off module is never imported. Bump it there and the README follows. It is 22, because claude-agent-acp 0.89.1 declares node >=22.
- Claude Code is connected one way in the README: the project's `.mcp.json`, the entry `start.mcp_entry()` writes. Do not print `claude mcp add` or `metaform install claude`; after a plain `uv tool install` the install has no wheel to register. Every claim the README makes about files (for example "writes only `.mcp.json` and a report zip") must match what the zip actually does.
