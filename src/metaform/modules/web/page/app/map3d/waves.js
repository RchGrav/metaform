/* A property's reach, VIEW-022 and VIEW-026: the waves and pulses a click on a property node sends through the map. */
import '/page/app/map3d/light.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
import {reduced} from '/page/app/core/dom.js';
import {S} from '/page/app/core/reads.js';
import {nodeIn} from '/page/app/graph/data.js';
import {layerColor} from '/page/app/header/layers.js';
import {colorOf, ownColor, colored, shine} from '/page/app/map3d/light.js';
import {G} from '/page/app/map3d/graph3d.js';
import {M} from '/page/app/map2d/build.js';

/* A property's reach, VIEW-022 and VIEW-026. Clicking a property node sends a wave out from the element it is linked
 * to, toward the leaves where it applies and toward the trunk where it is visible. A dot travels each namespace edge
 * away from that element; a node pulses when a dot arrives, holds it, and sends it on. The dots carry the property's
 * color and give off light at more than full brightness, which the bloom pass spreads; the edges keep their own
 * look. Selecting anything else puts the map back. */
export const R = {key: null, color: null, home: null, nodes: new Set(), edges: 0};
export const endOf = end => end?.id ?? end;
const inReach = link => R.key && link.k === 'tree' && R.nodes.has(endOf(link.source))
  && R.nodes.has(endOf(link.target));
/* The wave's times in seconds, chosen by eye and not settled, VIEW-026: how often a wave leaves, how long a dot takes
 * to cross an edge, which is the same for every edge since an edge's length on screen carries no meaning, and how
 * long a node holds a dot, which is how long it pulses. `gaussian` names the timers multiplied by rnd + rnd each time
 * they are used: that runs from 0 to 2 and is 1 on average, so a timer averages its time and never repeats.
 * `opacity` is how much a node tints the light passing through it; the node is drawn solid whatever it is. */
export const TIMES = {every: 3, cross: 1, hold: 0.25, opacity: 0.6, gaussian: ['every']};
const timed = name => TIMES[name] * (TIMES.gaussian.includes(name) ? Math.random() + Math.random() : 1);
export const W = {clock: 0, last: 0, next: 0, dots: [], held: [], pulses: new Map(), glows: new Map()};
export function setReach(key) {
  const thing = key?.startsWith('r:') ? S.items.get(key) : null;
  const home = thing ? [...S.elements.values()].find(entry => entry.element.id === thing.item.element_id)?.element
    : null;
  if (!home && !R.key) return;
  R.key = home ? key : null;
  R.color = home ? layerColor(thing.layer) : null;
  R.home = home ? home.id : null;
  R.nodes = new Set(home ? elementsAlong(home) : []);
  R.edges = G ? G.graphData().links.filter(inReach).length : 0;
  for (const dot of W.dots) G.scene().remove(dot.mesh);
  if (G) for (const node of G.graphData().nodes) pulse3d(node, 0);  // no node is left lit
  Object.assign(W, {dots: [], held: [], next: W.clock, pulses: new Map()});
  if (G) G.nodeColor(G.nodeColor());  // every node back to its own color
  for (const [id, node] of M.base?.nodes || []) {
    node.g.classList.toggle('reach', R.nodes.has(id));
    node.g.style.setProperty('--reach', R.color || '');
  }
}
/* The elements a property linked to `home` reaches: home, every element above it toward the trunk, and every one
 * under it toward the leaves. */
function elementsAlong(home) {
  const along = ({address}) => address === home.address || home.address.startsWith(address + '.')
    || address.startsWith(home.address + '.');
  return [...S.elements.values()].map(entry => entry.element).filter(along).map(element => element.id);
}
/* One material for each color, shared by every dot of that color, and one shape for every dot: a shape or a
 * material made for each dot would fill the graphics card's memory as the waves run. */
function glowOf(color) {
  if (!W.glows.has(color)) {
    const made = new THREE.MeshBasicMaterial({toneMapped: false});
    made.color.set(color).multiplyScalar(2.6);  // more than full brightness, which the bloom pass spreads
    W.glows.set(color, made);
  }
  return W.glows.get(color);
}
const channels = color => [1, 3, 5].map(at => parseInt(color.slice(at, at + 2), 16) / 255);
const hexOf = part => Math.round(Math.min(1, Math.max(0, part)) * 255).toString(16).padStart(2, '0');
const colorFrom = parts => '#' + parts.map(hexOf).join('');
/* A dot arrives: the node pulses for as long as it holds the dot, then sends it on. */
function reached(id, from, outward) {
  const hold = Math.max(0.017, timed('hold'));
  W.pulses.set(id, {start: W.clock, length: hold});
  W.held.push({at: W.clock + hold, id, from, outward});
}
/* From the element the property is linked to the wave goes both ways; past it, it keeps its way, on toward the
 * leaves or on toward the trunk, and never out along a branch the property does not reach. */
function send(data, id, from, outward) {
  const template = nodeIn(data, id)?.__threeObj;
  if (!template || !template.material) return;
  for (const link of data.links) {
    if (!inReach(link)) continue;
    const down = endOf(link.source) === id, up = endOf(link.target) === id;
    if (!down && !up) continue;
    const to = down ? endOf(link.target) : endOf(link.source);
    if (to === from || (outward !== null && down !== outward)) continue;
    const mesh = template.clone(false);
    mesh.material = glowOf(R.color);
    mesh.scale.setScalar(0.32);
    G.scene().add(mesh);
    W.dots.push({mesh, link, back: up, to, from: id, outward: down, start: W.clock,
      length: Math.max(0.034, timed('cross'))});
  }
}
/* The pulse through a node, VIEW-026. Its depth is 0 as the dot enters, 1 at the node's center and 0 as it leaves.
 * The node tints the pulse as colored glass tints light; its body moves from its own color toward that tinted color
 * by the depth, and the glow is the body's own color given off as light, brighter with the depth, so the two are
 * never apart. */
function pulse3d(node, depth) {
  const object = node.__threeObj;
  if (!object || !object.material) return;
  if (!depth) {
    if (object.material.userData.pulsed) {
      colored(object.material, colorOf(node));
      shine(object.material, null, 0);
      object.material.userData.pulsed = false;
    }
    return;
  }
  const own = channels(ownColor(node)), light = channels(R.color);
  const tinted = (part, at) => light[at] * (1 - TIMES.opacity + TIMES.opacity * part);
  const body = colorFrom(own.map((part, at) => part + (tinted(part, at) - part) * depth));
  if (!object.material.userData.own) { object.material = object.material.clone(); object.material.userData.own = true; }
  colored(object.material, body);
  shine(object.material, body, depth);
  object.material.userData.pulsed = true;
}
export function wave3d(data) {
  const now = performance.now() / 1000;
  W.clock += Math.min(0.1, Math.max(0, now - (W.last || now)));
  W.last = now;
  if (!R.key) return;
  if (reduced()) {  // no wave: the reach is shown lit and still
    for (const node of data.nodes) if (R.nodes.has(node.id)) pulse3d(node, 1);
    return;
  }
  if (W.clock >= W.next) { W.next = W.clock + Math.max(0.2, timed('every')); reached(R.home, null, null); }
  const leaving = W.held.filter(item => item.at <= W.clock);
  W.held = W.held.filter(item => item.at > W.clock);
  for (const item of leaving) send(data, item.id, item.from, item.outward);
  moveDots();
  for (const node of data.nodes) {
    if (!R.nodes.has(node.id)) continue;
    const pulse = W.pulses.get(node.id), gone = pulse ? (W.clock - pulse.start) / pulse.length : 2;
    pulse3d(node, gone >= 0 && gone <= 1 ? Math.sin(Math.PI * gone) : 0);
  }
}
/* Each dot a step further along its edge; one across is taken by the node it reached. */
function moveDots() {
  const still = [];
  for (const dot of W.dots) {
    const through = (W.clock - dot.start) / dot.length;
    if (through >= 1) { G.scene().remove(dot.mesh); reached(dot.to, dot.from, dot.outward); continue; }
    const along = dot.back ? 1 - through : through, from = dot.link.source, to = dot.link.target;
    const place = dot.link.__curve ? dot.link.__curve.getPoint(along)
      : {x: from.x + (to.x - from.x) * along, y: from.y + (to.y - from.y) * along, z: from.z + (to.z - from.z) * along};
    dot.mesh.position.set(place.x, place.y, place.z);
    still.push(dot);
  }
  W.dots = still;
}
