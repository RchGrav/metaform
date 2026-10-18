---
name: metaform-ing-public-page
description: Use when asked to build or publish a metaform.ing page.
category: development
---

# metaform.ing is the cloud broker's domain; a public page is a release

- The domain is already claimed. The `cloud` module's default `cloud_url` is `https://metaform.ing`, and the `node` module's `broker` role is meant to run there: accounts, passkey sign-in, and `/mcp`.
- As of 2026-10-16 nothing answers there: `curl` to `https://metaform.ing/` fails with connection refused on port 443. The broker is not deployed.
- A static page at `/` would sit beside the sign-in and `/mcp` routes on the broker's Caddy. That route is not planned.
- Before writing any copy, ask the user one question at a time: the audience; which host serves it (the broker Node, deployed by the user's own `metaform node` verb, or a static host); whether the page may link to the private repo; and whether now is the time.
- Check each claim against the source before it goes on the page.
