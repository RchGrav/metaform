/* Picking on the 3D map: the edge and node the pointer takes, clicks, the picked fiber, and the tooltip over the
 * hovered node. */
import '/page/app/map3d/nodes3d.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
import {$, css, h} from '/page/app/core/dom.js';
import {S} from '/page/app/core/reads.js';
import {joinOf} from '/page/app/graph/data.js';
import {CUT, cutLink} from '/page/app/figures/cut.js';
import {figureAt} from '/page/app/figures/ask.js';
import {shownNode} from '/page/app/map3d/light.js';
import {endOf} from '/page/app/map3d/waves.js';
import {unbuilt} from '/page/app/map3d/ghosts.js';
import {G, nodeSize, wake3d} from '/page/app/map3d/graph3d.js';
import {readout, readoutOf, edgeWords, short} from '/page/app/map3d/readout.js';
import {EDGE_PICK, segmentAway} from '/page/app/map2d/hover.js';
import {select} from '/page/app/selection/select.js';
import {toggleDepth} from '/page/app/keys/walk.js';

/* The join edge nearest the pointer on the screen, within EDGE_PICK.most CSS pixels, each edge projected to the screen
 * as the camera sees it, VIEW-008: the edge a click on no node takes and the one the pointer marks. A join's edges run
 * from its receiver to its purpose vertex and on to each element serving it; either selects the join. */
const LINK_ENDS = [new THREE.Vector3(), new THREE.Vector3()];
export function linkAt3d(x, y) {
  if (!G) return null;
  const box = $('#stage').getBoundingClientRect(), camera = G.camera(), [one, two] = LINK_ENDS;
  const px = x - box.left, py = y - box.top;
  let best = null, nearest = EDGE_PICK.most;
  for (const link of G.graphData().links) {
    if (!pickable3d(link)) continue;
    const from = link.source, to = link.target;
    one.set(from.x, from.y, from.z).project(camera);
    two.set(to.x, to.y, to.z).project(camera);
    if (Math.abs(one.z) > 1 || Math.abs(two.z) > 1) continue;  // behind the eye or past the far plane
    const away = segmentAway(px, py, (one.x + 1) / 2 * box.width, (1 - one.y) / 2 * box.height,
      (two.x + 1) / 2 * box.width, (1 - two.y) / 2 * box.height);
    if (away < nearest) { nearest = away; best = link; }
  }
  return best;
}
/* A join's edge, both its ends laid out and shown. */
function pickable3d(link) {
  const from = link.source, to = link.target;
  if (!link.join || (link.k !== 'purpose' && link.k !== 'encounter')) return false;
  return typeof from === 'object' && from.x !== undefined && to.x !== undefined && shownNode(from) && shownNode(to);
}
// the join an edge draws, as a selection names it: a join has no node of its own, only its edges
export const purposeOf = link => 'p:' + link.join;
/* Each node's reach, in both maps: the area of the screen where the pointer takes it. It reaches half the distance to
 * its nearest neighbour on the screen, centre to centre, so neighbours share the room between them evenly; never less
 * than the node as drawn, and never more than REACH.most CSS pixels, so a node alone does not take the empty space
 * around it. Where reaches overlap, the node whose centre is nearest the pointer takes it; an edge is picked only where
 * no node reaches, `linkAt3d` and `edgeAt2d`. The reaches are measured again at most once a frame, as the camera, the
 * layout or the zoom moves the nodes on the screen. A neighbour farther than twice the most a reach can be never
 * shortens it, so each node looks only at the cells of a grid around it. */
export const REACH = {most: 60, d3: null, d2: null};
export function reachOf(list) {  // list: {x, y, r} in CSS pixels, r the node as drawn; sets each one's `reach`
  const cell = 2 * REACH.most, grid = new Map(), at = (x, y) => `${x},${y}`;
  for (const one of list) {
    const key = at(Math.floor(one.x / cell), Math.floor(one.y / cell));
    (grid.get(key) || grid.set(key, []).get(key)).push(one);
  }
  for (const one of list) {
    const cx = Math.floor(one.x / cell), cy = Math.floor(one.y / cell);
    let nearest = Infinity;
    for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) {
      for (const other of grid.get(at(cx + dx, cy + dy)) || []) {
        if (other !== one) nearest = Math.min(nearest, Math.hypot(other.x - one.x, other.y - one.y));
      }
    }
    one.reach = Math.max(one.r, Math.min(nearest / 2, REACH.most));
  }
  return list;
}
/* The 3D map's nodes on the screen with their reaches, measured at most once a frame. */
const NODE_AT = new THREE.Vector3();
export function reaches3d() {
  const now = performance.now();
  if (REACH.d3 && now - REACH.d3.at < 16) return REACH.d3.list;
  const box = $('#stage').getBoundingClientRect(), camera = G.camera(), list = [];
  const across = Math.tan(camera.fov * Math.PI / 360);
  for (const node of G.graphData().nodes) {
    if (node.x === undefined || !shownNode(node)) continue;
    NODE_AT.set(node.x, node.y, node.z);
    const far = NODE_AT.distanceTo(camera.position);
    NODE_AT.project(camera);
    if (Math.abs(NODE_AT.z) > 1) continue;  // behind the eye or past the far plane
    list.push({node, x: box.left + (NODE_AT.x + 1) / 2 * box.width, y: box.top + (1 - NODE_AT.y) / 2 * box.height,
      r: Math.cbrt(nodeSize(node)) * 3 / (far * across) * box.height / 2});
  }
  REACH.d3 = {at: now, list: reachOf(list)};
  return list;
}
/* The node the pointer takes on the 3D map: of those whose reach covers it, the one whose centre is nearest, so a
 * large node close to the eye does not swallow the small ones drawn over it. */
export function nodeAt3d(x, y) {
  if (!G) return null;
  let best = null, nearest = Infinity;
  for (const one of reaches3d()) {
    const middle = Math.hypot(one.x - x, one.y - y);
    if (middle <= one.reach && middle < nearest) { nearest = middle; best = one.node; }
  }
  return best;
}
/* A click on the 3D map takes what the pointer marks: with the scissors out the nearest edge, `CUT`; an agent's
 * figure keeps its own click; then the nearest node within reach, then the nearest edge. */
export function clickedAt3d(event) {
  if (!event) return;
  if (CUT.on) return clickedLink3d(event);
  if (figureAt(event.clientX, event.clientY)) return;
  const node = nodeAt3d(event.clientX, event.clientY);
  if (node) return clicked3d(node);
  clickedLink3d(event);
}
function clickedLink3d(event) {
  const link = linkAt3d(event.clientX, event.clientY);
  if (CUT.on) return cutLink(link);  // with the scissors out a click cuts the edge, `CUT`
  if (link) select(purposeOf(link), true);
}
/* The edge the pointer would take, drawn as a bright strand in the text's color while it is the one, `fibers3d`. */
export function pick3d(link) {
  if (EDGE_PICK.link3d === link) return;
  if (link) readout('3d', edgeWords(joinOf(purposeOf(link)) || {receiver: '', providers: []}));
  EDGE_PICK.link3d = link;
  $('#stage').classList.toggle('picking', Boolean(link));
  wake3d();
}
/* A click on any vertex selects that object itself: an element or a join's purpose vertex. */
export function clicked3d(node) {
  if (!node) return;
  toggleDepth(node.id);  // a node holding parts deeper than the depth breaks them out in place, or folds them, VIEW-051
  select(node.id, true);
}
/* A node takes the pointer anywhere on its sphere, not only at its center, a ghost of a part not built as every
 * other node. Each node is picked by a ball of its size on the screen around its center. */
const PICK = {edge: 2};  // the pixels past a sphere that the picture smooths its edge over, measured 2026-10-03
const PICKED = {center: new THREE.Vector3(), at: new THREE.Vector3(), ball: new THREE.Sphere(),
  size: new THREE.Vector2()};
export function picked(raycaster, hits) {
  const node = this.__data, camera = raycaster.camera;
  if (!node || !camera?.isPerspectiveCamera) return;
  const {center, at, ball, size} = PICKED;
  this.getWorldPosition(center);
  const depth = -at.copy(center).applyMatrix4(camera.matrixWorldInverse).z;
  if (depth <= 0) return;
  // the world units a pixel spans there
  const unit = 2 * depth / (camera.projectionMatrix.elements[5] * G.renderer().getSize(size).y);
  const radius = Math.cbrt(nodeSize(node)) * 3 + PICK.edge * unit;
  if (!raycaster.ray.intersectSphere(ball.set(center, radius), at)) return;
  const distance = raycaster.ray.origin.distanceTo(at);
  if (distance >= raycaster.near && distance <= raycaster.far) hits.push({distance, point: at.clone(), object: this});
}
function tipFor(node) {
  if (node.t === 'el') return [h('b', {}, node.name), ...servedBy(node)];
  if (node.t === 'item') return [h('b', {}, node.layer), h('span', {}, short(node.text, 160))];
  const join = S.joins.find(item => item.id === node.join);
  if (node.t === 'purpose') return [h('span', {}, join?.purpose || 'purpose')];
  return [h('b', {}, node.name || '')];
}
/* What an element does, which its label does not say, VIEW-038: the ef of each join it provides, as written, with
 * no subject chosen, MAP-020. Its address is not shown, since that is its name read the other way. */
function servedBy(node) {
  return S.joins.filter(join => join.providers.includes(node.id) && (join.ef || join.purpose)).slice(0, 3).map(join =>
    h('span', {class: 'why'}, short(join.ef || join.purpose, 160)));
}
/* The tooltip sits above the hovered node, clear of its sphere at any zoom, so the pointer never covers it; it goes
 * below the node only where it would leave the top of the view. */
export let hovered = null;
export function setHovered(node) { hovered = node; }
/* The tooltip names the node under the pointer and nothing else: it goes when the pointer leaves the map, when a hand
 * turns the camera, and when a press elsewhere or a key may have put a menu or a window over the node. The graph
 * reports what is under the pointer's last place on the map, so while the pointer is off the map, `TIP.out`, nothing
 * is. */
export const TIP = {out: true};
export function hover3d(node) {
  const was = hovered;
  hovered = TIP.out ? null : node || null;
  // a ghost's name comes up, VIEW-027
  if (hovered !== was && [was, hovered].some(one => one && unbuilt(one))) wake3d();
  if (hovered === was && hovered) return;
  readout('3d', hovered ? readoutOf(hovered) : null);
}
