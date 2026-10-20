/* How a 3D figure moves: the places its way passes, its walk and orbit, its moods and acts on a node, the nodes it
 * nudges, its trail and the dock's point in the scene. */
import '/page/app/figures/agents.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
import {strokeOf} from '/page/agents3d.js';
import {$, reduced} from '/page/app/core/dom.js';
import {ROAM, nodeById} from '/page/app/figures/agents.js';
import {ROAM2D} from '/page/app/figures/roam2d.js';
import {G} from '/page/app/map3d/graph3d.js';
import {AT} from '/page/app/map3d/labels.js';
import {FLOW} from '/page/app/flow/flow.js';
import {fxDot} from '/page/app/flow/fx3d.js';
import {D} from '/page/app/agents/dispatch.js';
import {WS} from '/page/app/workspace/workspace.js';

/* The places a figure's way passes: each node a little above its center, or the point where the figure left its
 * orbit. Read again each frame, so a figure on its way moves with the map as the layout moves it. False while a node
 * of the way is not drawn. */
export function placed(figure, data, lift) {
  const points = figure.points;
  points.length = figure.way.length;
  for (let k = 0; k < figure.way.length; k++) {
    const step = figure.way[k];
    points[k] = points[k] || new THREE.Vector3();
    if (step.point) { points[k].copy(step.point); continue; }
    const node = nodeById(data, step.id);
    if (!node || node.x === undefined) return false;
    points[k].set(node.x, node.y + lift, node.z);
  }
  figure.curve.points = points;
  return points.length >= 2;
}
/* A figure walks its way as one smooth curve through its places. It sets off from rest, speeding up by ROAM.accel to
 * ROAM.speed, takes each turn slower the sharper it is, and slows to rest as it arrives, so it never starts, stops or
 * turns at once. Its place on the way is its leg and how far along that leg it is, so it keeps to the edge it is on
 * while the layout moves the nodes. Says whether it has arrived. */
const HEAD = new THREE.Vector3(), NEXT = new THREE.Vector3();
// How each way of taking a corner slows a figure into it, and how quickly it turns to face its way, `MOTION`
export const CORNERS = {bank: {slow: 0.35, turn: 0.16}, pivot: {slow: 0.9, turn: 0.45},
  drift: {slow: 0.25, turn: 0.08}, flit: {slow: 0.5, turn: 0.3}, bend: {slow: 0.45, turn: 0.14},
  hop: {slow: 0.6, turn: 0.35}};
export function walk(figure, passed, size = ROAM.size) {
  const points = figure.points, legs = points.length - 1, motion = figure.motion;
  const top = ROAM.speed * (motion?.speed ?? 1);
  const lengths = legLengths(points);
  const accel = ROAM.accel * (motion?.accel ?? 1), corner = CORNERS[motion?.corner]?.slow ?? ROAM.corner;
  const turnAt = k => HEAD.subVectors(points[k], points[k - 1]).normalize()
    .dot(NEXT.subVectors(points[k + 1], points[k]).normalize());
  let speed = wayspeed(figure.u, lengths, {top, accel, corner}, turnAt);
  // a swimmer surges on each push and glides between, a hopper covers ground in the air, `strokeOf`
  if (motion) speed *= strokeOf(motion, figure.stride || 0).pace;
  figure.top = top;
  figure.stride = (figure.stride || 0) + speed * passed / size;
  goOn(figure, speed * passed, lengths);
  figure.speed = speed;
  return figure.u >= legs - 1e-6;
}
/* The length of each leg of a way, never quite zero. */
function legLengths(points) {
  const lengths = [];
  for (let k = 0; k < points.length - 1; k++) lengths.push(Math.max(1e-3, points[k].distanceTo(points[k + 1])));
  return lengths;
}
/* How fast a figure may go at `u` on its way, its leg and how far along it: up to `top`, slower near either end and
 * into each sharp turn, as fast as it could have sped up from rest or still slow down in time at `accel`. `turnAt(k)`
 * is how straight the way goes on at its kth place, 1 straight on and -1 straight back; `corner` is how much of its
 * speed a turn straight back takes off. Shared by the figures of both maps. */
export function wayspeed(u, lengths, {top, accel, corner}, turnAt) {
  const legs = lengths.length;
  const total = lengths.reduce((sum, length) => sum + length, 0);
  const leg = Math.min(legs - 1, Math.floor(u));
  let done = (u - leg) * lengths[leg];
  for (let k = 0; k < leg; k++) done += lengths[k];
  const least = top * 0.12, reach = (limit, away) => Math.sqrt(limit * limit + 2 * accel * Math.max(0, away));
  let speed = Math.min(top, reach(least, done), reach(least, total - done));
  for (let k = 1, at = lengths[0]; k < legs; at += lengths[k], k++) {
    speed = Math.min(speed, reach(top * (1 - corner * (1 - turnAt(k)) / 2), Math.abs(at - done)));
  }
  return speed;
}
/* A figure goes `step` further along its way, leg by leg, its place kept as its leg and how far along it. */
export function goOn(figure, step, lengths) {
  const legs = lengths.length;
  while (step > 0 && figure.u < legs) {
    const now = Math.min(legs - 1, Math.floor(figure.u)), room = (now + 1 - figure.u) * lengths[now];
    if (step < room) { figure.u += step / lengths[now]; step = 0; } else { step -= room; figure.u = now + 1; }
  }
}
/* The point a figure circles its node from, measured from the node, and its first turn on the orbit: the side of the
 * node that lets it carry straight on the way it came, so it swings out onto its orbit with no turn back. */
function onOrbit(figure, target) {
  figure.from.copy(figure.mesh.position).sub(AT.set(target.x, target.y, target.z));
  const across = Math.hypot(figure.heading.x, figure.heading.z);
  if (across > 1e-3) figure.angle = Math.atan2(-figure.heading.x / across, figure.heading.z / across);
}
export const AHEAD = new THREE.Vector3(), ORBIT = new THREE.Vector3(), WANT = new THREE.Vector3();
export const PULL = new THREE.Vector3();
export const TOWARD = new THREE.Vector3(), SPOT = new THREE.Vector3();
export const easeBoth = k => k * k * (3 - 2 * k);  // from rest to rest
/* How each figure behaves on its node, VIEW-035, in its character's way, `MOTION` in agents3d.js. Where it means to
 * be is worked out each frame and it follows that place on a critically damped spring, `springTo`, so every move eases
 * in and out and any of them can be turned aside at once; how stiffly it follows is its character's, `STIFF`: a comet
 * snaps, a wisp drifts. What it does there comes from its session, `moodOf`:
 *  - working: it stays beside its node facing the label, and every so often does something with the node in its
 *    own way, its `act`: perches on top, pokes it, nudges it so the node sways, peeks in close;
 *  - a tool call, told by the event stream, `figureReached`: a quick, purposeful move toward the part touched, a lean
 *    and a reach, and back; on its own node, a poke;
 *  - waiting for the person: it settles beside the node and turns toward the chat dock, idling patiently;
 *  - a spinning or stuck signal: restless, uneven circling, kept calm;
 *  - done: a small flourish of its own before it walks home.
 * Two figures on one node take lanes apart, notice each other with a glance and a pause, and make room. Figures leave
 * a faint trail on the way, footprints, ripples or hop marks, that fades within seconds, `MARKS`. */
export const STIFF = {dart: 40, roll: 30, walk: 26, hover: 24, flutter: 30, flap: 20, glide: 14, float: 10, pulse: 12,
  swim: 14, creep: 18, hop: 22};
export const RESTLESS = ['spinning-calls', 'repeated-failure'];
export const ACTS = {perch: 4.5, peek: 3, poke: 1.6, nudge: 2.2, circle: 0};  // how long each act lasts, in seconds
// The wait before a figure's next act with its node, by its temper: a serious one keeps to its task and plays now and
// then, about every 25 seconds; a mischievous one about every 6.
export const actGap = (motion, clock) =>
  (6 + 20 * (1 - (motion.temper ?? 0.5))) * (0.6 + 0.8 * ((motion.phase * 7.13 + clock * 0.37) % 1));
export function moodOf(workId) {
  const child = ROAM.figures.get(workId)?.child;  // a subagent waits while its state asks for the person's input
  if (child) return /input|wait/i.test(String(child.state)) ? 'waiting' : 'working';
  const session = D.sessions.filter(one => one.work_id === workId && one.state === 'running').at(-1);
  if (!session) return 'working';
  if ((D.signals || []).some(one => one.session_id === session.session_id && one.active !== false
    && RESTLESS.includes(one.signal))) return 'restless';
  return session.activity === 'waiting' ? 'waiting' : 'working';
}
// the person chose a character for an agent's type, web_agent_glyphs: entries such as claude=owl
export function typeGlyph(workId) {
  return glyphOfType(String(D.sessions.filter(one => one.work_id === workId).at(-1)?.agent || ''));
}
/* The character the person chose for an agent's type, such as claude, or null; a roundtable's seats take it too. */
export function glyphOfType(agent) {
  if (!agent) return null;
  for (const entry of (WS.view().agent_glyphs || []).flatMap(one => String(one).split(/[,\s]+/))) {
    const [type, glyph] = String(entry).split('=').map(part => part.trim());
    if (type && glyph && (agent === type || agent.startsWith(type + '-'))) return glyph;
  }
  return null;
}
/* A tool call of a running agent reached these nodes, `flowEvent`: its figure reaches toward the first. */
export function figureReached(workId, to) {
  const figure = ROAM.figures.get(workId), figure2d = ROAM2D.figures.get(workId);
  if (figure && to) figure.reach = {to, at: figure.clock};
  if (figure2d && to) figure2d.reach = {to, at: figure2d.clock};
}
/* Toward a place, as fast as it can still stop there gently: `body` has pos and vel. Says how far it was. The mascot
 * and a figure its agent leads steer so. */
export function steer(body, want, passed, top, accel) {
  TOWARD.subVectors(want, body.pos);
  const away = TOWARD.length(), speed = Math.min(top, Math.sqrt(2 * accel * Math.max(0, away - 0.05)));
  TOWARD.multiplyScalar(away > 1e-4 ? speed / away : 0);
  PULL.subVectors(TOWARD, body.vel);
  const most = accel * passed * 1.5;
  if (PULL.length() > most) PULL.setLength(most);
  body.vel.add(PULL);
  body.pos.addScaledVector(body.vel, passed);
  return away;
}
/* How much faster than its own pace a body its agent sends `away` goes, at least 1: enough that a long way still
 * ends in about three seconds, setting off and arriving gently. */
export const drivePace = (top, away) => Math.max(1, away / 2 / Math.max(1e-3, top));
/* The way a body faces, flat on the ground plane, into `out`. */
export function facingOf(mesh, out) {
  mesh.getWorldDirection(out).setY(0);
  return out.lengthSq() > 1e-8 ? out.normalize() : out.set(0, 0, 1);
}
/* Where an agent sent its body, its `drive`, VIEW-005: beside a node at the offset fixed when it was sent, so it
 * follows the node as the layout moves it and never the person's camera, or a point of the scene; into `out`. Null
 * once the node has left the map. */
export function driveGoal(drive, data, out) {
  if (!drive.node) return drive.point ? out.copy(drive.point) : null;
  const node = nodeById(data, drive.node);
  return node && node.x !== undefined ? out.set(node.x, node.y, node.z).add(drive.offset) : null;
}
/* The point a driven body faces, into `out`: the node it was asked to face, or a way from where it stands `at`; null
 * when it faces the way it goes. */
export function driveFace(drive, at, data, out) {
  const face = drive.face;
  if (face?.node) {
    const node = nodeById(data, face.node);
    return node && node.x !== undefined ? out.set(node.x, node.y, node.z) : null;
  }
  return face?.dir ? out.copy(at).add(face.dir) : null;
}
export function springTo(figure, want, passed, stiff) {  // a critically damped spring toward where it means to be
  const damp = 2 * Math.sqrt(stiff);
  PULL.subVectors(want, figure.pos).multiplyScalar(stiff).addScaledVector(figure.vel, -damp);
  figure.vel.addScaledVector(PULL, passed);
  figure.pos.addScaledVector(figure.vel, passed);
}
/* A node a figure pokes or nudges sways a little and settles; only the drawn object turns, the layout is untouched. */
const SWAYS = new Map();
export function nudgeNode(node, k) {
  const object = node?.__threeObj;
  if (!object || reduced()) return;
  const held = SWAYS.get(node.id);
  const base = held?.base || {x: object.rotation.x, z: object.rotation.z};
  SWAYS.set(node.id, {node, k, at: performance.now() / 1000, base});
}
export function sway3d() {
  const now = performance.now() / 1000;
  for (const [id, one] of SWAYS) {
    const object = one.node.__threeObj, t = now - one.at;
    if (!object) { SWAYS.delete(id); continue; }
    if (t > 2.6) {
      object.rotation.x = one.base.x; object.rotation.z = one.base.z;
      SWAYS.delete(id);
      continue;
    }
    const swing = one.k * Math.exp(-t * 2.2) * Math.sin(t * 9);
    object.rotation.z = one.base.z + swing;
    object.rotation.x = one.base.x + swing * 0.4;
  }
}
/* The trail a figure leaves: a mark where each step, push or hop lands, faint and gone within seconds, drawn with the
 * flow, `fxMarks`. Fliers leave none. */
const MARKS = [];
const TRAILS = {walk: 'step', creep: 'step', roll: 'step', swim: 'ripple', pulse: 'ripple', hop: 'hop'};
export function markTrail(figure, size) {
  const m = figure.motion, steps = Math.floor((figure.stride || 0) / Math.max(0.05, m.stride));
  if (steps === figure.steps) return;
  figure.steps = steps;
  const kind = TRAILS[m.go] || null;
  if (!kind) return;
  const p = figure.mesh.position, side = steps % 2 ? 1 : -1;
  const aside = kind === 'step' ? side * size * 0.18 : 0;  // footprints fall left and right of the way
  AHEAD.set(-figure.heading.z, 0, figure.heading.x).normalize().multiplyScalar(aside);
  MARKS.push({x: p.x + AHEAD.x, y: p.y - size * 0.55, z: p.z + AHEAD.z, kind, size, at: FLOW.clock});
  if (MARKS.length > 90) MARKS.shift();
}
export function fxMarks(color) {
  while (MARKS.length && FLOW.clock - MARKS[0].at > 2.6) MARKS.shift();
  for (const one of MARKS) {
    const u = (FLOW.clock - one.at) / 2.6, fade = Math.pow(1 - u, 2) * 0.4;
    if (one.kind === 'step') fxDot(one, one.size * 0.22, color, fade, 0, 2, 5);
    else fxDot(one, one.size * (one.kind === 'hop' ? 0.5 + 0.4 * u : 0.4 + 1.1 * u), color, fade, 2, 4, 40);
  }
}
/* Where the chat dock is, as a point in the scene at the depth of `near`, so a figure waiting on the person faces
 * it. */
const DOCKAT = new THREE.Vector3();
export function dockPoint(near) {
  const area = G.renderer().domElement.getBoundingClientRect(), dock = $('#helpdesk');
  const box = dock && !dock.hidden ? dock.getBoundingClientRect() : null;
  const x = box && box.width ? box.left + box.width / 2 : area.right - 40;
  const y = box && box.height ? box.top + box.height / 2 : area.bottom - 20;
  DOCKAT.set(near.x, near.y, near.z).project(G.camera());
  DOCKAT.x = (x - area.left) / area.width * 2 - 1;
  DOCKAT.y = -(y - area.top) / area.height * 2 + 1;
  return DOCKAT.unproject(G.camera());
}
