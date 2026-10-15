---
name: metaform-live-update-browser-test
description: Use when a browser test waits for a live Metaform update.
category: development
---

# Browser tests: drive the live change through the real write, then wait on the DOM

Make the change with the same CLI write a person would make, then `page.wait_for_function` on the text it should produce. Never sleep.

- Create the ticket with `run('map', 'work', 'op=add', 'node=element:...', 'condition=...', 'task=...', 'title=...', cwd=mapped)` and read it back through `store.work(open=True, limit=0)`. `store.add_work` tickets carry no item or title, so a row that shows them stays blank.
- Take the work with `store.take_work(id, steps=N, by='claude')`. In `test_web.py`, `live_session(id)` and `thread_line(id, 1, words)` set up the session and its thread.
- Trigger the first render with `relay.deliver('map.changed', {...'tables': 'dispatch'})`, then wait for the element count you expect.
- Make the live change with `run('map', 'work', 'op=step', f'id={id}', 'said=...', cwd=mapped)`, then wait for the row's text, with a timeout of 15000 ms.
- Show the wait depends on the code by mutation: remove the call that carries the update and the test must fail. Restore from a copy, as `shared-checkout-concurrent-edits` says.
- Run each file in its own pytest command. With `-k`, the paths after the expression did not all run in one command. Include browser tests with `-m 'browser or not browser'` and unset `DISPLAY` and `WAYLAND_DISPLAY`, so no window opens on the person's screen.
- For a change to an event path, measure idle CPU as `metaform-event-handlers-filter-first` says; the test does not replace it.
