/* What each agent at work says, and what the mascot says, in comic word bubbles drawn as SVG in one layer over the
 * maps, `#bubbles`. A bubble is a white body with rounded corners, tilted so its top rises to the right, a thick dark
 * outline of one weight whatever its size, a soft shadow below and right, and bold words that wrap; the body grows and
 * shrinks around them. Its tail is drawn again every frame from the body to the speaker's head as it is on the screen,
 * `tailOf`, wherever the body sits, so the tail always shows who speaks (code.interface.graphical#c7, 2026-10-18).
 * Each bubble starts above its speaker and stays inside the map it is drawn over; nearest speaker first, one that would
 * cover a bubble placed before it is pushed apart, `apart`, eased over a few frames so it settles without jumping, its
 * tail following. A speaker off the screen keeps its bubble at the view's edge, its tail running to that edge toward
 * the speaker. An agent farther than the nearest one talking is drawn dimmer, still solid, and a nearer bubble covers a
 * farther one. A new line shows for web_bubble_seconds (auto by default, by its words, `bubbleSeconds`) and goes,
 * fading in and out by the clock, so at any frame rate; the pointer on an agent brings its last line back. In the agent
 * view, V, the agent seen through has no body on the screen, so its words are at the bottom of the view for as long as
 * it says them, the tail pointing down out of the view. The words are the newest line the agent said in its thread,
 * `said` on its session from the server, never its tool calls or its thinking (code.interface.graphical#81).
 * The elements are a pool made once and reused, `POOL`; each frame reads everything first, places the bubbles, then
 * writes the DOM in one pass, `bubbles3d`, and a body is laid out again only when its words change. */
import * as THREE from 'three';
import {eyeOf} from '/page/agents3d.js';
import {reduced} from '/page/app/core/dom.js';
import {ROAM} from '/page/app/figures/agents.js';
import {D} from '/page/app/agents/dispatch.js';
import {G, wake3d} from '/page/app/map3d/graph3d.js';
import {WS} from '/page/app/workspace/workspace.js';
import {BUBBLE, bubbleSeconds} from '/page/app/figures/bubble.js';

export const LOOK = {
  most: 140,  // the most characters shown; a longer line is cut at a word with an ellipsis
  width: 340,  // the widest the words run, SVG pixels
  font: 26, lines: 3, lineGap: 1.18,
  // a roundtable seat's bubble holds its whole turn: more characters, wider, more lines; it grows with its words
  seat: {most: 900, width: 560, lines: 10},
  family: "'Comic Neue', 'Comic Sans MS', 'Chalkboard SE', 'Trebuchet MS', sans-serif",
  padX: 22, padY: 16, minWidth: 90,
  tilt: -4,  // degrees; negative rises to the right
  outline: 6, radius: 22, shadowX: 7, shadowY: 8,
  base: 34,  // the tail's width where it leaves the body
  rise: 40, aside: 0.35,  // where a bubble starts: its body this far above the head, and moved right by this share
  name: 18,  // the size of the speaker's name over the body, SVG pixels
  dimmest: 0.33,  // the brightness of the farthest bubbles
  lift: 0.6,  // the speaker's head on the screen, where the tail points: this many figure sizes above its eyes
  pop: 320,  // ms of the pop when new words arrive
  fade: 84,  // ms, the time constant of the fade in and out: full within about a quarter of a second
  settle: 60,  // ms, the time constant of a bubble easing to the place it is pushed to
  margin: 6, gap: 6,  // the room kept from the view's edge, and between two bubbles, CSS pixels
};
/* The bubbles' size on the screen, CSS pixels per SVG pixel, the same for every bubble at any distance: key 5 steps
 * through these, the first the smallest allowed; the choice is kept in this browser. */
export const BUBBLE_SIZES = [0.75, 0.9, 1.05, 1.25, 1.5];
const SIZE_KEY = 'metaform.bubbleSize';
const DEFAULT_SIZE = 3;
const SIZE = {at: (() => {
  try {
    const saved = localStorage.getItem(SIZE_KEY), at = Number(saved);
    return saved !== null && saved.trim() !== '' && Number.isInteger(at)
      ? Math.min(BUBBLE_SIZES.length - 1, Math.max(0, at)) : DEFAULT_SIZE;
  } catch { return DEFAULT_SIZE; }
})()};
export function stepBubbleSize() {
  SIZE.at = (SIZE.at + 1) % BUBBLE_SIZES.length;
  try { localStorage.setItem(SIZE_KEY, String(SIZE.at)); } catch { /* storage can be blocked; the page keeps it */ }
  wake3d();
  return SIZE.at;
}
/* The body the person sees through in the agent view, V, set by `eyesOf`; null in their own view and the mascot's. */
export const WATCHED = {mesh: null};
/* The roundtable's seats, roundtable/stage.js: while its stage is on, `on`, the stage's frame runs here, `frame`, just
 * before the bubbles are placed, and each seat speaks through `list`, a pool of `Seated` the stage grows only as it
 * opens a table; the agents' figures in the map behind it say nothing meanwhile. */
export const SEATS = {on: false, frame: null, list: []};
export class Seated {
  constructor(n) {
    this.id = `\u0000seat${n}`;  // the pool's id for the seat's words, never a figure's
    // what it says: the line, cut for a bubble, when it began, how much it shows, 0 to 1, and the seat's name
    this.text = ''; this.lineAt = 0; this.want = 0; this.name = '';
    // its head on the page and the stage's edges, CSS pixels, and how far it is from the stage's eye
    this.x = 0; this.y = 0; this.left = 0; this.top = 0; this.right = 0; this.bottom = 0; this.far = 0;
  }
}
const MASCOT_ID = '\u0000mascot';  // the pool's id for the mascot's words, never a figure's
const HEAD = new THREE.Vector3(), GAZE = new THREE.Vector3(), SEEN = new THREE.Vector3();
const MEASURE = document.createElement('canvas').getContext('2d');
const TURN = LOOK.tilt * Math.PI / 180, COS = Math.cos(TURN), SIN = Math.sin(TURN);

/* The line a bubble shows: the last non-empty line of what the agent said, or with `whole` all of it, cut at a word
 * past `most` characters. */
export function bubbleText(text, most = LOOK.most, whole = false) {
  const parts = String(text || '').split(/\r?\n/).map(part => part.trim()).filter(Boolean);
  const line = whole ? parts.join(' ') : parts.at(-1) || '';
  const flat = line.replace(/[*_`#>]+/g, '').replace(/\s+/g, ' ').trim();
  if (flat.length <= most) return flat;
  const start = flat.slice(0, most - 1), word = start.lastIndexOf(' ');
  return `${(word > 40 ? start.slice(0, word) : start).trimEnd()}…`;
}
/* The words wrapped to the bubble's width, the font shrinking a step at a time until they fit in `lines`; words that
 * still run past them at the smallest size end the last line kept with an ellipsis, so the cut shows. */
function wrapped(text, width = LOOK.width, most = LOOK.lines) {
  for (let size = LOOK.font; size >= 16; size -= 2) {
    MEASURE.font = `800 ${size}px ${LOOK.family}`;
    const lines = [];
    let line = '';
    for (const word of text.split(' ')) {
      const next = line ? `${line} ${word}` : word;
      if (!line || MEASURE.measureText(next).width <= width) line = next;
      else { lines.push(line); line = word; }
    }
    if (line) lines.push(line);
    if (lines.length <= most || size <= 16) {
      const kept = lines.length <= most ? lines : cutLast(lines.slice(0, most), width);
      return {size, lines: kept, wide: Math.max(...kept.map(one => MEASURE.measureText(one).width))};
    }
  }
  return {size: 16, lines: [text], wide: width};
}
/* The last line ended with an ellipsis, a word at a time taken off, a letter at a time if one word, until it fits. */
function cutLast(lines, width = LOOK.width) {
  let last = `${lines.at(-1)}…`;
  while (last.length > 1 && MEASURE.measureText(last).width > width) {
    const words = last.slice(0, -1).trimEnd();
    const space = words.lastIndexOf(' ');
    last = `${space > 0 ? words.slice(0, space) : words.slice(0, -1)}…`;
  }
  lines[lines.length - 1] = last;
  return lines;
}

/* One bubble of the pool: its elements, made once, and its state, every field set here in one order. The body path
 * and the tail path are drawn once each, in the paper layer, and shown again by reference in the shadow and the ink
 * layers under it: the ink is stroked twice the outline's width, so the paper over it leaves the outline outside the
 * body and the tail as one shape. */
const SVG_NS = 'http://www.w3.org/2000/svg';
function svg(name, attributes) {
  const el = document.createElementNS(SVG_NS, name);
  for (const key in attributes) el.setAttribute(key, attributes[key]);
  return el;
}
class Bubble {
  constructor(n) {
    this.id = null;  // the figure whose words it shows, MASCOT_ID for the mascot's, null while free
    this.el = document.createElement('div');
    this.el.className = 'wbubble';
    this.el.style.display = 'none';
    this.svg = svg('svg', {overflow: 'visible', 'aria-hidden': 'true'});
    this.turn = svg('g', {});
    this.body = svg('path', {id: `wbubble-body-${n}`});
    this.tail = svg('path', {id: `wbubble-tail-${n}`});
    this.paper = svg('g', {class: 'paper', fill: '#fff'});
    this.words = svg('g', {class: 'words', 'font-family': LOOK.family.replace(/"/g, "'")});
    const shade = svg('g', {class: 'shade', transform: `translate(${LOOK.shadowX} ${LOOK.shadowY})`});
    const ink = svg('g', {class: 'ink', 'stroke-width': 2 * LOOK.outline});
    for (const layer of [shade, ink]) {
      layer.append(svg('use', {href: `#wbubble-body-${n}`}), svg('use', {href: `#wbubble-tail-${n}`}));
    }
    this.paper.append(this.body, this.tail);
    this.turn.append(shade, ink, this.paper, this.words);
    this.svg.append(this.turn);
    this.said = document.createElement('span');  // the words for screen readers
    this.said.className = 'said';
    this.el.append(this.svg, this.said);
    this.el.addEventListener('click', clickBubble);
    // what it says: the raw words heard, the line shown, the session line they belong to, when that line began, how
    // long it shows, and its laid-out body (font size, lines, width and height in SVG pixels); `dirty` until written
    this.raw = ''; this.text = ''; this.sid = ''; this.seq = -1; this.lineAt = 0; this.lasts = 0;
    this.size = 0; this.lines = null; this.w = 0; this.h = 0; this.dirty = false;
    // this frame: the frame it was last met, wanted or not, how far it has faded in and when that last stepped, shown
    // or not and whether it was the frame before, the agent view's own, the mascot's, its name and whether it is
    // clicked, and how far its speaker is
    this.seen = 0; this.want = 0; this.shown = 0; this.at = 0; this.on = false; this.was = false;
    this.fixed = false; this.mascot = false; this.name = ''; this.clickable = false; this.far = 0;
    // on the screen, CSS pixels: the speaker's head, the map's edges, the scale and the pop, the body's half extents,
    // where it starts, how far it is eased from there, where it is, the tail's tip, its brightness and its stacking
    this.hx = 0; this.hy = 0; this.left = 0; this.top = 0; this.right = 0; this.bottom = 0;
    this.k = 0; this.grow = 1; this.ex = 0; this.ey = 0;
    this.nx = 0; this.ny = 0; this.ox = 0; this.oy = 0; this.x = 0; this.y = 0; this.tipX = 0; this.tipY = 0;
    this.dim = 1; this.z = 0; this.lx = 0; this.ly = 0;  // lx, ly: the tip in the body's frame, `tipInBody`
    // what was last written, so a write happens only when it changes
    this.wrote = {shown: false, x: NaN, y: NaN, k: NaN, opacity: NaN, z: -1, paper: -1, name: '', clickable: false,
      lx: NaN, ly: NaN};
  }
}
/* The layer the bubbles are drawn in, over both maps, made with the page, and the pool of bubbles in it, grown by
 * `take` only when more speak at once than it holds. `live` tells screen readers the mascot's lines as they come: one
 * hidden status always in the layer, apart from the drawn bubble, which comes and goes; `heard` is the line it holds. */
const POOL = [];
const LAYER = {el: document.createElement('div'), live: document.createElement('span'), heard: ''};
LAYER.el.id = 'bubbles';
LAYER.live.className = 'heard';
LAYER.live.setAttribute('role', 'status');
LAYER.live.setAttribute('aria-live', 'polite');
LAYER.el.append(LAYER.live);
document.body.append(LAYER.el);
function grow(count) {
  for (let n = POOL.length; n < count; n++) {
    const bubble = new Bubble(n);
    POOL.push(bubble);
    LAYER.el.append(bubble.el);
  }
}
/* The bubble showing `id`'s words, or null. */
function bubbleOf(id) {
  for (let n = 0; n < POOL.length; n++) if (POOL[n].id === id) return POOL[n];
  return null;
}
/* A free bubble for `id`, the pool grown when none is free. */
function take(id) {
  let bubble = null;
  for (let n = 0; n < POOL.length && !bubble; n++) if (POOL[n].id === null) bubble = POOL[n];
  if (!bubble) { grow(Math.max(8, POOL.length * 2)); return take(id); }
  bubble.id = id;
  bubble.el.dataset.who = id === MASCOT_ID ? 'mascot' : id;  // whose words, for a check and a reader of the page
  bubble.raw = bubble.text = bubble.sid = '';
  bubble.seq = -1; bubble.lineAt = 0; bubble.shown = 0; bubble.at = FRAME.now; bubble.ox = bubble.oy = 0;
  return bubble;
}
/* New words: the body laid out for them, its size measured now and its elements written with the frame's writes. */
function laidOut(bubble, text, seat = false) {
  bubble.text = text;
  const {size, lines, wide} = seat ? wrapped(text, LOOK.seat.width, LOOK.seat.lines) : wrapped(text);
  bubble.size = size; bubble.lines = lines;
  bubble.w = Math.max(LOOK.minWidth, Math.ceil(wide) + 2 * LOOK.padX);
  bubble.h = Math.ceil(lines.length * size * LOOK.lineGap + 2 * LOOK.padY);
  bubble.dirty = true;
}
function writeBody(bubble) {
  const {w, h, size} = bubble, r = Math.min(LOOK.radius, h / 2.4), lineHeight = size * LOOK.lineGap;
  bubble.svg.setAttribute('width', w); bubble.svg.setAttribute('height', h);
  bubble.svg.style.left = `${-w / 2}px`; bubble.svg.style.top = `${-h / 2}px`;
  bubble.el.style.setProperty('--w', `${w}px`); bubble.el.style.setProperty('--h', `${h}px`);
  bubble.turn.setAttribute('transform', `rotate(${LOOK.tilt} ${w / 2} ${h / 2})`);
  bubble.body.setAttribute('d', `M${r},0 H${w - r} Q${w},0 ${w},${r} V${h - r} Q${w},${h} ${w - r},${h} H${r} `
    + `Q0,${h} 0,${h - r} V${r} Q0,0 ${r},0 Z`);
  bubble.words.setAttribute('font-size', size);
  bubble.words.replaceChildren(...bubble.lines.map((line, n) => {
    const one = svg('text', {x: w / 2, y: LOOK.padY + (n + 0.5) * lineHeight});
    one.textContent = line;
    return one;
  }));
  // an agent's words are there to be read; the mascot's are told by the layer's status, `LAYER.live`, and not twice
  bubble.said.textContent = bubble.id === MASCOT_ID ? '' : bubble.text;
  bubble.dirty = false;
}

/* A click on the mascot's bubble does what it was said with, and the bubble goes. An agent's bubble takes no click of
 * its own: a click on it reaches the 3D map, which opens its agent, `bubbleAt`. */
function clickBubble(event) {
  event.stopPropagation();
  const act = BUBBLE.click;
  if (!act) return;
  BUBBLE.until = 0;
  BUBBLE.el?.classList.remove('on');
  act();
}
/* The agent whose bubble is drawn at the page point x, y, the nearest one where two overlap, for a click on its
 * words; else null. */
export function bubbleAt(x, y) {
  for (let n = 0; n < SHOWN.length; n++) {
    const bubble = SHOWN[n];
    if (bubble.mascot || !bubble.on) continue;
    if (Math.abs(x - bubble.x) <= bubble.ex && Math.abs(y - bubble.y) <= bubble.ey) return bubble.id;
  }
  return null;
}

/* The agent the pointer is over, read once a frame from the 3D map's own pointer, `figureUnder`: its last bubble shows
 * for as long as the pointer stays on it. */
const HOVER = {id: null, x: 0, y: 0, moved: false, best: Infinity};  // best: how near the ray passes
const RAY = new THREE.Raycaster(), POINT = new THREE.Vector2(), BALL = new THREE.Sphere(), MIDDLE = new THREE.Vector3();
addEventListener('pointermove', event => {
  HOVER.x = event.clientX; HOVER.y = event.clientY; HOVER.moved = true;
}, {passive: true});
function figureUnder() {
  if (!HOVER.moved) return HOVER.id;
  HOVER.moved = false;
  if (!AREA.width || HOVER.x < AREA.left || HOVER.x > AREA.right || HOVER.y < AREA.top || HOVER.y > AREA.bottom) {
    return (HOVER.id = null);
  }
  POINT.set((HOVER.x - AREA.left) / AREA.width * 2 - 1, -(HOVER.y - AREA.top) / AREA.height * 2 + 1);
  RAY.setFromCamera(POINT, G.camera());
  HOVER.id = null;
  HOVER.best = Infinity;
  ROAM.figures.forEach(nearestUnder);
  return HOVER.id;
}
function nearestUnder(figure, id) {
  const size = Math.max(0.5, figure.mesh.scale.x), middle = figure.mesh.getWorldPosition(MIDDLE);
  BALL.set(middle, size);
  if (!RAY.ray.intersectsSphere(BALL)) return;
  const off = RAY.ray.distanceToPoint(middle) / size;
  if (off < HOVER.best) { HOVER.best = off; HOVER.id = id; }
}

/* The newest line of the running session of a figure, from the sessions the page reads; null when it says nothing. */
function sessionOf(figure) {
  if (figure.child || figure.stage === 'leaving' || figure.done) return null;
  const sessions = D.sessions;
  let found = null;
  for (let n = 0; n < sessions.length; n++) {
    const one = sessions[n];
    if (one.work_id === figure.id && one.state === 'running') found = one;
  }
  return found && found.activity === 'working' && found.said?.text ? found : null;
}
/* What the frame shares: its number and clock, the camera, reduced motion, the scale, the agent under the pointer,
 * and the 3D map's area on the page, read once. */
const FRAME = {n: 0, now: 0, last: 0, camera: null, still: false, scale: 1, under: null};
const AREA = {left: 0, top: 0, right: 0, bottom: 0, width: 0, height: 0};
const easeOut = k => 1 + 2.4 * (k - 1) ** 3 + 1.4 * (k - 1) ** 2;  // overshoots a little, then settles
/* The fade toward what the bubble wants, by the clock, so it comes and goes in the same time at any frame rate. */
function fade(bubble) {
  const step = FRAME.still ? 1 : 1 - Math.exp(-(FRAME.now - bubble.at) / LOOK.fade);
  bubble.shown += (bubble.want - bubble.shown) * step;
  bubble.at = FRAME.now;
}
/* Where the speaker's head is on the page, from its eyes, LOOK.lift figure sizes up: false when it is behind the eye,
 * where it says nothing on the screen. */
function headOf(bubble, mesh) {
  const camera = FRAME.camera;
  eyeOf(mesh, HEAD, GAZE);
  HEAD.y += LOOK.lift * mesh.scale.x;
  if (SEEN.copy(HEAD).applyMatrix4(camera.matrixWorldInverse).z >= -camera.near) return false;
  bubble.far = HEAD.distanceTo(camera.position);
  HEAD.project(camera);
  bubble.hx = AREA.left + (HEAD.x + 1) / 2 * AREA.width;
  bubble.hy = AREA.top + (1 - HEAD.y) / 2 * AREA.height;
  bubble.left = AREA.left; bubble.top = AREA.top; bubble.right = AREA.right; bubble.bottom = AREA.bottom;
  return true;
}
/* An agent's words this frame: new words laid out, its fade, and where its speaker is. */
function heard(figure, id) {
  const session = sessionOf(figure);
  let bubble = bubbleOf(id);
  if (!session && !bubble) return;
  bubble ||= take(id);
  bubble.seen = FRAME.n;
  if (session) {
    // a new line starts its time; the same line growing as it streams is laid out again and keeps its start, its
    // time set again by its words, `lasts`
    if (session.session_id !== bubble.sid || session.said.seq !== bubble.seq) {
      bubble.sid = session.session_id; bubble.seq = session.said.seq; bubble.lineAt = FRAME.now;
    }
    if (session.said.text !== bubble.raw) {
      bubble.raw = session.said.text;
      const text = bubbleText(bubble.raw);
      if (text && text !== bubble.text) {
        laidOut(bubble, text);
        bubble.lasts = 1000 * bubbleSeconds(text, WS.view()?.bubble_seconds ?? 'auto');
      }
    }
  }
  // a new line shows for web_bubble_seconds and goes; the pointer on the agent brings its last line back; the agent
  // seen through in the agent view shows what it says for as long as it says it
  const watched = figure.mesh === WATCHED.mesh;
  const fresh = session && (watched || FRAME.now - bubble.lineAt < bubble.lasts);
  bubble.want = bubble.text && (fresh || FRAME.under === id) ? 1 : 0;
  fade(bubble);
  bubble.fixed = watched; bubble.mascot = false; bubble.name = ''; bubble.clickable = false;
  bubble.on = bubble.shown > 0.02 && (watched || (figure.mesh.visible && headOf(bubble, figure.mesh)));
  if (!bubble.on) return;
  if (watched) {  // at the bottom of the view, in its middle, the tail pointing down out of it at the one speaking
    bubble.far = -1;
    bubble.left = AREA.left; bubble.top = AREA.top; bubble.right = AREA.right; bubble.bottom = AREA.bottom;
    bubble.hx = (AREA.left + AREA.right) / 2; bubble.hy = AREA.bottom + AREA.height;
  }
  SHOWN.push(bubble);
}
/* The mascot's words, or an embodied agent's through its figure, said with `say`; where its speaker is was read by
 * `placeBubble` just before. */
function heardMascot() {
  let bubble = bubbleOf(MASCOT_ID);
  if (!BUBBLE.seen && !bubble) return;
  bubble ||= take(MASCOT_ID);
  bubble.seen = FRAME.n;
  if (BUBBLE.since !== bubble.lineAt) bubble.lineAt = BUBBLE.since;
  if (BUBBLE.text && BUBBLE.text !== bubble.text) laidOut(bubble, BUBBLE.text);
  bubble.want = BUBBLE.seen ? 1 : 0;
  fade(bubble);
  bubble.fixed = false; bubble.mascot = true; bubble.name = BUBBLE.name; bubble.clickable = Boolean(BUBBLE.click);
  bubble.on = bubble.shown > 0.02 && BUBBLE.found && Boolean(bubble.text);
  if (!bubble.on) return;
  bubble.far = -0.5;  // after the agent view's own, before every agent's: the mascot keeps its place
  bubble.hx = BUBBLE.x; bubble.hy = BUBBLE.y;
  bubble.left = BUBBLE.left; bubble.top = BUBBLE.top; bubble.right = BUBBLE.right; bubble.bottom = BUBBLE.bottom;
  SHOWN.push(bubble);
}

/* A seat's words at the roundtable, where its head was read by the stage's frame just before. */
function heardSeat(seat) {
  let bubble = bubbleOf(seat.id);
  if (!seat.want && !bubble) return;
  bubble ||= take(seat.id);
  bubble.seen = FRAME.n;
  if (seat.lineAt !== bubble.lineAt) bubble.lineAt = seat.lineAt;
  if (seat.text && seat.text !== bubble.text) laidOut(bubble, seat.text, true);
  bubble.want = seat.want;
  fade(bubble);
  bubble.fixed = false; bubble.mascot = false; bubble.name = seat.name; bubble.clickable = false;
  bubble.on = bubble.shown > 0.02 && Boolean(bubble.text);
  if (!bubble.on) return;
  bubble.far = seat.far;
  bubble.hx = seat.x; bubble.hy = seat.y;
  bubble.left = seat.left; bubble.top = seat.top; bubble.right = seat.right; bubble.bottom = seat.bottom;
  SHOWN.push(bubble);
}

/* The bubbles shown this frame, nearest speaker first, the agent view's own first of all, then the mascot's: sorted
 * in place. */
const SHOWN = [];
function nearestFirst() {
  for (let n = 1; n < SHOWN.length; n++) {
    const one = SHOWN[n];
    let at = n - 1;
    while (at >= 0 && SHOWN[at].far > one.far) { SHOWN[at + 1] = SHOWN[at]; at--; }
    SHOWN[at + 1] = one;
  }
}
/* The boxes of the bubbles placed this frame, where each is settling to, CSS pixels, one array per edge; grown, never
 * shrunk, when more speak than it holds. */
const PLACED = {n: 0, x0: new Float64Array(32), y0: new Float64Array(32), x1: new Float64Array(32),
  y1: new Float64Array(32)};
function keep(x0, y0, x1, y1) {
  if (PLACED.n === PLACED.x0.length) {
    for (const edge of ['x0', 'y0', 'x1', 'y1']) {
      const more = new Float64Array(PLACED.n * 2);
      more.set(PLACED[edge]);
      PLACED[edge] = more;
    }
  }
  PLACED.x0[PLACED.n] = x0; PLACED.y0[PLACED.n] = y0; PLACED.x1[PLACED.n] = x1; PLACED.y1[PLACED.n] = y1;
  PLACED.n++;
}
/* The move tried for the bubble being placed, kept inside its map; the best so far is the one that covers the least
 * of the placed boxes, then the one moved least. */
const MOVE = {x: 0, y: 0, ex: 0, ey: 0, x0: 0, y0: 0, x1: 0, y1: 0, dx: 0, dy: 0, cover: Infinity, far: Infinity};
function covers(x, y) {
  const x0 = x - MOVE.ex, x1 = x + MOVE.ex, y0 = y - MOVE.ey, y1 = y + MOVE.ey;
  let area = 0;
  for (let n = 0; n < PLACED.n; n++) {
    const w = Math.min(x1, PLACED.x1[n]) - Math.max(x0, PLACED.x0[n]);
    const h = Math.min(y1, PLACED.y1[n]) - Math.max(y0, PLACED.y0[n]);
    if (w > 0 && h > 0) area += w * h;
  }
  return area;
}
const inside = (at, half, low, high) => high - low < 2 * half ? (low + high) / 2 : Math.min(Math.max(at, low + half),
  high - half);
function tryMove(dx, dy) {
  const x = inside(MOVE.x + dx, MOVE.ex, MOVE.x0, MOVE.x1), y = inside(MOVE.y + dy, MOVE.ey, MOVE.y0, MOVE.y1);
  dx = x - MOVE.x; dy = y - MOVE.y;
  const cover = covers(x, y), far = dx * dx + dy * dy;
  if (cover < MOVE.cover - 1e-6 || (cover <= MOVE.cover + 1e-6 && far < MOVE.far)) {
    MOVE.dx = dx; MOVE.dy = dy; MOVE.cover = cover; MOVE.far = far;
  }
}
/* A bubble set apart from the bubbles placed before it this frame, inside its map: where it starts, else just above,
 * below, right or left of one placed already, by the overlap and a gap, whichever covers no other bubble and moves it
 * least. With no free place it takes the one that covers the least, and the nearer bubble is drawn over it. */
function apart(bubble, x, y) {
  const margin = LOOK.margin, gap = LOOK.gap;
  MOVE.x = x; MOVE.y = y; MOVE.ex = bubble.ex; MOVE.ey = bubble.ey;
  MOVE.x0 = bubble.left + margin; MOVE.x1 = bubble.right - margin;
  MOVE.y0 = bubble.top + margin; MOVE.y1 = bubble.bottom - margin;
  MOVE.cover = MOVE.far = Infinity;
  tryMove(0, 0);
  for (let n = 0; n < PLACED.n && MOVE.cover > 0; n++) {
    tryMove(0, PLACED.y1[n] + gap - (y - bubble.ey));
    tryMove(0, PLACED.y0[n] - gap - (y + bubble.ey));
    tryMove(PLACED.x1[n] + gap - (x - bubble.ex), 0);
    tryMove(PLACED.x0[n] - gap - (x + bubble.ex), 0);
  }
}
/* Every bubble shown, placed: its size, where it starts, above its speaker or at the bottom of the agent view, where it
 * is pushed to apart from the nearer ones, eased there, and where its tail's tip is. */
function place() {
  nearestFirst();
  PLACED.n = 0;
  let nearest = Infinity;
  for (let n = 0; n < SHOWN.length; n++) if (!SHOWN[n].fixed && !SHOWN[n].mascot) { nearest = SHOWN[n].far; break; }
  const ease = FRAME.still ? 1 : 1 - Math.exp(-(FRAME.now - FRAME.last) / LOOK.settle), margin = LOOK.margin;
  for (let n = 0; n < SHOWN.length; n++) {
    const bubble = SHOWN[n];
    const ex = bubble.w / 2 * Math.abs(COS) + bubble.h / 2 * Math.abs(SIN) + LOOK.outline;
    const ey = bubble.w / 2 * Math.abs(SIN) + bubble.h / 2 * Math.abs(COS) + LOOK.outline;
    const k = Math.max(0, Math.min(FRAME.scale,
      (bubble.right - bubble.left - 2 * margin) / (2 * ex),
      (bubble.bottom - bubble.top - 2 * margin) / (2 * ey)));
    const pop = FRAME.still ? 1 : Math.min(1, (FRAME.now - bubble.lineAt) / LOOK.pop);
    bubble.grow = 0.55 + 0.45 * easeOut(pop);
    if (pop < 1) wake3d(50);
    // the body's half extents on the screen, turned, with its outline; placed at its full size, so the pop never
    // moves the others
    bubble.k = k;
    bubble.ex = k * ex;
    bubble.ey = k * ey;
    // the agent view's own at the bottom, its tail a short point down out of the view
    if (bubble.fixed) { bubble.nx = bubble.hx; bubble.ny = bubble.bottom - margin - bubble.ey - LOOK.rise * k / 2; }
    else { bubble.nx = bubble.hx + LOOK.aside * bubble.ex; bubble.ny = bubble.hy - bubble.ey - LOOK.rise * k; }
    const x = inside(bubble.nx, bubble.ex, bubble.left + margin, bubble.right - margin);
    const y = inside(bubble.ny, bubble.ey, bubble.top + margin, bubble.bottom - margin);
    apart(bubble, x, y);
    const toX = x + MOVE.dx, toY = y + MOVE.dy;
    keep(toX - bubble.ex, toY - bubble.ey, toX + bubble.ex, toY + bubble.ey);
    // eased toward where it is pushed, measured from where it starts, so it follows its speaker at once and settles
    // apart over a few frames; a bubble just shown is there at once
    if (!bubble.was) { bubble.ox = toX - bubble.nx; bubble.oy = toY - bubble.ny; }
    else { bubble.ox += (toX - bubble.nx - bubble.ox) * ease; bubble.oy += (toY - bubble.ny - bubble.oy) * ease; }
    bubble.x = inside(bubble.nx + bubble.ox, bubble.ex, bubble.left + margin, bubble.right - margin);
    bubble.y = inside(bubble.ny + bubble.oy, bubble.ey, bubble.top + margin, bubble.bottom - margin);
    if (Math.abs(bubble.x - toX) > 0.5 || Math.abs(bubble.y - toY) > 0.5) wake3d(50);
    tipOf(bubble);
    // the farther its agent is than the nearest one talking, the dimmer it is drawn, still solid, fading toward a
    // third; measured from the head, so a bubble moved apart is as bright as its agent is near
    bubble.dim = bubble.fixed || bubble.mascot ? 1
      : Math.max(LOOK.dimmest, Math.min(1, (nearest / Math.max(1e-6, bubble.far)) ** 1.5));
    bubble.z = SHOWN.length - n;  // the nearest drawn over the farther ones
  }
}
/* The tail's tip: at the speaker's head, or where the line from the body to it leaves the map when the head is off
 * it. */
function tipOf(bubble) {
  const x0 = bubble.left + 2, x1 = bubble.right - 2, y0 = bubble.top + 2, y1 = bubble.bottom - 2;
  const dx = bubble.hx - bubble.x, dy = bubble.hy - bubble.y;
  let t = 1;
  if (bubble.hx > x1 && dx > 0) t = Math.min(t, (x1 - bubble.x) / dx);
  if (bubble.hx < x0 && dx < 0) t = Math.min(t, (x0 - bubble.x) / dx);
  if (bubble.hy > y1 && dy > 0) t = Math.min(t, (y1 - bubble.y) / dy);
  if (bubble.hy < y0 && dy < 0) t = Math.min(t, (y0 - bubble.y) / dy);
  t = Math.max(0, t);
  bubble.tipX = bubble.x + dx * t; bubble.tipY = bubble.y + dy * t;
}
/* The tip in the body's own SVG pixels, from its middle, turned back into its frame, to a quarter pixel: the tail is
 * drawn again only when this changes, so a bubble that moves with its speaker only moves. */
function tipInBody(bubble) {
  const scale = bubble.k * bubble.grow, sx = (bubble.tipX - bubble.x) / scale, sy = (bubble.tipY - bubble.y) / scale;
  bubble.lx = Math.round((sx * COS + sy * SIN) * 4) / 4;
  bubble.ly = Math.round((-sx * SIN + sy * COS) * 4) / 4;
}
/* The tail as a path in the body's own SVG pixels: from the tip, back to a base of LOOK.base inside the body where the
 * line from its middle to the tip meets the inner edge of its rounded corners; none when the tip is on the body. */
function tailOf(bubble) {
  const w = bubble.w, h = bubble.h, r = Math.min(LOOK.radius, h / 2.4), dx = bubble.lx, dy = bubble.ly;
  if (Math.abs(dx) <= w / 2 && Math.abs(dy) <= h / 2) return '';
  const long = Math.hypot(dx, dy), ix = w / 2 - r, iy = h / 2 - r;
  const s = Math.min(dx ? ix / Math.abs(dx) : Infinity, dy ? iy / Math.abs(dy) : Infinity);
  const bx = w / 2 + dx * s, by = h / 2 + dy * s, half = Math.min(LOOK.base / 2, 0.35 * long * (1 - s));
  const nx = -dy / long * half, ny = dx / long * half, round = v => Math.round(v * 10) / 10;
  return `M${round(w / 2 + dx)},${round(h / 2 + dy)} L${round(bx + nx)},${round(by + ny)} `
    + `L${round(bx - nx)},${round(by - ny)} Z`;
}
/* The frame's writes, in one pass over the pool, each only when it changed. */
function write() {
  if (BUBBLE.text !== LAYER.heard) { LAYER.live.textContent = BUBBLE.text; LAYER.heard = BUBBLE.text; }
  for (let n = 0; n < POOL.length; n++) {
    const bubble = POOL[n], wrote = bubble.wrote, el = bubble.el;
    if (bubble.id !== null && bubble.seen !== FRAME.n) bubble.on = false;
    bubble.was = bubble.on;
    if (!bubble.on) {
      if (wrote.shown) { el.style.display = 'none'; wrote.shown = false; }
      // free once its figure is gone from the map; a figure keeps its bubble through frames it is not heard in, as
      // while the 3D map has no area in a view switch, so a line that has had its time never comes back
      if (bubble.id !== null && bubble.seen !== FRAME.n && (bubble.id === MASCOT_ID || !ROAM.figures.has(bubble.id))) {
        bubble.id = null;
      }
      continue;
    }
    const laid = bubble.dirty;
    if (laid) writeBody(bubble);
    if (!wrote.shown) { el.style.display = ''; wrote.shown = true; }
    const scale = bubble.k * bubble.grow, x = Math.round(bubble.x * 10) / 10, y = Math.round(bubble.y * 10) / 10;
    if (x !== wrote.x || y !== wrote.y || scale !== wrote.k) {
      el.style.transform = `translate(${x}px,${y}px) scale(${scale})`;
      wrote.x = x; wrote.y = y; wrote.k = scale;
    }
    const opacity = Math.round(Math.min(1, bubble.shown) * 100) / 100;
    if (opacity !== wrote.opacity) { el.style.opacity = opacity; wrote.opacity = opacity; }
    if (bubble.z !== wrote.z) { el.style.zIndex = bubble.z; wrote.z = bubble.z; }
    const paper = Math.round(255 * bubble.dim);
    if (paper !== wrote.paper) {
      bubble.paper.setAttribute('fill', `rgb(${paper},${paper},${paper})`);
      wrote.paper = paper;
    }
    if (bubble.name !== wrote.name) { el.dataset.name = bubble.name; wrote.name = bubble.name; }
    if (bubble.clickable !== wrote.clickable) {
      el.classList.toggle('clickable', bubble.clickable);
      wrote.clickable = bubble.clickable;
    }
    tipInBody(bubble);
    if (laid || bubble.lx !== wrote.lx || bubble.ly !== wrote.ly) {
      bubble.tail.setAttribute('d', tailOf(bubble));
      wrote.lx = bubble.lx; wrote.ly = bubble.ly;
    }
  }
  // the mascot's reply field, figures/ask.js, opens over its head, and closes with its time
  const box = BUBBLE.el;
  if (!box || !box.classList.contains('on')) return;
  if (FRAME.now > BUBBLE.until || !BUBBLE.found) { box.classList.remove('on'); return; }
  box.style.left = `${Math.round(BUBBLE.x)}px`;
  box.style.top = `${Math.round(BUBBLE.y)}px`;
}
/* Each frame: everything read first (the 3D map's area, the pointer, the speakers' heads and their words), then every
 * bubble placed, then the DOM written in one pass. The mascot's speaker was read by `placeBubble` just before. */
export function bubbles3d() {
  if (!G) return;
  FRAME.n++;
  FRAME.last = FRAME.now || performance.now();
  FRAME.now = performance.now();
  FRAME.camera = G.camera();
  FRAME.still = reduced();
  FRAME.scale = BUBBLE_SIZES[SIZE.at];
  const area = G.renderer().domElement.getBoundingClientRect();
  AREA.left = area.left; AREA.top = area.top; AREA.right = area.right; AREA.bottom = area.bottom;
  AREA.width = area.width; AREA.height = area.height;
  FRAME.under = figureUnder();
  SHOWN.length = 0;
  if (SEATS.on) {
    SEATS.frame(FRAME.now);
    for (let n = 0; n < SEATS.list.length; n++) heardSeat(SEATS.list[n]);
  } else if (AREA.width) ROAM.figures.forEach(heard);
  heardMascot();
  place();
  write();
  for (let n = 0; n < SHOWN.length; n++) {
    if (Math.abs(SHOWN[n].shown - SHOWN[n].want) > 0.02) { wake3d(50); break; }
  }
}
