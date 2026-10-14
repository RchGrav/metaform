# Node trust chain (as built 2026-10-14)

Code is the reference; the Node has no specification record yet.

## Flow

1. Caddy asks `/node/gate` before every page request. The gate answers the account, its role and its route classes in `X-Metaform-Account`, `X-Metaform-Role` and `X-Metaform-Classes`.
2. Caddy strips any client-sent copies of those headers, copies the gate's three, and adds `X-Metaform-Gate` from `gate.env`. Host and Origin pass through unchanged.
3. The page server (`web/server.py`, started with `--origin` and the secret) checks the gate secret, the Host, and for writes the Origin, then `route_class(method, path)`.

## Classes

- `read` and `write`: every account (`config.page_classes`).
- `dispatch`: only when `node_capability` is `dispatch`.
- `admin`: settings, modules, prompts, bases, backups, removing or clearing a project, builds, MCP Apps tool calls. Owner only.
- A POST not in the route table is `admin` (fail closed).

## Secrets and storage

- `gate.env` is written once by `write_project`/`update` through `_keep_gate`, mode 0600, and given as `env_file` to caddy and web only. A broker has none.
- `authserver.node_folder()` is `METAFORM_NODE_AUTH` or `home/node`. The `auth` volume is mounted at `/data/auth` into the auth service only (`config.AUTH_IN_IMAGE`). `move_from_home()` moves an older Node's entries on the auth service's first start and deletes the old folder. Do not mount over `home/node`: that hides accounts from auth while leaving them readable by web and mcp.

## Open gaps

- `run/node-introspection` (the credential mcp uses to check tokens) is still on the shared home, so web can read it. The review's fix is a read-only mount into mcp only. Not done.

## Tests

`uv run pytest src/metaform/modules/node/tests/test_node.py -k "non_owner or five_hosting or auth_database" -q`, with `-k` on the Caddyfile and compose assertions in the first test.
