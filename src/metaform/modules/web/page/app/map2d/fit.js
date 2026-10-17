/* How the 2D map fits its pane, P043: the direction likelier to fit, ELK's options, the fit picked and checked
 * again, and the move between layouts. */
import '/page/app/map2d/build.js';  // the part before runs first, so the parts run in the page's order
import {$, reduced, fill} from '/page/app/core/dom.js';
import {FRAMED, S} from '/page/app/core/reads.js';
import {paceOf} from '/page/app/map3d/light.js';
import {MARGIN} from '/page/app/camera/flight.js';
import {VIEW, PEEK} from '/page/app/views/settings.js';
import {M, FIT2D, build2D, glow2d, elkLaid, elkLayout} from '/page/app/map2d/build.js';
import {renderCrumbs} from '/page/app/map2d/inside.js';
import {frame, arrive, into, setCam, stopCam, moveCam, area2d, focus2d, aim2d,
  center2d, foot2d} from '/page/app/map2d/camera.js';
import {clicked2d} from '/page/app/map2d/flow2d.js';
import {menu} from '/page/app/board/messages.js';
import {getJson} from '/page/app/panel/prompts.js';

/* The map's layers as ELK ranks them, near enough to choose its direction before it is drawn, P043: each element at
 * the longest path to it from an element nothing points to, with the edges that close a loop left out, as ELK breaks
 * loops. `layers` is how many there are, `widest` the most elements in one and `nodes` how many elements in all. */
export function shape2d(keys, drawn) {
  const {kept, into} = loopsBroken(keys, drawn), rank = ranksOf(keys, kept, into);
  const counts = new Map();
  for (const layer of rank.values()) counts.set(layer, (counts.get(layer) || 0) + 1);
  return {layers: Math.max(1, counts.size), widest: Math.max(1, ...counts.values()), nodes: keys.size};
}
/* The edges kept once those that close a loop are left out, each element's out of it, and how many point into each. */
function loopsBroken(keys, drawn) {
  const out = new Map([...keys.keys()].map(id => [id, []])), kept = new Map([...keys.keys()].map(id => [id, []]));
  const into = new Map([...keys.keys()].map(id => [id, 0])), seen = new Map();
  for (const {join, provider} of drawn) out.get(join.receiver).push(provider);
  for (const root of keys.keys()) {  // depth first, without recursion, so a long chain does not overflow the stack
    if (seen.has(root)) continue;
    const stack = [[root, 0]];
    seen.set(root, 'open');
    while (stack.length) {
      const top = stack.at(-1), next = out.get(top[0])[top[1]++];
      if (next === undefined) { seen.set(top[0], 'done'); stack.pop(); continue; }
      if (seen.get(next) === 'open') continue;  // it closes a loop
      kept.get(top[0]).push(next);
      into.set(next, into.get(next) + 1);
      if (!seen.has(next)) { seen.set(next, 'open'); stack.push([next, 0]); }
    }
  }
  return {kept, into};
}
/* Each element's layer: the longest path to it from an element nothing points to, along the edges kept. */
function ranksOf(keys, kept, into) {
  const rank = new Map(), queue = [...keys.keys()].filter(id => !into.get(id));
  for (const id of queue) rank.set(id, 0);
  for (let at = 0; at < queue.length; at++) for (const next of kept.get(queue[at])) {
    rank.set(next, Math.max(rank.get(next) ?? 0, rank.get(queue[at]) + 1));
    into.set(next, into.get(next) - 1);
    if (!into.get(next)) queue.push(next);
  }
  return rank;
}
/* Which direction, top to bottom or left to right, is likelier to fit the pane, reckoned before anything is drawn: the
 * way ELK lays out first, `fitPick2d`, and the direction dagre draws if ELK fails. Each drawing's width to height is
 * reckoned from its layers, at the size Mermaid draws a 2D label and about the room ELK leaves between nodes and
 * between layers. Once drawn one way, the other must fit clearly better. */
const BOX2D = {w: 152, h: 45, across: 40, between: 50, clearly: 0.15};
export function vertical2d(shape, was = null) {
  const area = area2d();
  if (!shape || !area.width || !area.height) return was ?? true;
  const {layers, widest} = shape, {w, h: tall, across, between, clearly} = BOX2D;
  const down = (widest * w + (widest - 1) * across) / (layers * tall + (layers - 1) * between);
  const side = (layers * w + (layers - 1) * between) / (widest * tall + (widest - 1) * across);
  const pane = area.width / area.height, miss = ratio => Math.abs(Math.log(ratio / pane));
  return miss(down) <= miss(side) + (was === null ? 0 : was ? clearly : -clearly);
}
/* The most elements a layer may hold so a map whose layers are too wide for the pane fills it, VIEW-008, reckoned from
 * the likelier direction as ELK drew it, `drawn`: a few layers holding many elements each draw a narrow column left
 * to right or a thin band top to bottom, which neither folding nor packing reshapes, as both work across layers.
 * Cutting each layer into k makes the drawing about k times longer across its layers and k times shorter along them,
 * so k is the square root of what it falls short of the pane by; null where it falls short by less than `narrow`. */
function narrowFor(shape, drawn, pane) {
  const ratio = drawn.w / drawn.h, short = drawn.way.vertical ? ratio / pane : pane / ratio;
  return short < FIT2D.narrow ? null : Math.max(2, Math.ceil(shape.widest / Math.sqrt(short)));
}
/* The step of the pane's width to height, `FIT2D`: the drawn step `was` is held until the pane is `stay` steps from it.
 */
function fitStep2d(area, was = null) {
  if (!area.width || !area.height) return was ?? 0;
  const at = Math.log(area.width / area.height) / FIT2D.step;
  return was !== null && Math.abs(at - was) < FIT2D.stay ? was : Math.round(at);
}
/* ELK's options for one way, laid out for the width to height `aim`. The map has no subgraphs, so its root is laid out
 * on its own rather than with its children, which lets ELK lay out each part not joined to the rest apart, pack the
 * parts together to `aim` and close the gaps between them. A folded way also cuts each part's run of layers into rows
 * or columns, ELK's wrapping across several edges, cut where `wrap` names, MSD or ARD, with the correction `FIT2D`
 * gives, so a run too long for the pane goes on in the next row. A way may also name ELK's `layering`: MIN_WIDTH, its
 * layers held to about `bound` times the widest node, or STRETCH_WIDTH. Mermaid passes on its own few ELK options;
 * these reach the layout as `elk.rootLayoutOptions` in its configuration, which the vendored mermaid.min.js was
 * changed to forward, vendor/README.md. */
function fitOptions2d({wrap, aim, narrow, layering, bound}) {
  return {'elk.hierarchyHandling': 'SEPARATE_CHILDREN', 'elk.aspectRatio': String(aim),
    'elk.separateConnectedComponents': 'true', 'elk.layered.compaction.connectedComponents': 'true',
    ...(wrap ? {'elk.layered.wrapping.strategy': 'MULTI_EDGE', 'elk.layered.wrapping.cutting.strategy': wrap,
      'elk.layered.wrapping.correctionFactor': String(FIT2D.correction)} : {}),
    // a narrowed way, `narrowFor`: ELK's Coffman-Graham layering, which holds each layer to the bound it is given
    ...(narrow ? {'elk.layered.layering.strategy': 'COFFMAN_GRAHAM',
      'elk.layered.layering.coffmanGraham.layerBound': String(narrow)} : {}),
    ...(layering ? {'elk.layered.layering.strategy': layering} : {}),
    ...(bound ? {'elk.layered.layering.minWidth.upperBoundOnWidth': String(bound)} : {})};
}
/* One drawing with ELK's options given, Mermaid's configuration put back as it was once it is drawn, so the graph
 * inside a node and the memory network are laid out as before. */
async function fitDraw2d(id, text, options) {
  window.mermaid.initialize({...FIT2D.config, elk: {...FIT2D.config.elk, rootLayoutOptions: options}});
  try { return await window.mermaid.render(id, text, $('#draw')); }
  finally { window.mermaid.initialize(FIT2D.config); }
}
/* How large the whole drawing is drawn in the pane, in screen pixels to a unit of it, with the margin a fit leaves and
 * the room kept at its foot, as full fit draws it, `scaleFor`. */
function fitScale2d({w, h}, area) {
  const room = side => Math.min(MARGIN, side / 10);
  return Math.min((area.width - 2 * room(area.width)) / Math.max(1, w),
    (area.height - Math.min(foot2d(), area.height / 3) - 2 * room(area.height)) / Math.max(1, h));
}
// a way apart from the width to height it was laid out for: its direction, its fold, its layers' bound and layering
const fitWay2d = ({vertical, wrap, narrow, layering, bound}) =>
  `${vertical ? 'TB' : 'LR'}${wrap ? `w${wrap}` : ''}${narrow ? `n${narrow}` : ''}`
  + `${layering ? `-${layering}${bound || ''}` : ''}`;
/* web_map_direction as this page last read it, kept in `PEEK`: auto, across or down,
 * its directions also taken as Mermaid names them, LR and TB. */
export const fitPin2d = () => ({LR: 'across', TB: 'down'})[PEEK.direction] || PEEK.direction || 'auto';
function fitHash2d(text) {  // the map's text in a few characters, to know a drawing of it again
  let hash = 0x811c9dc5;
  for (let at = 0; at < text.length; at++) hash = Math.imul(hash ^ text.charCodeAt(at), 0x01000193);
  return `${text.length}.${(hash >>> 0).toString(36)}`;
}
/* The ways chosen for this base, kept in this browser so a reload draws the map once, F4: `chosen`, each map's text in
 * its step and direction with the way the whole search chose for it, the last `FIT2D.most`; and `last`, the way last
 * chosen in each pane, the large area or the small one, which a map whose text has changed since is drawn in first. */
const KEPT2D = {key: null, kept: null};
function kept2d() {
  const key = `metaform.fit2d.${S.project}.${S.base}`;
  if (KEPT2D.key === key) return KEPT2D.kept;
  let kept = null;
  try { kept = JSON.parse(localStorage.getItem(key) || 'null'); } catch { /* storage can be blocked: none kept */ }
  const valid = kept && typeof kept.chosen === 'object' && typeof kept.last === 'object';
  return Object.assign(KEPT2D, {key, kept: valid ? kept : {chosen: {}, last: {}}}).kept;
}
const pane2d = () => $('.app')?.classList.contains('swapped') ? 'large' : 'small';
const isWay2d = way => typeof way?.vertical === 'boolean';
function keepWay2d(mark, way) {
  const kept = kept2d();
  delete kept.chosen[mark];  // the latest last, and the oldest let go
  kept.chosen[mark] = way;
  for (const old of Object.keys(kept.chosen).slice(0, -FIT2D.most)) delete kept.chosen[old];
  kept.last[pane2d()] = way;
  try { localStorage.setItem(KEPT2D.key, JSON.stringify(kept)); } catch { /* storage can be blocked; kept for now */ }
}
/* The page waits for an idle moment before each layout of a choice made while a map is shown, so the frames and the
 * person's input go first; at most `wait` ms, so the choice still ends on a page that never idles. */
const idle2d = () => new Promise(go => window.requestIdleCallback
  ? requestIdleCallback(() => go(), {timeout: FIT2D.wait}) : setTimeout(go));
/* The map's text laid out for the pane, `FIT2D`: the drawing, its way, and whether it was `hurried`, or null once a
 * later drawing has begun. Every map whose text differs, and every step of the pane, is chosen for afresh; only the
 * same text in the same step and direction gets the way chosen for it before, once every way was drawn for it. The
 * map on the page stays, and takes the person's input between one drawing and the next, until the choice is made.
 * Each drawing is kept as it is made, so a choice begun again for the same map, as a change to its tickets alone
 * begins it, goes on where it was. The budget is counted from the first choice not yet shown, so changes that come
 * faster than the budget still show, each with the ways drawn by then. A choice that runs out of budget with ways
 * left, whether its own drawings or those of the choices before it spent it, is `hurried`: it is shown, and made
 * again once shown, going on with the ways not yet drawn, so a slow machine reaches the same choice later. The
 * project's settings are waited for while the page reads them, so a map held to one direction is drawn that way from
 * the first, and a direction changed while the map is laid out lays it out again. It fails only when ELK lays out
 * none of the ways.
 * A map drawn where none is shown yet, as at load, is drawn once and shown, F4: in the way this browser kept for the
 * same text, `kept2d`, which is the whole search's choice and so the last drawing; else in the way last chosen in this
 * pane, or the likelier direction, and the search goes on once it is shown, `hurried`. While a map is shown each
 * layout waits for an idle moment, `idle2d`. */
export async function fitPick2d(body, shape, generation, branch = false) {
  if (S.project && VIEW.read === S.project) await VIEW.reading;
  if (generation !== M.generation) return null;
  const area = area2d(), step = M.bucket = fitStep2d(area, M.bucket ?? null), pane = Math.exp(step * FIT2D.step);
  const pin = fitPin2d(), text = fitHash2d(body), mark = `${pin} ${step} ${text}`, aim = Number(pane.toPrecision(3));
  const kept = kept2d().chosen[mark], held = FIT2D.chosen.get(mark) || (isWay2d(kept) ? kept : null);
  const shown = Boolean(M.base);
  // A branch opened or closed on a map shown, `build2D`, is laid out once, in the way the map is drawn now and at once,
  // not after an idle moment: the page never idles while the 3D map draws, so each wait cost `wait` ms, and the
  // search over the ways cost up to `budget` before the branch showed (6.5 s at 1,000 elements, 2026-10-17). The way
  // is kept for this text in this page, so the map stays drawn that way; the search runs again on any other change.
  const same = branch && shown && !held && isWay2d(M.way)
    && (pin === 'auto' || M.way.vertical === (pin === 'down')) ? {...M.way, aim} : null;
  const ways = held ? [held] : same ? [same] : waysFor(shape, pin, aim), quick = branch && shown;
  const last = kept2d().last[pane2d()], first = !held && !shown && ways.length > 1;
  if (first && isWay2d(last) && pin === 'auto') ways.unshift({...last, aim});  // drawn first, then the rest searched
  const since = FIT2D.since ??= performance.now(), tried = new Set();
  let best = null, hurried = false;
  for (let at = 0; at < ways.length; at++) {
    const now = performance.now();
    if (best && (first || now - since > FIT2D.budget)) { hurried = true; break; }  // the ways left come once shown
    if (ways[at].narrow === true) {  // its layers' bound once the likelier direction is drawn, `narrowFor`
      const narrow = best && narrowFor(shape, best, pane);
      if (!narrow) continue;
      ways[at] = {...ways[at], narrow};
    }
    const way = ways[at], key = `${text} ${step} ${fitWay2d(way)} ${way.aim}`;
    if (tried.has(key)) continue;
    tried.add(key);
    let drawing = FIT2D.drawn.get(key);
    FIT2D.drawn.delete(key);
    if (!drawing) {
      await (shown && !quick ? idle2d() : new Promise(go => setTimeout(go)));  // the page takes its input first
      if (generation !== M.generation) return null;
      // a map drawn one way is laid out the other ways by ELK alone, in its worker, and only the way chosen is drawn
      const laid = FIT2D.laid.get(text);
      drawing = laid ? await sizeWay(way, laid) : await drawWay(way, body, `map2d${generation}n${at}`, shape.nodes);
      if (!drawing) { if (generation !== M.generation) return null; continue; }  // the other ways may still be drawn
      if (drawing.laid) {
        FIT2D.laid.set(text, drawing.laid);
        while (FIT2D.laid.size > 4) FIT2D.laid.delete(FIT2D.laid.keys().next().value);  // each a whole graph
      }
    }
    FIT2D.drawn.set(key, drawing);  // the latest last, and the oldest let go
    while (FIT2D.drawn.size > FIT2D.most) FIT2D.drawn.delete(FIT2D.drawn.keys().next().value);
    if (generation !== M.generation) return null;  // kept for the choice that follows
    const score = fitScale2d(drawing, area);
    if (!best || score > best.score) best = {...drawing, way, score, key};
  }
  if (best && !best.result) {  // the way chosen was laid out and not drawn: it is drawn now, the one Mermaid drawing
    await (shown && !quick ? idle2d() : new Promise(go => setTimeout(go)));
    if (generation !== M.generation) return null;
    const drawn = await drawWay(best.way, body, `map2d${generation}c`, shape.nodes);
    if (generation !== M.generation) return null;
    if (drawn) FIT2D.drawn.set(best.key, drawn);  // kept drawn, so the same map in the same pane is drawn at once
    best = drawn ? {...drawn, way: best.way, score: best.score, key: best.key} : null;
  }
  if (!best) { FIT2D.since = null; throw new Error('ELK laid out none of the ways.'); }
  if (fitPin2d() !== pin) return fitPick2d(body, shape, generation, branch);  // its direction was changed meanwhile
  if (same) FIT2D.chosen.set(mark, best.way);  // this page's alone: this browser keeps only the search's choices
  else if (!hurried) { FIT2D.chosen.set(mark, best.way); keepWay2d(mark, best.way); }
  while (FIT2D.chosen.size > FIT2D.most) FIT2D.chosen.delete(FIT2D.chosen.keys().next().value);
  FIT2D.since = null;
  return {result: best.result, way: best.way, hurried};
}
/* The ways to lay the map out for the pane, in the order they fill it best for the time they take: the one
 * web_map_direction holds it to; else the likelier direction first; then it with its layers narrowed where they came
 * out too wide for the pane, `narrowFor`, which is slow but the only way that reshapes such a map, and is reckoned from
 * the first drawing; then, for a map more than three layers deep, left to right folded into rows, cut both ways ELK
 * offers, which reshapes a long run in a pane of any shape; then, for a map of at most `small` elements, top to bottom
 * with its layers held narrow, MIN_WIDTH at three bounds and STRETCH_WIDTH, as these can take minutes on a large map
 * and one layout by ELK cannot be stopped; and the other direction last. */
function waysFor(shape, pin, aim) {
  if (pin === 'across' || pin === 'down') return [{vertical: pin === 'down', wrap: false, aim}];
  const first = vertical2d(shape, M.way?.vertical ?? null), small = shape.nodes <= FIT2D.small;
  return [{vertical: first, wrap: false, aim}, {vertical: first, wrap: false, aim, narrow: true},
    ...(shape.layers > 3 ? ['MSD', 'ARD'].map(wrap => ({vertical: false, wrap, aim})) : []),
    ...(small ? [1, 2, 4].map(bound => ({vertical: true, wrap: false, aim, layering: 'MIN_WIDTH', bound})) : []),
    ...(small ? [{vertical: true, wrap: false, aim, layering: 'STRETCH_WIDTH'}] : []),
    {vertical: !first, wrap: false, aim}];
}
/* One way laid out now, with its size; null where ELK fails it, or Mermaid gives back a drawing with no size. */
async function drawWay(way, body, id, nodes = null) {
  try {
    elkLaid();  // a layout asked before this drawing is not this drawing's
    const {svg} = await fitDraw2d(id, `flowchart ${way.vertical ? 'TB' : 'LR'}\n${body}`, fitOptions2d(way));
    const box = (svg.match(/viewBox="([^"]+)"/)?.[1] || '').split(/[\s,]+/).map(Number);
    if (!(box[2] > 0 && box[3] > 0)) return null;
    // what ELK laid this drawing out from, kept with how much larger Mermaid draws it than ELK laid it out, so the
    // other ways to lay the map out are measured from ELK's layouts alone, `sizeWay`
    const elk = elkLaid(), ok = elk && nodes !== null && elk.asked.graph?.children?.length === nodes;
    const pad = ok ? {w: box[2] - elk.answer.width, h: box[3] - elk.answer.height} : null;
    const laid = ok ? {asked: elk.asked, way, pad} : null;
    return {result: {svg}, w: box[2], h: box[3], laid};
  } catch (error) { return null; }
}
/* One way laid out by ELK alone, in its worker, from the graph a drawing of the same map was laid out from: the size
 * Mermaid would draw it, and no drawing, which is made only for the way chosen, `fitPick2d`. The graph's own options
 * are those that drawing was given, ELK's direction and the options of its way, `fitOptions2d`, given in place of the
 * drawing's; null where ELK fails it. */
async function sizeWay(way, laid) {
  const own = fitOptions2d(laid.way), options = {...laid.asked.graph.layoutOptions};
  // the drawing's own way's options taken out where they are still its own, and this way's put in their place, so
  // an option Mermaid set over the page's stays Mermaid's
  for (const [name, value] of Object.entries(own)) if (options[name] === value) delete options[name];
  for (const [name, value] of Object.entries(fitOptions2d(way))) if (!(name in options)) options[name] = value;
  options['elk.direction'] = way.vertical ? 'DOWN' : 'RIGHT';
  const message = {...laid.asked, graph: {...laid.asked.graph, layoutOptions: options}};
  try {
    const answer = await elkLayout(message);
    return {result: null, w: answer.width + laid.pad.w, h: answer.height + laid.pad.h, laid: null};
  } catch (error) { return null; }
}
/* A pane reshaped into another step of width to height, `fitStep2d`, lays the map out again, P043: 150 ms after it
 * stops changing, keeping the selection and the view, each node easing to its new place, `settle2D`. A
 * pane resized within its step keeps its layout; full fit refits it, `aim2d`. A pane that stops changing while the
 * page loads is looked at again once it has loaded, as the load may have laid the map out for the pane before. */
const RELAYOUT2D = {timer: 0};
function relayoutSoon() {
  clearTimeout(RELAYOUT2D.timer);
  RELAYOUT2D.timer = setTimeout(() => {
    if (S.loading) relayoutSoon();
    else if (M.base && fitStep2d(area2d(), M.bucket ?? null) !== M.bucket) build2D();
  }, 150);
}
new ResizeObserver(relayoutSoon).observe($('#viewport'));
/* web_map_direction as the page reads it again, `fitPin2d`: a change draws the map in it.
 * It is read with the workspace, and again whenever the page is looked at, its window focused or its tab shown, since
 * a direction set with `metaform set` while the page is open is not announced to it; the page takes it up then. */
export function fitDirection2d(direction) {
  if (!direction || direction === (PEEK.direction || 'auto')) return;
  PEEK.direction = direction;
  if (M.base) build2D();
}
async function fitRecheck2d() {
  if (!S.project || FRAMED || document.hidden) return;
  let found = null;
  try { found = await getJson(`/api/workspace?project=${encodeURIComponent(S.project)}`); } catch { return; }
  fitDirection2d(found?.view?.map_direction);
}
addEventListener('focus', fitRecheck2d);
document.addEventListener('visibilitychange', fitRecheck2d);
/* Where each node of a drawn map stands, by its element id, in the map's own units, counting any move it is still
 * making, so a map drawn again mid-move starts from where its nodes are and not where they were going. */
export function drawnAt(base) {
  const held = new Map();
  for (const [id, node] of base.nodes) {
    const [dx = 0, dy = 0] = String(node.g.style.translate || '').split(' ').map(parseFloat)
      .filter(value => !isNaN(value));
    held.set(id, {x: node.x + dx, y: node.y + dy, g: node.g});
  }
  return held;
}
/* The map moves between layouts, VIEW-041: the camera starts where it was, each node starts where it was drawn and
 * eases to its new place, a new node grows from where its parent stood, a node gone fades out, and the edges fade in
 * as the nodes arrive. It runs on animation frames, as the camera does, so the two move as one. With reduced motion
 * the new drawing only fades in. */
const SETTLE = {frame: 0};
export function settle2D(before, nodes, svg) {
  cancelAnimationFrame(SETTLE.frame);
  if (reduced()) { svg.animate([{opacity: 0}, {opacity: 1}], {duration: 160}); return; }
  const byAddress = new Map([...before.keys()].map(id => [S.elements.get(id)?.element.address, before.get(id)]));
  const moving = [];
  for (const [id, node] of nodes) {
    const old = before.get(id) || byAddress.get(S.elements.get(id)?.parent);
    moving.push({g: node.g, dx: old ? old.x - node.x : 0, dy: old ? old.y - node.y : 0, grow: !before.has(id)});
  }
  const ghosts = ghostsOf(before, nodes, svg.querySelector('.nodes') || svg.querySelector('g'));
  const edges = [...svg.querySelectorAll('.edgePaths, .edgeLabels')];
  const draw = (moved, faded, shown) => settleFrame(moving, ghosts, edges, moved, faded, shown);
  draw(0, 0, 0);  // the first frame shows the map as it stood
  let start = null;
  const step = now => {
    start ??= now;
    const gone = now - start;
    const moved = Math.min(1, gone / 520), faded = Math.min(1, gone / 300), shown = Math.min(1, gone / 780);
    draw(moved, faded, shown);
    if (shown < 1) SETTLE.frame = requestAnimationFrame(step); else for (const ghost of ghosts) ghost.remove();
  };
  SETTLE.frame = requestAnimationFrame(step);
}
/* A copy of each node gone, left where it stood to fade out, never taking the pointer. */
function ghostsOf(before, nodes, layer) {
  if (!layer) return [];
  return [...before].filter(([id]) => !nodes.has(id)).map(([, old]) => {
    const ghost = layer.appendChild(old.g.cloneNode(true));
    ghost.style.pointerEvents = 'none';
    return ghost;
  });
}
/* One frame of a move between layouts: each node `moved` of its way to its place on a cubic ease-out, a new one
 * growing in, the ghosts `faded`, and the edges coming in over the last part of `shown`. */
function settleFrame(moving, ghosts, edges, moved, faded, shown) {
  const ease = k => 1 - Math.pow(1 - k, 3);
  for (const one of moving) {
    const left = 1 - ease(moved);
    one.g.style.translate = left ? `${one.dx * left}px ${one.dy * left}px` : '';
    if (one.grow) {
      one.g.style.scale = left ? String(0.4 + 0.6 * (1 - left)) : '';
      one.g.style.opacity = left ? String(1 - left) : '';
    }
  }
  for (const ghost of ghosts) ghost.style.opacity = String(1 - faded);
  for (const part of edges) part.style.opacity = shown < 1 ? String(Math.max(0, (shown - 0.55) / 0.45)) : '';
}
/* Mermaid's strict SVG, the only markup parsed; hidden when it is measured without being shown. */
export function mountSvg(result, host, hidden) {
  const parsed = new DOMParser().parseFromString(result.svg, 'image/svg+xml');
  const svg = document.importNode(parsed.documentElement, true);
  svg.removeAttribute('height'); svg.removeAttribute('width'); svg.removeAttribute('style');
  svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  if (hidden) { svg.style.visibility = 'hidden'; host.append(svg); } else fill(host, svg);
  return svg;
}
/* Where a node's group is drawn: its box and its middle in the drawing's units. A drawing's nodes are all measured
 * before any is marked, `nodesIn`: a mark written between two measures made the browser lay the drawing out again for
 * each node. */
export function measureIn(group) {
  const box = group.getBBox();
  const matrix = group.transform.baseVal.consolidate()?.matrix;
  const center = new DOMPoint(box.x + box.width / 2, box.y + box.height / 2).matrixTransform(matrix || new DOMMatrix());
  return {box, center};
}
/* `title` names the node in full, kept on it as `data-title`; `tip` is its hovertext, shown only while the map's text
 * is drawn smaller than Small, `hover2d`. */
export function placeIn(nodes, id, group, title, work, tip = title, measured = measureIn(group)) {
  const {box, center} = measured;
  nodes.set(id, {g: group, x: center.x, y: center.y, w: box.width, h: box.height, tip});
  group.dataset.key = id;  // what the node stands for, kept from one drawing to the next as the mermaid id is not
  group.dataset.title = title;
  for (const condition of work || []) group.classList.add(`work-${condition}`);  // the node's condition, MAP-046
  if (work?.length) glow2d(group);  // its pulse drawn by a copy, `glow2d`
  const paced = S.progress?.get(id);
  if (paced) group.style.setProperty('--pace', `${paceOf({id})}s`);
  group.addEventListener('click', event => { event.stopPropagation(); clicked2d(id, event); });
  group.addEventListener('contextmenu', event => {
    event.preventDefault();
    event.stopPropagation();
    menu(id, event.clientX, event.clientY);
  });
}
/* The drawing's own bounds, the map's edge in its own units, VIEW-041. */
export function boundsOf(svg) {
  const scene = svg.querySelector('g').getBBox();
  return {x: scene.x, y: scene.y, w: scene.width, h: scene.height};
}
export const entryOf = () => [...S.elements.values()].find(item => item.element.role === 'DE')?.element.id
  || S.elements.keys().next().value;
export function showBase(left = null) {
  const base = M.base;
  renderCrumbs();
  if (!base) return;
  stopCam();  // a camera still easing on the level left must not move this one
  Object.assign(M, {svg: base.svg, nodes: base.nodes, edges: base.edges, bounds: base.bounds, vertical: base.vertical,
    drawn: null});
  fill($('#viewport'), base.svg);
  const node = left ? base.nodes.get(left) : null;
  const held = base.free && base.cam;  // a view the person zoomed comes back as it was left, VIEW-041
  // back from inside the node: the map returns zoomed on it, fades in and eases out, VIEW-016
  if (node && !reduced()) {
    setCam(frame(into(node)));
    arrive(base.svg);
    if (held) moveCam(base.cam); else aim2d(node);  // to full fit, the node left centered as far as the limits allow
    return;
  }
  base.svg.style.transition = ''; base.svg.style.opacity = '';  // a map faded on the way in shows whole again
  if (held) return setCam(frame(base.cam));
  aim2d(node || (base.cam ? focus2d(base.cam) : center2d(S.selected) || base.nodes.get(entryOf())
    || base.nodes.values().next().value), true);
}
