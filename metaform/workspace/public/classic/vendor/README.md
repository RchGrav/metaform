# Libraries the classic map page loads

These files are copied unchanged from the `vendor/` folder of the earlier Metaform web module. The page loads nothing from the network.

| File | Use | Release | License |
|---|---|---|---|
| `mermaid.min.js` | Draws the 2D map | Mermaid 12.0.0, with the changes below | MIT, `mermaid.LICENSE`. The packages it bundles are listed in `mermaid.THIRD-PARTY.LICENSE` with their license texts. |
| `elk-worker.min.js` | The Eclipse Layout Kernel in a worker. It lays out the map off the page's thread. | elkjs 0.9.3, the version Mermaid 12.0.0 bundles | EPL-2.0, `elkjs.LICENSE` |
| `fonts/` | The page's text | IBM Plex Sans, Sans Condensed and Mono | SIL Open Font License, `fonts/IBM-Plex.LICENSE` |

The source of elkjs is https://github.com/kieler/elkjs at tag 0.9.3. The layout algorithms are at https://github.com/eclipse/elk.

## The changes to Mermaid

The earlier module changed `mermaid.min.js` in these places, and `app/map2d/build.js` and `app/map2d/fit.js` rely on them. The earlier module's `vendor/README.md` describes each change in full.

- Mermaid passes `elk.rootLayoutOptions` of its configuration to the root of the ELK graph (`fitDraw2d`).
- Mermaid gives ELK the options that `globalThis.mermaidElk` returns, so the page can give ELK a worker (`mermaidElk`).
- Mermaid's drawing steps wait on `globalThis.mermaidStep`, so the page answers input while a large map is drawn.

When Mermaid is updated, make the same changes again and copy the `elk-worker.min.js` of the elkjs version that the new release bundles.
