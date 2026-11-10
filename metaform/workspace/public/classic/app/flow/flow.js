/* What travels the map, VIEW-005: each join's cycle, which joins flow, who asks whom, and what agents really did
 * read from the event stream. */
import '/classic/app/map3d/labels.js';  // the part before runs first, so the parts run in the page's order
import {S} from '/classic/app/core/reads.js';
import {HOVER2D} from '/classic/app/map2d/hover.js';
import {flows2d} from '/classic/app/map2d/flow2d.js';
import {wake3d} from '/classic/app/map3d/graph3d.js';
import {hovered} from '/classic/app/map3d/pick3d.js';
import {viewValue} from '/classic/app/views/settings.js';

/* What travels the map, VIEW-005, drawn so the map reads as a working system: who asks whom, which way the data goes,
 * and what gets written down because of it. Only the selected node's joins flow, those it receives on and those it
 * serves, through their purpose vertex, as in the 2D map; with nothing selected no join flows and a large map costs
 * nothing. Three things travel, each with a look of its own so they tell apart at a glance, and each smaller than
 * any node:
 *  - a request: one tiny white dot that glimmers, from the receiver through the join's purpose vertex to each element
 *    the join holds. A join asks when its information flow direction, its ifd, has the receiver take something:
 *    receives, or both.
 *  - the reply: one solid line, as thick as the request is across, in the colour of the element the data comes from,
 *    `fxReply`, leaving the moment the request arrives and running the way the data goes: back to the receiver when it
 *    receives, one line each way when both. Its length says how much data it carries: (random + random) times `data`
 *    times the request's size, a fresh length each cycle, so a request reads as a small ball going out and a reply as
 *    data coming back, short or long.
 *  - a record: a small card in the record colour, --record, on a join whose receiver sends (ifd sends, or none
 *    recorded, which the 2D arrows also draw as sending): what an element pushes on to the store or the log it feeds.
 *    It lands with a ring that opens on the element that takes it.
 * An element that answers a request sends its records the moment it answers, so a request, its answer and the records
 * it leaves behind run as one chain: a data-access element that is asked and writes to the database shows its writes
 * landing there as it answers. An element nobody asks sends on a clock of its own. All of it is read from the joins
 * and their ifd; no element is named.
 * A join's cycle is its request, `ask` seconds, the reply, `reply` seconds, then a wait of (random + random) times the
 * setting web_pulse_ms, a fresh wait every cycle, bunched about it with now and then a quick one or a slow one; a
 * record takes `send` seconds and its ring `burst`. Each join keeps its own clock, so the map never pulses in step.
 * Everything moves by the time that passed, on FLOW.clock, so it flows at one speed at any frame rate, and only while
 * the map draws frames, `FRAMES`, so a page left alone rests; with reduced motion nothing flows.
 * What agents really do is drawn in the same looks, `bright` times larger and brighter so it reads as real, wherever
 * it happens, selected or not, `flowLive`: an agent's session starting sends a request from the map's primary node to
 * its ticket's node; each tool call of a running agent sends a request from its ticket's node to every part of the map
 * the call touched and the reply back, and an edit leaves a record there; a note, an item or a work record written on
 * a node lands there as a record. They come from the page's event stream as they happen; web_live_flow turns them
 * off.
 * The 3D map draws all of it as two objects of its scene, points and line segments filled again each frame, so a
 * larger map adds no objects; a point is sized in map units but held between a few pixels, so nothing swells near the
 * camera. The selected node's edges in the 2D map carry the same, `flows2d`. The graph library's own particle, one to
 * a link, is made only for a browser check: `held`, a share of the way, shows it held there, `dots3d`, so the check
 * can read a dot over a node. */
export const FLOW = {clock: 0, last: 0, held: null, count: 0, ask: 0.45, reply: 0.9, data: 5, send: 0.8, burst: 0.55,
  mean: 3, streak: 0.3, trail: 0.06, bright: 1.35, live: [], net: null, mode: null, fades: new Map(), liveFade: 1, ease: 6};
const cycles = new Map();  // each join's current cycle: when it began on FLOW.clock, its wait, and whether it answered
/* A join's cycle at this moment; `active` is how long a cycle shows. A `driven` join sends its records only when its
 * receiver answers a request, `recorded`, so it has no clock of its own. */
function cycleOf(join, active, driven = false) {
  let cycle = cycles.get(join);
  if (!cycle || cycle.driven !== driven) cycles.set(join, cycle = freshCycle(driven));
  // a request's cycle is its request and its reply, the reply as long as the data it carries
  while (FLOW.clock - cycle.at > active + (cycle.reply || 0) + cycle.wait) {
    cycle.at += active + (cycle.reply || 0) + cycle.wait;
    cycle.wait = (Math.random() + Math.random()) * pulseMean();
    cycle.answered = false;
    Object.assign(cycle, replyData());
  }
  return cycle;
}
/* A join's first cycle: a driven one waits for its receiver's answers; any other starts at a random point of a
 * usual cycle, so joins never pulse in step. */
function freshCycle(driven) {
  if (driven) return {at: -Infinity, wait: Infinity, driven, answered: true};
  return {at: FLOW.clock - Math.random() * 2 * pulseMean(), wait: 0, driven, answered: false, ...replyData()};
}
// how much data a reply carries, a fresh amount each cycle: it runs (random + random) times `reply` seconds, bunched
// about it like the waits, slow enough to read, and its line is `replySize` times the request's size long
function replyData() {
  return {reply: Math.max(0.3, (Math.random() + Math.random()) * FLOW.reply), size: replySize()};
}
// how many times the request's size a reply's line runs: (random + random) times `data`, bunched about it, now and
// then a short one or a long one; its round ends add the request's size, so no reply is smaller than its request
export const replySize = () => (Math.random() + Math.random()) * FLOW.data;
const asksOf = join => join?.ifd === 'receives' || join?.ifd === 'both';
// the usual wait between a join's cycles, web_pulse_ms, `mean` until the page has read it
const pulseMean = () => FLOW.mean;
/* Whether a join's flow is drawn: only the selected node's joins, those it receives on and those it serves, through
 * their purpose vertex, as the 2D map draws them; with nothing selected no join flows, so a large map costs nothing. */
export function flowShown(join) {
  const mode = flowModeNow(), chosen = mode === 'hover' ? hoveredNow() : S.selected;
  if (mode === 'all') return Boolean(join);
  if (mode !== 'selected' && mode !== 'hover') return false;
  if (!chosen || !join) return false;
  return join.receiver === chosen || join.providers.includes(chosen) || chosen === 'p:' + join.id;
}
/* Which joins flow, web_flow_mode: off, none and no agents' activity either; hover, the joins of the node the pointer
 * is on, in either map; selected, the selected node's joins, the default; all, every join; live, only what agents
 * really do. `window.metaform.flowMode` changes it for the page, and
 * the mode bar and the View menu offer it; a change eases the dots in or out, `FLOW.fades`, never cutting them. */
export const FLOW_MODE_LIST = [{name: 'off', label: 'Off', help: 'No dots flow.'},
  {name: 'hover', label: 'Hover', help: 'Dots flow along the joins of the node the pointer is on.'},
  {name: 'selected', label: 'Selection', help: "Dots flow along the selected node's joins."},
  {name: 'all', label: 'All', help: 'Dots flow along every join.'}];
// the node the pointer is on, in the 3D map or the 2D one, for the hover flow
const hoveredNow = () => hovered?.id ?? HOVER2D.on ?? null;
export function flowModeNow() {
  if (FLOW.mode) return FLOW.mode;
  const kept = viewValue('web_flow_mode');
  return FLOW_MODE_LIST.some(one => one.name === kept) ? kept : 'selected';
}
export function flowMode(name) {
  if (FLOW_MODE_LIST.some(one => one.name === name) && name !== FLOW.mode) {
    FLOW.mode = name;
    flows2d();  // the 2D map's flowing edges are the new mode's, not the old one's until the next selection
    wake3d(1500);
  }
  return flowModeNow();
}
/* Who asks whom, read again only when the joins change: each join by its id, the elements some join asks, which
 * answer, and the joins each element sends records on. */
export function flowNet() {
  if (FLOW.net?.joins === S.joins && FLOW.net.size === S.joins.length) return FLOW.net;
  const byId = new Map(), answering = new Set(), sends = new Map();
  for (const join of S.joins) {
    byId.set(join.id, join);
    if (asksOf(join)) for (const id of join.providers) answering.add(id);
    else sends.set(join.receiver, [...(sends.get(join.receiver) || []), join.id]);
  }
  return FLOW.net = {joins: S.joins, size: S.joins.length, byId, answering, sends};
}
/* One join's flow at this moment: whether it asks, and how long since its cycle began; for a request, how long its
 * reply's line is, in the request's sizes, and how long it runs, else 0. The moment its request reaches the elements
 * it holds they answer, and each sends its records then. Both maps call it for every flowing join every frame, so every call fills the one
 * object, `AT`, which the caller reads before its next call. */
const AT = {asks: false, since: 0, size: 0, reply: 0};
export function flowAt(join) {
  const net = flowNet();
  if (asksOf(join)) {
    const cycle = cycleOf(join.id, FLOW.ask), since = FLOW.clock - cycle.at;
    if (since >= FLOW.ask && !cycle.answered) answered(join, cycle, since, net);
    AT.asks = true; AT.since = since; AT.size = cycle.size; AT.reply = cycle.reply;
    return AT;
  }
  const cycle = cycleOf(join.id, FLOW.send + FLOW.burst, net.answering.has(join.receiver));
  AT.asks = false; AT.since = FLOW.clock - cycle.at; AT.size = 0; AT.reply = 0;
  return AT;
}
/* The request has reached the elements the join holds: they answer, and each sends its records now, unless the reply
 * is already over. */
function answered(join, cycle, since, net) {
  cycle.answered = true;
  if (since >= FLOW.ask + cycle.reply) return;
  for (const id of join.providers) for (const sent of net.sends.get(id) || []) recorded(sent);
}
function recorded(join) {  // a record leaves on the join now, unless one is still on its way
  const cycle = cycleOf(join, FLOW.send + FLOW.burst, true);
  if (FLOW.clock - cycle.at >= FLOW.send) cycle.at = FLOW.clock;
}
export function flowTick(now) {  // the clock moves on by the time that passed, once a frame whichever map draws it
  if (now <= FLOW.last) return;
  FLOW.clock += Math.min(0.1, (now - (FLOW.last || now)) / 1000);
  FLOW.last = now;
}
