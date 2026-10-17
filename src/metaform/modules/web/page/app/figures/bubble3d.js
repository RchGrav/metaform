/* What each agent at work is saying, in a comic speech bubble beside its figure in the 3D map. The bubble is drawn in
 * SVG: a white body with rounded corners, tilted so its top rises to the right, a thick black outline of one weight
 * whatever its size, a soft shadow below and right, and a pointed tail from its lower left to the figure's head. The
 * words are set large and bold and wrap; the body grows and shrinks around them while the outline, corners and tail
 * keep their size. The drawing becomes the texture of a plane in the scene, not a layer over the map: it faces the
 * camera, is the same readable size on the screen at any distance, and is drawn over the map so its words can be read; a
 * nearer bubble covers a farther one, and an agent farther than the nearest one talking is drawn dimmer, still solid.
 * Every bubble stays inside the view and apart from the others, `apart`. A new line shows for web_bubble_seconds (5 by
 * default) and goes, fading in and out by the clock, so at any frame rate; the pointer on an agent brings its last line
 * back. In the agent view, V, the agent seen through has no body on the screen, so its words are at the bottom of the
 * view for as long as it says them, `atBottom`. It is drawn again only when its words change, never each frame. The
 * words are the newest line the agent said in its thread, `said` on its session from the server, never its tool calls
 * or its thinking (code.interface.graphical#81, 2026-10-15). */
import * as THREE from 'three';
import {eyeOf} from '/page/agents3d.js';
import {reduced} from '/page/app/core/dom.js';
import {ROAM} from '/page/app/figures/agents.js';
import {D} from '/page/app/agents/dispatch.js';
import {G, STAGE, wake3d} from '/page/app/map3d/graph3d.js';
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
  fade: 84,  // ms, the time constant of the fade in and out: full within about a quarter of a second
  edge: 0.98, gap: 0.012,  // the view's edge a bubble stays inside, and the gap between two, in view units (-1 to 1)
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
const BUBBLES = new Map();  // figure id -> bubble, `made`
/* The body the person sees through in the agent view, V, set by `eyesOf`; null in their own view and the mascot's. */
export const WATCHED = {mesh: null};
const HEAD = new THREE.Vector3(), GAZE = new THREE.Vector3(), SHIFT = new THREE.Vector3(), SIDE = new THREE.Vector3();
const AHEAD = new THREE.Vector3(), SEEN = new THREE.Vector3();
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
  // at: when its fade last stepped; head: how far its agent's head is; far: what `layer` sorts by; seen: the frame it
  // was last on; fixed: at the bottom of the agent view
  const bubble = {id, mesh, canvas, texture, text: '', drawn: null, born: 0, shown: 0, line: '', lineAt: 0,
    at: performance.now(), head: 0, far: 0, seen: 0, fixed: false};
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
/* The boxes on the screen of the bubbles placed this frame, in view units (-1 to 1), one array per edge; grown, never
 * shrunk, when more agents talk than it holds. */
const PLACED = {n: 0, x0: new Float64Array(32), y0: new Float64Array(32), x1: new Float64Array(32),
  y1: new Float64Array(32)};
function keep(box) {
  if (PLACED.n === PLACED.x0.length) {
    for (const edge of ['x0', 'y0', 'x1', 'y1']) {
      const more = new Float64Array(PLACED.n * 2);
      more.set(PLACED[edge]);
      PLACED[edge] = more;
    }
  }
  PLACED.x0[PLACED.n] = box.x0; PLACED.y0[PLACED.n] = box.y0; PLACED.x1[PLACED.n] = box.x1; PLACED.y1[PLACED.n] = box.y1;
  PLACED.n++;
}
/* A bubble's box on the screen: its plane faces the camera, so the box is its plane's, scaled. */
const CORNER = new THREE.Vector3(), UP = new THREE.Vector3(), RIGHT = new THREE.Vector3();
const BOX = {x0: 0, y0: 0, x1: 0, y1: 0};
function boxOf(mesh, camera) {
  CORNER.set(-0.5, -0.5, 0).applyMatrix4(mesh.matrixWorld).project(camera);
  BOX.x0 = CORNER.x; BOX.y0 = CORNER.y;
  CORNER.set(0.5, 0.5, 0).applyMatrix4(mesh.matrixWorld).project(camera);
  BOX.x1 = CORNER.x; BOX.y1 = CORNER.y;
  return BOX;
}
/* How much of the placed boxes the bubble's box covers, moved by dx, dy. */
function covers(dx, dy) {
  const x0 = BOX.x0 + dx, x1 = BOX.x1 + dx, y0 = BOX.y0 + dy, y1 = BOX.y1 + dy;
  let area = 0;
  for (let n = 0; n < PLACED.n; n++) {
    const w = Math.min(x1, PLACED.x1[n]) - Math.max(x0, PLACED.x0[n]);
    const h = Math.min(y1, PLACED.y1[n]) - Math.max(y0, PLACED.y0[n]);
    if (w > 0 && h > 0) area += w * h;
  }
  return area;
}
/* The bubble's move tried next, kept inside the view; the best so far is the one that covers the fewest placed boxes,
 * then the one moved least. */
const MOVE = {dx: 0, dy: 0, cover: Infinity, far: Infinity};
function tryMove(dx, dy) {
  const edge = LOOK.edge;
  dx = Math.min(Math.max(dx, -edge - BOX.x0), edge - BOX.x1);
  dy = Math.min(Math.max(dy, -edge - BOX.y0), edge - BOX.y1);
  const cover = covers(dx, dy), far = dx * dx + dy * dy;
  if (cover < MOVE.cover - 1e-9 || (cover <= MOVE.cover + 1e-9 && far < MOVE.far)) {
    MOVE.dx = dx; MOVE.dy = dy; MOVE.cover = cover; MOVE.far = far;
  }
}
/* A bubble set apart from the bubbles placed before it this frame, and inside the view: where it stands, else just
 * above, below, right or left of one placed already, by the overlap and a gap, whichever covers no other bubble and
 * moves it least; one crossing an edge of the view is pulled back inside it. With no free place, it takes the one that
 * covers the least, and the nearer bubble is drawn over it, `layer`. Then its box is added to the placed ones. */
function apart(mesh, camera) {
  mesh.updateMatrixWorld();
  boxOf(mesh, camera);
  MOVE.cover = MOVE.far = Infinity;
  tryMove(0, 0);
  const gap = LOOK.gap;
  for (let n = 0; n < PLACED.n && MOVE.cover > 0; n++) {
    tryMove(0, PLACED.y1[n] - BOX.y0 + gap);
    tryMove(0, PLACED.y0[n] - BOX.y1 - gap);
    tryMove(PLACED.x1[n] - BOX.x0 + gap, 0);
    tryMove(PLACED.x0[n] - BOX.x1 - gap, 0);
  }
  if (MOVE.dx || MOVE.dy) {
    // the move in world units, along the screen's right and up: the box's size on the screen is its plane's size
    RIGHT.set(1, 0, 0).applyQuaternion(camera.quaternion);
    UP.set(0, 1, 0).applyQuaternion(camera.quaternion);
    mesh.position.addScaledVector(RIGHT, MOVE.dx / Math.max(1e-6, BOX.x1 - BOX.x0) * mesh.scale.x)
      .addScaledVector(UP, MOVE.dy / Math.max(1e-6, BOX.y1 - BOX.y0) * mesh.scale.y);
    mesh.updateMatrixWorld();
    BOX.x0 += MOVE.dx; BOX.x1 += MOVE.dx; BOX.y0 += MOVE.dy; BOX.y1 += MOVE.dy;
  }
  keep(BOX);
}
/* The words of the agent seen through in the agent view: at the bottom of the view, in its middle, facing the camera
 * at full brightness, the tail pointing down out of the view at the one speaking. */
function atBottom(bubble, camera, unit, grow) {
  const {mesh, drawn} = bubble, along = camera.near * 50, half = along * Math.tan(camera.fov * Math.PI / 360);
  const size = unit * along * grow;
  mesh.scale.set(drawn.width * size, drawn.height * size, 1);
  camera.getWorldDirection(AHEAD);
  UP.set(0, 1, 0).applyQuaternion(camera.quaternion);
  mesh.position.copy(camera.position).addScaledVector(AHEAD, along)
    .addScaledVector(UP, -LOOK.edge * half + mesh.scale.y / 2);
  bubble.head = 0;
}
/* Every bubble is drawn over the map, never hidden by it, so its words can be read: the farthest first and the nearest
 * last, so a nearer bubble covers a farther one, the agent view's own words over them all. `SHOWN` is nearest first. */
function layer() {
  const count = SHOWN.length;
  for (let n = 0; n < count; n++) {
    SHOWN[n].mesh.renderOrder = SHOWN[n].fixed ? 1000 + count : 1000 + count - 1 - n;
  }
}
/* The bubbles shown this frame, nearest head first, the agent view's own first of all: sorted in place. */
const SHOWN = [];
function nearestFirst() {
  for (let n = 1; n < SHOWN.length; n++) {
    const one = SHOWN[n];
    let at = n - 1;
    while (at >= 0 && SHOWN[at].far > one.far) { SHOWN[at + 1] = SHOWN[at]; at--; }
    SHOWN[at + 1] = one;
  }
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
/* Each frame: every working figure's bubble placed over its head, facing the camera, its tail's point at the head;
 * then, nearest first, each set apart from the others inside the view, and dimmed by how far its agent is. */
const FRAME = {n: 0};
export function bubbles3d() {
  if (!G) return;
  const camera = G.camera(), now = performance.now(), under = figureUnder(), frame = ++FRAME.n;
  // a world unit per screen pixel, at a distance of one: the bubbles are the same size on the screen at any distance
  const perPixel = BUBBLE_SIZES[SIZE.at] * 2 * Math.tan(camera.fov * Math.PI / 360)
    / (STAGE.height || 1);
  const shows = 1000 * (Number(WS.view()?.bubble_seconds) || 5);
  SHOWN.length = 0;
  for (const [id, figure] of ROAM.figures) {
    const said = figure.stage === 'leaving' || figure.done ? null : saying(figure), text = said?.text || '';
    let bubble = BUBBLES.get(id);
    if (!text && !bubble) continue;
    bubble ||= made(id);
    bubble.seen = frame;
    // a new line starts its time; the same line growing as it streams is drawn again but keeps its time, so no
    // bubble stays up past web_bubble_seconds however long its agent talks
    if (said && said.line !== bubble.line) { bubble.line = said.line; bubble.lineAt = now; }
    if (text && text !== bubble.text) draw(bubble, text);
    // a new line shows for web_bubble_seconds and goes; the pointer on the agent brings its last line back; the agent
    // seen through in the agent view shows what it says for as long as it says it
    const watched = figure.mesh === WATCHED.mesh;
    const fresh = text && (watched || now - bubble.lineAt < shows), hovered = under === id && bubble.text;
    const want = bubble.drawn && (fresh || hovered) ? 1 : 0;
    // by the clock, not by the frame, so it comes and goes in the same time at any frame rate
    bubble.shown += (want - bubble.shown) * (reduced() ? 1 : 1 - Math.exp(-(now - bubble.at) / LOOK.fade));
    bubble.at = now;
    const {mesh, drawn} = bubble;
    if (mesh.parent !== G.scene()) G.scene().add(mesh);  // a whole reload of the map makes a new scene
    mesh.visible = bubble.shown > 0.02 && Boolean(drawn) && (watched || figure.mesh.visible);
    if (!mesh.visible) continue;
    const k = reduced() ? 1 : Math.min(1, (now - bubble.lineAt) / LOOK.pop);
    const grow = 0.55 + 0.45 * easeOut(k);
    mesh.quaternion.copy(camera.quaternion);
    bubble.fixed = watched;
    if (watched) atBottom(bubble, camera, perPixel, grow);
    else {
      // the tail's point sits just above the figure's head: the plane's middle is moved from it by the point's offset
      eyeOf(figure.mesh, HEAD, GAZE);
      HEAD.y += LOOK.lift * figure.mesh.scale.x;
      HEAD.addScaledVector(SIDE.set(1, 0, 0).applyQuaternion(camera.quaternion), LOOK.aside * figure.mesh.scale.x);
      // an agent behind the camera says nothing on the screen; one beside the view has its words at the view's edge
      if (SEEN.copy(HEAD).applyMatrix4(camera.matrixWorldInverse).z >= -camera.near) { mesh.visible = false; continue; }
      bubble.head = HEAD.distanceTo(camera.position);
      const unit = perPixel * bubble.head * grow;
      mesh.scale.set(drawn.width * unit, drawn.height * unit, 1);
      SHIFT.set((drawn.width / 2 - drawn.tip[0]) * unit, (drawn.tip[1] - drawn.height / 2) * unit, 0)
        .applyQuaternion(camera.quaternion);
      mesh.position.copy(HEAD).add(SHIFT);
    }
    bubble.far = watched ? -1 : bubble.head;
    mesh.material.opacity = Math.min(1, bubble.shown);
    SHOWN.push(bubble);
    if (k < 1 || Math.abs(bubble.shown - want) > 0.02) wake3d(50);
  }
  // nearest first, so the nearest keeps its place and the farther ones move; the agent view's own words first of all
  nearestFirst();
  PLACED.n = 0;
  let nearest = Infinity;
  for (let n = 0; n < SHOWN.length; n++) if (!SHOWN[n].fixed) { nearest = SHOWN[n].head; break; }
  for (let n = 0; n < SHOWN.length; n++) {
    const bubble = SHOWN[n];
    if (bubble.fixed) { bubble.mesh.updateMatrixWorld(); keep(boxOf(bubble.mesh, camera)); }
    else apart(bubble.mesh, camera);
    // the farther its agent is than the nearest one talking, the dimmer it is drawn, still solid, fading toward a
    // third; measured from the head, so a bubble moved apart is as bright as its agent is near
    bubble.mesh.material.color.setScalar(bubble.fixed ? 1
      : Math.max(LOOK.dimmest, Math.min(1, (nearest / Math.max(1e-6, bubble.head)) ** 1.5)));
  }
  layer();
  for (const [id, bubble] of BUBBLES) {
    if (bubble.seen === frame) continue;
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
