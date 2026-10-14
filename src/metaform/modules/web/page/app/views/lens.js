/* What a selection does to the 3D camera, node zoom, the lens chosen in the page, resizing both maps, and the
 * legend. */
import '/page/app/views/bar.js';  // the part before runs first, so the parts run in the page's order
import {$, reduced, h, fill} from '/page/app/core/dom.js';
import {toast} from '/page/app/core/controls.js';
import {S} from '/page/app/core/reads.js';
import {colorVar} from '/page/app/header/layers.js';
import {noMetaform} from '/page/app/header/admin.js';
import {CONDITIONS} from '/page/app/figures/agents.js';
import {G, wake3d} from '/page/app/map3d/graph3d.js';
import {swap, V3, fitBalls, fit3d} from '/page/app/camera/flight.js';
import {small3d, fly3d, EASE, easeCurve} from '/page/app/camera/fly3d.js';
import {VIEW, NODEZOOM, LENS, FOV3D, LENSES, LENS_WORDS, saveView, peek} from '/page/app/views/settings.js';
import {following} from '/page/app/live/stream.js';
import {autoZoom2d} from '/page/app/map2d/camera.js';

/* What a selection does to the 3D camera: in the small area it is met; in the large one, as the mode says. */
/* Node zoom, web_node_zoom, on unless the person turns it off: every selection flies the camera to the node and frames
 * it with its neighbours, in either pane, whatever Whole, Zoom, Free or physics is in force; Whole and Free frame the
 * map while nothing is being flown to. Off, a selection never moves the camera. Found 2026-10-12: with Whole or Free
 * chosen, by 1, 0 or the bar, a selection in the large pane no longer flew to its node, which hid what the map is for.
 */
export function follow3d(id) {
  // the small area always meets the node at four fifths of its width, NAME.in, whatever node zoom says; the large one
  // seen through a followed agent's eyes, V3.eyes, stays with them
  if (!small3d() && (VIEW.nodeZoom === false || V3.eyes)) return true;
  if (!small3d() && V3.mode === 'free') return true;  // Free leaves the camera to the hand
  // Whole turns the map round the node so it faces the eye near the middle, labelled, at the whole map's distance,
  // so the map shows around it; Zoom, and the small pane, fly close
  if (!small3d() && V3.mode === 'whole') return fly3d(id, 'whole');
  return fly3d(id);
}
export function toggleNodeZoom(on = VIEW.nodeZoom === false) {
  VIEW.nodeZoom = on;
  showNodeZoom();
  if (on && S.selected && G) fly3d(S.selected);
  if (on && S.selected) autoZoom2d(S.selected);  // the 2D map's auto zoom is the same setting, VIEW-041
  peek('key');
  toast(on ? 'Auto zoom on: each node selected moves both maps to it.'
    : 'Auto zoom off: a selection leaves both maps where they are.');
  saveView('web_node_zoom', on);
}
export function showNodeZoom() {
  NODEZOOM.button?.setAttribute('aria-pressed', String(VIEW.nodeZoom !== false));
  const state = NODEZOOM.button?.querySelector('.state');
  if (state) state.textContent = VIEW.nodeZoom !== false ? 'On' : 'Off';
  if ($('#nodezoomat')) $('#nodezoomat').checked = VIEW.nodeZoom !== false;
}
// The 2D map opens in the large area, where its names are read, unless this browser has put the 3D map there: the
// chart is the map a person reads, and the 3D map keeps the whole in view beside it, VIEW-028.
function openSwapped() {
  let kept = null;
  try { kept = localStorage.getItem('metaform.swapped'); } catch (error) { /* storage can be blocked: the default */ }
  if (kept === null || kept === '1') swap(true, false);
}
openSwapped();
/* The lens chosen in the page, web_lens: L steps through natural, wide and fisheye, as do the large map's bar and the
 * View menu. The field of view eases to the new one on the arrival curve, `EASE`, rather than jumping; with reduced
 * motion it changes at once. */
export function chooseLens(name, keep = true) {
  if (!(name in LENSES)) return;
  LENS.name = name;
  showLens();
  const camera = G?.camera(), from = camera?.fov;
  lens3d(name);
  if (camera && from !== undefined && camera.fov !== from && !reduced()) easeFov(camera, from);
  if (keep) { peek('key'); saveView('web_lens', name); }
}
/* The field of view eased from `from` to the one the lens has set. */
function easeFov(camera, from) {
  const to = camera.fov, start = performance.now(), curve = easeCurve(EASE.arrive);
  cancelAnimationFrame(LENS.frame);
  camera.fov = from;
  const step = now => {
    const s = Math.min(1, (now - start) / EASE.medium);
    camera.fov = from + (to - from) * curve(s);
    camera.updateProjectionMatrix();
    wake3d();
    if (s < 1) LENS.frame = requestAnimationFrame(step);
  };
  LENS.frame = requestAnimationFrame(step);
}
export function showLens() {
  LENS.pick?.show(LENS.name in LENS_WORDS ? LENS.name : 'natural');
  if ($('#lensat')) $('#lensat').value = LENS.name;
}
export function lens3d(name) {  // the lens chosen, its widest field of view, applied at once
  FOV3D.most = LENSES[name] ?? LENSES.natural;
  if (!G || V3.lensFirst === undefined) return;
  V3.lens = V3.lensFirst;  // from the lens it opened with, so a wider choice opens as far as it allows
  G.width(G.width() + 1);  // `resize` acts only on a change of size
  resize();
}
export function resize() {
  if (!G) return;
  const box = $('#stage').getBoundingClientRect(), width = G.width(), height = G.height();
  if (!box.width || !box.height || (width === box.width && height === box.height)) return;
  const camera = G.camera();
  // Keep the lens's pixels per world unit independent of panel height. A shorter panel crops vertically without
  // changing a name's width or moving the camera. Width changes reframe the name at the selected share below.
  V3.lensFirst ??= Math.tan(camera.fov * Math.PI / 360) / box.height;  // the lens the 3D map opened with
  V3.lens ??= V3.lensFirst;
  G.width(box.width).height(box.height);
  // The library applies its size asynchronously; framing must use the new projection immediately.
  camera.aspect = box.width / box.height;
  // Within a natural lens only: a pane that grows a lot, such as the 3D map swapped from the small area into the large
  // one, would otherwise widen the view into a fisheye. Held at the edge, the lens starts again from there.
  const fov = Math.atan(V3.lens * box.height) * 360 / Math.PI;
  const held = Math.min(FOV3D.most, Math.max(FOV3D.least, fov));
  if (held !== fov) V3.lens = Math.tan(held * Math.PI / 360) / box.height;
  camera.fov = held;
  camera.updateProjectionMatrix();
  if (S.selected && V3.focus === S.selected) {
    // a new width, a lens held at its edge, or in the small area any new size, where the name is framed both ways,
    // reframes the name
    if (width !== box.width || held !== fov || small3d()) fly3d(S.selected);
  } else if ((V3.auto || (V3.mode === 'whole' && !small3d())) && fitBalls(G.graphData()).length) fit3d();
  wake3d();
}
addEventListener('resize', resize);
new ResizeObserver(resize).observe($('#stage'));

export function renderLegend() {
  const inView = new Set([...S.elements.values()].map(entry => entry.element.layer)
    .concat(S.joins.map(join => join.layer)));
  const rows = [['--intake', 'purpose · receiver to join', ''],
    ['--tree', 'namespace', ''], ...[...inView].map(name => [colorVar(name), name, ''])];
  const legend = $('#legend');
  fill(legend, ...rows.map(([color, text, kind]) =>
    h('span', {style: {'--c': `var(${color})`}}, h('i', {class: kind}), text)));
  const open = new Set([...S.elements.values()].flatMap(entry => entry.element.open_work || [])
    .concat(S.joins.flatMap(join => join.open_work || [])));
  for (const condition of CONDITIONS) if (open.has(condition)) legend.append(conditionRow(condition));
  const shown = G ? G.graphData().nodes.length : 0;
  $('#count').textContent = noMetaform() ? 'no metaform yet'
    : `${S.elements.size} elements · ${S.joins.length} joins · ${shown} nodes shown` + (S.loading ? ' · loading' : '')
    + (following() ? ' · intake being recorded' : '');
}
const LEGEND_MARKS = {missing: 'dot bloom', unbuilt: 'dot bloom', 'under-construction': 'dot bloom pulse',
  question: 'dot bloom pulse', message: 'dot bloom pulse'};
/* A condition the open records hold, as the legend says it: a part not built in the text's color, else in its own,
 * a message as a question; waiting on the person, or a part's condition. */
function conditionRow(condition) {
  const unbuilt = condition === 'missing' || condition === 'unbuilt' || condition === 'under-construction';
  const color = unbuilt ? 'var(--text)' : `var(--${condition === 'message' ? 'question' : condition})`;
  const waiting = condition === 'question' || condition === 'message';
  return h('span', {style: {'--c': color}}, h('i', {class: LEGEND_MARKS[condition] || 'dot'}),
    waiting ? `waiting: ${condition}` : `part: ${condition.replace('-', ' ')}`);
}
