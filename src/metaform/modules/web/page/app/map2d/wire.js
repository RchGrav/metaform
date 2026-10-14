/* Letting go of the selection, the 2D map's own wiring of pointer and wheel, and back and forward through the nodes
 * selected. */
import '/page/app/map2d/flow2d.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {S, MEM} from '/page/app/core/reads.js';
import {setReach} from '/page/app/map3d/waves.js';
import {G, wake3d, touched} from '/page/app/map3d/graph3d.js';
import {meetEnds} from '/page/app/camera/fly3d.js';
import {M} from '/page/app/map2d/build.js';
import {showBase} from '/page/app/map2d/fit.js';
import {IN, samePath, drawInside} from '/page/app/map2d/inside.js';
import {leaveMemories} from '/page/app/memory/graph.js';
import {setCam, stopCam, area2d, labelSize, scaleFor, focus2d, place2d, aim2d, hold2d} from '/page/app/map2d/camera.js';
import {EDGE_PICK, edgeAt2d, nodeAt2d, pickNode2d, pickEdge2d, unmark2D} from '/page/app/map2d/hover.js';
import {clicked2d, modified2d} from '/page/app/map2d/flow2d.js';
import {select} from '/page/app/selection/select.js';

/* Letting go of the selection, by a click on the map's empty space or Escape, VIEW-008: its marks go from both maps,
 * the panel says nothing is selected, and nothing is selected again until the person selects, even as the map is read
 * again. */
export function deselect() {
  if (!S.selected) return;
  Object.assign(S, {selected: null, cleared: true, panelFor: null, trail: [], neighbors: new Set()});
  setReach(null);
  unmark2D();
  if (G) { G.nodeColor(G.nodeColor()); meetEnds(); wake3d(); }
  noneSelected();  // the 2D view stays where it is, VIEW-041
}
export function noneSelected() {
  fill($('#p-object'), h('p', {class: 'empty'},
    "Nothing is selected. Click a part on either map, or press an arrow key to start from the map's entry."));
}
/* A drag under way on the 2D map, and whether the last press was a drag, so its release is no click. */
const PAN = {drag: null, dragged: false};
function wire2D() {
  const host = $('#map2d');
  // A drag moves the view within the mode's limits, VIEW-041, and is not a click on what it started on.
  host.addEventListener('pointerdown', startPan);
  host.addEventListener('pointermove', pan);
  host.addEventListener('pointerup', () => { PAN.dragged = Boolean(PAN.drag?.moving); PAN.drag = null; });
  host.addEventListener('pointermove', markUnderPointer);
  host.addEventListener('pointerleave', () => { pickNode2d(null); pickEdge2d(null); });
  host.addEventListener('click', clickPicked, true);
  host.addEventListener('click', clickEmpty);
  host.addEventListener('wheel', wheel2d, {passive: false});
  // a press, a drag or the wheel here holds an agent start's auto zoom off for a while, `TOUCHED`, VIEW-041
  for (const type of ['pointerdown', 'wheel']) host.addEventListener(type, touched, {capture: true, passive: true});
  // full fit refits as the pane changes size, and a view held keeps its zoom, VIEW-041
  new ResizeObserver(() => aim2d()).observe($('#viewport'));
}
function startPan(event) {
  PAN.dragged = false;
  // the crumbs inside a node are links, never a place a pan starts
  if (event.target.closest('button, a, .crumbs') || !M.cam) return;
  PAN.drag = {x: event.clientX, y: event.clientY, cam: {...M.cam}, moving: false};
}
function pan(event) {
  const drag = PAN.drag;
  if (!drag) return;
  if (!drag.moving) {  // captured only once it is a drag, so a click still reaches the node under it
    if (Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 4) return;
    stopCam();
    drag.cam = {...M.cam};
    drag.moving = true; $('#map2d').setPointerCapture(event.pointerId);
  }
  const area = area2d(), scale = area.width / drag.cam.w, at = focus2d(drag.cam, area);
  const to = {x: at.x - (event.clientX - drag.x) / scale, y: at.y - (event.clientY - drag.y) / scale};
  setCam(place2d(scale, to, area));
}
/* What a click on the map would not take: off the map, on its crumbs, a button or an agent's figure, which keeps its
 * own. */
const offMap = target => !M.svg || target.closest?.('.crumbs, button, g.agent2d') || !target.closest?.('#viewport');
/* The edge a click would take, marked as the pointer moves, once a frame; a node under the pointer takes it instead:
 * the node nearest the pointer within reach, then the nearest edge. */
function markUnderPointer(event) {
  if (PAN.drag?.moving || EDGE_PICK.frame) return;
  const {clientX: x, clientY: y, target} = event;
  EDGE_PICK.frame = requestAnimationFrame(() => {
    EDGE_PICK.frame = 0;
    const off = offMap(target);
    const key = off ? null : nodeAt2d(x, y);
    pickNode2d(key);
    pickEdge2d(off || key ? null : edgeAt2d(x, y));
    $('#viewport').classList.toggle('picking', Boolean(key || EDGE_PICK.edge2d));
  });
}
/* A click takes the nearest node within reach, then the nearest edge, before a group behind them does. */
function clickPicked(event) {
  if (PAN.dragged || offMap(event.target)) return;
  const key = nodeAt2d(event.clientX, event.clientY), edge = key ? null : edgeAt2d(event.clientX, event.clientY);
  if (!key && !edge) return;
  event.stopPropagation();
  clicked2d(key || 'p:' + edge.join.id, event);
}
/* A click on the map where there is no node and no edge lets go of the selection, VIEW-008. */
function clickEmpty(event) {
  if (PAN.dragged) { PAN.dragged = false; return; }
  if (!M.svg || !event.target.closest('#viewport') || modified2d(event)) return;
  deselect();
}
/* The wheel, VIEW-041, and a pinch on a trackpad, which the browser sends as the wheel with Ctrl, zoom the map about
 * the pointer at any time: at once, as a wheel does, flat steps on a mouse wheel and its own acceleration on a
 * trackpad, between half the full fit and the most the map's text can be blown up, within the map's limits. The view
 * is then held where the person leaves it. */
function wheel2d(event) {
  if (!M.cam || !M.bounds) return;
  event.preventDefault();
  stopCam();
  const pixels = delta => event.deltaMode === 1 ? delta * 16 : event.deltaMode === 2 ? delta * 400 : delta;
  zoomByWheel(event, pixels(event.deltaY), area2d());
}
function zoomByWheel(event, delta, area) {
  const c = M.cam, scale = area.width / c.w;
  const f = Math.exp(Math.max(-200, Math.min(200, delta)) * 0.0015);
  const least = scaleFor(area) / 2, most = 64 / labelSize(M.svg);
  const zoom = Math.min(most, Math.max(least, scale / f)), w = area.width / zoom, height = area.height / zoom;
  const px = (event.clientX - area.left) / area.width, py = (event.clientY - area.top) / area.height;
  hold2d();
  const pointer = focus2d({x: c.x + (c.w - w) * px, y: c.y + (c.h - height) * py, w, h: height}, area);
  return setCam(place2d(zoom, pointer, area));
}
wire2D();
/* Back and forward step through the nodes selected, as a browser does, Alt with Left and Right, which ? lists; a new
 * selection drops the steps forward. */
export async function step(by) {
  if (MEM.key) { if (by < 0) leaveMemories(); return; }  // back from a memory network is back to the map, VIEW-031
  const to = S.at + by;
  if (to < 0 || to >= S.history.length) return;
  S.at = to;
  const entry = S.history[to];
  if (!samePath(entry.path, IN)) {
    if (!IN.length && M.base) M.base.cam = {...M.cam};
    IN.length = 0;
    IN.push(...entry.path.map(level => ({...level, more: {}, things: new Map()})));
    if (IN.length) await drawInside(); else showBase();
  }
  select(entry.id, true, false, true);
}
