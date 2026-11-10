/* What a selection does to the 3D camera, node zoom, the lens chosen in the page, resizing both maps, the legend,
 * and the 3D map turned on or off. From the earlier page's views/lens.js. */
import '/classic/app/views/bar.js';  // the part before runs first, so the parts run in the page's order
import {$, reduced, h, fill} from '/classic/app/core/dom.js';
import {toast} from '/classic/app/core/controls.js';
import {S} from '/classic/app/core/reads.js';
import {G, wake3d, start3D, FRAMES} from '/classic/app/map3d/graph3d.js';
import {draw3D} from '/classic/app/map3d/draw3d.js';
import {swap, SWAPPED_KEY, V3, fitBalls, fit3d} from '/classic/app/camera/flight.js';
import {small3d, fly3d, EASE, easeCurve, workShot, shotSoon} from '/classic/app/camera/fly3d.js';
import {VIEW, LENS, FOV3D, LENSES, saveView} from '/classic/app/views/settings.js';
import {build2D} from '/classic/app/map2d/build.js';
import {select} from '/classic/app/selection/select.js';

/* What a selection does to the 3D camera: in the small area it is met; in the large one, as the mode says. */
/* Node zoom, web_node_zoom, on unless the person turns it off: every selection flies the camera to the node and frames
 * it with its neighbours, in either pane, whatever Whole, Zoom, Free or physics is in force; Whole and Free frame the
 * map while nothing is being flown to. Off, a selection never moves the camera. Found 2026-10-12: with Whole or Free
 * chosen, by 1, 0 or the bar, a selection in the large pane no longer flew to its node, which hid what the map is for.
 */
export function follow3d(id) {
  // the small area always meets the node at four fifths of its width, NAME.in, whatever node zoom says
  if (!small3d() && VIEW.nodeZoom === false) return true;
  if (!small3d() && V3.mode === 'free') return true;  // Free leaves the camera to the hand
  // Whole turns the map round the node so it faces the eye near the middle, labelled, at the whole map's distance,
  // so the map shows around it; Work, Zoom and the small pane fly close
  if (!small3d() && V3.mode === 'whole') return fly3d(id, 'whole');
  if (!small3d() && V3.mode === 'work') return workShot(id);
  return fly3d(id);
}
export function toggleNodeZoom(on = VIEW.nodeZoom === false) {
  VIEW.nodeZoom = on;
  showNodeZoom();
  if (on && S.selected && G) fly3d(S.selected);
  // on this page the setting moves the 3D map alone: the 2D map refits on a selection, map2d/camera.js `autoZoom2d`
  toast(on ? 'Node zoom on: each element selected moves the 3D map to it.'
    : 'Node zoom off: a selection leaves the 3D map where it is.');
  saveView('web_node_zoom', on);
}
export function showNodeZoom() {
  if ($('#nodezoomat')) $('#nodezoomat').checked = VIEW.nodeZoom !== false;
}
// The 2D map opens in the large area, where its names are read, unless this browser has put the 3D map there: the
// chart is the map a person reads, and the 3D map keeps the whole in view beside it, VIEW-028.
function openSwapped() {
  let kept = null;
  try { kept = localStorage.getItem(SWAPPED_KEY); } catch (error) { /* storage can be blocked: the default */ }
  if (kept === null || kept === '1') swap(true, false);
}
openSwapped();
/* The lens chosen in the page, web_lens: 7 steps through natural, wide and fisheye, as does the View menu. The field
 * of view eases to the new one on the arrival curve, `EASE`, rather than jumping; with reduced motion it changes at
 * once. */
export function chooseLens(name, keep = true) {
  if (!(name in LENSES)) return;
  LENS.name = name;
  showLens();
  const camera = G?.camera(), from = camera?.fov;
  lens3d(name);
  if (camera && from !== undefined && camera.fov !== from && !reduced()) easeFov(camera, from);
  if (keep) saveView('web_lens', name);
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
  // the lens the 3D map opened with: the chosen lens's widest at the pane it opened in, `FOV3D`
  V3.lensFirst ??= Math.tan(FOV3D.most * Math.PI / 360) / box.height;
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
  else if (V3.mode === 'work' && !small3d() && width !== box.width) shotSoon();  // a new width, the shot taken again
  wake3d();
}
addEventListener('resize', resize);
new ResizeObserver(resize).observe($('#stage'));

/* The legend and the count at the foot of the 3D map while it has the large area: what a line is, a part not built
 * where the map holds one, and how much of the map is drawn. The earlier legend named each layer in view and each
 * condition of the open work; this map draws one layer and knows one condition, a part not built. */
export function renderLegend() {
  const links = G ? G.graphData().links : [];
  // the line from an element to the element that holds it by address is drawn only where no relies-on line joins them
  const rows = [['--intake', 'relies on', '']];
  if (links.some(link => link.k === 'tree')) rows.push(['--tree', 'held by', '']);
  const legend = $('#legend');
  fill(legend, ...rows.map(([color, text, kind]) =>
    h('span', {style: {'--c': `var(${color})`}}, h('i', {class: kind}), text)));
  const unbuilt = [...S.elements.values()].some(entry => (entry.element.open_work || []).includes('unbuilt'));
  if (unbuilt) legend.append(h('span', {style: {'--c': 'var(--text)'}}, h('i', {class: 'dot bloom'}), 'not built'));
  const shown = G ? G.graphData().nodes.length : 0;
  $('#count').textContent = !S.elements.size ? 'no map yet'
    : `${S.elements.size} elements · ${S.joins.length} lines · ${shown} elements shown`
      + (S.loading ? ' · loading' : '');
}
/* The 3D map turned on or off, the View menu's 3D map switch, kept as web_map3d with the other view settings; added
 * for this page. Off, the side column holds the tabs alone and the 2D map keeps the large area; the 3D map draws no
 * frame, and one never turned on is never started. On again, it is started if it was not, drawn from the map on the
 * page, and takes the small area. */
export async function show3d(on, keep = true) {
  VIEW.map3d = on;
  if ($('#map3dat')) $('#map3dat').checked = on;
  $('#swapBtn')?.toggleAttribute('disabled', !on);
  if (keep) saveView('web_map3d', on);
  const app = $('.app'), was = !app.classList.contains('no3d');
  if (on === was && (G || !on)) return;
  if (!on) {
    FRAMES.held = true;  // no frame is drawn while it is off, `wake3d`
    app.classList.add('no3d');
    if (!app.classList.contains('swapped')) await swap(true, false);  // the 2D map takes the large area
    return;
  }
  app.classList.remove('no3d');
  FRAMES.held = false;
  if (!G) start3D();
  if (G && S.elements.size) { draw3D(); renderLegend(); }
  resize();
  wake3d();
  // as a map loaded: fitted once it has spread, which in the small area meets the selection, `fit3d`
  const selected = S.selected;
  setTimeout(() => { if (G && !V3.focus && S.selected === selected) fit3d(800, 60); }, 2200);
  if (S.elements.size && !S.loading) {  // the 2D map is drawn for the area it has now
    await build2D(false);
    if (S.selected) select(S.selected, false, true);
  }
}
