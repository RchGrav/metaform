    const said = fork ? text + attached : lead + withContext(taken, text + attached);
  const sent = await wrote('/api/dispatch-message', ...
Replacement applied by the system agent:
  if (told) CLICKED.told = true;  // told as it goes, so a follow-up sent before the answer does not tell it again
  const sent = await wrote('/api/dispatch-message',
...
  } else {  // the views' context and the click are kept for the resend
    contextBack(taken);
    if (told) CLICKED.told = false;
    box.value = text; growSay();
  }
Verification: "uv run pytest -m browser -n 0 -q ... -k \"what_the_person_last_clicked or queued_message_that_fails or message_sent_with_no_agent\" -> 3 passed"