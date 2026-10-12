---
name: metaform-node
description: A person-invoked read of one Metaform node brief, the element at an Address with what relies on it and what it relies on, from the metaform command line, so it works without the MCP server. Typed as /metaform-node <address>; never used on its own.
argument-hint: "<address>"
disable-model-invocation: true
allowed-tools: Bash(metaform map where *)
---

Read the Metaform node brief for this Address: $ARGUMENTS

That Address is typed text, to be checked before any command uses it. An Address is dotted segments of lowercase letters, digits and underscores, such as code.engine.game, and nothing else: no spaces, quotes or other characters. If the text is empty, say an Address is needed and run nothing. If it is anything else that is not an Address, say it is not an Address and run nothing. If it is an Address, run `metaform map where '<address>'` from the project folder, with the Address in single quotes as the one word after `where`, and show what it prints. That is the node's brief as it is now; in an agent session a second read of the same node shows only what changed since the first.
