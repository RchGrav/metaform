# Libraries the classic map page loads

These files are copied unchanged from the `vendor/` folder of the earlier Metaform web module. The page loads nothing from the network. The page's `index.html` holds an import map that names each library of the 3D map as its files import it.

| File | Use | Release | License |
|---|---|---|---|
| `mermaid.min.js` | Draws the 2D map | Mermaid 12.0.0, with the changes below | MIT, `mermaid.LICENSE`. The packages it bundles are listed in `mermaid.THIRD-PARTY.LICENSE` with their license texts. |
| `elk-worker.min.js` | The Eclipse Layout Kernel in a worker. It lays out the map off the page's thread. | elkjs 0.9.3, the version Mermaid 12.0.0 bundles | EPL-2.0, `elkjs.LICENSE` |
| `three.module.min.js` | three.js, which the 3D map, its glass, its bloom and the Space theme draw with | three 0.168.0 | MIT, `three.LICENSE` |
| `three-addons/` | The three.js add-ons that are loaded: the controls, the render chain, the rounded box and the room environment | three 0.168.0 | MIT, `three.LICENSE` |
| `drei-vanilla/MeshTransmissionMaterial.js` | The glass that the nodes are made of in the plain themes | @pmndrs/vanilla 1.25.0 | MIT, `drei-vanilla/LICENSE` |
| `3d-force-graph/` and the packages it imports | The 3D force graph, as ES modules | 3d-force-graph 1.73.4; the other versions are in the table below | `3d-force-graph.LICENSE`; each other package holds its own `LICENSE` |
| `graph-modules.json` | The record of each graph package: its version, its source, and the SHA-256 of each copied file | | |
| `fonts/` | The page's text | IBM Plex Sans, Sans Condensed and Mono | SIL Open Font License, `fonts/IBM-Plex.LICENSE` |

The source of elkjs is https://github.com/kieler/elkjs at tag 0.9.3. The layout algorithms are at https://github.com/eclipse/elk.

## The 3D map's packages

Only the files that the module imports reach are copied, 313 files of about 1.4 MB, with each package's license file. `graph-modules.json` records each file. `ngraph.graph` and `ngraph.forcelayout` publish no ES module. The two adapters in the page's folder, `ngraph.graph.js` and `ngraph.forcelayout.js`, import their UMD files and export their factories.

| Package | Version | License file |
|---|---|---|
| `3d-force-graph` | 1.73.4 | `3d-force-graph.LICENSE` |
| `@babel/runtime` | 7.25.6 | `@babel/runtime/LICENSE` |
| `@tweenjs/tween.js` | 25.0.0 | `@tweenjs/tween.js/LICENSE` |
| `accessor-fn` | 1.5.1 | `accessor-fn/LICENSE` |
| `d3-array` | 3.2.4 | `d3-array/LICENSE` |
| `d3-binarytree` | 1.0.2 | `d3-binarytree/LICENSE` |
| `d3-color` | 3.1.0 | `d3-color/LICENSE` |
| `d3-dispatch` | 3.0.1 | `d3-dispatch/LICENSE` |
| `d3-force-3d` | 3.0.5 | `d3-force-3d/LICENSE` |
| `d3-format` | 3.1.0 | `d3-format/LICENSE` |
| `d3-interpolate` | 3.0.1 | `d3-interpolate/LICENSE` |
| `d3-octree` | 1.0.2 | `d3-octree/LICENSE` |
| `d3-quadtree` | 3.0.1 | `d3-quadtree/LICENSE` |
| `d3-scale` | 4.0.2 | `d3-scale/LICENSE` |
| `d3-scale-chromatic` | 3.1.0 | `d3-scale-chromatic/LICENSE` |
| `d3-time` | 3.1.0 | `d3-time/LICENSE` |
| `d3-time-format` | 4.1.0 | `d3-time-format/LICENSE` |
| `d3-timer` | 3.0.1 | `d3-timer/LICENSE` |
| `data-joint` | 1.3.1 | `data-joint/LICENSE` |
| `index-array-by` | 1.4.2 | `index-array-by/LICENSE` |
| `internmap` | 2.0.3 | `internmap/LICENSE` |
| `kapsule` | 1.14.5 | `kapsule/LICENSE` |
| `lodash-es` | 4.17.21 | `lodash-es/LICENSE` |
| `ngraph.events` | 1.2.2 | `ngraph.events/LICENSE` |
| `ngraph.forcelayout` | 3.3.1 | `ngraph.forcelayout/LICENSE` |
| `ngraph.graph` | 20.0.1 | `ngraph.graph/LICENSE` |
| `ngraph.merge` | 1.0.0 | `ngraph.merge/LICENSE` |
| `ngraph.random` | 1.1.0 | `ngraph.random/LICENSE` |
| `polished` | 4.3.1 | `polished/LICENSE.md` |
| `three-forcegraph` | 1.41.14 | `three-forcegraph/LICENSE` |
| `three-render-objects` | 1.29.5 | `three-render-objects/LICENSE` |
| `tinycolor2` | 1.6.0 | `tinycolor2/LICENSE` |

The `ngraph.events`, `ngraph.merge` and `ngraph.random` folders hold a license only: `ngraph.graph` and `ngraph.forcelayout` bundle their code.

## The changes to Mermaid

The earlier module changed `mermaid.min.js` in these places, and `app/map2d/build.js` and `app/map2d/fit.js` rely on them. The earlier module's `vendor/README.md` describes each change in full.

- Mermaid passes `elk.rootLayoutOptions` of its configuration to the root of the ELK graph (`fitDraw2d`).
- Mermaid gives ELK the options that `globalThis.mermaidElk` returns, so the page can give ELK a worker (`mermaidElk`).
- Mermaid's drawing steps wait on `globalThis.mermaidStep`, so the page answers input while a large map is drawn.

When Mermaid is updated, make the same changes again and copy the `elk-worker.min.js` of the elkjs version that the new release bundles.
