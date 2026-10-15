/* The mascot calls the person's attention to what needs them, and what the system agent and every figure do on the
 * page through the flow's events. */
import '/page/app/figures/cut.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
import {$, reduced, h} from '/page/app/core/dom.js';
import {S} from '/page/app/core/reads.js';
import {ROAM, nodeById, ticketNode, isSystemTalk, embody, ballOf, sizeOf} from '/page/app/figures/agents.js';
import {RESTLESS, drivePace, facingOf, driveGoal, driveFace} from '/page/app/figures/walk.js';
import {MASCOT, mascotGlyph, mascotDriven, driveMascot, releaseMascot, dropHeld} from '/page/app/figures/mascot.js';
import {BUBBLE, say} from '/page/app/figures/cut.js';
import {sight, viewing, approachPoint, capture} from '/page/app/figures/eyes.js';
import {mayAnnounce, speakReply} from '/page/voice.js';
import {ASKING, flushAsk} from '/page/app/figures/ask.js';
import {G, afterFrames, noMoreFrames, wake3d} from '/page/app/map3d/graph3d.js';
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
  if (ATTN.card) return;  // the shown card's done() calls this again when it closes
  if (wait > 0) { ATTN.timer = setTimeout(pumpAttention, wait); return; }  // the gap's deadline, once
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
  // the body the act moves: the caller's own figure, or else the person's mascot
  const figure = own ? ROAM.figures.get(own) : null, mover = figure ? figureBody(figure) : body ? mascotBody() : null;
  if (bodily && mover && act !== 'say') mover.bump();
  const said = mover && Object.hasOwn(MOVES, act) ? MOVES[act](payload, node, mover)
    : figure && Object.hasOwn(OWN_ACTS, act) ? OWN_ACTS[act](payload, node, figure, mover)
    : Object.hasOwn(MASCOT_ACTS, act) ? MASCOT_ACTS[act](payload, node, {own, body, tell}) : null;
  // an act that moves the body answers once it is done, `settle`, with where it is
  Promise.resolve(said).then(result => {
    if (result?.error) return answer({error: result.error});
    const told = result && typeof result === 'object' ? result : {};
    answer({done: true, ...(bodily && mover && !told.at ? stateOf(mover) : {}), ...told});
  });
  wake3d(4000);
  wake2d();
}
/* The body an act moves, VIEW-005: the calling agent's own figure, or the person's mascot, read live, so an answer
 * says where it is when it is given. `bump` counts its acts, so a later act stops the wait of an earlier one. */
const figureBody = figure => ({who: 'your figure', character: figure.glyph, mesh: () => figure.mesh, vel: figure.vel,
  drive: () => figure.drive, acts: () => figure.acts || 0, bump: () => { figure.acts = (figure.acts || 0) + 1; },
  ended: () => figure.done || ROAM.figures.get(figure.id) !== figure ? 'its conversation ended' : null,
  send: drive => sendFigure(figure, drive)});
const mascotBody = () => ({who: "the person's mascot", character: MASCOT.glyph, mesh: () => MASCOT.mesh,
  vel: MASCOT.vel, drive: () => MASCOT.job?.drive || null, acts: () => MASCOT.acts || 0,
  bump: () => { MASCOT.acts = (MASCOT.acts || 0) + 1; },
  ended: () => !MASCOT.mesh ? 'the mascot left the map' : !mascotDriven() ? 'its agent let it go' : null,
  send: drive => sendMascot(drive)});
/* Where an act sends a body, its `drive`: a goal, beside a node or a point, and a way to face, each kept from its last
 * act when the new one leaves it out, else where it stands and the way it faces now. It goes fast enough that a long
 * way ends in about three seconds, `drivePace`. False when the body cannot be sent, a figure on its way home. */
function sendBody(body, goal, face) {
  const mesh = body.mesh(), was = body.drive();
  if (!mesh) return false;
  const drive = {node: null, offset: null, point: null,
    ...(goal || (was ? {node: was.node, offset: was.offset, point: was.point} : {point: mesh.position.clone()})),
    face: face || was?.face || {dir: facingOf(mesh, new THREE.Vector3())}};
  const goes = driveGoal(drive, G.graphData(), new THREE.Vector3());
  drive.away = goes ? mesh.position.distanceTo(goes) : 0;
  return body.send(drive) ? drive : false;
}
// a figure leaving the map is not led any more; one still coming goes where it is sent once it is here, `arriving`
const LEAVING = ['flourish', 'returning', 'leaving'];
function sendFigure(figure, drive) {
  if (figure.done || LEAVING.includes(figure.stage)) return false;
  const m = figure.motion, top = ROAM.speed * (m?.speed ?? 1), fast = drivePace(top, drive.away);
  Object.assign(drive, {top: top * fast, accel: ROAM.accel * (m?.accel ?? 1) * fast});
  if (!figure.drive && figure.stage !== 'arriving') {
    if (figure.stage === 'going') figure.vel.copy(figure.heading).setLength(figure.speed || 0);
    figure.pos.copy(figure.mesh.position);
    Object.assign(figure, {stage: 'driven', clock: 0});
  }
  figure.drive = drive;
  return true;
}
function sendMascot(drive) {
  drive.fast = drivePace(ROAM.speed * (MASCOT.motion?.speed ?? 1) * 0.9, drive.away);
  MASCOT.call = null;
  MASCOT.facing = null;
  MASCOT.job = {kind: 'move', node: null, point: null, agent: true, drive};
  return true;
}
/* A goal beside a node: on the side the body comes from, level with it unless `height` says, `distance` from its
 * surface, its own size by default; the offset is fixed now, so the goal moves with the node and nothing else. */
function besideGoal(node, at, size, distance, height) {
  const there = nodeById(G.graphData(), node);
  if (!there || there.x === undefined) return null;
  const center = new THREE.Vector3(there.x, there.y, there.z);
  const side = new THREE.Vector3().subVectors(at, center).setY(0);
  if (side.lengthSq() < 1e-6) side.subVectors(G.camera().position, center).setY(0);
  if (side.lengthSq() < 1e-6) side.set(1, 0, 0);
  const away = ballOf(there) + Math.max(0, distance ?? size * 1.2);
  return {node, offset: side.setLength(away).setY(Number(height || 0))};
}
/* An act that moves a body: it answers once the body is at rest where it was sent and faces the way asked, or once it
 * stops for something else, `settle`. */
const MOVES = {
  go: (payload, node, body) => {
    if (!node) return {error: `Nothing at ${payload.address || 'that address'} is drawn on the map.`};
    const goal = besideGoal(node, body.mesh().position, drawnSize(), payload.distance ?? null, payload.height);
    if (!goal || !sendBody(body, goal, {node})) return {error: cannot(body)};
    return settle(body, {address: payload.address});
  },
  move: (payload, node, body) => {  // to a point, an address, or by a step from where it stands and faces
    const mesh = body.mesh(), at = mesh.position;
    const steps = ['forward', 'right', 'up'].some(key => payload[key] != null);
    let goal = null, face = null;
    if (Array.isArray(payload.point)) {
      const point = new THREE.Vector3(...payload.point.map(Number)), way = point.clone().sub(at).setY(0);
      goal = {point};
      if (way.lengthSq() > 1e-6) face = {dir: way.normalize()};
    } else if (steps) {
      const ahead = facingOf(mesh, new THREE.Vector3());
      goal = {point: stepFrom(at, ahead, payload)};
      face = {dir: ahead};
    } else if (node) {
      goal = besideGoal(node, at, drawnSize());
      face = {node};
    } else return {error: `Nothing at ${payload.address || 'that address'} is drawn on the map.`};
    if (!goal || !sendBody(body, goal, face)) return {error: cannot(body)};
    return settle(body, {address: node && !steps && !payload.point ? payload.address : null});
  },
  turn: (payload, node, body) => {  // to face a node, or by degrees from the way it faces, right positive
    const mesh = body.mesh();
    let face = node ? {node} : null;
    if (!face && Number.isFinite(Number(payload.degrees))) {
      const by = -Number(payload.degrees) * Math.PI / 180;  // right is clockwise seen from above
      face = {dir: facingOf(mesh, new THREE.Vector3()).applyAxisAngle(THREE.Object3D.DEFAULT_UP, by)};
    }
    if (!face) return {error: `Nothing at ${payload.address || 'that address'} is drawn on the map.`};
    if (!sendBody(body, null, face)) return {error: cannot(body)};
    return settle(body, {address: node ? payload.address : null});
  },
  point: (payload, node, body) => {  // it turns to a node and gestures at it
    if (!node) return {error: `Nothing at ${payload.address || 'that address'} is drawn on the map.`};
    if (!sendBody(body, null, {node})) return {error: cannot(body)};
    if (body.who === "the person's mascot") MASCOT.point = {node, at: MASCOT.clock, long: 2.4};
    return settle(body, {address: payload.address});
  },
};
const cannot = body => `${body.who[0].toUpperCase()}${body.who.slice(1)} cannot be sent now: ${body.ended()
  || 'it is on its way off the map'}.`;
const drawnSize = () => ROAM.drawn || (G ? sizeOf(G.graphData()) : 1);
/* The acts of an agent's own figure that do not move it far: a feeling shown, held still where it stands with a
 * reason, let go back to its conversation's way. Pushing and carrying elements are the mascot's alone. */
const OWN_ACTS = {
  emote: (payload, node, figure, body) => {
    if (!sendBody(body, null, null)) return {error: cannot(body)};
    figure.emote = {kind: payload.emote, at: figure.clock, long: payload.emote === 'sleep' ? 6 : 1.8};
    return null;
  },
  take: (payload, node, figure, body) => {
    if (!sendBody(body, {point: figure.mesh.position.clone()}, null)) return {error: cannot(body)};
    if (payload.reason) say(String(payload.reason).slice(0, 140), 4, null, figure.id, '');
    return null;
  },
  release: (payload, node, figure) => { figure.drive = null; return null; },
  push: () => ({error: PUSHING}), drag: () => ({error: PUSHING}), drop: () => ({error: PUSHING}),
};
const PUSHING = "Your own figure goes, turns, points and shows feelings; pushing and carrying elements are the "
  + "person's mascot's.";
/* Where a body is now and which way it faces, whether it is at rest, for every act's answer. */
const tenth = value => Math.round(value * 10) / 10;
function stateOf(body) {
  const mesh = body.mesh();
  if (!mesh) return {who: body.who};
  return {who: body.who, character: body.character, at: mesh.position.toArray().map(tenth),
    heading: facingOf(mesh, new THREE.Vector3()).toArray().map(one => Math.round(one * 100) / 100),
    at_rest: body.vel.length() < restSpeed()};
}
const restSpeed = () => Math.max(0.05, drawnSize() * 0.2);
/* How far a body is turned from the way its drive asks it to face, in degrees, flat; 0 when it is asked to face the
 * way it goes. */
const FACE = new THREE.Vector3(), FACING = new THREE.Vector3(), THERE = new THREE.Vector3();  // scratch, reused
function turnLeft(drive, mesh, data) {
  if (!drive || !mesh) return 0;
  const face = driveFace(drive, mesh.position, data, FACE);
  if (!face) return 0;
  face.sub(mesh.position).setY(0);
  if (face.lengthSq() < 1e-8) return 0;
  return facingOf(mesh, FACING).angleTo(face.normalize()) * 180 / Math.PI;
}
/* The wait for an act on a body, VIEW-005: it is done once the body is at rest where it was sent, within a tenth of
 * its size, and turned within TURNED degrees of the way asked; or stopped, by a later act, its target leaving the map,
 * its conversation ending or the mascot let go, or after `most` milliseconds still on its way, its deadline. It is
 * looked at once each frame that moves the body, `afterFrames`, never between. Its answer says where
 * the body is and faces, whether it is at rest, what stopped it, how far it was asked to go and went, how far it is
 * from where it was sent, and how far it is from the surface of the element it went to. */
export const ACT_MOST = 6000, TURNED = 3;
export function settle(body, {address = null, most = ACT_MOST} = {}) {
  const mine = body.acts(), began = performance.now(), mesh = body.mesh(), data = G.graphData();
  const from = mesh.position.clone(), facing = facingOf(mesh, new THREE.Vector3()), drive = body.drive();
  const goal = drive && driveGoal(drive, data, new THREE.Vector3());
  const asked = goal ? from.distanceTo(goal) : 0, turn = turnLeft(drive, mesh, data);
  wake3d(most + 1000);
  return new Promise(done => {
    const check = late => {
      const now = body.drive(), at = body.mesh(), size = drawnSize(), data = G.graphData();
      const there = now && driveGoal(now, data, THERE);
      const off = there && at ? at.position.distanceTo(there) : 0;
      const arrived = at && body.vel.length() < restSpeed() && off <= Math.max(0.1, size * 0.1)
        && turnLeft(now, at, data) <= TURNED;
      const why = body.acts() !== mine ? 'a later act' : body.ended() || (!now || !at ? 'its agent let it go'
        : now.node && !there ? 'its target left the map' : arrived ? (asked > size * 0.1 ? 'arrived' : 'turned')
        : late || performance.now() - began > most ? 'time' : null);
      if (!why) return;
      noMoreFrames(framed);
      clearTimeout(limit);
      const answer = {...stateOf(body), stopped_by: why};
      if (asked > size * 0.1) Object.assign(answer, {asked: tenth(asked), moved: tenth(from.distanceTo(at.position))});
      if (turn >= 1 && at) {
        Object.assign(answer, {asked_degrees: Math.round(turn),
          turned_degrees: Math.round(facing.angleTo(facingOf(at, FACING)) * 180 / Math.PI)});
      }
      if (there) answer.off = tenth(off);
      const target = address && now ? (now.node || now.face?.node) : null, seen = target && nodeById(data, target);
      if (seen && seen.x !== undefined && at) {
        answer.target = {address, distance: tenth(Math.max(0,
          at.position.distanceTo(new THREE.Vector3(seen.x, seen.y, seen.z)) - ballOf(seen)))};
      }
      done(answer);
    };
    const framed = () => check(false), limit = setTimeout(() => check(true), most);
    afterFrames(framed);
  });
}
/* see and look with an address: the body turns to face it, and what it sees is read once it has. */
export function faceToward(who, node, address) {
  const body = who.figure?.talk ? figureBody(who.figure) : who.mascot && mascotGlyph() ? mascotBody() : null;
  if (!body) return null;
  body.bump();
  if (!sendBody(body, null, {node})) return null;
  return settle(body, {address, most: 3000});
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
  if (!figure && !MASCOT.mesh) {  // the mascot is drawn once the person gives their system agent a body
    return {error: 'You have no figure on the map and the mascot is not drawn: take a body with web_embody.',
      next: 'web_embody with a character, then web_come again'};
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
  open: (payload, node, {tell}) => openFor(payload, tell),
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
/* A step from where a body stands, measured along the way it faces, `ahead`, flat: forward, to its right, and up. */
function stepFrom(at, ahead, payload) {
  const side = new THREE.Vector3().crossVectors(ahead, THREE.Object3D.DEFAULT_UP).normalize();
  return at.clone().addScaledVector(ahead, Number(payload.forward || 0))
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
/* What the agent opens on the page for the person, `which` naming the ticket or pane (`id` is the act's own): an
 * error when nothing opens, so `web open` never answers success for a box it did not open. */
function openFor(payload, tell) {
  const which = payload.which;
  if (payload.what === 'board') { if ($('#board').hidden) $('#boardBtn').click(); tell('The board.'); }
  else if (payload.what === 'settings') { openSettings(); tell('Settings.'); }
  else if (payload.what === 'pane') {  // a page's pane, or a pane by its own id
    if (!WS.active) return {error: `The workspace is off, so there is no pane ${which} to open.`};
    if (!which || !(WS.reveal(which) || WS.activate(which))) return {error: `No pane ${which} in the workspace.`};
    tell('There.');
  } else if (payload.what === 'ticket') {  // its node, its work in the panel
    const ticket = which ? ticketOf(which) : null;
    if (!ticket) { tell('I cannot find that ticket.'); return {error: `No ticket ${which} on this map.`}; }
    const node = ticketNode(ticket);
    MASCOT.call = {node, until: MASCOT.driven, agent: true};
    setTimeout(() => { select(node, true); showTab('object'); }, reduced() ? 0 : 900);
    tell(`Ticket on ${ticketPart(ticket)}.`);
  } else return {error: `${payload.what} cannot be opened.`};
  return {done: true};
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
