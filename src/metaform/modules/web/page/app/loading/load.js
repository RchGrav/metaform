/* Loading: the layers' items, each node's progress, projects, metaforms and the graph page by page, and the base
 * chooser's Activate and Remove. */
import '/page/app/live/ops.js';  // the part before runs first, so the parts run in the page's order
import {releaseGlyph} from '/page/agents3d.js';
import {$, h, fill} from '/page/app/core/dom.js';
import {toast, confirmAct} from '/page/app/core/controls.js';
import {S, MEM, read, viewLayers} from '/page/app/core/reads.js';
import {renderChips} from '/page/app/header/layers.js';
import {foldHeader} from '/page/app/header/menus.js';
import {emptyPanel} from '/page/app/header/admin.js';
import {withProviders, joinOf, READY} from '/page/app/graph/data.js';
import {ROAM, figures} from '/page/app/figures/agents.js';
import {leaveFollow} from '/page/app/figures/eyes.js';
import {ROAM2D} from '/page/app/figures/roam2d.js';
import {G} from '/page/app/map3d/graph3d.js';
import {draw3D} from '/page/app/map3d/draw3d.js';
import {V3, MODE, fit3d} from '/page/app/camera/flight.js';
import {renderLegend} from '/page/app/views/lens.js';
import {M, build2D} from '/page/app/map2d/build.js';
import {entryOf} from '/page/app/map2d/fit.js';
import {IN, renderCrumbs} from '/page/app/map2d/inside.js';
import {memoryOf, memoryThing, dropMemories} from '/page/app/memory/graph.js';
import {renderOrphans} from '/page/app/memory/manage.js';
import {noneSelected} from '/page/app/map2d/wire.js';
import {select, MERGE, renderMerges} from '/page/app/selection/select.js';
import {DOCK, dockState} from '/page/app/dock/embody.js';
import {drawTabs} from '/page/app/dock/threads.js';
import {leaveApps} from '/page/app/session/apps.js';
import {renderMessages} from '/page/app/board/messages.js';
import {B} from '/page/app/board/refs.js';
import {drawBoard} from '/page/app/board/board.js';
import {wrote} from '/page/app/board/history.js';
import {D, readAutostart, renderAgents} from '/page/app/agents/dispatch.js';
import {renderProv} from '/page/app/panel/agentview.js';
import {readHarnesses, forgetHarnesses, PICKERS, drawDockTab} from '/page/app/agents/pickers.js';
import {INTAKE, drawIntake, drawEmpty} from '/page/app/intake/intake.js';
import {LIVE, following, loadLive} from '/page/app/live/stream.js';
import {listen} from '/page/app/live/ops.js';
import {loadWorkspace} from '/page/app/workspace/workspace.js';

/* Every item and property of the layers, read as the context sees them, so selection, masks and hidden layers apply
 * as in every read, VIEW-017. */
async function itemsOf(generation) {
  const found = new Map();
  for (const layer of S.layers.filter(item => item.ready && item.kind !== 'base')) {
    let after = null;
    do {
      const page = await read('layer-items',
        {layer: layer.name, in_context: 'true', limit: 500, ...(after ? {after} : {}), ...viewLayers()});
      if (generation !== S.loading) return found;
      for (const item of page.results) {
        const entry = itemEntry(item, layer);
        found.set(entry.key, entry);
      }
      after = page.next;
    } while (after);
  }
  return found;
}
function itemEntry(item, layer) {
  const property = !('target' in item);  // a property sits on an element, an item on a node
  const key = property ? 'r:' + item.id : 'i:' + item.id;
  return {kind: property ? 'property' : 'item', key, item, value: item.value, layer: layer.name, layerKind: layer.kind};
}

/* ---------- loading: projects, metaforms, layers, then the graph page by page ---------- */
/* The steps filed and planned of each node's open tickets, the most advanced first, VIEW-035: an element's by its
 * id, a join's on its purpose vertex. */
export async function progressOf() {
  const found = new Map(), project = S.project, metaform = S.base;
  let tickets = [];
  try { tickets = (await read('work', {limit: 0})).results || []; } catch (error) { return found; }
  if (S.project !== project || S.base !== metaform) return found;  // a late answer for a project the person left
  S.tickets = tickets;
  for (const ticket of tickets) {
    if (!ticket.taken || ticket.done) continue;
    const keys = ticket.node_kind === 'join' ? ['p:' + ticket.node_id] : [ticket.node_id];
    const done = {filed: ticket.steps_done || 0, planned: ticket.steps || 0};
    const share = one => one.planned ? one.filed / one.planned : one.filed;
    for (const key of keys) if (!found.has(key) || share(done) > share(found.get(key))) found.set(key, done);
  }
  return found;
}
/* A load counts as opening from its first read until the panel of what it selects has been read, so loaded() is not
 * true while the page still reads what it loads. */
async function opening(work) {
  S.opening++;
  try { return await work(); } finally { S.opening--; if (!S.opening) drawEmpty(); }
}
/* agents: whether the agents key is read with the map; a map change does not read it, since the agents are read again
 * on dispatch events, VIEW-018. */
export function loadGraph(agents = true) { return opening(() => readGraph(agents)); }
async function readGraph(agents) {
  if (following()) { LIVE.seen = ''; S.loading = 0; return loadLive(); }
  const generation = ++S.loading, project = S.project, metaform = S.base;
  // a read is dropped once another has begun or the person has chosen another project or metaform
  const stale = () => generation !== S.loading || S.project !== project || S.base !== metaform;
  S.elements = new Map(); S.joins = [];
  let whole = false;
  try {
    if (!await readPages(stale)) return;
    whole = true;
    if (!await readBeside(generation, stale)) return;
  } catch (error) {
    toast(error.message);
    // The last whole map read is kept: a read that fails, as every read does while the server restarts, puts it back,
    // and the failure is said. Another metaform's is never put back, since its load begins with none.
    if (!stale() && !whole && S.whole) Object.assign(S, S.whole);
  }
  if (stale()) return;
  S.loading = 0;
  draw3D();
  renderLegend();
  // read beside the 2D map; the load ends when they are
  const told = Promise.all([renderMessages(), agents && renderAgents()]);
  await build2D();
  await selectLoaded();
  await told;
  drawIntake();
  window.metaform.onLoaded?.();  // the map view in an AI tool then turns to the address its call named, MCP-037
  READY.done?.();  // `window.metaform.ready`, once, the first map drawn
}
/* The map, page by page, drawn as each comes; false once the read is stale. */
async function readPages(stale) {
  let after = null;
  do {
    const page = await read('graph', {limit: 500, ...(after ? {after} : {}), ...viewLayers()});
    if (stale()) return false;
    for (const entry of page.elements) S.elements.set(entry.element.id, entry);
    S.joins.push(...page.joins.map(withProviders));
    draw3D(); renderLegend();
    after = page.next;
  } while (after);
  return true;
}
/* With the whole map read: the sequence it is at, the layers' items, the memory, and the tickets' progress and
 * figures; false once the read is stale. */
async function readBeside(generation, stale) {
  S.whole = {elements: S.elements, joins: S.joins};
  S.seq = await read('sequence');  // the sequence the map drawn is at; the ops after it are applied, STORE-046
  if (stale()) return false;
  const items = await itemsOf(generation);
  if (stale()) return false;
  S.items = items;
  const memory = await memoryOf();
  if (stale()) return false;
  S.memory = memory;
  renderOrphans();
  S.progress = await progressOf();
  figures(S.tickets || []);
  return true;
}
/* The selection kept when it still stands, else the memory open or the map's entry; with none, the panel says why. */
async function selectLoaded() {
  const keep = S.selected && (S.elements.has(S.selected) || joinOf(S.selected)
    || MEM.network?.entities.includes(S.selected) || memoryThing(S.selected)) ? S.selected : null;
  const start = keep || MEM.key || (S.cleared ? null : entryOf());  // a selection let go of stays let go, VIEW-008
  if (!start) S.cleared && S.elements.size ? noneSelected() : fill($('#p-object'), emptyPanel());
  else {
    // the whole map fitted once it has spread, unless a selection has flown the camera to its node meanwhile
    if (!keep) setTimeout(() => { if (G && !V3.focus && S.selected === start) fit3d(800, 60); }, 2200);
    await select(start, false, false, false, true);
  }
}
async function loadMetaform() {
  S.view = null; S.selected = null; S.cleared = false; IN.length = 0; M.base = null; dropMemories(); renderCrumbs();
  S.elements = new Map(); S.joins = []; S.whole = null;
  MODE.free = false;  // another metaform opens in full fit: a view held on the last one means nothing here, VIEW-041
  S.layers = (await read('layers', {limit: 0})).results;
  renderChips();
  if ($('#p-prov').hidden === false) renderProv();
  await loadGraph();
}
export function loadProject(wanted = null) { return opening(() => readProject(wanted)); }
async function readProject(wanted) {
  const project = S.project;
  readHarnesses();
  loadWorkspace();
  await readAutostart();
  const metaforms = (await read('bases', {limit: 0})).results;
  if (S.project !== project) return;  // the metaforms of a project the person has left

  S.bases = metaforms;
  const active = metaforms.find(item => item.id === wanted) || metaforms.find(item => item.active) || metaforms[0];
  S.base = active ? active.id : null;
  const option = item => h('option', {value: item.id, selected: item === active},
    item.name + (item.active ? ' · active' : ''));
  fill($('#mf'), ...(metaforms.length ? metaforms.map(option) : [h('option', {}, 'none yet')]));
  $('#mf').disabled = !metaforms.length;
  baseButtons();
  foldHeader();  // the names chosen take their room
  await loadMetaform();
}
/* Activate and Remove beside the base chooser, STORE-041: the chooser only changes what the page shows; Activate makes
 * the chosen base the active one, and Remove takes it out of the project with a copy kept. Neither acts on the active
 * base, as the command refuses to. */
function baseButtons() {
  const chosen = S.bases.find(item => item.id === $('#mf').value);
  $('#activateBase').disabled = !chosen || chosen.active;
  $('#removeBase').disabled = !chosen || chosen.active;
  // with one base or none there is no other to activate or remove, so neither shows until a second base is added
  $('#activateBase').hidden = $('#removeBase').hidden = S.bases.length < 2;
}
async function activateBase() {
  const chosen = S.bases.find(item => item.id === $('#mf').value);
  if (!chosen) return;
  $('#activateBase').disabled = true;
  if (await wrote('/api/activate-base', {name: chosen.name})) toast(`${chosen.name} is the active base.`);
  else baseButtons();
}
$('#activateBase').onclick = activateBase;
/* Removing a base cannot be undone from the page, so it is asked first, saying what goes and what is kept. */
async function removeBase() {
  const chosen = S.bases.find(item => item.id === $('#mf').value);
  if (!chosen || !await confirmAct({title: `Remove base ${chosen.name}?`,
    text: `It is taken out of ${S.project}. The page cannot bring it back; a copy of its store is kept.`,
    lost: [`Base ${chosen.name}, from the bases of ${S.project} and from what agents and the page can read`],
    kept: ['A copy of its store, under backups/remove-base in the Metaform home',
      `The active base and every other base of ${S.project}`],
    verb: 'Remove base'})) return;
  $('#removeBase').disabled = true;
  const done = await wrote('/api/remove-base', {name: chosen.name, confirm: true});
  if (done) toast(`Removed ${chosen.name}; its store is kept at ${done.kept}.`);
  else baseButtons();
}
$('#removeBase').onclick = removeBase;
/* Another project chosen: the agents drawn are the project left's, so its agent window closes and its agents go,
 * VIEW-039, and its figures with them at once, having no map here to walk back on, VIEW-035; the new project's are
 * read with its map. */
export function toProject(id) {
  S.project = id;
  S.tickets = []; B.tickets = [];  // nothing of the project left behind shows on the next one
  if (!$('#board').hidden) drawBoard();
  location.hash = 'p=' + encodeURIComponent(id);
  try { localStorage.setItem('metaform.project', id); }
  catch (error) { /* storage can be blocked; the address keeps it */ }
  Object.assign(LIVE, {layer: null, base: null, seen: ''});
  Object.assign(D, {sessions: []});
  $('#autostartAgents').checked = false;
  $('#autostartAgents').disabled = true;
  leaveAgents();
  Object.assign(INTAKE, {work: null, session: null, agent: null, waiting: 0, started: null});
  D.asking = [];
  drawDockTab();
  for (const id of ['#intake', '#build', '#buildPrompt']) $(id).hidden = true;
  drawIntake();
  renderMerges();  // the merges this project has waiting for review, VIEW-044
}
/* The project left's agents go: its threads, its agents key, its figures, its merges and the agents chosen there. */
function leaveAgents() {
  // the threads are the sessions of the project left, so they go with it
  Object.assign(DOCK, {chats: [], chat: null, target: null, session: null, label: '', mine: null, calling: null});
  $('#helpdesk .call').textContent = 'Call';
  drawTabs();
  ROAM.focus = null;
  for (const list of document.querySelectorAll('#agents .list')) fill(list);
  $('#agents').hidden = true;
  for (const [work, figure] of ROAM.figures) { G?.scene().remove(figure.mesh); releaseGlyph(work); }
  ROAM.figures.clear(); ROAM.seen.clear();
  leaveFollow();  // and the agent the person followed there, with the view from its eyes
  D.subagents = [];  // and the subagents of the project left, which are drawn from it
  for (const [work, figure] of ROAM2D.figures) { figure.g.remove(); releaseGlyph(work); }  // and the 2D map's
  ROAM2D.figures.clear(); ROAM2D.seen.clear();
  Object.assign(MERGE, {rows: [], chat: null});
  $('#reviewNotice').hidden = $('#mergeAsk').hidden = true;
  dockState('resting');  // the chat put away to its tab, so it can be opened again here
  forgetHarnesses();  // the agents another project's folder sets are its own, VIEW-039
  for (const one of [PICKERS.start, PICKERS.task, PICKERS.element]) one?.set(null);  // and so is a choice made there
  leaveApps();  // and the MCP Apps views shown for it, torn down, in the thread and in panels
}
$('#proj').onchange = () => { toProject($('#proj').value); loadProject(); listen(); };
$('#mf').onchange = () => { S.base = $('#mf').value; baseButtons(); loadMetaform(); };
