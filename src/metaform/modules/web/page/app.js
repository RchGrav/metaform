/* Metaform's web GUI, the viewer: the whole map in 3D and in 2D, kept in sync, and the selected object below.
 * Every piece of data comes from the server's reads, VIEW-004; the page never decides what is visible. Text from the
 * store is always set as text, never as HTML, VIEW-009. */
'use strict';

// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
import ForceGraph3D from '3d-force-graph';
import {createAgent, drawGlyph, releaseGlyph, orientAgent} from '/page/agents3d.js';
// drei's transmission material in its vanilla form, the glass itself, VIEW-025. It imports three.js as `three`, which
// the page's import map names as the same file, so both share one three.js.
import {MeshTransmissionMaterial} from '/vendor/drei-vanilla/MeshTransmissionMaterial.js';

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
/* Fill a node with these children, leaving in place each one already there in its place, so a text being typed into
 * keeps its text, its cursor and the focus. */
function keepFill(node, kids) {
  for (const child of [...node.childNodes]) if (!kids.includes(child)) child.remove();
  kids.forEach((kid, index) => { if (node.childNodes[index] !== kid) node.insertBefore(kid, node.childNodes[index] || null); });
}
/* Fill a list from rows {key, text, make}: a row whose key and text are unchanged keeps its node, a changed one is made
 * again, a new one is added, so a thread that grows only appends and never flashes. Says whether anything changed. */
function keyedFill(node, rows) {
  const before = node.keyed || new Map(), now = new Map();
  let changed = rows.length !== before.size;
  for (const row of rows) {
    const had = before.get(row.key);
    if (had && had.text === row.text) now.set(row.key, had);
    else { changed = true; now.set(row.key, {text: row.text, node: row.make()}); }
  }
  node.keyed = now;
  keepFill(node, [...now.values()].map(one => one.node));
  return changed;
}

/* ---------- reads ---------- */
const S = {
  projects: [], project: null, bases: [], base: null, layers: [], view: null,
  elements: new Map(), joins: [], items: new Map(), selected: null, neighbors: new Set(), trail: [], history: [], at: -1, loading: 0, opening: 0,
  whole: null,  // the last map read whole, {elements, joins}, put back when a read of it fails
  memory: {entities: new Map(), relations: [], joins: [], at: new Map(), age: 0, orphaned: 0},  // LAYER-013
};
/* The memory network open in both views, VIEW-031: the node it belongs to, what is drawn of it, and what the map was
 * when it gave way, to go back to: the levels entered in 2D and where each node of the 3D map stood. */
const MEM = {key: null, network: null, drawn: false, levels: [], positions: null, generation: 0};

/* The server restarts to take new code, and for the second it takes, the browser can reach nothing: a read waits
 * through that and asks again, and a write, which may not be repeated safely, says so in words. */
const DOWN = 'The server was restarting and did not get that. Try again in a moment.';
async function reach(url, options, again = 10) {
  for (let tries = 0; ; tries++) {
    try { return await fetch(url, options); }
    catch (error) {
      if (tries >= again) throw new Error(DOWN);
      await new Promise(done => setTimeout(done, 1000));
    }
  }
}
async function read(name, params = {}) {
  const query = new URLSearchParams({project: S.project, ...(S.base ? {base: S.base} : {}), ...params});
  const response = await reach(`/api/${name}?${query}`, {headers: {Accept: 'application/json'}});
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
  if (layer.kind === 'base') return '--intake';  // the base layer, kind base, keeps the intake color
  if (layer.kind === 'memory') return '--memory';
  const knowledge = S.layers.filter(item => !['base', 'memory'].includes(item.kind));
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
  const listed = S.layers;
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
  if (!$('#adminbox').hidden && !event.target.closest('.clearpick')) showAdmin(false);
  if (!$('#exportbox').hidden && !event.target.closest('.exportpick')) showExport(false);
  if (!$('#agentbox').hidden && !event.target.closest('.agentpick')) showAgentMenu(false);
});

/* ---------- clearing the project: what goes and what stays, asked on the page, VIEW-019 ----------
 * The warning is the command's own caution and the clear is the command's own operation, PROJ-025; every open page,
 * this one among them, follows it by the push, VIEW-018. */
/* The Administration menu, VIEW-019: acts on the project as a whole, reached on purpose. */
function showAdmin(open) {
  $('#adminbox').hidden = !open;
  $('#adminBtn').setAttribute('aria-expanded', String(open));
}
$('#adminBtn').onclick = async event => {
  event.stopPropagation();
  showClear(false);
  showExport(false);
  if (!$('#adminbox').hidden) return showAdmin(false);
  showAdmin(true);
  try { $('#restoreBtn').disabled = !(await getJson(`/api/backups?project=${encodeURIComponent(S.project)}`)).results.length; }
  catch (error) { $('#restoreBtn').disabled = true; }
};
async function restoreFrom(project, backup) {
  const response = await fetch('/api/restore', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({project, backup})});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) return toast(body.error || 'The backup was not restored.');
  fill($('#clearbox'), h('div', {class: 'warn'}, h('span', {class: 'restored'}, body.said),
    body.held_before ? h('span', {class: 'next'}, `What the project held was backed up as ${body.held_before}.`) : null,
    h('div', {class: 'toolbar'}, h('button', {class: 'btn keep', onclick: () => showClear(false)}, 'Close'))));
}
$('#restoreBtn').onclick = async event => {
  event.stopPropagation();
  showAdmin(false);
  let found;
  try { found = (await getJson(`/api/backups?project=${encodeURIComponent(S.project)}`)).results; }
  catch (error) { return toast(error.message); }
  fill($('#clearbox'), h('div', {class: 'warn'}, h('b', {}, `Restore ${S.project} from a backup`),
    h('span', {}, 'What the project holds now is backed up first, so nothing is lost.'),
    h('ul', {class: 'backups'}, found.map(kept => h('li', {}, h('span', {}, kept.name), ` ${kept.held} `,
      h('button', {class: 'btn', onclick: () => restoreFrom(S.project, kept.name)}, 'Restore')))),
    h('div', {class: 'toolbar'}, h('button', {class: 'btn keep', onclick: () => showClear(false)}, 'Close'))));
  showClear(true);
};
function showClear(open) {
  $('#clearbox').hidden = !open;
  $('#clearBtn').setAttribute('aria-expanded', String(open));
}
/* The export menu saves the map as a document the command writes: Markdown, MAP-052, or XML, MAP-059; VIEW-024. */
function showExport(open) {
  $('#exportbox').hidden = !open;
  $('#exportBtn').setAttribute('aria-expanded', String(open));
}
$('#exportBtn').onclick = event => { event.stopPropagation(); showAdmin(false); showExport($('#exportbox').hidden); };
async function exportAs(format, extension, type) {
  showExport(false);
  const query = new URLSearchParams({project: S.project, ...(S.base ? {base: S.base} : {}), ...viewLayers()});
  const response = await fetch(`/api/${format}?${query}`);
  if (!response.ok) return toast((await response.json().catch(() => ({}))).error || 'The map could not be exported.');
  const link = h('a', {href: URL.createObjectURL(new Blob([await response.text()], {type})),
    download: `${S.project}-map.${extension}`});
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}
$('#exportMarkdown').onclick = () => exportAs('markdown', 'md', 'text/markdown');
$('#exportXml').onclick = () => exportAs('xml', 'xml', 'application/xml');
/* The intake's ignore list, .metaform/ignore.txt: what is not the project, said by the person up front, so the
 * intake never reads it and never judges it, Rich 2026-10-08. */
$('#ignoreBtn').onclick = async event => {
  event.stopPropagation();
  showAdmin(false);
  let found;
  try { found = await read('ignore'); } catch (error) { return toast(error.message); }
  const text = h('textarea', {class: 'ignore', rows: 8, spellcheck: 'false',
    'aria-label': 'Intake ignores (one pattern per line, like .gitignore)'});
  text.value = found.text || '';
  fill($('#clearbox'), h('div', {class: 'warn'}, h('b', {}, 'Intake ignores (one pattern per line, like .gitignore)'),
    h('span', {}, `Kept in ${found.file}. The intake never reads what these name.`), text,
    h('button', {onclick: async () => {
      if (await wrote('/api/ignore', {text: text.value})) { toast('Ignore list saved.'); showClear(false); }
    }}, 'Save')));
  showClear(true);
};
$('#clearBtn').onclick = async event => {
  event.stopPropagation();
  showAdmin(false);
  let found;
  try { found = await getJson(`/api/clear-preview?project=${encodeURIComponent(S.project)}`); }
  catch (error) { return toast(error.message); }
  fill($('#clearbox'), h('div', {class: 'warn'}, h('b', {}, 'Are you sure?'), h('span', {}, found.caution),
    h('span', {class: 'backed'}, 'It is backed up first.'),
    ...typedConfirm('Clear it', () => clearProject(found.project))));
  showClear(true);
};
/* The gate on clearing or removing a project: the word confirm, typed, as the command takes --confirm; the
 * destructive button stays off until it is there, Rich 2026-10-07. */
function typedConfirm(verb, act) {
  const field = h('input', {class: 'typed', type: 'text', placeholder: 'confirm', autocomplete: 'off', spellcheck: 'false'});
  const go = h('button', {class: 'btn danger confirm', disabled: true, onclick: act}, verb);
  field.oninput = () => { go.disabled = field.value.trim().toLowerCase() !== 'confirm'; };
  field.onkeydown = event => { if (event.key === 'Enter' && !go.disabled) go.click(); };
  setTimeout(() => field.focus(), 0);
  return [h('label', {class: 'gate'}, 'Type confirm to go on:', field),
    h('div', {class: 'toolbar'}, go, h('button', {class: 'btn keep', onclick: () => showClear(false)}, 'Keep it'))];
}
async function clearProject(project) {
  const response = await fetch('/api/clear-project', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({project, confirm: true})});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) { showClear(false); return toast(body.error || 'The project was not cleared.'); }
  const left = body.not_removed || [];
  fill($('#clearbox'), h('div', {class: 'warn'}, h('span', {class: 'said'}, body.said),
    body.backup ? h('span', {class: 'backed'}, `Backed up as ${body.backup}.`) : null,
    left.length ? [h('b', {}, 'Not removed, still on disk:'),
      h('ul', {class: 'left'}, left.map(item => h('li', {}, `${item.path}: ${item.reason}`)))] : null,
    (body.notices || []).map(notice => h('span', {class: 'next'}, notice.message)),
    h('div', {class: 'toolbar'}, h('button', {class: 'btn keep', onclick: () => showClear(false)}, 'Close'))));
}
/* Remove project takes an empty project off the list, PROJ-031: one that still holds metaforms or reports is named
   with what it holds, since a clear backs it up first. */
$('#removeBtn').onclick = async event => {
  event.stopPropagation();
  showAdmin(false);
  let found;
  try { found = await getJson(`/api/remove-preview?project=${encodeURIComponent(S.project)}`); }
  catch (error) { return toast(error.message); }
  fill($('#clearbox'), found.held
    ? h('div', {class: 'warn'}, h('span', {class: 'held'}, found.held), h('span', {class: 'next'}, 'Use Clear project first.'),
      h('div', {class: 'toolbar'}, h('button', {class: 'btn keep', onclick: () => showClear(false)}, 'Close')))
    : h('div', {class: 'warn'}, h('b', {}, 'Are you sure?'), h('span', {}, found.caution),
      ...typedConfirm('Remove it', () => removeProject(found.project))));
  showClear(true);
};
async function removeProject(project) {
  const response = await fetch('/api/remove-project', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({project, confirm: true})});
  const body = await response.json().catch(() => ({}));
  showClear(false);
  if (!response.ok) return toast(body.error || 'The project was not removed.');
  toast(body.said);
  S.projects = ((await getJson('/api/projects')).projects || []);
  if (!S.projects.length) return location.reload();
  toProject(S.projects[0].id);
  fill($('#proj'), ...S.projects.map(item => h('option', {value: item.id, selected: item.id === S.project}, item.id)));
  await loadProject();
}
/* After a clear the project has no metaform until the next intake, or anything else written to it, makes one. */
const noMetaform = () => !S.bases.length;
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
 * encounter, a link on to each element the join holds, Rich's shape, 2026-10-04; the namespace joins each element to
 * its nearest parent element, VIEW-005. */
function graphData() {
  const nodes = [], links = [];
  const byAddress = new Map([...S.elements.values()].map(entry => [entry.element.address, entry.element.id]));
  for (const {element, parent} of S.elements.values()) {
    nodes.push({id: element.id, t: 'el', name: labelOf(element), address: element.address,
      role: element.role, work: element.open_work || [], layer: element.layer});
    if (parent && byAddress.has(parent)) links.push({source: byAddress.get(parent), target: element.id, k: 'tree'});
  }
  const ids = new Set(nodes.map(node => node.id));
  for (const join of S.joins) {
    const drawnTo = join.providers.filter(id => ids.has(id));
    if (!ids.has(join.receiver) || !drawnTo.length) continue;
    const purpose = 'p:' + join.id;
    nodes.push({id: purpose, t: 'purpose', join: join.id, layer: join.layer, work: join.open_work || []});
    links.push({source: join.receiver, target: purpose, k: 'purpose', layer: join.layer, join: join.id,
      work: join.open_work || []});
    for (const provider of drawnTo)
      links.push({source: purpose, target: provider, k: 'encounter', layer: join.layer, join: join.id,
        work: join.open_work || []});
  }
  // Every item and property of the layers turned on is its own node, hung from its node; a link runs on, VIEW-017.
  const drawnIds = new Set(nodes.map(node => node.id));
  const at = thing => thing.kind === 'property' ? thing.item.element_id : keyOf(thing.item.target);
  // The sources layer's refs are shown in the panel and never hung on the map, Rich 2026-10-04: the map is the design.
  const hung = [...S.items.values()].filter(thing => drawnIds.has(at(thing)) && thing.layer !== 'sources');
  for (const thing of hung) {
    nodes.push({id: thing.key, t: 'item', layer: thing.layer, text: itemText(thing.value)});
    drawnIds.add(thing.key);
  }
  for (const thing of hung) {
    links.push({source: at(thing), target: thing.key, k: 'item', layer: thing.layer});
    const to = keyOf(thing.item.link);
    if (to && drawnIds.has(to)) links.push({source: thing.key, target: to, k: 'relation', layer: thing.layer});
  }
  // Every memory shown at a node is its own node, hung from each node it is kept at, and each relation between two
  // memories drawn is a link, LAYER-013 and VIEW-017.
  const memory = memoryLayer();
  for (const [key, names] of S.memory.at) {
    if (!drawnIds.has(key)) continue;
    for (const name of names) {
      if (!drawnIds.has(memoryKey(name))) {
        nodes.push({id: memoryKey(name), t: 'item', layer: memory, text: name});
        drawnIds.add(memoryKey(name));
      }
      links.push({source: key, target: memoryKey(name), k: 'item', layer: memory});
    }
  }
  for (const relation of S.memory.relations) if (drawnIds.has(memoryKey(relation.from)) && drawnIds.has(memoryKey(relation.to)))
    links.push({source: memoryKey(relation.from), target: memoryKey(relation.to), k: 'relation', layer: memory,
      relation: relation.relationType});
  return {nodes, links};
}
/* A selection is an element's id or a join as 'p:<id>', the same keys the 3D view uses. */
/* A join as Rich's shape holds it, 2026-10-04: `providers` are the ids of every element it holds, each a provider;
 * `provider` and `provider_address` name the first, the one that names the join beside its receiver. */
const withProviders = join => ({...join, providers: (join.elements || []).map(each => each.element_id),
  provider: join.elements?.[0]?.element_id, provider_address: join.elements?.[0]?.address});
const accessed = (value, item) => typeof value === 'function' ? value(item) : value;
const joinOf = key => S.joins.find(join => 'p:' + join.id === key);
window.metaform = {graph: () => graphData(), selected: () => S.selected, select: id => select(id, true),
  click3d: id => clicked3d(G?.graphData().nodes.find(node => node.id === id)),
  drawn: () => G ? {nodes: G.graphData().nodes.length, links: G.graphData().links.length} : null,
  curves: () => G ? G.graphData().links.map(link => ({k: link.k, curve: accessed(G.linkCurvature(), link)})) : [],
  linkColors: () => G ? G.graphData().links.map(link => ({join: link.join || null, k: link.k,
    target: link.target?.id ?? link.target, color: linkColor(link)})) : [],
  layouts: () => V3.layouts, drawnWork: id => (G?.graphData().nodes.find(node => node.id === id)?.work || []).length,
  loaded: () => !S.loading && !S.opening, editor: () => P.editor, live: () => LIVE.layer, changes: () => LIVE.done,
  inside: () => IN.length && M.drawn === IN.at(-1) ? [...M.nodes.keys()] : [], vertical: () => M.vertical,
  at2d: id => M.nodes.has(id) ? {x: M.nodes.get(id).x, y: M.nodes.get(id).y} : null,
  look: id => look(id), fit: () => fit2D(), menu: id => menu(id), task: id => giveWork(id), element: id => addElement(id), note: id => notesAt(id),
  // The memory network of a node, VIEW-031: opened as the menu's entry opens it, and what both views draw of it, or
  // null on the map.
  memories: id => memories(id),
  memory: () => MEM.key && MEM.drawn ? {key: MEM.key, nodes: G ? G.graphData().nodes.map(node => node.id) : [],
    links: G ? G.graphData().links.map(link => ({source: endOf(link.source), target: endOf(link.target), relation: link.relation})) : [],
    nodes2d: [...M.nodes.keys()]} : null,
  away3d: () => G ? G.camera().position.distanceTo(G.controls().target) : 0, fits3d: () => V3.fits,
  samples3d: () => G ? G.postProcessingComposer().renderTarget1.samples : 0,
  samplesFor: name => samplesFor(name), drawnBy: () => G ? drawnBy() : '',
  // The samples a pixel are set, so a browser check can compare the picture with the smoothing and without it.
  smooth3d: samples => { if (!G) return; const chain = G.postProcessingComposer();
    for (const target of [chain.renderTarget1, chain.renderTarget2]) { target.samples = samples; target.dispose(); } },
  // The 3D map stops drawing, or draws again, so a browser check that steps the page's clock frame by frame to read
  // the 2D camera does not draw the 3D map at every step.
  pause3d: on => { if (G) { if (on) G.pauseAnimation(); else G.resumeAnimation(); } },
  zoom3d: share => { if (G) { const at = G.camera().position; G.cameraPosition({x: at.x * share, y: at.y * share, z: at.z * share}, undefined, 0); } },
  glass: (on, options = {}, segments = 16) => {  // to measure what it costs
    if (!G) return;
    Object.assign(GLASS, options);
    SEGMENTS = segments;
    shapes.clear();
    G.nodeThreeObject(node => asText(node) ? written(node) : on && isGlass(node) ? bead(node) : false);
  }, bloom: () => ({pass: Boolean(BLOOM), levels: BLOOM ? BLOOM.levels : 0, on: Boolean(BLOOM?.enabled)}),
  wave: () => ({dots: W.dots.length, shapes: G ? G.renderer().info.memory.geometries : 0,
    lit: G ? G.graphData().nodes.filter(node => node.__threeObj?.material?.userData.pulsed).map(node => node.id) : []}),
  // A node put where given and held there, the camera pointed, and where a node is on the page with its radius, so a
  // browser check can read a picture of the 3D map at known points.
  pin3d: (id, x, y, z) => {
    const node = G?.graphData().nodes.find(item => item.id === id);
    if (node) { Object.assign(node, {x, y, z, fx: x, fy: y, fz: z}); G.d3ReheatSimulation(); }
  },
  view3d: (from, to) => { if (G) G.cameraPosition(from, to, 0); },
  screen3d: id => {
    const node = G?.graphData().nodes.find(item => item.id === id);
    if (!node || node.x === undefined) return null;
    const point = G.graph2ScreenCoords(node.x, node.y, node.z), camera = G.camera(), box = $('#stage').getBoundingClientRect();
    const distance = Math.hypot(camera.position.x - node.x, camera.position.y - node.y, camera.position.z - node.z);
    return {x: box.left + point.x, y: box.top + point.y,
      r: Math.cbrt(nodeSize(node)) * 3 / (distance * Math.tan(camera.fov * Math.PI / 360)) * box.height / 2};
  },
  waveTimes: times => { Object.assign(TIMES, times, {gaussian: times.gaussian === false ? [] : times.gaussian || TIMES.gaussian}); W.next = W.clock; },
  reach: () => ({property: R.key, edges: R.edges,
    elements: [...S.elements.values()].map(entry => entry.element).filter(element => R.nodes.has(element.id)).map(element => element.address)}),
  own: id => { const node = G ? G.graphData().nodes.find(item => item.id === id) : null; return node ? ownColor(node).toLowerCase() : null; },
  box2d: id => { const box = M.nodes.get(id)?.g.getBoundingClientRect(); return box ? {left: box.left, right: box.right, top: box.top, bottom: box.bottom} : null; },
  edge2d: join => [...(M.base?.edges.find(edge => edge.join.id === join)?.path?.classList || [])]
    .filter(name => name.startsWith('work-')),
  // The dots that travel the joins held still at a share of the way along each link, and where on the page each
  // link's dots are, so a browser check can read a picture of a dot passing through a node.
  dots3d: along => {
    if (!G) return [];
    G.linkDirectionalParticleSpeed(0);
    const box = $('#stage').getBoundingClientRect();
    return G.graphData().links.filter(link => link.__photonsObj?.children.length).map(link => {
      for (const dot of link.__photonsObj.children) dot.__progressRatio = along;
      const from = link.source, to = link.target;
      const point = G.graph2ScreenCoords(from.x + (to.x - from.x) * along, from.y + (to.y - from.y) * along,
        from.z + (to.z - from.z) * along);
      return {source: from.id, target: to.id, x: box.left + point.x, y: box.top + point.y};
    });
  },
  // Each label of the 3D map: its text and lines, where it is on the page, its rank by depth, higher nearer, whether it
  // is under a nearer node or label, its color and its opacity, and whether it is in the scene and drawn with the depth
  // test and writing depth, which is what orders it with the nodes and the other labels, VIEW-038.
  labels3d: () => { const area = $('#stage').getBoundingClientRect();
    return [...tags.values()].map(tag => ({id: tag.id, text: tag.text, lines: tag.lines, hidden: tag.hidden, z: tag.z,
      under: tag.under, color: tag.color.toLowerCase(), opacity: tag.sprite.material.opacity, scene: tag.sprite.parent?.parent === G.scene(),
      depthTest: tag.sprite.material.depthTest, depthWrite: tag.sprite.material.depthWrite, left: area.left + (tag.rect?.left ?? 0), right: area.left + (tag.rect?.right ?? 0),
      top: area.top + (tag.rect?.top ?? 0), bottom: area.top + (tag.rect?.bottom ?? 0)})); },
  showLabels3d: on => { LABELS.on = Boolean(on); if (LABELS.group) LABELS.group.visible = LABELS.on; },
  hover3d: id => { const node = G?.graphData().nodes.find(item => item.id === id); hovered = node || null;
    $('#tip3d').hidden = !hovered; if (hovered) { fill($('#tip3d'), tipFor(hovered)); placeTip(); } },
  figures2d: () => [...ROAM2D.figures.values()].map(figure => ({work_id: figure.id, glyph: figure.glyph, stage: figure.stage,
    target: figure.target, home: figure.home, x: figure.x, y: figure.y, size: figure.size, angle: figure.angle,
    shown: Boolean(figure.g.isConnected && M.svg && M.svg.contains(figure.g)), icon: figure.g.querySelector('image').getAttribute('href')})),
  figures: () => [...ROAM.figures.values()].map(figure => ({work_id: figure.id, glyph: figure.glyph, stage: figure.stage,
    target: figure.target, home: figure.home, x: figure.mesh.position.x, y: figure.mesh.position.y, z: figure.mesh.position.z,
    scale: figure.mesh.scale.x, angle: figure.angle, clock: figure.clock, px: onScreen(figure.mesh)})),
  at3d: id => { const node = G ? G.graphData().nodes.find(item => item.id === id) : null;
    return node && node.x !== undefined ? {x: node.x, y: node.y, z: node.z, r: Math.cbrt(nodeSize(node)) * 3} : null; },
  ground: () => G ? G.backgroundColor() : null};

/* How a node is drawn for its condition, MAP-046, readable by a browser check: its open work, the 2D group's work
 * classes, computed opacity and whether its box is animating, and the 3D sphere's material opacity and whether it is
 * red at this frame. */
const BOX = new THREE.Box3();
function onScreen(mesh) {  // how many pixels a figure spans in the 3D view, across or up, VIEW-035
  BOX.setFromObject(mesh);
  const xs = [], ys = [];
  for (const x of [BOX.min.x, BOX.max.x]) for (const y of [BOX.min.y, BOX.max.y]) for (const z of [BOX.min.z, BOX.max.z]) {
    const point = G.graph2ScreenCoords(x, y, z);
    xs.push(point.x); ys.push(point.y);
  }
  return Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
}
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
    turns: writing.get(id)?.rate ?? 0, pace: node ? paceOf(node) : null,
    text: textOf(id), signal3d: writing.get(id)?.reached ?? 0, signalColor3d: writing.get(id)?.signalColor ?? null,
    glow2d: Boolean(box) && ['broken', 'fixing', 'exclude', 'question', 'message'].some(name => group.classList.contains('work-' + name))
      && [group, box].some(part => getComputedStyle(part).filter.includes('drop-shadow')),
    red3d: material ? '#' + material.color.getHexString() === css('--broken').toLowerCase() : false,
    material: material ? (material instanceof MeshTransmissionMaterial ? 'MeshTransmissionMaterial' : material.type) : null,
    // the light the glass lets through: drei's own amount, since three.js's `transmission` stays 0
    transmission: material ? (material._transmission ?? material.transmission) || 0 : 0,
    chromatic: material?.chromaticAberration ?? 0, distortion: material?.distortion ?? 0,
    // the near wall reads the picture that holds the far walls, and its far wall is drawn into it
    backside: Boolean(material?.userData.back && BEHIND.main && material.buffer === BEHIND.main.texture
      && material.userData.back.side === THREE.BackSide),
    shape: node?.__threeObj?.geometry ? node.__threeObj.geometry.uuid : null,
    // what is drawn around the node besides the node itself; the node that fades in over text is the node
    around3d: node?.__threeObj ? node.__threeObj.children.filter(child => !child.userData.arriving).length : null,
    reach3d: R.nodes.has(id), reach2d: Boolean(group?.classList.contains('reach')),

    bloom2d: Boolean(box && getComputedStyle(group).filter.includes('drop-shadow')),
    color3d: material ? '#' + material.color.getHexString() : null,
    label3d: (tags.get(id)?.classes || []).filter(name => name.startsWith('work-')),
    stroke2d: box ? toHex(getComputedStyle(box).stroke) : null,
    exclude3d: material ? '#' + material.color.getHexString() === css('--exclude').toLowerCase() : false};
}

/* ---------- 3D: a synaptic map, drawn as the approved prototype draws it ---------- */
const CONDITIONS = ['missing', 'in-progress', 'broken', 'fixing', 'flawed', 'enhancement', 'exclude', 'question', 'message'];
/* The agents at work, VIEW-035: a figure for each ticket an agent works, from the moment it is taken until it is
 * closed. It materializes on the most primary node, the DE, makes its way along the map's own edges to the ticket's
 * node, goes onto it and circles it slowly, facing the way it moves, at one steady pace until the ticket is closed;
 * then it makes its way back and is gone. Steps filed never speed it up: the node's flashing, or its text for a part
 * not built, shows how far along the work is. A figure is big enough to see what it is with the whole map in view:
 * its size is a share of the drawn map's span, and never less than ROAM.size. A ticket that was finished before its
 * figure got there is still touched, and then the figure walks back. A figure is one of the seventeen characters of
 * agents3d.js, drawn so that no two at work look alike. With reduced motion it stands at the node. */
const ROAM = {figures: new Map(), seen: new Set(), last: 0, speed: 70, size: 2.6, share: 0.11, orbit: 1.5, lap: 12,
  recent: 120, appear: 0.8, touch: 0.9, vanish: 0.6};
const nodeById = (data, id) => data.nodes.find(node => node.id === id);
const primaryOf = data => data.nodes.find(node => node.t === 'el' && node.role === 'DE') || data.nodes.find(node => node.t === 'el');
const ticketNode = ticket => ticket.node_kind === 'join' ? 'p:' + ticket.node_id : ticket.node_id;
const ballOf = node => Math.cbrt(nodeSize(node)) * 3;
function sizeOf(data) {  // a figure's size: a share of half the drawn map's widest side
  const low = [Infinity, Infinity, Infinity], high = [-Infinity, -Infinity, -Infinity];
  for (const node of data.nodes) {
    if (node.x === undefined) continue;
    [node.x, node.y, node.z].forEach((at, axis) => { low[axis] = Math.min(low[axis], at); high[axis] = Math.max(high[axis], at); });
  }
  const half = Math.max(0, ...high.map((top, axis) => (top - low[axis]) / 2).filter(Number.isFinite));
  return Math.max(ROAM.size, ROAM.share * half);
}
function routeOf(data, from, to) {  // the fewest edges of the drawn map from one node to another
  const near = new Map(), add = (one, two) => { if (!near.has(one)) near.set(one, []); near.get(one).push(two); };
  for (const link of data.links) { add(endOf(link.source), endOf(link.target)); add(endOf(link.target), endOf(link.source)); }
  const back = new Map([[from, null]]), queue = [from];
  while (queue.length && !back.has(to)) {
    const at = queue.shift();
    for (const next of near.get(at) || []) if (!back.has(next)) { back.set(next, at); queue.push(next); }
  }
  if (!back.has(to)) return [from, to];
  const path = [];
  for (let at = to; at !== null; at = back.get(at)) path.unshift(at);
  return path;
}
/* The figures, VIEW-035: one for each ticket an agent is working in a live session, the agents key's own list, so an
 * agent that is not active is not on the map, whatever its ticket says; when its session ends the figure walks back
 * and is gone. */
const liveWork = () => new Set(D.sessions.filter(one => one.activity === 'working')
  .map(one => one.work_id));
function figures(tickets) {
  figures2d(tickets);
  if (!G) return;
  const data = G.graphData(), home = primaryOf(data);
  if (!home) return;
  const live = liveWork();
  for (const ticket of tickets) {
    const figure = ROAM.figures.get(ticket.id), target = ticketNode(ticket);
    if (figure) { figure.done = Boolean(ticket.done) || !live.has(ticket.id); continue; }
    const working = live.has(ticket.id) && !ticket.done;
    if (working && !ROAM.seen.has(ticket.id) && nodeById(data, target)) {
      const glyph = drawGlyph(ticket.id, ownGlyph(ticket)), mesh = createAgent(glyph);
      mesh.scale.setScalar(0.001);
      G.scene().add(mesh);
      ROAM.seen.add(ticket.id);
      ROAM.figures.set(ticket.id, {id: ticket.id, glyph, mesh, home: home.id, target, stage: 'arriving',
        path: routeOf(data, home.id, target), leg: 0, along: 0, clock: 0, angle: Math.random() * Math.PI * 2,
        done: Boolean(ticket.done)});
    }
  }
  for (const [id, figure] of ROAM.figures) if (!tickets.some(ticket => ticket.id === id)) figure.done = true;
}
const AHEAD = new THREE.Vector3();
function roam3d(data) {
  const now = performance.now() / 1000, passed = Math.min(0.1, Math.max(0, now - (ROAM.last || now)));
  ROAM.last = now;
  const size = ROAM.figures.size ? sizeOf(data) : ROAM.size;
  for (const [id, figure] of ROAM.figures) {
    const {mesh} = figure;
    const gone = () => { G.scene().remove(mesh); releaseGlyph(id); ROAM.figures.delete(id); };
    figure.clock += passed;
    const target = nodeById(data, figure.target), home = nodeById(data, figure.home);
    if (!target || target.x === undefined || !home || home.x === undefined) continue;
    if (reduced()) {  // no walking: the figure stands on its node while the ticket is worked
      mesh.position.set(target.x, target.y + ballOf(target) + size, target.z);
      mesh.scale.setScalar(size);
      if (figure.done) gone();
      continue;
    }
    if (figure.stage === 'arriving') {  // it materializes on the most primary node
      const grown = Math.min(1, figure.clock / ROAM.appear), over = 1 + 1.7 * Math.pow(grown - 1, 3) + 0.7 * Math.pow(grown - 1, 2);
      mesh.position.set(home.x, home.y + ballOf(home) + size * 0.6, home.z);
      mesh.scale.setScalar(size * Math.max(0.001, over));
      if (grown >= 1) Object.assign(figure, {stage: 'going', leg: 0, along: 0, clock: 0});
    } else if (figure.stage === 'going' || figure.stage === 'returning') {  // along the map's own edges
      const from = nodeById(data, figure.path[figure.leg]), to = nodeById(data, figure.path[figure.leg + 1]);
      if (!from || !to || from.x === undefined || to.x === undefined) {
        Object.assign(figure, figure.stage === 'going' ? {stage: figure.done ? 'touching' : 'circling'} : {stage: 'leaving'}, {clock: 0});
        continue;
      }
      AHEAD.set(to.x - from.x, to.y - from.y, to.z - from.z);
      const length = Math.max(1, AHEAD.length());
      figure.along = Math.min(1, figure.along + passed * ROAM.speed / length);
      const hop = Math.sin(Math.PI * figure.along) * Math.min(6, length * 0.08);
      mesh.position.set(from.x + AHEAD.x * figure.along, from.y + AHEAD.y * figure.along + size * 0.6 + hop,
        from.z + AHEAD.z * figure.along);
      mesh.scale.setScalar(size);
      orientAgent(mesh, AHEAD, 0.25);
      if (figure.along >= 1) {
        figure.leg += 1;
        figure.along = 0;
        if (figure.leg >= figure.path.length - 1) {
          Object.assign(figure, {clock: 0, stage: figure.stage === 'returning' ? 'leaving' : figure.done ? 'touching' : 'circling'});
        }
      }
    } else if (figure.stage === 'circling') {  // on the node, around it, slowly at one steady pace
      const out = Math.min(1, figure.clock / 0.6), eased = 1 - Math.pow(1 - out, 3);  // it spirals out onto its orbit
      const reach = (ballOf(target) + size * ROAM.orbit) * eased;
      figure.angle += passed * 2 * Math.PI / ROAM.lap;
      const turn = figure.angle;
      mesh.position.set(target.x + Math.cos(turn) * reach, target.y + Math.sin(turn * 2) * reach * 0.18 + size * 0.3,
        target.z + Math.sin(turn) * reach);
      mesh.scale.setScalar(size);
      AHEAD.set(-Math.sin(turn), Math.cos(turn * 2) * 0.36, Math.cos(turn));
      orientAgent(mesh, AHEAD, 0.3);
      if (figure.done) Object.assign(figure, {stage: 'returning', path: routeOf(data, figure.target, figure.home), leg: 0, along: 0, clock: 0});
    } else if (figure.stage === 'touching') {  // finished before it got there: it still touches the node
      const dip = Math.min(1, figure.clock / ROAM.touch);
      mesh.position.set(target.x, target.y + ballOf(target) * (1 - 0.6 * Math.sin(Math.PI * dip)) + size * 0.4, target.z);
      if (dip >= 1) Object.assign(figure, {stage: 'returning', path: routeOf(data, figure.target, figure.home), leg: 0, along: 0, clock: 0});
    } else if (figure.stage === 'leaving') {  // home again, it is gone
      const faded = Math.min(1, figure.clock / ROAM.vanish);
      mesh.scale.setScalar(size * Math.max(0.001, 1 - faded));
      if (faded >= 1) { gone(); continue; }
    }
    mesh.userData.update(passed);
  }
}
/* The agents in 2D, VIEW-035: the same agents as the 3D map's figures, each drawn as its flat glyph,
 * page/agent-glyphs/<glyph>.svg, the glyph its 3D figure is drawn with. It appears on the DE, walks the 2D map's own
 * edges to its ticket's node, circles the node's box while the ticket is open, and when the ticket closes walks back
 * and is gone; a join's ticket is circled at the middle of the join's edge. Its size is a share of a node's height,
 * so it keeps its place beside the boxes at any zoom. With reduced motion it stands above its node. */
const ROAM2D = {figures: new Map(), seen: new Set(), frame: 0, last: 0, speed: 240, size: 1.2, orbit: 0.45, lap: 12,
  appear: 0.8, touch: 0.9, vanish: 0.6};
const home2d = () => [...S.elements.values()].find(item => item.element.role === 'DE')?.element.id
  || S.elements.keys().next().value;
function route2d(base, from, to) {  // the fewest edges of the 2D map from one element to another
  const near = new Map(), add = (one, two) => { if (!near.has(one)) near.set(one, []); near.get(one).push(two); };
  for (const {join, provider} of base.edges) { add(join.receiver, provider); add(provider, join.receiver); }
  const back = new Map([[from, null]]), queue = [from];
  while (queue.length && !back.has(to)) {
    const at = queue.shift();
    for (const next of near.get(at) || []) if (!back.has(next)) { back.set(next, at); queue.push(next); }
  }
  if (!back.has(to)) return [from, to];
  const path = [];
  for (let at = to; at !== null; at = back.get(at)) path.unshift(at);
  return path;
}
function spot2d(base, key) {  // where a 2D figure stands: an element's box, or the middle of a join's edge
  if (!key.startsWith('p:')) { const node = base.nodes.get(key); return node && {x: node.x, y: node.y, w: node.w, h: node.h}; }
  const path = base.edges.find(edge => edge.join.id === key.slice(2))?.path;
  if (!path?.getTotalLength) return null;
  const middle = path.getPointAtLength(path.getTotalLength() / 2);
  return {x: middle.x, y: middle.y, w: 0, h: 0};
}
function target2d(base, ticket) {  // the ticket's place, and the element its walk ends at
  if (ticket.node_kind !== 'join') return base.nodes.has(ticket.node_id) ? {key: ticket.node_id, last: ticket.node_id} : null;
  const edge = base.edges.find(one => one.join.id === ticket.node_id);
  return edge ? {key: 'p:' + ticket.node_id, last: edge.join.receiver} : null;
}
function back2d(base, figure) {  // the way home, from the middle of a join's edge through its receiver
  const way = route2d(base, figure.last, figure.home);
  return figure.target === figure.last ? way : [figure.target, ...way];
}
function figures2d(tickets) {
  const base = M.base, home = base && home2d();
  if (!base || !home || !base.nodes.has(home)) return;
  const live = liveWork();
  for (const ticket of tickets) {
    const figure = ROAM2D.figures.get(ticket.id);
    if (figure) { figure.done = Boolean(ticket.done) || !live.has(ticket.id); continue; }
    const working = live.has(ticket.id) && !ticket.done, target = working && target2d(base, ticket);
    if (target && !ROAM2D.seen.has(ticket.id)) {
      const glyph = ROAM.figures.get(ticket.id)?.glyph || glyphFor(ticket.id);
      const g = document.createElementNS(SVG, 'g'), image = document.createElementNS(SVG, 'image');
      g.setAttribute('class', 'agent2d');
      g.dataset.glyph = glyph;
      image.setAttribute('href', `/page/agent-glyphs/${glyph}.svg`);
      g.append(image);
      ROAM2D.seen.add(ticket.id);
      ROAM2D.figures.set(ticket.id, {id: ticket.id, glyph, g, home, target: target.key, last: target.last, stage: 'arriving',
        path: route2d(base, home, target.last), leg: 0, along: 0, clock: 0, angle: Math.random() * Math.PI * 2,
        x: 0, y: 0, size: 0, done: Boolean(ticket.done)});
    }
  }
  for (const [id, figure] of ROAM2D.figures) if (!tickets.some(ticket => ticket.id === id)) figure.done = true;
  if (ROAM2D.figures.size && !ROAM2D.frame) ROAM2D.frame = requestAnimationFrame(roam2d);
}
function layer2d(base) {  // the figures are drawn over the boxes, in the boxes' own coordinates
  if (base.agents?.isConnected || (base.agents && base.svg.contains(base.agents))) return base.agents;
  const holder = base.nodes.values().next().value?.g.parentNode;
  if (!holder) return null;
  base.agents = document.createElementNS(SVG, 'g');
  base.agents.setAttribute('class', 'agents2d');
  holder.append(base.agents);
  const heights = [...base.nodes.values()].map(node => node.h).sort((one, two) => one - two);
  base.agentSize = ROAM2D.size * (heights[Math.floor(heights.length / 2)] || 40);
  return base.agents;
}
function roam2d() {
  ROAM2D.frame = 0;
  const now = performance.now() / 1000, passed = Math.min(0.1, Math.max(0, now - (ROAM2D.last || now)));
  ROAM2D.last = now;
  const base = M.base, layer = base && layer2d(base);
  for (const [id, figure] of ROAM2D.figures) {
    const gone = () => { figure.g.remove(); ROAM2D.figures.delete(id); if (!ROAM.figures.has(id)) releaseGlyph(id); };
    if (!layer) { if (figure.done) gone(); continue; }
    if (figure.g.parentNode !== layer) layer.append(figure.g);
    figure.clock += passed;
    const size = base.agentSize, target = spot2d(base, figure.target), home = spot2d(base, figure.home);
    if (!target || !home) { if (figure.done) gone(); continue; }
    let x = target.x, y = target.y, scale = 1;
    if (reduced()) {  // no walking: it stands above its node while the ticket is worked
      y = target.y - target.h / 2 - size / 2;
      if (figure.done) { gone(); continue; }
    } else if (figure.stage === 'arriving') {  // it appears on the DE
      const grown = Math.min(1, figure.clock / ROAM2D.appear);
      ({x, y} = home); scale = Math.max(0.001, 1 + 1.7 * Math.pow(grown - 1, 3) + 0.7 * Math.pow(grown - 1, 2));
      if (grown >= 1) Object.assign(figure, {stage: 'going', leg: 0, along: 0, clock: 0});
    } else if (figure.stage === 'going' || figure.stage === 'returning') {  // along the map's own edges
      const from = spot2d(base, figure.path[figure.leg]), to = spot2d(base, figure.path[figure.leg + 1]);
      if (!from || !to) {
        Object.assign(figure, figure.stage === 'going' ? {stage: figure.done ? 'touching' : 'circling'} : {stage: 'leaving'}, {clock: 0});
        ({x, y} = figure); continue;
      }
      const length = Math.max(1, Math.hypot(to.x - from.x, to.y - from.y));
      figure.along = Math.min(1, figure.along + passed * ROAM2D.speed / length);
      x = from.x + (to.x - from.x) * figure.along;
      y = from.y + (to.y - from.y) * figure.along - Math.sin(Math.PI * figure.along) * Math.min(size * 0.4, length * 0.08);
      if (figure.along >= 1) {
        Object.assign(figure, {leg: figure.leg + 1, along: 0});
        if (figure.leg >= figure.path.length - 1) {
          // a join's figure steps from its receiver onto the middle of the join's edge
          if (figure.stage === 'going' && figure.path.at(-1) !== figure.target) figure.path.push(figure.target);
          else Object.assign(figure, {clock: 0, stage: figure.stage === 'returning' ? 'leaving' : figure.done ? 'touching' : 'circling'});
        }
      }
    } else if (figure.stage === 'circling') {  // around its box, slowly at one steady pace
      const out = Math.min(1, figure.clock / 0.6), eased = 1 - Math.pow(1 - out, 3);  // it spirals out onto its orbit
      figure.angle += passed * 2 * Math.PI / ROAM2D.lap;
      x = target.x + Math.cos(figure.angle) * (target.w / 2 + size * ROAM2D.orbit) * eased;
      y = target.y + Math.sin(figure.angle) * (target.h / 2 + size * ROAM2D.orbit) * eased;
      if (figure.done) Object.assign(figure, {stage: 'returning', path: back2d(base, figure), leg: 0, along: 0, clock: 0});
    } else if (figure.stage === 'touching') {  // finished before it got there: it still touches the node
      const dip = Math.min(1, figure.clock / ROAM2D.touch);
      scale = 1 - 0.3 * Math.sin(Math.PI * dip);
      if (dip >= 1) Object.assign(figure, {stage: 'returning', path: back2d(base, figure), leg: 0, along: 0, clock: 0});
    } else if (figure.stage === 'leaving') {  // home again, it is gone
      const faded = Math.min(1, figure.clock / ROAM2D.vanish);
      ({x, y} = home); scale = Math.max(0.001, 1 - faded);
      if (faded >= 1) { gone(); continue; }
    }
    Object.assign(figure, {x, y, size: size * scale});
    const image = figure.g.firstChild, drawn = size * scale;
    image.setAttribute('x', x - drawn / 2); image.setAttribute('y', y - drawn / 2);
    image.setAttribute('width', drawn); image.setAttribute('height', drawn);
  }
  if (ROAM2D.figures.size) ROAM2D.frame = requestAnimationFrame(roam2d);
}
/* A ticket's light, VIEW-035: broken flashes red, flawed yellow and enhancement green. Flashing lets the node's own
 * color show between flashes, and each step filed makes it faster: from FLASH.slow a beat while it waits, to
 * FLASH.fast as the steps planned are filed, or a little faster with each step when none were planned. */
const LIGHTS = [['broken', '--broken'], ['fixing', '--broken'], ['flawed', '--flawed'], ['enhancement', '--enhancement']];
const FLASH = {slow: 1.2, fast: 0.24, step: 0.35};
function paceOf(node) {
  const done = S.progress?.get(node.id);
  if (!done || !done.filed) return FLASH.slow;
  const share = done.planned ? Math.min(1, done.filed / done.planned) : 1 - 1 / (1 + FLASH.step * done.filed);
  return FLASH.slow + (FLASH.fast - FLASH.slow) * share;
}
const lightOf = node => LIGHTS.find(([condition]) => has(node, condition));
const has = (node, condition) => (node.work || []).includes(condition);
function colorOf(node) {
  if (node.t === 'el') return has(node, 'exclude') ? css('--exclude') : node.role === 'CQU' ? css('--signal')
    : node.role === 'DE' ? css('--de') : layerColor(node.layer);
  if (has(node, 'exclude')) return css('--exclude');
  if (node.t === 'purpose') return css('--text');
  return layerColor(node.layer);
}
/* The color an object has apart from any condition, which a exclude record pulses against. */
const ownColor = node => colorOf({...node, work: []});
/* A dimmed node keeps its own hue: its color with part of the background mixed in, the share set by the theme. */
function dim(color) {
  const keep = Number(css('--dim-keep')), channels = hex => [1, 3, 5].map(at => parseInt(hex.slice(at, at + 2), 16));
  const back = channels(css('--ground'));
  return '#' + channels(color).map((own, at) => Math.round(keep * own + (1 - keep) * back[at]).toString(16).padStart(2, '0')).join('');
}
const dimmed = node => S.selected && node.t === 'el' && node.id !== S.selected && !S.neighbors.has(node.id);
/* A node's color, given to whatever it is made of: glass takes it as its tint, as the color light takes on inside
 * it, and as the light it gives off. */
function colored(material, color) {
  material.color.set(color);
  if (material.isMeshPhysicalMaterial) { material.attenuationColor.set(color); material.emissive.set(color); }
}
/* Glass, VIEW-025: in every theme an element is made of a material that obeys reality. Light passes through it and
 * is tinted by it, so the theme's background shows through the node. It gives off a little of its own color, since
 * clear glass on a dark background with nothing to reflect shows as black. It is drei's transmission material: the
 * light behind it is read `samples` times, each color at its own index of refraction, which parts the colors at the
 * edges, `chromaticAberration`; the surface bends it by a noise, `distortion` at `distortionScale`, drifting at
 * `temporalDistortion`; the reads spread along the ray blur it, `anisotropicBlur`. What is behind the glass is drawn
 * by `addBehind`, as drei's own component draws it, with the far wall of every node in it: a node shows its own far
 * wall and the glass behind it, the backside. The drei values are a start and are not settled: with the frosting and
 * the absorption above, what is behind a node is blurred and tinted almost to its own color, so they hardly show. One
 * shape serves every node of a size. */
const GLASS = {transmission: 0.7, thickness: 9, roughness: 0.3, ior: 1.35, attenuationDistance: 7, clearcoat: 0.6,
  clearcoatRoughness: 0.25, emissiveIntensity: 0.45, metalness: 0,
  chromaticAberration: 0.06, distortion: 0.25, distortionScale: 0.35, temporalDistortion: 0.1, anisotropicBlur: 0.1,
  samples: 6};
const DRIFT = {value: 0};  // the one clock the distortion of every node drifts by; still with reduced motion
const shapes = new Map();
let SEGMENTS = 16;  // as the graph draws its own nodes; 32 halves the frame rate where there is no graphics card
const isGlass = node => node.t === 'el';
function bead(node) {
  const radius = Math.cbrt(nodeSize(node)) * 3;  // as the graph sizes a node: the cube root of its value, times 3
  if (!shapes.has(radius)) shapes.set(radius, new THREE.SphereGeometry(radius, SEGMENTS, SEGMENTS));
  const {transmission, thickness, roughness, attenuationDistance, chromaticAberration, distortion, distortionScale,
    temporalDistortion, anisotropicBlur, samples, ...physical} = GLASS;
  // drei's amount of light let through is `_transmission`; three.js's own `transmission` stays 0, since the page
  // draws what is behind the glass itself.
  const made = side => Object.assign(new MeshTransmissionMaterial({samples, _transmission: transmission, thickness,
    roughness, attenuationDistance, chromaticAberration, distortion, distortionScale, temporalDistortion,
    anisotropicBlur}), physical, {side});
  // The near wall reads the picture with every far wall in it. The far wall is a material of its own, since three.js
  // keeps a material's program when only its side changes; it shares every setting of the near wall but the picture
  // it reads, which is the scene with no glass in it.
  const material = made(THREE.FrontSide), back = made(THREE.BackSide);
  material.uniforms.time = DRIFT;
  material.uniforms.buffer.value = BEHIND.main?.texture ?? null;
  back.uniforms = {...material.uniforms, buffer: {value: BEHIND.back?.texture ?? null}};
  material.userData.back = back;
  back.userData.front = material;
  material.userData.own = true;
  colored(material, colorOf(node));
  return new THREE.Mesh(shapes.get(radius), material);
}
/* What is behind the glass, drawn each frame as drei's component draws it, once for every node, VIEW-025: the scene
 * with the glass hidden, into `back`; then with the far wall of every node, which reads `back`, into `main`; and the
 * near walls read `main` in the frame itself. Both are drawn at `scale` of the view's size, drei's `resolution` and
 * `backsideResolution`. It runs before the frame in the graph's own render chain. */
const BEHIND = {back: null, main: null, scale: 0.5};
function addBehind() {
  const composer = G.postProcessingComposer();
  if (!composer?.insertPass) return;
  const type = THREE.HalfFloatType;  // light over full brightness, seen through glass, is still spread by the bloom
  BEHIND.back = new THREE.WebGLRenderTarget(1, 1, {type});
  BEHIND.main = new THREE.WebGLRenderTarget(1, 1, {type});
  composer.insertPass({isPass: true, enabled: true, needsSwap: false, clear: false, renderToScreen: false,
    setSize(width, height) {
      const size = [Math.max(1, Math.round(width * BEHIND.scale)), Math.max(1, Math.round(height * BEHIND.scale))];
      BEHIND.back.setSize(...size);
      BEHIND.main.setSize(...size);
    },
    render(renderer) {
      const scene = G.scene(), camera = G.camera(), glass = [], was = renderer.getRenderTarget();
      scene.traverseVisible(object => { if (object.material?.userData.back) glass.push(object); });
      if (!glass.length) return;
      for (const object of glass) object.visible = false;
      renderer.setRenderTarget(BEHIND.back);
      renderer.render(scene, camera);
      // The far wall takes the node's tint and gives off no light toward the eye: a node's light leaves its glass
      // outward, so the far wall's light goes away from the eye, and the node is as bright as its near wall makes it.
      for (const object of glass) {
        const near = object.material, far = near.userData.back;
        far.color.copy(near.color);
        Object.assign(far, {emissiveIntensity: 0, opacity: near.opacity, transparent: near.transparent});
        Object.assign(object, {material: far, visible: true});
      }
      renderer.setRenderTarget(BEHIND.main);
      renderer.render(scene, camera);
      for (const object of glass) object.material = object.material.userData.front;
      renderer.setRenderTarget(was);
    },
    dispose() { BEHIND.back.dispose(); BEHIND.main.dispose(); }}, 0);
}
/* The light a node gives off, VIEW-029: the glass's own little light, VIEW-025, raised toward LIGHT in the given
 * color by `lit`, from 0 to 1. Above full brightness it is spread by the bloom pass past the node's outline, behind
 * whatever is nearer the eye. A node the graph draws itself, a join's purpose node, gives off none of its own. */
const LIGHT = 2.6;  // the light a node gives off when it is lit, chosen by eye; full brightness on a screen is 1
function shine(material, color, lit) {
  if (!material.emissive) return;
  const own = material.isMeshPhysicalMaterial ? GLASS.emissiveIntensity : 0;
  if (lit > 0 && color) material.emissive.set(color);
  material.emissiveIntensity = own + (LIGHT - own) * lit;
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
  const home = thing ? [...S.elements.values()].find(entry => entry.element.id === thing.item.element_id)?.element : null;
  if (!home && !R.key) return;
  R.key = home ? key : null;
  R.color = home ? layerColor(thing.layer) : null;
  R.home = home ? home.id : null;
  R.nodes = new Set(home ? [...S.elements.values()].map(entry => entry.element)
    .filter(({address}) => address === home.address || home.address.startsWith(address + '.') || address.startsWith(home.address + '.'))
    .map(element => element.id) : []);
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
 * by the depth, and the glow is the body's own color given off as light, brighter with the depth, so the two are
 * never apart. */
function pulse3d(node, depth) {
  const object = node.__threeObj;
  if (!object || !object.material || object.userData.written) return;  // text glows by itself, VIEW-027
  if (!depth) {
    if (object.material.userData.pulsed) {
      colored(object.material, colorOf(node));
      shine(object.material, null, 0);
      object.material.userData.pulsed = false;
    }
    return;
  }
  const own = channels(ownColor(node)), light = channels(R.color);
  const body = colorFrom(own.map((part, at) => part + (light[at] * (1 - TIMES.opacity + TIMES.opacity * part) - part) * depth));
  if (!object.material.userData.own) { object.material = object.material.clone(); object.material.userData.own = true; }
  colored(object.material, body);
  shine(object.material, body, depth);
  object.material.userData.pulsed = true;
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
 * a half, a quarter and an eighth of the size, and added to the picture. It runs while anything on the map is lit
 * above full brightness: a property's reach, a signal on text, a node that needs attention. The glow is put behind
 * whatever is nearer the eye, VIEW-029: the bright part of the picture carries its distance from the eye through the
 * blur, and the glow is added to a point only where what is drawn there is no nearer than the light that reaches it.
 * It is built from the classes of the objects the chain already holds, since the graph library keeps its 3D classes
 * to itself; the depth of the scene is kept in a depth texture of the page's own copy of three.js. */
let BLOOM = null;
const SOFT = 12;  // over how many units nearer than a light its glow fades out
const SAMPLES = 4;
const samplesFor = name => /swiftshader|llvmpipe|software|basic render/i.test(name) ? 0 : SAMPLES;
function drawnBy() {
  const gl = G.renderer().getContext(), told = gl.getExtension('WEBGL_debug_renderer_info');
  return String(told ? gl.getParameter(told.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
}
function addBloom() {
  const composer = G.postProcessingComposer(), copy = composer?.copyPass;
  if (!copy || !composer.renderTarget1) return;
  const Target = composer.renderTarget1.constructor, Material = copy.material.constructor, Quad = copy.fsQuad.constructor;
  // The scene's depth is kept beside its picture, in both of the chain's buffers, since they take turns.
  // The scene is drawn into these buffers and not onto the screen, so the smoothing of edges the screen has does
  // not reach it: each buffer takes four samples a pixel of its own. Without them a link thinner than a pixel,
  // as every link is with the whole map in view, breaks into dots. Where the drawing is done by the processor and
  // not by a graphics card the samples are left out: measured 2026-09-29 they took the page from 10 frames a
  // second to 6 there, and changed nothing that could be seen.
  for (const target of [composer.renderTarget1, composer.renderTarget2]) {
    target.depthTexture = new THREE.DepthTexture(target.width, target.height);
    target.samples = samplesFor(drawnBy());
    target.dispose();
  }
  const vertex = 'varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }';
  const shader = (fragmentShader, uniforms) => new Material({uniforms, vertexShader: vertex, fragmentShader, depthTest: false, depthWrite: false});
  const eye = {sceneDepth: {value: null}, cameraNear: {value: 1}, cameraFar: {value: 1}};
  // How far a point of the picture is from the eye, from the depth the scene was drawn with.
  const away = `#include <packing>
    uniform sampler2D sceneDepth; uniform float cameraNear; uniform float cameraFar;
    float away(vec2 at) { return -perspectiveDepthToViewZ(texture2D(sceneDepth, at).x, cameraNear, cameraFar); }`;
  // The part over full brightness, and in its fourth channel its distance from the eye weighted by its brightness, so
  // the blur carries the distance with the light; divided by the far distance, so it fits the buffer.
  const over = shader(`${away} uniform sampler2D tDiffuse; varying vec2 vUv;
    void main() { vec3 c = texture2D(tDiffuse, vUv).rgb; float top = max(c.r, max(c.g, c.b));
      vec3 bright = top > 1.0 ? c * (1.0 - 1.0 / top) : vec3(0.0);
      gl_FragColor = vec4(bright, (bright.r + bright.g + bright.b) * away(vUv) / cameraFar); }`,
  {tDiffuse: {value: null}, ...eye});
  const blur = shader(`uniform sampler2D tDiffuse; uniform vec2 along; varying vec2 vUv;
    void main() { vec4 sum = texture2D(tDiffuse, vUv) * 0.227027;
      sum += (texture2D(tDiffuse, vUv + along * 1.0) + texture2D(tDiffuse, vUv - along * 1.0)) * 0.1945946;
      sum += (texture2D(tDiffuse, vUv + along * 2.0) + texture2D(tDiffuse, vUv - along * 2.0)) * 0.1216216;
      sum += (texture2D(tDiffuse, vUv + along * 3.0) + texture2D(tDiffuse, vUv - along * 3.0)) * 0.054054;
      sum += (texture2D(tDiffuse, vUv + along * 4.0) + texture2D(tDiffuse, vUv - along * 4.0)) * 0.016216;
      gl_FragColor = sum; }`, {tDiffuse: {value: null}, along: {value: [0, 0]}});
  const mix = shader(`${away} uniform sampler2D tDiffuse; uniform sampler2D near; uniform sampler2D mid; uniform sampler2D far;
    uniform float strength; uniform float soft; varying vec2 vUv;
    // The glow of one level at this point, kept where what is drawn here is no nearer the eye than the light that
    // reaches it, and faded out over a short distance nearer than that, so a nearer node covers the glow.
    vec3 behind(vec4 light, float here) {
      float weight = light.r + light.g + light.b;
      if (weight <= 0.0) return vec3(0.0);
      return light.rgb * clamp((here - light.a / weight * cameraFar) / soft + 1.0, 0.0, 1.0);
    }
    void main() { vec4 base = texture2D(tDiffuse, vUv); float here = away(vUv);
      vec3 glow = behind(texture2D(near, vUv), here) + behind(texture2D(mid, vUv), here) * 1.2
        + behind(texture2D(far, vUv), here) * 1.4;
      // The picture and the glow are added as light and then made ready for the screen, so whatever the pass does
      // not light is drawn as it is without the pass.
      gl_FragColor = linearToOutputTexel(vec4(base.rgb + strength * glow, base.a));
    }`, {tDiffuse: {value: null}, near: {value: null}, mid: {value: null}, far: {value: null}, strength: {value: 0.8},
    soft: {value: SOFT}, ...eye});
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
      const camera = G.camera();
      eye.sceneDepth.value = readBuffer.depthTexture;
      eye.cameraNear.value = camera.near;
      eye.cameraFar.value = camera.far;
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
  rows: new Map()};
const writing = new Map();  // what is being written, by node id, kept while the map is drawn again
const unbuilt = node => has(node, 'missing') || has(node, 'in-progress');
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
const SIGNALS = [['broken', '--broken'], ['fixing', '--broken'], ['flawed', '--flawed'], ['enhancement', '--enhancement'],
  ['exclude', '--exclude'], ['question', '--question'], ['message', '--question']];
function text3d() {
  const now = performance.now() / 1000, passed = Math.min(0.1, Math.max(0, now - (T.last || now)));
  T.last = now;
  if (!writing.size) { if (T.rows.size) rows3d(G.graphData()); return; }
  const ratio = G.renderer().getPixelRatio();
  G.renderer().getDrawingBufferSize(T.screen.value);
  T.cell.value.set(TEXT.size * 0.62 * ratio, TEXT.size * 1.25 * ratio);
  const away = G.camera().position.distanceTo(G.controls().target);
  if (!T.away) T.away = away;
  T.zoom.value = Math.min(TEXT.near, Math.max(TEXT.far, T.away / away));  // the characters follow the zoom a little
  let finished = false;
  const shown = new Set();
  for (const node of G.graphData().nodes) {
    const state = writing.get(node.id), object = node.__threeObj;
    if (!state) continue;
    shown.add(node.id);
    if (!object?.userData.written) continue;
    const working = has(node, 'in-progress'), climbed = () => TEXT.first + (TEXT.top - TEXT.first) * Math.pow(state.level, 1.4);
    if (!unbuilt(node) && state.ending === null) state.ending = 0;   // it is built: the ending starts from where it is
    if (state.ending === null) {
      // Work with no phases to report climbs by itself, slowly, to a point short of the fastest; each step filed
      // lifts it, VIEW-035.
      if (working) state.level = Math.min(TEXT.hold, state.level + TEXT.hold * passed / TEXT.climb);
      const done = S.progress?.get(node.id);
      if (done?.filed) state.level = Math.max(state.level, Math.min(1, done.planned ? done.filed / done.planned
        : 1 - 1 / (1 + FLASH.step * done.filed)));
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
    let reached = found ? (reduced() ? 1 : Math.max(0, Math.sin(now * 2 * Math.PI / paceOf(node)))) : 0, color = found ? css(found[1]) : null;
    const dot = W.pulses.get(node.id), gone = dot ? (W.clock - dot.start) / dot.length : 2;
    if (gone >= 0 && gone <= 1 && Math.sin(Math.PI * gone) > reached) { reached = Math.sin(Math.PI * gone); color = R.color; }
    Object.assign(state, {reached, signalColor: reached > 0 && color ? color.toLowerCase() : null});
    state.glow.value = reached;
    if (reached > 0 && color) state.signal.value.set(color);
  }
  for (const id of writing.keys()) if (!shown.has(id)) writing.delete(id);  // no longer on the map
  rows3d(G.graphData());
  if (finished) G.nodeThreeObject(G.nodeThreeObject());             // the parts built are drawn as every built part
}
function textOf(id) {
  const state = writing.get(id);
  if (!state) return '';
  return [...state.cells.image.data.slice(0, 64)].map(value => T.order[Math.min(61, Math.floor(value / 256 * 62))]).join('');
}
/* The condition of a node in 3D, MAP-046, VIEW-005 and VIEW-029: an open broken record flashes it red, steady red
 * with reduced motion; a broken part being fixed is steady red; an open exclude record pulses it between the exclude color
 * and its own, steady in the exclude color with reduced motion; an open question or message keeps its color. While it is
 * lit the node gives off light in the color of what it signals, which the bloom spreads past its outline: a flash is
 * lit on its beat, a pulse swells for half its period and rests for the other half. The sphere takes its own material
 * first, so no other node of its color changes. Called every frame for the nodes that carry a record, and for a node
 * still lit when its record has closed, to put its light back. */
function paint3d(node) {
  const object = node.__threeObj;
  if (!object || !object.material || object.userData.written) return;  // text shows its own condition, VIEW-027
  const light = lightOf(node), exclude = has(node, 'exclude');
  // An open question glows in the question's color, pulsating, so it is seen with the whole map zoomed out, VIEW-021.
  const asked = has(node, 'question') || has(node, 'message');  // a message waits for the user, VIEW-030
  if (R.nodes.has(node.id) || (!light && !exclude && !asked)) {  // a wave shows on it, or nothing to signal
    if (object.material.userData.lit) { shine(object.material, null, 0); object.material.userData.lit = false; }
    return;
  }
  if (!object.material.userData.own) {
    object.material = object.material.clone();
    object.material.userData.own = true;
    object.material.transparent = true;
  }
  const period = light ? paceOf(node) : 1;
  const beat = reduced() || (performance.now() / 1000) % period < period / 2;
  const shown = light ? (beat ? css(light[1]) : ownColor(node)) : exclude ? (beat ? css('--exclude') : ownColor(node))
    : colorOf(node);
  colored(object.material, dimmed(node) && !(light || exclude) ? dim(shown) : shown);
  const swell = reduced() ? 1 : Math.max(0, Math.sin(performance.now() / 1600 * 2 * Math.PI));
  const lit = light || exclude ? (beat ? 1 : 0) : swell;
  shine(object.material, light ? css(light[1]) : exclude ? css('--exclude') : css('--question'), lit);
  object.material.userData.lit = true;
}

/* An encounter takes its layer's color. */
function linkColor(link) {
  if (link.k === 'tree') return css('--tree');
  if ((link.work || []).includes('exclude')) return css('--exclude');
  return layerColor(link.layer);
}
let G = null;
const nodeSize = node => node.t === 'el' ? (node.role === 'DE' ? 9 : node.role === 'CQU' ? 7 : 4) : node.t === 'purpose' ? 0.9
  : node.t === 'item' ? 0.3 : 0.35;
/* The background is part of the scene as well as the graph's clear color. The render chain clears its buffer before
 * three.js draws into it, with the clear color last converted for the screen; three.js clears a scene's background
 * itself in the color space of whatever it draws into, so with the bloom on the background is the one drawn without
 * it, VIEW-022. */
function grounded() { G.scene().background = new THREE.Color(css('--ground')); }
/* The dots that travel a join are drawn solid, VIEW-005, as the approved prototype draws them. The graph library gives
 * a dot three times the opacity of the links, which a picture drawn on the screen holds at 1. The pictures this page
 * draws for the glass, and for the bloom while it is on, keep light over full brightness and hold no such limit: with
 * links at 0.8 a dot there was drawn as 2.4 times its color less 1.4 times what was behind it, so a dot passing through
 * a white node, or in front of it, turned it dark, Rich 2026-09-29. The library makes the dots' materials again
 * whenever the map or the theme changes, so each is held at 1 as the scene is drawn. */
function solid() {
  for (const link of G.graphData().links) for (const dot of link.__photonsObj?.children || [])
    if (dot.material.opacity > 1) dot.material.opacity = 1;
}
/* The 3D view is started by trying it, never by asking the browser whether it can: a browser can say it has WebGL
 * and still fail when it is used, as Moli's answers null for the scissor box and three.js stops on it. When anything in
 * the start fails, the 2D map takes the large area and the small one says why, so the map still works there. */
function start3D() {
  try {
    if (typeof ForceGraph3D !== 'function') throw new Error('the 3D library did not load');
    create3D();
  } catch (error) {
    G = null;
    fill($('#stage'), h('p', {class: 'empty', style: {padding: '24px'}},
      `The 3D view could not start in this browser (${error.message}). The 2D map works as usual.`));
    swap(true, false);
  }
}
function create3D() {
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
  grounded();
  G.scene().onBeforeRender = solid;
  addBehind();
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
/* A click on any vertex selects that object itself: an element or a join's purpose vertex. */
function clicked3d(node) {
  if (!node) return;
  if (large()) MODE.mode = 'readable';  // a click on a node goes to mode two, VIEW-041
  select(node.id, true);
}
/* A node takes the pointer anywhere it is drawn, not only at its center, Rich 2026-10-03: a part not built on the
 * whole round of characters it is written in, which `DRAWN` keeps at least five characters wide however far away it
 * is, a cell drawn whole when its middle is inside; every other node on the whole of its sphere. Each node's object
 * is picked by a ball of that size on the screen around its center. */
const PICK = {edge: 2};  // the pixels past a sphere that the picture smooths its edge over, measured 2026-10-03
const PICKED = {center: new THREE.Vector3(), at: new THREE.Vector3(), ball: new THREE.Sphere(), size: new THREE.Vector2()};
function picked(raycaster, hits) {
  const node = this.__data, camera = raycaster.camera;
  if (!node || !camera?.isPerspectiveCamera) return;
  const {center, at, ball, size} = PICKED;
  this.getWorldPosition(center);
  const depth = -at.copy(center).applyMatrix4(camera.matrixWorldInverse).z;
  if (depth <= 0) return;
  const unit = 2 * depth / (camera.projectionMatrix.elements[5] * G.renderer().getSize(size).y);  // world units a pixel spans there
  const cell = T.cell.value.clone().multiplyScalar(T.zoom.value / G.renderer().getPixelRatio());  // a character, in pixels
  const radius = Math.cbrt(nodeSize(node)) * 3;
  const reach = this.userData.written ? Math.max(radius, 2.5 * cell.x * unit) + cell.y / 2 * unit
    : radius + PICK.edge * unit;
  if (!raycaster.ray.intersectSphere(ball.set(center, reach), at)) return;
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
/* The labels of the 3D map, VIEW-038, are drawn inside the scene, each its element's whole name, wrapped at word
 * breaks, painted on a canvas and shown as a sprite that faces the camera and keeps one size on the screen. Each
 * stands at its node's depth just above the node's sphere, and is drawn with the depth test as the nodes are, so the
 * depth buffer orders labels and nodes together: a node nearer the eye hides the part of a label behind it, a label
 * behind a glass node is seen through the glass as the material lets it through, VIEW-025, since what is behind the
 * glass is drawn with the labels in it, and a nearer label is drawn over a farther one. Nothing ranks over depth, the
 * selected node, its neighbors and a lit or blinking node included. A label that falls on a nearer node's sphere or
 * on a nearer label keeps its own color: what is in front hides it by depth or shows it through the glass, Rich
 * 2026-10-02. Every element keeps its label, VIEW-005; the text is in the theme's
 * text color on a box of the background, and none is faded toward the background, VIEW-023. A label is painted again
 * only when what it shows changes. */
const LABEL = {size: 11, chosen: 13, wide: 9, line: 1.15, padX: 4, padY: 1, gap: 8, written: 18, box: 0.72};
const tags = new Map();   // by node id: the label's sprite, its canvas, what it shows and where it is on the screen
const LABELS = {group: null, on: true, pen: null, measured: new Map()};
const UP = new THREE.Vector3(), AT = new THREE.Vector3();
const fontOf = look => `${look.weight} ${look.size}px ${look.family}`;
/* The name in lines no wider than the label's width, broken only between words, as the page wraps text; a word longer
 * than the width keeps its own line whole. */
function wrapped(text, look) {
  const key = fontOf(look) + '\n' + text;
  if (LABELS.measured.has(key)) return LABELS.measured.get(key);
  LABELS.pen = LABELS.pen || document.createElement('canvas').getContext('2d');
  LABELS.pen.font = fontOf(look);
  const most = LABEL.wide * look.size, lines = [];
  for (const word of text.split(/\s+/).filter(Boolean)) {
    const joined = lines.length ? lines.at(-1) + ' ' + word : null;
    if (joined !== null && LABELS.pen.measureText(joined).width <= most) lines[lines.length - 1] = joined;
    else lines.push(word);
  }
  if (!lines.length) lines.push('');
  const widest = Math.max(...lines.map(line => LABELS.pen.measureText(line).width));
  const made = {lines, width: Math.ceil(widest) + 2 * LABEL.padX, height: Math.ceil(lines.length * look.size * LABEL.line) + 2 * LABEL.padY};
  LABELS.measured.set(key, made);
  return made;
}
function painted(tag, look, ratio) {
  const shape = wrapped(tag.text, look), canvas = tag.texture.image, pen = canvas.getContext('2d');
  canvas.width = Math.ceil(shape.width * ratio); canvas.height = Math.ceil(shape.height * ratio);
  pen.scale(ratio, ratio);
  pen.globalAlpha = LABEL.box;
  pen.fillStyle = look.ground;
  pen.beginPath(); pen.roundRect(0, 0, shape.width, shape.height, 4); pen.fill();
  pen.globalAlpha = 1;
  pen.font = fontOf(look); pen.textAlign = 'center'; pen.textBaseline = 'middle';
  const step = look.size * LABEL.line;
  for (const blur of [...look.glow, 0]) {   // the text's glow of the background under it, then the text itself
    pen.shadowColor = blur ? look.ground : 'transparent'; pen.shadowBlur = blur * ratio;
    pen.fillStyle = look.color;
    shape.lines.forEach((line, index) => pen.fillText(line, shape.width / 2, LABEL.padY + step * (index + 0.5)));
  }
  tag.texture.dispose();                    // the canvas may have changed size
  tag.texture.needsUpdate = true;
  Object.assign(tag, {lines: shape.lines, width: shape.width, height: shape.height, color: look.color});
}
function labelFor(node) {
  let tag = tags.get(node.id);
  if (tag) return tag;
  if (!LABELS.group) {
    LABELS.group = new THREE.Group();
    G.scene().add(LABELS.group);
    // Measured and painted again once the page's face is there.
    Promise.all([500, 600].map(weight => document.fonts.load(`${weight} ${LABEL.size}px ${css('--sans')}`))).then(() => {
      LABELS.measured.clear();
      for (const each of tags.values()) each.key = '';
    }, () => {});
  }
  const texture = new THREE.CanvasTexture(document.createElement('canvas'));
  Object.assign(texture, {colorSpace: THREE.SRGBColorSpace, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter,
    generateMipmaps: false});
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({map: texture, sizeAttenuation: false, depthTest: true,
    depthWrite: true, transparent: true, alphaTest: 0.02, toneMapped: false}));
  sprite.center.set(0.5, 0);                // it stands on the point above the node
  sprite.raycast = () => {};                // a label is never picked in place of the node
  LABELS.group.add(sprite);
  tag = {id: node.id, text: node.name || '', sprite, texture, key: '', classes: [], lines: [], width: 0, height: 0,
    under: false, z: 0, hidden: true, rect: null, color: ''};
  tags.set(node.id, tag);
  return tag;
}
function dropLabel(id) {
  const tag = tags.get(id);
  if (!tag) return;
  LABELS.group?.remove(tag.sprite);
  tag.texture.dispose(); tag.sprite.material.dispose();
  tags.delete(id);
}
/* What a label shows from its classes, as the page's own styles would give it. */
function lookOf(classes, palette) {
  const is = name => classes.includes(name);
  const chosen = is('sel'), reach = is('reach');
  const color = is('work-exclude') ? palette.exclude : is('work-broken') || is('work-fixing') ? palette.broken
    : reach ? palette.text : is('dim') ? palette.muted : chosen ? palette.signal : palette.text;
  return {size: chosen ? LABEL.chosen : LABEL.size, weight: chosen || reach ? 600 : 500, family: palette.sans, color,
    ground: palette.ground, glow: reach ? [10, 6, 3] : [6, 2]};
}
/* Each frame: every label is put above its node at the node's depth and sized for the screen, and the labels that
 * fall on a nearer sphere or a nearer label are marked under. */
function layered() {
  const camera = G.camera(), area = $('#stage').getBoundingClientRect(), height = area.height || 1;
  const spread = camera.projectionMatrix.elements[5], ratio = G.renderer().getPixelRatio();
  const perPixel = depth => 2 * depth / (spread * height);   // world units a pixel spans at a depth
  const depthOf = node => -AT.set(node.x, node.y, node.z).applyMatrix4(camera.matrixWorldInverse).z;
  UP.set(0, 1, 0).applyQuaternion(camera.quaternion);
  const palette = {text: css('--text'), muted: css('--muted'), signal: css('--signal'), broken: css('--broken'),
    exclude: css('--exclude'), ground: css('--ground'), sans: css('--sans')};  // read once a frame, not once a label
  if (LABELS.group) LABELS.group.visible = LABELS.on;
  const spheres = [], shown = [];
  for (const node of G.graphData().nodes) {
    if (node.x === undefined) continue;
    const point = G.graph2ScreenCoords(node.x, node.y, node.z), depth = depthOf(node);
    spheres.push({id: node.id, x: point.x, y: point.y, far: depth, r: Math.cbrt(nodeSize(node)) * 3 / perPixel(depth)});
  }
  for (const node of G.graphData().nodes) {
    if (node.t !== 'el') continue;
    const tag = labelFor(node);
    tag.text = node.name || '';
    tag.hidden = node.x === undefined;
    tag.sprite.visible = !tag.hidden;
    if (tag.hidden) continue;
    tag.classes = [node.id === S.selected ? 'sel' : S.neighbors.has(node.id) ? 'near' : S.selected ? 'dim' : '',
      ...(node.work || []).map(condition => `work-${condition}`), R.nodes.has(node.id) ? 'reach' : '',
      node.__threeObj?.userData.written ? 'text' : ''].filter(Boolean);
    const look = lookOf(tag.classes, palette), shape = wrapped(tag.text, look);
    const depth = depthOf(node), unit = perPixel(Math.max(depth, 1e-3)), radius = Math.cbrt(nodeSize(node)) * 3;
    const lift = Math.max(radius, tag.classes.includes('text') ? LABEL.written * unit : 0) + LABEL.gap * unit;
    tag.sprite.position.set(node.x, node.y, node.z).addScaledVector(UP, lift);
    tag.sprite.scale.set(shape.width * 2 / (spread * height), shape.height * 2 / (spread * height), 1);
    const anchor = G.graph2ScreenCoords(tag.sprite.position.x, tag.sprite.position.y, tag.sprite.position.z);
    tag.rect = {left: anchor.x - shape.width / 2, right: anchor.x + shape.width / 2, top: anchor.y - shape.height, bottom: anchor.y};
    shown.push({tag, far: depth, look});
  }
  shown.sort((one, two) => one.far - two.far);
  shown.forEach((label, index) => {
    const box = label.tag.rect;
    const behind = spheres.some(sphere => sphere.id !== label.tag.id && sphere.far < label.far &&
      Math.hypot(Math.max(box.left, Math.min(sphere.x, box.right)) - sphere.x,
                 Math.max(box.top, Math.min(sphere.y, box.bottom)) - sphere.y) < sphere.r);
    const covered = shown.slice(0, index).some(({tag: other}) => !(box.right <= other.rect.left ||
      other.rect.right <= box.left || box.bottom <= other.rect.top || other.rect.bottom <= box.top));
    const tag = label.tag;
    tag.under = behind || covered;
    tag.z = shown.length - index;
    if (tag.under) tag.classes.push('under');
    const look = lookOf(tag.classes, palette), key = [tag.text, fontOf(look), look.color, look.ground, look.glow, ratio].join('|');
    if (key !== tag.key) { painted(tag, look, ratio); tag.key = key; }
  });
}
function labels() {
  if (G) {
    // A glass node is colored by the page, since the graph colors only the nodes it draws itself.
    for (const node of G.graphData().nodes) if (isGlass(node) && node.__threeObj?.material && !node.__threeObj.material.userData.pulsed)
      colored(node.__threeObj.material, dimmed(node) ? dim(colorOf(node)) : colorOf(node));
    DRIFT.value = reduced() ? 0 : performance.now() / 1000;  // the distortion of the glass drifts, VIEW-025
    wave3d(G.graphData());
    roam3d(G.graphData());
    text3d();
    let signaled = false;
    for (const node of G.graphData().nodes) {
      if (node.__threeObj && node.__threeObj.raycast !== picked) node.__threeObj.raycast = picked;
      if ((node.work && node.work.length) || node.__threeObj?.material?.userData.lit) paint3d(node);
      signaled = signaled || SIGNALS.some(([condition]) => has(node, condition));
    }
    layered();
    // The bloom runs while a reach is lit and while any part has a record that gives off light, VIEW-029, for as long
    // as the record is open and not only at the moments of its flash: the glass's highlights are over full brightness
    // too, and a pass switched with each flash would make them blink with it.
    if (BLOOM) BLOOM.enabled = Boolean(R.key) || signaled;
    placeTip();
  }
  requestAnimationFrame(labels);
}
/* The 3D view draws the map, or the memory network of a node while one is open, VIEW-031. `previous` holds where
 * each node stood, the positions of what is drawn now unless given. */
function draw3D(previous = null) {
  if (!G) return;
  if (MEM.key && S.loading) return;  // a memory network is drawn once the map and its items are read again
  previous = previous || new Map(G.graphData().nodes.map(node => [node.id, node]));
  const data = MEM.key ? memoryData() : graphData();
  for (const node of data.nodes) {  // keep drawn positions, so the picture does not jump as pages arrive
    const known = previous.get(node.id);
    if (known) Object.assign(node, {x: known.x, y: known.y, z: known.z, vx: known.vx, vy: known.vy, vz: known.vz,
      fx: known.fx, fy: known.fy, fz: known.fz});
  }
  const named = new Set(data.nodes.filter(node => node.t === 'el').map(node => node.id));
  for (const id of [...tags.keys()]) if (!named.has(id)) dropLabel(id);
  if (hovered) hovered = data.nodes.find(node => node.id === hovered.id) || null;
  $('#tip3d').hidden = !hovered;
  if (inPlace(data)) return;
  // A memory network is laid out before it is shown, so it opens settled and whole in view; the map keeps its own
  // layout running from where each node stands.
  G.warmupTicks(MEM.key ? 120 : 0);
  G.graphData(data);
  V3.layouts++;
}
/* New data starts the 3D layout again at full strength, which shakes the map, so a change that adds or removes no node
 * and no link is copied onto what is drawn, which is drawn again where it stands, VIEW-018. */
const PLACE = new Set(['x', 'y', 'z', 'vx', 'vy', 'vz', 'fx', 'fy', 'fz', 'index', '__threeObj', 'source', 'target']);
const end = value => value && typeof value === 'object' ? value.id : value;
const linkKey = link => `${end(link.source)}>${end(link.target)}>${link.k}`;
function inPlace(data) {
  const shown = G.graphData();
  if (shown.nodes.length !== data.nodes.length || shown.links.length !== data.links.length) return false;
  const nodes = new Map(shown.nodes.map(node => [node.id, node]));
  if (data.nodes.some(node => !nodes.has(node.id))) return false;
  const links = new Map();
  for (const link of shown.links) (links.get(linkKey(link)) || links.set(linkKey(link), []).get(linkKey(link))).push(link);
  const pairs = [];
  for (const link of data.links) {
    const same = links.get(linkKey(link));
    if (!same?.length) return false;
    pairs.push([same.shift(), link]);
  }
  const copy = (into, from) => { for (const [key, value] of Object.entries(from)) if (!PLACE.has(key)) into[key] = value; };
  for (const node of data.nodes) copy(nodes.get(node.id), node);
  for (const [into, from] of pairs) copy(into, from);
  G.refresh();
  return true;
}
/* A theme recolors both views in place, VIEW-023: the 3D view rereads its colors, the 2D map is drawn again. The
 * choice is the viewer's own, kept in this browser. */
function setTheme(name) {
  document.documentElement.dataset.theme = name;
  try { localStorage.setItem('metaform.theme', name); } catch (error) { /* storage can be blocked; the theme still shows */ }
  if (G) G.backgroundColor(css('--ground')).linkOpacity(Number(css('--link-opacity'))).nodeColor(G.nodeColor())
    .linkColor(G.linkColor()).linkDirectionalParticleColor(G.linkDirectionalParticleColor());
  if (G) grounded();
  mermaidReady = false;
  build2D();
}
$('#theme').value = document.documentElement.dataset.theme;
if ($('#theme').selectedIndex < 0) $('#theme').value = document.documentElement.dataset.theme = 'space';  // a kept name that is no longer a theme
$('#theme').onchange = () => setTheme($('#theme').value);
const MODE = {mode: 'whole', key: 5};  // the 2D camera's mode in the large area, VIEW-041; see modeTarget
/* The two views change places, VIEW-028: the 2D map takes the large area and the 3D map the small one, and back.
 * Each is then drawn for the area it has. The choice is the viewer's own, kept in this browser. */
async function swap(on, remember = true) {
  $('.app').classList.toggle('swapped', on);
  if (on) MODE.mode = 'whole';  // the 2D map comes to the large area in mode one, VIEW-041
  (on ? $('main') : $('#small')).append($('#map2d'));
  (on ? $('#small') : $('main')).append($('#big3d'));
  $('#swapBtn').title = on ? 'Put the 3D map back in the large area' : 'Put this map in the large area, and the 3D map here';
  $('#swap3dBtn').title = on ? 'Put this map back in the large area' : 'Put this map in the small area, and the 2D map here';
  if (remember) try { localStorage.setItem('metaform.swapped', on ? '1' : ''); } catch (error) { /* storage can be blocked; the swap still shows */ }
  resize();
  if (G) setTimeout(() => fit3d(600, on ? 24 : 60), 50);  // the whole 3D map in its new area
  if (S.loading || !S.elements.size) return;
  await build2D(false);  // drawn for its new area, opening as it does on loading
  if (S.selected) select(S.selected, false, true);
}
$('#swapBtn').onclick = $('#swap3dBtn').onclick = () => swap(!$('.app').classList.contains('swapped'));
/* The 3D map's own Fit goes between two views: the whole map, and close on the selected node. It moves the 3D map
 * only, as the 2D map's Fit moves the 2D map only. */
const V3 = {whole: 0, fits: 0, layouts: 0};  // how far the camera stands when the whole map is in view, and the fits ended
const away3d = () => G.camera().position.distanceTo(G.controls().target);
function fit3d(time = 700, room = 60) {
  if (!G) return;
  const took = reduced() ? 0 : time;
  G.zoomToFit(took, room);
  setTimeout(() => { if (G) { V3.whole = away3d(); V3.fits++; } }, took + 60);
}
function fly3d(id) {
  const node = G ? G.graphData().nodes.find(item => item.id === id) : null;
  if (!node || node.x === undefined) return false;
  const ratio = 1 + 90 / Math.hypot(node.x || 1, node.y || 1, node.z || 1);
  G.cameraPosition({x: node.x * ratio, y: node.y * ratio, z: node.z * ratio}, node, reduced() ? 0 : 900);
  return true;
}
// Where the camera stands decides it, and not which button was clicked last, since the person also moves the camera
// by hand: standing back with the whole map in view it goes in on the selected node, and from anywhere nearer it
// goes out to the whole map.
$('#fit3dBtn').onclick = () => {
  if (!G) return;
  const back = V3.whole && away3d() >= V3.whole * 0.8;
  if (back && S.selected && fly3d(S.selected)) return;
  fit3d();
};
try { if (localStorage.getItem('metaform.swapped')) swap(true); } catch (error) { /* storage can be blocked */ }
function resize() { if (G) { const box = $('#stage').getBoundingClientRect(); G.width(box.width).height(box.height); } }
addEventListener('resize', resize);

function renderLegend() {
  const inView = new Set([...S.elements.values()].map(entry => entry.element.layer).concat(S.joins.map(join => join.layer)));
  const rows = [['--intake', 'purpose · receiver to join', ''],
    ['--tree', 'namespace', ''], ...[...inView].map(name => [colorVar(name), name, ''])];
  const legend = $('#legend');
  fill(legend, ...rows.map(([color, text, kind]) =>
    h('span', {style: {'--c': `var(${color})`}}, h('i', {class: kind}), text)));
  const open = new Set([...S.elements.values()].flatMap(entry => entry.element.open_work || [])
    .concat(S.joins.flatMap(join => join.open_work || [])));
  for (const condition of CONDITIONS) if (open.has(condition))
    legend.append(h('span', {style: {'--c': condition === 'missing' || condition === 'in-progress' ? 'var(--text)'
      : `var(--${condition === 'fixing' ? 'broken' : condition === 'message' ? 'question' : condition})`}},
      h('i', {class: {missing: 'dot bloom', 'in-progress': 'dot bloom pulse', fixing: 'dot bloom pulse', question: 'dot bloom pulse', message: 'dot bloom pulse'}[condition] || 'dot'}),
      `work: ${condition}`));
  const shown = G ? G.graphData().nodes.length : 0;
  $('#count').textContent = noMetaform() ? 'no metaform yet'
    : `${S.elements.size} elements · ${S.joins.length} joins · ${shown} nodes shown` + (S.loading ? ' · loading' : '')
    + (following() ? ' · intake being recorded' : '');
}

/* ---------- 2D: the whole map, short names, no text on the edges; the camera moves node to node ---------- */
const M = {svg: null, nodes: new Map(), edges: [], cam: null, to: null, fit: null, frame: 0, generation: 0};
const MAP2D = 5000;  // the most elements Mermaid lays out; above it the 2D map is not drawn, BUILD-QUESTIONS Q52
const plain2d = text => String(text || '').replace(/["[\]{}()<>|#;`]/g, '').slice(0, 30);
let mermaidReady = false;
async function build2D(keep = true) {
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
  // One edge from a join's receiver to each element it holds, Rich's shape, 2026-10-04.
  const drawn = S.joins.filter(join => keys.has(join.receiver))
    .flatMap(join => join.providers.filter(id => keys.has(id)).map(provider => ({join, provider})));
  const vertical = S.elements.size > 5;
  const lines = [vertical ? 'flowchart TB' : 'flowchart LR'];
  for (const [id, {element}] of S.elements) lines.push(`${keys.get(id)}["${plain2d(labelOf(element))}"]`);
  drawn.forEach(({join, provider}, index) => lines.push(`${keys.get(join.receiver)} e${index}@--> ${keys.get(provider)}`));
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
  // The whole map drawn again keeps its camera and eases from there, VIEW-041, with the zoom the person has, VIEW-008.
  const was = keep && M.base && M.svg === M.base.svg && M.cam ? {cam: {...M.cam}, zoom: M.zoom} : null;
  const inside = IN.length > 0 || Boolean(MEM.key);
  const svg = mountSvg(result, host, inside);
  const nodes = new Map();
  for (const [id, key] of keys) {
    const group = svg.querySelector(`[id*="-flowchart-${key}-"]`);
    if (group) placeIn(nodes, id, group, S.elements.get(id).element.address, S.elements.get(id).element.open_work);
  }
  const edges = drawn.map(({join, provider}, index) => ({join, provider, path: svg.querySelector(`[data-id="e${index}"]`)
    || svg.querySelectorAll('.edgePaths path')[index]}));
  for (const edge of edges) for (const condition of edge.join.open_work || []) edge.path?.classList.add(`work-${condition}`);
  // The base map is kept while a node is entered and shown again as it was, VIEW-016.
  M.base = {svg, nodes, edges, fit: fitOf(svg), vertical, cam: null};
  figures2d(S.tickets || []);
  if (MEM.key) { svg.remove(); svg.style.visibility = ''; await drawMemory2d(); return; }
  if (inside) { svg.remove(); svg.style.visibility = ''; await drawInside(); return; }
  showBase();
  if (was) { setCam(was.cam, false); M.zoom = was.zoom; }
  if (S.selected) focus2D(S.selected); else applyMode();
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
  const paced = S.progress?.get(id);
  if (paced) group.style.setProperty('--pace', `${paceOf({id})}s`);
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
  stopCam();  // a camera still easing on the level left must not move this one
  Object.assign(M, {svg: base.svg, nodes: base.nodes, edges: base.edges, fit: base.fit, vertical: base.vertical, drawn: null});
  fill($('#viewport'), base.svg);
  const node = left ? base.nodes.get(left) : null;
  if (node && !reduced()) {  // back from inside the node: the map returns zoomed on it and fades in, VIEW-016
    const kept = base.cam || frame(readable(base.fit, node));  // the zoom held before going inside
    setCam(frame(into(node)), false);
    M.zoom = {w: kept.w, h: kept.h};
    arrive(base.svg);
    moveCam(moded() ? modeTarget() : {x: node.x - kept.w / 2, y: node.y - kept.h / 2, w: kept.w, h: kept.h});
    return;
  }
  base.svg.style.transition = ''; base.svg.style.opacity = '';  // a map faded on the way in shows whole again
  const entry = [...S.elements.values()].find(item => item.element.role === 'DE')?.element.id;
  setCam(base.cam || (moded() ? frame(modeTarget()) : frame(readable(base.fit, base.nodes.get(S.selected)
    || base.nodes.get(entry) || base.nodes.values().next().value))));
}

/* ---------- inside a node: the 2D map is replaced by the node's own graph, VIEW-016 ----------
 * Every node can be entered. Inside are the node, what it holds, one group for each layer turned on with what that
 * layer attaches to the node, and the nodes those items link to, which can be entered in turn. */
const IN = [];  // the levels entered from the base map: {key, label, more, things}
const GROUP = 20;
let insideGen = 0;
const kindOf = key => key.startsWith('p:') ? 'join' : 'element';
const bareId = key => key.replace(/^p:/, '');
const keyOf = node => !node ? null : node.kind === 'join' ? 'p:' + node.id : node.kind === 'element' ? node.id : null;
const label2d = text => plain2d(String(text ?? '').replace(/\s+/g, ' ')) || '·';
const samePath = (a, b) => a.length === b.length && a.every((level, index) => level.key === b[index].key);
/* An element is labeled with its name, the project's name for it, or else its short namespace name, its address read
 * through name_length, MAP-012, Rich 2026-10-04: "the fall back for name not being provided is the short namespace
 * name"; "the name on the join was the name for the element". A join has no name in Rich's shape, so it has no label;
 * its purpose shows when it is hovered or selected. */
const labelOf = element => element.name || element.short_name || element.address;
const joinLabel = () => '';
function nameOf(key, fallback = key) {
  if (key.startsWith('p:')) { const found = joinOf(key); return found ? joinLabel(found) : fallback; }
  const found = S.elements.get(key)?.element;
  return found ? labelOf(found) : fallback;
}
async function drawInside(arriving = false) {
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
      edges.push(`${add(join.receiver, nameOf(join.receiver), 'stub')} --> ${center}`);
      for (const provider of join.providers) edges.push(`${center} --> ${add(provider, nameOf(provider), 'stub')}`);
    }
  } else {
    for (const join of S.joins.filter(item => item.receiver === key))
      edges.push(`${center} --> ${add('p:' + join.id, joinLabel(join), 'purpose')}`);
  }
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
  for (const thing of linked) {
    const to = keyOf(thing.item.link);
    if (to) edges.push(`${ids.get(thing.key)} --> ${add(to, nameOf(to, thing.item.link.id), 'stub')}`);
  }
  // The memories kept at the node, in memory's group; each relation of theirs runs to the memory it names, and a memory
  // kept elsewhere leads on to the nodes it is kept at, LAYER-013.
  const kept = [...new Set(memoriesAt(key))];
  if (kept.length) {
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
        for (const at of there(name)) if (at !== key) edges.push(`${ids.get(memoryKey(name))} --> ${add(at, nameOf(at), 'stub')}`);
      }
      edges.push(`${ids.get(memoryKey(relation.from))} -->|"${label2d(relation.relationType)}"| ${ids.get(memoryKey(relation.to))}`);
    }
  }
  const coming = incoming.filter(item => !ids.has('i:' + item.id));
  if (coming.length) {
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
  lines.push(...edges, ...['center', 'item', 'stub', 'more', 'purpose'].map(kind => `classDef ${kind} font-size:11px`));
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
  stopCam();  // a camera still easing on the level left must not move this one
  Object.assign(M, {svg, nodes, edges: [], fit: fitOf(svg), vertical, drawn: level});
  setCam(frame(readable(M.fit, nodes.get(level.key))));
  renderCrumbs();
  if (S.selected && nodes.has(S.selected)) focus2D(S.selected);
}
function renderCrumbs() {
  const bar = $('#crumbs');
  bar.hidden = !IN.length && !MEM.key;
  if (MEM.key) {  // a memory network, VIEW-031: each part goes back to the map, at that level of it
    const back = (depth, text) => h('a', {href: '#', onclick: event => { event.preventDefault(); leaveMemories(depth); }}, text);
    return fill(bar, back(0, 'map'), MEM.levels.map((level, index) => [h('span', {class: 'sep'}, ' › '), back(index + 1, level.label)]),
      h('span', {class: 'sep'}, ' › '), h('b', {}, `memories of ${nameOf(MEM.key)}`));
  }
  const to = (depth, text) => h('a', {href: '#', onclick: event => { event.preventDefault(); goTo(depth); }}, text);
  fill(bar, ...(IN.length ? [to(0, 'map'), ...IN.flatMap((level, index) => [h('span', {class: 'sep'}, ' › '),
    index === IN.length - 1 ? h('b', {}, level.label) : to(index + 1, level.label)])] : []));
}
/* Enter a node, or the node an item links to; a group's "more" node shows the next ones. */
async function enter(key) {
  const level = IN.at(-1), thing = level?.things?.get(key);
  if (key.startsWith('m:')) { level.more[key.slice(2)] = (level.more[key.slice(2)] || GROUP) + GROUP; return drawInside(); }
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
  if (thing.kind === 'memory') return renderEntity(thing.name);
  if (thing.kind === 'item' || thing.kind === 'property') {
    const link = keyOf(thing.item.link);
    fill(pane,
      h('div', {class: 'eyebrow'}, thing.layerKind === 'memory' ? 'Memory' : thing.kind === 'property' ? 'Property' : 'Item'),
      h('div', {class: 'pills'}, thing.layer ? layerPill(thing.layer) : null, thing.item.state ? h('span', {class: 'pill'}, thing.item.state) : null),
      h('div', {class: 'itemtext'}, itemView(thing.value)),
      link ? h('p', {class: 'meta'}, 'Links to ', h('a', {class: 'link', href: '#', onclick: event => { event.preventDefault(); enter(link); }},
        nameOf(link, thing.item.link.id)), '; Enter goes there.') : null,
      refsOf(thing.item.refs));
    return;
  }
  fill(pane, h('div', {class: 'eyebrow'}, thing.kind === 'more' ? 'More' : 'Node'), h('h2', {}, thing.label),
    h('p', {class: 'meta'}, thing.kind === 'more' ? 'Enter shows the next ones.' : 'Enter goes inside it.'));
}

/* ---------- the memory graph, LAYER-013: a graph of its own, tied to the map's nodes by joins of type memory ----------
 * Read whole from the memory module's `graph`, each join saying whether its memory shows at its node in the layers in
 * view, VIEW-031. A memory is drawn as `e:<name>`, at each node it shows
 * at; a join the map no longer holds is orphaned and listed in the orphaned menu. */
const emptyMemory = () => ({entities: new Map(), relations: [], joins: [], at: new Map(), orphaned: 0});
const memoryLayer = () => S.layers.find(layer => layer.kind === 'memory')?.name || 'memory';
const memoryKey = name => 'e:' + name;
const memoryName = key => key.slice(2);
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
async function memoryOf() {
  let whole;
  try { whole = await read('memory-graph', viewLayers()); } catch (error) { return emptyMemory(); }
  const at = new Map(), joins = whole.joins.map(join => ({...join, key: join.orphaned ? null : nodeAt(join)}));
  for (const join of joins) {
    if (!join.shows || !join.key) continue;
    if (!at.has(join.key)) at.set(join.key, []);
    if (!at.get(join.key).includes(join.entity)) at.get(join.key).push(join.entity);
  }
  return {entities: new Map(whole.entities.map(entity => [entity.name, entity])), relations: whole.relations, joins, at,
    orphaned: joins.filter(join => join.orphaned).length};
}
/* The memories shown at a node, and a memory as the panel and the inside of a node take it. */
const memoriesAt = key => S.memory.at.get(key) || [];
function memoryThing(key) {
  if (!key?.startsWith('e:') || !S.memory.entities.has(memoryName(key))) return null;
  return {kind: 'memory', key, name: memoryName(key), value: memoryName(key), layer: memoryLayer(), layerKind: 'memory'};
}
/* The memory network of a node, VIEW-031: the memories kept at it, the memories their relations name, and every
 * relation between those; a relation one of them holds to a memory outside them is not drawn. */
function networkOf(key) {
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
function memoryData() {
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
  const node = G.graphData().nodes.find(item => item.id === key);
  if (node && node.x !== undefined) {
    const eye = G.camera().position, away = Math.hypot(eye.x - node.x, eye.y - node.y, eye.z - node.z) || 1;
    const share = Math.min(1, Math.cbrt(nodeSize(node)) * 3 * 2.5 / away);  // near enough that the node fills the view
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
  for (let frames = 0; frames < 2; frames++) await new Promise(resolve => requestAnimationFrame(resolve));
  G.zoomToFit(0, 60);
  V3.whole = away3d();
}
/* Open the memory network of a node in both views. From the map, what the map was is kept to go back to: the levels
 * entered in 2D and where each node of the 3D map stood. From a memory network, the network of another of its nodes
 * takes its place. */
async function memories(key) {
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
  if (M.fit && M.drawn === MEM) { stopCam(); setCam(frame(M.fit)); }  // it opens with the whole memory network in view
  await whole3d();
  if (generation !== MEM.generation) return;
  renderCrumbs();
  if (!reduced()) { if (M.drawn === MEM) fade(M.svg, 1); shown3d(1); }
}
/* Going back returns to the map: to the level of the 2D map the network was opened from, or to `depth` of it, with
 * each node of the 3D map where it stood, and the node the network belongs to selected. */
async function leaveMemories(depth = null) {
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
function dropMemories() {
  MEM.generation++;
  Object.assign(MEM, {key: null, network: null, drawn: false, levels: [], positions: null});
  Object.assign($('#stage').style, {transition: '', opacity: ''});
}
/* The memory network in 2D: the node, each memory by its name, a dotted line from the node to each memory kept at it,
 * and each relation a line in memory's color from the memory that holds it to the memory it names, with its relation
 * type on it. `hidden` puts it in place unseen, to fade in with the 3D view. */
async function drawMemory2d(hidden = false) {
  const network = MEM.network = networkOf(MEM.key);
  const generation = ++insideGen;  // a render still running for a level left is dropped
  const vertical = M.base ? M.base.vertical : true;
  const ids = new Map(network.entities.map((key, index) => [key, `v${index}`]));
  const label = key => key.startsWith('e:') ? memoryName(key) : nameOf(key);
  const lines = [vertical ? 'flowchart TB' : 'flowchart LR',
    ...network.entities.map(key => `${ids.get(key)}["${label2d(label(key))}"]:::${key === network.key ? 'center' : 'entity'}`),
    ...network.own.map(name => `${ids.get(network.key)} -.- ${ids.get(memoryKey(name))}`),
    ...network.relations.map((relation, index) =>
      `${ids.get(relation.from)} e${index}@-->|"${label2d(relation.type)}"| ${ids.get(relation.to)}`),
    ...['center', 'entity'].map(kind => `classDef ${kind} font-size:11px`)];
  let result;
  try { result = await window.mermaid.render(`memory${generation}`, lines.join('\n'), $('#draw')); }
  catch (error) { fill($('#viewport'), h('p', {class: 'empty', style: {padding: '16px'}}, 'These memories could not be drawn.')); return; }
  if (generation !== insideGen || !MEM.key) return;
  const svg = mountSvg(result, $('#viewport'), false);
  if (hidden && !reduced()) Object.assign(svg.style, {transition: '', opacity: '0'});
  const nodes = new Map();
  for (const [key, id] of ids) {
    const group = svg.querySelector(`[id*="-flowchart-${id}-"]`);
    if (!group) continue;
    placeIn(nodes, key, group, S.elements.get(key)?.element.address || label(key), entityNode(key).work);
    group.classList.add(key === network.key ? 'in-center' : 'in-entity');
  }
  network.relations.forEach((relation, index) => svg.querySelector(`path[data-id="e${index}"]`)?.classList.add('relation'));
  stopCam();  // a camera still easing on the view left must not move this one
  Object.assign(M, {svg, nodes, edges: [], fit: fitOf(svg), vertical, drawn: MEM});
  setCam(frame(M.fit));
  $('#map2d').classList.add('focused');
  for (const [key, value] of nodes) {
    value.g.classList.toggle('sel', key === S.selected);
    value.g.classList.toggle('near', key !== S.selected && S.neighbors.has(key));
  }
  renderCrumbs();
}
/* In a memory network the panel shows the node with the memories kept at it, each with its observations and its
 * relations, or the memory selected, as the memory module reads them, VIEW-009 and STORE-020. */
function renderMemories(id) {
  if (id.startsWith('e:')) return renderEntity(memoryName(id));
  const own = memoriesAt(id), kept = {class: 'item', style: {'--c': `var(${colorVar(memoryLayer())})`}};
  fill($('#p-object'),
    h('div', {class: 'eyebrow'}, 'Memories'),
    h('h2', {}, nameOf(id)),
    S.elements.has(id) ? h('div', {class: 'addr'}, S.elements.get(id).element.address) : null,
    own.length ? own.map(name => {
      const entity = S.memory.entities.get(name);
      const related = S.memory.relations.filter(relation => relation.from === name || relation.to === name);
      return h('div', kept, h('a', {class: 'link', href: '#', onclick: event => { event.preventDefault(); select(memoryKey(name), true); }}, name),
        entity ? h('small', {}, ` · ${entity.entityType}`) : null,
        (entity?.observations || []).map(one => h('p', {class: 'itemtext'}, one.content)),
        related.map(relation => h('p', {class: 'meta'}, `${relation.from} ${relation.relationType} ${relation.to}`)));
    }) : h('p', {class: 'empty'}, 'No memories are kept here in the layers in view.'));
}
/* ---------- managing the memories, VIEW-031: Rich, 2026-10-02, "memories can be fricking poison to a project" ----------
 * A memory in the panel, as the memory module keeps it: its type, its observations, its relations and the nodes it is
 * joined to, each edited or deleted in place. Every change is written with the memory module's commands through
 * /api/memory; an edit writes the new before it deletes the old, so a failure loses nothing. The page is told of the
 * change by map.changed, VIEW-018, and reads the memories again. */
async function memoryWrite(...steps) {
  return wrote('/api/memory', {steps: steps.map(([command, args]) => ({command, arguments: args}))});
}
/* What is typed in the panel's editors survives the panel drawn again, with the focus, VIEW-018. */
function keepDrafts(pane, draw) {
  const drafts = new Map([...pane.querySelectorAll('[data-draft]')].map(field => [field.dataset.draft, field.value]));
  const focused = document.activeElement?.closest('[data-draft]')?.dataset.draft;
  draw();
  for (const field of pane.querySelectorAll('[data-draft]')) if (drafts.has(field.dataset.draft)) field.value = drafts.get(field.dataset.draft);
  if (focused) pane.querySelector(`[data-draft="${CSS.escape(focused)}"]`)?.focus();
}
const EDITING = new Set();  // the editors open in the memory panel, kept open when it is drawn again
function joinPlace(join) {
  return join.address !== undefined ? join.address : `${join.receiver} → ${join.provider}`;
}
function renderEntity(name, pane = $('#p-object')) {
  const entity = S.memory.entities.get(name);
  if (!entity) return fill(pane, h('div', {class: 'eyebrow'}, 'Memory'), h('p', {class: 'empty'}, `No memory named ${name}.`));
  const joins = S.memory.joins.filter(join => join.entity === name);
  const related = S.memory.relations.filter(relation => relation.from === name || relation.to === name);
  const others = [...S.memory.entities.keys()].filter(other => other !== name);
  const color = {'--c': `var(${colorVar(memoryLayer())})`};
  const draft = key => `${name}\u0000${key}`;
  const observation = one => {
    const row = h('div', {class: 'item obs', style: color}), editing = draft('obs:' + one.content);
    const show = () => { EDITING.delete(editing); fill(row, h('p', {class: 'itemtext'}, one.content),
      h('div', {class: 'acts'}, h('button', {class: 'edit', onclick: edit}, 'Edit'),
        h('button', {class: 'delete', onclick: () => memoryWrite(['delete_observations',
          {deletions: [{entityName: name, observations: [one.content]}]}])}, 'Delete'))); };
    const edit = () => {
      EDITING.add(editing);
      const text = h('textarea', {'data-draft': editing}, one.content);  // its text, so the row is found by it
      fill(row, text, h('div', {class: 'acts'}, h('button', {class: 'save', onclick: async () => {
        const changed = text.value.trim();
        if (!changed || changed === one.content) return show();
        EDITING.delete(editing);
        await memoryWrite(['add_observations', {observations: [{entityName: name, contents: [changed]}]}],
          ['delete_observations', {deletions: [{entityName: name, observations: [one.content]}]}]);
      }}, 'Save'), h('button', {class: 'cancel', onclick: show}, 'Cancel')));
    };
    if (EDITING.has(editing)) edit(); else show();
    return row;
  };
  const relation = one => h('div', {class: 'item rel', style: color},
    one.from === name ? h('b', {}, name) : h('a', {class: 'link', href: '#', onclick: event => { event.preventDefault(); select(memoryKey(one.from), true); }}, one.from),
    ` ${one.relationType} `,
    one.to === name ? h('b', {}, name) : h('a', {class: 'link', href: '#', onclick: event => { event.preventDefault(); select(memoryKey(one.to), true); }}, one.to),
    h('div', {class: 'acts'}, h('button', {class: 'delete', onclick: () => memoryWrite(['delete_relations',
      {relations: [{from: one.from, to: one.to, relationType: one.relationType}]}])}, 'Delete')));
  const joined = one => h('div', {class: 'item join', style: color},
    one.key ? h('a', {class: 'link', href: '#', onclick: event => { event.preventDefault(); enter(one.key); }}, nameOf(one.key))
      : h('b', {}, joinPlace(one)),
    one.orphaned ? h('small', {}, ' · orphaned, the map no longer holds it') : one.key ? h('small', {}, '; Enter goes there.') : null,
    h('div', {class: 'acts'}, h('button', {class: 'unjoin', onclick: () => memoryWrite(['unjoin', {id: one.join_id}])}, 'Take away')));
  const renaming = draft('rename');
  const naming = h('div', {class: 'naming', hidden: !EDITING.has(renaming)},
    h('input', {class: 'name', 'data-draft': draft('name'), value: name, 'aria-label': 'Name'}),
    h('input', {class: 'type', 'data-draft': draft('type'), value: entity.entityType, 'aria-label': 'Type'}),
    h('button', {class: 'save-entity', onclick: () => renameEntity(name, naming.querySelector('.name').value.trim(),
      naming.querySelector('.type').value.trim())}, 'Save'),
    h('button', {class: 'cancel', onclick: () => { EDITING.delete(renaming); naming.hidden = true; }}, 'Cancel'));
  const adding = h('textarea', {class: 'add-obs', 'data-draft': draft('add'), placeholder: 'A new observation'});
  const relating = h('input', {class: 'add-rel-type', 'data-draft': draft('reltype'), placeholder: 'relation, in active voice'});
  const target = h('select', {class: 'add-rel-to', 'aria-label': 'To'}, others.map(other => h('option', {value: other}, other)));
  keepDrafts(pane, () => fill(pane,
    h('div', {class: 'eyebrow'}, 'Memory'),
    h('h2', {}, name),
    h('div', {class: 'pills'}, h('span', {class: 'pill'}, entity.entityType), layerPill(memoryLayer())),
    h('div', {class: 'acts'}, h('button', {class: 'rename', onclick: () => { EDITING.add(renaming); naming.hidden = false; naming.querySelector('.name').focus(); }}, 'Rename or retype'),
      h('button', {class: 'forget', onclick: () => memoryWrite(['delete_entities', {entityNames: [name]}])}, 'Delete memory')),
    naming,
    h('div', {class: 'eyebrow'}, 'Observations'),
    entity.observations.length ? entity.observations.map(observation) : h('p', {class: 'empty'}, 'No observations.'),
    adding, h('button', {class: 'add-obs', onclick: async () => {
      const text = adding.value.trim();
      if (!text) return;
      adding.value = '';  // emptied before the write, so the panel drawn again for it does not keep it
      if (!await memoryWrite(['add_observations', {observations: [{entityName: name, contents: [text]}]}])) adding.value = text;
    }}, 'Add observation'),
    h('div', {class: 'eyebrow'}, 'Relations'),
    related.length ? related.map(relation) : h('p', {class: 'empty'}, 'No relations.'),
    others.length ? h('div', {class: 'add-rel'}, relating, target, h('button', {class: 'add-rel', onclick: async () => {
      const type = relating.value.trim();
      if (!type) return;
      relating.value = '';
      if (!await memoryWrite(['create_relations', {relations: [{from: name, to: target.value, relationType: type}]}])) relating.value = type;
    }}, 'Add relation')) : null,
    h('div', {class: 'eyebrow'}, 'Kept at'),
    joins.length ? joins.map(joined) : h('p', {class: 'empty'}, 'Joined to no node.')));
}
/* A memory renamed or retyped: the reference server has no command for it, so it is made again under its new name and
 * type with its observations, joined again to each node of the map it was joined to, its relations made again, and the
 * old one deleted. A join the map no longer holds cannot be made again. */
async function renameEntity(name, next, type) {
  const entity = S.memory.entities.get(name);
  EDITING.delete(`${name}\u0000rename`);
  if (!entity || !next || !type || (next === name && type === entity.entityType)) return renderEntity(name);
  const made = {name: next, entityType: type, observations: entity.observations.map(one => one.content)};
  const again = S.memory.joins.filter(join => join.entity === name && join.key)
    .map(join => ['create_entities', {entities: [made], node: targetOf(join.key)}]);
  const swap = value => value === name ? next : value;
  const related = S.memory.relations.filter(relation => relation.from === name || relation.to === name)
    .map(relation => ({from: swap(relation.from), to: swap(relation.to), relationType: relation.relationType}));
  const steps = [['create_entities', {entities: [made]}], ...again,
    ...(related.length ? [['create_relations', {relations: related}]] : [])];
  const gone = ['delete_entities', {entityNames: [name]}];
  if (next === name ? await memoryWrite(gone, ...steps) : await memoryWrite(...steps, gone)) S.selected = memoryKey(next);
}
/* ---------- the orphaned menu, LAYER-013: Rich, 2026-10-02, "the memory chains can just show what they were attached
 * to, like through an orphaned menu" ----------
 * The memory joins the map no longer holds, from `memory orphaned`, each with what it was attached to, and the memories
 * joined to no node at all; a join is taken away or its memory deleted from here. */
const O = {open: false};
async function orphans() {
  let lost;
  try { lost = (await read('memory-orphaned')).joins; } catch (error) { toast(error.message); return; }
  Object.assign(F, {id: null, which: null, ids: new Set(), drawn: new Map()});
  O.open = true;
  const loose = [...S.memory.entities.keys()].filter(name => !S.memory.joins.some(join => join.entity === name));
  $('#float .title').textContent = 'Orphaned memories';
  fill($('#float .body'),
    lost.length ? lost.map(join => h('div', {class: 'ticket orphan'}, h('b', {}, join.entity),
      h('p', {class: 'note'}, `was attached to ${joinPlace(join)}`),
      h('div', {class: 'acts'}, h('button', {class: 'unjoin', onclick: async () => {
        if (await memoryWrite(['unjoin', {id: join.join_id}])) orphans(); }}, 'Take away the join'),
        h('button', {class: 'forget', onclick: async () => {
          if (await memoryWrite(['delete_entities', {entityNames: [join.entity]}])) orphans(); }}, 'Delete memory'))))
      : h('p', {class: 'empty'}, 'No memory join is orphaned.'),
    loose.length ? [h('div', {class: 'eyebrow'}, 'Joined to no node'), loose.map(name => h('div', {class: 'ticket loose'},
      h('b', {}, name), h('div', {class: 'acts'}, h('button', {class: 'forget', onclick: async () => {
        if (await memoryWrite(['delete_entities', {entityNames: [name]}])) orphans(); }}, 'Delete memory'))))] : null);
  $('#float').hidden = false;
}
function renderOrphans() {
  $('#orphanBtn').textContent = `Orphaned memories ${S.memory.orphaned}`;
  if (O.open && !$('#float').hidden && $('#float .title').textContent === 'Orphaned memories') orphans();
}
$('#orphanBtn').onclick = () => { showAdmin(false); orphans(); };
/* Agent prompts, VIEW-039: how agents' permission prompts are answered, read from the settings each time the window
 * opens and written back to them, so the administrator's choice is the one every agent follows and never reverts. */
const PROMPT_WORDS = {'approve-all': 'Approve every prompt', 'approve-reads': 'Approve reads and searches; ask for the rest',
  ask_all: 'Ask every prompt as a question at the ticket'};
$('#promptsBtn').onclick = async () => {
  showAgentMenu(false);
  let found;
  try { found = await read('dispatch-prompts'); } catch (error) { return toast(error.message); }
  fill($('#prompts .choices'), found.choices.map(choice => h('label', {class: 'choice'},
    h('input', {type: 'radio', name: 'prompts', value: choice, checked: choice === found.value,
                onchange: async () => {
                  if (await wrote('/api/dispatch-prompts', {value: choice})) $('#prompts .saved').textContent = `Saved: ${choice}`;
                  else $(`#prompts input[value="${found.value}"]`).checked = true;
                }}),
    h('b', {}, choice), h('span', {}, PROMPT_WORDS[choice] || ''))));
  $('#prompts .saved').textContent = `Now: ${found.value}`;
  await readAutostart();
  $('#prompts').hidden = false;
};
/* The Agents menu: the agents' own settings and repair, kept apart from Administration's project-wide removals. */
function showAgentMenu(open) {
  $('#agentbox').hidden = !open;
  $('#agentsMenuBtn').setAttribute('aria-expanded', String(open));
}
$('#agentsMenuBtn').onclick = async event => {
  event.stopPropagation();
  showAdmin(false); showExport(false);
  const open = $('#agentbox').hidden;
  showAgentMenu(open);
  if (open) { await readAutostart(); $('#agentCount').value = AUTO.agents ?? 5; }  // the saved setting, as it is now
};
$('#agentbox').onclick = event => event.stopPropagation();
$('#agentCount').onchange = async event => {
  const count = Number(event.target.value);
  if (!Number.isInteger(count) || count < 1) { event.target.value = AUTO.agents ?? 5; return; }
  event.target.disabled = true;
  try {
    const saved = await wrote('/api/dispatch-autostart', {agents: count});
    if (saved) { Object.assign(AUTO, saved); event.target.value = saved.agents; toast(`Agents at once: ${saved.agents}.`); }
    else event.target.value = AUTO.agents ?? 5;
  } finally { event.target.disabled = false; }
};
/* Voting results, VIEW-043: each question put to a vote, its choices with their votes, the voters' own words, and
 * what came of it; an applied answer can be reopened from here. */
async function renderVotes() {
  let found = [];
  try { found = (await read('consensus-results')).results || []; } catch (error) { toast(error.message); }
  const counted = found.reduce((all, one) => Object.assign(all, {[one.outcome]: (all[one.outcome] || 0) + 1}), {});
  fill($('#votes .body'),
    h('p', {class: 'summary'}, found.length ? Object.entries(counted).map(([what, n]) => `${n} ${what}`).join(' · ') : 'Nothing has been put to a vote yet.'),
    ...found.map(one => h('div', {class: `vote-result ${one.state.toLowerCase()}`},
      h('div', {class: 'head'}, h('span', {class: 'pill'}, one.outcome), h('small', {}, `${one.votes} vote(s)${one.rule ? ' · ' + one.rule : ''}`),
        one.address ? h('small', {}, one.address) : null),
      h('p', {class: 'question'}, one.question || '(the question is gone)'),
      h('ul', {class: 'choices'}, one.choices.map(choice => h('li', {class: choice.choice === one.answer ? 'won' : ''},
        h('b', {}, String(choice.votes)), ' ', choice.choice))),
      one.said.length ? h('div', {class: 'said'}, one.said.map(said => h('p', {}, h('b', {}, said.kind === 'write-in' ? 'Wrote in: ' : 'Commented: '), said.text))) : null,
      one.still_applied ? h('button', {class: 'reopen', title: 'Undo this answer: the question waits for an answer again', onclick: async event => {
        event.target.disabled = true;
        if (await wrote('/api/reopen', {id: one.message_id})) { toast('Reopened.'); renderVotes(); } else event.target.disabled = false;
      }}, 'Reopen') : null)));
}
$('#votesBtn').onclick = async () => { showAgentMenu(false); $('#votes').hidden = false; await renderVotes(); };
$('#votes .close').onclick = () => { $('#votes').hidden = true; };
movable($('#votes'));
$('#resetAgentsBtn').onclick = async event => {
  showAgentMenu(false);
  event.target.disabled = true;
  try {
    const done = await wrote('/api/dispatch-reset', {});
    if (done) {
      toast(`Reset: ${done.released.length} ticket(s) back on the board, ${done.sessions_ended.length} dead session(s) closed; ${done.still_working.length} agent(s) still working.`);
      await renderBoard(); await renderAgents();
    }
  } finally { event.target.disabled = false; }
};
$('#prompts .close').onclick = () => { $('#prompts').hidden = true; };
movable($('#prompts'));
function aspect() { const box = $('#viewport').getBoundingClientRect(); return Math.max(0.2, box.width / Math.max(1, box.height)); }
function frame(box) {
  let {x, y, w, h: height} = box; const a = aspect();
  if (w / height > a) { const nh = w / a; y -= (nh - height) / 2; height = nh; } else { const nw = height * a; x -= (nw - w) / 2; w = nw; }
  return {x, y, w, h: height};
}
/* A view fades in or out, and the promise settles once the browser has run the fade's time, which starts late when
 * frames come late; a fade that changes nothing settles on the timer. With reduced motion it changes at once,
 * VIEW-016. */
function fade(svg, to, ms = 480) {
  if (reduced()) { svg.style.transition = ''; svg.style.opacity = ''; return Promise.resolve(); }
  svg.style.transition = `opacity ${ms}ms ease`;
  svg.getBoundingClientRect();  // the fade starts from the opacity the view has now
  svg.style.opacity = String(to);
  const run = svg.getAnimations().find(one => one.transitionProperty === 'opacity');
  if (!run) return new Promise(resolve => setTimeout(resolve, ms));
  return run.finished.then(() => {}, () => {});  // a fade cut by another, or by its view leaving the page, settles too
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
const near = (a, b) => Boolean(a && b) && ['x', 'y', 'w', 'h'].every(k => Math.abs(a[k] - b[k]) <= Math.max(a.w, b.w) * 1e-4);
function stopCam() { cancelAnimationFrame(M.frame); M.to = null; }
/* Every move of the 2D camera eases in and out and is never set at once, VIEW-041; with reduced motion it moves at
 * once, VIEW-016. A move to where the camera is already going goes on as it is. */
function moveCam(target) {
  if (!M.svg) return;
  const to = frame(target);
  if (!M.cam) return setCam(to);
  if (near(M.to || M.cam, to)) return;
  stopCam();
  const from = {...M.cam};
  M.zoom = {w: to.w, h: to.h};
  if (reduced()) return setCam(to);
  M.to = to;
  // Its time starts at its first frame, so work the page does before that frame is not skipped over in one step.
  let start = null;
  const duration = 700, ease = t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  const step = now => {
    start ??= now;
    const k = ease(Math.min(1, (now - start) / duration));
    setCam({x: from.x + (to.x - from.x) * k, y: from.y + (to.y - from.y) * k, w: from.w + (to.w - from.w) * k, h: from.h + (to.h - from.h) * k}, false);
    if (k < 1) M.frame = requestAnimationFrame(step); else M.to = null;
  };
  M.frame = requestAnimationFrame(step);
}
/* The two modes of the 2D map in the large area, VIEW-041: `whole` keeps the whole diagram fitted to the area, and
 * `readable` fits it the same way but never draws its text below the minimum the keys 1 to 9 set, 8 to 24 px, holding
 * the selected node at the center when the minimum wins. The wheel leaves both, null, until a click or Fit. They set
 * the camera of the whole map; a node's own graph and a memory network keep theirs, and the small area keeps the zoom
 * VIEW-008 gives it. */
const large = () => $('.app').classList.contains('swapped');
const moded = () => large() && Boolean(MODE.mode) && Boolean(M.base) && M.svg === M.base.svg;
const at2d = id => !id ? null : M.nodes.get(id) || (id.startsWith('p:') ? M.nodes.get(joinOf(id)?.provider) : null);
function smallestText(svg) {  // the smallest font size of the diagram's labels, in its own units
  let least = Infinity;
  for (const text of svg.querySelectorAll('text, tspan'))
    if ([...text.childNodes].some(node => node.nodeType === 3 && node.textContent.trim()))
      least = Math.min(least, parseFloat(getComputedStyle(text).fontSize) || Infinity);
  return isFinite(least) ? least : 13;
}
function modeTarget() {
  const fit = frame(M.fit), area = M.svg.getBoundingClientRect();
  if (MODE.mode !== 'readable' || !area.width || !area.height) return fit;
  M.base.text ??= smallestText(M.base.svg);
  // The viewBox at which that text, times the screen pixels per unit, is the minimum; the larger on screen wins.
  const w = area.width * M.base.text / (6 + 2 * MODE.key), height = w * area.height / area.width;
  if (w >= fit.w) return fit;
  const entry = [...S.elements.values()].find(item => item.element.role === 'DE')?.element.id;
  const center = at2d(S.selected) || M.nodes.get(entry) || {x: fit.x + fit.w / 2, y: fit.y + fit.h / 2};
  return {x: center.x - w / 2, y: center.y - height / 2, w, h: height};
}
function applyMode() { if (moded()) moveCam(modeTarget()); }
function fit2D() {
  if (large()) MODE.mode = 'whole';
  M.view = 'out';
  $('#map2d').classList.remove('focused');
  for (const edge of M.edges) edge.path?.classList.remove('on');
  for (const node of M.nodes.values()) node.g.classList.remove('sel', 'near');
  if (M.fit) moveCam(M.fit);
}
function focus2D(id, framing = 'around', zoom = false) {
  const join = id.startsWith('p:') ? joinOf(id) : null;
  const node = M.nodes.get(id) || (join ? M.nodes.get(join.provider) : null);
  if (!M.svg) return;
  if (!node) return applyMode();
  if (IN.length) {
    for (const [key, value] of M.nodes) value.g.classList.toggle('sel', key === id);
  } else {
    $('#map2d').classList.add('focused');
    for (const [key, value] of M.nodes) { value.g.classList.toggle('sel', key === id); value.g.classList.toggle('near', key !== id && S.neighbors.has(key)); }
    for (const edge of M.edges) edge.path?.classList.toggle('on', join ? edge.join === join
      : edge.join.receiver === id || edge.provider === id);
  }
  if (moded()) return moveCam(modeTarget());  // in the large area the mode sets the camera, VIEW-041
  // Selecting moves the view to the node at the zoom it has; the zoom changes only when Fit asks, VIEW-008.
  const held = M.zoom || M.cam;
  if (!zoom) return moveCam({x: node.x - held.w / 2, y: node.y - held.h / 2, w: held.w, h: held.h});
  // 'around' shows the node with its joined nodes; 'inside' frames the node so the nodes it holds fill the view;
  // 'close' moves nearer to a node that holds nothing.
  M.view = framing === 'around' ? 'around' : 'in';
  const [w, height] = framing === 'inside' ? [node.w * 1.25, node.h * 1.25]
    : framing === 'close' ? [Math.max(node.w * 1.8, 160), Math.max(node.h * 2.6, 110)]
    : [Math.max(node.w * 3.4, 380), Math.max(node.h * 5, 260)];
  moveCam({x: node.x - w / 2, y: node.y - height / 2, w, h: height});
}
/* One click selects; a click on the selected node goes inside it; a group's "more" node shows the next ones. In the
 * large area a click on a node goes to mode two, VIEW-041. */
function clicked2d(id) {
  if (large()) MODE.mode = 'readable';
  if (!MEM.key && (id === S.selected || id.startsWith('m:'))) goInside(id); else select(id, true);
}
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
      stopCam();
      drag.cam = {...M.cam};
      drag.moving = true; host.setPointerCapture(event.pointerId);
    }
    const box = $('#viewport').getBoundingClientRect(), scale = M.cam.w / box.width;
    setCam({...drag.cam, x: drag.cam.x - (event.clientX - drag.x) * scale, y: drag.cam.y - (event.clientY - drag.y) * scale});
  });
  host.addEventListener('pointerup', () => { drag = null; });
  host.addEventListener('wheel', event => {
    if (!M.cam) return;
    event.preventDefault();
    if (large()) MODE.mode = null;  // the wheel leaves both modes, VIEW-041
    // The wheel zooms at once, by how far it turned: flat steps on a mouse wheel, its own acceleration on a trackpad.
    // No easing: a zoom that lags the wheel and lands after it stops is not how a mouse works.
    stopCam();
    const lines = event.deltaMode === 1 ? event.deltaY * 16 : event.deltaMode === 2 ? event.deltaY * 400 : event.deltaY;
    const f = Math.exp(Math.max(-200, Math.min(200, lines)) * 0.0015), box = $('#viewport').getBoundingClientRect();
    const px = (event.clientX - box.left) / box.width, py = (event.clientY - box.top) / box.height, c = M.cam;
    const w = c.w * f, height = c.h * f;
    const to = frame({x: c.x + (c.w - w) * px, y: c.y + (c.h - height) * py, w, h: height});
    M.zoom = {w: to.w, h: to.h};
    setCam(to);
  }, {passive: false});
  new ResizeObserver(() => applyMode()).observe($('#viewport'));  // the area changes size: the new fit, VIEW-041
})();
function fitAll() { fit2D(); fit3d(); }
/* Fit and F go through three views, Rich 2026-09-26: zoomed out to the whole map, zoomed in on the selected node,
 * with the nodes inside it when it holds any, and regular, the node with its joined nodes. In the large area they go
 * back to mode one, VIEW-041. */
function cycleView() {
  const here = S.selected;
  const next = {around: 'out', out: 'in', in: 'around'}[M.view || 'around'];
  if (large() || !here || next === 'out') return fit2D();  // its own map only; the 3D map has a Fit of its own, VIEW-028
  if (next === 'in') return focus2D(here, 'close', true);
  focus2D(here, 'around', true);
}
/* Back and forward step through the nodes selected, as a browser does; a new selection drops the steps forward. */
async function step(by) {
  if (MEM.key) { if (by < 0) leaveMemories(); return; }  // back from a memory network is back to the map, VIEW-031
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
  $('#backBtn').disabled = !MEM.key && S.at <= 0;
  $('#forwardBtn').disabled = Boolean(MEM.key) || S.at >= S.history.length - 1;
}

/* The keys walk the join tree, Rich 2026-09-26: Down goes deeper, to the providers of the node's joins and then to
 * the nodes inside it; Up goes back to the parent; Left and Right move between the nodes connected to the parent.
 * Enter goes inside a node; Escape or Shift+Enter backs out. F fits. */
function across(keys) {  // in their order across the 2D map
  const at = key => M.nodes.get(key) || {x: Infinity, y: Infinity};
  return [...keys].sort((a, b) => M.vertical ? at(a).x - at(b).x || at(a).y - at(b).y : at(a).y - at(b).y || at(a).x - at(b).x);
}
/* Down goes down an edge to the node drawn nearest under the selected one, across the map's other axis, so with seven
 * below it lands near the middle and not at the far end of the row; the nodes inside a node are gone to when no edge
 * leads down. A row not drawn yet gives its middle node. */
function below(key) {
  const row = childrenOf(key);
  const here = M.nodes.get(key), axis = M.vertical ? 'x' : 'y';
  const drawn = row.filter(child => M.nodes.has(child));
  if (!here || !drawn.length) return row[Math.floor((row.length - 1) / 2)];
  return drawn.reduce((best, child) =>
    Math.abs(M.nodes.get(child)[axis] - here[axis]) < Math.abs(M.nodes.get(best)[axis] - here[axis]) ? child : best);
}
/* Past either end of a parent's row, Left and Right go on to the nodes of the next parent over on the parent's level,
 * the first of them going right and the last going left, and past the last parent of the level round to the first, so
 * every node of a level is reached by Left and Right alone. A level is the children of every node on the level above,
 * in their order across the map, starting from the roots. Returns the node and the parent it is reached under. */
/* The node drawn nearest beside a node on its row of the 2D map, that way. */
function besideDrawn(key, by) {
  const here = M.nodes.get(key);
  if (!here) return null;
  const depth = M.vertical ? 'y' : 'x', across = M.vertical ? 'x' : 'y';
  const onward = [...M.nodes.entries()].filter(([id, node]) => id !== key
    && Math.abs(node[depth] - here[depth]) < 2 && (node[across] - here[across]) * by > 0);
  if (!onward.length) return null;
  return onward.reduce((best, one) => Math.abs(one[1][across] - here[across]) < Math.abs(best[1][across] - here[across]) ? one : best)[0];
}
function besideOnLevel(key, parent, by) {
  if (!parent) return null;  // the roots are one row already
  let level = roots(), seen = new Set(level);
  while (level.length && !level.includes(parent)) {
    level = level.flatMap(node => childrenOf(node)).filter(node => !seen.has(node) && seen.add(node));
  }
  if (!level.length) return null;
  const row = level.flatMap(node => childrenOf(node).map(next => ({next, parent: node})))
    .filter((one, at, all) => all.findIndex(other => other.next === one.next) === at);
  const at = row.findIndex(one => one.next === key && one.parent === parent);
  const from = at >= 0 ? at : row.findIndex(one => one.next === key);
  if (from < 0 || row.length < 2) return null;
  return row[(from + by + row.length) % row.length];
}
function childrenOf(key) {
  if (key.startsWith('p:')) return across((joinOf(key)?.providers || []).filter(id => S.elements.has(id)));
  return across(new Set(S.joins.filter(join => join.receiver === key).flatMap(join => join.providers)
    .filter(id => S.elements.has(id))));
}
function parentOf(key) {
  if (key.startsWith('p:')) return joinOf(key)?.receiver || null;
  return across(new Set(S.joins.filter(join => join.providers.includes(key) && S.elements.has(join.receiver)).map(join => join.receiver)))[0] || null;
}
function roots() {  // the nodes nothing receives from, CQUs first; then any part of the map they do not reach
  const top = [...S.elements.keys()].filter(key => !parentOf(key));
  const ordered = [...across(top.filter(key => S.elements.get(key).element.role === 'CQU')), ...across(top.filter(key => S.elements.get(key).element.role !== 'CQU'))];
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
function goInside(key) { if (!MEM.key) enter(key); }  // a memory network has no inside of its own
function backOut() {
  if (MEM.key) return leaveMemories();
  if (IN.length) return goTo(IN.length - 1);
  const here = S.selected;
  if (!here) return;
  if (here.startsWith('p:')) {
    const up = S.trail.length ? S.trail.pop() : parentOf(here);
    if (up) select(up, true, true);
  } else fitAll();
}
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && !$('#layerlist').hidden) { event.preventDefault(); showLayers(false); $('#layersBtn').focus(); return; }
  if (event.key === 'Escape' && !$('#adminbox').hidden) { event.preventDefault(); showAdmin(false); $('#adminBtn').focus(); return; }
  if (event.key === 'Escape' && !$('#exportbox').hidden) { event.preventDefault(); showExport(false); $('#exportBtn').focus(); return; }
  if (event.key === 'Escape' && !$('#clearbox').hidden) { event.preventDefault(); showClear(false); $('#adminBtn').focus(); return; }
  // A key typed into a text is a letter of it and never a shortcut.
  if (event.target.closest('select, input, textarea, .CodeMirror, [contenteditable="true"]')) return;
  if (event.key === 'f' || event.key === 'F') { event.preventDefault(); cycleView(); return; }
  if (event.key === 'Home') { event.preventDefault(); fitAll(); return; }
  // In the large area the keys 1 to 9 set the minimum text, 8 to 24 px, and go to mode two, VIEW-041.
  if (/^[1-9]$/.test(event.key) && !event.ctrlKey && !event.metaKey && !event.altKey && large()) {
    event.preventDefault(); Object.assign(MODE, {mode: 'readable', key: Number(event.key)}); applyMode(); return;
  }
  if (!S.selected) return;
  const here = S.selected;
  if (event.key === 'Escape' || (event.key === 'Enter' && event.shiftKey)) { event.preventDefault(); backOut(); return; }
  if (event.key === 'Enter') { event.preventDefault(); goInside(here); return; }
  if ((IN.length || MEM.key) && event.key.startsWith('Arrow')) {  // inside a node or a memory network the arrows go through its graph in order
    event.preventDefault();
    const order = across(M.nodes.keys()), at = order.indexOf(here);
    const by = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : -1;
    if (order.length) select(order[at < 0 ? 0 : (at + by + order.length) % order.length], true, true);
    return;
  }
  if (event.key === 'ArrowDown') {
    event.preventDefault();
    const next = below(here);
    if (next) { S.trail.push(here); select(next, true, true); }
  } else if (event.key === 'ArrowUp') {
    event.preventDefault();
    const parent = S.trail.length ? S.trail.pop() : parentOf(here);
    if (parent) select(parent, true, true);
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    event.preventDefault();
    const parent = S.trail.length ? S.trail[S.trail.length - 1] : parentOf(here);
    const row = parent ? childrenOf(parent) : roots();
    const at = row.indexOf(here), by = event.key === 'ArrowRight' ? 1 : -1;
    if (at >= 0 && row[at + by]) { select(row[at + by], true, true); return; }
    // past the end of the row: the node drawn nearest beside it that way, whatever its parent, whose row it is in
    // then; with nothing drawn beyond, round the level of the tree
    const drawn = besideDrawn(here, by);
    const beside = drawn ? {next: drawn, parent: parentOf(drawn)} : besideOnLevel(here, parent, by);
    if (!beside) return;
    if (S.trail.length && beside.parent) S.trail[S.trail.length - 1] = beside.parent;
    select(beside.next, true, true);
  }
});

/* ---------- selection: both views move together; the long text goes in the panel ----------
 * A selection made as the map is loaded or read again, again, leaves open the tab of the panel the person has open,
 * such as the prompt being edited. */
function select(id, fly, keepTrail = false, stepping = false, again = false) {
  if (!id) return;
  const join = id.startsWith('p:') ? joinOf(id) : null;
  const entity = Boolean(MEM.network?.entities.includes(id));  // a node of the memory network open, VIEW-031
  const known = join || S.elements.has(id) || entity,
    thing = IN.at(-1)?.things?.get(id) || S.items.get(id) || memoryThing(id);
  if (!known && !thing) return;
  if (!keepTrail) S.trail = [];
  const path = IN.map(({key, label}) => ({key, label})), last = S.history[S.at];
  if (!stepping && !MEM.key && !(last && last.id === id && samePath(last.path, path))) {
    S.history = [...S.history.slice(0, S.at + 1), {id, path}]; S.at = S.history.length - 1;
  }
  showSteps();
  S.selected = id;
  setReach(id);
  if (!known) { S.neighbors = new Set(); focus2D(id); if (!again) showTab('object'); renderThing(thing); return; }
  S.neighbors = MEM.key ? new Set([id, ...(MEM.network?.relations || []).flatMap(relation =>
      relation.from === id ? [relation.to] : relation.to === id ? [relation.from] : [])])
    : join ? new Set([join.receiver, ...join.providers])
    : new Set([id, ...S.joins.filter(item => item.receiver === id).flatMap(item => item.providers),
      ...S.joins.filter(item => item.providers.includes(id)).map(item => item.receiver)]);
  if (G) {
    G.nodeColor(G.nodeColor());
    const node = G.graphData().nodes.find(item => item.id === id);
    if (fly && node) fly3d(id);
  }
  focus2D(id);
  if (!again) showTab('object');
  // The panel's reads are returned, so a load waits for them before it says it is loaded.
  return MEM.key ? renderMemories(id) : join ? renderJoin(join) : renderObject(id);
}

function refsOf(refs) {
  return refs && refs.length ? h('div', {class: 'refs'}, refs.map(ref => h('span', {}, h('span', {class: 'k'}, ref.key), ref.value))) : null;
}
/* The work records of the selected object, MAP-046: each with its condition, note and task, held and reviewed,
 * and its resolution once done; read from /api/work for the node and written into the panel's work box. */
function workPill(condition) { return h('span', {class: `pill work-${condition}`}, condition); }
/* A question at the node, MAP-050 and VIEW-021, as the question form wrote it: the question, then each part the agent
 * filled under its heading, each with Create ticket so the person can turn it into work. Open, it takes a typed answer
 * or a click on a choice; answered, the answer stays beside it. */
const FORM_PARTS = [['#1 Specifications reviewed:', 'Investigate why the specifications did not settle this'],
  ['#2 Why this is not a configuration option:', 'Review whether this should be a configuration option'],
  ['#3 Unexplained "Rich said":', 'Decipher this, or delete it and reconstruct a proper, clear specification']];
function formParts(text) {
  const lines = (text || '').split('\n'), parts = [];
  let question = [], current = null;
  for (const line of lines) {
    const part = FORM_PARTS.find(([heading]) => line.trim() === heading);
    if (part) { current = {heading: part[0], task: part[1], lines: []}; parts.push(current); continue; }
    (current ? current.lines : question).push(line);
  }
  return {question: question.join('\n').trim(), parts: parts.map(part => ({...part, text: part.lines.join('\n').trim()}))};
}
function asked(record, metaform = S.base, full = false) {
  const answer = h('textarea', {class: 'answer', placeholder: 'Type an answer or a message'});
  const written = text => wrote('/api/answer', {id: record.id, answer: text, metaform});
  const send = h('button', {class: 'answer', onclick: async () => {
    if (!answer.value.trim()) return;
    send.disabled = true;
    if (!await written(answer.value)) send.disabled = false;
  }}, 'Send');
  // The answers the agent suggests, the one it recommends first: one click answers; the box takes anything else.
  const suggested = record.closed ? [] : (record.suggestions || []).map(String);
  const choices = suggested.length ? h('div', {class: 'choices'},
    suggested.map((text, index) => h('button', {class: index ? 'suggestion' : 'suggestion recommended', onclick: async event => {
      const buttons = [...event.target.parentNode.children];
      for (const button of buttons) button.disabled = true;
      if (!await written(text)) for (const button of buttons) button.disabled = false;
    }}, text))) : null;
  const {question, parts} = formParts(record.text);
  const node = nodeOf(record);
  const sections = parts.map(part => h('div', {class: 'form-part'},
    h('div', {class: 'heading'}, part.heading),
    h('p', {class: 'said'}, ...linked(part.text)),
    h('button', {class: 'create-ticket', title: 'Write a ticket from this part, at the node of the question', onclick: () => {
      if ($('#qa')) $('#qa').hidden = true;
      giveWork(node, `${part.task}: ${part.text}\n\nFrom question: ${question}`);
    }}, 'Create ticket')));
  const chat = h('button', {class: 'chat', title: 'Summon an agent to talk this question through with you', onclick: async event => {
    event.target.disabled = true;
    try { await questionChat(record, metaform); }
    catch (error) { toast(error.message); }
    finally { event.target.disabled = false; }
  }}, 'Chat with an agent');
  const reader = full ? null : h('button', {class: 'read-full', title: 'Read the whole question in a large window', onclick: () => {
    fill($('#qa .body'), asked(record, metaform, true));
    $('#qa').hidden = false;
  }}, 'Read in full');
  // Help me answer, VIEW-043: three agents say what it means and what they would answer; nothing changes until a click
  const advice = record.closed ? null : h('div', {class: 'advice', 'data-id': record.id});
  const helper = record.closed ? null : h('button', {class: 'help-answer',
    title: 'Three agents each explain the question in plain words and say what they would answer; nothing is applied',
    onclick: async event => {
      event.target.disabled = true;
      if (await wrote('/api/recommend', {id: record.id})) drawAdvice(advice, record, written);
      else event.target.disabled = false;
    }}, 'Help me answer');
  if (advice) drawAdvice(advice, record, written);
  return h('div', {class: full ? 'item work question-form full' : 'item work question-form'},
    h('div', {class: 'pills'}, workPill('question'), h('span', {class: 'pill'}, record.closed ? 'answered' : 'open'),
      record.by ? h('span', {class: 'pill'}, record.by) : null, chat, helper, reader),
    h('p', {class: 'asked'}, ...linked(question)),
    ...sections,
    advice,
    record.closed ? h('p', {class: 'obs'}, `Answer: ${record.answer || ''}`) : [choices, h('div', {class: 'typed'}, answer, send)],
    // Answered by mistake: Reopen clears the answer and the question waits again with its suggestions, MAP-050.
    record.closed ? h('button', {class: 'reopen', onclick: async event => {
      event.target.disabled = true;
      if (!await wrote('/api/reopen', {id: record.id, metaform})) event.target.disabled = false;
    }}, 'Reopen') : null);
}
$('#qa .close').onclick = () => { $('#qa').hidden = true; };
/* What the helpers said about a question: its meaning in plain words, the count for each answer with the recommended
 * one first, each answer one click away, and the other helpers' readings folded below. */
async function drawAdvice(box, record, written) {
  box.answer = written;
  let found;
  try { found = await read('advice', {id: record.id}); } catch { return; }
  const said = found.advice || [];
  if (!said.length) {
    fill(box, found.reading ? h('p', {class: 'reading'}, `${found.reading} agents are reading the question…`) : null);
    return;
  }
  const lead = said.find(one => one.choice === found.recommendation) || said[0];
  const answers = [...new Set(said.map(one => one.choice))]
    .sort((a, b) => (b === found.recommendation) - (a === found.recommendation) || (found.counts[b] || 0) - (found.counts[a] || 0));
  const pick = text => h('button', {class: text === found.recommendation ? 'suggestion recommended' : 'suggestion',
    title: 'Answer with this', onclick: async event => {
      const buttons = [...box.querySelectorAll('button')];
      for (const button of buttons) button.disabled = true;
      if (!await written(text)) for (const button of buttons) button.disabled = false;
    }}, text);
  fill(box, h('div', {class: 'eyebrow'}, 'What it means'), h('p', {class: 'meaning'}, lead.meaning || ''),
    h('div', {class: 'eyebrow'}, `What ${said.length} agent${said.length === 1 ? '' : 's'} would answer`),
    h('div', {class: 'tally'}, answers.map(text => h('div', {class: 'row'}, pick(text),
      h('span', {class: 'count'}, String(said.filter(one => one.choice === text).length))))),
    h('p', {class: 'reason'}, h('b', {}, 'Why: '), lead.reason || ''),
    said.length > 1 ? h('details', {}, h('summary', {}, 'Every agent\'s reading'),
      said.map(one => h('div', {class: 'one'}, h('p', {}, h('b', {}, `${one.choice}. `), one.meaning || ''),
        h('p', {class: 'reason'}, one.reason || '')))) : null,
    found.reading ? h('p', {class: 'reading'}, `${found.reading} more still reading…`) : null);
}
const refreshAdvice = () => document.querySelectorAll('.advice[data-id]').forEach(box =>
  box.answer && drawAdvice(box, {id: box.dataset.id}, box.answer));
/* The review-or-merge flow, VIEW-044: Review. while done work waits; a click takes it over for good, offers an agent's
 * help, and the help comes in a support window at the lower right. */
const MERGE = {rows: [], chat: null, since: 0};
async function renderMerges() {
  if (!S.project) return;
  try { MERGE.rows = (await read('merges')).merges || []; } catch { MERGE.rows = []; }
  const at = seconds => new Date(seconds * 1000).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
  fill($('#reviewNotice'), MERGE.rows.map(row => {
    const ticket = (B.tickets || []).find(one => one.id === row.work_id);
    return h('div', {class: 'notice'}, h('b', {}, 'Review.'),
      h('span', {}, ` ${ticket ? (ticket.task || ticket.note || '').slice(0, 80) : row.branch} · merges by itself at ${at(row.deadline)}`),
      h('button', {onclick: event => takeReview(row.work_id, event.target)}, 'Review'));
  }));
  $('#reviewNotice').hidden = !MERGE.rows.length;
}
async function takeReview(workId, button) {
  button.disabled = true;
  if (!await wrote('/api/merge-review', {work_id: workId})) { button.disabled = false; return; }
  await renderMerges();
  $('#mergeAsk .yes').onclick = async () => {
    $('#mergeAsk').hidden = true;
    openHelpdesk(workId);
    if (!await wrote('/api/merge-assist', {work_id: workId})) drawHelpdesk('The agent could not be started.');
  };
  $('#mergeAsk .no').onclick = () => { $('#mergeAsk').hidden = true; toast('The merge is yours to handle; its countdown is off.'); };
  $('#mergeAsk').hidden = false;
}
/* The chat dock: a thin sliver at the lower right that lifts when the pointer comes near and opens, on a click, into a
 * customer-service chat. Call reaches the person's system agent, the +1 outside the agent limit; /list and /chat <n>
 * talk with an agent at work instead. Bubbles alternate: the person's on the right, the agent's on the left. A file
 * attached with the paperclip is saved in the project and the agent is told where. Live monitoring stays in the agent
 * window; this is only the conversation. */
const DOCK = {target: null, session: null, label: '', since: 0, notes: [], list: [], files: [], mine: null, waiting: '',
  calling: null};
const STANDBY = 'Please stand by while we contact an agent for you.';
function dockState(state) {
  $('#dock').className = state;
  $('#helpdesk').hidden = state !== 'open' && state !== 'open big';
}
function dockNote(text) { DOCK.notes.push({at: Date.now(), text}); drawHelpdesk(); }
/* session: the session the chat is with, when it is known. The chat stays with it, so a later session of the same
 * ticket never swaps the conversation; with none known yet, the chat waits for the ticket's running session and then
 * stays with that one. */
function openHelpdesk(workId, label = 'an agent', waiting = 'Waiting for the next available agent.', session = null) {
  Object.assign(DOCK, {target: workId, session, label, waiting, since: Date.now()});
  MERGE.chat = workId;
  if (!$('#dock').className.startsWith('open')) dockState('open');
  $('#helpdesk .call').textContent = 'Dismiss';
  drawHelpdesk();
}
async function drawHelpdesk(trouble) {
  let lines = [];
  const target = DOCK.target;
  if (target) {
    try {
      const found = await read('dispatch-sessions', {id: target});
      if (DOCK.target !== target) return;  // the chat moved on while this was read
      const sessions = found.sessions || [];
      const session = DOCK.session ? sessions.find(one => one.session_id === DOCK.session)
        : sessions.filter(one => one.state === 'running').at(-1);
      if (session) DOCK.session = session.session_id;
      lines = session ? (found.lines || []).filter(line => line.session_id === session.session_id) : [];
    } catch (error) { trouble = error.message; }
  }
  const said = lines.filter(line => line.kind === 'agent_message_chunk' || line.kind === 'person');
  const waiting = DOCK.target && !said.some(line => line.kind !== 'person');
  $('#helpdesk .with').textContent = DOCK.target ? `With ${DOCK.label}` : 'Online';
  const intro = 'You are connected to Metaform Support. Press Call to reach an agent, or type /help.';
  const system = (key, text) => ({key, text, make: () => h('div', {class: 'system'}, text)});
  const log = $('#helpdesk .log');
  const changed = keyedFill(log, [
    system('intro', intro),
    ...DOCK.notes.filter(note => note.at >= DOCK.since - 1).map((note, index) => system(`note:${note.at}:${index}`, note.text)),
    ...said.map(line => ({key: `${line.session_id}:${line.name ?? line.seq}`, text: line.text,
      make: () => h('div', {class: line.kind === 'person' ? 'bubble mine' : 'bubble theirs'}, line.text)})),
    ...(waiting ? [{key: 'waiting', text: DOCK.waiting, make: () => h('div', {class: 'system waiting'}, DOCK.waiting,
      h('span', {class: 'typing', 'aria-hidden': 'true'}, h('i'), h('i'), h('i')))}] : []),
    ...(trouble ? [system('trouble', trouble)] : [])]);
  if (changed) log.scrollTop = log.scrollHeight;
}
async function dockCommand(text) {
  const [command, ...rest] = text.slice(1).trim().split(/\s+/);
  if (command === 'help') return dockNote('/list shows the agents at work · /chat <number> talks with one of them · /system calls your system agent · Call and Dismiss do the same from the button.');
  if (command === 'list') {
    let found = [];
    try { found = (await read('dispatch-sessions', {thread: 'false'})).sessions || []; } catch (error) { return dockNote(error.message); }
    DOCK.list = found.filter(one => one.state === 'running');
    return dockNote(DOCK.list.length ? DOCK.list.map((one, index) => `${index + 1}. ${agentName(one.agent)} on ${ticketPart(ticketOf(one.work_id))}${one.activity ? ' · ' + one.activity : ''}`).join('\n')
      : 'No agent is at work right now.');
  }
  if (command === 'chat') {
    const chosen = DOCK.list[Number(rest[0]) - 1];
    if (!chosen) return dockNote('Type /list first, then /chat with the number of the agent.');
    openHelpdesk(chosen.work_id, `${agentName(chosen.agent)} on ${ticketPart(ticketOf(chosen.work_id))}`, 'It answers when its current step ends.',
      chosen.session_id);
    return dockNote(`You are now talking with ${DOCK.label}. Its work goes on while you talk.`);
  }
  if (command === 'system') return callSystem();
  dockNote(`${text} is not a command here. Type /help.`);
}
async function callSystem() {
  dockState($('#dock').className.startsWith('open') ? $('#dock').className : 'open');
  Object.assign(DOCK, {since: Date.now()});
  $('#helpdesk .call').textContent = 'Dismiss';
  dockNote(STANDBY);
  const call = DOCK.calling = {};
  const started = await wrote('/api/system-chat', {});
  if (DOCK.calling !== call) {  // dismissed while it was being reached: it is stopped as soon as it answers
    if (started) await wrote('/api/dispatch-stop', {work_id: started.work_id});
    return;
  }
  DOCK.calling = null;
  if (!started) { $('#helpdesk .call').textContent = 'Call'; return; }
  DOCK.mine = started.work_id;
  openHelpdesk(started.work_id, 'your system agent', STANDBY, started.session_id);
}
/* Chat on anything the page shows, VIEW-042: a ticket, open or done, a node, a question, or an agent's session. An
 * agent at work on it is talked to directly; otherwise one starts to talk, and Dismiss stops it. */
async function talkAbout(given, label) {
  const started = await wrote('/api/talk', given);
  if (!started) return;
  if (started.conversation) DOCK.mine = started.work_id;
  openHelpdesk(started.work_id, label, started.state === 'running' ? 'It answers when its current step ends.' : STANDBY,
    started.session_id);
}
const chatButton = (given, label) => h('button', {class: 'chat', title: `Talk with an agent about ${label}`,
  onclick: event => { event.stopPropagation(); talkAbout(given, label); }}, 'Chat');
/* What a node is called to the agent: an element's address, or a join's receiver, which holds it. */
function nodeTalk(id) {
  const join = id.startsWith('p:') ? joinOf(id) : null;
  return {node: join ? join.receiver_address : S.elements.get(id)?.element.address || id};
}
async function dismiss() {
  if (DOCK.calling) {
    DOCK.calling = null;
    $('#helpdesk .call').textContent = 'Call';
    return dockNote('The call was cancelled.');
  }
  if (DOCK.target && DOCK.target === DOCK.mine) await wrote('/api/dispatch-stop', {work_id: DOCK.mine});
  Object.assign(DOCK, {target: null, session: null, label: '', mine: DOCK.target === DOCK.mine ? null : DOCK.mine});
  MERGE.chat = null;
  $('#helpdesk .call').textContent = 'Call';
  dockNote('The agent was dismissed.');
}
$('#helpdesk .call').onclick = () => (DOCK.target || DOCK.calling ? dismiss() : callSystem());
$('#helpdesk .compose').onsubmit = async event => {
  event.preventDefault();
  const box = $('#helpdesk .say'), text = box.value.trim();
  if (!text && !DOCK.files.length) return;
  box.value = '';
  if (text.startsWith('/')) return dockCommand(text);
  if (!DOCK.target) return dockNote('Press Call to reach an agent first, or type /list to talk with one at work.');
  const attached = DOCK.files.length ? '\n\nAttached files, saved in the project:\n' + DOCK.files.map(file => `- ${file}`).join('\n') : '';
  if (await wrote('/api/dispatch-message', {work_id: DOCK.target, text: text + attached})) {
    DOCK.files = []; fill($('#helpdesk .files')); drawHelpdesk();
  } else box.value = text;
};
$('#helpdesk .say').addEventListener('keydown', event => {  // Enter sends, Shift+Enter starts a new line
  if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); $('#helpdesk .compose').requestSubmit(); }
});
$('#helpdesk .clip input').onchange = async event => {
  for (const file of event.target.files) {
    const data = await new Promise(done => { const r = new FileReader(); r.onload = () => done(String(r.result).split(',')[1] || ''); r.readAsDataURL(file); });
    const saved = await wrote('/api/attach', {name: file.name, data});
    if (saved) { DOCK.files.push(saved.path); }
  }
  event.target.value = '';
  fill($('#helpdesk .files'), DOCK.files.map(file => h('span', {class: 'chip'}, file.split('/').pop())));
};
$('#dockTab').onclick = () => dockState('open');
$('#dockTab').onkeydown = event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); dockState('open'); } };
$('#helpdesk .min').onclick = () => dockState('resting');
$('#helpdesk .big').onclick = () => dockState($('#dock').className === 'open big' ? 'open' : 'open big');
document.addEventListener('pointermove', event => {  // near the sliver it lifts enough to click; away, it settles back
  const dock = $('#dock');
  if (dock.className.startsWith('open')) return;
  const box = $('#dockTab').getBoundingClientRect();
  const away = Math.hypot(Math.max(box.left - event.clientX, 0, event.clientX - box.right),
                          Math.max(box.top - event.clientY, 0, event.clientY - box.bottom));
  const state = away < 60 ? 'near' : 'resting';
  if (dock.className !== state) dock.className = state;
});
movable($('#qa'));
/* The messages of a node, VIEW-030: what agents say to the user there. A question waits for an answer and a note
 * waits to be read. */
const Q = {open: []};
const nodeOf = record => record.node_kind === 'element' ? record.node_id : 'p:' + record.node_id;
const targetOf = id => id.startsWith('p:') ? `join:${id.slice(2)}` : `element:${id}`;
const calledOf = id => (G ? G.graphData().nodes.find(node => node.id === id) : null)?.name
  || (S.elements.has(id) ? labelOf(S.elements.get(id).element) : null) || 'this node';
async function messagesOf(id) {
  const found = (await read('messages', {node: targetOf(id), limit: 0})).results;
  return {unread: found.filter(record => !record.closed), past: found.filter(record => record.closed), all: found};
}
/* The Messages button, VIEW-021: at the top of the page while anything waits for the user, with the count; a click
 * flies to the node of the oldest and opens its unread messages. */
async function renderMessages() {
  try {
    Q.open = noMetaform() ? [] : (await read('messages', {open: true, limit: 0})).results;
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
  if (F.id) await show(F.id, F.which, true);
}
/* The menu of a node, opened by a right-click in either view. Each entry says how many it holds, and one that holds
 * none cannot be chosen. It is where further acts on a node are added. */
async function menu(id, x = null, y = null) {
  let found = {unread: [], past: []}, note = null, tickets = [];
  try { found = await messagesOf(id); note = await noteOf(id); tickets = await ticketsOf(id); }
  catch (error) { toast(error.message); }
  const box = $('#menu');
  const entry = (which, text, count) => h('button', {class: which, disabled: !count, role: 'menuitem',
    onclick: () => { box.hidden = true; show(id, which); }}, text + ' ', h('b', {}, String(count)));
  const kept = networkOf(id).own.length;  // the memories kept at the node, VIEW-031
  fill(box, entry('unread', 'Unread messages', found.unread.length), entry('past', 'Past messages', found.past.length),
    h('button', {class: 'memories', disabled: !kept, role: 'menuitem', onclick: () => { box.hidden = true; memories(id); }},
      'Memories ', h('b', {}, String(kept))),
    h('button', {class: 'notes', role: 'menuitem', onclick: () => { box.hidden = true; notesAt(id); }}, 'Notes ',
      h('b', {}, note ? '1' : '0')),
    h('button', {class: 'history', disabled: !tickets.length, role: 'menuitem',
      onclick: () => { box.hidden = true; history(id); }}, 'Work history ', h('b', {}, String(tickets.length))),
    h('button', {class: 'chat', role: 'menuitem', onclick: () => { box.hidden = true; talkAbout(nodeTalk(id), calledOf(id) || 'this node'); }},
      'Chat about this'),
    h('button', {class: 'task', role: 'menuitem', onclick: () => { box.hidden = true; giveWork(id); }}, 'Add Task'),
    h('button', {class: 'element', role: 'menuitem', onclick: () => { box.hidden = true; addElement(id); }}, 'Add Element'),
    h('button', {class: 'agent', disabled: !tickets.some(waiting), role: 'menuitem', onclick: () => { box.hidden = true;
      startWindow(`Start an agent · ${calledOf(id)}`, tickets.filter(waiting)); }}, 'Start agent ',
      h('b', {}, String(tickets.filter(waiting).length))));
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
/* The board, VIEW-037: the project's tickets as a classic kanban board, one column for each place a ticket can be,
 * a card for each ticket. A card dragged to a column moves its ticket there and to the place it was dropped. */
const B = {tickets: [], off: new Set()};
const KINDS = ['missing', 'broken', 'flawed', 'enhancement', 'exclude'];
const BOARD = [['backlog', 'Backlog'], ['todo', 'To do'], ['doing', 'Doing'], ['done', 'Done']];
/* What a record's condition says about the part it is at, MAP-046: the condition belongs to the element or join, not
   to the ticket; the ticket is the work on it. A record with no condition is a plain task. */
const CONDITION_WORDS = {missing: 'not built yet', broken: 'broken', flawed: 'works, not right',
  enhancement: 'works, could be better', exclude: 'outside the artifact', 'in-progress': 'being built', fixing: 'being fixed'};
function conditionLabel(ticket, extra = '') {
  const condition = ticket.condition;
  const words = condition ? CONDITION_WORDS[condition] || condition : 'task';
  const title = condition ? `${ticketPart(ticket)} is ${words} (${condition}): this ticket is the work on it.`
    : `A task at ${ticketPart(ticket)}, with no condition recorded on the part.`;
  return h('span', {class: `kind kind-${condition || 'none'}${extra}`, title}, words);
}
const dated = text => { const d = new Date(text || ''); return isNaN(d) ? '' : d.toLocaleString(); };
const ago = text => {
  const seconds = Math.max(0, (Date.now() - Date.parse(text || '')) / 1000);
  return !isFinite(seconds) ? '' : seconds < 60 ? 'now' : seconds < 3600 ? `${Math.floor(seconds / 60)}m`
    : seconds < 86400 ? `${Math.floor(seconds / 3600)}h` : `${Math.floor(seconds / 86400)}d`;
};
const partAt = address => [...S.elements.values()].map(entry => entry.element).find(element => element.address === address);
function nodeChip(target, role) {
  const element = target.address ? partAt(target.address) : null;
  const key = target.kind === 'join' ? 'p:' + target.id : element?.id || target.id;
  const end = address => (address ? partAt(address) : null) ? named(partAt(address)) : address;
  const name = element ? named(element) : target.kind === 'join'
    ? joinOf('p:' + target.id)?.name || (target.ends?.[0] ? `${end(target.ends[0])} → ${end(target.ends[1])}` : 'a join')
    : target.address || target.id;
  return h('button', {class: `node ${role}`, title: `${role === 'assigned' ? 'Assigned' : 'For reference'}: ${target.address || target.id}`,
    onclick: event => { event.stopPropagation(); select(key, true); }}, name);
}
/* References in what the person reads, VIEW-042: a spec record's code, a ticket's or a message's id or its start, and
 * a path in the project. Each is drawn as plain text; once the server says what it stands for it becomes a link that
 * opens it in place, so an unknown code stays plain. */
const REF = /\b(?:[A-Z]{2,6}-\d{3}|D\d{2,4}|[0-9a-f]{8,32}|(?:[\w.-]+\/)+[\w.-]+\.\w{1,6})\b/g;
function linked(text) {
  text = String(text ?? '');
  const parts = [];
  let at = 0;
  for (const found of text.matchAll(REF)) {
    parts.push(text.slice(at, found.index), h('span', {class: 'ref', 'data-ref': found[0]}, found[0]));
    at = found.index + found[0].length;
  }
  parts.push(text.slice(at));
  return parts;
}
const LOOKED = new Map();  // project and reference → what it stands for, or null
const looked = ref => {
  const key = `${S.project}\n${ref}`;
  if (!LOOKED.has(key)) LOOKED.set(key, read('lookup', {ref}).then(found => (found.kind ? found : null)).catch(() => null));
  return LOOKED.get(key);
};
new MutationObserver(() => {
  for (const span of document.querySelectorAll('span.ref:not([data-looked])')) {
    span.dataset.looked = '1';
    looked(span.dataset.ref).then(found => {
      if (!found) return;
      span.classList.add('ref-link');
      Object.assign(span, {tabIndex: 0, title: found.title || span.dataset.ref});
      span.setAttribute('role', 'button');
    });
  }
}).observe(document.body, {childList: true, subtree: true});
const POP = h('div', {id: 'refPop', role: 'dialog', 'aria-label': 'What it refers to', hidden: true});
document.body.append(POP);
async function popRef(span, pinned) {
  const found = await looked(span.dataset.ref);
  if (!found) return;
  const kind = {spec: 'Specification', ticket: 'Ticket', message: found.type === 'question' ? 'Question' : 'Message', file: 'File'}[found.kind];
  const body = found.kind === 'spec' ? [h('h4', {}, found.title), h('p', {class: 'text'}, ...linked(found.text)), h('small', {}, found.file)]
    : found.kind === 'ticket' ? [h('h4', {}, ...linked(found.task || found.note || found.id)),
      h('p', {class: 'pills'}, h('span', {class: 'pill'}, found.condition || 'unsorted'),
        h('span', {class: 'pill'}, COLUMN_NAMES[found.column] || found.column), found.done ? h('span', {class: 'pill'}, 'done') : null),
      found.task && found.note ? h('p', {class: 'text'}, ...linked(found.note)) : null,
      found.resolution ? h('p', {class: 'text'}, h('b', {}, 'Resolved: '), ...linked(found.resolution)) : null,
      chatButton({id: found.id}, `ticket ${found.id.slice(0, 8)}`)]
    : found.kind === 'message' ? [h('p', {class: 'text'}, ...linked(found.text)),
      found.choices.length ? h('ol', {}, found.choices.map(choice => h('li', {}, choice))) : null,
      found.answer ? h('p', {}, h('b', {}, 'Answer: '), found.answer) : null,
      found.type === 'question' ? chatButton({question: found.id}, 'the question') : chatButton({node: found.address || ''}, 'its node'),
      found.type === 'question' && !found.closed ? h('button', {class: 'help-answer', onclick: async event => {
        event.target.disabled = true;
        if (await wrote('/api/recommend', {id: found.id})) toast('Three agents are reading the question; their help shows on it.');
        else event.target.disabled = false;
      }}, 'Help me answer') : null]
    : [h('h4', {}, found.title), h('pre', {class: 'text'}, found.text)];
  fill(POP, h('div', {class: 'eyebrow'}, kind, h('button', {class: 'close', 'aria-label': 'Close', onclick: () => { POP.hidden = true; }}, '×')), ...body);
  POP.pinned = pinned;
  POP.hidden = false;
  const box = span.getBoundingClientRect(), size = POP.getBoundingClientRect();
  POP.style.left = Math.max(8, Math.min(box.left, innerWidth - size.width - 8)) + 'px';
  POP.style.top = (box.bottom + size.height + 8 < innerHeight ? box.bottom + 6 : Math.max(8, box.top - size.height - 6)) + 'px';
}
document.addEventListener('click', event => {
  const span = event.target.closest?.('.ref-link');
  if (span) { event.preventDefault(); event.stopPropagation(); popRef(span, true); return; }
  if (!POP.hidden && !POP.contains(event.target)) POP.hidden = true;
}, true);
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && !POP.hidden) POP.hidden = true;
  if ((event.key === 'Enter' || event.key === ' ') && event.target.classList?.contains('ref-link')) { event.preventDefault(); popRef(event.target, true); }
});
if (matchMedia('(hover: hover)').matches) {  // on a desktop, resting the pointer on a reference shows it too
  let resting = null;
  document.addEventListener('mouseover', event => {
    const span = event.target.closest?.('.ref-link');
    clearTimeout(resting);
    if (span) resting = setTimeout(() => { if (POP.hidden || !POP.pinned) popRef(span, false); }, 350);
    else if (!POP.pinned && !POP.hidden && !POP.contains(event.target)) POP.hidden = true;
  });
}
function taskWords(text) {  // a node named inline, [[name|address]], shown as its name
  const parts = [], pattern = /\[\[([^|\]]+)\|([^\]]+)\]\]/g;
  let at = 0;
  for (const found of text.matchAll(pattern)) {
    parts.push(...linked(text.slice(at, found.index)), h('span', {class: 'inline', title: found[2]}, found[1]));
    at = found.index + found[0].length;
  }
  parts.push(...linked(text.slice(at)));
  return parts;
}
/* The agent a ticket prefers by default: Claude for front-end and GUI work, Codex for back-end and system work, as
 * dispatch chooses it; the person can choose another on the card at any time. */
const FRONTEND_WORDS = new Set(['gui', 'web', 'page', 'viewer', 'view', 'board', 'ui', 'frontend']);
const defaultAgent = address => (address || '').split('.').some(word => FRONTEND_WORDS.has(word)) ? 'claude' : 'codex';
const TICKET_AGENTS = [['claude', 'Claude Code'], ['codex', 'Codex'], ['gemini', 'Gemini CLI']];
const eligibleAgents = ticket => Array.isArray(ticket?.map?.eligible) ? ticket.map.eligible : [];
const allowsAgent = (ticket, agent) => !eligibleAgents(ticket).length || eligibleAgents(ticket).includes(agent);
function eligibilityPicker(agents, save) {
  let chosen = [...agents];
  const summary = h('summary', {}), options = h('div', {class: 'choices'});
  const box = h('details', {class: 'eligible', onclick: event => event.stopPropagation()}, summary, options);
  const names = [...new Set([...TICKET_AGENTS.map(([name]) => name), ...chosen])];
  const paint = () => {
    summary.textContent = 'Eligible agents: ' + (chosen.length ? chosen.map(agentName).join(', ') : 'Any agent');
    for (const input of options.querySelectorAll('input')) input.checked = input.classList.contains('any')
      ? !chosen.length : chosen.includes(input.dataset.agent);
  };
  const change = async event => {
    const before = [...chosen], input = event.target;
    chosen = input.classList.contains('any') ? [] : input.checked
      ? [...new Set([...chosen, input.dataset.agent])] : chosen.filter(name => name !== input.dataset.agent);
    paint();
    for (const control of options.querySelectorAll('input')) control.disabled = true;
    try { if (await save([...chosen]) === false) { chosen = before; paint(); } }
    finally { for (const control of options.querySelectorAll('input')) control.disabled = false; }
  };
  options.append(h('label', {}, h('input', {type: 'checkbox', class: 'any', onchange: change}), 'Any agent'),
    ...names.map(name => h('label', {}, h('input', {type: 'checkbox', 'data-agent': name, onchange: change}), agentName(name))));
  paint();
  return box;
}
const FIVE_AGENTS = ['jelly', 'gearling', 'kite', 'moth', 'drone'];  // five agents at work at most
function ticketControls(ticket) {
  const kept = ticket.map || {};
  const change = async (fields, control) => {
    control.disabled = true;
    try { if (await wrote('/api/ticket', {work_id: ticket.id, ...fields})) await renderBoard(); }
    finally { control.disabled = false; }
  };
  const chosen = kept.agent || defaultAgent(ticket.address);
  const glyphs = kept.glyph && !FIVE_AGENTS.includes(kept.glyph) ? [...FIVE_AGENTS, kept.glyph] : FIVE_AGENTS;
  return h('div', {class: 'ticket-controls', onclick: event => event.stopPropagation()},
    h('label', {title: 'The agent this ticket prefers; change it any time, even while one works on it'}, 'Agent ',
      h('select', {class: 'agent', onchange: event => change({agent: event.target.value}, event.target)},
        TICKET_AGENTS.map(([value, label]) => h('option', {value, selected: value === chosen}, label)))),
    eligibilityPicker(eligibleAgents(ticket), async agents => {
      if (!await wrote('/api/eligible', {work_id: ticket.id, agents})) return false;
      await renderBoard();
      return true;
    }),
    h('label', {title: 'Which agent works this ticket: the tickets with one glyph are one agent\'s, done one at a time'}, 'Glyph ',
      h('select', {class: 'glyph-pick', onchange: event => change({glyph: event.target.value}, event.target)},
        h('option', {value: '', selected: !kept.glyph}, 'any'),
        glyphs.map(glyph => h('option', {value: glyph, selected: glyph === kept.glyph}, glyph)))),
    ticket.taken && !ticket.done ? h('button', {class: 'recall', title: 'Recall the agent working this ticket; the ticket goes back on the board',
      onclick: async event => {
        event.target.disabled = true;
        if (await wrote('/api/dispatch-stop', {work_id: ticket.id})) await renderBoard(); else event.target.disabled = false;
      }}, 'Recall agent') : null,
    ticket.done ? null : h('button', {class: kept.hold ? 'hold on' : 'hold',
      title: kept.hold ? 'Release it: agents and automatic starts see it again' : 'Hold it: hidden from agents, automatic starts and consensus mode',
      onclick: event => change({hold: !kept.hold}, event.target)}, kept.hold ? 'Release hold' : 'Hold'));
}
function card(ticket, place, total) {
  const steps = ticket.steps || 0, filed = ticket.steps_done || 0;
  const move = async position => {
    if (await wrote('/api/move', {work_id: ticket.id, column: columnOf(ticket), position})) await renderBoard();
  };
  // its agent's glyph, VIEW-040: its own, or while its agent is at work the one its figure is drawn as
  const glyph = ownGlyph(ticket) || ROAM.figures.get(ticket.id)?.glyph;
  const box = h('div', {class: 'card', draggable: 'true', 'data-id': ticket.id, 'data-kind': ticket.condition || 'none',
    onclick: () => { const element = partAt(ticket.address); if (element) { select(element.id, true); history(element.id); } }},
    h('div', {class: 'top'}, glyph ? h('img', {class: 'glyph', src: `/page/agent-glyphs/${glyph}.svg`, alt: glyph,
      title: `Agent ${glyph}: the tickets with this glyph are one agent's, done one at a time`}) : null,
      conditionLabel(ticket),
      ticket.taken_by ? h('span', {class: 'by'}, ticket.taken_by) : null,
      h('span', {class: 'age', title: `${ticket.done ? 'Done' : ticket.taken ? 'Taken' : 'Opened'} ${dated(ticket.done || ticket.taken || ticket.created)}`},
        ago(ticket.done || ticket.taken || ticket.created))),
    h('div', {class: 'text'}, ...taskWords(ticket.task || ticket.note || '')),
    h('div', {class: 'nodes'}, nodeChip({kind: ticket.node_kind, id: ticket.node_id, address: ticket.address,
      ends: [ticket.receiver_address, ticket.provider_address]}, 'assigned'),
      ...(ticket.links || []).map(link => nodeChip(link, 'ref'))),
    steps || filed ? h('div', {class: 'progress'}, h('span', {style: {width: `${Math.min(100, 100 * filed / Math.max(steps, filed, 1))}%`}}),
      h('small', {}, `${filed}/${steps || filed}`)) : null,
    ticket.resolution ? h('div', {class: 'resolution'}, ...linked(ticket.resolution)) : null,
    h('div', {class: 'priority', role: 'group', 'aria-label': 'Card order'},
      [['Top', 'Move to top', 0, place === 0], ['Up', 'Move up', place - 1, place === 0],
        ['Down', 'Move down', place + 1, place === total - 1]].map(([text, label, position, disabled]) =>
        h('button', {title: label, 'aria-label': label, disabled, onclick: event => {
          event.stopPropagation(); move(position);
        }}, text))),
    ticketControls(ticket),
    waiting(ticket) ? h('button', {class: 'start', title: 'Start an agent on this ticket', onclick: event => {
      event.stopPropagation(); startWindow(`Start an agent · ${ticketPart(ticket)}`, [ticket]); }}, 'Start agent') : null);
  if (ticket.map?.hold) box.classList.add('on-hold');
  box.addEventListener('dragstart', event => { event.dataTransfer.setData('text/plain', ticket.id); box.classList.add('dragging'); });
  box.addEventListener('dragend', () => box.classList.remove('dragging'));
  return box;
}
function shownOnBoard(box) {
  const words = $('#board .search').value.trim().toLowerCase();
  box.hidden = B.off.has(box.dataset.kind) || Boolean(words && !box.textContent.toLowerCase().includes(words));
}
function drawBoard() {
  const order = (one, two) => (one.position ?? 1e9) - (two.position ?? 1e9) || B.tickets.indexOf(one) - B.tickets.indexOf(two);
  fill($('#board .kinds'), [...KINDS, 'none'].map(kind => h('button', {class: `kindtoggle${B.off.has(kind) ? ' off' : ''}`,
    'data-kind': kind, 'aria-pressed': String(!B.off.has(kind)),
    onclick: () => { B.off.has(kind) ? B.off.delete(kind) : B.off.add(kind); drawBoard(); }}, kind === 'none' ? 'unsorted' : kind)));
  fill($('#board .columns'), BOARD.map(([column, title]) => {
    const tickets = B.tickets.filter(ticket => columnOf(ticket) === column).sort(order);
    const cards = h('div', {class: 'cards'}, tickets.map((ticket, place) => card(ticket, place, tickets.length)));
    cards.addEventListener('dragover', event => { event.preventDefault(); cards.classList.add('over'); });
    cards.addEventListener('dragleave', () => cards.classList.remove('over'));
    cards.addEventListener('drop', async event => {
      event.preventDefault();
      cards.classList.remove('over');
      const id = event.dataTransfer.getData('text/plain');
      const others = [...cards.querySelectorAll('.card')].filter(box => box.dataset.id !== id);
      const after = others.findIndex(box => { const at = box.getBoundingClientRect(); return event.clientY < at.top + at.height / 2; });
      if (await wrote('/api/move', {work_id: id, column, position: after < 0 ? others.length : after, by: 'user'})) await renderBoard();
    });
    return h('div', {class: 'column', 'data-column': column},
      h('div', {class: 'head'}, h('span', {}, title), h('span', {class: 'tally'}, String(tickets.length))), cards);
  }));
  for (const box of $('#board').querySelectorAll('.card')) shownOnBoard(box);
  $('#board .start-all').disabled = D.starting || !B.tickets.some(waiting);
}
async function renderBoard() {
  if ($('#board').hidden || !S.project) return;
  const project = S.project, metaform = S.base;  // the agents are read on dispatch events only, VIEW-018
  try { B.tickets = (await read('work', {limit: 0})).results || []; } catch (error) { toast(error.message); return; }
  if (S.project !== project || S.base !== metaform) return;
  drawBoard();
}
$('#boardBtn').onclick = async () => { $('#board').hidden = false; await renderBoard(); $('#board .search').focus(); };
$('#board .close').onclick = () => { $('#board').hidden = true; };
$('#board .start-all').onclick = async () => {
  await renderBoard();
  const tickets = B.tickets.filter(waiting).sort((one, two) =>
    Number(Boolean(one.held)) - Number(Boolean(two.held)) || (one.position ?? 1e9) - (two.position ?? 1e9));
  startWindow('Start all agents', tickets, true);
};
$('#board .search').oninput = () => { for (const box of $('#board').querySelectorAll('.card')) shownOnBoard(box); };
$('#board .add').onclick = () => {
  const first = S.selected && S.elements.has(S.selected) ? S.selected : [...S.elements.keys()][0];
  if (first) giveWork(first); else toast('Add a card once the project has a map.');
};
/* A node's work history, VIEW-036: every ticket on it, open and done, newest first, in the floating window. */
const COLUMN_NAMES = {backlog: 'backlog', todo: 'to do', doing: 'doing', done: 'done'};
const columnOf = ticket => ticket.done ? 'done' : ticket.taken ? 'doing' : ticket.held ? 'backlog' : 'todo';
const when = text => (text || '').replace('T', ' ').replace('Z', '');
async function ticketsOf(id) { return (await read('work', {node: targetOf(id), limit: 0})).results || []; }
async function history(id) {
  let tickets, dispatched = [];
  try { tickets = await ticketsOf(id); } catch (error) { toast(error.message); return; }
  try { dispatched = (await read('dispatch-sessions')).sessions || []; } catch (error) { toast(error.message); }
  Object.assign(F, {id: null, which: null, ids: new Set(), drawn: new Map()});
  $('#float .title').textContent = `Work history · ${calledOf(id)}`;
  fill($('#float .body'), tickets.length ? [...tickets].reverse().map(ticket => h('div', {class: 'ticket'},
    h('div', {class: 'head'}, conditionLabel(ticket),
      h('span', {class: 'column'}, COLUMN_NAMES[columnOf(ticket)]),
      ticket.taken_by ? h('span', {class: 'by'}, ticket.taken_by) : null,
      h('span', {class: 'age', title: `${ticket.done ? 'Done' : ticket.taken ? 'Taken' : 'Opened'} ${dated(ticket.done || ticket.taken || ticket.created)}`},
        ago(ticket.done || ticket.taken || ticket.created))),
    ticket.task ? h('p', {class: 'task'}, ...linked(ticket.task)) : null,
    ticket.note ? h('p', {class: 'note'}, ...linked(ticket.note)) : null,
    h('div', {class: 'when'}, `opened ${when(ticket.created)}`, ticket.taken ? ` · taken ${when(ticket.taken)}` : '',
      ticket.done ? ` · done ${when(ticket.done)}` : ''),
    (ticket.said || []).length ? h('ol', {class: 'steps'}, ticket.said.map(step => h('li', {}, ...linked(step.said)))) : null,
    ticket.resolution ? h('p', {class: 'resolution'}, ...linked(ticket.resolution)) : null,
    chatButton({id: ticket.id}, ticketPart(ticket)),
    // each agent sent to work it, and its session's log, VIEW-036 and VIEW-039
    ...dispatched.filter(one => one.work_id === ticket.id).map(one => h('div', {class: 'dispatch'},
      h('span', {}, `${agentName(one.agent)} sent ${when(one.started)} · `
        + (one.state === 'running' ? 'working' : `ended${one.how ? `, ${one.how}` : ''}`)),
      chatButton(one.state === 'running' ? {id: one.work_id} : {session: `${one.work_id}:${one.session_id}`},
        `${agentName(one.agent)} on ${ticketPart(ticket)}`),
      h('button', {class: 'log', title: "The session's whole thread", onclick: async () => {
        await renderAgents();
        agentAt(one.work_id, one.session_id);
      }}, 'Open log')))))
    : h('p', {class: 'empty'}, 'No work here yet.'));
  $('#float').hidden = false;
}
/* The floating window, VIEW-030. It shows the messages it was opened with, each as it is now, so a question answered
 * in it shows its answer and a note read in it stays in sight until the window is closed. Shown again as the map
 * changes, a message that has not changed keeps the part of the window drawn for it, with whatever is typed there. */
const F = {id: null, which: null, ids: new Set(), drawn: new Map(), base: null};
async function show(id, which, again = false) {
  // Its messages are those of the metaform it was opened in; while another is shown it is left as it is.
  if (again && F.base !== S.base) return;
  let found;
  try { found = await messagesOf(id); } catch (error) { toast(error.message); return; }
  if (!again) Object.assign(F, {id, which, ids: new Set(found[which].map(record => record.id)), drawn: new Map(),
    base: S.base});
  if (F.id !== id) return;
  const shown = found.all.filter(record => F.ids.has(record.id));
  $('#float .title').textContent = `${which === 'unread' ? 'Unread' : 'Past'} messages · ${calledOf(id)}`;
  const drawn = new Map(shown.map(record => {
    const state = JSON.stringify([record.closed, record.answer, record.text, record.suggestions]), had = F.drawn.get(record.id);
    return [record.id, had && had.state === state ? had : {state, node: h('div', {},
      h('div', {class: 'when'}, record.created.replace('T', ' ').replace('Z', '')),
      record.kind === 'question' ? asked(record, F.base) : noted(record))}];
  }));
  F.drawn = drawn;
  keepFill($('#float .body'), shown.length ? [...drawn.values()].map(one => one.node) : [h('p', {class: 'empty'}, 'No messages here.')]);
  $('#float').hidden = false;
  for (const record of shown) if (record.kind === 'message' && !record.closed) wrote('/api/read', {id: record.id});
}
function noted(record) {
  return h('div', {class: 'item work'},
    h('div', {class: 'pills'}, workPill('message'), h('span', {class: 'pill'}, record.closed ? 'read' : 'unread'),
      record.by ? h('span', {class: 'pill'}, record.by) : null),
    h('p', {}, ...linked(record.text)));
}
async function wrote(path, given) {
  let response;
  try {
    response = await reach(path, {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({project: S.project, base: S.base, ...given})}, 0);
  } catch (error) { toast(error.message); return null; }
  const body = await response.json().catch(() => ({error: 'The server did not answer with JSON.'}));
  if (!response.ok) toast(body.error || 'It was not written.');
  return response.ok ? body : null;
}
/* A floating window is moved by its title. */
function movable(box) {
  box.querySelector('.bar').addEventListener('pointerdown', event => {
    if (event.target.closest('button')) return;
    const from = box.getBoundingClientRect(), start = [event.clientX - from.left, event.clientY - from.top];
    const move = moved => {
      box.style.left = Math.max(0, Math.min(moved.clientX - start[0], innerWidth - 60)) + 'px';
      box.style.top = Math.max(0, Math.min(moved.clientY - start[1], innerHeight - 40)) + 'px';
    };
    const end = () => { removeEventListener('pointermove', move); removeEventListener('pointerup', end); };
    addEventListener('pointermove', move);
    addEventListener('pointerup', end);
    event.preventDefault();
  });
}
/* ---------- agents dispatched on tickets, VIEW-039 ----------
 * The dispatch module starts, messages and stops an agent on a ticket, BASE-052; the page asks it to through three
 * writes, VIEW-011. What an agent does is read from the dispatch layer at its ticket's node with each map change. */
const AGENT_NAMES = {claude: 'Claude Code', codex: 'Codex', gemini: 'Gemini CLI'};  // as the dispatch module names them
const DOING = {agent_message_chunk: 'said', agent_thought_chunk: 'thought', user_message_chunk: 'was told',
  tool_call: 'ran', tool_call_update: 'ran', plan: 'plan', turn: 'turn', failed: 'failed', person: 'you', approved: 'approved'};
/* How each line of an agent's thread reads: what it says, what it thinks, what it runs, and what the person said. */
const THREAD = {agent_message_chunk: 'said', agent_thought_chunk: 'thought', user_message_chunk: 'told', tool_call: 'tool',
  tool_call_update: 'tool', plan: 'plan', turn: 'turn', failed: 'failed', person: 'you'};
const D = {sessions: [], notes: [], work: null, session: null, drawn: new Map(), starting: false, chat: null};
const AUTO = {value: false, agents: null};
async function readAutostart() {
  const project = S.project, control = $('#autostartAgents');
  control.disabled = true;
  try {
    const found = await read('dispatch-autostart');
    if (S.project !== project) return;
    Object.assign(AUTO, found);
    control.checked = found.value;
    if (found.agent) $('#dispatch select.agent').value = found.agent;
    control.disabled = found.available === false;
  } catch (error) { if (S.project === project) toast(error.message); }
}
$('#autostartAgents').onchange = async () => {
  const project = S.project, control = $('#autostartAgents');
  control.disabled = true;
  try {
    const saved = await wrote('/api/dispatch-autostart', {value: control.checked, agent: $('#dispatch select.agent').value});
    if (S.project !== project) return;
    if (saved) Object.assign(AUTO, saved);
    control.checked = AUTO.value;
  } catch (error) { if (S.project === project) { control.checked = AUTO.value; toast(error.message); } }
  finally { if (S.project === project) control.disabled = false; }
};
async function questionChat(record, metaform) {
  const project = S.project;
  const found = await wrote('/api/dispatch-chat', {id: record.id, metaform, agent: $('#dispatch select.agent').value});
  if (!found || S.project !== project || S.base !== metaform) return;
  if (found.conversation) DOCK.mine = found.work_id;  // Dismiss stops a conversation agent, never ticket work
  openHelpdesk(found.work_id, `${agentName(found.agent)} on the question`,
    found.state === 'running' ? 'It answers when its current step ends.' : STANDBY, found.session_id);
}
const waiting = ticket => !ticket.done && !ticket.taken && ticket.condition !== 'exclude'
  && !D.sessions.some(one => one.state === 'running'
    && (one.work_id === ticket.id || (ownGlyph(ticket) && ownGlyph(ticketOf(one.work_id)) === ownGlyph(ticket))));
const ticketOf = workId => (S.tickets || []).find(ticket => ticket.id === workId);
function ticketPart(ticket) {
  const element = ticket?.address ? partAt(ticket.address) : null;
  return element ? named(element) : ticket ? calledOf(ticketNode(ticket)) : 'its ticket';
}
// a ticket's own glyph, VIEW-040: the map module keeps it and the work read shows it under `map`, BASE-035
const ownGlyph = ticket => ticket?.map?.glyph;
// the character its 3D figure is, VIEW-035: the ticket's own glyph when it is assigned one, VIEW-040
const glyphFor = workId => drawGlyph(workId, ownGlyph(ticketOf(workId)));
const glyphOf = workId => `/page/agent-glyphs/${glyphFor(workId)}.svg`;
const agentName = agent => AGENT_NAMES[agent] || agent || 'An agent';
async function startAgent(workId, agent) {
  if (!await wrote('/api/dispatch-start', {work_id: workId, agent})) return false;
  toast(`${agentName(agent)} is starting on the ticket. It shows under Agent deployed while it is working.`);
  return true;
}
/* The window an agent is started from: the tickets, and the agent chosen once for the window. */
function startWindow(title, tickets, all = false) {
  if (D.starting) return;
  $('#dispatch .title').textContent = title;
  const startAll = $('#dispatch .start-all');
  const candidates = tickets;
  startAll.hidden = !all;
  startAll.disabled = !tickets.length;
  startAll.onclick = async () => {
    if (D.starting) return;
    D.starting = true;
    const agent = $('#dispatch select.agent').value;
    const buttons = [...$('#dispatch .tickets').querySelectorAll('button.start')];
    const pending = tickets.filter((ticket, i) => !buttons[i].disabled);
    startAll.disabled = true;
    $('#dispatch select.agent').disabled = true;
    for (const button of buttons) button.disabled = true;
    drawBoard();
    let started = 0;
    for (const ticket of pending) {
      const button = buttons[tickets.indexOf(ticket)];
      try {
        if (await startAgent(ticket.id, agent)) { started++; button.textContent = 'Starting'; }
        else { button.disabled = false; button.textContent = 'Retry'; }
      } catch (error) { toast(error.message); button.disabled = false; button.textContent = 'Retry'; }
    }
    $('#dispatch select.agent').disabled = false;
    D.starting = false;
    startAll.disabled = !buttons.some(button => !button.disabled);
    if (started === pending.length) $('#dispatch').hidden = true;
    toast(`${started} ${agentName(agent)} agent${started === 1 ? '' : 's'} starting.`
      + (started < pending.length ? ` ${pending.length - started} could not start; retry their tickets.` : ''));
    await renderBoard();
  };
  $('#dispatch select.agent').disabled = false;
  const draw = () => {
    const agent = $('#dispatch select.agent').value, glyphs = new Set();
    tickets = all ? candidates.filter(ticket => {
      if (!allowsAgent(ticket, agent)) return false;
      const glyph = ownGlyph(ticket);
      if (glyph && glyphs.has(glyph)) return false;
      if (glyph) glyphs.add(glyph);
      return true;
    }) : candidates;
    startAll.disabled = !tickets.length;
    fill($('#dispatch .tickets'), tickets.map(ticket => h('div', {class: 'ticket', 'data-id': ticket.id},
    conditionLabel(ticket),
    h('button', {class: 'start', disabled: !allowsAgent(ticket, agent),
      title: allowsAgent(ticket, agent) ? 'Start the agent chosen above on this ticket'
        : `Eligible agents: ${eligibleAgents(ticket).map(agentName).join(', ')}`, onclick: async event => {
      const agent = $('#dispatch select.agent').value;
      event.target.disabled = true;
      try {
        if (await startAgent(ticket.id, agent)) { $('#dispatch').hidden = true; await renderBoard(); }
        else event.target.disabled = false;
      } catch (error) { toast(error.message); event.target.disabled = false; }
    }}, 'Start'),
    h('div', {class: 'task'}, ...taskWords(ticket.task || ticket.note || '')))));
  };
  $('#dispatch select.agent').onchange = draw;
  draw();
  $('#dispatch').hidden = false;
}
$('#dispatch .close').onclick = () => { $('#dispatch').hidden = true; };
movable($('#dispatch'));
/* The agents key: each agent working in the project now, with its flat icon and in words what it is; a click opens its
 * session's thread. An ended session leaves the key and the map; its log stays in the node's work history, VIEW-036.
 * Sessions are the dispatch module's own tables, never the map. */
async function renderAgents() {
  const project = S.project, metaform = S.base;
  let found = {sessions: []};
  if (!noMetaform()) {
    try { found = await read('dispatch-sessions', {thread: 'false'}); }  // the threads are read for the open window only
    catch (error) { toast(error.message); found = {sessions: D.sessions}; }  // a failed read keeps the agents drawn
  }
  if (S.project !== project || S.base !== metaform) return;  // the answer for a project the person has left
  D.sessions = found.sessions || [];
  if (D.chat) {
    const pending = D.chat;
    const session = D.sessions.find(one => one.work_id === pending.work && one.state === 'running'
      && (pending.session ? one.session_id === pending.session : !pending.known.has(one.session_id)));
    if (session) { D.chat = null; agentAt(session.work_id, session.session_id); }
  }
  if (!$('#board').hidden) drawBoard();
  // at work: a session whose runner says a turn is executing, the same ones the map's figures follow
  const working = D.sessions.filter(one => one.activity === 'working');
  // an entry drawn the same stays in place, so the one under the pointer is not swapped while it is clicked
  keyedFill($('#agents .list'), working.map(one => ({key: one.session_id,
    text: [one.work_id, one.agent, glyphOf(one.work_id), ticketPart(ticketOf(one.work_id))].join('\n'),
    make: () => h('div', {class: 'agent-row'}, h('button', {
      class: 'agent working', 'data-id': one.work_id, 'data-session': one.session_id,
      title: `${agentName(one.agent)} on work ${one.work_id}: working`,
      onclick: () => agentAt(one.work_id, one.session_id)},
      h('img', {src: glyphOf(one.work_id), alt: glyphFor(one.work_id)}), h('b', {}, agentName(one.agent)),
      h('small', {}, `on ${ticketPart(ticketOf(one.work_id))} · working`)),
      chatButton({id: one.work_id}, `${agentName(one.agent)} on ${ticketPart(ticketOf(one.work_id))}`))})));
  $('#agents').hidden = !working.length;
  figures(S.tickets || []);  // the map's figures follow the same sessions
  if (D.work) await drawAgent();
}
function agentAt(workId, sessionId = null) {
  D.session = sessionId;
  if (D.work !== workId) { $('#agent .say').value = ''; D.drawn = new Map(); }
  D.work = workId;
  $('#agent').hidden = false;
  drawAgent();
}
/* One agent's window: what its session wrote on the dispatch layer, in order, its open questions, answered as every
 * question is, VIEW-021, a message to send it, and Stop. The text being written is part of the page and is never
 * drawn again, so a map change keeps it, VIEW-018. */
async function drawAgent() {
  const work = D.work;
  const session = D.sessions.filter(one => one.work_id === work && (!D.session || one.session_id === D.session)).at(-1);
  const {agent, session_id: sessionId, state} = session || {};
  const ticket = ticketOf(work);
  $('#agent .icon').src = glyphOf(work);
  $('#agent .icon').alt = glyphFor(work);
  $('#agent .title').textContent = `${agentName(agent)} · ${ticketPart(ticket)}${state && state !== 'running' ? ' · ended' : ''}`;
  const task = ticket ? ticket.task || ticket.note || '' : '';
  if ($('#agent .task').textContent !== task) $('#agent .task').classList.remove('open');  // a new ticket starts short
  $('#agent .task').textContent = task;
  $('#agent .task').title = 'Click to show all of the task, and again to fold it';
  // A chat: newest at the bottom, kept in view while the person is reading the end of it, VIEW-039.
  const project = S.project, metaform = S.base;
  let notes = D.notes;
  try { notes = (await read('dispatch-sessions', {id: work})).lines || []; }
  catch (error) { toast(error.message); }
  if (D.work !== work || S.project !== project || S.base !== metaform) return;
  D.notes = notes;
  const thread = $('#agent .activity');
  const following = !thread.childElementCount || thread.scrollTop + thread.clientHeight >= thread.scrollHeight - 24;
  keyedFill(thread, D.notes.filter(line => line.work_id === work && (!sessionId || line.session_id === sessionId))
    .map(line => ({key: `${line.session_id}:${line.name ?? line.seq}`, text: `${line.kind}\n${line.text}`,
      make: () => h('li', {class: THREAD[line.kind] || 'note'},
        h('small', {}, DOING[line.kind] || line.kind || ''), ...linked(line.text))})));
  if (following) thread.scrollTop = thread.scrollHeight;
  let open = [];
  if (ticket && sessionId) {
    try { open = (await messagesOf(ticketNode(ticket))).unread.filter(record => record.kind === 'question' && record.by === `${agent} ${sessionId}`); }
    catch (error) { toast(error.message); }
  }
  if (D.work !== work) return;
  const drawn = new Map(open.map(record => [record.id, D.drawn.get(record.id) || asked(record)]));
  D.drawn = drawn;
  keepFill($('#agent .asked'), [...drawn.values()]);
  $('#agent .send').disabled = $('#agent .stop').disabled = state !== 'running';
}
// The task shows in three lines, so the conversation always has the window; a click unfolds it, within a third.
$('#agent .task').onclick = () => $('#agent .task').classList.toggle('open');
$('#agent .chat').onclick = () => {
  const session = D.sessions.filter(one => one.work_id === D.work && (!D.session || one.session_id === D.session)).at(-1);
  const label = `${agentName(session?.agent)} on ${ticketPart(ticketOf(D.work))}`;
  talkAbout(!session || session.state === 'running' ? {id: D.work} : {session: `${D.work}:${session.session_id}`}, label);
};
$('#agent .send').onclick = async () => {
  const text = $('#agent .say').value.trim();
  if (!text) { toast('A message says something.'); return; }
  $('#agent .send').disabled = true;
  if (await wrote('/api/dispatch-message', {work_id: D.work, text})) { $('#agent .say').value = ''; toast('Sent to the agent.'); }
  $('#agent .send').disabled = false;
};
$('#agent .say').addEventListener('keydown', event => {  // Enter sends, Shift+Enter starts a new line
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); $('#agent .send').click(); }
});
$('#agent .stop').onclick = async () => {
  $('#agent .stop').disabled = true;
  if (await wrote('/api/dispatch-stop', {work_id: D.work})) toast('The agent was stopped.');
  else $('#agent .stop').disabled = false;
};
$('#agent .close').onclick = () => { $('#agent').hidden = true; D.work = null; };
movable($('#agent'));
/* Giving work, VIEW-032: the task is written as a person writes, the nodes it concerns are linked to it, and a node
 * inserted into the text reads there as its proper noun and carries its address. */
const K = {nodes: [], chosen: null, at: null, generation: 0, project: null, base: null, eligible: []};
const partOf = address => [...S.elements.values()].map(entry => entry.element).find(element => element.address === address);
const named = element => labelOf(element);
function chip(element, remove = null) {
  return h('span', {'data-address': element.address, title: element.address, contenteditable: 'false'}, named(element),
    remove ? h('button', {title: 'Take it off this task', onclick: remove}, 'x') : null);
}
function linkedNodes() {
  fill($('#task .linked'), K.nodes.map((address, index) => chip(partOf(address),
    index ? () => { K.nodes = K.nodes.filter(one => one !== address); linkedNodes(); } : null)));
}
async function taskWorkflows() {
  const generation = ++K.generation, picker = $('#task .workflow'), project = S.project, metaform = S.base;
  const stale = () => generation !== K.generation || $('#task').hidden || project !== S.project || metaform !== S.base;
  picker.disabled = true;
  fill(picker, h('option', {value: ''}, 'Loading workflows…'));
  $('#task .workflow-entry').hidden = true;
  $('#task .workflow-call').value = '';
  if (!S.bases.some(map => map.active && map.id === metaform)) {
    fill(picker, h('option', {value: ''}, 'Choose the active map to run workflows'));
    return;
  }
  try {
    const found = await read('workflows');
    if (stale()) return;
    const calls = found.workflows.flatMap(workflow => workflow.logic.map(name =>
      h('option', {value: `${workflow.address}.${name}`}, `${workflow.name || workflow.address} · ${name}`)));
    fill(picker, h('option', {value: ''}, found.enabled ? (calls.length ? 'No workflow' : 'No stored workflows') : 'Workflows unavailable'), ...calls);
    picker.disabled = !calls.length;
  } catch (error) {
    if (stale()) return;
    fill(picker, h('option', {value: ''}, 'Workflows could not load'));
    toast(error.message);
  }
}
$('#task .workflow').onchange = () => {
  const chosen = $('#task .workflow').value;
  $('#task .workflow-entry').hidden = !chosen;
  $('#task .workflow-call').value = chosen ? `${chosen}()` : '';
};
function giveWork(id, text = '') {
  const element = S.elements.get(id)?.element;
  if (!element) { toast('Work is given at an element.'); return; }
  Object.assign(K, {nodes: [element.address], chosen: null, at: null, project: S.project, base: S.base, eligible: []});
  $('#task .condition').value = '';
  $('#task .backlog').checked = false;
  $('#task .start-agent').checked = false;
  $('#task select.agent').value = defaultAgent(element.address);
  fill($('#task .eligibility'), eligibilityPicker([], agents => { K.eligible = agents; }));
  $('#task .title').textContent = `Add Task · ${named(element)}`;
  $('#task .text').replaceChildren(...(text ? [text] : []));
  $('#task .browser input').value = '';
  linkedNodes();
  const parts = [...S.elements.values()].map(entry => entry.element).sort((one, two) => one.address < two.address ? -1 : 1);
  fill($('#task .rows'), parts.map(part => h('button', {'data-address': part.address, onclick: () => choose(part.address)},
    named(part), h('small', {}, part.address))));
  $('#task .insert').disabled = $('#task .link').disabled = true;
  $('#task').hidden = false;
  taskWorkflows();
  $('#task .text').focus();
  chart(parts);
}
/* A part is chosen in the list or in the chart, and is then chosen in both. */
function choose(address) {
  K.chosen = address;
  for (const one of $('#task').querySelectorAll('.rows [data-address], .chart g[data-address]')) {
    one.classList.toggle('chosen', one.dataset.address === address);
    if (one.dataset.address === address && one.closest('.rows')) one.scrollIntoView({block: 'nearest'});
  }
  $('#task .insert').disabled = $('#task .link').disabled = false;
}
/* The editor's own chart of the project, VIEW-032: the parts and their joins, looked around by dragging and by the
 * wheel, apart from the two maps of the page, which it does not move and which do not move it. */
const C = {generation: 0, cam: null, whole: null};
function camera(cam) {
  C.cam = cam;
  $('#task .chart svg')?.setAttribute('viewBox', `${cam.x} ${cam.y} ${cam.w} ${cam.h}`);
}
async function chart(parts) {
  const host = $('#task .chart'), generation = ++C.generation;
  const unable = text => fill(host, h('p', {class: 'empty', style: {padding: '12px'}}, text));
  if (!window.mermaid || !mermaidReady) return unable('The chart could not load.');
  if (parts.length > MAP2D) return unable(`The chart lays out at most ${MAP2D} parts.`);
  const keys = new Map(parts.map((part, index) => [part.id, `c${index}`]));
  const lines = ['flowchart TB', ...parts.map(part => `${keys.get(part.id)}["${plain2d(named(part))}"]`),
    ...S.joins.filter(join => keys.has(join.receiver)).flatMap(join => join.providers.filter(id => keys.has(id))
      .map(provider => `${keys.get(join.receiver)} --> ${keys.get(provider)}`))];
  let result;
  try { result = await window.mermaid.render(`pick${generation}`, lines.join('\n'), $('#draw')); }
  catch (error) { return unable('The chart could not be drawn.'); }
  if (generation !== C.generation) return;
  const svg = document.importNode(new DOMParser().parseFromString(result.svg, 'image/svg+xml').documentElement, true);
  svg.removeAttribute('style'); svg.removeAttribute('width'); svg.removeAttribute('height');
  host.replaceChildren(svg);
  for (const part of parts) {
    const group = svg.querySelector(`[id*="-flowchart-${keys.get(part.id)}-"]`);
    if (!group) continue;
    group.dataset.address = part.address;
    group.append(Object.assign(document.createElementNS(SVG, 'title'), {textContent: part.address}));
    group.addEventListener('click', event => { event.stopPropagation(); choose(part.address); });
  }
  const whole = svg.viewBox.baseVal;
  C.whole = {x: whole.x, y: whole.y, w: whole.width, h: whole.height};
  // It opens on the part the task is added at, at the size its names are written in, so they are read at once; the
  // whole of a project's chart in so small an area is boxes too small to read.
  const first = svg.querySelector(`g[data-address="${CSS.escape(K.nodes[0])}"]`), area = host.getBoundingClientRect();
  if (first && area.width) {
    const box = first.getBBox(), matrix = first.transform.baseVal.consolidate()?.matrix || new DOMMatrix();
    const middle = new DOMPoint(box.x + box.width / 2, box.y + box.height / 2).matrixTransform(matrix);
    camera({x: middle.x - area.width / 2, y: middle.y - area.height / 2, w: area.width, h: area.height});
  } else camera(C.whole);
  if (K.chosen) choose(K.chosen);
}
$('#task .whole').onclick = () => { if (C.whole) camera(C.whole); };
(() => {
  const host = $('#task .chart');
  let drag = null;
  host.addEventListener('pointerdown', event => { if (C.cam) drag = {x: event.clientX, y: event.clientY, cam: {...C.cam}, moving: false}; });
  host.addEventListener('pointermove', event => {
    if (!drag) return;
    if (!drag.moving) {  // captured only once it is a drag, so a click still reaches the part under it
      if (Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 4) return;
      drag.moving = true; host.setPointerCapture(event.pointerId);
    }
    const scale = C.cam.w / host.getBoundingClientRect().width;
    camera({...drag.cam, x: drag.cam.x - (event.clientX - drag.x) * scale, y: drag.cam.y - (event.clientY - drag.y) * scale});
  });
  host.addEventListener('pointerup', () => { drag = null; });
  host.addEventListener('wheel', event => {
    if (!C.cam) return;
    event.preventDefault();
    const by = event.deltaY > 0 ? 1.15 : 0.87, box = host.getBoundingClientRect(), cam = C.cam;
    const px = (event.clientX - box.left) / box.width, py = (event.clientY - box.top) / box.height;
    camera({x: cam.x + (cam.w - cam.w * by) * px, y: cam.y + (cam.h - cam.h * by) * py, w: cam.w * by, h: cam.h * by});
  }, {passive: false});
})();
$('#task .full').onclick = () => {
  const full = $('#task').classList.toggle('full');
  $('#task .full').textContent = full ? 'Window' : 'Full screen';
};
/* Where the cursor was in the text, kept as the text loses it to the browser's buttons. It is kept as a node and a
 * count into it and not as a range, since a range is moved to the start of a text the browser writes again, which
 * it does to a space typed at the end of a line. */
function keepCursor() {
  const chosen = getSelection();
  if (chosen.rangeCount && $('#task .text').contains(chosen.anchorNode)) {
    const range = chosen.getRangeAt(0);
    K.at = {node: range.endContainer, count: range.endOffset};
  }
}
// It is read at each change of the text and as the text is left: the browser tells of a moved cursor a moment after
// it moved, which can be after the person has gone on to the browser of the namespace.
document.addEventListener('selectionchange', keepCursor);
for (const kind of ['input', 'keyup', 'mouseup', 'blur']) $('#task .text').addEventListener(kind, keepCursor);
$('#task .browser input').oninput = event => {
  const wanted = event.target.value.trim().toLowerCase();
  for (const row of $('#task .rows').children) row.hidden = Boolean(wanted) && !row.textContent.toLowerCase().includes(wanted);
};
$('#task .insert').onclick = () => {
  const text = $('#task .text'), made = chip(partOf(K.chosen));
  if (K.at && text.contains(K.at.node)) {
    const at = document.createRange(), most = K.at.node.nodeType === Node.TEXT_NODE ? K.at.node.length : K.at.node.childNodes.length;
    at.setStart(K.at.node, Math.min(K.at.count, most));
    at.collapse(true);
    at.insertNode(made);
  } else text.append(made);
  // A text of no width after the name, for the cursor to stand in: the browser cannot put a cursor after a part
  // of the text that is not typed into when nothing follows it, and what is typed there is lost.
  const hold = document.createTextNode('\u200b');
  made.after(hold);
  const after = document.createRange();
  after.setStart(hold, 1);
  after.collapse(true);
  getSelection().removeAllRanges();
  getSelection().addRange(after);
  text.focus();
};
$('#task .link').onclick = () => { if (!K.nodes.includes(K.chosen)) { K.nodes.push(K.chosen); linkedNodes(); } };
/* The task as text: an inline node is written `[[name|address]]`, so an agent has the name and the address. */
const taskText = () => [...$('#task .text').childNodes].map(function told(node) {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent;
  if (node.dataset?.address) return `[[${node.textContent}|${node.dataset.address}]]`;
  return (node.tagName === 'DIV' || node.tagName === 'BR' ? '\n' : '') + [...node.childNodes].map(told).join('');
}).join('').replace(/\u200b/g, '').replace(/\u00a0/g, ' ').trim();
$('#task .put').onclick = async () => {
  if (K.project !== S.project || K.base !== S.base) {
    toast('This task belongs to the map you left. Reopen Add Task at its target.');
    return;
  }
  let task = taskText();
  if (!task.trim() && !$('#task .workflow').value) { toast('Say what is to be done.'); return; }
  if ($('#task .workflow').value) {
    const call = $('#task .workflow-call').value.trim();
    if (!call) { toast('Give the workflow an entry call.'); return; }
    const input = {call, element: K.nodes[0]};
    task = (task ? task + '\n\n' : '') + 'Run this stored workflow using the workflow module\'s run command with the following input. ' +
      'Follow the returned instructions and use the workflow commands for calls, handoffs and returns. ' +
      'Complete this ticket with the result when the entry call returns. Report any workflow failure on this ticket.\n' +
      `Workflow input: ${JSON.stringify(input)}`;
  }
  if (!task) { toast('A task says what is to be done.'); return; }
  // One ticket on the node it is assigned to, the first listed; every other node of the task, linked or named
  // inline, is linked for reference, VIEW-035.
  const inline = [...$('#task .text').querySelectorAll('[data-address]')].map(node => node.dataset.address);
  const all = [...new Set([...K.nodes, ...inline])].filter(address => partOf(address));
  const nodes = all.map(address => `element:${partOf(address).id}`);
  const project = S.project, metaform = S.base, generation = K.generation;
  const agent = $('#task select.agent').value, startNow = $('#task .start-agent').checked;
  const eligible = [...K.eligible];
  const written = await wrote('/api/task', {task, nodes, condition: $('#task .condition').value || null, held: $('#task .backlog').checked,
    agent, eligible});
  if (project !== S.project || metaform !== S.base || generation !== K.generation) {
    if (written) toast(`Task saved in ${project}. Open that map to start its agent.`);
    return;
  }
  if (written) {
    $('#task').hidden = true;
    if (startNow) await startAgent(written.results[0].id,
      !eligible.length || eligible.includes(agent) ? agent : eligible[0]);
    renderBoard();
  }
};
$('#task .close').onclick = () => { $('#task').hidden = true; K.generation++; };
/* Notes, VIEW-034: Rich, 2026-10-02, "Allow one single note not a list, limit its characters to 2048, make it so you
 * can edit the note and so can the user". One note at the node, kept by the memory module and read and written with
 * `memory note`, whatever layers are in view. Writing it replaces what it held, and writing it empty clears it. A note
 * asks for nothing: it is not a message, it does not glow, and it stays. */
const N = {node: null};
const NOTE_LIMIT = 2048;
async function noteOf(id) { return (await read('memory-note', {node: targetOf(id)})).note; }
function noteBy(note) {
  if (!note) return 'No note here yet.';
  return `Written by ${note.by === 'user' ? 'you' : note.by || 'an agent'}, ${when(note.at)}`;
}
function noteCount() { $('#notes .count').textContent = `${$('#notes textarea').value.length} / ${NOTE_LIMIT}`; }
async function notesAt(id) {
  N.node = id;
  $('#notes .title').textContent = `Notes · ${calledOf(id)}`;
  let note = null;
  try { note = await noteOf(id); } catch (error) { toast(error.message); }
  if (N.node !== id) return;
  $('#notes .by').textContent = noteBy(note);
  $('#notes textarea').value = note ? note.text : '';
  noteCount();
  $('#notes').hidden = false;
}
$('#notes textarea').setAttribute('maxlength', String(NOTE_LIMIT));
$('#notes textarea').addEventListener('input', noteCount);
$('#notes .save').onclick = async () => {
  const text = $('#notes textarea').value.trim() ? $('#notes textarea').value : '';
  if (!await wrote('/api/note', {node: targetOf(N.node), text})) return;
  await notesAt(N.node);
};
$('#notes .close').onclick = () => { $('#notes').hidden = true; N.node = null; };
movable($('#notes'));
/* Adding an element, VIEW-033: a person gives it its address and joins it to the node the window was opened at. */
const E = {node: null, from: ''};
function addElement(id) {
  const element = S.elements.get(id)?.element;
  if (!element) { toast('An element is added at an element.'); return; }
  E.node = id;
  $('#element .title').textContent = `Add Element · joined to ${named(element)}`;
  $('#element .receives option[value="node"]').textContent = `${named(element)}, and the new element serves it`;
  $('#element .receives option[value="new"]').textContent = `the new element, and ${named(element)} serves it`;
  for (const name of ['.purpose', '.ef', '.name']) $('#element ' + name).value = '';
  // It is written on from the address of the node: a part added beside a part mostly shares its trunk.
  E.from = element.address.includes('.') ? element.address.slice(0, element.address.lastIndexOf('.') + 1) : '';
  $('#element .address').value = E.from;
  fill($('#addresses'), [...S.elements.values()].map(entry => h('option', {value: entry.element.address + '.'})));
  $('#element').hidden = false;
  $('#element .address').focus();
}
$('#element .add').onclick = async () => {
  const written = $('#element .address').value.trim();
  const address = written === E.from || written.endsWith('.') ? '' : written;  // what it was started from is no address
  if (!address || S.elements.size && [...S.elements.values()].some(entry => entry.element.address === address)) {
    toast(address ? `There is an element at ${address} already.` : 'An element has an address.');
    return;
  }
  const given = {address, node: `element:${E.node}`, receives: $('#element .receives').value,
    name_length: Number($('#element .length').value) || 1, name: $('#element .name').value.trim(),
    role: $('#element .role').value,
    purpose: $('#element .purpose').value.trim(), ef: $('#element .ef').value.trim(),
    validate: $('#element .validate').checked};
  const response = await fetch('/api/element', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({project: S.project, base: S.base, ...given})});
  const body = await response.json().catch(() => ({error: 'The server did not answer with JSON.'}));
  if (!response.ok) { toast(body.error || 'The element was not written.'); return; }
  for (const notice of body.notices || []) toast(notice.message);
  $('#element').hidden = true;
  if (given.validate) await startAgent(body.work.id, $('#element select.agent').value);
  // What a person adds is shown: where the layers in view are chosen by name, the layer of what is added by hand
  // is put among them.
  S.layers = (await read('layers', {limit: 0})).results;
  const on = new Set(shownOn());
  if (!on.has(body.element.layer)) { on.add(body.element.layer); S.view = on; }
  renderChips();
  await loadGraph();
};
$('#element .close').onclick = () => { $('#element').hidden = true; };
movable($('#element'));
movable($('#task'));
movable($('#float'));
$('#float .close').onclick = () => { $('#float').hidden = true; O.open = false; Object.assign(F, {id: null, which: null, ids: new Set(), drawn: new Map()}); };
async function renderWork(target, key, also = null) {
  let records = [];
  try {
    records = (await read('work', {node: target, limit: 0})).results;
    if (also) records = [...records, ...(await read('work', {node: also, limit: 0})).results];
  } catch (error) { toast(error.message); }
  const box = $('#work');
  if (!box || S.selected !== key) return;
  fill(box, h('div', {class: 'eyebrow'}, 'Work ', chatButton(nodeTalk(key), calledOf(key) || 'this node')),
    records.map(record => h('div', {class: 'item work'},
    h('div', {class: 'pills'}, workPill(record.condition), h('span', {class: 'pill'}, record.done ? 'done' : 'open'),
      record.held ? h('span', {class: 'pill'}, 'held') : null, record.reviewed ? h('span', {class: 'pill'}, 'reviewed') : null),
    record.note ? h('p', {}, ...linked(record.note)) : null,
    record.task ? h('p', {class: 'fn'}, ...linked(record.task)) : null,
    record.done ? h('p', {class: 'obs'}, 'Resolved: ', ...linked(record.resolution)) : null,
    chatButton({id: record.id}, ticketPart(record)))));
}
function layerPill(name) { return h('span', {class: 'pill layer', style: {'--c': `var(${colorVar(name)})`}}, name); }
function elementLink(id, address) {
  const entry = S.elements.get(id);
  return h('a', {class: 'link', href: '#', onclick: event => { event.preventDefault(); select(id, true); }},
    entry ? labelOf(entry.element) : address);
}
function joinCard(join, side) {
  // A join seen from an element it holds names its receiver; seen from its receiver, it names every element it holds.
  const others = side === 'provider' ? (join.elements || []).map(each => elementLink(each.element_id, each.address))
    : [elementLink(join.receiver, join.receiver_address)];
  return h('div', {class: 'join'},
    h('div', {class: 'row'}, h('span', {class: 'dir'}, `${side} · `, ...others.flatMap((link, at) => at ? [', ', link] : [link])),
      h('span', {class: 'lay', style: {'--c': `var(${colorVar(join.layer)})`}}, join.layer)),
    join.purpose ? h('p', {}, join.purpose) : null,
    join.ef ? h('p', {class: 'fn'}, join.ef) : null);
}
/* An item's value as text: an object as one `field: value` line per field it holds, empty fields left out, so a layer
 * such as intake details reads as fields, Rich 2026-10-04: "its not formatted". */
const filled = value => value !== null && value !== undefined && value !== '' && !(Array.isArray(value) && !value.length);
const fieldText = value => value && typeof value === 'object' ? JSON.stringify(value) : String(value);
function itemText(value) {
  if (Array.isArray(value)) return value.map(fieldText).join('\n');
  if (value && typeof value === 'object')
    return Object.entries(value).filter(([, each]) => filled(each)).map(([key, each]) => `${key}: ${fieldText(each)}`).join('\n');
  return String(value ?? '');
}
/* The same value for the panel: an object as a table of its fields. */
function itemView(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return itemText(value);
  return h('dl', {class: 'fields'}, Object.entries(value).filter(([, each]) => filled(each))
    .flatMap(([key, each]) => [h('dt', {}, key), h('dd', {}, fieldText(each))]));
}
/* A selected join shows only itself, so nothing needs finding in its receiver's text. */
function renderJoin(join) {
  fill($('#p-object'),
    h('div', {class: 'eyebrow'}, 'Join'),
    h('h2', {}, join.ef || `${join.receiver_address} receives from ${join.provider_address}`),
    h('p', {class: 'meta'}, elementLink(join.receiver, join.receiver_address), ' receives from ',
      ...(join.elements || []).flatMap((each, at) => [at ? ', ' : '', elementLink(each.element_id, each.address)]), '.'),
    (join.open_work || []).length ? h('div', {class: 'pills'}, join.open_work.map(workPill)) : null,
    joinCard(join, 'provider'),
    h('div', {id: 'work'}));
  renderWork(`join:${join.id}`, 'p:' + join.id);
}
async function renderObject(id) {
  const {element} = S.elements.get(id);
  const pane = $('#p-object');
  const held = S.joins.filter(join => join.receiver === id), serves = S.joins.filter(join => join.providers.includes(id));
  fill(pane, 
    h('div', {class: 'eyebrow'}, 'Element'),
    h('h2', {}, element.short_name || element.address),
    element.name ? h('div', {class: 'canonical'}, element.name) : null,  // what the project calls it
    h('div', {class: 'addr'}, element.address),
    h('div', {class: 'pills'}, element.role ? h('span', {class: 'pill'}, element.role) : null,
      (element.open_work || []).map(workPill), layerPill(element.layer),
      h('span', {class: 'pill'}, `${held.length} held · ${serves.length} served`)),
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
          itemView(item.value), item.state ? ` · ${item.state}` : '', refsOf(item.refs))));
    }
    // What the memory module adds to the node's read, as `map node` gives it, BASE-035: its one note, and while memory
    // shows here, the memories kept at it and those on the joins it receives and provides, LAYER-013 and VIEW-034.
    const memory = node.memory || {}, color = {'--c': `var(${colorVar(memoryLayer())})`};
    const remembered = entity => h('div', {class: 'item', style: color},
      h('a', {class: 'link', href: '#', onclick: event => { event.preventDefault(); select(memoryKey(entity.name), true); }}, entity.name),
      h('small', {}, ` · ${entity.entityType}`), entity.observations.map(text => h('p', {class: 'itemtext'}, text)));
    if (memory.note) box.append(h('div', {class: 'eyebrow'}, 'Note'), h('div', {class: 'item note', style: color},
      h('p', {class: 'itemtext'}, memory.note.text), h('small', {}, noteBy(memory.note))));
    if ((memory.entities || []).length) box.append(h('div', {class: 'eyebrow'}, 'Memory'), ...memory.entities.map(remembered),
      ...(memory.relations || []).map(relation => h('p', {class: 'meta'}, `${relation.from} ${relation.relationType} ${relation.to}`)));
    for (const join of memory.joins || []) box.append(h('div', {class: 'eyebrow'}, `Memory on ${join.receiver} → ${join.provider}`),
      ...join.entities.map(remembered));
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
const P = {editor: null, name: null, number: null, versions: [], asked: 0};
async function getJson(path) {
  const response = await reach(path, {headers: {Accept: 'application/json'}});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `${path} failed`);
  return body;
}
async function renderPrompt(name = P.name, number = P.number) {
  // only the last one asked for is shown: opening a layer's prompt asks twice, and an earlier read coming back after
  // the person has typed would put the stored text back
  const asked = ++P.asked;
  const listed = (await getJson('/api/prompts')).prompts;
  if (asked !== P.asked) return;
  if (!listed.length) {
    $('#promptNote').textContent = 'No stored prompts yet. The intake stores its prompt the first time it is served.';
    return;
  }
  const chosen = listed.some(item => item.name === name) ? name : listed[0].name;
  const versions = (await getJson(`/api/prompt-versions?name=${encodeURIComponent(chosen)}`)).versions;
  if (asked !== P.asked) return;
  P.name = chosen;
  P.versions = versions;
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
  const names = new Map(S.layers.map(layer => [layer.id, layer.name]));
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

/* ---------- tabs, toast ---------- */
const TABS = {object: '#p-object', prov: '#p-prov', prompt: '#p-prompt'};
function showTab(tab) {
  for (const [key, selector] of Object.entries(TABS)) { $(selector).hidden = key !== tab; $('#t-' + key).setAttribute('aria-selected', String(key === tab)); }
  if (tab === 'prov') renderProv();
  if (tab === 'prompt' && !P.editor) renderPrompt();
  if (tab === 'prompt' && P.editor) setTimeout(() => P.editor.refresh(), 0);
}
for (const key of Object.keys(TABS)) $('#t-' + key).onclick = () => showTab(key);
let toastTimer;
function toast(message) { const box = $('#toast'); box.textContent = message; box.hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { box.hidden = true; }, 4200); }

/* ---------- live: the server pushes what modules publish, and the page redraws; nothing polls, VIEW-018 ----------
 * An intake being recorded is drawn as each object arrives, BASE-039; any other write to the metaform shown is read
 * again. Events that come while the page reads are drawn once, when it is done. */
const LIVE = {layer: null, base: null, seen: '', busy: false, again: false, whole: false, named: null, done: 0, drawn: -Infinity};
const following = () => LIVE.layer !== null && S.base === LIVE.base;
async function loadLive() {
  const page = await read('layer-graph', {layer: LIVE.layer});
  const text = JSON.stringify(page);
  if (text === LIVE.seen || !following()) return;
  LIVE.seen = text;
  S.elements = new Map(page.elements.map(entry => [entry.element.id, entry]));
  S.joins = page.joins.map(withProviders);
  S.items = new Map();
  draw3D(); renderLegend();
  await build2D();
  const keep = S.selected && (S.elements.has(S.selected) || joinOf(S.selected)) ? S.selected : null;
  const start = keep || [...S.elements.values()].find(entry => entry.element.role === 'DE')?.element.id
    || S.elements.keys().next().value;
  if (start) select(start, false, false, false, true);
  else fill($('#p-object'), h('p', {class: 'empty'}, 'Nothing to show in these layers yet.'));
}
/* Follow the intake being recorded, found = {layer, base_id}, or return to the map when it is no longer being
 * recorded, saying what happened: it finished when its metaform still stands, or it stopped because the project was
 * cleared, the one thing that takes a metaform away, VIEW-019. */
async function follow(found) {
  if (found && found.layer !== LIVE.layer) {
    Object.assign(LIVE, {layer: found.layer, base: found.base_id, seen: ''});
    if (S.base !== found.base_id) await loadProject(found.base_id);
    else { S.layers = (await read('layers', {limit: 0})).results; renderChips(); }
    toast(`An intake is being recorded in ${found.layer}; the map follows it as each object is recorded.`);
  } else if (!found && LIVE.layer) {
    const {base} = LIVE;
    const stands = (await read('bases', {limit: 0})).results.some(item => item.id === base);
    Object.assign(LIVE, {layer: null, base: null, seen: ''});
    renderLegend();
    toast(stands ? `The intake finished.` : `The intake stopped: ${S.project} was cleared.`);
    await loadProject();
    return;
  }
  if (following()) await loadLive();
}
/* On connecting, and on the browser's own reconnect, what is being recorded now is read once. */
async function recordingNow() {
  const found = (await read('intake-recording')).results[0] || null;
  await follow(found ? {layer: found.layer.name, base_id: found.base_id} : null);
}
/* One push: the chassis fired map.changed for a metaform of this project, or for its metaforms themselves, VIEW-018.
 * The page reads what is being recorded, then follows it, returns to the map when it has finished, shows the active
 * metaform when the project's metaforms changed, or reads the layers and the map again, keeping the view and the
 * selection. A change to tickets or messages alone reads only those, below. */
async function changed(event) {
  if (event.topic !== 'map.changed' || event.payload?.project !== S.project) return;
  const named = event.payload.tables;
  const agents = named === 'dispatch' || Array.isArray(named) && named.some(table => String(table).startsWith('dispatch.'));
  if (agents) agentsChanged(!linesOnly(event.payload));
  // an agent's own tables, its thread, sessions and settings, change no map
  if (named === 'dispatch' || Array.isArray(named) && named.length && named.every(table => String(table).startsWith('dispatch.'))) return;
  const tickets = ticketsOnly(event.payload);
  if (tickets && event.payload.base_id && event.payload.base_id !== S.base) return;  // another metaform's
  if (!tickets) { LIVE.whole = true; LIVE.named = LIVE.named && opsOnly(LIVE.named) ? [...LIVE.named, ...(named || [])] : named || null; }
  if (LIVE.busy) { LIVE.again = true; return; }
  LIVE.busy = true;
  try {
    do {
      await settled();
      LIVE.again = false;
      if (!LIVE.whole && S.whole && !LIVE.layer) { await ticketsChanged(); continue; }
      LIVE.whole = false;
      const named = LIVE.named; LIVE.named = null;
      LIVE.drawn = performance.now();  // a whole reload: the next waits SPACING, a ticket change does not
      const found = (await read('intake-recording')).results[0] || null;
      if (found || LIVE.layer) { await follow(found ? {layer: found.layer.name, base_id: found.base_id} : null); continue; }
      const metaforms = (await read('bases', {limit: 0})).results;
      const same = metaforms.length === S.bases.length && metaforms.every(item =>
        S.bases.some(known => known.id === item.id && known.active === item.active));
      if (!same) await loadProject();  // the project's metaforms changed: show the active one, as on opening
      else if (opsOnly(named) && await appliedOps()) { await ticketsChanged(); continue; }  // the ops since the drawn sequence, applied
      else {
        S.layers = (await read('layers', {limit: 0})).results;
        renderChips();
        await loadGraph(false);
      }
      boardFromTickets();  // the work the map's read took, not read again
    } while (LIVE.again);
  } catch (error) { toast(error.message); } finally { LIVE.busy = false; LIVE.done++; }
}
/* The ops since the drawn sequence, applied to what is drawn, STORE-046 and VIEW-018: an element or a join added,
 * changed or removed, an item or a property of a layer in view. The map, the panel and the board are drawn from what
 * changed, not read again. A change to a layer's declaration or to a selection changes what is in view, and so does an
 * op of a layer the page cannot place; those fall back to the whole read. Returns whether the ops were applied. */
const plainWords = address => address.split('.').reverse().map(part => part.replace(/_/g, ' ')).join(' ');
const shortName = (address, length) => {
  const parts = address.split('.');
  return !length || length > parts.length ? plainWords(address) : plainWords(parts.slice(-length).join('.'));
};
function layerInView(layerId) {
  const layer = S.layers.find(item => item.id === layerId);
  if (!layer || !layer.ready) return null;
  if (layer.kind === 'base') return layer;
  const shown = S.view === null ? layer.on : S.view.has(layer.name);
  return shown ? layer : false;
}
function nearestParent(address) {
  const parts = address.split('.');
  const byAddress = new Map([...S.elements.values()].map(entry => [entry.element.address, entry.element.id]));
  for (let n = parts.length - 1; n > 0; n--) {
    const prefix = parts.slice(0, n).join('.');
    if (byAddress.has(prefix)) return prefix;
  }
  return null;
}
function heldOf(ids) {
  return ids.map(id => {
    const entry = S.elements.get(id);
    const element = entry ? entry.element : {address: null, name_length: null, name: null, role: null};
    return {element_id: id, address: element.address, short_name: entry ? element.short_name : '',
      name_length: element.name_length, name: element.name, role: element.role};
  });
}
async function appliedOps() {
  if (following() || !S.whole || typeof S.seq !== 'number') return false;
  const ops = await read('ops', {after: S.seq, limit: 0});
  if (!Array.isArray(ops) || !ops.length) return true;  // nothing of the map changed: the tickets are read beside
  for (const op of ops) {
    if (op.kind === 'layer' || op.kind === 'selection') return false;  // what is in view may have changed
    if (op.kind === 'type') continue;
    const layer = layerInView(op.layer_id);
    if (layer === null && op.op !== 'remove') return false;  // a layer this page has not read yet
    if (layer === false) continue;  // not in view: nothing to draw
    const data = op.data || {};
    const gone = op.op === 'remove';
    if (op.kind === 'element') {
      if (gone) { S.elements.delete(op.id); continue; }
      const kept = S.elements.get(op.id)?.element || {};
      const element = {...kept, id: op.id, layer_id: op.layer_id, layer: layer.name,
        ...('address' in data ? {address: data.address} : {}), ...('name' in data ? {name: data.name} : {}),
        ...('name_length' in data ? {name_length: data.name_length} : {}), ...('role' in data ? {role: data.role} : {})};
      if (!element.address) return false;
      element.reading = plainWords(element.address);
      element.short_name = shortName(element.address, element.name_length);
      element.open_work = kept.open_work || [];
      S.elements.set(op.id, {element, parent: nearestParent(element.address)});
    } else if (op.kind === 'join') {
      S.joins = S.joins.filter(join => join.id !== op.id);
      if (gone) continue;
      const before = S.whole.joins.find(join => join.id === op.id) || {};
      const held = 'held' in data ? data.held : before.providers || [];
      const receiver = 'receiver' in data ? data.receiver : before.receiver;
      const join = {id: op.id, layer_id: op.layer_id, layer: layer.name, type: data.type ?? before.type ?? 'purpose',
        receiver, receiver_address: S.elements.get(receiver)?.element.address ?? null,
        purpose: 'purpose' in data ? data.purpose : before.purpose ?? null, ef: 'ef' in data ? data.ef : before.ef ?? null,
        ifd: 'ifd' in data ? data.ifd : before.ifd ?? null, elements: heldOf(held), open_work: before.open_work || [],
        element: 'element' in data ? data.element : before.element ?? null};
      S.joins.push(withProviders(join));
    } else if (op.kind === 'item' || op.kind === 'property') {
      const key = (op.kind === 'item' ? 'i:' : 'r:') + op.id;
      if (gone) { S.items.delete(key); continue; }
      const kept = S.items.get(key)?.item || {};
      const value = 'value' in data ? JSON.parse(data.value) : kept.value;
      const refs = 'refs' in data ? data.refs.map(([k, v]) => ({key: k, value: v})) : kept.refs || [];
      const extra = 'extra' in data ? (data.extra ? JSON.parse(data.extra) : null) : kept.extra ?? null;
      const item = op.kind === 'item'
        ? {...kept, id: op.id, layer_id: op.layer_id, layer: layer.name, value, refs, extra,
           target: 'target_kind' in data ? {kind: data.target_kind, id: data.target_id} : kept.target,
           link: 'link_kind' in data ? (data.link_kind ? {kind: data.link_kind, id: data.link_id} : null) : kept.link ?? null,
           read_first: 'read_first' in data ? !!data.read_first : !!kept.read_first,
           always_show: 'always_show' in data ? !!data.always_show : !!kept.always_show}
        : {...kept, id: op.id, layer_id: op.layer_id, layer: layer.name, value, refs, extra,
           element_id: 'element_id' in data ? data.element_id : kept.element_id,
           address: S.elements.get('element_id' in data ? data.element_id : kept.element_id)?.element.address ?? null};
      if (op.kind === 'item' && !item.target) return false;
      S.items.set(key, {kind: op.kind, key, item, value, layer: layer.name, layerKind: layer.kind});
    }
  }
  for (const entry of S.elements.values()) entry.parent = nearestParent(entry.element.address);
  S.whole = {elements: S.elements, joins: S.joins};
  S.seq = ops[ops.length - 1].seq;
  draw3D();
  renderLegend();
  await build2D();
  if (S.selected && (S.elements.has(S.selected) || joinOf(S.selected))) await select(S.selected, false, false, false, true);
  else if (S.selected) { const start = [...S.elements.values()].find(entry => entry.element.role === 'DE')?.element.id || S.elements.keys().next().value; if (start) await select(start, false, false, false, true); }
  return true;
}
/* Agents write several times a second. The whole map is read again at most once every SPACING, and nothing is drawn
 * while the person is zooming or dragging, so nothing moves under their hands; the changes in between are read
 * together. */
const QUIET = 800, SPACING = 3000;
const HANDS = {at: 0, down: false};
addEventListener('wheel', () => { HANDS.at = performance.now(); }, {passive: true, capture: true});
addEventListener('pointerdown', () => { HANDS.down = true; HANDS.at = performance.now(); }, true);
addEventListener('pointerup', () => { HANDS.down = false; HANDS.at = performance.now(); }, true);
async function settled(after = LIVE.drawn + SPACING) {
  for (;;) {
    const now = performance.now();
    const wait = Math.max(HANDS.at + QUIET - now, after - now, HANDS.down ? QUIET : 0);
    if (wait <= 0) return;
    await new Promise(done => setTimeout(done, wait));
  }
}
/* The tables a ticket or a message is written in, as map.changed names them, VIEW-018. A change to these alone adds or
 * removes no node and no link, so the map, its layers' items and its memories are not read again for it. */
const TICKET_TABLES = new Set(['work', 'work_links', 'work_steps', 'messages', 'map.glyphs', 'map.ticket_settings',
  'map.question_work']);
const ticketsOnly = payload => Array.isArray(payload.tables) && payload.tables.length > 0
  && payload.tables.every(table => TICKET_TABLES.has(table) || String(table).startsWith('dispatch.'));
/* A change the page can apply from the ops alone, STORE-046: the log, the objects registry, the kinds of op, and the
 * tickets' tables; a module's own table, such as the memory graph's, is read again whole. */
const opsOnly = named => Array.isArray(named) && named.length > 0 && named.every(table => table === 'ops'
  || table === 'objects' || String(table).startsWith('op:') || TICKET_TABLES.has(table) || String(table).startsWith('dispatch.'));
/* A change to tickets or messages alone: work and the open messages are read once each, and the nodes' lights, the
 * figures, the board and the selected node's panel are drawn from them, VIEW-035 and VIEW-037. */
async function ticketsChanged() {
  const project = S.project, metaform = S.base;
  const [progress] = await Promise.all([progressOf(), renderMessages()]);
  if (S.project !== project || S.base !== metaform) return;
  S.progress = progress;
  openWork();
  draw3D();
  renderLegend();
  figures(S.tickets || []);
  boardFromTickets();
  workInPanel();
  await build2D();
}
function boardFromTickets() {
  if ($('#board').hidden || !S.tickets) return;
  B.tickets = S.tickets;
  drawBoard();
}
/* Each node's open work as the map read gives it, MAP-050: the conditions of its open tickets in row order, a taken one
 * as it reads once taken, then what waits for the person there; rebuilt from the tickets and open messages read. */
const TAKEN = {missing: 'in-progress', broken: 'fixing'};
function openWork() {
  const open = new Map(), add = (key, what) => open.set(key, [...(open.get(key) || []), what]);
  for (const ticket of S.tickets || []) if (!ticket.done)
    add(`${ticket.node_kind}:${ticket.node_id}`, ticket.taken ? TAKEN[ticket.condition] || ticket.condition : ticket.condition);
  for (const message of Q.open) add(`${message.node_kind}:${message.node_id}`, message.kind);
  for (const entry of S.elements.values()) entry.element.open_work = open.get(`element:${entry.element.id}`) || [];
  for (const join of S.joins) join.open_work = open.get(`join:${join.id}`) || [];
}
/* The selected node's open work pills and its Work box drawn again, the rest of its panel kept as it is. */
function workInPanel() {
  const id = S.selected, join = id && !MEM.key && id.startsWith('p:') ? joinOf(id) : null;
  const element = id && !MEM.key && !join ? S.elements.get(id)?.element : null;
  const pane = $('#p-object');
  if (!(join || element) || !pane.querySelector(':scope > #work')) return;
  let pills = pane.querySelector(':scope > .pills');
  if (!pills && join) { pills = h('div', {class: 'pills'}); pane.querySelector(':scope > .join')?.before(pills); }
  if (pills) {
    for (const pill of pills.querySelectorAll('.pill[class*="work-"]')) pill.remove();
    const before = pills.querySelector('.pill.layer');
    for (const condition of (join || element).open_work || []) pills.insertBefore(workPill(condition), before);
  }
  renderWork(join ? `join:${join.id}` : `element:${id}`, id);
}
/* A line an agent wrote, or its session begun or ended: the agents key, the open agent window and the open chat are
 * read again, at most once every BATCH and never under the person's hands, once for however many lines came
 * meanwhile. An agent streams about five lines a second, and drawing each one kept the page always reading and its
 * windows always redrawn. Only a change beyond the threads, `whole`, reads the merges and the advice again. */
const BATCH = 500;
const AGENTS = {busy: false, again: false, whole: false, at: -Infinity};
const linesOnly = payload => payload.tables === 'dispatch' && Array.isArray(payload.dispatch_tables)
  && payload.dispatch_tables.length > 0 && payload.dispatch_tables.every(table => table === 'dispatch.lines');
async function agentsChanged(whole = false) {
  if (whole) AGENTS.whole = true;
  if (AGENTS.busy) { AGENTS.again = true; return; }
  AGENTS.busy = true;
  try {
    do {
      await settled(AGENTS.at + BATCH);
      AGENTS.again = false;
      AGENTS.at = performance.now();
      if (AGENTS.whole) { AGENTS.whole = false; renderMerges(); refreshAdvice(); }
      await Promise.all([renderAgents(), MERGE.chat ? drawHelpdesk() : null]);
    } while (AGENTS.again);
  } catch (error) { toast(error.message); } finally { AGENTS.busy = false; }
}
/* On every open of the stream the agents and the open agent window are also read again: a line written while the
 * stream was down, as when an agent restarts this server, was announced to no page, work 109ae725, and so was one
 * written between the load's read of the agents and the first open, as a runner dying then, work f7cd3522. */
let STREAM = null;
function listen() {
  // the stream names the project this page shows: agents are started only for a project some page has open
  if (STREAM) STREAM.close();
  const source = STREAM = new EventSource(`/api/events?project=${encodeURIComponent(S.project || '')}`);
  source.onmessage = message => changed(JSON.parse(message.data));
  source.onopen = () => {
    recordingNow().catch(error => toast(error.message));
    agentsChanged();
  };
}

/* Every item and property of the layers, read as the context sees them, so selection, masks and hidden layers apply
 * as in every read, VIEW-017. */
async function itemsOf(generation) {
  const found = new Map();
  for (const layer of S.layers.filter(item => item.ready && item.kind !== 'base')) {
    let after = null;
    do {
      const page = await read('layer-items', {layer: layer.name, in_context: 'true', limit: 500, ...(after ? {after} : {}), ...viewLayers()});
      if (generation !== S.loading) return found;
      for (const item of page.results) {
        const property = !('target' in item);  // a property sits on an element, an item on a node
        const key = property ? 'r:' + item.id : 'i:' + item.id;
        found.set(key, {kind: property ? 'property' : 'item', key, item, value: item.value, layer: layer.name, layerKind: layer.kind});
      }
      after = page.next;
    } while (after);
  }
  return found;
}

/* ---------- loading: projects, metaforms, layers, then the graph page by page ---------- */
/* The steps filed and planned of each node's open tickets, the most advanced first, VIEW-035: an element's by its
 * id, a join's on its purpose vertex. */
async function progressOf() {
  const found = new Map(), project = S.project, metaform = S.base;
  let tickets = [];
  try { tickets = (await read('work', {limit: 0})).results || []; } catch (error) { return found; }
  if (S.project !== project || S.base !== metaform) return found;  // a late answer for a project the person left
  S.tickets = tickets;
  for (const ticket of tickets) {
    if (!ticket.taken || ticket.done) continue;
    const keys = ticket.node_kind === 'join' ? ['p:' + ticket.node_id] : [ticket.node_id];
    const done = {filed: ticket.steps_done || 0, planned: ticket.steps || 0};
    const share = one => one.planned ? one.filed / one.planned : one.filed;
    for (const key of keys) if (!found.has(key) || share(done) > share(found.get(key))) found.set(key, done);
  }
  return found;
}
/* A load counts as opening from its first read until the panel of what it selects has been read, so loaded() is not
 * true while the page still reads what it loads. */
async function opening(work) {
  S.opening++;
  try { return await work(); } finally { S.opening--; }
}
/* agents: whether the agents key is read with the map; a map change does not read it, since the agents are read again
 * on dispatch events, VIEW-018. */
function loadGraph(agents = true) { return opening(() => readGraph(agents)); }
async function readGraph(agents) {
  if (following()) { LIVE.seen = ''; S.loading = 0; return loadLive(); }
  const generation = ++S.loading, project = S.project, metaform = S.base;
  // a read is dropped once another has begun or the person has chosen another project or metaform
  const stale = () => generation !== S.loading || S.project !== project || S.base !== metaform;
  S.elements = new Map(); S.joins = [];
  let after = null, whole = false;
  try {
    do {
      const page = await read('graph', {limit: 500, ...(after ? {after} : {}), ...viewLayers()});
      if (stale()) return;
      for (const entry of page.elements) S.elements.set(entry.element.id, entry);
      S.joins.push(...page.joins.map(withProviders));
      draw3D(); renderLegend();
      after = page.next;
    } while (after);
    whole = true;
    S.whole = {elements: S.elements, joins: S.joins};
    S.seq = await read('sequence');  // the sequence the map drawn is at; the ops after it are applied, STORE-046
    if (stale()) return;
    const items = await itemsOf(generation);
    if (stale()) return;
    S.items = items;
    const memory = await memoryOf();
    if (stale()) return;
    S.memory = memory;
    renderOrphans();
    S.progress = await progressOf();
    figures(S.tickets || []);
  } catch (error) {
    toast(error.message);
    // The last whole map read is kept: a read that fails, as every read does while the server restarts, puts it back,
    // and the failure is said. Another metaform's is never put back, since its load begins with none.
    if (!stale() && !whole && S.whole) Object.assign(S, S.whole);
  }
  if (stale()) return;
  S.loading = 0;
  draw3D();
  renderLegend();
  const told = Promise.all([renderMessages(), agents && renderAgents()]);  // read beside the 2D map; the load ends when they are
  await build2D();
  const keep = S.selected && (S.elements.has(S.selected) || joinOf(S.selected)
    || MEM.network?.entities.includes(S.selected) || memoryThing(S.selected)) ? S.selected : null;
  const start = keep || MEM.key || [...S.elements.values()].find(entry => entry.element.role === 'DE')?.element.id
    || S.elements.keys().next().value;
  if (!start) fill($('#p-object'), h('p', {class: 'empty'}, noMetaform() ? noneYet() : 'Nothing to show in these layers yet.'));
  else {
    if (!keep) setTimeout(() => { if (G) fit3d(800, 60); }, 2200);
    await select(start, false, false, false, true);
  }
  await told;
}
async function loadMetaform() {
  S.view = null; S.selected = null; IN.length = 0; M.base = null; dropMemories(); renderCrumbs();
  S.elements = new Map(); S.joins = []; S.whole = null;
  S.layers = (await read('layers', {limit: 0})).results;
  renderChips();
  if ($('#p-prov').hidden === false) renderProv();
  await loadGraph();
}
function loadProject(wanted = null) { return opening(() => readProject(wanted)); }
async function readProject(wanted) {
  const project = S.project;
  await readAutostart();
  const metaforms = (await read('bases', {limit: 0})).results;
  if (S.project !== project) return;  // the metaforms of a project the person has left

  S.bases = metaforms;
  const active = metaforms.find(item => item.id === wanted) || metaforms.find(item => item.active) || metaforms[0];
  S.base = active ? active.id : null;
  fill($('#mf'), ...(metaforms.length ? metaforms.map(item => h('option', {value: item.id, selected: item === active}, item.name + (item.active ? ' · active' : '')))
    : [h('option', {}, 'none yet')]));
  $('#mf').disabled = !metaforms.length;
  baseButtons();
  await loadMetaform();
}
/* Activate and Remove beside the base chooser, STORE-041: the chooser only changes what the page shows; Activate makes
 * the chosen base the active one, and Remove takes it out of the project with a copy kept. Neither acts on the active
 * base, as the command refuses to. */
function baseButtons() {
  const chosen = S.bases.find(item => item.id === $('#mf').value);
  $('#activateBase').disabled = !chosen || chosen.active;
  $('#removeBase').disabled = !chosen || chosen.active;
}
$('#activateBase').onclick = async () => {
  const chosen = S.bases.find(item => item.id === $('#mf').value);
  if (!chosen) return;
  $('#activateBase').disabled = true;
  if (await wrote('/api/activate-base', {name: chosen.name})) toast(`${chosen.name} is the active base.`);
  else baseButtons();
};
$('#removeBase').onclick = async () => {
  const chosen = S.bases.find(item => item.id === $('#mf').value);
  if (!chosen || !confirm(`Remove base ${chosen.name} from ${S.project}? A copy of its store is kept under backups/remove-base.`)) return;
  $('#removeBase').disabled = true;
  const done = await wrote('/api/remove-base', {name: chosen.name, confirm: true});
  if (done) toast(`Removed ${chosen.name}; its store is kept at ${done.kept}.`);
  else baseButtons();
};
/* Another project chosen: the agents drawn are the project left's, so its agent window closes and its agents go,
 * VIEW-039, and its figures with them at once, having no map here to walk back on, VIEW-035; the new project's are
 * read with its map. */
function toProject(id) {
  S.project = id;
  S.tickets = []; B.tickets = [];  // nothing of the project left behind shows on the next one
  if (!$('#board').hidden) drawBoard();
  location.hash = 'p=' + encodeURIComponent(id);
  Object.assign(LIVE, {layer: null, base: null, seen: ''});
  Object.assign(D, {sessions: [], notes: [], work: null, session: null, drawn: new Map(), chat: null});
  $('#autostartAgents').checked = false;
  $('#autostartAgents').disabled = true;
  $('#agent').hidden = true;
  for (const list of document.querySelectorAll('#agents .list')) fill(list);
  $('#agents').hidden = true;
  for (const [work, figure] of ROAM.figures) { G?.scene().remove(figure.mesh); releaseGlyph(work); }
  ROAM.figures.clear(); ROAM.seen.clear();
  Object.assign(MERGE, {rows: [], chat: null});
  $('#reviewNotice').hidden = $('#mergeAsk').hidden = $('#helpdesk').hidden = true;
  renderMerges();  // the merges this project has waiting for review, VIEW-044
}
$('#proj').onchange = () => { toProject($('#proj').value); loadProject(); listen(); };
$('#mf').onchange = () => { S.base = $('#mf').value; baseButtons(); loadMetaform(); };

async function main() {
  const response = await reach('/api/projects');
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
  renderMerges();  // VIEW-044
}
main();
