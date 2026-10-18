/* Nodes that look alike drawn together, VIEW-010: each set of the map's nodes that share a shape and a shader drawn in
 * one draw, as the fibers are, `fibers3d`. */
import '/page/app/map3d/fibers3d.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
// The Space theme, web_theme space: the 3D map in outer space, drawn by its own module through the hooks marked ULTRA.
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
const OWN = new THREE.Matrix4(), PART = new THREE.Matrix4();
/* The batch a node part joins, or null. What a batch is, its key and look, is made once for each material and kept on
 * it while the values it was made from hold, so a frame makes no batch of its own, `cachedSphere`, `ULTRA.batch`. */
function batchOf(object) {
  const ultra = ULTRA.batch(object);
  if (ultra) return ultra;
  const material = object.material;
  // a sphere at the graph's own opacity; one fading in, `ghost3d`, is drawn alone until it is solid
  if (!object.__graphDefaultObj || !material?.isMeshLambertMaterial || material.userData.own || !material.visible
    || object.userData.ghost || material.opacity !== G.nodeOpacity()) return null;
  return cachedSphere(material);
}
function cachedSphere(material) {
  const {opacity, transparent, depthWrite} = material, kept = BATCHED.get(material);
  if (kept && kept.opacity === opacity && kept.transparent === transparent && kept.depthWrite === depthWrite) {
    return kept;
  }
  const batch = {key: `sphere:${opacity}:${transparent}:${depthWrite}`, look: material,
    clean: true, opacity, transparent, depthWrite,
    make: () => new THREE.MeshLambertMaterial({color: 0xffffff, opacity, transparent, depthWrite})};
  BATCHED.set(material, batch);
  return batch;
}
// what is kept for a material, a part and a part held by a batch, beside them and never in their userData, which
// three.js copies through JSON when it clones them
const BATCHED = new WeakMap(), KEYED_ON = new WeakMap(), SPHERES = new WeakMap();
/* The parts of each batch this frame, kept from frame to frame and refilled, so a frame allocates nothing: `objects`
 * and `hosts` side by side, `depths` for what is see-through, `order` the parts in the order they are drawn. LISTS is
 * walked by index; KEYED finds a list by its batch's key. */
const LISTS = [], KEYED = new Map();
// the parts drawn by a batch this frame and the last, swapped each frame, each part marked with the frame it was in
let HELD = [], WAS = [], FRAME = 0;
const FORWARD = new THREE.Vector3();
/* The batch's key with its shape's, kept on the part while its batch and shape are the same. */
function keyOf(object, batch) {
  const kept = KEYED_ON.get(object);
  if (kept && kept.batch === batch && kept.geometry === object.geometry) return kept.key;
  const key = `${batch.key}:${object.geometry.uuid}`;  // one shape a batch: a rock is one of four
  KEYED_ON.set(object, {batch, geometry: object.geometry, key});
  return key;
}
function joinBatch(object, host) {
  const batch = object.visible ? batchOf(object) : null;
  if (!batch) return;
  const key = keyOf(object, batch);
  let list = KEYED.get(key);
  if (!list) {
    list = {key, batch, objects: [], hosts: [], depths: [], order: [], n: 0};
    KEYED.set(key, list);
    LISTS.push(list);
  }
  list.batch = batch;
  const n = list.n++;
  list.objects[n] = object;
  list.hosts[n] = host;
  list.order[n] = n;
}
// what is see-through is drawn farthest first, as three.js sorts it; the depths are those of the list being sorted
let DEPTHS = null;
const farthestFirst = (one, two) => DEPTHS[two] - DEPTHS[one];
/* Each frame, before the scene is drawn. */
export function nodes3d() {
  if (!G) return;
  const scene = G.scene(), nodes = G.graphData().nodes;
  FRAME++;
  for (let l = 0; l < LISTS.length; l++) LISTS[l].n = 0;
  for (let i = 0; i < nodes.length; i++) {
    const object = nodes[i].__threeObj;
    if (!object?.visible || !object.parent) continue;
    joinBatch(object, null);
    const children = object.children;
    for (let c = 0; c < children.length; c++) joinBatch(children[c], object);
  }
  const camera = G.camera(), eye = camera.position;
  camera.getWorldDirection(FORWARD);
  const swap = WAS;
  WAS = HELD; HELD = swap; HELD.length = 0;
  for (let l = 0; l < LISTS.length; l++) {
    const list = LISTS[l], {batch, objects, n} = list;
    if (!n) { if (BATCHES.has(list.key)) drop(list.key); continue; }
    if (batch.look.transparent && batch.look.blending !== THREE.AdditiveBlending) {
      const depths = list.depths;
      for (let i = 0; i < n; i++) {
        const at = objects[i].position;
        depths[i] = (at.x - eye.x) * FORWARD.x + (at.y - eye.y) * FORWARD.y + (at.z - eye.z) * FORWARD.z;
      }
      DEPTHS = depths;
      list.order.length = n;
      list.order.sort(farthestFirst);
      DEPTHS = null;
    }
    let held = BATCHES.get(list.key);
    if (held && (held.ring[0].parent !== scene || held.ring[0].instanceMatrix.count < n)) {
      drop(list.key);
      held = null;
    }
    if (!held) {
      const room = Math.max(64, 2 ** Math.ceil(Math.log2(n)));
      const geometry = objects[0].geometry;
      held = {ring: Array.from({length: RING}, () => made(batch, geometry, room)), clean: Boolean(batch.clean)};
      scene.add(...held.ring);
      BATCHES.set(list.key, held);
    }
    let now = held.ring[RING - 1];
    for (let r = 0; r < RING; r++) if (held.ring[r].visible) { now = held.ring[r]; break; }
    const next = held.ring[(held.ring.indexOf(now) + 1) % RING];
    if (place(next, list, held.clean, now)) for (let r = 0; r < RING; r++) held.ring[r].visible = held.ring[r] === next;
    for (let i = 0; i < n; i++) {
      const object = objects[i];
      if (object.userData.heldAt !== FRAME - 1) unseen(object, true);
      object.userData.heldAt = FRAME;
      HELD.push(object);
    }
  }
  for (const key of BATCHES.keys()) if (!KEYED.get(key)?.n) drop(key);
  for (let i = 0; i < WAS.length; i++) if (WAS[i].userData.heldAt !== FRAME) unseen(WAS[i], false);
}
/* A part left out of its own drawing, or given it back. */
function unseen(object, held) {
  if (held) {
    if (object.boundingSphere === UNSEEN) return;
    object.userData.culled = object.frustumCulled;
    SPHERES.set(object, object.boundingSphere ?? null);
    object.frustumCulled = true;
    object.boundingSphere = UNSEEN;
  } else {
    object.boundingSphere = SPHERES.get(object) ?? undefined;
    object.frustumCulled = object.userData.culled ?? true;
  }
}
function drop(key) {
  const held = BATCHES.get(key);
  if (!held) return;
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
    for (const name of LOOKS) {
      mesh.geometry.setAttribute(name, new THREE.InstancedBufferAttribute(new Float32Array(room * 4), 4)
        .setUsage(THREE.DynamicDrawUsage));
    }
  }
  Object.assign(mesh, {frustumCulled: false, count: 0, visible: false});
  mesh.raycast = () => {};  // the page picks a node by its own object, `picked`
  return mesh;
}
const LOOKS = ['lookA', 'lookB', 'lookC'];
const LOOK = new Float32Array(12);
/* The parts written into `mesh`, in their order, and whether they differ from what `now` draws. */
function place(mesh, list, clean, now) {
  const matrices = mesh.instanceMatrix.array, {objects, hosts, order, n} = list;
  const attributes = mesh.geometry.attributes;
  const colors = clean ? mesh.instanceColor.array : null;
  const lookA = clean ? null : attributes.lookA.array, lookB = clean ? null : attributes.lookB.array;
  const lookC = clean ? null : attributes.lookC.array;
  for (let i = 0; i < n; i++) {
    const object = objects[order[i]], host = hosts[order[i]];
    // where the part is drawn this frame, from where it and its node now are: the matrices three.js keeps are
    // brought up to date only as the scene is drawn, after this
    OWN.compose(object.position, object.quaternion, object.scale);
    if (host) OWN.premultiply(PART.compose(host.position, host.quaternion, host.scale));
    OWN.premultiply((host || object).parent.matrixWorld);
    OWN.toArray(matrices, i * 16);
    if (clean) { object.material.color.toArray(colors, i * 3); continue; }
    ULTRA.lookOf(host ? host.material : object.material, LOOK, 0);
    for (let k = 0; k < 4; k++) {
      lookA[i * 4 + k] = LOOK[k]; lookB[i * 4 + k] = LOOK[4 + k]; lookC[i * 4 + k] = LOOK[8 + k];
    }
  }
  mesh.count = n;
  const was = now.geometry.attributes;
  const kept = now !== mesh && now.count === n && same(now.instanceMatrix.array, matrices, n * 16)
    && (clean ? same(now.instanceColor.array, colors, n * 3)
      : same(was.lookA.array, lookA, n * 4) && same(was.lookB.array, lookB, n * 4)
        && same(was.lookC.array, lookC, n * 4));
  if (kept) return false;
  sent(mesh.instanceMatrix, n * 16);
  if (clean) sent(mesh.instanceColor, n * 3);
  else { sent(attributes.lookA, n * 4); sent(attributes.lookB, n * 4); sent(attributes.lookC, n * 4); }
  return true;
}
function sent(attribute, count) {
  attribute.clearUpdateRanges();
  attribute.addUpdateRange(0, count);
  attribute.needsUpdate = true;
}
function same(one, two, length) {
  for (let i = 0; i < length; i++) if (one[i] !== two[i]) return false;
  return true;
}

/* ---------- the labels, drawn in one draw for each page of an atlas, VIEW-038 and VIEW-010 ---------- */
/* Each label keeps its own sign, `tags` in labels.js, which the page places, turns, sizes, fades and reads as before,
 * and its own canvas, painted only when what it shows changes; only its drawing moves here. Its canvas is copied into
 * a slot of an atlas page when it is painted, each page sent to the graphics card once in a frame where any of its
 * labels changed (a label sent alone waited on the graphics card for each one, seconds for a map's worth), and every
 * label of a page is one instance of one plane, its place, turn and size its sign's, its part of the page and its
 * opacity its own: one draw call a page in
 * place of one a label (874 at 1,000 elements, critic F1, 2026-10-17). The signs themselves stay out of the drawing,
 * on HIDDEN_LAYER, so three.js neither draws nor sorts them. A slot freed by a label painted at another size, or
 * dropped, is taken again by the next that fits; a page with no room left gets another page beside it. Instances are
 * written farthest first, as three.js sorted the signs, so a nearer name is drawn over a farther one. */
const PAGE = 2048, GUTTER = 2, ROW_STEP = 8;
export const HIDDEN_LAYER = 31;
export const ATLAS = {pages: [], scene: null};
const LABEL_VERTEX = ['#include <uv_vertex>', '#include <uv_vertex>\nvMapUv = labelUv.xy + vMapUv * labelUv.zw;\n'
  + 'vLabelOpacity = labelOpacity;'];
function atlasPage(index) {
  // a page is a canvas the labels are copied into, sent to the graphics card whole the first time, then each label
  // repainted on it sent alone into its slot, `atlasPaint`
  const canvas = Object.assign(document.createElement('canvas'), {width: PAGE, height: PAGE});
  const texture = new THREE.CanvasTexture(canvas);
  Object.assign(texture, {colorSpace: THREE.SRGBColorSpace, minFilter: THREE.LinearFilter,
    magFilter: THREE.LinearFilter, generateMipmaps: false});
  const material = new THREE.MeshBasicMaterial({map: texture, side: THREE.DoubleSide, depthTest: true,
    depthWrite: false, transparent: true, alphaTest: 0.02, toneMapped: false, fog: false});  // faded by its own depth
  material.onBeforeCompile = shader => {
    shader.vertexShader = 'attribute vec4 labelUv;\nattribute float labelOpacity;\nvarying float vLabelOpacity;\n'
      + shader.vertexShader.replace(...LABEL_VERTEX);
    shader.fragmentShader = 'varying float vLabelOpacity;\n' + shader.fragmentShader
      .replace('#include <map_fragment>', '#include <map_fragment>\ndiffuseColor.a *= vLabelOpacity;');
  };
  material.customProgramCacheKey = () => 'label-atlas';
  const page = {index, texture, pen: canvas.getContext('2d'), mesh: null, room: 0, dirty: false, spent: 0, rows: [],
    top: 0, n: 0};
  page.mesh = pageMesh(new THREE.PlaneGeometry(1, 1), material, 256, null);
  page.room = 256;
  ATLAS.scene.add(page.mesh);
  return page;
}
/* A page's instances, room for `room` labels, with what `old` held copied in. */
function pageMesh(geometry, material, room, old) {
  const mesh = new THREE.InstancedMesh(geometry, material, room);
  mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  for (const [name, size] of [['labelUv', 4], ['labelOpacity', 1]]) {
    const attribute = new THREE.InstancedBufferAttribute(new Float32Array(room * size), size)
      .setUsage(THREE.DynamicDrawUsage);
    if (old) attribute.array.set(old.geometry.attributes[name].array);
    geometry.setAttribute(name, attribute);
  }
  if (old) mesh.instanceMatrix.array.set(old.instanceMatrix.array);
  Object.assign(mesh, {frustumCulled: false, count: old ? old.count : 0, renderOrder: 10});
  mesh.raycast = () => {};  // a label is never picked in place of the node
  return mesh;
}
/* A slot w by h on some page, in rows of a height rounded up to ROW_STEP, each row's freed runs taken first. */
function slotFor(w, h) {
  const tall = Math.ceil((h + GUTTER) / ROW_STEP) * ROW_STEP, wide = w + GUTTER;
  if (wide > PAGE || tall > PAGE) return null;
  for (const page of ATLAS.pages) {
    const slot = slotIn(page, wide, tall);
    if (slot) return slot;
  }
  const page = atlasPage(ATLAS.pages.length);
  ATLAS.pages.push(page);
  return slotIn(page, wide, tall);
}
function slotIn(page, wide, tall) {
  for (const row of page.rows) {
    if (row.tall !== tall) continue;
    for (let at = 0; at < row.free.length; at++) {
      const run = row.free[at];
      if (run.wide < wide) continue;
      const slot = {page, row, x: run.x, y: row.y, wide, tall};
      run.x += wide; run.wide -= wide;
      if (!run.wide) row.free.splice(at, 1);
      return slot;
    }
    if (PAGE - row.used >= wide) {
      const slot = {page, row, x: row.used, y: row.y, wide, tall};
      row.used += wide;
      return slot;
    }
  }
  if (PAGE - page.top < tall) return null;
  const row = {y: page.top, tall, used: wide, free: []};
  page.top += tall;
  page.rows.push(row);
  return {page, row, x: 0, y: row.y, wide, tall};
}
function freeSlot(slot) {
  if (!slot) return;
  const free = slot.row.free;
  free.push({x: slot.x, wide: slot.wide});
  free.sort((one, two) => one.x - two.x);
  for (let at = free.length - 1; at > 0; at--) {  // runs side by side made one
    if (free[at - 1].x + free[at - 1].wide === free[at].x) { free[at - 1].wide += free[at].wide; free.splice(at, 1); }
  }
}
/* A repainted label sent alone into its slot of a page the graphics card holds: the label's picture, and nothing
 * over the rest of the slot, as the page holds after `clearRect`, so no part of the label that was there before is
 * drawn beside it. Sent by WebGL itself: three.js's copyTextureToTexture asks the card for five of its settings on
 * every copy, and each ask waits for the card, 17 ms a frame while the map turned (UX 2026-10-17). Its rows count up
 * from the page's foot on the card, where the picture is turned. False when the card holds no copy of the page yet. */
let NOTHING = new Uint8Array(0);  // zeros, grown as a wider strip needs and never shrunk, so a send allocates nothing
function sendSlot(page, slot, canvas, w, h) {
  const renderer = G.renderer(), held = renderer.properties.get(page.texture);
  if (!held.__webglTexture || held.__version !== page.texture.version) return false;
  const gl = renderer.getContext(), state = renderer.state, foot = PAGE - slot.y - slot.tall;
  state.bindTexture(gl.TEXTURE_2D, held.__webglTexture);
  gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, page.texture.flipY);
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, page.texture.premultiplyAlpha);
  gl.pixelStorei(gl.UNPACK_ALIGNMENT, page.texture.unpackAlignment);
  gl.texSubImage2D(gl.TEXTURE_2D, 0, slot.x, PAGE - slot.y - h, gl.RGBA, gl.UNSIGNED_BYTE, canvas);
  const right = slot.wide - w, under = slot.tall - h;
  const need = 4 * Math.max(right * slot.tall, w * under);
  if (NOTHING.length < need) NOTHING = new Uint8Array(need);
  const RGBA = gl.RGBA, BYTE = gl.UNSIGNED_BYTE;
  if (right > 0) gl.texSubImage2D(gl.TEXTURE_2D, 0, slot.x + w, foot, right, slot.tall, RGBA, BYTE, NOTHING);
  if (under > 0) gl.texSubImage2D(gl.TEXTURE_2D, 0, slot.x, foot, w, under, RGBA, BYTE, NOTHING);
  state.unbindTexture();
  return true;
}
/* A label's canvas, just painted, copied into its slot: a new slot when it no longer fits, or fits loosely. */
export function atlasPaint(tag) {
  if (!G) return;
  if (ATLAS.scene !== G.scene()) Object.assign(ATLAS, {pages: [], scene: G.scene()});
  const canvas = tag.texture.image, w = canvas.width, h = canvas.height;
  if (!w || !h) return;
  let slot = tag.slot;
  if (!slot || slot.page !== ATLAS.pages[slot.page.index] || slot.wide < w + GUTTER || slot.tall < h + GUTTER
    || slot.wide > 2 * (w + GUTTER)) {
    if (slot && slot.page === ATLAS.pages[slot.page.index]) freeSlot(slot);
    slot = tag.slot = slotFor(w, h);
    if (!slot) return;
  }
  const page = slot.page;
  page.pen.clearRect(slot.x, slot.y, slot.wide, slot.tall);
  page.pen.drawImage(canvas, slot.x, slot.y);
  // A page the graphics card holds is sent only the label repainted, into its slot, `sendSlot`: the whole 2048 by 2048
  // page sent again for each repaint was 16 MB a frame while the map turned, since labels repaint as their size
  // crosses a sharpness step, and frames came every sixth to eighth refresh (UX 2026-10-17, from 0019ec90). A page the
  // card holds no copy of yet is sent whole once, `atlasDraw`, however many labels it holds by then.
  // Many repainted at once, a branch opened or the names shown again, go with the page sent whole once, as before: an
  // eighth of a page's slots sent one by one in a frame costs more than the page.
  page.spent += slot.wide * slot.tall;
  if (page.dirty || page.spent > PAGE * PAGE / 8 || !sendSlot(page, slot, canvas, w, h)) page.dirty = true;
  // the label's part of its page, half a texel in from each side, so nothing beside it is sampled; the page's rows
  // count down from its top, and up from its foot on the graphics card, where the picture is turned
  tag.uv0 = (slot.x + 0.5) / PAGE; tag.uv1 = (PAGE - slot.y - h + 0.5) / PAGE;
  tag.uvw = (w - 1) / PAGE; tag.uvh = (h - 1) / PAGE;
}
export function atlasDrop(tag) {
  if (tag.slot && tag.slot.page === ATLAS.pages[tag.slot.page.index]) freeSlot(tag.slot);
  tag.slot = null;
}
/* The labels drawn this frame, each sign's place, turn and size, part of its page and opacity, written into its page's
 * instances farthest first; what is sent to the graphics card is sent only when it changed. `order` holds the labels
 * nearest first, as labels.js layers them, `count` of them; `on`, whether names are shown at all. */
const LABEL_MATRIX = new THREE.Matrix4();
const UV4 = new Float32Array(4), ONE = new Float32Array(1);
export function atlasDraw(order, count, on) {
  const pages = ATLAS.pages;
  for (let p = 0; p < pages.length; p++) {
    const page = pages[p];
    page.n = 0;
    page.mesh.visible = on;
    if (page.dirty) { page.texture.needsUpdate = true; page.dirty = false; }
    page.spent = 0;
  }
  for (let i = count - 1; i >= 0; i--) {
    const tag = order[i], sprite = tag.sprite, slot = tag.slot;
    if (!slot || !sprite.visible || tag.hidden || slot.page !== pages[slot.page.index]) continue;
    const page = slot.page;
    if (page.n === page.room) growPage(page);
    const n = page.n++, mesh = page.mesh, attributes = mesh.geometry.attributes;
    LABEL_MATRIX.compose(sprite.position, sprite.quaternion, sprite.scale);
    writeIf(mesh.instanceMatrix, LABEL_MATRIX.elements, n * 16, 16);
    UV4[0] = tag.uv0; UV4[1] = tag.uv1; UV4[2] = tag.uvw; UV4[3] = tag.uvh;
    writeIf(attributes.labelUv, UV4, n * 4, 4);
    ONE[0] = sprite.material.opacity;
    writeIf(attributes.labelOpacity, ONE, n, 1);
  }
  for (let p = 0; p < pages.length; p++) if (pages[p].mesh.count !== pages[p].n) pages[p].mesh.count = pages[p].n;
}
function writeIf(attribute, values, at, size) {
  const array = attribute.array;
  let same = true;
  for (let k = 0; k < size; k++) if (array[at + k] !== Math.fround(values[k])) { same = false; break; }
  if (same) return;
  for (let k = 0; k < size; k++) array[at + k] = values[k];
  attribute.needsUpdate = true;
}
function growPage(page) {
  const old = page.mesh, room = page.room * 2;
  const mesh = pageMesh(old.geometry, old.material, room, old);
  ATLAS.scene.remove(old);
  old.dispose();
  ATLAS.scene.add(mesh);
  page.mesh = mesh;
  page.room = room;
}
