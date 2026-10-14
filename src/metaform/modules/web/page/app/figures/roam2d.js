/* The agents in 2D, VIEW-035: each figure's flat glyph walking the 2D map as the 3D figures walk, its gait, and the
 * mascot on the 2D map. */
import '/page/app/figures/ask.js';  // the part before runs first, so the parts run in the page's order
import {releaseGlyph, motionOf, strokeOf} from '/page/agents3d.js';
import {$, reduced, SVG} from '/page/app/core/dom.js';
import {S} from '/page/app/core/reads.js';
import {ROAM, pathThrough, liveWork, drawnWorking} from '/page/app/figures/agents.js';
import {CORNERS, wayspeed, goOn, easeBoth, ACTS, actGap, moodOf} from '/page/app/figures/walk.js';
import {FLOURISH} from '/page/app/figures/roam3d.js';
import {MASCOT, mascotGlyph, mascotFigure, mascotDriven} from '/page/app/figures/mascot.js';
import {FRAMES} from '/page/app/map3d/graph3d.js';
import {M} from '/page/app/map2d/build.js';
import {DOCK} from '/page/app/dock/embody.js';
import {glyphFor} from '/page/app/agents/dispatch.js';
import {holderOf} from '/page/app/keys/walk.js';
import {openFigure} from '/page/app/figures/ask.js';
import {figureWords} from '/page/app/map3d/readout.js';

/* A figure takes its own click while its press still reaches the map's pan handler. Keep the same four-pixel
 * threshold as that handler, including a drag that returns to where it started. */
const FIGURE2D_PICK = {down: null};
$('#map2d').addEventListener('pointermove', event => {
  const down = FIGURE2D_PICK.down;
  if (down && event.pointerId === down.pointer && Math.hypot(event.clientX - down.x, event.clientY - down.y) >= 4) {
    down.dragged = true;
  }
}, true);
$('#map2d').addEventListener('pointercancel', () => { FIGURE2D_PICK.down = null; }, true);

/* The agents in 2D, VIEW-035: the same agents as the 3D map's figures, each drawn as its flat glyph,
 * page/agent-glyphs/<glyph>.svg, the glyph its 3D figure is drawn with. It appears on the DE, walks the 2D map's own
 * edges to its ticket's node, circles the node's box while the ticket is open, and when the ticket closes walks back
 * and is gone; a join's ticket is circled at the middle of the join's edge. Its size is a share of a node's height,
 * so it keeps its place beside the boxes at any zoom, and never so few pixels that it is lost with a large map
 * whole in view. It walks as the 3D figures do, on a smooth curve, setting off and arriving gently, with a step's
 * bounce and a lean the way it goes, and swings onto its orbit the way it came. With reduced motion it stands above
 * its node. */
export const ROAM2D = {figures: new Map(), seen: new Set(), frame: 0, last: 0, speed: 240, size: 1.2, orbit: 0.45,
  lap: 12, appear: 0.8, touch: 0.9, vanish: 0.6,
  // as the 3D figures move, `ROAM`, in the map's own units; the most it leans the way it goes, in degrees; and the
  // fewest pixels it spans on the screen, so it is still seen with the whole of a large map in view
  accel: 300, corner: 0.6, settle: 1.1, lean: 9, least: 22};
const home2d = () => [...S.elements.values()].find(item => item.element.role === 'DE')?.element.id
  || S.elements.keys().next().value;
function route2d(base, from, to) {  // the fewest edges of the 2D map from one element to another
  const near = new Map(), add = (one, two) => { if (!near.has(one)) near.set(one, []); near.get(one).push(two); };
  for (const {join, provider} of base.edges) { add(join.receiver, provider); add(provider, join.receiver); }
  return pathThrough(near, from, to);
}
export function spot2d(base, key) {  // where a 2D figure stands: an element's box, or the middle of a join's edge
  if (!key) return null;  // no node, as while the map is read again and has no elements yet
  if (!key.startsWith('p:')) {
    const node = base.nodes.get(key);
    return node && {x: node.x, y: node.y, w: node.w, h: node.h};
  }
  const path = base.edges.find(edge => edge.join.id === key.slice(2))?.path;
  if (!path?.getTotalLength) return null;
  const middle = path.getPointAtLength(path.getTotalLength() / 2);
  return {x: middle.x, y: middle.y, w: 0, h: 0};
}
function target2d(base, ticket) {  // the ticket's place, and the element its walk ends at
  // a part held deeper than the depth is worked at the node that holds it, VIEW-051
  const at = holderOf(ticket.node_kind === 'join' ? 'p:' + ticket.node_id : ticket.node_id);
  if (!at.startsWith('p:')) return base.nodes.has(at) ? {key: at, last: at} : null;
  const edge = base.edges.find(one => 'p:' + one.join.id === at);
  return edge ? {key: at, last: edge.join.receiver} : null;
}
function back2d(base, figure) {  // the way home, from the middle of a join's edge through its receiver
  const way = route2d(base, figure.last, figure.home);
  return figure.target === figure.last ? way : [figure.target, ...way];
}
export function figures2d(tickets) {
  const base = M.base, home = base && home2d();
  if (!base || !home || !base.nodes.has(home)) return;
  const live = liveWork();
  for (const ticket of tickets) {
    const figure = ROAM2D.figures.get(ticket.id);
    if (figure) {
      figure.g.querySelector('text').textContent = figureWords(ticket.id).card.title;
      const done = !drawnWorking(ticket, live);
      if (figure.done && !done) turnRound2d(figure, base);
      figure.done = done;
      continue;
    }
    const working = drawnWorking(ticket, live), target = working && target2d(base, ticket);
    if (target && !ROAM2D.seen.has(ticket.id)) startFigure2d(ticket, base, home, target);
  }
  for (const [id, figure] of ROAM2D.figures) if (!tickets.some(ticket => ticket.id === id)) figure.done = true;
  again2d();
}
/* A 2D figure whose session works again before it is gone turns round, as the 3D figures do, `turnRound`: from its
 * flourish back onto its orbit, from its way home back along it to its box, and from going on the DE back out and on
 * its way again. Once gone, `gone2d` forgets it was seen, so it walks on as a new figure. */
function turnRound2d(figure, base) {
  const join = figure.target !== figure.last ? [figure.target] : [];
  const toward = from => [...route2d(base, from, figure.last), ...join];
  if (figure.stage === 'flourish') Object.assign(figure, {stage: 'circling', clock: 0});
  else if (figure.stage === 'returning') {
    const from = figure.way[Math.floor(figure.u)]?.key;
    const way = !from || from === figure.target ? [figure.target] : toward(from);
    Object.assign(figure, {stage: 'going', u: 0, speed: 0, clock: 0, stride: 0,
      way: [{point: {x: figure.x, y: figure.y}}, ...way.map(key => ({key}))]});
  } else if (figure.stage === 'leaving') {
    const left = Math.min(1, figure.clock / ROAM2D.vanish);
    Object.assign(figure, {stage: 'arriving', u: 0, speed: 0, clock: (1 - left) * ROAM2D.appear,
      way: toward(figure.home).map(key => ({key}))});
  }
}
/* A flat glyph as the 2D map draws it: an SVG group holding its image. */
function glyph2d(glyph, kind) {
  const g = document.createElementNS(SVG, 'g'), image = document.createElementNS(SVG, 'image');
  g.setAttribute('class', kind);
  image.setAttribute('href', `/page/agent-glyphs/${glyph}.svg`);
  g.append(image);
  return g;
}
/* A new 2D figure for a ticket, the glyph its 3D figure has, set on its way from the DE; a join's figure walks on from
 * its receiver onto the middle of the join's edge. */
function startFigure2d(ticket, base, home, target) {
  const glyph = ROAM.figures.get(ticket.id)?.glyph || glyphFor(ticket.id);
  const g = glyph2d(glyph, 'agent2d');
  g.dataset.glyph = glyph;
  g.style.pointerEvents = 'auto';  // only the glyph and its name, never the empty layer around them
  const name = document.createElementNS(SVG, 'text');
  name.setAttribute('class', 'agent-name');
  name.textContent = figureWords(ticket.id).card.title;
  name.setAttribute('text-anchor', 'middle');
  name.style.fontFamily = 'var(--sans)';
  name.style.fill = 'var(--text)';
  g.append(name);
  g.addEventListener('pointerdown', event => {
    FIGURE2D_PICK.down = event.button === 0 ? {id: ticket.id, pointer: event.pointerId,
      x: event.clientX, y: event.clientY, dragged: false} : null;
  });
  g.addEventListener('click', event => {
    event.stopPropagation();
    const down = FIGURE2D_PICK.down;
    FIGURE2D_PICK.down = null;
    if (down?.id === ticket.id && !down.dragged && event.button === 0) openFigure(ticket.id);
  });
  ROAM2D.seen.add(ticket.id);
  const way = [...route2d(base, home, target.last), ...(target.key !== target.last ? [target.key] : [])];
  const motion = motionOf(glyph, ticket.id);
  ROAM2D.figures.set(ticket.id, {id: ticket.id, glyph, g, home, target: target.key, last: target.last,
    stage: 'arriving', way: way.map(key => ({key})), u: 0, speed: 0, clock: 0, angle: motion.phase * Math.PI * 2,
    stride: 0, lean: 0, motion, from: {x: 0, y: 0}, heading: {x: 1, y: 0}, x: 0, y: 0, size: 0, drawn: '',
    done: false});
}
export function again2d() {
  const wanted = ROAM2D.figures.size || mascotGlyph() || MASCOT2D.g;
  if (wanted && !ROAM2D.frame) ROAM2D.frame = requestAnimationFrame(roam2d);
}
function layer2d(base) {  // the figures are drawn over the boxes, in the boxes' own coordinates
  if (base.agents?.isConnected || (base.agents && base.svg.contains(base.agents))) return base.agents;
  const holder = base.nodes.values().next().value?.g.parentNode;
  if (!holder) return null;
  base.agents = document.createElementNS(SVG, 'g');
  base.agents.setAttribute('class', 'agents2d');
  holder.append(base.agents);
  const heights = [...base.nodes.values()].map(node => node.h).sort((one, two) => one - two);
  base.agentSize = ROAM2D.size * (heights[Math.floor(heights.length / 2)] || 40);
  return base.agents;
}
/* A point of the curve through a 2D figure's places at `u`, its leg and how far along it, a Catmull-Rom curve, which
 * passes through every place and turns smoothly at each. */
function curve2d(points, u) {
  const last = points.length - 1, leg = Math.min(last - 1, Math.max(0, Math.floor(u))), t = u - leg;
  const one = points[leg], two = points[leg + 1];
  const zero = points[leg - 1] || {x: 2 * one.x - two.x, y: 2 * one.y - two.y};
  const three = points[leg + 2] || {x: 2 * two.x - one.x, y: 2 * two.y - one.y};
  const t2 = t * t, t3 = t2 * t;
  const at = (a, b, c, d) =>
    0.5 * (2 * b + (c - a) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (3 * b - a - 3 * c + d) * t3);
  return {x: at(zero.x, one.x, two.x, three.x), y: at(zero.y, one.y, two.y, three.y)};
}
/* A 2D figure walks its way as the 3D figures do, `walk`: from rest up to ROAM2D.speed, slower into each sharp turn,
 * and to rest as it arrives. Says whether it has arrived. */
function walk2d(figure, points, passed) {
  const legs = points.length - 1, motion = figure.motion;
  const top = ROAM2D.speed * (motion?.speed ?? 1), accel = ROAM2D.accel * (motion?.accel ?? 1);
  const corner = CORNERS[motion?.corner]?.slow ?? ROAM2D.corner;
  const lengths = [];
  for (let k = 0; k < legs; k++) {
    lengths.push(Math.max(1e-3, Math.hypot(points[k + 1].x - points[k].x, points[k + 1].y - points[k].y)));
  }
  const turnAt = k => ((points[k].x - points[k - 1].x) * (points[k + 1].x - points[k].x)
    + (points[k].y - points[k - 1].y) * (points[k + 1].y - points[k].y)) / (lengths[k - 1] * lengths[k]);
  let speed = wayspeed(figure.u, lengths, {top, accel, corner}, turnAt);
  if (motion) speed *= strokeOf(motion, figure.stride / Math.max(1, figure.size || 40)).pace;
  figure.top = top;
  const step = speed * passed;
  figure.stride += step;
  goOn(figure, step, lengths);
  figure.speed = speed;
  return figure.u >= legs - 1e-6;
}
/* Where a 2D figure leaves its orbit, or the place it last stood, and the way home from there. */
function home2dFrom(base, figure) {
  const way = back2d(base, figure).slice(1);
  return [{point: {x: figure.x, y: figure.y}}, ...(way.length ? way : [figure.home]).map(key => ({key}))];
}
/* How a flat glyph carries its character's gait, `MOTION`, from its stride in glyph sizes: how high it is off its
 * line, how much it is squashed (less than 0 stretched), and the sway of a swimmer's push. */
function gait2d(figure, moving) {
  const m = figure.motion, stroke = strokeOf(m, figure.stride / Math.max(1, figure.size || 40));
  if (m.go === 'hop') {
    if (figure.wasPhase < 0.75 && stroke.phase >= 0.75) figure.landed = figure.clock;
    figure.wasPhase = stroke.phase;
    const crouch = stroke.phase >= 0.75 ? Math.sin((stroke.phase - 0.75) / 0.25 * Math.PI) : 0;
    const land = Math.exp(-(figure.clock - (figure.landed ?? -9)) * 14);
    const squash = crouch * 0.2 - (stroke.phase < 0.375 ? stroke.air * 0.12 : 0) + land * 0.12;
    return {lift: stroke.air * m.lift * 1.2, squash, sway: 0};
  }
  if (m.go === 'walk' || m.go === 'creep') {
    const lift = moving ? Math.abs(Math.sin(stroke.phase * Math.PI * 2)) * Math.max(0.04, m.lift) : 0;
    return {lift, squash: 0, sway: 0};
  }
  if (m.go === 'swim' || m.go === 'pulse') {
    return {lift: 0, squash: m.go === 'pulse' && moving ? (stroke.thrust - 0.5) * 0.12 : 0,
      sway: moving ? Math.sin(stroke.phase * Math.PI * 2) * 7 * stroke.thrust : 0};
  }
  if (m.go === 'flap') return {lift: moving ? stroke.thrust * 0.05 : 0, squash: 0, sway: 0};
  return {lift: 0, squash: 0, sway: 0};
}
function roam2d() {
  ROAM2D.frame = 0;
  const now = performance.now() / 1000, passed = Math.min(0.1, Math.max(0, now - (ROAM2D.last || now)));
  ROAM2D.last = now;
  const base = M.base, layer = base && layer2d(base);
  // A figure keeps its share of a box's height, and never less than ROAM2D.least pixels on the screen, so it is seen
  // with the whole of a large map in view.
  const view = $('#viewport').getBoundingClientRect();
  const perPixel = M.cam && view.width && M.svg === base?.svg ? M.cam.w / view.width : 0;
  let moving = false;
  for (const [id, figure] of ROAM2D.figures) if (stepFigure2d(id, figure, base, layer, perPixel, passed)) moving = true;
  const awake = mascot2d(base, layer, perPixel, passed);
  // With reduced motion a figure stands still, so the frames stop once each is drawn; a redraw or a change asks again.
  // The mascot alone keeps them going only while it is awake, so a page left alone rests.
  if ((ROAM2D.figures.size && (moving || !reduced())) || awake) ROAM2D.frame = requestAnimationFrame(roam2d);
}
/* Gone from the 2D map, and no longer seen, so its agent walks on again when its session works again. */
function gone2d(id, figure) {
  figure.g.remove();
  ROAM2D.figures.delete(id);
  ROAM2D.seen.delete(id);
  if (!ROAM.figures.has(id)) releaseGlyph(id);
}
/* What each stage does in a frame; a stage that answers false has ended the figure's frame, nothing more is drawn. */
const STAGES2D = {arriving: arriving2d, going: travelling2d, returning: travelling2d, circling: circling2d,
  flourish: finishing2d, leaving: leaving2d};
/* One 2D figure's frame: its stage, then its gait, and its glyph drawn again where anything changed. Says whether it
 * was drawn again. */
function stepFigure2d(id, figure, base, layer, perPixel, passed) {
  if (!layer) { if (figure.done) gone2d(id, figure); return false; }
  if (figure.g.parentNode !== layer) layer.append(figure.g);
  figure.clock += passed;
  const size = Math.max(base.agentSize, ROAM2D.least * perPixel);
  const target = spot2d(base, figure.target), home = spot2d(base, figure.home);
  if (!target || !home) { if (figure.done) gone2d(id, figure); return false; }
  const pose = {x: target.x, y: target.y, scale: 1, lift: 0, lean: 0, squash: 0, spin: 0, going: false};
  if (reduced()) {  // no walking: it stands above its node while the ticket is worked
    pose.y = target.y - target.h / 2 - size / 2;
    if (figure.done) { gone2d(id, figure); return false; }
  } else if (STAGES2D[figure.stage]?.(figure, {id, base, target, home, size, passed, pose}) === false) return false;
  if (!reduced() && figure.stage !== 'leaving' && figure.stage !== 'arriving') {
    const m = figure.motion, step = gait2d(figure, pose.going);
    pose.lift += step.lift; pose.squash += step.squash; pose.lean += step.sway;
    if (!pose.going && m.idle.includes('bob') && figure.stage === 'circling') {
      pose.lift += Math.sin(figure.clock * 2.4 + m.phase * 6) * 0.025;
    }
  }
  figure.lean += (pose.lean - figure.lean) * (1 - Math.exp(-passed * 8));
  const {x, y, scale, lift, squash, spin} = pose;
  Object.assign(figure, {x, y, size: size * scale});
  const drawn = size * scale, foot = y + drawn / 2 - lift * size;
  const nameSize = Math.max(drawn * 0.18, 11 * perPixel), nameY = foot + Math.max(drawn * 0.22, 12 * perPixel);
  const placed = [x - drawn / 2, foot, drawn, figure.lean, squash, spin, nameSize, nameY].map(hundredths).join(' ');
  if (placed === figure.drawn) return false;   // nothing to draw again
  figure.drawn = placed;
  const name = figure.g.querySelector('text');
  name.setAttribute('x', x); name.setAttribute('y', nameY);
  name.style.fontSize = `${nameSize}px`;
  // it leans the way it goes, squashes and stretches from its feet, and turns about its middle in a flourish
  drawFlat(figure.g.firstChild, x, foot, drawn, figure.lean + spin, squash);
  return true;
}
const hundredths = value => Math.round(value * 100) / 100;
/* A flat glyph's image placed with its feet at `foot`, `size` across, leaning `lean` degrees about its middle and
 * squashed from its feet. */
function drawFlat(image, x, foot, size, lean, squash) {
  image.setAttribute('x', x - size / 2); image.setAttribute('y', foot - size);
  image.setAttribute('width', size); image.setAttribute('height', size);
  const stretch = `scale(${(1 + squash * 0.6).toFixed(3)} ${(1 - squash).toFixed(3)})`;
  image.setAttribute('transform', `rotate(${lean.toFixed(2)} ${x} ${foot - size / 2}) `
    + `translate(${x} ${foot}) ${stretch} translate(${-x} ${-foot})`);
}
/* It appears on the DE, in its own way. */
function arriving2d(figure, {home, size, pose}) {
  const m = figure.motion, k = Math.min(1, figure.clock / ROAM2D.appear), e = easeBoth(k);
  ({x: pose.x, y: pose.y} = home);
  if (m.arrive === 'drop') pose.y -= (1 - e) * size * 3;
  else if (m.arrive === 'swoop') { pose.y -= (1 - e) * size * 2.5; pose.x -= (1 - e) * size * 2; }
  else if (m.arrive === 'rise') pose.y += (1 - e) * size * 1.5;
  pose.scale = m.arrive === 'pop' ? Math.max(0.001, 1 + 1.7 * Math.pow(k - 1, 3) + 0.7 * Math.pow(k - 1, 2))
    : Math.max(0.001, Math.min(1, k * 2));
  if (m.arrive === 'sprout') { pose.scale = 1; pose.squash = 1 - Math.max(0.001, e); }
  if (k >= 1) Object.assign(figure, {stage: 'going', u: 0, clock: 0});
}
/* Along the map's own edges, to its node or home again; arrived at its node, it swings onto its orbit from where it
 * came, on the side that carries it straight on. */
function travelling2d(figure, {base, target, size, passed, pose}) {
  const m = figure.motion, out = figure.stage === 'going';
  pose.going = true;
  const points = figure.way.map(step => step.point || spot2d(base, step.key));
  if (points.length < 2 || points.some(point => !point)) {  // a node of its way left the map
    Object.assign(figure, out ? {stage: figure.done ? 'flourish' : 'circling'} : {stage: 'leaving'},
      {clock: 0, from: {x: 0, y: 0}});
    return false;
  }
  const arrived = walk2d(figure, points, passed), at = curve2d(points, figure.u);
  const ahead = curve2d(points, Math.min(points.length - 1, figure.u + 0.02));
  ({x: pose.x, y: pose.y} = at);
  const heading = {x: ahead.x - pose.x, y: ahead.y - pose.y};
  if (Math.hypot(heading.x, heading.y) > 1e-3) figure.heading = heading;
  const pace = Math.min(1, figure.speed / figure.top);
  if (m.corner === 'flit') {  // a moth jinks from side to side
    const across = Math.hypot(figure.heading.x, figure.heading.y) || 1;
    const jink = Math.sin(figure.stride / size * 5.3) * size * 0.2 * pace;
    pose.x += -figure.heading.y / across * jink; pose.y += figure.heading.x / across * jink;
  }
  pose.lean = Math.sign(figure.heading.x) * pace * ROAM2D.lean * (m.corner === 'bank' ? 1.6 : 1);
  if (!arrived) return;
  if (out) {
    const {across, down} = orbit2d(target, size, m);
    figure.from = {x: pose.x - target.x, y: pose.y - target.y};
    figure.angle = m.dir * Math.atan2(figure.from.y / down, figure.from.x / across);
  }
  Object.assign(figure, {clock: 0, stage: !out ? 'leaving' : figure.done ? 'flourish' : 'circling'});
}
/* The half widths of a figure's orbit round a box, across and down. */
function orbit2d(target, size, m) {
  const out = size * ROAM2D.orbit * m.orbit / 1.5;
  return {across: target.w / 2 + out, down: target.h / 2 + out};
}
/* Around its box, in its own way and at its own lap, swinging out from where it arrived: beside it toward the chat
 * dock while it waits, reaching toward what a tool call touched, now and then perched on top or in close at its
 * side. */
function circling2d(figure, {id, base, target, size, passed, pose}) {
  const m = figure.motion, mood = moodOf(id), c = figure.clock;
  let rate = 2 * Math.PI / m.lap;
  if (mood === 'restless') rate *= 1 + 0.55 * Math.sin(c * 1.7) * Math.sin(c * 0.63 + 1);
  if (mood === 'waiting') rate = 0;
  figure.angle += rate * passed;
  const settled = easeBoth(Math.min(1, c / ROAM2D.settle));
  const {across, down} = orbit2d(target, size, m);
  const turn = m.dir * figure.angle;
  const want = {x: target.x + Math.cos(turn) * across, y: target.y + Math.sin(turn) * down};
  if (mood === 'waiting') {  // toward the chat dock
    Object.assign(want, {x: target.x + target.w / 2 + size * 0.7, y: target.y + target.h / 2});
    pose.lean = 8;
  }
  if (figure.reach) reach2d(figure, base, target, want);
  if (mood === 'working' && !figure.act && c > (figure.nextAct ?? 5) && ACTS[m.act]) {
    figure.act = {kind: m.act, at: c, long: ACTS[m.act]};
  }
  if (figure.act) act2d(figure, mood, target, size, turn, want);
  pose.x = target.x + figure.from.x + (want.x - target.x - figure.from.x) * settled;
  pose.y = target.y + figure.from.y + (want.y - target.y - figure.from.y) * settled;
  // its stride goes on with the distance it covers, and a hopper hops in place now and then as it waits
  const covered = Math.hypot(pose.x - figure.x, pose.y - figure.y);
  figure.stride += covered;
  if (m.go === 'hop' && covered < size * 0.01 && Math.sin(c * 0.6 + m.phase * 6) > 0.2) {
    figure.stride += passed * m.stride * size * 0.8;
  }
  pose.going = covered > size * 0.003;
  if (!pose.lean) pose.lean = -Math.sin(turn) * ROAM2D.lean * 0.5 * settled;
  if (figure.done) {
    Object.assign(figure, {stage: 'flourish', clock: 0, from: {x: pose.x - target.x, y: pose.y - target.y}});
  }
}
/* A tool call: a quick reach toward the part it touched, and back. */
function reach2d(figure, base, target, want) {
  const u = (figure.clock - figure.reach.at) / 1.3, to = spot2d(base, figure.reach.to);
  if (u >= 1 || !to) { figure.reach = null; return; }
  const k = Math.sin(Math.PI * u) ** 2, share = to === target || figure.reach.to === figure.target ? 0.5 : 0.3;
  want.x += (to.x - want.x) * share * k; want.y += (to.y - want.y) * share * k;
}
/* Something of its own with its box while it works: perched on top, or in close at its side. */
function act2d(figure, mood, target, size, turn, want) {
  const c = figure.clock, u = (c - figure.act.at) / figure.act.long;
  if (u >= 1 || mood !== 'working') { figure.act = null; figure.nextAct = c + actGap(figure.motion, c); return; }
  const k = easeBoth(Math.min(1, Math.sin(Math.PI * u) * 1.6));
  const [px, py] = figure.act.kind === 'perch' ? [target.x, target.y - target.h / 2 - size * 0.35]
    : [target.x + Math.cos(turn) * (target.w / 2 + size * 0.15),
      target.y + Math.sin(turn) * (target.h / 2 + size * 0.15)];
  want.x += (px - want.x) * k; want.y += (py - want.y) * k;
}
/* Done: its little flourish, then home. */
function finishing2d(figure, {base, target, pose}) {
  const u = Math.min(1, figure.clock / FLOURISH), k = Math.sin(Math.PI * u), kind = figure.motion.flourish;
  pose.x = target.x + figure.from.x; pose.y = target.y + figure.from.y;
  if (kind === 'spin' || kind === 'twirl' || kind === 'loop') pose.spin = easeBoth(u) * 360;
  if (kind === 'hop' || kind === 'flap' || kind === 'twirl') pose.lift = k * 0.9;
  if (kind === 'puff') pose.scale = 1 + 0.3 * k;
  if (kind === 'bow') pose.squash = k * 0.25;
  if (u >= 1) {
    const way = home2dFrom(base, {...figure, x: pose.x, y: pose.y});
    Object.assign(figure, {stage: 'returning', way, u: 0, clock: 0, stride: 0});
  }
}
/* Home again, it is gone. */
function leaving2d(figure, {id, home, pose}) {
  const faded = Math.min(1, figure.clock / ROAM2D.vanish);
  ({x: pose.x, y: pose.y} = home);
  pose.scale = Math.max(0.001, 1 - faded * faded);
  if (faded >= 1) { gone2d(id, figure); return false; }
}
/* The mascot on the 2D map, `MASCOT`: its flat glyph goes to the selected box, waits at its right, below the name,
 * walks over to the figure of the agent the person chats with, and sleeps while the person is away. */
export const MASCOT2D = {g: null, glyph: null, x: null, y: null, vx: 0, vy: 0, stride: 0, clock: 0, lean: 0, drawn: '',
  size: 0};
function mascot2d(base, layer, perPixel, passed) {
  const {glyph, leaving} = mascotFigure();
  if (MASCOT2D.g && (MASCOT2D.glyph !== glyph || !layer)) { MASCOT2D.g.remove(); MASCOT2D.g = null; }
  if (!glyph || !layer || !base || (leaving && !MASCOT2D.g)) return false;
  const size = Math.max(base.agentSize, ROAM2D.least * perPixel) * 0.95;
  if (!MASCOT2D.g) {
    const g = glyph2d(glyph, 'agent2d mascot2d');
    g.style.pointerEvents = 'none';  // never in the way of a click
    Object.assign(MASCOT2D, {g, glyph, motion: motionOf(glyph, 'mascot'), x: null});
  }
  if (MASCOT2D.g.parentNode !== layer) layer.append(MASCOT2D.g);
  MASCOT2D.clock += passed;
  const m = MASCOT2D.motion;
  const driven = !leaving && mascotDriven();
  MASCOT2D.g.classList.toggle('driven', driven);
  const at = mascotSpot2d(base, size, leaving, driven);
  if (!at) return false;
  const wx = at.x + at.w / 2 + size * 0.75, wy = at.y + at.h / 2 - size * 0.15;
  if (MASCOT2D.x === null || reduced()) Object.assign(MASCOT2D, {x: wx, y: wy, vx: 0, vy: 0});
  const asleep = !leaving && !driven && performance.now() - FRAMES.active > FRAMES.idle && !MASCOT.call;
  if (!reduced() && !asleep) steer2d(wx, wy, passed);
  const speed = Math.hypot(MASCOT2D.vx, MASCOT2D.vy);
  MASCOT2D.stride += speed * passed;
  MASCOT2D.size = size;
  const step = reduced() ? {lift: 0, squash: 0, sway: 0} : gait2d(MASCOT2D, speed > size * 0.05);
  const pace = Math.min(1, speed / (ROAM2D.speed * m.speed));
  const lean = asleep ? 6 : Math.sign(MASCOT2D.vx) * pace * ROAM2D.lean + step.sway;
  MASCOT2D.lean += (lean - MASCOT2D.lean) * (1 - Math.exp(-passed * 8));
  const squash = asleep ? 0.08 + Math.sin(MASCOT2D.clock * 0.9) * 0.03 : step.squash;
  const x = MASCOT2D.x, foot = MASCOT2D.y + size / 2 - step.lift * size;
  const placed = [x, foot, size, MASCOT2D.lean, squash].map(hundredths).join(' ');
  const awake = !reduced() && (!asleep || placed !== MASCOT2D.drawn);
  if (placed === MASCOT2D.drawn) return awake;
  MASCOT2D.drawn = placed;
  drawFlat(MASCOT2D.g.firstChild, x, foot, size, MASCOT2D.lean, squash);
  return awake;
}
/* Where the 2D mascot goes: home as its conversation ends; while its agent leads it, where it sent it, the node its
 * body works on, else it stays; on its own, where it is called, beside the figure the person chats with, the
 * selection, or home. */
function mascotSpot2d(base, size, leaving, driven) {
  const chat = !$('#helpdesk')?.hidden && DOCK.target ? ROAM2D.figures.get(DOCK.target) : null;
  const job = driven ? MASCOT.job : null;
  const call = MASCOT.call?.node && (driven || !MASCOT.call.agent) ? spot2d(base, MASCOT.call.node) : null;
  const working = job?.node ? spot2d(base, job.node) : null;
  const chosen = S.selected && spot2d(base, S.selected), home = spot2d(base, home2d());
  const stay = driven && MASCOT2D.x !== null
    ? {x: MASCOT2D.x - size * 0.75, y: MASCOT2D.y + size * 0.15, w: 0, h: 0} : null;
  if (leaving) return home;
  if (driven) return call || working || stay || home;
  return call || (chat ? {x: chat.x + size * 1.1, y: chat.y, w: 0, h: 0} : null) || chosen || home;
}
/* Steering, as the 3D mascot does: off gently, and to rest gently. */
function steer2d(wx, wy, passed) {
  const m = MASCOT2D.motion;
  const top = ROAM2D.speed * m.speed * 0.9, accel = ROAM2D.accel * m.accel, dx = wx - MASCOT2D.x, dy = wy - MASCOT2D.y;
  const away = Math.hypot(dx, dy), speed = Math.min(top, Math.sqrt(2 * accel * Math.max(0, away - 0.5)));
  const want = away > 1e-3 ? [dx / away * speed, dy / away * speed] : [0, 0];
  let ax = want[0] - MASCOT2D.vx, ay = want[1] - MASCOT2D.vy;
  const most = accel * passed * 1.5, push = Math.hypot(ax, ay);
  if (push > most) { ax *= most / push; ay *= most / push; }
  MASCOT2D.vx += ax; MASCOT2D.vy += ay;
  MASCOT2D.x += MASCOT2D.vx * passed; MASCOT2D.y += MASCOT2D.vy * passed;
}
