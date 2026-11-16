/* The panel's object: its work, joins and items as cards and tables, and renderObject. */
import '/page/app/task/notes.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {toast} from '/page/app/core/controls.js';
import {S, read, viewLayers} from '/page/app/core/reads.js';
import {colorVar} from '/page/app/header/layers.js';
import {labelOf} from '/page/app/map2d/inside.js';
import {memoryLayer, memoryKey} from '/page/app/memory/graph.js';
import {flowArrow} from '/page/app/map2d/flow2d.js';
import {select, refsOf, workPill} from '/page/app/selection/select.js';
import {DOCK, STANDBY} from '/page/app/dock/embody.js';
import {openHelpdesk} from '/page/app/dock/threads.js';
import {chatButton, nodeTalk} from '/page/app/dock/send.js';
import {calledOf} from '/page/app/board/messages.js';
import {CONDITION_WORDS, KIND_WORDS, ticketHead} from '/page/app/board/refs.js';
import {wrote, ageOf} from '/page/app/board/history.js';
import {noteBy} from '/page/app/task/notes.js';
import {showTab} from '/page/app/panel/prompts.js';
import {summonAgent, summonPicker} from '/page/app/agents/pickers.js';
import {following} from '/page/app/live/stream.js';
import {openRoundtable} from '/page/app/roundtable/stage.js';
import {renderLocalView} from '/page/app/panel/localview.js';

export async function renderWork(target, key, also = null) {
  let records = [];
  try {
    records = (await read('work', {node: target, limit: 0})).results;
    if (also) records = [...records, ...(await read('work', {node: also, limit: 0})).results];
  } catch (error) { toast(error.message); }
  const box = $('#work');
  if (!box || S.selected !== key) return;
  const held = records.find(record => !record.done && record.condition);
  const state = stateSelect(held ? held.condition : '', () => renderWork(target, key, also), target, key);
  const issue = issueForm(key);
  const tickets = records.filter(record => record.is_work), open = tickets.filter(record => !record.done);
  const past = tickets.filter(record => record.done).sort((one, two) => String(two.done).localeCompare(one.done));
  // One row for the part: its state, Raise an issue, one Chat for the node and, for an element, its Roundtable; then
  // one line for each open ticket on it, and the done ones folded, newest first.
  fill(box, h('div', {class: 'workhead'}, h('div', {class: 'eyebrow'}, 'Open work'), state, raiseButton(issue),
    chatButton(nodeTalk(key), calledOf(key) || 'this node'), S.elements.has(key) ? roundtableButton() : null), issue,
    open.length ? open.map(workRow) : h('p', {class: 'empty'}, 'No open work here.'),
    folded('Past work', past.length, past.length ? past.map(workRow) : h('p', {class: 'empty'}, 'No past work here.')));
}
/* A part of the tab folded closed under one line with its count; a person opens it when they want it. */
function folded(title, count, ...body) {
  return h('details', {class: 'fold'}, h('summary', {}, counted(title, count)), ...body);
}
const counted = (title, count) => (count === null ? title : `${title} · ${count}`);
// a part with no state is built, the normal state, which marks nothing: built and none are one choice, MAP-046
const STATES = [['unbuilt', 'unbuilt'], ['under-construction', 'under construction'], ['built', 'built'],
  ['broken', 'broken']];
/* The state of the part, written as it is chosen and the work drawn again. */
function stateSelect(current, redraw, target, key) {
  async function writeState(event) {
    event.target.disabled = true;
    const written = await wrote('/api/state', {node: target, condition: event.target.value});
    event.target.disabled = false;
    if (written) {
      toast(`${calledOf(key) || 'The part'} is ${CONDITION_WORDS[event.target.value] || 'built'}.`);
      redraw();
    }
  }
  return h('select', {class: 'state', 'aria-label': 'The state of this part',
    title: 'The state of this part: a stage on its way to existing, or broken. Built draws nothing',
    onchange: writeState}, ...STATES.map(([value, text]) => h('option', {value, selected: (current || 'built') === value}, text)));
}
/* Raise an issue: the person says what is wrong in their words, and an agent takes it up in the chat. */
function issueForm(key) {
  const issue = h('div', {class: 'issue', hidden: true},
    h('textarea', {rows: 4, placeholder: 'What is wrong, what you expected, and how to make it happen.',
      'aria-label': 'What is wrong'}),
    h('div', {class: 'issueacts'}, h('button', {class: 'btn sm primary send', type: 'button',
      onclick: event => sendIssue(event, issue, key)}, 'Send'), h('span', {class: 'pickhost'})));
  return issue;
}
async function sendIssue(event, issue, key) {
  const text = issue.querySelector('textarea').value.trim();
  if (!text) { toast('Say what is wrong.'); return; }
  event.target.disabled = true;
  const agent = summonAgent();
  const started = await wrote('/api/raise', {...nodeTalk(key), text, ...(agent ? {agent} : {})});
  event.target.disabled = false;
  if (!started) return;
  issue.hidden = true;
  if (started.conversation) DOCK.mine = started.work_id;
  const queued = started.state === 'queued' ? (Array.isArray(started.waiting_on)
    ? 'Queued: this part is in use, so the agent starts when that work is done.'
    : 'Queued: every agent slot is in use, so the agent starts when one is free.') : STANDBY;
  openHelpdesk(started.work_id, `the issue on ${calledOf(key) || 'this node'}`, queued, started.session_id,
    'conversation');
}
/* Roundtable, code.interface.graphical#131: a table of agents debates the person's question about this part on the
 * 3D map's stage, T. */
const roundtableButton = () => h('button', {class: 'btn sm roundtablebtn', type: 'button', 'aria-keyshortcuts': 'T',
  title: 'Ask a table of agents a question about this part and watch them debate it (T)',
  onclick: () => openRoundtable()}, 'Roundtable');
function raiseButton(issue) {
  const raise = h('button', {class: 'btn sm raise', type: 'button', 'aria-expanded': 'false',
    title: 'Say what is wrong with this part; an agent takes it up in the chat',
    onclick: () => toggleIssue(issue, raise)}, 'Raise an issue');
  return raise;
}
function toggleIssue(issue, raise) {
  issue.hidden = !issue.hidden;
  raise.setAttribute('aria-expanded', String(!issue.hidden));
  // the one picker of the issue form, moved into this form: the agent that takes the issue up
  if (!issue.hidden) {
    issue.querySelector('.pickhost').append(summonPicker('raise', {label: 'Agent'}));
    issue.querySelector('textarea').focus();
  }
}
const pill = text => h('span', {class: 'pill'}, text);
/* One ticket on the part on one line, so a glance says what it is: its condition, its kind, its number and its
 * title, and once done, how long since. A click opens the whole ticket, as the board's Inspect does; its body is never
 * here. */
const workRow = record => h('button', {class: 'item work line', type: 'button', title: 'Open this ticket',
  onclick: () => openTicket(record.id)},
record.condition ? workPill(record.condition) : null, pill(KIND_WORDS[record.kind] || record.kind || 'task'),
ticketHead(record), record.done ? ageOf(record) : null);
function openTicket(id) {
  const project = S.project, base = S.base || '';
  import('/page/app/board/detail.js').then(({ticketDetail}) => ticketDetail(id, project, base));
}
export function layerPill(name) {
  return h('span', {class: 'pill layer', style: {'--c': `var(${colorVar(name)})`}}, name);
}
function elementLink(id, address) {
  const entry = S.elements.get(id);
  return h('a', {class: 'link', href: '#', onclick: event => { event.preventDefault(); select(id, true); }},
    entry ? labelOf(entry.element) : address);
}
function joinCard(join, side) {
  // A join seen from an element it holds names its receiver; seen from its receiver, it names every element it holds.
  const others = side === 'provider' ? (join.elements || []).map(each => elementLink(each.element_id, each.address))
    : [elementLink(join.receiver, join.receiver_address)];
  return h('div', {class: 'join'},
    h('div', {class: 'row'},
      h('span', {class: 'dir'}, `${side} · `, ...others.flatMap((link, at) => at ? [', ', link] : [link])),
      h('span', {class: 'lay', style: {'--c': `var(${colorVar(join.layer)})`}}, join.layer)),
    join.purpose ? h('p', {}, join.purpose) : null,
    join.ef ? h('p', {class: 'fn'}, join.ef) : null);
}
/* An item's value as text: an object as one `field: value` line per field it holds, empty fields left out, so a layer
 * such as intake details reads as fields, not as raw data. */
const filled = value => value !== null && value !== undefined && value !== ''
  && !(Array.isArray(value) && !value.length);
const fieldText = value => value && typeof value === 'object' ? JSON.stringify(value) : String(value);
export function itemText(value) {
  if (Array.isArray(value)) return value.map(fieldText).join('\n');
  if (value && typeof value === 'object') {
    return Object.entries(value).filter(([, each]) => filled(each))
      .map(([key, each]) => `${key}: ${fieldText(each)}`).join('\n');
  }
  return String(value ?? '');
}
/* The same value for the panel: an object as a table of its fields. */
export function itemView(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return itemText(value);
  return h('dl', {class: 'fields'}, Object.entries(value).filter(([, each]) => filled(each))
    .flatMap(([key, each]) => [h('dt', {}, key), h('dd', {}, fieldText(each))]));
}
/* A selected join shows only itself, so nothing needs finding in its receiver's text. */
export function renderJoin(join) {
  // A join has no name of its own, MAP-020: it is headed by the parts it joins, and its purpose and function are read
  // below as text.
  const called = id => S.elements.has(id) ? labelOf(S.elements.get(id).element) : null;
  const providers = (join.elements || []).map(each => called(each.element_id) || each.address).join(', ');
  fill($('#p-object'),
    h('div', {class: 'eyebrow'}, 'Join'),
    h('h2', {}, `${called(join.receiver) || join.receiver_address} ${flowArrow(join)} `
      + `${providers || join.provider_address}`),
    h('p', {class: 'meta'}, elementLink(join.receiver, join.receiver_address), ' receives from ',
      ...(join.elements || []).flatMap((each, at) => [at ? ', ' : '', elementLink(each.element_id, each.address)]),
      '.'),
    (join.open_work || []).length ? h('div', {class: 'pills'}, join.open_work.map(workPill)) : null,
    joinCard(join, 'provider'),
    h('div', {id: 'work'}));
  renderWork(`join:${join.id}`, 'p:' + join.id);
}
export async function renderObject(id) {
  const {element} = S.elements.get(id);
  const pane = $('#p-object');
  const held = S.joins.filter(join => join.receiver === id);
  const serves = S.joins.filter(join => join.providers.includes(id));
  // The heading is its short name, the address read through name_length, VIEW-009; what the project calls it and its
  // address follow, each with its label, so neither is taken for the other.
  fill(pane,
    h('div', {class: 'eyebrow'}, 'Element'),
    h('h2', {}, element.short_name || element.address),
    h('dl', {class: 'facts'},
      element.name ? [h('dt', {}, 'Project name'), h('dd', {class: 'canonical'}, element.name)] : null,
      h('dt', {}, 'Address'), h('dd', {class: 'addr'}, element.address)),
    h('div', {class: 'pills'}, element.role ? h('span', {class: 'pill'}, element.role) : null,
      (element.open_work || []).map(workPill), layerPill(element.layer),
      h('span', {class: 'pill'}, `${held.length} held · ${serves.length} served`)),
    h('div', {id: 'localview', class: 'localview', hidden: true}),
    h('button', {class: 'btn sm quiet tobrief', type: 'button', 'aria-controls': 'p-brief',
      title: 'The brief an agent working here is handed, and the memories, messages and work numbered here',
      onclick: () => { showTab('brief'); $('#t-brief').focus(); }},
    'What an agent reads here', h('i', {class: 'i i-chev', 'aria-hidden': 'true'})),
    // A person's context is far smaller than an agent's: first the memories, what a person opens a node for, then its
    // open work; its past work, joins and knowledge fold, since the brief tab numbers the history and the map shows the
    // joins and the layers.
    h('div', {id: 'memories'}, h('div', {class: 'eyebrow'}, 'Memories')),
    h('div', {id: 'work'}),
    folded('Joins', held.length + serves.length,
      h('div', {class: 'eyebrow'}, 'Joins held by this element'),
      held.length ? held.map(join => joinCard(join, 'provider'))
        : h('p', {class: 'empty'}, 'This element receives nothing here.'),
      serves.length ? h('div', {class: 'eyebrow'}, 'Serves') : null,
      serves.map(join => joinCard(join, 'receiver'))),
    folded('Knowledge', null, h('div', {id: 'items'})));
  renderWork(`element:${id}`, id);
  renderLocalView(id);
  try {
    // While the page follows an intake being recorded, the element is shown as the building layer records it; that
    // layer is in no reading context until it finishes, LAYER-007, so a node read could only find nothing and is not
    // made.
    // An element that is not on the map shown, as one remembered from before the project was cleared, has nothing to
    // read: no request is made for it.
    const node = following() || !S.elements.has(id) ? {layers: []}
      : await read('node', {target: `element:${id}`, ...viewLayers()});
    if (S.selected !== id) return;
    const kept = $('#memories'), box = $('#items');
    for (const group of node.layers || []) layerItems(group.kind === 'memory' ? kept : box, group);
    memoryItems(kept, node.memory || {});
    const context = await read('context', {address: element.address, limit: 0, ...viewLayers()});
    if (S.selected !== id) return;
    const kinds = [['Properties that apply here', context.applying],
      ['Properties attached toward the leaves', context.visible]];
    for (const [title, found] of kinds) properties(box, title, found, element);
    for (const scoped of context.knowledge || []) {
      const section = h('details', {class: 'scoped-knowledge'},
        h('summary', {}, `${scoped.layer} · applies from ${scoped.scope}`),
        h('p', {}, `Source: ${scoped.source}. Layer selection and masks control this context.`));
      layerItems(section, {layer: scoped.layer, items: scoped.items || []});
      properties(section, 'Scoped properties', scoped.properties || [], element);
      for (const join of scoped.joins || []) section.append(h('div', {class: 'join'},
        h('p', {class: 'meta'}, join.receiver_address || scoped.source),
        join.purpose ? h('p', {}, join.purpose) : null,
        join.ef ? h('p', {class: 'fn'}, join.ef) : null));
      box.append(section);
    }
  } catch (error) {  // nothing in the layers turned on, such as an intake still being built, is not an error
    if (error.status !== 404) toast(error.message);
  }
  if (S.selected !== id) return;
  const kept = $('#memories'), box = $('#items');
  if (kept && kept.children.length === 1) kept.append(h('p', {class: 'empty'}, 'No memories are kept here.'));
  // the knowledge counted once read: each item, property and join it holds
  if (box) box.closest('details').querySelector('summary').textContent =
    counted('Knowledge', box.querySelectorAll('.item, .join').length);
}
/* A layer's items at the element, under the layer's name; a memory layer's under the Memories heading alone. */
function layerItems(box, group) {
  const items = group.items || [];
  if (!items.length) return;
  if (group.kind !== 'memory') box.append(h('div', {class: 'eyebrow'}, group.layer));
  box.append(...items.map(item => h('div', {class: 'item' + (item.orphaned ? ' orphaned' : ''),
    style: {'--c': `var(${colorVar(group.layer)})`}},
  itemView(item.value), item.state ? ` · ${item.state}` : '', refsOf(item.refs))));
}
/* What the memory module adds to the node's read, as `map node` gives it, BASE-035: its one note, and while memory
 * shows here, the memories kept at it and those on the joins it receives and provides, LAYER-013 and VIEW-034. */
function memoryItems(box, memory) {
  const color = {'--c': `var(${colorVar(memoryLayer())})`};
  const open = (event, entity) => { event.preventDefault(); select(memoryKey(entity.name), true); };
  const remembered = entity => h('div', {class: 'item', style: color},
    h('a', {class: 'link', href: '#', onclick: event => open(event, entity)}, entity.name),
    h('small', {}, ` · ${entity.entityType}`), entity.observations.map(text => h('p', {class: 'itemtext'}, text)));
  if (memory.note) {
    box.append(h('div', {class: 'eyebrow'}, 'Note'), h('div', {class: 'item note', style: color},
      h('p', {class: 'itemtext'}, memory.note.text), h('small', {}, noteBy(memory.note))));
  }
  if ((memory.entities || []).length) {
    box.append(...memory.entities.map(remembered),
      ...(memory.relations || []).map(relation =>
        h('p', {class: 'meta'}, `${relation.from} ${relation.relationType} ${relation.to}`)));
  }
  for (const join of memory.joins || []) {
    box.append(h('div', {class: 'eyebrow'}, `Memory on ${join.receiver} → ${join.provider}`),
      ...join.entities.map(remembered));
  }
}
/* Properties read in the element's context, each with its layer and, when it is attached elsewhere, where. */
function properties(box, title, found, element) {
  if (!found.length) return;
  const where = property => property.address && property.address !== element.address ? ' · at ' + property.address : '';
  box.append(h('div', {class: 'eyebrow'}, title), ...found.map(property => h('div', {class: 'item',
    style: {'--c': `var(${colorVar(property.layer)})`}},
  itemText(property.value), h('div', {class: 'refs'}, `${property.layer}${where(property)}`),
  refsOf(property.refs))));
}
