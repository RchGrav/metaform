/* A node's light and color in 3D: its condition, dimming, glass, shapes by artifact type, what is behind the glass
 * and the light a node gives off. From the earlier page's map3d/light.js; the parts of the map an agent's work used,
 * which that file also marked, are not part of this page. */
import '/classic/app/graph/data.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
// drei's transmission material in its vanilla form, the glass itself, VIEW-025. It imports three.js as `three`, which
// the page's import map names as the same file, so both share one three.js.
import {MeshTransmissionMaterial} from '/classic/vendor/drei-vanilla/MeshTransmissionMaterial.js';
import {RoundedBoxGeometry} from 'three/addons/geometries/RoundedBoxGeometry.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {css} from '/classic/app/core/dom.js';
import {S} from '/classic/app/core/reads.js';
import {layerColor} from '/classic/app/header/layers.js';
import {G, nodeSize, wake3d} from '/classic/app/map3d/graph3d.js';

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
/* Every node of the graph is shown. The earlier page hid the part of the map an agent's work used while its agent
 * was unchecked, VIEW-045; agents are not part of this page. */
export const shownNode = () => true;
export const lightOf = node => LIGHTS.find(([condition]) => has(node, condition));
export const has = (node, condition) => (node.work || []).includes(condition);
/* Those the project serves, the elements under `downstream`: the earlier map's CQU, which had the signal colour,
 * a larger ball and, in outer space, a world of its own. */
export const served = node => String(node?.address || '').split('.')[0] === 'downstream';
/* The earlier map gave the signal colour to those the project serves and a colour of its own to the map's entry;
 * here those are the elements under `downstream` and the Definitive element. */
export function colorOf(node) {
  if (node.t === 'el') {
    return served(node) ? css('--signal') : node.role === 'Definitive' ? css('--de') : layerColor(node.layer);
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
  if (material.isMeshPhysicalMaterial) {
    // the face of the glass is clear, and the colour is laid in by absorption along the light's way through it, deeper
    // the farther it goes, as coloured glass is coloured; the light the glass gives off is its own colour
    material.color.copy(WHITE);
    material.attenuationColor.set(color); material.emissive.set(color);
  }
}
const WHITE = new THREE.Color(1, 1, 1);
/* Glass, VIEW-025: in every theme an element is made of a material that obeys reality. Light passes through it and
 * is tinted by it, so the theme's background shows through the node, and it reflects the hall of `environment3d`. It
 * is drei's transmission material: the light behind it is read `samples` times, each color at its own index of
 * refraction, which parts the colors at the edges, `chromaticAberration`; the surface bends it by a noise,
 * `distortion` at `distortionScale`, drifting at `temporalDistortion`; the reads spread along the ray blur it,
 * `anisotropicBlur`. What is behind the glass is drawn by `addBehind`, as drei's own component draws it, with the far
 * wall of every node in it: a node shows its own far wall and the glass behind it, the backside. The values follow
 * drei's own example of the material, the gelatinous cube (2026-10-21): the light let through whole, the surface
 * polished under a clearcoat, the glass about as thick as the node is wide, `thickness` and `attenuationDistance`
 * being shares of the node's radius, and its colour laid in by absorption over a clear face, `colored`; a little
 * light of its own stays, for a node on a dark ground and for the bloom to raise when it is lit, `shine`. The glass
 * is clear: nothing frosts, spreads or bends what is behind it, so a name behind a node is read through it, refracted
 * as a lens refracts, and only the colours part a little at the edge; the person asked for clear glass whose edges
 * are what shows (2026-10-21). One shape serves every node of a size. */
export const GLASS = {transmission: 1, thickness: 1, roughness: 0, ior: 1.5, attenuationDistance: 3,
  clearcoat: 1, clearcoatRoughness: 0, emissiveIntensity: 0.2, metalness: 0, envMapIntensity: 0.9,
  chromaticAberration: 0.02, distortion: 0, distortionScale: 0.3, temporalDistortion: 0, anisotropicBlur: 0,
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
  const made = side => Object.assign(new MeshTransmissionMaterial({samples, _transmission: transmission,
    thickness: thickness * radius, roughness, attenuationDistance: attenuationDistance * radius, chromaticAberration,
    distortion, distortionScale, temporalDistortion, anisotropicBlur}), physical, {side});
  // The near wall reads the picture with every far wall in it. The far wall is a material of its own, since three.js
  // keeps a material's program when only its side changes; it shares every setting of the near wall but the picture
  // it reads, which is the scene with no glass in it.
  const material = made(THREE.FrontSide), back = made(THREE.BackSide);
  // drei's compile writes USE_TRANSMISSION into the material's own defines, after three.js has keyed the shader by
  // them, so the next key named another shader and the glass was linked twice; given here, its shader is linked once,
  // ahead of the frame, `warm3d`
  for (const one of [material, back]) one.defines.USE_TRANSMISSION = '';
  material.uniforms.time = DRIFT;
  material.uniforms.buffer.value = BEHIND.main?.texture ?? null;
  back.uniforms = {...material.uniforms, buffer: {value: BEHIND.back?.texture ?? null}};
  // each wall reads the depth of the picture it reads, for the fade by depth, `fading`
  material.uniforms.bufferDepth = {value: BEHIND.main?.depthTexture ?? null};
  back.uniforms.bufferDepth = {value: BEHIND.back?.depthTexture ?? null};
  const camera = G.camera();
  for (const one of [material, back]) {
    one.uniforms.behindNear = {value: camera.near};
    one.uniforms.behindFar = {value: camera.far};
    fading(one);
  }
  material.userData.back = back;
  back.userData.front = material;
  material.userData.own = true;
  colored(material, colorOf(node));
  return new THREE.Mesh(nodeShape(node, radius), material);
}
/* The fade of what is seen through the glass by its depth in it (2026-10-21): the light from a thing inside or behind
 * a node travels through the glass from where the thing is to the wall that reads it, not the node's whole thickness,
 * so a line that enters a node is clear where it enters and fades into the glass's colour as it goes deeper, and what
 * lies behind the node has travelled the whole thickness. The depth of the picture behind the glass is kept beside
 * it, `bufferDepth`, and read at the refracted point; drei's shader is given the way travelled in place of the
 * thickness where it applies the absorption. */
const FADE_HEAD = 'uniform sampler2D buffer;';
const FADE_UNIFORMS = `${FADE_HEAD} uniform sampler2D bufferDepth; uniform float behindNear; uniform float behindFar;
      float seenViewZ( const in vec2 at ) {
        float depth = texture2D( bufferDepth, at ).x;
        return -( behindNear * behindFar ) / ( ( behindFar - behindNear ) * depth - behindFar );
      }`;
const FADE_AT = 'vec3 attenuatedColor = applyVolumeAttenuation( transmittedLight.rgb, length( transmissionRay ), '
  + 'attenuationColor, attenuationDistance );';
const FADE_BY = `float hereZ = -( viewMatrix * vec4( position, 1.0 ) ).z;
            float travelled = clamp( seenViewZ( refractionCoords ) - hereZ, 0.0, length( transmissionRay ) );
            vec3 attenuatedColor = applyVolumeAttenuation( transmittedLight.rgb, travelled, attenuationColor, attenuationDistance );`;
function fading(material) {
  const theirs = material.onBeforeCompile;
  material.onBeforeCompile = (shader, renderer) => {
    theirs(shader, renderer);
    shader.fragmentShader = shader.fragmentShader.replace(FADE_HEAD, FADE_UNIFORMS).replace(FADE_AT, FADE_BY);
  };
}
/* What is behind the glass, drawn as drei's component draws it, once for every node, VIEW-025: the scene with the
 * glass hidden, into `back`; then with the far wall of every node, which reads `back`, into `main`; and the near walls
 * read `main` in the frame itself. Both are drawn at `scale` of the view's size, drei's `resolution` and
 * `backsideResolution`, the whole of it since 2026-10-21, as drei's example draws them. It runs before the frame in the graph's own render chain. The two pictures are drawn again
 * only on a frame where something of the map seen through the glass changed, `behindChanged`: drawn every frame they
 * took two of the frame's three drawings of the whole scene. What moves over the map without end is left out of
 * them, so it never makes them be drawn again: the flow's dots, light added over the map, and what walks or floats
 * about it, the agents' figures, the mascot, their speech bubbles and a wave's dots. Seen through a node's frosted
 * and tinted glass these hardly showed; a figure behind a node is now hidden by it. `drawn` counts the pictures. */
export const BEHIND = {back: null, main: null, scale: 1, kept: null, stale: true, drawn: 0};
const FAR_WALL = 0.6;  // how much of a far wall is its own, the rest what is drawn behind it in its picture
export function addBehind() {
  const composer = G.postProcessingComposer();
  if (!composer?.insertPass) return;
  const type = THREE.HalfFloatType;  // light over full brightness, seen through glass, is still spread by the bloom
  BEHIND.back = new THREE.WebGLRenderTarget(1, 1, {type});
  BEHIND.main = new THREE.WebGLRenderTarget(1, 1, {type});
  for (const target of [BEHIND.back, BEHIND.main]) target.depthTexture = new THREE.DepthTexture(1, 1);  // sized with it
  composer.insertPass({isPass: true, enabled: true, needsSwap: false, clear: false, renderToScreen: false,
    setSize: sizeBehind, render: drawBehind, dispose() { BEHIND.back.dispose(); BEHIND.main.dispose(); }}, 0);
}
function sizeBehind(width, height) {
  const size = [Math.max(1, Math.round(width * BEHIND.scale)), Math.max(1, Math.round(height * BEHIND.scale))];
  BEHIND.back.setSize(...size);
  BEHIND.main.setSize(...size);
  BEHIND.stale = true;
}
function drawBehind(renderer) {
  const scene = G.scene(), camera = G.camera(), glass = [], was = renderer.getRenderTarget();
  scene.traverseVisible(object => { if (object.material?.userData?.back) glass.push(object); });
  if (!glass.length) return;
  // Everything but the glass itself is in its pictures: the map, its labels, the agents' figures and the mascot, so
  // all of it is read through the glass (2026-10-21). A figure that moves draws the pictures again, as the camera
  // moving does.
  if (!behindChanged(scene, camera)) return;
  BEHIND.drawn++;
  for (const object of glass) object.visible = false;
  renderer.setRenderTarget(BEHIND.back);
  renderer.render(scene, camera);
  // The far wall takes the node's tint; a lit node's light leaves its glass outward, by its near wall alone.
  for (const object of glass) {
    const near = object.material, far = near.userData.back;
    far.color.copy(near.color);
    // A far wall is drawn over the far walls behind it blended at FAR_WALL, and gives off the glass's own little
    // light, never a lit node's, so a node behind a node shows through it, its colour by that light, as the two
    // pictures cannot hold it otherwise; the node's own far wall adds that little to its body (2026-10-21).
    Object.assign(far, {emissiveIntensity: Math.min(near.emissiveIntensity, GLASS.emissiveIntensity),
      opacity: FAR_WALL, transparent: true});
    Object.assign(object, {material: far, visible: true});
  }
  renderer.setRenderTarget(BEHIND.main);
  renderer.render(scene, camera);
  for (const object of glass) object.material = object.material.userData.front;
  renderer.setRenderTarget(was);
}
/* The room the glass reflects, VIEW-025: three.js's room environment, a plain room with soft lights in its walls and
 * ceiling, made once into the scene's environment through PMREM, so every physical material in the scene, the glass
 * first, takes its reflections and its light from it: the lights of the room are what a node's highlights and bright
 * rim are, as a studio's lights are in a picture of glass and polished things. It is made here from nothing and never
 * shown itself: each theme keeps its own ground, VIEW-023. */
export function environment3d() {
  const renderer = G.renderer(), scene = G.scene(), pmrem = new THREE.PMREMGenerator(renderer), room = new RoomEnvironment();
  scene.environment = pmrem.fromScene(room, 0.04).texture;
  room.traverse(part => { part.geometry?.dispose(); part.material?.dispose(); });
  pmrem.dispose();
  BEHIND.stale = true;
}
/* A part of the map, seen through the glass: the graph's nodes and links, the labels, the page's batches of fibers
 * and nodes, and the lights. */
/* Whether anything of the map seen through the glass changed since the pictures were drawn: the camera, and every
 * part of the map, where it is, how it is turned and sized, whether it is shown, its color, light and opacity, a
 * label's picture, a batch's instances. Each value is kept in a row and the row compared with the last one drawn. */
const KEEP = {values: new Float64Array(4096), n: 0};
const keep = value => {
  if (KEEP.n === KEEP.values.length) {
    const grown = new Float64Array(KEEP.values.length * 2);
    grown.set(KEEP.values);
    KEEP.values = grown;
  }
  KEEP.values[KEEP.n++] = value;
};
function keepObject(object) {
  const {position: p, quaternion: q, scale: s} = object;
  keep(p.x); keep(p.y); keep(p.z); keep(q.x); keep(q.y); keep(q.z); keep(q.w); keep(s.x); keep(s.y); keep(s.z);
  keep(object.boundingSphere ? 1 : 0);  // drawn by a batch, `nodes3d`
  const material = object.material;
  if (material && !Array.isArray(material)) {
    if (material.color) { keep(material.color.r); keep(material.color.g); keep(material.color.b); }
    if (material.emissive) { keep(material.emissive.r); keep(material.emissive.g); keep(material.emissive.b); }
    keep(material.emissiveIntensity ?? 0); keep(material.opacity); keep(material.map?.version ?? 0);
  }
  // the label atlas: its pages' pictures and its quads, so a label repainted or moved is drawn again through the glass
  if (Array.isArray(material)) for (const one of material) keep(one.map?.version ?? 0);
  if (object.isInstancedMesh) {
    keep(object.count); keep(object.instanceMatrix.version); keep(object.instanceColor?.version ?? 0);
  }
  if (object.isInstancedMesh || object.userData.atlas === true) {
    for (const attribute of Object.values(object.geometry.attributes)) keep(attribute.version);
  }
  if (object.isLight) { keep(object.intensity); keep(object.color.r); keep(object.color.g); keep(object.color.b); }
}
function behindChanged(scene, camera) {
  KEEP.n = 0;
  for (const value of camera.matrixWorld.elements) keep(value);
  for (const value of camera.projectionMatrix.elements) keep(value);
  if (scene.background?.isColor) { keep(scene.background.r); keep(scene.background.g); keep(scene.background.b); }
  for (const child of scene.children) if (child.visible) child.traverseVisible(keepObject);
  const kept = BEHIND.kept, n = KEEP.n;
  let same = !BEHIND.stale && kept && kept.length === n;
  for (let i = 0; same && i < n; i++) same = kept[i] === KEEP.values[i];
  if (same) return false;
  BEHIND.kept = KEEP.values.slice(0, n);
  BEHIND.stale = false;
  return true;
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
