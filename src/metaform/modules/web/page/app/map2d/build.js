/* The 2D map drawn by Mermaid with ELK: its state, its labels and shapes, and build2D. */
import '/page/app/views/lens.js';  // the part before runs first, so the parts run in the page's order
import {$, css, h, fill} from '/page/app/core/dom.js';
import {S, MEM} from '/page/app/core/reads.js';
import {underHiddenRoot} from '/page/app/header/layers.js';
import {noMetaform, noneYet} from '/page/app/header/admin.js';
import {drawEmpty} from '/page/app/intake/intake.js';
import {figures2d} from '/page/app/figures/roam2d.js';
import {paintInUse, typeOf} from '/page/app/map3d/light.js';
import {shape2d, vertical2d, fitPin2d, fitPick2d, drawnAt, settle2D, mountSvg, placeIn, boundsOf,
  showBase} from '/page/app/map2d/fit.js';
import {IN, labelOf, drawInside, renderCrumbs} from '/page/app/map2d/inside.js';
import {drawMemory2d} from '/page/app/memory/graph.js';
import {setCam, aim2d} from '/page/app/map2d/camera.js';
import {hits2d} from '/page/app/map2d/hover.js';
import {ends2d, pointed, focus2D} from '/page/app/map2d/flow2d.js';
import {heldName} from '/page/app/graph/data.js';
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
  narrow: 2, most: 24, wait: 1000, chosen: new Map(), drawn: new Map(), since: null};
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
export async function build2D(keep = true) {
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
  try { picked = await choosing(() => fitPick2d(lines.join('\n'), shape, generation)); }
  catch (error) {
    // ELK failing never leaves the pane empty: the same map is drawn with Mermaid's other layout, dagre, P043
    layout = 'dagre';
    try { picked = await choosing(() => dagre2d(lines, shape, generation)); }
    catch (again) { return emptyIn(host, 'The 2D map could not be drawn.'); }
  }
  if (generation !== M.generation || !picked) return;
  // the map read again while it was chosen for, as a load begins with none: the build that load makes draws it
  if ([...keys.keys()].some(id => !S.elements.has(id))) return;
  const {result, way} = picked, vertical = way.vertical;
  M.way = way;  // the way the whole map is drawn now, which a later choice tries first
  // a choice cut short by its budget is made again once it is shown, going on with the ways not drawn, `fitPick2d`;
  // the page counts as opening until that choice has begun, `choosing`
  if (picked.hurried) {
    S.opening++;
    setTimeout(() => { try { if (generation === M.generation) build2D(); } finally { opened2d(); } });
  }
  // The whole map drawn again keeps its camera and eases from there to its mode's framing, VIEW-041.
  const was = keep && M.base && M.svg === M.base.svg && M.cam ? {...M.cam} : null;
  const inside = IN.length > 0 || Boolean(MEM.key);
  const before = was && !inside ? drawnAt(M.base) : null;  // where each node is drawn now, to move it from there
  const svg = mountSvg(result, host, inside);
  // what laid it out, which way, whether and where its layers run on in rows, the most a layer holds if narrowed, and
  // the layering ELK was given, if any
  Object.assign(svg.dataset, {layout, direction: vertical ? 'TB' : 'LR', wrapped: String(way.wrap || false),
    narrowed: String(way.narrow || 0), layering: `${way.layering || ''}${way.bound || ''}`});
  const nodes = nodesIn(svg, keys), edges = edgesIn(svg, drawn);
  hits2d(edges);
  // The base map is kept while a node is entered and shown again as it was, VIEW-016.
  M.base = {svg, nodes, edges, bounds: boundsOf(svg), vertical, cam: null};
  figures2d(S.tickets || []);
  if (MEM.key) { svg.remove(); svg.style.visibility = ''; await drawMemory2d(); return; }
  if (inside) { svg.remove(); svg.style.visibility = ''; await drawInside(); return; }
  showBase();
  paintInUse();
  if (was) setCam(was);
  if (before) settle2D(before, nodes, svg);
  if (S.selected) focus2D(S.selected, false); else aim2d();  // drawn again, the view stays, VIEW-041
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
  const nodes = new Map(), groups = groupsByKey(svg);
  for (const [id, key] of keys) {
    const group = groups.get(key);
    const {element} = S.elements.get(id);
    if (group) placeIn(nodes, id, group, element.address, element.open_work,
      labelOf(element) === element.address ? element.address : `${labelOf(element)}\n${element.address}`);
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
  }
  for (const edge of edges) pointed(edge);
  return edges;
}
