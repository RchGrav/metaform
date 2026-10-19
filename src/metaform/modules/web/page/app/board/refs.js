/* The board's words for conditions and kinds, node chips, references in what the person reads and their popups, and
 * the task's words. */
import '/page/app/board/messages.js';  // the part before runs first, so the parts run in the page's order
import {h, fill} from '/page/app/core/dom.js';
import {overlay} from '/page/app/core/overlays.js';
import {S, read} from '/page/app/core/reads.js';
import {joinOf} from '/page/app/graph/data.js';
import {select} from '/page/app/selection/select.js';
import {chatButton} from '/page/app/dock/send.js';
import {COLUMN_NAMES} from '/page/app/board/history.js';
import {ticketPart} from '/page/app/agents/dispatch.js';
import {named} from '/page/app/task/task.js';

/* The board, VIEW-037: the project's tickets as a classic kanban board, one column for each place a ticket can be,
 * a card for each ticket. A card dragged to a column moves its ticket there and to the place it was dropped. */
/* The board's tickets, the kinds hidden, and cutoff: the time its done tickets start at, as the server's board read
 * gives it, board_done_days ago or the line in the sand; a ticket done before it is in the Archive. names: counted up
 * as element or join ops are applied to the map shown, so the cards draw the names those ops gave, `drawBoard`. */
export const B = {tickets: [], off: new Set(), cutoff: '', names: 0};
/* A ticket's fields as the page compares them, with the age the server counts in seconds left out: it differs on
 * every read, and the page shows its own, `ago`. A JSON.stringify replacer. */
export const unshown = (key, value) => (key === 'age_seconds' ? undefined : value);
export const KINDS = ['broken', 'flawed', 'enhancement'];  // a ticket's kind; none is a plain task
export const BOARD = [['backlog', 'Backlog'], ['todo', 'To do'], ['doing', 'Doing'], ['done', 'Done']];
/* What a record's condition says about the part it is at, MAP-046: the condition belongs to the element or join, not
   to the ticket; the ticket is the work on it. A record with no condition is a plain task. */
export const CONDITION_WORDS = {missing: 'missing', trouble: 'trouble', unbuilt: 'not built yet',
  'under-construction': 'under construction', built: 'built', broken: 'broken'};
/* A ticket's label is its kind, what sort of work it is, MAP-046 as amended 2026-10-08: never the part's stage, which
   the map shows on the node. A ticket with no kind is a plain task. */
export const KIND_WORDS = {broken: 'broken', flawed: 'flawed', enhancement: 'works, could be better'};
export function conditionLabel(ticket, extra = '') {
  const kind = ticket.kind || '';
  const words = kind ? KIND_WORDS[kind] || kind : 'task';
  const title = kind ? `This ticket's kind: ${words} (${kind}). The part's stage shows on its node.`
    : `A plain task at ${ticketPart(ticket)}. The part's stage shows on its node.`;
  return h('span', {class: `kind kind-${kind || 'none'}${extra}`, title}, words);
}
export function dated(text) {
  const date = new Date(text || '');
  return isNaN(date) ? '' : date.toLocaleString();
}
export const ago = text => {
  const seconds = Math.max(0, (Date.now() - Date.parse(text || '')) / 1000);
  return !isFinite(seconds) ? '' : seconds < 60 ? 'now' : seconds < 3600 ? `${Math.floor(seconds / 60)}m`
    : seconds < 86400 ? `${Math.floor(seconds / 3600)}h` : `${Math.floor(seconds / 86400)}d`;
};
export const partAt = address => [...S.elements.values()].map(entry => entry.element)
  .find(element => element.address === address);
export function nodeChip(target, role) {
  const element = target.address ? partAt(target.address) : null;
  const key = target.kind === 'join' ? 'p:' + target.id : element?.id || target.id;
  const end = address => (address ? partAt(address) : null) ? named(partAt(address)) : address;
  const ends = target.ends?.[0] ? `${end(target.ends[0])} → ${end(target.ends[1])}` : 'a join';
  const name = element ? named(element) : target.kind === 'join' ? joinOf('p:' + target.id)?.name || ends
    : target.address || target.id;
  const title = `${role === 'assigned' ? 'Assigned' : 'For reference'}: ${target.address || target.id}`;
  return h('button', {class: `node ${role}`, title, onclick: event => { event.stopPropagation(); select(key, true); }},
    name);
}
/* References in what the person reads, VIEW-042: a spec record's code, a ticket's or a message's id or its start, and
 * a path in the project. Each is drawn as plain text; once the server says what it stands for it becomes a link that
 * opens it in place, so an unknown code stays plain. */
// an intake agent's work id, intake-<hex>, is not a ticket, so its hex is never taken for one
const REF = /\b(?:[A-Z]{2,6}-\d{3}|D\d{2,4}|(?<!intake-)[0-9a-f]{8,32}|(?:[\w.-]+\/)+[\w.-]+\.\w{1,6})\b/g;
export function linked(text) {
  text = String(text ?? '');
  const parts = [];
  let at = 0;
  for (const found of text.matchAll(REF)) {
    parts.push(text.slice(at, found.index), h('span', {class: 'ref', 'data-ref': found[0]}, found[0]));
    at = found.index + found[0].length;
  }
  parts.push(text.slice(at));
  return parts;
}
const LOOKED = new Map();  // project and reference → a promise of what it stands for, or null
/* The references drawn since the last read, each with its promise's resolve, asked in one read for all of them: a
 * board drew about 900 references at once, one read each, and the server, reading every ticket for each, was held long
 * enough that a restart's readiness check gave up (2026-10-19). A read under way gathers what is drawn meanwhile for
 * the next. */
const LOOKUP = {waiting: new Map(), busy: false};
const LOOKUP_BATCH = 200;  // references in one read, so its address stays short
function looked(ref) {
  const key = `${S.project}\n${ref}`;
  if (!LOOKED.has(key)) {
    LOOKED.set(key, new Promise(resolve => { LOOKUP.waiting.set(key, resolve); }));
    // read once every reference this task draws has been asked for
    if (!LOOKUP.busy) { LOOKUP.busy = true; queueMicrotask(lookUp); }
  }
  return LOOKED.get(key);
}
async function lookUp() {
  try {
    while (LOOKUP.waiting.size) {
      const project = S.project, batch = [];
      for (const [key, resolve] of LOOKUP.waiting) {
        const at = key.indexOf('\n');
        if (key.slice(0, at) !== project) { LOOKED.delete(key); resolve(null); }  // drawn for a project left
        else batch.push([key.slice(at + 1), resolve]);
        LOOKUP.waiting.delete(key);
        if (batch.length === LOOKUP_BATCH) break;
      }
      if (!batch.length) continue;
      let found = {};
      try { found = (await read('lookup', {refs: batch.map(([ref]) => ref).join(' ')})).found || {}; }
      catch { found = {}; }
      for (const [ref, resolve] of batch) resolve(found[ref]?.kind ? found[ref] : null);
    }
  } finally { LOOKUP.busy = false; }
}
/* Each reference drawn anywhere on the page is looked up once, and becomes a link once it is known: only the nodes a
 * change added are searched, never the whole page again. */
function linkRef(span) {
  span.dataset.looked = '1';
  looked(span.dataset.ref).then(found => {
    if (!found) return;
    span.classList.add('ref-link');
    Object.assign(span, {tabIndex: 0, title: found.title || span.dataset.ref});
    span.setAttribute('role', 'button');
  });
}
function findRefs(records) {
  for (const record of records) {
    for (const node of record.addedNodes) {
      if (node.nodeType !== 1) continue;
      if (node.matches('span.ref:not([data-looked])')) linkRef(node);
      else for (const span of node.querySelectorAll('span.ref:not([data-looked])')) linkRef(span);
    }
  }
}
new MutationObserver(findRefs).observe(document.body, {childList: true, subtree: true});
const POP = h('div', {id: 'refPop', role: 'dialog', 'aria-label': 'What it refers to', hidden: true});
document.body.append(POP);
async function popRef(span, pinned) {
  const found = await looked(span.dataset.ref);
  if (!found) return;
  const kind = {spec: 'Specification', ticket: 'Ticket', message: found.type === 'question' ? 'Question' : 'Message',
    file: 'File'}[found.kind];
  const body = (REF_BODIES[found.kind] || fileBody)(found);
  const close = h('button', {class: 'close btn icon sm quiet', type: 'button', 'aria-label': 'Close',
    title: 'Close (Escape)', onclick: () => { POP.hidden = true; }},
  h('i', {class: 'i i-close', 'aria-hidden': 'true'}));
  fill(POP, h('div', {class: 'eyebrow'}, kind, close), ...body);
  POP.pinned = pinned;
  POP.hidden = false;
  const box = span.getBoundingClientRect(), size = POP.getBoundingClientRect();
  POP.style.left = Math.max(8, Math.min(box.left, innerWidth - size.width - 8)) + 'px';
  POP.style.top = (box.bottom + size.height + 8 < innerHeight ? box.bottom + 6 : Math.max(8, box.top - size.height - 6))
    + 'px';
}
/* What a reference stands for, by its kind: a spec record, a ticket with Chat, a message with Chat at its node, a
 * file. */
const specBody = found => [h('h4', {}, found.title), h('p', {class: 'text'}, ...linked(found.text)),
  h('small', {}, found.file)];
function ticketBody(found) {
  return [h('h4', {}, ...linked(found.task || found.note || found.id)),
    h('p', {class: 'pills'}, h('span', {class: 'pill'}, found.condition || 'unsorted'),
      h('span', {class: 'pill'}, COLUMN_NAMES[found.column] || found.column),
      found.done ? h('span', {class: 'pill'}, 'done') : null),
    found.task && found.note ? h('p', {class: 'text'}, ...linked(found.note)) : null,
    found.resolution ? h('p', {class: 'text'}, h('b', {}, 'Resolved: '), ...linked(found.resolution)) : null,
    chatButton({id: found.id}, `ticket ${found.id.slice(0, 8)}`)];
}
function messageBody(found) {
  return [h('p', {class: 'text'}, ...linked(found.text)),
    found.choices.length ? h('ol', {}, found.choices.map(choice => h('li', {}, choice))) : null,
    found.answer ? h('p', {}, h('b', {}, 'Answer: '), found.answer) : null,
    chatButton({node: found.address || ''}, 'its node')];
}
const fileBody = found => [h('h4', {}, found.title), h('pre', {class: 'text'}, found.text)];
const REF_BODIES = {spec: specBody, ticket: ticketBody, message: messageBody};
// On the overlay stack: a click outside it or Escape closes it; one opened by a click or a key takes the focus, one
// shown by resting the pointer does not.
overlay(POP, {kind: 'popover', focus: () => POP.pinned ? POP.querySelector('.close') : false});
function clickRef(event) {
  const span = event.target.closest?.('.ref-link');
  if (!span) return;
  event.preventDefault();
  event.stopPropagation();
  popRef(span, true);
}
function pressRef(event) {
  if ((event.key !== 'Enter' && event.key !== ' ') || !event.target.classList?.contains('ref-link')) return;
  event.preventDefault();
  popRef(event.target, true);
}
document.addEventListener('click', clickRef, true);
document.addEventListener('keydown', pressRef);
/* On a desktop, resting the pointer on a reference shows it too; moving off it puts away one it showed. */
const RESTING = {timer: null};
function restOnRef(event) {
  const span = event.target.closest?.('.ref-link');
  clearTimeout(RESTING.timer);
  if (span) RESTING.timer = setTimeout(() => { if (POP.hidden || !POP.pinned) popRef(span, false); }, 350);
  else if (!POP.pinned && !POP.hidden && !POP.contains(event.target)) POP.hidden = true;
}
if (matchMedia('(hover: hover)').matches) document.addEventListener('mouseover', restOnRef);
export function taskWords(text) {  // a node named inline, [[name|address]], shown as its name
  const parts = [], pattern = /\[\[([^|\]]+)\|([^\]]+)\]\]/g;
  let at = 0;
  for (const found of text.matchAll(pattern)) {
    parts.push(...linked(text.slice(at, found.index)), h('span', {class: 'inline', title: found[2]}, found[1]));
    at = found.index + found[0].length;
  }
  parts.push(...linked(text.slice(at)));
  return parts;
}
