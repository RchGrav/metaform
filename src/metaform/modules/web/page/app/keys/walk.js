/* The keys that walk the join tree: down, across and beside on the 2D map, up a level, and which keys the maps take. */
import '/page/app/map2d/wire.js';  // the part before runs first, so the parts run in the page's order
import {overlayHolds} from '/page/app/core/overlays.js';
import {S, MEM} from '/page/app/core/reads.js';
import {joinOf} from '/page/app/graph/data.js';
import {DIRECTION_KEYS, chooseDirection} from '/page/app/camera/flight.js';
import {peek} from '/page/app/views/settings.js';
import {setMode3d} from '/page/app/views/bar.js';
import {M} from '/page/app/map2d/build.js';
import {IN, enter, goTo} from '/page/app/map2d/inside.js';
import {leaveMemories} from '/page/app/memory/graph.js';
import {resetZoom} from '/page/app/map2d/camera.js';

/* The keys walk the join tree, Down goes deeper, to the providers of the node's joins and then to
 * the nodes inside it; Up goes back to the parent; Left and Right move between the nodes connected to the parent.
 * Enter goes inside a node; Escape or Shift+Enter backs out. F fits. */
export function across(keys) {  // in their order across the 2D map
  const at = key => M.nodes.get(key) || {x: Infinity, y: Infinity};
  const order = (a, b) => M.vertical ? at(a).x - at(b).x || at(a).y - at(b).y : at(a).y - at(b).y || at(a).x - at(b).x;
  return [...keys].sort(order);
}
/* Down goes down an edge to the node drawn nearest under the selected one, across the map's other axis, so with seven
 * below it lands near the middle and not at the far end of the row; the nodes inside a node are gone to when no edge
 * leads down. A row not drawn yet gives its middle node. */
export function below(key) {
  const row = childrenOf(key);
  const here = M.nodes.get(key), axis = M.vertical ? 'x' : 'y';
  const drawn = row.filter(child => M.nodes.has(child));
  if (!here || !drawn.length) return row[Math.floor((row.length - 1) / 2)];
  return drawn.reduce((best, child) =>
    Math.abs(M.nodes.get(child)[axis] - here[axis]) < Math.abs(M.nodes.get(best)[axis] - here[axis]) ? child : best);
}
/* The node drawn nearest beside a node on its row of the 2D map, that way. */
export function besideDrawn(key, by) {
  const here = M.nodes.get(key);
  if (!here) return null;
  const depth = M.vertical ? 'y' : 'x', across = M.vertical ? 'x' : 'y';
  const onward = [...M.nodes.entries()].filter(([id, node]) => id !== key
    && Math.abs(node[depth] - here[depth]) < 2 && (node[across] - here[across]) * by > 0);
  if (!onward.length) return null;
  const gap = one => Math.abs(one[1][across] - here[across]);
  return onward.reduce((best, one) => gap(one) < gap(best) ? one : best)[0];
}
/* Past either end of a parent's row, Left and Right go on to the nodes of the next parent over on the parent's level,
 * the first of them going right and the last going left, and past the last parent of the level round to the first, so
 * every node of a level is reached by Left and Right alone. A level is the children of every node on the level above,
 * in their order across the map, starting from the roots. Returns the node and the parent it is reached under. */
export function besideOnLevel(key, parent, by) {
  if (!parent) return null;  // the roots are one row already
  let level = roots(), seen = new Set(level);
  while (level.length && !level.includes(parent)) {
    level = level.flatMap(node => childrenOf(node)).filter(node => !seen.has(node) && seen.add(node));
  }
  if (!level.length) return null;
  const row = level.flatMap(node => childrenOf(node).map(next => ({next, parent: node})))
    .filter((one, at, all) => all.findIndex(other => other.next === one.next) === at);
  const at = row.findIndex(one => one.next === key && one.parent === parent);
  const from = at >= 0 ? at : row.findIndex(one => one.next === key);
  if (from < 0 || row.length < 2) return null;
  return row[(from + by + row.length) % row.length];
}
export function childrenOf(key) {
  if (key.startsWith('p:')) return across((joinOf(key)?.providers || []).filter(id => S.elements.has(id)));
  return across(new Set(S.joins.filter(join => join.receiver === key).flatMap(join => join.providers)
    .filter(id => S.elements.has(id))));
}
export function parentOf(key) {
  if (key.startsWith('p:')) return joinOf(key)?.receiver || null;
  const receivers = S.joins.filter(join => join.providers.includes(key) && S.elements.has(join.receiver))
    .map(join => join.receiver);
  return across(new Set(receivers))[0] || null;
}
export function roots() {  // the nodes nothing receives from, CQUs first; then any part of the map they do not reach
  const top = [...S.elements.keys()].filter(key => !parentOf(key));
  const cqu = key => S.elements.get(key).element.role === 'CQU';
  const ordered = [...across(top.filter(cqu)), ...across(top.filter(key => !cqu(key)))];
  const reached = new Set(ordered);
  reachAll([...ordered], reached);
  for (const key of across([...S.elements.keys()].filter(key => !reached.has(key)))) {
    if (reached.has(key)) continue;
    ordered.push(key); reached.add(key);
    reachAll([key], reached);
  }
  return ordered;
}
/* Every node reached down the tree from the ones queued, marked reached. */
function reachAll(queue, reached) {
  while (queue.length) {
    for (const next of childrenOf(queue.shift())) if (!reached.has(next)) { reached.add(next); queue.push(next); }
  }
}
export function goInside(key) { if (!MEM.key) enter(key); }  // a memory network has no inside of its own
/* Out one level, by Shift+Enter, a Shift-click, or Escape with nothing selected, VIEW-008: from a memory network or a
 * node's own graph to the level before; on the whole map there is no level to leave. */
export function levelUp() {
  if (MEM.key) return leaveMemories();
  if (IN.length) return goTo(IN.length - 1);
}
/* Which keys the maps take. A key typed into a text is a letter of it and never a shortcut. While a menu, a popover or
 * a modal window is open, or the focus is in any window, the maps' keys rest: the key belongs to what is open, VIEW-030
 * and VIEW-041. Enter and Space on a button or a link press it, and the arrows on a tab, a menu item or a choice move
 * between those; every other control leaves the keys to the maps. Escape that reaches here has closed nothing. */
const ARROWS_OWN = ['select', '[role=tab]', '[role=tablist]', '[role=menuitem]', '[role=option]', '[role=listbox]',
  '[role=radio]', '[role=radiogroup]', '[role=slider]', 'input[type=range]'].join(',');
const PRESSABLE = ['button', 'a[href]', 'summary', '[role=button]', '[role=tab]', '[role=menuitem]', '[role=option]',
  '[role=switch]', '[role=checkbox]', '[role=radio]', 'input[type=checkbox]', 'input[type=radio]'].join(',');
export function mapKeys(event) {
  const target = event.target instanceof Element ? event.target : document.body;
  if (event.defaultPrevented || event.isComposing || event.ctrlKey || event.metaKey || event.altKey) return false;
  const typing = target.closest('select, input, textarea, .CodeMirror, [contenteditable="true"]');
  if (typing && !target.matches('input[type=checkbox],input[type=radio]')) return false;
  if (overlayHolds(target)) return false;
  const onMap = target.closest('#map2d, #stage') && !target.closest('.bar2d, .bar3d');
  if ((event.key === 'Enter' || event.key === ' ') && !onMap && target.closest(PRESSABLE)) return false;
  if (event.key.startsWith('Arrow') && target.closest(ARROWS_OWN)) return false;
  return true;
}
/* The digits, VIEW-041 and VIEW-005: 0 and Home put the 2D map back to full fit and the large 3D map to Zoom at its
 * farthest; 4, 5 and 6 the large 3D map's zoom, far, medium and close on the selection; 7, 8 and 9 the 2D map's
 * direction. 1 and 2 are free; 3, auto zoom, is the key table's own. The small area takes no 3D zoom. The bar peeks
 * with the new choice checked. */
export function largeKey(key) {
  // the 2D map's keys, wherever it is: 0 its full fit, 7 to 9 its direction
  if (key === '0' || key === 'Home') return resetZoom();
  if (DIRECTION_KEYS[key]) { chooseDirection(DIRECTION_KEYS[key]); peek('key'); return; }
  // the large 3D map's zoom, its name a quarter, a half or three quarters wide
  const level = {4: 1, 5: 2, 6: 3}[key];
  if (level) { setMode3d('zoom', level); peek('key'); }
}
