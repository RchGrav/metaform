# Cold build check 3

Gaps that stop a builder on the path to the first working test, build order steps 1 to 8. Items already in OPEN-QUESTIONS.md or a section's Open questions are left out.

1. BASE-041, MCP-010, MCP-024. The wheel's `dist-info` is specified as exactly `METADATA`, `WHEEL` and `RECORD`, with no `entry_points.txt`. Without one, installing the wheel creates no `metaform` command, so `uvx --from <wheel> metaform mcp serve` and the proof step fail. The builder has to add a file the record leaves out.

2. BASE-041, BASE-022, BASE-026. `Requires-Dist` lists "the chassis's dependencies" plus each enabled module's `DEPENDENCIES`. No record says where the chassis's own list is read from at build time. The repo wheel carries every repo module, so its installed metadata also holds `mcp`. Read from that metadata, the list breaks the acceptance that a map-only build lists only the chassis's and map's dependencies.

3. BASE-036, BASE-039, MCP-009, MCP-024. `intake prompt` returns the intake text as a string result. BASE-036 says how the CLI prints an object result and a list result, but not a string. Over MCP, the result block is JSON, which makes the text a quoted string. MCP-009 requires the returned text to equal the stored file byte for byte, so the builder must pick: `say`, raw printing, or JSON decoding.

4. BASE-001, CLI-028, MCP-009, CLI-029. BASE-001 says chassis verbs never branch on a module id. Status (CLI-028 line 9) and `metaform help agents` are chassis output, yet they check whether the `intake` module is on and call `has_intake()` to show the notice. The module contract in BASE-035 has no hook that lets a module add status lines or a notice.

5. STORE-022, STORE-023, CLI-020, CLI-019, BASE-010, BASE-019. The template's history is a layer, and layers live only in project stores. In a folder with no project, `ctx.store` is None. CLI-020 still requires the template's verbs to exit 0 in an empty home. The select choices function in CLI-019 and the event subscriber also read the template's data, but the choices function takes no context, so it cannot tell which project to read.

6. BASE-028. The acceptance test needs two concurrent tool calls, each naming a different project. No record gives a tool a way to name its project. The server's folder is fixed at start, and MCP-011 is open. No record says whether the chassis `project` setting can be passed as a per-call switch on module verbs.

7. STORE-024, STORE-032, STORE-007, BASE-039. `discard` deletes "the layer and every row written to it". STORE-007 keeps identity rows, in `element_ids`, `join_ids`, `subtype_ids` and later `identities` and `item_ids`, "for as long as the store exists". No record says whether discard also removes those rows and the `types` rows it wrote.

8. STORE-028, STORE-027, CLI-011, BASE-043. The named options of `query` are "switches with the same names", and `export` takes a repeatable `--layer`. CLI-011 says every long switch is a setting, and BASE-043 passes data fields as `name=value` nouns. `--as`, `--raw` with the map module disabled, and `--layer` are not settings. The builder must choose a grammar.

9. CLI-002 and CLI-031. The exact error for `unset --all` differs. CLI-002 gives `--all is not a switch. all is an argument.`, and CLI-031 gives `--all is not a setting. A switch names one setting.`

10. CLI-022 and CLI-031. The exact output of a narrowing `set` differs. CLI-022 prints `Success: updated 1 key` and shows the empty `commands` value as `all`. CLI-031 prints `updated <n> key(s)` and shows an empty value as `(none)`.

11. CLI-003 and STORE-031. CLI-003's example registers a project named `-scratch` after `--`. STORE-031's id rule, `^[a-z0-9][a-z0-9_-]{0,63}$`, refuses that name.

## Resolution

1. BASE-041: the dist-info now includes `entry_points.txt` with `metaform = metaform.cli:main` and a `[metaform.modules]` line per carried module; acceptance runs `uvx --from <wheel> metaform --version`.
2. BASE-041 and BASE-026: the chassis's list is `[project].dependencies` from `pyproject.toml`, carried as `CHASSIS_DEPENDENCIES` in `metaform/_build_info.py`; `Requires-Dist` is that list plus the carried modules' `DEPENDENCIES`; `mcp` is only the `mcp` module's requirement.
3. BASE-036: a string result is printed byte for byte on the CLI and returned over MCP as one unmodified text block; acceptance checks `intake prompt` on both.
4. BASE-035 adds the module status hook, `status(ctx) -> Status(lines, notice)`, called generically in module id order; BASE-001, CLI-028, MCP-007 and MCP-009 use it; BASE-039 defines the intake module's hook.
5. CLI-019: choices functions receive the Context and return no choices without a project; CLI-020: project-needing module verbs stop with `Next: metaform add project <id> <path>` in an empty home; STORE-022 covers the template's verbs, subscriber and choices.
6. New MCP-025: every tool takes an optional `project` argument that overrides the folder's project for that call; BASE-028 and MCP-003 point to it; the no-project fallback stays D37.
7. STORE-024 and STORE-032: discard removes the layer's content rows, provenance, sources and layer row, and keeps identity and `types` rows, STORE-007; BASE-039's discard row matches.
8. STORE-027 and STORE-028: export's `file` and `layer` and query's named options are `name=value` nouns, BASE-043; `query` takes only `--json` as a switch.
9. CLI-031 points to CLI-002 for the `unset --all` error text.
10. CLI-022 owns the exact `set` output, with and without narrowing; CLI-031 points to it; the empty `commands` value is shown as `all`.
11. CLI-003's example now passes an observation beginning with `-40` after `--`, a valid noun of BASE-040.
