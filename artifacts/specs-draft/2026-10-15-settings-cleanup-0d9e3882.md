# Spec amendments drafted for the settings cleanup, ticket 0d9e3882 (2026-10-15)

The ticket asked that each record describing a changed setting be updated to match what is built. The
metaform-spec-amendments rule says a worker drafts the wording here, and the owner lands it once they approve it.
Each bullet below goes after its record's `Status:` line, marked `approved by the owner` when it lands. The code is the
reference; nothing here asks for a code change.

## specifications/05-cli-settings.md

### CLI-011 Every long switch is a setting

- Amendment, 2026-10-15, settings cleanup, ticket 0d9e3882: the list of person-only settings names keys that no longer
  exist. `agent_command` (web) is removed; nothing read it since 2026-10-03. `fork_agent` merged into dispatch's
  `dispatch_agent`. `dispatch_steering`, `dispatch_stderr_kb` and `dispatch_retry_seconds` are constants
  (steering always on when the agent offers it, `runner.STDERR_KB` 64, `RETRY_SECONDS` 30). `dispatch_agent_options`
  was already split by P199. `dispatch_wait_seconds` is no longer person-only: it is `per_call`, a switch of
  `dispatch wait` alone, never stored, since it paces only the agent that calls it. `dispatch_agent_strengths` is now
  `dispatch_<agent>_strengths`, one person-only setting for each agent `agent_choices()` returns. A switch kind
  CLI-011 does not name is now built: `per_call=True` (configuration#5) for `--http`, `--raw`, `--critic`,
  `--dry-run` and `--dispatch-wait-seconds`. Values that are not configuration have left the settings: constants
  beside their code, the page's view state (web `view.py`, VIEW-011's amendment), the A2A peers as records with verbs
  (MCP-040's amendment). The one-time carry of stored values out of a changed setting is
  `settings.carry_once(step, carry)`, marked `carried:<step>` in the home's meta.

### CLI-034 `--debug` and `--report` decide what agents are asked to report

- Amendment, 2026-10-15, settings cleanup, ticket 0d9e3882: `report` is removed. Nothing had read it since
  2026-09-29, as this record's Build says. `--debug` is the one setting here; the acceptance line about the intake
  text now reads "whatever `--debug` is". Where a project report is asked for stays open.

## specifications/04-chassis-modules.md

### BASE-052 The dispatch module starts an agent on a ticket through ACP

- Amendment, 2026-10-15, settings cleanup, ticket 0d9e3882: `dispatch_steering`, `dispatch_stderr_kb`,
  `dispatch_terminal_kb`, `dispatch_retry_seconds`, `dispatch_registry_hours` and `dispatch_usage_traces` are no
  longer settings. A message is steered into a turn whenever the agent advertises steering. The thread keeps 64 KB of
  stderr (`runner.STDERR_KB`), a terminal 1024 KB when the agent names no limit (`runner.TERMINAL_KB`). A retry first
  waits 30 seconds, doubled each time (`RETRY_SECONDS`). The registry is read again after 24 hours or with
  `refresh=true` (`REGISTRY_HOURS`). Every turn is a span where an OpenTelemetry SDK is set up.
  `--dispatch-wait-seconds`, 50 by default, is given on `dispatch wait` alone and never stored (`per_call`).
  `dispatch_agent_strengths` is `dispatch_<agent>_strengths`, one for each agent, carried once from a stored list by
  dispatch's start (`carry_strengths`).

### BASE-062 Editors mount Metaform as their ACP agent

- Amendment, 2026-10-15, settings cleanup, ticket 0d9e3882: `dispatch_serve_commands`, `dispatch_serve_record` and
  `dispatch_serve_mcp` are removed. Metaform's commands are always offered as the editor's slash commands where a
  module gives one. Editor sessions are always recorded on the held ticket "Sessions from editors". MCP reaches an
  agent over ACP whenever it says it takes MCP-over-ACP, else as a stdio server.

## specifications/06-mcp-install.md

### MCP-040 Metaform talks to the A2A peers the person names, and to no other

- Amendment, 2026-10-15, settings cleanup, ticket 0d9e3882: the peers are no longer the list setting
  `mcp_a2a_peers`. As one list, storing it replaced every peer at once. They are records for the whole home in
  `<home>/mcp/a2a-peers.json` (`a2a_peers.py`). `metaform mcp a2a_peer_add <name> <card URL> [token=<token variable>]` adds a
  peer or replaces the one of that name, and `metaform mcp a2a_peer_remove <name>` removes one; both run on the
  command line only and are refused in an agent's session. `mcp a2a_peers`, also the tool `mcp_a2a_peers`, lists them.
  The mcp module's start carries a stored list over once per home and removes its rows. The project table `a2a_peers`
  still caches each peer's card. `mcp_introspection` and `mcp_tasks` are removed in the same cleanup: an exposed
  server checks tokens at `oauth.DEFAULT_INTROSPECTION`, and tasks are offered to every AI tool that declares the
  extension.

## specifications/09-viewer.md

### VIEW-011 The viewer writes exactly eighteen things

- Amendment, 2026-10-15, settings cleanup, ticket 0d9e3882: how the person's page looks right now is view state, not a
  setting. The signs, the lens, the flow mode, the depth, the flow edges, the 2D map's direction, what the pointer
  shows, node zoom, the agents window, the physics, and the toolbar, layout, workspaces and workspace in use are kept
  by `view.py`, per account behind a Node's gate and the owner's otherwise, in `<home>/web/view.json`. They are
  written by `POST /api/view {key, value}`, classed read like `/api/hints` because any account keeps its own, and read
  by `GET /api/view`. The page no longer writes these keys through `/api/settings`. Reading the page's settings and
  view writes nothing, and a page load writes no setting. The web module's start carried any stored value over once
  per home and removed the rows.

### VIEW-023 The page offers a variety of color themes, and the graph stands clear of the background in each

- Amendment, 2026-10-15, settings cleanup, ticket 0d9e3882: the theme is the setting `web_theme`, global, whose choices
  are the theme names, `space` first and the default. It replaces `web_graphics`, which the page rewrote from the
  theme. The person's choice writes it: the picker, U, the Ultra choice in the map bar and the settings screen. A
  settings read applies a stored theme and writes nothing. Until a theme is chosen, each browser keeps the one it last
  showed, so no one's look changed when the theme became a setting. `space` draws the 3D map in outer space.
