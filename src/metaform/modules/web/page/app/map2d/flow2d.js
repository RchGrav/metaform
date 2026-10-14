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
 * gets a group of shapes over it, moved along the edge each frame, `frame2d`, while the page is in use, as the 3D map
 * draws its flow, `FRAMES`; with reduced motion nothing moves and nothing is shown. */
const FLOW2D = {id: 0, edges: []};
// an element's own colour on the map, as the 3D map draws it, for what comes from it
function color2d(id) {
  const node = G?.graphData().nodes.find(one => one.id === id);
  return node ? colorOf(node) : css('--signal');
}
export function flows2d() {
  for (const old of M.svg?.querySelectorAll('g.flows2d') || []) old.remove();
  FLOW2D.edges = [];
  const on = flowing2d();
  if (!on.length) return;
  // a group of their own just over the edges, so the edges stay what they are
  const flows = document.createElementNS(SVG, 'g'), edges = on[0].path.closest('.edgePaths') || on[0].path.parentNode;
  flows.setAttribute('class', 'flows2d');
  edges.after(flows);
  const made = (tag, name, attributes = {}) => {
    const shape = document.createElementNS(SVG, tag);
    shape.setAttribute('class', name);
    for (const [key, value] of Object.entries(attributes)) shape.setAttribute(key, value);
    shape.style.display = 'none';
    flows.append(shape);
    return shape;
  };
  for (const edge of on) FLOW2D.edges.push(edgeShapes(edge, made));
  wake2d();
}
/* The edges that flow: in all, every edge; in hover, the edges of the node the pointer is on; else the selection's. */
function flowing2d() {
  const mode = flowModeNow(), hover = mode === 'hover' ? HOVER2D.on : null;
  return M.edges.filter(edge => edge.join && (mode === 'all' || (hover ? edge.join.receiver === hover
    || edge.provider === hover : edge.path?.classList.contains('on'))));
}
/* One edge's shapes: a reply's train of dots each way, in the colour of the element it comes from, `fxTrain`; the
 * request; the record card and the ring it lands with. */
function edgeShapes(edge, made) {
  return {edge, length: edge.path.getTotalLength(),
    trains: [0, 1].map(way => ({color: color2d(way === 0 ? edge.provider : edge.join.receiver),
      beads: Array.from({length: 12}, () => made('circle', 'bead', {r: 2.1}))})),
    ask: made('circle', 'ask', {r: 1.9}),
    record: made('rect', 'record', {x: -4.5, y: -3.2, width: 9, height: 6.4, rx: 1.4}),
    ring: made('circle', 'ring', {r: 4})};
}
export function wake2d() {
  if (!FLOW2D.id && FLOW2D.edges.length && !reduced()) FLOW2D.id = requestAnimationFrame(frame2d);
  again2d();  // the figures and the mascot on the 2D map wake with any act too
}
/* A point at a distance along an edge, looked up in the edge's curve sampled once, `sampled`, never measured again each
 * frame: measuring a curve for every dot on every frame was the page's own heaviest work. */
function sampled(one) {
  if (!one.samples) {
    const count = Math.max(16, Math.ceil(one.length / 3));
    one.samples = Array.from({length: count + 1}, (_, i) => one.edge.path.getPointAtLength(one.length * i / count));
  }
  return one.samples;
}
function pointOn(one, distance) {
  const points = sampled(one), last = points.length - 1;
  const f = Math.min(last, Math.max(0, distance / Math.max(1e-6, one.length) * last));
  const i = Math.min(last - 1, Math.floor(f));
  const u = f - i, a = points[i], b = points[i + 1];
  return {x: a.x + (b.x - a.x) * u, y: a.y + (b.y - a.y) * u};
}
function frame2d(now) {
  FLOW2D.id = 0;
  const shown = FLOW2D.edges.filter(one => one.edge.path.isConnected);
  if (!shown.length || !M.svg?.getClientRects().length) return;
  // it rests as the 3D map's flow rests, once nothing was done for web_flow_seconds, until the next act
  const resting = reduced() || (FRAMES.rest !== null && performance.now() - FRAMES.active > FRAMES.idle);
  flowTick(now);
  // the flow mode, web_flow_mode: off and live draw none of it here; a change eases it in or out
  const wanted = ['hover', 'selected', 'all'].includes(flowModeNow()) ? 1 : 0, was = FLOW2D.fade ?? wanted;
  FLOW2D.fade = was + (wanted - was) * (1 - Math.exp(-Math.max(0, FLOW.clock - (FLOW2D.at ?? FLOW.clock)) * FLOW.ease));
  FLOW2D.at = FLOW.clock;
  const group = shown[0].ask.parentNode;
  if (group) group.style.opacity = FLOW2D.fade.toFixed(3);
  if (FLOW2D.fade < 0.01 && !wanted) {
    for (const shape of group?.children || []) shape.style.display = 'none';
    return;
  }
  for (const one of shown) flowEdge2d(one, resting);
  if (!resting) FLOW2D.id = requestAnimationFrame(frame2d);
}
const place2dShape = (shape, point) => {
  shape.style.display = '';
  shape.setAttribute('transform', `translate(${point.x} ${point.y})`);
};
/* One edge's flow this frame, the way its information goes: its records, its ring as one lands, its request, and its
 * reply's trains. Resting, nothing is shown. */
function flowEdge2d(one, resting) {
  const {edge, length, trains, ask, record, ring} = one, join = edge.join, receives = join.ifd === 'receives';
  const along = share => (receives ? 1 - share : share) * length;  // the edge runs the way its information goes
  const at = share => pointOn(one, along(Math.min(1, Math.max(0, share))));
  for (const shape of [ask, record, ring, ...trains.flatMap(train => train.beads)]) shape.style.display = 'none';
  if (resting) return;
  const {asks, since, amount = 7, reply = FLOW.reply} = flowAt(join);
  if (!asks) {
    if (since < FLOW.send) { const t = since / FLOW.send; place2dShape(record, at(t * t * (3 - 2 * t))); }
    else if (since < FLOW.send + FLOW.burst) {
      const u = (since - FLOW.send) / FLOW.burst;
      place2dShape(ring, at(1));
      ring.setAttribute('r', String(4 + 14 * u));
      ring.style.opacity = String(Math.pow(1 - u, 1.5));
    }
  } else if (since < FLOW.ask) place2dShape(ask, at(since / FLOW.ask));
  else if (since < FLOW.ask + reply) {  // the reply: a train of dots the way the data goes
    const t = (since - FLOW.ask) / reply;
    (join.ifd === 'both' ? [true, false] : [true]).forEach((back, index) => {
      train2d(trains[index], t, back, amount, length, at);
    });
  }
}
/* A reply's train of beads along the edge, spaced so they read as dots, the last few fading. */
function train2d({beads, color}, t, back, amount, length, at) {
  const spacing = Math.max(0.03, 2.1 * 2 * 2.3 / Math.max(1, length));
  const shown = Math.max(2, Math.min(beads.length, amount, Math.floor(0.6 / spacing) + 1));
  const head = t * (1 + spacing * (shown - 1));
  beads.forEach((bead, i) => {
    const s = head - spacing * i;
    if (i >= shown || s < 0 || s > 1) return;
    place2dShape(bead, at(back ? 1 - s : s));
    bead.style.fill = color;
    bead.style.opacity = String(i < shown - 3 ? 1 : 1 - (i - (shown - 4)) / 4);
  });
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
