uv run metaform map work op=edit id=3390dd596291451e875fe3cf7f266ac7 note="$(cat /tmp/t3390.note)" >/dev/null 2>&1; uv run metaform map work id=3390dd596291451e875fe3cf7f266ac7 2>&1 | grep -c "Follow-up for the orchestrator"

The "Follow-up for the orchestrator" text is back in 3390dd59's note after my edit. I'm finding out what restored it and what #1c is.

Nothing was reverted—the phrase just shows up in the orchestration history, and the launch packet simply had an older copy of the already-edited note.