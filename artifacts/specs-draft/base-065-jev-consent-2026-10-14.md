# Draft for Rich: BASE-065 amended for the `jev` consent (ticket code.analyzer.refactoring#7, review C2, GAP-01)

Not a specification. This is the text I would propose for BASE-065 in `specifications/04-chassis-modules.md` once
Rich confirms it. The code as built on 2026-10-14 is the reference; it already behaves as written below.

## Where the code and the current record disagree

1. BASE-065's requirement starts the follow-on "when the configured code graph MCP and a working Jev/OpenRouter API
   key are available". The code now also requires the person-only setting `jev` to be on. With `jev` off, finishing
   a code intake starts nothing, writes nothing under `.metaform/refactor/` and sends nothing; the follow-on reports
   `skipped` with the reason `jev is off; only the person turns it on.`
2. "The extension checks for the key and code inventory capability." The extension, `refactor_extend` and
   `refactor_associate` now check `jev` first, then take the shared Jev configuration (`metaform.jev`). So the key
   read is the one `jev_endpoint` names (`OPENROUTER_API_KEY` or `TYPESAFE_API_KEY`), the model is `jev_model` (its
   default is the dated snapshot `typesafe/jev-1.13-20260917`, not the alias `typesafe/jev-1.13` the module used
   before), and the person can leave the module out with `jev_decisions` by not naming `refactor.associate`.
3. A run prepared while `jev` was on and resumed after the person turned it off sends nothing. It is marked
   `unavailable` with the same reason and resumes once `jev` is on again.
4. Acceptance 1 ("with working services") and 2 ("Missing keys, ...") do not name `jev`.

Still as the record says, and not changed by this ticket: run artifacts stay under the project's `.metaform/refactor/`
(review C2 fix 4), and `refactor_associate` is still declared `effect='read'` (review C2 fix 3). Both are filed as
their own tickets.

## Proposed record text

- Requirement: Completing a code intake automatically follows it with provider classification when the person has
  turned on `jev`, and the configured code graph MCP and the key for `jev_endpoint` are available. With `jev` off, or
  without those services, the ordinary intake still completes and nothing is sent. The same extension is callable
  for an existing intake through `metaform refactor extend` and `refactor_extend`, under the same consent.
- Why (added): classification sends the project's function bodies to a third party. `jev` is the person's consent
  to that, and only the person can set it. A key in the environment is not consent: people set
  `OPENROUTER_API_KEY` for the roundtable and for tools that have nothing to do with Metaform. Going through
  `metaform.jev` means one switch, one endpoint, one model setting and one decision list govern every Jev request
  Metaform makes, so a person who turns Jev off has turned all of it off.
- What this means, second bullet replaced: The extension checks `jev`, then the shared Jev configuration (endpoint,
  model, key, and `jev_decisions` as the decision point `refactor.associate`), then the code inventory capability.
  It checks `jev` again before each run is executed, so a run prepared while `jev` was on never sends after the
  person turns it off. The configured MCP supplies code evidence. The first useful Jev batch verifies a responding
  API and model before the remaining batches run. An unavailable service, or `jev` off, is reported as such, not as
  a completed classification.
- Acceptance, 1 and 2 replaced, 7 added:
  1. Finishing a code intake with `jev` on and working services starts the extension against the finished base.
     No-building and noncode finishes do not start it.
  2. `jev` off, missing keys, unavailable code MCP and failed API responses leave the ordinary intake complete and
     report the extension's outcome.
  7. With `jev` off and a key in the environment, finishing a code intake starts no run, writes no run files and
     makes no network request; `refactor_extend` and `refactor_associate` refuse with the same reason.
- Verified by: `src/metaform/modules/refactor/tests/test_follow_on.py::test_intake_finish_sends_code_to_jev_only_when_the_person_turned_jev_on`.
- Relates to (added): CLI-011 (person-only settings).
