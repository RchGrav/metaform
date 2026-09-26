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
  elements: new Map(), joins: [], selected: null, neighbors: new Set(), loading: 0,
};

async function read(name, params = {}) {
  const query = new URLSearchParams({project: S.project, ...(S.metaform ? {metaform: S.metaform} : {}), ...params});
  const response = await fetch(`/api/${name}?${query}`, {headers: {Accept: 'application/json'}});
  const body = await response.json().catch(() => ({error: 'The server did not answer with JSON.'}));
  if (!response.ok) throw Object.assign(new Error(body.error || `${name} failed`), {status: response.status, body});
  return body;
}
const viewLayers = () => S.view === null ? {} : {layers: [...S.view].join(',')};

/* ---------- layers: color by position, chips, apply ---------- */
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

function renderChips() {
  const on = shownOn();
  const box = $('#layers');
  fill(box);
  for (const layer of S.layers.filter(item => item.kind !== 'correction')) {
    const usable = layer.ready && !layer.hidden;
    const chip = h('button', {class: 'chip', style: {'--c': `var(${colorVar(layer.name)})`},
      'aria-pressed': String(usable && on.has(layer.name)), disabled: !usable,
      title: layer.hidden ? 'Hidden: it stays out even when turned on.' : !layer.ready ? 'Still building.' : null,
      onclick: () => {
        const next = new Set(shownOn());
        next.has(layer.name) ? next.delete(layer.name) : next.add(layer.name);
        S.view = same(next, folderOn()) ? null : next;
        renderChips();
        loadGraph();
      }}, h('i'), layer.name);
    box.append(chip);
  }
  const corrections = S.layers.filter(item => item.kind === 'correction').length;
  if (corrections) box.append(h('span', {class: 'chip fixed', style: {'--c': 'var(--correction)'}, 'aria-pressed': 'true',
    title: 'Correction layers are always applied, in order.'}, h('i'), `corrections · ${corrections}`));
  $('#apply').disabled = S.view === null;
  const folder = S.projects.find(item => item.id === S.project)?.path || '';
  $('#note').textContent = S.view === null
    ? `Viewing only. These are the layers of ${folder}. What you toggle changes this view, not the folder, until you apply it.`
    : S.view.size === 0 ? 'No layer is chosen, which reads as every layer, as an empty --layers does.'
    : `This view differs from ${folder}. Apply to folder runs: metaform set --layers ${[...S.view].join(',')}`;
}

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

/* ---------- the graph data: every join in its tripartite form, VIEW-005 ---------- */
function graphData() {
  const nodes = [], links = [];
  const byAddress = new Map([...S.elements.values()].map(entry => [entry.element.address, entry.element.element_id]));
  for (const {element, parent} of S.elements.values()) {
    nodes.push({id: element.element_id, t: 'el', name: element.short_name || element.address, address: element.address,
      role: element.role, flag: element.flag, layer: element.layer, joins: 0});
    if (parent && byAddress.has(parent)) links.push({source: byAddress.get(parent), target: element.element_id, k: 'tree'});
  }
  const ids = new Set(nodes.map(node => node.id));
  const count = new Map();
  for (const join of S.joins) {
    if (!ids.has(join.receiver) || !ids.has(join.provider)) continue;
    const purpose = 'p:' + join.join_id, encounter = 'e:' + join.join_id;
    nodes.push({id: purpose, t: 'purpose', join: join.join_id, layer: join.layer, flag: join.flag});
    nodes.push({id: encounter, t: 'encounter', join: join.join_id, layer: join.layer, flag: join.flag});
    links.push({source: join.receiver, target: purpose, k: 'face', layer: join.layer, join: join.join_id});
    links.push({source: purpose, target: encounter, k: 'face', layer: join.layer, join: join.join_id});
    links.push({source: encounter, target: join.receiver, k: 'face', layer: join.layer, join: join.join_id});
    links.push({source: encounter, target: join.provider, k: 'tie', layer: join.layer, join: join.join_id});
    for (const subtype of join.subtypes || []) {
      nodes.push({id: 's:' + subtype.subtype_id, t: 'sub', join: join.join_id, layer: subtype.layer,
        name: subtype.name || subtype.address, flag: subtype.flag});
      links.push({source: encounter, target: 's:' + subtype.subtype_id, k: 'sub', layer: subtype.layer});
    }
    for (const end of [join.receiver, join.provider]) count.set(end, (count.get(end) || 0) + 1);
  }
  for (const node of nodes) if (node.t === 'el') node.joins = count.get(node.id) || 0;
  return {nodes, links};
}
window.metaform = {graph: () => graphData(), selected: () => S.selected, select: id => select(id, true)};

/* ---------- 3D: a synaptic map ---------- */
let G = null;
const FLAGS = {missing: '--missing', broken: '--broken', cruft: '--cruft'};
function nodeColor(node) {
  if (node.flag && FLAGS[node.flag]) return css(FLAGS[node.flag]);
  const dim = S.selected && node.t === 'el' && node.id !== S.selected && !S.neighbors.has(node.id);
  if (dim) return '#2b3644';
  if (node.t === 'el') return node.role === 'DE' ? '#ffffff' : node.role === 'VE' ? css('--signal') : layerColor(node.layer);
  if (node.t === 'purpose') return css('--text');
  return layerColor(node.layer);
}
function linkColor(link) {
  if (link.k === 'tree') return css('--tree');
  if (link.k === 'tie') return css('--signal');
  return layerColor(link.layer);
}
function start3D() {
  if (typeof ForceGraph3D !== 'function') {
    fill($('#stage'), h('p', {class: 'empty', style: {padding: '24px'}}, 'The 3D view needs WebGL and could not start here.'));
    return;
  }
  G = ForceGraph3D({controlType: 'orbit'})($('#stage'))
    .backgroundColor(css('--ground'))
    .showNavInfo(false)
    .nodeRelSize(3)
    .nodeVal(node => node.t === 'el' ? 3 + Math.min(10, node.joins * 1.5) + (node.role === 'DE' ? 4 : node.role === 'VE' ? 2 : 0)
      : node.t === 'purpose' ? 0.9 : node.t === 'encounter' ? 0.6 : 0.35)
    .nodeColor(nodeColor)
    .nodeOpacity(0.95)
    .nodeResolution(16)
    .nodeLabel(node => {
      const tip = h('div', {class: 'tip'});
      tip.style.cssText = 'font:12px var(--sans);max-width:280px;background:#0c1117ee;border:1px solid #2a3747;padding:6px 8px;border-radius:6px;color:#d9e2ec';
      if (node.t === 'el') tip.append(h('b', {}, node.name), h('br'), h('span', {style: {color: '#62e3d3', font: '11px var(--mono)'}}, node.address));
      else {
        const join = S.joins.find(item => item.join_id === node.join);
        tip.append(node.t === 'purpose' ? (join?.purpose || 'purpose') : node.t === 'encounter' ? (join?.function || 'encounter') : node.name);
      }
      return tip.outerHTML;
    })
    .linkColor(linkColor)
    .linkOpacity(0.55)
    .linkWidth(link => link.k === 'tree' ? 0.3 : link.k === 'sub' ? 0.25 : link.k === 'tie' ? 0.9 : 0.6)
    .linkCurvature(link => link.k === 'face' || link.k === 'tie' ? 0.18 : 0)
    .linkDirectionalArrowLength(link => link.k === 'tie' ? 3 : 0)
    .linkDirectionalArrowRelPos(1)
    .linkDirectionalParticles(link => link.k === 'tie' || link.k === 'face' ? 1 : 0)
    .linkDirectionalParticleSpeed(0.006)
    .linkDirectionalParticleWidth(1.4)
    .linkDirectionalParticleColor(linkColor)
    .onNodeClick(node => {
      const join = node.join && S.joins.find(item => item.join_id === node.join);
      select(node.t === 'el' ? node.id : join ? join.receiver : null, true);
    });
  G.d3Force('charge').strength(node => node.t === 'el' ? -140 : -18);
  G.d3Force('link')
    .distance(link => link.k === 'tree' ? 60 : link.k === 'sub' ? 8 : link.k === 'tie' ? 30 : 14)
    .strength(link => link.k === 'tree' ? 0.15 : 0.8);
  if (reduced()) G.cooldownTicks(0);
  resize();
  requestAnimationFrame(labels);
}
const tags = new Map();
function labels() {
  if (G) {
    const box = $('#labels3d');
    const nodes = G.graphData().nodes.filter(node => node.t === 'el');
    const few = nodes.length <= 300;
    for (const node of nodes) {
      let tag = tags.get(node.id);
      if (!tag) { tag = h('span', {}, node.name); box.append(tag); tags.set(node.id, tag); }
      const show = node.x !== undefined && (few || node.id === S.selected || S.neighbors.has(node.id));
      tag.hidden = !show;
      if (!show) continue;
      const point = G.graph2ScreenCoords(node.x, node.y, node.z);
      tag.style.left = point.x + 'px';
      tag.style.top = point.y + 'px';
      tag.className = node.id === S.selected ? 'sel' : S.neighbors.has(node.id) ? 'near' : S.selected ? 'dim' : '';
    }
  }
  requestAnimationFrame(labels);
}
function draw3D() {
  if (!G) return;
  const previous = new Map(G.graphData().nodes.map(node => [node.id, node]));
  const data = graphData();
  for (const node of data.nodes) {  // keep drawn positions, so the picture does not jump as pages arrive
    const known = previous.get(node.id);
    if (known) Object.assign(node, {x: known.x, y: known.y, z: known.z, vx: known.vx, vy: known.vy, vz: known.vz});
  }
  for (const [id, tag] of tags) if (!S.elements.has(id)) { tag.remove(); tags.delete(id); }
  G.graphData(data);
}
function resize() { if (G) { const box = $('#stage').getBoundingClientRect(); G.width(box.width).height(box.height); } }
addEventListener('resize', resize);

function renderLegend() {
  const inView = new Set([...S.elements.values()].map(entry => entry.element.layer).concat(S.joins.map(join => join.layer)));
  const rows = [...inView].map(name => [colorVar(name), name, '']);
  rows.push(['--signal', 'encounter tie to the provider', ''], ['--tree', 'namespace', 'dash']);
  const legend = $('#legend');
  fill(legend, ...rows.map(([color, text, kind]) =>
    h('span', {style: {'--c': `var(${color})`}}, h('i', {class: kind}), text)));
  const flags = new Set([...S.elements.values()].map(entry => entry.element.flag).concat(S.joins.map(join => join.flag)));
  for (const flag of ['missing', 'broken', 'cruft']) if (flags.has(flag))
    legend.append(h('span', {style: {'--c': `var(--${flag})`}}, h('i', {class: 'dot'}), `flag: ${flag}`));
  $('#count').textContent = `${S.elements.size} elements · ${S.joins.length} joins` + (S.loading ? ' · loading' : '');
}

/* ---------- 2D: the whole map, short names, no text on the edges; the camera moves node to node ---------- */
const M = {svg: null, nodes: new Map(), edges: [], cam: null, fit: null, frame: 0, generation: 0};
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
  const lines = [S.elements.size > 5 ? 'flowchart TB' : 'flowchart LR'];
  for (const [id, {element}] of S.elements) lines.push(`${keys.get(id)}["${plain2d(element.short_name || element.address)}"]`);
  const drawn = S.joins.filter(join => keys.has(join.receiver) && keys.has(join.provider));
  drawn.forEach((join, index) => lines.push(`${keys.get(join.receiver)} e${index}@--> ${keys.get(join.provider)}`));
  if (!S.elements.size) { fill(host, h('p', {class: 'empty', style: {padding: '16px'}}, 'This metaform has no elements in these layers.')); return; }
  let result;
  try { result = await window.mermaid.render(`map2d${generation}`, lines.join('\n')); }
  catch (error) { fill(host, h('p', {class: 'empty', style: {padding: '16px'}}, 'The 2D map could not be drawn.')); return; }
  if (generation !== M.generation) return;
  const parsed = new DOMParser().parseFromString(result.svg, 'image/svg+xml');  // only Mermaid's strict SVG is parsed
  M.svg = document.importNode(parsed.documentElement, true);
  M.svg.removeAttribute('height'); M.svg.removeAttribute('width'); M.svg.removeAttribute('style');
  M.svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  fill(host, M.svg);
  M.nodes.clear();
  for (const [id, key] of keys) {
    const group = M.svg.querySelector(`[id*="-flowchart-${key}-"]`);
    if (!group) continue;
    const box = group.getBBox();
    const matrix = group.transform.baseVal.consolidate()?.matrix;
    const center = new DOMPoint(box.x + box.width / 2, box.y + box.height / 2).matrixTransform(matrix || new DOMMatrix());
    M.nodes.set(id, {g: group, x: center.x, y: center.y, w: box.width, h: box.height});
    const flag = S.elements.get(id).element.flag;
    if (flag) group.classList.add(`flag-${flag}`);
    const title = document.createElementNS(SVG, 'title');
    title.textContent = S.elements.get(id).element.address;
    group.append(title);
    group.addEventListener('click', event => { event.stopPropagation(); select(id, true); });
  }
  M.edges = drawn.map((join, index) => ({join, path: M.svg.querySelector(`[data-id="e${index}"]`)
    || M.svg.querySelectorAll('.edgePaths path')[index]}));
  const scene = M.svg.querySelector('g').getBBox();
  M.fit = {x: scene.x - 30, y: scene.y - 30, w: scene.width + 60, h: scene.height + 60};
  setCam(frame(M.fit));
  if (S.selected) focus2D(S.selected, false);
}
function aspect() { const box = $('#map2d').getBoundingClientRect(); return Math.max(0.2, box.width / Math.max(1, box.height)); }
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
  $('#map2d').classList.remove('focused');
  for (const edge of M.edges) edge.path?.classList.remove('on');
  for (const node of M.nodes.values()) node.g.classList.remove('sel', 'near');
  if (M.fit) moveCam(M.fit);
}
function focus2D(id, animate = true) {
  const node = M.nodes.get(id);
  if (!node || !M.svg) return;
  $('#map2d').classList.add('focused');
  for (const [key, value] of M.nodes) { value.g.classList.toggle('sel', key === id); value.g.classList.toggle('near', key !== id && S.neighbors.has(key)); }
  for (const edge of M.edges) edge.path?.classList.toggle('on', edge.join.receiver === id || edge.join.provider === id);
  const w = Math.max(node.w * 3.4, 380), height = Math.max(node.h * 5, 260);
  moveCam({x: node.x - w / 2, y: node.y - height / 2, w, h: height}, animate);
}
(function wire2D() {
  const host = $('#map2d');
  $('#fitBtn').onclick = event => { event.stopPropagation(); fitAll(); };
  let drag = null;
  host.addEventListener('pointerdown', event => {
    if (event.target.closest('button') || !M.cam) return;
    drag = {x: event.clientX, y: event.clientY, cam: {...M.cam}, moving: false};
  });
  host.addEventListener('pointermove', event => {
    if (!drag) return;
    if (!drag.moving) {  // captured only once it is a drag, so a click still reaches the node under it
      if (Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 4) return;
      drag.moving = true; host.setPointerCapture(event.pointerId);
    }
    const box = host.getBoundingClientRect(), scale = M.cam.w / box.width;
    setCam({...drag.cam, x: drag.cam.x - (event.clientX - drag.x) * scale, y: drag.cam.y - (event.clientY - drag.y) * scale});
  });
  host.addEventListener('pointerup', () => { drag = null; });
  host.addEventListener('wheel', event => {
    if (!M.cam) return;
    event.preventDefault();
    const f = event.deltaY > 0 ? 1.15 : 0.87, box = host.getBoundingClientRect();
    const px = (event.clientX - box.left) / box.width, py = (event.clientY - box.top) / box.height, c = M.cam;
    setCam({x: c.x + (c.w - c.w * f) * px, y: c.y + (c.h - c.h * f) * py, w: c.w * f, h: c.h * f});
  }, {passive: false});
})();
function fitAll() { fit2D(); if (G) G.zoomToFit(reduced() ? 0 : 700, 60); }

/* Arrow keys follow joins: to the joined element that lies furthest the pressed way in the 2D map. F fits. */
document.addEventListener('keydown', event => {
  if (event.target.closest('select, input, textarea')) return;
  if (event.key === 'f' || event.key === 'F' || event.key === 'Home') { event.preventDefault(); fitAll(); return; }
  const way = {ArrowRight: [1, 0], ArrowLeft: [-1, 0], ArrowDown: [0, 1], ArrowUp: [0, -1]}[event.key];
  if (!way || !S.selected) return;
  event.preventDefault();
  const from = M.nodes.get(S.selected);
  if (!from) return;
  let best = null, score = Infinity;
  for (const id of S.neighbors) {
    if (id === S.selected) continue;
    const node = M.nodes.get(id);
    if (!node) continue;
    const dx = node.x - from.x, dy = node.y - from.y, along = dx * way[0] + dy * way[1];
    if (along <= 0) continue;
    const cost = Math.hypot(dx, dy) * (1 + Math.abs(dx * way[1] - dy * way[0]) / (along + 1));
    if (cost < score) { score = cost; best = id; }
  }
  if (best) select(best, true);
});

/* ---------- selection: both views move together; the long text goes in the panel ---------- */
function select(id, fly) {
  if (!id || !S.elements.has(id)) return;
  S.selected = id;
  S.neighbors = new Set([id, ...S.joins.filter(join => join.receiver === id).map(join => join.provider),
    ...S.joins.filter(join => join.provider === id).map(join => join.receiver)]);
  if (G) {
    G.nodeColor(G.nodeColor());
    const node = G.graphData().nodes.find(item => item.id === id);
    if (fly && node && node.x !== undefined) {
      const distance = 90, ratio = 1 + distance / Math.hypot(node.x || 1, node.y || 1, node.z || 1);
      G.cameraPosition({x: node.x * ratio, y: node.y * ratio, z: node.z * ratio}, node, reduced() ? 0 : 900);
    }
  }
  focus2D(id, fly);
  showTab('object');
  renderObject(id);
}

function refsOf(refs) {
  return refs && refs.length ? h('div', {class: 'refs'}, refs.map(ref => `${ref.key}: ${ref.value}`).join(' · ')) : null;
}
function flagPill(thing) {
  return thing.flag ? h('span', {class: `pill flag-${thing.flag}`, title: thing.flag_note || null}, thing.flag) : null;
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
    join.function ? h('p', {class: 'fn'}, join.function) : null,
    join.relation ? h('p', {class: 'fn'}, join.relation) : null,
    join.observation ? h('p', {class: 'obs'}, join.observation) : null,
    join.non_goal ? h('p', {class: 'obs'}, `Not: ${join.non_goal}`) : null,
    join.flag ? h('div', {class: 'pills'}, flagPill(join), join.flag_note ? h('span', {class: 'empty'}, join.flag_note) : null) : null,
    refsOf(join.refs),
    (join.subtypes || []).map(subtype => h('div', {class: 'sub'}, h('b', {}, subtype.name || subtype.address), ' ',
      h('span', {class: 'refs'}, subtype.address), subtype.function ? h('div', {}, subtype.function) : null,
      subtype.observation ? h('div', {}, subtype.observation) : null, flagPill(subtype), refsOf(subtype.refs))));
}
function itemText(value) {
  if (value && typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value ?? '');
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
    for (const [title, found] of [['Properties that apply here', context.applying], ['Properties visible from above', context.visible]]) {
      if (!found.length) continue;
      box.append(h('div', {class: 'eyebrow'}, title), ...found.map(property => h('div', {class: 'item', style: {'--c': `var(${colorVar(property.layer)})`}},
        itemText(property.value), h('div', {class: 'refs'}, `${property.layer}${property.address && property.address !== element.address ? ' · at ' + property.address : ''}`),
        refsOf(property.refs))));
    }
  } catch (error) { /* the joins above still show; the node read names its own trouble in the toast */ toast(error.message); }
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
    if (record.prompt) pane.append(h('details', {}, h('summary', {class: 'eyebrow'}, 'The prompt it was made from'),
      h('pre', {class: 'prompt'}, record.prompt)));
  } catch (error) { pane.append(h('p', {class: 'empty'}, error.message)); }
}

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
const TABS = {object: '#p-object', prov: '#p-prov', corr: '#p-corr'};
function showTab(tab) {
  for (const [key, selector] of Object.entries(TABS)) { $(selector).hidden = key !== tab; $('#t-' + key).setAttribute('aria-selected', String(key === tab)); }
  if (tab === 'prov') renderProv();
  if (tab === 'corr') renderCorr();
}
for (const key of Object.keys(TABS)) $('#t-' + key).onclick = () => showTab(key);
let toastTimer;
function toast(message) { const box = $('#toast'); box.textContent = message; box.hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { box.hidden = true; }, 4200); }

/* ---------- loading: projects, metaforms, layers, then the graph page by page ---------- */
async function loadGraph() {
  const generation = ++S.loading;
  S.elements = new Map(); S.joins = [];
  let after = null;
  try {
    do {
      const page = await read('graph', {limit: 500, ...(after ? {after} : {}), ...viewLayers()});
      if (generation !== S.loading) return;
      for (const entry of page.elements) S.elements.set(entry.element.element_id, entry);
      S.joins.push(...page.joins);
      draw3D(); renderLegend();
      after = page.next;
    } while (after);
  } catch (error) { toast(error.message); }
  if (generation !== S.loading) return;
  S.loading = 0;
  renderLegend();
  await build2D();
  const keep = S.selected && S.elements.has(S.selected) ? S.selected : null;
  const start = keep || [...S.elements.values()].find(entry => entry.element.role === 'DE')?.element.element_id
    || S.elements.keys().next().value;
  if (start) select(start, false);
  else fill($('#p-object'), h('p', {class: 'empty'}, 'Nothing to show in these layers yet.'));
  if (!keep) setTimeout(() => G && G.zoomToFit(reduced() ? 0 : 800, 60), 1500);
}
async function loadMetaform() {
  S.view = null; S.selected = null;
  S.layers = (await read('layers', {limit: 0})).results;
  renderChips();
  if ($('#p-prov').hidden === false) renderProv();
  await loadGraph();
}
async function loadProject() {
  const metaforms = (await read('metaforms', {limit: 0})).results;
  S.metaforms = metaforms;
  const active = metaforms.find(item => item.active) || metaforms[0];
  S.metaform = active ? active.metaform_id : null;
  fill($('#mf'), ...metaforms.map(item => h('option', {value: item.metaform_id, selected: item === active}, item.name + (item.active ? ' · active' : ''))));
  await loadMetaform();
}
$('#proj').onchange = () => { S.project = $('#proj').value; location.hash = 'p=' + encodeURIComponent(S.project); loadProject(); };
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
}
main();
