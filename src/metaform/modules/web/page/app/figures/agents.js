/* The 3D map's agents at work, VIEW-035: a figure for each ticket an agent works, bodies for conversation agents,
 * their characters and previews. */
import '/page/app/graph/checks.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
import {createAgent, releaseGlyph, motionOf, strokeOf, GLYPHS, MOTION} from '/page/agents3d.js';
import {reduced} from '/page/app/core/dom.js';
import {S} from '/page/app/core/reads.js';
import {MASCOT, preferredGlyph, mascotGlyph} from '/page/app/figures/mascot.js';
import {say} from '/page/app/figures/cut.js';
import {ROAM2D, figures2d} from '/page/app/figures/roam2d.js';
import {endOf} from '/page/app/map3d/waves.js';
import {G, nodeSize, wake3d} from '/page/app/map3d/graph3d.js';
import {AT} from '/page/app/map3d/labels.js';
import {flowLive, flowTickets} from '/page/app/flow/flow.js';
import {wake2d} from '/page/app/map2d/flow2d.js';
import {D, ticketOf, glyphFor} from '/page/app/agents/dispatch.js';
import {holderOf, depthView, setFocus} from '/page/app/keys/walk.js';
import {nodeIn} from '/page/app/graph/data.js';
import {keepMascot} from '/page/app/views/settings.js';

/* ---------- 3D: a synaptic map, drawn as the approved prototype draws it ---------- */
// built draws nothing
export const CONDITIONS = ['missing', 'unbuilt', 'under-construction', 'broken', 'trouble', 'question', 'message'];
/* The agents at work, VIEW-035: a figure for each ticket an agent works, from the moment it is taken until it is
 * closed. It materializes on the most primary node, the DE, makes its way along the map's own edges to the ticket's
 * node, goes onto it and circles it slowly, facing the way it moves, at one steady pace until the ticket is closed;
 * then it makes its way back and is gone. Steps filed never speed it up: the node's flashing, or its text for a part
 * not built, shows how far along the work is. A figure is big enough to see what it is with the whole map in view:
 * its size is a share of the drawn map's span, and never less than ROAM.size. A ticket that was finished before its
 * figure got there is still touched, and then the figure walks back. A figure is one of the seventeen characters of
 * agents3d.js, drawn so that no two at work look alike, or the one the person chose for its agent's type,
 * web_agent_glyphs. It moves as its body would, its character's motion profile, `MOTION` in agents3d.js, varied a
 * little by its ticket so two of one character still differ: its own pace and acceleration, how it takes a corner,
 * its gait (a fish's bursts and glides, a hopper's arcs, a walker's steps in time with the ground it covers), its
 * orbit, lap and way round, how it comes and goes, and its temper, from serious to mischievous. Along a smooth curve
 * through the nodes of its way it sets off and arrives gently and slows into sharp turns, facing the way it goes and,
 * if it flies or swims, leaning into its turns. On its node it does what its session is doing, `onNode`. With reduced
 * motion it stands at the node. */
export const ROAM = {figures: new Map(), seen: new Set(), last: 0, speed: 70, size: 2.6, share: 0.11, orbit: 1.5,
  lap: 12, recent: 120, appear: 0.8, touch: 0.9, vanish: 0.6,
  // how it moves along its way: units a second it speeds up and slows down by, and how much of its speed a turn
  // straight back takes off, a gentler turn less; how long it takes to settle from its way onto its orbit; and how
  // fast the size it is drawn at follows the map's span, so a layout that spreads never makes it jump
  accel: 70, corner: 0.6, settle: 1.1, grow: 10, drawn: 0, sized: 0,
  // the work whose thread the person chose in the chat dock: its figure is drawn this much larger, moving as if busy
  focus: null, focused: 1.4,
  // the most pixels a figure stands on the screen, however near the camera is, while `held`, as it is unless the
  // person let them grow: a camera watching a large figure otherwise stands inside it; key 6 lets figures grow as near
  // things do and holds them again, kept in this browser, `holdAgentSize`. The choice is kept under its own key since
  // 2026-10-18, when held became the default: the old key, metaform.agentSizeHeld, kept a choice made when figures
  // grew by default, and is no longer read.
  most: 110,
  held: (() => { try { return localStorage.getItem('metaform.agentSizeFree') !== '1'; } catch { return true; } })(),
  // told the node when a figure starts or ends its time at work there, the work camera's `workChanged`
  onWork: null};
// a join's key names its receiving element's node, as a join has no node of its own, `nodeIn`
export const nodeById = (data, id) => nodeIn(data, id);
export const primaryOf = data => data.nodes.find(node => node.t === 'el' && node.role === 'DE')
  || data.nodes.find(node => node.t === 'el');
export const ticketNode = ticket => ticket.node_kind === 'join' ? 'p:' + ticket.node_id : ticket.node_id;
export const ballOf = node => Math.cbrt(nodeSize(node)) * 3;
export function sizeOf(data) {  // a figure's size: a share of half the drawn map's widest side
  const low = [Infinity, Infinity, Infinity], high = [-Infinity, -Infinity, -Infinity];
  for (const node of data.nodes) {
    if (node.x === undefined) continue;
    [node.x, node.y, node.z].forEach((at, axis) => {
      low[axis] = Math.min(low[axis], at);
      high[axis] = Math.max(high[axis], at);
    });
  }
  const half = Math.max(0, ...high.map((top, axis) => (top - low[axis]) / 2).filter(Number.isFinite));
  return Math.max(ROAM.size, ROAM.share * half);
}
/* Each node's neighbours on the drawn map, by its id, both ways along every link. */
function neighboursOf(data) {
  const near = new Map(), add = (one, two) => { if (!near.has(one)) near.set(one, []); near.get(one).push(two); };
  for (const link of data.links) {
    add(endOf(link.source), endOf(link.target));
    add(endOf(link.target), endOf(link.source));
  }
  return near;
}
export function routeOf(data, from, to) {  // the fewest edges of the drawn map from one node to another
  return pathThrough(neighboursOf(data), from, to);
}
/* The fewest steps from one node to another through each node's neighbours, both ends included; straight across
 * when no way joins them. */
export function pathThrough(near, from, to) {
  const back = new Map([[from, null]]), queue = [from];
  while (queue.length && !back.has(to)) {
    const at = queue.shift();
    for (const next of near.get(at) || []) if (!back.has(next)) { back.set(next, at); queue.push(next); }
  }
  if (!back.has(to)) return [from, to];
  const path = [];
  for (let at = to; at !== null; at = back.get(at)) path.unshift(at);
  return path;
}
/* The figures, VIEW-035: one for each ticket an agent is working in a live session, the agents key's own list, so an
 * agent that is not active is not on the map, whatever its ticket says; when its session ends the figure walks back
 * and is gone. */
export const liveWork = () => new Set(D.sessions.filter(one => one.state === 'running'
  && (one.activity === 'working' || one.activity === 'waiting')).map(one => one.work_id));
export function figures(tickets) {
  // the branches of the work in hand open on both maps, and close when it is done or its agent stops, walk.js FOCUS
  const live = liveWork();
  setFocus('work', tickets.filter(ticket => !ticket.done && !conversing(ticket)
    && (ticket.taken || live.has(ticket.id))).map(ticketNode));
  flowTickets(tickets);  // a work record written lands on its node as a record, `FLOW`
  const drawn = helpers(live, figureTickets(tickets));
  figures2d(drawn);
  if (!G) return;
  const data = G.graphData(), home = primaryOf(data);
  if (!home) return;
  const view = depthView();  // what the depth shows with the branches just opened, worked out once for every ticket
  for (const ticket of drawn) {
    // a part held deeper than the depth is worked at the node that holds it, VIEW-051
    const figure = ROAM.figures.get(ticket.id);
    const target = holderOf(ticket.held ? talkTarget(ticket, data) : ticketNode(ticket), view);
    const working = drawnWorking(ticket, live);
    if (figure) {
      if (working && figure.done) turnRound(figure, data);
      figure.done = !working;
      reglyph(figure);
      continue;
    }
    if (working && (!ROAM.seen.has(ticket.id) || conversing(ticket)) && nodeById(data, target)) {
      startFigure(ticket, data, home, target);
    }
  }
  for (const [id, figure] of ROAM.figures) {
    if (!figure.child && !drawn.some(ticket => ticket.id === id)) figure.done = true;
  }
  childFigures(data, home);
  wake3d();
}
/* The tickets with a figure, and a helper the system agent started, dispatch helper, for each one working: it holds no
 * ticket, so it stands in as one at the map's primary element, the DE, where every figure comes from, and is drawn on
 * both maps as a ticket's agent is until its session ends. */
function helpers(live, tickets) {
  const de = [...S.elements.values()].find(item => item.element.role === 'DE')?.element.id;
  const working = de ? [...live].filter(id => String(id).startsWith('helper-')) : [];
  return working.length ? [...tickets, ...working.map(id => ({id, node_kind: 'element', node_id: de, held: false,
    done: null}))] : tickets;
}
/* An agent's own subagents, P016, each a figure of its own while it runs: the native child sessions its agent reports,
 * never a ticket. It walks out to the node its parent works at and works there beside it, waits there while its state
 * asks for input, and walks back when it ends or its parent's session does. Keyed by its own session id, so it never
 * takes a ticket's figure, and drawn from this project's sessions only. In 3D; the 2D map shows its parent alone. */
const CHILD_ENDED = ['completed', 'failed', 'cancelled', 'canceled', 'disconnected', 'ended', 'error'];
export const childKey = session => `child:${session}`;
export const childOf = id => ROAM.figures.get(id)?.child
  || (String(id).startsWith('child:') ? (D.subagents || []).find(one => childKey(one.session_id) === id) : null);
function childFigures(data, home) {
  const running = new Map(D.sessions.filter(one => one.state === 'running').map(one => [one.session_id, one]));
  const kids = new Map();
  for (const child of D.subagents || []) {
    const parent = running.get(child.parent);
    if (parent && !CHILD_ENDED.includes(String(child.state))) kids.set(childKey(child.session_id), {child, parent});
  }
  for (const [id, figure] of ROAM.figures) if (figure.child && !kids.has(id)) figure.done = true;
  for (const [id, {child, parent}] of kids) {
    const figure = ROAM.figures.get(id);
    if (figure) {
      if (figure.done) turnRound(figure, data);
      Object.assign(figure, {done: false, child: {...figure.child, state: child.state}});
      continue;
    }
    const ticket = ticketOf(parent.work_id);
    const target = ROAM.figures.get(parent.work_id)?.target || (ticket ? ticketNode(ticket) : home.id);
    if (!nodeById(data, target)) continue;
    startFigure({id}, data, home, target);
    ROAM.figures.get(id).child = {session: child.session_id, parent: parent.session_id, work: parent.work_id,
      name: child.name || null, state: child.state, agent: parent.agent};
  }
}
/* A figure whose session works again before it is gone turns round: from its flourish back onto its orbit, from its
 * way home back along it to its node, and from going on the primary node back out and on its way again. Once gone,
 * `gone` forgets it was seen, so the next time its session works it walks on as a new figure. */
function turnRound(figure, data) {
  if (figure.stage === 'flourish') Object.assign(figure, {stage: 'circling', clock: 0});
  else if (figure.stage === 'returning') {
    const from = figure.way[Math.floor(figure.u)]?.id || figure.target;
    Object.assign(figure, {stage: 'going', u: 0, speed: 0, clock: 0,
      way: [{point: figure.mesh.position.clone()}, ...routeOf(data, from, figure.target).map(id => ({id}))]});
  } else if (figure.stage === 'leaving') {
    const left = Math.min(1, figure.clock / ROAM.vanish);
    Object.assign(figure, {stage: 'arriving', u: 0, speed: 0, clock: (1 - left) * ROAM.appear,
      way: routeOf(data, figure.home, figure.target).map(id => ({id}))});
  }
}
/* A new figure for a ticket: its character's body, at the primary node, set on its way to the ticket's node. */
function startFigure(ticket, data, home, target) {
  const glyph = glyphFor(ticket.id), mesh = createAgent(glyph), motion = motionOf(glyph, ticket.id);
  mesh.userData.motion = motion;
  mesh.scale.setScalar(0.001);
  G.scene().add(mesh);
  ROAM.seen.add(ticket.id);
  flowLive('start', home.id, [target]);  // the session's request goes ahead of the figure, `FLOW`
  ROAM.figures.set(ticket.id, {id: ticket.id, glyph, mesh, motion, home: home.id, target, stage: 'arriving',
    way: routeOf(data, home.id, target).map(id => ({id})), u: 0, speed: 0, clock: 0,
    angle: motion.phase * Math.PI * 2, points: [], curve: new THREE.CatmullRomCurve3([], false, 'centripetal'),
    from: new THREE.Vector3(), heading: new THREE.Vector3(0, 0, 1), done: false,
    stride: 0, steps: 0, pos: new THREE.Vector3(), vel: new THREE.Vector3(), mood: 'working', act: null,
    nextAct: 4 + motion.phase * 6, reach: null, glance: null, nextGlance: 0, lane: 0, talk: conversing(ticket)});
}
/* A body for a conversation agent, VIEW-005: the person's system agent, from Call, or an agent the person chats with
 * about a node or a ticket. Unembodied, it is drawn as it always was: no figure while the person has a mascot, else a
 * plain one while it works. Given a body, `embody`, by the person through /mascot or by the agent itself
 * with web_embody, it walks out from the map's primary node in that character, with its motion and its temper: the
 * system agent to what the person has selected, or beside the mascot, and an agent chatting about something to it.
 * It sees from its own eyes, `seer`, and speaks in its own bubble. The body the person gives the system agent is the
 * mascot, web_mascot, held by the server for every conversation; one the system agent takes itself, web_embody, is
 * its own figure for that conversation, which its acts move. Any other body is kept for the conversation, by its
 * ticket, so a resumed conversation comes back in the same body; the person's choice stands over the agent's, and no
 * two figures at work share a character. */
const SYSTEM_TALK = 'Conversation with the system agent';  // the system agent's ticket, dispatch's SYSTEM_TASK
// Current system conversations live in dispatch, outside the board: the system conversation, `conversation-system`,
// and each user agent task, dispatch's user_agent, whose work id is its task's and whose session names it,
// `task_name`. A view record per conversation only gives their bodies the existing figure lifecycle; it never enters
// S.tickets or creates a work ticket.
const SYSTEM_WORK = 'conversation-system';
const SYSTEM_CONVERSATIONS = new Map();
function systemConversation(work) {
  if (!SYSTEM_CONVERSATIONS.has(work)) {
    SYSTEM_CONVERSATIONS.set(work,
      {id: work, node_kind: 'element', node_id: null, held: true, done: null, task: SYSTEM_TALK});
  }
  return SYSTEM_CONVERSATIONS.get(work);
}
/* Whether a work id is a conversation with the person's system agent: the system conversation, or a user agent
 * task's. */
const systemWork = work => work === SYSTEM_WORK
  || D.sessions.some(one => one.work_id === work && one.task_name === 'user_agent');
/* The sessions of the system conversations running now, the newest last. */
const systemSessions = () => D.sessions.filter(one => one.state === 'running' && systemWork(one.work_id));
export function conversationOf(work) {
  if (!systemWork(work)) return ticketOf(work);
  return D.sessions.some(one => one.work_id === work && one.state === 'running') ? systemConversation(work) : null;
}
/* The conversation the mascot speaks for: the newest system conversation running, else a ticket held for one. */
export const systemTalk = () => {
  const live = systemSessions().at(-1);
  return live ? systemConversation(live.work_id) : (S.tickets || []).find(isSystemTalk);
};
function figureTickets(tickets) {
  const systems = [...new Set(systemSessions().map(one => one.work_id))]
    .filter(work => !tickets.some(ticket => ticket.id === work)).map(systemConversation);
  if (!systems.length) return tickets;
  // The primary element is the conversation's home on either map, even after switching bases.
  const home = [...S.elements.values()].find(item => item.element.role === 'DE')?.element.id
    || S.elements.keys().next().value || null;
  for (const system of systems) system.node_id = home;
  return [...tickets, ...systems];
}
function keptBodies() {
  try { return JSON.parse(localStorage.getItem('metaform.bodies') || '{}'); } catch { return {}; }
}
export const BODIES = {chosen: keptBodies()};
export const bodyKey = work => `${S.project}|${work}`;
function keepBodies() {
  try { localStorage.setItem('metaform.bodies', JSON.stringify(BODIES.chosen)); } catch { /* kept for this page */ }
}
try { localStorage.removeItem('metaform.embodied'); } catch { /* the last body picked, kept before web_mascot was */ }
// a body kept for a conversation is the one it was given in: that session, and the same session resumed; a new
// conversation has none
function heldBody(work) {
  const held = BODIES.chosen[bodyKey(work)];
  if (!held?.glyph) return null;
  const live = held.session ? D.sessions.filter(one => one.work_id === work && one.state === 'running').at(-1) : null;
  return !live || live.session_id === held.session ? held : null;
}
// the body the system agent took itself in this conversation, web_embody, not the person's mascot
export const ownBody = ticket => {
  const held = heldBody(ticket.id);
  return held?.by === 'agent' ? held.glyph : null;
};
export const isSystemTalk = ticket => Boolean(ticket?.held && ticket.task === SYSTEM_TALK);
/* A conversation agent's body: the system agent's own, else the person's mascot; any other's, the one kept for it. */
export function bodyOf(work) {
  const ticket = conversationOf(work);
  if (isSystemTalk(ticket)) return ownBody(ticket) || mascotGlyph();
  return heldBody(work)?.glyph || null;
}
const talking = ticket => D.sessions.some(one => one.work_id === ticket.id && one.state === 'running');
/* A conversation's ticket: one held for it, or a done one a session began on after it was done, since dispatch ends a
 * ticket agent's session when its ticket is done and only a conversation about the ticket starts on it after. */
export const conversing = ticket => Boolean(ticket?.held || ticket?.done && D.sessions.some(one =>
  one.work_id === ticket.id && one.state === 'running' && Date.parse(one.started) > Date.parse(ticket.done)));
/* Whether a ticket's agent is drawn as a figure now. */
export function drawnWorking(ticket, live = liveWork()) {
  if (!conversing(ticket)) return !ticket.done && live.has(ticket.id);
  // the system agent is drawn as the mascot, web_mascot; a body it took itself is its own figure
  if (isSystemTalk(ticket) && !ownBody(ticket)) return false;
  const body = bodyOf(ticket.id);
  if (body) return talking(ticket);
  return live.has(ticket.id) && !mascotGlyph();
}
/* Where an embodied conversation agent goes: the system agent to the selection, or beside the mascot; another to what
 * it talks about. */
function talkTarget(ticket, data) {
  if (!isSystemTalk(ticket)) return ticketNode(ticket);
  if (S.selected && nodeById(data, S.selected)) return S.selected;
  return (MASCOT.mesh && nearestElement(data, MASCOT.pos)) || ticketNode(ticket);
}
/* The id of the drawn element nearest a point of the scene, or null. */
function nearestElement(data, point) {
  let best = null, nearest = Infinity;
  for (const node of data.nodes) {
    if (node.t !== 'el' || node.x === undefined) continue;
    const away = point.distanceTo(AT.set(node.x, node.y, node.z));
    if (away < nearest) { nearest = away; best = node.id; }
  }
  return best;
}
/* An embodied conversation figure follows what it is about: it walks on to a new selection, along the map's edges. */
export function retarget(figure, data) {
  if (!figure.talk || figure.stage !== 'circling' || figure.done) return;
  const ticket = conversationOf(figure.id), wanted = ticket && talkTarget(ticket, data);
  if (!wanted || wanted === figure.target || !nodeById(data, wanted)) return;
  const way = routeOf(data, figure.target, wanted);
  Object.assign(figure, {target: wanted, stage: 'going', u: 0, clock: 0,
    way: [{point: figure.mesh.position.clone()}, ...(way.length > 1 ? way.slice(1) : [wanted]).map(id => ({id}))]});
}
/* Give a conversation agent a body: `by` the person, whose choice stands, or the agent, `web_embody`. */
export function embody(work, glyph, by = 'person') {
  const ticket = conversationOf(work), key = bodyKey(work), held = BODIES.chosen[key];
  if (!GLYPHS.includes(glyph)) return {error: `${glyph} is not a character.`};
  if (!ticket) return {error: 'There is no such conversation on this page.'};
  const system = isSystemTalk(ticket);
  if (by === 'agent' && !system && held?.by === 'person') {
    if (held.glyph !== glyph) return {error: `The person gave you the ${held.glyph}; it stays.`};
    by = 'person';  // the person's gift stays theirs
  }
  if (by === 'agent' && system && glyph === preferredGlyph()) by = 'person';  // the person's mascot stays theirs
  // the body the person gives the system agent is the mascot; one an agent takes itself is its own figure; the
  // mascot's character is no other agent's while it is drawn
  const mascot = system && by === 'person';
  if (glyph === mascotGlyph() && !mascot) return {error: `The ${glyph} is the person's mascot.`};
  const other = [...ROAM.figures.values()]
    .find(figure => figure.id !== work && figure.glyph === glyph && figure.stage !== 'leaving');
  if (other) return {error: `The ${glyph} is at work already on this map.`};
  if (mascot) {  // the person's mascot, web_mascot, for every conversation; a body the agent took itself goes
    BODIES.chosen[key] = null;
    keepMascot(glyph);
  } else {  // kept with the session it was given in, so the same conversation resumed comes back in it
    const live = D.sessions.filter(one => one.work_id === work && one.state === 'running').at(-1);
    BODIES.chosen[key] = {glyph, by, session: live?.session_id || null};
  }
  keepBodies();
  releaseGlyph(work);
  const figure = ROAM.figures.get(work);
  if (figure) { if (mascot) figure.done = true; else reglyph(figure); }
  figures(S.tickets || []);
  // the mascot walks out from the map's primary node and greets the person
  const greeting = by === 'agent' ? 'A body of my own. Thank you.' : 'Here I am.';
  say(greeting, 3, null, mascot ? null : work, mascot ? glyph : '');
  wake3d(3000);
  if (typeof wake2d === 'function') wake2d();
  return {character: glyph, mascot, figure: !mascot};
}
// the person's mascot changed, on this page or another: an unembodied agent is drawn plain only while there is none,
// and the maps draw the mascot as it is now
document.addEventListener('metaform:mascot', () => {
  figures(S.tickets || []);
  wake3d(3000);
  if (typeof wake2d === 'function') wake2d();
});
/* Each conversation agent and its body, for the chat dock's offer. */
export function bodies() {
  return figureTickets(S.tickets || []).filter(ticket => conversing(ticket) && talking(ticket)).map(bodyRow);
}
function bodyRow(ticket) {
  const character = bodyOf(ticket.id), system = isSystemTalk(ticket);
  const mascot = system && Boolean(character) && !ownBody(ticket);  // the person's mascot is the person's choice
  return {work: ticket.id, system, character,
    by: mascot ? 'person' : character ? heldBody(ticket.id)?.by || null : null,
    drawn: mascot ? Boolean(MASCOT.mesh) : ROAM.figures.has(ticket.id), mascot};
}
/* The characters a body can be, for the picker: each with its name, its temper and a word for it, how it moves, whether
 * it is free now, and `preview(canvas)`, which draws it moving in its own way on a small canvas until the function it
 * returns is called; with reduced motion it stands still. */
const TEMPERS = [[0.2, 'serious'], [0.45, 'steady'], [0.7, 'playful'], [1.01, 'mischievous']];
export function characters() {
  const busy = new Set([...ROAM.figures.values()].map(figure => figure.glyph));
  return GLYPHS.map(name => characterOf(name, busy));
}
function characterOf(name, busy) {
  const temper = MOTION[name].temper;
  return {name, temper, temperament: TEMPERS.find(([most]) => temper < most)[1],
    moves: MOTION[name].go, free: !busy.has(name) && name !== mascotGlyph(), mascot: name === mascotGlyph(),
    preferred: name === preferredGlyph(),  // web_mascot: the person's own character, suggested first
    preview: canvas => previewOf(canvas, name)};
}
/* How a character's body is posed in its preview at this point of its stride: lifted, squashed or leaning. */
function poseOf(motion, stroke, landed, now) {
  let lift = 0, squash = 0, lean = 0;
  if (motion.go === 'hop') {
    lift = stroke.air * motion.lift * 0.5;
    const land = stroke.phase >= 0.75 ? Math.sin((stroke.phase - 0.75) / 0.25 * Math.PI) * 0.2 : 0;
    squash = land + Math.exp(-landed * 14) * 0.12;
  } else if (motion.go === 'walk' || motion.go === 'creep') {
    lift = Math.abs(Math.sin(stroke.phase * Math.PI * 2)) * 0.05;
  } else if (motion.go === 'swim' || motion.go === 'pulse') {
    lean = Math.sin(stroke.phase * Math.PI * 2) * 0.12 * stroke.thrust;
  } else lift = Math.sin(now / 1000 * 2.2) * 0.04;
  return {lift, squash, lean};
}
function previewOf(canvas, name) {
  const pen = canvas.getContext('2d'), image = new Image(), motion = {...MOTION[name], phase: 0};
  image.src = `/page/agent-glyphs/${name}.svg`;
  let id = 0, stride = 0, last = performance.now(), landed = 9, was = 0;
  const draw = now => {
    const passed = Math.min(0.1, (now - last) / 1000), w = canvas.width, h = canvas.height;
    const size = Math.min(w, h) * 0.7;
    last = now;
    stride += reduced() ? 0 : passed * motion.speed * 1.4;
    const stroke = strokeOf(motion, stride);
    if (was < 0.75 && stroke.phase >= 0.75) landed = 0;
    landed += passed; was = stroke.phase;
    const {lift, squash, lean} = poseOf(motion, stroke, landed, now);
    pen.clearRect(0, 0, w, h);
    if (image.complete && image.naturalWidth) {
      pen.save();
      pen.translate(w / 2, h * 0.9 - lift * h);
      pen.rotate(lean);
      pen.scale(1 + squash * 0.6, 1 - squash);
      pen.drawImage(image, -size / 2, -size, size, size);
      pen.restore();
    }
    if (!reduced()) id = requestAnimationFrame(draw);
  };
  image.onload = () => { cancelAnimationFrame(id); id = requestAnimationFrame(draw); };
  id = requestAnimationFrame(draw);
  return () => cancelAnimationFrame(id);
}
/* A figure drawn before the page knew its agent's type takes the character chosen for the type, web_agent_glyphs,
 * where it stands, in both maps. */
export function reglyph(figure) {
  const glyph = glyphFor(figure.id);
  if (glyph === figure.glyph) return;
  const mesh = createAgent(glyph), motion = motionOf(glyph, figure.id);
  mesh.userData.motion = motion;
  mesh.position.copy(figure.mesh.position);
  mesh.quaternion.copy(figure.mesh.quaternion);
  mesh.scale.copy(figure.mesh.scale);
  G.scene().remove(figure.mesh);
  G.scene().add(mesh);
  Object.assign(figure, {glyph, mesh, motion});
  const flat = ROAM2D.figures.get(figure.id);
  if (flat) {
    Object.assign(flat, {glyph, motion: motionOf(glyph, figure.id)});
    flat.g.dataset.glyph = glyph;
    flat.g.querySelector('image')?.setAttribute('href', `/page/agent-glyphs/${glyph}.svg`);
  }
}
