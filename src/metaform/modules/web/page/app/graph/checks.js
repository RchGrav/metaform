/* What a browser check reads of the page, window.metaform: the graph and both maps as drawn, the camera, the flow,
 * the labels, the figures and the mascot, and how a node is drawn for its condition. Later parts add their own
 * reads. */
import '/page/app/graph/data.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
// drei's transmission material in its vanilla form, the glass itself, VIEW-025. It imports three.js as `three`, which
// the page's import map names as the same file, so both share one three.js.
import {MeshTransmissionMaterial} from '/vendor/drei-vanilla/MeshTransmissionMaterial.js';
import {$, css} from '/page/app/core/dom.js';
import {S, MEM} from '/page/app/core/reads.js';
import {graphData, READY} from '/page/app/graph/data.js';
import {ROAM, embody, bodies, characters} from '/page/app/figures/agents.js';
import {MASCOT, mascotGlyph, mascotDriven} from '/page/app/figures/mascot.js';
import {BUBBLE, say, CUT, cutMode, cutLink} from '/page/app/figures/cut.js';
import {ATTN, mascotEvent} from '/page/app/figures/attention.js';
import {EYE, mascotEyes} from '/page/app/figures/eyes.js';
import {mascotScreen, figureAt} from '/page/app/figures/ask.js';
import {ROAM2D, MASCOT2D} from '/page/app/figures/roam2d.js';
import {paceOf, ownColor, GLASS, shapes, setSegments, BEHIND} from '/page/app/map3d/light.js';
import {R, endOf, TIMES, W} from '/page/app/map3d/waves.js';
import {BLOOM, samplesFor, drawnBy} from '/page/app/map3d/bloom.js';
import {nodeObject, linkColor} from '/page/app/map3d/ghosts.js';
import {G, nodeSize, FRAMES, wake3d} from '/page/app/map3d/graph3d.js';
import {linkAt3d, purposeOf, reaches3d, clicked3d, hovered, setHovered} from '/page/app/map3d/pick3d.js';
import {readout, readoutOf} from '/page/app/map3d/readout.js';
import {tags, LABELS} from '/page/app/map3d/labels.js';
import {FLOW, FLOW_MODE_LIST, flowMode, flowLive} from '/page/app/flow/flow.js';
import {FX} from '/page/app/flow/fx3d.js';
import {FLIGHT, MODE, V3, cameraNow} from '/page/app/camera/flight.js';
import {meetEnds} from '/page/app/camera/fly3d.js';
import {VIEW, LENS, peek, agentsWindow} from '/page/app/views/settings.js';
import {PHYS, setMode3d} from '/page/app/views/bar.js';
import {M} from '/page/app/map2d/build.js';
import {IN} from '/page/app/map2d/inside.js';
import {memories} from '/page/app/memory/graph.js';
import {area2d, foot2d, center2d, fullFit2d, hold2d, moveCam, place2d, focus2d,
  labelSize} from '/page/app/map2d/camera.js';
import {edgeAt2d, reaches2d} from '/page/app/map2d/hover.js';
import {ends2d} from '/page/app/map2d/flow2d.js';
import {select} from '/page/app/selection/select.js';
import {DOCK, EMBODY, embodyHooks} from '/page/app/dock/embody.js';
import {menu} from '/page/app/board/messages.js';
import {giveWork} from '/page/app/task/task.js';
import {notesAt, addElement} from '/page/app/task/notes.js';
import {P} from '/page/app/panel/prompts.js';
import {LIVE} from '/page/app/live/stream.js';

const accessed = (value, item) => typeof value === 'function' ? value(item) : value;
const node3d = id => G?.graphData().nodes.find(item => item.id === id);
const stageBox = () => $('#stage').getBoundingClientRect();

window.metaform = {graph: () => graphData(), selected: () => S.selected, select: id => select(id, true),
  ready: READY.promise,
  selectAddress,
  viewSlot: () => $('#viewslot'),
  find: address => [...S.elements.values()].find(entry => entry.element.address === address)?.element.id ?? null,
  click3d: id => clicked3d(node3d(id)),
  drawn: () => G ? {nodes: G.graphData().nodes.length, links: G.graphData().links.length} : null,
  curves: () => G ? G.graphData().links.map(link => ({k: link.k, curve: accessed(G.linkCurvature(), link)})) : [],
  linkColors: () => G ? G.graphData().links.map(link => ({join: link.join || null, k: link.k,
    target: link.target?.id ?? link.target, color: linkColor(link)})) : [],
  layouts: () => V3.layouts, drawnWork: id => (node3d(id)?.work || []).length,
  loaded: () => S.shown && !S.loading && !S.opening, editor: () => P.editor, live: () => LIVE.layer,
  changes: () => LIVE.done,
  inside: () => IN.length && M.drawn === IN.at(-1) ? [...M.nodes.keys()] : [], vertical: () => M.vertical,
  at2d: id => M.nodes.has(id) ? {x: M.nodes.get(id).x, y: M.nodes.get(id).y} : null,
  drawn2d,
  look: id => look(id), fit: () => fullFit2d(),
  // a zoom by hand, its text drawn `px` high, on the selection, eased there and then held, as the wheel holds it
  zoom2d: px => { hold2d(); moveCam(place2d(px / labelSize(M.svg), center2d(S.selected) || focus2d(M.cam))); },
  view2d: () => ({full: !MODE.free}),
  peek: () => peek(),
  embodyState: () => ({target: DOCK.target, session: DOCK.session, open: EMBODY.open, hooks: embodyHooks(),
    setting: VIEW.embody, turns: VIEW.embodyTurns}),
  fov3d: () => G ? Math.round(G.camera().fov * 10) / 10 : null, cameraAt: () => G ? cameraNow() : null,
  foot2d: () => Math.min(foot2d(), area2d().height / 3), lens: () => LENS.name,
  agentsWindow: count => agentsWindow(count), physics: () => PHYS.name,
  links3d,
  edgeAt: (x, y) => { const edge = edgeAt2d(x, y); return edge ? 'p:' + edge.join.id : null; },
  linkAt3d: (x, y) => { const link = linkAt3d(x, y); return link ? purposeOf(link) : null; },
  mode3d: (name, level) => setMode3d(name, level), menu: id => menu(id), task: id => giveWork(id),
  element: id => addElement(id), note: id => notesAt(id),
  // The memory network of a node, VIEW-031: opened as the menu's entry opens it, and what both views draw of it, or
  // null on the map.
  memories: id => memories(id),
  memory: memoryDrawn,
  away3d: () => G ? G.camera().position.distanceTo(G.controls().target) : 0, fits3d: () => V3.fits,
  samples3d: () => G ? G.postProcessingComposer().renderTarget1.samples : 0,
  samplesFor: name => samplesFor(name), drawnBy: () => G ? drawnBy() : '',
  smooth3d, pause3d,
  // The frames the 3D map has drawn, which stop once nothing on it moves.
  frames3d: () => FRAMES.drawn,
  zoom3d,
  glass,
  bloom: () => ({pass: Boolean(BLOOM), levels: BLOOM ? BLOOM.levels : 0, on: Boolean(BLOOM?.enabled)}),
  wave: () => ({dots: W.dots.length, shapes: G ? G.renderer().info.memory.geometries : 0,
    lit: G ? G.graphData().nodes.filter(node => node.__threeObj?.material?.userData.pulsed).map(node => node.id) : []}),
  pin3d, view3d, screen3d, waveTimes,
  reach: () => ({property: R.key, edges: R.edges, elements: [...S.elements.values()].map(entry => entry.element)
    .filter(element => R.nodes.has(element.id)).map(element => element.address)}),
  own: id => { const node = G ? node3d(id) : null; return node ? ownColor(node).toLowerCase() : null; },
  box2d,
  edge2d: join => [...(M.base?.edges.find(edge => edge.join.id === join)?.path?.classList || [])]
    .filter(name => name.startsWith('work-')),
  flow: flowDrawn,
  flowLive: (kind, from, to, edit) => flowLive(kind, from, to, edit),
  // which joins flow, web_flow_mode: read with no name, or changed for the page with one; and the modes offered
  flowMode: name => flowMode(name),
  get flowModes() { return FLOW_MODE_LIST.map(one => ({...one})); },
  reaches, dots3d, labels3d, showLabels3d,
  hover3d: id => { setHovered(node3d(id) || null); readout('3d', hovered ? readoutOf(hovered) : null); },
  figures2d: figures2dDrawn, figures: figuresDrawn, mascot: mascotState,
  // the voice's hooks into the mascot, `MASCOT`: what it says, shown in its bubble, and whether it is speaking now,
  // which makes it talk in its own way; and a feeling or a walk as its system agent asks, as the event stream does
  mascotSaid: text => say(String(text || '').slice(0, 280), Math.min(12, 3 + String(text || '').length / 18)),
  mascotSpeaking: on => { MASCOT.speaking = Boolean(on); wake3d(); },
  mascotEvent: payload => mascotEvent({project: S.project, ...payload}),
  // a body for a conversation agent, `BODIES`: give one, list them, and the characters to choose among
  embody: (workId, glyph) => embody(workId, glyph, 'person'), bodies: () => bodies(), characters: () => characters(),
  // the large 3D view through the mascot's eyes and back, E; the eye anchors and gazes drawn, for a check of look
  mascotEyes: on => mascotEyes(on), eyeDebug: on => { EYE.debug = Boolean(on); wake3d(); return EYE.debug; },
  // the keys the mascot and the flow add, for the page's list of keys
  mascotKeys: [{key: 'E', label: "Mascot's eyes", help: "See the 3D map through the mascot's eyes, and back"},
    {key: 'X', label: 'Scissors', help: 'Cut an edge with a click; the mascot mends it. Escape puts it back'}],
  // the scissors, `CUT`: on or off, and a cut of the join edge between two nodes, as a click on it with them out
  scissors: on => cutMode(on),
  cut: (source, target) => cutLink(G?.graphData().links.find(link =>
    endOf(link.source) === source && endOf(link.target) === target)),
  cutStage: () => CUT.job?.stage || (CUT.saved ? 'restoring' : null),
  // the figure under a point of the screen, as a click there finds it
  figureAt: (x, y) => figureAt(x, y),
  at3d,
  ground: () => G ? G.backgroundColor() : null};

/* Select the node at an Address once the first map is drawn; says whether there is one. */
async function selectAddress(address) {
  await READY.promise;
  const wanted = String(address || '').replace(/^metaform:\/\//, '').split('#')[0];
  const found = [...S.elements.values()].find(entry => entry.element.address === wanted)?.element.id;
  if (found) select(found, true);
  return Boolean(found);
}
/* What the base 2D map draws, by address: its nodes and each edge, from, to and its arrow as Mermaid writes it,
 * P063. */
function drawn2d() {
  if (!M.base) return null;
  const at = id => S.elements.get(id)?.element.address;
  return {nodes: [...M.base.nodes.keys()].map(at), edges: M.base.edges.map(edge =>
    [...ends2d(edge.join, edge.provider).map(at), edge.join.ifd === 'both' ? '<-->' : '-->'])};
}
/* The screen middles of the 3D map's join edges in view, well inside the map's window. */
function links3d() {
  if (!G) return [];
  const box = stageBox();
  const middle = link => {
    const mid = new THREE.Vector3((link.source.x + link.target.x) / 2, (link.source.y + link.target.y) / 2,
      (link.source.z + link.target.z) / 2).project(G.camera());
    return [box.left + (mid.x + 1) / 2 * box.width, box.top + (1 - mid.y) / 2 * box.height];
  };
  const inView = ([x, y]) => x > box.left + 30 && x < box.right - 30 && y > box.top + 60 && y < box.bottom - 30;
  return G.graphData().links.filter(link => link.join && link.source.x !== undefined).map(middle).filter(inView);
}
function memoryDrawn() {
  if (!(MEM.key && MEM.drawn)) return null;
  return {key: MEM.key, nodes: G ? G.graphData().nodes.map(node => node.id) : [],
    links: G ? G.graphData().links.map(link => ({source: endOf(link.source), target: endOf(link.target),
      relation: link.relation})) : [],
    nodes2d: [...M.nodes.keys()]};
}
/* The samples a pixel are set, so a browser check can compare the picture with the smoothing and without it. */
function smooth3d(samples) {
  if (!G) return;
  const chain = G.postProcessingComposer();
  for (const target of [chain.renderTarget1, chain.renderTarget2]) { target.samples = samples; target.dispose(); }
  wake3d();
}
/* The 3D map stops drawing, or draws again, so a browser check that steps the page's clock frame by frame to read
 * the 2D camera does not draw the 3D map at every step. */
function pause3d(on) {
  FRAMES.held = Boolean(on);
  if (!on) { wake3d(); return; }
  cancelAnimationFrame(FRAMES.id);
  FRAMES.id = 0;
}
function zoom3d(share) {
  if (!G) return;
  const at = G.camera().position;
  G.cameraPosition({x: at.x * share, y: at.y * share, z: at.z * share}, undefined, 0);
}
/* The glass on or off, with its options and the spheres' segments, to measure what it costs. */
function glass(on, options = {}, segments = 16) {
  if (!G) return;
  Object.assign(GLASS, options);
  setSegments(segments);
  shapes.clear();
  G.nodeThreeObject(node => nodeObject(node, on));
}
/* A node put where given and held there, the camera pointed, and where a node is on the page with its radius, so a
 * browser check can read a picture of the 3D map at known points. */
function pin3d(id, x, y, z) {
  const node = node3d(id);
  if (node) { Object.assign(node, {x, y, z, fx: x, fy: y, fz: z}); G.d3ReheatSimulation(); }
}
/* The camera put at a view, as a hand would move it there: a meeting is released, as a hand releases it, and a flight
 * under way and the fits that follow the map end, as a hand's start ends them in `steer3d`, so no later refit takes
 * the camera from where it was put. */
function view3d(from, to) {
  if (!G) return;
  FLIGHT.on = false; V3.auto = false; V3.focus = V3.hold = null;
  meetEnds(); G.cameraPosition(from, to, 0);
}
function screen3d(id) {
  const node = node3d(id);
  if (!node || node.x === undefined) return null;
  const point = G.graph2ScreenCoords(node.x, node.y, node.z), camera = G.camera(), box = stageBox();
  const distance = Math.hypot(camera.position.x - node.x, camera.position.y - node.y, camera.position.z - node.z);
  return {x: box.left + point.x, y: box.top + point.y,
    r: Math.cbrt(nodeSize(node)) * 3 / (distance * Math.tan(camera.fov * Math.PI / 360)) * box.height / 2};
}
function waveTimes(times) {
  Object.assign(TIMES, times, {gaussian: times.gaussian === false ? [] : times.gaussian || TIMES.gaussian});
  W.next = W.clock;
  wake3d();
}
function box2d(id) {
  const box = M.nodes.get(id)?.g.getBoundingClientRect();
  return box ? {left: box.left, right: box.right, top: box.top, bottom: box.bottom} : null;
}
/* The dots that travel the joins held still at a share of the way along each link, and where on the page each
 * link's dots are, so a browser check can read a picture of a dot passing through a node.
 * What the flow draws this frame, `FLOW`: the 3D map's points and line ends, the agents' trips under way, and the
 * shapes shown on the 2D map's selected edges; `live` draws one trip as the event stream would, `flowLive`. */
function flowDrawn() {
  const shapes2d = M.svg ? [...M.svg.querySelectorAll('g.flows2d > *')].filter(shape => shape.style.display !== 'none')
    .map(shape => shape.getAttribute('class')) : [];
  return {points: FX.n, lines: FX.m, live: FLOW.live.length, clock: FLOW.clock, shapes2d};
}
/* Each node's reach on the screen, `REACH`, in the 3D map or the 2D one: its centre, its box in 2D, and its reach. */
function reaches(which) {
  if (which === '2d') return (M.svg ? reaches2d() : []).map(one => ({id: one.key, x: one.x, y: one.y, reach: one.reach,
    left: one.box.left, top: one.box.top, right: one.box.right, bottom: one.box.bottom}));
  return (G ? reaches3d() : []).map(one => ({id: one.node.id, x: one.x, y: one.y, r: one.r, reach: one.reach}));
}
function dots3d(along) {
  if (!G) return [];
  FLOW.held = along;
  wake3d();
  const box = stageBox();
  return G.graphData().links.filter(link => link.__photonsObj?.children.length).map(link => {
    const from = link.source, to = link.target;
    const point = G.graph2ScreenCoords(from.x + (to.x - from.x) * along, from.y + (to.y - from.y) * along,
      from.z + (to.z - from.z) * along);
    return {source: from.id, target: to.id, x: box.left + point.x, y: box.top + point.y};
  });
}
/* Each label of the 3D map: its text and lines, where it is on the page, its rank by depth, higher nearer, whether it
 * is under a nearer node or label, its color and its opacity, and whether it is in the scene and drawn with the depth
 * test, which orders it with the nodes nearer than it, and whether it writes depth, VIEW-038. */
function labels3d() {
  const area = stageBox();
  return [...tags.values()].map(tag => ({id: tag.id, text: tag.text, lines: tag.lines, hidden: tag.hidden, z: tag.z,
    under: tag.under, color: tag.color.toLowerCase(), opacity: tag.sprite.material.opacity,
    scene: tag.sprite.parent?.parent === G.scene(), depthTest: tag.sprite.material.depthTest,
    depthWrite: tag.sprite.material.depthWrite, left: area.left + (tag.rect?.left ?? 0),
    right: area.left + (tag.rect?.right ?? 0), top: area.top + (tag.rect?.top ?? 0),
    bottom: area.top + (tag.rect?.bottom ?? 0)}));
}
/* `only`, a list of node ids, shows those labels alone, so a picture of one label is not changed by another's. */
function showLabels3d(on, only = null) {
  LABELS.on = Boolean(on);
  LABELS.only = only ? new Set(only) : null;
  if (LABELS.group) LABELS.group.visible = LABELS.on;
  wake3d();
}
function figures2dDrawn() {
  return [...ROAM2D.figures.values()].map(figure => ({work_id: figure.id, glyph: figure.glyph, stage: figure.stage,
    target: figure.target, home: figure.home, x: figure.x, y: figure.y, size: figure.size, angle: figure.angle,
    shown: Boolean(figure.g.isConnected && M.svg && M.svg.contains(figure.g)),
    icon: figure.g.querySelector('image').getAttribute('href')}));
}
function figuresDrawn() {
  return [...ROAM.figures.values()].map(figure => ({work_id: figure.id, glyph: figure.glyph, stage: figure.stage,
    target: figure.target, home: figure.home, x: figure.mesh.position.x, y: figure.mesh.position.y,
    z: figure.mesh.position.z, scale: figure.mesh.scale.x, angle: figure.angle, clock: figure.clock,
    px: onScreen(figure.mesh), focused: ROAM.focus === figure.id, mood: figure.mood, act: figure.act?.kind || null,
    lane: figure.lane}));
}
/* The person's mascot, `MASCOT`: its character, where it is in 3D and on the screen, and in 2D. */
function mascotState() {
  return {glyph: mascotGlyph(), shown: Boolean(MASCOT.mesh), sleeping: MASCOT.sleeping,
    driven: mascotDriven(), held: MASCOT.held?.reason ?? null, job: MASCOT.job?.kind || null,
    holding: MASCOT.holding?.id || null, x: MASCOT.pos.x, y: MASCOT.pos.y, z: MASCOT.pos.z,
    px: MASCOT.mesh ? onScreen(MASCOT.mesh) : 0,
    shown2d: Boolean(MASCOT2D.g?.isConnected), x2d: MASCOT2D.x, y2d: MASCOT2D.y, ...mascotScreen(),
    bubble: BUBBLE.el?.classList.contains('on') ? BUBBLE.el.textContent : null,
    cards: [...document.querySelectorAll('.mascot-card')].map(card => card.textContent), told: [...ATTN.seen]};
}
function at3d(id) {
  const node = G ? node3d(id) : null;
  return node && node.x !== undefined ? {x: node.x, y: node.y, z: node.z, r: Math.cbrt(nodeSize(node)) * 3} : null;
}

/* How a node is drawn for its condition, MAP-046, readable by a browser check: its open work, the 2D group's work
 * classes, computed opacity and whether its box is animating, and the 3D sphere's material opacity and whether it is
 * red at this frame. */
const BOX = new THREE.Box3();
export function onScreen(mesh) {  // how many pixels a figure spans in the 3D view, across or up, VIEW-035
  BOX.setFromObject(mesh);
  const xs = [], ys = [];
  const corners = [];
  for (const x of [BOX.min.x, BOX.max.x]) for (const y of [BOX.min.y, BOX.max.y]) corners.push([x, y]);
  for (const [x, y] of corners) for (const z of [BOX.min.z, BOX.max.z]) {
    const point = G.graph2ScreenCoords(x, y, z);
    xs.push(point.x); ys.push(point.y);
  }
  return Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
}
function toHex(color) {
  const found = (color || '').match(/\d+/g);
  return found ? '#' + found.slice(0, 3).map(part => Number(part).toString(16).padStart(2, '0')).join('') : null;
}
function look(id) {
  const node = G ? node3d(id) : null;
  const group = (M.base?.nodes.get(id) || M.nodes.get(id))?.g || null;
  const box = group?.querySelector('rect') || null;
  const material = node?.__threeObj?.material || null;
  return {...look2d(group, box), ...look3d(node, material, id),
    reach3d: R.nodes.has(id), reach2d: Boolean(group?.classList.contains('reach')),
    label3d: (tags.get(id)?.classes || []).filter(name => name.startsWith('work-')),
    // how strong its name is drawn for its ghost, 1 at full, and the name's opacity as drawn, VIEW-027
    sign3d: tags.get(id)?.ghost ?? null, signOpacity3d: tags.get(id)?.sprite.material.opacity ?? null};
}
/* A node's condition in the 2D map: its group's work classes, opacity, animation, glow and stroke. */
function look2d(group, box) {
  const moving = part => getComputedStyle(part).animationName !== 'none';
  const animated = box ? moving(box) || moving(group) : false;
  const marked = ['broken', 'trouble', 'question', 'message'].some(name => group?.classList.contains('work-' + name));
  return {classes: group ? [...group.classList].filter(name => name.startsWith('work-')) : [],
    opacity2d: group ? Number(getComputedStyle(group).opacity) : null,
    animated2d: animated,
    glow2d: Boolean(box) && marked && [group, box].some(part => getComputedStyle(part).filter.includes('drop-shadow')),
    bloom2d: Boolean(box && getComputedStyle(group).filter.includes('drop-shadow')),
    stroke2d: box ? toHex(getComputedStyle(box).stroke) : null};
}
/* A node's condition in the 3D map: its work, its material, its light and glass, its shape and what is around it. */
function look3d(node, material, id) {
  return {work: node?.work || [],
    opacity3d: material ? material.opacity : null,
    light3d: material ? material.emissiveIntensity ?? null : null,
    ghost: Boolean(node?.__threeObj?.userData.ghost), pace: node ? paceOf(node) : null,  // a part not built, VIEW-027
    red3d: material ? '#' + material.color.getHexString() === css('--broken').toLowerCase() : false,
    material: !material ? null
      : material instanceof MeshTransmissionMaterial ? 'MeshTransmissionMaterial' : material.type,
    // the light the glass lets through: drei's own amount, since three.js's `transmission` stays 0
    transmission: material ? (material._transmission ?? material.transmission) || 0 : 0,
    chromatic: material?.chromaticAberration ?? 0, distortion: material?.distortion ?? 0,
    // the near wall reads the picture that holds the far walls, and its far wall is drawn into it
    backside: Boolean(material?.userData.back && BEHIND.main && material.buffer === BEHIND.main.texture
      && material.userData.back.side === THREE.BackSide),
    shape: node?.__threeObj?.geometry ? node.__threeObj.geometry.uuid : null,
    // what is drawn around the node besides the node itself
    around3d: node?.__threeObj ? node.__threeObj.children.length : null,
    color3d: material ? '#' + material.color.getHexString() : null};
}
