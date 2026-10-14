/* What each agent at work is saying, in a comic speech bubble beside its figure in the 3D map. The bubble is drawn in
 * SVG: a white body with rounded corners, tilted so its top rises to the right, a thick black outline of one weight
 * whatever its size, a soft shadow below and right, and a pointed tail from its lower left to the figure's head. The
 * words are set large and bold and wrap; the body grows and shrinks around them while the outline, corners and tail
 * keep their size. The drawing becomes the texture of a plane in the scene, not a layer over the map: it faces the
 * camera, is as large on the screen as its distance makes it, and what stands in front of it hides it, so an agent
 * looked at closely shows its words large and the others' small in the distance. It is drawn again only when its
 * words change, never each frame. The words are the newest line the agent said in its thread, `said` on its
 * session from the server, never its tool calls or its thinking. */
import * as THREE from 'three';
import {eyeOf} from '/page/agents3d.js';
import {reduced} from '/page/app/core/dom.js';
import {ROAM} from '/page/app/figures/agents.js';
import {D} from '/page/app/agents/dispatch.js';
import {G, wake3d} from '/page/app/map3d/graph3d.js';

const LOOK = {
  most: 140,  // the most characters shown; a longer line is cut at a word with an ellipsis
  width: 340,  // the widest the words run, SVG pixels
  font: 26, lines: 4, lineGap: 1.18,
  family: "'Comic Neue', 'Comic Sans MS', 'Chalkboard SE', 'Trebuchet MS', sans-serif",
  padX: 22, padY: 16, minWidth: 90,
  tilt: -4,  // degrees; negative rises to the right
  outline: 6, radius: 22, shadow: [7, 8],
  tail: {at: 0.16, base: 34, length: 40, lean: -18},  // along the bottom edge, its width, how far down and left
  scale: 3,  // texture pixels per SVG pixel, so the bubble stays sharp up close
  world: 0.0105,  // world units per SVG pixel, per unit of the figure's size
  pop: 320,  // ms of the pop when new words arrive
};
const BUBBLES = new Map();  // figure id -> {mesh, texture, text, drawn, born, shown}
const HEAD = new THREE.Vector3(), GAZE = new THREE.Vector3(), SHIFT = new THREE.Vector3();
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
  const material = new THREE.MeshBasicMaterial({map: texture, transparent: true, depthWrite: false, toneMapped: false,
    opacity: 0});
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), material);
  mesh.renderOrder = 5;
  mesh.visible = false;
  mesh.raycast = () => {};  // never in the way of a click
  G.scene().add(mesh);
  const bubble = {id, mesh, canvas, texture, text: '', drawn: null, born: 0, shown: 0};
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
  if (!session || session.activity !== 'working' || !session.said?.text) return '';
  return bubbleText(session.said.text);
}
const easeOut = k => 1 + 2.4 * (k - 1) ** 3 + 1.4 * (k - 1) ** 2;  // overshoots a little, then settles
/* Each frame: every working figure's bubble placed over its head, facing the camera, its tail's point at the head. */
export function bubbles3d() {
  if (!G) return;
  const camera = G.camera(), now = performance.now(), live = new Set();
  for (const [id, figure] of ROAM.figures) {
    const text = figure.stage === 'leaving' || figure.done ? '' : saying(figure);
    let bubble = BUBBLES.get(id);
    if (!text && !bubble) continue;
    bubble ||= made(id);
    live.add(id);
    if (text && text !== bubble.text) draw(bubble, text);
    const want = text && bubble.drawn ? 1 : 0;
    bubble.shown += (want - bubble.shown) * (reduced() ? 1 : 0.18);
    const {mesh, drawn} = bubble;
    if (mesh.parent !== G.scene()) G.scene().add(mesh);  // a whole reload of the map makes a new scene
    mesh.visible = bubble.shown > 0.02 && Boolean(drawn) && figure.mesh.visible;
    if (!mesh.visible) continue;
    mesh.material.opacity = Math.min(1, bubble.shown);
    const k = reduced() ? 1 : Math.min(1, (now - bubble.born) / LOOK.pop);
    const grow = 0.55 + 0.45 * easeOut(k);
    const unit = LOOK.world * Math.max(0.5, figure.mesh.scale.x) * grow;
    mesh.scale.set(drawn.width * unit, drawn.height * unit, 1);
    mesh.quaternion.copy(camera.quaternion);
    // the tail's point sits just above the figure's head: the plane's middle is moved from it by the point's offset
    eyeOf(figure.mesh, HEAD, GAZE);
    HEAD.y += 0.35 * figure.mesh.scale.x;
    SHIFT.set((drawn.width / 2 - drawn.tip[0]) * unit, (drawn.tip[1] - drawn.height / 2) * unit, 0)
      .applyQuaternion(camera.quaternion);
    mesh.position.copy(HEAD).add(SHIFT);
    if (k < 1 || bubble.shown < 0.98) wake3d(50);
  }
  for (const [id, bubble] of BUBBLES) {
    if (live.has(id)) continue;
    bubble.mesh.removeFromParent();
    bubble.mesh.geometry.dispose(); bubble.mesh.material.dispose(); bubble.texture.dispose();
    BUBBLES.delete(id);
  }
}
