+def _holds(merged: str | None, note: str) -> bool:
+    """A merged note holds this note when it is the whole note or one of its paragraphs, the blank-line-separated
+    findings a merge joins; a note that is only a part of a paragraph is a new finding."""
+    note, merged = note.strip(), (merged or '').strip()
+    return note == merged or f'\n\n{note}\n\n' in f'\n\n{merged}\n\n' \
+        or note in (block.strip() for block in merged.split('\n\n'))

Tool result (before fix): FAILED test_a_finding_on_an_element_and_its_purpose_record_is_written_once[element] ... assert ticket.note.endswith('\n\nnever') ... 'never sounds\n\nother'.endswith