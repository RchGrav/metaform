/* The 2D map drawn by Mermaid with ELK: its state, its labels and shapes, and build2D. */
import '/page/app/views/lens.js';  // the part before runs first, so the parts run in the page's order
import {$, css, h, fill, reduced} from '/page/app/core/dom.js';
import {S, MEM} from '/page/app/core/reads.js';
import {underHiddenRoot} from '/page/app/header/layers.js';
import {noMetaform, noneYet} from '/page/app/header/admin.js';
import {drawEmpty} from '/page/app/intake/intake.js';
import {figures2d} from '/page/app/figures/roam2d.js';
import {paintInUse, typeOf, paceOf} from '/page/app/map3d/light.js';
import {shape2d, vertical2d, fitPin2d, fitPick2d, drawnAt, settle2D, mountSvg, placeIn, measureIn, boundsOf,
  showBase} from '/page/app/map2d/fit.js';
import {IN, labelOf, drawInside, renderCrumbs} from '/page/app/map2d/inside.js';
import {drawMemory2d} from '/page/app/memory/graph.js';
import {setCam, aim2d} from '/page/app/map2d/camera.js';
import {hits2d} from '/page/app/map2d/hover.js';
import {ends2d, pointed, focus2D} from '/page/app/map2d/flow2d.js';
import {heldName, workShown} from '/page/app/graph/data.js';
import {depthView} from '/page/app/keys/walk.js';

/* ---------- 2D: the whole map, short names, no text on the edges; the camera moves node to node ---------- */
export const M = {svg: null, nodes: new Map(), edges: [], cam: null, to: null, bounds: null, frame: 0, generation: 0};
// the most elements Mermaid lays out; above it the 2D map is not drawn, BUILD-QUESTIONS Q52
export const MAP2D = 5000;
/* Mermaid lays the 2D map out with ELK, the Eclipse Layout Kernel bundled in its release and its default layout, P043.
 * Its nodes are placed by network simplex, which keeps the edges short and straight; its crossings are reduced by ELK's
 * own default, the layer sweep, which Mermaid leaves as it is. Mermaid refuses a diagram over 500 edges or 50,000
 * characters, so its limits are raised to the most the 2D map writes: MAP2D labels of at most 40 characters a line
 * and EDGES2D edges of at most 32. */
const EDGES2D = MAP2D * 10;
const ELK2D = {layout: 'elk', elk: {nodePlacementStrategy: 'NETWORK_SIMPLEX'}, maxEdges: EDGES2D,
  maxTextSize: MAP2D * 40 + EDGES2D * 32};
/* The 2D map fills its pane as well as ELK can draw it, P043. ELK lays the map out several ways off screen, `waysFor`:
 * left to right and top to bottom; for a map more than three layers deep, left to right folded into rows, so a long
 * run goes on in the next row as text runs on in lines, ELK's wrapping with the `correction` it is given; for a map of
 * at most `small` elements, top to bottom with its layers held narrow; and, for a map whose few layers each hold so
 * many elements that the likelier direction comes out `narrow` times too long along its layers for the pane, with
 * each layer cut to fewer elements, `narrowFor`. The parts of the map not joined to each other are laid out apart and
 * packed together to the pane's width to height, `fitOptions2d`. The drawing kept is the one whose whole map is drawn
 * largest in the pane at full fit, with the fit's margin and the room at its foot, so the map fills as much of the
 * pane as it can. The setting web_map_direction holds the map to one direction, across or down, unfolded.
 *
 * The map is chosen for again whenever its text changes, as a node or an edge comes or goes, and whenever the pane
 * turns into another step of width to height, `fitStep2d`, each a quarter wider or narrower than the last; a step is
 * held until the pane is well into the next, so a pane resized within one is not laid out again. The choice is made
 * while the map drawn before stays on the page, and replaces it once made, `fitPick2d`. The way chosen for the same
 * text in the same step is kept, and the last `most` drawings, so a pane swapped back and forth, or a map redrawn as
 * it was, gets its own picture again at once. Laying out stops after `budget` ms once one way is drawn, so a large map
 * costs about that and no more; `since` is when the first choice not yet shown began. A map drawn where none is shown,
 * as at load, is drawn in one way and shown, and the search goes on after, each layout in an idle moment or after
 * `wait` ms; the ways chosen are kept in this browser for each base, so a reload draws the same map once, `kept2d`. */
export const FIT2D = {config: null, step: Math.log(1.25), stay: 0.75, budget: 6000, correction: 0.5, small: 100,
  narrow: 2, most: 24, wait: 1000, chosen: new Map(), drawn: new Map(), since: null, laid: new Map()};
/* A name as a 2D label: the characters Mermaid would read as its own taken out, and a name longer than `most` cut at
 * the last break between words that keeps most of it, with an ellipsis, so a label never ends in half a word and always
 * says it goes on. The whole name is in the panel and in the 3D map's tooltip. */
export function plain2d(text, most = 30) {
  const plain = String(text || '').replace(/["[\]{}()<>|#;`]/g, '').trim();
  if (plain.length <= most) return plain;
  const cut = plain.slice(0, most - 1), space = cut.lastIndexOf(' ');
  return (space >= most * 0.6 ? cut.slice(0, space) : cut).replace(/[\s,.;:–—-]+$/, '') + '…';
}
export let mermaidReady = false;
export function setMermaidReady(value) { mermaidReady = value; }
/* The Mermaid shape of each artifact type, as the 3D map's: a process box for code, a document, a display for media,
 * a database cylinder for data, stacked boxes for a collection, input and output parallelograms for upstream and
 * downstream. */
const SHAPES2D = {code: 'rect', document: 'doc', media: 'curv-trap', data: 'cyl', collection: 'st-rect',
  upstream: 'lean-r', downstream: 'lean-l'};
/* `branch`: what changed is a branch opened or closed, keys/walk.js FOCUS and a click breaking out a node's next level,
 * so the map is laid out at once in the way it is drawn now, without choosing among the ways again, `fitPick2d`. */
export async function build2D(keep = true, branch = false) {
  const generation = ++M.generation;
  const host = $('#viewport');
  if (!window.mermaid) return emptyIn(host, 'The 2D map could not load.');
  if (!mermaidReady) startMermaid();
  const depth = depthView();  // the parts the depth shows, as the 3D map draws them, VIEW-051
  const shown2d = [...S.elements].filter(([id, {element}]) => !underHiddenRoot(element.address)
    && (!depth.shown || depth.shown.has(id)));
  const keys = new Map(shown2d.map(([id], index) => [id, `n${index}`]));
  // One edge between a join's receiver and each element it holds, drawn the way its information goes, as the Mermaid
  // export writes it: from the element served to the receiver when the receiver receives, `ends2d`.
  const drawn = S.joins.filter(join => keys.has(join.receiver))
    .flatMap(join => join.providers.filter(id => keys.has(id)).map(provider => ({join, provider})));
  const shape = shape2d(keys, drawn);
  const lines = mapLines(shown2d, keys, drawn, depth.held);
  if (!S.elements.size || S.elements.size > MAP2D) { IN.length = 0; M.base = null; renderCrumbs(); }
  if (!S.elements.size) {
    return emptyIn(host, noMetaform() ? noneYet() : 'This metaform has no elements in these layers.');
  }
  if (S.elements.size > MAP2D) {
    M.svg = null; M.nodes = new Map(); M.edges = [];
    return emptyIn(host, `The 2D map lays out at most ${MAP2D} elements; these layers show ${S.elements.size}. `
      + 'The 3D view shows them all.');
  }
  let picked = null, layout = 'elk';
  try { picked = await choosing(() => fitPick2d(lines.join('\n'), shape, generation, branch)); }
  catch (error) {
    // ELK failing never leaves the pane empty: the same map is drawn with Mermaid's other layout, dagre, P043
    layout = 'dagre';
    try { picked = await choosing(() => dagre2d(lines, shape, generation)); }
    catch (again) { return emptyIn(host, 'The 2D map could not be drawn.'); }
  }
  if (generation !== M.generation || !picked) return;
  // the map read again while it was chosen for, as a load begins with none: the build that load makes draws it
  if ([...keys.keys()].some(id => !S.elements.has(id))) return;
  const {way} = picked;
  M.way = way;  // the way the whole map is drawn now, which a later choice tries first
  // a choice cut short by its budget is made again once it is shown, going on with the ways not drawn, `fitPick2d`;
  // the page counts as opening until that choice has begun, `choosing`
  if (picked.hurried) S.opening++;
  S.opening++;  // the page is opening until the drawing chosen is shown, as while it is chosen, `choosing`
  try { await placed2d(generation, keep, host, keys, drawn, picked, layout); }
  finally {  // the search goes on once this drawing is shown, or has given way to another
    opened2d();
    if (picked.hurried) {
      setTimeout(() => { try { if (generation === M.generation) build2D(); } finally { opened2d(); } });
    }
  }
}
/* A drawing chosen, put on the 2D map: the map's nodes and edges read from it, and the view kept, `build2D`. */
async function placed2d(generation, keep, host, keys, drawn, {result, way}, layout) {
  const vertical = way.vertical;
  const inside = IN.length > 0 || Boolean(MEM.key);
  // the drawing shown chosen again, as a search that goes on after the map is shown keeps it: nothing is drawn again,
  // and the marks on it are kept up to date where they change, `markWork2d`
  if (keep && M.base?.result === result && (inside || M.svg === M.base.svg)) return;
  // The drawing is put on the page out of sight and read in steps, each in a task of its own, so the page answers
  // between them: its nodes measured and marked, then its edges; it is shown once it is whole. A build begun meanwhile
  // takes over, and this drawing goes.
  await new Promise(go => setTimeout(go));  // Mermaid's own last step ran in the task before
  if (generation !== M.generation) return;
  const svg = mountSvg(result, host, true);
  // what laid it out, which way, whether and where its layers run on in rows, the most a layer holds if narrowed, and
  // the layering ELK was given, if any
  Object.assign(svg.dataset, {layout, direction: vertical ? 'TB' : 'LR', wrapped: String(way.wrap || false),
    narrowed: String(way.narrow || 0), layering: `${way.layering || ''}${way.bound || ''}`});
  const gone = async () => {
    await new Promise(go => setTimeout(go));
    if (generation === M.generation && [...keys.keys()].every(id => S.elements.has(id))) return false;
    svg.remove();
    return true;
  };
  if (await gone()) return;
  const nodes = nodesIn(svg, keys);
  if (await gone()) return;
  const edges = edgesIn(svg, drawn);
  hits2d(edges);
  if (await gone()) return;
  if (!inside) svg.style.visibility = '';
  // The whole map drawn again keeps its camera and eases from there to its mode's framing, VIEW-041.
  const was = keep && M.base && M.svg === M.base.svg && M.cam ? {...M.cam} : null;
  const before = was && !inside ? drawnAt(M.base) : null;  // where each node is drawn now, to move it from there
  // The base map is kept while a node is entered and shown again as it was, VIEW-016.
  M.base = {svg, nodes, edges, bounds: boundsOf(svg), vertical, cam: null, result};
  figures2d(S.tickets || []);
  if (MEM.key) { svg.remove(); svg.style.visibility = ''; await drawMemory2d(); return; }
  if (inside) { svg.remove(); svg.style.visibility = ''; await drawInside(); return; }
  showBase();
  paintInUse();
  if (was) setCam(was);
  if (before) settle2D(before, nodes, svg);
  // the view framed, and the selection's flow drawn, each in a task of its own, as is what follows the drawing
  await new Promise(go => setTimeout(go));
  if (generation !== M.generation) return;
  if (S.selected) focus2D(S.selected, false); else aim2d();  // drawn again, the view stays, VIEW-041
  await new Promise(go => setTimeout(go));
}
/* The map drawn again for changes that come while it is being laid out, CLAUDE.md section 2's rule 4: a change that
 * arrives while a drawing is pending is merged into one more drawing after it, so a burst of agents' writes costs one
 * layout after the one under way, not one each. */
const SOON2D = {pending: null, again: false};
export function build2DSoon() {
  if (SOON2D.pending) { SOON2D.again = true; return SOON2D.pending; }
  SOON2D.pending = (async () => {
    try { do { SOON2D.again = false; await build2D(); } while (SOON2D.again); }
    finally { SOON2D.pending = null; }
  })();
  return SOON2D.pending;
}
/* The nodes of the 2D map whose open work or progress changed, marked where they are drawn, MAP-046 and VIEW-035, and
 * the edges of every join, whose work is on its edges: the map is not laid out or drawn again for a ticket, since its
 * text, what Mermaid lays out, does not change. Each class or pace is written only where it differs. */
export function markWork2d(changed) {
  const base = M.base;
  if (!base || !changed.size) return;
  const work = workShown();
  for (const id of changed) {
    const node = base.nodes.get(id);
    if (node) workClasses(node.g, work.get(id) || []);
    if (node && S.progress?.get(id)) node.g.style.setProperty('--pace', `${paceOf({id})}s`);
  }
  for (const edge of base.edges) if (edge.path && changed.has(edge.join.receiver)) {
    workClasses(edge.path, edge.join.open_work || []);
  }
}
function workClasses(part, work) {
  let changed = false;
  for (const name of [...part.classList]) {
    if (name.startsWith('work-') && !work.includes(name.slice(5))) { part.classList.remove(name); changed = true; }
  }
  for (const condition of work) {
    if (!part.classList.contains(`work-${condition}`)) { part.classList.add(`work-${condition}`); changed = true; }
  }
  if (changed) glow2d(part);
}
/* A glow that pulses on the 2D map, a broken part's flash and the glow of a message, a question or a part under
 * construction, is drawn by a copy of the part beneath it with the glow at its brightest, whose opacity pulses, and
 * not by a pulsing filter: a filter that changes every frame made the browser sort the whole drawing into layers again
 * each frame, 33 ms of every frame at 1,000 elements (2026-10-17), where an opacity that changes repaints the copy
 * alone. The part keeps its own colours' pulse and the faint glow the pulse began from, app.css `.glowed`. A copy is
 * made when the part's work is marked and goes with it; with reduced motion there is none, as nothing pulses. */
const SVG2D = 'http://www.w3.org/2000/svg';
const FLASHED = ['work-broken', 'work-trouble'], PULSED = ['work-message', 'work-question', 'work-under-construction'];
export function glow2d(part) {
  const node = part.tagName === 'g', list = part.classList;
  const old = node ? part.querySelectorAll(':scope > .glow2d') : [part.previousElementSibling];
  for (const copy of old) if (copy?.classList.contains('glow2d')) copy.remove();
  const flash = node && FLASHED.some(name => list.contains(name)), pulse = PULSED.some(name => list.contains(name));
  list.toggle('glowed', flash || pulse);
  if (reduced() || !(flash || pulse)) return;
  if (flash) {
    const rect = part.querySelector(':scope > rect');
    if (rect) rect.before(glowCopy(rectPath(rect), 'glow2d'));
  }
  if (pulse && node) {
    const copy = document.createElementNS(SVG2D, 'g');
    for (const child of part.children) if (!child.classList.contains('glow2d')) copy.append(child.cloneNode(true));
    // its boxes as paths, so the node's own box is the first `rect` in it, as it was before it glowed
    for (const box of copy.querySelectorAll('rect')) box.replaceWith(rectPath(box));
    part.prepend(glowCopy(copy, 'glow2d pulse2d'));
  } else if (pulse) {
    const pulsing = PULSED.filter(name => list.contains(name)).join(' ');
    const copy = glowCopy(part.cloneNode(false), `glow2d pulse2d ${pulsing}`);
    for (const name of ['marker-end', 'marker-start', 'data-id']) copy.removeAttribute(name);
    part.before(copy);
  }
}
/* A node's box as a path of the same outline, its corners rounded as the box's are: the flash's copy, a path so the
 * node's own box stays the one `rect` it has. */
function rectPath(rect) {
  const at = name => Number(rect.getAttribute(name)) || 0;
  const x = at('x'), y = at('y'), w = at('width'), h = at('height');
  const rx = Math.min(w / 2, at('rx') || at('ry')), ry = Math.min(h / 2, at('ry') || at('rx'));
  const path = document.createElementNS(SVG2D, 'path');
  path.setAttribute('d', rx || ry
    ? `M${x + rx},${y}H${x + w - rx}A${rx},${ry} 0 0 1 ${x + w},${y + ry}V${y + h - ry}A${rx},${ry} 0 0 1 ${x + w - rx},`
      + `${y + h}H${x + rx}A${rx},${ry} 0 0 1 ${x},${y + h - ry}V${y + ry}A${rx},${ry} 0 0 1 ${x + rx},${y}Z`
    : `M${x},${y}H${x + w}V${y + h}H${x}Z`);
  if (rect.hasAttribute('transform')) path.setAttribute('transform', rect.getAttribute('transform'));
  return path;
}
function glowCopy(copy, classes) {
  copy.setAttribute('class', classes);
  copy.removeAttribute('id');
  copy.removeAttribute('style');
  for (const inner of copy.querySelectorAll('[id]')) inner.removeAttribute('id');
  return copy;
}
/* A choice of the 2D map's layout counts as opening, as a load does, so loaded() is not true while the map on the page
 * is still to be replaced by the one chosen for it, `fitPick2d`. */
async function choosing(work) {
  S.opening++;
  try { return await work(); } finally { opened2d(); }
}
function opened2d() { S.opening--; if (!S.opening) drawEmpty(); }
/* A word in the empty 2D pane, in place of the map. */
function emptyIn(host, text) {
  fill(host, h('p', {class: 'empty', style: {padding: '16px'}}, text));
}
/* ELK lays the 2D map out in a worker, off the page's thread, so a layout of a large map that takes seconds never
 * holds the page: the release's own elk-worker.min.js, of the elkjs Mermaid bundles, vendor/README.md. Mermaid makes an
 * ELK for each drawing and asks it for a worker, `mermaidElk`, which the vendored mermaid.min.js was changed to pass
 * on; each gets a port onto the one worker the page keeps, its messages' ids made the page's own so the answers go back
 * to the drawing that asked. A worker that cannot start fails each layout it was given, and the 2D map is drawn with
 * dagre as for any failure of ELK, `build2D`. */
const ELK = {worker: null, next: 1, waiting: new Map(), asked: null, answer: null};
function elkPort() {
  return {onmessage: null, terminate() {}, postMessage(message) { elkSend(this, message); }};
}
function elkSend(port, message) {
  if (!ELK.worker) {
    ELK.worker = new Worker('/vendor/elk-worker.min.js');
    ELK.worker.onmessage = elkHeard;
    ELK.worker.onerror = elkFailed;
  }
  const id = ELK.next++, layout = message.cmd === 'layout';
  ELK.waiting.set(id, {port, id: message.id, layout});
  // the graph as data alone: Mermaid's ELK graph carries its own drawing functions, which cannot go to a worker and
  // which ELK never reads; what ELK lays out comes back as a new graph, which Mermaid reads its places from
  const sent = JSON.parse(JSON.stringify({...message, id}));
  if (layout) { ELK.asked = sent; ELK.answer = null; }  // the last layout asked, which `elkLaid` reads
  ELK.worker.postMessage(sent);
}
function elkHeard({data}) {
  const asked = ELK.waiting.get(data.id);
  if (!asked) return;
  ELK.waiting.delete(data.id);
  if (asked.layout && !data.error) ELK.answer = data.data;
  asked.port.onmessage?.({data: {...data, id: asked.id}});
}
function elkFailed(event) {
  event.preventDefault?.();
  ELK.worker?.terminate();
  ELK.worker = null;
  const error = new Error('The 2D layout could not start.');
  for (const asked of ELK.waiting.values()) asked.port.onmessage?.({data: {id: asked.id, error}});
  ELK.waiting.clear();
}
globalThis.mermaidElk = () => ({workerFactory: elkPort});
/* Mermaid's own work on the page's thread, its steps given turns, `mermaidStep`, which the vendored mermaid.min.js was
 * changed to call, vendor/README.md: each node measured, and each node and edge drawn, takes its turn, and once a turn
 * has run STEP.slice ms the next waits for the next task, so the page answers between them however large the map: a
 * drawing of 1,000 elements held the page's thread for a second at once, one of 5,000 for many (2026-10-17). The steps
 * run in the order Mermaid gives them, so the drawing is the same; only the time it takes is spread. */
const STEP = {slice: 25, since: 0, busy: false, paused: [], waiting: [], posted: false, channel: new MessageChannel()};
STEP.channel.port1.onmessage = () => {
  STEP.posted = false;
  STEP.since = performance.now();
  const paused = STEP.paused.splice(0);
  for (const go of paused) go();
  if (!STEP.busy && STEP.waiting.length) { STEP.busy = true; STEP.waiting.shift()(); }
};
const stepNext = () => { if (!STEP.posted) { STEP.posted = true; STEP.channel.port2.postMessage(0); } };
const stepFits = () => performance.now() - STEP.since < STEP.slice;
globalThis.mermaidStep = {
  // a step between others: on at once while the slice lasts, else in the next task
  pause: () => (stepFits() ? null : new Promise(go => { STEP.paused.push(go); stepNext(); })),
  // a node's measure, one at a time: at once while the slice lasts and none is under way, else in its turn
  enter: () => {
    if (!STEP.busy && !STEP.waiting.length && stepFits()) { STEP.busy = true; return null; }
    return new Promise(go => { STEP.waiting.push(go); if (!STEP.busy) stepNext(); });
  },
  leave: () => {
    STEP.busy = false;
    if (!STEP.waiting.length) return;
    if (stepFits()) { STEP.busy = true; STEP.waiting.shift()(); } else stepNext();
  },
};
/* The last layout Mermaid asked of ELK and the graph ELK gave back, taken once: what a drawing of the map was laid
 * out from, so the other ways to lay the same map out are laid out from it in the worker alone, `fitPick2d`. */
export function elkLaid() {
  const laid = ELK.asked && ELK.answer ? {asked: ELK.asked, answer: ELK.answer} : null;
  ELK.asked = ELK.answer = null;
  return laid;
}
/* A layout asked of the worker directly: the graph ELK gives back, or a failure. */
export function elkLayout(message) {
  return new Promise((resolve, reject) => {
    elkSend({onmessage: ({data}) => (data.error ? reject(data.error) : resolve(data.data))}, message);
  });
}
/* Mermaid set up for the 2D map in the theme's colors, once for each theme. */
function startMermaid() {
  FIT2D.config = {startOnLoad: false, securityLevel: 'strict', theme: 'base', htmlLabels: false, ...ELK2D,
    flowchart: {htmlLabels: false, useMaxWidth: false, curve: 'basis', nodeSpacing: 28, rankSpacing: 45},
    themeVariables: {background: css('--ground'), primaryColor: css('--node'), primaryBorderColor: css('--node-line'),
      primaryTextColor: css('--text'), lineColor: css('--edge'), fontFamily: 'IBM Plex Sans, sans-serif',
      fontSize: '13px', tertiaryColor: css('--group')}};
  window.mermaid.initialize(FIT2D.config);
  FIT2D.drawn.clear();  // the drawings kept were drawn in the colors before
  mermaidReady = true;
}
/* The map as Mermaid reads it, without its direction, which the layout chosen for the pane gives it, `fitPick2d`:
 * each element shown in its type's shape, and each edge, numbered so its path is found again. */
function mapLines(shown2d, keys, drawn, held) {
  const lines = [];
  for (const [id, {element}] of shown2d) {
    const shape = typeOf(element) && SHAPES2D[typeOf(element)];
    const label = heldName(plain2d(labelOf(element)), held.get(id));
    lines.push(shape ? `${keys.get(id)}@{ shape: ${shape}, label: "${label}" }` : `${keys.get(id)}["${label}"]`);
  }
  drawn.forEach(({join, provider}, index) => {
    const [from, to] = ends2d(join, provider);
    lines.push(`${keys.get(from)} e${index}@--> ${keys.get(to)}`);
  });
  return lines;
}
/* The map drawn with dagre, the way the pane's shape or web_map_direction says. */
async function dagre2d(lines, shape, generation) {
  const pin = fitPin2d(), down = pin === 'down' || (pin !== 'across' && vertical2d(shape, M.way?.vertical ?? null));
  const text = `---\nconfig:\n  layout: dagre\n---\n${down ? 'flowchart TB' : 'flowchart LR'}\n${lines.join('\n')}`;
  const result = await window.mermaid.render(`map2d${generation}d`, text, $('#draw'));
  return {way: {vertical: down, wrap: false}, result};
}
/* Each element's drawn group, by its id, titled with its name and address. */
function nodesIn(svg, keys) {
  const nodes = new Map(), groups = groupsByKey(svg), work = workShown();  // a join's work on its receiver
  // every node measured first, then every node marked, so the drawing is laid out once and not once a node
  const measured = new Map();
  for (const key of keys.values()) if (groups.has(key)) measured.set(key, measureIn(groups.get(key)));
  for (const [id, key] of keys) {
    const group = groups.get(key);
    const {element} = S.elements.get(id);
    if (group) placeIn(nodes, id, group, element.address, work.get(id),
      labelOf(element) === element.address ? element.address : `${labelOf(element)}\n${element.address}`,
      measured.get(key));
  }
  return nodes;
}
/* For each key, the first part of the drawing, in its order, whose id holds `-flowchart-<key>-`, found in one walk of
 * it: a search of the whole drawing for each node made a build cost the nodes times the drawing. */
function groupsByKey(svg) {
  const found = new Map(), mark = '-flowchart-';
  for (const part of svg.querySelectorAll(`[id*="${mark}"]`)) {
    const id = part.id;
    for (let at = id.indexOf(mark); at >= 0; at = id.indexOf(mark, at + 1)) {
      const rest = id.slice(at + mark.length);
      for (let end = rest.indexOf('-'); end >= 0; end = rest.indexOf('-', end + 1)) {
        const key = rest.slice(0, end);
        if (!found.has(key)) found.set(key, part);
      }
    }
  }
  return found;
}
/* Each edge drawn, its path marked with its join's open work and its arrowheads, `pointed`. */
function edgesIn(svg, drawn) {
  // the drawing's parts by their data-id, the first of each, and its edge paths in order, each read once
  const byData = new Map(), paths = svg.querySelectorAll('.edgePaths path');
  for (const part of svg.querySelectorAll('[data-id]')) {
    if (!byData.has(part.dataset.id)) byData.set(part.dataset.id, part);
  }
  const edges = drawn.map(({join, provider}, index) => ({join, provider,
    path: byData.get(`e${index}`) || paths[index]}));
  for (const edge of edges) {
    for (const condition of edge.join.open_work || []) edge.path?.classList.add(`work-${condition}`);
    if (edge.path && edge.join.open_work?.length) glow2d(edge.path);
  }
  for (const edge of edges) pointed(edge);
  return edges;
}
