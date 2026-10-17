/* The keys that walk the join tree: down, across and beside on the 2D map, up a level, and which keys the maps take. */
import '/page/app/map2d/wire.js';  // the part before runs first, so the parts run in the page's order
import {overlayHolds} from '/page/app/core/overlays.js';
import {S, MEM} from '/page/app/core/reads.js';
import {joinOf} from '/page/app/graph/data.js';
import {NAME, small3d} from '/page/app/camera/fly3d.js';
import {setMode3d} from '/page/app/views/bar.js';
import {M, build2D} from '/page/app/map2d/build.js';
import {IN, enter, goTo} from '/page/app/map2d/inside.js';
import {leaveMemories} from '/page/app/memory/graph.js';
import {note2d} from '/page/app/map2d/hover.js';
import {fullFit2d} from '/page/app/map2d/camera.js';
import {GROW, draw3D} from '/page/app/map3d/draw3d.js';
import {G} from '/page/app/map3d/graph3d.js';
import {V3, fit3d} from '/page/app/camera/flight.js';
import {renderLegend} from '/page/app/views/lens.js';
import {saveView} from '/page/app/views/settings.js';
import {underHiddenRoot} from '/page/app/header/layers.js';

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
  // what each element receives from, and every element some element receives from, found in one pass over the joins:
  // asked of each element in turn, each asking walked every join (critic F1, 2026-10-17)
  const below = new Map(), provided = new Set();
  for (const join of S.joins) {
    if (!S.elements.has(join.receiver)) continue;
    let row = below.get(join.receiver);
    if (!row) below.set(join.receiver, row = []);
    for (const id of join.providers) if (S.elements.has(id)) { row.push(id); provided.add(id); }
  }
  const top = [...S.elements.keys()].filter(key => !provided.has(key));
  const cqu = key => S.elements.get(key).element.role === 'CQU';
  const ordered = [...across(top.filter(cqu)), ...across(top.filter(key => !cqu(key)))];
  const reached = new Set(ordered);
  reachAll([...ordered], reached, below);
  for (const key of across([...S.elements.keys()].filter(key => !reached.has(key)))) {
    if (reached.has(key)) continue;
    ordered.push(key); reached.add(key);
    reachAll([key], reached, below);
  }
  return ordered;
}
/* Every node reached down the tree from the ones queued, marked reached. */
function reachAll(queue, reached, below) {
  for (let at = 0; at < queue.length; at++) {
    for (const next of below.get(queue[at]) || []) if (!reached.has(next)) { reached.add(next); queue.push(next); }
  }
}
export function goInside(key) { if (!MEM.key) enter(key); }  // a memory network has no inside of its own
/* Out one level, by Shift+Enter, a Shift-click, or Escape with nothing selected, VIEW-008: from a memory network or a
 * node's own graph to the level before; on the whole map there is no level to leave. */
export function levelUp() {
  if (MEM.key) return leaveMemories();
  if (IN.length) return goTo(IN.length - 1);
}
/* Which keys the maps take. A key typed into a text is a letter of it and never a shortcut. A key held with Ctrl,
 * Meta or Alt is the system's or a tool's, `toolKeys`, except Alt with Left or Right alone, the 2D map's back and
 * forward, `HISTORY_KEYS`: the maps take those, so the browser's own history step on them is held back only when a map
 * takes the key. While a menu, a popover or a modal window is open, or the focus is in any window, the maps' keys
 * rest: the key belongs to what is open, VIEW-030 and VIEW-041. Enter and Space on a button or a link press it, and
 * the arrows on a tab, a menu item or a choice move between those; every other control leaves the keys to the maps.
 * Escape that reaches here has closed nothing. */
const ARROWS_OWN = ['select', '[role=tab]', '[role=tablist]', '[role=menuitem]', '[role=option]', '[role=listbox]',
  '[role=radio]', '[role=radiogroup]', '[role=slider]', 'input[type=range]'].join(',');
const PRESSABLE = ['button', 'a[href]', 'summary', '[role=button]', '[role=tab]', '[role=menuitem]', '[role=option]',
  '[role=switch]', '[role=checkbox]', '[role=radio]', 'input[type=checkbox]', 'input[type=radio]'].join(',');
const HISTORY_KEYS = ['ArrowLeft', 'ArrowRight'];
const historyKey = event => event.altKey && !event.shiftKey && HISTORY_KEYS.includes(event.key);
export function mapKeys(event) {
  const target = event.target instanceof Element ? event.target : document.body;
  if (event.defaultPrevented || event.isComposing || event.ctrlKey || event.metaKey) return false;
  if (event.altKey && !historyKey(event)) return false;
  const typing = target.closest('select, input, textarea, .CodeMirror, [contenteditable="true"]');
  if (typing && !target.matches('input[type=checkbox],input[type=radio]')) return false;
  if (overlayHolds(target)) return false;
  const onMap = target.closest('#map2d, #stage') && !target.closest('.crumbs');
  if ((event.key === 'Enter' || event.key === ' ') && !onMap && target.closest(PRESSABLE)) return false;
  if (event.key.startsWith('Arrow') && target.closest(ARROWS_OWN)) return false;
  return true;
}
/* 1, VIEW-005: the large 3D map's camera, round from Work, the shot that shows the work going on, to the zoom on the
 * selection with its name a quarter, a half or three quarters of the view's width, and back to Work. The small area
 * takes no 3D zoom: it always meets a node at four fifths. */
export function zoomKey() {
  if (small3d()) return note2d("3D zoom is the large 3D map's: S swaps the maps");
  if (V3.mode === 'zoom' && NAME.level === 3) {
    setMode3d('work');
    return note2d('3D camera: the work in view');
  }
  const level = V3.mode === 'zoom' ? NAME.level + 1 : 1;
  setMode3d('zoom', level);
  note2d(`3D zoom: ${['1/4', '1/2', '3/4'][level - 1]}`);
}

/* 4, web_map_depth, VIEW-051: how many levels of the map show, counted along the joins from the tops, `levels`, what
 * the viewer sees with nothing above it at level 1, what serves them at 2, and so on. A part's level is its shortest
 * way down from a top, so a part serving two receivers shows when either does. A part deeper than the depth stays
 * inside the receiver it is reached through, which counts every part held beneath it. A click on a node holding parts
 * breaks out its next level in place, `DEPTH.open`, and a click again folds it with what was opened under it; a change
 * of depth clears them. Both maps draw the same parts, `depthView`; the inside view, VIEW-016, is not depth's.
 * The depths are the map's own, Rich, 2026-10-16: the least shows joins, never a lone element or elements joined to
 * nothing, `least`, and the most is one level short of the map's deepest, past which the depth is all of it. */
export const DEPTH = {level: 'auto', open: new Set()};
/* auto, the depth until the person chooses one with 4: a map of up to AUTO_WHOLE parts shows whole, a larger one
 * collapsed to one level past the least, so a large map opens readable and every collapsed node says how many parts
 * it holds. Rich, 2026-10-17: collapsed by default, opened around the work. */
const AUTO_WHOLE = 200;
/* The branches opened for what is going on, beside the person's own clicks in `DEPTH.open`, VIEW-051: `work`, the
 * parts of the open tickets taken and of the agents at work, given by the figures from the board and the sessions;
 * `selected`, the node the person selected, or jumped to by search, a link or the board. Each opens the receivers on
 * its way down from a top, so it is drawn with its siblings, and a work part opens its own next level too. Nothing is
 * stored: the branches close when the ticket is done, the session stops or the selection moves or goes, since the
 * set is said again on each of those events, and the maps are drawn again only when what is opened changes, `sig`. */
export const FOCUS = {work: [], selected: null, sig: ''};
/* The levels of the parts the viewer sees: `level` and `via`, the receiver each part is first reached through;
 * `below`, what each receiver drawn receives from; `least`, the first depth that draws a join, Infinity for a map with
 * none; `deepest`, the deepest level. An element under an edge of the project the viewer hid, upstream or downstream,
 * is never drawn, so it is no level, and what it alone receives from is a top: counted on the whole map, with
 * downstream hidden the CQUs were level 1 and depth 1 drew nothing (2026-10-16). */
function levels() {
  const seen = key => S.elements.has(key) && !underHiddenRoot(S.elements.get(key).element.address);
  const below = new Map(), provided = new Set();
  for (const join of S.joins) {
    if (!seen(join.receiver)) continue;
    const row = below.get(join.receiver) || below.set(join.receiver, new Set()).get(join.receiver);
    for (const id of join.providers) if (seen(id) && id !== join.receiver) { row.add(id); provided.add(id); }
  }
  const level = new Map(), via = new Map(), queue = [];
  const down = starts => {  // the starts at level 1 together, then breadth first, so a level is the shortest way down
    for (const top of starts) if (!level.has(top)) { level.set(top, 1); queue.push(top); }
    while (queue.length) {
      const key = queue.shift();
      for (const next of below.get(key) || []) {
        if (!level.has(next)) { level.set(next, level.get(key) + 1); via.set(next, key); queue.push(next); }
      }
    }
  };
  // the tops, in the order `roots` gives them and then what only a hidden element received; then, one at a time as
  // `roots` takes them, any loop no top reaches
  const order = [...roots(), ...S.elements.keys()];
  down(order.filter(key => seen(key) && !provided.has(key)));
  for (const key of order) if (seen(key) && !level.has(key)) down([key]);
  let least = Infinity, deepest = 0;
  for (const at of level.values()) deepest = Math.max(deepest, at);
  for (const [receiver, row] of below) {  // a join is drawn once its receiver and a provider are
    for (const id of row) least = Math.min(least, Math.max(level.get(receiver), level.get(id)));
  }
  return {level, via, below, least, deepest};
}
/* The depth drawn: the one chosen held to the map's own, `least` at the fewest, and all at the map's deepest or past
 * it, where every level shows; 'all' too for a map with no join. */
function depthOf(chosen, {least, deepest, level}) {
  if (chosen === 'auto') chosen = level.size <= AUTO_WHOLE ? 'all' : String(least + 1);
  if (chosen === 'all' || !Number.isFinite(least) || least >= deepest) return 'all';
  const most = Math.max(least, Number(chosen) || least);
  return most >= deepest ? 'all' : String(most);
}
/* What the depth shows now: `shown`, the elements drawn, or null when every level is; `held`, how many parts each
 * node drawn holds beneath it; `via`, the receiver each part is first reached through. */
export function depthView() {
  if (DEPTH.level === 'all' || !S.elements.size) return {shown: null, held: new Map(), via: new Map()};
  const found = levels(), {level, via, below} = found, depth = depthOf(DEPTH.level, found);
  if (depth === 'all') return {shown: null, held: new Map(), via: new Map()};
  const most = Number(depth), open = focusOpen(via, below);
  for (const key of DEPTH.open) open.add(key);
  const shown = new Set([...level].filter(([, at]) => at <= most).map(([key]) => key));
  const opened = [...shown].filter(key => open.has(key));
  while (opened.length) {  // a node broken out shows its next level, and so on for what it shows that is open too
    for (const next of below.get(opened.shift()) || []) {
      if (!shown.has(next)) { shown.add(next); if (open.has(next)) opened.push(next); }
    }
  }
  const held = new Map();
  for (const key of shown) {
    const inside = new Set(), walk = [key];
    while (walk.length) {
      for (const next of below.get(walk.pop()) || []) {
        if (!shown.has(next) && !inside.has(next)) { inside.add(next); walk.push(next); }
      }
    }
    if (inside.size) held.set(key, inside.size);
  }
  return {shown, held, via};
}
/* The node drawn that holds a part, the part itself when it is drawn. */
export function holderOf(key, view = depthView()) {
  if (!view.shown || !key) return key;
  const join = key.startsWith('p:') ? joinOf(key) : null;
  if (join) return view.shown.has(join.receiver) && join.providers.some(id => view.shown.has(id)) ? key
    : holderOf(join.receiver, view);
  let at = key;
  while (at && !view.shown.has(at)) at = view.via.get(at);
  return at || key;
}
/* 4: the next depth, said at the 2D map's corner and kept in web_map_depth: from all to the least, a level more each
 * press, and all again after the one short of the map's deepest. A map with no join has all alone. */
export function stepDepth() {
  const found = levels(), now = DEPTH.level === 'all' ? 'all' : depthOf(DEPTH.level, found);
  const next = now === 'all' ? depthOf(String(found.least), found) : depthOf(String(Number(now) + 1), found);
  setDepth(next);
  saveView('web_map_depth', next);
}
export function setDepth(level, said = true) {
  if (level !== 'all' && level !== 'auto' && !/^[1-9][0-9]*$/.test(level)) level = 'all';
  DEPTH.level = level;
  DEPTH.open.clear();
  if (said) {
    const drawn = S.elements.size ? depthOf(level, levels()) : level;
    note2d(drawn === 'all' ? 'Depth: all levels' : `Depth: ${drawn} level${drawn === '1' ? '' : 's'}`);
  }
  if (S.elements.size) redrawDepth();
}
/* A click on an element: one broken out folds, with whatever was opened beneath it; one holding parts breaks out its
 * next level. Says whether it did either, so the click does not also go inside. */
export function toggleDepth(key) {
  if (DEPTH.level === 'all' || IN.length || MEM.key || !S.elements.has(key)) return false;
  if (DEPTH.open.has(key)) {
    DEPTH.open.delete(key);
    for (let view = depthView(), before = -1; before !== DEPTH.open.size; view = depthView()) {
      before = DEPTH.open.size;
      for (const one of [...DEPTH.open]) if (!view.shown?.has(one)) DEPTH.open.delete(one);
    }
  } else if (depthView().held.has(key)) DEPTH.open.add(key);
  else return false;
  redrawDepth(true);
  return true;
}
/* A part chosen, by a click, the search, a link, the keys, the board or an agent, is shown: every receiver on its way
 * down is opened, as clicks would, until the selection moves or goes, `FOCUS.selected`. A join shows with its
 * receiver opened. */
export function revealDepth(key) { setFocus('selected', key || null); }
/* The receivers the branches of `FOCUS` open: those on the way down to each part, and a work part itself, so the
 * parts it works with show. */
function focusOpen(via, below) {
  const open = new Set();
  const up = (key, own) => {
    const join = key.startsWith('p:') ? joinOf(key) : null, part = join ? join.receiver : key;
    if (!S.elements.has(part)) return;
    if ((own || join) && below.has(part)) open.add(part);
    for (let at = via.get(part); at; at = via.get(at)) open.add(at);
  };
  if (FOCUS.selected) up(FOCUS.selected, false);
  for (const key of FOCUS.work) up(key, true);
  return open;
}
/* One kind of branch said again, `work` with the parts at work or `selected` with the node selected; the maps are drawn
 * again, in place and unfitted, only when the parts drawn change, so a branch opens or closes once and an event that
 * changes nothing drawn draws nothing. */
export function setFocus(kind, value) {
  FOCUS[kind] = value;
  if (IN.length || MEM.key) return false;
  const sig = focusSig();
  if (sig === FOCUS.sig) return false;
  FOCUS.sig = sig;
  if (S.loading) return false;  // the load draws both maps once it has read the rest
  drawBranch();
  build2D(true, true);
  return true;
}
/* A branch opened or closed in the 3D map at once: the parts it opens grow out of their receiver, and what is drawn
 * stays where it is, draw3d.js GROW. The 2D map follows in the way it is drawn now, `build2D`'s `branch`. */
function drawBranch() {
  GROW.beside = true;
  try { draw3D(); } finally { GROW.beside = false; }
  renderLegend();
}
/* The parts drawn now, as text to compare, so a branch said again that opens nothing new draws nothing: empty while
 * every level shows. */
function focusSig() {
  const {shown} = depthView();
  return shown ? [...shown].sort().join(' ') : '';
}
/* Both maps drawn again with what the depth shows, and fitted whole. A node's next level broken out or folded by a
 * click, `branch`, is a branch: it opens in place as the branches of `FOCUS` do, `drawBranch`. */
function redrawDepth(branch = false) {
  FOCUS.sig = focusSig();  // what is drawn now opens these, so the next branch said is compared with them
  if (branch) drawBranch(); else { draw3D(); renderLegend(); }
  if (G && !small3d()) { V3.auto = true; fit3d(); }
  build2D(true, branch).then(fullFit2d);
}
