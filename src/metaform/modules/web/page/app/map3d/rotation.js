/* A hand's signed travel turns node bodies, independently of the layout and the signs, VIEW-005. Storage grows
 * only when graphData changes. Object replacement and visibility changes discard samples, never infer a journey. */
import * as THREE from 'three';

const GAIN = 0.16, SMOOTH = 0.08, DECAY = Math.LN2 / 0.45, STOP = 0.005;
export const TURN = {nodes: [], objects: [], x: new Float64Array(0), y: new Float64Array(0), z: new Float64Array(0),
  wx: new Float64Array(0), wy: new Float64Array(0), wz: new Float64Array(0), radius: new Float64Array(0),
  sampled: new Uint8Array(0), last: 0, camera: false, held: false, layout: false, dragging: false, moving: false};
const PREVIOUS = new THREE.Quaternion(), INVERSE = new THREE.Quaternion(), OLD_INVERSE = new THREE.Quaternion();
const BEFORE = new THREE.Vector3(), AFTER = new THREE.Vector3(), TRAVEL = new THREE.Vector3();
const NORMAL = new THREE.Vector3(), AXIS = new THREE.Vector3(), STEP = new THREE.Quaternion();

export function bindTurns(nodes, sizeOf) {
  const n = nodes.length;
  TURN.nodes = nodes;
  TURN.objects = new Array(n).fill(null);
  TURN.x = new Float64Array(n); TURN.y = new Float64Array(n); TURN.z = new Float64Array(n);
  TURN.wx = new Float64Array(n); TURN.wy = new Float64Array(n); TURN.wz = new Float64Array(n);
  TURN.radius = new Float64Array(n); TURN.sampled = new Uint8Array(n);
  for (let i = 0; i < n; i++) TURN.radius[i] = Math.cbrt(sizeOf(nodes[i])) * 3;
  resetTurns();
}
export function resetTurns() {
  TURN.sampled.fill(0);
  TURN.wx.fill(0); TURN.wy.fill(0); TURN.wz.fill(0);
  TURN.last = 0;
  TURN.camera = TURN.held = TURN.layout = TURN.dragging = TURN.moving = false;
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
 * Free rotation integrates exponential decay analytically, including long frames, so its endpoint is rate-independent. */
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
    TURN.objects[i] = object;
    TURN.sampled[i] = valid && object ? 1 : 0;
    TURN.x[i] = node.x; TURN.y[i] = node.y; TURN.z[i] = node.z;
    if (!sample) { TURN.wx[i] = TURN.wy[i] = TURN.wz[i] = 0; continue; }
    AXIS.crossVectors(NORMAL, TRAVEL).multiplyScalar(GAIN / TURN.radius[i]);
    const travel = AXIS.length();
    if (travel > 1e-9) {
      TURN.wx[i] += (AXIS.x / dt - TURN.wx[i]) * smooth;
      TURN.wy[i] += (AXIS.y / dt - TURN.wy[i]) * smooth;
      TURN.wz[i] += (AXIS.z / dt - TURN.wz[i]) * smooth;
    } else if (TURN.dragging || (orbit && TURN.held)) {
      TURN.wx[i] *= 1 - smooth; TURN.wy[i] *= 1 - smooth; TURN.wz[i] *= 1 - smooth;
    } else {
      AXIS.set(TURN.wx[i], TURN.wy[i], TURN.wz[i]).multiplyScalar((1 - decay) / DECAY);
      TURN.wx[i] *= decay; TURN.wy[i] *= decay; TURN.wz[i] *= decay;
    }
    const angle = AXIS.length();
    if (angle > 0) object.quaternion.premultiply(STEP.setFromAxisAngle(AXIS.multiplyScalar(1 / angle), angle)).normalize();
    const speed = Math.hypot(TURN.wx[i], TURN.wy[i], TURN.wz[i]);
    if (speed > STOP) TURN.moving = true;
    else TURN.wx[i] = TURN.wy[i] = TURN.wz[i] = 0;
  }
  PREVIOUS.copy(camera.quaternion);
  if (orbit && !changed && !TURN.held) TURN.camera = false;
}
