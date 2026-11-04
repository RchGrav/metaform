/* The chat dock's state, when the page first saw each line, and a body for the chat's agent on the map, web_embody. */
import '/page/app/selection/select.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {toast} from '/page/app/core/controls.js';
import {drawHelpdesk, followLog, launcherRect, reverseDock, growFrom} from '/page/app/dock/helpdesk.js';
import {setBox, dockLayout} from '/page/app/dock/place.js';
import {D} from '/page/app/agents/dispatch.js';
import {drawDockTab} from '/page/app/agents/pickers.js';
import {isIntake} from '/page/app/session/tools.js';
import {chatDocked} from '/page/app/workspace/workspace.js';

/* The chat dock: a thin sliver at the lower right that lifts when the pointer comes near and opens, on a click, into
 * the page's one place for conversations with agents. Every thread is an ACP session, kept by its session id, and a
 * tab of its own: an agent dispatched on a ticket, the intake, the person's system agent, a chat the person started, a
 * each with a chip saying where it comes from. A thread shows the agent's words, its thinking, its tool calls
 * and its permission requests in order, with its plan and its settings above; Call reaches the person's system agent,
 * the +1 outside the agent limit, and /list and /chat <n> talk with an agent at work, VIEW-039 and VIEW-045. Bubbles
 * alternate: the person's on the right, the agent's on the left. A file attached with the paperclip is saved in the
 * project and the agent is told where. The dock rests in the corner, docks at either side of the page, or floats where
 * its head is dragged. */
export const DOCK = {target: null, session: null, label: '', since: 0, notes: [], list: [], files: [], mine: null,
  waiting: '', calling: null,
  chats: [], chat: null, selection: 0,  // selection changes only when a thread is chosen
  pinned: true,
  queue: [],  // messages written before the agent was there, sent in order once it is
  attaching: null,  // the files still being saved, attached with the paperclip, pasted or dropped; a send waits for them
  unread: false, heard: new Set()};
/* When the page first saw each message of a thread. A thread's lines carry no time of their own, so those already
 * there when its session was first read have none, and each one after that has the moment it arrived. */
export const SEEN = {at: new Map(), sessions: new Set()};
export const clockOf = (when, day = false) => {
  const date = new Date(when);
  if (isNaN(date)) return '';
  const today = new Date().toDateString() === date.toDateString();
  const dated = day && !today ? {month: 'short', day: 'numeric'} : {};
  return date.toLocaleString([], {hour: '2-digit', minute: '2-digit', ...dated});
};
export const STANDBY = 'Please stand by while we contact an agent for you.';
// a ticket's agent with no session yet keeps what the person writes on its ticket, `holdQueued` in dock/send.js
export const HELD = 'It reads this when it starts.';
// the project's updates are read-only, said in the box in place of a message
export const UPDATES_ONLY = 'Project updates are read-only: write to My agent to answer them';
// the chat going into its tab, 'away', or coming out of it, 'back'
export const DOCKMOTION = {anim: null, dir: null};
export const dockGoingAway = () => Boolean(DOCKMOTION.anim)
  && (DOCKMOTION.dir === 'away') === (DOCKMOTION.anim.playbackRate > 0);
/* /mascot opens the existing character picker on demand. A choice for the system agent remains the person's
 * mascot across conversations. The flow owns the figures and the available characters. */
export const EMBODY = {open: null, session: null, stops: []};
export const embodyHooks = () => ['embody', 'characters', 'bodies']
  .every(name => typeof window.metaform?.[name] === 'function');
const hooked = (name, ...given) => { try { return window.metaform[name](...given); } catch { return null; } };
/* Only a conversation's agent takes a body this way, the system agent or a chat the person started; an agent at work
 * on a ticket walks as its own figure already. */
export const embodiable = chat => Boolean(chat && ['system', 'conversation'].includes(chat.source)
  && !isIntake(chat.target));
const bodyFor = work => (hooked('bodies') || []).find(one => one.work === work) || null;
function characterList(work) {
  const system = DOCK.chat?.source === 'system', mine = bodyFor(work)?.character;
  // the person's own character, web_mascot, first for their system agent; with none set, none is put first
  const list = (hooked('characters') || []).filter(one => one?.name && (!one.mascot || system)).map(one => ({...one,
    src: `/page/agent-glyphs/${one.name}.svg`, free: one.free !== false || one.name === mine || (one.mascot && system),
    preferred: Boolean(one.preferred && system)}));
  return [...list.filter(one => one.preferred), ...list.filter(one => !one.preferred)];
}
function stopPreviews() {
  for (const stop of EMBODY.stops.splice(0)) { try { stop(); } catch { /* already still */ } }
}
/* Give the chat's agent the character chosen; the flow says no when it is taken, and the chat says why. */
function embodyAs(work, glyph) {
  if (!work || !glyph || !embodyHooks()) return false;
  const done = hooked('embody', work, glyph);
  if (!done || done.error) {
    dockNote(done?.error || 'That body could not be given.');
    return false;
  }
  if (EMBODY.open === work) { EMBODY.open = null; stopPreviews(); }
  dockNote(done.mascot ? `Your system agent walks the map as the ${glyph} now, your mascot in every conversation.`
    : `It walks the map as the ${glyph} now.`);
  return true;
}
/* Open the choice only when the person asks with /mascot. */
export function askEmbody() {
  const work = DOCK.target;
  if (!embodyHooks()) return toast('Bodies on the map are not ready on this page yet.');
  if (!work || !embodiable(DOCK.chat)) return toast('Open a chat with your system agent, or one you started, first.');
  EMBODY.open = EMBODY.open === work ? null : work;
  EMBODY.session = DOCK.session;
  if (!EMBODY.open) stopPreviews();
  if (!$('#dock').className.startsWith('open')) dockState('open');
  drawHelpdesk().then(() => { if (EMBODY.open) followLog(true); });
}
/* The offer in the thread, a row of the conversation: each character moving in its own way on a small canvas, with
 * its name and temper, those taken by another agent unavailable, and Not now. */
export function embodyRows(work) {
  if (!work || EMBODY.open !== work || !embodyHooks()) { if (EMBODY.stops.length) stopPreviews(); return []; }
  const body = bodyFor(work), list = characterList(work);
  const text = `${body?.character || ''}:${list.map(one => `${one.name}${one.free ? '' : '-'}`).join(',')}`;
  return [{key: `embody:${work}`, text, make: () => embodyChoice(work, body, list)}];
}
function embodyChoice(work, body, list) {
  stopPreviews();
  const notNow = () => { EMBODY.open = null; stopPreviews(); drawHelpdesk(); };
  return h('div', {class: 'embody', role: 'group', 'aria-label': 'Give this agent a body on the map'},
    h('p', {class: 'ask'},
      h('b', {}, body?.by ? 'Change its body?' : `Give ${DOCK.label || 'this agent'} a body on the map?`),
      h('small', {}, 'It walks the map in that shape as it works. Change it at any time with /mascot.')),
    h('div', {class: 'choices'}, list.map(one => characterButton(work, body, one))),
    h('div', {class: 'acts'}, h('button', {type: 'button', class: 'btn sm quiet notnow', onclick: notNow}, 'Not now')));
}
/* One character to choose: moving on its canvas, its name and temper; one at work already cannot be chosen. */
function characterButton(work, body, one) {
  const canvas = h('canvas', {width: '96', height: '96', 'aria-hidden': 'true'});
  const stop = previewOn(one, canvas);
  if (typeof stop === 'function') EMBODY.stops.push(stop);
  const on = body?.by && body.character === one.name;
  const title = `${one.name}: ${one.temperament || ''}${one.moves ? `, it ${one.moves}s` : ''}`
    + (one.free ? '' : ' · at work already');
  return h('button', {type: 'button', class: `character${on ? ' on' : ''}`, disabled: !one.free, title,
    'aria-pressed': String(Boolean(on)), onclick: () => embodyAs(work, one.name)},
  canvas, h('span', {class: 'name'}, one.name),
  h('small', {}, one.preferred ? 'your character' : one.temperament || ''));
}
/* A character moving on its canvas, and what stops it; nothing where it cannot be drawn. */
function previewOn(one, canvas) {
  if (typeof one.preview !== 'function') return null;
  try { return one.preview(canvas); } catch { return null; }
}
/* Keep the chosen glyph visible without opening a picker when the context changes. */
export function paintAvatar(work, session) {
  if (EMBODY.open && (EMBODY.open !== work || EMBODY.session !== session?.session_id)) {
    EMBODY.open = null;
    EMBODY.session = null;
    stopPreviews();
  }
  const avatar = $('#helpdesk .head .avatar');
  if (!avatar) return;
  if (!avatar.dataset.letter) avatar.dataset.letter = avatar.textContent;
  const hooks = embodyHooks(), can = hooks && work && embodiable(DOCK.chat);
  const body = can ? bodyFor(work) : null, glyph = body && (body.by || body.drawn) ? body.character : null;
  if (avatar.dataset.glyph !== (glyph || '')) {
    avatar.dataset.glyph = glyph || '';
    fill(avatar, glyph ? h('img', {src: `/page/agent-glyphs/${glyph}.svg`, alt: ''}) : avatar.dataset.letter);
  }
  avatar.classList.toggle('embodied', Boolean(glyph));
  avatar.setAttribute('role', 'img');
  avatar.setAttribute('aria-label', glyph ? `Its body on the map: the ${glyph}` : 'Agent');
  avatar.title = glyph ? `Its body on the map: the ${glyph}. Change it with /mascot.` : 'Choose a glyph with /mascot';
}
/* Where a thread comes from, said on its chip. The system agent and a chat the person started are the person's own;
 * a session the page did not start is known only as an agent at work or an intake. */
export const SOURCES = {agent: 'Agent at work', intake: 'Intake', system: 'Your system agent',
  conversation: 'Your chat', merge: 'Merge help', notification: 'Project updates'};
export const sourceOf = workId => isIntake(workId) ? 'intake' : workId === DOCK.mine ? 'system' : 'agent';
export const sourceChip = source => h('span', {class: 'src', 'data-source': source}, SOURCES[source] || SOURCES.agent);
export function dockState(state) {
  const box = $('#helpdesk'), was = !box.hidden, open = state === 'open' || state === 'open big';
  const anim = DOCKMOTION.anim;
  if (open && dockGoingAway()) {  // called back on its way
    reverseDock();
    if (state === $('#dock').className) return;
  }
  if (!open && anim) {  // put away at once, as another project is chosen: no motion left running
    Object.assign(DOCKMOTION, {anim: null, dir: null});
    anim.cancel();
    $('#dockTab').classList.remove('launch');
    Object.assign(box.style, {transformOrigin: '', willChange: ''});
  }
  // measured while the tab still shows
  const from = open && !was && !chatDocked() ? launcherRect() : null;
  $('#dock').className = state;
  box.hidden = !open;
  dockLayout();
  if (open && !was) {  // opened, even empty, it says what it is and how to start, and grows out of its tab
    // the window may be smaller now
    if ($('#dock').dataset.place === 'float' && box.style.left) setBox(box.getBoundingClientRect(), false);
    DOCK.unread = false;
    drawDockTab();
    drawHelpdesk();
    if (from) growFrom(from);
  }
  if (!open) stopPreviews();
}
export function dockNote(text) { DOCK.notes.push({at: Date.now(), text}); drawHelpdesk(); }
