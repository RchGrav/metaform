---
name: metaform-spec-amendments
description: Use when amending a spec record after a code fix.
category: development
---

# Amend a spec record by appending a dated, ticketed bullet

When the code changes what a `specifications/*.md` record says, leave the original sentences as written and append one bullet to that record's own list: `- Amendment, YYYY-MM-DD, ticket <id>, <what changed and why>.` Name the ticket, say what the code now does, and say what it did before only when that matters to a reader.

- Put it after the record's `Status:` line, inside the same record; never create a new record number for an amendment.
- Use the date the change is made, not the date the record was first written.
- Mirror the existing amendments in `specifications/01-map.md` and `specifications/04-chassis-modules.md`; grep those files for `- Amendment,` to match the form before writing one.
- Do not edit the code to match a spec; the code is the reference, and the spec follows it.
