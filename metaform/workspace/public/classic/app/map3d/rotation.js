/* A hand's signed travel turns node bodies, independently of the layout and the signs, VIEW-005. Storage grows
 * only when graphData changes. Object replacement and visibility changes discard samples, never infer a journey. */
import * as THREE from 'three';

const GAIN = 1, SMOOTH = 0.08, DECAY = Math.LN2 / 0.65, COAST = 2, LAND = 1.6;
// Authored and landing quaternions live in field arrays, never on mutable graph or Three.js objects.
export const TURN = {nodes: [], objects: [], x: new Float64Array(0), y: new Float64Array(0), z: new Float64Array(0),
  wx: new Float64Array(0), wy: new Float64Array(0), wz: new Float64Array(0), radius: new Float64Array(0),
  restX: new Float64Array(0), restY: new Float64Array(0), restZ: new Float64Array(0), restW: new Float64Array(0),
  landX: new Float64Array(0), landY: new Float64Array(0), landZ: new Float64Array(0), landW: new Float64Array(0),
  age: new Float64Array(0), sampled: new Uint8Array(0), last: 0, camera: false, held: false, layout: false, dragging: false, moving: false};
const PREVIOUS = new THREE.Quaternion(), INVERSE = new THREE.Quaternion(), OLD_INVERSE = new THREE.Quaternion();
const BEFORE = new THREE.Vector3(), AFTER = new THREE.Vector3(), TRAVEL = new THREE.Vector3();
const REST = new THREE.Quaternion(), LANDING = new THREE.Quaternion();
const NORMAL = new THREE.Vector3(), AXIS = new THREE.Vector3(), STEP = new THREE.Quaternion();

export function bindTurns(nodes, sizeOf) {
  const n = nodes.length, old = new Map();
  const rx = TURN.restX, ry = TURN.restY, rz = TURN.restZ, rw = TURN.restW;
  for (let i = 0; i < TURN.objects.length; i++) if (TURN.objects[i]) old.set(TURN.objects[i], i);
  TURN.nodes = nodes;
  TURN.objects = new Array(n).fill(null);
  TURN.x = new Float64Array(n); TURN.y = new Float64Array(n); TURN.z = new Float64Array(n);
  TURN.wx = new Float64Array(n); TURN.wy = new Float64Array(n); TURN.wz = new Float64Array(n);
  TURN.radius = new Float64Array(n); TURN.sampled = new Uint8Array(n);
  TURN.restX = new Float64Array(n); TURN.restY = new Float64Array(n);
  TURN.restZ = new Float64Array(n); TURN.restW = new Float64Array(n);
  TURN.landX = new Float64Array(n); TURN.landY = new Float64Array(n);
  TURN.landZ = new Float64Array(n); TURN.landW = new Float64Array(n);
  TURN.age = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    TURN.radius[i] = Math.cbrt(sizeOf(nodes[i])) * 3;
    const object = nodes[i].__threeObj, at = old.get(object);
    if (at !== undefined) {
      TURN.objects[i] = object;
      TURN.restX[i] = rx[at]; TURN.restY[i] = ry[at]; TURN.restZ[i] = rz[at]; TURN.restW[i] = rw[at];
    }
  }
  resetTurns();
}
export function resetTurns() {
  TURN.sampled.fill(0);
  TURN.wx.fill(0); TURN.wy.fill(0); TURN.wz.fill(0);
  TURN.last = 0;
  TURN.camera = TURN.held = TURN.layout = TURN.dragging = TURN.moving = false;
  for (let i = 0; i < TURN.objects.length; i++) {
    const q = TURN.objects[i]?.quaternion;
    const displaced = q && 1 - Math.abs(q.x * TURN.restX[i] + q.y * TURN.restY[i]
      + q.z * TURN.restZ[i] + q.w * TURN.restW[i]) > 1e-14;
    TURN.age[i] = displaced ? 0 : -1;
    if (displaced) TURN.moving = true;
  }
}
export function cameraTurnStart() { TURN.camera = TURN.held = true; }
export function cameraTurnEnd() { TURN.held = false; }
export function cameraTurnStop() { TURN.camera = TURN.held = false; }
export function nodeTurnStart() { TURN.layout = TURN.dragging = true; cameraTurnStop(); }
export function nodeTurnEnd() { TURN.dragging = false; }
export function layoutTurnEnd() { TURN.layout = false; }

/* Called after layout, camera and theme effects, before node batching. Camera rotation supplies apparent travel
 * about the current orbit target; camera distance and target translation supply none, so zoom cannot spin bodies.
 * Travel itself sets the turn. The 80ms velocity estimate smooths momentum without making the distance speed-dependent.
 * Two seconds of free exponential coast precede a finite, smooth landing at the authored orientation. The landing
 * blends the continuing analytic coast to rest with a quintic ease, preserving velocity at both boundaries.
 * Time crossings are split exactly so coasting and landing are independent of the frame rate, even on long frames. */
export function turn3d(now, camera, target, reduced, automatic) {
  const dt = TURN.last ? Math.max(0, (now - TURN.last) / 1000) : 0;
  TURN.last = now;
  if (automatic) cameraTurnStop();
  const orbit = TURN.camera && dt > 0 && !reduced;
  const changed = 1 - Math.abs(PREVIOUS.dot(camera.quaternion)) > 1e-14;
  OLD_INVERSE.copy(PREVIOUS).invert();
  INVERSE.copy(camera.quaternion).invert();
  NORMAL.set(0, 0, 1).applyQuaternion(camera.quaternion);
  const smooth = -Math.expm1(-dt / SMOOTH), decay = Math.exp(-DECAY * dt);
  TURN.moving = false;
  for (let i = 0; i < TURN.nodes.length; i++) {
    const node = TURN.nodes[i], object = node.__threeObj;
    const valid = Number.isFinite(node.x) && Number.isFinite(node.y) && Number.isFinite(node.z);
    const sample = valid && object && TURN.objects[i] === object && TURN.sampled[i] && dt > 0 && !reduced;
    TRAVEL.set(0, 0, 0);
    if (sample && TURN.layout) TRAVEL.set(node.x - TURN.x[i], node.y - TURN.y[i], node.z - TURN.z[i]);
    if (sample && orbit && changed) {
      AFTER.set(node.x - target.x, node.y - target.y, node.z - target.z);
      BEFORE.copy(AFTER).applyQuaternion(OLD_INVERSE);
      AFTER.applyQuaternion(INVERSE).sub(BEFORE).applyQuaternion(camera.quaternion);
      TRAVEL.add(AFTER);
    }
    if (object && TURN.objects[i] !== object) {
      // A newly authored theme/type object is captured before its first turn, without allocating in the frame.
      const q = object.quaternion;
      TURN.restX[i] = q.x; TURN.restY[i] = q.y; TURN.restZ[i] = q.z; TURN.restW[i] = q.w;
      TURN.age[i] = -1;
    }
    TURN.objects[i] = object;
    TURN.sampled[i] = valid && object ? 1 : 0;
    TURN.x[i] = node.x; TURN.y[i] = node.y; TURN.z[i] = node.z;
    if (!object) { TURN.wx[i] = TURN.wy[i] = TURN.wz[i] = 0; TURN.age[i] = -1; continue; }
    REST.set(TURN.restX[i], TURN.restY[i], TURN.restZ[i], TURN.restW[i]);
    if (reduced) {
      // Accessibility changes cancel decorative motion immediately, including any pending upright animation.
      object.quaternion.copy(REST);
      TURN.wx[i] = TURN.wy[i] = TURN.wz[i] = 0; TURN.age[i] = -1;
      continue;
    }
    if (!sample) {
      TURN.wx[i] = TURN.wy[i] = TURN.wz[i] = 0;
      if (TURN.age[i] >= 0) TURN.moving = true;
      continue;
    }
    AXIS.crossVectors(NORMAL, TRAVEL).multiplyScalar(GAIN / TURN.radius[i]);
    const travel = AXIS.length(), held = TURN.dragging || (orbit && TURN.held);
    if (travel > 1e-9 || held) {
      TURN.wx[i] += (AXIS.x / dt - TURN.wx[i]) * smooth;
      TURN.wy[i] += (AXIS.y / dt - TURN.wy[i]) * smooth;
      TURN.wz[i] += (AXIS.z / dt - TURN.wz[i]) * smooth;
      if (travel > 1e-9) {
        object.quaternion.premultiply(STEP.setFromAxisAngle(AXIS.multiplyScalar(1 / travel), travel)).normalize();
        TURN.age[i] = 0;
      } else if (TURN.age[i] >= 0) TURN.age[i] = 0;
    } else if (TURN.age[i] >= 0) {
      const age = TURN.age[i], next = age + dt;
      if (next >= COAST + LAND) {
        object.quaternion.copy(REST);
        TURN.wx[i] = TURN.wy[i] = TURN.wz[i] = 0; TURN.age[i] = -1;
        continue;
      }
      const free = Math.min(dt, Math.max(0, COAST - age));
      AXIS.set(TURN.wx[i], TURN.wy[i], TURN.wz[i]).multiplyScalar(-Math.expm1(-DECAY * free) / DECAY);
      const angle = AXIS.length();
      if (angle > 0) object.quaternion.premultiply(STEP.setFromAxisAngle(AXIS.multiplyScalar(1 / angle), angle)).normalize();
      if (age < COAST && next >= COAST) {
        const q = object.quaternion;
        TURN.landX[i] = q.x; TURN.landY[i] = q.y; TURN.landZ[i] = q.z; TURN.landW[i] = q.w;
      }
      TURN.wx[i] *= decay; TURN.wy[i] *= decay; TURN.wz[i] *= decay;
      if (next >= COAST) {
        const time = next - COAST, t = time / LAND, ease = t * t * t * (10 + t * (-15 + 6 * t));
        // Current velocity times expm1 reconstructs the residual coast from the stored landing origin.
        AXIS.set(TURN.wx[i], TURN.wy[i], TURN.wz[i]).multiplyScalar(Math.expm1(DECAY * time) / DECAY * (1 - ease));
        const angle = AXIS.length();
        // The fixed origin keeps the shortest recovery arc stable even if the residual spin crosses 180 degrees.
        LANDING.set(TURN.landX[i], TURN.landY[i], TURN.landZ[i], TURN.landW[i]).slerp(REST, ease);
        if (angle > 0) LANDING.premultiply(STEP.setFromAxisAngle(AXIS.multiplyScalar(1 / angle), angle)).normalize();
        object.quaternion.copy(LANDING);
      }
      TURN.age[i] = next;
    }
    if (TURN.age[i] >= 0) TURN.moving = true;
  }
  PREVIOUS.copy(camera.quaternion);
  if (orbit && !changed && !TURN.held) TURN.camera = false;
}
