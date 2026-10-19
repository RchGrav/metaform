# Draft spec changes for ticket bd730760 (code.interface.speech#b), for the owner's approval

Phone: quiet start, help from the system agent, and a direct port route, 2026-10-15, a system-review remediation of the phone self-check (ticket 0a044360). No table changes.

No record in `specifications/` names the phone or twilio. The phone's page banner was drafted as an amendment to VIEW-051 in `view-051-module-notices-2026-10-15.md`, which has not landed; this ticket reverses that banner, so that draft should not land as written. The bullets below are drafted for the owner to approve, each going after its record's `Status:` line.

## VIEW-051 (`specifications/09-viewer.md`)

- Amendment, 2026-10-15, system-review remediation, ticket bd730760 (code.interface.speech#b): the page shows no text from a module's check of something the person set up. twilio's status hook gives no notice, so `/api/notices` answers none for it, and the phone's findings stay in `run/twilio/twilio.log`, `run/twilio/check.json`, `metaform twilio check` and `metaform twilio status`. When a module raises dispatch's `setup-not-working` signal (BASE-057) and no system agent session runs, `setupNotice` in `page/app/agents/dispatch.js` shows one closable `info` banner from the signals the page already reads: "It looks like <feature> may not be working. Your system agent can look at it with you.", with the one action Talk it over, which starts the system agent (`callSystem`). The agent then takes the signal as its turn. Closed, the notice does not come back for the same signals. Why: a log dump in the terminal or an error banner is the wrong way to help someone who set up a feature; the system agent raises it with them one to one. Acceptance: `test_the_phone_checks_problem_is_never_a_notice_on_the_page`.

## BASE-057 (`specifications/04-chassis-modules.md`)

- Amendment, 2026-10-15, system-review remediation, ticket bd730760 (code.interface.speech#b): a module tells the person's system agent that a feature the person set up is not working with the signal `setup-not-working`, published as `signal.raised` with its own `key`, `feature`, `set_up`, `look` and `report`; dispatch's `collect` keeps the key as `signal_key`, and the producer clears the signal with the same key and `clear` true. The system agent's runner takes each such signal as a queued turn, after any turn in flight and never inside one, both when it hears the signal and when it starts, and clears the signal as it takes it, so each is given once. The turn is dispatch's `<setup_trouble>` prompt, a draft awaiting the owner's approval: the agent raises the matter as a colleague would, with no error text, and works through it with the person only if they agree. twilio raises it for the phone, once per set of findings, again when the findings change or a day after nobody asked for the check. Acceptance: `test_a_raised_problem_is_the_system_agents_turn_once_it_starts`, `test_a_problem_goes_to_the_system_agent_once_until_its_findings_change_or_a_day_passes_untaken`.

## A new record for the phone's direct route, if the owner wants one

No record covers the twilio bridge, so the direct route would be a new record rather than an amendment. A draft, for `specifications/04-chassis-modules.md` after BASE-065, numbered when it lands:

### BASE-0xx The phone bridge can be reached by a forwarded port, with TLS of its own

- Requirement: A person who can forward a port to their machine can have Twilio reach the phone bridge directly, with no Node or tunnel.
- Build: `twilio_bind` (default `127.0.0.1`) and `twilio_certificate` (a PEM holding the chain and key, empty behind the person's own TLS terminator), both global and person-only. The port stays 7441. The signature check holds on every route. `metaform twilio check`, when `twilio_public_url` resolves to this machine (its interfaces, or the address `checkip.amazonaws.com` reports) on a non-loopback bind, reports a closed port, a port that does not speak TLS, or a certificate Twilio would refuse, each with its next step. Under WSL2 with NAT networking it says the port reaches Windows, not Linux. The twilio README documents the port to forward, Twilio's Static Proxy ranges (Security and Enterprise Editions only), and the WSL2 steps.
- Acceptance: `test_the_direct_route_names_a_closed_port_a_failed_handshake_and_a_wrong_certificate`.
- Status: built 2026-10-15, ticket bd730760 (code.interface.speech#b).
