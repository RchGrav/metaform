# Resolution of findings for `downstream.chair` (`user`)

Prepared by TunedMantis. These are decisions and proposed changes; no implementation changes are claimed.

Evidence scope: the supplied snapshot contains only `crates/roundtable-web/assets/index.html`, `crates/roundtable-web/src/app.rs`, and `crates/roundtable-web/src/tables.rs`, all beneath `source/`. References below use those paths relative to `source/`. The reviewers' cited `engine.rs`, `turn.rs`, `events.rs`, `config.rs`, README, and Intake specification are absent. Claims depending on those files are identified as reviewer-reported rather than independently verified.

## GF1 — Accept: contribution scores are not displayed

`index.html:234` retains `d.scores`, but `renderItem` at lines 339–355 never renders them. Rejections display `reasons` and a tooltip containing `note`; neither provides the complete evaluation. Peer ratings are rendered separately at lines 242–243 and 251, so the finding concerns contribution evaluations, not a total absence of numerical scores.

Change the code to render the evaluation supplied with each judged contribution, accepted or rejected, with labeled checks/scores and any available explanation. Preserve the explicit unjudged state and do not fabricate scores for missing evaluations. If rejected evaluations are reduced to reason strings upstream, extend the event payload using the evaluator's actual schema; that upstream reduction is reported by the reviewer but cannot be checked here. Record the missing contribution-score display in `elephant.gaps` until implemented. The author's explicit visibility claim warrants a fix rather than simply deleting the promised feature.

## GF2 — Accept the overpromise; qualify the word “contradicts”

A want can describe an aspiration, but this want's function reads as a guarantee of actual behavior. The page defaults to ten rounds and topics unchecked (`index.html:139–140`); the request type defaults topics to false and documents ten rounds (`tables.rs:29–34`). Its round default delegates to a core constant whose definition is absent. The two-unproductive-round termination rule is reviewer-reported from the absent engine.

Change the description to: “Runs a turn-based discussion among heterogeneous agents sharing a workspace, with optional judging and topic progression, subject to configured limits and chair commands, to help produce the requested deliverable.” Document ten-round and topics-off defaults and the reported unproductive-round stopping rule, with its exact applicability checked against the engine before publishing it as independently verified behavior. Do not remove useful limits or enable topics merely to match the old prose. Ending a run does not prove a deliverable exists; see GF12.

## GF3 — Accept the ambiguity; preserve graceful ending

An End control exists and dispatches `Command::End` (`index.html:406`; `tables.rs:165`). Thus `elephant.built` is not false merely because ending takes a rating phase. However, the confirmation mentions shutting down every harness without explaining the intervening phase or the second-click behavior. Rating events are visibly supported (`index.html:242–243`); the first-End/second-End engine semantics are reviewer-reported, not independently verified here.

Describe the reported contract explicitly: first End requests the closing rating phase, after which the table shuts down; another End during closing stops immediately. Change the confirmation to explain that sequence. Have the UI track the engine's closing state and label the available action accordingly, such as “Stop now” during closing, rather than repeating the initial confirmation. Keep the engine's graceful behavior unless a separate requirement calls for immediate cancellation.

## GF4 — Accept as documentation coverage, not missing implementation

The omitted features are present: explicit or proposed next topics (`index.html:405`), judging toggle (407), OpenRouter settings (`app.rs:230–243`), stored-table replay (`app.rs:279–341`; `index.html:371–401`), received prompts (255, 321–331), and identity/session selection (412–457; `tables.rs:127–128`).

Expand the description with a compact account of these chair capabilities. Explain that replay reads a record rather than restarting a table, and that identity resume requests an earlier session from its harness rather than guaranteeing every harness can resume it. Mention that the key is held in memory and settings changes are forwarded to active tables' JEV instances. Topic progression and judging should state their configuration/key dependencies; the form already warns that absent an OpenRouter key, contributions are shared unjudged (`index.html:136`). No new controls are needed to resolve these omissions. Calling every omitted secondary feature Major overstates the implementation impact.

## GF5 — Accept: access prerequisites belong in the description

All registered `/api` routes use chair authentication (`app.rs:143–154, 192–198`), and the outer router checks Host and any supplied Origin (160, 170–183). The page itself at `/` is not behind chair-token authentication. The browser extracts the fragment token into tab session storage, removes the fragment, uses Bearer authentication for fetch, and supplies a token query parameter for the event stream (`index.html:164–169, 508`). The middleware actually accepts a query token for any API route, though the page uses it for the stream.

Document opening the startup-provided authenticated link, keeping the chair credential private, and using a server address accepted by these checks. State that reading/controlling the API needs the credential and participant tools use separate authorization. Preserve the protection. The page itself instructs use of the startup link (468, 505–506); the startup code printing that link is absent.

## GF6 — Partly accept; separate the four claims

- **`d.truncated`:** line 234 copies it, but the supplied renderer never uses it. Remove this dead client property unless an actual event contract and display requirement justify it. The claim that `Contribution` lacks the field depends on absent `events.rs`; this is not evidence of a current truncation-display failure.
- **512 default:** line 177 initializes temporary client state to 512, but `roundtable.opened` replaces it with `d.base_allowance` and updates existing seats (218); floor events also supply allowances (227). The creation form sends null for an empty limit (137, 486), matching `tables.rs:23–25`. Reject the implication that ordinary new tables are constrained to 512 characters. This also holds on replay: `openPast` (`index.html:391–401`) re-applies the recorded `roundtable.opened` event, whose unconditional `t.base = d.base_allowance` (`index.html:218`) overwrites the 512 default before any seat card renders, so a replayed no-limit table correctly shows "no length limit" (`index.html:317`). `history_list`'s summary lacking `base_allowance` (`app.rs:289`) is irrelevant — that summary feeds only the Past-tables list, not seat cards. No code change needed; the 512 is an inert placeholder.
- **Hold:** accept the need to document that it pauses scheduling new turns while ongoing work can continue, based on the reviewer's engine account. The supplied web code proves command dispatch, not cancellation semantics. “Hold” should not imply interrupting active agent work.
- **Empty gaps:** accept that confirmed mismatches such as GF1 belong there. An omitted description of an already implemented feature is fixed in the description, not recorded as a missing feature. Do not list all review comments indiscriminately as product gaps.

## GF7 — Accept the need to reconcile the accounts

“Observation-only” is a historical audit characterization, whereas the owner's later account explicitly intends interaction. Current source confirms guidance, hold/resume, advance, judging and end commands (`tables.rs:157–165`). There is no basis for restricting the current chair to observation to preserve the older wording.

Amend the decision to date and delimit the earlier audit: it described an observation-only chair in that audit's scope; the current chair can interact through the implemented controls. If that historical limitation cannot be substantiated from the audit, remove it as supporting evidence for current behavior. Keep the decision's useful definition of the chair as the person convening the table.

## GF8 — Accept: map terminology lacks a local explanation

Explain that `downstream.chair` is the stable map address and `user` is its human-facing alias; they need not be identical. Define the chair's responsibilities in ordinary language beside the role metadata. Link and summarize the authoritative meaning of `CQU` and the relevant Intake 3.1 naming rule before retaining the claim that `user` is invalid in that role. Neither authority is supplied, so inventing an acronym expansion or renaming the element based on the unsupported rule would be unjustified. If no authoritative definition is available, remove the unexplained rule claim and retain an explicit plain-language role description.

## GF9 — Accept the description omission; reject a missing-feature inference

The chair already enters the objective and selects seats, harnesses/custom commands and models in the New table dialog (`index.html:129–145, 409–457`). Submission includes objective and seats (484–488), and the server turns them into table configuration (`tables.rs:94–144`).

Add these setup capabilities to `elephant.built`: “The chair enters an objective and shared workspace and selects participants by seat, harness and optional model or resumable identity.” No implementation work or feature-gap entry is justified for objective/participant selection. The separate score-display gap still needs recording.

## GF10 — Accept: guidance delivery needs a contract

The page says guidance goes to every participant at its next turn (`index.html:115, 296`), posts a guidance command (402), and renders chair events separately from contribution events (248, 356). `tables.rs:162` maps nonblank guidance directly to `Command::Guidance`. This supports describing guidance as chair input rather than an ordinary participant contribution.

Document the recipients and deferred delivery: guidance is intended for all participants on their next turns, not injected into a prompt already in progress. State whether it bypasses JEV contribution judging. The separate web command path is consistent with bypass, but cannot establish the engine's judging behavior; verify that explicit clause in the missing command handler. Also specify retention across subsequent turns from that handler rather than assuming guidance is delivered only once or forever.

## GF11 — Accept: add access instructions and a short glossary

`app.rs:156, 164–165` serves the page at `/` through the supplied HTTP listener. Document opening the server's printed link at its configured HTTP address, including the chair token as described in GF5. Do not invent a default port or bind address: the executable selecting them is absent.

Define a table as one discussion run with an objective, configured participants and shared workspace; a rejection/veto as a participant contribution withheld from the group by evaluation while visible to the chair; and JEV as the contribution evaluator. Verify any acronym expansion against project documentation before adding it. These changes make the description understandable without requiring knowledge of internal labels.

## GF12 — Accept: stopping and acceptance are distinct

Neither the supplied API nor page provides a deliverable-acceptance command or a proof that work exists when a table ends. The chair requests a substantive deliverable and assesses whether it satisfies the objective; that acceptance responsibility should be stated as the intended human workflow, not asserted as an implemented completion detector.

Replace “until the work is produced” as proposed in GF2. Say explicitly that chair-requested termination, configured limits, and engine stopping rules can end a run without the chair accepting the deliverable. Evaluation scores and participant ratings judge contributions or participants; they do not establish deliverable acceptance. No new automatic completion mechanism is required by this element's stated design.
