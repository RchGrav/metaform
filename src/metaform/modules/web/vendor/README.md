# Vendored files

Every file the web GUI loads is served from this folder or `page/`, so it works offline and sends nothing to a third party, VIEW-003. Each library file is an unchanged release file with its license alongside it. The two ngraph module adapters are in `page/`.

| File | What | Version | License | Source | SHA-256 |
| --- | --- | --- | --- | --- | --- |
| `3d-force-graph/dist/3d-force-graph.mjs` and its module dependencies | the 3D force graph ES module, importing the shared `three` runtime; unchanged dependency files and licenses | 3d-force-graph 1.73.4 | See `graph-modules.json` and the dependency table below | https://registry.npmjs.org/3d-force-graph/-/3d-force-graph-1.73.4.tgz, `package/dist/3d-force-graph.mjs` | See `graph-modules.json` for every file’s SHA-256 |
| `three.module.min.js` | three.js, shared by the graph, glass, bloom and agent figures through the import map | three 0.168.0 | MIT, `three.LICENSE` | https://registry.npmjs.org/three/-/three-0.168.0.tgz, `package/build/three.module.min.js` | `ee08b04912b21d9bf71f13658a65da65c113827601377076663e710c0b1772d0` |
| `three-addons/geometries/RoundedBoxGeometry.js` | three.js's rounded box, which the agent figures are built with, VIEW-035; it imports three.js as `three` | three 0.168.0 | MIT, `three.LICENSE` | https://registry.npmjs.org/three/-/three-0.168.0.tgz, `package/examples/jsm/geometries/RoundedBoxGeometry.js` | `d20aeaf7077c459a8d952d215738d7b44fba028440bb862d84b622a34f0c80bb` |
| `drei-vanilla/MeshTransmissionMaterial.js` | drei's transmission material in its vanilla form, the glass the nodes are made of; it imports three.js as `three`, which the page's import map names as `three.module.min.js` above | @pmndrs/vanilla 1.25.0 | MIT, `drei-vanilla/LICENSE` | https://registry.npmjs.org/@pmndrs/vanilla/-/vanilla-1.25.0.tgz, `package/materials/MeshTransmissionMaterial.js` | `373f0b920a21e24847855ecd762fa666374e73ec53af60edf23dd62f60926f71` |
| `codemirror/codemirror.js`, `codemirror.css`, `xml.js`, `markdown.js`, `search.js`, `searchcursor.js`, `dialog.js`, `dialog.css` | the prompt editor: the editor, its XML and Markdown modes, and search and replace with its dialog | CodeMirror 5.65.16, the version the approved prototype used | MIT, `codemirror/LICENSE` | https://registry.npmjs.org/codemirror/-/codemirror-5.65.16.tgz, `package/lib/`, `package/mode/`, `package/addon/search/`, `package/addon/dialog/` | `0644e6418c4129c9584b9b772b8b8bdb0b4fbab1efd848a98baf1fe147381f22`, `eb494ea972d2661ef86f7f6ac656dd6786d721e49c9c1b46e1eb967e4b6f9bf3`, `dc7e44d410399326f802e2924573cbf6f942a79f647fd0b97f0b607973bc9a09`, `8fe7b11848f79cc9119b2a239f38a00944f6f2bb764a00bc837ecf8d34cf7690`, `4949580371fcd81c0ad70164b169dd8bcab2bd9869eddaa0d7e295508bec7a04`, `2c0b8cd8fe7ca5ca2253f4aacc914b390bff5b3cac3475df66c43a9ea8c8ccbe`, `fd8c925fcc25357617faff21220c026bb91a617b995268d96c5d39232fd42833`, `5df690d771f12118348562dd2a90060433ae2edeccd0908abcaa4480b1e3e468` |
| `mermaid.min.js` | the 2D layout | Mermaid 12.0.0, the build vetted on branch `main-wip-2026-09-24` | MIT, `mermaid.LICENSE`; the packages it bundles, among them the Eclipse Layout Kernel under EPL-2.0, in `mermaid.THIRD-PARTY.LICENSE`, see below | https://registry.npmjs.org/mermaid/-/mermaid-12.0.0.tgz, `package/dist/mermaid.min.js` | `28fca7ae6ebc7ed7bb63bde63136a74bfef14f296a57e403657eeb8b32836073` |
| `fonts/IBMPlexSans-Regular.woff2` | IBM Plex Sans 400 | @ibm/plex-sans 1.1.0 | SIL Open Font License 1.1, `fonts/IBM-Plex.LICENSE` | https://registry.npmjs.org/@ibm/plex-sans/-/plex-sans-1.1.0.tgz, `package/fonts/complete/woff2/` | `ba711a3085ff9f27440b6b9c4550cfc47c97bf36591d5da958b975bb3add8c1a` |
| `fonts/IBMPlexSans-Medium.woff2` | IBM Plex Sans 500 | @ibm/plex-sans 1.1.0 | as above | as above | `5660f8a658f8bb50dbc005232f885eadffd2bc1c235c4f6fbb63469d1f9cde6d` |
| `fonts/IBMPlexSans-SemiBold.woff2` | IBM Plex Sans 600 | @ibm/plex-sans 1.1.0 | as above | as above | `f78048030eab62e860efa39a0df79e2e5581bf122eb95b9bc42c0b8a4988d205` |
| `fonts/IBMPlexMono-Regular.woff2` | IBM Plex Mono 400 | @ibm/plex-mono 2.5.0 | as above | https://registry.npmjs.org/@ibm/plex-mono/-/plex-mono-2.5.0.tgz, `package/fonts/complete/woff2/` | `ba204497f16b6d334cee9d1e963a831b73e3a56e1d6300a8489d18df7214b350` |
| `fonts/IBMPlexMono-Medium.woff2` | IBM Plex Mono 500 | @ibm/plex-mono 2.5.0 | as above | as above | `33faf307fa6031fb4062276d7320a6d632de890cbb347576fd80cfa01077bc25` |
| `fonts/IBMPlexSansCondensed-Medium.woff2` | IBM Plex Sans Condensed 500 | @ibm/plex-sans-condensed 2.0.0 | as above | https://registry.npmjs.org/@ibm/plex-sans-condensed/-/plex-sans-condensed-2.0.0.tgz, `package/fonts/complete/woff2/` | `eb93da02ace70c39e4c4e811b8b02dd5f5d4804d186202d6668bea60d22f57d0` |
| `fonts/IBMPlexSansCondensed-SemiBold.woff2` | IBM Plex Sans Condensed 600 | @ibm/plex-sans-condensed 2.0.0 | as above | as above | `385a082a1eac88343eab01fb6746be04b7175dacaf4550b17dee76ea0f78126d` |

The three Plex packages carry the same license text.

To update a file, take it unchanged from the named package, replace its license, update this table, and run the web module's tests and the browser checks.

## What Mermaid bundles

`mermaid.min.js` is one file, but it holds the code of about eighty other package releases as well as Mermaid's own. `mermaid.THIRD-PARTY.LICENSE` lists each with the version bundled, its license and its npm release, and carries every license text. The list comes from the release's own source map, `package/dist/mermaid.min.js.map` in the Mermaid tarball, and from the source maps of the `@mermaid-js/parser` 2.0.0 chunks it includes, which bundle Langium and its dependencies. Most are MIT, ISC or BSD-3-Clause. The others:

- `elkjs` 0.9.3, the Eclipse Layout Kernel compiled to JavaScript, under the Eclipse Public License 2.0. The EPL asks whoever passes on a compiled copy to say where its source is: https://github.com/kieler/elkjs at tag 0.9.3, the elkjs 0.9.3 npm tarball, and https://github.com/eclipse/elk for the layout algorithms. The notice file says so. Its `elk.bundled.js` also holds Google's `web-worker` browser entry under Apache-2.0. Mermaid 12 registers this ELK as its `elk` layout and makes it the default, and the 2D map is laid out with it, P043. `@mermaid-js/layout-elk` 1.0.0, released with Mermaid 12.0.0, is not vendored: its README says it is only for builds without ELK, such as `mermaid.tiny.js`, and that registering it with a full build loads a second copy of the same layout code.
- `chevrotain` 11.1.2 and its `@chevrotain/*` parts, Apache-2.0. None ships a NOTICE file.
- `dompurify` 3.4.12, MPL-2.0 or Apache-2.0 at the user's choice; both texts are in the notice file.

Mermaid keeps a few license comments of its own at the end of `mermaid.min.js`: DOMPurify, Lodash and the MIT parts inside Cytoscape. When Mermaid is updated, build the list again from the new release's source maps, because each release bundles different versions.

## Graph modules

The graph uses its published ES-module build. `index.html` maps all bare imports to local files, including both Three.js addon prefixes to `three-addons/`. Dependencies are pinned to the releases available when 3d-force-graph 1.73.4 was published (2024-09-25), with Three.js kept at 0.168.0. No npm installation or build runs when the page opens.

`graph-modules.json` records each package’s version and tarball source, and every copied file’s original package path and SHA-256. Only files reachable from the module imports are copied. Relative imports retain their release paths. The Three.js addons retain paths below `examples/jsm/` under `three-addons/`.

The pinned `ngraph.graph` and `ngraph.forcelayout` packages publish CommonJS and UMD rather than ES modules. Their unchanged UMD releases contain no Three.js. `page/ngraph.graph.js` and `page/ngraph.forcelayout.js` import them and export their factories for the graph’s module imports. The licenses of their bundled `ngraph.events`, `ngraph.merge` and `ngraph.random` dependencies are included.

| Package | Version | License file | Source |
| --- | --- | --- | --- |
| `3d-force-graph` | 1.73.4 | `3d-force-graph.LICENSE` | https://registry.npmjs.org/3d-force-graph/-/3d-force-graph-1.73.4.tgz |
| `@babel/runtime` | 7.25.6 | `@babel/runtime/LICENSE` | https://registry.npmjs.org/@babel/runtime/-/runtime-7.25.6.tgz |
| `@tweenjs/tween.js` | 25.0.0 | `@tweenjs/tween.js/LICENSE` | https://registry.npmjs.org/@tweenjs/tween.js/-/tween.js-25.0.0.tgz |
| `accessor-fn` | 1.5.1 | `accessor-fn/LICENSE` | https://registry.npmjs.org/accessor-fn/-/accessor-fn-1.5.1.tgz |
| `d3-array` | 3.2.4 | `d3-array/LICENSE` | https://registry.npmjs.org/d3-array/-/d3-array-3.2.4.tgz |
| `d3-binarytree` | 1.0.2 | `d3-binarytree/LICENSE` | https://registry.npmjs.org/d3-binarytree/-/d3-binarytree-1.0.2.tgz |
| `d3-color` | 3.1.0 | `d3-color/LICENSE` | https://registry.npmjs.org/d3-color/-/d3-color-3.1.0.tgz |
| `d3-dispatch` | 3.0.1 | `d3-dispatch/LICENSE` | https://registry.npmjs.org/d3-dispatch/-/d3-dispatch-3.0.1.tgz |
| `d3-force-3d` | 3.0.5 | `d3-force-3d/LICENSE` | https://registry.npmjs.org/d3-force-3d/-/d3-force-3d-3.0.5.tgz |
| `d3-format` | 3.1.0 | `d3-format/LICENSE` | https://registry.npmjs.org/d3-format/-/d3-format-3.1.0.tgz |
| `d3-interpolate` | 3.0.1 | `d3-interpolate/LICENSE` | https://registry.npmjs.org/d3-interpolate/-/d3-interpolate-3.0.1.tgz |
| `d3-octree` | 1.0.2 | `d3-octree/LICENSE` | https://registry.npmjs.org/d3-octree/-/d3-octree-1.0.2.tgz |
| `d3-quadtree` | 3.0.1 | `d3-quadtree/LICENSE` | https://registry.npmjs.org/d3-quadtree/-/d3-quadtree-3.0.1.tgz |
| `d3-scale` | 4.0.2 | `d3-scale/LICENSE` | https://registry.npmjs.org/d3-scale/-/d3-scale-4.0.2.tgz |
| `d3-scale-chromatic` | 3.1.0 | `d3-scale-chromatic/LICENSE` | https://registry.npmjs.org/d3-scale-chromatic/-/d3-scale-chromatic-3.1.0.tgz |
| `d3-time` | 3.1.0 | `d3-time/LICENSE` | https://registry.npmjs.org/d3-time/-/d3-time-3.1.0.tgz |
| `d3-time-format` | 4.1.0 | `d3-time-format/LICENSE` | https://registry.npmjs.org/d3-time-format/-/d3-time-format-4.1.0.tgz |
| `d3-timer` | 3.0.1 | `d3-timer/LICENSE` | https://registry.npmjs.org/d3-timer/-/d3-timer-3.0.1.tgz |
| `data-joint` | 1.3.1 | `data-joint/LICENSE` | https://registry.npmjs.org/data-joint/-/data-joint-1.3.1.tgz |
| `index-array-by` | 1.4.2 | `index-array-by/LICENSE` | https://registry.npmjs.org/index-array-by/-/index-array-by-1.4.2.tgz |
| `internmap` | 2.0.3 | `internmap/LICENSE` | https://registry.npmjs.org/internmap/-/internmap-2.0.3.tgz |
| `kapsule` | 1.14.5 | `kapsule/LICENSE` | https://registry.npmjs.org/kapsule/-/kapsule-1.14.5.tgz |
| `lodash-es` | 4.17.21 | `lodash-es/LICENSE` | https://registry.npmjs.org/lodash-es/-/lodash-es-4.17.21.tgz |
| `ngraph.events` | 1.2.2 | `ngraph.events/LICENSE` | https://registry.npmjs.org/ngraph.events/-/ngraph.events-1.2.2.tgz |
| `ngraph.forcelayout` | 3.3.1 | `ngraph.forcelayout/LICENSE` | https://registry.npmjs.org/ngraph.forcelayout/-/ngraph.forcelayout-3.3.1.tgz |
| `ngraph.graph` | 20.0.1 | `ngraph.graph/LICENSE` | https://registry.npmjs.org/ngraph.graph/-/ngraph.graph-20.0.1.tgz |
| `ngraph.merge` | 1.0.0 | `ngraph.merge/LICENSE` | https://registry.npmjs.org/ngraph.merge/-/ngraph.merge-1.0.0.tgz |
| `ngraph.random` | 1.1.0 | `ngraph.random/LICENSE` | https://registry.npmjs.org/ngraph.random/-/ngraph.random-1.1.0.tgz |
| `polished` | 4.3.1 | `polished/LICENSE.md` | https://registry.npmjs.org/polished/-/polished-4.3.1.tgz |
| `three` | 0.168.0 | `three.LICENSE` | https://registry.npmjs.org/three/-/three-0.168.0.tgz |
| `three-forcegraph` | 1.41.14 | `three-forcegraph/LICENSE` | https://registry.npmjs.org/three-forcegraph/-/three-forcegraph-1.41.14.tgz |
| `three-render-objects` | 1.29.5 | `three-render-objects/LICENSE` | https://registry.npmjs.org/three-render-objects/-/three-render-objects-1.29.5.tgz |
| `tinycolor2` | 1.6.0 | `tinycolor2/LICENSE` | https://registry.npmjs.org/tinycolor2/-/tinycolor2-1.6.0.tgz |
