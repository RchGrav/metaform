/* The 3D flow's drawing: points and line segments for dots, cards and rings, requests and replies along joins, live
 * trips, and flow3d each frame. */
import '/page/app/flow/flow.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
import {css, reduced} from '/page/app/core/dom.js';
import {ballOf} from '/page/app/figures/agents.js';
import {fxMarks} from '/page/app/figures/walk.js';
import {EYE, eyeDebug3d} from '/page/app/figures/eyes.js';
import {colorOf} from '/page/app/map3d/light.js';
import {G, FRAMES} from '/page/app/map3d/graph3d.js';
import {AT} from '/page/app/map3d/labels.js';
import {FLOW, flowShown, flowModeNow, flowNet, flowAt, flowTick} from '/page/app/flow/flow.js';

/* The 3D flow's two objects: points, each a dot, a card or a ring by its shape, and line segments for the streaks'
 * tails, both added to what is behind them so they read as light. Their buffers grow as needed and are filled again
 * each frame. A point's size is in map units, held between a few pixels and its own most, `look`. Each frame fills
 * the next of RING pairs and shows it alone: a buffer the GPU may still be reading for a frame before is never
 * written, since that write waits for the frame to be drawn, `fibers3d`. `points`, `lines` and the arrays are the
 * pair being filled. */
export const FX = {scene: null, points: null, lines: null, n: 0, m: 0, cap: 0, capL: 0, tints: new Map(), fade: 1,
  ring: [], at: 0};
const RING = 3;
const WHITE = new THREE.Color(1, 1, 1), LIT = new THREE.Color();
export function tintOf(color) {
  if (!FX.tints.has(color)) FX.tints.set(color, color ? new THREE.Color(color) : WHITE.clone());
  return FX.tints.get(color);
}
// What travels runs along the middle of a link, inside its fiber, which is drawn with depth: each point is set a
// little toward the eye for the depth test alone, where it is drawn on the screen unchanged, so the fiber never
// hides it and a node still does.
const NEAR = `
      vec4 near(vec4 at) { float far = length(at.xyz); at.xyz *= max(0.01, far - 1.5) / far; return at; }`;
const POINTS_VERTEX = `attribute vec4 tint; attribute vec4 look; uniform float scale; uniform float ratio;
      varying vec4 vTint; varying float vShape;${NEAR}
      void main() {
        vec4 at = near(modelViewMatrix * vec4(position, 1.0));
        gl_Position = projectionMatrix * at;
        gl_PointSize = clamp(look.x * scale / max(0.001, -at.z), look.z * ratio, max(look.z, look.w) * ratio);
        vTint = tint; vShape = look.y;
      }`;
// a dot is a white-hot core in a glow of its colour; a card, a small lit rectangle with two lines across it; a
// ring, a thin circle
const POINTS_FRAGMENT = `varying vec4 vTint; varying float vShape;
      void main() {
        vec2 c = gl_PointCoord * 2.0 - 1.0;
        float d = length(c), a = 1.0;
        vec3 color = vTint.rgb;
        if (vShape < 0.5) {
          a = max(smoothstep(0.6, 0.35, d), 0.7 * pow(max(0.0, 1.0 - d), 1.5));
          color = mix(color, vec3(1.0), 0.25 + 0.75 * smoothstep(0.6, 0.1, d));
        } else if (vShape < 1.5) {
          vec2 q = abs(c) / vec2(0.86, 0.64);
          float edge = max(q.x, q.y);
          if (edge > 1.0) discard;
          float line = step(abs(abs(c.y) - 0.2), 0.08) * step(abs(c.x), 0.55);
          color = mix(color, vec3(1.0), 0.35 * smoothstep(0.7, 0.95, edge)) * (1.0 - 0.5 * line);
        } else {
          a = smoothstep(0.14, 0.0, abs(d - 0.84));
        }
        if (a * vTint.a < 0.004) discard;
        gl_FragColor = vec4(color, a * vTint.a);
      }`;
const LINES_VERTEX = `attribute vec3 shade; varying vec3 vShade;${NEAR}
      void main() { gl_Position = projectionMatrix * near(modelViewMatrix * vec4(position, 1.0)); vShade = shade; }`;
const LINES_FRAGMENT = `varying vec3 vShade; void main() { gl_FragColor = vec4(vShade, 1.0); }`;
function fxMake() {
  const scene = G.scene();
  if (FX.scene === scene) return;
  FX.scene = scene;
  const light = {transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false};
  const points = new THREE.ShaderMaterial({...light, uniforms: {scale: {value: 1}, ratio: {value: 1}},
    vertexShader: POINTS_VERTEX, fragmentShader: POINTS_FRAGMENT});
  const lines = new THREE.ShaderMaterial({...light, vertexShader: LINES_VERTEX, fragmentShader: LINES_FRAGMENT});
  FX.ring = Array.from({length: RING}, () => {
    const pair = {points: new THREE.Points(new THREE.BufferGeometry(), points),
      lines: new THREE.LineSegments(new THREE.BufferGeometry(), lines), cap: 0, capL: 0};
    for (const object of [pair.points, pair.lines]) {
      object.frustumCulled = false;
      object.renderOrder = 10;
      object.visible = false;
      scene.add(object);
    }
    return pair;
  });
  FX.points = null;
  for (FX.at = 0; FX.at < RING; FX.at++) {
    Object.assign(FX, {...FX.ring[FX.at], pos: null, tint: null, look: null, lpos: null, lcol: null});
    fxGrow(true); fxGrow(false);
    Object.assign(FX.ring[FX.at], {cap: FX.cap, capL: FX.capL, pos: FX.pos, tint: FX.tint, look: FX.look,
      lpos: FX.lpos, lcol: FX.lcol});
  }
  FX.at = RING - 1;
}
/* The next pair of the ring, the one to fill this frame, its buffers as the last frame it was filled grew them. */
function fxNext() {
  Object.assign(FX.ring[FX.at], {cap: FX.cap, capL: FX.capL, pos: FX.pos, tint: FX.tint, look: FX.look,
    lpos: FX.lpos, lcol: FX.lcol});
  FX.at = (FX.at + 1) % RING;
  const pair = FX.ring[FX.at];
  Object.assign(FX, {points: pair.points, lines: pair.lines, cap: pair.cap, capL: pair.capL, pos: pair.pos,
    tint: pair.tint, look: pair.look, lpos: pair.lpos, lcol: pair.lcol});
}
/* A buffer `size` long holding what the old one held. */
function grown(old, size) {
  const made = new Float32Array(size);
  if (old) made.set(old.subarray(0, Math.min(old.length, size)));
  return made;
}
/* The points' buffers, or the lines', twice as large, keeping what they hold. */
function fxGrow(points) {
  const geometry = (points ? FX.points : FX.lines).geometry;
  const put = (name, array, width) => geometry.setAttribute(name,
    new THREE.BufferAttribute(array, width).setUsage(THREE.DynamicDrawUsage));
  if (points) {
    FX.cap = Math.max(512, FX.cap * 2);
    put('position', FX.pos = grown(FX.pos, FX.cap * 3), 3);
    put('tint', FX.tint = grown(FX.tint, FX.cap * 4), 4);
    put('look', FX.look = grown(FX.look, FX.cap * 4), 4);
  } else {
    FX.capL = Math.max(1024, FX.capL * 2);
    put('position', FX.lpos = grown(FX.lpos, FX.capL * 3), 3);
    put('shade', FX.lcol = grown(FX.lcol, FX.capL * 3), 3);
  }
}
// shape: 0 a dot, 1 a card, 2 a ring; `size` across in map units, held between `least` and `most` pixels
export function fxDot(at, size, color, alpha, shape, least, most) {
  if (FX.n === FX.cap) fxGrow(true);
  const i = FX.n++;
  FX.pos[i * 3] = at.x; FX.pos[i * 3 + 1] = at.y; FX.pos[i * 3 + 2] = at.z;
  FX.tint[i * 4] = color.r; FX.tint[i * 4 + 1] = color.g; FX.tint[i * 4 + 2] = color.b;
  FX.tint[i * 4 + 3] = alpha * FX.fade;
  FX.look[i * 4] = size; FX.look[i * 4 + 1] = shape; FX.look[i * 4 + 2] = least; FX.look[i * 4 + 3] = most;
}
// a segment fading from glowA to glowB, its colour toward white as it glows
export function fxLine(a, b, color, glowA, glowB) {
  if (FX.m + 2 > FX.capL) fxGrow(false);
  for (const [at, shown] of [[a, glowA], [b, glowB]]) {
    const glow = shown * FX.fade, i = FX.m++, white = 0.6 * glow;
    FX.lpos[i * 3] = at.x; FX.lpos[i * 3 + 1] = at.y; FX.lpos[i * 3 + 2] = at.z;
    FX.lcol[i * 3] = (color.r + (1 - color.r) * white) * glow;
    FX.lcol[i * 3 + 1] = (color.g + (1 - color.g) * white) * glow;
    FX.lcol[i * 3 + 2] = (color.b + (1 - color.b) * white) * glow;
  }
}
function fxDone() {
  if (!FX.points) return;
  for (const pair of FX.ring) if (pair.points !== FX.points) pair.points.visible = pair.lines.visible = false;
  const renderer = G.renderer(), camera = G.camera();
  const scale = renderer.domElement.height / (2 * Math.tan((camera.fov || 50) * Math.PI / 360));
  FX.scale = FX.points.material.uniforms.scale.value = scale;
  FX.ratio = FX.points.material.uniforms.ratio.value = renderer.getPixelRatio();
  for (const [object, count] of [[FX.points, FX.n], [FX.lines, FX.m]]) {
    object.visible = count > 0;
    object.geometry.setDrawRange(0, count);
    for (const attribute of Object.values(object.geometry.attributes)) attribute.needsUpdate = count > 0;
  }
}
/* The point a share of the way along a way of nodes, each leg an equal share: a join's way is its receiver, its
 * purpose vertex and one element it holds, so the purpose vertex is half way. */
function wayAt(way, share, out = {x: 0, y: 0, z: 0}) {
  const legs = way.length - 1, s = Math.min(1, Math.max(0, share)) * legs;
  const i = Math.min(legs - 1, Math.floor(s)), u = s - i;
  const a = way[i], b = way[i + 1];
  out.x = a.x + (b.x - a.x) * u; out.y = a.y + (b.y - a.y) * u; out.z = a.z + (b.z - a.z) * u;
  return out;
}
const TAIL = Array.from({length: 11}, () => ({x: 0, y: 0, z: 0}));
function fxRequest(way, t, live) {  // tiny, white, glimmering, with a short faint trail that says which way it goes
  const k = live ? FLOW.bright : 1, glimmer = 0.75 + 0.25 * Math.sin(FLOW.clock * 16);
  const head = wayAt(way, t, TAIL[0]), tail = wayAt(way, t - FLOW.trail, TAIL[1]);
  if (t > FLOW.trail) fxLine(tail, head, WHITE, 0, 0.5 * k);
  fxDot(head, 0.6 * k, WHITE, glimmer, 0, 6 * k, 8 * k);
}
/* A reply: one solid line along the join the way the data goes, in the colour of the element it comes from, as thick
 * as a reply's dot, and `size` times the request's least size long on the screen, `replySize`; it leaves as the
 * request arrives, and its end arrives as the reply ends. A join too short for it shows it the join's length. It is
 * drawn as dots close enough to run together, each faint, since the flow's light adds up where dots overlap: about
 * four overlap anywhere along it, which adds up to the light of one dot. */
function fxReply(way, t, back, color, live, size) {
  const k = live ? FLOW.bright : 1, dot = 5.5 * k;
  color = LIT.copy(color).lerp(WHITE, 0.35);  // a little lighter than the element, so it reads over the fibers
  const across = Math.max(1, pixelsAlong(way)), long = Math.min(1, size * 6 * k / across);
  const head = t * (1 + long), from = Math.max(0, head - long), to = Math.min(1, head);
  if (from > to) return;
  const step = dot * 0.25 / across, count = Math.floor((to - from) / step);
  for (let i = 0; i <= count; i++) {
    const s = to - i * step;
    fxDot(wayAt(way, back ? 1 - s : s, TAIL[0]), 0.7 * k, color, 0.3, 0, dot, dot * 1.4);
  }
}
/* How long a way is in pixels on the screen, seen at the depth of its middle. */
function pixelsAlong(way) {
  let long = 0;
  for (let i = 1; i < way.length; i++) {
    long += Math.hypot(way[i].x - way[i - 1].x, way[i].y - way[i - 1].y, way[i].z - way[i - 1].z);
  }
  const middle = wayAt(way, 0.5, TAIL[1]);
  const far = Math.max(1e-3, G.camera().position.distanceTo(AT.set(middle.x, middle.y, middle.z)));
  return long * (FX.scale || 800) / (FX.ratio || 1) / far;
}
function fxBurst(node, u, color, live) {  // a ring that opens on a node as something lands on it, and a brief flash
  const k = live ? FLOW.bright : 1, ball = node.t ? ballOf(node) : 3;
  const ring = Math.pow(1 - u, 1.5) * (live ? 1 : 0.85);
  fxDot(node, ball * 2.4 * (1 + 0.9 * u) * k, color, ring, 2, 20 * (1 + u) * k, 260);
  fxDot(node, ball * 1.4, color, Math.pow(1 - u, 3) * 0.45 * k, 0, 8 * k, 160);
  if (live && u > 0.3) {
    fxDot(node, ball * 2.4 * (1 + 1.4 * (u - 0.3)), color, Math.pow(1 - u, 2) * 0.6, 2, 12 * (1 + 2 * (u - 0.3)), 300);
  }
}
function fxRecord(way, since, color, live) {  // a card on its way, then the ring where it lands
  const k = live ? FLOW.bright : 1;
  if (since < FLOW.send) {
    const t = since / FLOW.send, eased = t * t * (3 - 2 * t);
    return fxDot(wayAt(way, eased, TAIL[0]), 2.4 * k, color, 1, 1, 12 * k, 16 * k);
  }
  const u = (since - FLOW.send) / FLOW.burst;
  if (u < 1) fxBurst(way[way.length - 1], u, color, live);
}
/* What agents really did, as it came from the event stream, `flowLive`: each trip drawn until it is over. */
function live3d(data, colors) {
  FLOW.live = FLOW.live.filter(trip => FLOW.clock - trip.at < trip.long);
  if (!FLOW.live.length) return;
  const nodes = new Map(data.nodes.map(node => [node.id, node]));
  for (const trip of FLOW.live) {
    const since = FLOW.clock - trip.at, from = nodes.get(trip.from);
    for (const id of trip.to) {
      const to = nodes.get(id);
      if (to && to.x !== undefined) liveTrip(trip, from, to, since, colors);
    }
  }
}
/* One trip of an agent's to one node: a record dropped onto it from just above, or a request on its way, then for a
 * start the ring where the session lands, for a touch the reply back and the record an edit leaves. */
function liveTrip(trip, from, to, since, colors) {
  if (trip.kind === 'record') {
    return fxRecord([{x: to.x, y: to.y + ballOf(to) * 4, z: to.z}, to], since, colors.record, true);
  }
  const way = from && from.x !== undefined && from !== to ? [from, to] : null;
  const going = trip.kind === 'start' ? 2 * FLOW.ask : FLOW.ask;
  if (since < going) { if (way) fxRequest(way, since / going, true); return; }
  const after = since - going;
  if (trip.kind === 'start') { if (after < FLOW.burst) fxBurst(to, after / FLOW.burst, colors.signal, true); return; }
  if (way && after < FLOW.reply) fxReply(way, after / FLOW.reply, true, tintOf(colorOf(to)), true, trip.size);
  if (trip.edit) fxRecord(way || [to, to], after, colors.record, true);
  else if (!way && after < FLOW.burst) fxBurst(to, after / FLOW.burst, colors.signal, true);
}
const phases = new Map();
export function phaseOf(join) {
  if (!phases.has(join)) {
    let hash = 0x811c9dc5;  // FNV-1a over the join's id, so a join keeps its phase on every load
    for (const char of String(join)) { hash ^= char.codePointAt(0); hash = Math.imul(hash, 0x01000193) >>> 0; }
    phases.set(join, hash / 0x100000000);
  }
  return phases.get(join);
}
export function flow3d(now, data) {
  // the clock moves by the frame's own time, as the 2D map's does: a time read partway through the frame differs from
  // frame to frame by the work done before it, and the dots would jump by that much
  flowTick(FRAMES.last || now);
  if (FLOW.held === null) { fxMake(); fxNext(); }
  FX.n = FX.m = 0;
  const {ways, count} = waysOf(data);
  FLOW.count = FLOW.held !== null ? count : 0;
  if (FLOW.held === null && !reduced()) {
    const colors = {record: tintOf(css('--record')), signal: tintOf(css('--signal'))}, net = flowNet();
    // a join's dots ease in as it starts to flow, and out as it stops, by the flow's own clock
    const ease = 1 - Math.exp(-Math.max(0, FLOW.clock - (FLOW.fadedAt ?? FLOW.clock)) * FLOW.ease);
    FLOW.fadedAt = FLOW.clock;
    for (const [id, way] of ways) {
      const join = net.byId.get(id);
      if (join && way.receiver) flowJoin(id, join, way, ease, colors);
    }
    FLOW.liveFade += ((flowModeNow() === 'off' ? 0 : 1) - FLOW.liveFade) * ease;
    FX.fade = FLOW.liveFade;
    live3d(data, colors);
    FX.fade = 1;
    fxMarks(tintOf(css('--muted')));  // the trails the figures leave
    if (EYE.debug) eyeDebug3d();  // each figure's eye anchor and gaze, for a check of `look`
  }
  fxDone();
}
/* The links that carry a join's flow: its edges, from its receiver to each element it holds. */
export const carries = link => !reduced() && link.k === 'encounter' ? 1 : 0;
/* Each join drawn, by its links that carry the flow and are shown: its receiver, its purpose vertex and the elements
 * drawn that it holds; and how many such links there are. While the flow is held, `dots3d`, the library's own dots,
 * made for that check alone, are shown held at that share of the way instead, and no way is gathered. */
function waysOf(data) {
  let count = 0;
  const ways = new Map(), visible = G.linkVisibility();
  const shown = typeof visible === 'function' ? visible : () => visible !== false;
  for (const link of data.links) {
    const from = link.source, to = link.target;
    if (from?.x === undefined || to?.x === undefined) continue;
    if (FLOW.held !== null) {
      const dots = link.__photonsObj?.children;
      if (dots?.length && link.__photonsObj.parent) { count++; holdDots(dots, from, to); }
      continue;
    }
    if (!carries(link) || !shown(link)) continue;
    count++;
    let way = ways.get(link.join);
    if (!way) ways.set(link.join, way = {receiver: from, providers: []});
    way.providers.push(to);
  }
  return {ways, count};
}
function holdDots(dots, from, to) {
  const dx = to.x - from.x, dy = to.y - from.y, dz = to.z - from.z;
  for (const dot of dots) {
    Object.assign(dot, {visible: true, __progressRatio: FLOW.held});
    dot.position.set(from.x + dx * FLOW.held, from.y + dy * FLOW.held, from.z + dz * FLOW.held);
    dot.scale.setScalar(1);
  }
}
/* One join's flow this frame, eased in or out as the mode shows it or not, `flowShown`: its records, or its request
 * and then its reply, one line each way for a join that goes both ways. */
function flowJoin(id, join, way, ease, colors) {
  const fade = (FLOW.fades.get(id) ?? 0) + ((flowShown(join) ? 1 : 0) - (FLOW.fades.get(id) ?? 0)) * ease;
  if (fade < 0.01) { FLOW.fades.delete(id); return; }
  FLOW.fades.set(id, fade);
  FX.fade = fade;
  FLOW.count++;
  const {asks, since, size, reply} = flowAt(join);
  for (const to of way.providers) {
    const path = [way.receiver, to];
    if (!asks) fxRecord(path, since, colors.record, false);
    else if (since < FLOW.ask) fxRequest(path, since / FLOW.ask, false);
    else if (since < FLOW.ask + reply) for (const back of join.ifd === 'both' ? [true, false] : [true]) {
      fxReply(path, (since - FLOW.ask) / reply, back, tintOf(colorOf(back ? to : way.receiver)), false, size);
    }
  }
}
