/* The developer level, the workspace's toolbar, panes and their places, window.metaform's workspace reads, and main. */
import '/page/app/onboard/hints.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
// The toolbar, the panes and their places, and the views the page draws only as panes.
import {createWorkspace} from '/page/workspace.js';
import {createViews} from '/page/views.js';
import {$, h, fill} from '/page/app/core/dom.js';
import {expandCut} from '/page/app/core/expand.js';
import {OVERLAY, overlay, overlayHolds, restack, place} from '/page/app/core/overlays.js';
import {toast, undoable, confirmAct, segmented, progressBar, copyField, choice} from '/page/app/core/controls.js';
import {FRAMED, S, reach, read, viewLayers} from '/page/app/core/reads.js';
import {readFailed, pageFailed} from '/page/app/core/errors.js';
import {sideAt} from '/page/app/header/layers.js';
import {ROAM} from '/page/app/figures/agents.js';
import {BUBBLE} from '/page/app/figures/cut.js';
import {NOTICES} from '/page/app/core/banner.js';
import {ROAM2D} from '/page/app/figures/roam2d.js';
import {VIEW_SETTINGS, shapes3d} from '/page/app/map3d/light.js';
import {G, start3D, FRAMES} from '/page/app/map3d/graph3d.js';
import {readoutBox} from '/page/app/map3d/readout.js';
import {tags} from '/page/app/map3d/labels.js';
import {swap} from '/page/app/camera/flight.js';
import {readView} from '/page/app/views/settings.js';
import {M, build2D} from '/page/app/map2d/build.js';
import {fitDirection2d} from '/page/app/map2d/fit.js';
import {openSettings, showSettings} from '/page/app/settings/screen.js';
import {openHelp} from '/page/app/keys/keys.js';
import {select, renderMerges} from '/page/app/selection/select.js';
import {DOCK, STANDBY, dockState} from '/page/app/dock/embody.js';
import {openHelpdesk} from '/page/app/dock/threads.js';
import {drawHelpdesk} from '/page/app/dock/helpdesk.js';
import {DOCK_PLACE, placeDock, dockLayout} from '/page/app/dock/place.js';
import {nodeOf} from '/page/app/board/messages.js';
import {renderBoard} from '/page/app/board/board.js';
import {show, wrote, movable} from '/page/app/board/history.js';
import {D, renderAgents, agentAt} from '/page/app/agents/dispatch.js';
import {giveWork} from '/page/app/task/task.js';
import {addElement} from '/page/app/task/notes.js';
import {briefAddress, elementAt, briefTo, renderBrief} from '/page/app/panel/brief.js';
import {openAgentView, readAgentView, renderProv} from '/page/app/panel/agentview.js';
import {P, renderPrompt, showTab, TAB_PAGES, nodeTabs, classicTabs} from '/page/app/panel/prompts.js';
import {openSearch} from '/page/app/search/search.js';
import {HARNESS, agentName} from '/page/app/agents/pickers.js';
import {isIntake, workPart} from '/page/app/session/tools.js';
import {INTAKE, openIntakeChat, openIntake} from '/page/app/intake/intake.js';
import {BUILD} from '/page/app/build/build.js';
import {listen, agentsIdle, heardCount} from '/page/app/live/ops.js';
import {loadProject, fillProjects} from '/page/app/loading/load.js';
import {openMapFolder} from '/page/app/header/admin.js';

/* ---------- the developer level: browser-console detail and traces, only with metaform web start --web-debug
 * ---------- Off, the default, logs nothing and keeps no trace. info logs each read and write of the page and keeps
 * them for the Traces pane; verbose adds the events heard and each pane drawn; trace adds every raw response. The level
 * comes with the workspace's read, from the web_debug setting or the last start's --web-debug. */
const DEBUG = {level: 'off', rows: [], most: 400};
const DEBUG_LEVELS = ['off', 'info', 'verbose', 'trace'];
export const debugAt = level => DEBUG_LEVELS.indexOf(DEBUG.level) >= DEBUG_LEVELS.indexOf(level)
  && DEBUG.level !== 'off';
export function dlog(level, ...said) { if (debugAt(level)) console.info(`[metaform ${level}]`, ...said); }
export function traced(row) {
  if (DEBUG.level === 'off') return;
  DEBUG.rows.push({at: Date.now(), ...row});
  if (DEBUG.rows.length > DEBUG.most) DEBUG.rows.splice(0, DEBUG.rows.length - DEBUG.most);
}
/* Every read and write of the page traced, with its time and, at trace, its raw answer; off, fetch is the browser's. */
function traceFetch() {
  const own = window.fetch.bind(window);
  window.fetch = async (input, options = {}) => {
    if (DEBUG.level === 'off') return own(input, options);
    const what = typeof input === 'string' ? input : input.url, method = (options.method || 'GET').toUpperCase();
    const began = performance.now();
    const response = await own(input, options);
    const ms = Math.round(performance.now() - began);
    let raw = null;
    if (debugAt('trace')) { try { raw = (await response.clone().text()).slice(0, 20000); } catch { raw = null; } }
    traced({kind: method, what, status: response.status, ms, raw});
    dlog('info', method, what, response.status, `${ms} ms`);
    return response;
  };
}
traceFetch();

/* ---------- the workspace: the toolbar, the panes and their places, web/README.md "Toolbar and panes" ----------
 * Drawn from /api/workspace by workspace.js, which this part lends the page's own views and commands. In an AI tool's
 * frame, or with no workspace read, the page stays as written. */
export const TAB_VIEWS = {object: 'object', brief: 'brief', prov: 'provenance', prompt: 'prompt'};
export const PANE_VIEWS = createViews({h, fill, read, wrote, toast, confirmAct, project: () => S.project,
  debug: () => DEBUG.level, trace: () => DEBUG.rows, getJson: workspaceJson,
  openMessages: record => { const id = nodeOf(record); select(id, true); show(id, 'unread'); }});
for (const view of Object.values(PANE_VIEWS)) $('.app').append(view.el);
async function workspaceJson(path) {
  const response = await reach(path, {headers: {Accept: 'application/json'}});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw Object.assign(new Error(body.error || `${path} failed`), {status: response.status, body});
  return body;
}
/* A window of the page shown as a pane leaves the overlay stack while it is docked, so it neither covers the page nor
 * holds its keys, and is a window on the stack again when it floats or closes. */
function overlayDocked(box, on) {
  if (on) {
    const known = OVERLAY.known.get(box);
    if (known) { box.wsOverlay = known; OVERLAY.known.delete(box); }
    OVERLAY.stack = OVERLAY.stack.filter(entry => entry.box !== box);
    box.inert = false;
    restack();
  } else if (box.wsOverlay) {
    OVERLAY.known.set(box, box.wsOverlay);
    delete box.wsOverlay;
  }
}
/* The chat in a pane's body: it stays open there, its tab and its own place left aside; null puts it back in its dock.
 */
function chatPane(on) {
  const box = $('#helpdesk');
  overlayDocked(box, on);
  if (on) {
    $('#dock').dataset.place = 'pane';
    $('#dock').className = 'open';
    box.hidden = false;
    dockLayout();
    drawHelpdesk();
    return;
  }
  $('#dock').append(box);
  let kept = 'corner';
  try { kept = localStorage.getItem(DOCK_PLACE) || 'corner'; } catch { /* storage can be blocked */ }
  placeDock(kept, false);
  dockState('resting');
}
export const chatDocked = () => $('#dock').dataset.place === 'pane';
/* An agent's figure on the 2D map opens the exact session it walks for, as its figure in 3D and its row under Agent
 * deployed do; the click goes to the figure, not to the box under it. */
function openFigure2d(event) {
  const g = event.target.closest?.('g.agent2d');
  if (!g) return;
  const figure = [...ROAM2D.figures.values()].find(one => one.g === g);
  if (!figure) return;
  event.stopPropagation();
  event.preventDefault();
  const session = D.sessions.filter(one => one.work_id === figure.id && one.state === 'running').at(-1);
  agentAt(figure.id, session?.session_id || null);
}
$('#viewport').addEventListener('click', openFigure2d, true);
/* The chat docked at a side of the page is as wide as the person drags its inner edge, kept in this browser as a view
 * preference of the screen; a double-click puts it back. */
const DOCK_WIDTH = 'metaform.dockWidth';
/* The docked chat's width, kept in this browser; null puts back the default. */
function setDockWidth(pixels) {
  if (pixels === null) {
    document.documentElement.style.removeProperty('--dock-width');
    try { localStorage.removeItem(DOCK_WIDTH); } catch { /* blocked */ }
  } else {
    const width = Math.round(Math.max(320, Math.min(innerWidth - 360, pixels)));
    document.documentElement.style.setProperty('--dock-width', `${width}px`);
    try { localStorage.setItem(DOCK_WIDTH, String(width)); } catch { /* storage can be blocked; it is sized for now */ }
  }
  dispatchEvent(new Event('resize'));
}
/* The inner edge dragged: the chat is as wide as from the pointer to the side it is docked at. */
function dragDockEdge(event) {
  event.preventDefault();
  const right = $('#dock').dataset.place === 'right';
  const move = moved => setDockWidth(right ? innerWidth - moved.clientX : moved.clientX);
  const end = () => { removeEventListener('pointermove', move); removeEventListener('pointerup', end); };
  addEventListener('pointermove', move);
  addEventListener('pointerup', end);
}
const EDGE_STEPS = {ArrowLeft: 24, ArrowRight: -24};
function stepDockEdge(event) {
  const by = Object.hasOwn(EDGE_STEPS, event.key) ? EDGE_STEPS[event.key] : undefined;
  if (!by) return;
  event.preventDefault();
  const now = $('#helpdesk').getBoundingClientRect().width;
  setDockWidth(now + ($('#dock').dataset.place === 'right' ? by : -by));
}
function dockEdge() {
  const edge = h('div', {class: 'dockedge', role: 'separator', 'aria-orientation': 'vertical', tabindex: '0',
    'aria-label': 'The docked chat\'s width', title: 'Drag to resize the chat; double-click to reset'});
  $('#helpdesk').append(edge);
  edge.addEventListener('pointerdown', dragDockEdge);
  edge.addEventListener('dblclick', () => setDockWidth(null));
  edge.addEventListener('keydown', stepDockEdge);
  try { const kept = Number(localStorage.getItem(DOCK_WIDTH)); if (kept) setDockWidth(kept); }
  catch { /* the default width */ }
}
dockEdge();
const VIEWS = {
  object: {el: $('#p-object'), show: () => { if (S.selected) select(S.selected, false, true, false, true); }},
  brief: {el: $('#p-brief'), show: () => renderBrief()},
  provenance: {el: $('#p-prov'), show: () => renderProv()},
  prompt: {el: $('#p-prompt'), show: () => (P.editor ? setTimeout(() => P.editor.refresh(), 0) : renderPrompt())},
  settings: {el: $('#settings'), show: () => showSettings(), docked: on => overlayDocked($('#settings'), on)},
  'agent-view': {el: $('#agentview'), show: () => readAgentView(), docked: on => overlayDocked($('#agentview'), on)},
  board: {el: $('#board'), show: () => renderBoard(), docked: on => overlayDocked($('#board'), on)},
  dock: {el: $('#helpdesk'), show: () => drawHelpdesk(), docked: on => chatPane(on)},
  ...PANE_VIEWS,
};
const COMMANDS = {
  search: () => openSearch(),
  'export-markdown': () => $('#exportMarkdown').click(), 'export-xml': () => $('#exportXml').click(),
  'export-mermaid': () => $('#exportMermaid').click(), 'copy-mermaid': () => $('#copyMermaid').click(),
  build: () => $('#buildBtn').click(), shortcuts: () => openHelp(),
  layers: () => $('#layersBtn').click(), agents: () => $('#agentsMenuBtn').click(), intake: () => openIntake(),
  orphaned: () => $('#orphanBtn').click(),
  'add-task': address => { const element = elementAt(address); if (element) giveWork(element.id); },
  'add-element': address => addElement(elementAt(address)?.id || S.selected),
  'dispatch-node': address => dispatchNode(address),
};
/* Add Task at the node, with Start an agent now ticked. */
function dispatchNode(address) {
  const element = elementAt(address);
  if (!element) return;
  giveWork(element.id);
  $('#task .start-agent').checked = true;
}
const TAB_BUTTONS = {object: '#t-object', brief: '#t-brief', provenance: '#t-prov', prompt: '#t-prompt'};
/* The large map the layout asks for, the views swapped when it is the other; the two maps' places. */
function mapsFor(large) {
  const swapped = $('.app').classList.contains('swapped');
  if ((large === 'map2d') !== swapped) swap(large === 'map2d', false);
  return {large: $('main'), small: $('#small')};
}
function openAddress(uri) {
  const element = elementAt(uri.replace(/^metaform:\/\//, '').split('#')[0]);
  if (element) briefTo(element.id);
}
const WINDOWS = {board: () => $('#boardBtn').click(), settings: () => openSettings(),
  'agent-view': () => openAgentView()};
export const WS = createWorkspace({h, fill, expandCut, toast, confirmAct, overlay, movable, place, wrote, getJson: workspaceJson,
  project: () => S.project, selection: () => briefAddress(), layers: () => viewLayers(),
  view: page => (page === 'dev-prompts' || page === 'dev-trace') && DEBUG.level === 'off' ? null : VIEWS[page] || null,
  hasCommand: page => page in COMMANDS, command: (page, address) => COMMANDS[page]?.(address),
  tab: page => (Object.hasOwn(TAB_BUTTONS, page) ? $(TAB_BUTTONS[page]) : null) || null,
  openAddress,
  maps: mapsFor,
  classic: on => { $('.app').classList.toggle('ws', !on); if (on) $('#toolbar').hidden = true; },
  // the arrangement that is the page as written: its side column at that side with the node's tabs as laid out, its
  // tab open, its windows opened and closed as their own buttons do, and the large map this browser's choice
  classicFrame: ({side, panes, tabs, off}) => { sideAt(side === 'right'); classicTabs(panes, tabs, off); },
  tabOpen: page => $('#t-' + TAB_PAGES[page])?.getAttribute('aria-selected') === 'true',
  showTab: page => showTab(TAB_PAGES[page]),
  largeMap: () => ($('.app').classList.contains('swapped') ? 'map2d' : 'map3d'),
  openWindow: page => (Object.hasOwn(WINDOWS, page) ? WINDOWS[page] : undefined)?.(),
  overlayHolds, log: dlog});
/* The workspace read with the project, the page's developer level with it; without it, the node's tabs as the
 * declarations give them, `nodeTabs`. */
export async function loadWorkspace() {
  if (FRAMED) return nodeTabs();
  await readView();
  const before = WS.on;  // web_panes off, WS.load keeps the page as written and reads the view settings alone
  const on = await WS.load();
  applyView(WS.view());  // read with panes on or off, web_panes
  if (!on) return nodeTabs();
  if (DEBUG.level !== 'off' && !before) WS.render();  // the developer panes, offered now that the level is known
  dlog('info', 'workspace', WS.state()?.workspace, WS.layout());
}
/* The view settings the workspace read gives: the developer level, the shapes, the flow's pace and the 2D map's way. */
function applyView(view) {
  DEBUG.level = view.debug || 'off';
  if (G) G.renderer().debug.checkShaderErrors = DEBUG.level !== 'off';  // read only for a developer, F5
  const shapes = view.shapes !== false;
  if (shapes !== VIEW_SETTINGS.shapes) { VIEW_SETTINGS.shapes = shapes; shapes3d(); if (M.base) build2D(); }
  Object.assign(FRAMES, {idle: 1000 * Number(view.flow_seconds ?? 30), rest: view.idle_flow ? null : 0});
  fitDirection2d(view.map_direction);  // web_map_direction, the 2D map's way, `fitPin2d`
  BUBBLE.seconds = view.bubble_seconds ?? 'auto';  // web_bubble_seconds, for the mascot's bubble
  NOTICES.on = view.notices === true;  // web_notices, whether a notice raises a banner
}
/* web_bubble_seconds changed on this page, from the Agents menu: every bubble takes it at once. */
export function takeBubbleSeconds(seconds) {
  WS.view().bubble_seconds = seconds;
  BUBBLE.seconds = seconds;
}
// Where a node's sign is on the screen, its four corners projected as the scene draws them, for a check of its framing.
window.metaform.signRect = id => {
  const sign = tags.get(id)?.sprite;
  if (!G || !sign) return null;
  sign.updateMatrixWorld();
  const box = $('#stage').getBoundingClientRect(), camera = G.camera();
  let left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
  for (const [x, y] of [[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]]) {
    const at = new THREE.Vector3(x, y, 0).applyMatrix4(sign.matrixWorld).project(camera);
    const sx = box.left + (at.x + 1) / 2 * box.width, sy = box.top + (1 - at.y) / 2 * box.height;
    left = Math.min(left, sx); right = Math.max(right, sx); top = Math.min(top, sy); bottom = Math.max(bottom, sy);
  }
  return {left, top, right, bottom};
};
// What a browser check reads of the agents drawn: the agents read again, and where an agent's figure is on the screen.
function figureOnScreen(work) {
  const figure = ROAM.figures.get(work);
  if (!G || !figure?.mesh) return null;
  const box = $('#stage').getBoundingClientRect(), at = figure.mesh.position.clone().project(G.camera());
  return {x: box.left + (at.x + 1) / 2 * box.width, y: box.top + (1 - at.y) / 2 * box.height};
}
function readoutShown(which) {
  const box = readoutBox(which);
  return box && !box.hidden && box.classList.contains('on') ? box.textContent : null;
}
Object.assign(window.metaform, {renderAgents: () => renderAgents(), agentsIdle, heard: heardCount, figureOnScreen,
  readout: readoutShown});
// What a browser check reads of the workspace: whether it is on, the layout drawn, and where a pane stands.
window.metaform.workspace = {on: () => WS.on, layout: () => WS.layout(), toolbar: () => WS.toolbar(),
  where: id => WS.where(id), shown: id => WS.isShown(id), activate: id => WS.activate(id),
  move: (id, target) => WS.moveTo(id, target)};
/* What changes with a selection in the workspace: the brief and provenance shown read again, and the panes that
 * follow the selection. */
export function wsSelected() {
  if (WS.isShown('map.brief')) renderBrief();
  if (WS.isShown('map.provenance')) renderProv();
  WS.refresh(true);
}

export async function main() {
  let listed;
  try { listed = await read('projects'); }
  catch (error) {
    // The project list did not come: the error surface says why, and the page stays usable around it.
    readFailed(error);
    listen();
    revealed();
    return;
  }
  S.projects = listed.projects || [];
  if (!S.projects.length) {
    fillProjects();  // its Map a folder… registers one from here
    fill($('#p-object'), h('div', {class: 'emptypanel'},
      h('p', {class: 'empty'}, 'No project is registered. Map a folder of yours, or run metaform start in it.'),
      h('div', {class: 'acts'}, h('button', {class: 'btn primary', type: 'button', onclick: () => openMapFolder()},
        'Map a folder…'))));
    listen();  // still hears what modules publish: an intake started in a project registered later takes the page there
    revealed();
    return;
  }
  // The project shown first, VIEW-002: the one the address names; else the project of the folder `metaform web` ran
  // in; else the one this browser showed last; else the first.
  let remembered = null;
  try { remembered = sessionStorage.getItem('metaform.project'); } catch (error) { /* storage can be blocked */ }
  const registered = id => S.projects.some(item => item.id === id);
  S.project = [new URLSearchParams(location.hash.slice(1)).get('p'), remembered, listed.opened].find(registered)
    || S.projects[0].id;
  try { sessionStorage.setItem('metaform.project', S.project); } catch (error) { /* storage can be blocked */ }
  const selected = new URLSearchParams(location.hash.slice(1));
  if (selected.get('p') !== S.project) selected.delete('b');
  selected.set('p', S.project);
  window.history.replaceState(null, '', '#' + selected);
  fillProjects();
  start3D();
  // a project that cannot be read is said by the error surface; the page around it is shown and still listens
  try { await loadProject(); } catch (error) { pageFailed(error); }
  revealed();
  listen();
  renderMerges();  // VIEW-044
}
/* The page shown once it is laid out, two frames after the map is drawn, `booting` in theme.js. */
function revealed() {
  S.shown = true;  // the first project is drawn, or there is none; before it, the page has not loaded
  requestAnimationFrame(() => requestAnimationFrame(() => document.documentElement.classList.remove('booting')));
}
// What a browser check reads of the page's controls, the overlays open, bottom to top, and the controls themselves,
// for the views built on them.
// an agent's session opened in the chat dock or in its window, as its chat button and its entry in the key open it
function chatOf(work, session = null) {
  if (isIntake(work)) return openIntakeChat(work, session);
  const agent = agentName(D.sessions.find(one => one.session_id === session)?.agent);
  return openHelpdesk(work, `${agent} on ${workPart(work)}`, STANDBY, session);
}
// the dock's threads, each by its session with where it comes from, the one on view, and where the dock stands
const dockNow = () => ({threads: DOCK.chats.map(chat => ({work_id: chat.target, session: chat.session,
  source: chat.source, label: chat.label})), on: DOCK.chat?.session || null,
place: $('#dock').dataset.place || 'corner'});
Object.assign(window.metaform, {overlays: () => OVERLAY.stack.map(entry => entry.box.id || entry.box.className),
  harnesses: () => ({...HARNESS, pickers: undefined, reading: undefined}), build: () => BUILD.job,
  intake: () => ({...INTAKE}), chat: chatOf, agent: (work, session = null) => agentAt(work, session), dock: dockNow,
  ui: {overlay, confirmAct, undoable, toast, segmented, progressBar, copyField, choice}});
