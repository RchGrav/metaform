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
- When a ticket's code makes a sentence of a record false, a worker does not leave it as a note alone. It drafts the bullet into `artifacts/specs-draft/` in the same run, names that file in its final resolution, and says which sentence the code now contradicts.
- Check the record's earlier amendments as well as its original sentences: an amendment from a prior ticket can be what the new code contradicts. Then the draft is a superseding bullet that names that amendment by date and ticket and quotes the sentence it replaces. Never rewrite the earlier bullet in place.
- A worker agent running a ticket does not write the bullet into `specifications/`, even when the ticket asks for the amendment to land: the worker drafts the wording, and the owner's approval lands it. A ticket that says to update the record directly does not change this: draft into `artifacts/specs-draft/`, name that file in the resolution, and say the ticket asked for a direct edit. Specs changed without approval are reverted by the owner, not defended. It drafts the wording in `artifacts/specs-draft/`, and the bullet lands in the spec only after the owner approves that exact wording, marked `approved by the owner` (metaform-development, Tickets and source passes). The bullet above is what the owner's own session appends.
- Before opening a new record, check whether a record already covers the surface the feature changes. New behaviour on a surface an existing record covers is an amendment to that record (the phone's page banner is part of VIEW-051, the error surface, so it amends VIEW-051 rather than a phone record that does not exist). A feature with no record at all, where no existing record's area describes it, gets a new record, not an amendment: the next free number after its area's last record, in the same file, with a status line in the form the neighbouring records use, naming the date built, the topic and the ticket. Name the record in the ticket's final step so the link is findable.
