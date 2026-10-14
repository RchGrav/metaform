/* A comic speech bubble drawn on a canvas: a white body with rounded corners, sheared a little so its top rises to
 * the right, a thick dark outline, a soft shadow below and right, and a tail from its lower left. The words are wrapped
 * and sized to fit: a short line is drawn large, a long one smaller over more lines, down to `minFont`; what still
 * does not fit ends in an ellipsis. The canvas can be shown as it is, or used as the texture of a sprite over a figure;
 * `tip` is the point of the tail, in CSS pixels from the canvas's top left, where the bubble meets who speaks. */
const BUBBLE = {
  maxWidth: 300,  // the widest the words run, CSS pixels
  maxLines: 4,
  maxFont: 22, minFont: 12,
  lineGap: 1.22,  // line height, as a multiple of the font size
  padX: 16, padY: 11,
  minWidth: 64,
  tilt: -3.5,  // degrees the body is sheared: negative rises to the right
  outline: 4, ink: '#111', paper: '#fff', shadow: 'rgba(0,0,0,0.18)', drop: [6, 6],
  tail: {at: 0.14, base: 30, length: 30, lean: -14},  // where on the bottom edge, its width, how far down and left
};

export function speechBubble(text, options = {}) {
  const o = {...BUBBLE, ...options, tail: {...BUBBLE.tail, ...options.tail}};
  const family = o.font || getComputedStyle(document.documentElement).getPropertyValue('--sans').trim() || 'sans-serif';
  const measure = document.createElement('canvas').getContext('2d');
  const {lines, size} = fitWords(measure, String(text ?? '').replace(/\s+/g, ' ').trim(), family, o);
  const lineHeight = size * o.lineGap;
  const wide = Math.max(...lines.map(line => measure.measureText(line).width), 0);
  const w = Math.max(o.minWidth, Math.ceil(wide) + 2 * o.padX);
  const h = Math.ceil(lines.length * lineHeight) + 2 * o.padY;
  const shear = Math.tan(o.tilt * Math.PI / 180);
  const r = Math.min(18, h / 3);
  const base = Math.max(10, Math.min(o.tail.base, w * 0.3));
  const from = Math.max(r + 2, w * o.tail.at);  // clear of the rounded corner
  const tip = [from + o.tail.lean, h + o.tail.length];
  // the canvas holds the sheared body, its tail, the outline and the shadow
  const corners = [[0, 0], [w, 0], [0, h], [w, h], tip].map(([x, y]) => [x, y + x * shear]);
  const edge = o.outline / 2 + 1;
  const left = Math.min(...corners.map(([x]) => x)) - edge, top = Math.min(...corners.map(([, y]) => y)) - edge;
  const width = Math.ceil(Math.max(...corners.map(([x]) => x)) + edge + o.drop[0] - left);
  const height = Math.ceil(Math.max(...corners.map(([, y]) => y)) + edge + o.drop[1] - top);
  const dpr = o.dpr || window.devicePixelRatio || 1;
  const canvas = document.createElement('canvas');
  canvas.width = Math.ceil(width * dpr); canvas.height = Math.ceil(height * dpr);
  canvas.style.width = `${width}px`; canvas.style.height = `${height}px`;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.translate(-left, -top);
  ctx.transform(1, shear, 0, 1, 0, 0);
  const outline = bubblePath(w, h, r, from, base, tip);
  ctx.save();  // the shadow: the same shape, offset, under the body
  ctx.translate(...o.drop);
  ctx.fillStyle = o.shadow;
  ctx.fill(outline);
  ctx.restore();
  ctx.fillStyle = o.paper;
  ctx.fill(outline);
  ctx.lineJoin = 'round';
  ctx.lineWidth = o.outline;
  ctx.strokeStyle = o.ink;
  ctx.stroke(outline);
  ctx.fillStyle = o.ink;
  ctx.font = fontOf(size, family);
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  lines.forEach((line, n) => ctx.fillText(line, w / 2, o.padY + (n + 0.5) * lineHeight));
  return {canvas, width, height, tip: [tip[0] - left, tip[1] + tip[0] * shear - top], lines, size};
}
const fontOf = (size, family) => `600 ${size}px ${family}`;
/* The largest size whose wrapped words take at most `maxLines`; at the smallest, the last line is cut with "…". */
function fitWords(ctx, text, family, o) {
  const room = o.maxWidth - 2 * o.padX;
  for (let size = o.maxFont; size >= o.minFont; size--) {
    ctx.font = fontOf(size, family);
    const lines = wrapWords(ctx, text, room);
    if (lines.length <= o.maxLines || size === o.minFont) {
      return {size, lines: lines.length <= o.maxLines ? lines : cutLast(ctx, lines.slice(0, o.maxLines), room)};
    }
  }
  return {size: o.minFont, lines: []};
}
function wrapWords(ctx, text, room) {
  const lines = [];
  let line = '';
  for (const word of text ? text.split(' ') : []) {
    const next = line ? `${line} ${word}` : word;
    if (ctx.measureText(next).width <= room) { line = next; continue; }
    if (line) lines.push(line);
    line = word;
    while (ctx.measureText(line).width > room && line.length > 1) {  // a word wider than the room is broken
      let cut = line.length - 1;
      while (cut > 1 && ctx.measureText(line.slice(0, cut)).width > room) cut--;
      lines.push(line.slice(0, cut));
      line = line.slice(cut);
    }
  }
  if (line) lines.push(line);
  return lines;
}
function cutLast(ctx, lines, room) {
  let last = `${lines.at(-1)}…`;
  while (last.length > 1 && ctx.measureText(last).width > room) {  // a word at a time, a letter at a time if one
    const words = last.slice(0, -1).trimEnd();
    const space = words.lastIndexOf(' ');
    last = `${space > 0 ? words.slice(0, space) : words.slice(0, -1)}…`;
  }
  return [...lines.slice(0, -1), last];
}
/* The body's rounded outline, going clockwise, with the tail drawn out of its bottom edge between `from` and
 * `from + base`, to `tip`. */
function bubblePath(w, h, r, from, base, tip) {
  const path = new Path2D();
  path.moveTo(r, 0);
  path.arcTo(w, 0, w, h, r);
  path.arcTo(w, h, 0, h, r);
  path.lineTo(from + base, h);
  path.lineTo(...tip);
  path.lineTo(from, h);
  path.arcTo(0, h, 0, 0, r);
  path.arcTo(0, 0, w, 0, r);
  path.closePath();
  return path;
}
