/* The 2D map drawn by Mermaid with ELK: its state, its labels and shapes, and build2D. */
import '/page/app/views/lens.js';  // the part before runs first, so the parts run in the page's order
import {$, css, h, fill} from '/page/app/core/dom.js';
import {S, MEM} from '/page/app/core/reads.js';
import {underHiddenRoot} from '/page/app/header/layers.js';
import {noMetaform, noneYet} from '/page/app/header/admin.js';
import {figures2d} from '/page/app/figures/roam2d.js';
import {paintInUse, typeOf} from '/page/app/map3d/light.js';
import {shape2d, vertical2d, fitPin2d, fitPick2d, drawnAt, settle2D, mountSvg, placeIn, boundsOf,
  showBase} from '/page/app/map2d/fit.js';
import {IN, labelOf, drawInside, renderCrumbs} from '/page/app/map2d/inside.js';
import {drawMemory2d} from '/page/app/memory/graph.js';
import {setCam, aim2d} from '/page/app/map2d/camera.js';
import {showModes, hits2d} from '/page/app/map2d/hover.js';
import {ends2d, pointed, focus2D} from '/page/app/map2d/flow2d.js';

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
/* The 2D map fills its pane as well as ELK can draw it, P043. ELK lays the map out a few ways off screen: left to
 * right and top to bottom, and, for a map more than three layers deep, each of those folded, so a long run goes on in
 * rows or columns as text runs on in lines. A run is folded only where one edge alone joins its two halves, so a
 * branching part is never cut and a small tree is never folded on its own. The parts of the map not joined to each
 * other are laid out apart and packed together to a width to height ELK is given, `fitOptions2d`. A map whose few
 * layers each hold so many elements that the likelier direction comes out `narrow` times too long along its layers
 * for the pane is also laid out with each layer cut to fewer elements, so it fills the pane, `narrowFor`.
 *
 * ELK reaches the width to height it is given only roughly, so each way is first laid out for the pane's, and the way
 * that comes out best is laid out again for the width to height that corrects what it missed by, at most `refine`
 * times. The drawing kept is the one whose whole map can be drawn largest in the pane. A folded way is kept only when
 * it is `fold` times larger, as its runs turn back across the map, and the way drawn now is kept unless another is
 * `keep` times larger, so a pane near the point between two ways never turns the map back and forth. The setting
 * web_map_direction holds the map to one direction, across or down, unfolded, its parts still packed to the pane.
 *
 * The pane's shape is taken in steps, `fitStep2d`, each a quarter wider or narrower than the last, and a step is held
 * until the pane is well into the next, so a pane resized within one is not laid out again. The way chosen for each
 * step is kept with the map's layers when it was chosen, and the last `most` drawings with the map's text, so a pane
 * swapped back and forth gets its own picture again at once. A map whose layers change by a quarter is chosen for
 * again. Laying out stops after `budget` ms once one way is drawn, so a large map costs about that and no more. */
export const FIT2D = {config: null, step: Math.log(1.25), stay: 0.75, keep: 1.12, fold: 1.15, refine: 2, budget: 2000,
  narrow: 2, most: 16, chosen: new Map(), drawn: new Map()};
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
  const shown2d = [...S.elements].filter(([, {element}]) => !underHiddenRoot(element.address));
  const keys = new Map(shown2d.map(([id], index) => [id, `n${index}`]));
  // One edge between a join's receiver and each element it holds, drawn the way its information goes, as the Mermaid
  // export writes it: from the element served to the receiver when the receiver receives, `ends2d`.
  const drawn = S.joins.filter(join => keys.has(join.receiver))
    .flatMap(join => join.providers.filter(id => keys.has(id)).map(provider => ({join, provider})));
  const shape = shape2d(keys, drawn);
  const lines = mapLines(shown2d, keys, drawn);
  if (!S.elements.size || S.elements.size > MAP2D) { IN.length = 0; M.base = null; renderCrumbs(); }
  if (!S.elements.size) {
    return emptyIn(host, noMetaform() ? noneYet() : 'This metaform has no elements in these layers.');
  }
  if (S.elements.size > MAP2D) {
    M.svg = null; M.nodes = new Map(); M.edges = []; showModes();
    return emptyIn(host, `The 2D map lays out at most ${MAP2D} elements; these layers show ${S.elements.size}. `
      + 'The 3D view shows them all.');
  }
  let picked = null, layout = 'elk';
  try { picked = await fitPick2d(lines.join('\n'), shape, generation); }
  catch (error) {
    // ELK failing never leaves the pane empty: the same map is drawn with Mermaid's other layout, dagre, P043
    layout = 'dagre';
    try { picked = await dagre2d(lines, shape, generation); }
    catch (again) { return emptyIn(host, 'The 2D map could not be drawn.'); }
  }
  if (generation !== M.generation || !picked) return;
  const {result, way} = picked, vertical = way.vertical;
  M.way = way;  // the way the whole map is drawn now, which a later choice keeps unless another is clearly better
  // The whole map drawn again keeps its camera and eases from there to its mode's framing, VIEW-041.
  const was = keep && M.base && M.svg === M.base.svg && M.cam ? {...M.cam} : null;
  const inside = IN.length > 0 || Boolean(MEM.key);
  const before = was && !inside ? drawnAt(M.base) : null;  // where each node is drawn now, to move it from there
  const svg = mountSvg(result, host, inside);
  // what laid it out, which way, whether its layers run on in rows or columns, and the most a layer holds if narrowed
  Object.assign(svg.dataset, {layout, direction: vertical ? 'TB' : 'LR', wrapped: String(way.wrap),
    narrowed: String(way.narrow || 0)});
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
function mapLines(shown2d, keys, drawn) {
  const lines = [];
  for (const [id, {element}] of shown2d) {
    const shape = typeOf(element) && SHAPES2D[typeOf(element)], label = plain2d(labelOf(element));
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
  const nodes = new Map();
  for (const [id, key] of keys) {
    const group = svg.querySelector(`[id*="-flowchart-${key}-"]`);
    const {element} = S.elements.get(id);
    if (group) placeIn(nodes, id, group, element.address, element.open_work,
      labelOf(element) === element.address ? element.address : `${labelOf(element)}\n${element.address}`);
  }
  return nodes;
}
/* Each edge drawn, its path marked with its join's open work and its arrowheads, `pointed`. */
function edgesIn(svg, drawn) {
  const edges = drawn.map(({join, provider}, index) => ({join, provider,
    path: svg.querySelector(`[data-id="e${index}"]`) || svg.querySelectorAll('.edgePaths path')[index]}));
  for (const edge of edges) {
    for (const condition of edge.join.open_work || []) edge.path?.classList.add(`work-${condition}`);
  }
  for (const edge of edges) pointed(edge);
  return edges;
}
