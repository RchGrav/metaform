/* What each agent at work is saying, in a comic speech bubble beside its figure in the 3D map. The bubble is drawn in
 * SVG: a white body with rounded corners, tilted so its top rises to the right, a thick black outline of one weight
 * whatever its size, a soft shadow below and right, and a pointed tail from its lower left to the figure's head. The
 * words are set large and bold and wrap; the body grows and shrinks around them while the outline, corners and tail
 * keep their size. The drawing becomes the texture of a plane in the scene, not a layer over the map: it faces the
 * camera, is the same readable size on the screen at any distance, and is drawn over the map so its words can be read; a
 * nearer bubble covers a farther one, and farther ones are drawn dimmer, still solid. A new line shows for
 * web_bubble_seconds (5 by default) and goes; the pointer on an agent brings its last line back. So an agent
 * looked at closely shows its words large and the others' small in the distance. It is drawn again only when its
 * words change, never each frame. The words are the newest line the agent said in its thread, `said` on its
 * session from the server, never its tool calls or its thinking. */
import * as THREE from 'three';
import {eyeOf} from '/page/agents3d.js';
import {reduced} from '/page/app/core/dom.js';
import {ROAM} from '/page/app/figures/agents.js';
import {D} from '/page/app/agents/dispatch.js';
import {G, wake3d} from '/page/app/map3d/graph3d.js';
import {WS} from '/page/app/workspace/workspace.js';

const LOOK = {
  most: 140,  // the most characters shown; a longer line is cut at a word with an ellipsis
  width: 340,  // the widest the words run, SVG pixels
  font: 26, lines: 3, lineGap: 1.18,
  family: "'Comic Neue', 'Comic Sans MS', 'Chalkboard SE', 'Trebuchet MS', sans-serif",
  padX: 22, padY: 16, minWidth: 90,
  tilt: -4,  // degrees; negative rises to the right
  outline: 6, radius: 22, shadow: [7, 8],
  tail: {at: 0.16, base: 34, length: 40, lean: -18},  // along the bottom edge, its width, how far down and left
  scale: 3,  // texture pixels per SVG pixel, so the bubble stays sharp up close
  dimmest: 0.33,  // the brightness of the farthest bubbles
  lift: 0.6, aside: 0.4,  // where the tail's point sits: up and to the right of the head, in figure sizes
  pop: 320,  // ms of the pop when new words arrive
};
/* The bubbles' size on the screen, CSS pixels per SVG pixel, the same for every bubble at any distance: key 5 steps
 * through these, the first the smallest allowed; the choice is kept in this browser. */
export const BUBBLE_SIZES = [0.75, 0.9, 1.05, 1.25, 1.5];
const SIZE_KEY = 'metaform.bubbleSize';
const SIZE = {at: (() => {
  try { return Math.min(BUBBLE_SIZES.length - 1, Math.max(0, Number(localStorage.getItem(SIZE_KEY)) || 0)); }
  catch { return 0; }
})()};
export function stepBubbleSize() {
  SIZE.at = (SIZE.at + 1) % BUBBLE_SIZES.length;
  try { localStorage.setItem(SIZE_KEY, String(SIZE.at)); } catch { /* storage can be blocked; the page keeps it */ }
  wake3d();
  return SIZE.at;
}
const BUBBLES = new Map();  // figure id -> {mesh, texture, text, drawn, born, shown}
const HEAD = new THREE.Vector3(), GAZE = new THREE.Vector3(), SHIFT = new THREE.Vector3(), SIDE = new THREE.Vector3();
const MEASURE = document.createElement('canvas').getContext('2d');

/* The line a bubble shows: the last non-empty line of what the agent said, cut at a word. */
export function bubbleText(text) {
  const line = String(text || '').split(/\r?\n/).map(part => part.trim()).filter(Boolean).at(-1) || '';
  const flat = line.replace(/[*_`#>]+/g, '').replace(/\s+/g, ' ').trim();
  if (flat.length <= LOOK.most) return flat;
  const start = flat.slice(0, LOOK.most - 1), word = start.lastIndexOf(' ');
  return `${(word > 40 ? start.slice(0, word) : start).trimEnd()}…`;
}
/* The words wrapped to the bubble's width, the font shrinking a step at a time until they fit in `lines`. */
function wrapped(text) {
  for (let size = LOOK.font; size >= 16; size -= 2) {
    MEASURE.font = `800 ${size}px ${LOOK.family}`;
    const lines = [];
    let line = '';
    for (const word of text.split(' ')) {
      const next = line ? `${line} ${word}` : word;
      if (!line || MEASURE.measureText(next).width <= LOOK.width) line = next;
      else { lines.push(line); line = word; }
    }
    if (line) lines.push(line);
    if (lines.length <= LOOK.lines || size <= 16) {
      return {size, lines: lines.slice(0, LOOK.lines),
        wide: Math.max(...lines.slice(0, LOOK.lines).map(one => MEASURE.measureText(one).width))};
    }
  }
  return {size: 16, lines: [text], wide: LOOK.width};
}
const escaped = text => text.replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'})[c]);
/* The bubble as SVG: its size, and where the tail's point is, in its own pixels. */
export function bubbleSVG(text) {
  const {size, lines, wide} = wrapped(text);
  const lineHeight = size * LOOK.lineGap;
  const w = Math.max(LOOK.minWidth, Math.ceil(wide) + 2 * LOOK.padX);
  const h = Math.ceil(lines.length * lineHeight + 2 * LOOK.padY);
  const r = Math.min(LOOK.radius, h / 2.4), t = LOOK.tail;
  const from = Math.max(r + 4, w * t.at), base = Math.min(t.base, w * 0.3);
  const tip = [from + t.lean, h + t.length];
  const body = `M${r},0 H${w - r} Q${w},0 ${w},${r} V${h - r} Q${w},${h} ${w - r},${h} H${from + base} `
    + `L${tip[0]},${tip[1]} L${from},${h} H${r} Q0,${h} 0,${h - r} V${r} Q0,0 ${r},0 Z`;
  // the whole bubble turns about its middle; the canvas is sized to hold it turned, with its outline and shadow
  const turn = LOOK.tilt * Math.PI / 180, cos = Math.cos(turn), sin = Math.sin(turn), cx = w / 2, cy = h / 2;
  const turned = ([x, y]) => [cx + (x - cx) * cos - (y - cy) * sin, cy + (x - cx) * sin + (y - cy) * cos];
  const corners = [[0, 0], [w, 0], [0, h], [w, h], tip].map(turned);
  const edge = LOOK.outline;
  const left = Math.min(...corners.map(([x]) => x)) - edge, top = Math.min(...corners.map(([, y]) => y)) - edge;
  const width = Math.ceil(Math.max(...corners.map(([x]) => x)) + edge + LOOK.shadow[0] - left);
  const height = Math.ceil(Math.max(...corners.map(([, y]) => y)) + edge + LOOK.shadow[1] - top);
  const words = lines.map((line, n) => `<text x="${cx}" y="${LOOK.padY + (n + 0.5) * lineHeight}">${escaped(line)}</text>`)
    .join('');
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width * LOOK.scale}" height="${height * LOOK.scale}" `
    + `viewBox="${left} ${top} ${width} ${height}">`
    + `<g transform="rotate(${LOOK.tilt} ${cx} ${cy})">`
    + `<path d="${body}" transform="translate(${LOOK.shadow[0]} ${LOOK.shadow[1]})" fill="rgba(20,22,30,0.28)"/>`
    + `<path d="${body}" fill="#fff" stroke="#111" stroke-width="${LOOK.outline}" stroke-linejoin="round"/>`
    + `<g font-family="${LOOK.family.replace(/"/g, "'")}" font-size="${size}" font-weight="800" fill="#111" `
    + `text-anchor="middle" dominant-baseline="central" letter-spacing="0.3">${words}</g></g></svg>`;
  const [tx, ty] = turned(tip);
  return {svg, width, height, tip: [tx - left, ty - top]};
}
/* One bubble's plane: a texture the SVG is drawn into, shown in the scene, facing the camera. */
function made(id) {
  const canvas = document.createElement('canvas');
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = G.renderer().capabilities.getMaxAnisotropy();
  // drawn over the map, `layer`, so its words can always be read
  const material = new THREE.MeshBasicMaterial({map: texture, transparent: true, depthTest: false, depthWrite: false,
    alphaTest: 0.05, toneMapped: false,
    fog: false, opacity: 0});
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), material);
  mesh.renderOrder = 1000;
  mesh.visible = false;
  mesh.raycast = () => {};  // never in the way of a click
  G.scene().add(mesh);
  const bubble = {id, mesh, canvas, texture, text: '', drawn: null, born: 0, shown: 0, line: '', lineAt: 0};
  BUBBLES.set(id, bubble);
  return bubble;
}
/* Draw new words into the bubble's texture: the SVG is made an image, and the image is painted once. */
function draw(bubble, text) {
  bubble.text = text;
  const {svg, width, height, tip} = bubbleSVG(text);
  const image = new Image();
  image.onload = () => {
    if (bubble.text !== text) return;  // newer words arrived while this one loaded
    const {canvas} = bubble;
    canvas.width = Math.ceil(width * LOOK.scale); canvas.height = Math.ceil(height * LOOK.scale);
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
    bubble.texture.dispose();  // a new size needs a new GPU texture
    bubble.texture.needsUpdate = true;
    bubble.drawn = {width, height, tip};
    bubble.born = performance.now();
    wake3d(LOOK.pop + 100);
  };
  image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}
/* The newest line of the running session of each figure, from the sessions the page reads. */
function saying(figure) {
  const session = figure.child ? null
    : D.sessions.filter(one => one.work_id === figure.id && one.state === 'running').at(-1);
  if (!session || session.activity !== 'working' || !session.said?.text) return null;
  return {text: bubbleText(session.said.text), line: `${session.session_id}:${session.said.seq}`};
}
/* A bubble moved up, along the screen's up, until its box on the screen overlaps none of the bubbles placed before it
 * this frame; then its box is added to them. Bubbles of agents side by side stack instead of covering each other. */
const CORNER = new THREE.Vector3(), UP = new THREE.Vector3();
function boxOf(mesh, camera) {
  const box = {x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity};
  for (const [x, y] of [[-0.5, -0.5], [0.5, -0.5], [-0.5, 0.5], [0.5, 0.5]]) {
    CORNER.set(x, y, 0).applyMatrix4(mesh.matrixWorld).project(camera);
    box.x0 = Math.min(box.x0, CORNER.x); box.x1 = Math.max(box.x1, CORNER.x);
    box.y0 = Math.min(box.y0, CORNER.y); box.y1 = Math.max(box.y1, CORNER.y);
  }
  return box;
}
function apart(mesh, camera, placed) {
  UP.set(0, 1, 0).applyQuaternion(camera.quaternion);
  for (let tries = 0; tries < 8; tries++) {
    mesh.updateMatrixWorld();
    const box = boxOf(mesh, camera);
    const under = placed.find(one => box.x0 < one.x1 && box.x1 > one.x0 && box.y0 < one.y1 && box.y1 > one.y0);
    if (!under) { placed.push(box); return; }
    // up by the overlap and a small gap, in world units: the box's height on screen is its plane's height
    const rise = (under.y1 - box.y0 + 0.01) / Math.max(1e-6, box.y1 - box.y0) * mesh.scale.y;
    mesh.position.addScaledVector(UP, rise);
  }
  mesh.updateMatrixWorld();
  placed.push(boxOf(mesh, camera));
}
/* Every bubble is drawn over the map, never hidden by it, so its words can be read: the farthest first and the nearest
 * last, so a nearer bubble covers a farther one, each dimmer the farther back it is. */
function layer() {
  [...BUBBLES.values()].filter(one => one.mesh.visible).sort((a, b) => b.far - a.far)
    .forEach((one, n) => { one.mesh.renderOrder = 1000 + n; });
}
/* The agent the pointer is over, read once a frame from the 3D map's own pointer, `figureUnder`: its last bubble shows
 * for as long as the pointer stays on it. */
const HOVER = {id: null, x: 0, y: 0, moved: false};
const RAY = new THREE.Raycaster(), AT = new THREE.Vector2(), BALL = new THREE.Sphere(), MIDDLE = new THREE.Vector3();
addEventListener('pointermove', event => {
  HOVER.x = event.clientX; HOVER.y = event.clientY; HOVER.moved = true;
}, {passive: true});
function figureUnder() {
  if (!HOVER.moved) return HOVER.id;
  HOVER.moved = false;
  const area = G.renderer().domElement.getBoundingClientRect();
  if (!area.width || HOVER.x < area.left || HOVER.x > area.right || HOVER.y < area.top || HOVER.y > area.bottom) {
    return (HOVER.id = null);
  }
  AT.set((HOVER.x - area.left) / area.width * 2 - 1, -(HOVER.y - area.top) / area.height * 2 + 1);
  RAY.setFromCamera(AT, G.camera());
  let best = null, nearest = Infinity;
  for (const [id, figure] of ROAM.figures) {
    const size = Math.max(0.5, figure.mesh.scale.x), middle = figure.mesh.getWorldPosition(MIDDLE);
    BALL.set(middle, size);
    if (!RAY.ray.intersectsSphere(BALL)) continue;
    const off = RAY.ray.distanceToPoint(middle) / size;
    if (off < nearest) { nearest = off; best = id; }
  }
  return (HOVER.id = best);
}
const easeOut = k => 1 + 2.4 * (k - 1) ** 3 + 1.4 * (k - 1) ** 2;  // overshoots a little, then settles
/* Each frame: every working figure's bubble placed over its head, facing the camera, its tail's point at the head. */
export function bubbles3d() {
  if (!G) return;
  const camera = G.camera(), now = performance.now(), live = new Set(), placed = [], under = figureUnder();
  for (const [id, figure] of ROAM.figures) {
    const said = figure.stage === 'leaving' || figure.done ? null : saying(figure), text = said?.text || '';
    let bubble = BUBBLES.get(id);
    if (!text && !bubble) continue;
    bubble ||= made(id);
    live.add(id);
    // a new line starts its time; the same line growing as it streams is drawn again but keeps its time, so no
    // bubble stays up past web_bubble_seconds however long its agent talks
    if (said && said.line !== bubble.line) { bubble.line = said.line; bubble.lineAt = now; }
    if (text && text !== bubble.text) draw(bubble, text);
    // a new line shows for web_bubble_seconds and goes; the pointer on the agent brings its last line back
    const shows = 1000 * (Number(WS.view()?.bubble_seconds) || 5);
    const fresh = text && now - bubble.lineAt < shows, hovered = under === id && bubble.text;
    const want = bubble.drawn && (fresh || hovered) ? 1 : 0;
    bubble.shown += (want - bubble.shown) * (reduced() ? 1 : 0.18);
    const {mesh, drawn} = bubble;
    if (mesh.parent !== G.scene()) G.scene().add(mesh);  // a whole reload of the map makes a new scene
    mesh.visible = bubble.shown > 0.02 && Boolean(drawn) && figure.mesh.visible;
    if (!mesh.visible) continue;
    mesh.material.opacity = Math.min(1, bubble.shown);
    const k = reduced() ? 1 : Math.min(1, (now - bubble.lineAt) / LOOK.pop);
    const grow = 0.55 + 0.45 * easeOut(k);
    mesh.quaternion.copy(camera.quaternion);
    // the tail's point sits just above the figure's head: the plane's middle is moved from it by the point's offset
    eyeOf(figure.mesh, HEAD, GAZE);
    HEAD.y += LOOK.lift * figure.mesh.scale.x;
    HEAD.addScaledVector(SIDE.set(1, 0, 0).applyQuaternion(camera.quaternion), LOOK.aside * figure.mesh.scale.x);
    // the same size on the screen at any distance: a world unit per screen pixel at the head's distance
    const view = G.renderer().domElement.clientHeight || 1;
    const pixel = 2 * HEAD.distanceTo(camera.position) * Math.tan(camera.fov * Math.PI / 360) / view;
    const unit = BUBBLE_SIZES[SIZE.at] * pixel * grow;
    mesh.scale.set(drawn.width * unit, drawn.height * unit, 1);
    SHIFT.set((drawn.width / 2 - drawn.tip[0]) * unit, (drawn.tip[1] - drawn.height / 2) * unit, 0)
      .applyQuaternion(camera.quaternion);
    mesh.position.copy(HEAD).add(SHIFT);
    apart(mesh, camera, placed);  // never on top of another bubble
    bubble.far = mesh.position.distanceTo(camera.position);
    // the farther behind where the camera looks, the dimmer it is drawn, still solid: full brightness at that distance
    // or nearer, fading toward a third; it is only see-through while it comes and goes
    const focus = camera.position.distanceTo(G.controls().target) || bubble.far;
    const depth = Math.max(LOOK.dimmest, Math.min(1, (focus / Math.max(1e-6, bubble.far)) ** 1.5));
    mesh.material.color.setScalar(depth);
    mesh.material.opacity = Math.min(1, bubble.shown);
    if (k < 1 || Math.abs(bubble.shown - want) > 0.02) wake3d(50);
  }
  layer();
  for (const [id, bubble] of BUBBLES) {
    if (live.has(id)) continue;
    bubble.mesh.removeFromParent();
    bubble.mesh.geometry.dispose(); bubble.mesh.material.dispose(); bubble.texture.dispose();
    BUBBLES.delete(id);
  }
}
/* The bubble the ray `caster` meets first, for a click on its words: its agent and how far along the ray, or null. */
const HITS = [];
export function bubbleAt(caster) {
  HITS.length = 0;
  for (const bubble of BUBBLES.values()) {
    if (bubble.mesh.visible) THREE.Mesh.prototype.raycast.call(bubble.mesh, caster, HITS);
  }
  if (!HITS.length) return null;
  HITS.sort((a, b) => a.distance - b.distance);
  const id = [...BUBBLES.values()].find(bubble => bubble.mesh === HITS[0].object)?.id;
  return id ? {id, distance: HITS[0].distance} : null;
}
