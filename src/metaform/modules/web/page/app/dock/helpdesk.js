/* The chat on view as ACP gives it, drawHelpdesk, following its newest line, putting it away and growing it back
 * from its tab, and the questions asked at a ticket's node. */
import '/page/app/dock/threads.js';  // the part before runs first, so the parts run in the page's order
import {$, reduced, h, keepFill, keyedFill} from '/page/app/core/dom.js';
import {expandCut} from '/page/app/core/expand.js';
import {toast} from '/page/app/core/controls.js';
import {read} from '/page/app/core/reads.js';
import {ticketNode} from '/page/app/figures/agents.js';
import {mascotHeard} from '/page/app/figures/ask.js';
import {EASE} from '/page/app/camera/fly3d.js';
import {asked} from '/page/app/selection/select.js';
import {DOCK, clockOf, STANDBY, DOCKMOTION, dockGoingAway, embodyOffer, embodyRows,
  dockState} from '/page/app/dock/embody.js';
import {showChat, drawProposals, drawTabs, drawThreadBar, drawSubagents, drawSpend, sessionStatus,
  chatActivity, drawAgentSessions} from '/page/app/dock/threads.js';
import {queuedRows, deliverQueued, startFailed} from '/page/app/dock/send.js';
import {messagesOf} from '/page/app/board/messages.js';
import {D, ticketOf, agentAt} from '/page/app/agents/dispatch.js';
import {agentName, summonAgent, drawDockTab} from '/page/app/agents/pickers.js';
import {isIntake, workPart, isSystemState} from '/page/app/session/tools.js';
import {galleryRows, threadRows} from '/page/app/session/apps.js';
import {drawPlan, drawSession} from '/page/app/session/text.js';
import {notificationState, drawAssignment} from '/page/app/session/orchestration.js';
import {SESSIONPOP} from '/page/app/session/settings.js';
import {openIntakeChat} from '/page/app/intake/intake.js';
import {chatDocked} from '/page/app/workspace/workspace.js';

/* The chat on view, as ACP gives it: its settings and usage in the session bar, its plan as a checklist, and its
 * thread, the conversation with the agent's tool calls and permission requests in it. With no chat on view, what
 * waits for the person's permission elsewhere is listed, each with Open. */
let DRAWS = 0;  // the draws begun, so a read that lands after a later one's is let go
export async function drawHelpdesk(trouble) {
  let lines = [], session = null, state = null;
  const target = DOCK.target, draw = ++DRAWS;
  if (target) {
    try {
      const read = await readThread(target, DOCK.session, DOCK.chat, draw);
      if (read.moved) return;  // the chat moved on while this was read
      if (read.other) return showChat(read.other);
      ({lines, session, state} = read);
    } catch (error) { trouble = error.message; }
  } else DOCK.subagents = [];
  drawSubagents();
  drawSpend(target);
  DOCK.state = state;
  DOCK.agent = session?.agent || null;
  DOCK.live = session?.state === 'running';
  drawThreadBar(session);
  drawAgentSessions();
  const notification = notificationState(state);
  $('#helpdesk .call').hidden = notification || Boolean(DOCK.live || DOCK.calling);
  $('#helpdesk .compose').hidden = notification;
  $('#helpdesk .calls').hidden = notification;
  drawAsked(target, session, lines);
  mascotHeard(target, lines);  // the system agent's answer to the mascot, said in its bubble too
  drawProposals();
  drawSession($('#helpdesk .sessionbar'), {work: target, session, state});
  drawAssignment($('#helpdesk .assignmentbox'), state, agentAt);
  drawPlan($('#helpdesk .planbox'), target ? state?.plan : null);
  const activity = chatActivity(session);
  const waiting = DOCK.target && !session;
  const busy = DOCK.target && activity.busy && session?.activity !== 'waiting';
  embodyOffer(target, session, lines, busy);  // a body for this chat's agent on the map, offered at a pause
  const connecting = Boolean(DOCK.calling) || (DOCK.target && !session);
  chatHead(session, activity, busy, connecting);
  const log = $('#helpdesk .log');
  const changed = keyedFill(log, [
    ...introRows(),
    ...askingRows(),
    ...begunRows(session),
    ...DOCK.notes.filter(note => note.at >= DOCK.since - 1)
      .map((note, index) => systemRow(`note:${note.at}:${index}`, note.text)),
    ...threadRows(lines, {work: target, agent: session?.agent, session}),
    ...queuedRows(),
    ...embodyRows(target),
    ...galleryRows(),
    ...typingRows(session, activity, waiting, busy, connecting),
    ...(trouble ? [systemRow('trouble', trouble)] : [])]);
  if (changed) followLog();
  if (changed && $('#helpdesk').hidden && lines.some(line => line.kind === 'agent_message_chunk')) markUnread();
  deliverQueued(session);  // what was written while the agent was being reached, sent once it is there
  chatAway(session, changed);
  D.onAsking?.();  // the thread on screen changed: the pop-up leaves its requests to it, agents/asking.js
}
/* The thread on view as dispatch reads it: its session, the running one or the one it is with, its state and its
 * lines, or a child session's lines when one is open. `moved` when the chat moved on while this was read, or a later
 * draw began, whose read is the newer and draws instead; reads land in any order, and one that lands last is not
 * newest; `other` when a waiting thread finds its session already open in another tab, which it gives way to. */
async function readThread(target, openedSession, chat, draw) {
  const found = await read('dispatch-sessions', {id: target,
    ...(openedSession ? {session: openedSession} : {latest: 'true'})});
  if (DOCK.target !== target || DOCK.session !== openedSession || draw !== DRAWS) return {moved: true};
  const sessions = found.sessions || [];
  let session = DOCK.session ? sessions.find(one => one.session_id === DOCK.session)
    : sessions.filter(one => one.state === 'running').at(-1);
  // a thread waiting for its agent whose start failed takes that session, so it says why instead of waiting on
  let failed = null;
  if (!session && !DOCK.session && chat) {
    failed = sessions.filter(one => one.state !== 'running' && /^it (failed|did not start)/.test(one.how || '')
      && Date.parse(one.started || '') >= chat.since - 5000).at(-1) || null;
    session = failed;
  }
  let state = null;
  if (session) {
    const other = DOCK.chats.find(one => one !== chat && one.session === session.session_id);
    if (other && chat && !chat.session) {
      DOCK.chats = DOCK.chats.filter(one => one !== chat);
      return {other};
    }
    DOCK.session = session.session_id;
    if (chat) chat.session = session.session_id;
    if (chat && session.state === 'running') chat.starting = 0;  // reached: it reads what waits for it
    state = (found.states || {})[session.session_id] || null;
    knownAsSystem(chat, state);
    if (failed) {
      startFailed(`${agentName(failed.agent)} did not start: `
        + String(failed.how).replace(/^it (failed|did not start):?\s*/, ''), null,
      chat.target === DOCK.mine || chat.source === 'system');
    }
  }
  let lines = session ? (found.lines || []).filter(line => line.session_id === session.session_id) : [];
  // the subagents this session started, each a child thread of its own; one opened shows its own lines
  DOCK.subagents = session ? (found.subagents || []).filter(one => one.parent === session.session_id) : [];
  const child = DOCK.child && DOCK.subagents.find(one => one.session_id === DOCK.child);
  if (child) lines = child.lines || [];
  else DOCK.child = null;
  return {lines, session, state};
}
/* The system agent is known by what its session is about, however it was started: by the page, the phone or the
 * command line. A conversation about a node hangs on the same held ticket and stays the person's chat. */
function knownAsSystem(chat, state) {
  if (chat && notificationState(state)) {
    Object.assign(chat, {source: 'notification', label: state.title || state.about || 'Project updates'});
    DOCK.label = chat.label;
    return;
  }
  if (!chat || !isSystemState(state, chat.target) || chat.source === 'system') return;
  Object.assign(chat, {source: 'system', label: 'your system agent'});
  DOCK.label = chat.label;
  drawTabs();
}
/* One quiet status in the head, on the line that says whom the chat is with: a login only the person gives and a lost
 * runner said as such, else what the agent is doing; its dot takes the state's color. Whom the chat is with is its
 * title; the line under it then says only what it is doing. */
function chatHead(session, activity, busy, connecting) {
  const notification = notificationState(DOCK.state);
  const told = session ? sessionStatus(session) : null;
  const special = told && ['login', 'dead', 'restarting'].includes(told.reason);
  const status = $('#helpdesk .status');
  status.textContent = notification ? 'Updates' : special ? told.words : session ? activity.label : connecting ? 'Connecting' : '';
  status.title = special ? told.why : session ? activity.note || activity.label
    : connecting ? DOCK.waiting || STANDBY : '';
  status.hidden = !status.textContent;
  $('#helpdesk .head').dataset.state = special ? told.reason : connecting ? 'connecting' : !session ? 'none'
    : session.state !== 'running' ? 'ended' : session.activity === 'waiting' ? 'asks' : busy ? 'working' : 'ready';
  $('#helpdesk').classList.toggle('asks', Boolean(session && session.activity === 'waiting'));
  $('#helpdesk .interrupt').disabled = notification || !DOCK.target || !activity.interruptible;
  $('#helpdesk .interrupt').hidden = notification || !DOCK.target || !(activity.interruptible || session?.interrupting);
  $('#helpdesk .with').textContent = DOCK.target ? `With ${DOCK.label}` : 'Online';
  const named = DOCK.target ? String(DOCK.label || 'an agent').replace(/^the /, '') : '';
  $('#helpdesk .who .title').textContent = named ? named[0].toUpperCase() + named.slice(1) : 'Metaform Support';
  $('#helpdesk .with').classList.toggle('visually-hidden', Boolean(DOCK.target || DOCK.calling) && !status.hidden);
}
const systemRow = (key, text) => ({key, text, make: () => h('div', {class: 'system'}, text)});
/* With nothing on view, the chat says what it is and how to start, once, as an empty conversation does. */
function introRows() {
  if (DOCK.target || DOCK.calling || DOCK.queue.length) return [];
  return [{key: 'intro', text: summonAgent() || '', make: () => h('div', {class: 'empty'},
    h('b', {}, 'Metaform Support'),
    h('p', {}, 'Write a message and press Enter: your system agent starts and reads it. '
      + "Type / for the chat's commands."),
    h('p', {class: 'hint'}, h('kbd', {}, 'C'), ' opens and puts it away · ', h('kbd', {}, '?'), ' every key'))}];
}
/* The conversation's start, with its agent and when, above its first line. */
function begunRows(session) {
  if (!session) return [];
  const said = `${agentName(session.agent)}${session.started ? ` · ${clockOf(session.started, true)}` : ''}`;
  return [{key: `start:${session.session_id}`, text: session.started || '',
    make: () => h('div', {class: 'system begun'}, said)}];
}
/* With no chat on view, each agent waiting for the person's permission or answer, with Open, so the dock's count
 * leads somewhere. */
function askingRows() {
  if (DOCK.target) return [];
  return (D.asking || []).map(one => ({key: `asks:${one.work_id}:${one.request}`, text: `${one.work_id}\n${one.tool}`,
    make: () => {
      const who = `${agentName(one.agent)} on ${workPart(one.work_id)}`;
      const open = () => isIntake(one.work_id) ? openIntakeChat(one.work_id, one.session_id)
        : agentAt(one.work_id, one.session_id);
      return h('div', {class: 'system asking'}, one.signal === 'question-waiting'
        ? `${who} asks: ${one.question || 'a question'}` : `${who} asks to ${one.tool || 'use a tool'}.`,
      h('button', {class: 'btn sm primary', type: 'button', onclick: open}, 'Open'));
    }}));
}
/* The agent at work, said as a quiet typing row where its next words will come, its fuller note on hover. */
function typingRows(session, activity, waiting, busy, connecting) {
  if (!(waiting || busy || (DOCK.calling && !DOCK.target))) return [];
  const doing = waiting || connecting ? DOCK.waiting || STANDBY : `${agentName(session?.agent)} is working`;
  return [{key: 'waiting', text: doing, make: () => h('div',
    {class: 'waiting typingrow', role: 'status', title: activity.note || ''},
    h('span', {class: 'typing', 'aria-hidden': 'true'}, h('i'), h('i'), h('i')), h('span', {class: 'said'}, doing))}];
}
/* The thread follows its newest line while the person reads its end; scrolled up to read, it stays put and a quiet
 * "New messages" button below says something came, which a click, or Alt+End, goes to. */
export function followLog(force = false) {
  const log = $('#helpdesk .log');
  if (force) DOCK.pinned = true;
  const latest = $('#helpdesk .latest');
  if (DOCK.pinned) { log.scrollTop = log.scrollHeight; latest.hidden = true; return; }
  // just above the box
  latest.style.bottom = `${$('#helpdesk').getBoundingClientRect().bottom - log.getBoundingClientRect().bottom + 10}px`;
  latest.hidden = false;
}
$('#helpdesk .latest').onclick = () => { followLog(true); $('#helpdesk .say').focus({preventScroll: true}); };
// a tool call's title cut short opens in place at a click, or shows whole while a call with more to show is open
expandCut($('#helpdesk .log'), {row: '.tool', text: '.toolhead .title'});
/* What came while the chat was put away: a dot on its tab, cleared as it opens. */
function markUnread() {
  const fresh = !DOCK.unread;
  DOCK.unread = true;
  drawDockTab();
  if (fresh) flashDockTab();
}
/* The chat's tab flashes once for a message that came while the chat is put away, not again until it is read. */
function flashDockTab() {
  const tab = $('#dockTab');
  tab.classList.remove('flash');
  void tab.offsetWidth;  // a flash already running starts again
  tab.classList.add('flash');
  tab.addEventListener('animationend', () => tab.classList.remove('flash'), {once: true});
}
/* The chat puts itself away 15 seconds after its agent is gone or its session has ended:
 * it eases away and leaves no gap, and its threads are kept, so opening it again shows the conversation. The count
 * waits while the person types in it, has the focus in it or the pointer over it; a line arriving or the agent back,
 * a resume, stops it. The close × in its head and C put it away at any time; Escape never does, escapeChat. In a workspace pane it stays open until explicitly closed. */
const CHAT_AWAY = {timer: 0, for: null, had: false, held: false, wait: 15000};
function chatAway(session, changed = false) {
  const open = $('#dock').className.startsWith('open') && !chatDocked();
  if (session?.state === 'running') CHAT_AWAY.had = true;
  const gone = open && CHAT_AWAY.had && (session ? session.state !== 'running' : !DOCK.target);
  if (!gone || changed) {
    clearTimeout(CHAT_AWAY.timer);
    CHAT_AWAY.timer = 0; CHAT_AWAY.for = null; CHAT_AWAY.held = false;
    if (!gone) return;
  }
  const key = session?.session_id || 'none';
  if (CHAT_AWAY.for === key && CHAT_AWAY.timer) return;
  CHAT_AWAY.for = key;
  clearTimeout(CHAT_AWAY.timer);
  CHAT_AWAY.timer = setTimeout(awayNow, CHAT_AWAY.wait);
}
const chatHeld = box => box.contains(document.activeElement) || box.matches(':hover') ||
  Boolean($('#helpdesk .say')?.value.trim());
function awayNow() {
  CHAT_AWAY.timer = 0;
  if (chatHeld($('#helpdesk'))) { CHAT_AWAY.held = true; return; }  // the count starts again when the person leaves it
  CHAT_AWAY.had = false;
  putChatAway();
}
/* The person leaving the chat, by focus, pointer or emptying what they typed, starts the put-away count again, once. */
function chatLeft() {
  if (!CHAT_AWAY.held) return;
  requestAnimationFrame(() => {  // after the focus has moved on
    if (!CHAT_AWAY.held || chatHeld($('#helpdesk'))) return;
    CHAT_AWAY.held = false;
    CHAT_AWAY.timer = setTimeout(awayNow, CHAT_AWAY.wait);
  });
}
for (const type of ['focusout', 'mouseleave', 'input']) $('#helpdesk').addEventListener(type, chatLeft);
/* Put away and opened again, the chat shrinks and fades into its tab and grows back out of it along the same path:
 * only a transform, a translation and a scale about the tab's middle, and its opacity, so its own size and place,
 * as moved and sized, are exactly what they were. Away leaves on the leaving curve, back arrives on the arriving one,
 * each about 260 to 340 ms by the way it travels; one interrupted turns back from where it is. The tab answers with
 * a small pulse as the chat lands in it. Under reduced motion only the opacity changes. The close ×, C and the
 * put-away after an agent leaves all go this way, as a chat docked at a side does. */
export function launcherRect() {
  const dock = $('#dock');
  dock.classList.add('measure');  // the tab, laid out where it rests but not shown, to be measured
  const rect = $('#dockTab').getBoundingClientRect();
  dock.classList.remove('measure');
  return rect;
}
function towardsTab(panel, tab) {
  const sx = Math.max(0.02, tab.width / panel.width), sy = Math.max(0.02, tab.height / panel.height);
  const ox = tab.left + tab.width / 2 - panel.left, oy = tab.top + tab.height / 2 - panel.top;  // the tab's middle
  const moved = `translate(${(ox - panel.width / 2) * sx}px, ${(oy - panel.height / 2) * sy}px)`;
  return {transform: `${moved} scale(${sx}, ${sy})`, origin: `${ox}px ${oy}px`,
    travel: Math.hypot(ox - panel.width / 2, oy - panel.height / 2)};
}
export const dockCurve = name => `cubic-bezier(${EASE[name].join(',')})`;
function moveDock(dir, tab) {
  const box = $('#helpdesk'), panel = box.getBoundingClientRect(), path = towardsTab(panel, tab);
  const still = reduced(), duration = still ? 140 : Math.round(Math.min(340, 260 + path.travel * 0.06));
  const shut = still ? {opacity: 0} : {transform: path.transform, opacity: 0.12};
  const full = still ? {opacity: 1} : {transform: 'none', opacity: 1};
  DOCKMOTION.anim?.cancel();
  // on its way out the focus leaves it, so C, or a click on the page, can call it back before it lands
  if (dir === 'away' && box.contains(document.activeElement)) document.activeElement.blur();
  Object.assign(box.style, {transformOrigin: path.origin, willChange: still ? 'opacity' : 'transform, opacity'});
  const anim = box.animate(dir === 'away' ? [full, shut] : [shut, full],
    {duration, easing: dockCurve(dir === 'away' ? 'leave' : 'arrive'), fill: 'both'});
  Object.assign(DOCKMOTION, {anim, dir});
  $('#dockTab').classList.toggle('launch', dir === 'back');  // the tab, not the dock, whose class is its state
  anim.onfinish = () => dockLanded(anim, still);
}
/* The move done: put away, the dock rests and its tab answers with a pulse and takes the focus; back, the message box
 * takes it. A move turned back by another is that one's to finish. */
function dockLanded(anim, still) {
  if (DOCKMOTION.anim !== anim) return;
  const away = (DOCKMOTION.dir === 'away') === (anim.playbackRate > 0);
  Object.assign(DOCKMOTION, {anim: null, dir: null});
  $('#dockTab').classList.remove('launch');
  if (away && $('#dock').className.startsWith('open')) {
    dockState('resting');
    const launcher = $('#dockTab');
    const pulse = [{scale: '1'}, {scale: '1.08'}, {scale: '1'}];
    if (!still) launcher.animate(pulse, {duration: 360, easing: dockCurve('arrive')});
    launcher.focus({preventScroll: true});
  } else if (!away) $('#helpdesk .say').focus({preventScroll: true});
  anim.cancel();
  Object.assign($('#helpdesk').style, {transformOrigin: '', willChange: ''});
}
export function reverseDock() {
  const anim = DOCKMOTION.anim;
  if (!anim) return;
  anim.reverse();  // from where it is, back the way it came
  $('#dockTab').classList.toggle('launch', (DOCKMOTION.dir === 'back') === (anim.playbackRate > 0));
}
export function growFrom(tab) { moveDock('back', tab); }
export function putChatAway() {
  const box = $('#helpdesk');
  if (box.hidden) return;
  if (chatDocked()) { box.hidden = true; return; }
  if (DOCKMOTION.anim) {  // on its way out of the tab: it turns back
    if (!dockGoingAway()) reverseDock();
    return;
  }
  $('#dockMenu').hidden = true;
  if (SESSIONPOP.el) SESSIONPOP.el.hidden = true;
  moveDock('away', launcherRect());
}
/* The open questions an agent at work on a ticket asked at its node, answered as every question is, VIEW-021; a
 * permission request is answered from its own card in the thread, so its question at the node is not shown again. */
const ASKED = {drawn: new Map(), session: null};
async function drawAsked(target, session, lines) {
  const ticket = target && !isIntake(target) ? ticketOf(target) : null, sessionId = session?.session_id || null;
  let open = [];
  if (ticket && sessionId && DOCK.chat?.source === 'agent') {
    const by = `${session.agent} ${sessionId}`;
    const askedHere = record => record.kind === 'question' && record.by === by;
    try { open = (await messagesOf(ticketNode(ticket))).unread.filter(askedHere); }
    catch (error) { toast(error.message); }
  }
  if (DOCK.target !== target || DOCK.session !== sessionId && sessionId) return;
  const permits = new Set(lines.filter(line => line.kind === 'permission').map(line => line.data?.message_id)
    .filter(Boolean));
  open = open.filter(record => !permits.has(record.id));
  const kept = ASKED.session === sessionId ? ASKED.drawn : new Map();
  ASKED.drawn = new Map(open.map(record => [record.id, kept.get(record.id) || asked(record)]));
  ASKED.session = sessionId;
  keepFill($('#helpdesk .asked'), [...ASKED.drawn.values()]);
}
