/* The bloom pass added to the graph's own render chain, and its samples. */
import '/classic/app/map3d/waves.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
import {G} from '/classic/app/map3d/graph3d.js';

/* The bloom pass, added to the graph's own render chain: what is over full brightness is kept in its hue, blurred at
 * a half, a quarter and an eighth of the size, and added to the picture. It runs while anything on the map is lit
 * above full brightness: a property's reach, a signal on text, a node that needs attention. The glow is put behind
 * whatever is nearer the eye, VIEW-029: the bright part of the picture carries its distance from the eye through the
 * blur, and the glow is added to a point only where what is drawn there is no nearer than the light that reaches it.
 * It is built from the classes of the objects the chain already holds, since the graph library keeps its 3D classes
 * to itself; the depth of the scene is kept in a depth texture of the page's own copy of three.js. */
export let BLOOM = null;
const SOFT = 12;  // over how many units nearer than a light its glow fades out
const SAMPLES = 4;
export const samplesFor = name => /swiftshader|llvmpipe|software|basic render/i.test(name) ? 0 : SAMPLES;
export function drawnBy() {
  const gl = G.renderer().getContext(), told = gl.getExtension('WEBGL_debug_renderer_info');
  return String(told ? gl.getParameter(told.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
}
/* The vertex shader of every bloom pass: the picture's quad as it is. */
const QUAD_VERTEX = 'varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix'
  + ' * vec4(position, 1.0); }';
// How far a point of the picture is from the eye, from the depth the scene was drawn with.
const AWAY = `#include <packing>
    uniform sampler2D sceneDepth; uniform float cameraNear; uniform float cameraFar;
    float away(vec2 at) { return -perspectiveDepthToViewZ(texture2D(sceneDepth, at).x, cameraNear, cameraFar); }`;
// The part over full brightness, and in its fourth channel its distance from the eye weighted by its brightness, so
// the blur carries the distance with the light; divided by the far distance, so it fits the buffer.
const OVER = `${AWAY} uniform sampler2D tDiffuse; varying vec2 vUv;
    void main() { vec3 c = texture2D(tDiffuse, vUv).rgb; float top = max(c.r, max(c.g, c.b));
      vec3 bright = top > 1.0 ? c * (1.0 - 1.0 / top) : vec3(0.0);
      gl_FragColor = vec4(bright, (bright.r + bright.g + bright.b) * away(vUv) / cameraFar); }`;
const BLUR = `uniform sampler2D tDiffuse; uniform vec2 along; varying vec2 vUv;
    void main() { vec4 sum = texture2D(tDiffuse, vUv) * 0.227027;
      sum += (texture2D(tDiffuse, vUv + along * 1.0) + texture2D(tDiffuse, vUv - along * 1.0)) * 0.1945946;
      sum += (texture2D(tDiffuse, vUv + along * 2.0) + texture2D(tDiffuse, vUv - along * 2.0)) * 0.1216216;
      sum += (texture2D(tDiffuse, vUv + along * 3.0) + texture2D(tDiffuse, vUv - along * 3.0)) * 0.054054;
      sum += (texture2D(tDiffuse, vUv + along * 4.0) + texture2D(tDiffuse, vUv - along * 4.0)) * 0.016216;
      gl_FragColor = sum; }`;
const MIX = `${AWAY} uniform sampler2D tDiffuse; uniform sampler2D near; uniform sampler2D mid; uniform sampler2D far;
    uniform float strength; uniform float soft; varying vec2 vUv;
    // The glow of one level at this point, kept where what is drawn here is no nearer the eye than the light that
    // reaches it, and faded out over a short distance nearer than that, so a nearer node covers the glow.
    vec3 behind(vec4 light, float here) {
      float weight = light.r + light.g + light.b;
      if (weight <= 0.0) return vec3(0.0);
      return light.rgb * clamp((here - light.a / weight * cameraFar) / soft + 1.0, 0.0, 1.0);
    }
    void main() { vec4 base = texture2D(tDiffuse, vUv); float here = away(vUv);
      vec3 glow = behind(texture2D(near, vUv), here) + behind(texture2D(mid, vUv), here) * 1.2
        + behind(texture2D(far, vUv), here) * 1.4;
      // The picture and the glow are added as light and then made ready for the screen, so whatever the pass does
      // not light is drawn as it is without the pass.
      gl_FragColor = linearToOutputTexel(vec4(base.rgb + strength * glow, base.a));
    }`;
/* The scene's depth is kept beside its picture, in both of the chain's buffers, since they take turns.
 * The scene is drawn into these buffers and not onto the screen, so the smoothing of edges the screen has does
 * not reach it: each buffer takes four samples a pixel of its own. Without them a link thinner than a pixel,
 * as every link is with the whole map in view, breaks into dots. Where the drawing is done by the processor and
 * not by a graphics card the samples are left out: measured 2026-09-29 they took the page from 10 frames a
 * second to 6 there, and changed nothing that could be seen. */
function deepen(composer) {
  for (const target of [composer.renderTarget1, composer.renderTarget2]) {
    target.depthTexture = new THREE.DepthTexture(target.width, target.height);
    target.samples = samplesFor(drawnBy());
    target.dispose();
  }
}
export function addBloom() {
  const composer = G.postProcessingComposer(), copy = composer?.copyPass;
  if (!copy || !composer.renderTarget1) return;
  // the chain's own classes, since the graph library keeps its copy of three.js to itself
  const Target = composer.renderTarget1.constructor, Material = copy.material.constructor;
  const Quad = copy.fsQuad.constructor;
  deepen(composer);
  const shader = (fragmentShader, uniforms) => new Material({uniforms, vertexShader: QUAD_VERTEX, fragmentShader,
    depthTest: false, depthWrite: false});
  const eye = {sceneDepth: {value: null}, cameraNear: {value: 1}, cameraFar: {value: 1}};
  const over = shader(OVER, {tDiffuse: {value: null}, ...eye});
  const blur = shader(BLUR, {tDiffuse: {value: null}, along: {value: [0, 0]}});
  const mix = shader(MIX, {tDiffuse: {value: null}, near: {value: null}, mid: {value: null}, far: {value: null},
    strength: {value: 0.8}, soft: {value: SOFT}, ...eye});
  const quad = new Quad(over), type = composer.renderTarget1.texture.type;
  const levels = [2, 4, 8].map(() => ({across: new Target(1, 1, {type}), down: new Target(1, 1, {type})}));
  const draw = (renderer, material, target) => {
    quad.material = material;
    renderer.setRenderTarget(target);
    quad.render(renderer);
  };
  /* One frame of the pass: the bright part taken at half size, blurred across and down at each level, each level the
   * next one's start, and the levels mixed into the picture behind what is nearer. */
  const frame = (renderer, writeBuffer, readBuffer, toScreen) => {
    const camera = G.camera();
    eye.sceneDepth.value = readBuffer.depthTexture;
    eye.cameraNear.value = camera.near;
    eye.cameraFar.value = camera.far;
    let from = readBuffer.texture;
    levels.forEach((level, index) => {
      if (index === 0) {
        over.uniforms.tDiffuse.value = from;
        draw(renderer, over, level.down);
        from = level.down.texture;
      }
      blur.uniforms.tDiffuse.value = from; blur.uniforms.along.value = [1 / level.across.width, 0];
      draw(renderer, blur, level.across);
      blur.uniforms.tDiffuse.value = level.across.texture; blur.uniforms.along.value = [0, 1 / level.down.height];
      draw(renderer, blur, level.down);
      from = level.down.texture;
    });
    mix.uniforms.tDiffuse.value = readBuffer.texture;
    [mix.uniforms.near.value, mix.uniforms.mid.value, mix.uniforms.far.value] = levels.map(level => level.down.texture);
    draw(renderer, mix, toScreen ? null : writeBuffer);
  };
  BLOOM = {isPass: true, enabled: false, needsSwap: true, clear: false, renderToScreen: false, levels: levels.length,
    setSize(width, height) { sizeLevels(levels, width, height); },
    render(renderer, writeBuffer, readBuffer) { frame(renderer, writeBuffer, readBuffer, this.renderToScreen); },
    // the shaders it draws, linked ahead of its first frame, `warm3d`; `screen` the one drawn on the screen when last
    quads: () => [{material: over}, {material: blur}, {material: mix, screen: true}],
    dispose() { for (const level of levels) { level.across.dispose(); level.down.dispose(); } }};
  composer.addPass(BLOOM);
}
/* Each level at a half, a quarter and an eighth of the picture's size. */
function sizeLevels(levels, width, height) {
  levels.forEach((level, index) => {
    const share = 2 ** (index + 1);
    const size = [Math.max(1, Math.round(width / share)), Math.max(1, Math.round(height / share))];
    level.across.setSize(...size); level.down.setSize(...size);
  });
}
