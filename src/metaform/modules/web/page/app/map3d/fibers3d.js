/* The links' fibers, VIEW-005, drawn by the page rather than the graph library: every fiber of one look in one draw,
 * as the flow's dots are, `flow3d`. */
import '/page/app/map3d/graph3d.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
// The Space theme, web_theme space: the 3D map in outer space, drawn by its own module through the hooks marked ULTRA.
import * as ULTRA from '/page/ultra.js';
import {css} from '/page/app/core/dom.js';
import {S} from '/page/app/core/reads.js';
import {G, FIBERS, FIBER_VERTEX, FIBER_FRAGMENT, EDGE, linkWidthOf, nodeSize} from '/page/app/map3d/graph3d.js';
import {linkColor} from '/page/app/map3d/ghosts.js';
import {EDGE_PICK} from '/page/app/map2d/hover.js';

/* The graph library made a mesh for each link, each its own draw with its own uploads: 625 links were 625 draws a
 * frame, and three times that where the glass draws the scene behind it. The library now holds an empty object for
 * each link, which says only whether it is drawn, `visible`, as the map's toggles and the scissors set it; the page
 * draws the fibers as instances of one tube, one draw for each look: the clean fiber, which also draws the edge the
 * pointer would take in the text's color, and ultra's filament. Each instance has its link's tint, its opacity or
 * strength, and its width, and runs from the link's source to its target as the library ran its tube: the same
 * six-sided tube, the same shader. The clean fibers are drawn farthest first, as three.js sorted the library's meshes,
 * since they are see-through and write depth; the filaments add their light, so their order does not matter. Both
 * are drawn before the labels and the flow, which are drawn over the map, LABEL.after and `flow3d`. */
const TUBE = new THREE.CylinderGeometry(1, 1, 1, 6, 1, false).translate(0, 0.5, 0).rotateX(Math.PI / 2);
// A fiber's head, the cone that says which way its information goes, as the 2D map's arrowhead does, `ends2d`: its
// base at z 0 and its tip at z 1, drawn with the fiber's own shader and tint (2026-10-21).
const CONE = new THREE.ConeGeometry(1, 1, 8, 1, false).translate(0, 0.5, 0).rotateX(Math.PI / 2);
const GAP = 0.25;  // the space left between a node's surface and its fiber, as a share of the node's radius
const HEAD = {radius: 3, length: 7};  // a cone's base radius and its length, in the fiber's radii
// read when first drawn: graph3d.js, which these parts import from each other, has run by then
const LOOKS = {
  clean: () => ({fragment: FIBER_FRAGMENT, depthWrite: true, blending: THREE.NormalBlending}),
  ultra: () => ({fragment: ULTRA.FILAMENT, depthWrite: false, blending: THREE.AdditiveBlending}),
};
/* What the fibers are sent to the graphics card as is sent only when it changed: while the layout and the camera are
 * still nothing is, and a buffer the GPU may still be reading for a frame before is never written, since a write to
 * one waits for that frame to be drawn, which on a slow path to the graphics card took 20 ms a frame for 625 fibers.
 * Each look has RING tubes: a change is written into the next and drawn from it, the one drawn RING changes ago. */
const RING = 3;
const DRAWN = {clean: null, ultra: null, stamp: '', picked: new THREE.Color()};
const UP = new THREE.Vector3(0, 1, 0), FROM = new THREE.Vector3(), TO = new THREE.Vector3(), SIZE = new THREE.Vector3();
const DIR = new THREE.Vector3(), PLACED = new THREE.Matrix4();
const BASE = new THREE.Vector3(), TIP = new THREE.Vector3(), HEADED = new THREE.Matrix4();
const NONE = new THREE.Matrix4().makeScale(0, 0, 0);  // a head not drawn: an instance of no size
const REL = 3;  // the graph's nodeRelSize: a node's radius is the cube root of its size times it, `nodeRelSize(3)`
const radiusOf = node => Math.cbrt(nodeSize(node)) * REL;
/* An instanced tube of a look, with room for `room` fibers, in the scene. */
function made(name, room) {
  const look = LOOKS[name](), geometry = TUBE.clone();
  geometry.setAttribute('fiber', new THREE.InstancedBufferAttribute(new Float32Array(room * 4), 4)
    .setUsage(THREE.DynamicDrawUsage));
  // in the scene's haze of depth, `depth3d`, as the nodes are
  const material = new THREE.ShaderMaterial({transparent: true, depthWrite: look.depthWrite,
    blending: look.blending, vertexShader: FIBER_VERTEX, fragmentShader: look.fragment, fog: true,
    uniforms: {...THREE.UniformsUtils.clone(THREE.UniformsLib.fog), edgeLeast: EDGE.uniform}});
  const mesh = new THREE.InstancedMesh(geometry, material, room);
  mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  Object.assign(mesh, {frustumCulled: false, renderOrder: 9, count: 0});
  mesh.raycast = () => {};  // the page picks an edge on the screen, `linkAt3d`
  // its heads: two instances of the cone for each fiber, one at each end, of no size where an end has none; the
  // same material, so the heads are drawn as the fibers are
  const heads = CONE.clone();
  heads.setAttribute('fiber', new THREE.InstancedBufferAttribute(new Float32Array(room * 8), 4)
    .setUsage(THREE.DynamicDrawUsage));
  const cone = new THREE.InstancedMesh(heads, material, room * 2);
  cone.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  Object.assign(cone, {frustumCulled: false, renderOrder: 9, count: 0});
  cone.raycast = () => {};
  mesh.userData.cone = cone;
  return mesh;
}
/* Which ends of a link carry a head, as the 2D map points its arrowheads, `ends2d` and `pointed`: where the
 * information arrives. An encounter's fiber runs from the receiver to the provider: the head is at the provider,
 * at the receiver when the join receives, at both when both; a memory's relation points at what it names; a tree
 * line and an item's line have none. 1 is the target end, 2 the source end. */
function headsOf(link) {
  if (link.k === 'relation') return 1;
  if (link.k !== 'encounter') return 0;
  const join = S.joins.find(one => one.id === link.join);
  return join?.ifd === 'both' ? 3 : join?.ifd === 'receives' ? 2 : 1;
}
/* The look of a link: which tube draws it and its tint and opacity, read again when the theme, the look or the data
 * changes, never each frame. */
function lookOf(link, stamp) {
  if (link.__fiber?.stamp === stamp) return link.__fiber;
  const ultra = ULTRA.fiber(link), color = new THREE.Color(ultra ? ultra.color : linkColor(link));
  const width = Math.ceil(linkWidthOf(link) * 10) / 10;  // as the library sized its tube
  link.__fiber = {stamp, ultra: Boolean(ultra), r: color.r, g: color.g, b: color.b,
    a: ultra ? ultra.strength : Number(css('--link-opacity')), radius: width / 2, heads: headsOf(link)};
  return link.__fiber;
}
const drawn = link => link.__lineObj?.visible && link.__lineObj.parent && link.source?.x !== undefined
  && link.target?.x !== undefined;
/* Each frame, before the scene is drawn: every fiber shown placed between its ends. */
export function fibers3d() {
  if (!G) return;
  const scene = G.scene(), camera = G.camera(), links = G.graphData().links;
  const stamp = `${FIBERS.version}|${ULTRA.on()}`;
  if (stamp !== DRAWN.stamp) { DRAWN.stamp = stamp; DRAWN.picked.set(css('--text')); }
  const lists = {clean: [], ultra: []};
  for (const link of links) {
    if (!drawn(link)) continue;
    const look = lookOf(link, stamp);
    lists[look.ultra && link !== EDGE_PICK.link3d ? 'ultra' : 'clean'].push(link);
  }
  // farthest first, by where each starts, as three.js sorts what is see-through
  const forward = camera.getWorldDirection(TO), eye = camera.position;
  for (const link of lists.clean) {
    const at = link.source;
    link.__depth = (at.x - eye.x) * forward.x + (at.y - eye.y) * forward.y + (at.z - eye.z) * forward.z;
  }
  lists.clean.sort((a, b) => b.__depth - a.__depth);
  for (const name of ['clean', 'ultra']) {
    const list = lists[name];
    let ring = DRAWN[name];
    if (ring && (ring[0].parent !== scene || ring[0].instanceMatrix.count < list.length)) {
      for (const mesh of ring) {
        mesh.parent?.remove(mesh);
        mesh.userData.cone.parent?.remove(mesh.userData.cone);
        mesh.geometry.dispose();
        mesh.userData.cone.geometry.dispose();
        mesh.material.dispose();
      }
      ring = DRAWN[name] = null;
    }
    if (!ring && !list.length) continue;
    if (!ring) {
      const room = Math.max(256, 2 ** Math.ceil(Math.log2(list.length)));
      ring = DRAWN[name] = Array.from({length: RING}, () => made(name, room));
      scene.add(...ring, ...ring.map(mesh => mesh.userData.cone));
    }
    const now = ring.find(mesh => mesh.visible) || ring[RING - 1], next = ring[(ring.indexOf(now) + 1) % RING];
    if (!place(next, list, now)) continue;
    for (const mesh of ring) mesh.visible = mesh.userData.cone.visible = mesh === next;
  }
}
/* The fibers of a look written into `mesh`, and whether they differ from those `now` draws. */
function place(mesh, list, now) {
  const matrices = mesh.instanceMatrix.array, fiber = mesh.geometry.getAttribute('fiber'), values = fiber.array;
  const cone = mesh.userData.cone, heads = cone.instanceMatrix.array, headFiber = cone.geometry.getAttribute('fiber'),
    headValues = headFiber.array;
  list.forEach((link, i) => {
    const look = link.__fiber, from = link.source, to = link.target;
    FROM.set(from.x, from.y || 0, from.z || 0);
    TO.set(to.x, to.y || 0, to.z || 0);
    // A fiber stops short of each node, GAP beyond its surface, and never runs inside it: what is inside the glass
    // is the node's own, and only that is hidden; what is behind the glass still shows through it (2026-10-21). Two
    // nodes that overlap leave their fiber no length.
    const span = FROM.distanceTo(TO), into = radiusOf(from) * (1 + GAP), out = radiusOf(to) * (1 + GAP);
    let length = Math.max(0, span - into - out);
    if (span > 0) FROM.addScaledVector(DIR.subVectors(TO, FROM).divideScalar(span), Math.min(into, span));
    else DIR.set(0, 0, 1);
    // its heads, each taking its length off the tube, which ends at the cone's base
    const long = Math.min(look.radius * HEAD.length, length / 2), wide = look.radius * HEAD.radius;
    if (look.heads & 1) {
      TIP.copy(FROM).addScaledVector(DIR, length);
      BASE.copy(TIP).addScaledVector(DIR, -long);
      HEADED.lookAt(TIP, BASE, UP).scale(SIZE.set(wide, wide, long)).setPosition(BASE).toArray(heads, i * 32);
      length -= long;
    } else NONE.toArray(heads, i * 32);
    if (look.heads & 2) {
      TIP.copy(FROM);
      BASE.copy(FROM).addScaledVector(DIR, long);
      HEADED.lookAt(TIP, BASE, UP).scale(SIZE.set(wide, wide, long)).setPosition(BASE).toArray(heads, i * 32 + 16);
      FROM.addScaledVector(DIR, long);
      length -= long;
    } else NONE.toArray(heads, i * 32 + 16);
    // the library's tube: at its source, turned to look at its target, as long as the link, `Object3D.lookAt`
    PLACED.lookAt(TO, FROM, UP).scale(SIZE.set(look.radius, look.radius, Math.max(0, length))).setPosition(FROM);
    PLACED.toArray(matrices, i * 16);
    const picked = link === EDGE_PICK.link3d;
    values[i * 4] = picked ? DRAWN.picked.r : look.r;
    values[i * 4 + 1] = picked ? DRAWN.picked.g : look.g;
    values[i * 4 + 2] = picked ? DRAWN.picked.b : look.b;
    values[i * 4 + 3] = picked ? 1 : look.a;
    for (let k = 0; k < 8; k++) headValues[i * 8 + k] = values[i * 4 + k % 4];  // each head in its fiber's tint
  });
  mesh.count = list.length;
  cone.count = list.length * 2;
  if (now !== mesh && now.count === mesh.count && same(now.instanceMatrix.array, matrices, list.length * 16)
    && same(now.geometry.getAttribute('fiber').array, values, list.length * 4)) return false;
  for (const [attribute, size] of [[mesh.instanceMatrix, 16], [fiber, 4], [cone.instanceMatrix, 32], [headFiber, 8]]) {
    attribute.clearUpdateRanges();
    attribute.addUpdateRange(0, list.length * size);
    attribute.needsUpdate = true;
  }
  return true;
}
function same(one, two, length) {
  for (let i = 0; i < length; i++) if (one[i] !== two[i]) return false;
  return true;
}
