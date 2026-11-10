/* Selection, both views together: select and selectNow, the work records shown, the question form at a node, and the
 * review-or-merge flow. */
import '/classic/app/keys/keys.js';  // the part before runs first, so the parts run in the page's order
import {$, h} from '/classic/app/core/dom.js';
import {shown, overlayHolds} from '/classic/app/core/overlays.js';
import {S, MEM} from '/classic/app/core/reads.js';
import {largeView} from '/classic/app/header/menus.js';
import {joinOf, nodeIn} from '/classic/app/graph/data.js';
import {G} from '/classic/app/map3d/graph3d.js';
import {follow3d} from '/classic/app/views/lens.js';
import {revealDepth} from '/classic/app/keys/walk.js';
import {IN, samePath, renderThing} from '/classic/app/map2d/inside.js';
import {focus2D} from '/classic/app/map2d/flow2d.js';
import {renderJoin, renderObject} from '/classic/app/panel/object.js';
import {tabNow, showTab} from '/classic/app/panel/tabs.js';
import {renderBrief} from '/classic/app/panel/brief.js';
import {renderProv} from '/classic/app/panel/provenance.js';

/* ---------- selection: both views move together; the long text goes in the panel ----------
 * A selection made as the map is loaded or read again, again, leaves open the tab of the panel the person has open,
 * such as the prompt being edited. */
export function select(id, fly, keepTrail = false, stepping = false, again = false) {
  if (!id) return;
  revealDepth(id);  // a part held deeper than the depth is broken out to be seen, VIEW-051
  const drawn = selectNow(id, fly, keepTrail, stepping, again), moved = S.panelFor !== id;
  // a new object is read from its top
  if (moved && S.selected === id) { S.panelFor = id; $('#p-object').scrollTop = 0; }
  if (fly && !again && S.selected === id && !keepsFocus(document.activeElement)) {
    largeView().focus({preventScroll: true});
  }
  return drawn;
}
/* A person who chose a node from elsewhere on the page goes on with the keys on the map; a text being written, an open
 * window and the maps themselves keep the focus. */
function keepsFocus(active) {
  if (!active || active === document.body || !shown(active)) return false;
  return Boolean(active.closest('input, textarea, select, [contenteditable="true"], .CodeMirror, #map2d, #stage')
    || overlayHolds(active));
}
function selectNow(id, fly, keepTrail, stepping, again) {
  const join = id.startsWith('p:') ? joinOf(id) : null;
  const known = join || S.elements.has(id);
  const thing = IN.at(-1)?.things?.get(id) || S.items.get(id);
  if (!known && !thing) return;
  if (!keepTrail) S.trail = [];
  if (!stepping && !MEM.key) remember(id);
  // auto zoom frames what the person selects anew, not the map loaded or read again, nor the node selected again as
  // a level is entered or left, VIEW-041
  const frame = !again && S.selected !== id;
  S.selected = id;
  S.cleared = false;
  if (!known) {
    S.neighbors = new Set();
    focus2D(id, frame);
    if (!again) showTab('object');
    renderThing(thing);
    return;
  }
  S.neighbors = neighborsOf(id, join);
  if (G) {
    G.nodeColor(G.nodeColor());
    const node = nodeIn(G.graphData(), id);
    if (fly && node) follow3d(id);
  }
  focus2D(id, frame);
  // The brief stays on view while the person walks the map from it, and on this page the provenance too, which is
  // the selected element's own; a selection made as the map is read again draws the tab on view again.
  const tab = tabNow();
  if (!again) showTab(tab);
  else if (tab === 'brief') renderBrief();
  else if (tab === 'prov') renderProv();
  // A map read again leaves the Object tab as it is while nothing it was drawn from changed, so agents writing
  // elsewhere neither make it flicker nor take the person's place in it (2026-10-18).
  const print = MEM.key ? null : panelPrint(id);
  if (again && print !== null && print === S.panelPrint && S.panelFor === id) return undefined;
  S.panelPrint = print;
  // The panel's reads are returned, so a load waits for them before it says it is loaded.
  return join ? renderJoin(join) : renderObject(id);
}
/* What the Object tab of node `id` is drawn from on the page: its element or join, the joins it receives or holds,
 * the items and properties on any of them, and their open work, as one string to compare. */
function panelPrint(id) {
  const joins = S.joins.filter(one => 'p:' + one.id === id || one.receiver === id
    || one.elements.some(held => held.element_id === id));
  const on = new Set([id, ...joins.map(one => 'p:' + one.id)]);
  const items = [];
  for (const entry of S.items.values()) {
    const item = entry.item, target = item.target;
    if (on.has(item.element_id) || (target && on.has(target.kind === 'join' ? 'p:' + target.id : target.id))) {
      items.push([entry.key, entry.value, item.refs, item.extra]);
    }
  }
  return JSON.stringify([S.elements.get(id)?.element ?? null, joins, items]);
}
/* A selection becomes a step of the history Back and Forward walk, unless it is the step it is on: the steps forward
 * are dropped, as a browser drops them. */
function remember(id) {
  const path = IN.map(({key, label}) => ({key, label})), last = S.history[S.at];
  if (last && last.id === id && samePath(last.path, path)) return;
  S.history = [...S.history.slice(0, S.at + 1), {id, path}];
  S.at = S.history.length - 1;
}
/* What is beside a selection: in a memory network, the memories its relations name; for a join, its receiver and its
 * providers; for an element, what it receives from and what receives from it. */
function neighborsOf(id, join) {
  if (join) return new Set([join.receiver, ...join.providers]);
  return new Set([id, ...S.joins.filter(item => item.receiver === id).flatMap(item => item.providers),
    ...S.joins.filter(item => item.providers.includes(id)).map(item => item.receiver)]);
}

export function refsOf(refs) {
  if (!refs || !refs.length) return null;
  return h('div', {class: 'refs'}, refs.map(ref => h('span', {}, h('span', {class: 'k'}, ref.key), ref.value)));
}
