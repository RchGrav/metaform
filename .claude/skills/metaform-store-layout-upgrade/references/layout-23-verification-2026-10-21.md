# Layout 23 verification, 2026-10-21

- Before the upgrade: the metaform project's three live stores (main, app-internal-refactor, feature-code-alignment-20261013) were at version 22 and the base had no notes to move in the live data.
- Upgraded by relayed MCP servers at 16:01Z: each store got one backup under `~/.metaform/backups/upgrade-23`.
- Notes moved: 0 in every live store. app-internal-refactor's 19 noted versions were all history, which is kept as-is until `map collapse` rewrites it.
- Other projects' stores (ccl-min, flask, mgm-main, roundtable) stayed at 22 until opened.
- Fixture check: a layout-22 map with a note in its base, after the new upgrade, has no base note, the text in the critic layer, and the old text in history.
