/* Metaform's web GUI, the viewer: the whole map in 3D and in 2D, kept in sync, and the selected object below.
 * Every piece of data comes from the server's reads, VIEW-004; the page never decides what is visible. Text from the
 * store is always set as text, never as HTML, VIEW-009. */
'use strict';

// three.js, for the glass the nodes are made of, VIEW-025. It is the release the graph library holds and does not
// give out, carried in vendor/ so the page loads nothing from outside itself, VIEW-003.
import * as THREE from '/vendor/three.module.min.js';

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
  if (!$('#clearbox').hidden && !event.target.closest('.clearpick')) showClear(false);
});

/* ---------- clearing the project: what goes and what stays, asked on the page, VIEW-019 ----------
 * The warning is the command's own caution and the clear is the command's own operation, PROJ-025; every open page,
 * this one among them, follows it by the push, VIEW-018. */
function showClear(open) {
  $('#clearbox').hidden = !open;
  $('#clearBtn').setAttribute('aria-expanded', String(open));
}
/* Export saves the map as the short Markdown document the command writes, MAP-052 and VIEW-024. */
$('#exportBtn').onclick = async () => {
  const query = new URLSearchParams({project: S.project, ...(S.metaform ? {metaform: S.metaform} : {}), ...viewLayers()});
  const response = await fetch(`/api/markdown?${query}`);
  if (!response.ok) return toast((await response.json().catch(() => ({}))).error || 'The map could not be exported.');
  const link = h('a', {href: URL.createObjectURL(new Blob([await response.text()], {type: 'text/markdown'})),
    download: `${S.project}-map.md`});
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
};
$('#clearBtn').onclick = async event => {
  event.stopPropagation();
  if (!$('#clearbox').hidden) return showClear(false);
  let found;
  try { found = await getJson(`/api/clear-preview?project=${encodeURIComponent(S.project)}`); }
  catch (error) { return toast(error.message); }
  fill($('#clearbox'), h('div', {class: 'warn'}, h('b', {}, `Clear ${found.project}?`), h('span', {}, found.caution),
    h('div', {class: 'toolbar'},
      h('button', {class: 'btn danger confirm', onclick: () => clearProject(found.project)}, 'Clear it'),
      h('button', {class: 'btn keep', onclick: () => showClear(false)}, 'Keep it'))));
  showClear(true);
};
async function clearProject(project) {
  const response = await fetch('/api/clear-project', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({project, confirm: true})});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) { showClear(false); return toast(body.error || 'The project was not cleared.'); }
  const left = body.not_removed || [];
  fill($('#clearbox'), h('div', {class: 'warn'}, h('span', {class: 'said'}, body.said),
    left.length ? [h('b', {}, 'Not removed, still on disk:'),
      h('ul', {class: 'left'}, left.map(item => h('li', {}, `${item.path}: ${item.reason}`)))] : null,
    (body.notices || []).map(notice => h('span', {class: 'next'}, notice.message)),
    h('div', {class: 'toolbar'}, h('button', {class: 'btn keep', onclick: () => showClear(false)}, 'Close'))));
}
/* After a clear the project has no metaform until the next intake, or anything else written to it, makes one. */
const noMetaform = () => !S.metaforms.length;
const noneYet = () => `${S.project} has no metaform yet. The next intake creates one.`;
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
      role: element.role, work: element.open_work || [], layer: element.layer});
    if (parent && byAddress.has(parent)) links.push({source: byAddress.get(parent), target: element.element_id, k: 'tree'});
  }
  const ids = new Set(nodes.map(node => node.id));
  for (const join of S.joins) {
    if (!ids.has(join.receiver) || !ids.has(join.provider)) continue;
    const purpose = 'p:' + join.join_id;
    nodes.push({id: purpose, t: 'purpose', join: join.join_id, layer: join.layer, work: join.open_work || []});
    links.push({source: join.receiver, target: purpose, k: 'purpose', layer: join.layer, join: join.join_id,
      work: join.open_work || []});
    links.push({source: purpose, target: join.provider, k: 'encounter', layer: join.layer, join: join.join_id,
      ef: join.ef, work: join.open_work || []});
    for (const subtype of join.subtypes || []) {
      nodes.push({id: 's:' + subtype.join_id, t: 'sub', join: join.join_id, layer: subtype.layer,
        name: subtype.short_name || subtype.address, joinName: subtype.name, work: subtype.open_work || []});
      links.push({source: purpose, target: 's:' + subtype.join_id, k: 'layer', layer: subtype.layer, join: join.join_id,
        ef: subtype.ef, work: join.open_work || []});
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
/* A selection is an element's id, a subtype as 's:<id>' by its subtype join's id, or a join as 'p:<id>', the same
 * keys the 3D view uses. The element a subtype join holds is no node of the outer map, MAP-031, so what is attached to
 * it is shown at its subtype, `heldBy`. */
const subtypeOf = new Map(), heldBy = new Map();
function indexSubtypes() {
  subtypeOf.clear();
  heldBy.clear();
  for (const join of S.joins) for (const subtype of join.subtypes || []) {
    subtypeOf.set('s:' + subtype.join_id, {subtype, join});
    if (!heldBy.has(subtype.element_id)) heldBy.set(subtype.element_id, 's:' + subtype.join_id);
  }
}
const accessed = (value, item) => typeof value === 'function' ? value(item) : value;
const joinOf = key => S.joins.find(join => 'p:' + join.join_id === key);
window.metaform = {graph: () => graphData(), selected: () => S.selected, select: id => select(id, true),
  click3d: id => clicked3d(G?.graphData().nodes.find(node => node.id === id)),
  drawn: () => G ? {nodes: G.graphData().nodes.length, links: G.graphData().links.length} : null,
  curves: () => G ? G.graphData().links.map(link => ({k: link.k, curve: accessed(G.linkCurvature(), link)})) : [],
  linkColors: () => G ? G.graphData().links.map(link => ({join: link.join || null, k: link.k,
    target: link.target?.id ?? link.target, color: linkColor(link)})) : [],
  loaded: () => !S.loading, editor: () => P.editor, live: () => LIVE.layer,
  inside: () => IN.length && M.drawn === IN.at(-1) ? [...M.nodes.keys()] : [], vertical: () => M.vertical,
  look: id => look(id), fit: () => fit2D(), menu: id => menu(id),
  away3d: () => G ? G.camera().position.distanceTo(G.controls().target) : 0,
  zoom3d: share => { if (G) { const at = G.camera().position; G.cameraPosition({x: at.x * share, y: at.y * share, z: at.z * share}, undefined, 0); } },
  glass: (on, options = {}, segments = 16) => {  // to measure what it costs
    if (!G) return;
    Object.assign(GLASS, options);
    SEGMENTS = segments;
    shapes.clear();
    G.nodeThreeObject(node => asText(node) ? written(node) : on && isGlass(node) ? bead(node) : false);
  }, bloom: () => ({pass: Boolean(BLOOM), levels: BLOOM ? BLOOM.levels : 0}),
  wave: () => ({dots: W.dots.length, shapes: G ? G.renderer().info.memory.geometries : 0,
    lit: G ? G.graphData().nodes.filter(node => node.__threeObj?.children.some(child => child.userData.pulse)).map(node => node.id) : []}),
  waveTimes: times => { Object.assign(TIMES, times, {gaussian: times.gaussian === false ? [] : times.gaussian || TIMES.gaussian}); W.next = W.clock; },
  reach: () => ({property: R.key, edges: R.edges,
    elements: [...S.elements.values()].map(entry => entry.element).filter(element => R.nodes.has(element.element_id)).map(element => element.address)}),
  own: id => { const node = G ? G.graphData().nodes.find(item => item.id === id) : null; return node ? ownColor(node).toLowerCase() : null; },
  box2d: id => { const box = M.nodes.get(id)?.g.getBoundingClientRect(); return box ? {left: box.left, right: box.right, top: box.top, bottom: box.bottom} : null; },
  edge2d: join => [...(M.base?.edges.find(edge => edge.join.join_id === join)?.path?.classList || [])]
    .filter(name => name.startsWith('work-')),
  ground: () => G ? G.backgroundColor() : null};

/* How a node is drawn for its condition, MAP-046, readable by a browser check: its open work, the 2D group's work
 * classes, computed opacity and whether its box is animating, and the 3D sphere's material opacity and whether it is
 * red at this frame. */
const toHex = color => { const found = (color || '').match(/\d+/g);
  return found ? '#' + found.slice(0, 3).map(part => Number(part).toString(16).padStart(2, '0')).join('') : null; };
function look(id) {
  const node = G ? G.graphData().nodes.find(item => item.id === id) : null;
  const group = (M.base?.nodes.get(id) || M.nodes.get(id))?.g || null;
  const box = group?.querySelector('rect') || null;
  const material = node?.__threeObj?.material || null;
  return {work: node?.work || [], classes: group ? [...group.classList].filter(name => name.startsWith('work-')) : [],
    opacity2d: group ? Number(getComputedStyle(group).opacity) : null,
    animated2d: box ? getComputedStyle(box).animationName !== 'none' || getComputedStyle(group).animationName !== 'none' : false,
    opacity3d: material ? material.opacity : null,
    light3d: material ? material.emissiveIntensity ?? null : null,
    text3d: Boolean(node?.__threeObj?.userData.written),  // until the node itself is drawn in its place
    turns: writing.get(id)?.rate ?? 0,
    text: textOf(id), signal3d: writing.get(id)?.reached ?? 0, signalColor3d: writing.get(id)?.signalColor ?? null,
    glow2d: Boolean(box) && ['broken', 'fixing', 'cruft', 'question', 'message'].some(name => group.classList.contains('work-' + name))
      && [group, box].some(part => getComputedStyle(part).filter.includes('drop-shadow')),
    red3d: material ? '#' + material.color.getHexString() === css('--broken').toLowerCase() : false,
    material: material ? material.type : null, transmission: material ? material.transmission || 0 : 0,
    shape: node?.__threeObj?.geometry ? node.__threeObj.geometry.uuid : null,
    bloom3d: Boolean(node?.__threeObj?.children.some(child => child.userData.bloom)) && !node.__threeObj.userData.light,
    glow3d: node?.__threeObj?.userData.glow ?? 0,
    reach3d: R.nodes.has(id), reach2d: Boolean(group?.classList.contains('reach')),

    bloom2d: Boolean(box && getComputedStyle(group).filter.includes('drop-shadow')),
    color3d: material ? '#' + material.color.getHexString() : null,
    label3d: [...(tags.get(id)?.classList || [])].filter(name => name.startsWith('work-')),
    stroke2d: box ? toHex(getComputedStyle(box).stroke) : null,
    cruft3d: material ? '#' + material.color.getHexString() === css('--cruft').toLowerCase() : false};
}

/* ---------- 3D: a synaptic map, drawn as the approved prototype draws it ---------- */
const CONDITIONS = ['tbd', 'in-progress', 'broken', 'fixing', 'cruft', 'question', 'message'];
const has = (node, condition) => (node.work || []).includes(condition);
function colorOf(node) {
  if (node.t === 'el') return has(node, 'cruft') ? css('--cruft') : node.role === 'VE' ? css('--signal')
    : node.role === 'DE' ? css('--de') : layerColor(node.layer);
  if (has(node, 'cruft')) return css('--cruft');
  if (node.t === 'purpose') return css('--text');
  return layerColor(node.layer);
}
/* The color an object has apart from any condition, which a cruft record pulses against. */
const ownColor = node => colorOf({...node, work: []});
/* A dimmed node keeps its own hue: its color with part of the background mixed in, the share set by the theme. */
function dim(color) {
  const keep = Number(css('--dim-keep')), channels = hex => [1, 3, 5].map(at => parseInt(hex.slice(at, at + 2), 16));
  const back = channels(css('--ground'));
  return '#' + channels(color).map((own, at) => Math.round(keep * own + (1 - keep) * back[at]).toString(16).padStart(2, '0')).join('');
}
const dimmed = node => S.selected && node.t === 'el' && node.id !== S.selected && !S.neighbors.has(node.id);
/* Light drawn around a node: added to what is behind it, and seen from every side. It is plain light and never
 * glass, whatever the node it surrounds is made of. */
const lightOf = opacity => new THREE.MeshBasicMaterial({transparent: true, opacity, blending: THREE.AdditiveBlending,
  depthWrite: false, side: THREE.BackSide, toneMapped: false});
/* A node's color, given to whatever it is made of: glass takes it as its tint, as the color light takes on inside
 * it, and as the light it gives off. */
function colored(material, color) {
  material.color.set(color);
  if (material.isMeshPhysicalMaterial) { material.attenuationColor.set(color); material.emissive.set(color); }
}
/* Glass, VIEW-025: in every theme an element is made of a material that obeys reality. Light passes through it and
 * is tinted by it, so the theme's background shows through the node. It gives off a little of its own color, since
 * clear glass on a dark background with nothing to reflect shows as black. One shape serves every node of a size. */
const GLASS = {transmission: 0.7, thickness: 9, roughness: 0.3, ior: 1.35, attenuationDistance: 7, clearcoat: 0.6,
  clearcoatRoughness: 0.25, emissiveIntensity: 0.45, metalness: 0};
const shapes = new Map();
let SEGMENTS = 16;  // as the graph draws its own nodes; 32 halves the frame rate where there is no graphics card
const isGlass = node => node.t === 'el' || node.t === 'sub';
function bead(node) {
  const radius = Math.cbrt(nodeSize(node)) * 3;  // as the graph sizes a node: the cube root of its value, times 3
  if (!shapes.has(radius)) shapes.set(radius, new THREE.SphereGeometry(radius, SEGMENTS, SEGMENTS));
  const material = new THREE.MeshPhysicalMaterial(GLASS);
  material.userData.own = true;
  colored(material, colorOf(node));
  return new THREE.Mesh(shapes.get(radius), material);
}
/* The circles around a part that needs building, VIEW-005: three shells around the sphere in its own color, each
 * larger and fainter, lit additively, so the node glows and keeps its color and opacity. They are steady while the
 * part waits and pulsate once an agent has taken its task. The shells are made from the sphere's own geometry and
 * material, since the graph library holds the 3D classes. */
const SHELLS = [[1.8, 0.5], [2.8, 0.28], [4.2, 0.14]];
const pulse = () => reduced() ? 1 : 0.95 + 0.6 * Math.sin(performance.now() / 1600 * 2 * Math.PI);
function bloom3d(object, strength, color) {
  const shells = object.children.filter(child => child.userData.bloom);
  object.userData.glow = strength;
  if (!strength) { for (const shell of shells) object.remove(shell); return; }
  if (!shells.length) for (const [scale, opacity] of SHELLS) {
    const shell = object.clone(false);
    shell.material = lightOf(opacity);
    shell.position.set(0, 0, 0);
    shell.scale.setScalar(scale);
    shell.userData.bloom = true;
    shell.userData.opacity = opacity;
    object.add(shell);
  }
  for (const shell of object.children) if (shell.userData.bloom) {
    shell.material.color.set(color);
    shell.material.opacity = shell.userData.opacity * strength;
  }
}

/* A property's reach, VIEW-022 and VIEW-026. Clicking a property node sends a wave out from the element it is linked
 * to, toward the leaves where it applies and toward the trunk where it is visible. A dot travels each namespace edge
 * away from that element; a node pulses when a dot arrives, holds it, and sends it on. The dots carry the property's
 * color and give off light at more than full brightness, which the bloom pass spreads; the edges keep their own
 * look. Selecting anything else puts the map back. */
const R = {key: null, color: null, home: null, nodes: new Set(), edges: 0};
const endOf = end => end?.id ?? end;
const inReach = link => R.key && link.k === 'tree' && R.nodes.has(endOf(link.source)) && R.nodes.has(endOf(link.target));
/* The wave's times in seconds, chosen by eye and not settled, VIEW-026: how often a wave leaves, how long a dot takes
 * to cross an edge, which is the same for every edge since an edge's length on screen carries no meaning, and how
 * long a node holds a dot, which is how long it pulses. `gaussian` names the timers multiplied by rnd + rnd each time
 * they are used: that runs from 0 to 2 and is 1 on average, so a timer averages its time and never repeats.
 * `opacity` is how much a node tints the light passing through it; the node is drawn solid whatever it is. */
const TIMES = {every: 3, cross: 1, hold: 0.25, opacity: 0.6, gaussian: ['every']};
const timed = name => TIMES[name] * (TIMES.gaussian.includes(name) ? Math.random() + Math.random() : 1);
const W = {clock: 0, last: 0, next: 0, dots: [], held: [], pulses: new Map(), glows: new Map()};
function setReach(key) {
  const thing = key?.startsWith('r:') ? S.items.get(key) : null;
  const home = thing ? [...S.elements.values()].find(entry => entry.element.element_id === thing.item.element_id)?.element : null;
  if (!home && !R.key) return;
  R.key = home ? key : null;
  R.color = home ? layerColor(thing.layer) : null;
  R.home = home ? home.element_id : null;
  R.nodes = new Set(home ? [...S.elements.values()].map(entry => entry.element)
    .filter(({address}) => address === home.address || home.address.startsWith(address + '.') || address.startsWith(home.address + '.'))
    .map(element => element.element_id) : []);
  R.edges = G ? G.graphData().links.filter(inReach).length : 0;
  if (BLOOM) BLOOM.enabled = Boolean(R.key) || T.signaled;
  for (const dot of W.dots) G.scene().remove(dot.mesh);
  if (G) for (const node of G.graphData().nodes) pulse3d(node, 0);  // no node is left lit
  Object.assign(W, {dots: [], held: [], next: W.clock, pulses: new Map()});
  if (G) G.nodeColor(G.nodeColor());  // every node back to its own color
  for (const [id, node] of M.base?.nodes || []) {
    node.g.classList.toggle('reach', R.nodes.has(id));
    node.g.style.setProperty('--reach', R.color || '');
  }
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
const colorFrom = parts => '#' + parts.map(part => Math.round(Math.min(1, Math.max(0, part)) * 255).toString(16).padStart(2, '0')).join('');
/* A dot arrives: the node pulses for as long as it holds the dot, then sends it on. */
function reached(id, from, outward) {
  const hold = Math.max(0.017, timed('hold'));
  W.pulses.set(id, {start: W.clock, length: hold});
  W.held.push({at: W.clock + hold, id, from, outward});
}
/* From the element the property is linked to the wave goes both ways; past it, it keeps its way, on toward the
 * leaves or on toward the trunk, and never out along a branch the property does not reach. */
function send(data, id, from, outward) {
  const template = data.nodes.find(node => node.id === id)?.__threeObj;
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
    W.dots.push({mesh, link, back: up, to, from: id, outward: down, start: W.clock, length: Math.max(0.034, timed('cross'))});
  }
}
/* The pulse through a node, VIEW-026. Its depth is 0 as the dot enters, 1 at the node's center and 0 as it leaves.
 * The node tints the pulse as colored glass tints light; its body moves from its own color toward that tinted color
 * by the depth, and the glow is the body's own color and brightness, so the two are never apart. */
function pulse3d(node, depth) {
  const object = node.__threeObj;
  if (!object || !object.material || object.userData.written) return;  // text glows by itself, VIEW-027
  let shell = object.children.find(child => child.userData.pulse);
  if (!depth) {
    if (shell) { object.remove(shell); shell.material.dispose(); }
    if (object.material.userData.pulsed) { colored(object.material, colorOf(node)); object.material.userData.pulsed = false; }
    return;
  }
  const own = channels(ownColor(node)), light = channels(R.color);
  const body = own.map((part, at) => part + (light[at] * (1 - TIMES.opacity + TIMES.opacity * part) - part) * depth);
  if (!object.material.userData.own) { object.material = object.material.clone(); object.material.userData.own = true; }
  colored(object.material, colorFrom(body));
  object.material.userData.pulsed = true;
  if (!shell) {
    shell = object.clone(false);
    shell.material = lightOf(0);
    shell.position.set(0, 0, 0);
    shell.scale.setScalar(1.5);
    shell.userData.pulse = true;
    object.add(shell);
  }
  shell.material.color.set(colorFrom(body)).multiplyScalar(1 + 1.6 * depth);  // the body's own color, as light
  shell.material.opacity = 0.6 * depth;
}
function wave3d(data) {
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
  for (const node of data.nodes) {
    if (!R.nodes.has(node.id)) continue;
    const pulse = W.pulses.get(node.id), gone = pulse ? (W.clock - pulse.start) / pulse.length : 2;
    pulse3d(node, gone >= 0 && gone <= 1 ? Math.sin(Math.PI * gone) : 0);
  }
}
/* The bloom pass, added to the graph's own render chain: what is over full brightness is kept in its hue, blurred at
 * a half, a quarter and an eighth of the size, and added to the picture. It runs only while a property's reach is
 * lit, so the map with nothing lit is drawn exactly as it is without the pass. It is built from the classes of the objects
 * the chain already holds, since the graph library keeps its 3D classes to itself and the page loads nothing else. */
let BLOOM = null;
function addBloom() {
  const composer = G.postProcessingComposer(), copy = composer?.copyPass;
  if (!copy || !composer.renderTarget1) return;
  const Target = composer.renderTarget1.constructor, Material = copy.material.constructor, Quad = copy.fsQuad.constructor;
  const vertex = 'varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }';
  const shader = (fragmentShader, uniforms) => new Material({uniforms, vertexShader: vertex, fragmentShader, depthTest: false, depthWrite: false});
  const over = shader(`uniform sampler2D tDiffuse; varying vec2 vUv;
    void main() { vec3 c = texture2D(tDiffuse, vUv).rgb; float top = max(c.r, max(c.g, c.b));
      gl_FragColor = vec4(top > 1.0 ? c * (1.0 - 1.0 / top) : vec3(0.0), 1.0); }`, {tDiffuse: {value: null}});
  const blur = shader(`uniform sampler2D tDiffuse; uniform vec2 along; varying vec2 vUv;
    void main() { vec3 sum = texture2D(tDiffuse, vUv).rgb * 0.227027;
      sum += (texture2D(tDiffuse, vUv + along * 1.0).rgb + texture2D(tDiffuse, vUv - along * 1.0).rgb) * 0.1945946;
      sum += (texture2D(tDiffuse, vUv + along * 2.0).rgb + texture2D(tDiffuse, vUv - along * 2.0).rgb) * 0.1216216;
      sum += (texture2D(tDiffuse, vUv + along * 3.0).rgb + texture2D(tDiffuse, vUv - along * 3.0).rgb) * 0.054054;
      sum += (texture2D(tDiffuse, vUv + along * 4.0).rgb + texture2D(tDiffuse, vUv - along * 4.0).rgb) * 0.016216;
      gl_FragColor = vec4(sum, 1.0); }`, {tDiffuse: {value: null}, along: {value: [0, 0]}});
  // The background arrives as the color the screen shows; what is drawn over it arrives as light.
  const mix = shader(`uniform sampler2D tDiffuse; uniform sampler2D near; uniform sampler2D mid; uniform sampler2D far;
    uniform float strength; uniform vec3 ground; varying vec2 vUv;
    void main() { vec4 base = texture2D(tDiffuse, vUv);
      vec3 glow = texture2D(near, vUv).rgb + texture2D(mid, vUv).rgb * 1.2 + texture2D(far, vUv).rgb * 1.4;
      // What is drawn over the background is taken apart from it before it is made ready for the screen, so a glow
      // fades into the background itself and not into a grey.
      vec3 light = clamp(base.rgb - ground, 0.0, 1.0);
      vec3 shown = ground + linearToOutputTexel(vec4(light, 1.0)).rgb;
      gl_FragColor = vec4(shown + strength * linearToOutputTexel(vec4(glow, 1.0)).rgb, base.a);
    }`, {tDiffuse: {value: null}, near: {value: null}, mid: {value: null}, far: {value: null}, strength: {value: 0.8},
    ground: {value: [0, 0, 0]}});
  const quad = new Quad(over), type = composer.renderTarget1.texture.type;
  const levels = [2, 4, 8].map(() => ({across: new Target(1, 1, {type}), down: new Target(1, 1, {type})}));
  const draw = (renderer, material, target) => { quad.material = material; renderer.setRenderTarget(target); quad.render(renderer); };
  BLOOM = {isPass: true, enabled: false, needsSwap: true, clear: false, renderToScreen: false, levels: levels.length,
    setSize(width, height) {
      levels.forEach((level, index) => {
        const size = [Math.max(1, Math.round(width / 2 ** (index + 1))), Math.max(1, Math.round(height / 2 ** (index + 1)))];
        level.across.setSize(...size); level.down.setSize(...size);
      });
    },
    render(renderer, writeBuffer, readBuffer) {
      let from = readBuffer.texture;
      levels.forEach((level, index) => {
        if (index === 0) { over.uniforms.tDiffuse.value = from; draw(renderer, over, level.down); from = level.down.texture; }
        blur.uniforms.tDiffuse.value = from; blur.uniforms.along.value = [1 / level.across.width, 0];
        draw(renderer, blur, level.across);
        blur.uniforms.tDiffuse.value = level.across.texture; blur.uniforms.along.value = [0, 1 / level.down.height];
        draw(renderer, blur, level.down);
        from = level.down.texture;
      });
      mix.uniforms.tDiffuse.value = readBuffer.texture;
      mix.uniforms.ground.value = [1, 3, 5].map(at => parseInt(css('--ground').slice(at, at + 2), 16) / 255);
      [mix.uniforms.near.value, mix.uniforms.mid.value, mix.uniforms.far.value] = levels.map(level => level.down.texture);
      draw(renderer, mix, this.renderToScreen ? null : writeBuffer);
    },
    dispose() { for (const level of levels) { level.across.dispose(); level.down.dispose(); } }};
  composer.addPass(BLOOM);
}
/* A part not built yet is drawn in characters, VIEW-027: text floating where its node will be, which is the one mark
 * of it. The characters are the numbers and the letters in both cases, made at random and all made again at each
 * turn. They give the ball its shape by their weight, which is how much ink a character puts down: the heavy ones
 * where the ball is bright, the light ones where it is dark, toward the rim. Nothing is colored to make the shape.
 * How fast the text changes says how far the work is: slow while the part waits, quickening once an agent has taken
 * it. When the part is built the text speeds up to a blur, the node fades in over it and the text fades away. A
 * signal reaching the text makes it glow in the signal's color, and the glow swells and fades. The values are
 * chosen by eye and are not settled. */
const LETTERS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';
const TEXT = {size: 10, waiting: 1.5, first: 2.5, top: 10, fastest: 30, hold: 0.85, climb: 60, light: 2.4,
  speedUp: 3, fadeIn: 2, fadeOut: 1.2, near: 1.6, far: 0.7};
const T = {letters: null, strokes: null, order: LETTERS, cell: {value: new THREE.Vector2(6, 12)},
  screen: {value: new THREE.Vector2(1, 1)}, zoom: {value: 1}, light: {value: TEXT.light}, away: 0, last: 0,
  signaled: false, rows: new Map()};
const writing = new Map();  // what is being written, by node id, kept while the map is drawn again
const unbuilt = node => has(node, 'tbd') || has(node, 'in-progress');
const asText = node => unbuilt(node) || writing.has(node.id);
const FACE = '500 48px "IBM Plex Mono", ui-monospace, monospace', WIDE = 30, HIGH = 60;
function weightOf(letter) {
  const canvas = document.createElement('canvas');
  canvas.width = 40; canvas.height = 64;
  const pen = canvas.getContext('2d', {willReadFrequently: true});
  pen.fillStyle = 'white'; pen.font = FACE; pen.textAlign = 'center'; pen.textBaseline = 'middle';
  pen.fillText(letter, 20, 32);
  const painted = pen.getImageData(0, 0, 40, 64).data;
  let sum = 0;
  for (let at = 3; at < painted.length; at += 4) sum += painted[at];
  return sum;
}
/* A strip of characters, painted large so the graphics card scales them with smooth edges. */
function strip(texture, text) {
  const canvas = texture.image;
  canvas.width = WIDE * text.length; canvas.height = HIGH;
  const pen = canvas.getContext('2d');
  // Black and white here are not colors of the page: the strip is a mask, read for how much a stroke covers.
  pen.fillStyle = 'black'; pen.fillRect(0, 0, canvas.width, canvas.height);
  pen.fillStyle = 'white'; pen.font = FACE; pen.textAlign = 'center'; pen.textBaseline = 'middle';
  [...text].forEach((letter, index) => pen.fillText(letter, WIDE * (index + 0.5), HIGH / 2 + 1));
  texture.needsUpdate = true;
}
function letters() {
  const weights = new Map([...LETTERS].map(letter => [letter, weightOf(letter)]));
  T.order = [...LETTERS].sort((one, two) => weights.get(one) - weights.get(two)).join('');  // lightest first
  strip(T.letters, T.order);
  strip(T.strokes, '-/|\\');
}
function ready() {
  if (T.letters) return;
  T.letters = new THREE.CanvasTexture(document.createElement('canvas'));
  T.strokes = new THREE.CanvasTexture(document.createElement('canvas'));
  letters();
  document.fonts.load(FACE).then(letters, () => {});  // painted again once the face is there
}
const PLACED = `uniform float radius; uniform vec2 screen; uniform vec2 cell; uniform float zoom;
  varying vec2 vMiddle; varying float vReach;
  void main() {
    vec4 center = modelViewMatrix * vec4(0.0, 0.0, 0.0, 1.0);
    float reach = radius * length(modelViewMatrix[0].xyz);
    vec4 middle = projectionMatrix * center, edge = projectionMatrix * (center + vec4(reach, 0.0, 0.0, 0.0));
    vMiddle = middle.xy / middle.w;
    vReach = edge.x / edge.w - vMiddle.x;
    // Room for the whole of the last cells, and from far away for the few characters a part still holds.
    float room = 1.6 * max(1.0, 5.0 * cell.x * zoom / screen.x / max(vReach, 0.0001));
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position * room, 1.0);
  }`;
const DRAWN = `uniform sampler2D letters; uniform sampler2D cells; uniform vec2 screen; uniform vec2 cell;
  uniform float zoom; uniform vec3 ink; uniform vec3 signal; uniform float reached; uniform float seen;
  uniform float light;
  varying vec2 vMiddle; varying float vReach;
  void main() {
    vec2 size = cell * zoom;
    vec2 which = floor(gl_FragCoord.xy / size), within = fract(gl_FragCoord.xy / size);
    vec2 middle = (which + 0.5) * size / screen * 2.0 - 1.0;
    float wide = max(vReach, 5.0 * size.x / screen.x);                 // from far away a part still holds a few characters
    vec2 off = (middle - vMiddle) / vec2(wide, wide * screen.x / screen.y);
    float out2 = dot(off, off);
    if (out2 > 1.0) discard;
    vec3 normal = vec3(off, sqrt(1.0 - out2));
    float facing = clamp(dot(normal, normalize(vec3(0.45, 0.6, 0.66))) * 0.8 + 0.2, 0.0, 1.0);
    // Each cell is handed a number made at random by the page, new at each turn, so every graphics card shows the
    // same. The character is picked by weight around the ball's brightness there, and stays random within it.
    float got = texture2D(cells, (mod(which, 32.0) + 0.5) / 32.0).r;
    float weighed = clamp(facing + (got - 0.5) * 0.45, 0.0, 0.999);
    float letter = min(61.0, floor(weighed * 62.0));
    // The size of a character on the screen is given to the lookup; left to guess it, the graphics card reads a
    // smeared copy at a cell's border.
    vec2 stepX = vec2(1.0 / size.x, 0.0), stepY = vec2(0.0, 1.0 / size.y);
    float mark = textureGrad(letters, vec2((letter + within.x) / 62.0, within.y), stepX / 62.0, stepY).r;
    float cover = clamp(mark * 1.25, 0.0, 1.0);                        // smooth at any size
    if (cover < 0.02) discard;                                         // the characters float: nothing is behind them
    gl_FragColor = vec4(mix(ink, signal, reached * 0.85) * (1.15 + light * reached), seen * cover);
  }`;
function written(node) {
  ready();
  const radius = Math.cbrt(nodeSize(node)) * 3;
  if (!shapes.has(radius)) shapes.set(radius, new THREE.SphereGeometry(radius, SEGMENTS, SEGMENTS));
  let state = writing.get(node.id);
  if (!state) {
    const cells = new THREE.DataTexture(new Uint8Array(1024).map(() => Math.floor(Math.random() * 256)), 32, 32, THREE.RedFormat);
    cells.needsUpdate = true;
    state = {level: 0, tick: 0, wrote: 0, rate: TEXT.waiting, ending: null, cells, reached: 0, signalColor: null,
      seen: {value: 1}, glow: {value: 0}, signal: {value: new THREE.Color(1, 1, 1)}};
    writing.set(node.id, state);
  }
  const ink = new THREE.Color(ownColor(node));
  const material = new THREE.ShaderMaterial({vertexShader: PLACED, fragmentShader: DRAWN, transparent: true, depthWrite: false,
    uniforms: {letters: {value: T.letters}, cells: {value: state.cells}, screen: T.screen, cell: T.cell, zoom: T.zoom,
      ink: {value: ink}, signal: state.signal, reached: state.glow, seen: state.seen, light: T.light, radius: {value: radius}}});
  material.color = new THREE.Color(ownColor(node));  // the page colors a node through its material's color
  material.userData.own = true;
  const mesh = new THREE.Mesh(shapes.get(radius), material);
  mesh.userData.written = true;
  // The node itself, which fades in over the text when the part is built.
  const arriving = isGlass(node) ? bead({...node, work: []})
    : new THREE.Mesh(shapes.get(radius), new THREE.MeshLambertMaterial({color: ownColor(node)}));
  Object.assign(arriving.material, {transparent: true, opacity: 0});
  arriving.visible = false;
  arriving.userData.arriving = true;
  mesh.add(arriving);
  return mesh;
}
/* An edge of a part not built is a row of characters floating along it, each the one that slopes as the edge does on
 * the screen, as lines are drawn in text. */
const DOTS = 40;
function row() {
  const shape = new THREE.BufferGeometry();
  shape.setAttribute('position', new THREE.BufferAttribute(new Float32Array(DOTS * 3), 3));
  const made = new THREE.Points(shape, new THREE.ShaderMaterial({transparent: true, depthWrite: false,
    uniforms: {strokes: {value: T.strokes}, which: {value: 0}, cell: T.cell, zoom: T.zoom, ink: {value: new THREE.Color()}},
    vertexShader: `uniform vec2 cell; uniform float zoom;
      void main() { gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); gl_PointSize = cell.y * zoom; }`,
    // A point is square and a cell is taller than it is wide, so the character is drawn in the middle of the point.
    fragmentShader: `uniform sampler2D strokes; uniform float which; uniform vec3 ink; uniform vec2 cell;
      void main() { float across = (gl_PointCoord.x - 0.5) * cell.y / cell.x + 0.5;
        if (across < 0.0 || across > 1.0) discard;
        float cover = clamp(texture2D(strokes, vec2((which + across) / 4.0, 1.0 - gl_PointCoord.y)).r * 1.25, 0.0, 1.0);
        if (cover < 0.02) discard;
        gl_FragColor = vec4(ink * 1.15, cover); }`}));
  made.frustumCulled = false;
  return made;
}
function rows3d(data) {
  const live = new Set();
  const textOf = end => typeof end === 'object' && end.__threeObj?.userData.written && writing.get(end.id)?.ending === null;
  for (const link of data.links) {
    const from = link.source, to = link.target, line = link.__lineObj;
    if (!line || from?.x === undefined || to?.x === undefined) continue;
    // A join's links are drawn in characters. A namespace edge and a layer's links stay thin lines, since they are
    // many and dim, and rows of characters along all of them cover the map.
    const joined = link.k === 'purpose' || link.k === 'encounter';
    if (!joined || (!textOf(from) && !textOf(to))) { if (link.rowed) { line.visible = true; link.rowed = false; } continue; }
    live.add(link);
    let made = T.rows.get(link);
    if (!made) { made = row(); T.rows.set(link, made); G.scene().add(made); }
    line.visible = false;
    link.rowed = true;
    made.material.uniforms.ink.value.set(linkColor(link));
    const one = G.graph2ScreenCoords(from.x, from.y, from.z), two = G.graph2ScreenCoords(to.x, to.y, to.z);
    const long = Math.hypot(two.x - one.x, two.y - one.y), size = TEXT.size * 1.1 * T.zoom.value;
    const count = Math.max(2, Math.min(DOTS, Math.floor(long * 0.8 / size)));
    const turn = ((Math.atan2(-(two.y - one.y), two.x - one.x) * 180 / Math.PI) % 180 + 180) % 180;  // 0 to 180 degrees
    made.material.uniforms.which.value = turn < 22.5 || turn >= 157.5 ? 0 : turn < 67.5 ? 1 : turn < 112.5 ? 2 : 3;
    // The row runs from the edge of one node to the edge of the other, so it never crosses a node's own characters.
    const whole = Math.max(1, Math.hypot(to.x - from.x, to.y - from.y, to.z - from.z));
    const clear = end => Math.min(0.45, Math.cbrt(nodeSize(end)) * 3 * 1.2 / whole);
    const begin = clear(from), end = 1 - clear(to), places = made.geometry.attributes.position;
    for (let at = 0; at < DOTS; at++) {
      const along = begin + (end - begin) * (Math.min(at, count - 1) + 0.5) / count;
      places.setXYZ(at, from.x + (to.x - from.x) * along, from.y + (to.y - from.y) * along, from.z + (to.z - from.z) * along);
    }
    places.needsUpdate = true;
  }
  for (const [link, made] of T.rows) if (!live.has(link)) {
    G.scene().remove(made); made.geometry.dispose(); made.material.dispose(); T.rows.delete(link);
  }
}
const WHITE = new THREE.Color(1, 1, 1);
const SIGNALS = [['broken', '--broken'], ['fixing', '--broken'], ['cruft', '--cruft'], ['question', '--question'],
  ['message', '--question']];
function text3d() {
  const now = performance.now() / 1000, passed = Math.min(0.1, Math.max(0, now - (T.last || now)));
  T.last = now;
  if (!writing.size) { if (T.rows.size) rows3d(G.graphData()); T.signaled = false; return; }
  const ratio = G.renderer().getPixelRatio();
  G.renderer().getDrawingBufferSize(T.screen.value);
  T.cell.value.set(TEXT.size * 0.62 * ratio, TEXT.size * 1.25 * ratio);
  const away = G.camera().position.distanceTo(G.controls().target);
  if (!T.away) T.away = away;
  T.zoom.value = Math.min(TEXT.near, Math.max(TEXT.far, T.away / away));  // the characters follow the zoom a little
  let finished = false, signaled = false;
  const shown = new Set();
  for (const node of G.graphData().nodes) {
    const state = writing.get(node.id), object = node.__threeObj;
    if (!state) continue;
    shown.add(node.id);
    if (!object?.userData.written) continue;
    const working = has(node, 'in-progress'), climbed = () => TEXT.first + (TEXT.top - TEXT.first) * Math.pow(state.level, 1.4);
    if (!unbuilt(node) && state.ending === null) state.ending = 0;   // it is built: the ending starts from where it is
    if (state.ending === null) {
      // Work with no phases to report climbs by itself, slowly, to a point short of the fastest.
      if (working) state.level = Math.min(TEXT.hold, state.level + TEXT.hold * passed / TEXT.climb);
      state.rate = working ? climbed() : TEXT.waiting;
    } else {
      state.ending += passed;
      const up = Math.min(1, state.ending / TEXT.speedUp);
      const into = Math.min(1, Math.max(0, (state.ending - TEXT.speedUp) / TEXT.fadeIn));
      const out = Math.min(1, Math.max(0, (state.ending - TEXT.speedUp - TEXT.fadeIn) / TEXT.fadeOut));
      state.rate = climbed() + (TEXT.fastest - climbed()) * up;
      state.seen.value = 1 - out;
      const arriving = object.children.find(child => child.userData.arriving);
      if (arriving) { arriving.visible = into > 0.01; arriving.material.opacity = 0.7 * into + 0.3 * out; }
      if (out >= 1 || reduced()) { writing.delete(node.id); finished = true; continue; }
    }
    if (!reduced()) state.tick += passed * state.rate;
    // The text is the color the page gives the part, lightened, since thin strokes show less of a color than a
    // ball does.
    object.material.uniforms.ink.value.copy(object.material.color).lerp(WHITE, 0.5);
    if (Math.floor(state.tick) !== state.wrote) {                     // the whole of it is made again at once
      state.wrote = Math.floor(state.tick);
      const held = state.cells.image.data;
      for (let at = 0; at < held.length; at++) held[at] = Math.floor(Math.random() * 256);
      state.cells.needsUpdate = true;
    }
    // A signal reaching the text: a condition that needs attention, or the dot of a property's wave.
    const found = SIGNALS.find(([condition]) => has(node, condition));
    let reached = found ? (reduced() ? 1 : Math.max(0, Math.sin(now * 2 * Math.PI / 1.6))) : 0, color = found ? css(found[1]) : null;
    const dot = W.pulses.get(node.id), gone = dot ? (W.clock - dot.start) / dot.length : 2;
    if (gone >= 0 && gone <= 1 && Math.sin(Math.PI * gone) > reached) { reached = Math.sin(Math.PI * gone); color = R.color; }
    Object.assign(state, {reached, signalColor: reached > 0 && color ? color.toLowerCase() : null});
    state.glow.value = reached;
    if (reached > 0 && color) state.signal.value.set(color);
    signaled = signaled || reached > 0;
  }
  for (const id of writing.keys()) if (!shown.has(id)) writing.delete(id);  // no longer on the map
  T.signaled = signaled;
  if (BLOOM) BLOOM.enabled = Boolean(R.key) || signaled;  // the text's glow is spread by the bloom
  rows3d(G.graphData());
  if (finished) G.nodeThreeObject(G.nodeThreeObject());             // the parts built are drawn as every built part
}
function textOf(id) {
  const state = writing.get(id);
  if (!state) return '';
  return [...state.cells.image.data.slice(0, 64)].map(value => T.order[Math.min(61, Math.floor(value / 256 * 62))]).join('');
}
/* The condition of a node in 3D, MAP-046 and VIEW-005: an open tbd record puts the circles around it, which pulsate
 * once its task is taken; a broken part being fixed is steady red with pulsating circles; an open
 * broken record flashes it red, steady red with reduced motion, and an open cruft record pulses it between the cruft
 * color and its own, steady in the cruft color with reduced motion. The sphere takes its own
 * material first, so no other node of its color changes. Called every frame for the nodes that carry a record. */
function paint3d(node) {
  const object = node.__threeObj;
  if (!object || !object.material || object.userData.written) return;  // text shows its own condition, VIEW-027
  const broken = has(node, 'broken'), cruft = has(node, 'cruft'), fixing = has(node, 'fixing');
  // An open question glows in the question's color, pulsating, so it is seen with the whole map zoomed out, VIEW-021.
  const asked = has(node, 'question') || has(node, 'message');  // a message waits for the user, VIEW-030
  // A flash gives off its light on its beat and a trace of it between, so the circles are made once, VIEW-029.
  const flashing = (has(node, 'broken') || has(node, 'cruft')) && !fixing;
  const onBeat = reduced() || Math.floor(performance.now() / 500) % 2 === 0;
  const strength = flashing ? (onBeat ? 1.4 : 0.02) : asked || has(node, 'in-progress') || fixing ? pulse()
    : has(node, 'tbd') ? 1 : 0;
  bloom3d(object, strength, has(node, 'broken') || fixing ? css('--broken') : has(node, 'cruft') ? css('--cruft')
    : asked ? css('--question') : ownColor(node));
  // The circles of a part not built yet or in work are a mark of their own; those of a flash are its light.
  object.userData.light = flashing && !has(node, 'tbd') && !has(node, 'in-progress');  // at full strength when the node is dimmed too
  if (R.nodes.has(node.id) || (!broken && !cruft && !fixing && !asked)) return;
  if (!object.material.userData.own) {
    object.material = object.material.clone();
    object.material.userData.own = true;
    object.material.transparent = true;
  }
  const beat = reduced() || Math.floor(performance.now() / 500) % 2 === 0;
  const shown = fixing || (broken && beat) ? css('--broken') : cruft ? (beat ? css('--cruft') : ownColor(node))
    : colorOf(node);
  colored(object.material, dimmed(node) && !(broken || cruft || fixing) ? dim(shown) : shown);
  // While it is lit the node gives off light, which the bloom spreads past its outline, VIEW-029: a flash is lit
  // on its beat, a pulse swells for half its period and rests for the other half.
  const swell = reduced() ? 1 : Math.max(0, Math.sin(performance.now() / 1600 * 2 * Math.PI));
  const lit = broken || cruft ? (beat ? 1 : 0) : swell;
  if (!object.material.isMeshPhysicalMaterial) return;
  if (asked && !broken && !cruft && !fixing && lit > 0) object.material.emissive.set(css('--question'));
  object.material.emissiveIntensity = GLASS.emissiveIntensity + (LIGHT - GLASS.emissiveIntensity) * lit;
}
const LIGHT = 2.6;  // the light a node gives off when it is lit, chosen by eye; full brightness on a screen is 1

/* An encounter takes the color of its EF's word, Function or Encounter; one with no word keeps its layer's color. */
const EF = {Function: '--function', Encounter: '--encounter'};
function linkColor(link) {
  if (link.k === 'tree') return css('--tree');
  if ((link.work || []).includes('cruft')) return css('--cruft');
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
    .nodeThreeObject(node => asText(node) ? written(node) : isGlass(node) ? bead(node) : false)
    .nodeColor(node => dimmed(node) ? dim(colorOf(node)) : colorOf(node))
    .nodeOpacity(0.95)
    .nodeResolution(16)
    .nodeLabel(() => '')  // the page shows its own tooltip, anchored above the node, not under the pointer
    .onNodeHover(node => {
      hovered = node || null;
      $('#tip3d').hidden = !hovered;
      if (hovered) { fill($('#tip3d'), tipFor(hovered)); placeTip(); }
    })
    .linkColor(linkColor)
    .linkOpacity(Number(css('--link-opacity')))
    .linkWidth(link => link.k === 'tree' ? 0.4 : link.k === 'layer' || link.k === 'item' ? 0.25 : link.k === 'relation' ? 0.5 : 0.9)
    .linkCurvature(0)
    .linkDirectionalParticles(link => !reduced() && (link.k === 'purpose' || link.k === 'encounter') ? 2 : 0)
    .linkDirectionalParticleSpeed(0.006)
    .linkDirectionalParticleWidth(1.6)
    .linkDirectionalParticleColor(linkColor)
    .onNodeClick(clicked3d)
    .onNodeRightClick((node, event) => { if (node) menu(node.id, event.clientX, event.clientY); });
  addBloom();
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
  if (node.t === 'purpose') return [join?.name ? h('b', {}, join.name) : null, h('span', {}, join?.purpose || 'purpose')];
  return [h('b', {}, node.name || ''), node.joinName ? h('span', {}, node.joinName) : null];
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
    // A glass node is colored by the page, since the graph colors only the nodes it draws itself.
    for (const node of G.graphData().nodes) if (isGlass(node) && node.__threeObj?.material && !node.__threeObj.material.userData.pulsed)
      colored(node.__threeObj.material, dimmed(node) ? dim(colorOf(node)) : colorOf(node));
    wave3d(G.graphData());
    text3d();
    for (const node of G.graphData().nodes) {
      if ((node.work && node.work.length) || node.__threeObj?.userData.glow) paint3d(node);
      if (node.t !== 'el') continue;
      let tag = tags.get(node.id);
      if (!tag) { tag = h('span', {}, short(node.name, 26)); box.append(tag); tags.set(node.id, tag); }
      tag.hidden = node.x === undefined;
      if (tag.hidden) continue;
      const point = G.graph2ScreenCoords(node.x, node.y, node.z);
      tag.style.left = point.x + 'px';
      tag.style.top = point.y + 'px';
      tag.className = [node.id === S.selected ? 'sel' : S.neighbors.has(node.id) ? 'near' : S.selected ? 'dim' : '',
        ...(node.work || []).map(condition => `work-${condition}`), R.nodes.has(node.id) ? 'reach' : '',
        node.__threeObj?.userData.written ? 'text' : '']
        .filter(Boolean).join(' ');
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
/* A theme recolors both views in place, VIEW-023: the 3D view rereads its colors, the 2D map is drawn again. The
 * choice is the viewer's own, kept in this browser. */
function setTheme(name) {
  document.documentElement.dataset.theme = name;
  try { localStorage.setItem('metaform.theme', name); } catch (error) { /* storage can be blocked; the theme still shows */ }
  if (G) G.backgroundColor(css('--ground')).linkOpacity(Number(css('--link-opacity'))).nodeColor(G.nodeColor())
    .linkColor(G.linkColor()).linkDirectionalParticleColor(G.linkDirectionalParticleColor());
  mermaidReady = false;
  build2D();
}
$('#theme').value = document.documentElement.dataset.theme;
if ($('#theme').selectedIndex < 0) $('#theme').value = document.documentElement.dataset.theme = 'space';  // a kept name that is no longer a theme
$('#theme').onchange = () => setTheme($('#theme').value);
/* The two views change places, VIEW-028: the 2D map takes the large area and the 3D map the small one, and back.
 * Each is then drawn for the area it has. The choice is the viewer's own, kept in this browser. */
async function swap(on) {
  $('.app').classList.toggle('swapped', on);
  (on ? $('main') : $('#small')).append($('#map2d'));
  (on ? $('#small') : $('main')).append($('#big3d'));
  $('#swapBtn').title = on ? 'Put the 3D map back in the large area' : 'Put this map in the large area, and the 3D map here';
  $('#swap3dBtn').title = on ? 'Put this map back in the large area' : 'Put this map in the small area, and the 2D map here';
  try { localStorage.setItem('metaform.swapped', on ? '1' : ''); } catch (error) { /* storage can be blocked; the swap still shows */ }
  resize();
  if (G) setTimeout(() => G.zoomToFit(reduced() ? 0 : 600, on ? 24 : 60), 50);  // the whole 3D map in its new area
  if (S.loading || !S.elements.size) return;
  await build2D();
  if (S.selected) select(S.selected, false, true);
}
$('#swapBtn').onclick = $('#swap3dBtn').onclick = () => swap(!$('.app').classList.contains('swapped'));
$('#fit3dBtn').onclick = () => { if (G) G.zoomToFit(reduced() ? 0 : 700, 60); };
try { if (localStorage.getItem('metaform.swapped')) swap(true); } catch (error) { /* storage can be blocked */ }
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
  const open = new Set([...S.elements.values()].flatMap(entry => entry.element.open_work || [])
    .concat(S.joins.flatMap(join => (join.open_work || []).concat((join.subtypes || []).flatMap(subtype => subtype.open_work || [])))));
  for (const condition of CONDITIONS) if (open.has(condition))
    legend.append(h('span', {style: {'--c': condition === 'tbd' || condition === 'in-progress' ? 'var(--text)'
      : `var(--${condition === 'fixing' ? 'broken' : condition === 'message' ? 'question' : condition})`}},
      h('i', {class: {tbd: 'dot bloom', 'in-progress': 'dot bloom pulse', fixing: 'dot bloom pulse', question: 'dot bloom pulse', message: 'dot bloom pulse'}[condition] || 'dot'}),
      `work: ${condition}`));
  const shown = G ? G.graphData().nodes.length : 0;
  $('#count').textContent = noMetaform() ? 'no metaform yet'
    : `${S.elements.size} elements · ${S.joins.length} joins · ${shown} nodes shown` + (S.loading ? ' · loading' : '')
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
      themeVariables: {background: css('--ground'), primaryColor: css('--node'), primaryBorderColor: css('--node-line'),
        primaryTextColor: css('--text'), lineColor: css('--edge'), fontFamily: 'IBM Plex Sans, sans-serif', fontSize: '13px',
        tertiaryColor: css('--group')}});
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
      inner.set('s:' + subtype.join_id, key);
      lines.push(`${key}["${plain2d(subtype.short_name || subtype.address)}"]:::sub`);
    }
    lines.push('end');
  }
  if (inner.size) lines.push('classDef sub font-size:11px');
  drawn.forEach((join, index) => lines.push(`${keys.get(join.receiver)} e${index}@--> ${keys.get(join.provider)}`));
  if (!S.elements.size || S.elements.size > MAP2D) { IN.length = 0; M.base = null; renderCrumbs(); }
  if (!S.elements.size) { fill(host, h('p', {class: 'empty', style: {padding: '16px'}}, noMetaform() ? noneYet() : 'This metaform has no elements in these layers.')); return; }
  if (S.elements.size > MAP2D) {
    M.svg = null; M.nodes = new Map(); M.edges = [];
    fill(host, h('p', {class: 'empty', style: {padding: '16px'}}, `The 2D map lays out at most ${MAP2D} elements; these layers show ${S.elements.size}. The 3D view shows them all.`));
    return;
  }
  let result;
  try { result = await window.mermaid.render(`map2d${generation}`, lines.join('\n'), $('#draw')); }
  catch (error) { fill(host, h('p', {class: 'empty', style: {padding: '16px'}}, 'The 2D map could not be drawn.')); return; }
  if (generation !== M.generation) return;
  const inside = IN.length > 0;
  const svg = mountSvg(result, host, inside);
  const nodes = new Map();
  for (const [id, key] of keys) {
    const group = held.has(id) ? svg.querySelector(`g.cluster[id="${key}"], g.cluster[id$="-${key}"]`)
      : svg.querySelector(`[id*="-flowchart-${key}-"]`);
    if (group) placeIn(nodes, id, group, S.elements.get(id).element.address, S.elements.get(id).element.open_work);
  }
  for (const [id, key] of inner) {
    const group = svg.querySelector(`[id*="-flowchart-${key}-"]`);
    const {subtype} = subtypeOf.get(id) || {};
    if (group && subtype) placeIn(nodes, id, group, subtype.address, subtype.open_work);
  }
  const edges = drawn.map((join, index) => ({join, path: svg.querySelector(`[data-id="e${index}"]`)
    || svg.querySelectorAll('.edgePaths path')[index]}));
  for (const edge of edges) if (EF[edge.join.ef]) edge.path?.classList.add(`ef-${edge.join.ef.toLowerCase()}`);
  for (const edge of edges) for (const condition of edge.join.open_work || []) edge.path?.classList.add(`work-${condition}`);
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
function placeIn(nodes, id, group, title, work) {
  const box = group.getBBox();
  const matrix = group.transform.baseVal.consolidate()?.matrix;
  const center = new DOMPoint(box.x + box.width / 2, box.y + box.height / 2).matrixTransform(matrix || new DOMMatrix());
  nodes.set(id, {g: group, x: center.x, y: center.y, w: box.width, h: box.height});
  for (const condition of work || []) group.classList.add(`work-${condition}`);  // the node's condition, MAP-046
  const text = document.createElementNS(SVG, 'title');
  text.textContent = title;
  group.append(text);
  group.addEventListener('click', event => { event.stopPropagation(); clicked2d(id); });
  group.addEventListener('contextmenu', event => { event.preventDefault(); event.stopPropagation(); menu(id, event.clientX, event.clientY); });
}
/* Where the camera opens on a node's own graph, VIEW-016: the whole graph when its labels can be read at that size,
 * otherwise the node entered, at the size its labels are written in. Fit still shows the whole graph. */
function readable(fit, center) {
  const view = $('#viewport').getBoundingClientRect();
  if (!center || !view.width || view.width / frame(fit).w >= 1) return fit;
  const w = view.width, height = view.height || w;
  const x = Math.min(Math.max(center.x - w / 2, fit.x), Math.max(fit.x, fit.x + fit.w - w));
  const y = Math.min(Math.max(center.y - height / 2, fit.y), Math.max(fit.y, fit.y + fit.h - height));
  return {x, y, w, h: height};
}
function fitOf(svg) {
  const scene = svg.querySelector('g').getBBox();
  return {x: scene.x - 30, y: scene.y - 30, w: scene.width + 60, h: scene.height + 60};
}
function showBase(left = null) {
  const base = M.base;
  renderCrumbs();
  if (!base) return;
  cancelAnimationFrame(M.frame);  // a camera still easing on the level left must not move this one
  Object.assign(M, {svg: base.svg, nodes: base.nodes, edges: base.edges, fit: base.fit, vertical: base.vertical, drawn: null});
  fill($('#viewport'), base.svg);
  const node = left ? base.nodes.get(left) : null;
  if (node && !reduced()) {  // back from inside the node: the map returns zoomed on it and fades in, VIEW-016
    const kept = base.cam || frame(readable(base.fit, node));  // the zoom held before going inside
    setCam(frame(into(node)), false);
    M.zoom = {w: kept.w, h: kept.h};
    arrive(base.svg);
    moveCam({x: node.x - kept.w / 2, y: node.y - kept.h / 2, w: kept.w, h: kept.h});
    return;
  }
  base.svg.style.transition = ''; base.svg.style.opacity = '';  // a map faded on the way in shows whole again
  const entry = [...S.elements.values()].find(item => item.element.role === 'DE')?.element.element_id;
  setCam(base.cam || frame(readable(base.fit, base.nodes.get(S.selected) || base.nodes.get(entry)
    || base.nodes.values().next().value)));
}

/* ---------- inside a node: the 2D map is replaced by the node's own graph, VIEW-016 ----------
 * Every node can be entered. Inside are the node, what it holds, one group for each layer turned on with what that
 * layer attaches to the node, and the nodes those items link to, which can be entered in turn. */
const IN = [];  // the levels entered from the base map: {key, label, more, things}
const GROUP = 20;
let insideGen = 0;
const kindOf = key => key.startsWith('s:') || key.startsWith('p:') ? 'join' : 'element';  // a subtype join is a join
const bareId = key => key.replace(/^[sp]:/, '');
const keyOf = node => !node ? null
  : node.kind === 'join' ? (subtypeOf.has('s:' + node.id) ? 's:' + node.id : 'p:' + node.id)
  : node.kind === 'element' ? (S.elements.has(node.id) ? node.id : heldBy.get(node.id) || node.id) : null;
const label2d = text => plain2d(String(text ?? '').replace(/\s+/g, ' ')) || '·';
const samePath = (a, b) => a.length === b.length && a.every((level, index) => level.key === b[index].key);
/* An element's and a subtype's name is its short name, its address read through name_length, MAP-012; a join's is the
 * project's own name for the functionality, MAP-020, or its purpose when it has none. */
const joinLabel = join => join.name || join.purpose || join.relation || 'join';
function nameOf(key, fallback = key) {
  if (key.startsWith('s:')) { const found = subtypeOf.get(key)?.subtype; return found ? found.short_name || found.address : fallback; }
  if (key.startsWith('p:')) { const found = joinOf(key); return found ? joinLabel(found) : fallback; }
  const found = S.elements.get(key)?.element;
  return found ? found.short_name || found.address : fallback;
}
async function drawInside(arriving = false) {
  const level = IN.at(-1);
  if (!level) return showBase();
  const generation = ++insideGen;
  const target = `${kindOf(level.key)}:${bareId(level.key)}`;
  let view = null, incoming = [];
  const held = level.key.startsWith('s:') ? subtypeOf.get(level.key)?.subtype.element_id : null;
  try {
    view = await read('node', {target, ...viewLayers()});
    incoming = (await read('links-to', {target, limit: 0, ...viewLayers()})).results || [];
    if (held) {  // the absorbed part stays one element, so what is attached to it shows at its subtype, MAP-030
      const part = await read('node', {target: `element:${held}`, ...viewLayers()});
      const groups = new Map((view?.layers || []).map(group => [group.layer, group]));
      for (const group of part?.layers || []) {
        const into = groups.get(group.layer);
        if (into) { into.items = [...(into.items || []), ...(group.items || [])]; into.properties = [...(into.properties || []), ...(group.properties || [])]; }
        else if (view) view.layers = [...(view.layers || []), group];
      }
      incoming = [...incoming, ...((await read('links-to', {target: `element:${held}`, limit: 0, ...viewLayers()})).results || [])];
    }
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
      for (const subtype of join.subtypes || []) edges.push(`${center} --- ${add('s:' + subtype.join_id, subtype.short_name || subtype.address, 'sub')}`);
    }
  } else if (key.startsWith('s:')) {
    const found = subtypeOf.get(key);
    if (found) edges.push(`${add('p:' + found.join.join_id, joinLabel(found.join), 'purpose')} --- ${center}`);
  } else {
    for (const join of S.joins.filter(item => item.provider === key)) for (const subtype of join.subtypes || [])
      edges.push(`${center} --- ${add('s:' + subtype.join_id, subtype.short_name || subtype.address, 'sub')}`);
    for (const join of S.joins.filter(item => item.receiver === key))
      edges.push(`${center} --> ${add('p:' + join.join_id, joinLabel(join), 'purpose')}`);
  }
  const linked = [];
  for (const found of view?.layers || []) {
    const all = [...(found.items || []).map(item => ({kind: 'item', key: 'i:' + item.item_id, item})),
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
  try { result = await window.mermaid.render(`inside${generation}`, lines.join('\n'), $('#draw')); }
  catch (error) { fill($('#viewport'), h('p', {class: 'empty', style: {padding: '16px'}}, 'This node could not be drawn.')); return; }
  if (generation !== insideGen || IN.at(-1) !== level) return;
  const svg = mountSvg(result, $('#viewport'), false);
  if (arriving) arrive(svg);  // the node's own graph fades in, VIEW-016
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
  setCam(frame(readable(M.fit, nodes.get(level.key))));
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
  const node = M.nodes.get(key);
  if (M.svg && node && !reduced()) {  // the camera goes into the node as the view it is on fades, VIEW-016
    moveCam(into(node));
    await fade(M.svg, 0);
  }
  IN.push({key, label: nameOf(key, thing?.label || key), more: {}, things: new Map()});
  await drawInside(true);
  select(key, false, true);
}
/* Up to a level: 0 is the base map. The node left is selected where it shows. */
async function goTo(depth) {
  if (depth >= IN.length) return;
  const left = IN[depth].key;
  if (M.svg && !reduced()) await fade(M.svg, 0);  // the node's graph fades as it is left, VIEW-016
  IN.length = depth;
  if (depth) await drawInside(true); else showBase(left);
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
/* A view fades in or out, and the promise settles once it has; with reduced motion it changes at once, VIEW-016. */
function fade(svg, to, ms = 480) {
  if (reduced()) { svg.style.transition = ''; svg.style.opacity = ''; return Promise.resolve(); }
  svg.style.transition = `opacity ${ms}ms ease`;
  svg.getBoundingClientRect();  // the fade starts from the opacity the view has now
  svg.style.opacity = String(to);
  return new Promise(resolve => setTimeout(resolve, ms));
}
/* A view that has just been put in place, faded in from nothing. */
function arrive(svg) {
  if (reduced()) return;
  svg.style.transition = ''; svg.style.opacity = '0';
  fade(svg, 1);
}
const into = node => ({x: node.x - node.w * 0.6, y: node.y - node.h * 0.6, w: node.w * 1.2, h: node.h * 1.2});
/* M.zoom is the zoom the person has: the size the view opened at, what Fit set, or what they set by wheel. A
 * selection moves the view at that size; a camera still easing toward it never changes it, VIEW-008. */
function setCam(cam, settled = true) {
  M.cam = cam;
  if (settled) M.zoom = {w: cam.w, h: cam.h};
  M.svg?.setAttribute('viewBox', `${cam.x} ${cam.y} ${cam.w} ${cam.h}`);
}
function moveCam(target, animate = true) {
  if (!M.svg) return;
  cancelAnimationFrame(M.frame);
  const to = frame(target), from = {...M.cam};
  M.zoom = {w: to.w, h: to.h};
  if (!animate || reduced()) return setCam(to);
  const start = performance.now(), duration = 700;
  const ease = t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  const step = now => {
    const k = ease(Math.min(1, (now - start) / duration));
    setCam({x: from.x + (to.x - from.x) * k, y: from.y + (to.y - from.y) * k, w: from.w + (to.w - from.w) * k, h: from.h + (to.h - from.h) * k}, false);
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
  if (IN.length) {
    for (const [key, value] of M.nodes) value.g.classList.toggle('sel', key === id);
  } else {
    $('#map2d').classList.add('focused');
    for (const [key, value] of M.nodes) { value.g.classList.toggle('sel', key === id); value.g.classList.toggle('near', key !== id && S.neighbors.has(key)); }
    for (const edge of M.edges) edge.path?.classList.toggle('on', join ? edge.join === join
      : edge.join.receiver === id || edge.join.provider === id);
  }
  // Selecting moves the view to the node at the zoom it has; the zoom changes only when Fit asks, VIEW-008.
  const held = M.zoom || M.cam;
  if (!zoom) return moveCam({x: node.x - held.w / 2, y: node.y - held.h / 2, w: held.w, h: held.h}, animate);
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
  return across(S.joins.filter(join => join.provider === key).flatMap(join => (join.subtypes || []).map(subtype => 's:' + subtype.join_id)));
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
  if (event.key === 'Escape' && !$('#clearbox').hidden) { event.preventDefault(); showClear(false); $('#clearBtn').focus(); return; }
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
  setReach(id);
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
  return refs && refs.length ? h('div', {class: 'refs'}, refs.map(ref => h('span', {}, h('span', {class: 'k'}, ref.key), ref.value))) : null;
}
/* The work records of the selected object, MAP-046: each with its condition, note and task, held and reviewed,
 * and its resolution once done; read from /api/work for the node and written into the panel's work box. */
function workPill(condition) { return h('span', {class: `pill work-${condition}`}, condition); }
/* A question at the node, MAP-050 and VIEW-021: open, it takes the answer here; answered, the answer stays beside it. */
function asked(record) {
  const answer = h('textarea', {class: 'answer', placeholder: 'Your answer'});
  const written = text => wrote('/api/answer', {id: record.work_id, answer: text});
  const send = h('button', {class: 'answer', onclick: async () => {
    if (!answer.value.trim()) return;
    send.disabled = true;
    if (!await written(answer.value)) send.disabled = false;
  }}, 'Answer');
  // The answers the agent suggests, the one it recommends first: one click answers. Other opens the box to type in.
  let suggested = [];
  try { const given = JSON.parse(record.task || '[]'); if (Array.isArray(given)) suggested = given.map(String); } catch (error) { /* a task that is not a list is no suggestion */ }
  const typed = h('div', {class: 'typed', hidden: suggested.length > 0}, answer, send);
  const choices = suggested.length ? h('div', {class: 'choices'},
    suggested.map((text, index) => h('button', {class: index ? 'suggestion' : 'suggestion recommended', onclick: async event => {
      const buttons = [...event.target.parentNode.children];
      for (const button of buttons) button.disabled = true;
      if (!await written(text)) for (const button of buttons) button.disabled = false;
    }}, text)),
    h('button', {class: 'other', onclick: () => { typed.hidden = false; answer.focus(); }}, 'Other')) : null;
  if (suggested.length) typed.replaceChildren();               // the box is put in only when Other is asked for
  if (choices) choices.lastChild.addEventListener('click', () => typed.replaceChildren(answer, send), {once: true});
  return h('div', {class: 'item work'},
    h('div', {class: 'pills'}, workPill('question'), h('span', {class: 'pill'}, record.done ? 'answered' : 'open')),
    h('p', {class: 'asked'}, record.note || ''),
    record.done ? h('p', {class: 'obs'}, `Answer: ${record.resolution || ''}`) : [choices, typed]);
}
/* The messages of a node, VIEW-030: what agents say to the user there. A question waits for an answer and a note
 * waits to be read. */
const MESSAGES = ['question', 'message'];
const Q = {open: []};
const nodeOf = record => record.kind === 'element' ? record.id : joinOf('p:' + record.id) ? 'p:' + record.id : 's:' + record.id;
const targetOf = id => id.startsWith('p:') || id.startsWith('s:') ? `join:${id.slice(2)}` : `element:${id}`;
const calledOf = id => (G ? G.graphData().nodes.find(node => node.id === id) : null)?.name
  || S.elements.get(id)?.element.short_name || joinOf(id)?.name || 'this node';
async function messagesOf(id) {
  const found = (await read('work', {node: targetOf(id), limit: 0})).results.filter(record => MESSAGES.includes(record.condition));
  return {unread: found.filter(record => !record.done), past: found.filter(record => record.done), all: found};
}
/* The Messages button, VIEW-021: at the top of the page while anything waits for the user, with the count; a click
 * flies to the node of the oldest and opens its unread messages. */
async function renderMessages() {
  try {
    Q.open = noMetaform() ? [] : (await Promise.all(MESSAGES.map(condition => read('work', {condition, open: true, limit: 0}))))
      .flatMap(page => page.results).sort((one, two) => one.created < two.created ? -1 : one.created > two.created ? 1 : 0);
  } catch (error) { Q.open = []; toast(error.message); }
  const button = $('#messages');
  button.hidden = !Q.open.length;
  button.textContent = `Messages ${Q.open.length}`;
  button.onclick = () => {
    if (!Q.open.length) return;
    const id = nodeOf(Q.open[0]);
    select(id, true);
    show(id, 'unread');
  };
  if (F.id) show(F.id, F.which, true);
}
/* The menu of a node, opened by a right-click in either view. Each entry says how many it holds, and one that holds
 * none cannot be chosen. It is where further acts on a node are added. */
async function menu(id, x = null, y = null) {
  let found = {unread: [], past: []};
  try { found = await messagesOf(id); } catch (error) { toast(error.message); }
  const box = $('#menu');
  const entry = (which, text, count) => h('button', {class: which, disabled: !count, role: 'menuitem',
    onclick: () => { box.hidden = true; show(id, which); }}, text + ' ', h('b', {}, String(count)));
  fill(box, entry('unread', 'Unread messages', found.unread.length), entry('past', 'Past messages', found.past.length));
  box.hidden = false;
  if (x === null && G) {  // asked for with no pointer: beside the node in the 3D map
    const node = G.graphData().nodes.find(item => item.id === id), stage = $('#stage').getBoundingClientRect();
    const at = node && node.x !== undefined ? G.graph2ScreenCoords(node.x, node.y, node.z) : {x: 40, y: 40};
    [x, y] = [stage.left + at.x + 12, stage.top + at.y + 12];
  }
  const size = box.getBoundingClientRect();
  box.style.left = Math.max(4, Math.min(x ?? 40, innerWidth - size.width - 4)) + 'px';
  box.style.top = Math.max(4, Math.min(y ?? 40, innerHeight - size.height - 4)) + 'px';
}
addEventListener('click', event => { if (!$('#menu').hidden && !$('#menu').contains(event.target)) $('#menu').hidden = true; });
addEventListener('keydown', event => { if (event.key === 'Escape' && !$('#menu').hidden) { $('#menu').hidden = true; event.stopPropagation(); } }, true);
/* The floating window, VIEW-030. It shows the messages it was opened with, each as it is now, so a question answered
 * in it shows its answer and a note read in it stays in sight until the window is closed. */
const F = {id: null, which: null, ids: new Set()};
async function show(id, which, again = false) {
  let found;
  try { found = await messagesOf(id); } catch (error) { toast(error.message); return; }
  if (!again) Object.assign(F, {id, which, ids: new Set(found[which].map(record => record.work_id))});
  if (F.id !== id) return;
  const shown = found.all.filter(record => F.ids.has(record.work_id));
  $('#float .title').textContent = `${which === 'unread' ? 'Unread' : 'Past'} messages · ${calledOf(id)}`;
  fill($('#float .body'), shown.length ? shown.map(record => h('div', {},
    h('div', {class: 'when'}, record.created.replace('T', ' ').replace('Z', '')),
    record.condition === 'question' ? asked(record) : noted(record)))
    : h('p', {class: 'empty'}, 'No messages here.'));
  $('#float').hidden = false;
  for (const record of shown) if (record.condition === 'message' && !record.done) wrote('/api/read', {id: record.work_id});
}
function noted(record) {
  return h('div', {class: 'item work'},
    h('div', {class: 'pills'}, workPill('message'), h('span', {class: 'pill'}, record.done ? 'read' : 'unread')),
    h('p', {}, record.note || ''));
}
async function wrote(path, given) {
  const response = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({project: S.project, metaform: S.metaform, ...given})});
  const body = await response.json().catch(() => ({error: 'The server did not answer with JSON.'}));
  if (!response.ok) toast(body.error || 'It was not written.');
  return response.ok;
}
$('#float .close').onclick = () => { $('#float').hidden = true; Object.assign(F, {id: null, which: null, ids: new Set()}); };
$('#float .bar').addEventListener('pointerdown', event => {
  if (event.target.closest('button')) return;
  const box = $('#float'), from = box.getBoundingClientRect(), start = [event.clientX - from.left, event.clientY - from.top];
  const move = moved => {
    box.style.left = Math.max(0, Math.min(moved.clientX - start[0], innerWidth - 60)) + 'px';
    box.style.top = Math.max(0, Math.min(moved.clientY - start[1], innerHeight - 40)) + 'px';
  };
  const end = () => { removeEventListener('pointermove', move); removeEventListener('pointerup', end); };
  addEventListener('pointermove', move);
  addEventListener('pointerup', end);
  event.preventDefault();
});
async function renderWork(target, key, also = null) {
  let records = [];
  try {
    records = (await read('work', {node: target, limit: 0})).results;
    if (also) records = [...records, ...(await read('work', {node: also, limit: 0})).results];
  } catch (error) { toast(error.message); }
  records = records.filter(record => !MESSAGES.includes(record.condition));  // messages are read in the window, VIEW-030
  const box = $('#work');
  if (!box || S.selected !== key || !records.length) return;
  fill(box, h('div', {class: 'eyebrow'}, 'Work'), records.map(record => h('div', {class: 'item work'},
    h('div', {class: 'pills'}, workPill(record.condition), h('span', {class: 'pill'}, record.done ? 'done' : 'open'),
      record.held ? h('span', {class: 'pill'}, 'held') : null, record.reviewed ? h('span', {class: 'pill'}, 'reviewed') : null),
    record.note ? h('p', {}, record.note) : null,
    record.task ? h('p', {class: 'fn'}, record.task) : null,
    record.done ? h('p', {class: 'obs'}, `Resolved: ${record.resolution || ''}`) : null)));
}
function efPill(thing) {
  return EF[thing.ef] ? h('span', {class: 'pill ef', style: {'--c': `var(${EF[thing.ef]})`}}, thing.ef) : null;
}
function layerPill(name) { return h('span', {class: 'pill layer', style: {'--c': `var(${colorVar(name)})`}}, name); }
function elementLink(id, address) {
  const entry = S.elements.get(id);
  return h('a', {class: 'link', href: '#', onclick: event => { event.preventDefault(); select(id, true); }},
    entry ? (entry.element.short_name || address) : address);
}
function joinCard(join, side) {
  const other = side === 'provider' ? join.provider : join.receiver;
  const otherAddress = side === 'provider' ? join.provider_address : join.receiver_address;
  return h('div', {class: 'join'},
    h('div', {class: 'row'}, h('span', {class: 'dir'}, `${side} · `, elementLink(other, otherAddress)),
      h('span', {class: 'lay', style: {'--c': `var(${colorVar(join.layer)})`}}, join.layer)),
    join.name ? h('p', {class: 'name'}, h('b', {}, join.name)) : null,
    join.purpose ? h('p', {}, join.purpose) : null,
    join.function ? h('p', {class: 'fn'}, efPill(join), join.function) : null,
    join.relation ? h('p', {class: 'fn'}, join.relation) : null,
    join.observation ? h('p', {class: 'obs'}, join.observation) : null,
    join.non_goal ? h('p', {class: 'obs'}, `Not: ${join.non_goal}`) : null,
    refsOf(join.refs),
    (join.subtypes || []).map(subtype => h('div', {class: 'sub'}, h('a', {class: 'link', href: '#', onclick: event => {
      event.preventDefault(); select('s:' + subtype.join_id, true); }}, h('b', {}, subtype.short_name || subtype.address)), ' ',
      subtype.name ? h('span', {}, subtype.name, ' ') : null,
      h('span', {class: 'refs'}, subtype.address), subtype.function ? h('div', {}, efPill(subtype), subtype.function) : null,
      subtype.observation ? h('div', {}, subtype.observation) : null, refsOf(subtype.refs))));
}
function itemText(value) {
  if (value && typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value ?? '');
}
/* A selected subtype or join shows only itself, so nothing needs finding in its parent's text. */
function renderSubtype({subtype, join}) {
  fill($('#p-object'),
    h('div', {class: 'eyebrow'}, 'Subtype'),
    h('h2', {}, subtype.short_name || subtype.address),
    h('div', {class: 'addr'}, subtype.address),
    subtype.name ? h('p', {class: 'name'}, h('b', {}, subtype.name)) : null,
    h('div', {class: 'pills'}, subtype.role ? h('span', {class: 'pill'}, subtype.role) : null, efPill(subtype),
      (subtype.open_work || []).map(workPill), layerPill(subtype.layer)),
    h('p', {class: 'meta'}, 'Inside ', elementLink(join.provider, join.provider_address), ', in the join that serves ',
      elementLink(join.receiver, join.receiver_address), '.'),
    subtype.function ? h('p', {}, subtype.function) : null,
    subtype.relation ? h('p', {class: 'fn'}, subtype.relation) : null,
    subtype.observation ? h('p', {class: 'obs'}, subtype.observation) : null,
    refsOf(subtype.refs),
    h('div', {id: 'work'}),
    h('div', {class: 'eyebrow'}, 'The join it sits in'),
    joinCard(join, 'provider'));
  renderWork(`join:${subtype.join_id}`, 's:' + subtype.join_id, `element:${subtype.element_id}`);
}
function renderJoin(join) {
  fill($('#p-object'),
    h('div', {class: 'eyebrow'}, 'Join'),
    h('h2', {}, join.name || join.relation || `${join.receiver_address} receives from ${join.provider_address}`),
    h('p', {class: 'meta'}, elementLink(join.receiver, join.receiver_address), ' receives from ',
      elementLink(join.provider, join.provider_address), '.'),
    (join.open_work || []).length ? h('div', {class: 'pills'}, join.open_work.map(workPill)) : null,
    joinCard(join, 'provider'),
    h('div', {id: 'work'}));
  renderWork(`join:${join.join_id}`, 'p:' + join.join_id);
}
async function renderObject(id) {
  const {element} = S.elements.get(id);
  const pane = $('#p-object');
  const held = S.joins.filter(join => join.receiver === id), serves = S.joins.filter(join => join.provider === id);
  fill(pane, 
    h('div', {class: 'eyebrow'}, 'Element'),
    h('h2', {}, element.short_name || element.address),
    h('div', {class: 'addr'}, element.address),
    h('div', {class: 'pills'}, element.role ? h('span', {class: 'pill'}, element.role) : null,
      (element.open_work || []).map(workPill), layerPill(element.layer),
      h('span', {class: 'pill'}, `${held.length} held · ${serves.length} served`)),
    refsOf(element.refs),
    h('div', {id: 'work'}),
    h('div', {id: 'items'}),
    h('div', {class: 'eyebrow'}, 'Joins held by this element'),
    held.length ? held.map(join => joinCard(join, 'provider')) : h('p', {class: 'empty'}, 'This element receives nothing here.'),
    serves.length ? h('div', {class: 'eyebrow'}, 'Serves') : null,
    serves.map(join => joinCard(join, 'receiver')));
  renderWork(`element:${id}`, id);
  try {
    // While the page follows an intake being recorded, the element is shown as the building layer records it; that
    // layer is in no reading context until it finishes, LAYER-007, so a node read could only find nothing and is not made.
    const node = following() ? {layers: []} : await read('node', {target: `element:${id}`, ...viewLayers()});
    if (S.selected !== id) return;
    const box = $('#items');
    for (const group of node.layers || []) {
      const items = group.items || [];
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
  if (noMetaform()) return fill(pane, h('p', {class: 'empty'}, noneYet()));
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
  if (noMetaform()) return fill(pane, h('p', {class: 'empty'}, noneYet()));
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
/* Follow the intake being recorded, found = {layer, metaform_id}, or return to the map when it is no longer being
 * recorded, saying what happened: it finished when its metaform still stands, or it stopped because the project was
 * cleared, the one thing that takes a metaform away, VIEW-019. */
async function follow(found) {
  if (found && found.layer !== LIVE.layer) {
    Object.assign(LIVE, {layer: found.layer, metaform: found.metaform_id, seen: ''});
    if (S.metaform !== found.metaform_id) await loadProject(found.metaform_id);
    else { S.layers = (await read('layers', {limit: 0})).results; renderChips(); }
    toast(`An intake is being recorded in ${found.layer}; the map follows it as each object is recorded.`);
  } else if (!found && LIVE.layer) {
    const {layer, metaform} = LIVE;
    const stands = (await read('metaforms', {limit: 0})).results.some(item => item.metaform_id === metaform);
    Object.assign(LIVE, {layer: null, metaform: null, seen: ''});
    renderLegend();
    toast(stands ? `The intake ${layer} finished.` : `The intake ${layer} stopped: ${S.project} was cleared.`);
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
 * as in every read, VIEW-017. */
async function itemsOf(generation) {
  const found = new Map();
  for (const layer of S.layers.filter(item => item.ready && !['intake', 'correction'].includes(item.kind))) {
    let after = null;
    do {
      const page = await read('layer-items', {layer: layer.name, in_context: 'true', limit: 500, ...(after ? {after} : {}), ...viewLayers()});
      if (generation !== S.loading) return found;
      for (const item of page.results) {
        const property = 'property_id' in item;
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
  renderMessages();
  await build2D();
  const keep = S.selected && (S.elements.has(S.selected) || subtypeOf.has(S.selected) || joinOf(S.selected)) ? S.selected : null;
  const start = keep || [...S.elements.values()].find(entry => entry.element.role === 'DE')?.element.element_id
    || S.elements.keys().next().value;
  if (!start) fill($('#p-object'), h('p', {class: 'empty'}, noMetaform() ? noneYet() : 'Nothing to show in these layers yet.'));
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
  if ($('#p-corr').hidden === false) renderCorr();
  await loadGraph();
}
async function loadProject(wanted = null) {
  const metaforms = (await read('metaforms', {limit: 0})).results;
  S.metaforms = metaforms;
  const active = metaforms.find(item => item.metaform_id === wanted) || metaforms.find(item => item.active) || metaforms[0];
  S.metaform = active ? active.metaform_id : null;
  fill($('#mf'), ...(metaforms.length ? metaforms.map(item => h('option', {value: item.metaform_id, selected: item === active}, item.name + (item.active ? ' · active' : '')))
    : [h('option', {}, 'none yet')]));
  $('#mf').disabled = !metaforms.length;
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
