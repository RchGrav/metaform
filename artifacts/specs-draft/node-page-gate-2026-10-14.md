# Draft for Rich: the Node's page gate and auth volume (ticket code.server.hosting#4, review C1 and H2)

Not a specification. The Node has no specification record (review MU-F6). This is the text I would propose once
Rich decides where Node records live. Code as built on 2026-10-14 is the reference.

## Where the code and the current records disagree

1. MAP (01-map.md, amendment 2026-10-08) and BASE-052 (04-chassis-modules.md) say "The page is the person's and is
   never refused." On a Node the page now refuses a signed-in account that is not the owner on every admin route,
   and refuses dispatch routes to every account below `dispatch` capability. Without a Node gate (local `metaform web`)
   the page is still never refused.
2. CLI-011's list of person-only settings does not name `node_projects`, `node_host`, `node_ssh_identity`,
   `node_ssh_public_key` or `intake_file`, which are now person-only. The review (H2) also says the list is stale in
   other ways; its proposed fix is the rule plus a pointer to the schema.

## Proposed record text

- On a Node, the page sits behind the authorization server's session. The gate (`/node/gate`) answers the account,
  its role and the classes of page route it may use: `read` and `write` for every account; `dispatch` only on a Node
  at `dispatch` capability; `admin` (settings, modules, prompts, bases, backups, removing or clearing a project,
  builds, MCP Apps tool calls) only for the owner. Caddy drops any client-sent copies of those headers, copies the
  gate's, and adds a per-deploy secret (`gate.env`). The page server, started with `--origin https://<domain>` and
  that secret, refuses any request without the secret or for another host, and any route whose class the account
  was not given. A write route not yet classed is admin. Why: before this, every signed-in account had the owner's
  power on the page, whatever `node_capability` said (review C1, MU-F1).
- The authorization server's accounts, passkeys and keys are on the `auth` volume, mounted into the auth container
  only. An older Node's `<home>/node` is moved there on auth's first start. Why: every container shares `home`, so
  code started from the page or MCP could add itself a passkey or an owner account.
- Acceptance: `src/metaform/modules/node/tests/test_node.py -k "non_owner or five_hosting or auth_database"`.
