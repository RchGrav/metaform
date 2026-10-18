/* Sending from the chat: the agent started when none is there, queued messages, failures said in the chat, closing,
 * resume and stay connected, the chat's keys, menu and message box. */
import '/page/app/dock/commands.js';  // the part before runs first, so the parts run in the page's order
// speech to text in the boxes a person writes to agents in, the voice module
import {voiceAudio} from '/page/voice.js';
import {$, reduced, h, fill} from '/page/app/core/dom.js';
import {FOCUSABLE, overlay} from '/page/app/core/overlays.js';
import {toast} from '/page/app/core/controls.js';
import {S, read} from '/page/app/core/reads.js';
import {joinOf} from '/page/app/graph/data.js';
import {MAC} from '/page/app/map2d/camera.js';
import {openHelp} from '/page/app/keys/keys.js';
import {DOCK, embodyHooks, embodiable, askEmbody, dockState, dockNote} from '/page/app/dock/embody.js';
import {drawTabs, interruptChat, onOther, showMine, listShown} from '/page/app/dock/threads.js';
import {drawHelpdesk, followLog, putChatAway} from '/page/app/dock/helpdesk.js';
import {dockCommand, callSystem, talkAbout} from '/page/app/dock/commands.js';
import {narrowPage, resetDock} from '/page/app/dock/place.js';
import {wrote} from '/page/app/board/history.js';
import {isIntake} from '/page/app/session/tools.js';
import {showGallery, takeContext, withContext, contextBack} from '/page/app/session/apps.js';
import {messageRow} from '/page/app/session/text.js';
import {notificationState} from '/page/app/session/orchestration.js';
import {sessionPop} from '/page/app/session/settings.js';
import {posted} from '/page/app/intake/intake.js';
import {sharing, startShare, shareFrame, CLICKED, clickedLine} from '/page/app/figures/eyes.js';

/* A start that answered before its session runs: a resume names its session at once, though the session is live only
 * once the resume is done. Until then the thread is being reached, and a message written meanwhile waits for it and
 * starts nothing more; a start that never comes is given up after a minute and a half. */
export function reaching(started) {
  if (DOCK.chat && DOCK.chat.target === started.work_id) {
    DOCK.chat.starting = started.state === 'running' ? 0 : Date.now();
  }
}
const beingReached = chat => Boolean(chat?.starting) && Date.now() - chat.starting < 90000;
/* Sending with no agent there starts one, as Call does, or, on a thread whose agent has ended, as Continue does; the
 * message waits in the thread, marked as waiting, and goes as the first message once the session is there, after a
 * resume has finished. What is written meanwhile waits behind it, in order. */
function ensureAgent() {
  if (notificationState(DOCK.state)) return;
  // being reached already
  if (DOCK.calling || DOCK.talking || (DOCK.target && !DOCK.session) || beingReached(DOCK.chat)) return;
  if (!DOCK.target) { callSystem(); return; }
  if (DOCK.live) return;
  const chat = DOCK.chat;
  if (!chat || isIntake(chat.target)) {
    startFailed('This conversation has ended; an intake is not taken up again from here.');
    return;
  }
  if (chat.source === 'system' || chat.target === DOCK.mine && chat.source !== 'conversation') { callSystem(); return; }
  talkAbout({session: `${chat.target}:${chat.session}`}, chat.label);
}
export function queuedRows() {
  // a message sent is let go once the agent has it, or half a minute on
  const settled = item => item.state === 'sent'
    && (DOCK.heard.has((item.sent || item.text).trim()) || Date.now() - item.at > 30000);
  DOCK.queue = DOCK.queue.filter(item => !settled(item));
  return DOCK.queue.map((item, index) => ({key: `queued:${item.id}`, text: `${item.state}:${index}`,
    make: () => messageRow(item.text, {mine: true, who: 'You', first: index === 0, at: item.at,
      pending: {waiting: 'Sent once the agent is there', sending: 'Sending…', sent: 'Sent'}[item.state] || ''})}));
}
let QUEUE_ID = 0;
export async function deliverQueued(session) {
  if (DOCK.delivering || DOCK.calling || session?.state !== 'running' || session.session_id !== DOCK.session
    || !DOCK.queue.some(one => one.state === 'waiting')) return;
  const work = DOCK.target;
  DOCK.delivering = true;
  try {
    for (const item of DOCK.queue.filter(one => one.state === 'waiting')) {
      if (DOCK.target !== work) return;
      item.state = 'sending';
      const lead = item.clicked ? `${item.clicked}\n\n` : '';  // what the person clicked stays first
      // the view's context goes to the agent only; the item keeps the person's own words, so a failed send puts back
      // what they wrote and nothing more
      const taken = takeContext({work, session: session.session_id});
      const said = lead + withContext(taken, item.text.slice(lead.length));
      item.sent = said;  // as the agent got it, which its thread echoes back
      const done = await posted('/api/dispatch-message', {work_id: work, session: session.session_id, text: said});
      if (!done.ok) {
        contextBack(taken);  // kept for the resend
        item.state = 'waiting';
        startFailed(done.body?.error || 'The message was not sent.', done.body?.next);
        return;
      }
      item.state = 'sent';
    }
  } finally { DOCK.delivering = false; }
  drawHelpdesk();
}
/* A start or a send that failed: why, in the chat, and every message still waiting back in the box, so nothing
 * written is lost. */
export function startFailed(reason, next = null) {
  // what the person wrote, without the line about their click, which was never theirs to see in the box
  const left = DOCK.queue.filter(item => item.state !== 'sent');
  const waiting = left.map(item => item.text.slice(item.clicked ? item.clicked.length + 2 : 0));
  // the message never went, so the click it named is still untold: the resend carries it while it is fresh
  if (left.some(item => item.clicked)) CLICKED.told = false;
  DOCK.queue = DOCK.queue.filter(item => item.state === 'sent');
  const box = $('#helpdesk .say');
  if (waiting.length) { box.value = [...waiting, box.value.trim()].filter(Boolean).join('\n\n'); growSay(); }
  dockNote(`${reason}${next ? ` Next: ${next}` : ''}${waiting.length ? ' Your message is back in the box.' : ''}`);
}
export const chatButton = (given, label) => h('button', {class: 'chat', title: `Talk with an agent about ${label}`,
  onclick: event => { event.stopPropagation(); talkAbout(given, label); }}, 'Chat');
/* What a node is called to the agent: an element's address, or a join's receiver, which holds it. */
export function nodeTalk(id) {
  const join = id.startsWith('p:') ? joinOf(id) : null;
  return {node: join ? join.receiver_address : S.elements.get(id)?.element.address || id};
}
$('#helpdesk .interrupt').onclick = () => interruptChat(DOCK.target, DOCK.session, $('#helpdesk .interrupt'));
$('#helpdesk .call').onclick = () => callSystem();
/* Resume and Stay connected beside Call: the dispatch_resume_chats and dispatch_stay_connected settings of this
 * project, read when the dock opens and saved on a change. */
export async function syncResume() {
  const project = S.project, box = $('#helpdesk .resume input'), stay = $('#helpdesk .stay input');
  if (!project) return;  // read with the project's own settings, once one is shown
  try {
    const rows = (await read('settings')).settings || [];
    const row = rows.find(one => one.key === 'dispatch_resume_chats');
    const kept = rows.find(one => one.key === 'dispatch_stay_connected');
    if (S.project === project && row) box.checked = row.value !== false;
    if (S.project === project && kept) stay.checked = kept.value === true;
  } catch { /* the box keeps what it shows */ }
}
/* A switch beside Call saved as its setting; a refused save turns it back and says why. */
async function saveSwitch(event, key, what) {
  const done = await posted('/api/settings', {key, value: event.target.checked});
  if (!done.ok) {
    event.target.checked = !event.target.checked;
    dockNote(done.body.error || `${what} was not saved.`);
  }
  return done.ok;
}
$('#helpdesk .resume input').onchange = event => saveSwitch(event, 'dispatch_resume_chats', 'Resume');
$('#helpdesk .stay input').onchange = async event => {
  if (await saveSwitch(event, 'dispatch_stay_connected', 'Stay connected') && event.target.checked) {
    dockNote('Your system agent stays connected to this project; closing the chat never stops it, and Stop agent turns '
      + 'this off.');
  }
};
/* The person's stop of their system agent turns Stay connected off for the project, dispatch's `disconnect`: the box
 * follows, and the dock says so. `stopped` is the stop's answer. */
export function stayedOff(stopped) {
  return (stopped?.stay_connected === false ? (($('#helpdesk .stay input').checked = false),
    ' Stay connected is off for this project until you check it again.') : '') + queuePaused(stopped);
}
/* The person's stop of an agent while Full Auto is on turns Full Auto off, dispatch's `paused`, so no waiting ticket
 * starts in its place: the switch follows, and the toast says so. UX review round 1, 2026-10-17. */
export function queuePaused(stopped) {
  if (stopped?.autostart !== false) return '';
  $('#autostartAgents').checked = false;
  return ` ${stopped.notice || 'Full Auto is now off for this project.'}`;
}
const toSystem = () => !DOCK.target || DOCK.target === DOCK.mine || DOCK.chat?.source === 'system';
/* What the person writes goes to the agent on view, with the files attached; a /command is the chat's or the
 * agent's; with no agent there yet it waits in the thread, and one is reached. */
async function sendMessage(event) {
  event.preventDefault();
  if (notificationState(DOCK.state)) return;
  if (DOCK.attaching) await DOCK.attaching;  // files still being saved go with the message
  const box = $('#helpdesk .say'), text = box.value.trim();
  if (!text && !DOCK.files.length) return;
  if (text) remember(text);
  if (text.startsWith('/')) { box.value = ''; return dockCommand(text); }
  const attached = DOCK.files.length
    ? '\n\nAttached files, saved in the project:\n' + DOCK.files.map(file => `- ${file}`).join('\n') : '';
  box.value = '';
  growSay();
  followLog(true);  // what the person sends is followed to the end of the thread
  // a fork's thread on view is written to as the fork, which takes the words alone; an agent's own subagent is not
  // written to, so what is written there goes to its parent. Words for a fork never wait for its parent's agent
  const open = DOCK.child && (DOCK.subagents || []).find(one => one.session_id === DOCK.child);
  const fork = open?.fork === true ? DOCK.child : null;
  // a frame of the share goes as a picture only to a running session whose agent takes pictures, never as words alone
  const frame = DOCK.frame;
  const refused = !frame ? null : fork ? 'A fork takes words only, so the frame was not sent.'
    : !DOCK.live ? 'The frame goes once the agent is running; send it then.'
      : DOCK.state?.capabilities?.image !== true ? 'This agent does not take pictures, so the frame was not sent; '
        + 'remove it to send your words alone.' : null;
  if (refused) { box.value = text; growSay(); return toast(refused); }
  const told = !fork && toSystem() ? clickedLine() : '', lead = told ? `${told}\n\n` : '';
  // told as it is taken, so a follow-up, or a click made while this one goes, is never counted as this one's
  if (told) CLICKED.told = true;
  if (!fork && (!DOCK.live || DOCK.queue.some(item => item.state !== 'sent'))) {
    DOCK.queue.push({id: ++QUEUE_ID, text: lead + text + attached, sent: '', clicked: told, state: 'waiting',
      at: Date.now()});
    CLICKED.told = true;
    DOCK.files = []; fill($('#helpdesk .files'));
    ensureAgent();
    drawHelpdesk();
    return;
  }
  // a spoken message's recording goes with it, where the agent takes audio
  const audio = await voiceAudio(text, !fork && DOCK.state?.capabilities?.audio === true);
  const taken = fork ? null : takeContext({work: DOCK.target, session: DOCK.session});
  const said = fork ? text + attached : lead + withContext(taken, text + attached);
  const sent = await wrote('/api/dispatch-message', {work_id: DOCK.target, session: DOCK.session, text: said,
    ...(fork ? {fork} : {}), ...audio, ...(frame ? {image: frame.jpeg} : {})});
  if (sent) {
    DOCK.files = []; DOCK.frame = null; drawAttached(); drawHelpdesk();
    if (frame && sent.image !== true) toast('Your words were sent, but the frame did not reach the agent.');
  } else {  // the views' context and the click are kept for the resend
    contextBack(taken);
    if (told) CLICKED.told = false;
    box.value = text; growSay();
  }
}
$('#helpdesk .compose').onsubmit = sendMessage;
/* What the person sent in each thread from this page, as typed, newest last, as a Claude Code prompt history: Up in
 * an empty box brings back the last, again goes further back, Down comes forward and past the newest empties the box.
 * Once a recalled message is edited, Up and Down move the caret again. */
const SENT = new Map(), RECALL = {target: null, at: -1};
function remember(text) {
  const list = SENT.get(DOCK.target) || [];
  if (list.at(-1) !== text) list.push(text);
  SENT.set(DOCK.target, list);
  RECALL.at = -1;
}
function recall(by) {
  const box = $('#helpdesk .say'), list = SENT.get(DOCK.target) || [];
  const walking = RECALL.at >= 0 && RECALL.target === DOCK.target && box.value === list[RECALL.at];
  if (!walking && (box.value || by > 0 || !list.length)) return false;
  const next = (walking ? RECALL.at : list.length) + by;
  if (next < 0) return true;  // at the oldest: it stays
  RECALL.target = DOCK.target;
  RECALL.at = next < list.length ? next : -1;
  box.value = next < list.length ? list[next] : '';
  box.setSelectionRange(box.value.length, box.value.length);
  growSay();
  return true;
}
/* Enter sends, Shift+Enter starts a new line; an IME's Enter confirms the word it composes and never sends:
 * isComposing, or Safari's 229 as composition ends. Page Up and Page Down read the conversation without leaving the
 * box; Up and Down walk what was sent, `recall`. */
function sayKeys(event) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
    event.preventDefault();
    $('#helpdesk .compose').requestSubmit();
  }
  if ((event.key === 'ArrowUp' || event.key === 'ArrowDown') && !event.isComposing && !event.shiftKey
    && !event.altKey && !event.ctrlKey && !event.metaKey && recall(event.key === 'ArrowUp' ? -1 : 1)) {
    event.preventDefault();
  }
  if ((event.key === 'PageUp' || event.key === 'PageDown') && !event.altKey && !event.ctrlKey && !event.metaKey) {
    event.preventDefault();
    const log = $('#helpdesk .log');
    const by = (event.key === 'PageUp' ? -1 : 1) * log.clientHeight * 0.85;
    log.scrollBy({top: by, behavior: reduced() ? 'auto' : 'smooth'});
  }
}
$('#helpdesk .say').addEventListener('keydown', sayKeys);
/* The chat's own keys, anywhere in it, each in the `?` reference: interrupt the turn, the thread before or after, the
 * newest message, the agent's settings. */
function chatKeys(event) {
  if (event.isComposing) return;
  if (event.key === 'Escape') {
    event.preventDefault();
    event.stopPropagation();
    escapeChat();
    return;
  }
  const mod = MAC ? event.metaKey : event.ctrlKey;
  if (mod && event.key === '.') {
    event.preventDefault();
    if (!$('#helpdesk .interrupt').disabled) $('#helpdesk .interrupt').click();
    return;
  }
  if (!event.altKey || event.ctrlKey || event.metaKey) return;
  if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
    // in the order drawn, My agent first: the agent list's rows at full size, else the tabs
    const tabs = [...document.querySelectorAll(listShown() ? '#helpdesk .agentlist .agentrow'
      : '#helpdesk .tabs .tab')];
    if (tabs.length < 2) return;
    event.preventDefault();
    const at = tabs.findIndex(tab => tab.classList.contains('on')), by = event.key === 'ArrowUp' ? -1 : 1;
    tabs[(at + by + tabs.length) % tabs.length].click();
  } else if (event.key === 'End') { event.preventDefault(); followLog(true); }
  else if (event.key === ',') { event.preventDefault(); openSessionPop(); }
}
$('#helpdesk').addEventListener('keydown', chatKeys);
/* Escape as in Claude Code, and never putting the chat away, which the close × and C do: a running turn is
 * interrupted; else text in the box is cleared, as an edit Ctrl+Z takes back; else another agent's thread goes back
 * to My agent; else nothing. */
function escapeChat() {
  const stop = $('#helpdesk .interrupt'), box = $('#helpdesk .say');
  if (!stop.hidden && !stop.disabled) { stop.click(); return; }
  if (box.value) {
    box.focus();
    box.select();
    if (!document.execCommand('delete')) box.value = '';
    growSay();
    return;
  }
  if (onOther()) showMine();
}
function openSessionPop() {
  const line = $('#helpdesk .sessionline');
  if (!line) return toast("The agent's settings show once one is chosen.");
  if (sessionPop().hidden) line.click();
  requestAnimationFrame(() => sessionPop().querySelector(FOCUSABLE)?.focus());
}
/* The head's menu: what is used now and then, each with its key. */
const DOCKMENU = overlay($('#dockMenu'), {kind: 'menu'});
function drawDockMenu() {
  const big = $('#dock').className === 'open big', side = ['left', 'right'].includes($('#dock').dataset.place);
  const item = (label, key, run, shown = true) => shown ? h('button', {type: 'button', role: 'menuitem',
    onclick: () => { DOCKMENU.hidden = true; run(); }}, h('span', {}, label), key ? h('kbd', {}, key) : null) : null;
  fill(DOCKMENU,
    item('Give this agent a body…', 'B', askEmbody, embodyHooks() && embodiable(DOCK.chat)),
    item('Agent and settings…', 'Alt ,', openSessionPop),
    item('Apps…', '/apps', showGallery),
    item(big ? 'Back to its size' : 'Make it large', null, () => $('#helpdesk .big').click(), !narrowPage()),
    item(side ? 'Float it' : 'Dock it at the side', null, () => $('#helpdesk .place').click(), !narrowPage()),
    item('Put it back in its corner', 'Double-click head', resetDock, !narrowPage() && !big),
    h('hr'),
    item('Keyboard shortcuts', '?', () => openHelp()));
}
function toggleDockMenu(event) {
  event.stopPropagation();
  if (!DOCKMENU.hidden) { DOCKMENU.hidden = true; return; }
  drawDockMenu();
  DOCKMENU.hidden = false;
}
$('#helpdesk .more').onclick = toggleDockMenu;
/* The message box grows with what is typed, from one line to about five, and scrolls only past that. */
function growSay() {
  const box = $('#helpdesk .say'), most = parseFloat(getComputedStyle(box).lineHeight || '20') * 5 + 14;
  box.style.height = 'auto';
  box.style.height = `${Math.min(box.scrollHeight + 2, most)}px`;
  box.style.overflowY = box.scrollHeight + 2 > most ? 'auto' : 'hidden';
}
$('#helpdesk .say').addEventListener('input', growSay);
$('#helpdesk .compose').addEventListener('submit', () => requestAnimationFrame(growSay));
/* A file's contents as base64, read in the browser; null when it cannot be read, as a dropped folder cannot. */
function readBase64(file) {
  return new Promise(done => {
    const reader = new FileReader();
    reader.onload = () => done(String(reader.result).split(',')[1] || '');
    reader.onerror = () => done(null);
    reader.readAsDataURL(file);
  });
}
/* Files attached with the paperclip, pasted into the box or dropped on the chat, by one path: each saved in the
 * project by /api/attach, and shown as a chip until the message goes. One the server refuses, or the browser cannot
 * read, is named in the chat with why. Files given while others are being saved wait their turn, in order. */
function attachFiles(files) {
  const given = [...files];
  if (!given.length) return;
  const saving = (DOCK.attaching || Promise.resolve()).then(() => saveFiles(given));
  DOCK.attaching = saving;
  saving.then(() => { if (DOCK.attaching === saving) DOCK.attaching = null; });
}
async function saveFiles(files) {
  for (const file of files) {
    const name = file.name || 'pasted';
    const data = await readBase64(file);
    if (data === null) {
      dockNote(`${name} was not attached: the browser could not read it. A folder cannot be attached; its files can.`);
      continue;
    }
    const saved = await posted('/api/attach', {name, data});
    if (saved.ok) DOCK.files.push(saved.body.path);
    else dockNote(`${name} was not attached: ${saved.body.error || 'the server did not save it.'}`);
    drawAttached();
  }
}
$('#helpdesk .clip input').onchange = event => { attachFiles(event.target.files); event.target.value = ''; };
/* A picture pasted into the box, a screenshot say, is attached as the paperclip attaches it. Whatever comes with
 * text pastes as its text: a copy from a document or a sheet carries a picture of itself beside its words. */
function pasteFiles(event) {
  const given = event.clipboardData;
  if (!given || !given.files.length || given.types.includes('text/plain')) return;
  event.preventDefault();
  attachFiles(given.files);
}
$('#helpdesk .say').addEventListener('paste', pasteFiles);
/* Files dragged from the desktop over the chat: where their chips will land is marked, above the box, and a drop on
 * the box or the conversation attaches them. A drag of anything but files is left to the page. */
const HELPDESK = $('#helpdesk');
const carriesFiles = event => Boolean(event.dataTransfer?.types.includes('Files'));
function dragFiles(event) {
  if (!carriesFiles(event)) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = 'copy';
  HELPDESK.classList.add('dropping');
}
HELPDESK.addEventListener('dragenter', dragFiles);
HELPDESK.addEventListener('dragover', dragFiles);
HELPDESK.addEventListener('dragleave', event => {
  if (!HELPDESK.contains(event.relatedTarget)) HELPDESK.classList.remove('dropping');
});
HELPDESK.addEventListener('drop', event => {
  HELPDESK.classList.remove('dropping');
  if (!carriesFiles(event)) return;
  event.preventDefault();
  attachFiles(event.dataTransfer.files);
  $('#helpdesk .say').focus();
});
/* A frame of what the person shares with agents, from the screen button: sent with the next message as a picture.
 * With nothing shared the button starts the share first, the browser's picker opened by this click. */
async function attachFrame() {
  if (!sharing() && !await startShare()) return;
  const frame = shareFrame();
  if (frame.error) return toast(frame.error);
  DOCK.frame = frame;
  drawAttached();
}
$('#helpdesk .frame').onclick = attachFrame;
/* What goes with the next message: each file attached, and the frame, which can be taken off. */
function drawAttached() {
  const frame = DOCK.frame && h('span', {class: 'chip'}, `Screen ${DOCK.frame.width}×${DOCK.frame.height} `,
    h('button', {class: 'btn icon sm quiet', type: 'button', 'aria-label': 'Remove the frame',
      onclick: () => { DOCK.frame = null; drawAttached(); }}, '×'));
  fill($('#helpdesk .files'), ...DOCK.files.map(file => h('span', {class: 'chip'}, file.split('/').pop())), frame);
}
$('#dockTab').onclick = () => dockState('open');
$('#dockTab').onkeydown = event => {
  if (event.key !== 'Enter' && event.key !== ' ') return;
  event.preventDefault();
  dockState('open');
};
$('#helpdesk .close').onclick = () => putChatAway();  // eased away; its threads are kept
$('#helpdesk .close').title = 'Close chat without stopping the agent (C)';
// On the overlay stack as the dock: Escape inside it is the chat's own, escapeChat, and it stays usable over the board.
overlay($('#helpdesk'), {kind: 'dock', close: escapeChat, focus: '.say'});
$('#helpdesk .big').onclick = () => dockState($('#dock').className === 'open big' ? 'open' : 'open big');
