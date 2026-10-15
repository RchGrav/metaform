---
name: metaform-twilio-phone
description: Use when editing the Twilio phone bridge or phone check.
category: development
---
# Twilio phone: silent to the person, raised to the system agent

The phone check never shows its errors to the person, not even as one line. A problem goes to the person's system agent, which raises it with them. Any new check output follows this rule.

- Every check line is written with `write_log(echo=False)`. `web start` prints nothing for the phone, and the page shows no phone banner. Status lives in `twilio.log`, `check.json`, `twilio check` and `twilio status`.
- A check nobody asked for (web start, the bridge's own checking) raises dispatch's `setup-not-working` signal through `troubled()`. A check someone asked for (the verb, from CLI or MCP) is `asked=True`: it raises nothing and marks the raise taken.
- Raises are recorded in `run/twilio/raised.json` as key, findings fingerprint, `at`, `taken`. A new key raises and clears the old one. The same key re-raises only if untaken and after a day (`AGAIN_SECONDS`). Findings that come back ok clear it. Signal mechanics are in metaform-module-signals.
- `twilio_status` and `twilio_check` are MCP tools only when the phone is begun and `METAFORM_ROLE` is unset or `system` (`listed=helps`). `check fix=true` is refused over MCP; the person runs it.
- Direct route: `twilio_bind` (default 127.0.0.1) and `twilio_certificate` (one PEM with chain and key) are global, person-only, category advanced. `selfcheck.direct` names a closed port, a wrong certificate or missing TLS, each with its next step. Mirrored WSL2 networking adds no WSL step; NAT does, and a unit test covers it.
- Tests: after `run()` in a test, import `metaform.modules.twilio` again inside the test, or its globals can be gone (NameError on selfcheck). Stub `twilio._publish` to capture signals, and stub `twilio.project_of` when the temp folder has no registered project. Reuse the test module's `bridge`, `inbound` and `self_signed` helpers for the HTTPS path.
