/* The memory graph, LAYER-013: the memories at a node, its memory network in both views, and the panel's memories. */
import '/page/app/map2d/inside.js';  // the part before runs first, so the parts run in the page's order
import {$, reduced, h, fill} from '/page/app/core/dom.js';
import {S, MEM, read, viewLayers} from '/page/app/core/reads.js';
import {colorVar} from '/page/app/header/layers.js';
import {joinOf, nodeIn} from '/page/app/graph/data.js';
import {G, nodeSize} from '/page/app/map3d/graph3d.js';
import {draw3D} from '/page/app/map3d/draw3d.js';
import {V3, away3d} from '/page/app/camera/flight.js';
import {meetEnds} from '/page/app/camera/fly3d.js';
import {renderLegend} from '/page/app/views/lens.js';
import {M} from '/page/app/map2d/build.js';
import {mountSvg, placeIn, boundsOf, showBase} from '/page/app/map2d/fit.js';
import {IN, insideGen, nextInsideGen, label2d, labelOf, nameOf, drawInside,
  renderCrumbs} from '/page/app/map2d/inside.js';
import {renderEntity} from '/page/app/memory/manage.js';
import {fade, into, stopCam, moveCam, aim2d} from '/page/app/map2d/camera.js';
import {markNodes} from '/page/app/map2d/flow2d.js';
import {select} from '/page/app/selection/select.js';

/* ---------- the memory graph, LAYER-013: a graph of its own, tied to the map's nodes by joins of type memory
 * ---------- Read whole from the memory module's `graph`, each join saying whether its memory shows at its node in the
 * layers in view, VIEW-031. A memory is drawn as `e:<name>`, at each node it shows at; a join the map no longer holds
 * is orphaned and listed in the orphaned menu. */
const emptyMemory = () => ({entities: new Map(), relations: [], joins: [], at: new Map(), orphaned: 0});
export const memoryLayer = () => S.layers.find(layer => layer.kind === 'memory')?.name || 'memory';
export const memoryKey = name => 'e:' + name;
export const memoryName = key => key.slice(2);
/* The node of the map a memory join names: an element by its address, and a map join by its receiver's address and the
 * address of an element it holds, STORE-020. */
function nodeAt(join) {
  const addressOf = id => S.elements.get(id)?.element.address;
  if (join.address !== undefined) {
    const found = [...S.elements.values()].find(entry => entry.element.address === join.address);
    return found ? found.element.id : null;
  }
  const parent = S.joins.find(one => addressOf(one.receiver) === join.receiver
    && (one.elements || []).some(each => each.address === join.provider));
  return parent ? 'p:' + parent.id : null;
}
export async function memoryOf() {
  let whole;
  try { whole = await read('memory-graph', viewLayers()); } catch (error) { return emptyMemory(); }
  const joins = whole.joins.map(join => ({...join, key: join.orphaned ? null : nodeAt(join)}));
  return {entities: new Map(whole.entities.map(entity => [entity.name, entity])), relations: whole.relations, joins,
    at: memoriesByNode(joins), orphaned: joins.filter(join => join.orphaned).length};
}
/* The memories shown at each node, by its key, each once. */
function memoriesByNode(joins) {
  const at = new Map();
  for (const join of joins) {
    if (!join.shows || !join.key) continue;
    if (!at.has(join.key)) at.set(join.key, []);
    if (!at.get(join.key).includes(join.entity)) at.get(join.key).push(join.entity);
  }
  return at;
}
/* The memories shown at a node, and a memory as the panel and the inside of a node take it. */
export const memoriesAt = key => S.memory.at.get(key) || [];
export function memoryThing(key) {
  if (!key?.startsWith('e:') || !S.memory.entities.has(memoryName(key))) return null;
  const name = memoryName(key);
  return {kind: 'memory', key, name, value: name, layer: memoryLayer(), layerKind: 'memory'};
}
/* The memory network of a node, VIEW-031: the memories kept at it, the memories their relations name, and every
 * relation between those; a relation one of them holds to a memory outside them is not drawn. */
export function networkOf(key) {
  const own = memoriesAt(key), names = new Set(own);
  for (const relation of S.memory.relations) if (own.includes(relation.from) || own.includes(relation.to)) {
    names.add(relation.from); names.add(relation.to);
  }
  const relations = S.memory.relations.filter(relation => names.has(relation.from) && names.has(relation.to))
    .map(relation => ({from: memoryKey(relation.from), to: memoryKey(relation.to), type: relation.relationType}));
  return {key, own, entities: [key, ...[...names].map(memoryKey)], relations};
}
/* The node is drawn as the map draws it: an element as its glass and a join as its purpose; each memory as a memory is
 * drawn in the map. */
function entityNode(key) {
  if (key.startsWith('e:')) return {id: key, t: 'item', layer: memoryLayer(), text: memoryName(key), work: []};
  const element = S.elements.get(key)?.element;
  if (element) return {id: key, t: 'el', name: labelOf(element), address: element.address,
    role: element.role, work: element.open_work || [], layer: element.layer};
  const join = joinOf(key);
  if (join) return {id: key, t: 'purpose', join: join.id, layer: join.layer, work: join.open_work || []};
  return {id: key, t: 'el', name: key, address: key, work: []};  // a node the layers in view do not draw
}
export function memoryData() {
  const network = MEM.network = networkOf(MEM.key), layer = memoryLayer();
  return {nodes: network.entities.map(entityNode), links: [
    ...network.own.map(name => ({source: network.key, target: memoryKey(name), k: 'item', layer, relation: null})),
    ...network.relations.map(relation => ({source: relation.from, target: relation.to, k: 'relation', layer,
      relation: relation.type}))]};
}
/* The view zooms into the node as the map gives way to it: each camera goes up to the node while its view fades
 * toward the background. With reduced motion the views change at once. */
function into3d(key) {
  if (!G || reduced()) return Promise.resolve();
  const node = nodeIn(G.graphData(), key);
  if (node && node.x !== undefined) {
    // the camera leaves a sign it met, whose name is drawn over the map only while it is met square on
    meetEnds();
    const eye = G.camera().position, away = Math.hypot(eye.x - node.x, eye.y - node.y, eye.z - node.z) || 1;
    // near enough that the node fills the view
    const share = Math.min(1, Math.cbrt(nodeSize(node)) * 3 * 2.5 / away);
    G.cameraPosition({x: node.x + (eye.x - node.x) * share, y: node.y + (eye.y - node.y) * share,
      z: node.z + (eye.z - node.z) * share}, {x: node.x, y: node.y, z: node.z}, 480);
  }
  return shown3d(0);
}
function into2d(key) {
  if (!M.svg || reduced()) return Promise.resolve();
  const node = M.nodes.get(key);
  if (node) moveCam(into(node));
  return fade(M.svg, 0);
}
const shown3d = to => fade($('#stage'), to);  // the labels are drawn in the 3D view, VIEW-038
/* The whole memory network in the 3D view, once the graph has taken its nodes. */
async function whole3d() {
  if (!G) return;
  for (let frames = 0; frames < 2; frames++) await nextFrame();
  G.zoomToFit(0, 60);
  V3.whole = away3d();
}
const nextFrame = () => new Promise(resolve => requestAnimationFrame(resolve));
/* Open the memory network of a node in both views. From the map, what the map was is kept to go back to: the levels
 * entered in 2D and where each node of the 3D map stood. From a memory network, the network of another of its nodes
 * takes its place. */
export async function memories(key) {
  if (!key) return;
  const generation = ++MEM.generation;
  if (!MEM.key) {
    if (!IN.length && M.base) M.base.cam = {...M.cam};
    MEM.levels = IN.splice(0);
    MEM.positions = G ? new Map(G.graphData().nodes.map(node => [node.id, node])) : null;
  }
  await Promise.all([into2d(key), into3d(key)]);
  if (generation !== MEM.generation) return;
  Object.assign(MEM, {key, drawn: false, network: networkOf(key)});
  draw3D();
  renderLegend();
  await drawMemory2d(true);
  if (generation !== MEM.generation) return;
  MEM.drawn = true;
  select(key, false, true);
  // it opens framed by the mode, VIEW-041
  if (M.bounds && M.drawn === MEM) { stopCam(); aim2d(M.nodes.get(key), true); }
  await whole3d();
  if (generation !== MEM.generation) return;
  renderCrumbs();
  if (!reduced()) { if (M.drawn === MEM) fade(M.svg, 1); shown3d(1); }
}
/* Going back returns to the map: to the level of the 2D map the network was opened from, or to `depth` of it, with
 * each node of the 3D map where it stood, and the node the network belongs to selected. */
export async function leaveMemories(depth = null) {
  if (!MEM.key) return;
  const key = MEM.key, generation = ++MEM.generation;
  const levels = MEM.levels.slice(0, depth ?? MEM.levels.length);
  if (!reduced()) await Promise.all([M.svg ? fade(M.svg, 0) : null, shown3d(0)]);
  if (generation !== MEM.generation) return;
  const positions = MEM.positions;
  Object.assign(MEM, {key: null, network: null, drawn: false, levels: [], positions: null});
  draw3D(positions);
  renderLegend();
  IN.push(...levels);
  if (IN.length) await drawInside(true); else showBase(key);
  select(key, true, true);
  if (!reduced()) shown3d(1);
}
/* Another metaform or project is shown: its map, at once. */
export function dropMemories() {
  MEM.generation++;
  Object.assign(MEM, {key: null, network: null, drawn: false, levels: [], positions: null});
  Object.assign($('#stage').style, {transition: '', opacity: ''});
}
/* The memory network in 2D: the node, each memory by its name, a dotted line from the node to each memory kept at it,
 * and each relation a line in memory's color from the memory that holds it to the memory it names, with its relation
 * type on it. `hidden` puts it in place unseen, to fade in with the 3D view. */
export async function drawMemory2d(hidden = false) {
  const network = MEM.network = networkOf(MEM.key);
  const generation = nextInsideGen();  // a render still running for a level left is dropped
  const vertical = M.base ? M.base.vertical : true;
  const ids = new Map(network.entities.map((key, index) => [key, `v${index}`]));
  const lines = memoryLines(network, ids, vertical);
  let result;
  try { result = await window.mermaid.render(`memory${generation}`, lines.join('\n'), $('#draw')); }
  catch (error) {
    fill($('#viewport'), h('p', {class: 'empty', style: {padding: '16px'}}, 'These memories could not be drawn.'));
    return;
  }
  if (generation !== insideGen || !MEM.key) return;
  const svg = mountSvg(result, $('#viewport'), false);
  if (hidden && !reduced()) Object.assign(svg.style, {transition: '', opacity: '0'});
  const nodes = memoryNodes(svg, ids, network);
  network.relations.forEach((relation, index) => {
    svg.querySelector(`path[data-id="e${index}"]`)?.classList.add('relation');
  });
  stopCam();  // a camera still easing on the view left must not move this one
  Object.assign(M, {svg, nodes, edges: [], bounds: boundsOf(svg), vertical, drawn: MEM});
  aim2d(nodes.get(MEM.key), true);
  $('#map2d').classList.add('focused');
  markNodes(nodes, S.selected);
  renderCrumbs();
}
const memoryLabel = key => key.startsWith('e:') ? memoryName(key) : nameOf(key);
/* The network as Mermaid reads it: the node and each memory by its name, a dotted line from the node to each memory
 * kept at it, and each relation with its type on it. */
function memoryLines(network, ids, vertical) {
  const kind = key => key === network.key ? 'center' : 'entity';
  return [vertical ? 'flowchart TB' : 'flowchart LR',
    ...network.entities.map(key => `${ids.get(key)}["${label2d(memoryLabel(key))}"]:::${kind(key)}`),
    ...network.own.map(name => `${ids.get(network.key)} -.- ${ids.get(memoryKey(name))}`),
    ...network.relations.map((relation, index) =>
      `${ids.get(relation.from)} e${index}@-->|"${label2d(relation.type)}"| ${ids.get(relation.to)}`),
    ...['center', 'entity'].map(kind => `classDef ${kind} font-size:11px`)];
}
/* Each node of the network drawn, by its key, titled by its address or its name. */
function memoryNodes(svg, ids, network) {
  const nodes = new Map();
  for (const [key, id] of ids) {
    const group = svg.querySelector(`[id*="-flowchart-${id}-"]`);
    if (!group) continue;
    placeIn(nodes, key, group, S.elements.get(key)?.element.address || memoryLabel(key), entityNode(key).work);
    group.classList.add(key === network.key ? 'in-center' : 'in-entity');
  }
  return nodes;
}
/* In a memory network the panel shows the node with the memories kept at it, each with its observations and its
 * relations, or the memory selected, as the memory module reads them, VIEW-009 and STORE-020. */
export function renderMemories(id) {
  if (id.startsWith('e:')) return renderEntity(memoryName(id));
  const own = memoriesAt(id), kept = {class: 'item', style: {'--c': `var(${colorVar(memoryLayer())})`}};
  fill($('#p-object'),
    h('div', {class: 'eyebrow'}, 'Memories'),
    h('h2', {}, nameOf(id)),
    S.elements.has(id) ? h('div', {class: 'addr'}, S.elements.get(id).element.address) : null,
    own.length ? own.map(name => memoryRow(name, kept))
      : h('p', {class: 'empty'}, 'No memories are kept here in the layers in view.'));
}
/* One memory kept at the node: its name, which selects it, its type, its observations and its relations. */
function memoryRow(name, kept) {
  const entity = S.memory.entities.get(name);
  const related = S.memory.relations.filter(relation => relation.from === name || relation.to === name);
  const go = event => { event.preventDefault(); select(memoryKey(name), true); };
  return h('div', kept, h('a', {class: 'link', href: '#', onclick: go}, name),
    entity ? h('small', {}, ` · ${entity.entityType}`) : null,
    (entity?.observations || []).map(one => h('p', {class: 'itemtext'}, one.content)),
    related.map(relation => h('p', {class: 'meta'}, `${relation.from} ${relation.relationType} ${relation.to}`)));
}
