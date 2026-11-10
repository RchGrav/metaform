/* The view's compact choices, from the earlier page's views/bar.js: the flow's steps and the edges shown. The 3D map's
 * layout, lens and signs, which that file also held, are not part of this page. */
import '/classic/app/views/settings.js';  // the part before runs first, so the parts run in the page's order
import {$} from '/classic/app/core/dom.js';
import {VIEW, FLOWSET, saveView, FLOW_MODES, flowNow, chooseFlow, chooseInfo,
  chooseDirection} from '/classic/app/views/settings.js';
import {note2d} from '/classic/app/map2d/hover.js';

if ($('#infoat')) $('#infoat').onchange = event => chooseInfo(event.target.value);
$('#flowat').onchange = event => chooseFlow(event.target.value);
$('#directionat').onchange = event => chooseDirection(event.target.value);
/* 2 steps the flow through every mode, off, hover, the selection and all, with the joins' lines drawn, then the same
 * again with the lines hidden, so only what flows shows, and round again; said at the map's corner. The edges' choice
 * is web_flow_edges. */
const FLOW_STEPS = [true, false].flatMap(edges => FLOW_MODES.map(([name]) => [name, edges]));
export function stepFlow() {
  const now = FLOW_STEPS.findIndex(([name, edges]) => name === flowNow() && edges === (VIEW.edges !== false));
  const [name, edges] = FLOW_STEPS[(now + 1) % FLOW_STEPS.length];
  chooseFlow(name);
  if (edges !== (VIEW.edges !== false)) { showEdges(edges); saveView('web_flow_edges', edges); }
  note2d(`Flow: ${FLOW_MODES.find(([one]) => one === name)[1]}${edges ? '' : ', edges hidden'}`);
}
/* The joins' lines drawn or hidden, web_flow_edges; hidden, the flow still runs where they were. Only a change does
 * anything. */
export function showEdges(on) {
  if (VIEW.edges === on) return;
  VIEW.edges = on;
  $('#map2d')?.classList.toggle('noedges', !on);
}
export function showFlow(name = flowNow()) {
  FLOWSET.name = name;
  if ($('#flowat')) $('#flowat').value = name;
}
