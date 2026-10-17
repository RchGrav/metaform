/* The 3D graph: links as fibers, the scene's background, the 3D view started by trying it, a frame drawn only when
 * something moves, and create3D. */
import '/page/app/map3d/ghosts.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
import ForceGraph3D from '3d-force-graph';
// The Space theme, web_theme space: the 3D map in outer space, drawn by its own module through the hooks marked ULTRA.
import * as ULTRA from '/page/ultra.js';
import {$, css, reduced, h, fill} from '/page/app/core/dom.js';
import {toast} from '/page/app/core/controls.js';
import {S, read} from '/page/app/core/reads.js';
import {MASCOT, HANDDRAG} from '/page/app/figures/mascot.js';
import {FIGURE_PICK, figureAt, openFigure} from '/page/app/figures/ask.js';
import {shownNode, colorOf, dim, dimmed, VIEW_SETTINGS, addBehind} from '/page/app/map3d/light.js';
import {addBloom} from '/page/app/map3d/bloom.js';
import {nodeObject, linkColor} from '/page/app/map3d/ghosts.js';
import {linkAt3d, nodeAt3d, clickedAt3d, pick3d, hovered, TIP, hover3d} from '/page/app/map3d/pick3d.js';
import {readout, rehover3d, figureWords} from '/page/app/map3d/readout.js';
import {prepare3d} from '/page/app/map3d/labels.js';
import {fibers3d} from '/page/app/map3d/fibers3d.js';
import {nodes3d} from '/page/app/map3d/nodes3d.js';
import {swap, V3, FLIGHT} from '/page/app/camera/flight.js';
import {MEET, meetEnds, settled3d} from '/page/app/camera/fly3d.js';
import {VIEW} from '/page/app/views/settings.js';
import {PHYS, applyPhysics} from '/page/app/views/bar.js';
import {resize} from '/page/app/views/lens.js';
import {EDGE_PICK} from '/page/app/map2d/hover.js';
import {wake2d} from '/page/app/map2d/flow2d.js';
import {menu} from '/page/app/board/messages.js';
import {posted} from '/page/app/intake/intake.js';

/* The links are fibers, VIEW-005, shaded as the nodes are rather than flat: the graph library drew each as a matte
 * tube that light falls on evenly, beside nodes of glass that give off light, so the two did not look of one map. A
 * fiber gives off its color with a bright core along its middle, where the tube faces the eye, and dims toward its
 * rim, so it reads as a round strand of light at any width. It is never brighter than full, so the bloom never takes
 * it: light that spreads on the map means a node needs attention, VIEW-029, and fibers that glowed with it made the
 * whole map hazy whenever one did. The page draws every fiber of a look in one draw, `fibers3d`: each is an instance
 * of one tube, its tint and opacity its own, `fiber`. `version` counts the changes to what the links are or how they
 * look, so each link's look is read again only then. */
export const FIBERS = {version: 0};
/* The least width an edge is drawn at on the screen, VIEW-005: Rich, 2026-10-17, "enforce a minimal width of the
 * edges". A fiber is as wide as its link in the map, so a near one widens by perspective; where that would draw it
 * thinner than `least` CSS pixels across, the vertex shader widens its tube at that end to `least`, from the depth of
 * the point on its axis, so a far edge never thins to nothing and a near one is as perspective makes it. The tube is
 * six-sided, so `least` is held across its flats, its narrowest. `uniform.value` is `least` over the stage's height
 * in CSS pixels, set when the stage is measured, never each frame; every fiber material shares the one uniform. */
export const EDGE = {least: 1.5, uniform: {value: 0}};
// a fiber takes the haze of depth as the nodes do, `depth3d`, through three.js's own fog
export const FIBER_VERTEX = `attribute vec4 fiber; uniform float edgeLeast;
      varying vec3 vNormal; varying vec3 vView; varying vec4 vFiber;
      #include <fog_pars_vertex>
      void main() { vec4 axis = modelViewMatrix * instanceMatrix * vec4(0.0, 0.0, position.z, 1.0);
        vec3 side = mat3(modelViewMatrix) * (mat3(instanceMatrix) * vec3(position.xy, 0.0));
        float radius = length(mat3(modelViewMatrix) * instanceMatrix[0].xyz);
        // the radius that draws least across the tube's flats at this depth: w over the lens's scale is the map
        // units the stage's height spans, halved, and the flats are cos 30 degrees of the radius
        float least = edgeLeast * (projectionMatrix * axis).w / projectionMatrix[1][1] / 0.8660254;
        vec4 at = axis + vec4(side * max(1.0, least / max(radius, 1e-6)), 0.0);
        vNormal = normalize(normalMatrix * mat3(instanceMatrix) * normal);
        vView = normalize(-at.xyz); vFiber = fiber; gl_Position = projectionMatrix * at;
        vec4 mvPosition = at;
        #include <fog_vertex>
      }`;
export const FIBER_FRAGMENT = `varying vec3 vNormal; varying vec3 vView; varying vec4 vFiber;
      #include <fog_pars_fragment>
      void main() { vec3 tint = vFiber.rgb; float opacity = vFiber.a;
        float facing = abs(dot(normalize(vNormal), normalize(vView)));
        float core = pow(facing, 1.6), spark = pow(facing, 12.0);
        gl_FragColor = vec4(tint * min(1.0, 0.4 + 0.5 * core + 0.3 * spark), opacity * (0.25 + 0.75 * core));
        #include <fog_fragment>
      }`;
export let G = null;
/* The size of a node and the width of a link, in the map's units, so the eye's perspective alone sizes them: a node or
 * an edge near the eye is large and thick, one far away small and fine, and scale reads from them as it does from the
 * names. No node or name is held to a size on the screen; an edge is held only to a least width, `EDGE`. Raised
 * 2026-10-17 at Rich's request, the edges and nodes having read as too thin and small: each link twice as wide, and
 * an element's ball half as wide again on the screen as before from the same camera. A ball's radius is the cube root
 * of its value, times 3, and the 60-degree lens shows a map unit at 0.81 of the old 50-degree lens's size, so the old
 * values (DE 9, CQU 7, others 4) are raised by (1.5 / 0.81) cubed, about
 * 6.4. Purposes, items and the rest keep their size. Raised again the same day at his request, "increasing the width
 * of the edges and node sizes": each link half as wide again, and an element's ball 1.3 times as wide on the screen,
 * its value times 1.3 cubed (DE 58 to 127, CQU 45 to 99, others 26 to 57). A fiber is never drawn thinner than
 * `EDGE.least` on the screen. */
export const nodeSize = node => node.t === 'el' ? (node.role === 'DE' ? 127 : node.role === 'CQU' ? 99 : 57)
  : node.t === 'purpose' ? 1.8 : node.t === 'item' ? 0.6 : 0.7;
export const linkWidthOf = link => link.k === 'tree' ? 1.2 : link.k === 'layer' || link.k === 'item' ? 0.75
  : link.k === 'relation' ? 1.5 : 2.7;
/* The haze of depth, VIEW-038: what is far from the eye is dimmed toward the background, the theme's ground, as the
 * air dims a far hill, so the nodes, the edges and the figures say their depth as the names do. Its span is the names'
 * own fade, from the front of the names in view, where nothing is hazed, to past their back, where a thing keeps
 * `HAZE.back`'s complement of its own colour; it is set each time the names are placed, `layered`, so a still frame
 * changes nothing. One three.js fog, the scene's, kept for the page's life: the materials three.js draws take it as
 * they are, and the page's own shaders, the fibers and outer space's bodies, take it through three.js's fog chunks.
 * The labels fade by their own depth and take none. */
export const HAZE = {fog: new THREE.Fog(0x000000, 1e9, 2e9), back: 0.6, span: 0};
// the share of the fog's span at which three.js's linear fog, a smoothstep, reaches `back`: the smoothstep's inverse
HAZE.span = 0.5 - Math.sin(Math.asin(1 - 2 * HAZE.back) / 3);
export function depth3d(nearest, deepest) {
  const fog = HAZE.fog;
  if (!(deepest > nearest) || !Number.isFinite(nearest) || !Number.isFinite(deepest)) {
    fog.near = 1e9; fog.far = 2e9;
    return;
  }
  fog.near = nearest;
  fog.far = nearest + (deepest - nearest) / HAZE.span;
}
/* The background is part of the scene as well as the graph's clear color. The render chain clears its buffer before
 * three.js draws into it, with the clear color last converted for the screen; three.js clears a scene's background
 * itself in the color space of whatever it draws into, so with the bloom on the background is the one drawn without
 * it, VIEW-022. */
export function grounded() {
  G.scene().background = new THREE.Color(css('--ground'));
  HAZE.fog.color.set(css('--ground'));  // the haze of depth is the ground's colour
  G.scene().fog = HAZE.fog;
}
/* The dots that travel a join are drawn solid, VIEW-005, as the approved prototype draws them. The graph library gives
 * a dot three times the opacity of the links, which a picture drawn on the screen holds at 1. The pictures this page
 * draws for the glass, and for the bloom while it is on, keep light over full brightness and hold no such limit: with
 * links at 0.8 a dot there was drawn as 2.4 times its color less 1.4 times what was behind it, so a dot passing through
 * a white node, or in front of it, turned it dark. The library makes the dots' materials again
 * whenever the map or the theme changes, so each is held at 1 as the scene is drawn. */
function solid() {
  for (const link of G.graphData().links) for (const dot of link.__photonsObj?.children || [])
    if (dot.material.opacity > 1) dot.material.opacity = 1;
}
/* The 3D view is started by trying it, never by asking the browser whether it can: a browser can say it has WebGL
 * and still fail when it is used, as Moli's answers null for the scissor box and three.js stops on it. When anything in
 * the start fails, the 2D map takes the large area and the small one says why, so the map still works there. */
export function start3D() {
  try {
    if (typeof ForceGraph3D !== 'function') throw new Error('the 3D library did not load');
    create3D();
  } catch (error) {
    G = null;
    fill($('#stage'), h('p', {class: 'empty', style: {padding: '24px'}},
      `The 3D view could not start in this browser (${error.message}). The 2D map works as usual.`));
    swap(true, false);
  }
}
/* The 3D map draws a frame only when something on it moves, so a page left alone costs the machine nothing. The page
 * runs the graph's frames itself, `frame3d`, in place of the library's own loop, which draws every frame forever. A
 * frame is drawn while the layout settles, the camera flies or coasts, the pointer is on the map, a part flashes or
 * pulses, a property's wave, a part's text or an agent moves, and for `grace` after anything changes what is drawn:
 * every setter of the graph and every act on the map wakes it, `wake3d`. The dots that flow along the joins, a part's
 * flash or pulse, a ghost rising, an agent's figure, a lit reach and the mascot up and about move without end: while
 * any of them runs, every frame is drawn, at the screen's rate, for as long as the page is open. With web_idle_flow
 * off the map may rest: left alone for `idle` (web_flow_seconds), it stops drawing until the next act or until its
 * tab comes back into view. It is never drawn at a lower rate. With reduced motion nothing flows or flashes, so an
 * idle map draws nothing at all. */
export const FRAMES = {id: 0, held: false, until: 0, active: 0, last: 0, drawn: 0, engine: false,
  moved: false, busy: false, flowing: false, grace: 700, idle: 30000, rest: null};
// `idle` and `rest` are the web module's settings, web_flow_seconds and web_idle_flow, read with the workspace: rest
// null, the default, keeps the map running; 0 lets it stop `idle` after the last act or change.
/* The 3D area's size on the page, kept by an observer of #stage as it changes, `create3D`, so a frame reads it here
 * and never asks the page for a layout: each read of a size after the 2D flow wrote its styles forced a second layout
 * every frame (round 7's F5, 2026-10-15). */
export const STAGE = {width: 0, height: 0};
const DAMPING = 0.12;
// the share of a turn of the camera a hand gave that it loses each 60th of a second: it coasts
// (DAMPING, above); and the share of its speed a node loses each tick while one is dragged, 0.4 otherwise
export const DRAG_FRICTION = 0.65;
/* What waits on the figures as they move, each told at the end of every frame that moved them, `settle`: frames run
 * while one waits, and nothing checks between them. A dense array walked by index, so a frame allocates nothing. */
export const AFTER = [];
export function afterFrames(told) { AFTER.push(told); wake3d(); }
export function noMoreFrames(told) {
  const at = AFTER.indexOf(told);
  if (at < 0) return;
  AFTER[at] = AFTER[AFTER.length - 1];
  AFTER.pop();
}
export function wake3d(ms = FRAMES.grace) {
  const now = performance.now();
  FRAMES.until = Math.max(FRAMES.until, now + ms);
  FRAMES.active = now;
  wake2d();  // the selected node's flow in the 2D map goes on with any act, as the 3D map's does
  if (!G || FRAMES.held || FRAMES.id) return;
  FRAMES.id = requestAnimationFrame(frame3d);
}
function frame3d(now) {
  // While a frame is drawn `id` holds a mark, so a wake from inside the frame asks for no frame of its own: the frame
  // asks for one next frame at its end, and only one, or every wake would start a second run of frames beside it.
  FRAMES.id = -1;
  if (!G || FRAMES.held) { FRAMES.id = 0; return; }
  const passed = Math.min(0.1, Math.max(0.001, (now - (FRAMES.last || now - 16)) / 1000));
  FRAMES.last = now;
  FRAMES.engine = FRAMES.moved = false;
  const controls = G.controls();  // the camera coasts for the same time at any frame rate
  if (controls.enableDamping) controls.dampingFactor = 1 - Math.pow(1 - DAMPING, passed * 60);
  try { G._animationCycle(); }  // the layout's tick, the dots, the controls, the picture and what the pointer is over
  finally { G.pauseAnimation(); FRAMES.id = 0; releaseChain(); keepPrograms(); }  // the page asks for its own frame
  FRAMES.drawn++;
  for (let at = AFTER.length - 1; at >= 0; at--) {  // from the end, so one that lets go of itself skips none
    const told = AFTER[at];
    try { told(now); } catch (error) { noMoreFrames(told); reportError(error); }  // the frames go on whatever it does
  }
  const still = now - FRAMES.active;
  if (moving3d(now, still)) FRAMES.id = requestAnimationFrame(frame3d);
}
/* Whether the next frame is drawn: something changed lately, the layout or the camera moves, or a flight is under way;
 * and while the flow or an ambient animation runs (a figure, the mascot, a record's flash), every frame, for as long
 * as the page is open. Only with web_idle_flow off may the map rest: once it has been left alone for `idle` it stops
 * drawing, and the next act, or the tab coming back into view, wakes it. It is never drawn at a lower rate. */
function moving3d(now, still) {
  if (now < FRAMES.until || FRAMES.engine || FRAMES.moved || FLIGHT.on) return true;
  if (AFTER.length > 0 || WARM.waiting !== null) return true;  // a wait on the figures, or shaders linking
  return (FRAMES.busy || FRAMES.flowing) && (FRAMES.rest === null || still < FRAMES.idle);
}
// A tab the person comes back to is drawn at once: a hidden tab gets no frames, and nothing else would wake it.
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') wake3d(); });
/* The library's setters and the methods that change what is drawn wake the map, as does every camera move asked for
 * from outside the page's own flights; such a move also ends a flight under way and, unless it fits the whole map,
 * tells the settled layout not to fit it again, since someone put the camera where it is. */
const WAKERS = new Set(['refresh', 'd3ReheatSimulation', 'resumeAnimation', 'emitParticle']);
const READERS = new Set(['graph2ScreenCoords', 'screen2GraphCoords', 'getGraphBbox', 'getPointerPos',
  'pauseAnimation']);
function wakeful(graph) {
  for (const [name, method] of Object.entries(graph)) {
    if (typeof method !== 'function' || name.startsWith('_') || READERS.has(name)) continue;
    graph[name] = function (...args) {
      // a getter, a force asked for by its name, or a reading of where something is drawn changes nothing
      const reading = (!args.length && !WAKERS.has(name)) || (name === 'd3Force' && args.length < 2);
      if (reading) return method.apply(this, args);
      if (name === 'graphData' || name === 'refresh' || name.startsWith('link')) FIBERS.version++;
      if (name === 'cameraPosition' || name === 'zoomToFit') {
        FLIGHT.on = false;
        V3.focus = V3.hold = null;
        V3.auto = name === 'zoomToFit';
        const takes = Number(args[name === 'zoomToFit' ? 0 : 2]) || 0;
        wake3d(FRAMES.grace + takes);
        setTimeout(rehover3d, takes);  // the readout decided again once the flight is done
      } else wake3d();
      return method.apply(this, args);
    };
  }
}
/* A node the page draws no object for, a purpose vertex in the clean themes, is the graph library's own sphere, whose
 * shape and material the library makes for it at each digest. When the library takes such a node away, as it does for
 * every node when the theme or the graphics change, it frees only what the object holds inside it and leaves the
 * sphere's own shape and material on the graphics card, one more for each change. They are freed here once the digest
 * is done, unless a node still drawn shares them. */
const FREED = {gone: new Set(), queued: false, watched: new WeakSet()};
const isLibrary = object => typeof object.tickFrame === 'function';
function freeDefaults() {  // the library's group of nodes and links, now or once it is put in the scene
  for (const child of G.scene().children) if (isLibrary(child)) freeing(child);
  G.scene().addEventListener('childadded', ({child}) => { WARM.added++; if (isLibrary(child)) freeing(child); });
}
function freeing(library) {
  if (FREED.watched.has(library)) return;
  FREED.watched.add(library);
  library.addEventListener('childadded', () => { WARM.added++; });  // a node made, whose shaders `warm3d` links
  library.addEventListener('childremoved', ({child}) => {
    if (!child.__graphDefaultObj) return;
    FREED.gone.add(child);
    if (FREED.queued) return;
    FREED.queued = true;
    queueMicrotask(() => {
      const kept = new Set();
      for (const one of library.children) if (one.__graphDefaultObj) kept.add(one.geometry).add(one.material);
      for (const one of FREED.gone) {
        if (!kept.has(one.geometry)) one.geometry.dispose();
        if (!kept.has(one.material)) one.material.dispose();
      }
      FREED.gone.clear();
      FREED.queued = false;
    });
  });
}
/* Shaders are linked before they are drawn, F5. three.js links a material's shader the first time it draws it and
 * then waits for the link on the page's thread, one shader after another: 2.4 to 3.6 s at load. Whenever something is
 * put in the scene (`added`), the links change (FIBERS.version) or a pass is turned on or off, the page's own pass
 * hands three.js's compile every material in the scene, for the picture the scene is drawn into, with the far walls
 * of the glass and each pass's own shaders, `quads`; that starts the links side by side, off the page's thread. The
 * frame is drawn only once they are done (`waiting`), up to `most` ms; the frames before it are not drawn, so the map
 * shows the picture it showed until then. Every shader linked is kept for as long as the page is open (`kept`), so a
 * map read again or a theme switched back links nothing: three.js frees a shader once no material uses it, and every
 * whole reload made each again. Shader errors are read only at a developer level, as reading them waits for the link
 * too, `applyView`. Without parallel linking in the browser, a frame waits as before. */
export const WARM = {added: 0, seen: '', waiting: null, done: null, linked: null, since: 0, most: 5000, held: [],
  kept: new WeakSet(),
  programs: 0, quad: new THREE.Mesh(new THREE.PlaneGeometry(2, 2))};
function warm3d(renderer, read) {
  if (WARM.waiting) return linking3d();
  const scene = G.scene(), composer = G.postProcessingComposer();
  const mark = `${WARM.added} ${FIBERS.version} ${composer.passes.map(pass => pass.enabled ? 1 : 0).join('')}`;
  if (mark === WARM.seen) return false;
  WARM.seen = mark;
  const at = composer.passes.findIndex(pass => pass.scene === scene);
  const was = renderer.getRenderTarget();
  // the picture the scene pass draws into, as a shader is linked for the screen or for a picture drawn on
  renderer.setRenderTarget(at >= 0 && composer.renderToScreen && composer.isLastEnabledPass(at) ? null : read);
  const camera = G.camera(), materials = new Set();
  try {
    for (const material of renderer.compile(scene, camera)) materials.add(material);
    // the far wall of each glass node, which the picture behind the glass is drawn with, `drawBehind`
    for (const material of renderer.compile(farWalls(scene), camera, scene)) materials.add(material);
    // each pass's own shaders, drawn on a picture, or on the screen by the last pass
    composer.passes.forEach((pass, index) => {
      if (!pass.enabled || !pass.quads) return;
      const last = composer.renderToScreen && composer.isLastEnabledPass(index);
      for (const {material, screen} of pass.quads()) {
        renderer.setRenderTarget(screen && last ? null : read);
        WARM.quad.material = material;
        for (const one of renderer.compile(WARM.quad, camera)) materials.add(one);
      }
    });
  } finally { renderer.setRenderTarget(was); }
  const linking = [...materials].map(material => renderer.properties.get(material).currentProgram)
    .filter(program => program && !program.isReady());
  if (!linking.length) return false;
  WARM.waiting = linking;
  WARM.since = performance.now();
  WARM.done = new Promise(go => { WARM.linked = go; });
  return true;
}
/* At each frame while shaders link, the frame that would draw with them, `moving3d` keeping the frames coming: those
 * linked are let go, and once none is left, or `most` ms have passed, this frame is drawn. The browser's parallel
 * linking, KHR_parallel_shader_compile, has no event of its own: it says a link is done only when asked,
 * COMPLETION_STATUS_KHR (program.isReady), so it is asked by the frames being drawn, and never between them. */
function linking3d() {
  const waiting = WARM.waiting;
  for (let at = waiting.length - 1; at >= 0; at--) {
    if (!waiting[at].isReady()) continue;
    waiting[at] = waiting[waiting.length - 1];
    waiting.pop();
  }
  if (waiting.length > 0 && performance.now() - WARM.since < WARM.most) return true;
  WARM.waiting = null;
  WARM.linked();
  return false;
}
/* The glass nodes of the scene each with its far wall on, as `drawBehind` draws them, for three.js's compile, which
 * reads only `traverse` of a scene it is given beside the scene drawn. */
const farWalls = scene => ({traverse(visit) {
  scene.traverse(object => {
    const near = object.material, far = near?.userData?.back;
    if (!far) return;
    object.material = far;
    try { visit(object); } finally { object.material = near; }
  });
}, traverseVisible() {}});
/* The passes after the page's own are not drawn this frame, and are drawn again from the next. */
function holdChain(own) {
  for (const pass of G.postProcessingComposer().passes) {
    if (pass !== own && pass.enabled) { pass.enabled = false; WARM.held.push(pass); }
  }
}
function releaseChain() { for (const pass of WARM.held.splice(0)) pass.enabled = true; }
/* Each shader linked is kept: three.js counts the materials using it and frees it at none. */
function keepPrograms() {
  const programs = G.renderer().info.programs;
  if (!programs || programs.length === WARM.programs) return;
  for (const program of programs) if (!WARM.kept.has(program)) { WARM.kept.add(program); program.usedTimes++; }
  WARM.programs = programs.length;
}
/* Resolved once the shaders being linked are done, for a switch of looks that waits for them under its veil. */
export const linked3d = () => WARM.waiting ? WARM.done : Promise.resolve();
function create3D() {
  G = ForceGraph3D({controlType: 'orbit'})($('#stage'));
  G.renderer().debug.checkShaderErrors = false;  // read at a developer level, `applyView`
  G.pauseAnimation();  // the page runs the frames, `frame3d`
  wakeful(G);
  configure3d();
  grounded();
  G.scene().onBeforeRender = solid;
  freeDefaults();
  addBehind();
  addBloom();
  ULTRA.setting(document.documentElement.dataset.theme === 'space' ? 'ultra' : 'clean');  // the theme decides the look
  ULTRA.attach(G, {wake: wake3d, reduced, css, selected: () => S.selected, hovered: () => hovered?.id ?? null,  // ULTRA
    dimmed: node => Boolean(dimmed(node)), idle:() => performance.now() - FRAMES.active > FRAMES.idle, toast,
    chained: () => FRAMES.id > 0, settings: async () => (await read('settings')).settings || [],
    save: async value => {  // the theme the look names: space, or the last plain one; draw3d.js loads after this part
      const {PLAIN} = await import('/page/app/map3d/draw3d.js');
      return posted('/api/settings', {key: 'web_theme', value: value === 'ultra' ? 'space' : PLAIN.last});
    },
    shapes: () => VIEW_SETTINGS.shapes,
    linked: linked3d, stage: STAGE});
  // The page's own work for each frame runs first in the render chain: after the layout's tick and the controls, before
  // anything is drawn, so the camera's flight, the labels, the dots and the tooltip are all of the same frame.
  G.postProcessingComposer().insertPass({isPass: true, enabled: true, needsSwap: false, clear: false,
    renderToScreen: false, setSize() {}, dispose() {},
    render(renderer, write, read) { prepare3d(); fibers3d(); nodes3d(); if (warm3d(renderer, read)) holdChain(this); }},
  0);
  applyPhysics(PHYS.name, false);  // the forces of the physics chosen, `PHYSICS`
  steer3d(G.controls());
  listen3d($('#stage'));
  const stage = $('#stage'), measure = () => {
    const box = stage.getBoundingClientRect();
    STAGE.width = box.width; STAGE.height = box.height;
    EDGE.uniform.value = EDGE.least / (box.height || 1);  // the edges' least width, `EDGE`
  };
  measure();
  new ResizeObserver(measure).observe(stage);
  resize();
  wake3d();
}
/* How the graph draws the map: its nodes and their shapes, colors and visibility, the links as fibers, the dots, the
 * layout's settling, and what a drag, a click and a right-click do. */
function configure3d() {
  G.backgroundColor(css('--ground'))
    .showNavInfo(false)
    .nodeRelSize(3)
    .nodeVal(nodeSize)
    .nodeThreeObject(node => nodeObject(node))
    .nodeColor(node => dimmed(node) ? dim(colorOf(node)) : colorOf(node))
    .nodeVisibility(shownNode)
    .linkVisibility(link => VIEW.edges !== false && shownNode(link.source) && shownNode(link.target))
    .nodeOpacity(0.95)
    .nodeResolution(16)
    .nodeLabel(() => '')  // the page shows its own tooltip, anchored above the node, not under the pointer
    .onNodeHover(() => {})  // the hover is the page's nearest-node choice, `nodeAt3d`
    .linkColor(linkColor)
    .linkOpacity(Number(css('--link-opacity')))
    // the page draws the fibers, `fibers3d`; the library keeps for each link only an object saying it is shown
    .linkThreeObject(() => Object.assign(new THREE.Object3D(), {matrixAutoUpdate: false}))
    .linkPositionUpdate(() => true)
    .linkCurvature(0)
    // the page draws the flow itself, `flow3d`: the library's own dot, one to a link, is made only while a browser
    // check holds the dots still, `dots3d`, so no frame moves or hides one that is never shown
    .linkDirectionalParticles(0)
    .linkDirectionalParticleSpeed(0)
    .linkDirectionalParticleWidth(1.6)
    .linkDirectionalParticleColor(linkColor)
    // The layout settles once its energy is spent rather than after a fixed time, and the map is then fitted to the
    // view if nobody has moved the camera, `settled3d`.
    .d3AlphaMin(0.001)
    .onEngineTick(() => { FRAMES.engine = true; V3.ticks++; })
    .onEngineStop(() => { if (V3.ticks > 30) settled3d(); V3.ticks = 0; })
    .onNodeDrag(dragNode)
    .onNodeDragEnd(() => { HANDDRAG.node = null; G.d3AlphaMin(0.001).d3VelocityDecay(PHYS.decay); })
    .onNodeClick((node, event) => clickedAt3d(event))
    // a click on no node takes the nearest join's edge within reach, `linkAt3d`, as the 2D map does
    .onLinkClick((link, event) => clickedAt3d(event))
    .onBackgroundClick(event => clickedAt3d(event))
    .onNodeRightClick((node, event) => { if (node) menu(node.id, event.clientX, event.clientY); });
}
/* A node dragged gives the layout energy, so the nodes joined to it follow and the map settles again once it is let
 * go: a settled layout would stop at once and leave the map rigid, so it is kept running while a node is held. The
 * graph library warms it to 0.3 for a drag, which throws the whole map about; the nodes move against more friction
 * while one is held, DRAG_FRICTION, so the map follows gently. The mascot never pushes the node in the person's hand,
 * and lets go of one taken from it. */
function dragNode(node) {
  HANDDRAG.node = node;
  if (MASCOT.holding === node) { MASCOT.holding = null; MASCOT.job = null; }
  G.d3AlphaMin(0).d3VelocityDecay(DRAG_FRICTION);
}
/* The camera coasts after a hand lets it go, and the wheel zooms toward the point under the pointer. A hand on the
 * camera releases a meeting: the sign goes back into the scene, the map behind comes back into focus, and the camera
 * stays where the hand leaves it, so the small area is a map to look around, until the next selection meets a sign
 * again; the camera no longer follows the met node as the layout moves, `holdMet`. */
function steer3d(controls) {
  Object.assign(controls, {enableDamping: true, dampingFactor: DAMPING, zoomToCursor: true});
  controls.addEventListener('start', () => {
    FLIGHT.on = false; V3.auto = false; V3.focus = V3.hold = null; hover3d(null);
    if (MEET.on) meetEnds();
  });
  // the readout is decided again at rest
  controls.addEventListener('change', () => { FRAMES.moved = true; rehover3d(); });
}
/* When the person last used a map: a press, the wheel or a drag on either map, a map key, or a node they chose. An
 * agent start moves the cameras under auto zoom only when nothing of these came in the last 8 seconds, so the map
 * never moves under the person's hands, VIEW-041. */
export const TOUCHED = {at: -Infinity};
export const touched = () => { TOUCHED.at = performance.now(); };
/* The 3D map's own pointer and keys: any act wakes it; the pointer's node, edge or figure is marked; a click on a
 * figure opens its thread; a press elsewhere or a key ends the tooltip. */
function listen3d(stage) {
  for (const type of ['pointerdown', 'wheel', 'keydown']) {
    stage.addEventListener(type, () => { touched(); wake3d(); }, {passive: true});
  }
  for (const type of ['pointerenter', 'pointermove']) {
    stage.addEventListener(type, () => { TIP.out = false; wake3d(); }, {passive: true});
  }
  stage.addEventListener('pointerleave', () => { TIP.out = true; hover3d(null); pick3d(null); });
  stage.addEventListener('pointermove', pointAt3d, {passive: true});
  // a click on an agent's figure, not a drag of the camera, opens its thread
  stage.addEventListener('pointerdown', event => { FIGURE_PICK.down = [event.clientX, event.clientY]; }, true);
  stage.addEventListener('click', clickFigure);
  // A press anywhere else, or a key, ends the tooltip: a menu or a window may now cover the node it named.
  document.addEventListener('pointerdown', event => { if (!stage.contains(event.target)) hover3d(null); }, true);
  document.addEventListener('keydown', () => hover3d(null), true);
}
/* The edge a click would take, marked once a frame as the pointer moves; a node under the pointer takes the click. */
function pointAt3d(event) {
  if (EDGE_PICK.frame3d || event.buttons) return;
  const {clientX: x, clientY: y} = event;
  EDGE_PICK.frame3d = requestAnimationFrame(() => {
    EDGE_PICK.frame3d = 0;
    // the node nearest the pointer within reach, then the nearest edge: what a click will take, `pickAt3d`
    if (!TIP.out) hover3d(nodeAt3d(x, y));
    const link = hovered ? null : linkAt3d(x, y);
    pick3d(link);
    $('#stage').classList.toggle('picking', Boolean(hovered || link));
    // an agent's figure under the pointer, with no node or edge, is said in the readout and takes the click
    const work = !hovered && !link ? figureAt(x, y) : null;
    if (work) readout('3d', figureWords(work));
    else if (!hovered && !link) readout('3d', null);
  });
}
function clickFigure(event) {
  const down = FIGURE_PICK.down;
  if (!down || Math.hypot(event.clientX - down[0], event.clientY - down[1]) > 5) return;
  const work = figureAt(event.clientX, event.clientY);
  if (work) openFigure(work);
}
/* The 3D layout held still or running, P and R, which ? lists: `paused` while every vertex is pinned where it is. */
export const LAYOUT = {paused: false};
/* Pausing pins every vertex where it is; resuming frees them and warms the layout. A toast says which, as no button
 * shows it. */
export function pauseLayout() {
  if (!G) return;
  const paused = LAYOUT.paused;
  for (const node of G.graphData().nodes) Object.assign(node, paused ? {fx: undefined, fy: undefined, fz: undefined}
    : {fx: node.x, fy: node.y, fz: node.z});
  if (paused) G.d3ReheatSimulation(); else wake3d();
  LAYOUT.paused = !paused;
  toast(paused ? 'The 3D layout runs again.' : 'The 3D layout is paused; P resumes it.');
}
/* A new layout: every vertex given a new place, settled again and fitted to the view as it settles. */
export function relayout() {
  if (!G) return;
  const data = G.graphData();
  const placed = ['x', 'y', 'z', 'vx', 'vy', 'vz', 'fx', 'fy', 'fz'];
  for (const node of data.nodes) for (const key of placed) delete node[key];
  LAYOUT.paused = false;
  toast('The 3D layout runs again from new places.');
  V3.auto = true;
  G.graphData(data);  // the layout gives vertices without a position new ones and settles again
}
