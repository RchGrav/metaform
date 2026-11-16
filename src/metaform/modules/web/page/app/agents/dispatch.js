/* Agents dispatched on tickets, VIEW-039: the signals of an agent waiting on the person, the start window, the
 * agents key and an agent's session opened. */
import '/page/app/board/history.js';  // the part before runs first, so the parts run in the page's order
import {drawGlyph} from '/page/agents3d.js';
import {$, h, fill, keyedFill} from '/page/app/core/dom.js';
import {expandCut} from '/page/app/core/expand.js';
import {overlay} from '/page/app/core/overlays.js';
import {toast} from '/page/app/core/controls.js';
import {FRAMED, S, read} from '/page/app/core/reads.js';
import {readFailed} from '/page/app/core/errors.js';
import {banner, bannered, unbanner} from '/page/app/core/banner.js';
import {ticketNode, figures, bodyOf, isSystemTalk} from '/page/app/figures/agents.js';
import {typeGlyph} from '/page/app/figures/walk.js';
import {noticeAttention} from '/page/app/figures/attention.js';
import {INUSE, paintInUse} from '/page/app/map3d/light.js';
import {G, TOUCHED} from '/page/app/map3d/graph3d.js';
import {agentsWindow, VIEW} from '/page/app/views/settings.js';
import {follow3d} from '/page/app/views/lens.js';
import {autoZoom2d, FOLLOW} from '/page/app/map2d/camera.js';
import {DOCK} from '/page/app/dock/embody.js';
import {openHelpdesk, drawAgentSessions, drawAgentList} from '/page/app/dock/threads.js';
import {chatButton} from '/page/app/dock/send.js';
import {callSystem} from '/page/app/dock/commands.js';
import {calledOf} from '/page/app/board/messages.js';
import {conditionLabel, partAt, taskWords} from '/page/app/board/refs.js';
import {eligibleAgents, allowsAgent, drawBoard, renderBoard} from '/page/app/board/board.js';
import {wrote} from '/page/app/board/history.js';
import {named} from '/page/app/task/task.js';
import {HARNESS, readHarnesses, agentName, agentPicker, PICKERS, drawDockTab, optionWords}
  from '/page/app/agents/pickers.js';
import {isIntake, workPart, isSystemSession} from '/page/app/session/tools.js';
import {notificationState, taskSummary} from '/page/app/session/tasks.js';
import {renderWorkerBoard} from '/page/app/agents/workers.js';
import {readIntake, openIntakeChat} from '/page/app/intake/intake.js';
import {nodeIn} from '/page/app/graph/data.js';
import {drawPermissions as renderPermissions} from '/page/app/agents/permissions.js';
/* ---------- agents dispatched on tickets, VIEW-039 ----------
 * The dispatch module starts, messages and stops an agent on a ticket, BASE-052; the page asks it to through three
 * writes, VIEW-011. What an agent does is read from the dispatch layer at its ticket's node with each map change. */
export const D = {sessions: [], starting: false, signals: [], states: {}, subagents: [], claims: [],
  asking: [], onAsking: null, next: null, historyBusy: false, menuMost: 40};
export const SESSIONS_DRAWN = [];  // what a later part draws again with the sessions, such as the broadcast window
/* The signals of an agent waiting on the person: a permission request, or a question of its own, ACP's elicitation. */
export const WAITS_ON_PERSON = ['permission-waiting', 'question-waiting'];
/* Full Auto, the header's switch: the shown project's tasks_full_auto. When a worktree closes, its branch is merged
 * into the branch checked out in the project's folder and the worktree is removed. Read with the project and again
 * when the tasks module's settings change, here or elsewhere; saved as the person turns it. */
// turn: the newest read or save begun, so an older one that lands after it is let go; a read asked for while a save
// is in flight waits for it, `again`, so the change the save itself announces is read once, after its answer
const FULLAUTO = {turn: 0, saving: false, again: false};
export async function readFullAuto() {
  const project = S.project, control = $('#fullAuto');
  if (FRAMED || !project) return;
  if (FULLAUTO.saving) { FULLAUTO.again = true; return; }
  const turn = ++FULLAUTO.turn;
  try {
    const rows = (await read('settings', {keys: 'tasks_full_auto'})).settings || [];
    if (turn === FULLAUTO.turn) showFullAuto(rows, project);
  } catch (error) {
    if (S.project !== project || turn !== FULLAUTO.turn) return;
    control.disabled = false;  // a turn saves the value it shows and reads again, so a failed read is not a dead end
    readFailed(error);
  }
}
/* The switch as the settings say it; a server without the tasks module's setting has nothing to turn. */
function showFullAuto(rows, project) {
  if (S.project !== project) return;
  const row = rows.find(one => one.key === 'tasks_full_auto'), control = $('#fullAuto');
  control.checked = row?.value === true;
  control.disabled = !row;
}
$('#fullAuto').onchange = async () => {
  const project = S.project, control = $('#fullAuto'), on = control.checked;
  control.disabled = true;
  ++FULLAUTO.turn;
  FULLAUTO.saving = true;
  let saved = null;
  try {
    saved = await wrote('/api/settings', {key: 'tasks_full_auto', value: on});
  } finally { FULLAUTO.saving = false; }
  if (saved && S.project === project) {
    showFullAuto(saved.settings || [], project);  // the save answers with every setting as it is now
    toast(on ? 'Full Auto is on: a worktree that closes is merged into your checked-out branch and removed.'
      : 'Full Auto is off: a worktree that closes stays, with its branch, for you to merge.');
  }
  // a refused save reads the value in force; a read asked for meanwhile, another project's among them, runs now
  if (!saved || FULLAUTO.again) { FULLAUTO.again = false; readFullAuto(); }
};
document.addEventListener('metaform:settings', event => {
  if (Array.isArray(event.detail) && event.detail.includes('tasks.settings')) readFullAuto();
});
export const waiting = ticket => !ticket.done && !ticket.taken && (ticket.task || '').trim()
  && !D.sessions.some(one => one.state === 'running'
    && (one.work_id === ticket.id || (ownGlyph(ticket) && ownGlyph(ticketOf(one.work_id)) === ownGlyph(ticket))));
export const ticketOf = workId => (S.tickets || []).find(ticket => ticket.id === workId);
/* An agent's own name, two capitalized words dispatch works out from its session id as the session starts,
 * `StableComet`, `name` on the session's state: what the person calls it, and how they call its context back,
 * `dispatch resume <name>`. Shown as given, never split or recased. None for a session that ran before agents had
 * names. */
export const nameOf = session => (session && D.states?.[session.session_id]?.name) || null;
/* An agent as the dock, the agents key and the session lists say it: its name first, then its ticket's number; its
 * kind where it has no name, and the part it works on where its work is no ticket. */
export function agentLabel(session, workId = session?.work_id) {
  const name = nameOf(session) || agentName(session?.agent), item = ticketOf(workId)?.map?.item;
  return item ? `${name} · ${item}` : `${name} on ${workPart(workId)}`;
}
/* The model and the thinking level a session runs, from its settings as the dock's line shows them. */
export function runsOn(state) {
  const settings = state?.settings || [];
  return ['model', 'thought_level'].map(category => settings.find(one => one.category === category))
    .filter(Boolean).map(optionWords).filter(Boolean);
}
export function ticketPart(ticket) {
  const element = ticket?.address ? partAt(ticket.address) : null;
  return element ? named(element) : ticket ? calledOf(ticketNode(ticket)) : 'its ticket';
}
// a ticket's own glyph, VIEW-040: the map module keeps it and the work read shows it under `map`, BASE-035
export const ownGlyph = ticket => ticket?.map?.glyph;
// the character its 3D figure is, VIEW-035: the ticket's own glyph when it is assigned one, VIEW-040
// and else the character the person chose for the agent's type, web_agent_glyphs, when no agent at work has it
// a body chosen for a conversation agent, `embody`, comes before it
export const glyphFor = workId => drawGlyph(workId, ownGlyph(ticketOf(workId)) || bodyOf(workId),
  typeGlyph(workId));
export const glyphOf = workId => `/page/agent-glyphs/${glyphFor(workId)}.svg`;
export {PROMPT_WORDS} from '/page/app/agents/permissions.js';
export async function startAgent(workId, agent, own = {}) {
  if (!await wrote('/api/dispatch-start', {work_id: workId, agent, ...own})) return false;
  toast(`${agentName(agent)} is starting on the ticket. It shows under Agent deployed while it is working.`);
  return true;
}
const startAgentFor = (ticket, agent) => START.agentChanged ? agent : ticket.map?.agent || agent;
/* Each ticket keeps its assigned agent until the person changes this window's picker, VIEW-039. A card's own start
 * opens on that assignment rather than a previous window's choice. */
export function startWindow(title, tickets, all = false) {
  if (D.starting) return;
  $('#dispatch .title').textContent = title;
  const pick = PICKERS.start ||= agentPicker({label: 'Agent', kept: true,
    onchange: () => { START.agentChanged = true; START.draw?.(); }});
  START.agentChanged = false;
  if (!all && tickets.length === 1 && tickets[0].map?.agent) pick.set(tickets[0].map.agent);
  if (!$('#dispatch .pickhost').firstChild) $('#dispatch .pickhost').append(pick);
  const startAll = $('#dispatch .start-all');
  let shown = tickets;  // the tickets the window offers now, for the agent chosen
  startAll.hidden = !all;
  $('#dispatch .slots').hidden = !all;
  startAll.disabled = !tickets.length;
  startAll.onclick = () => startAllTickets(shown, pick, startAll);
  pick.hold(false);
  let counted = false;  // Start all waits for the slots read as the window opens, so its label is what it starts
  const draw = () => {
    const agent = pick.value();
    shown = all ? startable(tickets, agent) : tickets;
    const said = startAllLabel(shown.filter(ticket => allowsAgent(ticket, startAgentFor(ticket, agent))).length);
    startAll.textContent = counted ? said.label : 'Start all';
    $('#dispatch .slots').textContent = counted ? said.said : 'Reading the agent slots…';
    startAll.disabled = !shown.length || !agent || !counted || !said.count;
    // A ticket's own Start is off, with why, only while the machine is full.
    const full = counted && HARNESS.slots ? HARNESS.slots.machine_free <= 0 : false;
    fill($('#dispatch .tickets'), shown.map(ticket => h('div', {class: 'ticket', 'data-id': ticket.id},
      conditionLabel(ticket), h('span', {class: 'agent'}, agentName(startAgentFor(ticket, agent))),
      startButton(ticket, startAgentFor(ticket, agent), pick, full),
      h('div', {class: 'task'}, ...taskWords(ticket.task || ticket.note || '')))));
    drawPermissions(agent);
  };
  START.draw = draw;
  START.own = {prompts: '', mode: ''};
  START.permissionsFor = null;  // drawn afresh, at the project's settings
  draw();
  $('#dispatch').hidden = false;
  readHarnesses().then(() => { counted = true; if (!$('#dispatch').hidden && START.draw === draw) draw(); });
}
/* A mode belongs to the selected agent. Changing the agent follows its project setting again. */
function drawPermissions(agent) {
  const key = `${S.project}:${agent}`;
  if (START.permissionsFor === key) return;
  START.permissionsFor = key;
  const own = START.own;
  own.mode = '';
  return renderPermissions($('#dispatch .permissions'), agent, own,
    () => START.permissionsFor === key && START.own === own);
}
/* The permissions chosen for this launch. A mode belongs only to the agent whose options supplied it. */
const launchOwn = agent => Object.fromEntries(Object.entries(START.own || {}).filter(([key, value]) => value
  && (key !== 'mode' || START.permissionsFor === `${S.project}:${agent}`)));
/* Start all offers the tickets the agent chosen may take, one for each glyph, since a glyph's tickets are one
 * agent's, done one at a time. */
function startable(candidates, agent) {
  const glyphs = new Set();
  return candidates.filter(ticket => {
    if (!allowsAgent(ticket, startAgentFor(ticket, agent))) return false;
    const glyph = ownGlyph(ticket);
    if (glyph && glyphs.has(glyph)) return false;
    if (glyph) glyphs.add(glyph);
    return true;
  });
}
/* How many of the tickets offered Start all starts now: the agent slots free as dispatch's gate counts them, the
 * project's and the machine's, read when the window opens; a count that cannot be read starts none, never all. UX
 * review round 1, 2026-10-17 (forensic cause 3, dispatch-concurrency F5): the person learned how many started only
 * from the toast afterwards, and an unread count offered every ticket. */
export function startAllLabel(offered) {
  const free = HARNESS.free, slots = HARNESS.slots;
  if (free === null || free === undefined) return {count: 0, label: 'Start all', said: 'Could not read the agent '
    + 'slots, so Start all starts none; start a ticket on its own, or open this window again.'};
  const count = Math.min(free, offered);
  const machine = slots && slots.machine_free < Math.max(0, slots.limit - slots.used)
    ? `; this machine runs ${slots.machine_used} of the ${slots.machine_limit} it allows` : '';
  // A ticket's own Start is available whenever the machine has room.
  const own = slots && slots.machine_free > 0 ? ' Start a ticket on its own to run it now.'
    : ' A ticket can start once an agent finishes or is stopped.';
  return {count, label: `Start ${count} of ${offered}`, said: `${free} of ${slots ? slots.limit : '?'} agent `
    + `slots free${machine}.${free ? '' : own} `
    + `${offered - count ? `${offered - count} wait in To do for an explicit start or agent choice.` : ''}`.trim()};
}
/* Start all: each ticket's assigned agent, or the person's override, starts one after another, up to the
 * agent slots free now, as its label says before the click; the rest wait in To do for an explicit start or agent
 * choice. Stop starting ends the run between two starts. A failed start can be retried on its own ticket. */
async function startAllTickets(tickets, pick, startAll) {
  if (D.starting) { START.cancel = true; return; }  // the button reads Stop starting while it runs
  D.starting = true;
  START.cancel = false;
  // one token for the run: a Stop all in the middle of it refuses every start of it still on its way, on the server
  START.batch = Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, '0')).join('');
  const agent = pick.value();
  const buttons = [...$('#dispatch .tickets').querySelectorAll('button.start')];
  const offered = tickets.filter((ticket, i) => !buttons[i].disabled);
  pick.hold(true);
  for (const button of buttons) button.disabled = true;
  drawBoard();
  const {count} = startAllLabel(offered.length);  // what the label said, from the read made when it opened
  for (const ticket of offered.slice(count)) buttons[tickets.indexOf(ticket)].textContent = 'Waiting';
  const label = startAll.textContent;
  startAll.textContent = 'Stop starting';
  // A ticket refused spends no slot: the next offered takes its turn, so one ticket that cannot start does not leave
  // the slot idle and the rest unstarted (UX review round 2, held-and-signals F2).
  let started = 0, left = 0, failed = 0, tried = 0;
  for (const ticket of offered) {
    if (started >= count) break;
    tried++;
    const button = buttons[tickets.indexOf(ticket)];
    if (START.cancel) { left++; button.disabled = false; continue; }
    try {
      const chosen = startAgentFor(ticket, agent);
      if (await startAgent(ticket.id, chosen, {...launchOwn(chosen), batch: START.batch})) {
        started++; button.textContent = 'Starting';
      }
      else { failed++; button.disabled = false; button.textContent = 'Retry'; }
    } catch (error) { toast(error.message); failed++; button.disabled = false; button.textContent = 'Retry'; }
  }
  for (const ticket of offered.slice(tried)) {  // not reached: they wait for a slot, as their label says
    buttons[tickets.indexOf(ticket)].textContent = 'Waiting';
  }
  const waiting = offered.length - tried;
  pick.hold(false);
  D.starting = false;
  startAll.textContent = label;
  startAll.disabled = !buttons.some(button => !button.disabled);
  if (!failed && !left) $('#dispatch').hidden = true;
  toast(`${started} agent${started === 1 ? '' : 's'} starting.`
    + (left ? ` You stopped the run; ${left} were not started.` : '')
    + (failed ? ` ${failed} could not start; retry their tickets.` : '')
    + (waiting ? ` ${waiting} wait in To do for an explicit start or agent choice.` : ''));
  await renderBoard();
}
/* One ticket's Start uses its assignment or the person's current override, within its eligible agents. */
function startButton(ticket, agent, pick, full = false) {
  const start = async event => {
    const chosen = startAgentFor(ticket, pick.value());
    event.target.disabled = true;
    try {
      if (await startAgent(ticket.id, chosen, launchOwn(chosen))) { $('#dispatch').hidden = true; await renderBoard(); }
      else event.target.disabled = false;
    } catch (error) { toast(error.message); event.target.disabled = false; }
  };
  return h('button', {class: 'btn primary start', type: 'button',
    disabled: !agent || !allowsAgent(ticket, agent) || full,
    title: !allowsAgent(ticket, agent) ? `Eligible agents: ${eligibleAgents(ticket).map(agentName).join(', ')}`
      : full ? 'This machine runs the most agents dispatch_machine_agents allows; it can start once one finishes or is '
        + 'stopped'
      : `Start ${agentName(agent)} on this ticket`, onclick: start}, 'Start');
}
// the start window's tickets, drawn again for the agent chosen, and the permissions chosen for its launches
const START = {draw: null, own: {prompts: '', mode: ''}, permissionsFor: null, cancel: false, batch: null,
  agentChanged: false};
/* Stop all ends a Start all run between two starts, as its own Stop starting does; true when one was running. UX
 * review round 2 (ux-verify-combined F1): Stop all left the run going, and three agents started after it. */
export function cancelStarting() {
  if (!D.starting) return false;
  START.cancel = true;
  return true;
}
$('#dispatch .close').onclick = () => { $('#dispatch').hidden = true; START.permissionsFor = null; };
overlay($('#dispatch'), {kind: 'dialog', focus: () => $('#dispatch .choice > .btn'),
  close: () => { $('#dispatch').hidden = true; START.draw = null; START.permissionsFor = null; }});
/* The agents key: each agent working in the project now, with its flat icon and in words what it is; a click opens its
 * session's thread. An ended session leaves the key and the map; its log stays in the node's work history, VIEW-036.
 * Sessions are the dispatch module's own tables, never the map. */
let WHOLE_READS = 0;  // the reads of every agent begun, so one that lands after a later one's is let go
const PENDING = {project: null, base: null, whole: null};
const WORKERS = {reading: null, again: false};
export function renderWorkerPanel() {
  if (WORKERS.reading) { WORKERS.again = true; return WORKERS.reading; }
  WORKERS.reading = updateWorkerPanel().finally(() => {
    WORKERS.reading = null;
    if (WORKERS.again) { WORKERS.again = false; return renderWorkerPanel(); }
  });
  return WORKERS.reading;
}
async function updateWorkerPanel() {
  let container = $('#workerBoard');
  if (!container) {
    container = h('div', {id: 'workerBoard'});
    $('#agents').insertBefore(container, $('#agents .list'));
  }
  await renderWorkerBoard(container);
  agentsWindow(container.querySelectorAll('.worker-entry').length + D.sessions.filter(one => one.activity === 'working').length);
}

export async function renderAgents(only = null, bySession = false) {
  if (FRAMED || Array.isArray(only) && !only.length) return;
  const project = S.project, metaform = S.base;
  if (only === null) await renderWorkerPanel();
  const some = Array.isArray(only);
  // A live-list snapshot must land before a later event's records, so it cannot overwrite them afterwards.
  while (some && PENDING.whole && PENDING.project === project && PENDING.base === metaform) await PENDING.whole;
  if (S.project !== project || S.base !== metaform) return;
  const whole = some ? WHOLE_READS : ++WHOLE_READS;
  const reading = some ? readSelected(only, bySession) : readDispatch();
  if (!some) Object.assign(PENDING, {project, base: metaform, whole: reading});
  const {found, claimed} = await reading;
  if (PENDING.whole === reading) PENDING.whole = null;
  if (S.project !== project || S.base !== metaform) return;  // the answer for a project the person has left
  // reads land in any order: a read of every agent begun after this one is the newer, and draws instead
  if (whole !== WHOLE_READS) return;
  if (some) mergeSessions(only, found, bySession);
  else {
    D.sessions = found.sessions || [];
    // a login needed is read from the signals, `sessionStatus`, and a spinning or stuck agent's figure circles
    // restlessly, `moodOf`
    D.signals = found.signals || [];
    D.states = found.states || {};  // each session's state, by session id
    D.next = found.next || null;
    D.menuMost = 40;
  }
  followStart(D.sessions);
  setupNotice();
  drawAgentSessions();
  drawAgentList();  // the full-size dock's agents, each with its state
  for (const draw of SESSIONS_DRAWN) draw();
  if (!some) D.subagents = found.subagents || [];  // the running sessions' own subagents, each a figure, `childFigures`
  if (claimed) {
    D.claims = claimed.claims || [];
  }
  noticeAttention();  // and the mascot calls the person to what needs them, `ATTN`
  // the permission requests and the agents' questions waiting for the person, counted on the chat's tab
  const asking = D.signals.filter(one => WAITS_ON_PERSON.includes(one.signal) && one.active !== false);
  D.asking = asking.map(one => ({...one, agent: D.sessions.find(row => row.session_id === one.session_id)?.agent}))
    .filter(one => D.sessions.some(row => row.session_id === one.session_id && row.state === 'running'));
  drawDockTab();
  D.onAsking?.();  // and the pop-up for a request whose thread is not on screen, agents/asking.js
  readIntake(D.signals);
  if (!$('#board').hidden) drawBoard();
  // at work: a session whose runner says a turn is executing, the same ones the map's figures follow
  const working = D.sessions.filter(one => one.activity === 'working');
  // an entry drawn the same stays in place, so the one under the pointer is not swapped while it is clicked
  keyedFill($('#agents .list'), working.map(one => ({key: one.session_id,
    text: [one.work_id, one.agent, glyphOf(one.work_id), workPart(one.work_id), agentLabel(one),
      onOtherBase(one), taskSummary(D.states?.[one.session_id])].join('\n'),
    make: () => agentRow(one)})));
  markFollowed();
  agentsWindow(working.length + ($('#workerBoard')?.querySelectorAll('.worker-entry').length || 0));  // slides out while any is at work, away a few seconds after
  paintInUse();
  figures(S.tickets || []);  // the map's figures follow the same sessions
}
/* A feature the person set up that a module says is not working, dispatch's setup-not-working signal, is the person's
 * system agent's to bring up with them; it takes the signal as its turn. While no system agent runs, one small notice
 * says so in plain words, with the one action that starts it. Closed, it stays away until other findings are raised. */
const SETUP = {closed: null};
function setupNotice() {
  const waiting = D.signals.filter(one => one.signal === 'setup-not-working' && one.active !== false);
  const talking = D.sessions.some(one => one.state === 'running' && isSystemSession(one, D.states));
  const raised = waiting.map(one => one.signal_key).sort().join(' ');
  if (!waiting.length || talking || raised === SETUP.closed) {
    if (bannered('setup')) unbanner('setup');
    return;
  }
  const what = waiting.length === 1 && waiting[0].feature ? waiting[0].feature : 'something you set up';
  banner('setup', {tone: 'info', text: `It looks like ${what} may not be working. Your system agent can look at it `
    + 'with you.', actions: [{label: 'Talk it over', primary: true, run: () => { unbanner('setup'); callSystem(); }}],
  onClose: by => { if (by === 'person') SETUP.closed = raised; }});
}
/* Auto zoom follows the newest agent start, VIEW-041 and VIEW-005: with web_node_zoom on, a session that begins
 * running on a ticket that had none running takes both cameras to the ticket's node, the 2D map framing it as a
 * selection does and the 3D map flying to it as `follow3d` does; the selection stays. Of several begun since the last
 * read, the newest. The first read of a metaform is where the page starts, never a start; and while the person has
 * used a map in the last 8 seconds, `TOUCHED`, the cameras stay where they are. Off, an agent start never moves them.
 * A session whose ticket the page has not read yet is not counted as running, so its start is still met once the
 * ticket arrives; one on another metaform's ticket never is. */
const STARTS = {shown: null, running: null};
function followStart(sessions) {
  const shown = `${S.project}/${S.base}`, before = STARTS.shown === shown ? STARTS.running : null;
  const running = sessions.filter(one => one.state === 'running' && ticketOf(one.work_id));
  Object.assign(STARTS, {shown, running: new Set(running.map(one => one.work_id))});
  // while the person follows an agent, A, the cameras go with its figure
  if (!before || FOLLOW.work || VIEW.nodeZoom === false || performance.now() - TOUCHED.at < 8000) return;
  const begun = running.filter(one => !before.has(one.work_id) && !isSystemTalk(ticketOf(one.work_id)));
  const newest = begun.sort((a, b) => (Date.parse(a.started) || 0) - (Date.parse(b.started) || 0)).at(-1);
  if (!newest) return;
  const node = ticketNode(ticketOf(newest.work_id));
  if (G && nodeIn(G.graphData(), node)) follow3d(node);
  autoZoom2d(node);
}
/* One batch of named sessions or shown tickets. Claims do not change with a session. */
async function readSelected(ids, bySession) {
  try { return {found: await read('dispatch-sessions', {thread: 'false',
    [bySession ? 'session_ids' : 'ids']: JSON.stringify(ids)}), claimed: null}; }
  catch (error) { readFailed(error); return {found: null, claimed: null}; }
}
export function mergeSessions(ids, found, bySession = true) {
  if (!found) return;
  const named = new Set(ids), field = bySession ? 'session_id' : 'work_id';
  const theirs = bySession ? named : new Set(D.sessions.filter(one => named.has(one.work_id)).map(one => one.session_id));
  D.sessions = D.sessions.filter(one => !named.has(one[field])).concat(found.sessions || [])
    .sort((one, two) => one.seq - two.seq);
  D.signals = D.signals.filter(one => !named.has(one[field])).concat(found.signals || []);
  for (const id of theirs) D.states[id] = null;
  Object.assign(D.states, found.states || {});
  D.subagents = D.subagents.filter(one => !theirs.has(one.parent)).concat(found.subagents || []);
}
/* Ended sessions are read only when the person asks for another history page. */
export async function readSessionHistory() {
  if (D.historyBusy || !D.next) return;
  const project = S.project, whole = WHOLE_READS;
  D.historyBusy = true;
  drawAgentSessions();
  try {
    const found = await read('dispatch-sessions', {history: 'true', after: D.next, limit: 50, thread: 'false'});
    if (S.project !== project || whole !== WHOLE_READS) return;
    mergeSessions((found.sessions || []).map(one => one.session_id), found);
    D.next = found.next || null;
    D.menuMost += (found.sessions || []).length;
  } catch (error) { readFailed(error); }
  finally { D.historyBusy = false; drawAgentSessions(); }
}
/* The sessions and the claims dispatch holds for the project; the threads are read for the open window only. A failed
 * read keeps the agents drawn as last read. The conversations are the project's whatever its map holds, so they are
 * read with no metaform too, after a clear or before the first intake, PROJ-026. */
async function readDispatch() {
  // With no project chosen, as on a home that holds none, there is nothing to ask the server for.
  if (!S.project) return {found: {sessions: []}, claimed: {claims: []}};
  let found = {sessions: []};
  let claimed = {claims: D.claims || []};
  try { found = await read('dispatch-sessions', {thread: 'false'}); }
  catch (error) { readFailed(error); found = {sessions: D.sessions}; }
  try { claimed = await read('dispatch-claims'); } catch (error) { readFailed(error); }
  return {found, claimed};
}
/* One agent at work in the key: whether the part of the map it uses shows in white, its glyph, its name and what it
 * works on, opening its thread, and Chat. */
/* The name of the base an agent's session is pinned to when it is not the base shown, else empty: an agent at work on
 * a base the page does not show is still listed and stoppable here, and says where it works (UX review round 2,
 * 2026-10-17, project-scope F5). */
export function onOtherBase(one) {
  if (!one.base || one.base === S.base) return '';
  for (let at = 0; at < S.bases.length; at++) if (S.bases[at].id === one.base) return S.bases[at].name;
  return 'another base';
}
function agentRow(one) {
  const name = nameOf(one) || agentName(one.agent), elsewhere = onOtherBase(one);
  const responsibility = taskSummary(D.states?.[one.session_id]);
  const showUse = event => { INUSE.off[event.target.checked ? 'delete' : 'add'](one.work_id); paintInUse(); };
  return h('div', {class: 'agent-row'},
    h('input', {type: 'checkbox', class: 'inuse', checked: !INUSE.off.has(one.work_id),
      'aria-label': `The part of the map ${name} is using`, onchange: showUse,
      title: 'Checked: the part of the map this work is using shows in white. Unchecked: it is hidden.'}),
    h('button', {class: 'agent working', 'data-id': one.work_id, 'data-session': one.session_id,
      title: `${name} on work ${one.work_id}: working`, onclick: () => agentAt(one.work_id, one.session_id)},
    h('img', {src: glyphOf(one.work_id), alt: glyphFor(one.work_id)}), h('b', {}, agentLabel(one)),
    h('small', {}, [responsibility, `on ${workPart(one.work_id)} · working${elsewhere ? ` · on ${elsewhere}` : ''}`]
      .filter(Boolean).join(' · '))),
    chatButton({id: one.work_id}, `${name} on ${workPart(one.work_id)}`));
}
// what an agent works on, cut short, is its button's tooltip, `expandCut`: the button's click is its own
expandCut($('#agents .list'), {row: '.agent-row', text: '.agent small'});
/* The agent the person follows, A, `followFigure` in figures/eyes.js, named at the 2D map's top right for as long as
 * it is followed: its glyph's image, its agent's name and its glyph, gone when none is followed; and its entry in the
 * key marked as the one followed. */
export function showFollowed(workId, glyph) {
  const chip = $('#followed');
  if (!workId) chip?.remove();
  else {
    const agent = D.sessions.find(one => one.work_id === workId && one.state === 'running')?.agent
      || ticketOf(workId)?.map?.agent;
    fill(chip || $('#map2d').appendChild(h('div', {id: 'followed', class: 'followed', role: 'status'})),
      h('img', {src: `/page/agent-glyphs/${glyph}.svg`, alt: ''}), `Following ${agentName(agent)} · ${glyph}`);
  }
  markFollowed();
}
function markFollowed() {
  for (const row of document.querySelectorAll('#agents .agent-row')) {
    if (row.querySelector('.agent')?.dataset.id === FOLLOW.work) row.setAttribute('aria-current', 'true');
    else row.removeAttribute('aria-current');
  }
}
/* An agent's session opened in the chat dock, as the agents key, a figure in 3D, the node's work history and a
 * request waiting for the person open it: the thread of that session, or of the ticket's newest session, chosen by the
 * person, so its agent and its part are shown on the maps. */
export function agentAt(workId, sessionId = null) {
  const sessions = D.sessions.filter(one => one.work_id === workId);
  const session = sessionId ? sessions.find(one => one.session_id === sessionId) || {session_id: sessionId}
    : sessions.filter(one => one.state === 'running').at(-1) || sessions.at(-1) || null;
  if (isIntake(workId)) return openIntakeChat(workId, session?.session_id || null, {focus: true});
  const state = D.states?.[session?.session_id];
  if (notificationState(state)) return openHelpdesk(workId, state.title || state.about || 'Project updates', '',
    session?.session_id, 'notification');
  // a thread already open keeps its name and where it comes from: the person's chat about a node and the system agent
  // hang on the same held ticket, and the thread read tells them apart
  const open = session && DOCK.chats.find(one => one.session === session.session_id);
  openHelpdesk(workId, open?.label || agentLabel(session, workId),
    'It answers when its current step ends.', session?.session_id || null, null, {focus: true});
}
