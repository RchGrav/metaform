/* The links' fibers, VIEW-005, drawn by the page rather than the graph library: every fiber of one look in one draw,
 * as the flow's dots are, `flow3d`. */
import '/page/app/map3d/graph3d.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
// The Space theme, web_theme space: the 3D map in outer space, drawn by its own module through the hooks marked ULTRA.
import * as ULTRA from '/page/ultra.js';
import {css} from '/page/app/core/dom.js';
import {G, FIBERS, FIBER_VERTEX, FIBER_FRAGMENT, linkWidthOf} from '/page/app/map3d/graph3d.js';
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
const PLACED = new THREE.Matrix4();
/* An instanced tube of a look, with room for `room` fibers, in the scene. */
function made(name, room) {
  const look = LOOKS[name](), geometry = TUBE.clone();
  geometry.setAttribute('fiber', new THREE.InstancedBufferAttribute(new Float32Array(room * 4), 4)
    .setUsage(THREE.DynamicDrawUsage));
  const material = new THREE.ShaderMaterial({transparent: true, depthWrite: look.depthWrite,
    blending: look.blending, vertexShader: FIBER_VERTEX, fragmentShader: look.fragment});
  const mesh = new THREE.InstancedMesh(geometry, material, room);
  mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  Object.assign(mesh, {frustumCulled: false, renderOrder: 9, count: 0});
  mesh.raycast = () => {};  // the page picks an edge on the screen, `linkAt3d`
  return mesh;
}
/* The look of a link: which tube draws it and its tint and opacity, read again when the theme, the look or the data
 * changes, never each frame. */
function lookOf(link, stamp) {
  if (link.__fiber?.stamp === stamp) return link.__fiber;
  const ultra = ULTRA.fiber(link), color = new THREE.Color(ultra ? ultra.color : linkColor(link));
  const width = Math.ceil(linkWidthOf(link) * 10) / 10;  // as the library sized its tube
  link.__fiber = {stamp, ultra: Boolean(ultra), r: color.r, g: color.g, b: color.b,
    a: ultra ? ultra.strength : Number(css('--link-opacity')), radius: width / 2};
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
        mesh.geometry.dispose();
        mesh.material.dispose();
      }
      ring = DRAWN[name] = null;
    }
    if (!ring && !list.length) continue;
    if (!ring) {
      const room = Math.max(256, 2 ** Math.ceil(Math.log2(list.length)));
      ring = DRAWN[name] = Array.from({length: RING}, () => made(name, room));
      scene.add(...ring);
    }
    const now = ring.find(mesh => mesh.visible) || ring[RING - 1], next = ring[(ring.indexOf(now) + 1) % RING];
    if (!place(next, list, now)) continue;
    for (const mesh of ring) mesh.visible = mesh === next;
  }
}
/* The fibers of a look written into `mesh`, and whether they differ from those `now` draws. */
function place(mesh, list, now) {
  const matrices = mesh.instanceMatrix.array, fiber = mesh.geometry.getAttribute('fiber'), values = fiber.array;
  list.forEach((link, i) => {
    const look = link.__fiber, from = link.source, to = link.target;
    FROM.set(from.x, from.y || 0, from.z || 0);
    TO.set(to.x, to.y || 0, to.z || 0);
    // the library's tube: at its source, turned to look at its target, as long as the link, `Object3D.lookAt`
    PLACED.lookAt(TO, FROM, UP).scale(SIZE.set(look.radius, look.radius, FROM.distanceTo(TO))).setPosition(FROM);
    PLACED.toArray(matrices, i * 16);
    const picked = link === EDGE_PICK.link3d;
    values[i * 4] = picked ? DRAWN.picked.r : look.r;
    values[i * 4 + 1] = picked ? DRAWN.picked.g : look.g;
    values[i * 4 + 2] = picked ? DRAWN.picked.b : look.b;
    values[i * 4 + 3] = picked ? 1 : look.a;
  });
  mesh.count = list.length;
  if (now !== mesh && now.count === mesh.count && same(now.instanceMatrix.array, matrices, list.length * 16)
    && same(now.geometry.getAttribute('fiber').array, values, list.length * 4)) return false;
  for (const [attribute, size] of [[mesh.instanceMatrix, 16], [fiber, 4]]) {
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
