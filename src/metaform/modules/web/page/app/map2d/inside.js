/* Inside a node, VIEW-016: the 2D map replaced by the node's own graph, its crumbs, entering and leaving, and the
 * panel's thing. */
import '/page/app/map2d/fit.js';  // the part before runs first, so the parts run in the page's order
import {$, reduced, h, fill} from '/page/app/core/dom.js';
import {toast} from '/page/app/core/controls.js';
import {S, MEM, read, reach, viewLayers} from '/page/app/core/reads.js';
import {colorVar} from '/page/app/header/layers.js';
import {joinOf} from '/page/app/graph/data.js';
import {M, plain2d} from '/page/app/map2d/build.js';
import {mountSvg, placeIn, boundsOf, showBase} from '/page/app/map2d/fit.js';
import {memoryLayer, memoryKey, memoryName, memoriesAt, memoryThing, leaveMemories} from '/page/app/memory/graph.js';
import {renderEntity} from '/page/app/memory/manage.js';
import {fade, arrive, into, stopCam, moveCam, aim2d} from '/page/app/map2d/camera.js';
import {flowArrow, focus2D} from '/page/app/map2d/flow2d.js';
import {select, refsOf} from '/page/app/selection/select.js';
import {layerPill, itemText, itemView} from '/page/app/panel/object.js';

/* ---------- inside a node: the 2D map is replaced by the node's own graph, VIEW-016 ----------
 * Every node can be entered. Inside are the node, what it holds, one group for each layer turned on with what that
 * layer attaches to the node, and the nodes those items link to, which can be entered in turn. */
export const IN = [];  // the levels entered from the base map: {key, label, more, things}
const GROUP = 20;
const PURPOSE2D = 64;  // a join's purpose in its box inside a node, VIEW-016: about three lines as Mermaid wraps it
export let insideGen = 0;
export const nextInsideGen = () => ++insideGen;
const kindOf = key => key.startsWith('p:') ? 'join' : 'element';
const bareId = key => key.replace(/^p:/, '');
export const keyOf = node => !node ? null : node.kind === 'join' ? 'p:' + node.id
  : node.kind === 'element' ? node.id : null;
export const label2d = (text, most = 30) => plain2d(String(text ?? '').replace(/\s+/g, ' '), most) || '·';
export const samePath = (a, b) => a.length === b.length && a.every((level, index) => level.key === b[index].key);
/* An element is labeled with its name, the project's name for it, or else its short namespace name, its address read
 * through name_length, MAP-012. A join has no name of its own, since a name belongs to the element it holds; its box
 * shows its purpose, the operative purpose it records, so a drill-in never draws a blank box. */
export const labelOf = element => element.name || element.short_name || element.address;
const joinLabel = join => join?.purpose || '';
// A join's title, its receiver and the parts that serve it, as the 3D map shows it on a selected join, VIEW-038.
export function joinTitle(node) {
  const join = S.joins.find(item => item.id === node.join);
  return join ? `${nameOf(join.receiver)} ${flowArrow(join)} ${join.providers.map(id => nameOf(id)).join(', ')}` : '';
}
export function nameOf(key, fallback = key) {
  if (key.startsWith('p:')) { const found = joinOf(key); return found ? joinLabel(found) : fallback; }
  const found = S.elements.get(key)?.element;
  return found ? labelOf(found) : fallback;
}
export async function drawInside(arriving = false) {
  const level = IN.at(-1);
  if (!level) return showBase();
  const generation = ++insideGen;
  const target = `${kindOf(level.key)}:${bareId(level.key)}`;
  let view = null, incoming = [];
  try {
    view = await read('node', {target, ...viewLayers()});
    incoming = (await read('links-to', {target, limit: 0, ...viewLayers()})).results || [];
  } catch (error) { if (error.status !== 404) toast(error.message); }
  if (generation !== insideGen) return;
  const vertical = M.base ? M.base.vertical : true;  // the whole map's orientation, so going inside never turns it
  const graph = insideGraph(vertical);
  const key = level.key, center = graph.add(key, level.label, 'center');
  insideJoins(graph, key, center);
  const linked = insideLayers(graph, view, level, center);
  for (const thing of linked) {
    const to = keyOf(thing.item.link);
    if (!to) continue;
    const from = graph.ids.get(thing.key);
    graph.edges.push(`${from} --> ${graph.add(to, nameOf(to, thing.item.link.id), 'stub')}`);
  }
  insideMemories(graph, key, center);
  insideIncoming(graph, incoming, center);
  const {lines, edges, ids, things, groups} = graph;
  lines.push(...edges, ...['center', 'item', 'stub', 'more', 'purpose'].map(kind => `classDef ${kind} font-size:11px`));
  let result;
  try { result = await window.mermaid.render(`inside${generation}`, lines.join('\n'), $('#draw')); }
  catch (error) {
    fill($('#viewport'), h('p', {class: 'empty', style: {padding: '16px'}}, 'This node could not be drawn.'));
    return;
  }
  if (generation !== insideGen || IN.at(-1) !== level) return;
  const svg = mountSvg(result, $('#viewport'), false);
  if (arriving) arrive(svg);  // the node's own graph fades in, VIEW-016
  const nodes = insideNodes(svg, ids, things);
  markGroups(svg, groups);
  level.things = things;
  stopCam();  // a camera still easing on the level left must not move this one
  Object.assign(M, {svg, nodes, edges: [], bounds: boundsOf(svg), vertical, drawn: level});
  aim2d(nodes.get(level.key), true);  // the node's own graph fades in, in full fit, VIEW-016 and VIEW-041
  renderCrumbs();
  if (S.selected && nodes.has(S.selected)) focus2D(S.selected, false);  // it opens in full fit, VIEW-041
}
/* The text of a node's own graph as it is built: its lines and edges, each thing drawn by its key with the Mermaid id
 * it takes, and the groups by their ids; `add` draws a thing once and gives its id. */
function insideGraph(vertical) {
  const graph = {lines: [vertical ? 'flowchart TB' : 'flowchart LR'], edges: [], ids: new Map(), things: new Map(),
    groups: new Map()};
  graph.add = (key, label, kind, thing = null) => {
    if (graph.ids.has(key)) return graph.ids.get(key);
    const id = `v${graph.ids.size}`;
    graph.ids.set(key, id);
    graph.things.set(key, thing || {kind, key, label});
    graph.lines.push(`${id}["${label2d(label, kind === 'purpose' ? PURPOSE2D : 30)}"]:::${kind}`);
    return id;
  };
  return graph;
}
/* A join's receiver and the elements serving it; or each join an element receives, as its purpose, with the elements
 * that serve it drawn under it. */
function insideJoins({add, edges}, key, center) {
  if (key.startsWith('p:')) {
    const join = joinOf(key);
    if (!join) return;
    edges.push(`${add(join.receiver, nameOf(join.receiver), 'stub')} --> ${center}`);
    for (const provider of join.providers) edges.push(`${center} --> ${add(provider, nameOf(provider), 'stub')}`);
    return;
  }
  for (const join of S.joins.filter(item => item.receiver === key)) {
    const purpose = add('p:' + join.id, joinLabel(join), 'purpose');
    edges.push(`${center} --> ${purpose}`);
    for (const provider of join.providers) edges.push(`${purpose} --> ${add(provider, nameOf(provider), 'stub')}`);
  }
}
/* One group for each layer turned on, with the items and properties it attaches to the node, GROUP at a time and the
 * rest as "more"; the things that link elsewhere are given back, to draw their links. */
function insideLayers({add, lines, edges, groups}, view, level, center) {
  const linked = [];
  for (const found of view?.layers || []) {
    const all = [...(found.items || []).map(item => ({kind: 'item', key: 'i:' + item.id, item})),
      ...(found.properties || []).map(item => ({kind: 'property', key: 'r:' + item.id, item}))]
      .map(thing => ({...thing, value: thing.item.value, layer: found.layer, layerKind: found.kind}));
    if (!all.length) continue;
    const shown = level.more[found.layer] || GROUP, gid = `g${groups.size}`;
    groups.set(gid, found.layer);
    lines.push(`subgraph ${gid} ["${label2d(found.kind === 'memory' ? 'memory' : found.layer)}"]`, 'direction TB');
    for (const thing of all.slice(0, shown)) {
      add(thing.key, itemText(thing.value) + (thing.item.state ? ` · ${thing.item.state}` : ''), 'item', thing);
      if (thing.item.link) linked.push(thing);
    }
    if (all.length > shown) add(`m:${found.layer}`, `${all.length - shown} more`, 'more');
    lines.push('end');
    edges.push(`${center} --- ${gid}`);
  }
  return linked;
}
/* The memories kept at the node, in memory's group; each relation of theirs runs to the memory it names, and a
 * memory kept elsewhere leads on to the nodes it is kept at, LAYER-013. */
function insideMemories(graph, key, center) {
  const {add, lines, edges, groups, ids} = graph;
  const kept = [...new Set(memoriesAt(key))];
  if (!kept.length) return;
  const gid = `g${groups.size}`;
  groups.set(gid, memoryLayer());
  lines.push(`subgraph ${gid} ["memory"]`, 'direction TB');
  for (const name of kept) add(memoryKey(name), name, 'item', memoryThing(memoryKey(name)));
  lines.push('end');
  edges.push(`${center} --- ${gid}`);
  const there = name => [...S.memory.at].filter(([, names]) => names.includes(name)).map(([at]) => at);
  for (const relation of S.memory.relations) {
    if (!kept.includes(relation.from) && !kept.includes(relation.to)) continue;
    for (const name of [relation.from, relation.to]) if (!ids.has(memoryKey(name))) {
      add(memoryKey(name), name, 'item', memoryThing(memoryKey(name)));
      for (const at of there(name)) {
        if (at !== key) edges.push(`${ids.get(memoryKey(name))} --> ${add(at, nameOf(at), 'stub')}`);
      }
    }
    const kind = label2d(relation.relationType);
    edges.push(`${ids.get(memoryKey(relation.from))} -->|"${kind}"| ${ids.get(memoryKey(relation.to))}`);
  }
}
/* The items of other nodes that link here, in a group of their own, each from the node it is attached to. */
function insideIncoming({add, lines, edges, groups, ids}, incoming, center) {
  const coming = incoming.filter(item => !ids.has('i:' + item.id));
  if (!coming.length) return;
  const gid = `g${groups.size}`;
  groups.set(gid, null);
  lines.push(`subgraph ${gid} ["linked here"]`, 'direction TB');
  for (const item of coming) add('i:' + item.id, itemText(item.value), 'item', {kind: 'item', key: 'i:' + item.id,
    item, value: item.value, layer: item.layer, layerKind: S.layers.find(layer => layer.name === item.layer)?.kind});
  lines.push('end');
  for (const item of coming) {
    const from = keyOf(item.target);
    if (from) edges.push(`${add(from, nameOf(from, item.target.id), 'stub')} --> ${ids.get('i:' + item.id)}`);
  }
  edges.push(`${gid} --> ${center}`);
}
/* Each thing's drawn group, by its key, its hovertext its name in full. */
function insideNodes(svg, ids, things) {
  const nodes = new Map();
  for (const [thingKey, id] of ids) {
    const group = svg.querySelector(`[id*="-flowchart-${id}-"]`), thing = things.get(thingKey);
    if (!group) continue;
    const title = thing.value !== undefined ? itemText(thing.value) : thing.label;
    placeIn(nodes, thingKey, group, title, null, nameOf(thingKey, title));
    group.classList.add(`in-${thing.kind}`);
  }
  return nodes;
}
/* Each layer's group drawn in its layer's color. */
function markGroups(svg, groups) {
  for (const [gid, layer] of groups) {
    const cluster = svg.querySelector(`g.cluster[id="${gid}"], g.cluster[id$="-${gid}"]`);
    if (!cluster) continue;
    cluster.classList.add('layergroup');
    if (layer) cluster.style.setProperty('--c', `var(${colorVar(layer)})`);
  }
}
export function renderCrumbs() {
  const bar = $('#crumbs');
  bar.hidden = !IN.length && !MEM.key;
  const crumb = go => (depth, text) =>
    h('a', {href: '#', onclick: event => { event.preventDefault(); go(depth); }}, text);
  const sep = () => h('span', {class: 'sep'}, ' › ');
  if (MEM.key) {  // a memory network, VIEW-031: each part goes back to the map, at that level of it
    const back = crumb(leaveMemories);
    return fill(bar, back(0, 'map'), MEM.levels.map((level, index) => [sep(), back(index + 1, level.label)]),
      sep(), h('b', {}, `memories of ${nameOf(MEM.key)}`));
  }
  const to = crumb(goTo);
  fill(bar, ...(IN.length ? [to(0, 'map'), ...IN.flatMap((level, index) => [sep(),
    index === IN.length - 1 ? h('b', {}, level.label) : to(index + 1, level.label)])] : []));
}
/* Enter a node, or the node an item links to; a group's "more" node shows the next ones. */
export async function enter(key) {
  const level = IN.at(-1), thing = level?.things?.get(key);
  if (key.startsWith('m:')) {
    level.more[key.slice(2)] = (level.more[key.slice(2)] || GROUP) + GROUP;
    return drawInside();
  }
  if (key.startsWith('e:')) {  // a memory has no inside; Enter goes to the node it is kept at, as an item's link does
    const at = [...S.memory.at].find(([, names]) => names.includes(memoryName(key)))?.[0];
    return at && at !== level?.key ? enter(at) : undefined;
  }
  if (thing && (thing.kind === 'item' || thing.kind === 'property')) {
    const to = keyOf(thing.item.link);
    if (!to) return;
    return enter(to);
  }
  if (level?.key === key) return;
  if (!IN.length && M.base) M.base.cam = {...M.cam};
  const node = M.nodes.get(key);
  if (M.svg && node && !reduced()) {  // the camera dives into the node as the view it is on fades, VIEW-016
    moveCam(into(node), {length: 0.48, dive: true});
    await fade(M.svg, 0);
  }
  IN.push({key, label: nameOf(key, thing?.label || key), more: {}, things: new Map()});
  await drawInside(true);
  select(key, false, true);
}
/* Up to a level: 0 is the base map. The node left is selected where it shows. */
export async function goTo(depth) {
  if (depth >= IN.length) return;
  const left = IN[depth].key, here = M.drawn === IN.at(-1) ? M.nodes.get(IN.at(-1).key) : null;
  if (M.svg && !reduced()) {  // the node's graph gathers onto the node and fades as it is left, VIEW-016
    if (here) moveCam(into(here), {length: 0.48});
    await fade(M.svg, 0);
  }
  IN.length = depth;
  if (depth) await drawInside(true); else showBase(left);
  select(left, true, true);
}
/* An element's array of open records in one overlay, the node the map hangs off it (the person, 2026-11-17: "those
 * arrays should read as a node, and you should be able to mark them complete so they don't pollute other agents'
 * contexts"). Each open record with Mark complete; a completed one leaves every read but by its id or a search. */
async function renderArray(thing) {
  const pane = $('#p-object'), {element, overlay} = thing.item.array;
  fill(pane, h('div', {class: 'eyebrow'}, 'Records'), h('div', {class: 'pills'}, layerPill(overlay)),
    h('p', {class: 'meta'}, 'Reading…'));
  let found;
  try {
    found = (await read('layer-items', {layer: overlay, element})).results;
  } catch (error) { toast(error.message); return; }
  if (S.selected !== thing.key) return;  // the person has moved on
  const complete = async (record, row) => {
    row.querySelector('button').disabled = true;
    const response = await reach('/api/record-complete', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({project: S.project, base: S.base, element, overlay, position: record.position,
        record: record.record, revision: record.revision})}, 0).catch(error => ({ok: false, json: async () => ({error: error.message})}));
    const body = await response.json().catch(() => ({}));
    if (!response.ok) { toast(body.error || 'It was not completed.'); row.querySelector('button').disabled = false; return; }
    toast('Completed: it leaves every read, and is found again by its id or a search.');
    renderArray(thing);  // the open records again: positions close up once one leaves
  };
  const rows = found.map(record => {
    const fields = Object.fromEntries(Object.entries(record).filter(([key]) =>
      !['record', 'revision', 'position', 'completed'].includes(key)));
    const row = h('div', {class: 'array-record'}, h('div', {class: 'itemtext'}, itemView(fields)));
    row.append(h('button', {class: 'btn small', title: 'It leaves every read, found again by its id or a search',
      onclick: () => complete(record, row)}, 'Mark complete'));
    return row;
  });
  fill(pane, h('div', {class: 'eyebrow'}, 'Records'), h('div', {class: 'pills'}, layerPill(overlay)),
    h('p', {class: 'meta'}, `${found.length} open at ${element || 'the project'}`), ...rows);
}

export function renderThing(thing) {
  const pane = $('#p-object');
  if (thing.kind === 'memory') return renderEntity(thing.name);
  if (thing.kind === 'item' && thing.item.array) return renderArray(thing);
  if (thing.kind === 'item' || thing.kind === 'property') {
    const link = keyOf(thing.item.link);
    const go = event => { event.preventDefault(); enter(link); };
    fill(pane,
      h('div', {class: 'eyebrow'},
        thing.layerKind === 'memory' ? 'Memory' : thing.kind === 'property' ? 'Property' : 'Item'),
      h('div', {class: 'pills'}, thing.layer ? layerPill(thing.layer) : null,
        thing.item.state ? h('span', {class: 'pill'}, thing.item.state) : null),
      h('div', {class: 'itemtext'}, itemView(thing.value)),
      link ? h('p', {class: 'meta'}, 'Links to ', h('a', {class: 'link', href: '#', onclick: go},
        nameOf(link, thing.item.link.id)), '; Enter goes there.') : null,
      refsOf(thing.item.refs));
    return;
  }
  fill(pane, h('div', {class: 'eyebrow'}, thing.kind === 'more' ? 'More' : 'Node'), h('h2', {}, thing.label),
    h('p', {class: 'meta'}, thing.kind === 'more' ? 'Enter shows the next ones.' : 'Enter goes inside it.'));
}
