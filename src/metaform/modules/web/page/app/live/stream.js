/* Live: what modules publish pushed to the page, VIEW-018, the intake followed as it is recorded, and changes
 * applied as they come. */
import '/page/app/build/build.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {toast} from '/page/app/core/controls.js';
import {S, read} from '/page/app/core/reads.js';
import {renderChips} from '/page/app/header/layers.js';
import {withProviders, joinOf} from '/page/app/graph/data.js';
import {attend} from '/page/app/figures/attention.js';
import {G, start3D} from '/page/app/map3d/graph3d.js';
import {draw3D} from '/page/app/map3d/draw3d.js';
import {renderLegend} from '/page/app/views/lens.js';
import {build2D} from '/page/app/map2d/build.js';
import {entryOf} from '/page/app/map2d/fit.js';
import {noneSelected} from '/page/app/map2d/wire.js';
import {select} from '/page/app/selection/select.js';
import {renderBrief} from '/page/app/panel/brief.js';
import {getJson} from '/page/app/panel/prompts.js';
import {drawIntake, offerNext} from '/page/app/intake/intake.js';
import {appliedOps, settled, briefTouched, ticketsOnly, opsOnly, ticketsChanged, boardFromTickets, linesOnly,
  agentsChanged, listen} from '/page/app/live/ops.js';
import {loadGraph, loadProject, toProject} from '/page/app/loading/load.js';
import {PANE_VIEWS, WS} from '/page/app/workspace/workspace.js';

/* ---------- live: the server pushes what modules publish, and the page redraws; nothing polls, VIEW-018 ----------
 * An intake being recorded is drawn as each object arrives, BASE-039; any other write to the metaform shown is read
 * again. Events that come while the page reads are drawn once, when it is done. */
export const LIVE = {layer: null, base: null, seen: '', busy: false, again: false, whole: false, named: null, done: 0,
  drawn: -Infinity, brief: false};
export const following = () => LIVE.layer !== null && S.base === LIVE.base;
export async function loadLive() {
  const page = await read('layer-graph', {layer: LIVE.layer});
  const text = JSON.stringify(page);
  if (text === LIVE.seen || !following()) return;
  LIVE.seen = text;
  S.elements = new Map(page.elements.map(entry => [entry.element.id, entry]));
  S.joins = page.joins.map(withProviders);
  S.items = new Map();
  draw3D(); renderLegend();
  drawIntake();  // the bar over the map counts the parts recorded so far
  await build2D();
  // the intake may have ended while the map was drawn: `follow` then loads the project, and a selection made here
  // would read its node from a metaform that may be cleared
  if (!following()) return;
  const keep = S.selected && (S.elements.has(S.selected) || joinOf(S.selected)) ? S.selected : null;
  const start = keep || (S.cleared ? null : entryOf());  // a selection let go of stays let go, VIEW-008
  if (start) select(start, false, false, false, true);
  else if (S.cleared && S.elements.size) noneSelected();
  else fill($('#p-object'), h('p', {class: 'empty'}, 'Nothing to show in these layers yet.'));
}
/* Follow the intake being recorded, found = {layer, base_id}, or return to the map when it is no longer being
 * recorded, saying what happened: it finished when its metaform still stands, or it stopped because the project was
 * cleared, the one thing that takes a metaform away, VIEW-019. */
async function follow(found) {
  if (found) ELSEWHERE.followed.add(`${S.project}/${found.base_id}/${found.layer}`);
  if (found && found.layer !== LIVE.layer) {
    Object.assign(LIVE, {layer: found.layer, base: found.base_id, seen: ''});
    if (S.base !== found.base_id) await loadProject(found.base_id);
    else { S.layers = (await read('layers', {limit: 0})).results; renderChips(); }
    drawIntake();
    toast(`An intake is being recorded in ${found.layer}; the map follows it as each object is recorded.`);
  } else if (!found && LIVE.layer) {
    const {base} = LIVE;
    const stands = (await read('bases', {limit: 0})).results.some(item => item.id === base);
    Object.assign(LIVE, {layer: null, base: null, seen: ''});
    renderLegend();
    drawIntake();
    toast(stands ? `The intake finished.` : `The intake stopped: ${S.project} was cleared.`);
    if (stands) attend(`intake:${base}`, 'The intake finished', null, null);  // the mascot says so too, `ATTN`
    if (stands) offerNext();
    await loadProject();
    return;
  }
  if (following()) await loadLive();
}
/* On connecting, and on the browser's own reconnect, what is being recorded now is read once. */
export async function recordingNow() {
  const found = (await read('intake-recording')).results[0] || null;
  await follow(found ? {layer: found.layer.name, base_id: found.base_id} : null);
}
/* One push: the chassis fired map.changed for a metaform of this project, or for its metaforms themselves, VIEW-018.
 * The page reads what is being recorded, then follows it, returns to the map when it has finished, shows the active
 * metaform when the project's metaforms changed, or reads the layers and the map again, keeping the view and the
 * selection. A change to tickets or messages alone reads only those, below. */
/* An intake happening in another project takes the page there, as one started in this project takes the map to it:
 * the person watches an intake where it is recorded. Only a change written into the intake being recorded does it,
 * once for that intake, so a person who goes back is left there; nothing else in another project ever switches the
 * page, and a change of tickets or agents elsewhere is not even looked at. */
const ELSEWHERE = {followed: new Set(), busy: false};
async function intakeElsewhere(payload) {
  const named = payload.tables;
  if (ELSEWHERE.busy || named === 'dispatch' || ticketsOnly(payload)) return;
  ELSEWHERE.busy = true;
  try {
    const found = (await getJson(`/api/intake-recording?project=${encodeURIComponent(payload.project)}`)).results?.[0];
    // only a change written into the intake being recorded: an intake happening now, never an old one left unfinished
    if (!found || payload.base_id !== found.base_id) return;
    const key = `${payload.project}/${found.base_id}/${found.layer.name}`;
    if (ELSEWHERE.followed.has(key) || payload.project === S.project) return;
    ELSEWHERE.followed.add(key);
    S.projects = (await getJson('/api/projects')).projects || [];  // a first run registers its folder just before
    if (!G) start3D();  // a page opened with no project has not drawn a 3D map yet
    toProject(payload.project);
    fill($('#proj'),
      ...S.projects.map(item => h('option', {value: item.id, selected: item.id === S.project}, item.id)));
    await loadProject();
    listen();
    toast(`An intake started in ${payload.project}; the page follows it there.`);
  } catch (error) { /* a project that cannot be read now is not followed */ }
  finally { ELSEWHERE.busy = false; }
}
/* Whether a change named tables, every one of them passing the test. */
const allTables = (named, test) => Array.isArray(named) && named.length && named.every(table => test(String(table)));
export async function changed(event) {
  if (event.topic !== 'map.changed') return;
  if (event.payload?.project && event.payload.project !== S.project) return intakeElsewhere(event.payload);
  if (event.payload?.project !== S.project) return;
  if (WS.on) {  // the workspace's panes that read the map, its messages and its workflow runs, read again
    WS.refresh();
    for (const page of ['messages', 'runs']) if (WS.isShown(WS.paneOfPage(page)?.id)) PANE_VIEWS[page].show();
  } else if (WS.active) WS.refresh();
  const named = event.payload.tables;
  // a setting changed, here or elsewhere: the settings screen reads again if it is open, F13
  if (Array.isArray(named) && named.some(table => /(^|\.)settings$/.test(String(table)))) {
    document.dispatchEvent(new CustomEvent('metaform:settings'));
  }
  if (briefTouched(named)) LIVE.brief = true;
  if (allTables(named, table => table.startsWith('jev.'))) {
    if (!LIVE.busy) { if (!$('#p-brief').hidden) renderBrief(); LIVE.brief = false; }
    return;  // a Jev decision kept at a node is an item there: its brief changes, the map does not
  }
  const agents = named === 'dispatch'
    || Array.isArray(named) && named.some(table => String(table).startsWith('dispatch.'));
  if (agents) agentsChanged(!linesOnly(event.payload));
  // an agent's own tables, its thread, sessions and settings, change no map
  if (named === 'dispatch' || allTables(named, table => table.startsWith('dispatch.'))) return;
  // nor do the settings, the page's own view choices among them, each read where it is used: a key that steps a view
  // choice saves it, and a map read again for every save faded the edges out and in as the keys were pressed
  if (allTables(named, table => /(^|\.)settings$/.test(table))) return;
  const tickets = ticketsOnly(event.payload);
  if (tickets && event.payload.base_id && event.payload.base_id !== S.base) return;  // another metaform's
  if (!tickets) {
    LIVE.whole = true;
    LIVE.named = LIVE.named && opsOnly(LIVE.named) ? [...LIVE.named, ...(named || [])] : named || null;
  }
  if (LIVE.busy) { LIVE.again = true; return; }
  LIVE.busy = true;
  try {
    do await readAgain(); while (LIVE.again);
  } catch (error) { toast(error.message); } finally {
    LIVE.busy = false; LIVE.done++;
    if (LIVE.brief && !$('#p-brief').hidden) renderBrief();  // what is held at the node, and its numbers, changed
    LIVE.brief = false;
  }
}
/* One read for the changes heard: the tickets alone, the intake being recorded, the project's metaforms when they
 * changed, the ops since the drawn sequence, or else the layers and the map again. */
async function readAgain() {
  await settled();
  LIVE.again = false;
  if (!LIVE.whole && S.whole && !LIVE.layer) { await ticketsChanged(); return; }
  LIVE.whole = false;
  const named = LIVE.named; LIVE.named = null;
  LIVE.drawn = performance.now();  // a whole reload: the next waits SPACING, a ticket change does not
  const found = (await read('intake-recording')).results[0] || null;
  if (found || LIVE.layer) { await follow(found ? {layer: found.layer.name, base_id: found.base_id} : null); return; }
  const metaforms = (await read('bases', {limit: 0})).results;
  const same = metaforms.length === S.bases.length && metaforms.every(item =>
    S.bases.some(known => known.id === item.id && known.active === item.active));
  // the project's metaforms changed: show the active one, as on opening; else the ops since the drawn sequence,
  // applied, or the layers and the map read again
  if (!same) await loadProject();
  else if (opsOnly(named) && await appliedOps()) { await ticketsChanged(); return; }
  else {
    S.layers = (await read('layers', {limit: 0})).results;
    renderChips();
    await loadGraph(false);
  }
  boardFromTickets();  // the work the map's read took, not read again
}
