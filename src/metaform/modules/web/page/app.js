/* Metaform's web GUI, the viewer: the whole map in 3D and in 2D, kept in sync, and the selected object below.
 * Every piece of data comes from the server's reads, VIEW-004; the page never decides what is visible. Text from the
 * store is always set as text, never as HTML, VIEW-009. */
'use strict';

const $ = selector => document.querySelector(selector);
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const SVG = 'http://www.w3.org/2000/svg';

/* A DOM node from a tag, its properties and its children; strings become text nodes, never markup. */
function h(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'style') for (const [name, v] of Object.entries(value)) node.style.setProperty(name, v);
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? '' : value);
  }
  return put(node, children, false);
}
/* Fill a node with children: nested lists are flattened, empty ones dropped, strings kept as text. */
function put(node, children, replace = true) {
  const kids = [children].flat(Infinity).filter(child => child !== null && child !== undefined && child !== false)
    .map(child => child instanceof Node ? child : String(child));
  if (replace) node.replaceChildren(...kids); else node.append(...kids);
  return node;
}
const fill = (node, ...children) => put(node, children);

/* ---------- reads ---------- */
const S = {
  projects: [], project: null, metaforms: [], metaform: null, layers: [], view: null,
  elements: new Map(), joins: [], items: new Map(), selected: null, neighbors: new Set(), trail: [], history: [], at: -1, loading: 0,
};

async function read(name, params = {}) {
  const query = new URLSearchParams({project: S.project, ...(S.metaform ? {metaform: S.metaform} : {}), ...params});
  const response = await fetch(`/api/${name}?${query}`, {headers: {Accept: 'application/json'}});
  const body = await response.json().catch(() => ({error: 'The server did not answer with JSON.'}));
  if (!response.ok) throw Object.assign(new Error(body.error || `${name} failed`), {status: response.status, body});
  return body;
}
const viewLayers = () => S.view === null ? {} : {layers: [...S.view].join(',')};

/* ---------- layers: color by position, the Layers checklist, apply ---------- */
const KNOWLEDGE = ['--k1', '--k2', '--k3', '--k4', '--k5', '--k6'];
function colorVar(layerName) {
  const layer = S.layers.find(item => item.name === layerName);
  if (!layer) return '--intake';
  if (layer.kind === 'intake') return '--intake';
  if (layer.kind === 'memory') return '--memory';
  if (layer.kind === 'correction') return '--correction';
  const knowledge = S.layers.filter(item => !['intake', 'memory', 'correction'].includes(item.kind));
  return KNOWLEDGE[knowledge.indexOf(layer) % KNOWLEDGE.length];
}
const layerColor = name => css(colorVar(name));
const folderOn = () => new Set(S.layers.filter(layer => layer.on).map(layer => layer.name));
const shownOn = () => S.view ?? folderOn();
const same = (a, b) => a.size === b.size && [...a].every(x => b.has(x));

/* The layers: a checklist opened from the header's Layers button, one row each, VIEW-007, Rich 2026-09-26. */
function renderChips() {
  const on = shownOn();
  const box = $('#layers');
  fill(box);
  const listed = S.layers.filter(item => item.kind !== 'correction');
  let count = 0;
  for (const layer of listed) {
    const usable = layer.ready && !layer.hidden, checked = usable && on.has(layer.name);
    if (checked) count++;
    const input = h('input', {type: 'checkbox', 'data-layer': layer.name, disabled: !usable, onchange: () => {
      const next = new Set(shownOn());
      input.checked ? next.add(layer.name) : next.delete(layer.name);
      S.view = same(next, folderOn()) ? null : next;
      renderChips();
      loadGraph();
    }});
    input.checked = checked;
    const state = layer.hidden ? 'hidden' : !layer.ready ? 'building' : 'ready';
    box.append(h('label', {class: 'layerrow', style: {'--c': `var(${colorVar(layer.name)})`},
      title: layer.hidden ? 'Hidden: it stays out even when turned on.' : !layer.ready ? 'Still building.' : null},
      input, h('i'), h('span', {class: 'name'}, layer.name), ' ', h('span', {class: 'meta'}, [layer.kind, ...(layer.tags || []), state].join(' · '))));
  }
  const corrections = S.layers.filter(item => item.kind === 'correction').length;
  if (corrections) {
    const input = h('input', {type: 'checkbox', disabled: true});
    input.checked = true;
    box.append(h('label', {class: 'layerrow fixed', style: {'--c': 'var(--correction)'}, title: 'Correction layers are always applied, in order.'},
      input, h('i'), h('span', {class: 'name'}, 'corrections'), ' ', h('span', {class: 'meta'}, `${corrections} · always applied`)));
  }
  $('#layersBtn').textContent = `Layers · ${count} of ${listed.length}`;
  $('#apply').disabled = S.view === null;
  const folder = S.projects.find(item => item.id === S.project)?.path || '';
  $('#note').textContent = S.view === null
    ? `Viewing only. These are the layers of ${folder}. What you toggle changes this view, not the folder, until you apply it.`
    : S.view.size === 0 ? 'No layer is chosen, which reads as every layer, as an empty --layers does.'
    : `This view differs from ${folder}. Apply to folder runs: metaform set --layers ${[...S.view].join(',')}`;
}

function showLayers(open) {
  $('#layerlist').hidden = !open;
  $('#layersBtn').setAttribute('aria-expanded', String(open));
}
$('#layersBtn').onclick = event => { event.stopPropagation(); showLayers($('#layerlist').hidden); };
document.addEventListener('click', event => {
  if (!$('#layerlist').hidden && !event.target.closest('.layerpick')) showLayers(false);
});
$('#apply').onclick = async () => {
  if (S.view === null) return;
  const response = await fetch('/api/apply-layers', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({project: S.project, layers: [...S.view]})});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) return toast(body.error || 'The folder was not changed.');
  S.view = null;
  S.layers = (await read('layers', {limit: 0})).results;
  renderChips();
  toast(['Applied to the folder.', ...(body.notices || []).map(notice => notice.message)].join(' '));
};

/* ---------- the graph data ---------- */
/* The graph as the approved prototype draws it: each join uncollapsed as its receiver, a purpose vertex and the
 * encounter, the link on to its provider; subtypes hang from their join's purpose; the namespace joins each element to
 * its nearest parent element, VIEW-005. */
function graphData() {
  const nodes = [], links = [];
  const byAddress = new Map([...S.elements.values()].map(entry => [entry.element.address, entry.element.element_id]));
  for (const {element, parent} of S.elements.values()) {
    nodes.push({id: element.element_id, t: 'el', name: element.short_name || element.address, address: element.address,
      role: element.role, flag: element.flag, layer: element.layer});
    if (parent && byAddress.has(parent)) links.push({source: byAddress.get(parent), target: element.element_id, k: 'tree'});
  }
  const ids = new Set(nodes.map(node => node.id));
  for (const join of S.joins) {
    if (!ids.has(join.receiver) || !ids.has(join.provider)) continue;
    const purpose = 'p:' + join.join_id;
    nodes.push({id: purpose, t: 'purpose', join: join.join_id, layer: join.layer, flag: join.flag});
    links.push({source: join.receiver, target: purpose, k: 'purpose', layer: join.layer, join: join.join_id});
    links.push({source: purpose, target: join.provider, k: 'encounter', layer: join.layer, join: join.join_id,
      ef: join.ef});
    for (const subtype of join.subtypes || []) {
      nodes.push({id: 's:' + subtype.subtype_id, t: 'sub', join: join.join_id, layer: subtype.layer,
        name: subtype.name || subtype.address, flag: subtype.flag});
      links.push({source: purpose, target: 's:' + subtype.subtype_id, k: 'layer', layer: subtype.layer, join: join.join_id,
        ef: subtype.ef});
    }
  }
  // Every item and property of the layers turned on is its own node, hung from its node; a link runs on, VIEW-017.
  const drawnIds = new Set(nodes.map(node => node.id));
  const at = thing => thing.kind === 'property' ? thing.item.element_id : keyOf(thing.item.target);
  const hung = [...S.items.values()].filter(thing => drawnIds.has(at(thing)));
  for (const thing of hung) {
    nodes.push({id: thing.key, t: 'item', layer: thing.layer, text: itemText(thing.value)});
    drawnIds.add(thing.key);
  }
  for (const thing of hung) {
    links.push({source: at(thing), target: thing.key, k: 'item', layer: thing.layer});
    const to = keyOf(thing.item.link);
    if (to && drawnIds.has(to)) links.push({source: thing.key, target: to, k: 'relation', layer: thing.layer});
  }
  return {nodes, links};
}
/* A selection is an element's id, a subtype as 's:<id>' or a join as 'p:<id>', the same keys the 3D view uses. */
const subtypeOf = new Map();
function indexSubtypes() {
  subtypeOf.clear();
  for (const join of S.joins) for (const subtype of join.subtypes || []) subtypeOf.set('s:' + subtype.subtype_id, {subtype, join});
}
const joinOf = key => S.joins.find(join => 'p:' + join.join_id === key);
window.metaform = {graph: () => graphData(), selected: () => S.selected, select: id => select(id, true),
  click3d: id => clicked3d(G?.graphData().nodes.find(node => node.id === id)),
  drawn: () => G ? {nodes: G.graphData().nodes.length, links: G.graphData().links.length} : null,
  linkColors: () => G ? G.graphData().links.map(link => ({join: link.join || null, k: link.k,
    target: link.target?.id ?? link.target, color: linkColor(link)})) : [],
  loaded: () => !S.loading, editor: () => P.editor, live: () => LIVE.layer,
  inside: () => IN.length && M.drawn === IN.at(-1) ? [...M.nodes.keys()] : [], vertical: () => M.vertical};

/* ---------- 3D: a synaptic map, drawn as the approved prototype draws it ---------- */
const FLAGS = {missing: '--missing', broken: '--broken', cruft: '--cruft'};
function colorOf(node) {
  if (node.t === 'el') return node.flag && FLAGS[node.flag] ? css(FLAGS[node.flag]) : node.role === 'VE' ? css('--signal')
    : node.role === 'DE' ? '#ffffff' : layerColor(node.layer);
  if (node.t === 'purpose') return css('--text');
  return layerColor(node.layer);
}
/* An encounter takes the color of its EF's word, Function or Encounter; one with no word keeps its layer's color. */
const EF = {Function: '--function', Encounter: '--encounter'};
function linkColor(link) {
  if (link.k === 'tree') return css('--tree');
  if (EF[link.ef]) return css(EF[link.ef]);
  return layerColor(link.layer);
}
let G = null;
const nodeSize = node => node.t === 'el' ? (node.role === 'DE' ? 9 : node.role === 'VE' ? 7 : 4) : node.t === 'purpose' ? 0.9
  : node.t === 'item' ? 0.3 : 0.35;
function start3D() {
  if (typeof ForceGraph3D !== 'function') {
    fill($('#stage'), h('p', {class: 'empty', style: {padding: '24px'}}, 'The 3D view needs WebGL and could not start here.'));
    return;
  }
  G = ForceGraph3D({controlType: 'orbit'})($('#stage'))
    .backgroundColor(css('--ground'))
    .showNavInfo(false)
    .nodeRelSize(3)
    .nodeVal(nodeSize)
    .nodeColor(node => S.selected && node.t === 'el' && node.id !== S.selected && !S.neighbors.has(node.id) ? '#2b3644' : colorOf(node))
    .nodeOpacity(0.95)
    .nodeResolution(16)
    .nodeLabel(() => '')  // the page shows its own tooltip, anchored above the node, not under the pointer
    .onNodeHover(node => {
      hovered = node || null;
      $('#tip3d').hidden = !hovered;
      if (hovered) { fill($('#tip3d'), tipFor(hovered)); placeTip(); }
    })
    .linkColor(linkColor)
    .linkOpacity(0.55)
    .linkWidth(link => link.k === 'tree' ? 0.4 : link.k === 'layer' || link.k === 'item' ? 0.25 : link.k === 'relation' ? 0.5 : 0.9)
    .linkCurvature(link => link.k === 'layer' || link.k === 'item' ? 0 : 0.18)
    .linkDirectionalParticles(link => !reduced() && (link.k === 'purpose' || link.k === 'encounter') ? 2 : 0)
    .linkDirectionalParticleSpeed(0.006)
    .linkDirectionalParticleWidth(1.6)
    .linkDirectionalParticleColor(linkColor)
    .onNodeClick(clicked3d);
  G.d3Force('charge').strength(node => node.t === 'el' ? -140 : node.t === 'item' ? -10 : -18);
  G.d3Force('link').distance(link => link.k === 'layer' ? 8 : link.k === 'item' ? 12 : link.k === 'tree' ? 60 : 34);
  resize();
  requestAnimationFrame(labels);
  $('#pauseBtn').onclick = () => {  // pausing pins every vertex where it is; resuming frees them and warms the layout
    const paused = $('#pauseBtn').dataset.paused === 'true';
    for (const node of G.graphData().nodes) Object.assign(node, paused ? {fx: undefined, fy: undefined, fz: undefined}
      : {fx: node.x, fy: node.y, fz: node.z});
    if (paused) G.d3ReheatSimulation();
    $('#pauseBtn').dataset.paused = String(!paused);
    $('#pauseBtn').textContent = paused ? 'Pause layout' : 'Resume layout';
  };
  $('#relayoutBtn').onclick = () => {
    const data = G.graphData();
    for (const node of data.nodes) for (const key of ['x', 'y', 'z', 'vx', 'vy', 'vz', 'fx', 'fy', 'fz']) delete node[key];
    $('#pauseBtn').dataset.paused = 'false';
    $('#pauseBtn').textContent = 'Pause layout';
    G.graphData(data);  // the layout gives vertices without a position new ones and settles again
  };
}
/* A click on any vertex selects that object itself: an element, a join's purpose vertex or a subtype. */
function clicked3d(node) { if (node) select(node.id, true); }
function tipFor(node) {
  if (node.t === 'el') return [h('b', {}, node.name), h('span', {}, node.address)];
  if (node.t === 'item') return [h('b', {}, node.layer), h('span', {}, short(node.text, 160))];
  const join = S.joins.find(item => item.join_id === node.join);
  return [node.t === 'purpose' ? (join?.purpose || 'purpose') : node.name || ''];
}
/* The tooltip sits above the hovered node, clear of its sphere at any zoom, so the pointer never covers it; it goes
 * below the node only where it would leave the top of the view. */
let hovered = null;
function placeTip() {
  const tip = $('#tip3d');
  if (!G || !hovered || hovered.x === undefined) return;
  const point = G.graph2ScreenCoords(hovered.x, hovered.y, hovered.z);
  const camera = G.camera(), box = $('#stage').getBoundingClientRect();
  const distance = Math.hypot(camera.position.x - hovered.x, camera.position.y - hovered.y, camera.position.z - hovered.z);
  const radius = Math.cbrt(nodeSize(hovered)) * 3 / (distance * Math.tan(camera.fov * Math.PI / 360)) * box.height / 2;
  const above = point.y - radius - 10 - tip.offsetHeight >= 0;
  tip.style.left = point.x + 'px';
  tip.style.top = (above ? point.y - radius - 10 : point.y + radius + 10) + 'px';
  tip.style.transform = `translate(-${Math.min(100, Math.max(0, point.x / box.width * 100))}%, ${above ? '-100%' : '0'})`;
}
const short = (text, most) => text.length > most ? text.slice(0, most - 1) + '…' : text;
const tags = new Map();
function labels() {
  if (G) {
    const box = $('#labels3d');
    for (const node of G.graphData().nodes) {
      if (node.t !== 'el') continue;
      let tag = tags.get(node.id);
      if (!tag) { tag = h('span', {}, short(node.name, 26)); box.append(tag); tags.set(node.id, tag); }
      tag.hidden = node.x === undefined;
      if (tag.hidden) continue;
      const point = G.graph2ScreenCoords(node.x, node.y, node.z);
      tag.style.left = point.x + 'px';
      tag.style.top = point.y + 'px';
      tag.className = node.id === S.selected ? 'sel' : S.neighbors.has(node.id) ? 'near' : S.selected ? 'dim' : '';
    }
    placeTip();
  }
  requestAnimationFrame(labels);
}
function draw3D() {
  if (!G) return;
  const previous = new Map(G.graphData().nodes.map(node => [node.id, node]));
  const data = graphData();
  for (const node of data.nodes) {  // keep drawn positions, so the picture does not jump as pages arrive
    const known = previous.get(node.id);
    if (known) Object.assign(node, {x: known.x, y: known.y, z: known.z, vx: known.vx, vy: known.vy, vz: known.vz,
      fx: known.fx, fy: known.fy, fz: known.fz});
  }
  for (const [id, tag] of tags) if (!S.elements.has(id)) { tag.remove(); tags.delete(id); }
  if (hovered) hovered = data.nodes.find(node => node.id === hovered.id) || null;
  $('#tip3d').hidden = !hovered;
  G.graphData(data);
}
function resize() { if (G) { const box = $('#stage').getBoundingClientRect(); G.width(box.width).height(box.height); } }
addEventListener('resize', resize);

function renderLegend() {
  const inView = new Set([...S.elements.values()].map(entry => entry.element.layer).concat(S.joins.map(join => join.layer)));
  const words = new Set(S.joins.flatMap(join => [join.ef, ...(join.subtypes || []).map(subtype => subtype.ef)]));
  const rows = [['--intake', 'purpose · receiver to join', ''],
    ...(words.has('Function') ? [['--function', 'Function · the encounter of a functionality', '']] : []),
    ...(words.has('Encounter') ? [['--encounter', 'Encounter · the functionality of the encounter', '']] : []),
    ['--tree', 'namespace', ''], ...[...inView].map(name => [colorVar(name), name, ''])];
  const legend = $('#legend');
  fill(legend, ...rows.map(([color, text, kind]) =>
    h('span', {style: {'--c': `var(${color})`}}, h('i', {class: kind}), text)));
  const flags = new Set([...S.elements.values()].map(entry => entry.element.flag).concat(S.joins.map(join => join.flag)));
  for (const flag of ['missing', 'broken', 'cruft']) if (flags.has(flag))
    legend.append(h('span', {style: {'--c': `var(--${flag})`}}, h('i', {class: 'dot'}), `flag: ${flag}`));
  const shown = G ? G.graphData().nodes.length : 0;
  $('#count').textContent = `${S.elements.size} elements · ${S.joins.length} joins · ${shown} nodes shown` + (S.loading ? ' · loading' : '')
    + (following() ? ' · intake being recorded' : '');
}

/* ---------- 2D: the whole map, short names, no text on the edges; the camera moves node to node ---------- */
const M = {svg: null, nodes: new Map(), edges: [], cam: null, fit: null, frame: 0, generation: 0};
const MAP2D = 5000;  // the most elements Mermaid lays out; above it the 2D map is not drawn, BUILD-QUESTIONS Q52
const plain2d = text => String(text || '').replace(/["[\]{}()<>|#;`]/g, '').slice(0, 30);
let mermaidReady = false;
async function build2D() {
  const generation = ++M.generation;
  const host = $('#viewport');
  if (!window.mermaid) { fill(host, h('p', {class: 'empty', style: {padding: '16px'}}, 'The 2D map could not load.')); return; }
  if (!mermaidReady) {
    window.mermaid.initialize({startOnLoad: false, securityLevel: 'strict', theme: 'base', htmlLabels: false,
      flowchart: {htmlLabels: false, useMaxWidth: false, curve: 'basis', nodeSpacing: 28, rankSpacing: 45},
      themeVariables: {background: '#06080c', primaryColor: '#111821', primaryBorderColor: '#2a3747',
        primaryTextColor: '#d9e2ec', lineColor: '#7fb0ff', fontFamily: 'IBM Plex Sans, sans-serif', fontSize: '13px',
        tertiaryColor: '#0c1117'}});
    mermaidReady = true;
  }
  const keys = new Map([...S.elements.keys()].map((id, index) => [id, `n${index}`]));
  const drawn = S.joins.filter(join => keys.has(join.receiver) && keys.has(join.provider));
  // The nodes inside an element are the subtypes of the joins it provides; it is drawn as a box holding them.
  const held = new Map();
  for (const join of drawn) for (const subtype of join.subtypes || [])
    held.set(join.provider, [...(held.get(join.provider) || []), subtype]);
  const inner = new Map();
  const vertical = S.elements.size > 5;
  const lines = [vertical ? 'flowchart TB' : 'flowchart LR'];
  for (const [id, {element}] of S.elements) {
    const label = plain2d(element.short_name || element.address);
    if (!held.has(id)) { lines.push(`${keys.get(id)}["${label}"]`); continue; }
    lines.push(`subgraph ${keys.get(id)} ["${label}"]`, 'direction TB');
    for (const subtype of held.get(id)) {
      const key = `s${inner.size}`;
      inner.set('s:' + subtype.subtype_id, key);
      lines.push(`${key}["${plain2d(subtype.name || subtype.address)}"]:::sub`);
    }
    lines.push('end');
  }
  if (inner.size) lines.push('classDef sub font-size:11px');
  drawn.forEach((join, index) => lines.push(`${keys.get(join.receiver)} e${index}@--> ${keys.get(join.provider)}`));
  if (!S.elements.size || S.elements.size > MAP2D) { IN.length = 0; M.base = null; renderCrumbs(); }
  if (!S.elements.size) { fill(host, h('p', {class: 'empty', style: {padding: '16px'}}, 'This metaform has no elements in these layers.')); return; }
  if (S.elements.size > MAP2D) {
    M.svg = null; M.nodes = new Map(); M.edges = [];
    fill(host, h('p', {class: 'empty', style: {padding: '16px'}}, `The 2D map lays out at most ${MAP2D} elements; these layers show ${S.elements.size}. The 3D view shows them all.`));
    return;
  }
  let result;
  try { result = await window.mermaid.render(`map2d${generation}`, lines.join('\n')); }
  catch (error) { fill(host, h('p', {class: 'empty', style: {padding: '16px'}}, 'The 2D map could not be drawn.')); return; }
  if (generation !== M.generation) return;
  const inside = IN.length > 0;
  const svg = mountSvg(result, host, inside);
  const nodes = new Map();
  for (const [id, key] of keys) {
    const group = held.has(id) ? svg.querySelector(`g.cluster[id="${key}"], g.cluster[id$="-${key}"]`)
      : svg.querySelector(`[id*="-flowchart-${key}-"]`);
    if (group) placeIn(nodes, id, group, S.elements.get(id).element.address, S.elements.get(id).element.flag);
  }
  for (const [id, key] of inner) {
    const group = svg.querySelector(`[id*="-flowchart-${key}-"]`);
    const {subtype} = subtypeOf.get(id) || {};
    if (group && subtype) placeIn(nodes, id, group, subtype.address, subtype.flag);
  }
  const edges = drawn.map((join, index) => ({join, path: svg.querySelector(`[data-id="e${index}"]`)
    || svg.querySelectorAll('.edgePaths path')[index]}));
  for (const edge of edges) if (EF[edge.join.ef]) edge.path?.classList.add(`ef-${edge.join.ef.toLowerCase()}`);
  // The base map is kept while a node is entered and shown again as it was, VIEW-016.
  M.base = {svg, nodes, edges, fit: fitOf(svg), vertical, cam: null};
  if (inside) { svg.remove(); svg.style.visibility = ''; await drawInside(); return; }
  showBase();
  if (S.selected) focus2D(S.selected, false);
}
/* Mermaid's strict SVG, the only markup parsed; hidden when it is measured without being shown. */
function mountSvg(result, host, hidden) {
  const parsed = new DOMParser().parseFromString(result.svg, 'image/svg+xml');
  const svg = document.importNode(parsed.documentElement, true);
  svg.removeAttribute('height'); svg.removeAttribute('width'); svg.removeAttribute('style');
  svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  if (hidden) { svg.style.visibility = 'hidden'; host.append(svg); } else fill(host, svg);
  return svg;
}
function placeIn(nodes, id, group, title, flag) {
  const box = group.getBBox();
  const matrix = group.transform.baseVal.consolidate()?.matrix;
  const center = new DOMPoint(box.x + box.width / 2, box.y + box.height / 2).matrixTransform(matrix || new DOMMatrix());
  nodes.set(id, {g: group, x: center.x, y: center.y, w: box.width, h: box.height});
  if (flag) group.classList.add(`flag-${flag}`);
  const text = document.createElementNS(SVG, 'title');
  text.textContent = title;
  group.append(text);
  group.addEventListener('click', event => { event.stopPropagation(); clicked2d(id); });
}
function fitOf(svg) {
  const scene = svg.querySelector('g').getBBox();
  return {x: scene.x - 30, y: scene.y - 30, w: scene.width + 60, h: scene.height + 60};
}
function showBase() {
  const base = M.base;
  renderCrumbs();
  if (!base) return;
  cancelAnimationFrame(M.frame);  // a camera still easing on the level left must not move this one
  Object.assign(M, {svg: base.svg, nodes: base.nodes, edges: base.edges, fit: base.fit, vertical: base.vertical, drawn: null});
  fill($('#viewport'), base.svg);
  setCam(base.cam || frame(base.fit));
}

/* ---------- inside a node: the 2D map is replaced by the node's own graph, VIEW-016 ----------
 * Every node can be entered. Inside are the node, what it holds, one group for each layer turned on with what that
 * layer attaches to the node, and the nodes those items link to, which can be entered in turn. */
const IN = [];  // the levels entered from the base map: {key, label, more, things}
const GROUP = 20;
let insideGen = 0;
const kindOf = key => key.startsWith('s:') ? 'subtype' : key.startsWith('p:') ? 'join' : 'element';
const bareId = key => key.replace(/^[sp]:/, '');
const keyOf = node => !node ? null : node.kind === 'subtype' ? 's:' + node.id : node.kind === 'join' ? 'p:' + node.id
  : node.kind === 'element' ? node.id : null;
const isDescriptor = value => value && typeof value === 'object' && 'descriptor' in value;
const label2d = text => plain2d(String(text ?? '').replace(/\s+/g, ' ')) || '·';
const samePath = (a, b) => a.length === b.length && a.every((level, index) => level.key === b[index].key);
function nameOf(key, fallback = key) {
  if (key.startsWith('s:')) { const found = subtypeOf.get(key)?.subtype; return found ? found.name || found.address : fallback; }
  if (key.startsWith('p:')) { const found = joinOf(key); return found ? found.purpose || found.relation || 'join' : fallback; }
  const found = S.elements.get(key)?.element;
  return found ? found.name || found.short_name || found.address : fallback;
}
async function drawInside() {
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
  const lines = [vertical ? 'flowchart TB' : 'flowchart LR'], edges = [], ids = new Map(), things = new Map(), groups = new Map();
  const add = (key, label, kind, thing = null) => {
    if (ids.has(key)) return ids.get(key);
    const id = `v${ids.size}`;
    ids.set(key, id);
    things.set(key, thing || {kind, key, label});
    lines.push(`${id}["${label2d(label)}"]:::${kind}`);
    return id;
  };
  const key = level.key, center = add(key, level.label, 'center');
  if (key.startsWith('p:')) {
    const join = joinOf(key);
    if (join) {
      edges.push(`${add(join.receiver, nameOf(join.receiver), 'stub')} --> ${center}`,
        `${center} --> ${add(join.provider, nameOf(join.provider), 'stub')}`);
      for (const subtype of join.subtypes || []) edges.push(`${center} --- ${add('s:' + subtype.subtype_id, subtype.name || subtype.address, 'sub')}`);
    }
  } else if (key.startsWith('s:')) {
    const found = subtypeOf.get(key);
    if (found) edges.push(`${add('p:' + found.join.join_id, found.join.purpose || 'join', 'purpose')} --- ${center}`);
  } else {
    for (const join of S.joins.filter(item => item.provider === key)) for (const subtype of join.subtypes || [])
      edges.push(`${center} --- ${add('s:' + subtype.subtype_id, subtype.name || subtype.address, 'sub')}`);
    for (const join of S.joins.filter(item => item.receiver === key))
      edges.push(`${center} --> ${add('p:' + join.join_id, join.purpose || join.relation || 'join', 'purpose')}`);
  }
  const linked = [];
  for (const found of view?.layers || []) {
    const all = [...(found.items || []).filter(item => !isDescriptor(item.value)).map(item => ({kind: 'item', key: 'i:' + item.item_id, item})),
      ...(found.properties || []).map(item => ({kind: 'property', key: 'r:' + item.property_id, item}))]
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
  for (const thing of linked) {
    const to = keyOf(thing.item.link);
    if (to) edges.push(`${ids.get(thing.key)} --> ${add(to, nameOf(to, thing.item.link.id), 'stub')}`);
  }
  const coming = incoming.filter(item => !ids.has('i:' + item.item_id));
  if (coming.length) {
    const gid = `g${groups.size}`;
    groups.set(gid, null);
    lines.push(`subgraph ${gid} ["linked here"]`, 'direction TB');
    for (const item of coming) add('i:' + item.item_id, itemText(item.value), 'item', {kind: 'item', key: 'i:' + item.item_id,
      item, value: item.value, layer: item.layer, layerKind: S.layers.find(layer => layer.name === item.layer)?.kind});
    lines.push('end');
    for (const item of coming) {
      const from = keyOf(item.target);
      if (from) edges.push(`${add(from, nameOf(from, item.target.id), 'stub')} --> ${ids.get('i:' + item.item_id)}`);
    }
    edges.push(`${gid} --> ${center}`);
  }
  lines.push(...edges, ...['center', 'item', 'stub', 'more', 'purpose', 'sub'].map(kind => `classDef ${kind} font-size:11px`));
  let result;
  try { result = await window.mermaid.render(`inside${generation}`, lines.join('\n')); }
  catch (error) { fill($('#viewport'), h('p', {class: 'empty', style: {padding: '16px'}}, 'This node could not be drawn.')); return; }
  if (generation !== insideGen || IN.at(-1) !== level) return;
  const svg = mountSvg(result, $('#viewport'), false);
  const nodes = new Map();
  for (const [thingKey, id] of ids) {
    const group = svg.querySelector(`[id*="-flowchart-${id}-"]`), thing = things.get(thingKey);
    if (!group) continue;
    placeIn(nodes, thingKey, group, thing.value !== undefined ? itemText(thing.value) : thing.label, null);
    group.classList.add(`in-${thing.kind}`);
  }
  for (const [gid, layer] of groups) {
    const cluster = svg.querySelector(`g.cluster[id="${gid}"], g.cluster[id$="-${gid}"]`);
    if (!cluster) continue;
    cluster.classList.add('layergroup');
    if (layer) cluster.style.setProperty('--c', `var(${colorVar(layer)})`);
  }
  level.things = things;
  cancelAnimationFrame(M.frame);  // a camera still easing on the level left must not move this one
  Object.assign(M, {svg, nodes, edges: [], fit: fitOf(svg), vertical, drawn: level});
  setCam(frame(M.fit));
  renderCrumbs();
  if (S.selected && nodes.has(S.selected)) focus2D(S.selected, false);
}
function renderCrumbs() {
  const bar = $('#crumbs');
  bar.hidden = !IN.length;
  const to = (depth, text) => h('a', {href: '#', onclick: event => { event.preventDefault(); goTo(depth); }}, text);
  fill(bar, ...(IN.length ? [to(0, 'map'), ...IN.flatMap((level, index) => [h('span', {class: 'sep'}, ' › '),
    index === IN.length - 1 ? h('b', {}, level.label) : to(index + 1, level.label)])] : []));
}
/* Enter a node, or the node an item links to; a group's "more" node shows the next ones. */
async function enter(key) {
  const level = IN.at(-1), thing = level?.things?.get(key);
  if (key.startsWith('m:')) { level.more[key.slice(2)] = (level.more[key.slice(2)] || GROUP) + GROUP; return drawInside(); }
  if (thing && (thing.kind === 'item' || thing.kind === 'property')) {
    const to = keyOf(thing.item.link);
    if (!to) return;
    return enter(to);
  }
  if (level?.key === key) return;
  if (!IN.length && M.base) M.base.cam = {...M.cam};
  IN.push({key, label: nameOf(key, thing?.label || key), more: {}, things: new Map()});
  await drawInside();
  select(key, false, true);
}
/* Up to a level: 0 is the base map. The node left is selected where it shows. */
async function goTo(depth) {
  if (depth >= IN.length) return;
  const left = IN[depth].key;
  IN.length = depth;
  if (depth) await drawInside(); else showBase();
  select(left, true, true);
}
function renderThing(thing) {
  const pane = $('#p-object');
  if (thing.kind === 'item' || thing.kind === 'property') {
    const link = keyOf(thing.item.link);
    fill(pane,
      h('div', {class: 'eyebrow'}, thing.layerKind === 'memory' ? 'Memory' : thing.kind === 'property' ? 'Property' : 'Item'),
      h('div', {class: 'pills'}, thing.layer ? layerPill(thing.layer) : null, thing.item.state ? h('span', {class: 'pill'}, thing.item.state) : null),
      h('p', {class: 'itemtext'}, itemText(thing.value)),
      link ? h('p', {class: 'meta'}, 'Links to ', h('a', {class: 'link', href: '#', onclick: event => { event.preventDefault(); enter(link); }},
        nameOf(link, thing.item.link.id)), '; Enter goes there.') : null,
      refsOf(thing.item.refs));
    return;
  }
  fill(pane, h('div', {class: 'eyebrow'}, thing.kind === 'more' ? 'More' : 'Node'), h('h2', {}, thing.label),
    h('p', {class: 'meta'}, thing.kind === 'more' ? 'Enter shows the next ones.' : 'Enter goes inside it.'));
}
function aspect() { const box = $('#viewport').getBoundingClientRect(); return Math.max(0.2, box.width / Math.max(1, box.height)); }
function frame(box) {
  let {x, y, w, h: height} = box; const a = aspect();
  if (w / height > a) { const nh = w / a; y -= (nh - height) / 2; height = nh; } else { const nw = height * a; x -= (nw - w) / 2; w = nw; }
  return {x, y, w, h: height};
}
function setCam(cam) { M.cam = cam; M.svg?.setAttribute('viewBox', `${cam.x} ${cam.y} ${cam.w} ${cam.h}`); }
function moveCam(target, animate = true) {
  if (!M.svg) return;
  cancelAnimationFrame(M.frame);
  const to = frame(target), from = {...M.cam};
  if (!animate || reduced()) return setCam(to);
  const start = performance.now(), duration = 700;
  const ease = t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  const step = now => {
    const k = ease(Math.min(1, (now - start) / duration));
    setCam({x: from.x + (to.x - from.x) * k, y: from.y + (to.y - from.y) * k, w: from.w + (to.w - from.w) * k, h: from.h + (to.h - from.h) * k});
    if (k < 1) M.frame = requestAnimationFrame(step);
  };
  M.frame = requestAnimationFrame(step);
}
function fit2D() {
  M.view = 'out';
  $('#map2d').classList.remove('focused');
  for (const edge of M.edges) edge.path?.classList.remove('on');
  for (const node of M.nodes.values()) node.g.classList.remove('sel', 'near');
  if (M.fit) moveCam(M.fit);
}
function focus2D(id, animate = true, framing = 'around', zoom = false) {
  const join = id.startsWith('p:') ? joinOf(id) : null;
  const node = M.nodes.get(id) || (join ? M.nodes.get(join.provider) : null);
  if (!node || !M.svg) return;
  if (IN.length) {  // inside a node its whole graph stays in view; the camera moves only when Fit asks
    for (const [key, value] of M.nodes) value.g.classList.toggle('sel', key === id);
    if (!zoom) return;
  } else {
    $('#map2d').classList.add('focused');
    for (const [key, value] of M.nodes) { value.g.classList.toggle('sel', key === id); value.g.classList.toggle('near', key !== id && S.neighbors.has(key)); }
    for (const edge of M.edges) edge.path?.classList.toggle('on', join ? edge.join === join
      : edge.join.receiver === id || edge.join.provider === id);
  }
  // 'around' shows the node with its joined nodes; 'inside' frames the node so the nodes it holds fill the view;
  // 'close' moves nearer to a node that holds nothing.
  M.view = framing === 'around' ? 'around' : 'in';
  const [w, height] = framing === 'inside' ? [node.w * 1.25, node.h * 1.25]
    : framing === 'close' ? [Math.max(node.w * 1.8, 160), Math.max(node.h * 2.6, 110)]
    : [Math.max(node.w * 3.4, 380), Math.max(node.h * 5, 260)];
  moveCam({x: node.x - w / 2, y: node.y - height / 2, w, h: height}, animate);
}
/* One click selects; a click on the selected node goes inside it; a group's "more" node shows the next ones. */
function clicked2d(id) { if (id === S.selected || id.startsWith('m:')) goInside(id); else select(id, true); }
(function wire2D() {
  const host = $('#map2d');
  $('#fitBtn').onclick = event => { event.stopPropagation(); cycleView(); };
  $('#backBtn').onclick = event => { event.stopPropagation(); step(-1); };
  $('#forwardBtn').onclick = event => { event.stopPropagation(); step(1); };
  let drag = null;
  host.addEventListener('pointerdown', event => {
    if (event.target.closest('button, a') || !M.cam) return;
    drag = {x: event.clientX, y: event.clientY, cam: {...M.cam}, moving: false};
  });
  host.addEventListener('pointermove', event => {
    if (!drag) return;
    if (!drag.moving) {  // captured only once it is a drag, so a click still reaches the node under it
      if (Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 4) return;
      drag.moving = true; host.setPointerCapture(event.pointerId);
    }
    const box = $('#viewport').getBoundingClientRect(), scale = M.cam.w / box.width;
    setCam({...drag.cam, x: drag.cam.x - (event.clientX - drag.x) * scale, y: drag.cam.y - (event.clientY - drag.y) * scale});
  });
  host.addEventListener('pointerup', () => { drag = null; });
  host.addEventListener('wheel', event => {
    if (!M.cam) return;
    event.preventDefault();
    const f = event.deltaY > 0 ? 1.15 : 0.87, box = $('#viewport').getBoundingClientRect();
    const px = (event.clientX - box.left) / box.width, py = (event.clientY - box.top) / box.height, c = M.cam;
    setCam({x: c.x + (c.w - c.w * f) * px, y: c.y + (c.h - c.h * f) * py, w: c.w * f, h: c.h * f});
  }, {passive: false});
})();
function fitAll() { fit2D(); if (G) G.zoomToFit(reduced() ? 0 : 700, 60); }
/* Fit and F go through three views, Rich 2026-09-26: zoomed out to the whole map, zoomed in on the selected node,
 * with the nodes inside it when it holds any, and regular, the node with its joined nodes. */
function cycleView() {
  const here = S.selected;
  const next = {around: 'out', out: 'in', in: 'around'}[M.view || 'around'];
  if (!here || next === 'out') return fitAll();
  if (next === 'in') return focus2D(here, true, !IN.length && insideOf(here).length ? 'inside' : 'close', true);
  focus2D(here, true, 'around', true);
}
/* Back and forward step through the nodes selected, as a browser does; a new selection drops the steps forward. */
async function step(by) {
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
function showSteps() {
  $('#backBtn').disabled = S.at <= 0;
  $('#forwardBtn').disabled = S.at >= S.history.length - 1;
}

/* The keys walk the join tree, Rich 2026-09-26: Down goes deeper, to the providers of the node's joins and then to
 * the nodes inside it; Up goes back to the parent; Left and Right move between the nodes connected to the parent.
 * Enter goes inside a node; Escape or Shift+Enter backs out. F fits. */
function across(keys) {  // in their order across the 2D map
  const at = key => M.nodes.get(key) || {x: Infinity, y: Infinity};
  return [...keys].sort((a, b) => M.vertical ? at(a).x - at(b).x || at(a).y - at(b).y : at(a).y - at(b).y || at(a).x - at(b).x);
}
function insideOf(key) {
  return across(S.joins.filter(join => join.provider === key).flatMap(join => (join.subtypes || []).map(subtype => 's:' + subtype.subtype_id)));
}
function childrenOf(key) {
  if (key.startsWith('p:')) return [joinOf(key)?.provider].filter(Boolean);
  if (key.startsWith('s:')) return [];
  const providers = across(new Set(S.joins.filter(join => join.receiver === key && S.elements.has(join.provider)).map(join => join.provider)));
  return [...providers, ...insideOf(key)];
}
function parentOf(key) {
  if (key.startsWith('p:')) return joinOf(key)?.receiver || null;
  if (key.startsWith('s:')) return subtypeOf.get(key)?.join.provider || null;
  return across(new Set(S.joins.filter(join => join.provider === key && S.elements.has(join.receiver)).map(join => join.receiver)))[0] || null;
}
function roots() {  // the nodes nothing receives from, vested entities first; then any part of the map they do not reach
  const top = [...S.elements.keys()].filter(key => !parentOf(key));
  const ordered = [...across(top.filter(key => S.elements.get(key).element.role === 'VE')), ...across(top.filter(key => S.elements.get(key).element.role !== 'VE'))];
  const reached = new Set(ordered), queue = [...ordered];
  while (queue.length) for (const next of childrenOf(queue.shift())) if (!reached.has(next)) { reached.add(next); queue.push(next); }
  for (const key of across([...S.elements.keys()].filter(key => !reached.has(key)))) {
    if (reached.has(key)) continue;
    ordered.push(key); reached.add(key);
    const more = [key];
    while (more.length) for (const next of childrenOf(more.shift())) if (!reached.has(next)) { reached.add(next); more.push(next); }
  }
  return ordered;
}
function goInside(key) { enter(key); }
function backOut() {
  if (IN.length) return goTo(IN.length - 1);
  const here = S.selected;
  if (!here) return;
  if (here.startsWith('s:') || here.startsWith('p:')) {
    const up = S.trail.length ? S.trail.pop() : parentOf(here);
    if (up) select(up, true, true);
  } else fitAll();
}
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && !$('#layerlist').hidden) { event.preventDefault(); showLayers(false); $('#layersBtn').focus(); return; }
  if (event.target.closest('select, input, textarea, .CodeMirror')) return;
  if (event.key === 'f' || event.key === 'F') { event.preventDefault(); cycleView(); return; }
  if (event.key === 'Home') { event.preventDefault(); fitAll(); return; }
  if (!S.selected) return;
  const here = S.selected;
  if (event.key === 'Escape' || (event.key === 'Enter' && event.shiftKey)) { event.preventDefault(); backOut(); return; }
  if (event.key === 'Enter') { event.preventDefault(); goInside(here); return; }
  if (IN.length && event.key.startsWith('Arrow')) {  // inside a node the arrows go through its graph in order
    event.preventDefault();
    const order = across(M.nodes.keys()), at = order.indexOf(here);
    const by = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : -1;
    if (order.length) select(order[at < 0 ? 0 : (at + by + order.length) % order.length], true, true);
    return;
  }
  if (event.key === 'ArrowDown') {
    event.preventDefault();
    const next = childrenOf(here)[0];
    if (next) { S.trail.push(here); select(next, true, true); }
  } else if (event.key === 'ArrowUp') {
    event.preventDefault();
    const parent = S.trail.length ? S.trail.pop() : parentOf(here);
    if (parent) select(parent, true, true);
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    event.preventDefault();
    const parent = S.trail.length ? S.trail[S.trail.length - 1] : parentOf(here);
    const row = parent ? childrenOf(parent) : roots();
    const at = row.indexOf(here);
    if (at < 0 || row.length < 2) return;
    select(row[(at + (event.key === 'ArrowRight' ? 1 : -1) + row.length) % row.length], true, true);
  }
});

/* ---------- selection: both views move together; the long text goes in the panel ---------- */
function select(id, fly, keepTrail = false, stepping = false) {
  if (!id) return;
  const subtype = id.startsWith('s:') ? subtypeOf.get(id) : null, join = id.startsWith('p:') ? joinOf(id) : null;
  const known = subtype || join || S.elements.has(id), thing = IN.at(-1)?.things?.get(id) || S.items.get(id);
  if (!known && !thing) return;
  if (!keepTrail) S.trail = [];
  const path = IN.map(({key, label}) => ({key, label})), last = S.history[S.at];
  if (!stepping && !(last && last.id === id && samePath(last.path, path))) {
    S.history = [...S.history.slice(0, S.at + 1), {id, path}]; S.at = S.history.length - 1;
  }
  showSteps();
  S.selected = id;
  if (!known) { S.neighbors = new Set(); focus2D(id, fly); showTab('object'); renderThing(thing); return; }
  S.neighbors = subtype ? new Set([subtype.join.provider, subtype.join.receiver, ...insideOf(subtype.join.provider)])
    : join ? new Set([join.receiver, join.provider])
    : new Set([id, ...S.joins.filter(item => item.receiver === id).map(item => item.provider),
      ...S.joins.filter(item => item.provider === id).map(item => item.receiver)]);
  if (G) {
    G.nodeColor(G.nodeColor());
    const node = G.graphData().nodes.find(item => item.id === id);
    if (fly && node && node.x !== undefined) {
      const ratio = 1 + 90 / Math.hypot(node.x || 1, node.y || 1, node.z || 1);
      G.cameraPosition({x: node.x * ratio, y: node.y * ratio, z: node.z * ratio}, node, reduced() ? 0 : 900);
    }
  }
  focus2D(id, fly);
  showTab('object');
  if (subtype) renderSubtype(subtype); else if (join) renderJoin(join); else renderObject(id);
}

function refsOf(refs) {
  return refs && refs.length ? h('div', {class: 'refs'}, refs.map(ref => `${ref.key}: ${ref.value}`).join(' · ')) : null;
}
function flagPill(thing) {
  return thing.flag ? h('span', {class: `pill flag-${thing.flag}`, title: thing.flag_note || null}, thing.flag) : null;
}
function efPill(thing) {
  return EF[thing.ef] ? h('span', {class: 'pill ef', style: {'--c': `var(${EF[thing.ef]})`}}, thing.ef) : null;
}
function layerPill(name) { return h('span', {class: 'pill layer', style: {'--c': `var(${colorVar(name)})`}}, name); }
function elementLink(id, address) {
  const entry = S.elements.get(id);
  return h('a', {class: 'link', href: '#', onclick: event => { event.preventDefault(); select(id, true); }},
    entry ? (entry.element.name || entry.element.short_name) : address);
}
function joinCard(join, side) {
  const other = side === 'provider' ? join.provider : join.receiver;
  const otherAddress = side === 'provider' ? join.provider_address : join.receiver_address;
  return h('div', {class: 'join'},
    h('div', {class: 'row'}, h('span', {class: 'dir'}, `${side} · `, elementLink(other, otherAddress)),
      h('span', {class: 'lay', style: {'--c': `var(${colorVar(join.layer)})`}}, join.layer)),
    join.purpose ? h('p', {}, join.purpose) : null,
    join.function ? h('p', {class: 'fn'}, efPill(join), join.function) : null,
    join.relation ? h('p', {class: 'fn'}, join.relation) : null,
    join.observation ? h('p', {class: 'obs'}, join.observation) : null,
    join.non_goal ? h('p', {class: 'obs'}, `Not: ${join.non_goal}`) : null,
    join.flag ? h('div', {class: 'pills'}, flagPill(join), join.flag_note ? h('span', {class: 'empty'}, join.flag_note) : null) : null,
    refsOf(join.refs),
    (join.subtypes || []).map(subtype => h('div', {class: 'sub'}, h('a', {class: 'link', href: '#', onclick: event => {
      event.preventDefault(); select('s:' + subtype.subtype_id, true); }}, h('b', {}, subtype.name || subtype.address)), ' ',
      h('span', {class: 'refs'}, subtype.address), subtype.function ? h('div', {}, efPill(subtype), subtype.function) : null,
      subtype.observation ? h('div', {}, subtype.observation) : null, flagPill(subtype), refsOf(subtype.refs))));
}
function itemText(value) {
  if (value && typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value ?? '');
}
/* A selected subtype or join shows only itself, so nothing needs finding in its parent's text. */
function renderSubtype({subtype, join}) {
  fill($('#p-object'),
    h('div', {class: 'eyebrow'}, 'Subtype'),
    h('h2', {}, subtype.name || subtype.address),
    h('div', {class: 'addr'}, subtype.address),
    h('div', {class: 'pills'}, subtype.role ? h('span', {class: 'pill'}, subtype.role) : null, efPill(subtype), flagPill(subtype),
      layerPill(subtype.layer)),
    h('p', {class: 'meta'}, 'Inside ', elementLink(join.provider, join.provider_address), ', in the join that serves ',
      elementLink(join.receiver, join.receiver_address), '.'),
    subtype.function ? h('p', {}, subtype.function) : null,
    subtype.relation ? h('p', {class: 'fn'}, subtype.relation) : null,
    subtype.observation ? h('p', {class: 'obs'}, subtype.observation) : null,
    subtype.flag_note ? h('p', {class: 'empty'}, subtype.flag_note) : null,
    refsOf(subtype.refs),
    h('div', {class: 'eyebrow'}, 'The join it sits in'),
    joinCard(join, 'provider'));
}
function renderJoin(join) {
  fill($('#p-object'),
    h('div', {class: 'eyebrow'}, 'Join'),
    h('h2', {}, join.relation || `${join.receiver_address} receives from ${join.provider_address}`),
    h('p', {class: 'meta'}, elementLink(join.receiver, join.receiver_address), ' receives from ',
      elementLink(join.provider, join.provider_address), '.'),
    joinCard(join, 'provider'));
}
async function renderObject(id) {
  const {element} = S.elements.get(id);
  const pane = $('#p-object');
  const held = S.joins.filter(join => join.receiver === id), serves = S.joins.filter(join => join.provider === id);
  fill(pane, 
    h('div', {class: 'eyebrow'}, 'Element'),
    h('h2', {}, element.name || element.short_name || element.address),
    h('div', {class: 'addr'}, element.address),
    h('div', {class: 'pills'}, element.role ? h('span', {class: 'pill'}, element.role) : null, flagPill(element),
      layerPill(element.layer), h('span', {class: 'pill'}, `${held.length} held · ${serves.length} served`)),
    element.flag_note ? h('p', {class: 'empty'}, element.flag_note) : null,
    refsOf(element.refs),
    h('div', {id: 'items'}),
    h('div', {class: 'eyebrow'}, 'Joins held by this element'),
    held.length ? held.map(join => joinCard(join, 'provider')) : h('p', {class: 'empty'}, 'This element receives nothing here.'),
    serves.length ? h('div', {class: 'eyebrow'}, 'Serves') : null,
    serves.map(join => joinCard(join, 'receiver')));
  try {
    const node = await read('node', {target: `element:${id}`, ...viewLayers()});
    if (S.selected !== id) return;
    const box = $('#items');
    for (const group of node.layers || []) {
      const items = (group.items || []).filter(item => !(item.value && typeof item.value === 'object' && 'descriptor' in item.value));
      if (!items.length) continue;
      box.append(h('div', {class: 'eyebrow'}, group.kind === 'memory' ? 'Memory' : group.layer),
        ...items.map(item => h('div', {class: 'item' + (item.orphaned ? ' orphaned' : ''), style: {'--c': `var(${colorVar(group.layer)})`}},
          itemText(item.value), item.state ? ` · ${item.state}` : '', refsOf(item.refs))));
    }
    const context = await read('context', {address: element.address, limit: 0, ...viewLayers()});
    if (S.selected !== id) return;
    for (const [title, found] of [['Properties that apply here', context.applying], ['Properties attached toward the leaves', context.visible]]) {
      if (!found.length) continue;
      box.append(h('div', {class: 'eyebrow'}, title), ...found.map(property => h('div', {class: 'item', style: {'--c': `var(${colorVar(property.layer)})`}},
        itemText(property.value), h('div', {class: 'refs'}, `${property.layer}${property.address && property.address !== element.address ? ' · at ' + property.address : ''}`),
        refsOf(property.refs))));
    }
  } catch (error) {  // nothing in the layers turned on, such as an intake still being built, is not an error
    if (error.status !== 404) toast(error.message);
  }
}

/* ---------- provenance ---------- */
let provLayer = null;
async function renderProv() {
  const pane = $('#p-prov');
  provLayer = provLayer && S.layers.some(layer => layer.name === provLayer) ? provLayer : S.layers[0]?.name;
  const list = h('div', {class: 'layerlist'}, S.layers.map(layer => h('button', {'aria-pressed': String(layer.name === provLayer),
    style: {'--c': `var(${colorVar(layer.name)})`}, onclick: () => { provLayer = layer.name; renderProv(); }},
    h('span', {style: {display: 'flex', gap: '8px', 'align-items': 'center'}}, h('i', {class: 'sw'}), layer.name),
    h('span', {class: 'pill'}, layer.kind))));
  fill(pane, h('div', {class: 'eyebrow'}, 'Layers in this metaform'), list);
  if (!provLayer) return;
  const layer = S.layers.find(item => item.name === provLayer);
  pane.append(h('div', {class: 'eyebrow'}, 'How it was made'), h('h2', {}, layer.name),
    h('dl', {class: 'prov'}, h('dt', {}, 'kind'), h('dd', {}, layer.kind), h('dt', {}, 'module'), h('dd', {}, layer.module),
      h('dt', {}, 'created'), h('dd', {}, layer.created), h('dt', {}, 'state'),
      h('dd', {}, layer.ready ? `ready ${layer.ready}` : 'building'), h('dt', {}, 'tags'), h('dd', {}, (layer.tags || []).join(', ') || 'none'),
      h('dt', {}, 'holds'), h('dd', {}, layer.variable || '')));
  if (layer.kind === 'memory') return pane.append(h('p', {class: 'empty'}, 'Memory has no provenance. Agents write it freely.'));
  try {
    const record = await read('provenance', {layer: layer.name});
    if (provLayer !== layer.name) return;
    const reports = (record.refs || []).map(ref => `${ref.key}: ${ref.value}`);
    pane.append(h('dl', {class: 'prov'},
      ...[['workflow', record.workflow], ['model', record.model], ['role', record.role],
        ['blinded', record.blinded === null ? '' : record.blinded ? 'yes' : 'no'], ['reports', reports.join(' · ') || 'none']]
        .flatMap(([key, value]) => [h('dt', {}, key), h('dd', {}, value || 'not recorded')])));
    if (record.prompt_version) pane.append(h('div', {class: 'toolbar'}, h('button', {class: 'btn primary open-prompt',
      onclick: () => { showTab('prompt'); renderPrompt(record.prompt_version.name, record.prompt_version.number); }},
      `Open prompt ${record.prompt_version.name}, version ${record.prompt_version.number}`)));
    if (record.prompt) pane.append(h('details', {}, h('summary', {class: 'eyebrow'}, 'The prompt as it was delivered'),
      h('pre', {class: 'prompt'}, record.prompt)));
  } catch (error) { pane.append(h('p', {class: 'empty'}, error.message)); }
}

/* ---------- prompts: edited in a real editor, saved as a new version, VIEW-013 ---------- */
const P = {editor: null, name: null, number: null, versions: []};
async function getJson(path) {
  const response = await fetch(path, {headers: {Accept: 'application/json'}});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `${path} failed`);
  return body;
}
async function renderPrompt(name = P.name, number = P.number) {
  const listed = (await getJson('/api/prompts')).prompts;
  if (!listed.length) {
    $('#promptNote').textContent = 'No stored prompts yet. The intake stores its prompt the first time it is served.';
    return;
  }
  P.name = listed.some(item => item.name === name) ? name : listed[0].name;
  P.versions = (await getJson(`/api/prompt-versions?name=${encodeURIComponent(P.name)}`)).versions;
  P.number = P.versions.some(item => item.number === number) ? number : P.versions[0].number;
  fill($('#promptSel'), listed.map(item => h('option', {value: item.name, selected: item.name === P.name}, item.name)));
  fill($('#verSel'), P.versions.map(item => h('option', {value: String(item.number), selected: item.number === P.number},
    `version ${item.number} · ${item.origin} · ${item.created}`)));
  const version = P.versions.find(item => item.number === P.number);
  if (!P.editor) P.editor = CodeMirror.fromTextArea($('#editor'), {lineNumbers: true, lineWrapping: true});
  P.editor.setOption('mode', version.format === 'markdown' ? 'markdown' : version.format === 'xml' ? 'xml' : null);
  P.editor.setValue(version.text);
  P.editor.clearHistory();
  $('#diffOut').hidden = true;
  const names = new Map(S.layers.map(layer => [layer.layer_id, layer.name]));
  const made = version.layers.map(use => names.get(use.layer_id) || `a layer of ${use.project_id}`);
  $('#promptNote').textContent = made.length ? `Version ${version.number} made: ${made.join(', ')}.`
    : `No layer was made with version ${version.number}.`;
  setTimeout(() => P.editor.refresh(), 0);
}
$('#promptSel').onchange = () => renderPrompt($('#promptSel').value, null);
$('#verSel').onchange = () => renderPrompt(P.name, Number($('#verSel').value));
function lineDiff(a, b) {
  a = a.split('\n'); b = b.split('\n');
  const n = a.length, m = b.length;
  if (n * m > 4e6) return [{t: 'gap', s: 'Too large to compare here.'}];
  const dp = Array.from({length: n + 1}, () => new Uint32Array(m + 1));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const out = []; let i = 0, j = 0;
  while (i < n && j < m) { if (a[i] === b[j]) { out.push({t: 'same', s: a[i]}); i++; j++; } else if (dp[i + 1][j] >= dp[i][j + 1]) out.push({t: 'del', s: a[i++]}); else out.push({t: 'add', s: b[j++]}); }
  while (i < n) out.push({t: 'del', s: a[i++]});
  while (j < m) out.push({t: 'add', s: b[j++]});
  const keep = new Set();
  out.forEach((row, k) => { if (row.t !== 'same') for (let d = -2; d <= 2; d++) keep.add(k + d); });
  const shown = []; let skipped = false;
  out.forEach((row, k) => { if (keep.has(k)) { shown.push(row); skipped = false; } else if (!skipped) { shown.push({t: 'gap', s: '···'}); skipped = true; } });
  return shown;
}
function showDiff() {
  const base = P.versions.find(item => item.number === P.number).text;
  const rows = lineDiff(base, P.editor.getValue());
  const changed = rows.some(row => row.t === 'add' || row.t === 'del');
  fill($('#diffOut'), changed ? rows.map(row => h('div', {class: row.t}, (row.t === 'add' ? '+ ' : row.t === 'del' ? '- ' : '  ') + row.s))
    : h('div', {class: 'gap'}, `No changes from version ${P.number}.`));
  $('#diffOut').hidden = false;
  return changed;
}
$('#diffBtn').onclick = showDiff;
$('#saveBtn').onclick = async () => {
  if (!showDiff()) return toast(`Nothing to save. The text matches version ${P.number}.`);
  const response = await fetch('/api/save-prompt', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name: P.name, text: P.editor.getValue(), parent: P.number})});
  const saved = await response.json().catch(() => ({}));
  if (!response.ok) return toast(saved.error || 'The prompt was not saved.');
  await renderPrompt(P.name, saved.number);
  toast(`Saved as version ${saved.number}. Layers made with earlier versions still show the version that made them.`);
};

/* ---------- corrections: removed one at a time from the top, after a warning, VIEW-014 ---------- */
async function renderCorr(warning = null) {
  const pane = $('#p-corr');
  fill(pane, h('div', {class: 'eyebrow'}, 'Correction stack · applied in order, newest on top'),
    h('p', {class: 'empty'}, 'Correction layers always apply and cannot be toggled. Only the top one can be removed.'));
  let stack;
  try { stack = (await read('stack', {limit: 0})).results.slice().reverse(); }
  catch (error) { pane.append(h('p', {class: 'empty'}, error.message)); return; }
  if (!stack.length) return pane.append(h('p', {class: 'empty'}, 'No correction layers. The metaform reads as the intake left it.'));
  pane.append(h('div', {class: 'stack'}, stack.map((layer, index) => h('div', {class: 'lyr' + (index === 0 ? ' top' : '')},
    h('div', {style: {display: 'flex', 'justify-content': 'space-between', gap: '8px'}}, h('b', {}, layer.name),
      h('span', {class: 'meta'}, layer.ready || '')),
    layer.provenance?.role ? h('div', {class: 'meta'}, `${layer.provenance.role}${layer.provenance.model ? ' · ' + layer.provenance.model : ''}`) : null,
    h('div', {class: 'meta'}, layer.variable || ''),
    index === 0 && !warning ? h('div', {}, h('button', {class: 'btn danger remove', onclick: () => warn(layer.name)},
      'Remove this layer')) : null))));
  if (warning) pane.append(warning);
}
async function warn(name) {
  let preview;
  try { preview = await read('peel-preview', {layer: name}); } catch (error) { return toast(error.message); }
  if (!preview.top) { toast((preview.notices || []).map(notice => notice.message).join(' ') || `${name} is no longer on top.`); return renderCorr(); }
  const lines = preview.changes.map(change => h('li', {}, `${change.kind} ${change.what} ${change.effect}` + (change.detail ? `, ${change.detail}` : '')));
  const box = h('div', {class: 'warn'}, h('b', {}, `Remove ${name}?`), h('span', {}, 'This changes the metaform every agent reads:'),
    lines.length ? h('ul', {}, lines) : h('p', {class: 'empty'}, 'It changed nothing that is still applied.'),
    h('div', {class: 'toolbar'},
      h('button', {class: 'btn danger confirm', onclick: () => removeTop(name)}, 'Remove it'),
      h('button', {class: 'btn', onclick: () => renderCorr()}, 'Keep it')));
  renderCorr(box);
}
async function removeTop(name) {
  const response = await fetch('/api/remove-correction', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({project: S.project, metaform: S.metaform, layer: name})});
  const body = await response.json().catch(() => ({}));
  if (!response.ok || !body.removed) toast(body.error || (body.notices || []).map(notice => notice.message).join(' ') || 'Nothing was removed.');
  else toast(`${name} removed. The layer below it is now on top.`);
  S.layers = (await read('layers', {limit: 0})).results;
  renderChips();
  await renderCorr();
  loadGraph();
}

/* ---------- tabs, toast ---------- */
const TABS = {object: '#p-object', prov: '#p-prov', prompt: '#p-prompt', corr: '#p-corr'};
function showTab(tab) {
  for (const [key, selector] of Object.entries(TABS)) { $(selector).hidden = key !== tab; $('#t-' + key).setAttribute('aria-selected', String(key === tab)); }
  if (tab === 'prov') renderProv();
  if (tab === 'corr') renderCorr();
  if (tab === 'prompt' && !P.editor) renderPrompt();
  if (tab === 'prompt' && P.editor) setTimeout(() => P.editor.refresh(), 0);
}
for (const key of Object.keys(TABS)) $('#t-' + key).onclick = () => showTab(key);
let toastTimer;
function toast(message) { const box = $('#toast'); box.textContent = message; box.hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { box.hidden = true; }, 4200); }

/* ---------- live: the server pushes what modules publish, and the page redraws; nothing polls, VIEW-018 ----------
 * An intake being recorded is drawn as each object arrives, BASE-039; any other write to the metaform shown is read
 * again. Events that come while the page reads are drawn once, when it is done. */
const LIVE = {layer: null, metaform: null, seen: '', busy: false, again: false};
const following = () => LIVE.layer !== null && S.metaform === LIVE.metaform;
async function loadLive() {
  const page = await read('layer-graph', {layer: LIVE.layer});
  const text = JSON.stringify(page);
  if (text === LIVE.seen || !following()) return;
  LIVE.seen = text;
  S.elements = new Map(page.elements.map(entry => [entry.element.element_id, entry]));
  S.joins = [...page.joins];
  S.items = new Map();
  indexSubtypes(); draw3D(); renderLegend();
  await build2D();
  const keep = S.selected && (S.elements.has(S.selected) || subtypeOf.has(S.selected) || joinOf(S.selected)) ? S.selected : null;
  const start = keep || [...S.elements.values()].find(entry => entry.element.role === 'DE')?.element.element_id
    || S.elements.keys().next().value;
  if (start) select(start, false);
  else fill($('#p-object'), h('p', {class: 'empty'}, 'Nothing to show in these layers yet.'));
}
/* Follow the intake being recorded, found = {layer, metaform_id}, or return to the map when it has finished. */
async function follow(found) {
  if (found && found.layer !== LIVE.layer) {
    Object.assign(LIVE, {layer: found.layer, metaform: found.metaform_id, seen: ''});
    if (S.metaform !== found.metaform_id) await loadProject(found.metaform_id);
    else { S.layers = (await read('layers', {limit: 0})).results; renderChips(); }
    toast(`An intake is being recorded in ${found.layer}; the map follows it as each object is recorded.`);
  } else if (!found && LIVE.layer) {
    const finished = LIVE.layer;
    Object.assign(LIVE, {layer: null, metaform: null, seen: ''});
    renderLegend();
    toast(`The intake ${finished} finished.`);
    await loadProject();
    return;
  }
  if (following()) await loadLive();
}
/* On connecting, and on the browser's own reconnect, what is being recorded now is read once. */
async function recordingNow() {
  const found = (await read('intake-recording')).results[0] || null;
  await follow(found ? {layer: found.layer.name, metaform_id: found.metaform_id} : null);
}
/* One push: the chassis fired map.changed for a metaform of this project, or for its metaforms themselves, VIEW-018.
 * The page reads what is being recorded, then follows it, returns to the map when it has finished, shows the active
 * metaform when the project's metaforms changed, or reads the layers and the map again, keeping the view and the
 * selection. */
async function changed(event) {
  if (event.topic !== 'map.changed' || event.payload?.project !== S.project) return;
  if (LIVE.busy) { LIVE.again = true; return; }
  LIVE.busy = true;
  try {
    do {
      LIVE.again = false;
      const found = (await read('intake-recording')).results[0] || null;
      if (found || LIVE.layer) { await follow(found ? {layer: found.layer.name, metaform_id: found.metaform_id} : null); continue; }
      const metaforms = (await read('metaforms', {limit: 0})).results;
      const same = metaforms.length === S.metaforms.length && metaforms.every(item =>
        S.metaforms.some(known => known.metaform_id === item.metaform_id && known.active === item.active));
      if (!same) await loadProject();  // the project's metaforms changed: show the active one, as on opening
      else {
        S.layers = (await read('layers', {limit: 0})).results;
        renderChips();
        await loadGraph();
      }
    } while (LIVE.again);
  } catch (error) { toast(error.message); } finally { LIVE.busy = false; }
}
function listen() {
  const source = new EventSource('/api/events');
  source.onmessage = message => changed(JSON.parse(message.data));
  source.onopen = () => recordingNow().catch(error => toast(error.message));
}

/* Every item and property of the layers, read as the context sees them, so selection, masks and hidden layers apply
 * as in every read; descriptor items, the intake's names and roles, are not items to draw, VIEW-017. */
async function itemsOf(generation) {
  const found = new Map();
  for (const layer of S.layers.filter(item => item.ready && !['intake', 'correction'].includes(item.kind))) {
    let after = null;
    do {
      const page = await read('layer-items', {layer: layer.name, in_context: 'true', limit: 500, ...(after ? {after} : {}), ...viewLayers()});
      if (generation !== S.loading) return found;
      for (const item of page.results) {
        const property = 'property_id' in item;
        if (!property && isDescriptor(item.value)) continue;
        const key = property ? 'r:' + item.property_id : 'i:' + item.item_id;
        found.set(key, {kind: property ? 'property' : 'item', key, item, value: item.value, layer: layer.name, layerKind: layer.kind});
      }
      after = page.next;
    } while (after);
  }
  return found;
}

/* ---------- loading: projects, metaforms, layers, then the graph page by page ---------- */
async function loadGraph() {
  if (following()) { LIVE.seen = ''; S.loading = 0; return loadLive(); }
  const generation = ++S.loading;
  S.elements = new Map(); S.joins = [];
  let after = null;
  try {
    do {
      const page = await read('graph', {limit: 500, ...(after ? {after} : {}), ...viewLayers()});
      if (generation !== S.loading) return;
      for (const entry of page.elements) S.elements.set(entry.element.element_id, entry);
      S.joins.push(...page.joins);
      indexSubtypes();
      draw3D(); renderLegend();
      after = page.next;
    } while (after);
    const items = await itemsOf(generation);
    if (generation !== S.loading) return;
    S.items = items;
  } catch (error) { toast(error.message); }
  if (generation !== S.loading) return;
  S.loading = 0;
  draw3D();
  renderLegend();
  await build2D();
  const keep = S.selected && (S.elements.has(S.selected) || subtypeOf.has(S.selected) || joinOf(S.selected)) ? S.selected : null;
  const start = keep || [...S.elements.values()].find(entry => entry.element.role === 'DE')?.element.element_id
    || S.elements.keys().next().value;
  if (!start) fill($('#p-object'), h('p', {class: 'empty'}, 'Nothing to show in these layers yet.'));
  else {
    select(start, false);
    if (!keep) setTimeout(() => { if (G) G.zoomToFit(reduced() ? 0 : 800, 60); }, 2200);
  }
}
async function loadMetaform() {
  S.view = null; S.selected = null; IN.length = 0; M.base = null; renderCrumbs();
  S.layers = (await read('layers', {limit: 0})).results;
  renderChips();
  if ($('#p-prov').hidden === false) renderProv();
  await loadGraph();
}
async function loadProject(wanted = null) {
  const metaforms = (await read('metaforms', {limit: 0})).results;
  S.metaforms = metaforms;
  const active = metaforms.find(item => item.metaform_id === wanted) || metaforms.find(item => item.active) || metaforms[0];
  S.metaform = active ? active.metaform_id : null;
  fill($('#mf'), ...metaforms.map(item => h('option', {value: item.metaform_id, selected: item === active}, item.name + (item.active ? ' · active' : ''))));
  await loadMetaform();
}
$('#proj').onchange = () => { S.project = $('#proj').value; location.hash = 'p=' + encodeURIComponent(S.project); Object.assign(LIVE, {layer: null, metaform: null, seen: ''}); loadProject(); };
$('#mf').onchange = () => { S.metaform = $('#mf').value; loadMetaform(); };

async function main() {
  const response = await fetch('/api/projects');
  S.projects = (await response.json()).projects || [];
  if (!S.projects.length) {
    fill($('#p-object'), h('p', {class: 'empty'}, 'No project is registered. Register one with: metaform add project <id> <path>'));
    return;
  }
  const wanted = new URLSearchParams(location.hash.slice(1)).get('p');
  S.project = S.projects.some(item => item.id === wanted) ? wanted : S.projects[0].id;
  fill($('#proj'), ...S.projects.map(item => h('option', {value: item.id, selected: item.id === S.project}, item.id)));
  start3D();
  await loadProject();
  listen();
}
main();
