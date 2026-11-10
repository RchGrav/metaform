/* The person's view the page follows, from the earlier page's views/settings.js: the flow mode, the map's depth and
 * direction, the edges shown and the hover information. The earlier page kept them on its server behind /api/view;
 * the new server has no such route, so this page keeps them in this browser, under the same keys. */
import '/classic/app/camera/flight.js';  // the part before runs first, so the parts run in the page's order
import {$} from '/classic/app/core/dom.js';
import {toast} from '/classic/app/core/controls.js';
import {readout} from '/classic/app/map2d/readout.js';
import {flowMode} from '/classic/app/flow/flow.js';
import {showEdges, showFlow} from '/classic/app/views/bar.js';
import {flows2d} from '/classic/app/map2d/flow2d.js';
import {fitDirection2d} from '/classic/app/map2d/fit.js';
import {DEPTH, setDepth} from '/classic/app/keys/walk.js';

export const VIEW = {read: null, reading: null};
// declared before the view is read, which shows it: the flow mode
export const FLOWSET = {name: null};
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
  const flow = String(viewValue('web_flow_mode', 'selected'));
  flowMode(flow);
  showFlow(flow);
  // no depth kept: auto, the map collapsed when it is large, walk.js `AUTO_WHOLE`
  if (String(viewValue('web_map_depth', 'auto')) !== DEPTH.level) setDepth(String(viewValue('web_map_depth', 'auto')), false);
  showEdges(viewValue('web_flow_edges', true) !== false);
  VIEW.hoverInfo = String(viewValue('web_hover_info', 'name+summary'));
  showInfo();
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
  readout('2d', null);
  saveView('web_hover_info', name);
}
function showInfo() {
  const now = VIEW.hoverInfo || 'name+summary';
  if ($('#infoat')) $('#infoat').value = now;
}
