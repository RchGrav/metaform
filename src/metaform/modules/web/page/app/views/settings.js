/* The view settings the page follows, the agents window, the flow's modes and what the maps say of what the pointer
 * is on. */
import '/page/app/camera/fly3d.js';  // the part before runs first, so the parts run in the page's order
// The Space theme, web_theme: the 3D map in outer space, drawn by its own module through the hooks marked ULTRA.
import * as ULTRA from '/page/ultra.js';
import {$, reduced} from '/page/app/core/dom.js';
import {toast} from '/page/app/core/controls.js';
import {S, read} from '/page/app/core/reads.js';
import {readout} from '/page/app/map3d/readout.js';
import {EASE} from '/page/app/camera/fly3d.js';
import {showEdges, showFlow, PHYS, applyPhysics, showUltra, showSigns} from '/page/app/views/bar.js';
import {showNodeZoom, showLens, lens3d} from '/page/app/views/lens.js';
import {flows2d} from '/page/app/map2d/flow2d.js';
import {posted} from '/page/app/intake/intake.js';
import {DEPTH, setDepth} from '/page/app/keys/walk.js';
import {drawHelpdesk} from '/page/app/dock/helpdesk.js';
import {setTheme} from '/page/app/map3d/draw3d.js';

/* The person's view the page follows, read once a project is shown from /api/view, view.py: the agents window,
 * web_agents_window; the 3D map's physics, web_physics; the 2D map's direction, web_map_direction; and the rest of
 * what the View menu and the keys change. A change made here is kept in the person's view, never as a setting, so
 * every project and every reload opens the same way (settings cleanup, 2026-10-15). The web module's settings the page
 * follows, web_embody, web_chat_details and web_theme, are read beside it. Reading writes nothing. Whether the page is
 * drawn from its workspace is web_panes, which the workspace reads itself. */
export const VIEW = {agents: 'auto', physics: 'organic', read: null, reading: null};
// the bar's Info choice, web_hover_info, `showInfo`, drawn as the view is read
export const INFOSET = {buttons: new Map()};
// declared before the view settings are read, which shows them: the flow modes and the node zoom switch
export const FLOWSET = {name: null};
export const NODEZOOM = {button: null};
export const LENS = {name: 'natural', button: null, frame: 0};
const LENS_NEXT = {natural: 'wide', wide: 'fisheye', fisheye: 'natural'};
/* The signs, web_signs: outward, the map's names standing out from its middle as signs in the scene, or facing, each
 * turned to the eye. The View menu switches them. */
export const SIGNS = {button: null, words: {outward: 'Outward', facing: 'Facing'}};
export const FOV3D = {least: 30, most: 55};  // the 3D map's field of view in degrees, top to bottom, `resize`
export const LENSES = {natural: 55, wide: 80, fisheye: 120};  // web_lens: the widest the view opens
export const LENS_WORDS = {natural: 'Natural', wide: 'Wide', fisheye: 'Fisheye'};
export function readView() {
  const project = S.project;
  if (!project) return Promise.resolve();
  if (VIEW.read === project) return VIEW.reading;
  VIEW.read = project;
  VIEW.reading = (async () => {
    let rows = [], view = {};
    try { [rows, view] = await Promise.all([read('settings').then(found => found.settings || []),
      read('view').then(found => found.view || {})]); } catch { return; }
    if (S.project === project) followView(rows, view);
  })();
  return VIEW.reading;
}
/* The view and the settings read, each applied to the page and shown in the View menu. */
function followView(rows, view) {
  const setting = (key, otherwise) => rows.find(row => row.key === key)?.value ?? otherwise;
  const value = (key, otherwise) => view[key] ?? otherwise;
  VIEW.agents = value('web_agents_window', 'auto');
  PEEK.direction = value('web_map_direction', 'auto');
  VIEW.signs = String(value('web_signs', 'outward'));
  VIEW.embody = String(setting('web_embody', 'offer'));
  const details = setting('web_chat_details', false) === true;  // the agent's work in the chat, `workShown`
  if (details !== Boolean(VIEW.chatDetails)) { VIEW.chatDetails = details; drawHelpdesk(); }
  showSigns();
  LENS.name = String(value('web_lens', 'natural'));
  lens3d(LENS.name);
  showLens();
  // the theme decides the look: web_theme once the person has chosen one, applied and never written here; until then
  // the theme this browser last showed
  const theme = rows.find(row => row.key === 'web_theme');
  if (theme && theme.state !== 'default' && theme.value !== document.documentElement.dataset.theme) {
    setTheme(String(theme.value), false);
  }
  ULTRA.setting(document.documentElement.dataset.theme === 'space' ? 'ultra' : 'clean');
  const physics = value('web_physics', 'organic');
  if (physics !== PHYS.name) applyPhysics(physics);
  showFlow(String(value('web_flow_mode', flowNow())));
  if (String(value('web_map_depth', 'all')) !== DEPTH.level) setDepth(String(value('web_map_depth', 'all')), false);
  showEdges(value('web_flow_edges', true) !== false);
  VIEW.nodeZoom = value('web_node_zoom', true) !== false;
  showNodeZoom();
  VIEW.hoverInfo = String(value('web_hover_info', 'name+summary'));
  showInfo();
  agentsWindow();
  peekParts();
}
/* A view choice kept in the person's view, /api/view; the saves of one key go one after another, so quick presses of
 * a key that steps it are kept in the order they were made. */
const SAVING = new Map();
export function saveView(key, value) {
  const save = (SAVING.get(key) || Promise.resolve()).then(async () => {
    const done = await posted('/api/view', {key, value});
    if (!done.ok) toast(done.body.error || 'That choice was not kept.');
    return done.ok;
  });
  SAVING.set(key, save);
  return save;
}

/* What the page keeps of the view as it last read it: the 2D map's direction, web_map_direction, `fitPin2d`, and the
 * Space theme's choice, `showUltra`. The maps have no bar: their keys, which ? lists, do what its buttons did. */
export const PEEK = {direction: null, ultra: null};
export function peekParts() {
  if (PEEK.ultra) showUltra();  // U pressed elsewhere: the choice names the look the map has now
}
/* A choice changed, by a key or a click: what shows it names it at once. */
export function peek() { peekParts(); }
$('#agentsat').onchange = event => chooseAgents(event.target.value);

/* The window of the agents at work, web_agents_window: auto slides it out as an agent starts work and keeps it while
 * any is at work, and slides it away completely a few seconds after the last one stops; open pins it out, saying when
 * none is at work, and hidden pins it away. A, and the View menu, change it. */
const AGENTS_WINDOW = {timer: 0, working: 0};
export function agentsWindow(count = AGENTS_WINDOW.working) {
  AGENTS_WINDOW.working = count;
  const box = $('#agents');
  box.querySelector('.none')?.toggleAttribute('hidden', count > 0);
  const want = VIEW.agents === 'open' || (VIEW.agents === 'auto' && count > 0);
  clearTimeout(AGENTS_WINDOW.timer);
  if (want) slideIn(box);
  else if (VIEW.agents === 'auto' && !box.hidden) AGENTS_WINDOW.timer = setTimeout(() => slideOut(box), 4000);
  else slideOut(box);
  if ($('#agentsat')) $('#agentsat').value = VIEW.agents;
}
function slideIn(box) {
  if (!box.hidden && !box.classList.contains('away')) return;
  box.classList.add('away');
  box.hidden = false;
  void box.offsetWidth;  // from where it stands away, so it slides in
  box.classList.remove('away');
}
function slideOut(box) {
  if (box.hidden || box.classList.contains('away')) return;
  box.classList.add('away');
  setTimeout(() => { if (box.classList.contains('away')) box.hidden = true; }, reduced() ? 0 : EASE.medium + 60);
}
function chooseAgents(choice) {
  VIEW.agents = choice;
  agentsWindow();
  toast({auto: 'The agents window shows while agents are at work.', open: 'The agents window stays out.',
    hidden: 'The agents window stays away.'}[choice]);
  saveView('web_agents_window', choice);
}

/* Which joins the dots flow along, web_flow_mode, the flow's own setting: off, the selection's joins, all of them, or
 * live, only what agents really do. The flow draws it, `window.metaform.flowMode`; this is its choice in the View menu,
 * every mode, and the key 2, which steps through them all, said at the 2D map's corner. */
export const FLOW_MODES = [['off', 'Off', 'No dots flow'],
  ['hover', 'Hover', 'Dots flow along the joins of the node under the pointer'],
  ['selected', 'Selection', "Dots flow along the selection's joins"],
  ['all', 'All', 'Dots flow along every join'], ['live', 'Live', 'Dots show only what agents really do']];
export function flowNow() {
  const asked = typeof window.metaform?.flowMode === 'function' ? window.metaform.flowMode() : null;
  return (typeof asked === 'string' && asked) || FLOWSET.name || 'all';
}
export function chooseFlow(name) {
  FLOWSET.name = name;
  if (typeof window.metaform?.flowMode === 'function') window.metaform.flowMode(name);
  flows2d();  // the 2D map's edges that carry it follow the choice
  if ($('#flowat')) $('#flowat').value = name;
  peek('key');
  saveView('web_flow_mode', name);
}
/* What the maps say of what the pointer is on, web_hover_info: the name and the card, the name alone, the card alone,
 * or nothing; in the bar as Info, the View menu and the key I, which steps through them, applied at once. */
export const HOVER_INFO = [
  ['name+summary', 'Both', 'The name where it cannot be read on the map, and the card of its details'],
  ['name', 'Name', 'Only the name, where it cannot be read on the map'],
  ['summary', 'Card', 'Only the card of its details'],
  ['off', 'Off', 'Nothing said of what the pointer is on']];
export function chooseInfo(name) {
  VIEW.hoverInfo = name;
  showInfo();
  readout('3d', null); readout('2d', null);
  peek('key');
  saveView('web_hover_info', name);
}
function showInfo() {
  const now = VIEW.hoverInfo || 'name+summary';
  INFOSET.pick?.show(now);
  if ($('#infoat')) $('#infoat').value = now;
}
