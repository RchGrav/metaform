/* The page's state S, the memory store's state, and reads of the server's API that wait out a restart. */
import '/page/app/core/controls.js';  // the part before runs first, so the parts run in the page's order
import {$} from '/page/app/core/dom.js';

/* ---------- reads ---------- */
/* The page in an AI tool's frame, the MCP Apps map view, MCP-037: it shows the maps and the panel only, so the agents,
 * their merges and autostart, which it does not show, are not read. */
export const FRAMED = document.documentElement.classList.contains('frame');
// In a frame, the view's bar the host's code adds to the page, #viewbar, stands in the frame's header slot, #viewslot.
function adoptViewbar() {
  const bar = document.getElementById('viewbar');
  if (bar && bar.parentElement !== $('#viewslot')) $('#viewslot').append(bar);
}
if (FRAMED) {
  new MutationObserver(adoptViewbar).observe(document.body, {childList: true});
  adoptViewbar();
}
export const S = {
  projects: [], project: null, bases: [], base: null, layers: [], view: null,
  elements: new Map(), joins: [], items: new Map(), selected: null, neighbors: new Set(), trail: [], history: [],
  at: -1, loading: 0, opening: 0, shown: false,
  cleared: false,  // the person let go of the selection, VIEW-008, so a map read again selects nothing in its place
  whole: null,  // the last map read whole, {elements, joins}, put back when a read of it fails
  // LAYER-013
  memory: {entities: new Map(), relations: [], joins: [], at: new Map(), age: 0, orphaned: 0},
};
/* The memory network open in both views, VIEW-031: the node it belongs to, what is drawn of it, and what the map was
 * when it gave way, to go back to: the levels entered in 2D and where each node of the 3D map stood. */
export const MEM = {key: null, network: null, drawn: false, levels: [], positions: null, generation: 0};

/* The server restarts to take new code, and for the second it takes, the browser can reach nothing: a read waits
 * through that and asks again, and a write, which may not be repeated safely, says so in words. */
const DOWN = 'The server was restarting and did not get that. Try again in a moment.';
const pause = ms => new Promise(done => setTimeout(done, ms));
export async function reach(url, options, again = 10) {
  for (let tries = 0; ; tries++) {
    try { return await fetch(url, options); }
    catch (error) {
      if (tries >= again) throw new Error(DOWN);
      await pause(1000);
    }
  }
}
export async function read(name, params = {}) {
  const query = new URLSearchParams({project: S.project, ...(S.base ? {base: S.base} : {}), ...params});
  const response = await reach(`/api/${name}?${query}`, {headers: {Accept: 'application/json'}});
  const body = await response.json().catch(() => ({error: 'The server did not answer with JSON.'}));
  if (!response.ok) throw Object.assign(new Error(body.error || `${name} failed`), {status: response.status, body});
  return body;
}
export const viewLayers = () => S.view === null ? {} : {layers: [...S.view].join(',')};
