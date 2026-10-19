---
name: headless-page-smoke-check
description: "Use when a page or GUI edit needs a load or click check."
category: development
---

# Load the live page headless before calling a page change working

Confirm a page change by loading the page in headless Chromium and clicking the control under test. Run `scripts/page_smoke.py` (in this skill folder) with the project venv's python in isolated mode: `.venv/bin/python -I scripts/page_smoke.py URL '#control'`. It prints the HTTP status, the click result, and any console errors or uncaught page errors.

Why: static checks of page scripts give false findings. A regex that reads only the first name after `export const` misses names declared after a comma, so one checker reported 14 missing exports that were not missing. Treat a static finding as a lead until the page load confirms it.

- GPU and WebGL warnings are not failures; the script reports only `error` messages and uncaught exceptions.
- A click that times out is a finding: report the selector and the error, not "it works".
