# web

Metaform's one web GUI for the user: one server per Metaform home, serving every registered project.

## Purpose

People see the map in a browser. `metaform web` starts the server and prints its address; run again from any folder, it prints the address it already runs at. `metaform web stop` stops it. Before an intake, agents start it and tell the user the address, while `--web-autostart` is on, so the map can be watched as it is recorded. It ships enabled.

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

`server.py` runs the standard library's threading HTTP server. Every request must carry a `Host` header naming the server's own address and port; on a wildcard bind only the port is checked, since the token guards every request there. On a bind address other than loopback, every request needs the home's token, kept in `run/web-token`: as `?t=` on the page URL, which also sets an `HttpOnly`, `SameSite=Strict` cookie, as that cookie, or as the `X-Metaform-Token` header. It serves `page/` at `/`, `vendor/` under `/vendor/`, `/api/server` with its process id and home, and `/api/projects` with every registered project. It writes what went wrong to `run/web.log`.

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
