/* The large map's compact choices: info, flow steps, the edges shown, the 3D layout and its physics, lens, signs and
 * the Ultra graphics menu. */
import '/page/app/views/settings.js';  // the part before runs first, so the parts run in the page's order
// the forces the 3D map's physics presets add, from the same library the graph runs, `applyPhysics`
import {forceX, forceY, forceZ, forceRadial} from 'd3-force-3d';
// Ultra graphics, web_graphics: the 3D map in outer space, drawn by its own module through the hooks marked ULTRA.
import * as ULTRA from '/page/ultra.js';
import {$, h, fill} from '/page/app/core/dom.js';
import {overlay} from '/page/app/core/overlays.js';
import {S} from '/page/app/core/reads.js';
import {shownNode} from '/page/app/map3d/light.js';
import {endOf} from '/page/app/map3d/waves.js';
import {G, wake3d} from '/page/app/map3d/graph3d.js';
import {PLAIN, setTheme} from '/page/app/map3d/draw3d.js';
import {V3, cameraNow, flyTo, framed, fitTrim, fitBalls, fit3d} from '/page/app/camera/flight.js';
import {NAME, small3d, fly3d} from '/page/app/camera/fly3d.js';
import {VIEW, INFOSET, FLOWSET, NODEZOOM, LENS, SIGNS, saveView, PEEK, peekParts, peek, FLOW_MODES, flowModes, flowNow,
  chooseFlow, HOVER_INFO, chooseInfo} from '/page/app/views/settings.js';
import {toggleNodeZoom, showModes3d, chooseLens, showLens} from '/page/app/views/lens.js';
import {note2d} from '/page/app/map2d/hover.js';

/* A choice of the large map's bar made less often: one compact button naming the choice in force, "Lens Natural L ▾",
 * opening a small menu of every choice with what it does, as the physics opens; the frequent ones, Node zoom, the
 * modes, Fit and Flow, stay segmented controls, so the bar keeps one row. `list` is [name, word, why]; `choose` takes
 * a name; `show(name)` names it on the button and checks it in the menu. */
function barPick({id, label, key, title, list, choose}) {
  const items = new Map();
  const pick = {items, button: null, menu: null, show: null};
  const item = ([name, word, why]) => {
    const one = checkItem(word, {title: why}, () => { pick.menu.hidden = true; choose(name); });
    items.set(name, one);
    return one;
  };
  pick.menu = h('div', {class: 'menu physicsmenu barmenu', id, role: 'menu', hidden: true, 'aria-label': title},
    list.map(item));
  document.body.append(pick.menu);
  overlay(pick.menu, {kind: 'menu'});
  pick.button = h('button', {class: `btn sm quiet barpick ${id.replace(/menu$/, '')}btn`, type: 'button',
    'aria-haspopup': 'menu', 'aria-controls': id, 'aria-expanded': 'false', 'aria-keyshortcuts': key,
    title: `${title} (${key})`, onclick: event => toggleBelow(event, pick.menu, pick.button)});
  pick.show = name => {
    const word = (list.find(([one]) => one === name) || list[0])[1];
    // drawn again only when the choice changed: the bar names its parts on every press in it, and a button whose
    // contents are made again between the press and the release takes no click
    if (pick.drawn === word) return;
    pick.drawn = word;
    // the key stays in the title and aria-keyshortcuts, and the reference ? lists it, so the button keeps its room
    fill(pick.button, h('span', {class: 'peeklabel'}, label), h('span', {class: 'value'}, word),
      h('i', {class: 'i i-chev', 'aria-hidden': 'true'}));
    pick.button.setAttribute('aria-label', `${label}: ${word}`);
    for (const [one, item] of items) item.setAttribute('aria-checked', String(one === name));
  };
  return pick;
}
/* A menu's item checked when its choice is in force: its word after a check mark. */
function checkItem(word, props, chosen) {
  return h('button', {type: 'button', role: 'menuitemradio', 'aria-checked': 'false', ...props,
    onclick: event => { event.stopPropagation(); chosen(); }},
  h('span', {class: 'wsitem'}, h('i', {class: 'i i-check wscheck', 'aria-hidden': 'true'}), word));
}
/* A bar's menu opened under its button, its right edge at the button's and kept inside the window, or closed. */
function toggleBelow(event, menu, button) {
  event.stopPropagation();
  if (!menu.hidden) { menu.hidden = true; return; }
  menu.hidden = false;
  const at = button.getBoundingClientRect(), size = menu.getBoundingClientRect();
  Object.assign(menu.style, {position: 'fixed', top: `${at.bottom + 4}px`,
    left: `${Math.max(8, Math.min(at.right - size.width, innerWidth - size.width - 8))}px`});
}
INFOSET.pick = barPick({id: 'infomenu', label: 'Info', key: 'I', title: 'What is said of what the pointer is on',
  list: HOVER_INFO, choose: name => chooseInfo(name)});
INFOSET.buttons = INFOSET.pick.items;
INFOSET.pick.show(VIEW.hoverInfo || 'name+summary');
if ($('#infoat')) $('#infoat').onchange = event => chooseInfo(event.target.value);
function stepInfo() {
  const names = HOVER_INFO.map(([name]) => name), at = names.indexOf(VIEW.hoverInfo || 'name+summary');
  chooseInfo(names[(at + 1) % names.length]);
}
// Node zoom, in the bar beside the modes, as pressed while each selection is flown to (Z)
NODEZOOM.button = h('button', {class: 'btn sm quiet nodezoom', type: 'button', 'aria-pressed': 'true',
  'aria-keyshortcuts': 'Z', 'aria-label': 'Node zoom',
  title: 'Node zoom: fly to each node selected and frame it with its neighbours; off, a selection leaves the camera'
    + ' (Z)', onclick: event => { event.stopPropagation(); toggleNodeZoom(); }},
  h('span', {class: 'state'}, 'On'), h('kbd', {}, 'Z'));
$('#nodezoomat').onchange = event => toggleNodeZoom(event.target.checked);
$('#flowat').onchange = event => chooseFlow(event.target.value);
/* D steps the flow through hover, the selection and all, with the edges drawn, then the three again with the edges
 * hidden, so only what flows shows; off and live stay in the View menu and the bar. The edges' choice is
 * web_flow_edges, said at the corner as the flow's is. */
const FLOW_STEPS = [['hover', true], ['selected', true], ['all', true], ['hover', false], ['selected', false],
  ['all', false]];
export function stepFlow() {
  const now = FLOW_STEPS.findIndex(([name, edges]) => name === flowNow() && edges === (VIEW.edges !== false));
  const [name, edges] = FLOW_STEPS[(now + 1) % FLOW_STEPS.length];
  chooseFlow(name);
  showEdges(edges);
  saveView('web_flow_edges', edges);
  const word = FLOW_MODES.find(([one]) => one === name)?.[1];
  note2d(`Flow: ${word}${edges ? '' : ', edges hidden'}`);
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
  const offered = new Set(flowModes().map(([one]) => one));
  for (const [one, button] of FLOWSET.buttons) {
    button.hidden = !offered.has(one);
    button.setAttribute('aria-checked', String(one === name));
  }
  if ($('#flowat')) $('#flowat').value = name;
}
/* The 3D map's layout, web_physics, VIEW-005: Organic or Flat, chosen in the bar's Layout menu, and L switches between
 * them. Each is a named way for the layout to move, with what it helps the reader see. The forces are d3-force-3d's,
 * which the graph runs: a change is only new forces and a warmed layout, so the nodes ease to their new places from
 * where they stand. */
export const PHYSICS = [
  ['organic', 'Organic', 'The natural layout', {}],
  ['flat', 'Flat', 'Everything on one plane', {flat: true, facing: true}],
];
export const PHYS = {name: 'organic', decay: 0.4, buttons: new Map()};
/* The views whose layout turns outward signs sideways to the eye face their signs forward instead, those views only. */
export const signsFacing = () => VIEW.signs === 'facing'
  || Boolean(PHYSICS.find(([name]) => name === PHYS.name)?.[3].facing);
const baseCharge = node => node.t === 'el' ? -140 : node.t === 'item' ? -10 : -18;
const baseDistance = link => link.k === 'layer' ? 8 : link.k === 'item' ? 12 : link.k === 'tree' ? 60 : 34;
/* Each node's step along the chains of service: 0 for an element that serves no one, a join's purpose half a step on
 * from its receiver, and each part serving it a whole step. A node off every chain has none and is not pulled. */
function serviceSteps(data) {
  const next = new Map(), served = new Set(), steps = new Map();
  for (const link of data.links) {
    if (link.k !== 'purpose' && link.k !== 'encounter') continue;
    const from = endOf(link.source), to = endOf(link.target);
    if (!next.has(from)) next.set(from, []);
    next.get(from).push(to);
    served.add(to);
  }
  const queue = data.nodes.filter(node => node.t === 'el' && !served.has(node.id)).map(node => node.id);
  for (const id of queue) steps.set(id, 0);
  while (queue.length) {
    const id = queue.shift();
    for (const to of next.get(id) || []) if (!steps.has(to)) { steps.set(to, steps.get(id) + 0.5); queue.push(to); }
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
  peekParts();
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
  if (name === PHYS.name) return peek('key');
  applyPhysics(name);
  if (flatNow()) faceFlat();
  peek('key');
  saveView('web_physics', name);
}
/* The layout in the bar: one button naming the layout in force, opening the list of both, each by its name and what it
 * helps the reader see, so the bar stays one quiet row; L switches between them. */
function physicsItem([name, word, why]) {
  const button = checkItem(word, {'aria-checked': String(name === PHYS.name), 'aria-keyshortcuts': 'L',
    title: `${why} (L)`}, () => { PHYS.list.hidden = true; choosePhysics(name); });
  PHYS.buttons.set(name, button);
  return button;
}
PHYS.list = h('div', {class: 'menu physicsmenu', id: 'physicsmenu', role: 'menu', hidden: true,
  'aria-label': "The 3D map's layout"}, PHYSICS.map(physicsItem));
document.body.append(PHYS.list);
overlay(PHYS.list, {kind: 'menu'});
PHYS.shown = h('button', {class: 'btn sm quiet physicsbtn', type: 'button', 'aria-haspopup': 'menu',
  'aria-controls': 'physicsmenu', 'aria-expanded': 'false',
  title: "How the 3D map is laid out, Organic or Flat; L switches between them",
  onclick: event => toggleBelow(event, PHYS.list, PHYS.shown)});
PEEK.physics.append(PHYS.shown);
// the 3D map's lens, its names and its graphics, each a compact choice of the bar beside the modes, `barPick`; L, S
// and U still step through them
LENS.pick = barPick({id: 'lensmenu', label: 'Lens', key: 'L',
  title: "The 3D map's lens: how far its view opens as its pane grows tall",
  list: [['natural', 'Natural', 'The view opens no wider than the eye sees, 55°'],
    ['wide', 'Wide', 'The view opens to 80° as the pane grows tall'],
    ['fisheye', 'Fisheye', 'The view opens to 120°, the whole map close around you']],
  choose: name => chooseLens(name)});
LENS.button = LENS.pick.button;
$('#lensat').onchange = event => chooseLens(event.target.value);
showLens();
SIGNS.pick = barPick({id: 'signsmenu', label: 'Signs', key: 'S', title: "How the 3D map's names stand",
  list: [
    ['outward', 'Outward', "Each name a sign standing out from the map's middle, turned round when seen from behind"],
    ['facing', 'Facing', 'Each name turned to face you']], choose: name => chooseSigns(name)});
SIGNS.button = SIGNS.pick.button;
$('#signsat').onchange = event => chooseSigns(event.target.value);
// Ultra graphics, U, page/ultra.js: the 3D map in outer space or clean; the button names the look the map has
PEEK.ultra = barPick({id: 'ultramenu', label: 'Ultra', key: 'U',
  title: 'How the 3D map is drawn: clean, or in outer space',
  list: [['clean', 'Off', 'The map as it has always been drawn'],
    ['ultra', 'On', 'The map in outer space: a starfield, bodies and filaments of light']],
  choose: name => { setTheme(name === 'ultra' ? 'space' : PLAIN.last); showUltra(); peek('key'); }});
export function showUltra() { PEEK.ultra.show(ULTRA.stats().mode === 'ultra' ? 'ultra' : 'clean'); }
showUltra();
function chooseSigns(name) {
  VIEW.signs = name === 'facing' ? 'facing' : 'outward';
  showSigns();
  wake3d();
  peek('key');
  saveView('web_signs', VIEW.signs);
}
export function showSigns() {
  SIGNS.pick?.show(VIEW.signs === 'facing' ? 'facing' : 'outward');
  if ($('#signsat')) $('#signsat').value = VIEW.signs || 'outward';
}
showSigns();
export function showPhysics() {
  const at = PHYSICS.findIndex(([one]) => one === PHYS.name), preset = PHYSICS[Math.max(0, at)];
  if (PHYS.drawn === preset[0]) return;  // as `barPick`: made again only on a change, so a press on it is never lost
  PHYS.drawn = preset[0];
  fill(PHYS.shown, h('span', {class: 'peeklabel'}, 'Layout'), h('span', {class: 'value'}, preset[1]),
    h('i', {class: 'i i-chev', 'aria-hidden': 'true'}));  // each preset's key is in its menu
  PHYS.shown.setAttribute('aria-label', `Physics: ${preset[1]}`);
}
showPhysics();
// No Alt shortcuts: Alt with a digit is taken by the system on some machines; L switches the layout.
export function setMode3d(mode, level = null) {
  if (!G || small3d()) return;
  V3.mode = mode;
  if (level) NAME.level = level;
  showModes3d();
  if (mode === 'whole') fit3d();
  else if (mode === 'zoom' && S.selected) fly3d(S.selected, true);
  else if (mode === 'free') V3.auto = false;  // the layout no longer refits it either
}
