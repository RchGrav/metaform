/* The 2D map's joins, their directions and arrows, the flow drawn along the selected node's joins, focus, clicks and
 * modified clicks. */
import '/page/app/map2d/hover.js';  // the part before runs first, so the parts run in the page's order
import {$, css, reduced, SVG} from '/page/app/core/dom.js';
import {S, MEM} from '/page/app/core/reads.js';
import {joinOf} from '/page/app/graph/data.js';
import {again2d} from '/page/app/figures/roam2d.js';
import {colorOf} from '/page/app/map3d/light.js';
import {G, FRAMES} from '/page/app/map3d/graph3d.js';
import {FLOW, flowModeNow, flowAt, flowTick} from '/page/app/flow/flow.js';
import {M} from '/page/app/map2d/build.js';
import {IN} from '/page/app/map2d/inside.js';
import {MAC, aim2d, autoZoom2d, fullFit2d} from '/page/app/map2d/camera.js';
import {HOVER2D} from '/page/app/map2d/hover.js';
import {goInside, levelUp, toggleDepth} from '/page/app/keys/walk.js';
import {select} from '/page/app/selection/select.js';

/* A join's information flow direction, its ifd, MAP-020, as the receiver has it: it sends to the elements that serve
 * it, receives from them, or both. The 2D map's arrows and flow and the 3D map's dots go the way the information goes.
 */
const flowOf = join => join?.ifd === 'receives' ? ['back'] : join?.ifd === 'both' ? ['forth', 'back'] : ['forth'];
/* The arrow between a join's receiver and its providers in its title: the receiver comes first, which says who needs
 * whom, and the arrow says which way the information goes, its ifd, as the 2D map's arrowheads do: ← when the receiver
 * receives, → when it sends or nothing is recorded, as the 2D map's arrowhead points, ↔ both ways. */
export const flowArrow = join => join?.ifd === 'both' ? '↔' : join?.ifd === 'receives' ? '←' : '→';
/* An edge of the 2D map runs the way its join's information goes, as `metaform map mermaid` writes it: from the
 * receiver to the element served when the receiver sends or nothing is recorded, from the element served to the
 * receiver when it receives. So the page and the export give ELK the same graph to lay out. */
export const ends2d = (join, provider) => join?.ifd === 'receives' ? [provider, join.receiver]
  : [join.receiver, provider];
/* Mermaid draws the arrowhead at an edge's end, where the information arrives; both ways it gets one at its start. */
export function pointed(edge) {
  const path = edge.path, end = path?.getAttribute('marker-end');
  if (end && edge.join?.ifd === 'both') path.setAttribute('marker-start', end.replace('pointEnd', 'pointStart'));
}
/* The selected node's joins in the 2D map carry its flow in the 3D map's looks, on the same clocks, VIEW-005 and
 * `FLOW`: a tiny white request from the receiver to the element served, the answer back as a short bright streak, the
 * way the information goes, and on a join whose receiver sends, a record card that lands with a ring. Only the
 * selected node's, so the map stays still to read and the flow says what the selection takes from where. Each edge
 * gets its shapes once, in a group just over the edges, so they run under the node boxes; each frame, `frame2d`, while
 * the page is in use, as the 3D map draws its flow, `FRAMES`, moves them with as few writes as it can: a train of dots
 * is a path holding only its dots, each a round cap on a stroke of no length, rewritten only when a dot moves, and a
 * shape is shown or hidden only when its part of the cycle begins or ends; with reduced motion nothing moves and
 * nothing is shown. The browser paints a changed path again over its whole box: a path the length of its edge, as a
 * dashed copy of the edge was, made it paint every moving edge's whole length each frame, where a path of dots only
 * paints the dots. */
const FLOW2D = {id: 0, edges: [], opacity: -1, group: null, fade: -1, at: -1};
const BEAD = 2.1;  // a dot's radius
const TAIL = [0.75, 0.5, 0.25];  // the last three dots of a train fade
/* A shape of the flow and what it last showed, kept here and not on the element, so a frame compares its own fields
 * and writes the element only when they change: whether it is shown, and the dots of a dot path. */
class Shape2d {
  constructor(element, on) {
    this.element = element;
    this.on = on;
    this.d = '';
  }
}
/* A reply's train: its group, shown or hidden, its path of full-strength dots and one path for each fading dot. */
class Train2d {
  constructor(g, solid, tail) {
    this.g = g;
    this.solid = solid;
    this.tail = tail;
  }
}
/* An edge's curve sampled once, one array of x and one of y, and its length: kept for as long as its drawn edge lives,
 * by the edge, `SAMPLED`, so a new selection or mode measures nothing again. */
class Samples2d {
  constructor(length, xs, ys) {
    this.length = length;
    this.xs = xs;
    this.ys = ys;
  }
}
const SAMPLED = new WeakMap();
/* What the flow keeps of one edge for as long as this flow lasts: the edge, its join and path, its samples, and its
 * shapes: a train each way, the request, the record card and the ring. */
class Edge2d {
  constructor(edge, samples, trains, ask, record, ring) {
    this.edge = edge;
    this.join = edge.join;
    this.path = edge.path;
    this.length = samples.length;
    this.xs = samples.xs;
    this.ys = samples.ys;
    this.trains = trains;
    this.ask = ask;
    this.record = record;
    this.ring = ring;
  }
}
// where a frame puts the point it looks up, `place`: one object, read before the next look-up
const POINT = {x: 0, y: 0};
// an element's own colour on the map, as the 3D map draws it, for what comes from it, from the 3D map's nodes by id,
// `byId`, gathered once for each build of the flow and not searched again for each end of each edge
function color2d(id, byId) {
  const node = byId.get(id);
  return node ? colorOf(node) : css('--signal');
}
export function flows2d() {
  for (const old of M.svg?.querySelectorAll('g.flows2d') || []) old.remove();
  FLOW2D.edges = [];
  FLOW2D.opacity = -1;
  FLOW2D.group = null;
  const on = flowing2d();
  if (!on.length) return;
  // a group of their own just over the edges, so the edges stay what they are
  const flows = document.createElementNS(SVG, 'g'), edges = on[0].path.closest('.edgePaths') || on[0].path.parentNode;
  flows.setAttribute('class', 'flows2d');
  edges.after(flows);
  // every train in one group, every request in another and the records and rings in a third, each a layer of its own
  // in the page's CSS, `will-change`: each glow, `.trains` and `.asks`, is drawn once over its group by the browser's
  // compositor, not its painter for every dot each frame, and a frame's moves paint their layer again, not the map's
  const glows = {};
  for (const name of ['trains', 'asks', 'marks']) {
    glows[name] = document.createElementNS(SVG, 'g');
    glows[name].setAttribute('class', name);
    flows.append(glows[name]);
  }
  const made = (tag, name, attributes = {}, parent = glows.marks) => {
    const shape = document.createElementNS(SVG, tag);
    shape.setAttribute('class', name);
    for (const [key, value] of Object.entries(attributes)) shape.setAttribute(key, value);
    shape.style.display = 'none';
    parent.append(shape);
    return new Shape2d(shape, false);
  };
  const byId = new Map((G?.graphData().nodes || []).map(node => [node.id, node]));
  for (const edge of on) FLOW2D.edges.push(edgeShapes(edge, made, glows, byId));
  extent2d(Object.values(glows), FLOW2D.edges);
  FLOW2D.group = flows;
  wake2d();
}
/* Each layer of the flow keeps one size, the box of all its edges, for as long as this flow lasts: a rect that draws
 * nothing. A layer sized by its moving dots changed size every frame, and the browser then cut the map after it into
 * new layers each frame and painted them whole. A ring grows to 18 around the end of its edge. */
function extent2d(layers, edges) {
  let left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
  const pad = 20;
  for (const {xs, ys} of edges) {
    for (let i = 0; i < xs.length; i++) {
      left = Math.min(left, xs[i]); top = Math.min(top, ys[i]);
      right = Math.max(right, xs[i]); bottom = Math.max(bottom, ys[i]);
    }
  }
  for (const layer of layers) {
    const rect = document.createElementNS(SVG, 'rect');
    const size = {x: left - pad, y: top - pad, width: right - left + 2 * pad, height: bottom - top + 2 * pad};
    for (const [key, value] of Object.entries(size)) rect.setAttribute(key, value.toFixed(1));
    rect.setAttribute('fill', 'none');
    rect.setAttribute('stroke', 'none');
    layer.prepend(rect);
  }
}
/* The edges that flow: in all, every edge; in hover, the edges of the node the pointer is on; else the selection's. */
function flowing2d() {
  const mode = flowModeNow(), hover = mode === 'hover' ? HOVER2D.on : null;
  return M.edges.filter(edge => edge.join && (mode === 'all' || (hover ? edge.join.receiver === hover
    || edge.provider === hover : edge.path?.classList.contains('on'))));
}
/* One edge's shapes: a reply's train each way, in the colour of the element it comes from, `fxTrain`, one path for its
 * dots at full strength and one for each fading dot; the request, one dot on a path of its own; the record card and
 * the ring it lands with. The dots' paths are empty until a frame places their dots, `dots2d`; the train's group is
 * what is shown or hidden. The edge is measured here, `sampled`, before any frame writes into the map: measured later,
 * each measure after a frame's first write makes the browser lay out the page again. */
function edgeShapes(edge, made, {trains, asks}, byId) {
  const dots = (attributes, parent) => {
    const path = made('path', 'bead', attributes, parent.element);
    show2d(path, true);
    return path;
  };
  const train = way => {
    const g = made('g', 'train', {}, trains);
    g.element.style.stroke = color2d(way === 0 ? edge.provider : edge.join.receiver, byId);
    return new Train2d(g, dots({}, g), TAIL.map(opacity => dots({opacity}, g)));
  };
  return new Edge2d(edge, sampled(edge), [train(0), train(1)], made('path', 'ask', {}, asks),
    made('rect', 'record', {x: -4.5, y: -3.2, width: 9, height: 6.4, rx: 1.4}), made('circle', 'ring', {r: 4}));
}
export function wake2d() {
  if (!FLOW2D.id && FLOW2D.edges.length && !reduced()) FLOW2D.id = requestAnimationFrame(frame2d);
  again2d();  // the figures and the mascot on the 2D map wake with any act too
  clearTimeout(AMBIENT2D.timer);
  if (AMBIENT2D.at) for (const one of ambients2d()) if (one.playState === 'paused') one.play();
  AMBIENT2D.at = 0;
  AMBIENT2D.timer = setTimeout(rest2d, FRAMES.idle);
}
/* The 2D map's ambient animations, the flash of a part's record and the pulse of one under construction, VIEW-029,
 * are the page's CSS and run at the screen's rate for as long as the page is open. Only with web_idle_flow off may they
 * rest: once nothing has been done or changed for `FRAMES.idle` they are paused, and the next act, or the tab coming
 * back into view, lets them run again, `wake2d`. They are never stepped at a lower rate. Only those that repeat for
 * ever: a fade runs out by itself. */
const AMBIENT2D = {timer: 0, at: 0};
const ambients2d = () => ($('#map2d')?.getAnimations({subtree: true}) || []).filter(one => one instanceof CSSAnimation
  && one.effect?.getTiming().iterations === Infinity);
function rest2d() {
  if (FRAMES.rest === null) return;  // the map keeps running
  const still = performance.now() - FRAMES.active;
  if (still < FRAMES.idle) { AMBIENT2D.timer = setTimeout(rest2d, FRAMES.idle - still); return; }
  AMBIENT2D.at = performance.now();
  for (const one of ambients2d()) if (one.playState === 'running') one.pause();
}
/* A point at a distance along an edge, looked up in the edge's curve sampled once, `sampled`, never measured again each
 * frame: measuring a curve for every dot on every frame was the page's own heaviest work. */
function sampled(edge) {
  let samples = SAMPLED.get(edge);
  if (!samples) {
    const length = edge.path.getTotalLength(), count = Math.max(16, Math.ceil(length / 3));
    const xs = new Float32Array(count + 1), ys = new Float32Array(count + 1);
    for (let i = 0; i <= count; i++) {
      const point = edge.path.getPointAtLength(length * i / count);
      xs[i] = point.x; ys[i] = point.y;
    }
    SAMPLED.set(edge, samples = new Samples2d(length, xs, ys));
  }
  return samples;
}
// the point at a distance along the edge, into `POINT`
function place(one, distance) {
  const xs = one.xs, ys = one.ys, last = xs.length - 1;
  const f = Math.min(last, Math.max(0, distance / Math.max(1e-6, one.length) * last));
  const i = Math.min(last - 1, Math.floor(f)), u = f - i;
  POINT.x = xs[i] + (xs[i + 1] - xs[i]) * u;
  POINT.y = ys[i] + (ys[i + 1] - ys[i]) * u;
}
/* A frame of the flow: every read first, whether the map is drawn and which edges are still in it, then the writes.
 * It allocates nothing but the text of what it writes. */
function frame2d(now) {
  FLOW2D.id = 0;
  const edges = FLOW2D.edges;
  let shown = 0;
  for (let i = 0; i < edges.length; i++) if (edges[i].path.isConnected) shown++;
  if (!shown || !M.svg?.checkVisibility()) return;
  // it rests as the 3D map's flow rests, once nothing was done for web_flow_seconds, until the next act
  const resting = reduced() || (FRAMES.rest !== null && performance.now() - FRAMES.active > FRAMES.idle);
  flowTick(now);
  // the flow mode, web_flow_mode: off and live draw none of it here; a change eases it in or out
  const mode = flowModeNow(), wanted = mode === 'hover' || mode === 'selected' || mode === 'all' ? 1 : 0;
  const was = FLOW2D.fade < 0 ? wanted : FLOW2D.fade, since = FLOW2D.at < 0 ? 0 : FLOW.clock - FLOW2D.at;
  FLOW2D.fade = was + (wanted - was) * (1 - Math.exp(-Math.max(0, since) * FLOW.ease));
  FLOW2D.at = FLOW.clock;
  const opacity = Math.round(FLOW2D.fade * 1000);  // in thousandths, written only when that changes
  if (FLOW2D.group && opacity !== FLOW2D.opacity) {
    FLOW2D.opacity = opacity;
    FLOW2D.group.style.opacity = String(opacity / 1000);
  }
  const hidden = FLOW2D.fade < 0.01 && !wanted;
  for (let i = 0; i < edges.length; i++) if (edges[i].path.isConnected) flowEdge2d(edges[i], hidden || resting);
  if (!hidden && !resting) FLOW2D.id = requestAnimationFrame(frame2d);
}
// a shape is shown or hidden only when that changes, so a frame writes only what moves
function show2d(shape, on) {
  if (shape.on !== on) {
    shape.on = on;
    shape.element.style.display = on ? '' : 'none';
  }
}
// a dot path's dots, written only when they change
function dots2d(shape, d) {
  if (shape.d !== d) {
    shape.d = d;
    shape.element.setAttribute('d', d);
  }
}
/* A dot at a share of the way along the edge, forward or back, as a stroke of no length whose round caps make the dot;
 * none off either end. */
function dot(one, share, forward) {
  if (share < 0 || share > 1) return '';
  place(one, (forward ? share : 1 - share) * one.length);
  return `M${POINT.x.toFixed(2)},${POINT.y.toFixed(2)}h0`;
}
// the point at a share of the way the edge's information goes, into `POINT`
function at(one, share, receives) {
  const clamped = Math.min(1, Math.max(0, share));
  place(one, (receives ? 1 - clamped : clamped) * one.length);
}
/* One edge's flow this frame, the way its information goes: its records, its ring as one lands, its request, and its
 * reply's trains. Resting, nothing is shown. */
function flowEdge2d(one, resting) {
  const join = one.join, receives = join.ifd === 'receives', record = one.record, ring = one.ring;
  let asks = false, since = 0, amount = 7, reply = FLOW.reply;
  if (!resting) {
    const now = flowAt(join);
    asks = now.asks; since = now.since;
    if (asks) { amount = now.amount; reply = now.reply; }
  }
  const live = !resting, sends = live && !asks;
  const recording = sends && since < FLOW.send, ringing = sends && !recording && since < FLOW.send + FLOW.burst;
  const asking = live && asks && since < FLOW.ask, replying = live && asks && !asking && since < FLOW.ask + reply;
  if (recording) {
    const t = since / FLOW.send;
    at(one, t * t * (3 - 2 * t), receives);
    record.element.setAttribute('transform', `translate(${POINT.x} ${POINT.y})`);
  }
  show2d(record, recording);
  if (ringing) {
    const u = (since - FLOW.send) / FLOW.burst;
    if (!ring.on) {
      at(one, 1, receives);
      ring.element.setAttribute('transform', `translate(${POINT.x} ${POINT.y})`);
    }
    ring.element.setAttribute('r', String(4 + 14 * u));
    ring.element.style.opacity = String(Math.pow(1 - u, 1.5));
  }
  show2d(ring, ringing);
  if (asking) {
    at(one, since / FLOW.ask, receives);
    dots2d(one.ask, `M${POINT.x.toFixed(2)},${POINT.y.toFixed(2)}h0`);
  }
  show2d(one.ask, asking);
  // the reply: a train of dots the way the data goes, both ways on a join whose information goes both ways; the
  // first train runs back to the receiver, the second forth
  const ways = replying ? (join.ifd === 'both' ? 2 : 1) : 0;
  for (let index = 0; index < 2; index++) {
    const train = one.trains[index];
    if (index < ways) train2d(train, (since - FLOW.ask) / reply, index === 0, amount, one, receives);
    show2d(train.g, index < ways);
  }
}
/* A reply's train of dots along the edge, spaced so they read as dots, the last few fading: dot i is i spaces behind
 * the head, and a dot off either end of the edge is not drawn. The full-strength dots share one path and each fading
 * dot has its own, so a frame writes at most four paths a train, each holding only its dots. */
function train2d(train, t, back, amount, one, receives) {
  const length = one.length, spacing = Math.max(0.03, BEAD * 2 * 2.3 / Math.max(1, length));
  const shown = Math.max(2, Math.min(12, amount, Math.floor(0.6 / spacing) + 1));
  const head = t * (1 + spacing * (shown - 1)), forward = receives === back;
  let solid = '';
  for (let i = 0; i < shown - 3; i++) solid += dot(one, head - i * spacing, forward);
  dots2d(train.solid, solid);
  for (let j = 0; j < TAIL.length; j++) {
    const i = shown - 3 + j;
    dots2d(train.tail[j], i < 0 ? '' : dot(one, head - i * spacing, forward));
  }
}
export function focus2D(id, frame = true) {
  const join = id.startsWith('p:') ? joinOf(id) : null;
  const node = M.nodes.get(id) || (join ? M.nodes.get(join.provider) : null);
  if (!M.svg) return;
  if (!node) return aim2d();
  if (IN.length) {
    for (const [key, value] of M.nodes) value.g.classList.toggle('sel', key === id);
  } else {
    $('#map2d').classList.add('focused');
    markNodes(M.nodes, id);
    for (const edge of M.edges) {
      const on = join ? edge.join === join : edge.join.receiver === id || edge.provider === id;
      edge.path?.classList.toggle('on', on);
      edge.hit?.classList.toggle('on', on);  // its band a pixel wider than the line drawn for a selection
    }
  }
  flows2d();
  // The view stays where it is, refitted only in full fit, VIEW-041; only the node of an agent the person follows
  // is framed, `autoZoom2d`.
  if (frame) autoZoom2d(id); else aim2d();
}
/* The selected node marked, and its neighbours. */
export function markNodes(nodes, id) {
  for (const [key, value] of nodes) {
    value.g.classList.toggle('sel', key === id);
    value.g.classList.toggle('near', key !== id && S.neighbors.has(key));
  }
}
/* A click on the map, VIEW-008: on a node or an edge it selects it, and on the selected one it goes inside it; a
 * group's "more" node shows the next ones. Anywhere on the map, with Shift held it backs out one level, and with Ctrl
 * held, Command on macOS, where a click with Control is the system's right-click, it goes back to full fit. */
export function clicked2d(id, event) {
  if (modified2d(event)) return;
  // a node holding parts deeper than the depth breaks them out in place, or folds them, and is selected, VIEW-051
  if (toggleDepth(id)) return select(id, true);
  if (!MEM.key && (id === S.selected || id.startsWith('m:'))) goInside(id); else select(id, true);
}
export function modified2d(event) {
  if (event?.shiftKey) { levelUp(); return true; }
  if (event && (MAC ? event.metaKey : event.ctrlKey)) { fullFit2d(); return true; }
  return false;
}
