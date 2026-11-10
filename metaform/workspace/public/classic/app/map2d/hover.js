/* The 2D map's notes and modes, hover, the edges and nodes a click takes, and unmarking. */
import '/classic/app/map2d/camera.js';  // the part before runs first, so the parts run in the page's order
import {$, SVG, h} from '/classic/app/core/dom.js';
import {REACH, reachOf, readout, readoutOf, edgeWords} from '/classic/app/map2d/readout.js';
import {flowModeNow} from '/classic/app/flow/flow.js';
import {MODE} from '/classic/app/camera/flight.js';
import {M} from '/classic/app/map2d/build.js';
import {flows2d} from '/classic/app/map2d/flow2d.js';

/* The choice made, said at the map's top right a moment, or `held` until it is done, and then faded. */
export function note2d(text, held = false) {
  const box = $('#note2d') || $('#map2d').appendChild(h('div', {id: 'note2d', class: 'note2d', role: 'status',
    'aria-live': 'polite'}));
  box.textContent = text;
  box.classList.add('on');
  clearTimeout(MODE.note);
  if (!held) MODE.note = setTimeout(() => box.classList.remove('on'), 1600);
}
/* A node's name is its hovertext only while the map's text is drawn smaller than Small, VIEW-041: there the eye
 * cannot read it, and above it a tip would cover a map that can be read. */
export function hover2d() {
  // the readout at the top of the map's window names what the pointer is on at every size, `readout`, so no node
  // carries a hover title of its own
  if (!M.svg) return;
  for (const node of M.nodes.values()) node.g.querySelector(':scope > title')?.remove();
}
/* Each edge of the whole map takes a click, which selects its join, VIEW-008: on a band one screen pixel wider than its
 * line, a copy of it with no paint in a group of their own just over the edges, `.hits2d`. They lie under the nodes, so
 * where a band crosses a node the node takes the click. */
export function hits2d(edges) {
  const drawn = edges.filter(edge => edge.path);
  if (!drawn.length) return;
  const hits = document.createElementNS(SVG, 'g');
  const group = drawn[0].path.closest('.edgePaths') || drawn[0].path.parentNode;
  hits.setAttribute('class', 'hits2d');
  group.after(hits);
  for (const edge of drawn) {
    const hit = edge.hit = edge.path.cloneNode(false);
    for (const name of ['id', 'marker-end', 'marker-start', 'data-id', 'style']) hit.removeAttribute(name);
    hit.setAttribute('class', 'hit');
    hits.append(hit);  // its band shows the selection's edges; which edge a click takes is `edgeAt2d`'s choice
  }
}
/* Which edge a click on the map takes, in both maps alike, VIEW-008: the one nearest the pointer on the screen, within
 * EDGE_PICK.most CSS pixels, so each edge takes all the room up to where the next edge is nearer, and a node under the
 * pointer always wins. The pointer shows it first: the edge it would take is marked as the pointer moves. */
export const EDGE_PICK = {most: 24, edge2d: null, node2d: null, link3d: null, frame: 0, frame3d: 0};
export const segmentAway = (x, y, x1, y1, x2, y2) => {
  const dx = x2 - x1, dy = y2 - y1, length = dx * dx + dy * dy;
  const t = length ? Math.max(0, Math.min(1, ((x - x1) * dx + (y - y1) * dy) / length)) : 0;
  return Math.hypot(x - x1 - t * dx, y - y1 - t * dy);
};
/* An edge's line as points along it, in its own units, taken again only when its path changes. */
function edgePoints(edge) {
  const path = edge.path, d = path.getAttribute('d');
  if (edge.sampled === d && edge.points) return edge.points;
  const length = path.getTotalLength(), step = Math.max(2, length / 160), points = [];
  for (let at = 0; at < length; at += step) {
    const one = path.getPointAtLength(at);
    points.push(one.x, one.y);
  }
  const end = path.getPointAtLength(length);
  points.push(end.x, end.y);
  return Object.assign(edge, {sampled: d, points}).points;
}
export function edgeAt2d(x, y) {
  if (!M.svg) return null;
  let best = null, nearest = EDGE_PICK.most;
  for (const edge of M.edges) {
    const away = edgeAway(edge, x, y, nearest);
    if (away < nearest) { nearest = away; best = edge; }
  }
  return best;
}
/* How far a join's edge is from a point of the screen, in screen pixels; Infinity for an edge that takes no click or
 * whose box is farther than `within`. */
function edgeAway(edge, x, y, within) {
  const path = edge.path;
  if (!edge.join || !path?.isConnected || path.classList.contains('reserved')) return Infinity;
  const box = path.getBoundingClientRect();
  const outside = x < box.left - within || x > box.right + within || y < box.top - within || y > box.bottom + within;
  if (outside) return Infinity;
  const ctm = path.getScreenCTM();
  if (!ctm) return Infinity;
  const local = new DOMPoint(x, y).matrixTransform(ctm.inverse()), scale = Math.hypot(ctm.a, ctm.b);
  const points = edgePoints(edge);
  let least = Infinity;
  for (let at = 0; at + 3 < points.length; at += 2) {
    least = Math.min(least,
      segmentAway(local.x, local.y, points[at], points[at + 1], points[at + 2], points[at + 3]) * scale);
  }
  return least;
}
/* The 2D map's nodes on the screen with their reaches, `REACH`, measured at most once a frame. A node is a box: the
 * whole box is its own, as drawn, and around its centre it reaches half the distance to the nearest box's centre, at
 * most REACH.most, which past a small box's edge is the room between it and its neighbours, and leaves the gaps
 * between large boxes to the edges drawn there. A group's box is not one, so the nodes and edges in it come first. */
export function reaches2d() {
  const now = performance.now();
  if (REACH.d2 && now - REACH.d2.at < 16) return REACH.d2.list;
  const list = [];
  for (const [key, node] of M.nodes) {
    const g = node.g;
    if (!g?.isConnected || !g.classList.contains('node') || g.classList.contains('reserved')) continue;
    const box = g.getBoundingClientRect();
    if (!box.width) continue;
    list.push({key, box, x: (box.left + box.right) / 2, y: (box.top + box.bottom) / 2, r: 0});
  }
  REACH.d2 = {at: now, list: reachOf(list)};
  return list;
}
/* The node the pointer takes on the 2D map: inside a box, that node; elsewhere, of those whose reach covers the
 * pointer, the one whose centre is nearest. Its key, or null. */
export function nodeAt2d(x, y) {
  if (!M.svg) return null;
  let best = null, nearest = Infinity;
  for (const one of reaches2d()) {
    const {box} = one, inside = x >= box.left && x <= box.right && y >= box.top && y <= box.bottom;
    const middle = Math.hypot(one.x - x, one.y - y);
    if (!inside && middle > one.reach) continue;
    const rank = inside ? -1 : middle;  // inside a box it is that node's
    if (rank < nearest) { nearest = rank; best = one.key; }
  }
  return best;
}
export function pickNode2d(key) {
  if (EDGE_PICK.node2d === key) return;
  M.nodes.get(EDGE_PICK.node2d)?.g.classList.remove('pick');
  EDGE_PICK.node2d = key;
  M.nodes.get(key)?.g.classList.add('pick');
  if (!HOVER2D.on?.startsWith('figure:')) HOVER2D.on = key;
  if (flowModeNow() === 'hover') flows2d();
  if (key && !HOVER2D.on?.startsWith('figure:')) readout('2d', readoutOf(key, '2d'));
}
export function pickEdge2d(edge) {
  if (EDGE_PICK.edge2d === edge) return;
  for (const one of [EDGE_PICK.edge2d, edge]) {
    if (!one) continue;
    one.path?.classList.toggle('pick', one === edge);
    one.hit?.classList.toggle('pick', one === edge);
  }
  EDGE_PICK.edge2d = edge;
  $('#viewport').classList.toggle('picking', Boolean(edge));
  if (HOVER2D.on?.startsWith('figure:')) return;
  if (edge) readout('2d', edgeWords(edge.join));
  else if (!HOVER2D.on) readout('2d', null);
}
/* The 2D map's hover, as the 3D map's: a node, an agent's figure or a box inside a node said in the readout; the
 * edge under the pointer is `pickEdge2d`'s. */
export const HOVER2D = {on: null};
function hoverOver(event) {
  const node = event.target.closest?.('g.node');
  if (!node?.dataset.key) return;
  HOVER2D.on = node.dataset.key;
  readout('2d', readoutOf(node.dataset.key, '2d'));
}
function hoverOut(event) {
  const from = event.target.closest?.('g.node');
  if (!from || from.contains(event.relatedTarget)) return;
  HOVER2D.on = EDGE_PICK.node2d;  // a node still within reach keeps the readout, `nodeAt2d`
  readout('2d', EDGE_PICK.node2d ? readoutOf(EDGE_PICK.node2d, '2d')
    : EDGE_PICK.edge2d ? edgeWords(EDGE_PICK.edge2d.join) : null);
}
$('#viewport').addEventListener('pointerover', hoverOver);
$('#viewport').addEventListener('pointerout', hoverOut);
/* All shows the whole map and leaves the selection as it is, its node and its joins still marked, so the whole map is
 * seen with what the selected node is joined to; letting go of the selection clears the marks, `deselect`. */
export function unmark2D() {
  $('#map2d').classList.remove('focused');
  for (const edge of M.edges) { edge.path?.classList.remove('on'); edge.hit?.classList.remove('on'); }
  flows2d();
  for (const node of M.nodes.values()) node.g.classList.remove('sel', 'near');
}
