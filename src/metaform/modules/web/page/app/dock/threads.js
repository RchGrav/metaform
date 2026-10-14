/* The chat's threads: their sources and tabs, proposals, the thread bar, subagents, spend, and a ticket's status,
 * cancel and interrupt. */
import '/page/app/dock/embody.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill, keyedFill} from '/page/app/core/dom.js';
import {toast, confirmAct} from '/page/app/core/controls.js';
import {S, read} from '/page/app/core/reads.js';
import {joinOf} from '/page/app/graph/data.js';
import {ROAM, ticketNode} from '/page/app/figures/agents.js';
import {INUSE, idsAt, paintInUse} from '/page/app/map3d/light.js';
import {wake3d} from '/page/app/map3d/graph3d.js';
import {select, MERGE} from '/page/app/selection/select.js';
import {DOCK, SOURCES, sourceOf, sourceChip, dockState, clockOf} from '/page/app/dock/embody.js';
import {drawHelpdesk} from '/page/app/dock/helpdesk.js';
import {stayedOff} from '/page/app/dock/send.js';
import {talkAbout} from '/page/app/dock/commands.js';
import {renderBoard} from '/page/app/board/board.js';
import {wrote} from '/page/app/board/history.js';
import {D, ticketOf, glyphFor, glyphOf, renderAgents} from '/page/app/agents/dispatch.js';
import {agentName} from '/page/app/agents/pickers.js';
import {isIntake, countOf} from '/page/app/session/tools.js';

/* session: the session the thread is with, when it is known. A thread stays with its session, so a later session of
 * the same ticket opens a thread of its own and never swaps the conversation; with none known yet, the thread waits
 * for the ticket's running session and then stays with that one. `source` says where it comes from, `focus` that the
 * person chose it, so its agent and its part are shown on the maps. */
export function openHelpdesk(workId, label = 'an agent', waiting = 'Waiting for the next available agent.',
  session = null, source = null, {focus = false} = {}) {
  const same = DOCK.chats.filter(one => one.target === workId);
  const live = one => !one.session || D.sessions.some(row => row.session_id === one.session && row.state === 'running');
  let chat = session ? DOCK.chats.find(one => one.session === session) || same.find(one => !one.session)
    : same.filter(live).at(-1);
  const kind = source || chat?.source || sourceOf(workId);
  if (chat) Object.assign(chat, {label, waiting, source: kind, ...(session ? {session} : {})});
  else DOCK.chats.push(chat = {target: workId, session, label, waiting, mine: DOCK.mine === workId, since: Date.now(),
    source: kind});
  showChat(chat, {focus});
  if (!$('#dock').className.startsWith('open')) dockState('open');
}
/* Several threads are open at once, each a tab; the one on view is the dock's target, and switching keeps each
 * conversation and its session. A thread the person chooses shows its agent and its part on the maps. */
export function showChat(chat, {focus = false} = {}) {
  const moved = DOCK.chat !== chat;
  Object.assign(DOCK, {chat, target: chat.target, session: chat.session, label: chat.label, waiting: chat.waiting,
    since: chat.since});
  if (moved) { DOCK.pinned = true; DOCK.child = null; }  // another thread opens on its own agent, not a subagent
  MERGE.chat = chat.target;
  dockState($('#dock').className === 'open big' ? 'open big' : 'open');
  drawTabs();
  drawHelpdesk();
  if (focus) focusThread(chat);
}
/* A thread chosen shows where its agent works: its figure stands out among the agents in 3D, and its ticket's part is
 * selected, so both maps move to it. The system agent's held ticket and the intake have no part to show. */
function focusThread(chat) {
  ROAM.focus = chat.target;
  wake3d();
  const ticket = chat.source === 'system' || isIntake(chat.target) ? null : ticketOf(chat.target);
  const key = ticket ? ticketNode(ticket) : null;
  if (key && (S.elements.has(key) || joinOf(key))) select(key, true);
}
/* A sentinel's proposals in its chat, VIEW-045: each with its grounds, its disruption and how much of the map its
 * reach reserves, its benefit and trade-off, a link to its own explanation when it made one, Show on the map, which
 * paints its reach white, and Choose, which tells the sentinel. */
export function drawProposals() {
  const box = $('#helpdesk .proposals'), given = (D.proposals || {})[DOCK.target] || [];
  box.hidden = !given.length;
  const total = S.elements.size;
  fill(box, given.map((one, index) => proposalRow(one, index, total)));
}
function proposalRow(one, index, total) {
  const reach = idsAt(one.reach), on = reach.length && reach.every(id => INUSE.preview.has(id));
  const link = /^https?:\/\//.test(one.view || '')
    ? h('a', {href: one.view, target: '_blank', rel: 'noopener noreferrer'}, 'Its explanation') : null;
  const showReach = () => {
    INUSE.preview = new Set(on ? [] : reach);
    paintInUse(); drawProposals();
  };
  const choose = async () => {
    const text = `I choose proposal ${index + 1}: ${one.title}.`;
    if (await wrote('/api/dispatch-message', {work_id: DOCK.target, session: DOCK.session, text})) {
      INUSE.preview = new Set(); paintInUse(); drawHelpdesk();
    }
  };
  return h('div', {class: 'proposal'},
    h('b', {}, `${index + 1}. ${one.title}`),
    one.grounds ? h('p', {}, h('small', {}, 'Grounds '), one.grounds) : null,
    h('p', {class: 'disruption'}, h('small', {}, 'Disruption '), `Reserves ${reach.length} of ${total} parts`,
      one.disruption ? ` · ${one.disruption}` : ''),
    one.benefit ? h('p', {}, h('small', {}, 'Benefit '), one.benefit) : null,
    one.tradeoff ? h('p', {}, h('small', {}, 'Trade-off '), one.tradeoff) : null,
    h('div', {class: 'acts'}, link,
      h('button', {type: 'button', class: on ? 'reach on' : 'reach', disabled: !reach.length, onclick: showReach},
        on ? 'Hide from the map' : 'Show on the map'),
      h('button', {type: 'button', class: 'choose', onclick: choose}, 'Choose')));
}
export function drawTabs() {
  const tabs = $('#helpdesk .tabs');
  tabs.hidden = DOCK.chats.length < 2;
  fill(tabs, DOCK.chats.map(chat => h('button', {class: chat === DOCK.chat ? 'tab on' : 'tab', role: 'tab',
    'aria-selected': String(chat === DOCK.chat), 'data-source': chat.source, 'data-session': chat.session || '',
    title: `${SOURCES[chat.source] || SOURCES.agent}: ${chat.label}`, onclick: () => showChat(chat, {focus: true})},
    h('i', {class: 'srcdot', 'aria-hidden': 'true'}), chat.label.replace(/^the /, ''))));
}
/* Recovery is attached to the session, never to whichever ticket happens to run next. Dispatch retains the
 * session and its end signals across reloads. A stop made here also keeps its timestamp in this browser, and the
 * dock lists only those stops, until the person forgets the line or the session runs again. */
const stoppedByPerson = session => session?.state !== 'running' && session?.how === 'stopped by the person';
const stopKey = () => `metaform.stopped-agents.${S.project}`;
function stopTimes() { try { return JSON.parse(localStorage.getItem(stopKey()) || '{}'); } catch { return {}; } }
function keepStops(times) {
  try { localStorage.setItem(stopKey(), JSON.stringify(times)); } catch { /* signals remain */ }
}
function rememberStop(session, at) { keepStops({...stopTimes(), [session]: at}); }
function forgetStops(...sessions) {
  const times = stopTimes();
  sessions.forEach(session => delete times[session]);
  keepStops(times);
}
/* How a session ended, in one word: only the person's own stop is "Stopped", the one a Resume brings back. */
function endWord(session) {
  const how = String(session.how || '');
  return stoppedByPerson(session) ? 'Stopped' : how.startsWith('it failed') ? 'Failed'
    : how === 'cancelled by the person' ? 'Cancelled' : 'Ended';
}
function sessionTask(session, state = D.states?.[session.session_id]) {
  const ticket = ticketOf(session.work_id);
  const conversation = state?.about === 'system' ? 'Conversation with your system agent'
    : state?.about ? `Conversation about ${state.about.replace(/^[^:]+:/, '')}`
    : ticket?.held ? 'Conversation' : null;
  return conversation || ticket?.task || ticket?.map?.title || ticket?.note || `ticket ${session.work_id}`;
}
/* The dock holds the stops made in this browser, so the person can bring back an agent stopped by mistake; the Agents
 * menu holds every session, each with how it ended. */
const RESUMED = new Set();
export function drawAgentSessions() {
  const again = D.sessions.filter(one => one.state === 'running' && RESUMED.delete(one.session_id));
  if (again.length) forgetStops(...again.map(one => one.session_id));
  const times = stopTimes(), stopped = D.sessions.filter(one => stoppedByPerson(one) && times[one.session_id]);
  const dock = $('#helpdesk .stopped-agents'), menu = $('#agentbox .agent-sessions');
  dock.hidden = !stopped.length;
  menu.hidden = !D.sessions.length;
  const row = forget => session => ({key: session.session_id,
    text: JSON.stringify([session.state, session.how, agentName(session.agent), glyphOf(session.work_id), sessionTask(session),
      times[session.session_id], D.signals?.filter(one => one.session_id === session.session_id)]),
    make: () => sessionRow(session, forget)});
  keyedFill(dock, stopped.map(row(true)));
  keyedFill(menu, D.sessions.map(row(false)));
}
function sessionRow(session, forget = false) {
  const stopped = stoppedByPerson(session), name = agentName(session.agent), task = sessionTask(session);
  const ended = session.state !== 'running', word = endWord(session);
  const signals = (D.signals || []).filter(one => one.session_id === session.session_id
    && one.reason === session.how && one.at).sort((a, b) => a.at.localeCompare(b.at));
  const at = signals.at(-1)?.at || stopTimes()[session.session_id] || null;
  const open = () => {
    $('#agentbox').hidden = true;
    openHelpdesk(session.work_id, `${name} on ${task}`, '', session.session_id,
      D.states?.[session.session_id]?.about === 'system' ? 'system' : null, {focus: true});
  };
  const resume = async event => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      const done = await wrote('/api/dispatch-resume', {work_id: session.work_id, session: session.session_id});
      if (!done) return;
      RESUMED.add(session.session_id);  // its line goes once it runs again
      open();
      if (done.state !== 'running') DOCK.chat.starting = Date.now();
      toast(`${name} is resuming with its memory.`);
      await renderAgents();
      await drawHelpdesk();
    } finally { button.disabled = false; }
  };
  const how = session.how ? `It ended: ${session.how}.` : 'Its session ended.';
  return h('div', {class: `agent-session${stopped ? ' stopped-agent' : ''}`, 'data-session': session.session_id},
    h('img', {src: glyphOf(session.work_id), alt: glyphFor(session.work_id)}),
    h('div', {class: 'details'}, h('b', {}, name), h('span', {class: 'task'}, task),
      !ended ? h('span', {class: 'meta'}, 'Running')
        : at ? h('time', {datetime: at, title: `${how} ${new Date(at).toLocaleString()}`}, `${word} ${clockOf(at, true)}`)
        : h('span', {class: 'meta', title: how}, stopped ? 'Stopped · time unavailable' : word)),
    h('button', {type: 'button', class: 'btn sm open-chat', onclick: open}, 'Chat'),
    stopped ? h('button', {type: 'button', class: 'btn sm resume', onclick: resume}, 'Resume') : null,
    forget ? h('button', {type: 'button', class: 'btn sm quiet forget', 'aria-label': 'Forget this line',
      title: 'Forget this line; the session stays in the Agents menu',
      onclick: () => { forgetStops(session.session_id); drawAgentSessions(); }}, '×') : null);
}
/* The thread's own bar: the chip of where it comes from, its agent's glyph and its task, Show on map and Stop agent while
 * its session runs. A stopped session has its own Resume row; Continue on a completed ticket starts a conversation. */
export function drawThreadBar(session) {
  const bar = $('#helpdesk .threadbar'), chat = DOCK.chat, target = DOCK.target;
  bar.hidden = !target || !chat;
  if (bar.hidden) return;
  const ticket = isIntake(target) || chat.source === 'system' ? null : ticketOf(target);
  const icon = bar.querySelector('.icon'), withGlyph = chat.source === 'agent' && Boolean(ticket);
  icon.hidden = !withGlyph;
  if (withGlyph && icon.getAttribute('src') !== glyphOf(target)) {
    icon.src = glyphOf(target);
    icon.alt = glyphFor(target);
  }
  // its status is said once, quietly, in the chat's head, `drawHelpdesk`, with the reason a login or a lost runner
  // gives
  fill(bar.querySelector('.source'), sourceChip(chat.source));
  const task = ticket ? ticket.task || ticket.note || ''
    : isIntake(target) ? `The intake of ${S.project}: it records the map as it reads the project.` : '';
  const said = bar.querySelector('.task');
  if (said.textContent !== task) { said.classList.remove('open'); said.textContent = task; }
  said.title = task ? 'Click to show all of the task, and again to fold it' : '';
  const key = ticket ? ticketNode(ticket) : null;
  bar.querySelector('.locate').hidden = !(key && (S.elements.has(key) || joinOf(key)));
  const running = session?.state === 'running', ended = Boolean(session) && !running;
  // a session an editor runs through metaform dispatch serve ends in that editor, BASE-062: no Stop, where it runs
  const inEditor = running && DOCK.state?.editor === true;
  (bar.querySelector('.where') || editorNote(bar)).hidden = !inEditor;
  bar.querySelector('.stop').hidden = !running || inEditor;
  bar.querySelector('.stop').disabled = STOPPING.has(session?.session_id);
  bar.querySelector('.again').hidden = !ended || stoppedByPerson(session) || isIntake(target);
  const cancel = bar.querySelector('.cancel') || cancelButton(bar);
  cancel.hidden = !ticket || Boolean(ticket.done) || chat.source !== 'agent';
  // The person's own chat names its agent in the head. Stop agent remains a separate explicit action.
  const own = ['system', 'conversation'].includes(chat.source);
  bar.querySelector('.source').hidden = own;
  bar.hidden = own && !task && [...bar.querySelectorAll('button')].every(one => one.hidden);
}
/* A session an editor runs through metaform dispatch serve ends in that editor, BASE-062: said where Stop would be. */
function editorNote(bar) {
  const where = h('span', {class: 'where meta', title: 'This session runs in your editor: answer it and end it there.'},
    'In your editor');
  bar.querySelector('.stop').before(where);
  return where;
}
/* Cancel, beside Stop: the ticket closed as cancelled, asked first, never a completion. */
function cancelButton(bar) {
  const cancel = h('button', {class: 'btn sm quiet cancel', type: 'button',
    title: 'Cancel this ticket: its agent stops and the ticket is closed as cancelled, not completed',
    onclick: async () => { const one = ticketOf(DOCK.target); if (one) await cancelTicket(one, cancel); }},
  'Cancel ticket…');
  bar.querySelector('.stop').after(cancel);
  return cancel;
}
/* Stop is session-specific and asks once while a turn or an open ticket is at stake. Closing keeps both intact. */
const STOPPING = new Set();
async function stopThread(event) {
  const button = event.currentTarget, work = DOCK.target, sessionId = DOCK.session;
  if (STOPPING.has(sessionId)) return;
  STOPPING.add(sessionId);
  button.disabled = true;
  try {
    const found = await read('dispatch-sessions', {id: work, thread: 'false'});
    const session = (found.sessions || []).find(one => one.session_id === sessionId);
    if (session?.state !== 'running') return;
    const ticket = ticketOf(work), name = agentName(session.agent);
    const task = sessionTask(session, found.states?.[sessionId]);
    if ((chatActivity(session).busy || ticket && !ticket.done) && !await confirmAct({
      title: `Stop ${name}?`, text: `It is working on ${task}. You can resume it later with its memory.`,
      verb: 'Stop agent', cancel: 'Keep working'})) return;
    const stopped = await wrote('/api/dispatch-stop', {work_id: work, session: sessionId});
    if (!stopped) return;
    rememberStop(sessionId, new Date().toISOString());
    toast(`${name} stopped. Resume its session below or in the Agents menu.${stayedOff(stopped)}`);
    await renderAgents();
    await drawHelpdesk();
  } catch (error) { toast(error.message); }
  finally { STOPPING.delete(sessionId); button.disabled = false; }
}
/* Continue, once a session has ended: an agent that reads the thread first. */
function continueThread() {
  const chat = DOCK.chat;
  if (chat?.session) talkAbout({session: `${chat.target}:${chat.session}`}, chat.label);
}
$('#helpdesk .threadbar .task').onclick = event => event.currentTarget.classList.toggle('open');
$('#helpdesk .threadbar .locate').onclick = () => DOCK.chat && focusThread(DOCK.chat);
$('#helpdesk .threadbar .stop').onclick = stopThread;
$('#helpdesk .threadbar .again').onclick = continueThread;
/* The thread keeps its newest line in view while the person reads its end: it is pinned there until they scroll up. */
function pinLog() {
  const log = $('#helpdesk .log');
  DOCK.pinned = log.scrollTop + log.clientHeight >= log.scrollHeight - 24;
  if (DOCK.pinned) $('#helpdesk .latest').hidden = true;
}
function keepLatest() {
  const log = $('#helpdesk .log');
  if (DOCK.pinned) log.scrollTop = log.scrollHeight;
}
$('#helpdesk .log').addEventListener('scroll', pinLog);
new ResizeObserver(keepLatest).observe($('#helpdesk .log'));
/* A box of the chat made the first time it is drawn, under the session's own bar. */
function underBar(selector, make) {
  let box = $(`#helpdesk ${selector}`);
  if (!box) { box = make(); $('#helpdesk .sessionbar').after(box); }
  return box;
}
/* The subagents of the session on view, P016: each a child session with its own thread, opened in place and back to
 * its parent, so the person follows the parent and every child it started from one chat. */
export function drawSubagents() {
  const box = underBar('.subagents',
    () => h('div', {class: 'subagents', role: 'group', 'aria-label': 'Subagents of this session'}));
  const kids = DOCK.subagents || [];
  box.hidden = !kids.length;
  if (!kids.length) return fill(box);
  const open = DOCK.child;
  fill(box, h('span', {class: 'eyebrow'}, `Subagents · ${kids.length}`),
    open ? h('button', {class: 'btn sm quiet', type: 'button', title: 'Back to the thread of the agent that started it',
      onclick: () => { DOCK.child = null; drawHelpdesk(); }},
    h('i', {class: 'i i-back', 'aria-hidden': 'true'}), 'Parent') : null,
    kids.map(kid => subagentButton(kid, open)));
}
/* One child session: opened in place, or closed back to its parent; its status beside its name. */
function subagentButton(kid, open) {
  const on = kid.session_id === open;
  return h('button', {class: `btn sm${on ? ' primary' : ''}`, type: 'button', 'aria-pressed': String(on),
    title: [kid.description || kid.prompt || '', `Session ${kid.session_id}`].filter(Boolean).join(' · '),
    onclick: () => { DOCK.child = on ? null : kid.session_id; drawHelpdesk(); }},
  kid.name || kid.title || kid.agent || 'Subagent',
  statusChip(kid.state ? sessionStatus({...kid, work_id: DOCK.target}) : null));
}
/* What the ticket on view has spent today, as dispatch spend reads it against the budgets, M01; read again at most
 * every few seconds while the chat is drawn. */
const SPEND = {work: null, at: 0, data: null};
export async function drawSpend(work) {
  const box = underBar('.spend', () => h('div', {class: 'spend', role: 'status'}));
  // a ticket's agent only: the person's own chat holds a ticket of its own that nobody reads as work
  if (!work || isIntake(work) || ['system', 'conversation'].includes(DOCK.chat?.source)) { box.hidden = true; return; }
  if (SPEND.work !== work || Date.now() - SPEND.at > 5000) {
    SPEND.work = work; SPEND.at = Date.now();
    try { SPEND.data = await read('dispatch-spend', {id: work}); } catch { SPEND.data = null; }
  }
  const ticket = SPEND.data?.ticket;
  box.hidden = !ticket;
  if (!ticket || work !== DOCK.target) return;
  const budgets = ticket.budgets || {};
  const tokens = `${countOf(ticket.tokens || 0)} tokens${budgets.ticket ? ` of ${countOf(budgets.ticket)}` : ''}`;
  const cost = ticket.cost !== null && ticket.cost !== undefined && ticket.currency
    ? ` · ${ticket.currency === 'USD' ? '$' : `${ticket.currency} `}${Number(ticket.cost).toFixed(2)}` : '';
  const blind = (ticket.unmetered?.tokens || []).length ? ' · some sessions report no usage' : '';
  fill(box, h('span', {class: 'eyebrow'}, 'Spent on this ticket'), ` ${tokens}${cost}${blind}`);
  box.title = SPEND.data.measure || '';
}
/* One status for a ticket and its agent, as data/status.py names it for every surface, with the reason the person
 * needs: a cancelled ticket is never shown as completed, a login only the person can give is not an ordinary wait,
 * and a runner that is gone is not an agent at work. {state, reason, words, why}. */
export function sessionStatus(session, signals = D.signals || []) {
  if (!session) return null;
  const agent = agentName(session.agent), how = String(session.how || '');
  const login = signals.some(one => one.signal === 'login-needed' && one.active !== false
    && (one.session_id === session.session_id || (!one.session_id && one.work_id === session.work_id)));
  if (login || /needs a login/.test(how)) {
    return {state: 'input_required', reason: 'login', words: 'Needs a login',
      why: `${agent} needs a login, which only you can give: metaform dispatch login ${session.agent || ''}`.trim()};
  }
  if (session.state === 'running') {
    if (session.waiting_on === 'permission') {
      return {state: 'input_required', reason: 'permission', words: 'Needs your permission',
        why: "Its request is in the thread, with the agent's own choices."};
    }
    if (session.waiting_on === 'question') {
      return {state: 'input_required', reason: 'question', words: 'Needs your answer',
        why: 'Its question is in the thread.'};
    }
    if (session.activity === 'working') {
      return {state: 'running', reason: 'working', words: 'Working', why: `${agent} is working a turn.`};
    }
    return {state: 'running', reason: 'idle', words: 'Ready',
      why: `${agent}'s turn has ended; it reads your next message.`};
  }
  if (/runner is no longer|no longer listening|another session|runner of another/.test(how)) {
    return {state: 'failed', reason: 'dead', words: 'Runner gone',
      why: `Its runner stopped: ${how}. The ticket goes back to the board for another agent.`};
  }
  if (/ticket is done/.test(how)) {
    return {state: 'completed', reason: 'done', words: 'Ended', why: 'Its ticket is done.'};
  }
  return {state: 'submitted', reason: 'ended', words: 'Ended', why: how ? `It ended: ${how}.` : 'Its session ended.'};
}
export function ticketStatus(ticket) {
  if (!ticket) return null;
  if (ticket.done) {
    const outcome = ticket.outcome || 'completed';
    const words = {completed: 'Completed', cancelled: 'Cancelled', failed: 'Failed'}[outcome] || outcome;
    return {state: outcome, reason: outcome, words,
      why: ticket.resolution || (outcome === 'cancelled' ? 'Cancelled by the person, not completed.' : '')};
  }
  const session = D.sessions.filter(one => one.work_id === ticket.id).at(-1);
  return session ? sessionStatus(session) : null;
}
export function statusChip(status) {
  if (!status) return null;
  return h('span', {class: `statechip ${status.state} ${status.reason || ''}`, title: status.why || status.words,
    'aria-label': `${status.words}${status.why ? `: ${status.why}` : ''}`}, status.words);
}
/* Cancel a ticket, the person's own: asked first with an optional reason; dispatch cancel stops its agent's turn with
 * session/cancel as the person's own stop, so nothing retries it, and closes the ticket as cancelled, never completed.
 */
export async function cancelTicket(ticket, button = null) {
  const reason = h('input', {type: 'text', class: 'reason', placeholder: 'Why (optional), kept as its resolution',
    'aria-label': 'Why it is cancelled', autocomplete: 'off'});
  const sure = await confirmAct({title: 'Cancel this ticket?', verb: 'Cancel ticket', cancel: 'Keep it',
    text: [ticket.taken ? 'The agent working it is stopped, and nothing retries it.' : 'No agent has taken it.',
      reason],
    lost: ['The ticket stays on the board only in Done, marked cancelled, not completed.']});
  if (!sure) return false;
  if (button) button.disabled = true;
  const done = await wrote('/api/dispatch-cancel', {work_id: ticket.id, reason: reason.value.trim()});
  if (done) {
    toast('Ticket cancelled.');
    await renderAgents();
    if (!$('#board').hidden) await renderBoard();
  } else if (button) button.disabled = false;
  return Boolean(done);
}
export function chatActivity(session) {
  if (!session) return {label: 'Connecting', busy: false, interruptible: false};
  if (session.state !== 'running') return {label: 'Ended', busy: false, interruptible: false};
  const busy = session.activity === 'working' || session.activity === 'waiting';
  const label = session.interrupting ? 'Interrupting'
    : session.activity === 'waiting' && session.waiting_on === 'question' ? 'Waiting for your answer'
    : ({working: 'Busy', waiting: 'Waiting for permission', idle: 'Ready'}[session.activity] || 'Status unavailable');
  const note = session.interrupting ? 'Interrupting the current task.'
    : session.activity === 'working'
      ? 'Agent is working on a task. A message is read when its current step ends; Interrupt stops the step.'
    : session.activity === 'waiting' && session.waiting_on === 'question'
      ? 'Waiting for your answer: its question is in the thread.'
    : session.activity === 'waiting'
      ? "Waiting for your permission: its request is in the thread, with the agent's own choices." : '';
  return {label, note, busy, interruptible: busy && !session.interrupting};
}
export async function interruptChat(work, session, button) {
  button.disabled = true;
  const result = await wrote('/api/dispatch-interrupt', {work_id: work, session});
  if (result) toast(result.requested ? 'Interruption requested.' : 'The agent has no active turn.');
  await renderAgents();
  if (DOCK.target) await drawHelpdesk();
}
