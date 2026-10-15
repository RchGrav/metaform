---
name: metaform-web-page-controls
description: Use when adding a web page header button or menu item.
category: development
---

# New web page controls go in an existing menu, never a new header button

The header gives back room in steps before it folds: `foldHeader` (`page/app/header/menus.js`) adds step classes only while the row overflows (search to its icon, tighter spacing, labels and padding, shorter names), and folds the rest behind the menu button last. The full row needs about 1,907 px at the default text size; at 1280 px it holds only at the steps' tightest, so a new header button can fold every control there and browser tests that click Agents or Board at 1280 px then fail.

- Put a new project-wide action as the first item of an existing menu: Agents (`#agentbox`) for agent actions, Window or Help for the rest.
- Before any header change, measure in a headless page: remove the fold, add the control, and compare the children's right edges with the header's edge. `scrollWidth` rounds and under-read the row by about 3 px, which let the selects be squeezed, so measure each child's own right edge against the header's right edge less its padding, not `scrollWidth`.
- A new write the page sends is a `/api/...` route in `web/server.py`. The spec record VIEW-011 says the viewer "writes exactly eighteen things" and lists them: add the new write to that list and its count, and to the test that checks dispatch writes come only from the page (`test_the_dispatch_writes_are_taken_only_from_the_page`, `web/tests/test_web.py`).
- Record the route in the module's README and CHANGELOG Unreleased. The spec amendment goes on the VIEW record it changes.
