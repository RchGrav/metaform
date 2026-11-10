/* The 2D map's joins, their directions and arrows, the flow drawn along the selected node's joins, focus, clicks and
 * modified clicks. */
import '/classic/app/map2d/hover.js';  // the part before runs first, so the parts run in the page's order
import {$, css, reduced, SVG} from '/classic/app/core/dom.js';
import {S, MEM} from '/classic/app/core/reads.js';
import {joinOf} from '/classic/app/graph/data.js';
import {colorOf} from '/classic/app/map2d/looks.js';
import {FLOW, flowModeNow, flowAt, flowTick} from '/classic/app/flow/flow.js';
import {M} from '/classic/app/map2d/build.js';
import {IN} from '/classic/app/map2d/inside.js';
import {MAC, aim2d, autoZoom2d, fullFit2d} from '/classic/app/map2d/camera.js';
import {HOVER2D} from '/classic/app/map2d/hover.js';
import {goInside, levelUp, toggleDepth} from '/classic/app/keys/walk.js';
import {select} from '/classic/app/selection/select.js';

/* When the flow may rest, from the earlier page's map3d/graph3d.js: `rest` null, its default, keeps the map
 * running; the setting that let it rest after `idle` ms is not part of this page. */
const FRAMES = {active: 0, idle: 30000, rest: null};

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
 * the page is in use, as the 3D map draws its flow, `FRAMES`, moves them with as few writes as it can: a reply is one
 * path, its line, the stretch of the edge it covers, rewritten only when it moves, and a shape is shown or hidden only
 * when its part of the cycle begins or ends; with reduced motion nothing moves and nothing is shown. The browser paints
 * a changed path again over its whole box: a path the length of its edge, as a dashed copy of the edge was, made it
 * paint every moving edge's whole length each frame, where a path of the line alone paints the line. */
const FLOW2D = {id: 0, edges: [], opacity: -1, group: null, fade: -1, at: -1, seen: true, watched: null,
  watcher: null};
const ASK = 3.8;  // the request's size across, its stroke in the page's CSS, `.ask`: a reply's line is in these
/* A shape of the flow and what it last showed, kept here and not on the element, so a frame compares its own fields
 * and writes the element only when they change: whether it is shown, and a path's `d`. */
class Shape2d {
  constructor(element, on) {
    this.element = element;
    this.on = on;
    this.d = '';
  }
}
/* A reply's train: its group, shown or hidden, in the colour the data comes from, and its line. */
class Train2d {
  constructor(g, line) {
    this.g = g;
    this.line = line;
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
// an element's own colour, for what comes from it, `colorOf`
function color2d(id) {
  const entry = S.elements.get(id);
  return entry ? colorOf(entry.element) : css('--signal');
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
  for (const edge of on) FLOW2D.edges.push(edgeShapes(edge, made, glows));
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
/* One edge's shapes: a reply's train each way, in the colour of the element it comes from, `fxReply`, its line one
 * path; the request, one dot on a path of its own; the record card and the ring it lands with. The paths are empty
 * until a frame places them, `drawn2d`; the train's group is what is shown or hidden. The edge is measured here,
 * `sampled`, before any frame writes into the map: measured later, each measure after a frame's first write makes the
 * browser lay out the page again. */
function edgeShapes(edge, made, {trains, asks}) {
  const train = way => {
    const g = made('g', 'train', {}, trains), line = made('path', 'line', {}, g.element);
    g.element.style.stroke = color2d(way === 0 ? edge.provider : edge.join.receiver);
    show2d(line, true);
    return new Train2d(g, line);
  };
  return new Edge2d(edge, sampled(edge), [train(0), train(1)], made('path', 'ask', {}, asks),
    made('rect', 'record', {x: -4.5, y: -3.2, width: 9, height: 6.4, rx: 1.4}), made('circle', 'ring', {r: 4}));
}
export function wake2d() {
  if (!FLOW2D.id && FLOW2D.edges.length && !reduced()) FLOW2D.id = requestAnimationFrame(frame2d);
  clearTimeout(AMBIENT2D.timer);
  if (AMBIENT2D.at) for (const one of ambients2d()) if (one.playState === 'paused') one.play();
  AMBIENT2D.at = 0;
  if (FRAMES.rest !== null) AMBIENT2D.timer = setTimeout(rest2d, FRAMES.idle);  // the map keeps running: no rest due
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
  if (!samples) samples = flatSampled(edge.path.getAttribute('d') || '');
  if (!samples) {  // a path `flatSampled` does not read: measured by the browser
    const length = edge.path.getTotalLength(), count = Math.max(16, Math.ceil(length / 3));
    const xs = new Float32Array(count + 1), ys = new Float32Array(count + 1);
    for (let i = 0; i <= count; i++) {
      const point = edge.path.getPointAtLength(length * i / count);
      xs[i] = point.x; ys[i] = point.y;
    }
    samples = new Samples2d(length, xs, ys);
  }
  SAMPLED.set(edge, samples);
  return samples;
}
/* The same samples read from the path's own `d`, its lines and Bézier curves laid flat in short straight pieces and
 * walked at even steps, without asking the browser: the browser walks the whole path again for each point it is asked
 * for, so an edge of a large map, thousands of units long, cost a second for the flow of one selection, and a branch
 * opened on a map of 1,000 elements waited seven seconds on it (2026-10-17). Null for a path of more than one move,
 * which the browser measures. */
const FLAT = {xs: new Float64Array(1024), ys: new Float64Array(1024), at: new Float64Array(1024), size: 0};
const COMMAND2D = /([MmLlHhVvCcSsQqTtAaZz])([^MmLlHhVvCcSsQqTtAaZz]*)/g;
function flatSampled(d) {
  if (!d || (d.match(/[Mm]/g) || []).length !== 1) return null;
  FLAT.size = 0;
  let x = 0, y = 0, startX = 0, startY = 0, lastX = 0, lastY = 0, last = '';  // lastX, lastY: the control point
  for (const [, command, rest] of d.matchAll(COMMAND2D)) {
    const n = rest.match(/-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?/g)?.map(Number) || [];
    const relative = command === command.toLowerCase(), kind = command.toUpperCase();
    const ox = () => (relative ? x : 0), oy = () => (relative ? y : 0);
    if (kind === 'Z') { flatPoint(startX, startY); x = startX; y = startY; last = kind; continue; }
    const size = {M: 2, L: 2, H: 1, V: 1, C: 6, S: 4, Q: 4, T: 2, A: 7}[kind];
    if (n.length % size) return null;  // a path written in a way not read here, as arc flags run together
    for (let i = 0; i + size <= n.length; i += size) {
      if (kind === 'M' && i === 0) {
        x = n[0] + ox(); y = n[1] + oy(); startX = x; startY = y;
        flatPoint(x, y);
      } else if (kind === 'M' || kind === 'L') { x = n[i] + ox(); y = n[i + 1] + oy(); flatPoint(x, y); }
      else if (kind === 'H') { x = n[i] + (relative ? x : 0); flatPoint(x, y); }
      else if (kind === 'V') { y = n[i] + (relative ? y : 0); flatPoint(x, y); }
      else if (kind === 'A') {
        const ex = n[i + 5] + ox(), ey = n[i + 6] + oy();
        flatArc(x, y, n[i], n[i + 1], n[i + 2], n[i + 3], n[i + 4], ex, ey);
        x = ex; y = ey;
      }
      else {
        const quad = kind === 'Q' || kind === 'T', smooth = kind === 'S' || kind === 'T';
        const mirrored = smooth && last !== '' && (quad ? 'QT' : 'CS').includes(last);
        const c1x = smooth ? (mirrored ? 2 * x - lastX : x) : n[i] + ox();
        const c1y = smooth ? (mirrored ? 2 * y - lastY : y) : n[i + 1] + oy();
        const at = smooth ? i : i + 2;
        const c2x = quad ? c1x : n[at] + ox(), c2y = quad ? c1y : n[at + 1] + oy();
        const endAt = quad ? (smooth ? i : i + 2) : at + 2, ex = n[endAt] + ox(), ey = n[endAt + 1] + oy();
        if (quad) flatCurve(x, y, x + 2 / 3 * (c1x - x), y + 2 / 3 * (c1y - y), ex + 2 / 3 * (c1x - ex),
          ey + 2 / 3 * (c1y - ey), ex, ey);
        else flatCurve(x, y, c1x, c1y, c2x, c2y, ex, ey);
        lastX = quad ? c1x : c2x; lastY = quad ? c1y : c2y;
        x = ex; y = ey;
      }
      last = kind;
    }
  }
  if (FLAT.size < 2) return null;
  const length = FLAT.at[FLAT.size - 1], count = Math.max(16, Math.ceil(length / 3));
  const xs = new Float32Array(count + 1), ys = new Float32Array(count + 1);
  for (let i = 0, piece = 1; i <= count; i++) {
    const want = length * i / count;
    while (piece < FLAT.size - 1 && FLAT.at[piece] < want) piece++;
    const from = FLAT.at[piece - 1], span = FLAT.at[piece] - from, u = span > 0 ? (want - from) / span : 0;
    xs[i] = FLAT.xs[piece - 1] + (FLAT.xs[piece] - FLAT.xs[piece - 1]) * u;
    ys[i] = FLAT.ys[piece - 1] + (FLAT.ys[piece] - FLAT.ys[piece - 1]) * u;
  }
  return new Samples2d(length, xs, ys);
}
function flatPoint(x, y) {
  if (FLAT.size === FLAT.xs.length) {  // grown once to a longer path, and kept that size
    const grow = array => { const more = new Float64Array(array.length * 2); more.set(array); return more; };
    FLAT.xs = grow(FLAT.xs); FLAT.ys = grow(FLAT.ys); FLAT.at = grow(FLAT.at);
  }
  const at = FLAT.size;
  FLAT.xs[at] = x; FLAT.ys[at] = y;
  FLAT.at[at] = at ? FLAT.at[at - 1] + Math.hypot(x - FLAT.xs[at - 1], y - FLAT.ys[at - 1]) : 0;
  FLAT.size++;
}
/* An elliptical arc as SVG draws it, from its end points to its centre, SVG 1.1 F.6.5, in straight pieces of about
 * half a unit; a line where a radius is nought. */
function flatArc(x0, y0, rx, ry, degrees, large, sweep, x, y) {
  rx = Math.abs(rx); ry = Math.abs(ry);
  if (!rx || !ry || (x0 === x && y0 === y)) { flatPoint(x, y); return; }
  const phi = degrees * Math.PI / 180, cos = Math.cos(phi), sin = Math.sin(phi);
  const hx = (x0 - x) / 2, hy = (y0 - y) / 2, px = cos * hx + sin * hy, py = -sin * hx + cos * hy;
  const grow = px * px / (rx * rx) + py * py / (ry * ry);
  if (grow > 1) { rx *= Math.sqrt(grow); ry *= Math.sqrt(grow); }
  const top = rx * rx * ry * ry - rx * rx * py * py - ry * ry * px * px;
  const root = Math.sqrt(Math.max(0, top / (rx * rx * py * py + ry * ry * px * px))) * (large === sweep ? -1 : 1);
  const cx1 = root * rx * py / ry, cy1 = -root * ry * px / rx;
  const cx = cos * cx1 - sin * cy1 + (x0 + x) / 2, cy = sin * cx1 + cos * cy1 + (y0 + y) / 2;
  const angle = (ux, uy, vx, vy) => Math.atan2(ux * vy - uy * vx, ux * vx + uy * vy);
  const start = angle(1, 0, (px - cx1) / rx, (py - cy1) / ry);
  let turn = angle((px - cx1) / rx, (py - cy1) / ry, (-px - cx1) / rx, (-py - cy1) / ry);
  if (!sweep && turn > 0) turn -= 2 * Math.PI; else if (sweep && turn < 0) turn += 2 * Math.PI;
  const pieces = Math.min(512, Math.max(4, Math.ceil(Math.abs(turn) * Math.max(rx, ry) * 2)));
  for (let k = 1; k <= pieces; k++) {
    const a = start + turn * k / pieces, ax = rx * Math.cos(a), ay = ry * Math.sin(a);
    if (k === pieces) flatPoint(x, y); else flatPoint(cos * ax - sin * ay + cx, sin * ax + cos * ay + cy);
  }
}
/* A cubic Bézier curve in straight pieces of about half a unit along its control polygon, at most 512. */
function flatCurve(x0, y0, x1, y1, x2, y2, x3, y3) {
  const hull = Math.hypot(x1 - x0, y1 - y0) + Math.hypot(x2 - x1, y2 - y1) + Math.hypot(x3 - x2, y3 - y2);
  const pieces = Math.min(512, Math.max(4, Math.ceil(hull * 2)));
  for (let k = 1; k <= pieces; k++) {
    const t = k / pieces, s = 1 - t, a = s * s * s, b = 3 * s * s * t, c = 3 * s * t * t, e = t * t * t;
    flatPoint(a * x0 + b * x1 + c * x2 + e * x3, a * y0 + b * y1 + c * y2 + e * y3);
  }
}
// the point at a distance along the edge, into `POINT`
function place(one, distance) {
  const xs = one.xs, ys = one.ys, last = xs.length - 1;
  const f = Math.min(last, Math.max(0, distance / Math.max(1e-6, one.length) * last));
  const i = Math.min(last - 1, Math.floor(f)), u = f - i;
  POINT.x = xs[i] + (xs[i + 1] - xs[i]) * u;
  POINT.y = ys[i] + (ys[i + 1] - ys[i]) * u;
}
/* Whether the 2D map is in view, kept by an observer of its drawing as it shows and hides, so a frame never asks the
 * page for a layout: `checkVisibility` in each frame forced one after the last frame's writes (round 7's F5,
 * 2026-10-16). It starts seen, and the flow wakes when the map comes back into view, since a frame that finds it
 * hidden asks for no next one. */
function watch2d(svg) {
  FLOW2D.watcher ??= new IntersectionObserver(entries => {
    const entry = entries[entries.length - 1];
    if (entry.target !== FLOW2D.watched) return;
    const was = FLOW2D.seen;
    FLOW2D.seen = entry.isIntersecting;
    if (FLOW2D.seen && !was) wake2d();
  });
  if (FLOW2D.watched) FLOW2D.watcher.unobserve(FLOW2D.watched);
  FLOW2D.watched = svg; FLOW2D.seen = true;
  FLOW2D.watcher.observe(svg);
}
/* A frame of the flow: every read first, whether the map is drawn and which edges are still in it, then the writes.
 * It allocates nothing but the text of what it writes. */
function frame2d(now) {
  FLOW2D.id = 0;
  const edges = FLOW2D.edges;
  let shown = 0;
  for (let i = 0; i < edges.length; i++) if (edges[i].path.isConnected) shown++;
  if (M.svg && M.svg !== FLOW2D.watched) watch2d(M.svg);
  if (!shown || !M.svg || !FLOW2D.seen) return;
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
// a path's `d`, written only when it changes
function drawn2d(shape, d) {
  if (shape.d !== d) {
    shape.d = d;
    shape.element.setAttribute('d', d);
  }
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
  let asks = false, since = 0, size = 0, reply = FLOW.reply;
  if (!resting) {
    const now = flowAt(join);
    asks = now.asks; since = now.since;
    if (asks) { size = now.size; reply = now.reply; }
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
    drawn2d(one.ask, `M${POINT.x.toFixed(2)},${POINT.y.toFixed(2)}h0`);
  }
  show2d(one.ask, asking);
  // the reply: a line the way the data goes, both ways on a join whose information goes both ways; the first runs
  // back to the receiver, the second forth
  const ways = replying ? (join.ifd === 'both' ? 2 : 1) : 0;
  for (let index = 0; index < 2; index++) {
    const train = one.trains[index];
    if (index < ways) reply2d(train, (since - FLOW.ask) / reply, index === 0, size, one, receives);
    show2d(train.g, index < ways);
  }
}
/* A reply's line along the edge, `size` times the request's size long, `replySize`: it leaves as the request arrives
 * and its end arrives as the reply ends; an edge too short for it shows it the edge's length. It is the stretch of the
 * edge's own curve between its two ends, its samples between them, so it bends as the edge does; its round caps add
 * the request's size, so a reply is never smaller than its request. One path, written once a frame while it moves. */
function reply2d(train, t, back, size, one, receives) {
  const length = one.length, long = Math.min(1, size * ASK / Math.max(1, length));
  const head = t * (1 + long), from = Math.max(0, head - long), to = Math.min(1, head);
  if (from > to) { drawn2d(train.line, ''); return; }
  // its ends as distances along the path, which runs against the data when the line runs back
  const forward = receives === back;
  const start = (forward ? from : 1 - to) * length, end = (forward ? to : 1 - from) * length;
  place(one, start);
  let d = `M${POINT.x.toFixed(2)},${POINT.y.toFixed(2)}`;
  if (end - start < 0.01) d += 'h0';
  else {
    const xs = one.xs, ys = one.ys, last = xs.length - 1, per = length / last;
    for (let i = Math.floor(start / per) + 1; i < last && i * per < end; i++) {
      d += `L${xs[i].toFixed(2)},${ys[i].toFixed(2)}`;
    }
    place(one, end);
    d += `L${POINT.x.toFixed(2)},${POINT.y.toFixed(2)}`;
  }
  drawn2d(train.line, d);
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
