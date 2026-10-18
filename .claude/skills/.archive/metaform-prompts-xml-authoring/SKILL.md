---
name: metaform-prompts-xml-authoring
description: Use when editing a module's prompts.xml system prompt.
category: development
---

# Prompts are XML: escape first, then fix the wording

`prompts.xml` is parsed with `ET.fromstring` (`prompt_files.py`). One raw `&` or `<` in the text stops the whole file loading. Write `&amp;` in the file. The agent receives `&`.

- Check that the file parses before judging its content.
- Never strip characters to get a file to parse. Escape them.
- When the person says a prompt is too broken to edit, rewrite the whole element and return the full text. Do not list critiques first or ask which ones to change.
- Before saying a prompt lacks context, read what the connect-time MCP instructions already give the agent. A claim withdrawn after checking costs a round.
- Comments in `prompts.xml` are product documentation and are never sent. The prompt text goes out exactly as written, so numbering and headers must read cleanly to the agent.
- Do not write code that checks a prompt's structure: no header checks, no Axiom-name checks, no "incomplete prompt" signal. Axiom module names (@STATE_INIT, @ROUTER and the rest) are contextual, not literal headers, so a complete prompt written without them is still complete. Whether a prompt says what to do, how, how it works and when is judged by the prompt's reader. Dispatch sends a first turn as written; workflow stores subroutines as written.
- Edit an element by its real position, never by a bare string search. A `re.search(r'<instructions>.*?</instructions>')` matched the word `<instructions>` quoted inside a comment above the element, so the splice put a second copy in the comment and the file stopped parsing (`not well-formed (invalid token)`). Anchor on the element after its comment block, or rewrite the whole file from a parsed copy.
- After every write, run `prompt_files.text(...)` on the module and compare it with the text you meant to store. If it fails, `git checkout --` the file before anything else, then redo the edit. Do not move on with a broken prompts file.
