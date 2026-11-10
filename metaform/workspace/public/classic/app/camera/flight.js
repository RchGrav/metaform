/* The 2D map's framing constants, the two views changing places, and the 3D camera's flights, fits and facing. From
 * the earlier page's camera/flight.js; the 2D map's direction is chosen in views/settings.js on this page. */
import '/classic/app/map3d/draw3d.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
import {$, reduced} from '/classic/app/core/dom.js';
import {S} from '/classic/app/core/reads.js';
import {shownNode} from '/classic/app/map3d/light.js';
import {G, wake3d, ballOf} from '/classic/app/map3d/graph3d.js';
import {LABEL} from '/classic/app/map3d/labels.js';
import {small3d, fly3d, meetEnds, workShot, pivotEnds} from '/classic/app/camera/fly3d.js';
import {VIEW} from '/classic/app/views/settings.js';
import {flatNow, flatFacing} from '/classic/app/views/bar.js';
import {resize} from '/classic/app/views/lens.js';
import {build2D} from '/classic/app/map2d/build.js';
import {note2d} from '/classic/app/map2d/hover.js';
import {FOOT2D, restingCard} from '/classic/app/map2d/camera.js';
import {select} from '/classic/app/selection/select.js';
/* The 2D map's framing, VIEW-041, the same in the large area, the small one and inside a node: full fit, the whole
 * map in the pane, which the page opens in and 0, Home and a Ctrl-click go back to; free zoom, the wheel zooming about
 * the pointer and a drag panning, the view then held where the person leaves it, `free`; and auto zoom, web_node_zoom,
 * on which a selection frames its node with its neighbours, 3 toggling it. `svg` is the drawing the framing is for and
 * `base` whether it is the map's own, `drawing2d`. `page` holds the page's text sizes the auto zoom's closest is read
 * from, `pageText`, and `labels` each drawing's own label size. The 3D map's zoom is its own, VIEW-005. */
export const MODE = {free: false, svg: null, base: false, note: 0, page: null, labels: new WeakMap()};
export const MARGIN = 40;  // the most screen pixels shown beyond the map's edge where it runs past the pane, VIEW-041
/* The two views change places, VIEW-028: the 2D map takes the large area and the 3D map the small one, and back.
 * Each is then drawn for the area it has. The choice is the viewer's own, kept in this browser. */
export const SWAPPED_KEY = 'classic.swapped';
export async function swap(on, remember = true) {
  $('.app').classList.toggle('swapped', on);
  (on ? $('main') : $('#small')).append($('#map2d'));
  (on ? $('#small') : $('main')).append($('#big3d'));
  $('#swapBtn')?.setAttribute('aria-pressed', String(!on));
  if (remember) {
    try { localStorage.setItem(SWAPPED_KEY, on ? '1' : ''); } catch (error) { /* storage can be blocked */ }
  }
  resize();
  if (G) setTimeout(() => refit3d(on), 50);
  if (S.loading || !S.elements.size) return;
  await build2D(false, false, true);  // drawn for its new area, opening as it does on loading, and at once
  if (S.selected) select(S.selected, false, true);
}
/* The 3D map in its new area: a met name kept at the new area's share; an unfocused map still opens whole. */
function refit3d(large2d) {
  if (!large2d && V3.mode === 'work' && workShot(S.selected)) return;
  if (S.selected && (large2d || V3.mode === 'zoom') && fly3d(S.selected)) return;
  if (large2d || V3.mode !== 'free') fit3d(600, large2d ? 24 : 60);
}
/* S, which ? lists, and the header's Swap button swap the maps, `swap`. With the 3D map turned off, View menu, the
 * 2D map keeps the large area and the corner says why. */
export function swapMaps() {
  if ($('.app').classList.contains('no3d')) return note2d('The 3D map is off: the View menu turns it on');
  return swap(!$('.app').classList.contains('swapped'));
}
/* The 3D map's own Fit goes between two views: the whole map, and close on the selected node. It moves the 3D map
 * only, as the 2D map's Fit moves the 2D map only. `auto` says the camera still shows the whole map as the page last
 * fitted it, with no hand and no selection having moved it since, so the layout may fit it again once it settles. */
// `mode`, the large area's Work, Whole, Zoom or Free, `setMode3d`, Work by default, `workShot`; `hold`, the small area's met node the camera follows,
// `holdMet`
export const V3 = {whole: 0, fits: 0, layouts: 0, ticks: 0, auto: true, followed: 0, asked: false, focus: null,
  lens: null, mode: 'work', hold: null};
export const away3d = () => G.camera().position.distanceTo(G.controls().target);
/* The 3D camera's flights, VIEW-008 and VIEW-028. A flight moves the point looked at and the camera's place around it
 * together: the point in a straight line, the camera around it by its turn, its tilt and the log of its distance, so it
 * swings round and moves in or out at an even pace rather than cutting through the map. Each part comes to rest as
 * the flight ends and starts at the speed it has, so a flight asked for while another runs carries on from it without
 * a jolt, and one from rest eases in. Between places far apart the camera draws back on the way, so where it goes is
 * in sight before it arrives. A flight is run each frame before anything is drawn, `prepare3d`, so the labels and the
 * tooltip follow it in the same frame. A hand on the camera ends it; with reduced motion the camera is put there at
 * once. */
export const FLIGHT = {on: false, from: null, to: null, rate: null, start: 0, length: 1, back: 0, done: null};
const PARTS = ['x', 'y', 'z', 'turn', 'tilt', 'far'];
export function cameraNow() {
  const camera = G.camera().position, target = G.controls().target;
  const dx = camera.x - target.x, dy = camera.y - target.y, dz = camera.z - target.z;
  const far = Math.max(1e-6, Math.hypot(dx, dy, dz));
  return {x: target.x, y: target.y, z: target.z, turn: Math.atan2(dx, dz),
    tilt: Math.acos(Math.max(-1, Math.min(1, dy / far))), far: Math.log(far)};
}
function putCamera(at) {
  const camera = G.camera(), target = G.controls().target, far = Math.exp(at.far), across = Math.sin(at.tilt) * far;
  target.set(at.x, at.y, at.z);
  camera.position.set(at.x + across * Math.sin(at.turn), at.y + Math.cos(at.tilt) * far,
    at.z + across * Math.cos(at.turn));
  camera.lookAt(target);
  camera.updateMatrixWorld();
}
/* A cubic from `from`, leaving at `rate` a second, to rest at `to` after `length` seconds: its value and rate at `s`,
 * the share of the time gone. From rest it eases in and out. */
export function hermite(from, to, rate, length, s) {
  const s2 = s * s, s3 = s2 * s;
  return [(2 * s3 - 3 * s2 + 1) * from + (s3 - 2 * s2 + s) * rate * length + (3 * s2 - 2 * s3) * to,
    ((6 * s2 - 6 * s) * from + (3 * s2 - 4 * s + 1) * rate * length + (6 * s - 6 * s2) * to) / length];
}
function flightAt(now) {
  const s = Math.min(1, Math.max(0, (now - FLIGHT.start) / 1000 / FLIGHT.length)), at = {}, rate = {};
  for (const part of PARTS) {
    [at[part], rate[part]] = hermite(FLIGHT.from[part], FLIGHT.to[part], FLIGHT.rate[part], FLIGHT.length, s);
  }
  // drawing back on the way, nothing at either end and at rest there
  at.far += FLIGHT.back * 16 * s * s * (1 - s) * (1 - s);
  rate.far += FLIGHT.back * 32 * s * (1 - s) * (1 - 2 * s) / FLIGHT.length;
  return {at, rate, s};
}
export function flyTo(to, {length = null, done = null} = {}) {
  if (!G) return;
  V3.focus = V3.hold = null;  // a flight elsewhere lets the held node go; a meeting holds it again, `flyToSign`
  pivotEnds();  // and the point turned about, which a flight to the selection's node takes again on arrival, `pivotOn`
  meetEnds();  // every flight starts with the whole scene drawn again; a meeting clears its foreground on arrival
  const now = performance.now(), under = FLIGHT.on ? flightAt(now) : null, here = under ? under.at : cameraNow();
  const goal = {...to, turn: here.turn + Math.atan2(Math.sin(to.turn - here.turn), Math.cos(to.turn - here.turn)),
    tilt: Math.min(Math.PI - 0.05, Math.max(0.05, to.tilt))};
  const moved = Math.hypot(goal.x - here.x, goal.y - here.y, goal.z - here.z) / Math.exp(Math.max(here.far, goal.far));
  const turned = Math.abs(goal.turn - here.turn) + Math.abs(goal.tilt - here.tilt) + Math.abs(goal.far - here.far);
  if (reduced()) {
    Object.assign(FLIGHT, {on: false, done: null});
    putCamera(goal);
    wake3d();
    return done?.();
  }
  Object.assign(FLIGHT, {on: true, from: here, to: goal, start: now, done,
    rate: under ? under.rate : Object.fromEntries(PARTS.map(part => [part, 0])),
    length: length ?? Math.min(1.6, Math.max(0.6, 0.5 + 0.45 * Math.sqrt(moved + turned * 0.6))),
    back: Math.min(Math.log(1.7), 0.3 * Math.max(0, moved - 0.25))});
  wake3d();
}
export function flight(now) {
  if (!FLIGHT.on) return;
  const {at, s} = flightAt(now);
  putCamera(at);
  if (s < 1) return;
  const done = FLIGHT.done;
  Object.assign(FLIGHT, {on: false, done: null});
  done?.();
}
/* Where the camera stands to show the given balls, {x, y, z, r}, whole on the screen with `room` pixels to spare and
 * room above for the labels, seen the way the camera looks now: the point looked at, which is the middle of what is
 * shown, or `toward` of the way from there to the ball `on`, and the distance, the least at which every ball is in
 * view. */
const LOOK = {back: new THREE.Vector3(), right: new THREE.Vector3(), up: new THREE.Vector3(), at: new THREE.Vector3()};
export function framed(balls, {room = 60, on = null, toward = 0, facing = null, mass = 0} = {}) {
  // seen the way the camera looks now, or from `facing`, a turn and a tilt
  const here = {...cameraNow(), ...(facing || {})}, camera = G.camera(), box = $('#stage').getBoundingClientRect();
  const {right, up, at} = lookAxes(here, camera);
  const tall = Math.tan(camera.fov * Math.PI / 360), height = Math.max(1, box.height), width = Math.max(1, box.width);
  const spare = (pixels, of) => Math.max(0.25, 1 - 2 * pixels / of);
  // the room kept at the foot, `foot3d`: the frame fits the height above it, and is raised by half of it, below
  const foot = Math.min(foot3d(), height / 3);
  const across = tall * camera.aspect * spare(room, width);
  const down = tall * spare(room + LABEL.size, height) * (1 - foot / height);
  const raise = result => {
    if (!foot) return result;
    const distance = Math.exp(result.far), lift = foot / height * tall * distance;  // half the room, in map units there
    at.set(result.x, result.y, result.z).addScaledVector(up, -lift);
    return {...result, x: at.x, y: at.y, z: at.z};
  };
  // the middle of what is shown, as seen from the camera's way
  const middle = new THREE.Vector3();
  for (const ball of balls) middle.add(at.set(ball.x, ball.y, ball.z));
  middle.divideScalar(Math.max(1, balls.length));
  if (mass && balls.length >= 6) return raise(massFrame(balls, middle, mass, {across, down, here}));
  const [low, high] = spreadOf(balls, middle);
  middle.addScaledVector(right, (low[0] + high[0]) / 2).addScaledVector(up, (low[1] + high[1]) / 2);
  if (on) middle.lerp(at.set(on.x, on.y, on.z), toward);
  let far = 0;
  for (const ball of balls) far = Math.max(far, needOf(ball, middle, across, down));
  return raise({x: middle.x, y: middle.y, z: middle.z, turn: here.turn, tilt: here.tilt,
    far: Math.log(Math.max(far, 1))});
}
/* The camera's way back, right and up for a turn and a tilt, kept in LOOK. */
function lookAxes(here, camera) {
  const {back, right, up} = LOOK;
  back.set(Math.sin(here.tilt) * Math.sin(here.turn), Math.cos(here.tilt), Math.sin(here.tilt) * Math.cos(here.turn));
  right.crossVectors(camera.up, back);
  if (right.lengthSq() < 1e-8) right.set(1, 0, 0);
  right.normalize();
  up.crossVectors(back, right);
  return LOOK;
}
/* How far the balls reach from the middle, across and up as the camera sees them, each with its radius. */
function spreadOf(balls, middle) {
  const {right, up, at} = LOOK;
  let low = [Infinity, Infinity], high = [-Infinity, -Infinity];
  for (const ball of balls) {
    at.set(ball.x, ball.y, ball.z).sub(middle);
    const x = at.dot(right), y = at.dot(up);
    low = [Math.min(low[0], x - ball.r), Math.min(low[1], y - ball.r)];
    high = [Math.max(high[0], x + ball.r), Math.max(high[1], y + ball.r)];
  }
  return [low, high];
}
/* The distance one ball needs the camera to stand at to have it in view, beyond the point looked at: by its place and
 * size across and up, how much farther from the camera than that point it is, and its own size. */
function needOf(ball, middle, across, down) {
  const {back, right, up, at} = LOOK;
  at.set(ball.x, ball.y, ball.z).sub(middle);
  const ahead = -at.dot(back);  // how much farther from the camera than the point looked at
  return Math.max((Math.abs(at.dot(right)) + ball.r) / across - ahead, (Math.abs(at.dot(up)) + ball.r) / down - ahead,
    ball.r * 2 - ahead);
}
/* The map's mass: across and up as the camera sees them, the spread between the `mass` quantile and its mirror on
 * each axis, so the few nodes far out on their own do not set the frame and may run off the edges. Each node's own
 * need, with its size and its depth as the camera sees it, and only the `mass` share of the nodes that need the most
 * left out, so a small map is framed whole, every node and its ball in view. */
function massFrame(balls, middle, mass, {across, down, here}) {
  const {right, up, at} = LOOK;
  const xs = [], ys = [];
  for (const ball of balls) { at.set(ball.x, ball.y, ball.z).sub(middle); xs.push(at.dot(right)); ys.push(at.dot(up)); }
  const cut = (values, share) => {
    values.sort((a, b) => a - b);
    return values[Math.round(share * (values.length - 1))];
  };
  const low = [cut(xs, mass), cut(ys, mass)], high = [cut(xs, 1 - mass), cut(ys, 1 - mass)];
  middle.addScaledVector(right, (low[0] + high[0]) / 2).addScaledVector(up, (low[1] + high[1]) / 2);
  const needs = balls.map(ball => needOf(ball, middle, across, down)).sort((a, b) => b - a);
  const far = needs[Math.min(needs.length - 1, Math.floor(mass * needs.length))];
  return {x: middle.x, y: middle.y, z: middle.z, turn: here.turn, tilt: here.tilt, far: Math.log(Math.max(far, 1))};
}
/* The room kept free at the foot of the 3D map's window, in screen pixels, as `foot2d` keeps it in 2D: the legend and
 * the count where they stand now, and the hover card at rest, so a card that grows while it shows never moves the
 * camera; and a small gap. */
function foot3d() {
  const view = $('#stage')?.closest('.view3d');
  if (!view) return 0;
  const bottom = view.getBoundingClientRect().bottom, shows = VIEW.hoverInfo || 'name+summary';
  let most = shows === 'name' || shows === 'off' ? 0 : FOOT2D.card || restingCard(view);
  for (const one of view.querySelectorAll(':scope > .legend, :scope > .count')) {
    const box = one.getBoundingClientRect();
    if (one.hidden || !box.height || getComputedStyle(one).display === 'none' || bottom - box.bottom > 60) continue;
    most = Math.max(most, bottom - box.top);
  }
  return most ? most + FOOT2D.gap : 0;
}
export const ball = node => ({x: node.x, y: node.y, z: node.z, r: ballOf(node)});
const drawnBalls = data => data.nodes.filter(node => node.x !== undefined && shownNode(node)).map(ball);
/* What a fit of the whole map frames: its mass, every drawn node with the outer FIT share of their spread trimmed
 * from each side as the camera sees it, `framed`'s `mass`, so the map is seen close enough to read and the few nodes
 * far out on their own may run off the edges; a little more is trimmed in the small area, where room is short. */
const FIT = {large: 0.1, small: 0.12};
export const fitTrim = () => $('.app').classList.contains('swapped') ? FIT.small : FIT.large;
export const fitBalls = data => drawnBalls(data);
export function fit3d(time = 700, room = 60) {
  if (!G) return;
  // In the small area the map is read by its selected node, met at its sign, VIEW-005: the whole map is too small to
  // read there, so with a selection there is one view, and the mouse looks around it.
  if (small3d() && S.selected && fly3d(S.selected)) return;
  const balls = fitBalls(G.graphData());
  Object.assign(V3, {auto: true, asked: true});
  if (!balls.length) return;
  // in Flat a fit faces the plane, so the fits that follow the nodes as they flatten finish the turn instead of ending
  // it
  flyTo(framed(balls, {room, mass: fitTrim(), facing: flatNow() ? flatFacing() : null}),
    {length: time / 1000, done: () => { V3.whole = away3d(); V3.fits++; }});
}
/* A selected node is turned to face the eye: the camera swings round the map's middle to the side the node stands
 * out on, so the node is in front, its sign turned to the eye, VIEW-038, as if the whole map had turned to present it.
 * It stays right side up: the camera keeps the map's up as its own and is never more than TILT off level, so it never
 * looks straight down on the map. Only a selection turns it; a hand on the camera, or a drag, moves it as the hand
 * does. Swinging the camera round the middle shows what turning the whole map would, and keeps every node where the
 * layout put it. */
const TILT = 0.85;  // the most the camera rises above or falls below level, in radians, when it turns to a node
export function facingOf(node, balls) {
  if (flatNow()) return flatFacing();  // the plane is faced square on, whichever node is chosen
  const share = (sum, one) => ({x: sum.x + one.x / balls.length, y: sum.y + one.y / balls.length,
    z: sum.z + one.z / balls.length});
  const middle = balls.reduce(share, {x: 0, y: 0, z: 0});
  const dx = node.x - middle.x, dy = node.y - middle.y, dz = node.z - middle.z, away = Math.hypot(dx, dy, dz);
  if (away < 1e-3) return null;  // the node at the middle: seen from where the camera is
  const tilt = Math.min(Math.PI / 2 + TILT, Math.max(Math.PI / 2 - TILT, Math.acos(dy / away)));
  return {turn: Math.atan2(dx, dz), tilt};
}
