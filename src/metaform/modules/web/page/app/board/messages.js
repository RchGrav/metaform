/* The messages of a node, the Messages button, and the menu of a node opened by a right-click. */
import '/page/app/dock/place.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {overlay} from '/page/app/core/overlays.js';
import {toast} from '/page/app/core/controls.js';
import {S, read} from '/page/app/core/reads.js';
import {noMetaform} from '/page/app/header/admin.js';
import {G} from '/page/app/map3d/graph3d.js';
import {labelOf} from '/page/app/map2d/inside.js';
import {networkOf, memories} from '/page/app/memory/graph.js';
import {select} from '/page/app/selection/select.js';
import {talkAbout} from '/page/app/dock/commands.js';
import {nodeTalk} from '/page/app/dock/send.js';
import {ticketsOf, history, F, show} from '/page/app/board/history.js';
import {waiting, startWindow} from '/page/app/agents/dispatch.js';
import {giveWork} from '/page/app/task/task.js';
import {noteOf, notesAt, addElement} from '/page/app/task/notes.js';

/* The messages of a node, VIEW-030: what agents say to the user there. A question waits for an answer and a note
 * waits to be read. */
export const Q = {open: []};
export const nodeOf = record => record.node_kind === 'element' ? record.node_id : 'p:' + record.node_id;
export const targetOf = id => id.startsWith('p:') ? `join:${id.slice(2)}` : `element:${id}`;
export const calledOf = id => (G ? G.graphData().nodes.find(node => node.id === id) : null)?.name
  || (S.elements.has(id) ? labelOf(S.elements.get(id).element) : null) || 'this node';
export async function messagesOf(id) {
  const found = (await read('messages', {node: targetOf(id), limit: 0})).results;
  return {unread: found.filter(record => !record.closed), past: found.filter(record => record.closed), all: found};
}
/* The Messages button, VIEW-021: at the top of the page while anything waits for the user, with the count; a click
 * flies to the node of the oldest and opens its unread messages. */
export async function renderMessages() {
  try {
    Q.open = noMetaform() ? [] : (await read('messages', {open: true, limit: 0})).results;
  } catch (error) { Q.open = []; toast(error.message); }
  const button = $('#messages');
  button.hidden = !Q.open.length;
  button.textContent = `Messages ${Q.open.length}`;
  button.onclick = openOldest;
  if (F.id) await show(F.id, F.which, true);
}
/* The node of the oldest message waiting, flown to with its unread messages open. */
function openOldest() {
  if (!Q.open.length) return;
  const id = nodeOf(Q.open[0]);
  select(id, true);
  show(id, 'unread');
}
/* The menu of a node, opened by a right-click in either view. Each entry says how many it holds, and one that holds
 * none cannot be chosen. It is where further acts on a node are added. */
export async function menu(id, x = null, y = null) {
  let found = {unread: [], past: []}, note = null, tickets = [];
  try { found = await messagesOf(id); note = await noteOf(id); tickets = await ticketsOf(id); }
  catch (error) { toast(error.message); }
  const box = $('#menu');
  // an entry closes the menu and does its act; one that counts what it holds cannot be chosen holding none
  const item = (kind, text, act, {count = null, disabled = count === 0, title = null} = {}) =>
    h('button', {class: kind, disabled, role: 'menuitem', title, onclick: () => { box.hidden = true; act(); }},
      count === null ? text : [text + ' ', h('b', {}, String(count))]);
  const kept = networkOf(id).own.length;  // the memories kept at the node, VIEW-031
  const ready = tickets.filter(waiting);
  fill(box,
    item('unread', 'Unread messages', () => show(id, 'unread'), {count: found.unread.length}),
    item('past', 'Past messages', () => show(id, 'past'), {count: found.past.length}),
    item('memories', 'Memories', () => memories(id), {count: kept}),
    item('notes', 'Notes', () => notesAt(id), {count: note ? 1 : 0, disabled: false}),
    item('history', 'Work history', () => history(id), {count: tickets.length}),
    item('chat', 'Chat about this', () => talkAbout(nodeTalk(id), calledOf(id) || 'this node')),
    item('raise', 'Raise an issue', () => raiseIssue(id),
      {title: 'Say what is wrong with this part; a sentinel investigates and brings you proposals'}),
    item('task', 'Add Task', () => giveWork(id)),
    item('element', 'Add Element', () => addElement(id)),
    item('agent', 'Start agent', () => startWindow(`Start an agent · ${calledOf(id)}`, ready), {count: ready.length}));
  box.hidden = false;
  if (x === null && G) [x, y] = beside3d(id);  // asked for with no pointer: beside the node in the 3D map
  const size = box.getBoundingClientRect();
  box.style.left = Math.max(4, Math.min(x ?? 40, innerWidth - size.width - 4)) + 'px';
  box.style.top = Math.max(4, Math.min(y ?? 40, innerHeight - size.height - 4)) + 'px';
}
/* The issue box of the node's panel, opened and given the focus. */
async function raiseIssue(id) {
  await select(id, true);
  const issue = $('#work .issue');
  if (issue) { issue.hidden = false; issue.querySelector('textarea').focus(); }
}
/* Where on the page a node of the 3D map is, a little to its lower right. */
function beside3d(id) {
  const node = G.graphData().nodes.find(item => item.id === id), stage = $('#stage').getBoundingClientRect();
  const at = node && node.x !== undefined ? G.graph2ScreenCoords(node.x, node.y, node.z) : {x: 40, y: 40};
  return [stage.left + at.x + 12, stage.top + at.y + 12];
}
// a click outside it or Escape closes it, and the focus goes back where it was
overlay($('#menu'), {kind: 'menu'});
