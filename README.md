# Metaform

Metaform keeps a functional map of a project: what each part is for, who
receives what it does, and how it does it. Agents read the map before they
work, so they start from the project's purpose.

## Install and start

```
uv tool install metaform          # or: pip install metaform
metaform help                     # short overview
metaform add project mgm ~/mgm-main
cd ~/mgm-main && metaform         # status for this folder's project
```

All data lives in `~/.metaform` (set `METAFORM_HOME` to move it). Nothing is
written into a project's folder.

## The command line

Commands are verbs, the words after them are the nouns they act on, and
switches change how they run.

| Command | Does |
|---|---|
| `metaform` | Status: home, folder, project, modules |
| `metaform help [intro\|commands\|switches\|<thing>]` | Overview, indexes, or a man page |
| `metaform <command> --help` | Syntax only |
| `metaform add project <id> <path>` | Register a project |
| `metaform list projects\|modules` | List them |
| `metaform enable\|disable module <id>` | Turn a module on or off |
| `metaform set --<setting> <value> [--glue]` | Save settings |
| `metaform unset --<setting>\|all [--unglue]` | Return settings to defaults |
| `metaform config [--show]` | Settings screen, or print settings |
| `metaform <module> <verb> <nouns> [--adverbs]` | Run a module's verb |
| `metaform mcp` | Serve this folder's module verbs as MCP tools |

## Settings

Every setting is at its default, set, or glued. `unset all` returns settings
to their defaults and skips glued ones; `unset all --unglue` resets those too.
Out of the box the defaults are the working settings.

Folder settings belong to the folder you run in. `project` defaults to the
registered project that contains the folder; `set --project <id>` works on
another project from here. `commands` narrows which command groups are shown
and run in a folder; `unset --commands` restores them all.

## Modules

A module is a folder with `SUPPORTED_OS` and `MODULE = Module(...)` in its
`__init__.py`. Metaform finds modules in the package itself, in
`~/.metaform/modules/`, and in installed packages with a `metaform.modules`
entry point. Start from `src/metaform/modules/template`, which shows every
feature once and documents each in its README.

## Agents over MCP

```
claude mcp add metaform -- metaform mcp
```

Each module verb on the folder's command surface becomes a tool named
`<module>_<verb>`, for example `map_where` and `map_element`. It takes the words
the CLI takes after the verb as `nouns`, and each switch as a named argument.

## Tests

```
uv pip install -e '.[dev]' && pytest
```
