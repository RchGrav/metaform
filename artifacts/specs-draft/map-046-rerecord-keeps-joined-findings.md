# MAP-046: recording a part again keeps the findings that joined its ticket

Draft for the owner's approval. Goes under MAP-046 in `specifications/01-map.md`, after the 2026-10-14 amendment's "No duplicates." bullet.

- Amendment, 2026-10-15, written to match what is built, round 6 blind check of the 2026-10-14 system review, ticket code.dispatcher.agent#2f (c021d1146da44215b1d82c999b8a538a): recorded again with the same marker and a new note, the untaken ticket at that part replaces only its own note, the first paragraph, and keeps the paragraphs that markers on the element or purpose record of the same node joined to it. Before, the new note replaced the whole note, so the first verification pass that recorded the part again erased the other part's finding without a notice. Recorded again with no note, the ticket keeps only the joined paragraphs. Build: intake `_condition`, its `same` branch. Acceptance: `test_a_finding_on_an_element_and_its_purpose_record_is_written_once`.
