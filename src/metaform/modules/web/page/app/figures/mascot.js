/* The person's mascot in 3D, web_mascot: who leads it, its wanders and mischief, the nodes it pushes and carries,
 * and its frame. */
import '/page/app/figures/roam3d.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
import {createAgent, orientAgent, motionOf, strokeOf, reserveGlyph, GLYPHS} from '/page/agents3d.js';
import {$, css, reduced} from '/page/app/core/dom.js';
import {S} from '/page/app/core/reads.js';
import {ROAM, nodeById, primaryOf, ballOf, BODIES, bodyKey, isSystemTalk} from '/page/app/figures/agents.js';
import {AHEAD, TOWARD, easeBoth, nudgeNode, markTrail, SPOT, steer, driveGoal, driveFace}
  from '/page/app/figures/walk.js';
import {CUT, mascotForCut} from '/page/app/figures/cut.js';
import {EYE} from '/page/app/figures/eyes.js';
import {G, FRAMES, DRAG_FRICTION, wake3d} from '/page/app/map3d/graph3d.js';
import {AT} from '/page/app/map3d/labels.js';
import {PHYS} from '/page/app/views/bar.js';
import {wake2d} from '/page/app/map2d/flow2d.js';
import {DOCK} from '/page/app/dock/embody.js';
import {D} from '/page/app/agents/dispatch.js';
import {WS} from '/page/app/workspace/workspace.js';

/* The person's mascot, web_mascot: one of the characters, standing for the person on the map, never given to an agent
 * and never picked by a click. It goes to what the person selects, in its own way, and waits beside it, on the side
 * away from its name; when the person chats with an agent at work it goes to that agent and the two greet each other;
 * agents passing notice it. Left alone, it wanders now and then, web_mascot_mischief playful or chaotic, nudging a
 * node it passes, and dodges a pointer that chases it; calm, it only goes where it is needed. Once the page has been
 * left alone as long as the flow lasts, web_flow_seconds, it falls asleep where it is, and wakes with the person. It
 * moves by steering, setting off and arriving gently at its own pace, and with reduced motion it just stands there. */
export const MASCOT = {glyph: null, mesh: null, motion: null, pos: new THREE.Vector3(), vel: new THREE.Vector3(),
  heading: new THREE.Vector3(0, 0, 1), stride: 0, clock: 0, state: 'idle', greeted: null, wander: null, nextWander: 20,
  nudged: 0, dodge: null, pointer: {x: -1e4, y: -1e4, at: 0, speed: 0}, sleeping: false, most: 64};
const ASIDE = new THREE.Vector3(), UPWARD = new THREE.Vector3(), FACEAT = new THREE.Vector3();
/* web_mascot is the person's preferred character, the one the body picker suggests first; it draws nothing. The
 * mascot is the person's system agent once it has a body: no figure is on the map until the system agent offers to
 * take one and the person accepts, or the person gives it one. It is drawn while that conversation runs, and a
 * resumed conversation, the same session again, comes back in the same body; a new one is offered a body afresh. A
 * body the system agent took itself, web_embody, is its own figure and not the mascot. */
export function preferredGlyph() {
  const chosen = WS.view().mascot;
  return GLYPHS.includes(chosen) ? chosen : null;
}
export function mascotGlyph() {
  const ticket = (S.tickets || []).find(isSystemTalk);
  const held = ticket ? BODIES.chosen[bodyKey(ticket.id)] : null;
  if (!held || held.by === 'agent' || !GLYPHS.includes(held.glyph)) return null;
  const live = D.sessions.filter(one => one.work_id === ticket.id && one.state === 'running').at(-1);
  return live && (!held.session || held.session === live.session_id) ? held.glyph : null;
}
/* The mascot as it is drawn: its body while its conversation runs, then, once that ends, the same body walking home
 * for a few seconds before it goes; with reduced motion it goes at once. */
const MASCOT_GONE = {glyph: null, since: 0};
export function mascotFigure() {
  const glyph = mascotGlyph();
  if (glyph) { Object.assign(MASCOT_GONE, {glyph, since: 0}); return {glyph, leaving: false}; }
  if (!MASCOT_GONE.glyph) return {glyph: null, leaving: false};
  if (!MASCOT_GONE.since) MASCOT_GONE.since = performance.now();
  if (reduced() || performance.now() - MASCOT_GONE.since > 7000) {
    MASCOT_GONE.glyph = null;
    return {glyph: null, leaving: false};
  }
  return {glyph: MASCOT_GONE.glyph, leaving: true};
}
/* Who leads the mascot: its own will, wandering, following the selection and going where it is needed, by its
 * temper; or its system agent, through its body's verbs. Each verb holds it for DRIVE_HOLD after the last, or until
 * the agent's turn ends; web_take holds it longer, with a reason, until web_release. While the agent drives, the
 * person's selection waits for it, and nothing else sends the mascot anywhere. Let go, it takes up its own way again
 * from where it stands. */
const DRIVE_HOLD = 20000, DRIVE_TAKEN = 600000;
export function mascotDriven() {
  const now = performance.now();
  if (!MASCOT.driven || now >= MASCOT.driven) { if (MASCOT.driven) releaseMascot(); return false; }
  if (!MASCOT.held && now - (MASCOT.drivenAt || 0) > 3000) {  // its turn has ended: the agent let it go
    const ticket = (S.tickets || []).find(isSystemTalk);
    const live = ticket && D.sessions.filter(one => one.work_id === ticket.id && one.state === 'running').at(-1);
    if (!live || live.activity !== 'working') { releaseMascot(); return false; }
  }
  return true;
}
export function driveMascot(take = null) {
  const now = performance.now();
  if (take) MASCOT.held = {reason: take.reason || '', at: now};
  MASCOT.drivenAt = now;
  MASCOT.driven = Math.max(MASCOT.driven || 0, now + (MASCOT.held ? DRIVE_TAKEN : DRIVE_HOLD));
}
export function releaseMascot() {
  Object.assign(MASCOT, {driven: 0, held: null, facing: null});
  if (MASCOT.call?.agent) MASCOT.call = null;  // where the agent sent it; what the person selected meanwhile is next
  wake3d(1500);
  if (typeof wake2d === 'function') wake2d();
}
const mischief = () => WS.view().mascot_mischief || 'playful';
export function mascotAwake() {  // it keeps the 3D map drawing only while it is up and about
  return Boolean(MASCOT.mesh) && !reduced() && !MASCOT.sleeping;
}
function besideNode(node, size, out) {  // beside a node on the screen's right, below where its name is drawn
  const camera = G.camera();
  ASIDE.setFromMatrixColumn(camera.matrixWorld, 0).normalize();
  UPWARD.setFromMatrixColumn(camera.matrixWorld, 1).normalize();
  // below and to the right, clear of the name drawn across the node
  return out.set(node.x, node.y, node.z).addScaledVector(ASIDE, ballOf(node) + size * 0.6)
    .addScaledVector(UPWARD, -(ballOf(node) + size * 0.7));
}
/* Where a call sends the mascot: beside its node, or a viewpoint as far from it and as high as asked, facing it. */
function callSpot(data, size) {
  const node = nodeById(data, MASCOT.call?.node), call = MASCOT.call;
  if (!node || node.x === undefined) return null;
  if (call.distance == null && call.height == null) return {want: besideNode(node, size, SPOT), face: null};
  TOWARD.subVectors(MASCOT.pos, AT.set(node.x, node.y, node.z)).setY(0);
  if (TOWARD.lengthSq() < 1e-6) TOWARD.set(1, 0, 0);
  const want = SPOT.set(node.x, node.y + Number(call.height || 0), node.z)
    .addScaledVector(TOWARD.normalize(), Math.max(ballOf(node) + size, Number(call.distance ?? size * 3)));
  return {want, face: FACEAT.set(node.x, node.y, node.z)};
}
/* A wander of its own: anywhere in the scene around the map, not only beside a node, as its character moves there,
 * a flyer through the air, a swimmer through the water, a walker hopping or floating; now and then to a node. */
function wanderTo(data, size) {
  const nodes = data.nodes.filter(node => node.t === 'el' && node.x !== undefined);
  if (!nodes.length) return null;
  if (Math.random() < 0.35) return {id: nodes[Math.floor(Math.random() * nodes.length)].id, until: MASCOT.clock + 9};
  const low = [Infinity, Infinity, Infinity], high = [-Infinity, -Infinity, -Infinity];
  for (const node of nodes) [node.x, node.y, node.z].forEach((at, axis) => {
    low[axis] = Math.min(low[axis], at);
    high[axis] = Math.max(high[axis], at);
  });
  const anywhere = axis => low[axis] - size * 2 + Math.random() * (high[axis] - low[axis] + size * 4);
  const point = new THREE.Vector3(...[0, 1, 2].map(anywhere));
  return {point, until: MASCOT.clock + 9};
}
/* Its own mischief, by its temper: now and then a wander anywhere in the scene, rarer while it keeps the person
 * company beside a selection, and now and then a shove at a node, more often the more mischievous it is. Returns
 * whether it is on a wander now. */
function mischiefDue(data, size, m, keeping) {
  const chaotic = mischief() === 'chaotic';
  if (MASCOT.wander && MASCOT.clock > MASCOT.wander.until) MASCOT.wander = null;
  if (!MASCOT.wander && MASCOT.clock > MASCOT.nextWander) {
    MASCOT.wander = wanderTo(data, size);
    MASCOT.nextWander = MASCOT.clock + (chaotic ? 10 : 24) * (keeping ? 1.8 : 1) + Math.random() * 14;
  }
  if (!MASCOT.job && MASCOT.clock > (MASCOT.nextPush ?? 24 - 12 * m.temper)) {
    MASCOT.nextPush = MASCOT.clock + 70 - 55 * m.temper + Math.random() * 30;
    const free = data.nodes.filter(node => node.t === 'el' && node.x !== undefined && pushable(node));
    const pick = free[Math.floor(Math.random() * free.length)];
    if (pick) MASCOT.job = {kind: 'push', node: pick.id, dir: null, strength: 0.25 + 0.35 * m.temper, agent: false};
  }
  return Boolean(MASCOT.wander);
}
/* The node the person drags by hand, which the mascot never pushes or takes. */
export const HANDDRAG = {node: null};
const pushable = node => node && node.id !== S.selected && node !== HANDDRAG.node && node.fx === undefined
  && !CUT.job;
/* A node the mascot holds, pinned where it carries it; one at a time. Let go, it goes back to the layout, which
 * settles round it. Only the layout's positions change, as when the person drags a node: never the map. */
export function dropHeld() {
  const held = MASCOT.holding;
  if (!held) return;
  MASCOT.holding = null;
  Object.assign(held, {fx: undefined, fy: undefined, fz: undefined});
  if (!G) return;
  G.d3VelocityDecay(DRAG_FRICTION).d3ReheatSimulation();
  setTimeout(() => G?.d3VelocityDecay(PHYS.decay), 1500);
}
/* A shove: a kick of speed along `dir`, capped so the map is never flung apart; its joins pull its neighbours after
 * it and the layout settles, against more friction for a moment so it follows gently. Under reduced motion the node
 * is simply where the shove leaves it. */
function shove(node, dir, strength, size) {
  const kick = Math.min(1, Math.max(0.05, strength)) * size * 1.2;
  if (reduced()) {
    node.x += dir.x * kick * 2.5; node.y += dir.y * kick * 2.5; node.z += dir.z * kick * 2.5;
  } else {
    node.vx = (node.vx || 0) + dir.x * kick; node.vy = (node.vy || 0) + dir.y * kick;
    node.vz = (node.vz || 0) + dir.z * kick;
  }
  nudgeNode(node, 0.12);
  G.d3VelocityDecay(DRAG_FRICTION).d3ReheatSimulation();
  setTimeout(() => G?.d3VelocityDecay(PHYS.decay), 1500);
}
/* What the mascot is doing with its body, `MASCOT.job`: going to a point, pushing a node, or carrying one. Returns
 * where it steers this frame, or null once the job is done. A job of the agent's runs while the agent drives. */
function mascotJob(data, size) {
  const job = MASCOT.job;
  if (job.kind === 'move') return moveJob(job, data, size);
  const node = nodeById(data, job.node);
  if (!node || node.x === undefined || (!job.agent && !pushable(node) && MASCOT.holding !== node)) {
    MASCOT.job = null;
    return null;
  }
  AT.set(node.x, node.y, node.z);
  if (job.kind === 'push') return pushJob(job, node, size);
  if (job.kind === 'drag') return dragJob(job, node, data, size);
  MASCOT.job = null;
  return null;
}
/* Going beside a node or to a point; its own move ends once it is there. Where its agent sent it, `drive` in
 * attention.js, it goes at the pace fixed when it was sent and stays, facing the way asked. */
function moveJob(job, data, size) {
  if (job.drive) {
    return {want: driveGoal(job.drive, data, SPOT) || SPOT.copy(MASCOT.pos),
      face: driveFace(job.drive, MASCOT.pos, data, FACEAT), fast: job.drive.fast || 1};
  }
  const node = job.node ? nodeById(data, job.node) : null;
  const want = node && node.x !== undefined ? besideNode(node, size, SPOT) : job.point ? SPOT.copy(job.point) : null;
  if (!want || MASCOT.pos.distanceTo(want) < size * 0.3 && !job.agent) { MASCOT.job = null; return null; }
  return {want, fast: 1};
}
/* A push: from the side away from where it shoves, then a run at it; its own shoves go wherever it came from. The
 * node is at `AT`. */
function pushJob(job, node, size) {
  const dir = job.dir ? new THREE.Vector3(...job.dir) : TOWARD.subVectors(AT, MASCOT.pos).normalize().clone();
  if (dir.lengthSq() < 1e-6) dir.set(1, 0, 0);
  dir.normalize();
  const reach = ballOf(node) + size * 0.5;
  if (!job.charging) {
    const start = SPOT.copy(AT).addScaledVector(dir, -(reach + size * 1.5));
    if (MASCOT.pos.distanceTo(start) < size * 0.6 || reduced()) job.charging = true;
    return {want: start, face: FACEAT.copy(AT), fast: 1};
  }
  if (MASCOT.pos.distanceTo(AT) <= reach * 1.15 || reduced()) {
    shove(node, dir, job.strength ?? 0.5, size);
    MASCOT.hello = MASCOT.clock;  // a little hop as it lands the shove
    MASCOT.job = job.agent ? {kind: 'move', point: MASCOT.pos.clone(), agent: true} : null;
    return {want: SPOT.copy(MASCOT.pos), face: FACEAT.copy(AT)};
  }
  return {want: SPOT.copy(AT), face: FACEAT.copy(AT), fast: 1.8};
}
/* A carry: to the node first, then it takes hold and goes beside another node or to a point; the node rides along,
 * pinned where it carries it, and the map follows through its joins. The node is at `AT`. */
function dragJob(job, node, data, size) {
  if (MASCOT.holding !== node) {
    const grip = besideNode(node, size, SPOT);
    if (MASCOT.pos.distanceTo(grip) > size * 0.7 && !reduced()) return {want: grip, face: FACEAT.copy(AT)};
    dropHeld();
    MASCOT.holding = node;
    job.offset = new THREE.Vector3().subVectors(AT, MASCOT.pos);
    G.d3VelocityDecay(DRAG_FRICTION);
  }
  const beside = job.beside ? nodeById(data, job.beside) : null;
  let to = null;
  if (beside && beside.x !== undefined) {
    const there = new THREE.Vector3(beside.x, beside.y, beside.z);
    to = there.clone().addScaledVector(TOWARD.subVectors(AT, there).normalize(), ballOf(beside) + ballOf(node) + size);
  } else if (job.point) to = new THREE.Vector3(...job.point);
  const want = to ? SPOT.copy(to).sub(job.offset) : SPOT.copy(MASCOT.pos);
  if (reduced()) MASCOT.pos.copy(want);
  const at = AT.copy(MASCOT.pos).add(job.offset);
  Object.assign(node, {fx: at.x, fy: at.y, fz: at.z});
  G.d3ReheatSimulation();
  return {want, face: null, fast: 0.8};
}
/* The mascot's body, made the first time it is drawn, beside the map's primary node; never in the way of a click. */
function makeMascot(glyph, home, size) {
  const mesh = createAgent(glyph);
  mesh.traverse(object => { object.raycast = () => {}; });
  mesh.userData.motion = MASCOT.motion = motionOf(glyph, 'mascot');
  G.scene().add(mesh);
  Object.assign(MASCOT, {glyph, mesh, clock: 0, greeted: null, wander: null, fade: undefined});
  besideNode(home, size, MASCOT.pos);
  MASCOT.vel.set(0, 0, 0);
}
const given = (value, fallback) => value === undefined ? fallback : value;
export function mascot3d(data, size, passed) {
  const {glyph, leaving} = mascotFigure();
  reserveGlyph(glyph);
  if (MASCOT.mesh && MASCOT.glyph !== glyph) {
    dropHeld();
    G.scene().remove(MASCOT.mesh);
    MASCOT.mesh = null; MASCOT.job = null;
  }
  const home = primaryOf(data);
  if (!glyph || !size || !home || home.x === undefined) return;
  if (!MASCOT.mesh && leaving) return;  // a conversation that ended before its body was drawn: nothing to walk home
  if (!MASCOT.mesh) makeMascot(glyph, home, size);
  const m = MASCOT.motion, mesh = MASCOT.mesh, now = performance.now();
  m.temper = {calm: 0.1, playful: 0.6, chaotic: 0.95}[mischief()] ?? 0.6;  // its own temper, web_mascot_mischief
  MASCOT.clock += passed;
  // as large as an agent with the whole map in view, and never more than MASCOT.most pixels tall close up
  const camera = G.camera(), far = Math.max(1, camera.position.distanceTo(MASCOT.pos));
  const perPixel = 2 * far * Math.tan((camera.fov || 50) * Math.PI / 360)
    / Math.max(1, G.renderer().domElement.clientHeight);
  mesh.scale.setScalar(Math.min(size * 0.95, MASCOT.most * perPixel / 1.6));
  const driven = !leaving && mascotDriven();
  MASCOT.sleeping = !leaving && !driven && now - FRAMES.active > FRAMES.idle + 2500 && !MASCOT.call && !CUT.job
    && !MASCOT.job;
  if (MASCOT.call && now > MASCOT.call.until) MASCOT.call = null;
  const job = !leaving && MASCOT.job && (driven || !MASCOT.job.agent) ? mascotJob(data, size) : null;
  if (MASCOT.job?.agent && !driven) { dropHeld(); MASCOT.job = null; }  // let go: what the agent had it do ends
  const mending = leaving || driven || job ? null : mascotForCut(size);  // an edge the person cut, `CUT`
  const aim = mascotAim(data, size, passed, {leaving, driven, job, mending, home, now});
  if (reduced()) {  // it just stands there, facing what it is asked to at once
    if (aim.want) MASCOT.pos.copy(aim.want);
    mesh.position.copy(MASCOT.pos);
    if (aim.face) orientAgent(mesh, AHEAD.subVectors(aim.face, MASCOT.pos), 1);
    mesh.userData.update(0, {move: {speed: 0, stride: 0, state: 'idle'}});
    return;
  }
  // a pointer that chases it: it hops aside
  if (MASCOT.dodge && MASCOT.clock < MASCOT.dodge.until && aim.want) {
    aim.want = SPOT.copy(aim.want).add(MASCOT.dodge.by);
  }
  const top = ROAM.speed * m.speed * 0.9 * aim.fast * strokeOf(m, MASCOT.stride).pace;
  const accel = ROAM.accel * m.accel * aim.fast;
  if (aim.state !== 'sleep' && aim.want) steer(MASCOT, aim.want, passed, top, accel);
  else MASCOT.vel.multiplyScalar(Math.exp(-passed * 4));
  mesh.position.copy(MASCOT.pos);
  const speed = MASCOT.vel.length();
  MASCOT.stride += speed * passed / size;
  bounce(aim, speed, size, passed);
  gestures(aim, data, passed, now);
  brushPast(data, speed, size);
  faceMascot(mesh, aim, speed, size, passed);
  if (aim.puff !== 1) mesh.scale.multiplyScalar(aim.puff);
  markTrail(MASCOT, size);
  mesh.userData.update(passed, {move: {speed: Math.min(1, speed / Math.max(1, top)), stride: MASCOT.stride,
    state: aim.state}});
}
/* Where it goes and how this frame: walking home as its conversation ends, a job, where its agent sent it, mending
 * a cut edge, calling the person's attention, asleep while the page rests, greeting an agent the person chats with,
 * a wander of its own, beside the selection, or home. */
function mascotAim(data, size, passed, {leaving, driven, job, mending, home, now}) {
  const aim = {want: null, face: null, state: 'idle', fast: 1, spin: 0, puff: 1};
  const m = MASCOT.motion;
  const chatting = !$('#helpdesk')?.hidden && DOCK.target ? ROAM.figures.get(DOCK.target) : null;
  const selected = S.selected ? nodeById(data, S.selected) : null;
  if (leaving) {  // its conversation has ended: it walks home and goes
    aim.want = besideNode(home, size, SPOT);
    // home, it shrinks away on the leaving curve and is gone
    if (MASCOT.pos.distanceTo(aim.want) < size * 0.6) MASCOT.fade = Math.max(0, (MASCOT.fade ?? 1) - passed * 2.2);
    if (MASCOT.fade === 0) MASCOT_GONE.glyph = null;
    else if (MASCOT.fade !== undefined) aim.puff = Math.max(0.01, 1 - easeBoth(1 - MASCOT.fade));
  } else if (job) {
    Object.assign(aim, {want: given(job.want, null), face: given(job.face, null), fast: given(job.fast, 1)});
    if (MASCOT.job?.drive && aim.face) aim.state = 'attend';  // it holds its gaze where its agent has it face
  } else if (driven) {  // its system agent leads it: where it was sent, or it stays where it was taken
    const spot = MASCOT.call?.agent ? callSpot(data, size) : null;
    if (spot) Object.assign(aim, {want: spot.want, face: given(spot.face, null)});
    else aim.want = SPOT.copy(MASCOT.pos);
  } else if (mending) {
    Object.assign(aim, {want: given(mending.want, null), fast: given(mending.fast, 1), spin: given(mending.spin, 0),
      puff: given(mending.puff, 1)});
    if (mending.face) aim.face = mending.face;
    if (mending.stomp) { aim.state = 'cross'; MASCOT.stride += passed * m.stride * 2.2; }
  } else if (MASCOT.call?.node && !MASCOT.call.agent) {  // calling the person's attention, `ATTN`
    const spot = callSpot(data, size);
    if (spot) Object.assign(aim, {want: spot.want, face: given(spot.face, null)});
  } else if (now - FRAMES.active > FRAMES.idle) {
    aim.state = 'sleep';
  } else if (chatting && chatting.mesh) {
    greet(aim, chatting, size);
  } else if (mischief() !== 'calm' && mischiefDue(data, size, m, Boolean(selected))) {  // off on a wander of its own
    const node = MASCOT.wander?.id && nodeById(data, MASCOT.wander.id);
    aim.want = MASCOT.wander?.point ? SPOT.copy(MASCOT.wander.point)
      : besideNode(node && node.x !== undefined ? node : home, size, SPOT);
  } else if (selected && selected.x !== undefined) {
    aim.want = besideNode(selected, size, SPOT);
  } else aim.want = besideNode(home, size, SPOT);
  return aim;
}
/* To the agent the person chats with, beside it, and the two greet each other once it is near. */
function greet(aim, chatting, size) {
  aim.want = SPOT.copy(chatting.mesh.position).addScaledVector(ASIDE.setFromMatrixColumn(G.camera().matrixWorld, 0),
    size * 1.8);
  aim.face = chatting.mesh.position;
  if (MASCOT.greeted !== chatting.id && MASCOT.pos.distanceTo(aim.want) < size * 1.5) {
    MASCOT.greeted = chatting.id;
    MASCOT.hello = MASCOT.clock;
    chatting.glance = {other: 'mascot', until: chatting.clock + 1.6};
  }
}
/* Its step quickens in place: a hopper hops while it idles, a hop of hello, and it bobs while it talks. */
function bounce(aim, speed, size, passed) {
  const m = MASCOT.motion;
  if (m.go === 'hop' && speed < size * 0.3 && aim.state !== 'sleep' && Math.sin(MASCOT.clock * 0.5) > 0.4)
    MASCOT.stride += passed * m.stride * 0.8;
  if (MASCOT.hello && MASCOT.clock - MASCOT.hello < 1.2) MASCOT.stride += passed * m.stride * 1.5;
  if (MASCOT.speaking) {  // talking
    MASCOT.stride += passed * m.stride * 1.1;
    aim.puff = 1 + 0.04 * Math.sin(MASCOT.clock * 18);
  }
}
/* What its system agent asks of it, `mascotEvent`: a way to face, a turn and a gesture toward a part, a feeling
 * shown. An explicit turn wins over the viewpoint's own. */
function gestures(aim, data, passed, now) {
  const m = MASCOT.motion;
  if (MASCOT.facing && now < (MASCOT.driven || 0)) {
    const toward = MASCOT.facing.node ? nodeById(data, MASCOT.facing.node) : null;
    if (toward && toward.x !== undefined) aim.face = AT.set(toward.x, toward.y, toward.z);
    else if (MASCOT.facing.dir) aim.face = AT.copy(MASCOT.pos).add(MASCOT.facing.dir);
  }
  const pointed = MASCOT.point && MASCOT.clock - MASCOT.point.at < MASCOT.point.long;
  const pointing = pointed ? nodeById(data, MASCOT.point.node) : null;
  if (pointing && pointing.x !== undefined) {
    aim.face = AT.set(pointing.x, pointing.y, pointing.z);
    MASCOT.stride += passed * m.stride * 0.6;
  }
  const feeling = MASCOT.emote && MASCOT.clock - MASCOT.emote.at < MASCOT.emote.long ? MASCOT.emote : null;
  if (!feeling) return;
  const u = (MASCOT.clock - feeling.at) / feeling.long;
  if (feeling.kind === 'wave') {
    aim.spin = Math.sin(u * Math.PI * 6) * 0.35;
    MASCOT.stride += passed * m.stride * 0.8;
  } else if (feeling.kind === 'celebrate') {
    aim.spin = easeBoth(u) * Math.PI * 2;
    MASCOT.stride += passed * m.stride * 2;
    aim.puff = 1 + 0.12 * Math.sin(Math.PI * u);
  } else if (feeling.kind === 'shrug') aim.puff = 1 + 0.06 * Math.sin(Math.PI * u);
  else if (feeling.kind === 'think') {
    aim.spin = Math.sin(u * Math.PI) * 0.5;
    aim.face = aim.face || G.camera().position;
  } else if (feeling.kind === 'sleep') aim.state = 'sleep';
}
/* Light mischief: a node it passes at speed sways. */
function brushPast(data, speed, size) {
  if (mischief() === 'calm' || speed <= size || MASCOT.clock <= MASCOT.nudged) return;
  const brush = data.nodes.find(node => node.t === 'el' && node.x !== undefined
    && MASCOT.pos.distanceTo(AT.set(node.x, node.y, node.z)) < ballOf(node) + size * 0.8);
  if (brush) { nudgeNode(brush, 0.06); MASCOT.nudged = MASCOT.clock + (mischief() === 'chaotic' ? 3 : 8); }
}
/* Which way it faces: what it looks at, or the way it goes; at rest it half turns to the person; a spin turns it. */
function faceMascot(mesh, aim, speed, size, passed) {
  if (speed > 1e-2) MASCOT.heading.lerp(AHEAD.copy(MASCOT.vel).normalize(), 0.25);
  AHEAD.copy(aim.face ? TOWARD.subVectors(aim.face, MASCOT.pos) : MASCOT.heading);
  if (!aim.face && speed < size * 0.2 && aim.state !== 'sleep' && !EYE.view && !EYE.saved)
    AHEAD.lerp(TOWARD.subVectors(G.camera().position, MASCOT.pos).normalize(), 0.5);
  if (aim.spin) AHEAD.applyAxisAngle(THREE.Object3D.DEFAULT_UP, aim.spin);
  orientAgent(mesh, AHEAD, aim.spin ? 0.6 : 0.15, passed);
}
/* The pointer over the 3D map: where it is and how fast it moves, so the mascot can dodge one that chases it. */
function dodgePointer(event) {
  const pointer = MASCOT.pointer, now = performance.now(), passed = Math.max(1, now - pointer.at);
  pointer.speed = Math.hypot(event.clientX - pointer.x, event.clientY - pointer.y) / passed;
  Object.assign(pointer, {x: event.clientX, y: event.clientY, at: now});
  if (!MASCOT.mesh || !G || mischief() === 'calm' || pointer.speed < 0.8) return;
  const area = G.renderer().domElement.getBoundingClientRect();
  const at = SPOT.copy(MASCOT.mesh.position).project(G.camera());
  const x = area.left + (at.x + 1) / 2 * area.width, y = area.top + (1 - at.y) / 2 * area.height;
  if (Math.hypot(x - event.clientX, y - event.clientY) > 60) return;
  if (MASCOT.dodge && MASCOT.clock < MASCOT.dodge.until) return;
  ASIDE.setFromMatrixColumn(G.camera().matrixWorld, 0);
  const away = (x < event.clientX ? -1 : 1) * ROAM.drawn * 2.5;
  MASCOT.dodge = {until: MASCOT.clock + 1.4, by: ASIDE.clone().multiplyScalar(away)};
  MASCOT.stride += MASCOT.motion.stride * 0.5;
  wake3d();
}
$('#stage').addEventListener('pointermove', dodgePointer, {passive: true});
