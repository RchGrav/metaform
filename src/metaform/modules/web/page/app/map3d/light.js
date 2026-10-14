/* A node's light and color in 3D: its condition, the work in use, dimming, glass, shapes by artifact type, what is
 * behind the glass and the light a node gives off. */
import '/page/app/figures/roam2d.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
// drei's transmission material in its vanilla form, the glass itself, VIEW-025. It imports three.js as `three`, which
// the page's import map names as the same file, so both share one three.js.
import {MeshTransmissionMaterial} from '/vendor/drei-vanilla/MeshTransmissionMaterial.js';
import {RoundedBoxGeometry} from 'three/addons/geometries/RoundedBoxGeometry.js';
import {css} from '/page/app/core/dom.js';
import {S} from '/page/app/core/reads.js';
import {layerColor} from '/page/app/header/layers.js';
import {ticketNode} from '/page/app/figures/agents.js';
import {G, nodeSize, wake3d} from '/page/app/map3d/graph3d.js';
import {M} from '/page/app/map2d/build.js';
import {D, ticketOf} from '/page/app/agents/dispatch.js';

/* A part's light, VIEW-035 and MAP-046: broken flashes red. Flashing lets the node's own
 * color show between flashes, and each step filed makes it faster: from FLASH.slow a beat while it waits, to
 * FLASH.fast as the steps planned are filed, or a little faster with each step when none were planned. */
const LIGHTS = [['broken', '--broken'], ['trouble', '--broken']];  // the one fault a built part can have, MAP-046
const FLASH = {slow: 1.2, fast: 0.24, step: 0.35};
export function paceOf(node) {
  const done = S.progress?.get(node.id);
  if (!done || !done.filed) return FLASH.slow;
  const share = done.planned ? Math.min(1, done.filed / done.planned) : 1 - 1 / (1 + FLASH.step * done.filed);
  return FLASH.slow + (FLASH.fast - FLASH.slow) * share;
}
/* The part of the map each agent's work is using, VIEW-045: the node of the ticket it took, until work claims reserve
 * wider areas, LAYER-029. Checked beside the agent it shows in white; unchecked it is hidden, so the rest of the map
 * can be reviewed without it. `parts` holds node id → true when shown, false when hidden. */
export const INUSE = {off: new Set(), parts: new Map(), preview: new Set()};
/* The element ids of addresses, as the map holds them. */
export function idsAt(addresses) {
  const wanted = new Set(addresses || []);
  return [...S.elements.values()].filter(entry => wanted.has(entry.element.address)).map(entry => entry.element.id);
}
export function paintInUse() {
  const parts = partsInUse();
  const same = parts.size === INUSE.parts.size && [...parts].every(([id, shown]) => INUSE.parts.get(id) === shown);
  INUSE.parts = parts;
  if (G && !same) G.nodeColor(G.nodeColor()).nodeVisibility(G.nodeVisibility()).linkVisibility(G.linkVisibility());
  for (const [id, node] of M.base?.nodes || []) {
    node.g.classList.toggle('inuse', parts.get(id) === true);
    node.g.classList.toggle('reserved', parts.get(id) === false);
  }
  for (const edge of M.base?.edges || []) {
    const hidden = parts.get(edge.join.receiver) === false || parts.get(edge.provider) === false;
    edge.path?.classList.toggle('reserved', hidden);
  }
}
/* Each node some running agent's work uses, shown or hidden as its agent is checked, and a proposal's reach. */
function partsInUse() {
  const parts = new Map();
  for (const one of D.sessions) {
    const ticket = one.state === 'running' ? ticketOf(one.work_id) : null;
    if (!ticket || !ticket.taken || ticket.done) continue;
    const shown = !INUSE.off.has(one.work_id);
    // a ticket inside an active work claim is using all the claim reserves, LAYER-029; else the node it is on
    const held = (D.claims || []).find(claim => claim.state === 'active' && claim.work.includes(one.work_id));
    for (const node of held ? [ticketNode(ticket), ...idsAt(held.nodes)] : [ticketNode(ticket)]) {
      parts.set(node, parts.get(node) === true || shown);
    }
  }
  for (const node of INUSE.preview) parts.set(node, true);  // a proposal's reach, shown while it is reviewed
  return parts;
}
export const shownNode = node => INUSE.parts.get(typeof node === 'object' ? node.id : node) !== false;
export const lightOf = node => LIGHTS.find(([condition]) => has(node, condition));
export const has = (node, condition) => (node.work || []).includes(condition);
export function colorOf(node) {
  if (INUSE.parts.get(node.id) === true) return css('--in-use');  // the part an agent's work is using, VIEW-045
  if (node.t === 'el') {
    return node.role === 'CQU' ? css('--signal') : node.role === 'DE' ? css('--de') : layerColor(node.layer);
  }
  if (node.t === 'purpose') return css('--text');
  return layerColor(node.layer);
}
/* The color an object has apart from any condition. */
export const ownColor = node => colorOf({...node, work: []});
/* A dimmed node keeps its own hue: its color with part of the background mixed in, the share set by the theme. */
export function dim(color) {
  const keep = Number(css('--dim-keep')), back = channelsOf(css('--ground'));
  const mixed = (own, at) => Math.round(keep * own + (1 - keep) * back[at]).toString(16).padStart(2, '0');
  return '#' + channelsOf(color).map(mixed).join('');
}
const channelsOf = hex => [1, 3, 5].map(at => parseInt(hex.slice(at, at + 2), 16));
export const dimmed = node => S.selected && node.t === 'el' && node.id !== S.selected && !S.neighbors.has(node.id);
/* A node's color, given to whatever it is made of: glass takes it as its tint, as the color light takes on inside
 * it, and as the light it gives off. */
export function colored(material, color) {
  material.color.set(color);
  if (material.isMeshPhysicalMaterial) { material.attenuationColor.set(color); material.emissive.set(color); }
}
/* Glass, VIEW-025: in every theme an element is made of a material that obeys reality. Light passes through it and
 * is tinted by it, so the theme's background shows through the node. It gives off a little of its own color, since
 * clear glass on a dark background with nothing to reflect shows as black. It is drei's transmission material: the
 * light behind it is read `samples` times, each color at its own index of refraction, which parts the colors at the
 * edges, `chromaticAberration`; the surface bends it by a noise, `distortion` at `distortionScale`, drifting at
 * `temporalDistortion`; the reads spread along the ray blur it, `anisotropicBlur`. What is behind the glass is drawn
 * by `addBehind`, as drei's own component draws it, with the far wall of every node in it: a node shows its own far
 * wall and the glass behind it, the backside. The drei values are a start and are not settled: with the frosting and
 * the absorption above, what is behind a node is blurred and tinted almost to its own color, so they hardly show. One
 * shape serves every node of a size. */
export const GLASS = {transmission: 0.7, thickness: 9, roughness: 0.3, ior: 1.35, attenuationDistance: 7,
  clearcoat: 0.6, clearcoatRoughness: 0.25, emissiveIntensity: 0.45, metalness: 0,
  chromaticAberration: 0.06, distortion: 0.25, distortionScale: 0.35, temporalDistortion: 0.1, anisotropicBlur: 0.1,
  samples: 6};
export const DRIFT = {value: 0};  // the one clock the distortion of every node drifts by; still with reduced motion
export const shapes = new Map();
let SEGMENTS = 16;  // as the graph draws its own nodes; 32 halves the frame rate where there is no graphics card
export function setSegments(value) { SEGMENTS = value; }  // a binding written from another part goes through its own
export const isGlass = node => node.t === 'el';
const ballShape = radius => shapes.get(radius)
  || shapes.set(radius, new THREE.SphereGeometry(radius, SEGMENTS, SEGMENTS)).get(radius);
/* An element's shape tells its artifact type, the first segment of its address, before any text is read, P042: code a
 * box, a document a page, media a screen, data a cylinder, a collection a stack, upstream a cone pointing up, toward
 * what feeds the project, and downstream one pointing down, toward who it serves. Each is about the size of the sphere
 * it replaces, so sizes still compare; anything else stays a sphere. The web_node_shapes setting turns them off. The 2D
 * map draws the same types as Mermaid shapes, SHAPES2D. One shape serves every node of a type and size. */
export const VIEW_SETTINGS = {shapes: true};
const TYPE_ROOTS = ['code', 'document', 'media', 'data', 'collection', 'upstream', 'downstream'];
export const typeOf = node => {
  const root = String(node?.address || '').split('.')[0];
  return VIEW_SETTINGS.shapes && TYPE_ROOTS.includes(root) ? root : null;
};
function stacked(parts) {
  const loose = parts.map(part => part.index ? part.toNonIndexed() : part);
  const merged = new THREE.BufferGeometry();
  for (const name of ['position', 'normal', 'uv']) {
    const size = loose[0].getAttribute(name).itemSize;
    const all = new Float32Array(loose.reduce((sum, part) => sum + part.getAttribute(name).array.length, 0));
    let at = 0;
    for (const part of loose) {
      all.set(part.getAttribute(name).array, at);
      at += part.getAttribute(name).array.length;
    }
    merged.setAttribute(name, new THREE.BufferAttribute(all, size));
  }
  return merged;
}
/* Each artifact type's shape at radius `r`, `box` a rounded box in shares of it. */
const TYPE_SHAPES = {
  code: (r, box) => box(1.55, 1.55, 1.55),
  document: (r, box) => box(1.35, 1.85, 0.45),
  media: (r, box) => box(2.05, 1.3, 0.35),
  data: r => new THREE.CylinderGeometry(r, r, 1.5 * r, SEGMENTS),
  collection: (r, box) => stacked([-0.62, 0, 0.62].map(y => box(1.8, 0.42, 1.8).translate(0, y * r, 0))),
  upstream: r => new THREE.ConeGeometry(1.1 * r, 1.9 * r, SEGMENTS),
  downstream: r => new THREE.ConeGeometry(1.1 * r, 1.9 * r, SEGMENTS).rotateX(Math.PI),
};
function typeShape(type, radius) {
  const key = `${type}:${radius}`;
  if (shapes.has(key)) return shapes.get(key);
  const r = radius, box = (w, hh, d) => new RoundedBoxGeometry(w * r, hh * r, d * r, 2, Math.min(w, hh, d) * r * 0.2);
  const made = TYPE_SHAPES[type]?.(r, box) ?? null;
  shapes.set(key, made);
  return made;
}
export const nodeShape = (node, radius) => (typeOf(node) && typeShape(typeOf(node), radius)) || ballShape(radius);
/* The shapes turned on or off: each element's node drawn again in its shape. */
export function shapes3d() {
  if (!G) return;
  for (const node of G.graphData().nodes) {
    const object = node.__threeObj;
    if (object?.isMesh && isGlass(node)) object.geometry = nodeShape(node, Math.cbrt(nodeSize(node)) * 3);
  }
  wake3d();
}
export function bead(node) {
  const radius = Math.cbrt(nodeSize(node)) * 3;  // as the graph sizes a node: the cube root of its value, times 3

  const {transmission, thickness, roughness, attenuationDistance, chromaticAberration, distortion, distortionScale,
    temporalDistortion, anisotropicBlur, samples, ...physical} = GLASS;
  // drei's amount of light let through is `_transmission`; three.js's own `transmission` stays 0, since the page
  // draws what is behind the glass itself.
  const made = side => Object.assign(new MeshTransmissionMaterial({samples, _transmission: transmission, thickness,
    roughness, attenuationDistance, chromaticAberration, distortion, distortionScale, temporalDistortion,
    anisotropicBlur}), physical, {side});
  // The near wall reads the picture with every far wall in it. The far wall is a material of its own, since three.js
  // keeps a material's program when only its side changes; it shares every setting of the near wall but the picture
  // it reads, which is the scene with no glass in it.
  const material = made(THREE.FrontSide), back = made(THREE.BackSide);
  material.uniforms.time = DRIFT;
  material.uniforms.buffer.value = BEHIND.main?.texture ?? null;
  back.uniforms = {...material.uniforms, buffer: {value: BEHIND.back?.texture ?? null}};
  material.userData.back = back;
  back.userData.front = material;
  material.userData.own = true;
  colored(material, colorOf(node));
  return new THREE.Mesh(nodeShape(node, radius), material);
}
/* What is behind the glass, drawn each frame as drei's component draws it, once for every node, VIEW-025: the scene
 * with the glass hidden, into `back`; then with the far wall of every node, which reads `back`, into `main`; and the
 * near walls read `main` in the frame itself. Both are drawn at `scale` of the view's size, drei's `resolution` and
 * `backsideResolution`. It runs before the frame in the graph's own render chain. */
export const BEHIND = {back: null, main: null, scale: 0.5};
export function addBehind() {
  const composer = G.postProcessingComposer();
  if (!composer?.insertPass) return;
  const type = THREE.HalfFloatType;  // light over full brightness, seen through glass, is still spread by the bloom
  BEHIND.back = new THREE.WebGLRenderTarget(1, 1, {type});
  BEHIND.main = new THREE.WebGLRenderTarget(1, 1, {type});
  composer.insertPass({isPass: true, enabled: true, needsSwap: false, clear: false, renderToScreen: false,
    setSize: sizeBehind, render: drawBehind, dispose() { BEHIND.back.dispose(); BEHIND.main.dispose(); }}, 0);
}
function sizeBehind(width, height) {
  const size = [Math.max(1, Math.round(width * BEHIND.scale)), Math.max(1, Math.round(height * BEHIND.scale))];
  BEHIND.back.setSize(...size);
  BEHIND.main.setSize(...size);
}
function drawBehind(renderer) {
  const scene = G.scene(), camera = G.camera(), glass = [], was = renderer.getRenderTarget();
  scene.traverseVisible(object => { if (object.material?.userData.back) glass.push(object); });
  if (!glass.length) return;
  for (const object of glass) object.visible = false;
  renderer.setRenderTarget(BEHIND.back);
  renderer.render(scene, camera);
  // The far wall takes the node's tint and gives off no light toward the eye: a node's light leaves its glass
  // outward, so the far wall's light goes away from the eye, and the node is as bright as its near wall makes it.
  for (const object of glass) {
    const near = object.material, far = near.userData.back;
    far.color.copy(near.color);
    Object.assign(far, {emissiveIntensity: 0, opacity: near.opacity, transparent: near.transparent});
    Object.assign(object, {material: far, visible: true});
  }
  renderer.setRenderTarget(BEHIND.main);
  renderer.render(scene, camera);
  for (const object of glass) object.material = object.material.userData.front;
  renderer.setRenderTarget(was);
}
/* The light a node gives off, VIEW-029: the glass's own little light, VIEW-025, raised toward LIGHT in the given
 * color by `lit`, from 0 to 1. Above full brightness it is spread by the bloom pass past the node's outline, behind
 * whatever is nearer the eye. A node the graph draws itself, a join's purpose node, gives off none of its own. */
const LIGHT = 2.6;  // the light a node gives off when it is lit, chosen by eye; full brightness on a screen is 1
export function shine(material, color, lit) {
  if (!material.emissive) return;
  const own = material.isMeshPhysicalMaterial ? GLASS.emissiveIntensity : 0;
  if (lit > 0 && color) material.emissive.set(color);
  material.emissiveIntensity = own + (LIGHT - own) * lit;
}
