/* The view's compact choices, from the earlier page's views/bar.js: the flow's steps, the edges shown, and the 3D
 * map's layout and its physics, lens and signs. The bar of buttons over the large map, which that file also made, is
 * not part of this page: the View menu and the keys make every choice. */
import '/classic/app/views/settings.js';  // the part before runs first, so the parts run in the page's order
// the forces the 3D map's physics presets add, from the same library the graph runs, `applyPhysics`
import {forceX, forceY, forceZ, forceRadial} from 'd3-force-3d';
import {$} from '/classic/app/core/dom.js';
import {S} from '/classic/app/core/reads.js';
import {shownNode} from '/classic/app/map3d/light.js';
import {endOf} from '/classic/app/map3d/waves.js';
import {G, wake3d} from '/classic/app/map3d/graph3d.js';
import {V3, cameraNow, flyTo, framed, fitTrim, fitBalls, fit3d, swapMaps} from '/classic/app/camera/flight.js';
import {NAME, small3d, fly3d, workShot} from '/classic/app/camera/fly3d.js';
import {VIEW, FLOWSET, saveView, FLOW_MODES, flowNow, chooseFlow, chooseInfo,
  chooseDirection} from '/classic/app/views/settings.js';
import {toggleNodeZoom, chooseLens, showLens, show3d} from '/classic/app/views/lens.js';
import {note2d} from '/classic/app/map2d/hover.js';

if ($('#infoat')) $('#infoat').onchange = event => chooseInfo(event.target.value);
$('#flowat').onchange = event => chooseFlow(event.target.value);
$('#directionat').onchange = event => chooseDirection(event.target.value);
$('#nodezoomat').onchange = event => toggleNodeZoom(event.target.checked);
$('#map3dat').onchange = event => show3d(event.target.checked);
$('#swapBtn').onclick = () => swapMaps();
/* 2 steps the flow through every mode, off, hover, the selection and all, with the joins' lines drawn, then the same
 * again with the lines hidden, so only what flows shows, and round again; said at the map's corner. The edges' choice
 * is web_flow_edges. */
const FLOW_STEPS = [true, false].flatMap(edges => FLOW_MODES.map(([name]) => [name, edges]));
export function stepFlow() {
  const now = FLOW_STEPS.findIndex(([name, edges]) => name === flowNow() && edges === (VIEW.edges !== false));
  const [name, edges] = FLOW_STEPS[(now + 1) % FLOW_STEPS.length];
  chooseFlow(name);
  if (edges !== (VIEW.edges !== false)) { showEdges(edges); saveView('web_flow_edges', edges); }
  note2d(`Flow: ${FLOW_MODES.find(([one]) => one === name)[1]}${edges ? '' : ', edges hidden'}`);
}
/* The joins' lines drawn or hidden, web_flow_edges, in both maps; hidden, the flow still runs where they were. Only a
 * change does anything, and in 3D it shows or hides the lines already drawn: handing the graph its link rule again
 * would have it rebuild and restart its layout, and the map would shift for seconds after each key. */
export function showEdges(on) {
  if (VIEW.edges === on) return;
  VIEW.edges = on;
  $('#map2d')?.classList.toggle('noedges', !on);
  if (!G) return;
  const links = G.graphData().links;
  // a map opened with its edges hidden never had their lines made: the graph makes them now, once
  const shown = link => shownNode(link.source) && shownNode(link.target);
  if (on && links.some(link => !link.__lineObj && shown(link))) G.linkVisibility(G.linkVisibility());
  for (const link of links) if (link.__lineObj) link.__lineObj.visible = on && shown(link);
  wake3d();
}
export function showFlow(name = flowNow()) {
  FLOWSET.name = name;
  if ($('#flowat')) $('#flowat').value = name;
}
/* The 3D map's layout, web_physics, VIEW-005: Organic or Flat; 3 switches between them. Each is a named way for the
 * layout to move, with what it helps the reader see. The forces are d3-force-3d's, which the graph runs: a change is
 * only new forces and a warmed layout, so the nodes ease to their new places from where they stand. */
export const PHYSICS = [
  ['organic', 'Organic', 'The natural layout', {}],
  ['flat', 'Flat', 'Everything on one plane', {flat: true, facing: true}],
];
export const PHYS = {name: 'organic', decay: 0.4};
/* The views whose layout turns outward signs sideways to the eye face their signs forward instead, those views only. */
export const signsFacing = () => VIEW.signs === 'facing'
  || Boolean(PHYSICS.find(([name]) => name === PHYS.name)?.[3].facing);
const baseCharge = node => node.t === 'el' ? -140 : node.t === 'item' ? -10 : -18;
const baseDistance = link => link.k === 'layer' ? 8 : link.k === 'item' ? 12 : link.k === 'tree' ? 60 : 34;
/* Each node's step along the chains of service: 0 for an element that serves no one, and each part serving it a whole
 * step on, along the join's edge from its receiver. A node off every chain has none and is not pulled. */
function serviceSteps(data) {
  const next = new Map(), served = new Set(), steps = new Map();
  for (const link of data.links) {
    if (link.k !== 'encounter') continue;
    const from = endOf(link.source), to = endOf(link.target);
    if (!next.has(from)) next.set(from, []);
    next.get(from).push(to);
    served.add(to);
  }
  const queue = data.nodes.filter(node => node.t === 'el' && !served.has(node.id)).map(node => node.id);
  for (const id of queue) steps.set(id, 0);
  while (queue.length) {
    const id = queue.shift();
    for (const to of next.get(id) || []) if (!steps.has(to)) { steps.set(to, steps.get(id) + 1); queue.push(to); }
  }
  return steps;
}
/* A weak gravity on each connected part of the map as a whole: each part's middle is drawn toward the map's middle,
 * every node of it by the same amount, so a part joined to nothing of the rest stays near it instead of drifting off,
 * and no part is squeezed. Its parts are read again whenever the graph's nodes change. */
function partsGravity(strength) {
  let parts = null;
  const force = alpha => {
    parts ??= partsOf(force.nodes);
    const pull = strength * alpha;
    for (const part of parts) {
      let x = 0, y = 0, z = 0;
      for (const node of part) { x += node.x || 0; y += node.y || 0; z += node.z || 0; }
      x /= part.length; y /= part.length; z /= part.length;
      for (const node of part) {
        node.vx -= x * pull; node.vy -= y * pull;
        if (node.vz !== undefined) node.vz -= z * pull;
      }
    }
  };
  force.initialize = nodes => { force.nodes = nodes; parts = null; };
  force.nodes = [];
  return force;
}
/* The connected parts of the map, its nodes grouped by the links between them, found by union and find. */
function partsOf(nodes) {
  const owner = new Map();
  const find = id => {
    while (owner.get(id) !== id) id = owner.set(id, owner.get(owner.get(id))).get(id);
    return id;
  };
  for (const node of nodes) owner.set(node.id, node.id);
  for (const link of G.graphData().links) {
    const one = endOf(link.source), two = endOf(link.target);
    if (owner.has(one) && owner.has(two)) owner.set(find(one), find(two));
  }
  const groups = new Map();
  for (const node of nodes) {
    const root = find(node.id);
    if (!groups.has(root)) groups.set(root, []);
    groups.get(root).push(node);
  }
  return [...groups.values()];
}
export function applyPhysics(name, warm = true) {
  const preset = PHYSICS.find(([one]) => one === name) || PHYSICS[0], how = preset[3];
  PHYS.name = preset[0];
  if (!G) return;
  const steps = how.axis || how.radial ? serviceSteps(G.graphData()) : null, gap = 52;
  const at = node => (steps?.get(node.id) ?? 0) * gap, pulled = node => steps?.has(node.id) ? 0.22 : 0;
  // Spread pushes within a part, not part from part: the push reaches no farther than PHYSICS_REACH
  G.d3Force('charge').strength(node => baseCharge(node) * (how.charge || 1)).distanceMax(how.reach || Infinity);
  G.d3Force('parts', partsGravity(how.gravity ?? 0.06));
  G.d3Force('link').distance(link => baseDistance(link) * (how.distance || 1));
  G.d3Force('serviceX', how.axis === 'x' ? forceX(node => at(node) * how.sign).strength(pulled) : null);
  G.d3Force('serviceY', how.axis === 'y' ? forceY(node => at(node) * how.sign).strength(pulled) : null);
  G.d3Force('serviceZ', how.axis === 'z' ? forceZ(node => at(node) * how.sign).strength(pulled)
    : how.flat ? forceZ(0).strength(0.35) : null);
  G.d3Force('serviceR', how.radial ? forceRadial(node => at(node) + gap * 0.25).strength(pulled) : null);
  PHYS.decay = how.decay || 0.4;
  G.d3VelocityDecay(PHYS.decay);
  if (warm) G.d3ReheatSimulation();
}
/* Flat lays the map on one plane, z = 0. Choosing it turns the camera to face that plane square on, from whichever
 * side it is nearer, so the map is seen flat at once; a drag turns it from there as ever. */
export const flatNow = () => Boolean(PHYSICS.find(([name]) => name === PHYS.name)?.[3].flat);
export const flatFacing = () => ({turn: Math.cos(cameraNow().turn) >= 0 ? 0 : Math.PI, tilt: Math.PI / 2});
function faceFlat() {
  if (!G) return;
  const balls = fitBalls(G.graphData()).map(one => ({...one, z: 0}));  // where Flat is taking them
  if (balls.length) flyTo(framed(balls, {mass: fitTrim(), facing: flatFacing()}));
}
export function choosePhysics(name) {
  if (name === PHYS.name) return;
  applyPhysics(name);
  if (flatNow()) faceFlat();
  saveView('web_physics', name);
}
// the 3D map's lens and its names, each a choice of the View menu; 7 steps through the lenses
$('#lensat').onchange = event => chooseLens(event.target.value);
showLens();
$('#signsat').onchange = event => chooseSigns(event.target.value);
function chooseSigns(name) {
  VIEW.signs = name === 'facing' ? 'facing' : 'outward';
  showSigns();
  wake3d();
  saveView('web_signs', VIEW.signs);
}
export function showSigns() {
  if ($('#signsat')) $('#signsat').value = VIEW.signs || 'facing';
}
showSigns();
export function setMode3d(mode, level = null) {
  if (!G || small3d()) return;
  V3.mode = mode;
  if (level) NAME.level = level;
  if (mode === 'whole') fit3d();
  else if (mode === 'work') workShot(S.selected);
  else if (mode === 'zoom' && S.selected) fly3d(S.selected, true);
  else if (mode === 'free') V3.auto = false;  // the layout no longer refits it either
}
