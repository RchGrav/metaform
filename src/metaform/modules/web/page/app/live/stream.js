/* Live: what modules publish pushed to the page, VIEW-018, the intake followed as it is recorded, and changes
 * applied as they come. */
import '/page/app/build/build.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {toast} from '/page/app/core/controls.js';
import {S, read} from '/page/app/core/reads.js';
import {renderChips} from '/page/app/header/layers.js';
import {withProviders, joinOf} from '/page/app/graph/data.js';
import {attend} from '/page/app/figures/attention.js';
import {draw3D} from '/page/app/map3d/draw3d.js';
import {renderLegend} from '/page/app/views/lens.js';
import {build2D} from '/page/app/map2d/build.js';
import {entryOf} from '/page/app/map2d/fit.js';
import {noneSelected} from '/page/app/map2d/wire.js';
import {select} from '/page/app/selection/select.js';
import {renderBrief} from '/page/app/panel/brief.js';
import {getJson} from '/page/app/panel/prompts.js';
import {drawIntake, drawLeft, offerNext, intakeRunning} from '/page/app/intake/intake.js';
import {appliedOps, settled, briefTouched, ticketsOnly, opsOnly, ticketsChanged, boardFromTickets, sessionsConcerned,
  agentsChanged, linesOnly, mergesConcerned, ticketsHeard, ticketsRead} from '/page/app/live/ops.js';
import {listBases, loadGraph, loadProject, fillProjects, goToProject} from '/page/app/loading/load.js';
import {PANE_VIEWS, WS} from '/page/app/workspace/workspace.js';

/* ---------- live: the server pushes what modules publish, and the page redraws; nothing polls, VIEW-018 ----------
 * An intake being recorded is drawn as each object arrives, BASE-039; any other write to the metaform shown is read
 * again. Events that come while the page reads are drawn once, when it is done. */
// left: the intake left unfinished, with no agent recording it; bases: a change in the batch may have changed the
// project's metaforms; intake: one may have begun or ended an intake's recording
export const LIVE = {layer: null, base: null, seen: '', busy: false, again: false, whole: false, named: null, done: 0,
  drawn: -Infinity, brief: false, left: null, bases: false, intake: false};
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
 * recorded, saying what happened: its agent stopped when it is left unfinished, it finished when its metaform still
 * stands, or it stopped because the project was cleared, the one thing that takes a metaform away, VIEW-019. An intake
 * recorded in a base of its own, beside the one shown, is followed only once the person shows that base: the page,
 * its board, chats and agents stay where they are, and the base list offers the new one, VIEW-045 as amended
 * 2026-10-17. */
async function follow(found) {
  if (found) ELSEWHERE.followed.add(`${S.project}/${found.base_id}/${found.layer}`);
  if (found && found.layer !== LIVE.layer) {
    Object.assign(LIVE, {layer: found.layer, base: found.base_id, seen: ''});
    if (S.base !== found.base_id) {
      const listed = await listBases();
      // beside a base the page shows; a page that shows none, its project cleared or never mapped, shows the base
      // the intake makes, which is the project's only one
      if (S.base && listed.some(item => item.id === S.base)) {
        const named = listed.find(item => item.id === found.base_id)?.name || 'a base of its own';
        drawIntake();
        toast(`An intake is being recorded in ${named}, beside the map shown here, which stays as it is with its `
          + `tickets and chats. Choose ${named} in the base list to watch it.`);
        return;
      }
      S.base = found.base_id;
      await listBases();
    }
    S.layers = (await read('layers', {limit: 0})).results; renderChips();
    drawIntake();
    toast(`An intake is being recorded in ${found.layer}; the map follows it as each object is recorded.`);
  } else if (!found && LIVE.layer) {
    const {base, layer} = LIVE;
    const left = LIVE.left && LIVE.left.base_id === base && LIVE.left.layer.name === layer;
    const now = left ? [] : await listBases();
    const stands = now.some(item => item.id === base);
    Object.assign(LIVE, {layer: null, base: null, seen: ''});
    renderLegend();
    drawIntake();
    // one finished in a base of its own is finished beside the active map, which stays active until the person
    // activates it, STORE-041 as amended 2026-10-17; the page stays on the base it shows
    const beside = stands && !now.find(item => item.id === base).active;
    toast(left ? `The intake agent stopped; the intake ${layer} was left unfinished.`
      : beside ? `The intake ${layer} finished in a base of its own, beside the active map, which stays active: `
        + 'choose it in the base list and press Activate to work on it.'
      : stands ? `The intake finished.` : `The intake stopped: ${S.project} was cleared.`);
    if (stands) attend(`intake:${base}`, 'The intake finished', null, null);  // the mascot says so too, `ATTN`
    if (stands) offerNext();
    await loadProject(stands ? S.base : null);
    return;
  }
  if (following()) await loadLive();
}
/* The intakes building, BASE-039: the one an agent records now, to follow, its process alive or this project's intake
 * agent running, which reads before its first record; any other is left unfinished, kept in `LIVE.left` for its
 * notice and never followed. */
async function building() {
  const project = S.project;
  const all = (await read('intake-building')).results || [];
  if (S.project !== project) return null;
  const now = all.find(one => one.recording) || (intakeRunning() ? all[0] : null) || null;
  LIVE.left = !now && all[0] ? {...all[0], project} : null;
  drawLeft();
  return now ? {layer: now.layer.name, base_id: now.base_id} : null;
}
/* On connecting, on the browser's own reconnect, and when this project's intake agent stops, what is being recorded
 * now is read once. */
export async function recordingNow() {
  await follow(await building());
}
/* One push: the chassis fired map.changed for a metaform of this project, or for its metaforms themselves, VIEW-018.
 * The page reads what is being recorded, then follows it, returns to the map when it has finished, shows the active
 * metaform when the project's metaforms changed, or reads the layers and the map again, keeping the view and the
 * selection. A change to tickets or messages alone reads only those, below. */
/* An intake happening in another project takes the page there, as one started in this project takes the map to it:
 * the person watches an intake where it is recorded. Only a change written into the intake being recorded does it,
 * once for that intake, so a person who goes back is left there; nothing else in another project ever switches the
 * page, and a change of tickets or agents elsewhere is not even looked at. */
/* An intake agent starting in another project takes the page there too, at its launch, not at its first record, which
 * may be minutes later: its session's change names its `intake-` work id (UX review round 2, 2026-10-17,
 * new-project-intake F1 and F3). Each test is decided from the event alone, before any read, and an event that comes
 * while one is read is kept, the latest in one slot, and read once the read in hand is done, never dropped (CLAUDE.md
 * section 2, rules 2 and 4). */
const ELSEWHERE = {followed: new Set(), busy: false, pending: null};
/* The intake agent's work id an event names, or null. */
function intakeWork(payload) {
  const works = payload.work_ids;
  if (!Array.isArray(works)) return null;
  for (let at = 0; at < works.length; at++) if (String(works[at]).startsWith('intake-')) return String(works[at]);
  return null;
}
/* Whether an event of another project can concern an intake there: a write that may be into the layer being recorded,
 * or the intake agent's own session. A change of that project's bases alone never is, nor a change of its tickets or
 * of any other agent. */
function mayBeIntake(payload) {
  if (intakeWork(payload)) return true;
  if (!payload.base_id) return false;
  const named = payload.tables;
  if (named === 'dispatch' || ticketsOnly(payload)) return false;
  if (!Array.isArray(named)) return true;
  for (let at = 0; at < named.length; at++) {
    const table = String(named[at]);
    if (table !== 'intake.recorder' && !opTable(table)) return false;
  }
  return true;
}
async function intakeElsewhere(payload) {
  if (!mayBeIntake(payload)) return;
  if (ELSEWHERE.busy) { ELSEWHERE.pending = payload; return; }
  ELSEWHERE.busy = true;
  try {
    const project = payload.project, work = intakeWork(payload);
    if (work) return await intakeStarting(project, work);
    const found = (await getJson(`/api/intake-recording?project=${encodeURIComponent(project)}`)).results?.[0];
    // only a change written into the intake being recorded: an intake happening now, never an old one left unfinished
    if (!found || payload.base_id !== found.base_id) return;
    const key = `${project}/${found.base_id}/${found.layer.name}`;
    if (ELSEWHERE.followed.has(key) || project === S.project) return;
    ELSEWHERE.followed.add(key);
    await goToProject(project, `An intake started in ${project}; the page follows it there.`);
  } catch (error) { /* a project that cannot be read now is not followed */ }
  finally {
    ELSEWHERE.busy = false;
    const next = ELSEWHERE.pending;
    ELSEWHERE.pending = null;
    if (next) intakeElsewhere(next);
  }
}
/* An intake agent of another project, launched or running: the page goes there, where its bar shows it starting and
 * its chat; one that ended without starting is said with why, and the page stays. Once per intake. */
async function intakeStarting(project, work) {
  const key = `${project}/${work}`;
  if (ELSEWHERE.followed.has(key) || project === S.project) return;
  const read = await getJson(`/api/dispatch-sessions?project=${encodeURIComponent(project)}&id=${
    encodeURIComponent(work)}&thread=false`);
  const sessions = read.sessions || [];
  const now = sessions.findLast(one => one.work_id === work) || null;
  if (!now) return;
  ELSEWHERE.followed.add(key);
  if (now.state === 'running' || now.state === 'starting') {
    await goToProject(project, `An intake agent is starting in ${project}; the page follows it there.`);
  } else if (/did not start|failed/.test(String(now.how || ''))) {
    toast(`The intake agent in ${project} did not start: ${String(now.how).replace(/^it (failed|did not start):?\s*/, '')}`);
  }
}
/* A change to the registered projects, or a project opened from its folder, VIEW-002: the chooser lists what is
 * registered now, read once for a burst of them, and the page goes to the project the person opened, whichever it
 * shows (UX review round 2, 2026-10-17, new-project-intake F2). Decided from the event alone. */
const PROJECTS = {busy: false, again: false, open: null};
function projectsChange(payload) {
  const named = payload.tables;
  if (payload.base_id || !Array.isArray(named)) return false;
  let projects = false, opened = false;
  for (let at = 0; at < named.length; at++) {
    if (named[at] === 'home.projects') projects = true;
    else if (named[at] === 'web.opened') opened = true;
    else return false;
  }
  if (opened && payload.project !== S.project) PROJECTS.open = payload.project;
  if (projects || opened) heardProjects();
  return true;
}
async function heardProjects() {
  if (PROJECTS.busy) { PROJECTS.again = true; return; }
  PROJECTS.busy = true;
  try {
    do {
      PROJECTS.again = false;
      const open = PROJECTS.open;
      PROJECTS.open = null;
      if (open && open !== S.project) {
        await goToProject(open, `The page went to ${open}, opened from its folder.`);
      } else {
        S.projects = (await getJson('/api/projects')).projects || [];
        fillProjects();
      }
    } while (PROJECTS.again);
  } catch (error) { /* the chooser stays as it was until the next change */ }
  finally { PROJECTS.busy = false; }
}
/* Whether a change is to an agent's thread lines alone, as its kinds say, or its tables when it says no kinds. Each
 * test here runs per event and allocates nothing. */
function threadOnly(payload) {
  const kinds = payload.kinds;
  if (!Array.isArray(kinds)) return linesOnly(payload) && !payload.signal;
  for (let at = 0; at < kinds.length; at++) if (kinds[at] !== 'line') return false;
  return kinds.length > 0;
}
/* Whether a change names a table passing the test, or names none, so it may have changed any. */
function namesTable(named, test) {
  if (!named) return true;
  if (!Array.isArray(named)) return false;
  for (let at = 0; at < named.length; at++) if (test(String(named[at]))) return true;
  return false;
}
/* The workspace's panes read again only for a change to their own tables. */
const PANE_TABLES = [['messages', table => table === 'messages' || table === 'map.question_work'],
  ['runs', table => table.startsWith('workflow')]];
/* Whether a change named tables, every one of them passing the test. */
const allTables = (named, test) => Array.isArray(named) && named.length && named.every(table => test(String(table)));
/* Whether a change to this metaform's ops says nothing past what is drawn: the sequence it reached is one the page
 * has drawn already, as when it arrives while a read is under way that applies its ops. */
const opTable = table => table === 'ops' || table === 'objects' || table.startsWith('op:');
const drawnAlready = payload => payload.base_id === S.base && typeof payload.seq === 'number'
  && typeof S.seq === 'number' && payload.seq <= S.seq && allTables(payload.tables, opTable);
export async function changed(event) {
  if (event.topic !== 'map.changed') return;
  if (event.payload && projectsChange(event.payload)) return;
  if (event.payload?.project && event.payload.project !== S.project) return intakeElsewhere(event.payload);
  if (event.payload?.project !== S.project) return;
  const named = event.payload.tables;
  // the workspace's panes that read the map read again, but for an agent's thread lines alone, which no pane shows;
  // its messages and its workflow runs only when the change names their tables, or names none
  if (WS.on && !threadOnly(event.payload)) {
    WS.refresh();
    for (let at = 0; at < PANE_TABLES.length; at++) {
      const page = PANE_TABLES[at][0];
      if (namesTable(named, PANE_TABLES[at][1]) && WS.isShown(WS.paneOfPage(page)?.id)) PANE_VIEWS[page].show();
    }
  } else if (WS.active && !threadOnly(event.payload)) WS.refresh();
  // the agent recording an intake has gone: what is building is read at once, so its bar goes, and no map is read
  if (allTables(named, table => table === 'intake.recorder')) return recordingNow().catch(error => toast(error.message));
  // a setting changed, here or elsewhere: the settings screen reads again if it is open, F13
  if (Array.isArray(named) && named.some(table => /(^|\.)settings$/.test(String(table)))) {
    document.dispatchEvent(new CustomEvent('metaform:settings', {detail: named}));  // the tables it names
  }
  if (drawnAlready(event.payload)) return;
  if (briefTouched(named)) LIVE.brief = true;
  if (allTables(named, table => table.startsWith('jev.'))) {
    if (!LIVE.busy) { if (!$('#p-brief').hidden) renderBrief(); LIVE.brief = false; }
    return;  // a Jev decision kept at a node is an item there: its brief changes, the map does not
  }
  const agents = named === 'dispatch'
    || Array.isArray(named) && named.some(table => String(table).startsWith('dispatch.'));
  if (agents) {
    const payload = event.payload;
    const works = Array.isArray(payload.work_ids) ? payload.work_ids : null;
    agentsChanged(mergesConcerned(payload), sessionsConcerned(payload), works);
  }
  // an agent's own tables, its thread, sessions and settings, change no map
  if (named === 'dispatch' || allTables(named, table => table.startsWith('dispatch.'))) return;
  // nor do the settings, the page's own view choices among them, each read where it is used: a key that steps a view
  // choice saves it, and a map read again for every save faded the edges out and in as the keys were pressed
  if (allTables(named, table => /(^|\.)settings$/.test(table))) return;
  const tickets = ticketsOnly(event.payload);
  if (tickets && event.payload.base_id && event.payload.base_id !== S.base) return;  // another metaform's
  ticketsHeard(event.payload);  // the tickets and the messages it says it concerns, read once for the batch
  if (!tickets) {
    LIVE.whole = true;
    LIVE.named = LIVE.named && opsOnly(LIVE.named) ? [...LIVE.named, ...(named || [])] : named || null;
    // a change of the project's metaforms names no metaform, changes.note; one that names its tables names the
    // intake's recorder when an agent begins or ends recording an intake, data/recorder.py
    if (!event.payload.base_id) LIVE.bases = true;
    if (!Array.isArray(named) || named.includes('intake.recorder')) LIVE.intake = true;
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
 * changed, the ops since the drawn sequence, or else the layers and the map again. Each is read only when a change in
 * the batch says it may have changed it. */
async function readAgain() {
  await settled();
  LIVE.again = false;
  if (!LIVE.whole && S.whole && !LIVE.layer) { await ticketsChanged(); return; }
  LIVE.whole = false;
  const named = LIVE.named; LIVE.named = null;
  const bases = LIVE.bases, intake = LIVE.intake;
  LIVE.bases = false; LIVE.intake = false;
  LIVE.drawn = performance.now();  // a whole reload: the next waits SPACING, a ticket change does not
  // what is building, when a change may have begun or ended an intake's recording, while one is followed, or while
  // this project's intake agent runs, which may make its layer before it records into it
  const asked = intake || LIVE.layer !== null || intakeRunning();
  if (asked) {
    const found = await building();
    if (found || LIVE.layer) { await follow(found); return; }
  }
  // the project's metaforms changed: show the active one, as on opening; else the ops since the drawn sequence,
  // applied, or the layers and the map read again
  const metaforms = bases ? (await read('bases', {limit: 0})).results : S.bases;
  const same = metaforms.length === S.bases.length && metaforms.every(item =>
    S.bases.some(known => known.id === item.id && known.active === item.active));
  if (same && opsOnly(named) && await appliedOps()) {
    await ticketsChanged();  // the tickets and messages the batch's changes said they concern, if any
    return;
  }
  // a whole read, which takes the tickets and messages too; what is building is read beside it when not read above,
  // since a layer begun, finished or discarded, as an intake from the command line makes, falls back to it
  ticketsRead();
  if (!asked) {
    const found = await building();
    if (found) { await follow(found); return; }
  }
  if (!same) await loadProject();
  else {
    S.layers = (await read('layers', {limit: 0})).results;
    renderChips();
    await loadGraph(false);
  }
  boardFromTickets();  // the work the map's read took, not read again
}
