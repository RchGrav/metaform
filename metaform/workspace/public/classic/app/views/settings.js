/* The person's view the page follows, from the earlier page's views/settings.js: the flow mode, the map's depth and
 * direction, the edges shown, the hover information, and the 3D map's signs, lens, layout and node zoom. The earlier
 * page kept them on its server behind /api/view; the new server has no such route, so this page keeps them in this
 * browser, under the same keys. Whether the 3D map is shown at all, web_map3d, is this page's own. */
import '/classic/app/camera/fly3d.js';  // the part before runs first, so the parts run in the page's order
// The Space theme, web_theme: the 3D map in outer space, drawn by its own module through the hooks marked ULTRA.
import * as ULTRA from '/classic/ultra.js';
import {$} from '/classic/app/core/dom.js';
import {toast} from '/classic/app/core/controls.js';
import {readout} from '/classic/app/map3d/readout.js';
import {flowMode} from '/classic/app/flow/flow.js';
import {showEdges, showFlow, PHYS, applyPhysics, showSigns} from '/classic/app/views/bar.js';
import {showNodeZoom, showLens, lens3d, show3d} from '/classic/app/views/lens.js';
import {flows2d} from '/classic/app/map2d/flow2d.js';
import {fitDirection2d} from '/classic/app/map2d/fit.js';
import {DEPTH, setDepth} from '/classic/app/keys/walk.js';

export const VIEW = {read: null, reading: null, signs: 'facing', map3d: true};
// declared before the view is read, which shows it: the flow mode
export const FLOWSET = {name: null};
export const LENS = {name: 'natural', frame: 0};
/* The signs, web_signs: facing, the default, each name turned to the eye that sees it; or outward, each of the map's
 * names a sign standing in the scene out from the map's middle. The View menu switches them. */
/* The 3D map's field of view in degrees, top to bottom, `resize`: it opens at the lens's widest, and a shorter pane
 * narrows it no further than `least`, so near things stay large and far things small, a view with depth, and never a
 * long lens that flattens the map. Widened 2026-10-17 at Rich's request (from 30 to 55, opening at three.js's 50),
 * for scale and depth. */
export const FOV3D = {least: 45, most: 60};
export const LENSES = {natural: 60, wide: 80, fisheye: 120};  // web_lens: the widest the view opens
export const LENS_WORDS = {natural: 'Natural', wide: 'Wide', fisheye: 'Fisheye'};
/* The view kept in this browser, one JSON object of key and value. */
const STORE = 'classic.view';
function kept() {
  try { return JSON.parse(localStorage.getItem(STORE) || '{}') || {}; } catch { return {}; }  // storage can be blocked
}
export const viewValue = (key, otherwise = undefined) => kept()[key] ?? otherwise;
/* A view choice kept; null returns it to its default. Says whether it was kept. */
export function saveView(key, value) {
  const view = kept();
  if (value === null) delete view[key]; else view[key] = value;
  try { localStorage.setItem(STORE, JSON.stringify(view)); } catch {
    toast('That choice was not kept: this browser does not let the page store it.');
    return Promise.resolve(false);
  }
  return Promise.resolve(true);
}
/* The view read and applied to the page, and shown in the View menu and the header. */
export function readView() {
  VIEW.read = true;
  VIEW.reading = Promise.resolve();
  PEEK.direction = String(viewValue('web_map_direction', 'auto'));
  if ($('#directionat')) $('#directionat').value = PEEK.direction;
  VIEW.signs = String(viewValue('web_signs', 'facing'));
  showSigns();
  LENS.name = String(viewValue('web_lens', 'natural'));
  lens3d(LENS.name);
  showLens();
  ULTRA.setting(document.documentElement.dataset.theme === 'space' ? 'ultra' : 'clean');  // the theme decides the look
  const physics = String(viewValue('web_physics', 'organic'));
  if (physics !== PHYS.name) applyPhysics(physics);
  const flow = String(viewValue('web_flow_mode', 'selected'));
  flowMode(flow);
  showFlow(flow);
  // no depth kept: auto, the map collapsed when it is large, walk.js `AUTO_WHOLE`
  if (String(viewValue('web_map_depth', 'auto')) !== DEPTH.level) setDepth(String(viewValue('web_map_depth', 'auto')), false);
  showEdges(viewValue('web_flow_edges', true) !== false);
  VIEW.nodeZoom = viewValue('web_node_zoom', true) !== false;
  showNodeZoom();
  VIEW.hoverInfo = String(viewValue('web_hover_info', 'name+summary'));
  showInfo();
  show3d(viewValue('web_map3d', true) !== false, false);  // the 3D map is started here, unless it is turned off
  return VIEW.reading;
}
/* What the page keeps of the view as it last read it: the map's direction, web_map_direction, `fitPin2d`. */
export const PEEK = {direction: null};
/* The map's direction chosen in the header: Auto, left to right or top to bottom, kept as web_map_direction; the map
 * is drawn in it at once, `fitDirection2d`. */
export async function chooseDirection(direction) {
  if (!await saveView('web_map_direction', direction)) return;
  fitDirection2d(direction);
}
/* Which joins the dots flow along, web_flow_mode, the flow's own setting: off, the joins of the node under the
 * pointer, the selection's joins, or all of them. This is its choice in the View menu, and the key 2, which steps
 * through them all, said at the map's corner. */
export const FLOW_MODES = [['off', 'Off', 'No dots flow'],
  ['hover', 'Hover', 'Dots flow along the joins of the node under the pointer'],
  ['selected', 'Selection', "Dots flow along the selection's joins"],
  ['all', 'All', 'Dots flow along every join']];
export function flowNow() {
  return flowMode() || FLOWSET.name || 'selected';
}
export function chooseFlow(name) {
  FLOWSET.name = name;
  flowMode(name);
  flows2d();  // the map's edges that carry it follow the choice
  if ($('#flowat')) $('#flowat').value = name;
  saveView('web_flow_mode', name);
}
/* What the map says of what the pointer is on, web_hover_info: the name and the card, the name alone, the card alone,
 * or nothing; in the View menu, applied at once. */
export const HOVER_INFO = [
  ['name+summary', 'Both', 'The name where it cannot be read on the map, and the card of its details'],
  ['name', 'Name', 'Only the name, where it cannot be read on the map'],
  ['summary', 'Card', 'Only the card of its details'],
  ['off', 'Off', 'Nothing said of what the pointer is on']];
export function chooseInfo(name) {
  VIEW.hoverInfo = name;
  showInfo();
  readout('3d', null); readout('2d', null);
  saveView('web_hover_info', name);
}
function showInfo() {
  const now = VIEW.hoverInfo || 'name+summary';
  if ($('#infoat')) $('#infoat').value = now;
}
