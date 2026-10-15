# Changelog

## Unreleased

- Settings cleanup, 2026-10-15, ticket 0d9e3882: `fork_agent` merged into the dispatch default agent, `dispatch_agent`, so one choice names the person's agent everywhere. `init` writes it into the workflow (dispatch's own default, `codex`, before dispatch is enabled); the workflow's setup step runs `metaform set --dispatch-agent <agent>`, and `fork wheel` and `fork upkeep` no longer take `--fork-agent`. A repository made earlier replaces `--fork-agent <agent>` in its workflow with that setup line when it moves to this release.
- Run the existing template upkeep path for registered module repositories after a successful newer wheel installation, retaining manual retries, BASE-027 and BASE-047.
- Scaffold module-only repositories, carry three-system CI reports into dispatched quality review, build reviewed modules over the released chassis, and dispatch template updates as pull requests, BASE-027.
