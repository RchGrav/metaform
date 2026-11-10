/* Ultra graphics, the Space theme (the web module's web_theme setting at space): the 3D map drawn as outer space. U switches between it and
 * clean, the map as it is drawn without it; the 2D map is never changed.
 *
 * What it draws, and why each part looks as it does:
 *  - The sky: a deep starfield in three layers, each a little nearer than the one behind, so the stars move against
 *    each other as the camera moves; a faint band of the galaxy across it; and behind them a nebula, painted once into
 *    a picture of the whole sky when ultra first starts, so it costs nothing to draw. Nothing is loaded: every star
 *    and every cloud is made here from a fixed seed, so the sky is the same on every load.
 *  - The elements, as celestial bodies, one kind for each artifact type, the first segment of the address, so the
 *    type is told at a glance as the shapes tell it in clean, by its outline first, since across the whole map a body
 *    is a few pixels wide: code a rocky world, lumpy and faceted; a document a gas giant, wide and flattened, whose few
 *    broad bands run like lines of text; media a ringed planet; data a crystal, a tall double point; a collection a
 *    planet with three bright moons close around it; upstream a pulsar whose jets send; downstream a dark body drawing
 *    in a disk. The DE is a star, which lights every planet from where it is; a CQU an inhabited world whose night side
 *    carries city lights. Every body keeps its node's map color as its own, and the page colors, dims, flashes and
 *    pulses it as it does the glass; a body that signals keeps its surface, and its signal glows as its atmosphere.
 *  - The selection: the selected body is ringed by a fine orbit of light and glows, both held to a size that is seen
 *    from across the whole map and never fills the view up close; the bodies away from it, the ones the page dims,
 *    recede grey and dark, so the selection and what it joins lead.
 *  - The small leaves, a part's items and properties, as moons; a join's purpose vertex as a small bright bead.
 *  - The joins as luminous filaments: light added to the sky, bright along their middle and gone at their edges.
 *  - Bloom, its own pass at the end of the render chain while ultra is on: what is over full brightness spreads into a
 *    soft glow that stays close to it, the wide levels of the glow weighed less than the near ones. The selected
 *    node's atmosphere rises over full brightness, as do the star's middle, the flow's dots and bursts, and the agents'
 *    lights, so they glow; the filaments, the nebula and the labels stay under it, so the map is never hazy, the space
 *    behind every name stays dark and every name stays crisp.
 *  - The flow, its requests and data, reads as comets and light: the flow's own materials are raised over full
 *    brightness here, and the bloom does the rest. The flow's code is not touched.
 *
 * Motion: the stars drift and twinkle, the nebula turns, moons orbit and the disk and the star's surface churn only
 * while the map draws frames, by the time that passed, so an idle map still rests as the frame budget says, and they
 * never jump when it wakes. With reduced motion none of it moves and the sky holds still as the camera turns.
 * Switching fades through the dark of space and back, never a cut.
 * Quality: while ultra is drawn the frame rate is measured over the frames the map draws one after another, however
 * long each takes, so the slowest machine is measured too; held under 40 frames a second for three seconds, the
 * bloom is drawn smaller and the sky holds fewer stars, one step at a time, and quietly.
 * The setting: U switches it and keeps it; a change on the Settings screen, or with `metaform set --web-graphics`
 * while the page is open, fades the map over too, the second as the page comes back into focus. */
import * as THREE from 'three';
import {FullScreenQuad} from 'three/addons/postprocessing/Pass.js';

const SPACE = '#010208';  // the dark of space, behind the nebula and the veil a switch fades through
const TYPE_ROOTS = ['code', 'document', 'media', 'data', 'collection', 'upstream', 'downstream'];
/* Each kind of body, by the number its shader is compiled with. */
const KIND = {plain: 0, rocky: 1, banded: 2, ringed: 3, crystal: 4, system: 5, pulsar: 6, sink: 7, star: 8, world: 9,
  moon: 10, knot: 11};
const BY_TYPE = {code: 'rocky', document: 'banded', media: 'ringed', data: 'crystal', collection: 'system',
  upstream: 'pulsar', downstream: 'sink'};
/* The steps quality comes down by while the frame rate stays low: how large the bloom is drawn, as a share of the
 * picture, through how many levels it spreads, the share of the stars drawn, and whether the sky moves. */
const QUALITY = [
  {bloom: 0.5, levels: 6, stars: 1, drift: true},
  {bloom: 0.5, levels: 5, stars: 0.66, drift: true},
  {bloom: 1 / 3, levels: 5, stars: 0.42, drift: true},
  {bloom: 0.25, levels: 4, stars: 0.25, drift: false}];
/* The fps under which it steps down, over how long, and a gap between two frames long enough to be a stall, a
 * hidden tab or a machine asleep, rather than a frame. */
const GOVERNOR = {low: 40, span: 3000, stall: 4000};
const STAR_COUNT = 9000;
const LOOK = {gain: 3, bloom: 0.62, spread: 0.6, vignette: 0.16, reveal: 1600};  // chosen by eye

const U = {
  G: null, ctx: null, mode: 'clean', drawn: 'clean', wanted: null, turn: 0, quality: 0,
  clock: 0, last: 0, reveal: 1, revealFrom: 0, sky: null, pass: null, veil: null,
  shared: {time: {value: 0}, sun: {value: new THREE.Vector3()}, sunOn: {value: 0}},
  gain: {value: 1}, patched: new WeakSet(), shapes: new Map(), sprites: new Map(),
  measure: {time: 0, frames: 0, last: 0, chained: false, fps: 0, steps: 0}, frames: 0, ease: null, saved: null,
  saving: 0, view: {perPixel: 0, camera: null},
};

/* ---------- what the page calls ---------- */

/* Called once the 3D map is made, with the graph and what ultra needs of the page: `wake(ms)` draws frames for that
 * long, `reduced()`, `css(name)`, the `selected()` and `hovered()` ids, `dimmed(node)` whether a node is away from
 * the selection, `idle()` whether the map is drawing only its slow idle frames, `chained()` whether the frame just
 * drawn asked for the next one straight after it, `toast(text)`, `save(mode)` to keep the setting, `settings()` the
 * folder's settings as the page reads them, `shapes()` whether elements are drawn by their type,
 * web_node_shapes, and `linked()` a promise of the shaders being linked. */
export function attach(graph, context) {
  U.G = graph;
  U.ctx = context;
  U.pass = makePass(graph);
  U.veil = Object.assign(document.createElement('div'), {className: 'ultra-veil'});
  Object.assign(U.veil.style, {position: 'absolute', inset: '0', pointerEvents: 'none', opacity: '0', zIndex: '1',
    background: SPACE});
  U.veil.setAttribute('aria-hidden', 'true');
  graph.renderer().domElement.parentElement?.append(U.veil);
  // a tab put away is no frame to measure; and the setting changed elsewhere, as with metaform set, is taken up as
  // the page is looked at again
  document.addEventListener('visibilitychange', () => {
    U.measure.chained = false;
    if (document.visibilityState === 'visible') reread();
  });
  window.addEventListener('focus', reread);
  // a map with nothing drawn yet starts in the look asked for: there is nothing to fade from, and drawing clean first
  // linked every shader of both looks at load
  if (U.wanted === 'ultra' && !graph.graphData().nodes.length) { U.mode = 'ultra'; apply('ultra'); }
  else if (U.wanted) setting(U.wanted);
}
/* The setting as read with the project's view settings, or as changed on the Settings screen: the map is drawn in it,
 * fading over when it changes. */
export function setting(value) {
  const mode = value === 'ultra' ? 'ultra' : 'clean';
  U.wanted = mode;
  if (U.G && mode !== U.mode) show(mode);
}
/* The setting read again, as the page comes back into view, so a change made with the command line while the page
 * was open shows; never while U's own change is still being kept, which would read the value before it. */
async function reread() {
  return;  // the page's theme decides the look now (space is outer space, any other theme clean), never a reread setting
  if (!U.ctx?.settings || U.saving) return;
  let rows = [];
  try { rows = await U.ctx.settings(); } catch { return; }
  const value = rows.find(row => row.key === 'web_graphics')?.value;
  if (value !== undefined && !U.saving) setting(value);
}
/* The other look, kept as the theme, web_theme, so every page and reload opens in it. */
export async function toggle() {
  const mode = U.mode === 'ultra' ? 'clean' : 'ultra';
  U.wanted = mode;
  show(mode);
  U.ctx?.toast(mode === 'ultra' ? 'Ultra graphics: the map in outer space. U for clean.' : 'Clean graphics. U for ultra.');
  U.saving++;
  let done;
  try { done = await U.ctx?.save(mode); } finally { U.saving--; }
  if (done && !done.ok) U.ctx.toast(done.body?.error || 'The graphics setting was not saved; this page keeps it until reload.');
}
/* The key, an entry of the page's key table, `KEYS`, which runs it and lists it in the reference ? opens, beside S
 * and L, the 3D map's other looks. */
export const KEY = {group: 'Modes', keys: ['U'], what: 'Ultra graphics: the 3D map in outer space, or clean, fading between them',
  match: ['u', 'U'], run: () => toggle()};
/* Whether the map is drawn in ultra: the graph's own bloom rests while it is, since ultra's takes its place. */
export const on = () => U.drawn === 'ultra';
/* What a node is drawn as in ultra, or null in clean, where the page draws it as before. */
export function body(node) {
  if (U.drawn !== 'ultra' || !U.G) return null;
  return makeBody(node);
}
/* A join's look in ultra, a filament of light, or null in clean: its color and how strongly it shines, a quiet one, a
 * link of the tree, a layer or an item, at half. The page draws it with FILAMENT, `fibers3d`. */
export function fiber(link) {
  if (U.drawn !== 'ultra' || !U.G) return null;
  const quiet = link.k === 'tree' || link.k === 'layer' || link.k === 'item';
  return {color: U.G.linkColor()(link), strength: quiet ? 0.5 : 0.95};
}
/* For the browser checks: the look drawn, the quality step, the frame rate last measured, and the sky's own clock,
 * which stands still with reduced motion. */
export const stats = () => ({mode: U.mode, drawn: U.drawn, quality: U.quality, fps: Math.round(U.measure.fps * 10) / 10,
  steps: U.measure.steps, stars: U.sky ? U.sky.shown : 0, bloom: Boolean(U.pass?.enabled), frames: U.frames,
  clock: Math.round(U.clock * 1000) / 1000});
/* Where a node is in the 3D map, what it is drawn as and how much of the page's signal light it carries now, for the
 * browser checks that look at one body up close. */
export function at(id) {
  const node = U.G?.graphData().nodes.find(item => item.id === id), object = node?.__threeObj;
  return node ? {x: node.x, y: node.y, z: node.z, kind: object?.userData.kind ?? null,
    signal: object?.material?.emissiveIntensity ?? 0} : null;
}
/* Steps the quality to a given step, for the browser checks and for a person who wants it lower than measured. */
export function quality(step) { setQuality(Math.max(0, Math.min(QUALITY.length - 1, step))); }

/* The page's work for each frame, run before the scene is drawn: the sky follows the camera, the bodies take the
 * selection and the star's light, moons orbit, and the frame rate is measured. Costs nothing in clean. */
export function frame(now, data) {
  if (!U.G) return;
  const passed = Math.min(0.1, Math.max(0, (now - (U.last || now)) / 1000));
  U.last = now;
  if (U.drawn !== 'ultra') return;
  U.frames++;
  const reduce = U.ctx.reduced(), moving = !reduce && QUALITY[U.quality].drift;
  if (moving) U.clock += passed;
  U.shared.time.value = U.clock;
  governor(now);
  const camera = U.G.camera(), scene = U.G.scene();
  // the world's size of one pixel at a distance of one, for what is held to a size on the screen
  const tall = U.ctx.stage.height || 1;  // the area's size as last observed, `STAGE`: no layout read a frame
  U.view.camera = camera;
  U.view.perPixel = camera.isPerspectiveCamera ? 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2) / tall : 0;
  if (scene.background !== U.sky.ground) scene.background = U.sky.ground;
  patchFlow(scene);
  // the sky fades in after a switch, on the page's arrive curve
  if (U.reveal < 1) U.reveal = Math.min(1, (now - U.revealFrom) / LOOK.reveal);
  sky(camera, reduce, U.ease ? U.ease(U.reveal) : U.reveal);
  // the star's place, which lights every planet, in the camera's frame
  const selected = U.ctx.selected(), hovered = U.ctx.hovered(), step = 1 - Math.exp(-passed * 12);
  let sun = null;
  for (const node of data.nodes) {
    const object = node.__threeObj;
    if (!object?.userData.ultra) continue;
    if (!sun && object.userData.kind === 'star') sun = object;
    if (object.userData.corona) held(object.userData.corona, node, object.userData.corona.userData.size);
    if (node.t === 'el') selectionLight(object, node);
    const target = node.id === selected ? 1 : node.id === hovered ? 0.4 : 0, away = U.ctx.dimmed(node) ? 1 : 0;
    object.userData.select += (target - object.userData.select) * (reduce ? 1 : step);
    object.userData.dim += (away - object.userData.dim) * (reduce ? 1 : step);
    const uniforms = object.material.uniforms;
    if (uniforms) { uniforms.select.value = object.userData.select; uniforms.dim.value = object.userData.dim; }
    if (object.userData.paint && U.frames % 20 === 1) object.material.color.set(U.G.nodeColor()(node));
    if (object.userData.spin) object.userData.spin(U.clock);
  }
  U.shared.sunOn.value = sun ? 1 : 0;
  if (sun) U.shared.sun.value.setFromMatrixPosition(sun.matrixWorld).applyMatrix4(camera.matrixWorldInverse);
}

/* ---------- switching ---------- */

/* Fades the map to the dark of space, changes what it is drawn as under the veil, draws it once so every shader is
 * ready, and fades back up; the sky then rises on its own. A switch during a switch takes over from where it is. */
async function show(mode) {
  U.mode = mode;
  const turn = ++U.turn, reduce = U.ctx.reduced();
  const out = reduce ? 80 : 240, back = reduce ? 120 : 560;
  U.ease = U.ease || curve();
  U.veil.style.background = mode === 'ultra' ? SPACE : U.ctx.css('--ground') || SPACE;
  U.veil.style.transition = `opacity ${out}ms var(--ease-leave, cubic-bezier(.5,0,.75,0))`;
  U.veil.style.opacity = '1';
  U.ctx.wake(out + back + LOOK.reveal + 400);
  await covered(out);  // the swap waits until the veil is whole, however busy the page is
  if (turn !== U.turn) return;
  apply(mode);
  await frames(2);  // drawn under the veil: the new shaders are compiled before anything is seen
  await U.ctx.linked?.();  // and linked, as the page holds its frames until they are
  if (turn !== U.turn) return;
  U.measure = {...U.measure, time: 0, frames: 0, last: 0, chained: false};  // the compiling frames are not measured
  U.revealFrom = performance.now();
  U.reveal = mode === 'ultra' ? 0 : 1;
  U.veil.style.transition = `opacity ${back}ms var(--ease-arrive, cubic-bezier(.16,1,.3,1))`;
  U.veil.style.opacity = '0';
  U.ctx.wake(back + LOOK.reveal + 400);
}
function apply(mode) {
  const G = U.G, ultra = mode === 'ultra';
  U.drawn = mode;
  if (ultra && !U.sky) U.sky = makeSky(G);
  if (U.sky) U.sky.group.visible = ultra;
  U.pass.enabled = ultra;
  U.gain.value = ultra ? LOOK.gain : 1;
  U.measure = {...U.measure, time: 0, frames: 0, last: 0, chained: false};
  if (ultra) G.scene().background = U.sky.ground;
  else G.scene().background = new THREE.Color(U.ctx.css('--ground') || SPACE);
  G.nodeThreeObject(G.nodeThreeObject());  // every node made again, as a body or as glass; the fibers follow `on`
}
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
/* The veil's fade has ended, or a while past when it should have. */
const covered = ms => new Promise(resolve => {
  const done = () => { U.veil.removeEventListener('transitionend', done); clearTimeout(late); resolve(); };
  const late = setTimeout(done, ms * 4 + 200);
  U.veil.addEventListener('transitionend', done);
});
const frames = count => new Promise(resolve => {
  const step = left => (left ? requestAnimationFrame(() => step(left - 1)) : resolve());
  step(count);
});
/* The page's arrive curve, the one every motion that comes in settles on, read from the page; a smooth step without
 * it. */
function curve() {
  const own = window.metaformEase?.curve?.('arrive');
  return typeof own === 'function' ? own : share => share * share * (3 - 2 * share);
}

/* ---------- the frame rate ---------- */

/* Counted over the frames drawn one after another, each frame the one the frame before asked for straight after it,
 * however long it took: on the slowest machine a frame can take half a second, and that is the machine that most
 * needs the quality lowered. A gap the page left on purpose is not a frame: the map at rest until the next act or
 * change, the idle map's slow frames, a tab put away, and a stall longer than GOVERNOR.stall. Three seconds under
 * GOVERNOR.low steps quality down once, and the count starts again. */
function governor(now) {
  const m = U.measure, gap = m.chained && m.last ? now - m.last : Infinity;
  m.last = now;
  m.chained = false;
  // whether this frame asks for the next straight away is known once the page's frame has ended, when the browser
  // runs what was queued during it
  queueMicrotask(() => { U.measure.chained = Boolean(U.ctx.chained?.()) && document.visibilityState === 'visible'; });
  if (gap > GOVERNOR.stall || U.ctx.idle()) return;
  m.time += gap;
  m.frames++;
  if (m.time < GOVERNOR.span) return;
  m.fps = 1000 * m.frames / m.time;
  m.time = m.frames = 0;
  if (m.fps < GOVERNOR.low && U.quality < QUALITY.length - 1) { m.steps++; setQuality(U.quality + 1); }
}
function setQuality(step) {
  U.quality = step;
  if (U.sky) {
    U.sky.shown = 0;
    for (const layer of U.sky.layers) {
      const count = Math.round(layer.count * QUALITY[step].stars);
      layer.points.geometry.setDrawRange(0, count);
      U.sky.shown += count;
    }
  }
  U.pass?.resize();
}

/* ---------- the sky ---------- */

/* A seeded random number, so the sky is the same on every load. */
function seeded(seed) {
  return () => {
    seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
/* The galaxy's plane, which the stars crowd toward and the nebula's band follows. */
const BAND = new THREE.Vector3(0.28, 0.92, 0.27).normalize();
/* Star colors by temperature, from blue-white to orange, the common ones repeated so they come up more often. */
const TEMPERATURES = ['#9db4ff', '#aabfff', '#cad8ff', '#e4e8ff', '#f8f7ff', '#f8f7ff', '#fff4ea', '#fff4ea', '#ffe6c8',
  '#ffd2a1', '#ffc078'].map(hex => new THREE.Color(hex));
/* The starfield in three layers, far to near: each further one follows the camera more closely, so the nearer
 * stars move against the further ones as the camera moves, `follow`; and a sphere around it all carrying the nebula. */
function makeSky(G) {
  const random = seeded(20261012), group = new THREE.Group();
  group.name = 'ultra-sky';
  const ratio = {value: G.renderer().getPixelRatio()}, fade = {value: 0};
  const layers = [
    {share: 0.64, radius: 26000, follow: 0.985, size: [0.9, 1.9], drift: 0.0016},
    {share: 0.28, radius: 20000, follow: 0.95, size: [1.3, 2.6], drift: 0.0028},
    {share: 0.08, radius: 15000, follow: 0.9, size: [1.8, 3.6], drift: 0.004}].map(layer => {
    const count = Math.round(STAR_COUNT * layer.share);
    const position = new Float32Array(count * 3), tint = new Float32Array(count * 3), look = new Float32Array(count * 2);
    const at = new THREE.Vector3(), side = new THREE.Vector3(), up = new THREE.Vector3();
    side.set(1, 0, 0).cross(BAND).normalize();
    up.copy(BAND).cross(side);
    for (let i = 0; i < count; i++) {
      if (random() < 0.42) {  // in the galaxy's band: a point on its great circle, a little above or below it
        const angle = random() * Math.PI * 2, lift = (random() + random() + random() - 1.5) * 0.22;
        at.copy(side).multiplyScalar(Math.cos(angle)).addScaledVector(up, Math.sin(angle)).addScaledVector(BAND, lift);
      } else at.set(random() * 2 - 1, random() * 2 - 1, random() * 2 - 1);
      if (at.lengthSq() < 1e-6) at.set(0, 1, 0);
      at.normalize().multiplyScalar(layer.radius * (0.92 + random() * 0.16));
      position.set([at.x, at.y, at.z], i * 3);
      // most stars faint, a few bright: the brightest go over full brightness and the bloom gives them a soft halo
      const bright = 0.18 + 0.7 * Math.pow(random(), 3.2) + (random() < 0.012 ? 0.9 + random() * 0.8 : 0);
      const color = TEMPERATURES[Math.floor(random() * TEMPERATURES.length)];
      tint.set([color.r * bright, color.g * bright, color.b * bright], i * 3);
      look.set([layer.size[0] + (layer.size[1] - layer.size[0]) * Math.pow(random(), 2), random() * 6.283], i * 2);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(position, 3));
    geometry.setAttribute('tint', new THREE.BufferAttribute(tint, 3));
    geometry.setAttribute('look', new THREE.BufferAttribute(look, 2));
    const points = new THREE.Points(geometry, new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      uniforms: {ratio, fade, time: U.shared.time, twinkle: {value: 1}},
      vertexShader: `attribute vec3 tint; attribute vec2 look; uniform float ratio; uniform float time; uniform float twinkle;
        varying vec3 vTint;
        void main() {
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          float glint = 1.0 + twinkle * 0.22 * sin(time * (0.7 + 0.5 * fract(look.y * 7.0)) + look.y) * step(0.55, length(tint));
          vTint = tint * glint;
          gl_PointSize = look.x * ratio;
        }`,
      fragmentShader: `uniform float fade; varying vec3 vTint;
        void main() {
          float d = length(gl_PointCoord * 2.0 - 1.0);
          float a = exp(-d * d * 5.0);
          if (a < 0.01) discard;
          gl_FragColor = vec4(vTint * a * fade, 1.0);
        }`}));
    Object.assign(points, {frustumCulled: false, renderOrder: -20});
    const holder = new THREE.Group();
    holder.add(points);
    group.add(holder);
    return {...layer, count, points, holder};
  });
  // the nebula: a sphere around everything, carrying the picture of the whole sky painted once, `paintNebula`
  const nebula = new THREE.Mesh(new THREE.SphereGeometry(30000, 48, 24), new THREE.ShaderMaterial({
    side: THREE.BackSide, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: {picture: {value: null}, fade},
    vertexShader: 'varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
    fragmentShader: `uniform sampler2D picture; uniform float fade; varying vec2 vUv;
      void main() { gl_FragColor = vec4(texture2D(picture, vUv).rgb * fade, 1.0); }`}));
  Object.assign(nebula, {frustumCulled: false, renderOrder: -21});
  // painted once its painter's shader is linked, off the page's thread, `nebulaPainter`; the sky rises over the
  // first second and a half after a switch, `reveal`, so it comes in with it
  nebulaPainter(G.renderer());
  NEBULA.ready.then(() => { nebula.material.uniforms.picture.value = paintNebula(G.renderer()); U.ctx.wake(); });
  group.add(nebula);
  group.visible = false;
  G.scene().add(group);
  const sky = {group, layers, nebula, ratio, fade, ground: new THREE.Color(SPACE), shown: STAR_COUNT};
  U.sky = sky;
  setQuality(U.quality);
  return sky;
}
/* Each frame: the nebula stays around the camera, each star layer follows it by its share, the sky turns slowly
 * while frames are drawn, and the whole sky rises by `reveal` after a switch. */
function sky(camera, reduce, reveal) {
  const s = U.sky, moving = !reduce && QUALITY[U.quality].drift;
  s.fade.value = reveal;
  s.ratio.value = U.G.renderer().getPixelRatio();
  s.nebula.position.copy(camera.position);
  s.nebula.rotation.y = moving ? U.clock * 0.0009 : s.nebula.rotation.y;
  for (const layer of s.layers) {
    layer.holder.position.copy(camera.position).multiplyScalar(reduce ? 1 : layer.follow);
    if (moving) layer.points.rotation.y = U.clock * layer.drift;
    layer.points.material.uniforms.twinkle.value = moving ? 1 : 0;
  }
}
/* The nebula, painted once into a picture of the whole sky: each point of the picture is a direction, so it has no
 * seam and nothing pinches at the poles. Thin clouds of indigo, teal and a little rose, thicker along the galaxy's
 * band, with darker dust across the band; all of it faint, so the map in front is what is seen. */
function paintNebula(renderer) {
  const {target, material} = nebulaPainter(renderer);
  const quad = new FullScreenQuad(material), was = renderer.getRenderTarget();
  renderer.setRenderTarget(target);
  quad.render(renderer);
  renderer.setRenderTarget(was);
  quad.dispose();
  material.dispose();
  return target.texture;
}
/* The nebula's painter, made once, its shader linked off the page's thread before it paints, `makeSky`: its noise
 * took a second to link, and three.js waits for a link on the page's thread when it first draws. */
const NEBULA = {painter: null, ready: null};
function nebulaPainter(renderer) {
  if (NEBULA.painter) return NEBULA.painter;
  const target = new THREE.WebGLRenderTarget(1024, 512, {type: THREE.HalfFloatType, depthBuffer: false});
  const material = new THREE.ShaderMaterial({uniforms: {band: {value: BAND}},
    vertexShader: 'varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }',
    fragmentShader: `${NOISE} uniform vec3 band; varying vec2 vUv;
      void main() {
        float phi = vUv.x * 6.2831853, theta = (1.0 - vUv.y) * 3.1415927;
        vec3 d = vec3(-cos(phi) * sin(theta), cos(theta), sin(phi) * sin(theta));
        float lat = dot(d, band), inBand = exp(-lat * lat * 7.0);
        float n1 = fbm(d * 2.1 + 3.7), n2 = fbm(d * 4.3 + 11.0 + n1 * 1.6), n3 = fbm(d * 1.2 + 23.0);
        float cloud = smoothstep(0.38, 0.86, n1 * 0.62 + n2 * 0.48);
        float dust = smoothstep(0.5, 0.78, fbm(d * 7.0 + 41.0 + n2));
        vec3 indigo = vec3(0.075, 0.06, 0.26), teal = vec3(0.015, 0.13, 0.17), rose = vec3(0.2, 0.035, 0.15);
        vec3 c = mix(indigo, teal, smoothstep(0.32, 0.72, n3));
        c = mix(c, rose, smoothstep(0.58, 0.82, n2) * 0.55);
        c *= cloud * (0.28 + 0.72 * inBand) * (1.0 - 0.65 * dust * inBand);
        c += vec3(0.5, 0.56, 0.75) * inBand * inBand * 0.03 * (0.4 + n2);
        gl_FragColor = vec4(c * 0.16, 1.0);  // faint enough that a grey name before it keeps clean's contrast
      }`, depthTest: false, depthWrite: false});
  NEBULA.painter = {target, material};
  const was = renderer.getRenderTarget();
  renderer.setRenderTarget(target);  // linked for the picture it paints
  try { NEBULA.ready = renderer.compileAsync(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material), U.G.camera()); }
  finally { renderer.setRenderTarget(was); }
  return NEBULA.painter;
}

/* ---------- the bodies ---------- */

/* Value noise in three dimensions, and its sum over four octaves; enough to make a surface or a cloud. */
const NOISE = `
  float hash3(vec3 p) { p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
  float noise3(vec3 x) {
    vec3 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(mix(hash3(i), hash3(i + vec3(1.0, 0.0, 0.0)), f.x),
                   mix(hash3(i + vec3(0.0, 1.0, 0.0)), hash3(i + vec3(1.0, 1.0, 0.0)), f.x), f.y),
               mix(mix(hash3(i + vec3(0.0, 0.0, 1.0)), hash3(i + vec3(1.0, 0.0, 1.0)), f.x),
                   mix(hash3(i + vec3(0.0, 1.0, 1.0)), hash3(i + vec3(1.0, 1.0, 1.0)), f.x), f.y), f.z);
  }
  float fbm(vec3 p) {
    float s = 0.0, a = 0.5;
    for (int i = 0; i < 4; i++) { s += a * noise3(p); p = p * 2.03 + vec3(1.7, 9.2, 3.1); a *= 0.5; }
    return s / 0.9375;
  }`;
/* Where the light comes from, in the camera's frame: from the star when the map has one, mixed with a light from the
 * upper left before the eye, so no body is ever seen only by its dark side. */
const LIGHT = `
  uniform vec3 sun; uniform float sunOn;
  vec3 lightFrom(vec3 at) {
    vec3 key = normalize(vec3(-0.45, 0.6, 0.65));
    return sunOn > 0.5 ? normalize(normalize(sun - at) * 1.1 + key) : key;
  }`;
// a body and its halo take the page's haze of depth, `depth3d`, through three.js's fog, `FOGGED`
const BODY_VERTEX = `varying vec3 vNormal; varying vec3 vView; varying vec3 vAt; varying vec3 vLocal;
  #include <fog_pars_vertex>
  void main() {
    vec4 at = modelViewMatrix * vec4(position, 1.0);
    vAt = at.xyz; vView = normalize(-at.xyz); vLocal = position;
    vNormal = normalize(normalMatrix * normal);
    gl_Position = projectionMatrix * at;
    vec4 mvPosition = at;
    #include <fog_vertex>
  }`;
// the uniforms a material in the haze (`fog: true`) carries: three.js fills them from the scene's fog as it draws
const FOGGED = () => THREE.UniformsUtils.clone(THREE.UniformsLib.fog);
/* One shader for every body, compiled once for each kind. Its surface is in the node's color, lit by the star; its
 * rim is its atmosphere, which rises over full brightness as the node is selected, so the bloom rings it; the light
 * the page gives a node that signals, `emissive`, is added over it all as it is to the glass. */
const BODY_FRAGMENT = `${NOISE}${LIGHT}
  uniform vec3 color; uniform vec3 emissive; uniform float emissiveIntensity; uniform float opacity;
  uniform float seed; uniform float select; uniform float dim; uniform float time; uniform float radius;
  varying vec3 vNormal; varying vec3 vView; varying vec3 vAt; varying vec3 vLocal;
  #include <fog_pars_fragment>
  void main() {
    vec3 N = normalize(vNormal), V = normalize(vView);
  #if KIND == 4 || KIND == 1
    N = normalize(cross(dFdx(vAt), dFdy(vAt)));  // a crystal's faces are flat, and so are a rocky world's
  #endif
    vec3 L = lightFrom(vAt), P = vLocal / radius;
    float ndl = dot(N, L), lit = clamp((ndl + 0.28) / 1.28, 0.0, 1.0);
    float facing = clamp(dot(N, V), 0.0, 1.0), fres = pow(1.0 - facing, 2.6);
    vec3 albedo = color, glow = vec3(0.0);
    float rim = 1.0, ambient = 0.14;
  #if KIND == 1
    // rock: the node's color weathered toward grey-brown, its faces lit one by one
    float n = fbm(P * 2.4 + seed), crater = smoothstep(0.62, 0.7, noise3(P * 5.0 + seed * 3.0));
    albedo = mix(color, vec3(0.5, 0.44, 0.38) * length(color), 0.3) * (0.62 + 0.6 * n) * (1.0 - 0.28 * crater);
    ambient = 0.08;
  #elif KIND == 2
    // a gas giant's few broad bands, light and dark, wide enough to be seen as stripes across the whole map
    float bands = sin(P.y * 9.0 + fbm(P * 1.8 + seed) * 2.4);
    albedo = mix(color * (0.5 + 0.42 * bands), vec3(1.0), 0.1 + 0.12 * bands);
  #elif KIND == 3
    float bands = sin(P.y * 9.0 + fbm(P * 1.8 + seed) * 3.2);
    albedo = mix(color * (0.74 + 0.22 * bands), vec3(1.0), 0.06 + 0.06 * bands);
  #elif KIND == 4
    albedo = mix(color, vec3(1.0), 0.22) * (0.82 + 0.3 * noise3(P * 3.0 + seed));
    glow = vec3(1.0) * pow(max(dot(reflect(-L, N), V), 0.0), 24.0) * 0.4;
  #elif KIND == 6
    albedo = mix(color, vec3(1.0), 0.6); ambient = 1.0; lit = 0.0;
    glow = albedo * (1.1 + 0.9 * pow(facing, 2.0));
  #elif KIND == 7
    // the edge of the dark is a thin line in its own color, never brighter than a planet until it is selected
    albedo = color * 0.04; ambient = 0.0; rim = 0.0;
    glow = mix(color, vec3(1.0), 0.35) * pow(1.0 - facing, 6.0) * (0.55 + 2.1 * select);
  #elif KIND == 8
    // a star seen as one is: white-hot in the middle, its own color toward the limb and darker there, its surface
    // grained by cells that churn slowly; only the middle goes over full brightness, so the bloom haloes it and the
    // surface stays seen
    float grain = fbm(P * 7.0 + vec3(time * 0.05, 0.0, time * 0.035) + seed);
    float cells = fbm(P * 16.0 + vec3(0.0, time * 0.08, 0.0) + seed * 2.0);
    float limb = facing;
    vec3 edge = color * vec3(1.0, 0.7, 0.42);  // the limb cooler and warmer, as a real star's is
    vec3 hot = mix(edge, mix(color, vec3(1.0, 0.98, 0.94), 0.5), smoothstep(0.15, 0.95, limb));
    albedo = vec3(0.0); ambient = 0.0; lit = 0.0; rim = 0.0;
    glow = hot * (0.14 + 1.0 * pow(limb, 0.85)) * (0.8 + 0.28 * grain + 0.16 * cells);
  #elif KIND == 9
    float land = smoothstep(0.48, 0.56, fbm(P * 2.2 + seed));
    albedo = mix(color * 0.55, color * 1.05, land);
    float night = smoothstep(0.15, -0.25, ndl), city = step(0.74, noise3(P * 26.0 + seed)) * land;
    glow = mix(color, vec3(1.0, 0.86, 0.6), 0.5) * city * night * 1.3;
  #elif KIND == 10
    float n = fbm(P * 3.2 + seed), crater = smoothstep(0.6, 0.7, noise3(P * 6.0 + seed));
    albedo = mix(color, vec3(0.92), 0.55) * (0.72 + 0.5 * n) * (1.0 - 0.3 * crater);
    rim = 0.45; ambient = 0.45;
  #elif KIND == 11
    albedo = vec3(0.0); ambient = 0.0; lit = 0.0; rim = 0.0;
    glow = mix(color, vec3(1.0), 0.3) * (0.9 + 0.35 * facing);
  #else
    albedo = color * (0.8 + 0.3 * fbm(P * 1.6 + seed));
  #endif
    vec3 air = mix(color, vec3(1.0), 0.3);
    vec3 c = albedo * (ambient + 0.95 * lit) + glow;
    c += air * fres * rim * (0.45 + 0.55 * clamp(ndl + 0.6, 0.0, 1.0)) * (0.8 + 1.6 * select) * (1.0 - 0.75 * dim);
    // a node away from the selection recedes: grey and dark, so what is selected and beside it leads
    c = mix(c, vec3(dot(c, vec3(0.3, 0.59, 0.11))), 0.6 * dim) * (1.0 - 0.62 * dim);
    // the light the page gives a node that signals is its atmosphere's, strongest at the limb and over full brightness
    // there, so the bloom haloes it; the face takes only a little of it and keeps its surface under the threshold
    float signal = emissiveIntensity * (0.1 + 0.55 * pow(fres, 0.8));
    c = c * (1.0 - 0.08 * min(emissiveIntensity, 1.0)) + emissive * signal;
    gl_FragColor = vec4(c, opacity);
    #include <fog_fragment>
  }`;
/* The material of a body. It answers to what the page sets on a node's material, color, emissive,
 * emissiveIntensity and opacity, so the page dims, flashes, pulses and fades it as it does the glass, and it clones
 * as the page clones a node's material before it lights one node alone. */
class BodyMaterial extends THREE.ShaderMaterial {
  constructor(kind = 'plain') {
    super({vertexShader: BODY_VERTEX, fragmentShader: BODY_FRAGMENT, defines: {KIND: KIND[kind]}, fog: true,
      uniforms: {color: {value: new THREE.Color()}, emissive: {value: new THREE.Color(0, 0, 0)},
        emissiveIntensity: {value: 0}, opacity: {value: 1}, seed: {value: 0}, select: {value: 0}, dim: {value: 0},
        radius: {value: 1}, ...FOGGED()}});
    this.kind = kind;
    this.share();
  }
  share() { Object.assign(this.uniforms, U.shared); return this; }
  get color() { return this.uniforms.color.value; }
  get emissive() { return this.uniforms.emissive.value; }
  get emissiveIntensity() { return this.uniforms.emissiveIntensity.value; }
  set emissiveIntensity(value) { this.uniforms.emissiveIntensity.value = value; }
  onBeforeRender() { this.uniforms.opacity.value = this.opacity; }
  copy(source) { super.copy(source); this.kind = source.kind; return this.share(); }
}
/* The atmosphere's halo outside a body's edge: the far side of a larger sphere, brightest just past the body and gone
 * at its own edge, lit on the star's side. It takes the body's color, light and selection each time it is drawn. */
const HALO_FRAGMENT = `${LIGHT}
  uniform vec3 color; uniform vec3 emissive; uniform float emissiveIntensity; uniform float opacity;
  uniform float select; uniform float dim; uniform float edge; uniform float strength;
  varying vec3 vNormal; varying vec3 vView; varying vec3 vAt; varying vec3 vLocal;
  #include <fog_pars_fragment>
  void main() {
    vec3 N = normalize(vNormal), V = normalize(vView);
    float inner = clamp(-dot(N, V) / edge, 0.0, 1.0), a = pow(inner, 3.2);
    float side = clamp(0.35 + 0.8 * dot(N, lightFrom(vAt)), 0.2, 1.0);
    vec3 c = mix(color, vec3(1.0), 0.22) * side * strength * (0.6 + 1.6 * select) * (1.0 - 0.85 * dim)
      + emissive * emissiveIntensity * 0.75;
    gl_FragColor = vec4(c * a * opacity, 1.0);
    #include <fog_fragment>
  }`;
function halo(host, radius, scale = 1.24, strength = 1) {
  const material = new THREE.ShaderMaterial({vertexShader: BODY_VERTEX, fragmentShader: HALO_FRAGMENT,
    side: THREE.BackSide, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: true,
    uniforms: {color: {value: new THREE.Color()}, emissive: {value: new THREE.Color()}, emissiveIntensity: {value: 0},
      opacity: {value: 1}, select: {value: 0}, dim: {value: 0}, strength: {value: strength},
      edge: {value: Math.sqrt(1 - 1 / (scale * scale))}, ...U.shared, ...FOGGED()}});
  const shell = new THREE.Mesh(sphere(radius * scale, 32, 20), material);
  follows(shell, host, uniforms => {
    const from = host.material;
    uniforms.color.value.copy(from.color);
    uniforms.emissive.value.copy(from.emissive);
    uniforms.emissiveIntensity.value = from.emissiveIntensity;
    uniforms.opacity.value = from.opacity;
    uniforms.select.value = from.uniforms.select.value;
    uniforms.dim.value = from.uniforms.dim.value;
  });
  return shell;
}
/* ---------- the bodies drawn together ---------- */

/* Many bodies of one kind and size, or many halos of one shape, drawn in one draw by the page, `nodes3d`: the same
 * shaders, with what each body's material holds as its own uniforms given instead to each instance, `look`. */
const BATCH_VERTEX = `attribute vec4 lookA; attribute vec4 lookB; attribute vec4 lookC;
  varying vec3 vNormal; varying vec3 vView; varying vec3 vAt; varying vec3 vLocal;
  varying vec3 color; varying float opacity; varying vec3 emissive; varying float emissiveIntensity;
  varying float seed; varying float select; varying float dim;
  #include <fog_pars_vertex>
  void main() {
    vec4 at = modelViewMatrix * instanceMatrix * vec4(position, 1.0);
    vAt = at.xyz; vView = normalize(-at.xyz); vLocal = position;
    vNormal = normalize(normalMatrix * mat3(instanceMatrix) * normal);
    color = lookA.rgb; opacity = lookA.a; emissive = lookB.rgb; emissiveIntensity = lookB.a;
    seed = lookC.x; select = lookC.y; dim = lookC.z;
    gl_Position = projectionMatrix * at;
    vec4 mvPosition = at;
    #include <fog_vertex>
  }`;
const OWN = `uniform vec3 color; uniform vec3 emissive; uniform float emissiveIntensity; uniform float opacity;`;
const GIVEN = `varying vec3 color; varying vec3 emissive; varying float emissiveIntensity; varying float opacity;`;
const BATCH_BODY = BODY_FRAGMENT.replace(OWN, GIVEN)
  .replace('uniform float seed; uniform float select; uniform float dim;', 'varying float seed; varying float select; varying float dim;');
const BATCH_HALO = HALO_FRAGMENT.replace(OWN, GIVEN)
  .replace('uniform float select; uniform float dim;', 'varying float seed; varying float select; varying float dim;');
/* How a node's part is drawn in a batch, or null when it is drawn alone: a body that is solid and not a part of
 * another, by its kind and size, and the halo of any body, by its shape. `look` is the material whose values each
 * instance takes. A body lit alone, a ghost or one fading is see-through and stays drawn alone. */
export function batch(object) {
  if (U.drawn !== 'ultra') return null;
  const material = object.material;
  // each batch made once for a material and kept on it while what it was made from holds, so a frame makes none
  if (material instanceof BodyMaterial && !material.transparent && material.visible && !object.userData.host) {
    const radius = material.uniforms.radius.value, kept = BATCHED.get(material);
    if (kept && kept.a === radius) return kept;
    return keptBatch(material, {key: `body:${material.kind}:${radius}`, look: material, a: radius, b: 0,
      make: () => new THREE.ShaderMaterial({vertexShader: BATCH_VERTEX, fragmentShader: BATCH_BODY, fog: true,
        defines: {KIND: KIND[material.kind]}, uniforms: {radius: {value: radius}, ...U.shared, ...FOGGED()}})});
  }
  const host = object.userData.host?.material;
  if (material?.fragmentShader === HALO_FRAGMENT && host instanceof BodyMaterial) {
    const {edge, strength} = material.uniforms, kept = BATCHED.get(material);
    if (kept && kept.look === host && kept.a === edge.value && kept.b === strength.value) return kept;
    return keptBatch(material, {key: `halo:${edge.value}:${strength.value}`, look: host, a: edge.value,
      b: strength.value, make: () =>
      new THREE.ShaderMaterial({vertexShader: BATCH_VERTEX, fragmentShader: BATCH_HALO, side: THREE.BackSide,
        transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: true,
        uniforms: {edge: {value: edge.value}, strength: {value: strength.value}, ...U.shared, ...FOGGED()}})});
  }
  return null;
}
// each material's batch, kept beside it and not in its userData, which three.js copies through JSON when it clones
const BATCHED = new WeakMap();
const keptBatch = (material, batch) => { BATCHED.set(material, batch); return batch; };
/* What one instance takes from a body's material: its color and opacity, its signal light, its seed, selection and
 * dimming, as the body's own material and its halo's `follows` read them. The selection and the dimming ease toward
 * where they go and never quite arrive, so they are taken to a thousandth, and a body at rest sends nothing. */
export function lookOf(material, out, at) {
  const {color, emissive, uniforms} = material;
  out[at] = color.r; out[at + 1] = color.g; out[at + 2] = color.b; out[at + 3] = material.opacity;
  out[at + 4] = emissive.r; out[at + 5] = emissive.g; out[at + 6] = emissive.b;
  out[at + 7] = material.emissiveIntensity;
  out[at + 8] = uniforms.seed.value;
  out[at + 9] = Math.round(uniforms.select.value * 1000) / 1000; out[at + 10] = Math.round(uniforms.dim.value * 1000) / 1000;
  out[at + 11] = 0;
}
/* A part of a body that is not the body itself: it never takes a click, which the body's own outline takes, and it
 * takes the body's look each time it is drawn, `sync`. */
function follows(part, host, sync) {
  part.raycast = () => {};
  part.userData.host = host;
  if (sync) part.onBeforeRender = function (renderer, scene, camera, geometry, material) {
    if (host.material?.uniforms && material.uniforms) sync(material.uniforms, material);
  };
  return part;
}
const sphere = (radius, across = 32, down = 20) => shape(`ball:${radius}:${across}`, () => new THREE.SphereGeometry(radius, across, down));
function shape(key, make) {
  if (!U.shapes.has(key)) U.shapes.set(key, make());
  return U.shapes.get(key);
}
/* A ring's band, a media planet's rings or a sink's disk, in the plane of the body's equator, each drawn by its own
 * shader: the rings banded and lit, the disk hot within and turning. */
function band(host, radius, inner, outer, fragmentShader, additive) {
  const material = new THREE.ShaderMaterial({vertexShader: BODY_VERTEX, fragmentShader,
    side: THREE.DoubleSide, transparent: true, depthWrite: false,
    blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
    uniforms: {color: {value: new THREE.Color()}, opacity: {value: 1}, inner: {value: inner * radius},
      outer: {value: outer * radius}, seed: {value: 0}, emissive: {value: new THREE.Color()},
      emissiveIntensity: {value: 0}, dim: {value: 0}, select: {value: 0}, ...U.shared}});
  const ring = new THREE.Mesh(shape(`ring:${radius}:${inner}:${outer}`,
    () => new THREE.RingGeometry(inner * radius, outer * radius, 96, 1).rotateX(-Math.PI / 2)), material);
  return follows(ring, host, uniforms => {
    const from = host.material;
    uniforms.color.value.copy(from.color);
    uniforms.opacity.value = from.opacity;
    uniforms.seed.value = from.uniforms.seed.value;
    uniforms.emissive.value.copy(from.emissive);
    uniforms.emissiveIntensity.value = from.emissiveIntensity;
    uniforms.dim.value = from.uniforms.dim.value;
    uniforms.select.value = from.uniforms.select.value;
  });
}
const RINGS = `${NOISE}${LIGHT}
  uniform vec3 color; uniform float opacity; uniform float inner; uniform float outer; uniform float seed;
  uniform vec3 emissive; uniform float emissiveIntensity; uniform float dim;
  varying vec3 vNormal; varying vec3 vView; varying vec3 vAt; varying vec3 vLocal;
  void main() {
    float r = (length(vLocal.xz) - inner) / (outer - inner);
    float bands = 0.55 + 0.45 * sin(r * 38.0 + seed) * sin(r * 11.0 + 1.3 + seed);
    float gap = smoothstep(0.0, 0.04, abs(r - 0.62)), edges = smoothstep(0.0, 0.08, r) * smoothstep(1.0, 0.85, r);
    // the rings in the planet's own color and fainter than it, so they tell the type without drawing the eye
    float light = 0.4 + 0.45 * abs(dot(normalize(vNormal), lightFrom(vAt)));
    vec3 c = mix(color, vec3(0.92), 0.2) * light + emissive * emissiveIntensity * 0.4;
    gl_FragColor = vec4(c * (1.0 - 0.6 * dim), bands * gap * edges * 0.4 * (1.0 - 0.55 * dim) * opacity);
  }`;
const DISK = `${NOISE}
  uniform vec3 color; uniform float opacity; uniform float inner; uniform float outer; uniform float seed; uniform float time;
  uniform vec3 emissive; uniform float emissiveIntensity; uniform float dim; uniform float select;
  varying vec3 vNormal; varying vec3 vView; varying vec3 vAt; varying vec3 vLocal;
  void main() {
    float r = (length(vLocal.xz) - inner) / (outer - inner), turn = atan(vLocal.z, vLocal.x);
    float swirl = fbm(vec3(cos(turn + r * 5.0 - time * 0.35) * 2.2, sin(turn + r * 5.0 - time * 0.35) * 2.2, r * 5.0 + seed));
    float heat = pow(1.0 - clamp(r, 0.0, 1.0), 1.7) * smoothstep(0.0, 0.05, r);
    vec3 c = mix(mix(color, vec3(1.0), 0.45), color, smoothstep(0.0, 0.6, r)) * heat * (0.55 + 0.75 * swirl) * (0.36 + 1.0 * select) * (1.0 - 0.8 * dim);
    c += emissive * emissiveIntensity * heat * 0.6;
    gl_FragColor = vec4(c * opacity, 1.0);
  }`;
/* The jets of a pulsar: two thin cones of light out of its poles, brightest at the star and gone at their ends. */
function jets(host, radius) {
  const material = new THREE.ShaderMaterial({vertexShader: BODY_VERTEX, side: THREE.DoubleSide, transparent: true,
    depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: {color: {value: new THREE.Color()}, opacity: {value: 1}, dim: {value: 0}, length: {value: radius * 3.4}},
    fragmentShader: `uniform vec3 color; uniform float opacity; uniform float dim; uniform float length;
      varying vec3 vNormal; varying vec3 vView; varying vec3 vAt; varying vec3 vLocal;
      void main() {
        float along = clamp(abs(vLocal.y) / length, 0.0, 1.0), core = pow(abs(dot(normalize(vNormal), normalize(vView))), 1.5);
        gl_FragColor = vec4(mix(color, vec3(1.0), 0.5) * pow(1.0 - along, 2.2) * core * 1.5 * (1.0 - 0.7 * dim) * opacity, 1.0);
      }`});
  const geometry = shape(`jets:${radius}`, () => {
    const one = new THREE.ConeGeometry(radius * 0.32, radius * 3.4, 18, 1, true).translate(0, -radius * 1.7, 0);
    const both = [one.clone().rotateX(Math.PI), one];
    const merged = new THREE.BufferGeometry();
    for (const name of ['position', 'normal', 'uv']) {
      const parts = both.map(part => part.toNonIndexed().getAttribute(name));
      const all = new Float32Array(parts.reduce((sum, part) => sum + part.array.length, 0));
      let at = 0;
      for (const part of parts) { all.set(part.array, at); at += part.array.length; }
      merged.setAttribute(name, new THREE.BufferAttribute(all, parts[0].itemSize));
    }
    return merged;
  });
  return follows(new THREE.Mesh(geometry, material), host, uniforms => {
    uniforms.color.value.copy(host.material.color);
    uniforms.opacity.value = host.material.opacity;
    uniforms.dim.value = host.material.uniforms.dim.value;
  });
}
/* A soft glow around a star or a pulsar, faced to the eye: a disk of light falling off from its middle, with four
 * faint rays on the DE's star, as a telescope draws a bright star. Up close it is held to a part of the view, `held`,
 * so the star lights its neighbours and never washes the view behind their names. */
function corona(host, radius, rays) {
  // one picture shared by every glow; when the graph frees a node's parts it is sent again on its next use
  const material = new THREE.SpriteMaterial({map: glowPicture(rays ? 'rays' : 'soft'), blending: THREE.AdditiveBlending,
    depthWrite: false, transparent: true, toneMapped: false});
  const glow = follows(new THREE.Sprite(material), host, null);
  glow.userData.size = {world: radius * (rays ? 6 : 5), least: 0, most: rays ? 0.3 : 0.18};
  glow.scale.setScalar(glow.userData.size.world);
  glow.onBeforeRender = () => {
    material.color.copy(host.material.color).multiplyScalar((rays ? 0.7 : 0.85) * (1 - 0.8 * host.material.uniforms.dim.value));
    material.opacity = host.material.opacity;
  };
  host.userData.corona = glow;
  return glow;
}
/* A glow's size: its own size in the world, but never under `least` pixels across, so it is seen from across the whole
 * map, nor over `most` of the view's height, so up close it never fills the view. Set before the frame is drawn. */
function held(sprite, node, size) {
  const view = U.view, scale = sprite.parent?.scale.x || 1;
  let world = size.world;
  if (view.perPixel && view.camera) {
    const far = view.camera.position.distanceTo(_at.set(node.x || 0, node.y || 0, node.z || 0));
    const pixel = far * view.perPixel, tall = U.ctx.stage.height || 1;
    world = Math.min(Math.max(world, size.least * pixel), size.most * tall * pixel);
  }
  sprite.scale.setScalar(world / scale);
}
const _at = new THREE.Vector3();
/* The picture of a glow, drawn once: light falling off from its middle, and with `rays` the four faint rays; or the
 * selection's orbit, `orbit`, a fine circle of light with a soft edge, a little brighter on two opposite arcs so its
 * slow turn is seen. */
function glowPicture(key) {
  if (key === 'orbit' && !U.sprites.has(key)) {
    const size = 256, canvas = Object.assign(document.createElement('canvas'), {width: size, height: size});
    const pen = canvas.getContext('2d'), middle = size / 2;
    pen.translate(middle, middle);
    for (const [width, alpha] of [[14, 0.12], [7, 0.3], [2.6, 0.95]]) {
      pen.lineWidth = width;
      const sweep = pen.createConicGradient(0, 0, 0);
      sweep.addColorStop(0, `rgba(255,255,255,${alpha})`);
      sweep.addColorStop(0.25, `rgba(255,255,255,${alpha * 0.45})`);
      sweep.addColorStop(0.5, `rgba(255,255,255,${alpha})`);
      sweep.addColorStop(0.75, `rgba(255,255,255,${alpha * 0.45})`);
      sweep.addColorStop(1, `rgba(255,255,255,${alpha})`);
      pen.strokeStyle = sweep;
      pen.beginPath();
      pen.arc(0, 0, middle * 0.82, 0, Math.PI * 2);
      pen.stroke();
    }
    U.sprites.set(key, new THREE.CanvasTexture(canvas));
  }
  if (!U.sprites.has(key)) {
    const rays = key === 'rays';
    const size = 256, canvas = Object.assign(document.createElement('canvas'), {width: size, height: size});
    const pen = canvas.getContext('2d'), middle = size / 2;
    const fall = pen.createRadialGradient(middle, middle, 0, middle, middle, middle);
    // light falling off as the inverse square does, eased to nothing at the edge so no disc is ever seen
    for (let i = 0; i <= 16; i++) {
      const at = i / 16, fall2 = 1 / (1 + 90 * at * at) * (1 - at) * (1 - at);
      fall.addColorStop(at, `rgba(255,255,255,${(0.85 * fall2).toFixed(4)})`);
    }
    pen.fillStyle = fall;
    pen.fillRect(0, 0, size, size);
    if (rays) {
      pen.globalCompositeOperation = 'lighter';
      for (const turn of [0, Math.PI / 2]) {
        pen.save();
        pen.translate(middle, middle);
        pen.rotate(turn + Math.PI / 4);
        const ray = pen.createLinearGradient(-middle, 0, middle, 0);
        ray.addColorStop(0, 'rgba(255,255,255,0)');
        ray.addColorStop(0.5, 'rgba(255,255,255,0.35)');
        ray.addColorStop(1, 'rgba(255,255,255,0)');
        pen.fillStyle = ray;
        pen.fillRect(-middle, -1.2, size, 2.4);
        pen.restore();
      }
    }
    U.sprites.set(key, new THREE.CanvasTexture(canvas));
  }
  return U.sprites.get(key);
}
/* The selection's light: a soft glow behind the selected body and a fine orbit of light around it, in its color. Both
 * are held to a size on the screen, `held`: across the whole map, where a body is a few pixels wide, the glow is
 * still a mark the eye finds first and the orbit rings the body clear of its neighbours; up close the glow is held to
 * a part of the view, so the names in front of it keep a dark ground, and the orbit hugs the body. Each body has its
 * own, made the first time it is selected: it rises with the body's selection and falls as it is let go, so moving
 * the selection hands the light over smoothly. A hovered body takes a little of it. */
function selectionLight(object, node) {
  let light = object.userData.light;
  const share = object.userData.select * (1 - 0.8 * object.userData.dim);
  if (!light && share < 0.01) return;
  if (!light) {
    const sprite = picture => follows(new THREE.Sprite(new THREE.SpriteMaterial({map: glowPicture(picture),
      blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, toneMapped: false})), object, null);
    const radius = object.userData.radius;
    light = object.userData.light = {glow: sprite('soft'), orbit: sprite('orbit'),
      sizes: {glow: {world: radius * 6, least: 72, most: 0.2}, orbit: {world: radius * 3.4, least: 34, most: 1}}};
    object.add(light.glow, light.orbit);
  }
  const shown = share > 0.01;
  light.glow.visible = light.orbit.visible = shown;
  if (!shown) return;
  held(light.glow, node, light.sizes.glow);
  held(light.orbit, node, light.sizes.orbit);
  light.glow.material.color.copy(object.material.color).lerp(WHITE, 0.3).multiplyScalar(1.5 * share);
  light.orbit.material.color.copy(object.material.color).lerp(WHITE, 0.55).multiplyScalar(1.25 * share);
  light.orbit.material.rotation = U.clock * 0.05;
}
const WHITE = new THREE.Color(1, 1, 1);
/* The moons of a collection: three bright moons close around it, each on its own tilted orbit, turning while frames
 * are drawn; large and bright enough that across the whole map the planet reads as a small cluster. */
function moons(host, radius, seed) {
  const random = seeded(Math.floor(seed * 1e6)), orbits = [];
  for (let i = 0; i < 3; i++) {
    const material = new BodyMaterial('moon');
    material.uniforms.radius.value = radius * 0.36;
    material.uniforms.seed.value = seed + i;
    const moon = follows(new THREE.Mesh(sphere(radius * 0.36, 16, 12), material), host, uniforms => {
      uniforms.color.value.copy(host.material.color);
      uniforms.select.value = host.material.uniforms.select.value * 0.5;
      uniforms.dim.value = host.material.uniforms.dim.value;
    });
    material.onBeforeRender = function () { this.uniforms.opacity.value = host.material.opacity; };
    const tilt = new THREE.Group();
    tilt.rotation.set((random() - 0.5) * 0.9, random() * Math.PI, (random() - 0.5) * 0.9);
    tilt.add(moon);
    host.add(tilt);
    orbits.push({moon, far: radius * (1.62 + i * 0.4), speed: 0.35 / (1 + i * 0.6), phase: i * 2.094 + random() * 1.2});
  }
  host.userData.spin = clock => {
    for (const orbit of orbits) {
      const turn = orbit.phase + clock * orbit.speed;
      orbit.moon.position.set(Math.cos(turn) * orbit.far, 0, Math.sin(turn) * orbit.far);
    }
  };
  host.userData.spin(U.clock);
}
/* A node's body: its kind by its role and type, its size as the graph sizes the node, its own color, and the parts
 * around it its kind has. */
function makeBody(node) {
  const G = U.G, size = Number(G.nodeVal()(node)) || 1, radius = Math.cbrt(size) * G.nodeRelSize();
  const root = String(node.address || '').split('.')[0];
  const typed = U.ctx.shapes() && TYPE_ROOTS.includes(root) ? BY_TYPE[root] : null;
  // Changed for the new map's roles: the Definitive element is the star, the earlier DE. The new map has no role for
  // those the project serves, the earlier CQU and its inhabited world; an element under `downstream` has that type's
  // own body.
  const kind = node.t === 'el' ? (node.role === 'Definitive' ? 'star' : typed || 'plain')
    : node.t === 'purpose' ? 'knot' : 'moon';
  const seed = hashOf(String(node.id));
  const material = new BodyMaterial(kind);
  material.uniforms.seed.value = seed * 100;
  // the outline tells the type across the whole map: a rock lumpy, a gas giant wide and flat, a crystal a tall point
  const geometry = kind === 'crystal' ? shape(`crystal:${radius}`, () => new THREE.OctahedronGeometry(radius * 1.12, 0).scale(0.9, 1.45, 0.9))
    : kind === 'rocky' ? rock(radius, Math.floor(seed * 4))
    : kind === 'banded' ? shape(`giant:${radius}`, () => new THREE.SphereGeometry(radius, 40, 28).scale(1.2, 0.8, 1.2))
    : kind === 'knot' ? sphere(radius * 0.45, 16, 12)
    : kind === 'pulsar' ? sphere(radius * 0.55)
    : kind === 'sink' ? sphere(radius * 0.62)
    : kind === 'moon' ? sphere(radius, 20, 14)
    : sphere(radius, 40, 28);
  material.uniforms.radius.value = kind === 'pulsar' ? radius * 0.55 : kind === 'sink' ? radius * 0.62
    : kind === 'knot' ? radius * 0.45 : radius;
  material.color.set(G.nodeColor()(node));
  const object = new THREE.Mesh(geometry, material);
  Object.assign(object.userData, {ultra: true, kind, radius, select: 0, dim: 0, paint: node.t !== 'el'});
  const tilt = (seed - 0.5) * 0.7;
  if (['plain', 'ringed', 'system', 'world'].includes(kind)) object.add(halo(object, radius));
  if (kind === 'rocky') object.add(halo(object, radius * 1.1, 1.2, 0.5));  // a rock's air is thin
  if (kind === 'banded') object.add(halo(object, radius * 1.15, 1.2));
  if (kind === 'crystal') object.add(halo(object, radius * 1.05, 1.2, 0.7));
  if (kind === 'ringed') object.add(band(object, radius, 1.45, 2.35, RINGS, false)).children.at(-1).rotation.set(0.42 + tilt, 0, 0.18);
  if (kind === 'sink') {
    object.add(band(object, radius, 1.0, 2.7, DISK, true)).children.at(-1).rotation.set(0.5 + tilt, 0, 0.25);
    object.add(halo(object, radius * 0.62, 1.5, 0.35));
  }
  if (kind === 'pulsar') {
    object.add(jets(object, radius)).children.at(-1).rotation.set(0.35 + tilt, 0, 0.3);
    object.add(corona(object, radius * 0.55, false));
  }
  if (kind === 'star') object.add(corona(object, radius, true));
  if (kind === 'system') moons(object, radius, seed);
  if (kind === 'banded' || kind === 'world') object.rotation.z = tilt * 0.6;
  if (kind === 'rocky') object.rotation.set(seed * 5.1, seed * 11.3, tilt * 1.4);  // each rock lies its own way
  return object;
}
/* A rocky world's shape, one of four: a sphere of eighty faces drawn out along one side and pushed in and out by a
 * smooth wave over its surface, so its outline is a lumpy rock's, never a circle, and its faces catch the light one
 * by one. Each point moves by its own direction alone, so the faces still meet. */
function rock(radius, variant) {
  return shape(`rock:${radius}:${variant}`, () => {
    const geometry = new THREE.IcosahedronGeometry(radius, 1), at = geometry.getAttribute('position');
    const a = 1.3 + variant * 0.9, b = 0.4 + variant * 1.7, c = 2.1 + variant * 0.6, point = new THREE.Vector3();
    for (let i = 0; i < at.count; i++) {
      point.fromBufferAttribute(at, i).normalize();
      const lump = 1 + 0.2 * Math.sin(2.3 * point.x + a) * Math.sin(2.1 * point.y + b)
        + 0.13 * Math.sin(3.7 * point.z + c) + 0.07 * Math.sin(6.0 * point.y + 2.3 * point.x + a);
      point.multiplyScalar(radius * lump).multiply(_long);
      at.setXYZ(i, point.x, point.y, point.z);
    }
    geometry.computeVertexNormals();
    return geometry;
  });
}
const _long = new THREE.Vector3(1.22, 0.86, 0.94);  // a rock drawn out along one side
function hashOf(text) {
  let hash = 0x811c9dc5;
  for (const char of text) { hash ^= char.codePointAt(0); hash = Math.imul(hash, 0x01000193) >>> 0; }
  return hash / 0x100000000;
}

/* ---------- the joins ---------- */

/* A join as a filament of light: added to the sky, bright along its middle where the tube faces the eye, a thin
 * white core, and nothing at its edges, so it reads as a strand of light at any width. The namespace's own edges are
 * fainter than the joins. Never over full brightness, so the bloom never takes it and the map stays clear. Its light
 * is added to what is behind it and writes no depth. The page draws every filament in one draw, `fibers3d`, whose
 * shader gives each its tint and strength, `vFiber`. */
export const FILAMENT = `varying vec3 vNormal; varying vec3 vView; varying vec4 vFiber;
      #include <fog_pars_fragment>
      void main() { vec3 tint = vFiber.rgb; float strength = vFiber.a;
        float facing = abs(dot(normalize(vNormal), normalize(vView)));
        float core = pow(facing, 2.4), thread = pow(facing, 16.0);
        vec3 c = (tint * (0.16 + 0.74 * core) + vec3(0.95) * thread * 0.45) * strength;
        gl_FragColor = vec4(min(c, vec3(0.98)), 1.0);
        #include <fog_fragment>
      }`;

/* ---------- the flow ---------- */

/* The flow's own materials, its dots, streaks, cards and rings, made brighter by `gain` while ultra is drawn: over
 * full brightness, so the bloom turns its requests into points of light and its answers into comets. In clean the
 * gain is 1, and they are drawn exactly as before. Each is found once among the scene's own objects: light added to
 * the picture and drawn last. */
function patchFlow(scene) {
  for (const object of scene.children) {
    const material = object.material;
    if (!material?.isShaderMaterial || U.patched.has(material) || material.blending !== THREE.AdditiveBlending
      || !(object.isPoints || object.isLineSegments) || object.renderOrder !== 10) continue;
    U.patched.add(material);
    material.onBeforeCompile = shader => {
      shader.uniforms.ultraGain = U.gain;
      shader.fragmentShader = 'uniform float ultraGain;\n' + shader.fragmentShader.replace(/}\s*$/, '  gl_FragColor.rgb *= ultraGain;\n}');
    };
    material.customProgramCacheKey = () => 'ultra-gain';
    material.needsUpdate = true;
  }
}

/* ---------- the bloom ---------- */

/* Ultra's bloom, the last pass of the render chain while ultra is drawn. What is over full brightness, with a soft
 * knee so nothing pops as it crosses, is drawn; the knee starts just under full brightness, so the page's names and
 * the filaments, drawn at full brightness at most, never spread into a haze behind the names around them. It is
 * drawn at `bloom` of the picture's size, halved again and again through
 * `levels`, and built back up, each level adding a wider, softer glow; it is added to the picture, a light vignette
 * holds the eye in the middle, and the picture is made ready for the screen with a dither too faint to see that keeps
 * the dark gradients of the sky from banding. */
function makePass(G) {
  const vertex = 'varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }';
  const shader = (fragmentShader, uniforms) => new THREE.ShaderMaterial({uniforms, vertexShader: vertex, fragmentShader,
    depthTest: false, depthWrite: false});
  const over = shader(`uniform sampler2D tDiffuse; uniform vec2 texel; uniform float threshold; uniform float knee; varying vec2 vUv;
    void main() {
      vec3 c = (texture2D(tDiffuse, vUv + texel * vec2(-0.5, -0.5)).rgb + texture2D(tDiffuse, vUv + texel * vec2(0.5, -0.5)).rgb
        + texture2D(tDiffuse, vUv + texel * vec2(-0.5, 0.5)).rgb + texture2D(tDiffuse, vUv + texel * vec2(0.5, 0.5)).rgb) * 0.25;
      float top = max(c.r, max(c.g, c.b));
      float soft = clamp(top - threshold + knee, 0.0, 2.0 * knee); soft = soft * soft / (4.0 * knee + 1e-4);
      gl_FragColor = vec4(c * max(soft, top - threshold) / max(top, 1e-4), 1.0);
    }`, {tDiffuse: {value: null}, texel: {value: new THREE.Vector2()}, threshold: {value: 1.05}, knee: {value: 0.1}});
  const down = shader(`uniform sampler2D tDiffuse; uniform vec2 texel; varying vec2 vUv;
    void main() {
      vec3 c = texture2D(tDiffuse, vUv).rgb * 4.0 + texture2D(tDiffuse, vUv - texel).rgb + texture2D(tDiffuse, vUv + texel).rgb
        + texture2D(tDiffuse, vUv + vec2(texel.x, -texel.y)).rgb + texture2D(tDiffuse, vUv - vec2(texel.x, -texel.y)).rgb;
      gl_FragColor = vec4(c / 8.0, 1.0);
    }`, {tDiffuse: {value: null}, texel: {value: new THREE.Vector2()}});
  // each wider level is weighed by `spread` as it is added to the nearer one, so the glow stays close to what is bright
  const up = shader(`uniform sampler2D tDiffuse; uniform sampler2D tAdd; uniform vec2 texel; uniform float spread; varying vec2 vUv;
    void main() {
      vec3 c = texture2D(tDiffuse, vUv + vec2(-2.0, 0.0) * texel).rgb + texture2D(tDiffuse, vUv + vec2(2.0, 0.0) * texel).rgb
        + texture2D(tDiffuse, vUv + vec2(0.0, -2.0) * texel).rgb + texture2D(tDiffuse, vUv + vec2(0.0, 2.0) * texel).rgb
        + (texture2D(tDiffuse, vUv + vec2(-1.0, 1.0) * texel).rgb + texture2D(tDiffuse, vUv + vec2(1.0, 1.0) * texel).rgb
        + texture2D(tDiffuse, vUv + vec2(-1.0, -1.0) * texel).rgb + texture2D(tDiffuse, vUv + vec2(1.0, -1.0) * texel).rgb) * 2.0;
      gl_FragColor = vec4(c / 12.0 * spread + texture2D(tAdd, vUv).rgb, 1.0);
    }`, {tDiffuse: {value: null}, tAdd: {value: null}, texel: {value: new THREE.Vector2()}, spread: {value: LOOK.spread}});
  const mix = shader(`uniform sampler2D tDiffuse; uniform sampler2D tBloom; uniform float strength; uniform float vignette; varying vec2 vUv;
    float grain(vec2 at) { return fract(sin(dot(at, vec2(12.9898, 78.233))) * 43758.5453); }
    void main() {
      vec4 base = texture2D(tDiffuse, vUv);
      vec3 c = base.rgb + texture2D(tBloom, vUv).rgb * strength;
      c *= 1.0 - vignette * smoothstep(0.42, 1.0, length((vUv - 0.5) * vec2(1.0, 0.82)) * 1.5);
      vec4 shown = linearToOutputTexel(vec4(c, base.a));
      gl_FragColor = vec4(shown.rgb + (grain(gl_FragCoord.xy) - 0.5) / 255.0, shown.a);
    }`, {tDiffuse: {value: null}, tBloom: {value: null}, strength: {value: LOOK.bloom}, vignette: {value: LOOK.vignette}});
  const quad = new FullScreenQuad(over), type = THREE.HalfFloatType;
  const draw = (renderer, material, target) => { quad.material = material; renderer.setRenderTarget(target); quad.render(renderer); };
  let width = 1, height = 1, levels = [];
  const pass = {isPass: true, enabled: false, needsSwap: true, clear: false, renderToScreen: false,
    setSize(w, h) { width = w; height = h; pass.resize(); },
    resize() {
      for (const level of levels) { level.down.dispose(); level.up.dispose(); }
      const q = QUALITY[U.quality];
      levels = [];
      let w = Math.max(1, Math.round(width * q.bloom)), h = Math.max(1, Math.round(height * q.bloom));
      for (let i = 0; i < q.levels && w > 2 && h > 2; i++) {
        levels.push({down: new THREE.WebGLRenderTarget(w, h, {type, depthBuffer: false}),
          up: new THREE.WebGLRenderTarget(w, h, {type, depthBuffer: false})});
        w = Math.max(1, Math.round(w / 2)); h = Math.max(1, Math.round(h / 2));
      }
    },
    render(renderer, writeBuffer, readBuffer) {
      if (!levels.length) return;
      over.uniforms.tDiffuse.value = readBuffer.texture;
      over.uniforms.texel.value.set(1 / readBuffer.width, 1 / readBuffer.height);
      draw(renderer, over, levels[0].down);
      for (let i = 1; i < levels.length; i++) {
        down.uniforms.tDiffuse.value = levels[i - 1].down.texture;
        down.uniforms.texel.value.set(1 / levels[i - 1].down.width, 1 / levels[i - 1].down.height);
        draw(renderer, down, levels[i].down);
      }
      let from = levels[levels.length - 1].down;
      for (let i = levels.length - 2; i >= 0; i--) {
        up.uniforms.tDiffuse.value = from.texture;
        up.uniforms.tAdd.value = levels[i].down.texture;
        up.uniforms.texel.value.set(1 / from.width, 1 / from.height);
        draw(renderer, up, levels[i].up);
        from = levels[i].up;
      }
      mix.uniforms.tDiffuse.value = readBuffer.texture;
      mix.uniforms.tBloom.value = from.texture;
      mix.uniforms.strength.value = LOOK.bloom / Math.max(1, levels.length * 0.5);
      draw(renderer, mix, pass.renderToScreen ? null : writeBuffer);
    },
    // the shaders it draws, which the page links ahead of its first frame; `screen` the one drawn on the screen when last
    quads: () => [{material: over}, {material: down}, {material: up}, {material: mix, screen: true}],
    dispose() { for (const level of levels) { level.down.dispose(); level.up.dispose(); } quad.dispose(); }};
  G.postProcessingComposer().addPass(pass);
  return pass;
}
