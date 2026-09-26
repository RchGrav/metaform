# Vendored files

Every file the web GUI loads is served from this folder or `page/`, so it works offline and sends nothing to a third party, VIEW-003. Each file is an unchanged release file with its license beside it.

| File | What | Version | License | Source | SHA-256 |
| --- | --- | --- | --- | --- | --- |
| `three/three.module.min.js`, `three/three.core.min.js` | three.js, which draws the 3D view; the module build imports the core file beside it | three 0.180.0 | MIT, `three/LICENSE` | https://registry.npmjs.org/three/-/three-0.180.0.tgz, `package/build/` | `e2b5ee6bccd38fd6d8a2428546b83c5f2426d84b152ef82be8055556e3b40eb6`, `61ba0df005b05991361d040d8ff670e1aadfd0ce7aeebd1fdb0725957a8957de` |
| `d3/d3-force-3d.min.js` | the 3D force layout, run in a worker | d3-force-3d 3.0.6 | MIT, `d3/d3-force-3d.LICENSE` | https://registry.npmjs.org/d3-force-3d/-/d3-force-3d-3.0.6.tgz, `package/dist/` | `412b4aadc3218aa65de10b70ba3324dd365d4bf7a061299fa682f530e8506ee9` |
| `d3/d3-binarytree.min.js` | used by d3-force-3d | d3-binarytree 1.0.2 | MIT, `d3/d3-binarytree.LICENSE` | https://registry.npmjs.org/d3-binarytree/-/d3-binarytree-1.0.2.tgz, `package/dist/` | `34ee89660516611365de94ab44ff8e06d968f6bfb7b3772667d12793a4bc5b57` |
| `d3/d3-octree.min.js` | used by d3-force-3d | d3-octree 1.1.0 | MIT, `d3/d3-octree.LICENSE` | https://registry.npmjs.org/d3-octree/-/d3-octree-1.1.0.tgz, `package/dist/` | `62c23034a7a7e9c3d5cb3118e108ac82ceffed0351f2d7b6400ddc66cd2643a2` |
| `d3/d3-quadtree.min.js` | used by d3-force-3d | d3-quadtree 3.0.1 | ISC, `d3/d3-quadtree.LICENSE` | https://registry.npmjs.org/d3-quadtree/-/d3-quadtree-3.0.1.tgz, `package/dist/` | `57e2ad12824ed82893ba447523f2a2fb9beeb9222aafb2c778a9f5b313348b0e` |
| `d3/d3-dispatch.min.js` | used by d3-force-3d | d3-dispatch 3.0.1 | ISC, `d3/d3-dispatch.LICENSE` | https://registry.npmjs.org/d3-dispatch/-/d3-dispatch-3.0.1.tgz, `package/dist/` | `94b3bbdb6b98dc1325a15762b051013e8253999b0e0436b27d1da17b952ba0af` |
| `d3/d3-timer.min.js` | used by d3-force-3d | d3-timer 3.0.1 | ISC, `d3/d3-timer.LICENSE` | https://registry.npmjs.org/d3-timer/-/d3-timer-3.0.1.tgz, `package/dist/` | `911ceda305f014b6b53ca68d5c896a9a387da120cfd56a421a2c60cca2fc9b36` |
| `mermaid.min.js` | the 2D layout | Mermaid 12.0.0, the build vetted on branch `main-wip-2026-09-24` | MIT, `mermaid.LICENSE` | https://registry.npmjs.org/mermaid/-/mermaid-12.0.0.tgz, `package/dist/mermaid.min.js` | `28fca7ae6ebc7ed7bb63bde63136a74bfef14f296a57e403657eeb8b32836073` |
| `fonts/IBMPlexSans-Regular.woff2` | IBM Plex Sans 400 | @ibm/plex-sans 1.1.0 | SIL Open Font License 1.1, `fonts/IBM-Plex.LICENSE` | https://registry.npmjs.org/@ibm/plex-sans/-/plex-sans-1.1.0.tgz, `package/fonts/complete/woff2/` | `ba711a3085ff9f27440b6b9c4550cfc47c97bf36591d5da958b975bb3add8c1a` |
| `fonts/IBMPlexSans-Medium.woff2` | IBM Plex Sans 500 | @ibm/plex-sans 1.1.0 | as above | as above | `5660f8a658f8bb50dbc005232f885eadffd2bc1c235c4f6fbb63469d1f9cde6d` |
| `fonts/IBMPlexSans-SemiBold.woff2` | IBM Plex Sans 600 | @ibm/plex-sans 1.1.0 | as above | as above | `f78048030eab62e860efa39a0df79e2e5581bf122eb95b9bc42c0b8a4988d205` |
| `fonts/IBMPlexMono-Regular.woff2` | IBM Plex Mono 400 | @ibm/plex-mono 2.5.0 | as above | https://registry.npmjs.org/@ibm/plex-mono/-/plex-mono-2.5.0.tgz, `package/fonts/complete/woff2/` | `ba204497f16b6d334cee9d1e963a831b73e3a56e1d6300a8489d18df7214b350` |
| `fonts/IBMPlexMono-Medium.woff2` | IBM Plex Mono 500 | @ibm/plex-mono 2.5.0 | as above | as above | `33faf307fa6031fb4062276d7320a6d632de890cbb347576fd80cfa01077bc25` |
| `fonts/IBMPlexSansCondensed-Medium.woff2` | IBM Plex Sans Condensed 500 | @ibm/plex-sans-condensed 2.0.0 | as above | https://registry.npmjs.org/@ibm/plex-sans-condensed/-/plex-sans-condensed-2.0.0.tgz, `package/fonts/complete/woff2/` | `eb93da02ace70c39e4c4e811b8b02dd5f5d4804d186202d6668bea60d22f57d0` |
| `fonts/IBMPlexSansCondensed-SemiBold.woff2` | IBM Plex Sans Condensed 600 | @ibm/plex-sans-condensed 2.0.0 | as above | as above | `385a082a1eac88343eab01fb6746be04b7175dacaf4550b17dee76ea0f78126d` |

The three Plex packages carry the same license text.

To update a file, take it unchanged from the named package, replace its license, update this table, and run the web module's tests and the browser checks.
