/* Selection, both views together: select and selectNow, the work records shown, the question form at a node, and the
 * review-or-merge flow. */
import '/page/app/keys/keys.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {OVERLAY, shown, overlay, overlayHolds} from '/page/app/core/overlays.js';
import {toast} from '/page/app/core/controls.js';
import {FRAMED, S, MEM, read} from '/page/app/core/reads.js';
import {largeView} from '/page/app/header/menus.js';
import {joinOf, addressOf, nodeIn} from '/page/app/graph/data.js';
import {revealDepth} from '/page/app/keys/walk.js';
import {noticeAttention} from '/page/app/figures/attention.js';
import {setReach} from '/page/app/map3d/waves.js';
import {G, touched} from '/page/app/map3d/graph3d.js';
import {follow3d} from '/page/app/views/lens.js';
import {IN, samePath, renderThing} from '/page/app/map2d/inside.js';
import {memoryThing, renderMemories} from '/page/app/memory/graph.js';
import {focus2D} from '/page/app/map2d/flow2d.js';
import {openHelpdesk} from '/page/app/dock/threads.js';
import {drawHelpdesk} from '/page/app/dock/helpdesk.js';
import {nodeOf} from '/page/app/board/messages.js';
import {B, linked} from '/page/app/board/refs.js';
import {wrote} from '/page/app/board/history.js';
import {giveWork} from '/page/app/task/task.js';
import {renderJoin, renderObject} from '/page/app/panel/object.js';
import {renderBrief} from '/page/app/panel/brief.js';
import {tabNow, showTab} from '/page/app/panel/prompts.js';
import {WS, wsSelected} from '/page/app/workspace/workspace.js';

/* ---------- selection: both views move together; the long text goes in the panel ----------
 * A selection made as the map is loaded or read again, again, leaves open the tab of the panel the person has open,
 * such as the prompt being edited. */
export function select(id, fly, keepTrail = false, stepping = false, again = false) {
  if (!id) return;
  revealDepth(id);  // a part held deeper than the depth is broken out to be seen, VIEW-051
  if (fly && !again) touched();  // a node chosen holds an agent start's auto zoom off for a while, `TOUCHED`, VIEW-041
  const drawn = selectNow(id, fly, keepTrail, stepping, again), moved = S.panelFor !== id;
  // a new object is read from its top
  if (moved && S.selected === id) { S.panelFor = id; $('#p-object').scrollTop = 0; }
  if (fly && !again && S.selected === id && !keepsFocus(document.activeElement)) {
    largeView().focus({preventScroll: true});
  }
  return drawn;
}
/* A person who chose a node from elsewhere on the page goes on with the keys on the map; a text being written, an open
 * window and the maps themselves keep the focus. */
function keepsFocus(active) {
  if (!active || active === document.body || !shown(active)) return false;
  return Boolean(active.closest('input, textarea, select, [contenteditable="true"], .CodeMirror, #map2d, #stage')
    || overlayHolds(active));
}
function selectNow(id, fly, keepTrail, stepping, again) {
  const join = id.startsWith('p:') ? joinOf(id) : null;
  const entity = Boolean(MEM.network?.entities.includes(id));  // a node of the memory network open, VIEW-031
  const known = join || S.elements.has(id) || entity;
  const thing = IN.at(-1)?.things?.get(id) || S.items.get(id) || memoryThing(id);
  if (!known && !thing) return;
  if (!keepTrail) S.trail = [];
  if (!stepping && !MEM.key) remember(id);
  // auto zoom frames what the person selects anew, not the map loaded or read again, nor the node selected again as
  // a level is entered or left, VIEW-041
  const frame = !again && S.selected !== id;
  S.selected = id;
  S.cleared = false;
  window.metaform.onSelect?.(addressOf(id));  // the map view in an AI tool tells its agent, MCP-037
  setReach(id);
  if (!known) {
    S.neighbors = new Set();
    focus2D(id, frame);
    if (!again) showTab('object');
    renderThing(thing);
    return;
  }
  S.neighbors = neighborsOf(id, join);
  if (G) {
    G.nodeColor(G.nodeColor());
    const node = nodeIn(G.graphData(), id);
    if (fly && node) follow3d(id);
  }
  focus2D(id, frame);
  // The brief stays on view while the person walks the map from it; any other tab gives way to the object.
  const briefing = tabNow() === 'brief';
  // in the workspace every pane stays where the person left it, and those shown follow the selection
  if (WS.on) wsSelected();
  else {
    if (WS.active) WS.refresh(true);  // the page as written with the toolbar: its tools follow the selection too
    if (!again) showTab(briefing ? 'brief' : 'object');
    else if (briefing) renderBrief();
  }
  // A map read again leaves the Object tab as it is while nothing it was drawn from changed, so agents writing
  // elsewhere neither make it flicker nor take the person's place in it (2026-10-18).
  const print = MEM.key ? null : panelPrint(id);
  if (again && print !== null && print === S.panelPrint && S.panelFor === id) return undefined;
  S.panelPrint = print;
  // The panel's reads are returned, so a load waits for them before it says it is loaded.
  return MEM.key ? renderMemories(id) : join ? renderJoin(join) : renderObject(id);
}
/* What the Object tab of node `id` is drawn from on the page: its element or join, the joins it receives or holds,
 * the items and properties on any of them, and their open work, as one string to compare. */
function panelPrint(id) {
  const joins = S.joins.filter(one => 'p:' + one.id === id || one.receiver === id
    || one.elements.some(held => held.element_id === id));
  const on = new Set([id, ...joins.map(one => 'p:' + one.id)]);
  const items = [];
  for (const entry of S.items.values()) {
    const item = entry.item, target = item.target;
    if (on.has(item.element_id) || (target && on.has(target.kind === 'join' ? 'p:' + target.id : target.id))) {
      items.push([entry.key, entry.value, item.refs, item.extra]);
    }
  }
  return JSON.stringify([S.elements.get(id)?.element ?? null, joins, items]);
}
/* A selection becomes a step of the history Back and Forward walk, unless it is the step it is on: the steps forward
 * are dropped, as a browser drops them. */
function remember(id) {
  const path = IN.map(({key, label}) => ({key, label})), last = S.history[S.at];
  if (last && last.id === id && samePath(last.path, path)) return;
  S.history = [...S.history.slice(0, S.at + 1), {id, path}];
  S.at = S.history.length - 1;
}
/* What is beside a selection: in a memory network, the memories its relations name; for a join, its receiver and its
 * providers; for an element, what it receives from and what receives from it. */
function neighborsOf(id, join) {
  if (MEM.key) {
    const related = relation => relation.from === id ? [relation.to] : relation.to === id ? [relation.from] : [];
    return new Set([id, ...(MEM.network?.relations || []).flatMap(related)]);
  }
  if (join) return new Set([join.receiver, ...join.providers]);
  return new Set([id, ...S.joins.filter(item => item.receiver === id).flatMap(item => item.providers),
    ...S.joins.filter(item => item.providers.includes(id)).map(item => item.receiver)]);
}

export function refsOf(refs) {
  if (!refs || !refs.length) return null;
  return h('div', {class: 'refs'}, refs.map(ref => h('span', {}, h('span', {class: 'k'}, ref.key), ref.value)));
}
/* The work records of the selected object, MAP-046: each with its condition, note and task, held and reviewed,
 * and its resolution once done; read from /api/work for the node and written into the panel's work box. */
export function workPill(condition) { return h('span', {class: `pill work-${condition}`}, condition); }
/* A question at the node, MAP-050 and VIEW-021, as the question form wrote it: the question, then each part the agent
 * filled under its heading, each with Create ticket so the person can turn it into work. Open, it takes a typed answer
 * or a click on a choice; answered, the answer stays beside it. */
const FORM_PARTS = [['#1 Specifications reviewed:', 'Investigate why the specifications did not settle this'],
  ['#2 Why this is not a configuration option:', 'Review whether this should be a configuration option'],
  ['#3 Unexplained "Rich said":', 'Decipher this, or delete it and reconstruct a proper, clear specification']];
function formParts(text) {
  const lines = (text || '').split('\n'), parts = [];
  let question = [], current = null;
  for (const line of lines) {
    const part = FORM_PARTS.find(([heading]) => line.trim() === heading);
    if (part) { current = {heading: part[0], task: part[1], lines: []}; parts.push(current); continue; }
    (current ? current.lines : question).push(line);
  }
  return {question: question.join('\n').trim(),
    parts: parts.map(part => ({...part, text: part.lines.join('\n').trim()}))};
}
export function asked(record, metaform = S.base, full = false) {
  const answer = h('textarea', {class: 'answer', placeholder: 'Type an answer or a message'});
  const written = text => wrote('/api/answer', {id: record.id, answer: text, metaform});
  const send = h('button', {class: 'btn sm primary answer', type: 'button', onclick: async () => {
    if (!answer.value.trim()) return;
    send.disabled = true;
    if (!await written(answer.value)) send.disabled = false;
  }}, 'Send');
  const {question, parts} = formParts(record.text);
  const node = nodeOf(record);
  const reader = full ? null : h('button', {class: 'btn sm quiet read-full', type: 'button',
    title: 'Read the whole question in a large window', onclick: () => {
      fill($('#qa .body'), asked(record, metaform, true));
      $('#qa').hidden = false;
    }}, 'Read in full');
  return h('div', {class: full ? 'item work question-form full' : 'item work question-form'},
    h('div', {class: 'pills'}, workPill('question'), h('span', {class: 'pill'}, record.closed ? 'answered' : 'open'),
      record.by ? h('span', {class: 'pill'}, record.by) : null, reader),
    h('p', {class: 'asked'}, ...linked(question)),
    ...parts.map(part => formPart(part, node, question)),
    record.closed ? h('p', {class: 'obs'}, `Answer: ${record.answer || ''}`)
      : [suggestions(record, written), h('div', {class: 'typed'}, answer, send)],
    record.closed ? reopenButton(record, metaform) : null);
}
/* The answers the agent suggests, the one it recommends first: one click answers; the box takes anything else. */
function suggestions(record, written) {
  const suggested = (record.suggestions || []).map(String);
  if (!suggested.length) return null;
  const answer = async (event, text) => {
    const buttons = [...event.target.parentNode.children];
    for (const button of buttons) button.disabled = true;
    if (!await written(text)) for (const button of buttons) button.disabled = false;
  };
  return h('div', {class: 'choices'}, suggested.map((text, index) => h('button', {type: 'button',
    class: index ? 'suggestion' : 'suggestion recommended', onclick: event => answer(event, text)}, text)));
}
/* One part the agent filled under its heading, with Create ticket, at the node of the question. */
function formPart(part, node, question) {
  const create = () => {
    if ($('#qa')) $('#qa').hidden = true;
    giveWork(node, `${part.task}: ${part.text}\n\nFrom question: ${question}`);
  };
  return h('div', {class: 'form-part'},
    h('div', {class: 'heading'}, part.heading),
    h('p', {class: 'said'}, ...linked(part.text)),
    h('button', {class: 'btn sm create-ticket', type: 'button',
      title: 'Write a ticket from this part, at the node of the question', onclick: create}, 'Create ticket'));
}
/* Answered by mistake: Reopen clears the answer and the question waits again with its suggestions, MAP-050. */
function reopenButton(record, metaform) {
  return h('button', {class: 'btn sm reopen', type: 'button', onclick: async event => {
    event.target.disabled = true;
    if (!await wrote('/api/reopen', {id: record.id, metaform})) event.target.disabled = false;
  }}, 'Reopen');
}
$('#qa .close').onclick = () => { $('#qa').hidden = true; };
overlay($('#qa'), {kind: 'dialog', focus: 'textarea.answer'});
overlay($('#mergeAsk'), {kind: 'dialog', focus: '.yes'});
overlay($('#confirm'), {kind: 'dialog'});
/* The review-or-merge flow, VIEW-044: Review. while done work waits; a click takes it over for good, offers an agent's
 * help, and the help comes in a support window at the lower right. */
export const MERGE = {rows: [], chat: null, since: 0};
export async function renderMerges() {
  if (!S.project || FRAMED) return;
  try { MERGE.rows = (await read('merges')).merges || []; } catch { MERGE.rows = []; }
  noticeAttention();  // a merge waiting for review: the mascot tells the person, `ATTN`
  const at = seconds => new Date(seconds * 1000).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
  fill($('#reviewNotice'), MERGE.rows.map(row => {
    const ticket = (B.tickets || []).find(one => one.id === row.work_id);
    const what = ticket ? (ticket.task || ticket.note || '').slice(0, 80) : row.branch;
    return h('div', {class: 'notice'}, h('b', {}, 'Review.'),
      h('span', {}, ` ${what} · merges by itself at ${at(row.deadline)}`),
      h('button', {class: 'btn sm primary', type: 'button', onclick: event => takeReview(row.work_id, event.target)},
        'Review'));
  }));
  $('#reviewNotice').hidden = !MERGE.rows.length;
}
export async function takeReview(workId, button) {
  button.disabled = true;
  if (!await wrote('/api/merge-review', {work_id: workId})) { button.disabled = false; return; }
  await renderMerges();
  $('#mergeAsk .yes').onclick = async () => {
    $('#mergeAsk').hidden = true;
    openHelpdesk(workId, 'an agent', 'Waiting for the next available agent.', null, 'merge');
    if (!await wrote('/api/merge-assist', {work_id: workId})) drawHelpdesk('The agent could not be started.');
  };
  $('#mergeAsk .no').onclick = () => {
    $('#mergeAsk').hidden = true;
    toast('The merge is yours to handle; its countdown is off.');
  };
  OVERLAY.known.get($('#mergeAsk')).close = () => $('#mergeAsk .no').click();
  $('#mergeAsk').hidden = false;
}
