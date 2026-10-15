/* Nodes that look alike drawn together, VIEW-010: each set of the map's nodes that share a shape and a shader drawn in
 * one draw, as the fibers are, `fibers3d`. */
import '/page/app/map3d/fibers3d.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
// Ultra graphics, web_graphics: the 3D map in outer space, drawn by its own module through the hooks marked ULTRA.
import * as ULTRA from '/page/ultra.js';
import {G} from '/page/app/map3d/graph3d.js';

/* Each node keeps its own object, which the page and the graph library move, color, light, pick and drag as before;
 * only its drawing moves into a batch. A node part joins the batch of its shape and shader when its look is one the
 * batch can give each instance: in clean, the graph's own spheres of the join's purpose vertices, in the shared
 * material of their color, which a lit, pulsed or ghost node leaves for one of its own; in ultra, a solid body of a
 * kind and size, and every body's halo, `ULTRA.batch`. A part in a batch is left out of the drawing by the frustum test
 * alone, an empty bounding sphere, `UNSEEN`, so it is still visible to everything that asks, picked, dragged and seen
 * by the agents' eyes; leaving the batch gives it its own drawing back. What is sent to the graphics card is sent only
 * when it changed, into the next of RING buffers, as the fibers' is. */
const UNSEEN = new THREE.Sphere(new THREE.Vector3(), -Infinity);
const RING = 3;
export const BATCHES = new Map();  // key: {ring, clean}, read by the browser checks
const HELD = new Set();     // the parts drawn by a batch
const OWN = new THREE.Matrix4(), PART = new THREE.Matrix4();
/* The batch a node part joins, or null. */
function batchOf(object) {
  const ultra = ULTRA.batch(object);
  if (ultra) return ultra;
  const material = object.material;
  // a sphere at the graph's own opacity; one fading in, `ghost3d`, is drawn alone until it is solid
  if (!object.__graphDefaultObj || !material?.isMeshLambertMaterial || material.userData.own || !material.visible
    || object.userData.ghost || material.opacity !== G.nodeOpacity()) return null;
  const {opacity, transparent, depthWrite} = material;
  return {key: `sphere:${opacity}:${transparent}:${depthWrite}`, look: material, clean: true,
    make: () => new THREE.MeshLambertMaterial({color: 0xffffff, opacity, transparent, depthWrite})};
}
/* Each frame, before the scene is drawn. */
export function nodes3d() {
  if (!G) return;
  const scene = G.scene(), lists = new Map(), was = new Set(HELD);
  const join = (object, host) => {
    const batch = object.visible ? batchOf(object) : null;
    if (!batch) return;
    const key = `${batch.key}:${object.geometry.uuid}`;  // one shape a batch: a rock is one of four
    if (!lists.has(key)) lists.set(key, {batch, parts: []});
    lists.get(key).parts.push({object, host});
  };
  for (const node of G.graphData().nodes) {
    const object = node.__threeObj;
    if (!object?.visible || !object.parent) continue;
    join(object, null);
    for (const part of object.children) join(part, object);
  }
  // what is see-through is drawn farthest first, as three.js sorts it
  const camera = G.camera(), forward = camera.getWorldDirection(new THREE.Vector3()), eye = camera.position;
  for (const {batch, parts} of lists.values()) {
    if (!batch.look.transparent || batch.look.blending === THREE.AdditiveBlending) continue;
    for (const part of parts) {
      const at = part.object.position;
      part.depth = (at.x - eye.x) * forward.x + (at.y - eye.y) * forward.y + (at.z - eye.z) * forward.z;
    }
    parts.sort((a, b) => b.depth - a.depth);
  }
  HELD.clear();
  for (const [key, {batch, parts}] of lists) {
    let held = BATCHES.get(key);
    if (held && (held.ring[0].parent !== scene || held.ring[0].instanceMatrix.count < parts.length)) {
      drop(key);
      held = null;
    }
    if (!held) {
      const room = Math.max(64, 2 ** Math.ceil(Math.log2(parts.length)));
      const geometry = parts[0].object.geometry;
      held = {ring: Array.from({length: RING}, () => made(batch, geometry, room)), clean: Boolean(batch.clean)};
      scene.add(...held.ring);
      BATCHES.set(key, held);
    }
    const now = held.ring.find(mesh => mesh.visible) || held.ring[RING - 1];
    const next = held.ring[(held.ring.indexOf(now) + 1) % RING];
    if (place(next, parts, held.clean, now)) for (const mesh of held.ring) mesh.visible = mesh === next;
    for (const {object} of parts) {
      HELD.add(object);
      if (!was.has(object)) unseen(object, true);
    }
  }
  for (const key of BATCHES.keys()) if (!lists.has(key)) drop(key);
  for (const object of was) if (!HELD.has(object)) unseen(object, false);
}
/* A part left out of its own drawing, or given it back. */
function unseen(object, held) {
  if (held) {
    object.userData.culled = object.frustumCulled;
    object.frustumCulled = true;
    object.boundingSphere = UNSEEN;
  } else {
    delete object.boundingSphere;
    object.frustumCulled = object.userData.culled ?? true;
  }
}
function drop(key) {
  const held = BATCHES.get(key);
  for (const mesh of held.ring) {
    mesh.parent?.remove(mesh);
    mesh.material.dispose();
    mesh.dispose();  // its instance buffers
    if (!held.clean) mesh.geometry.dispose();  // its own copy, made in `made`; a clean batch draws the graph's
  }
  BATCHES.delete(key);
}
/* An instanced copy of a part's shape with its batch's shader, room for `room` parts. */
function made(batch, geometry, room) {
  const mesh = new THREE.InstancedMesh(geometry, batch.make(), room);
  mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  if (batch.clean) {
    mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(room * 3), 3)
      .setUsage(THREE.DynamicDrawUsage);
  } else {
    // a copy of the parts' shape, with the instance values as its own attributes: a copy, so that dropping the batch
    // frees its buffers and never those the parts still draw with
    mesh.geometry = geometry.clone();
    for (const name of ['lookA', 'lookB', 'lookC']) {
      mesh.geometry.setAttribute(name, new THREE.InstancedBufferAttribute(new Float32Array(room * 4), 4)
        .setUsage(THREE.DynamicDrawUsage));
    }
  }
  Object.assign(mesh, {frustumCulled: false, count: 0, visible: false});
  mesh.raycast = () => {};  // the page picks a node by its own object, `picked`
  return mesh;
}
const LOOK = new Float32Array(12);
/* The parts written into `mesh`, and whether they differ from what `now` draws. */
function place(mesh, parts, clean, now) {
  const matrices = mesh.instanceMatrix.array, looks = looksOf(mesh, clean);
  parts.forEach(({object, host}, i) => {
    // where the part is drawn this frame, from where it and its node now are: the matrices three.js keeps are
    // brought up to date only as the scene is drawn, after this
    OWN.compose(object.position, object.quaternion, object.scale);
    if (host) OWN.premultiply(PART.compose(host.position, host.quaternion, host.scale));
    OWN.premultiply((host || object).parent.matrixWorld);
    OWN.toArray(matrices, i * 16);
    if (clean) return object.material.color.toArray(looks[0].array, i * 3);
    ULTRA.lookOf(host ? host.material : object.material, LOOK, 0);
    for (let n = 0; n < 3; n++) looks[n].array.set(LOOK.subarray(n * 4, n * 4 + 4), i * 4);
  });
  mesh.count = parts.length;
  const sizes = [16, ...looks.map(look => look.itemSize)], attributes = [mesh.instanceMatrix, ...looks];
  const before = [now.instanceMatrix, ...looksOf(now, clean)];
  const kept = (attribute, n) => same(before[n].array, attribute.array, parts.length * sizes[n]);
  if (now !== mesh && now.count === mesh.count && attributes.every(kept)) return false;
  attributes.forEach((attribute, n) => {
    attribute.clearUpdateRanges();
    attribute.addUpdateRange(0, parts.length * sizes[n]);
    attribute.needsUpdate = true;
  });
  return true;
}
const looksOf = (mesh, clean) => clean ? [mesh.instanceColor]
  : ['lookA', 'lookB', 'lookC'].map(name => mesh.geometry.getAttribute(name));
function same(one, two, length) {
  for (let i = 0; i < length; i++) if (one[i] !== two[i]) return false;
  return true;
}
