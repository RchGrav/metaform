/* The mascot's word bubble, and cutting an edge, a playful mode of the 3D map: the scissors, the fall, the mascot's
 * repair and the spring back. */
import '/page/app/figures/mascot.js';  // the part before runs first, so the parts run in the page's order
import {$, reduced, h} from '/page/app/core/dom.js';
import {onScreen} from '/page/app/graph/checks.js';
import {ROAM, primaryOf, ballOf, sizeOf} from '/page/app/figures/agents.js';
import {easeBoth, SPOT} from '/page/app/figures/walk.js';
import {MASCOT, mascotGlyph} from '/page/app/figures/mascot.js';
import {mascotEyes} from '/page/app/figures/eyes.js';
import {MASCOT2D} from '/page/app/figures/roam2d.js';
import {linkColor} from '/page/app/map3d/ghosts.js';
import {G, wake3d} from '/page/app/map3d/graph3d.js';
import {AT} from '/page/app/map3d/labels.js';
import {tintOf, fxLine} from '/page/app/flow/fx3d.js';
import {V3} from '/page/app/camera/flight.js';
import {speechBubble, bubbleSeconds} from '/page/app/figures/bubble.js';

/* A word bubble over the mascot, in 3D and 2D: a short line in its voice, eased in and out, placed over the figure
 * each frame so it reads at any angle; one at a time, never piled up. `say` shows one for a while; a click on it does
 * what `onClick` says. */
// `seconds`: web_bubble_seconds, auto or a number, set from the view as the page reads it
export const BUBBLE = {el: null, text: '', until: 0, click: null, seconds: 'auto'};
export function bubble() {
  if (BUBBLE.el) return BUBBLE.el;
  BUBBLE.el = h('div', {class: 'mascot-bubble', role: 'status', 'aria-live': 'polite'});
  BUBBLE.el.addEventListener('click', clickBubble);
  document.body.append(BUBBLE.el);
  return BUBBLE.el;
}
/* A click on the bubble does what it was said with, and the bubble goes. */
function clickBubble(event) {
  event.stopPropagation();
  const act = BUBBLE.click;
  if (act) { hush(); act(); }
}
// `who`: an embodied agent's figure, else the mascot
export function say(text, seconds = 4, onClick = null, who = null, name = '') {
  const el = bubble();
  el.dataset.name = name;  // the agent speaking through it, named quietly over its words; its own words go unnamed
  Object.assign(BUBBLE, {text, until: performance.now() + seconds * 1000, click: onClick, who});
  // drawn as a comic speech bubble whose tail tip stands on the speaker; the words stay in the element for readers
  const drawn = speechBubble(text);
  drawn.canvas.setAttribute('aria-hidden', 'true');
  el.replaceChildren(drawn.canvas, h('span', {class: 'said'}, text));
  el.style.setProperty('--tipx', `${drawn.tip[0]}px`);
  el.style.setProperty('--tipy', `${drawn.tip[1]}px`);
  el.classList.add('drawn');
  el.classList.toggle('clickable', Boolean(onClick));
  el.classList.add('on');
  wake3d(seconds * 1000);
}
/* How long a line stays up, by web_bubble_seconds, `bubbleSeconds`. */
export const readFor = text => bubbleSeconds(text, BUBBLE.seconds);
export function hush() { BUBBLE.until = 0; BUBBLE.el?.classList.remove('on'); }
export function placeBubble() {  // over the mascot as it is drawn: the large map's figure, else the 2D one
  if (!BUBBLE.el) return;
  if (performance.now() > BUBBLE.until) { BUBBLE.el.classList.remove('on'); return; }
  const over = speakerAt3d() || speakerAt2d();
  if (!over) { BUBBLE.el.classList.remove('on'); return; }
  const {x, y} = over;
  BUBBLE.at = {x, y};
  BUBBLE.el.style.left = `${Math.round(x)}px`;
  BUBBLE.el.style.top = `${Math.round(y)}px`;
}
/* Over the figure that speaks in the 3D map, an embodied agent or else the mascot, when it is in front of the eye and
 * drawn: a body the view sees from inside, its own eyes', `eyesOf`, is hidden and carries no bubble at the eye. */
function speakerAt3d() {
  const speaker = (BUBBLE.who && ROAM.figures.get(BUBBLE.who)?.mesh) || MASCOT.mesh;
  if (!G || !speaker?.visible) return null;
  const area = G.renderer().domElement.getBoundingClientRect(), at = SPOT.copy(speaker.position).project(G.camera());
  if (!area.width || Math.abs(at.z) >= 1) return null;
  return {x: area.left + (at.x + 1) / 2 * area.width,
    y: area.top + (1 - at.y) / 2 * area.height - onScreen(speaker) * 0.6};
}
/* Over the mascot's flat glyph on the 2D map. */
function speakerAt2d() {
  if (!MASCOT2D.g?.isConnected) return null;
  const box = MASCOT2D.g.getBoundingClientRect();
  return box.width ? {x: box.left + box.width / 2, y: box.top} : null;
}
/* Cut an edge, VIEW-005, a playful mode of the 3D map: X turns scissors on, and a click cuts the join edge the pointer
 * marks, the edge the page's own picking chooses, `EDGE_PICK`. The edge snaps, its halves whipping back, and whatever
 * has lost its way back to the map's primary node through the joins and namespace links left falls: the group hangs
 * together on its strings like a mobile, swinging as it drops, and lands softly at the foot of the view. The mascot
 * notices, runs over in its own gait, is cross with the person in its own words, picks up the loose end, carries it
 * back with the rest dangling from it, reties the edge with a little flourish, and everything springs back into place.
 * Nearby agents glance over. It is all drawn: no join is changed and nothing is written. Escape, or X again, puts
 * everything back at once. With reduced motion the cut and the repair happen without the swing or the run. */
export const CUT = {on: false, job: null, saved: null};
const CROSS = {jelly: 'Hey! I felt that one in every tentacle.', gearling: 'Clunk! That was load-bearing.',
  kite: 'You cut my string! Rude.', moth: 'Who turned off that light?!', drone: 'Delivery interrupted. Not cool.',
  snail: 'I am going as fast as I can, and you do this?', crystal: 'That join was flawless. Was.',
  wisp: 'Ooh, that sent a chill right through me.', comet: 'Whoa! Did you see that fall?',
  beetle: 'Hmph. I will push it back.',
  slime: 'Splat. Really? Really?', plane: 'Mayday! Mayday! Who did that?', puffer: 'I am puffed up and I am not happy.',
  owl: 'Whoo cut that? Hoo-hum. I saw you.', cubebot: 'ERROR: edge severed. Fixing your mess.',
  mushroom: 'Stomp! That was holding things up!', seahorse: 'Now I have to tie that with my tail.'};
export function cutMode(on) {
  if (!G) return;
  if (!on) restoreCut();
  CUT.on = on;
  $('#stage').classList.toggle('scissors', on);
  if (on) say('Scissors out. Careful…', 2.2);
  wake3d();
}
function restoreCut() {  // everything back where it was, at once
  const saved = CUT.saved;
  CUT.job = null;
  if (!saved) return;
  for (const [node, place] of saved.nodes) Object.assign(node, place);
  for (const link of saved.hidden) if (link.__lineObj) link.__lineObj.visible = true;
  // the layout stops where everything was, with no warmth left to move it and no fit of the view after
  const decay = G.d3AlphaDecay();
  G.d3AlphaDecay(1).d3AlphaMin(0.001).cooldownTime(saved.cooldown);
  V3.ticks = 0;
  setTimeout(() => G?.d3AlphaDecay(decay), 400);
  CUT.saved = null;
  wake3d();
}
function supportedFrom(data, start, cut) {  // what still reaches the primary node through the links left
  const near = new Map(), add = (one, two) => { if (!near.has(one)) near.set(one, []); near.get(one).push(two); };
  for (const link of data.links) {
    if (cut.has(link) || typeof link.source !== 'object') continue;
    add(link.source, link.target); add(link.target, link.source);
  }
  const held = new Set([start]), queue = [start];
  while (queue.length) {
    for (const next of near.get(queue.shift()) || []) if (!held.has(next)) { held.add(next); queue.push(next); }
  }
  return held;
}
/* The layout holds every node where it is; the page moves the fallen ones itself, through where they are held. What
 * each node held is kept, to put everything back. */
function holdLayout(data) {
  const kept = node => ({x: node.x, y: node.y, z: node.z, fx: node.fx, fy: node.fy, fz: node.fz, vx: 0, vy: 0, vz: 0});
  CUT.saved = {nodes: new Map(data.nodes.map(node => [node, kept(node)])), hidden: [], cooldown: G.cooldownTime()};
  for (const node of data.nodes) Object.assign(node, {fx: node.x, fy: node.y, fz: node.z});
  G.cooldownTime(Infinity).d3AlphaMin(0);
  G.d3ReheatSimulation();
}
/* The strings of the fallen group, each link between two fallen nodes but the cut one, at its length now. */
function ropesOf(data, falling, cut) {
  const fell = one => typeof one.source === 'object' && falling.includes(one.source) && falling.includes(one.target);
  return data.links.filter(one => fell(one) && one !== cut).map(one => ({one: one.source, two: one.target,
    long: Math.hypot(one.source.x - one.target.x, one.source.y - one.target.y, one.source.z - one.target.z)}));
}
/* Each fallen node as a verlet body where it is, its drag a little different from its neighbours'. */
function bodiesOf(falling) {
  return new Map(falling.map((node, index) => [node, {x: node.x, y: node.y, z: node.z, px: node.x, py: node.y,
    pz: node.z, drag: 0.985 - (index % 3) * 0.006, home: {x: node.x, y: node.y, z: node.z}}]));
}
export function cutLink(link) {
  const data = G.graphData(), home = primaryOf(data);
  if (!link || !home || CUT.job) return;
  if (!CUT.saved) holdLayout(data);
  CUT.saved.hidden.push(link);
  if (link.__lineObj) link.__lineObj.visible = false;
  const held = supportedFrom(data, home, new Set([link]));
  const loose = held.has(link.source) ? link.target : link.source;
  const anchor = loose === link.source ? link.target : link.source;
  const falling = data.nodes.filter(node => !held.has(node) && node.x !== undefined);
  const span = Math.max(40, sizeOf(data) / ROAM.share);
  CUT.job = {link, loose: falling.includes(loose) ? loose : null, anchor, falling, at: performance.now() / 1000,
    stage: 'fall', clock: 0, span, ropes: ropesOf(data, falling, link), bodies: bodiesOf(falling),
    ends: [link.source, link.target].map(end => ({x: end.x, y: end.y, z: end.z}))};
  // the agents nearby look over
  for (const figure of ROAM.figures.values()) figure.glance = {other: 'cut', until: figure.clock + 1.5};
  if (reduced()) for (const [node, body] of CUT.job.bodies) { body.y = floorAt(body) + ballOf(node); body.py = body.y; }
  wake3d(20000);
}
function floorAt(at) {  // the foot of the view, at the depth of a point
  const camera = G.camera();
  SPOT.set(at.x, at.y, at.z).project(camera);
  SPOT.set(0, -0.86, SPOT.z).unproject(camera);
  return SPOT.y;
}
/* Each frame of a cut: the fall and its swing, the mascot's run, its cross words, the carry, the knot and the spring
 * back, with the halves of the cut edge whipping back as it snaps. */
export function cut3d(size, passed) {
  const job = CUT.job;
  if (!job) return;
  job.clock += passed;
  if (!MASCOT.mesh) mascotForCut(size);  // with no mascot the cut mends itself
  if (job.stage !== 'spring') {
    fall(job, passed);
    carry(job, size);
    tighten(job);
  } else if (springBack(job)) return;
  for (const [node, body] of job.bodies) {
    Object.assign(node, {fx: body.x, fy: body.y, fz: body.z, x: body.x, y: body.y, z: body.z});
  }
  snapBack(job);
  if (job.carried) fxLine(job.anchor, job.carried, tintOf(linkColor(job.link)), 0.8, 0.8);  // the loose end in hand
}
/* The fallen group: verlet bodies under gravity, landing softly at the foot of the view; the one carried rides. */
function fall(job, passed) {
  const g = job.span * 1.4;
  for (const [node, body] of job.bodies) {
    if (job.carried === node) continue;
    if (reduced()) continue;
    const vx = (body.x - body.px) * body.drag, vy = (body.y - body.py) * body.drag, vz = (body.z - body.pz) * body.drag;
    Object.assign(body, {px: body.x, py: body.y, pz: body.z});
    body.x += vx; body.y += vy - g * passed * passed; body.z += vz;
    const floor = floorAt(body.home) + ballOf(node);
    if (body.y < floor) {
      body.y = floor;
      body.py = floor + (body.y - body.py) * -0.25;
      body.px = body.x - vx * 0.6; body.pz = body.z - vz * 0.6;
    }
  }
}
/* The loose end rides above the mascot, and the rest dangles from it. */
function carry(job, size) {
  if (!job.carried) return;
  const at = job.bodies.get(job.carried);
  Object.assign(at, {x: MASCOT.pos.x, y: MASCOT.pos.y + size * 1.1, z: MASCOT.pos.z});
  Object.assign(at, {px: at.x, py: at.y, pz: at.z});
}
/* Its own strings hold the group together: a string pulls only when taut, and the end in hand does not give. */
function tighten(job) {
  for (let round = 0; round < 3; round++) for (const rope of job.ropes) {
    const one = job.bodies.get(rope.one), two = job.bodies.get(rope.two);
    const dx = two.x - one.x, dy = two.y - one.y, dz = two.z - one.z, long = Math.hypot(dx, dy, dz);
    if (long <= rope.long || long < 1e-6) continue;
    const fix = (long - rope.long) / long / 2, pinOne = job.carried === rope.one, pinTwo = job.carried === rope.two;
    const a = pinOne ? 0 : pinTwo ? 2 : 1, b = pinTwo ? 0 : pinOne ? 2 : 1;
    one.x += dx * fix * a; one.y += dy * fix * a; one.z += dz * fix * a;
    two.x -= dx * fix * b; two.y -= dy * fix * b; two.z -= dz * fix * b;
  }
}
/* Everything springs back into place; once there, the cut is over and all is put back. Says whether it is over. */
function springBack(job) {
  const u = Math.min(1, (job.clock) / 1.1), k = 1 - Math.exp(-u * 6) * Math.cos(u * 5);
  for (const body of job.bodies.values()) {
    body.x = body.from.x + (body.home.x - body.from.x) * k;
    body.y = body.from.y + (body.home.y - body.from.y) * k;
    body.z = body.from.z + (body.home.z - body.from.z) * k;
  }
  if (u < 1) return false;
  restoreCut();
  return true;
}
/* The halves of the cut edge whip back to their ends as it snaps. */
function snapBack(job) {
  const snap = Math.min(1, job.clock / 0.55);
  if (snap >= 1 || reduced()) return;
  const back = 1 - (1 + 2.2 * Math.pow(snap - 1, 3) + 1.2 * Math.pow(snap - 1, 2)), color = tintOf(linkColor(job.link));
  const [a, b] = [job.link.source, job.link.target], mid = {x: (job.ends[0].x + job.ends[1].x) / 2,
    y: (job.ends[0].y + job.ends[1].y) / 2, z: (job.ends[0].z + job.ends[1].z) / 2};
  for (const end of [a, b]) {
    const tip = {x: end.x + (mid.x - end.x) * back, y: end.y + (mid.y - end.y) * back,
      z: end.z + (mid.z - end.z) * back};
    fxLine(end, tip, color, 0.9, 0.5);
  }
}
/* What the mascot does about a cut, `mascot3d` asks it each frame: where it goes, what it faces, and how it moves. */
export function mascotForCut(size) {
  const job = CUT.job;
  if (!job) return null;
  const loose = job.loose ? job.bodies.get(job.loose) : null;
  if (!mascotGlyph() || !MASCOT.mesh || !loose) {  // no mascot, or nothing fell: it springs back by itself
    if (job.stage === 'fall' && job.clock > 2.4) startSpring(job);
    return null;
  }
  if (job.stage === 'fall' && job.clock > (reduced() ? 0.2 : 0.7)) Object.assign(job, {stage: 'run', clock: 0});
  if (job.stage === 'run') {
    if (reduced() || MASCOT.pos.distanceTo(AT.set(loose.x, loose.y, loose.z)) < size * 1.6) {
      Object.assign(job, {stage: 'cross', clock: 0});
      say(CROSS[MASCOT.glyph] || 'Hey! Who cut that?', 2.8);
    }
    return {want: SPOT.set(loose.x + size, loose.y, loose.z), fast: 1.7};
  }
  if (job.stage === 'cross') {  // it stomps and puffs up, facing the person
    if (job.clock > 2.4) Object.assign(job, {stage: 'carry', clock: 0, carried: job.loose});
    return {want: null, face: G.camera().position, stomp: true, puff: 1 + 0.12 * Math.max(0, Math.sin(job.clock * 5))};
  }
  if (job.stage === 'carry') {  // back to where the loose end belongs, the rest dangling from it
    const home = job.bodies.get(job.loose).home;
    if (reduced() || MASCOT.pos.distanceTo(AT.set(home.x, home.y - size * 1.1, home.z)) < size * 0.5) {
      Object.assign(job, {stage: 'tie', clock: 0});
      say('There. Knotted.', 1.6);
    }
    return {want: SPOT.set(home.x, home.y - size * 1.1, home.z), fast: 0.8};
  }
  if (job.stage === 'tie') {  // a little knot flourish
    if (job.clock > 1 || reduced()) startSpring(job);
    return {want: null, spin: easeBoth(Math.min(1, job.clock)) * Math.PI * 2};
  }
  return null;
}
function startSpring(job) {
  job.carried = null;
  for (const body of job.bodies.values()) body.from = {x: body.x, y: body.y, z: body.z};
  for (const link of CUT.saved?.hidden || []) if (link.__lineObj) link.__lineObj.visible = true;
  Object.assign(job, {stage: 'spring', clock: reduced() ? 9 : 0});
}
/* X takes the scissors out and puts them away, E looks through the mascot's eyes and back, and Escape puts a cut
 * back; none of them while a key is typed into a field or held with a modifier. */
function cutKeys(event) {
  if (!G || event.ctrlKey || event.metaKey || event.altKey) return;
  if (event.target.closest?.('input, textarea, select, [contenteditable="true"]')) return;
  if (event.key === 'x' || event.key === 'X') cutMode(!CUT.on);
  else if ((event.key === 'e' || event.key === 'E') && MASCOT.mesh) mascotEyes();
  else if (event.key === 'Escape' && CUT.on) { event.stopImmediatePropagation(); cutMode(false); }
}
document.addEventListener('keydown', cutKeys, true);
