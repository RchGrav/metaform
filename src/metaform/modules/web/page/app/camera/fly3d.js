/* The 3D camera meeting a selection's name, flying to it, meeting signs, keeping a spreading map framed, the 3D
 * modes, and the page's easing tokens. */
import '/page/app/camera/flight.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
import {$, reduced} from '/page/app/core/dom.js';
import {S, MEM} from '/page/app/core/reads.js';
import {nodeIn, selectedNode} from '/page/app/graph/data.js';
import {ROAM, ballOf, sizeOf} from '/page/app/figures/agents.js';
import {shownNode} from '/page/app/map3d/light.js';
import {endOf} from '/page/app/map3d/waves.js';
import {G, FRAMES, wake3d, LAYOUT, TOUCHED} from '/page/app/map3d/graph3d.js';
import {LABEL, tags, layered, MET, middle, signsOut} from '/page/app/map3d/labels.js';
import {V3, FLIGHT, cameraNow, flyTo, framed, ball, fitTrim, fitBalls, fit3d,
  facingOf} from '/page/app/camera/flight.js';
import {flatNow, flatFacing} from '/page/app/views/bar.js';
import {VIEW} from '/page/app/views/settings.js';
import {FOLLOW} from '/page/app/map2d/camera.js';

/* A selection meets its name at a fixed share of the panel's width, VIEW-005. The large area's levels are a quarter,
 * a half and three quarters, opening at 2; the small area always uses four fifths. Unnamed nodes use their neighbors
 * for framing. Without `close` the camera keeps its distance. */
// the small pane: the name block fills 80% of the width or of the height, whichever binds
export const NAME = {in: 0.8, level: 2, tall: 0.8, floor: 12};
export const small3d = () => $('.app').classList.contains('swapped');
/* How far the camera stands, as a log, for the node's name, at its real size in the map, to span `share` of the
 * view's width; null while the name is not drawn yet. */
/* The selected name at `share` of the view's width, VIEW-005: in the small area four fifths, NAME.in, unless at that
 * size it would be taller than the pane, when it fits NAME.tall of the pane's height instead, every wrapped line in
 * view. The camera's distance does the framing; the name is drawn as it is. In the small
 * area, where even the floor would not fit its lines, the name is drawn on one line ending in an ellipsis,
 * `SMALL_NAME`. */
export const SMALL_NAME = {id: null};
const NODE_AT = new THREE.Vector3();
function nameFar(node, share) {
  const tag = tags.get(node.id), sign = tag?.sprite;
  if (!sign?.scale.x) return null;
  const camera = G.camera(), tall = 2 * Math.tan(camera.fov * Math.PI / 360), across = tall * camera.aspect;
  const out = Math.hypot(sign.position.x - node.x, sign.position.y - node.y, sign.position.z - node.z);
  // The sign's size in the map is not fixed: `placeLabel` sizes its letters by the depth of its node, growing as the
  // node's depth to the power 1 - LABEL.rate, so the nearer the camera comes the smaller the sign stands in the map.
  // Measured at the node's depth now, `now`, its size at the depth the camera will stand at, `far`, is that size
  // times (far / now) ** (1 - LABEL.rate). Taking its size now as its size there left the name short of its share
  // once names grew at 0.75 of the map's rate, 2026-10-17.
  const now = -NODE_AT.set(node.x, node.y, node.z).applyMatrix4(camera.matrixWorldInverse).z;
  if (!(now > 1e-3)) return null;
  const grow = 1 - LABEL.rate;
  // In the small pane the whole name block fits, every line inside with a margin: 80% of the width unless its height
  // needs the camera farther, so the farther of the two fits wins and a name of two lines stays two lines; the camera
  // distance alone sizes it, and the name itself is never capped. Measured in a 150 px pane, 2026-10-12, where a name
  // of two lines was clipped. The large area's levels are a share of its width alone.
  const need = Math.max(sign.scale.x / (share * across), small3d() ? sign.scale.y / (NAME.tall * tall) : 0);
  // The camera meets the sign square on, `flyToSign`, its node `out` behind it: the node's depth `far` is the sign's
  // `far - out`, and the sign spans its share when far - out = need * (far / now) ** grow. Each step from the
  // sign's size now cuts the error to at most `grow` of what it was, so a few steps settle it.
  let far = out + need;
  for (let step = 0; step < 12; step++) far = out + need * Math.pow(far / now, grow);
  SMALL_NAME.id = null;
  return Math.log(far);
}
export function fly3d(id, close = true) {
  const data = G ? G.graphData() : null, node = nodeIn(data, id);
  if (!node || node.x === undefined) return false;
  const around = nearestAround(data, node);
  const facing = facingOf(node, fitBalls(data));
  const view = framed([ball(node), ...around.map(ball)], {room: 70, on: node, toward: 1, facing});
  const whole = framed(fitBalls(data), {facing, mass: fitTrim()}).far;
  // `close` 'whole': turned to the node at the whole map's distance, the map around it, `follow3d`
  if (close === 'whole') { view.far = whole; V3.auto = false; flyTo(view); V3.focus = null; return true; }
  // a selection keeps the zoom the person has
  view.far = close ? Math.min(Math.max(view.far, Math.log(ballOf(node) * 7)), whole + Math.log(0.4))
    : (FLIGHT.on ? FLIGHT.to.far : cameraNow().far);
  // Measure the selected font and any newly selected join title before choosing the distance. Measuring the old
  // label lets it grow past the intended framing on the next frame.
  if (close) layered();
  const named = close ? nameFar(node, small3d() ? NAME.in : NAME.level / 4) : null;
  if (named !== null) view.far = named;
  V3.auto = false;
  const sign = close ? tags.get(node.id)?.sprite : null;  // a join's, its receiver's, which bears its title
  if (sign?.scale.x && !MEM.key && flyToSign(sign, node, view, data)) return true;
  flyTo(view);
  return true;
}
/* The three nearest of a node's neighbours drawn, its own links' ends and, selected, its neighbours in the map. */
function nearestAround(data, node) {
  const id = node.id, near = new Set(id === S.selected ? S.neighbors : []);
  for (const link of data.links) {
    const one = endOf(link.source), two = endOf(link.target);
    if (one === id) near.add(two);
    if (two === id) near.add(one);
  }
  near.delete(id);
  const reach = item => Math.hypot(item.x - node.x, item.y - node.y, item.z - node.z);
  return data.nodes.filter(item => near.has(item.id) && item.x !== undefined && shownNode(item))
    .sort((one, two) => reach(one) - reach(two)).slice(0, 3);
}
/* The camera meets the node's sign: square on to it, along the way it faces, so its letters are level and whole, at
 * the distance the view chose for the node; on arrival what stands between the eye and the sign is cleared,
 * `meetBegins`. A hand on the camera ends the meeting and the camera eases back to the view. Says whether it flies,
 * which it does not for a sign at its node's very center. */
function flyToSign(sign, node, view, data) {
  const face = new THREE.Vector3(sign.position.x - node.x, sign.position.y - node.y, sign.position.z - node.z);
  const out = face.length();
  if (out <= 1e-6) return false;
  face.divideScalar(out);
  const reach = Math.max(Math.exp(view.far) - out, 1e-3);
  // How near the agents circling the node come to the eye: their orbit, its rise and fall, and a figure's size.
  const size = ROAM.drawn || sizeOf(data), ring = (ballOf(node) + size * ROAM.orbit) * 1.05 + size * 1.3;
  MEET.back = {id: node.id, far: view.far};
  // in Flat the sign stands above its node and faces the eye, so the camera meets it facing the plane
  const square = flatNow() ? flatFacing()
    : {turn: Math.atan2(face.x, face.z), tilt: Math.acos(Math.max(-1, Math.min(1, face.y)))};
  flyTo({x: sign.position.x, y: sign.position.y, z: sign.position.z, ...square, far: Math.log(reach)},
    {done: () => meetBegins(reach, reach + out - ring)});
  V3.focus = node.id;
  if (small3d() && node.id === selectedNode()) {  // the selection's node, a join's receiver
    V3.hold = {id: node.id, node, data, x: node.x, y: node.y, z: node.z, shape: null, out: null};
  }
  return true;
}
/* The small area holds its met name, VIEW-005: a change on the map hands the layout new data and it moves again, and
 * the camera follows the selected node by the same step each frame, at the same distance, so the name stays where it
 * was met with its near plane as it was; during the flight to it, the flight's ends move with it. A sign that stands
 * out from the map's middle turns round its node as the middle moves, and the camera turns round the node with it,
 * so the name stays square to the eye: followed by the step alone, it turned edge on and slid aside, measured
 * 2026-10-14 at a third of its met width three seconds after a reheat. A node drawn again is a new object, found by
 * its id. A name drawn at a new size is met again, once. It lets go at a hand on the camera, any other flight, another
 * selection, a memory network or the panes swapping. */
export function holdMet(data) {
  const hold = V3.hold;
  if (!hold) return;
  if (!small3d() || hold.id !== selectedNode() || MEM.key) { V3.hold = null; return; }
  if (hold.data !== data) {
    hold.data = data;
    hold.node = nodeIn(data, hold.id);
    if (!hold.node) { V3.hold = null; return; }
  }
  const node = hold.node;
  if (node.x === undefined) return;
  // the way its sign stands out, as `outward` takes it; none at the middle itself, where the sign stands up
  let out = signsOut() ? HELD.out.set(node.x - middle.x, node.y - middle.y, node.z - middle.z) : null;
  out = out && out.lengthSq() > 1e-6 ? out.normalize() : null;
  const turned = Boolean(out && hold.out && !FLIGHT.on && hold.out.dot(out) < 1 - 1e-9);
  if (turned) HELD.turn.setFromUnitVectors(hold.out, out);
  if (out) (hold.out ||= new THREE.Vector3()).copy(out);
  if (node.x !== hold.x || node.y !== hold.y || node.z !== hold.z || turned) {
    HELD.from.set(hold.x, hold.y, hold.z);
    HELD.to.set(node.x, node.y, node.z);
    Object.assign(hold, {x: node.x, y: node.y, z: node.z});
    if (FLIGHT.on) {
      for (const end of [FLIGHT.from, FLIGHT.to]) Object.assign(end, {x: end.x + node.x - HELD.from.x,
        y: end.y + node.y - HELD.from.y, z: end.z + node.z - HELD.from.z});
    } else {
      const camera = G.camera(), target = G.controls().target;
      for (const point of [camera.position, target]) {
        point.sub(HELD.from);
        if (turned) point.applyQuaternion(HELD.turn);
        point.add(HELD.to);
      }
      camera.lookAt(target);
    }
  }
  // the name's size on its canvas, taken once it is met; a new size, its text or its look changed, is met again
  const shape = tags.get(hold.id)?.shape;
  if (FLIGHT.on || !shape) return;
  if (!hold.shape) { hold.shape = {width: shape.width, height: shape.height}; return; }
  if (Math.abs(shape.width - hold.shape.width) > 1 || Math.abs(shape.height - hold.shape.height) > 1) fly3d(hold.id);
}
const HELD = {from: new THREE.Vector3(), to: new THREE.Vector3(), out: new THREE.Vector3(),
  turn: new THREE.Quaternion()};
/* Meeting a sign, VIEW-005: the camera's near plane is moved out to just short of the sign, so the nodes, signs and
 * edges between the eye and it are not drawn and it is read whole; it eases there and back. The plane is the camera's
 * own, set back to its value when the meeting ends. */
export const MEET = {on: false, back: null, own: null, from: 0, to: 0, start: 0};
function easeNear(to, length = 0.35) {
  const camera = G.camera();
  if (MEET.own === null) MEET.own = camera.near;
  Object.assign(MEET, {from: camera.near, to, start: performance.now()});
  const step = now => {
    const s = reduced() ? 1 : Math.min(1, (now - MEET.start) / (length * 1000)), e = s * s * (3 - 2 * s);
    camera.near = MEET.from + (MEET.to - MEET.from) * e;
    camera.updateProjectionMatrix();
    wake3d();
    if (s < 1 && MEET.to === to) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}
function meetBegins(reach, clear = reach) {
  MEET.on = true;
  // in the small area the map behind the met sign goes soft, as a lens focused on the sign sees it
  $('#big3d').classList.toggle('met', small3d());
  // The sign is square to the eye, so its whole face is at one depth: the plane stops a hair short of it, and
  // nothing in front of it, an edge crossing the last stretch included, is drawn. Where the node's agents circle
  // nearer the eye than the sign, the plane stops short of their orbit, so an agent passing in front is drawn whole;
  // it never comes nearer than the camera's own plane.
  const own = MEET.own ?? G.camera().near;
  easeNear(Math.max(own, Math.min(reach - Math.max(0.05, reach * 0.004), clear)));
}
/* `now`: the near plane back at once, not eased, for a camera that leaves the meeting's place in the same frame, as
 * when the view goes to an agent's eyes, `eyesOf`. */
export function meetEnds(now = false) {
  if (MEET.own === null || (!MEET.on && G.camera().near === MEET.own && MEET.to === MEET.own)) return;
  MEET.on = false;
  if (MET.box) MET.box.hidden = true;
  $('#big3d').classList.remove('met');
  if (!now) return easeNear(MEET.own);
  Object.assign(MEET, {from: MEET.own, to: MEET.own});
  G.camera().near = MEET.own;
  G.camera().updateProjectionMatrix();
}
/* While a map opens and its layout first spreads out, the camera keeps it framed, easing after it four times a second,
 * so the map unfolds in view rather than off the edge of it or as a speck in the middle; the page's first fit then has
 * little left to do. It stops once a fit is asked for, at a hand on the camera, or when the layout rests. */
export function frameWhileSpreading(now, data) {
  if (V3.asked || !V3.auto || !FRAMES.engine || MEM.key || reduced() || now - V3.followed < 250) return;
  V3.followed = now;
  const balls = fitBalls(data);
  if (balls.length > 1) flyTo(framed(balls, {mass: fitTrim()}), {length: 0.9});
}
/* Once the layout has settled, the map is fitted to the view, so the shape it settled into is seen whole, unless a
 * hand or a selection has moved the camera since the page last fitted it, or the layout is held, or the camera already
 * shows it so. */
export function settled3d() {
  if (!G || !V3.auto || FLIGHT.on || MEM.key || LAYOUT.paused) return;
  const balls = fitBalls(G.graphData());
  if (!balls.length) return;
  const view = framed(balls, {mass: fitTrim()}), here = cameraNow();
  const off = Math.hypot(view.x - here.x, view.y - here.y, view.z - here.z) / Math.exp(here.far);
  if (Math.abs(view.far - here.far) > 0.06 || off > 0.04) fit3d(1100);
}
/* The 3D map's modes in the large area, VIEW-005, `V3.mode`, `setMode3d`: Work, the default, shows the work going on,
 * `workShot`; Whole keeps the whole map framed through selections, layout changes and new sizes; Zoom follows the
 * selection close up, at the name level 1 chose; Free moves the camera only by hand. A hand on the camera always takes
 * over: the mode moves it again at the next selection or change. F fits the whole map once and leaves the mode as it
 * is. The small area is not configured: it takes none of these keys and meets each selection on its own, while the
 * hand still moves it. */

/* Work: rather than closing on a node, the camera takes the shot in which the work is seen. A selected node is shown
 * with the agents working on it, and with no selection every node agents work at, with them; of the angles round it,
 * the one where most of that is in view, nothing of the map standing in front of it, and the node, its name and each
 * agent apart from one another rather than one behind the other, so several agents are all seen in perspective. It
 * prefers a slightly raised view and the way the camera already looks, so it does not swing round for little. A node
 * with nobody at work on it is met close, as Zoom meets it; with no work anywhere the whole map is shown. It is taken
 * at a selection, at an agent's start, when the mode is chosen, and again as an agent arrives at its node or finishes
 * there, `workChanged`; a burst of those is one shot. */
const SHOT = {pending: false, count: 0, obstacles: 0, exempt: new Set(), size: 0,
  xs: new Float64Array(64), ys: new Float64Array(64), zs: new Float64Array(64), rs: new Float64Array(64),
  ox: new Float64Array(256), oy: new Float64Array(256), oz: new Float64Array(256), or: new Float64Array(256)};
const SHOT_TURNS = 12, SHOT_TILTS = [0.8, 1.05, 1.3, 1.6], SHOT_LEVEL = 1.15;
export function workShot(focus = null) {
  if (!G) return false;
  const data = G.graphData();
  if (!gatherWork(focus, data)) {
    if (focus !== null) return fly3d(focus);
    fit3d();
    return true;
  }
  const facing = bestFacing(data), balls = [];
  for (let i = 0; i < SHOT.count; i++) balls.push({x: SHOT.xs[i], y: SHOT.ys[i], z: SHOT.zs[i], r: SHOT.rs[i]});
  V3.auto = false;
  flyTo(framed(balls, {room: 70, facing}));
  return true;
}
/* An agent arrived at its node or finished its work there: the work shot is taken again, once for a burst, unless the
 * person used a map in the last 8 seconds, `TOUCHED`, follows an agent, looks through an agent's eyes, turned node
 * zoom off, or has a node selected that this agent is not at. */
export function workChanged(target) {
  if (V3.mode !== 'work' || !G || small3d() || V3.eyes || FOLLOW.work || VIEW.nodeZoom === false) return;
  if (performance.now() - TOUCHED.at < 8000 || (S.selected && target !== S.selected)) return;
  shotSoon();
}
ROAM.onWork = workChanged;
export function shotSoon() {
  if (SHOT.pending) return;
  SHOT.pending = true;
  requestAnimationFrame(() => { SHOT.pending = false; if (V3.mode === 'work' && !small3d()) workShot(S.selected); });
}
function addPoint(x, y, z, r) {
  if (SHOT.count === SHOT.xs.length) for (const name of ['xs', 'ys', 'zs', 'rs']) SHOT[name] = grown(SHOT[name]);
  const at = SHOT.count++;
  SHOT.xs[at] = x; SHOT.ys[at] = y; SHOT.zs[at] = z; SHOT.rs[at] = r;
}
const grown = values => { const more = new Float64Array(values.length * 2); more.set(values); return more; };
/* The points the shot keeps in view: each agent at work, at `focus` or anywhere, with its node and the node's name.
 * Says how many agents. */
function gatherWork(focus, data) {
  SHOT.count = 0;
  SHOT.exempt.clear();
  SHOT.size = ROAM.drawn || sizeOf(data);
  let workers = 0;
  for (const figure of ROAM.figures.values()) {
    if (figure.stage !== 'circling' || figure.done || (focus !== null && figure.target !== focus)) continue;
    const node = nodeIn(data, figure.target);
    if (!node || node.x === undefined) continue;
    const at = figure.mesh.position;
    addPoint(at.x, at.y, at.z, SHOT.size * 0.8);
    workers++;
    if (SHOT.exempt.has(node.id)) continue;
    SHOT.exempt.add(node.id);
    addPoint(node.x, node.y, node.z, ballOf(node));
    const sign = tags.get(node.id)?.sprite;
    if (sign?.visible && sign.scale.x) addPoint(sign.position.x, sign.position.y, sign.position.z, sign.scale.x / 2);
  }
  return workers;
}
/* The turn and tilt the shot is seen from: of SHOT_TURNS turns at each of SHOT_TILTS, and the way the camera looks
 * now, the one where the fewest of the points are hidden behind the map, the points stand farthest apart across the
 * view, the view is nearest a little raised, and the camera turns least. */
function bestFacing(data) {
  const n = SHOT.count, {xs, ys, zs, rs} = SHOT;
  let cx = 0, cy = 0, cz = 0, spread = 0;
  for (let i = 0; i < n; i++) { cx += xs[i]; cy += ys[i]; cz += zs[i]; }
  cx /= n; cy /= n; cz /= n;
  for (let i = 0; i < n; i++) spread = Math.max(spread, Math.hypot(xs[i] - cx, ys[i] - cy, zs[i] - cz) + rs[i]);
  const reach = spread / Math.tan(G.camera().fov * Math.PI / 360) * 1.3 + spread;
  obstaclesNear(data, cx, cy, cz, reach + spread);
  const here = cameraNow();
  let best = -Infinity, turn = here.turn, tilt = here.tilt;
  for (let t = 0; t <= SHOT_TURNS * SHOT_TILTS.length; t++) {
    const last = t === SHOT_TURNS * SHOT_TILTS.length;
    const oneTurn = last ? here.turn : (t % SHOT_TURNS) * 2 * Math.PI / SHOT_TURNS;
    const oneTilt = last ? here.tilt : SHOT_TILTS[Math.floor(t / SHOT_TURNS)];
    const score = shotScore(oneTurn, oneTilt, cx, cy, cz, reach, here);
    if (score > best) { best = score; turn = oneTurn; tilt = oneTilt; }
  }
  return {turn, tilt};
}
/* The drawn nodes near the shot that could stand in front of it, every one but the nodes at work. */
function obstaclesNear(data, cx, cy, cz, within) {
  SHOT.obstacles = 0;
  for (const node of data.nodes) {
    if (node.x === undefined || SHOT.exempt.has(node.id) || !shownNode(node)) continue;
    if (Math.hypot(node.x - cx, node.y - cy, node.z - cz) > within) continue;
    if (SHOT.obstacles === SHOT.ox.length) for (const name of ['ox', 'oy', 'oz', 'or']) SHOT[name] = grown(SHOT[name]);
    const at = SHOT.obstacles++;
    SHOT.ox[at] = node.x; SHOT.oy[at] = node.y; SHOT.oz[at] = node.z; SHOT.or[at] = ballOf(node);
  }
}
function shotScore(turn, tilt, cx, cy, cz, reach, here) {
  const n = SHOT.count, {xs, ys, zs, rs, ox, oy, oz, or} = SHOT;
  const dx = Math.sin(tilt) * Math.sin(turn), dy = Math.cos(tilt), dz = Math.sin(tilt) * Math.cos(turn);
  const ex = cx + dx * reach, ey = cy + dy * reach, ez = cz + dz * reach;  // the eye
  let hidden = 0;
  for (let i = 0; i < n; i++) {
    const vx = xs[i] - ex, vy = ys[i] - ey, vz = zs[i] - ez, long = vx * vx + vy * vy + vz * vz;
    for (let o = 0; o < SHOT.obstacles; o++) {
      const s = ((ox[o] - ex) * vx + (oy[o] - ey) * vy + (oz[o] - ez) * vz) / long;
      if (s <= 0 || s >= 0.97) continue;  // behind the eye, or at the point itself
      const gx = ex + vx * s - ox[o], gy = ey + vy * s - oy[o], gz = ez + vz * s - oz[o];
      if (gx * gx + gy * gy + gz * gz < or[o] * or[o] * 0.8) { hidden++; break; }
    }
  }
  // how far apart the two points least apart stand across the view, as a share of their distance in the map: 1 side by
  // side, 0 one straight behind the other, whatever the shot's size
  let apart = 1;
  for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
    const vx = xs[j] - xs[i], vy = ys[j] - ys[i], vz = zs[j] - zs[i], along = vx * dx + vy * dy + vz * dz;
    const long = vx * vx + vy * vy + vz * vz;
    if (long > 1e-9) apart = Math.min(apart, Math.sqrt(Math.max(0, 1 - along * along / long)));
  }
  const swing = Math.acos(Math.max(-1, Math.min(1, Math.sin(here.tilt) * Math.sin(here.turn) * dx
    + Math.cos(here.tilt) * dy + Math.sin(here.tilt) * Math.cos(here.turn) * dz)));
  return -2 * hidden + apart - 0.3 * Math.abs(tilt - SHOT_LEVEL) - 0.2 * swing;
}
/* The page's easing tokens: one set for every motion, defined once here and as CSS custom properties in app.css's
 * :root (--ease-arrive, --ease-leave, --ease-move, --dur-1 to --dur-3), the same curves. What arrives settles with a
 * spring's ease-out and no overshoot; what leaves goes with a gentle ease-in; a move from one place to another eases
 * both ways; a larger move takes a little longer, `durFor`. CSS transitions carry an interrupted move on from where
 * it is. With reduced motion every state still changes, without moving. The maps' cameras ease as before, aim2d,
 * settle2D and the 3D flights, on curves of the same feel; the agents' figures take these. */
export const EASE = {arrive: [0.16, 1, 0.3, 1], leave: [0.5, 0, 0.75, 0], move: [0.45, 0, 0.2, 1], short: 180,
  medium: 320, long: 520};
export const durFor = pixels => Math.round(Math.min(EASE.long, EASE.short + Math.sqrt(Math.max(0, pixels)) * 9));
/* A token's curve as a function of the share of time gone, for motion drawn on a canvas or in the 3D scene. */
export function easeCurve([x1, y1, x2, y2]) {
  const at = (t, one, two) => 3 * one * t * (1 - t) ** 2 + 3 * two * t * t * (1 - t) + t ** 3;
  return s => {
    if (s <= 0 || s >= 1) return Math.min(1, Math.max(0, s));
    let low = 0, high = 1, t = s;
    for (let step = 0; step < 24; step++) { t = (low + high) / 2; if (at(t, x1, x2) < s) low = t; else high = t; }
    return at(t, y1, y2);
  };
}
// for the flow's figures, the same curves
window.metaformEase = {...EASE, durFor, curve: name => easeCurve(EASE[name])};
