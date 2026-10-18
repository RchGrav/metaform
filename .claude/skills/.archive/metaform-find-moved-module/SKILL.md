---
name: metaform-find-moved-module
description: Use when a named Metaform module is missing or gone.
category: development
---

# Find a module that moved out of the tree

Before saying a Metaform module is lost, find where it went. A module missing from `src/metaform/modules` has usually been extracted to its own repository.

1. Find the removal: `git log --all --oneline -i --grep=<name>` and `git log --all --diff-filter=D --name-only --format='%h %ad %s' --date=short -- 'src/metaform/modules/<name>/*'`.
2. Read the commit before the removal. Its message often names the destination ("before it moves to its own MCP server").
3. Look for the standalone repo: `ls -d ~/<name>* ~/*/<name>`. Check its `git log` and `git status`.
4. Confirm it is not shipped: `uv run metaform list modules` must not show it.

Report where the code lives, whether its work is committed, and what is uncommitted. Do not recreate the module inside Metaform without the user's decision.
