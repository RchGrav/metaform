/* The mascot calls the person's attention to what needs them, and what the system agent and every figure do on the
 * page through the flow's events. */
import '/page/app/figures/cut.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
import {$, reduced, h} from '/page/app/core/dom.js';
import {opened} from '/page/app/core/overlays.js';
import {S} from '/page/app/core/reads.js';
import {ROAM, nodeById, ticketNode, isSystemTalk, embody} from '/page/app/figures/agents.js';
import {RESTLESS} from '/page/app/figures/walk.js';
import {MASCOT, mascotGlyph, mascotDriven, driveMascot, releaseMascot, dropHeld} from '/page/app/figures/mascot.js';
import {BUBBLE, say} from '/page/app/figures/cut.js';
import {sight, viewing, approachPoint, capture} from '/page/app/figures/eyes.js';
import {mayAnnounce, speakReply} from '/page/voice.js';
import {ASKING, flushAsk} from '/page/app/figures/ask.js';
import {G, wake3d} from '/page/app/map3d/graph3d.js';
import {flowMode} from '/page/app/flow/flow.js';
import {swap} from '/page/app/camera/flight.js';
import {fly3d} from '/page/app/camera/fly3d.js';
import {showFlow, PHYSICS, applyPhysics, setMode3d} from '/page/app/views/bar.js';
import {openSettings} from '/page/app/settings/screen.js';
import {wake2d} from '/page/app/map2d/flow2d.js';
import {select, MERGE, takeReview} from '/page/app/selection/select.js';
import {partAt} from '/page/app/board/refs.js';
import {wrote} from '/page/app/board/history.js';
import {D, ticketOf, ticketPart, agentAt} from '/page/app/agents/dispatch.js';
import {showTab} from '/page/app/panel/prompts.js';
import {agentName} from '/page/app/agents/pickers.js';
import {WS} from '/page/app/workspace/workspace.js';

/* The mascot calls the person's attention, VIEW-005: when something needs them, an agent waiting for an answer, a
 * ticket done, a spinning or stuck agent, an intake finished or a merge to review, it goes there, says so in its
 * bubble, and brings a small note card into view, set down near the pointer, that takes the person to it on a click
 * and goes on its ×. Driven by what the page already reads as it happens, never by a model. It speaks rarely and
 * briefly: one call at a time, ATTN.gap apart, each thing once, at most ATTN.most waiting, the oldest dropped. */
export const ATTN = {seen: new Set(), queue: [], last: 0, timer: 0, card: null, gap: 6000, most: 3, held: 25000};
export function attend(key, text, node, open) {
  if (!mascotGlyph() || ATTN.seen.has(key)) return;
  ATTN.seen.add(key);
  ATTN.queue = [...ATTN.queue.filter(one => one.text !== text), {text, node, open}].slice(-ATTN.most);
  pumpAttention();
}
function pumpAttention() {
  clearTimeout(ATTN.timer);
  const wait = ATTN.last + ATTN.gap - Date.now();
  if (!ATTN.queue.length) return;
  if (wait > 0 || ATTN.card) { ATTN.timer = setTimeout(pumpAttention, Math.max(500, wait)); return; }
  const call = ATTN.queue.shift();
  ATTN.last = Date.now();
  // while its agent drives it the card still comes, but the mascot goes nowhere on its own
  if (!mascotDriven()) MASCOT.call = call.node ? {node: call.node, until: performance.now() + 9000} : null;
  wake3d(9000);
  say(call.text, 6, call.open);
  bringCard(call);
}
/* Where a card is set down: near the pointer if it moved in the last half minute, else at the lower right. */
function cardSpot() {
  if (performance.now() - MASCOT.pointer.at >= 30000) return {x: innerWidth - 200, y: innerHeight - 140};
  return {x: Math.min(innerWidth - 160, Math.max(160, MASCOT.pointer.x + 24)),
    y: Math.min(innerHeight - 60, Math.max(80, MASCOT.pointer.y + 28))};
}
function bringCard(call) {  // a note card, carried from the mascot to near the pointer, eased in and out
  const card = ATTN.card = h('div', {class: 'mascot-card', role: 'alert'},
    h('button', {class: 'go', type: 'button', onclick: () => { done(); call.open?.(); }}, call.text),
    h('button', {class: 'x', type: 'button', title: 'Dismiss', 'aria-label': 'Dismiss', onclick: () => done()}, '×'));
  const from = BUBBLE.at || {x: innerWidth - 120, y: innerHeight - 80}, to = cardSpot();
  Object.assign(card.style, {left: `${from.x}px`, top: `${from.y}px`});
  document.body.append(card);
  requestAnimationFrame(() => requestAnimationFrame(() => {
    card.classList.add('on');
    Object.assign(card.style, {left: `${to.x}px`, top: `${to.y}px`});
  }));
  const timer = setTimeout(() => done(), ATTN.held);
  function done() {
    clearTimeout(timer);
    card.classList.remove('on');
    setTimeout(() => card.remove(), 400);
    if (ATTN.card === card) ATTN.card = null;
    if (MASCOT.call?.node === call.node) MASCOT.call = null;
    pumpAttention();
  }
}
/* What needs the person now, read from what the page has just read: an agent waiting for them, one spinning or stuck,
 * and a merge waiting for review. A ticket done is told by `flowTickets`, an intake finished where the page learns
 * it. */
export function noticeAttention() {
  if (ASKING.pending) flushAsk();  // words to the system agent waiting for its session to start
  for (const one of D.asking || []) {
    const session = D.sessions.find(row => row.session_id === one.session_id);
    if (session) attendSession(`ask:${one.session_id}:${one.signal}:${one.key || ''}`, 'is waiting on you', session);
  }
  for (const one of D.signals || []) {
    if (one.active === false || !RESTLESS.includes(one.signal)) continue;
    const session = D.sessions.find(row => row.session_id === one.session_id && row.state === 'running');
    if (session) attendSession(`stuck:${one.session_id}:${one.signal}`, 'seems stuck', session);
  }
  for (const row of MERGE.rows || []) {
    const ticket = ticketOf(row.work_id);
    attend(`merge:${row.work_id}`, 'A merge is waiting for your review', ticket ? ticketNode(ticket) : null,
      () => takeReview(row.work_id, null));
  }
}
/* An agent's session that needs the person: said with the agent's name, at its ticket's node, opening its chat. */
function attendSession(key, words, session) {
  const ticket = ticketOf(session.work_id);
  attend(key, `${agentName(session.agent)} ${words}`, ticket ? ticketNode(ticket) : null,
    () => agentAt(session.work_id, session.session_id));
}
/* What the person's system agent, as the mascot, and every agent, as its figure, do on the page, VIEW-005: the web
 * module's verbs reach the page as `mascot` events with an id, and what they ask, what a figure sees, a picture from
 * its eyes, what the person is looking at, is answered to /api/mascot-result under that id. Every act shows on the
 * page as the mascot doing it: it walks to what it selects, gestures at what it opens, and says so in a word. */
export function mascotEvent(payload) {
  if (!payload || payload.project !== S.project) return;
  const act = payload.act, node = nodeOfAddress(payload.address);
  const answer = result => payload.id && wrote('/api/mascot-result', {id: payload.id, result});
  if (act === 'see' || act === 'look') {  // the system agent looking through the mascot's eyes leads it too
    if (mascotGlyph() && (!payload.work || isSystemTalk(ticketOf(payload.work)))) driveMascot();
    return sight(payload, node, answer);
  }
  if (act === 'viewing') return answer(viewing());
  if (act === 'come') return answer(come(payload));
  if (act === 'capture') return capture(payload, answer);
  if (act === 'embody') return answer(payload.work ? embody(payload.work, payload.character, 'agent')
    : {error: 'Only an agent in a conversation can take a body: run it from that agent.'});
  // an embodied agent's own figure
  const own = payload.work && ROAM.figures.get(payload.work)?.talk ? payload.work : null;
  // the body's acts need a body; the page's own acts, the camera, a tab, a pane, the maps, are done with or without one
  const bodily = BODILY.includes(act);
  const body = Boolean(mascotGlyph());
  if (bodily && !body && !own) {
    const why = 'The mascot has no body on the map yet: it is drawn once your system agent has one.';
    if (payload.id) answer({error: why});
    return;
  }
  // its system agent leads it now: autonomy pauses until the agent lets go, `mascotDriven`
  if (body && !own) driveMascot(act === 'take' ? {reason: String(payload.reason || '')} : null);
  const tell = (words, seconds = 2.4) => say(words, seconds);
  const said = Object.hasOwn(MASCOT_ACTS, act) ? MASCOT_ACTS[act](payload, node, {own, body, tell}) : null;
  answer({done: true, ...(said && typeof said === 'object' ? said : {})});
  wake3d(4000);
  wake2d();
}
const BODILY = ['say', 'go', 'turn', 'point', 'emote', 'move', 'push', 'drag', 'drop', 'take', 'release'];
/* web_come: the caller's own figure, or else the person's mascot, comes to the person to get their attention, as the
 * agent chooses: to the front of their view, under their mouse pointer, or beside what the pointer takes; following it
 * or staying where it was; for as long as the agent says, facing the person, then back to what it was doing. Asked
 * again it changes the approach; `seconds` 0 ends it now. A place that is not there now, the pointer off the map or
 * taking nothing, is refused rather than guessed. */
const COME = 10, COME_MOST = 3600;  // seconds it stays when the agent does not say, and the most it may
const COMES = ['view', 'pointer', 'hit'];
function come(payload) {
  if (!G) return {error: 'The 3D map is not open on this page.'};
  const to = payload.to || 'view', seconds = payload.seconds == null ? COME : Number(payload.seconds);
  if (!COMES.includes(to)) return {error: `${to} is not where a body comes: ${COMES.join(', ')}.`};
  if (!(seconds >= 0 && seconds <= COME_MOST)) return {error: `seconds is from 0 to ${COME_MOST}.`};
  const figure = payload.work ? ROAM.figures.get(payload.work) : null;
  if (!figure && !MASCOT.mesh) {
    return {error: 'You have no figure on the map and the mascot is not drawn: take a body with web_embody.'};
  }
  const who = figure ? 'your figure' : "the person's mascot";
  if (!seconds) {  // the approach ends now
    if (figure) figure.come = null;
    else if (MASCOT.job?.come) { MASCOT.job = null; releaseMascot(); }
    return {done: true, who, ended: true};
  }
  const approach = {to, follow: payload.follow !== false, point: null};
  const point = approachPoint(approach, ROAM.drawn || 1, new THREE.Vector3());
  if (!point) {
    return {error: to === 'pointer' ? "The person's pointer is not on the 3D map now."
      : 'The pointer takes nothing on the 3D map now: no element, join or figure is under it.'};
  }
  if (figure) figure.come = {...approach, until: figure.clock + seconds};
  else {
    driveMascot({reason: ''});  // held past the agent's turn for as long as it chose, then let go
    MASCOT.driven = performance.now() + seconds * 1000;
    MASCOT.call = null;
    MASCOT.job = {kind: 'move', node: null, point, agent: true, come: approach};
    MASCOT.facing = {dir: new THREE.Vector3().subVectors(G.camera().position, point)};
  }
  wake3d(seconds * 1000);
  return {done: true, who, to, follow: approach.follow, seconds, point: point.toArray().map(one => Math.round(one))};
}
/* Each act of the web module's verbs, done on the page: (payload, node, {own, body, tell}). */
const MASCOT_ACTS = {
  release: () => { releaseMascot(); dropHeld(); MASCOT.job = null; },
  take: payload => {
    if (payload.reason) say(String(payload.reason).slice(0, 140), 4, null, null, MASCOT.glyph || '');
  },
  // an embodied agent speaks in its own bubble; the mascot's agent is named in it; aloud too when it asks and the
  // person's voice settings speak, VIEW-005
  say: (payload, node, {own}) => {
    const text = String(payload.text || '');
    say(text.slice(0, 280), Math.min(12, 3 + text.length / 18), null, own, own ? '' : MASCOT.glyph || '');
    if (!payload.speak) return null;
    const aloud = mayAnnounce();
    if (aloud) speakReply(text.slice(0, 280));
    return {spoken: aloud, ...(aloud ? {} : {why: 'The person\'s voice settings do not speak here: voice is off, or '
      + 'set never to speak.'})};
  },
  go: (payload, node) => {
    if (!node) return;
    MASCOT.call = {node, until: MASCOT.driven, distance: payload.distance, height: payload.height, agent: true};
    MASCOT.facing = null;
    MASCOT.job = null;
  },
  move: (payload, node) => {  // to a point, an address, or by a step relative to its heading
    const point = Array.isArray(payload.point) ? new THREE.Vector3(...payload.point.map(Number)) : null;
    const step = ['forward', 'right', 'up'].some(key => payload[key] != null) ? stepFrom(payload) : null;
    MASCOT.call = null;
    MASCOT.job = {kind: 'move', node: point || step ? null : node, point: point || step, agent: true};
  },
  push: (payload, node) => {
    if (!node) return;
    MASCOT.call = null;
    MASCOT.job = {kind: 'push', node, dir: pushDirection(payload, node), strength: Number(payload.strength ?? 0.5),
      agent: true};
  },
  drag: (payload, node) => {
    if (!node) return;
    MASCOT.call = null;
    if (MASCOT.holding && MASCOT.holding.id !== node) dropHeld();  // one node held at a time
    MASCOT.job = {kind: 'drag', node, point: Array.isArray(payload.point) ? payload.point.map(Number) : null,
      beside: payload.beside ? nodeOfAddress(payload.beside) : null, agent: true};
  },
  drop: () => { dropHeld(); MASCOT.job = null; },
  turn: (payload, node) => turnMascot(node, payload.degrees),
  point: (payload, node) => { if (node) MASCOT.point = {node, at: MASCOT.clock, long: 2.4}; },
  emote: payload => {
    MASCOT.emote = {kind: payload.emote, at: MASCOT.clock, long: payload.emote === 'sleep' ? 6 : 1.8};
  },
  select: (payload, node, {body}) => {  // it walks over, and the selection follows it
    if (!node) return;
    if (body) MASCOT.call = {node, until: MASCOT.driven, agent: true};
    setTimeout(() => select(node, true), reduced() || !body ? 0 : 900);
  },
  camera: (payload, node, {tell}) => {
    if (payload.mode) setMode3d(payload.mode);
    if (node) { MASCOT.point = {node, at: MASCOT.clock, long: 2}; fly3d(node, true); }
    tell(payload.mode ? `${payload.mode[0].toUpperCase()}${payload.mode.slice(1)} view.` : 'Over here.');
  },
  tab: (payload, node, {tell}) => {
    showTab(payload.tab === 'provenance' ? 'prov' : payload.tab);
    MASCOT.emote = {kind: 'wave', at: MASCOT.clock, long: 1.2};
    tell(`The ${payload.tab} tab.`);
  },
  open: (payload, node, {tell}) => opened(payload, tell),
  swap: (payload, node, {tell}) => {
    swap(payload.large === '2d');
    tell(`The ${payload.large.toUpperCase()} map, large.`);
  },
  flow: (payload, node, {tell}) => {
    flowMode(payload.mode);
    if (typeof showFlow === 'function') showFlow(payload.mode);
    tell(`Flow: ${payload.mode}.`);
  },
  physics: (payload, node, {tell}) => {
    if (!PHYSICS.some(([name]) => name === payload.preset)) return tell(`I don't know the ${payload.preset} physics.`);
    applyPhysics(payload.preset);
    tell(`Physics: ${payload.preset}.`);
  },
};
/* A step from where the mascot stands, measured along its heading: forward, to its right, and up. */
function stepFrom(payload) {
  const ahead = MASCOT.heading.clone().setY(0).normalize();
  const side = new THREE.Vector3().crossVectors(ahead, THREE.Object3D.DEFAULT_UP).normalize();
  return MASCOT.pos.clone().addScaledVector(ahead, Number(payload.forward || 0))
    .addScaledVector(side, Number(payload.right || 0)).add(new THREE.Vector3(0, Number(payload.up || 0), 0));
}
/* Which way a push goes: up, down, or toward another node, else wherever the mascot comes from. */
function pushDirection(payload, node) {
  const fixed = {up: [0, 1, 0], down: [0, -1, 0]}[payload.direction];
  if (fixed) return fixed;
  const toward = payload.toward ? nodeOfAddress(payload.toward) : null;
  const at = nodeById(G?.graphData() || {nodes: []}, node);
  if (!toward || !at) return null;
  const other = nodeById(G.graphData(), toward);
  return other ? [other.x - at.x, other.y - at.y, other.z - at.z] : null;
}
function openFor(payload, tell) {  // what the agent opens on the page for the person
  if (payload.what === 'board') { if ($('#board').hidden) $('#boardBtn').click(); tell('The board.'); }
  else if (payload.what === 'settings') { openSettings(); tell('Settings.'); }
  else if (payload.what === 'pane' && payload.id && WS.on) { WS.reveal(payload.id); tell('There.'); }
  else if (payload.what === 'ticket' && payload.id) {  // its node, its work in the panel
    const ticket = ticketOf(payload.id);
    if (!ticket) return tell('I cannot find that ticket.');
    const node = ticketNode(ticket);
    MASCOT.call = {node, until: MASCOT.driven, agent: true};
    setTimeout(() => { select(node, true); showTab('object'); }, reduced() ? 0 : 900);
    tell(`Ticket on ${ticketPart(ticket)}.`);
  }
}
// an element by its address, or a join written receiver>provider, as the node the maps draw for it
function nodeOfAddress(address) {
  if (!address) return null;
  const [receiver, provider] = String(address).split('>').map(part => part.trim());
  if (provider) {
    const one = partAt(receiver)?.id, two = partAt(provider)?.id;
    const join = S.joins.find(item => item.receiver === one && item.providers.includes(two));
    return join ? 'p:' + join.id : null;
  }
  return partAt(receiver)?.id ?? null;
}
export function turnMascot(node, degrees) {
  if (node) MASCOT.facing = {node};
  else if (Number.isFinite(Number(degrees))) {
    const by = -Number(degrees) * Math.PI / 180;  // right is clockwise seen from above
    MASCOT.facing = {dir: MASCOT.heading.clone().setY(0).normalize().applyAxisAngle(THREE.Object3D.DEFAULT_UP, by)};
  }
  MASCOT.driven = performance.now() + 120000;
}
