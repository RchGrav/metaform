# DocileIsotope — code evidence for resolution

Supporting line-level evidence for the verdicts in `resolution.md`, from the provided source.

## GF2 — reason never reaches the agent
`decide()` returns only an option index; the reason goes to the bus:
```
harness.rs:920-928   bus.publish(PermissionDecided { ... allowed, reason, ... });
harness.rs:929        option.map(|(index, _)| index)
harness.rs:947        Some(index) => Selected(request.options[index].option_id.clone())
harness.rs:948        None => Cancelled
harness.rs:970-971    Selected / CancelledPermissionOutcome
```
The response carries an `option_id` or `Cancelled` — no reason string.

## GF5 — permission edge cases
```
permission.rs:130-131   if outside.is_empty() { Allow }        // no-location => allow any kind
permission.rs:58-60     !absolute && !cwd.absolute => false   // unknown cwd => refuse
permission.rs:68         MAX_SYMLINKS = 40
harness.rs:964           Command => (Some("execute"), vec![command.cwd.0])
harness.rs:910-914       allowed && no allow option => downgrade to reject
harness.rs:905-909       allow() prefers AllowOnce over AllowAlways
```

## GF6 — lifecycle behaviors
```
harness.rs:317-319/329-331  AUTH_REQUIRED -> authenticate() then retry session/new
harness.rs:350-384          authenticate() : v1 authenticate / v2 auth/login
harness.rs:392-428          resume_session: v2 resume, v1 resume else load
harness.rs:432-459          load_v1 sets replaying=true (replay suppressed)
harness.rs:465-506          set_config only for advertised options
harness.rs:1118-1131        mcp_server_v2 bails on "sse"
harness.rs:848-860          idle ends turn only if turn.active
harness.rs:266-276          on exit: fail_open_turns
harness.rs:602-644          shutdown(): session/close each open session
process.rs:25-27,132-148    EXIT_GRACE=1s, TERMINATE_GRACE=2s, then SIGKILL group
process.rs:17-18            STDERR_LINES=40, STDERR_LINE_BYTES=2000
process.rs:63-70            env_remove applied before .envs()
```

## GF3 / GF7 — v2 status inconsistency
- `verified` (element.md 2026-11-05): "ACP v2 not implemented."
- `harness.rs:198-229`: launches v2 first, falls back to v1.
- `elephant.built` (element.md 2026-11-07): "speaks ACP v2 first and v1 as a fallback."
- `verified` note itself names v1-only live checks ("ACP v2 not implemented").

## GF9 — reply rule
- `final_message()` (harness.rs:168-170): last non-empty segment.
- v1 splits segments on tool calls (harness.rs:746-759) => "after the last tool call" coincides.
- v2 segments are per-message-id; tool calls do not split (harness.rs:819-832).

## GF1 / GF8 — scope: workspace vs project root
- decision (element.md:108): "Scope = the project root that contains the shared workspace."
- gate RT-G18 (element.md:147): "outside the workspace."
- GF1: code default is `cfg.scope` = the workspace; web page sends no scope.
Note: cited files (`engine.rs`, `config.rs`, `index.html`) are not in the provided source.
