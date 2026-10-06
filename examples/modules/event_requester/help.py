"""Embedded guidance exposed through the chassis module menu."""

MODULE_HELP = """Send work with request-work --prompt "Your exact instructions". This module
stores the prompt and publishes its revision reference on harness.request.
The harness_runner module queues work and returns a job id immediately. Its
harness.response event later produces data.event_requester.response with a
completed, failed, or cancelled status and exact request/response references.

Inspect events and records data.event_requester.response --provenance. Exit to the
base menu and use jobs show ID to inspect the responder's job. Until a responder
is loaded, requests remain inspectable events without a response.

Select fixture, Codex or Claude from the harness_runner module's harness-config
command. Provider selection belongs to the responder; the request protocol stays
the same. Exit returns to the chassis menu.

This module owns a local copy of the standalone showcase lifecycle scaffold
in template.py and adds its own feature contributions. Copy this package to
install it; the standalone showcase is optional."""
