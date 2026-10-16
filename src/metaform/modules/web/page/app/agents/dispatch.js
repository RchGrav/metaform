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
import {noMetaform} from '/page/app/header/admin.js';
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
import {readHarnesses, agentName, agentPicker, PICKERS, drawDockTab} from '/page/app/agents/pickers.js';
import {isIntake, workPart} from '/page/app/session/tools.js';
import {readIntake, openIntakeChat} from '/page/app/intake/intake.js';

/* ---------- agents dispatched on tickets, VIEW-039 ----------
 * The dispatch module starts, messages and stops an agent on a ticket, BASE-052; the page asks it to through three
 * writes, VIEW-011. What an agent does is read from the dispatch layer at its ticket's node with each map change. */
export const D = {sessions: [], starting: false, readFor: null};
export const SESSIONS_DRAWN = [];  // what a later part draws again with the sessions, such as the broadcast window
/* The signals of an agent waiting on the person: a permission request, or a question of its own, ACP's elicitation. */
export const WAITS_ON_PERSON = ['permission-waiting', 'question-waiting'];
export const AUTO = {value: false, agents: null};
export async function readAutostart() {
  if (FRAMED) return;
  const project = S.project, control = $('#autostartAgents');
  control.disabled = true;
  try {
    const found = await read('dispatch-autostart');
    if (S.project !== project) return;
    Object.assign(AUTO, found);
    control.checked = found.value;
    control.disabled = found.available === false;
  } catch (error) { if (S.project === project) readFailed(error); }
}
async function saveAutostart() {
  const project = S.project, control = $('#autostartAgents');
  control.disabled = true;
  try {
    // the switch alone: Autostart starts each ticket with the agent its card prefers, and the default agent is the
    // person's own choice, made in a picker, never taken from whatever a window last showed
    const saved = await wrote('/api/dispatch-autostart', {value: control.checked});
    if (S.project !== project) return;
    if (saved) Object.assign(AUTO, saved);
    control.checked = AUTO.value;
  } catch (error) { if (S.project === project) { control.checked = AUTO.value; toast(error.message); } }
  finally { if (S.project === project) control.disabled = false; }
}
$('#autostartAgents').onchange = saveAutostart;
export const waiting = ticket => !ticket.done && !ticket.taken && (ticket.task || '').trim()
  && !D.sessions.some(one => one.state === 'running'
    && (one.work_id === ticket.id || (ownGlyph(ticket) && ownGlyph(ticketOf(one.work_id)) === ownGlyph(ticket))));
export const ticketOf = workId => (S.tickets || []).find(ticket => ticket.id === workId);
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
/* How each dispatch_prompts choice reads, and what approving every prompt risks; the Agents menu and the start window
 * say them alike. */
export const PROMPT_WORDS = {
  'approve-all': ['Approve every prompt',
    'Agents run any tool without asking, including ones that change or delete files.'],
  'approve-reads': ['Approve reads and searches; ask for the rest', ''],
  ask_all: ['Ask every prompt as a question at the ticket', '']};
/* The harness modes that let the agent act without asking, whatever the prompts answer. */
const OPEN_MODES = ['bypassPermissions', 'agent-full-access'];
const promptWords = choice => PROMPT_WORDS[choice]?.[0] || choice;
export async function startAgent(workId, agent, own = {}) {
  if (!await wrote('/api/dispatch-start', {work_id: workId, agent, ...own})) return false;
  toast(`${agentName(agent)} is starting on the ticket. It shows under Agent deployed while it is working.`);
  return true;
}
/* The window an agent is started from: the tickets, and the agent chosen once for the window, in the picker every
 * start shares, VIEW-039. */
export function startWindow(title, tickets, all = false) {
  if (D.starting) return;
  $('#dispatch .title').textContent = title;
  const pick = PICKERS.start ||= agentPicker({label: 'Agent', kept: true, onchange: () => START.draw?.()});
  if (!$('#dispatch .pickhost').firstChild) $('#dispatch .pickhost').append(pick);
  const startAll = $('#dispatch .start-all');
  let shown = tickets;  // the tickets the window offers now, for the agent chosen
  startAll.hidden = !all;
  startAll.disabled = !tickets.length;
  startAll.onclick = () => startAllTickets(shown, pick, startAll);
  pick.hold(false);
  const draw = () => {
    const agent = pick.value();
    shown = all ? startable(tickets, agent) : tickets;
    startAll.disabled = !shown.length || !agent;
    fill($('#dispatch .tickets'), shown.map(ticket => h('div', {class: 'ticket', 'data-id': ticket.id},
      conditionLabel(ticket), startButton(ticket, agent, pick),
      h('div', {class: 'task'}, ...taskWords(ticket.task || ticket.note || '')))));
    drawPermissions(agent);
  };
  START.draw = draw;
  START.own = {prompts: '', mode: ''};
  START.permissionsFor = null;  // drawn afresh, at the project's settings
  draw();
  $('#dispatch').hidden = false;
  readHarnesses().then(() => { if (!$('#dispatch').hidden && START.draw === draw) draw(); });
}
/* The window's permissions, for the launches it starts only: how the agent's permission prompts are answered,
 * dispatch_prompts, and its harness's own mode, as it offered them at its last session here, `dispatch options`.
 * Each starts at the project's setting and says what that is; approving everything says what it risks. */
async function drawPermissions(agent) {
  const box = $('#dispatch .permissions'), project = S.project;
  if (START.permissionsFor === `${project}:${agent}`) return;
  START.permissionsFor = `${project}:${agent}`;
  START.own.mode = '';  // a mode is the agent's own, so another agent starts at the project's again
  let prompts = null, found = null;
  try { prompts = await read('dispatch-prompts'); } catch { prompts = null; }
  try { found = agent ? (await read('dispatch-options', {agent})).agents?.[0] || null : null; } catch { found = null; }
  if (S.project !== project || START.permissionsFor !== `${project}:${agent}`) return;
  const own = START.own;
  const choices = prompts?.choices || Object.keys(PROMPT_WORDS);
  const promptsPick = h('select', {'aria-label': 'Permission prompts', class: 'prompts',
    onchange: () => { own.prompts = promptsPick.value; sayRisk(); }},
  h('option', {value: ''}, `Project setting: ${prompts ? promptWords(prompts.value) : 'unknown'}`),
  choices.map(choice => h('option', {value: choice, selected: choice === own.prompts},
    promptWords(choice))));
  const setting = (found?.settings || []).find(one => one.key === 'mode');
  const modes = setting?.choices || [];
  const named = value => modes.find(one => one.value === value)?.name || value;
  const projectMode = setting ? setting.chosen ?? setting.current : null;
  const modePick = setting ? h('select', {'aria-label': 'Agent mode', class: 'mode',
    onchange: () => { own.mode = modePick.value; sayRisk(); }},
  h('option', {value: ''}, `Project setting: ${named(projectMode)}`),
  modes.map(one => h('option', {value: one.value, title: one.description || ''}, one.name || one.value))) : null;
  fill(box.querySelector('.controls'), h('label', {class: 'setting'}, h('span', {}, 'Permission prompts'), promptsPick),
    modePick ? h('label', {class: 'setting'}, h('span', {}, 'Mode'), modePick) : null);
  box.querySelector('.hint').textContent = (modePick ? '' : found?.next
    ? `${agentName(agent)} offers its modes once it has run here: ${found.next}. `
    : agent ? `${agentName(agent)} offers no mode to choose. ` : '')
    + 'Left at the project setting, each start follows the settings; a choice here is for the agents this window '
    + 'starts, and the settings stay as they are.';
  const sayRisk = () => {
    const prompting = own.prompts || prompts?.value, mode = own.mode || projectMode;
    const said = [prompting === 'approve-all' ? PROMPT_WORDS['approve-all'][1] : '',
      OPEN_MODES.includes(mode) ? `In ${named(mode)} mode the agent acts without asking: `
        + `${modes.find(one => one.value === mode)?.description || 'it accepts every permission'}.` : '']
      .filter(Boolean);
    const risk = box.querySelector('.risk');
    risk.textContent = said.length ? `${said.join(' ')} Nothing stops a wrong or harmful action.` : '';
    risk.hidden = !said.length;
  };
  sayRisk();
}
/* The permissions chosen for this launch, only those changed from the project's. */
const launchOwn = () => Object.fromEntries(Object.entries(START.own || {}).filter(([, value]) => value));
/* Start all offers the tickets the agent chosen may take, one for each glyph, since a glyph's tickets are one
 * agent's, done one at a time. */
function startable(candidates, agent) {
  const glyphs = new Set();
  return candidates.filter(ticket => {
    if (!allowsAgent(ticket, agent)) return false;
    const glyph = ownGlyph(ticket);
    if (glyph && glyphs.has(glyph)) return false;
    if (glyph) glyphs.add(glyph);
    return true;
  });
}
/* Start all: the agent chosen started on each ticket offered that is not started yet, one after another, up to the
 * agent slots free now; the rest wait in To do, and autostart starts them as slots free. A start that fails can be
 * retried on its own ticket. */
async function startAllTickets(tickets, pick, startAll) {
  if (D.starting) return;
  D.starting = true;
  const agent = pick.value();
  const buttons = [...$('#dispatch .tickets').querySelectorAll('button.start')];
  const offered = tickets.filter((ticket, i) => !buttons[i].disabled);
  startAll.disabled = true;
  pick.hold(true);
  for (const button of buttons) button.disabled = true;
  drawBoard();
  const {free} = await readHarnesses();
  const pending = free === null ? offered : offered.slice(0, free);
  const waiting = offered.length - pending.length;
  for (const ticket of offered.slice(pending.length)) buttons[tickets.indexOf(ticket)].textContent = 'Waiting';
  let started = 0;
  for (const ticket of pending) {
    const button = buttons[tickets.indexOf(ticket)];
    try {
      if (await startAgent(ticket.id, agent, launchOwn())) { started++; button.textContent = 'Starting'; }
      else { button.disabled = false; button.textContent = 'Retry'; }
    } catch (error) { toast(error.message); button.disabled = false; button.textContent = 'Retry'; }
  }
  pick.hold(false);
  D.starting = false;
  startAll.disabled = !buttons.some(button => !button.disabled);
  if (started === pending.length) $('#dispatch').hidden = true;
  toast(`${started} ${agentName(agent)} agent${started === 1 ? '' : 's'} starting.`
    + (started < pending.length ? ` ${pending.length - started} could not start; retry their tickets.` : '')
    + (waiting ? ` ${waiting} wait in To do for a free agent slot; with Autostart agents checked they start as agents`
      + ' finish.' : ''));
  await renderBoard();
}
/* One ticket's Start, for the agent chosen above, unless the ticket's eligible agents leave it out. */
function startButton(ticket, agent, pick) {
  const start = async event => {
    const chosen = pick.value();
    event.target.disabled = true;
    try {
      if (await startAgent(ticket.id, chosen, launchOwn())) { $('#dispatch').hidden = true; await renderBoard(); }
      else event.target.disabled = false;
    } catch (error) { toast(error.message); event.target.disabled = false; }
  };
  return h('button', {class: 'btn primary start', type: 'button', disabled: !agent || !allowsAgent(ticket, agent),
    title: allowsAgent(ticket, agent) ? 'Start the agent chosen above on this ticket'
      : `Eligible agents: ${eligibleAgents(ticket).map(agentName).join(', ')}`, onclick: start}, 'Start');
}
// the start window's tickets, drawn again for the agent chosen, and the permissions chosen for its launches
const START = {draw: null, own: {prompts: '', mode: ''}, permissionsFor: null};
$('#dispatch .close').onclick = () => { $('#dispatch').hidden = true; START.permissionsFor = null; };
overlay($('#dispatch'), {kind: 'dialog', focus: () => $('#dispatch .choice > .btn'),
  close: () => { $('#dispatch').hidden = true; START.draw = null; START.permissionsFor = null; }});
/* The agents key: each agent working in the project now, with its flat icon and in words what it is; a click opens its
 * session's thread. An ended session leaves the key and the map; its log stays in the node's work history, VIEW-036.
 * Sessions are the dispatch module's own tables, never the map. */
export async function renderAgents(only = null) {
  if (FRAMED) return;
  const project = S.project, metaform = S.base, shown = `${project}/${metaform}`;
  // a change that names its tickets reads those tickets alone and merges them in, once the whole has been read here
  const some = Array.isArray(only) && only.length > 0 && D.readFor === shown;
  const {found, claimed} = some ? await readTickets(only) : await readDispatch();
  if (S.project !== project || S.base !== metaform) return;  // the answer for a project the person has left
  if (some) mergeTickets(only, found);
  else {
    D.sessions = found.sessions || [];
    // a login needed is read from the signals, `sessionStatus`, and a spinning or stuck agent's figure circles
    // restlessly, `moodOf`
    D.signals = found.signals || [];
    D.states = found.states || {};  // each session's state, the intake guard's phase among it, `drawIntake`
    D.readFor = shown;
  }
  followStart(D.sessions);
  setupNotice();
  drawAgentSessions();
  drawAgentList();  // the full-size dock's agents, each with its state
  for (const draw of SESSIONS_DRAWN) draw();
  if (!some) D.subagents = found.subagents || [];  // the running sessions' own subagents, each a figure, `childFigures`
  if (claimed) {
    D.claims = claimed.claims || [];
    D.proposals = claimed.proposals || {};
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
    text: [one.work_id, one.agent, glyphOf(one.work_id), workPart(one.work_id), agentName(one.agent)].join('\n'),
    make: () => agentRow(one)})));
  markFollowed();
  agentsWindow(working.length);  // slides out while any is at work, away a few seconds after
  paintInUse();
  figures(S.tickets || []);  // the map's figures follow the same sessions
}
/* A feature the person set up that a module says is not working, dispatch's setup-not-working signal, is the person's
 * system agent's to bring up with them; it takes the signal as its turn. While no system agent runs, one small notice
 * says so in plain words, with the one action that starts it. Closed, it stays away until other findings are raised. */
const SETUP = {closed: null};
function setupNotice() {
  const waiting = D.signals.filter(one => one.signal === 'setup-not-working' && one.active !== false);
  const talking = D.sessions.some(one => one.state === 'running' && D.states[one.session_id]?.about === 'system');
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
  if (G?.graphData().nodes.some(item => item.id === node)) follow3d(node);
  autoZoom2d(node);
}
/* The sessions of the tickets a change named, each ticket read on its own; the claims are not read again, as no
 * session change moves them. A failed read keeps what was drawn. */
async function readTickets(works) {
  const reads = works.map(id => read('dispatch-sessions', {id, thread: 'false'})
    .catch(error => { readFailed(error); return null; }));
  const found = {sessions: [], signals: [], states: {}, subagents: [], failed: []};
  const answers = await Promise.all(reads);
  for (let at = 0; at < works.length; at++) {
    const one = answers[at];
    if (one === null) { found.failed.push(works[at]); continue; }
    found.sessions.push(...(one.sessions || []));
    found.signals.push(...(one.signals || []));
    Object.assign(found.states, one.states || {});
    found.subagents.push(...(one.subagents || []));
  }
  return {found, claimed: null};
}
/* The named tickets' sessions, signals, states and subagents in place of what was read for them before. */
function mergeTickets(works, found) {
  const read = new Set(works.filter(id => !found.failed.includes(id)));
  const theirs = new Set(D.sessions.filter(one => read.has(one.work_id)).map(one => one.session_id));
  D.sessions = D.sessions.filter(one => !read.has(one.work_id)).concat(found.sessions);
  D.signals = (D.signals || []).filter(one => !read.has(one.work_id)).concat(found.signals);
  D.states = Object.assign(D.states || {}, found.states);
  D.subagents = (D.subagents || []).filter(one => !theirs.has(one.parent)).concat(found.subagents);
}
/* The sessions and the claims dispatch holds for the project; the threads are read for the open window only. A failed
 * read keeps the agents drawn as last read. */
async function readDispatch() {
  let found = {sessions: []};
  let claimed = {claims: D.claims || [], proposals: D.proposals || {}};
  if (noMetaform()) return {found, claimed};
  try { found = await read('dispatch-sessions', {thread: 'false'}); }
  catch (error) { readFailed(error); found = {sessions: D.sessions}; }
  try { claimed = await read('dispatch-claims'); } catch (error) { readFailed(error); }
  return {found, claimed};
}
/* One agent at work in the key: whether the part of the map it uses shows in white, its glyph, its name and what it
 * works on, opening its thread, and Chat. */
function agentRow(one) {
  const name = agentName(one.agent);
  const showUse = event => { INUSE.off[event.target.checked ? 'delete' : 'add'](one.work_id); paintInUse(); };
  return h('div', {class: 'agent-row'},
    h('input', {type: 'checkbox', class: 'inuse', checked: !INUSE.off.has(one.work_id),
      'aria-label': `The part of the map ${name} is using`, onchange: showUse,
      title: 'Checked: the part of the map this work is using shows in white. Unchecked: it is hidden.'}),
    h('button', {class: 'agent working', 'data-id': one.work_id, 'data-session': one.session_id,
      title: `${name} on work ${one.work_id}: working`, onclick: () => agentAt(one.work_id, one.session_id)},
    h('img', {src: glyphOf(one.work_id), alt: glyphFor(one.work_id)}), h('b', {}, name),
    h('small', {}, `on ${workPart(one.work_id)} · working`)),
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
  // a thread already open keeps its name and where it comes from: the person's chat about a node and the system agent
  // hang on the same held ticket, and the thread read tells them apart
  const open = session && DOCK.chats.find(one => one.session === session.session_id);
  openHelpdesk(workId, open?.label || `${agentName(session?.agent)} on ${workPart(workId)}`,
    'It answers when its current step ends.', session?.session_id || null, null, {focus: true});
}
