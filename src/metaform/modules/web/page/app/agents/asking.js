/* A permission request waiting while its thread is not on screen, in a small pop-up of its own,
 * code.interface.graphical#72: the agent, its ticket, what it asks to do and every answer the thread's card gives,
 * with Open chat; several waiting stack as one window, 1 of N. */
import '/page/app/intake/intake.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {S, read} from '/page/app/core/reads.js';
import {DOCK} from '/page/app/dock/embody.js';
import {D, agentAt, glyphOf, glyphFor, ticketOf, onOtherBase} from '/page/app/agents/dispatch.js';
import {agentName} from '/page/app/agents/pickers.js';
import {isIntake, workPart, permissionCard} from '/page/app/session/tools.js';
import {openIntakeChat} from '/page/app/intake/intake.js';
import {chatDocked} from '/page/app/workspace/workspace.js';

/* The pop-up's state: the request it shows, the requests the person closed it on or answered from it, and each
 * request's line as its thread holds it, read once. It never takes the page: no backdrop, no focus taken, no Escape
 * held, so the page stays usable under it. */
const ASKING = {shown: null, closed: new Set(), answered: new Set(), lines: new Map(), drawn: '', reading: new Set()};
const BOX = h('div', {id: 'asking', class: 'window', hidden: true, role: 'dialog', 'aria-modal': 'false',
  'aria-label': 'A permission request waiting for you'});
document.body.append(BOX);
D.onAsking = drawAsking;  // renderAgents and drawHelpdesk call it, so neither imports this part
/* Whether the person sees the thread a request waits in now: the chat is open on that session. */
function onScreen(one) {
  const box = $('#helpdesk');
  return Boolean(box && !box.hidden && DOCK.session === one.session_id
    && ($('#dock').className.startsWith('open') || chatDocked()));
}
/* The requests the pop-up offers: each permission request waiting on a running session whose thread is not on screen,
 * that the person has not closed it on or answered from it, in the order they were asked. */
const waitingHere = () => (D.asking || []).filter(one => one.signal === 'permission-waiting' && one.request
  && !ASKING.closed.has(one.request) && !ASKING.answered.has(one.request) && !onScreen(one));
/* The pop-up drawn again for the requests waiting now; the request it showed stays shown while it still waits. */
export function drawAsking() {
  placeAsking();
  const waiting = waitingHere();
  if (!waiting.length) { BOX.hidden = true; ASKING.shown = null; ASKING.drawn = ''; return; }
  const at = Math.max(0, waiting.findIndex(one => one.request === ASKING.shown));
  const one = waiting[at];
  ASKING.shown = one.request;
  const line = ASKING.lines.get(one.request);
  if (!line) readLine(one);
  const session = D.sessions.find(row => row.session_id === one.session_id) || null;
  // drawn again only when what it shows changed, so a control under the person's hand is not swapped
  const drawn = [one.request, at, waiting.length, Boolean(line), session?.prompts, session?.prompts_from].join('|');
  if (drawn === ASKING.drawn && !BOX.hidden) return;
  ASKING.drawn = drawn;
  fill(BOX, bar(one, at, waiting), h('div', {class: 'body'}, line
    ? permissionCard(line, one.work_id, 'div', one.agent, {session, answered})
    : h('p', {class: 'hint'}, `${agentName(one.agent)} asks to ${one.tool || 'use a tool'}.`)),
  h('div', {class: 'foot'}, h('button', {type: 'button', class: 'btn sm openchat', onclick: () => openChat(one)},
    h('i', {class: 'i i-chat', 'aria-hidden': 'true'}), 'Open chat')));
  BOX.hidden = false;
}
/* At the top right, or beside the chat when the chat is open there, so neither covers the other. */
function placeAsking() {
  const chat = $('#helpdesk');
  BOX.style.right = '';
  if (!chat || chat.hidden || !$('#dock').className.startsWith('open') || chatDocked()) return;
  // where the chat stands once it has opened: its layout box, not its rectangle while it grows out of its tab
  const box = chat.getBoundingClientRect(), fixed = chat.offsetParent === null;
  const held = fixed ? {left: chat.offsetLeft, top: chat.offsetTop, right: chat.offsetLeft + chat.offsetWidth} : box;
  const gap = 12, wide = Math.min(400, innerWidth - 2 * gap);
  if (held.right < innerWidth - wide - gap || held.top > 56 + gap + 240) return;  // clear of where it stands
  if (held.left >= wide + 2 * gap) BOX.style.right = `${innerWidth - held.left + gap}px`;
}
/* Its head: the agent's glyph and name, its ticket, the place in the stack with the way through it, and close. */
/* A request of an agent at work on a base the page does not show is still the person's to answer, and says where
 * (UX review round 2, 2026-10-17, combined F4). */
function elsewhere(one) {
  const name = onOtherBase(one);
  return name ? ` · on ${name}` : '';
}
function bar(one, at, waiting) {
  const ticket = isIntake(one.work_id) ? null : ticketOf(one.work_id);
  const step = by => () => {
    ASKING.shown = waiting[(at + by + waiting.length) % waiting.length].request;
    drawAsking();
  };
  const many = waiting.length > 1;
  return h('div', {class: 'bar'},
    h('img', {class: 'glyph', src: glyphOf(one.work_id), alt: glyphFor(one.work_id)}),
    h('div', {class: 'title'}, h('b', {}, agentName(one.agent)),
      h('small', {title: ticket?.title || ''}, ` on ${workPart(one.work_id)}${ticket?.map?.item
        ? ` · ${ticket.map.item}` : ''}${elsewhere(one)}`)),
    many ? h('button', {type: 'button', class: 'btn icon sm prev', title: 'The request before',
      'aria-label': 'The request before', onclick: step(-1)},
    h('i', {class: 'i i-chev', 'aria-hidden': 'true'})) : null,
    many ? h('span', {class: 'stackcount', 'aria-live': 'polite'}, `${at + 1} of ${waiting.length}`) : null,
    many ? h('button', {type: 'button', class: 'btn icon sm next', title: 'The next request',
      'aria-label': 'The next request', onclick: step(1)}, h('i', {class: 'i i-chev', 'aria-hidden': 'true'})) : null,
    h('button', {type: 'button', class: 'btn icon close', title: 'Hide this request; it still waits in its chat',
      'aria-label': 'Hide this request', onclick: () => { ASKING.closed.add(one.request); drawAsking(); }},
    h('i', {class: 'i i-close', 'aria-hidden': 'true'})));
}
/* Answered from the pop-up: it leaves at once, as its thread's card says it was answered when next drawn. */
function answered(request) {
  ASKING.answered.add(request);
  setTimeout(drawAsking, 900);  // the card's word on what was chosen is read first
}
function openChat(one) {
  if (isIntake(one.work_id)) openIntakeChat(one.work_id, one.session_id, {focus: true});
  else agentAt(one.work_id, one.session_id);
  drawAsking();
}
/* The request's line from its thread, read once: its options, what it would act on and its state. */
async function readLine(one) {
  if (ASKING.reading.has(one.request)) return;
  ASKING.reading.add(one.request);
  const project = S.project;
  try {
    const found = await read('dispatch-sessions', {id: one.work_id, session: one.session_id});
    if (S.project !== project) return;
    const line = (found.lines || []).find(row => row.kind === 'permission' && row.session_id === one.session_id
      && row.data?.request === one.request);
    if (line) { ASKING.lines.set(one.request, line); drawAsking(); }
  } catch { /* the pop-up says what is asked without its answers; the chat holds them */ }
  finally { ASKING.reading.delete(one.request); }
}
/* A new project's requests are its own. */
export function leaveAsking() {
  Object.assign(ASKING, {shown: null, drawn: ''});
  for (const kept of [ASKING.closed, ASKING.answered, ASKING.lines]) kept.clear();
  BOX.hidden = true;
}
// the chat opened, put away or moved to another thread changes what is on screen
new MutationObserver(() => drawAsking()).observe($('#dock'), {attributes: true, attributeFilter: ['class', 'style']});
new MutationObserver(() => drawAsking()).observe($('#helpdesk'), {attributes: true,
  attributeFilter: ['hidden', 'style']});
addEventListener('resize', placeAsking);
