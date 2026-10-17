/* A node's work history, the floating window it shows in, and windows moved by their title. */
import '/page/app/board/board.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill, keepFill} from '/page/app/core/dom.js';
import {keepPlace} from '/page/app/core/overlays.js';
import {toast} from '/page/app/core/controls.js';
import {S, reach, read} from '/page/app/core/reads.js';
import {workPill, asked} from '/page/app/selection/select.js';
import {chatButton} from '/page/app/dock/send.js';
import {targetOf, calledOf, messagesOf} from '/page/app/board/messages.js';
import {conditionLabel, dated, ago, linked} from '/page/app/board/refs.js';
import {ticketPart, renderAgents, agentAt} from '/page/app/agents/dispatch.js';
import {agentName} from '/page/app/agents/pickers.js';

/* A node's work history, VIEW-036: every ticket on it, open and done, newest first, in the floating window. */
export const COLUMN_NAMES = {backlog: 'backlog', todo: 'to do', doing: 'doing', done: 'done'};
export const columnOf = ticket => ticket.done ? 'done' : ticket.taken ? 'doing' : ticket.held ? 'backlog' : 'todo';
export const when = text => (text || '').replace('T', ' ').replace('Z', '');
export async function ticketsOf(id) { return (await read('work', {node: targetOf(id), limit: 0})).results || []; }
export async function history(id) {
  let tickets, dispatched = [];
  try { tickets = await ticketsOf(id); } catch (error) { toast(error.message); return; }
  try { dispatched = (await read('dispatch-sessions')).sessions || []; } catch (error) { toast(error.message); }
  Object.assign(F, {id: null, which: null, ids: new Set(), drawn: new Map()});
  $('#float .title').textContent = `Work history · ${calledOf(id)}`;
  fill($('#float .body'), tickets.length ? [...tickets].reverse().map(ticket => historyTicket(ticket, dispatched))
    : h('p', {class: 'empty'}, 'No work here yet.'));
  $('#float').hidden = false;
}
/* Who has a ticket, in words: an agent starting, the agent at work by its name, or who took it by hand; never the
 * reservation token or the session id it is recorded with, which stay on hover, UX review round 1 (web-gui-controls
 * F11). */
export function takenWords(ticket) {
  const by = String(ticket?.taken_by || '');
  if (!by) return null;
  const [who, ...rest] = by.split(' ');
  const said = by.startsWith('dispatch starting ') ? 'Starting…'
    : rest.length === 1 && /^[0-9a-f-]{8,}$/i.test(rest[0]) ? agentName(who) : by;
  return h('span', {class: 'by', title: by}, said);
}
/* How long since a ticket was opened, taken or done, its date on hover. */
export function ageOf(ticket) {
  const at = ticket.done || ticket.taken || ticket.created;
  return h('span', {class: 'age', title: `${ticket.done ? 'Done' : ticket.taken ? 'Taken' : 'Opened'} ${dated(at)}`},
    ago(at));
}
/* One ticket of the history: its kind, column and who took it, its task and note, when it was opened, taken and done,
 * the steps its agent reported, how it was resolved, and each agent sent to work it. */
function historyTicket(ticket, dispatched) {
  return h('div', {class: 'ticket'},
    h('div', {class: 'head'}, conditionLabel(ticket),
      h('span', {class: 'column'}, COLUMN_NAMES[columnOf(ticket)]),
      takenWords(ticket),
      ageOf(ticket)),
    ticket.task ? h('p', {class: 'task'}, ...linked(ticket.task)) : null,
    ticket.note ? h('p', {class: 'note'}, ...linked(ticket.note)) : null,
    h('div', {class: 'when'}, `opened ${when(ticket.created)}`, ticket.taken ? ` · taken ${when(ticket.taken)}` : '',
      ticket.done ? ` · done ${when(ticket.done)}` : ''),
    (ticket.said || []).length ? h('ol', {class: 'steps'}, ticket.said.map(step => h('li', {}, ...linked(step.said))))
      : null,
    ticket.resolution ? h('p', {class: 'resolution'}, ...linked(ticket.resolution)) : null,
    chatButton({id: ticket.id}, ticketPart(ticket)),
    ...dispatched.filter(one => one.work_id === ticket.id).map(one => dispatchRow(one, ticket)));
}
/* Each agent sent to work a ticket, and its session's thread, opened in the chat dock, VIEW-036 and VIEW-039; the
 * records stay here, on the node, and only the session's conversation is a thread. */
function dispatchRow(one, ticket) {
  const open = async () => {
    await renderAgents();
    agentAt(one.work_id, one.session_id);
  };
  return h('div', {class: 'dispatch'},
    h('span', {}, `${agentName(one.agent)} sent ${when(one.started)} · `
      + (one.state === 'running' ? 'working' : `ended${one.how ? `, ${one.how}` : ''}`)),
    chatButton(one.state === 'running' ? {id: one.work_id} : {session: `${one.work_id}:${one.session_id}`},
      `${agentName(one.agent)} on ${ticketPart(ticket)}`),
    h('button', {class: 'btn sm log', type: 'button', title: "The session's whole thread, in the chat dock",
      onclick: open}, 'Open in dock'));
}
/* The floating window, VIEW-030. It shows the messages it was opened with, each as it is now, so a question answered
 * in it shows its answer and a note read in it stays in sight until the window is closed. Shown again as the map
 * changes, a message that has not changed keeps the part of the window drawn for it, with whatever is typed there. */
export const F = {id: null, which: null, ids: new Set(), drawn: new Map(), base: null};
export async function show(id, which, again = false) {
  // Its messages are those of the metaform it was opened in; while another is shown it is left as it is.
  if (again && F.base !== S.base) return;
  let found;
  try { found = await messagesOf(id); } catch (error) { toast(error.message); return; }
  if (!again) Object.assign(F, {id, which, ids: new Set(found[which].map(record => record.id)), drawn: new Map(),
    base: S.base});
  if (F.id !== id) return;
  const shown = found.all.filter(record => F.ids.has(record.id));
  $('#float .title').textContent = `${which === 'unread' ? 'Unread' : 'Past'} messages · ${calledOf(id)}`;
  const drawn = new Map(shown.map(record => [record.id, messageDrawn(record)]));
  F.drawn = drawn;
  keepFill($('#float .body'), shown.length ? [...drawn.values()].map(one => one.node)
    : [h('p', {class: 'empty'}, 'No messages here.')]);
  $('#float').hidden = false;
  for (const record of shown) if (record.kind === 'message' && !record.closed) wrote('/api/read', {id: record.id});
}
/* A message as drawn in the window: kept as it was while it is unchanged, else drawn again, a question as its form. */
function messageDrawn(record) {
  const state = JSON.stringify([record.closed, record.answer, record.text, record.suggestions]);
  const had = F.drawn.get(record.id);
  if (had && had.state === state) return had;
  return {state, node: h('div', {}, h('div', {class: 'when'}, record.created.replace('T', ' ').replace('Z', '')),
    record.kind === 'question' ? asked(record, F.base) : noted(record))};
}
function noted(record) {
  return h('div', {class: 'item work'},
    h('div', {class: 'pills'}, workPill('message'), h('span', {class: 'pill'}, record.closed ? 'read' : 'unread'),
      record.by ? h('span', {class: 'pill'}, record.by) : null),
    h('p', {}, ...linked(record.text)));
}
export async function wrote(path, given) {
  let response;
  try {
    response = await reach(path, {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({project: S.project, base: S.base, ...given})}, 0);
  } catch (error) { toast(error.message); return null; }
  const body = await response.json().catch(() => ({error: 'The server did not answer with JSON.'}));
  if (!response.ok) toast(body.error || 'It was not written.');
  return response.ok ? body : null;
}
/* A floating window is moved by its title, and opens where the person last put it. `handle` is the part it is held
 * by; `start` runs as it first moves and `end` as it is let go, with the pointer's last place. */
export function movable(box, {handle = '.bar', start = null, end = null} = {}) {
  box.classList.add('movable');
  box.querySelector(handle).addEventListener('pointerdown', event => dragWindow(event, box, start, end));
}
function dragWindow(event, box, start, end) {
  if (event.button || box.classList.contains('full')) return;
  if (event.target.closest('button, input, select, textarea, a')) return;
  const at = [event.clientX, event.clientY];
  let from = null, grip = null;
  const stop = () => { removeEventListener('pointermove', move); removeEventListener('pointerup', done); };
  const move = moved => {
    if (!from) {  // held, not yet moved: a click on the title leaves the window where it is
      if (Math.hypot(moved.clientX - at[0], moved.clientY - at[1]) < 4) return;
      from = box.getBoundingClientRect();
      grip = [at[0] - from.left, at[1] - from.top];
      if (start?.(moved) === false) { stop(); from = null; return; }
      // a centered dialog moves from where it is
      Object.assign(box.style, {transform: 'none', left: from.left + 'px', top: from.top + 'px'});
    }
    box.style.left = Math.max(0, Math.min(moved.clientX - grip[0], innerWidth - 60)) + 'px';
    box.style.top = Math.max(0, Math.min(moved.clientY - grip[1], innerHeight - 40)) + 'px';
  };
  const done = last => {
    stop();
    if (!from) return;
    keepPlace(box);
    end?.(last);
  };
  addEventListener('pointermove', move);
  addEventListener('pointerup', done);
  event.preventDefault();
}
