/* Each frame of the 3D figures: where a figure means to be on its node, its flourish when its work is done, how it
 * comes and goes, and roam3d, which steps every figure through its stages. */
import '/page/app/figures/walk.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
import {releaseGlyph, orientAgent} from '/page/agents3d.js';
import {reduced} from '/page/app/core/dom.js';
import {ROAM, nodeById, ballOf, sizeOf, routeOf, retarget, reglyph} from '/page/app/figures/agents.js';
import {placed, CORNERS, walk, AHEAD, TOWARD, easeBoth, STIFF, ACTS, actGap, moodOf, springTo, nudgeNode, sway3d,
  markTrail, dockPoint, WANT, SPOT} from '/page/app/figures/walk.js';
import {MASCOT, mascotGlyph, mascot3d, mascotDriven} from '/page/app/figures/mascot.js';
import {placeBubble, CUT, cut3d} from '/page/app/figures/cut.js';
import {eyes3d, approachPoint} from '/page/app/figures/eyes.js';
import {G} from '/page/app/map3d/graph3d.js';
import {AT} from '/page/app/map3d/labels.js';

/* Where a figure means to be on its node this frame, `WANT`, and what it looks at, if anything but the way it goes:
 * its orbit, or beside the node while it waits, then what it does with the node, a tool call's reach, something it
 * was asked to look at, and a glance at a figure nearby, each later one turning its face over the one before. */
function onNode(figure, target, size, data) {
  const m = figure.motion, ball = ballOf(target), c = figure.clock;
  orbitPlace(figure, target, size, ball);
  let face = figure.mood === 'waiting' ? waitBeside(figure, target, size, ball) : null;
  // now and then while it works, something of its own with the node
  if (figure.mood === 'working' && !figure.act && c > figure.nextAct && ACTS[m.act])
    figure.act = {kind: m.act, at: c, long: ACTS[m.act], hit: false};
  if (figure.act) face = actWith(figure, target, size, ball) ?? face;
  if (figure.reach) face = reachFor(figure, target, size, ball, data) ?? face;
  if (figure.lookAt && c < figure.lookAt.until) face = lookedAt(figure, data) ?? face;  // asked to look, `sight`
  if (figure.glance && c < figure.glance.until) face = glancedAt(figure) ?? face;
  if (figure.come && c < figure.come.until && approachPoint(figure.come, size, SPOT)) {  // to the person, web_come
    WANT.copy(SPOT);
    face = AT.copy(G.camera().position);
  }
  return face;
}
/* The figure's place on its orbit: the angle always grows at its lap's pace, and which way round it goes is its
 * character's, `dir`; restless, it circles unevenly, never frantic; glancing, it nearly stops; waiting, it stays. */
function orbitPlace(figure, target, size, ball) {
  const m = figure.motion, c = figure.clock;
  let rate = 2 * Math.PI / m.lap, reach = ball + size * (m.orbit + figure.lane * 0.8);
  if (figure.mood === 'restless') {
    rate *= 1 + 0.55 * Math.sin(c * 1.7) * Math.sin(c * 0.63 + 1);
    reach *= 1 + 0.12 * Math.sin(c * 1.1);
  }
  if (figure.glance && c < figure.glance.until) rate *= 0.15;
  if (figure.mood === 'waiting') rate = 0;
  figure.angle += rate * figure.passed;
  const turn = m.dir * figure.angle + figure.lane * Math.PI;
  WANT.set(target.x + Math.cos(turn) * reach, target.y + Math.sin(turn * 2) * reach * 0.18 + size * 0.3,
    target.z + Math.sin(turn) * reach);
}
/* Waiting on the person: beside its node, toward the chat dock, patient; it faces the dock. */
function waitBeside(figure, target, size, ball) {
  const dock = dockPoint(target);
  TOWARD.subVectors(dock, AT.set(target.x, target.y, target.z)).normalize();
  WANT.set(target.x, target.y + size * 0.2, target.z).addScaledVector(TOWARD, ball + size * (1.1 + figure.lane * 0.8));
  return SPOT.copy(dock);
}
/* The act under way with the node: perched on top looking about, peeking in close, or a poke or a nudge that makes the
 * node sway; once over, the next is due after its temper's wait. What it faces, or null where the act names none. */
function actWith(figure, target, size, ball) {
  const act = figure.act, c = figure.clock, u = (c - act.at) / act.long;
  if (u >= 1 || figure.mood !== 'working') {
    figure.act = null;
    figure.nextAct = c + actGap(figure.motion, c);
    return null;
  }
  const k = Math.sin(Math.PI * u), center = AT.set(target.x, target.y, target.z);
  TOWARD.subVectors(WANT, center).normalize();
  if (act.kind === 'perch') {  // it settles on top and looks about
    WANT.lerp(SPOT.set(target.x, target.y + ball + size * 0.42, target.z), easeBoth(Math.min(1, k * 1.6)));
    return null;
  }
  if (act.kind === 'peek') {  // in close at its side, looking in
    WANT.lerp(SPOT.copy(center).addScaledVector(TOWARD, ball + size * 0.6), easeBoth(Math.min(1, k * 1.5)));
    return AT.set(target.x, target.y, target.z);
  }
  // a poke darts in to touch it; a nudge leans in and pushes, and the node sways
  WANT.lerp(SPOT.copy(center).addScaledVector(TOWARD, ball + size * 0.35), k * k);
  const face = AT.set(target.x, target.y, target.z);
  if (!act.hit && u > 0.45) { act.hit = true; nudgeNode(target, act.kind === 'nudge' ? 0.14 : 0.07); }
  return face;
}
/* A tool call: a quick, purposeful reach toward what it touched, and back; on its own node, a poke. */
function reachFor(figure, target, size, ball, data) {
  const u = (figure.clock - figure.reach.at) / 1.3, to = nodeById(data, figure.reach.to);
  if (u >= 1 || !to || to.x === undefined) { figure.reach = null; return null; }
  const k = Math.sin(Math.PI * Math.min(1, u)) ** 2;
  if (to === target) {
    TOWARD.subVectors(WANT, AT.set(target.x, target.y, target.z)).normalize();
    WANT.lerp(SPOT.set(target.x, target.y, target.z).addScaledVector(TOWARD, ball + size * 0.4), k);
    if (u > 0.45 && !figure.reach.hit) { figure.reach.hit = true; nudgeNode(target, 0.05); }
  } else WANT.lerp(SPOT.set(to.x, to.y, to.z), 0.32 * k);
  return AT.set(to.x, to.y, to.z);
}
function lookedAt(figure, data) {
  const toward = nodeById(data, figure.lookAt.node);
  return toward && toward.x !== undefined ? AT.set(toward.x, toward.y, toward.z) : null;
}
/* What a glance turns it to: another figure, the mascot, or the loose end of a cut join. */
function glancedAt(figure) {
  const other = figure.glance.other, job = CUT.job, loose = job?.loose && job.bodies.get(job.loose);
  const seen = ROAM.figures.get(other)?.mesh.position || (other === 'mascot' ? MASCOT.mesh?.position
    : other === 'cut' && loose ? AT.set(loose.x, loose.y, loose.z) : null);
  return seen ? AT.copy(seen) : null;
}
/* A figure's flourish when its work is done, before it walks home: where it is this moment, around where it stood. */
export const FLOURISH = 1.4;
function flourish(figure, size, u) {
  const kind = figure.motion.flourish, k = Math.sin(Math.PI * u), spin = easeBoth(u) * Math.PI * 2;
  WANT.copy(figure.from);
  let turn = 0, scale = 1;
  if (kind === 'spin' || kind === 'twirl') {
    turn = spin;
    if (kind === 'twirl') WANT.y += k * size * 0.8;
  } else if (kind === 'loop') {
    WANT.y += (1 - Math.cos(spin)) * size * 0.7;
    WANT.addScaledVector(figure.heading, Math.sin(spin) * size * 0.7);
  } else if (kind === 'hop' || kind === 'flap') {
    WANT.y += k * size * (kind === 'hop' ? 1.2 : 0.8);
    figure.stride += figure.passed * 3;
  } else if (kind === 'puff') scale = 1 + 0.3 * k;
  else if (kind === 'bow') turn = 0;
  return {turn, scale, bow: kind === 'bow' ? k * 0.6 : 0};
}
/* How a figure comes and goes, its character's `arrive`: where it is and how large, a share `k` of the way in. */
function arrival(figure, at, size, k, leaving) {
  const style = figure.motion.arrive, e = leaving ? 1 - easeBoth(1 - k) : easeBoth(k);
  WANT.copy(at);
  let scale = 1, tall = 1;
  if (style === 'drop') { WANT.y += (1 - e) * size * 5; scale = Math.min(1, k * 3); }
  else if (style === 'swoop') {
    WANT.y += (1 - e) * size * 4; WANT.x += (1 - e) * size * 3;
    scale = Math.min(1, k * 2);
  }
  else if (style === 'rise') { WANT.y -= (1 - e) * size * 3; scale = Math.min(1, k * 2.5); }
  else if (style === 'sprout') { tall = Math.max(0.001, e); WANT.y -= (1 - e) * size * 0.5; }
  else if (style === 'fade') scale = Math.max(0.001, e);
  else if (leaving) scale = Math.max(0.001, 1 - (1 - k) * (1 - k));
  else scale = Math.max(0.001, 1 + 1.7 * Math.pow(k - 1, 3) + 0.7 * Math.pow(k - 1, 2));  // a pop that overshoots
  return {scale, tall};
}
export function roam3d(data) {
  const now = performance.now() / 1000, passed = Math.min(0.1, Math.max(0, now - (ROAM.last || now)));
  ROAM.last = now;
  const size = drawnSize(data, now), lift = size * 0.6;
  sway3d();
  takeLanes(size);
  for (const [id, figure] of ROAM.figures) stepFigure(id, figure, data, size, lift, passed);
  // the mascot's approach to the person, web_come: where it goes this frame, and over once its time is up
  if (MASCOT.job?.come) {
    if (!mascotDriven()) MASCOT.job = null;
    else approachPoint(MASCOT.job.come, size, MASCOT.job.point);
  }
  cut3d(size, passed);
  mascot3d(data, size, passed);
  eyes3d(passed);  // the person watching through the mascot's eyes, `EYE`
  placeBubble();
}
/* The size figures are drawn at follows the map's span gently, so a layout still spreading never makes a figure jump
 * in size; with no figure and no mascot it is 0. */
function drawnSize(data, now) {
  const real = Math.min(1, Math.max(0, now - (ROAM.sized || now)));
  ROAM.sized = now;
  const follow = () => ROAM.drawn ? ROAM.drawn + (sizeOf(data) - ROAM.drawn) * (1 - Math.exp(-real * ROAM.grow))
    : sizeOf(data);
  ROAM.drawn = ROAM.figures.size || mascotGlyph() || MASCOT.mesh ? follow() : 0;
  return ROAM.drawn;
}
/* Figures on one node take lanes apart, and notice each other as they pass. */
function takeLanes(size) {
  const lanes = new Map();
  for (const figure of [...ROAM.figures.values()].sort((one, two) => one.id < two.id ? -1 : 1)) {
    if (figure.stage !== 'circling') continue;
    figure.lane = lanes.get(figure.target) || 0;
    lanes.set(figure.target, figure.lane + 1);
  }
  for (const one of ROAM.figures.values()) for (const two of ROAM.figures.values()) {
    if (one.id >= two.id || one.stage !== 'circling' || two.stage !== 'circling' || one.target !== two.target) continue;
    if (one.clock < one.nextGlance || one.mesh.position.distanceTo(two.mesh.position) > size * 3) continue;
    one.glance = {other: two.id, until: one.clock + 1.1}; two.glance = {other: one.id, until: two.clock + 1.1};
    one.nextGlance = one.clock + 9; two.nextGlance = two.clock + 9;
  }
}
/* Gone from the map, and no longer seen, so its agent walks on again as a new figure when its session works again. */
function gone(id, figure) {
  G.scene().remove(figure.mesh);
  releaseGlyph(id);
  ROAM.figures.delete(id);
  ROAM.seen.delete(id);
}
/* What each stage does in a frame; a stage that answers false has ended the figure's frame, nothing more is drawn. */
const STAGES = {arriving, going: travelling, returning: travelling, circling, flourish: finishing, leaving};
/* One figure's frame: its character checked again once a second, its stage, and then how it is drawn. */
function stepFigure(id, figure, data, size, lift, passed) {
  figure.checked = (figure.checked || 0) + passed;
  if (figure.checked > 1) { figure.checked = 0; reglyph(figure); retarget(figure, data); }
  const {mesh} = figure;
  figure.clock += passed;
  figure.passed = passed;
  const target = nodeById(data, figure.target), home = nodeById(data, figure.home);
  if (!target || target.x === undefined || !home || home.x === undefined) return;
  const grown = ROAM.focus === id ? ROAM.focused : 1;
  if (reduced()) {  // no walking: the figure stands on its node while the ticket is worked
    mesh.position.set(target.x, target.y + ballOf(target) + size, target.z);
    mesh.scale.setScalar(size * grown);
    if (figure.done) gone(id, figure);
    return;
  }
  figure.mood = moodOf(id);
  const pose = {state: 'travel', scale: 1, tall: 1, turn: 0, bow: 0, face: null};
  const on = STAGES[figure.stage]?.(figure, {id, data, target, home, size, lift, passed, pose});
  if (on === false) return;
  drawFigure(figure, size, grown, passed, pose);
}
/* It comes onto the most primary node in its own way. */
function arriving(figure, {home, size, lift, pose}) {
  const k = Math.min(1, figure.clock / ROAM.appear);
  ({scale: pose.scale, tall: pose.tall} = arrival(figure, AT.set(home.x, home.y + lift, home.z), size, k, false));
  figure.mesh.position.copy(WANT);
  if (k >= 1) Object.assign(figure, {stage: 'going', u: 0, clock: 0});
}
/* Along the map's own edges, to its node or home again. */
function travelling(figure, {data, target, size, lift, passed, pose}) {
  const mesh = figure.mesh, m = figure.motion, going = figure.stage === 'going';
  if (!placed(figure, data, lift)) {  // a node of its way left the map: it goes on to what comes next
    figure.pos.copy(mesh.position); figure.vel.set(0, 0, 0);
    figure.from.copy(mesh.position);
    Object.assign(figure, going ? {stage: figure.done ? 'flourish' : 'circling'} : {stage: 'leaving'}, {clock: 0});
    return false;
  }
  const arrived = walk(figure, passed, size), along = figure.u / (figure.points.length - 1);
  figure.curve.getPoint(along, mesh.position);
  figure.curve.getTangent(along, AHEAD);
  if (AHEAD.lengthSq() > 1e-8) figure.heading.copy(AHEAD);
  swerve(figure, size);
  mischief(figure, data, size);
  markTrail(figure, size);
  pose.face = noticeMascot(figure, size);
  if (arrived) {
    figure.pos.copy(mesh.position); figure.vel.copy(figure.heading).multiplyScalar(figure.speed * 0.5);
    figure.from.copy(mesh.position);
    // onto its orbit from where it arrived, so it swings straight out onto it
    figure.angle = m.dir * Math.atan2(mesh.position.z - target.z, mesh.position.x - target.x) - figure.lane * Math.PI;
    Object.assign(figure, {clock: 0, stage: !going ? 'leaving' : figure.done ? 'flourish' : 'circling'});
  }
}
/* Off its line as it goes: a moth jinks from side to side; a mischievous one takes a little detour. */
function swerve(figure, size) {
  const mesh = figure.mesh, m = figure.motion, pace = Math.min(1, figure.speed / figure.top);
  if (m.corner === 'flit') {
    TOWARD.set(-figure.heading.z, 0, figure.heading.x).normalize();
    mesh.position.addScaledVector(TOWARD, Math.sin(figure.stride * 5.3) * size * 0.25 * pace);
  }
  const temper = m.temper ?? 0.5;
  if (temper > 0.55 && m.corner !== 'flit') {
    TOWARD.set(-figure.heading.z, 0, figure.heading.x).normalize();
    mesh.position.addScaledVector(TOWARD, Math.sin(figure.stride * 0.9 + m.phase * 6) * size * 0.45 * (temper - 0.5)
      * pace);
  }
}
/* A mischievous one pokes a node it passes, and teases a figure it meets with a little hop at it. */
function mischief(figure, data, size) {
  const mesh = figure.mesh, m = figure.motion, temper = m.temper ?? 0.5;
  if (temper <= 0.6) return;
  if (figure.clock > (figure.poked || 0)) {
    const brush = data.nodes.find(node => node.t === 'el' && node.x !== undefined && node.id !== figure.target
      && mesh.position.distanceTo(AT.set(node.x, node.y, node.z)) < ballOf(node) + size * 0.7);
    if (brush) { nudgeNode(brush, 0.05 * temper); figure.poked = figure.clock + 12 - 6 * temper; }
  }
  if (figure.clock > (figure.teased || 0)) for (const other of ROAM.figures.values()) {
    if (other === figure || mesh.position.distanceTo(other.mesh.position) > size * 2.5) continue;
    figure.glance = {other: other.id, until: figure.clock + 0.8};
    figure.stride += m.stride * 0.6;
    figure.teased = figure.clock + 15;
    break;
  }
}
/* An agent passing the mascot notices it, and faces it while it glances. */
function noticeMascot(figure, size) {
  const near = MASCOT.mesh && figure.mesh.position.distanceTo(MASCOT.mesh.position) < size * 4;
  if (near && figure.clock > (figure.noticed || 0)) {
    figure.noticed = figure.clock + 12;
    figure.glance = {other: 'mascot', until: figure.clock + 0.9};
  }
  if (figure.glance?.other === 'mascot' && figure.clock < figure.glance.until && MASCOT.mesh)
    return AT.copy(MASCOT.mesh.position);
  return null;
}
/* On its node, in its own way, `onNode`, following where it means to be on its spring. */
function circling(figure, {data, target, size, passed, pose}) {
  const mesh = figure.mesh, m = figure.motion;
  pose.face = onNode(figure, target, size, data);
  springTo(figure, WANT, passed, STIFF[m.go] || 20);
  mesh.position.copy(figure.pos);
  pose.state = figure.mood === 'waiting' ? 'wait' : figure.mood;
  if (figure.vel.lengthSq() > 1e-4) figure.heading.lerp(AHEAD.copy(figure.vel).normalize(), 0.2);
  figure.stride += figure.vel.length() * passed / size;
  // a hopper hops in place now and then while it idles
  if (m.go === 'hop' && figure.vel.length() < size * 0.3 && Math.sin(figure.clock * 0.6 + m.phase * 6) > 0.2)
    figure.stride += passed * m.stride * 0.8;
  markTrail(figure, size);
  if (figure.done) { figure.from.copy(mesh.position); Object.assign(figure, {stage: 'flourish', clock: 0}); }
}
/* Done: a little flourish of its own, then home. */
function finishing(figure, {data, size, passed, pose}) {
  const mesh = figure.mesh, u = Math.min(1, figure.clock / FLOURISH);
  ({turn: pose.turn, scale: pose.scale, bow: pose.bow} = flourish(figure, size, u));
  springTo(figure, WANT, passed, 40);
  mesh.position.copy(figure.pos);
  pose.state = 'flourish';
  if (u < 1) return;
  const back = routeOf(data, figure.target, figure.home);
  const way = (back.length > 1 ? back.slice(1) : [figure.home]).map(one => ({id: one}));
  Object.assign(figure, {stage: 'returning', u: 0, clock: 0, way: [{point: mesh.position.clone()}, ...way]});
}
/* Home again, it goes in its own way. */
function leaving(figure, {id, home, size, lift, pose}) {
  const k = Math.min(1, figure.clock / ROAM.vanish);
  ({scale: pose.scale, tall: pose.tall} = arrival(figure, AT.set(home.x, home.y + lift, home.z), size, 1 - k, true));
  figure.mesh.position.copy(WANT);
  if (k >= 1) { gone(id, figure); return false; }
}
/* How a figure is drawn this frame: its size, its arrival, the thread on view drawn larger, never more than ROAM.most
 * pixels tall close up; the way it faces, what it looks at or the way it goes, turned by a flourish's spin and tipped
 * by a bow; and its body's own motion. */
function drawFigure(figure, size, grown, passed, {state, scale, tall, turn, bow, face}) {
  const mesh = figure.mesh, m = figure.motion;
  mesh.scale.set(size * scale * grown, size * scale * tall * grown, size * scale * grown);
  // never more than ROAM.most pixels tall close up, so a figure the camera has flown near stays a figure
  const far = Math.max(1, G.camera().position.distanceTo(mesh.position));
  const most = ROAM.most * 2 * far * Math.tan((G.camera().fov || 50) * Math.PI / 360)
    / Math.max(1, G.renderer().domElement.clientHeight) / 1.6;
  if (mesh.scale.x > most) mesh.scale.multiplyScalar(most / mesh.scale.x);
  if (face) AHEAD.subVectors(face, mesh.position); else AHEAD.copy(figure.heading);
  if (turn) AHEAD.applyAxisAngle(THREE.Object3D.DEFAULT_UP, turn);
  orientAgent(mesh, AHEAD, CORNERS[m.corner]?.turn ?? 0.25, passed);
  if (bow) mesh.rotateX(bow);
  const top = figure.top || ROAM.speed * m.speed;
  const speed = figure.stage === 'circling' || figure.stage === 'flourish' ? figure.vel.length() : figure.speed;
  mesh.userData.update(passed, {busy: grown !== 1 ? 1 : 0,
    move: {speed: Math.min(1, speed / Math.max(1, top)), stride: figure.stride, state}});
}
