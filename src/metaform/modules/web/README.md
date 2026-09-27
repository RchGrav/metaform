# web

Metaform's one web GUI for the user: one server per Metaform home, serving every registered project.

## Purpose

People see the map in a browser. `metaform web` starts the server and prints its address; run again from any folder, it prints the address it already runs at. `metaform web stop` stops it. Before an intake, agents start it and tell the user the address, while `--web-autostart` is on, so the map can be watched as it is recorded. It ships enabled.

Clear project in the header clears the selected project as `metaform clear project <project> --confirm` does, PROJ-025 and VIEW-019: it shows the command's caution, what goes and what stays, asks on the page, then clears through the same chassis operation and names any file it could not remove with what to do. Every open page then shows the project with no metaform until the next intake.

The page shows each node's condition from its work records, MAP-046: a node with an open `tbd` record is drawn ghostly, at 70% opacity, and turns solid when its task is done; one with an open `broken` record flashes red until it is resolved; `cruft` keeps its look. The panel lists the selected object's records with their note, task, held and reviewed flags, and the resolution once done. `/api/work` is the store's `work` read.

## Template version

Started from template 0.3.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ()`, `SHIPS_DISABLED = False`. `MODULE` declares `start`, its default verb, and `stop`, and a status hook.

## Common base used

`metaform.module` for the declaration, `Context`, `Status` and `Stop`; `metaform.settings` for its three settings; `metaform.home` for the home's folder and the registered projects.

## Verbs

- `start`, the default, so `metaform web` runs it: when this home's server answers at the address in `run/web.json`, returns `state: running` with its address; otherwise checks the port and bind address are free, starts `server.py` as a process detached from the terminal, waits until it answers, and returns `state: started` with its address. On a bind address other than loopback the address ends with `?t=<token>`, and `token` is returned too. A port held by another program stops with `Next: metaform set --web-port <port>`; an address it cannot bind stops with `Next: metaform set --web-bind <address>`. Tool `web_start`.
- `stop`: ends the recorded server and removes `run/web.json`. Returns `state: stopped`, or `state: not running`. Tool `web_stop`.

## Settings

- `--web-port`, a number, default 7433, for the whole home.
- `--web-bind`, text, default `127.0.0.1`, for the whole home. At a wildcard address, `0.0.0.0` or `::`, the printed address uses the machine's host name.
- `--web-autostart`, on or off, default on, per folder. While on, the status hook's notice tells agents to start the GUI before an intake and give the user its address.

## The server

`server.py` runs the standard library's threading HTTP server. Every request must carry a `Host` header naming the server's own address and port; on a wildcard bind only the port is checked, since the token guards every request there. On a bind address other than loopback, every request needs the home's token, kept in `run/web-token`: as `?t=` on the page URL, which also sets an `HttpOnly`, `SameSite=Strict` cookie, as that cookie, or as the `X-Metaform-Token` header. It serves `page/` at `/`, `vendor/` under `/vendor/`, `/api/server` with its process id and home, `/api/projects` with every registered project, and `/api/clear-preview` with what clearing a project removes and keeps. Its four writes, VIEW-011, are POSTs from its own page, with the page's `Origin` and a JSON body: `/api/apply-layers`, `/api/save-prompt`, `/api/remove-correction` and `/api/clear-project`, which clears only with `confirm` true. It writes what went wrong to `run/web.log`.

## Events

None.

## Sync and async

Every verb is a plain function.

## Layers

None. The web GUI reads through the data access object and writes only what VIEW-011 names.

## Lifecycle and cleanup

No `start` or `stop` hooks, and no tasks. The server is its own process, detached from the terminal that started it; `metaform web stop` ends it, and so do logout and restart. Nothing of it runs inside other Metaform commands.

## Modules relied on

None. The web GUI reads through the chassis's data access object and settings.

## Systems supported

Linux, macOS and Windows. On POSIX the server runs in a new session; on Windows as a detached process with no console.

## Resources owned

`page/`, the GUI's HTML, CSS and scripts, and `vendor/`, the bundled libraries with their licenses, VIEW-003. Under the home: `run/web.json`, the running server's record; `run/web-token`, the token for bind addresses other than loopback; `run/web.log`, what went wrong in the server.

## Installed and direct wheel

The same in both; the page and the vendor files travel inside the module.

## Demonstration

```
metaform web
metaform web --json
metaform set --web-port 7500
metaform web stop
```
