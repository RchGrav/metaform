/* The page's state S, from the earlier page's core/reads.js. The earlier page's reads of its own server are not part of
 * this page: the map is read by adapter.js from the new server and kept here in the shapes the map code expects. */
import '/classic/app/core/controls.js';  // the part before runs first, so the parts run in the page's order

export const S = {
  projects: [], project: null, layers: [],
  elements: new Map(), joins: [], items: new Map(), selected: null, neighbors: new Set(), trail: [], history: [],
  at: -1, loading: 0, opening: 0,
  cleared: false,  // the person let go of the selection, VIEW-008, so a map read again selects nothing in its place
  // the node the Object tab shows, and a print of what it was drawn from, `panelPrint`
  panelFor: null, panelPrint: null,
};
/* The earlier page's memory network, VIEW-031, is not part of this page. `MEM.key` stays null, so the map code that
 * asks whether a memory network is open reads as it did and always takes the map's own branch. */
export const MEM = {key: null};
