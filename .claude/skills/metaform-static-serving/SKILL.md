---
name: metaform-static-serving
description: Use when editing Metaform web page static file serving.
category: development
---

# Metaform static serving: keep module identity and caching intact

Every page file the server sends is rewritten: each `/vendor/` address becomes `/vendor/v-` plus a 16-hex-digit digest of the vendor files. Never serve a page file unrewritten, and never import a vendor file by a path the import map also covers, or the browser loads two Three.js instances.

- Current-version vendor addresses are `public, max-age=31536000, immutable`. Unversioned or stale-version addresses stay `no-cache` with an ETag.
- Page parts keep ETag revalidation on every load. Files on disk keep plain `/vendor/` paths because the map-view build reads them.
- Gzip text, JSON and SVG of 1 KB or more when `Accept-Encoding` allows it. The gzip copy is cached by file stamp, carries an ETag ending in `-gzip`, and is sent with `Vary: Accept-Encoding`.
- `index.html` lists `modulepreload` links after the import map, built from the static imports reachable from the module scripts. A preload placed before the map is not resolved through it.
- Keep `disable_nagle_algorithm = True` on the handler; see the stdlib-http-nagle-stall skill.
- In `test_web.py`, match versioned vendor addresses with a regex such as `/vendor/v-[0-9a-f]{16}/three\.module\.min\.js$`, and keep the exactly-one-fetch count assertion.
- VIEW-003 still says vendor files are revalidated on every load; that no longer matches the code. Amend it through the spec-amendments skill rather than editing the code to match.
