/* The 2D map's camera, VIEW-041: its frame and fades, eased moves, full fit, the zoom held where it is left, auto
 * zoom on a selection, and resets. */
import '/classic/app/map2d/inside.js';  // the part before runs first, so the parts run in the page's order
import {$, reduced, h} from '/classic/app/core/dom.js';
import {joinOf} from '/classic/app/graph/data.js';
import {MODE, MARGIN, hermite} from '/classic/app/camera/flight.js';
import {VIEW} from '/classic/app/views/settings.js';
import {M} from '/classic/app/map2d/build.js';
import {note2d, hover2d} from '/classic/app/map2d/hover.js';

function aspect() {
  const box = $('#viewport').getBoundingClientRect();
  return Math.max(0.2, box.width / Math.max(1, box.height));
}
/* A box grown to the pane's width to height about its middle, so all of it shows. */
export function frame(box) {
  let {x, y, w, h: height} = box;
  const a = aspect();
  if (w / height > a) {
    const nh = w / a;
    y -= (nh - height) / 2; height = nh;
  } else {
    const nw = height * a;
    x -= (nw - w) / 2; w = nw;
  }
  return {x, y, w, h: height};
}
/* A view fades in or out, and the promise settles once the browser has run the fade's time, which starts late when
 * frames come late; a fade that changes nothing settles on the timer. With reduced motion it changes at once,
 * VIEW-016. */
export function fade(svg, to, ms = 480) {
  if (reduced()) { svg.style.transition = ''; svg.style.opacity = ''; return Promise.resolve(); }
  svg.style.transition = `opacity ${ms}ms ease`;
  svg.getBoundingClientRect();  // the fade starts from the opacity the view has now
  svg.style.opacity = String(to);
  const run = svg.getAnimations().find(one => one.transitionProperty === 'opacity');
  if (!run) return new Promise(resolve => setTimeout(resolve, ms));
  return run.finished.then(() => {}, () => {});  // a fade cut by another, or by its view leaving the page, settles too
}
/* A view that has just been put in place, faded in from nothing. */
export function arrive(svg) {
  if (reduced()) return;
  svg.style.transition = ''; svg.style.opacity = '0';
  fade(svg, 1);
}
export const into = node => ({x: node.x - node.w * 0.6, y: node.y - node.h * 0.6, w: node.w * 1.2, h: node.h * 1.2});
/* The camera is the map's viewBox, VIEW-041. */
export function setCam(cam) {
  M.cam = cam;
  M.svg?.setAttribute('viewBox', `${cam.x} ${cam.y} ${cam.w} ${cam.h}`);
  // An edge is never thinner than a pixel on the screen, in either area and inside a node, VIEW-008: `--pixel2d` is
  // the map's units one pixel spans, which the edges' width is held to at least, so a map seen whole keeps its edges;
  // zoomed in, they keep the width the map gives them. Every edge takes a click a pixel wider than it is drawn,
  // `--unit2d`.
  const wide = M.svg?.getBoundingClientRect().width;
  M.svg?.style.setProperty('--pixel2d', wide ? String(cam.w / wide) : '0');
  M.svg?.style.setProperty('--unit2d', wide ? String(cam.w / wide) : '0');
  hover2d(wide ? wide / cam.w : 0);
}
function near(a, b) {  // compared part by part, so a followed frame that asks allocates nothing
  if (!a || !b) return false;
  const tol = Math.max(a.w, b.w) * 1e-4;
  return Math.abs(a.x - b.x) <= tol && Math.abs(a.y - b.y) <= tol && Math.abs(a.w - b.w) <= tol
    && Math.abs(a.h - b.h) <= tol;
}
export function stopCam() { cancelAnimationFrame(M.frame); M.to = null; }
/* Every move of the 2D camera eases in and out and is never set at once, VIEW-041; with reduced motion it moves at
 * once, VIEW-016. A move to where the camera is already going goes on as it is. The middle of the view moves in a
 * straight line and its size by its log, so a zoom runs at one pace however far it goes, as the eye takes a zoom; a
 * move asked for while another runs leaves at the speed that one had, so the camera never jolts, and one from rest
 * eases in and out, `hermite`. `dive` speeds up all the way, the camera going into a node as its map fades out,
 * VIEW-016; `length` is its time in seconds. Its time starts at its first frame, so work the page does before that
 * frame is not skipped over in one step. */
const MOVE = {from: null, to: null, rate: null, start: null, length: 0.7, dive: false};
const CAM_PARTS = ['x', 'y', 'w', 'h'];
const camParts = cam => ({x: cam.x + cam.w / 2, y: cam.y + cam.h / 2, w: Math.log(cam.w), h: Math.log(cam.h)});
function camAt(now) {  // the camera of the move under way at `now`, how fast each part moves, and the share gone
  const s = MOVE.start === null ? 0 : Math.min(1, Math.max(0, (now - MOVE.start) / 1000 / MOVE.length));
  const at = {}, rate = {};
  for (const part of CAM_PARTS) {
    const from = MOVE.from[part], to = MOVE.to[part];
    if (MOVE.dive) [at[part], rate[part]] = [from + (to - from) * s * s * s, 3 * s * s * (to - from) / MOVE.length];
    else [at[part], rate[part]] = hermite(from, to, MOVE.rate[part], MOVE.length, s);
  }
  const w = Math.exp(at.w), height = Math.exp(at.h);
  return {cam: {x: at.x - w / 2, y: at.y - height / 2, w, h: height}, rate, s};
}
export function moveCam(target, {length = 0.7, dive = false} = {}) {
  if (!M.svg) return;
  const to = frame(target);
  if (!M.cam) return setCam(to);
  if (near(M.to || M.cam, to)) return;
  const under = M.to && MOVE.start !== null && !MOVE.dive ? camAt(performance.now()) : null;
  stopCam();
  if (reduced()) return setCam(to);
  M.to = to;
  Object.assign(MOVE, {from: camParts(M.cam), to: camParts(to), start: null, length, dive,
    rate: under && !dive ? under.rate : Object.fromEntries(CAM_PARTS.map(part => [part, 0]))});
  const step = now => {
    MOVE.start ??= now;
    const {cam, s} = camAt(now);
    setCam(cam);
    if (s < 1) M.frame = requestAnimationFrame(step); else M.to = null;
  };
  M.frame = requestAnimationFrame(step);
}
/* The 2D map's camera, VIEW-041: full fit, the whole map in the pane, `scaleFor`, which the page opens in and which
 * refits, eased, as the pane or the map changes size; free zoom, the wheel zooming about the pointer and a drag
 * panning, after which the view is held where the person left it, `MODE.free`; a followed agent's node framed with its
 * neighbours, `autoZoom2d`; and the limits where a view stands, `place2d`. */
const at2d = id => !id ? null : M.nodes.get(id) || (id.startsWith('p:') ? M.nodes.get(joinOf(id)?.provider) : null);
export const area2d = () => $('#viewport').getBoundingClientRect();
const mid2d = box => ({x: box.x + box.w / 2, y: box.y + box.h / 2});
export const MAC = /Mac|iPhone|iPad/.test(navigator.userAgentData?.platform || navigator.platform || '');
function smallestText(svg) {  // the smallest font size of the diagram's labels, in its own units
  let least = Infinity;
  for (const text of svg.querySelectorAll('text, tspan')) {
    const words = [...text.childNodes].some(node => node.nodeType === 3 && node.textContent.trim());
    if (words) least = Math.min(least, parseFloat(getComputedStyle(text).fontSize) || Infinity);
  }
  return isFinite(least) ? least : 13;
}
export function labelSize(svg) {  // read once for each drawing, while it is on the page
  if (!MODE.labels.has(svg) && svg.isConnected) MODE.labels.set(svg, smallestText(svg));
  return MODE.labels.get(svg) || 12;
}
/* The zoom full fit sets, in screen pixels to a unit of the map: the whole map in the pane, with a margin of MARGIN
 * pixels, less on a pane too small to spare it, on the sides it fits, and the room kept at its foot. */
export function scaleFor(area = area2d()) {
  const box = M.bounds, room = side => Math.min(MARGIN, side / 10);
  const across = (area.width - 2 * room(area.width)) / Math.max(1, box.w);
  const down = (area.height - Math.min(foot2d(), area.height / 3) - 2 * room(area.height)) / Math.max(1, box.h);
  return Math.min(across, down);
}
/* The room kept free at the foot of the 2D map's window, in screen pixels, so no node is fitted under what stands
 * there: the hover card at rest, as tall as it is with a line of words, so a card that grows while it shows never
 * moves the map, and any other overlay standing at the window's foot, measured as it is now; and a small gap. */
export const FOOT2D = {card: 0, gap: 8};
export function foot2d() {
  const root = $('#map2d');
  if (!root) return 0;
  const bottom = root.getBoundingClientRect().bottom, shows = VIEW.hoverInfo || 'name+summary';
  let most = shows === 'name' || shows === 'off' ? 0 : FOOT2D.card || restingCard(root);
  for (const one of root.children) {
    if (one.matches('#viewport, .crumbs, .readout, .hovercard') || one.hidden) continue;
    const style = getComputedStyle(one), box = one.getBoundingClientRect();
    if (style.position !== 'absolute' || !box.height || style.display === 'none' || bottom - box.bottom > 48) continue;
    most = Math.max(most, bottom - box.top);
  }
  return most ? most + FOOT2D.gap : 0;
}
/* The card's height at rest, its kind, its address and one line of words, measured once from a copy out of sight. */
export function restingCard(root) {
  const probe = h('div', {class: 'hovercard', style: {visibility: 'hidden', transition: 'none'}},
    h('div', {class: 'kind'}, 'element'), h('code', {class: 'address'}, 'a.b'), h('p', {class: 'text'}, 'A line.'));
  root.append(probe);
  const tall = probe.getBoundingClientRect().height, inset = parseFloat(getComputedStyle(probe).bottom) || 0;
  probe.remove();
  if (tall) FOOT2D.card = Math.ceil(tall + inset);
  return FOOT2D.card;
}
addEventListener('resize', () => { FOOT2D.card = 0; });  // its inset and text follow the window's size
/* The view at `scale` with its middle as near `center` as the limits let it be: along an axis where the map runs past
 * the pane, no more than MARGIN screen pixels beyond the map's edge show, and along one where it does not, the map is
 * centered; down the pane, in the part above the room kept at its foot, `foot2d`. */
/* The point `place2d` keeps in the middle of a view: its middle across, and down the middle of the part above the
 * room at its foot, so a view turned back into its center and placed again stands where it stood. */
export function focus2d(view, area = area2d()) {
  const foot = Math.min(foot2d(), area.height / 3) * view.w / Math.max(1, area.width);
  return {x: view.x + view.w / 2, y: view.y + (view.h - foot) / 2};
}
export function place2d(scale, center, area = area2d()) {
  const box = M.bounds, w = area.width / scale, height = area.height / scale, room = MARGIN / scale;
  const foot = Math.min(foot2d(), area.height / 3) / scale, usable = height - foot;
  const along = (at, start, size, view) => size <= view ? start + size / 2 - view / 2
    : Math.min(Math.max(at - view / 2, start - room), start + size + room - view);
  const down = box.h <= usable ? box.y + box.h / 2 - usable / 2
    : Math.min(Math.max(center.y - usable / 2, box.y - room), box.y + box.h + room + foot - height);
  return {x: along(center.x, box.x, box.w, w), y: down, w, h: height};
}
/* Each drawing keeps its own framing: a node's own graph and a memory network open in full fit; the map, left for
 * one, comes back held or fitted as it was left; and the map drawn again, as the data changes or reflows, keeps it. */
function drawing2d() {
  if (MODE.svg === M.svg) return;
  const base = Boolean(M.svg) && M.svg === M.base?.svg;
  if (MODE.base && !base && M.base) M.base.free = MODE.free;
  if (!base) MODE.free = false;
  else if (!MODE.base) MODE.free = Boolean(M.base.free);
  Object.assign(MODE, {svg: M.svg, base});
}
/* The view the person has taken by hand, the wheel or a drag, is held from now on; while an agent is followed, at the
 * zoom the hand chose. */
export function hold2d() { drawing2d(); MODE.free = true; }
/* The camera to full fit, or with the view held to the zoom it is at; with `center` in the middle as far as the limits
 * allow, or the middle of the view where it is going; eased, or with `now` put there at once, for a view that fades
 * in. */
export function aim2d(center = null, now = false) {
  const area = area2d(), here = M.to || M.cam;
  if (!M.svg || !M.bounds || !area.width || !area.height) return;
  drawing2d();
  const scale = MODE.free && here ? area.width / here.w : scaleFor(area);
  const view = place2d(scale, center || (here ? focus2d(here, area) : mid2d(M.bounds)), area);
  if (now || !M.cam) setCam(view); else moveCam(view);
}
/* A selection refits the map in full fit and leaves a view held by hand where it is, VIEW-041, as on the earlier
 * page, where only a followed agent's node was framed. Agents are not part of this page. One case is added: with the
 * view held by hand, a part selected outside it is brought to its middle at the zoom held, so a part chosen from the
 * search or the keys is always in view. */
export function autoZoom2d(id) {
  const area = area2d(), center = center2d(id), here = M.to || M.cam;
  if (!M.svg || !M.bounds || !area.width || !area.height) return;
  drawing2d();
  const outside = center && here && (center.x < here.x || center.x > here.x + here.w || center.y < here.y
    || center.y > here.y + here.h);
  aim2d(MODE.free && outside ? center : null);
}
/* The middle of a join's edge on the whole map, from the earlier page's figures/roam2d.js. */
function spot2d(base, key) {
  const path = base.edges.find(edge => edge.join.id === key.slice(2))?.path;
  if (!path?.getTotalLength) return null;
  const middle = path.getPointAtLength(path.getTotalLength() / 2);
  return {x: middle.x, y: middle.y, w: 0, h: 0};
}
/* Where a selection is centered: a node at its middle, and a join of the whole map at the middle of its edge, where a
 * 2D figure stands at it, `spot2d`. */
export function center2d(id) {
  const edge = id?.startsWith('p:') && M.base && M.svg === M.base.svg ? spot2d(M.base, id) : null;
  if (edge) return edge;
  const node = at2d(id);
  return node ? {x: node.x, y: node.y} : null;
}
/* Full fit, VIEW-041: the whole map in the pane, eased there, and kept so as the pane or the map changes size. */
export function fullFit2d() {
  drawing2d();
  MODE.free = false;
  MODE.page = null;  // read again, in case the page's text has changed since
  aim2d();
}
/* 0, and Home: full fit, the whole of each map in view, the 2D map's and the large 3D map's. */
export function resetZoom() {
  fullFit2d();
  note2d('Full fit');
}
