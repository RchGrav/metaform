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
import {CONDITION_WORDS, KIND_WORDS, linked} from '/page/app/board/refs.js';
import {wrote} from '/page/app/board/history.js';
import {noteBy} from '/page/app/task/notes.js';
import {showTab} from '/page/app/panel/prompts.js';
import {summonAgent, summonPicker} from '/page/app/agents/pickers.js';
import {following} from '/page/app/live/stream.js';

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
  // One row for the part: its state, Raise an issue and one Chat for the node; then one row for each ticket on it.
  fill(box, h('div', {class: 'workhead'}, h('div', {class: 'eyebrow'}, 'Work'), state, raiseButton(issue),
    chatButton(nodeTalk(key), calledOf(key) || 'this node')), issue,
    records.map(workRow));
}
const STATES = [['', 'state: not set'], ['unbuilt', 'unbuilt'], ['under-construction', 'under construction'],
  ['built', 'built'], ['broken', 'broken']];
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
    onchange: writeState}, ...STATES.map(([value, text]) => h('option', {value, selected: current === value}, text)));
}
/* Raise an issue, the person says what is wrong in their words; a sentinel investigates and brings
 * proposals to the chat; what they choose becomes held tickets. The only way work on an issue begins. */
function issueForm(key) {
  const issue = h('div', {class: 'issue', hidden: true},
    h('textarea', {rows: 4, placeholder: 'What is wrong, what you expected, and how to make it happen.',
      'aria-label': 'What is wrong'}),
    h('div', {class: 'issueacts'}, h('button', {class: 'btn sm primary send', type: 'button',
      onclick: event => sendIssue(event, issue, key)}, 'Send to the sentinel'), h('span', {class: 'pickhost'})));
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
    ? 'Queued: this part is in use, so the sentinel starts when that work is done.'
    : 'Queued: every agent slot is in use, so the sentinel starts when one is free.') : STANDBY;
  openHelpdesk(started.work_id, `the sentinel on ${calledOf(key) || 'this node'}`, queued, started.session_id,
    'sentinel');
}
function raiseButton(issue) {
  const raise = h('button', {class: 'btn sm raise', type: 'button', 'aria-expanded': 'false',
    title: 'Say what is wrong with this part; a sentinel investigates and brings you proposals',
    onclick: () => toggleIssue(issue, raise)}, 'Raise an issue');
  return raise;
}
function toggleIssue(issue, raise) {
  issue.hidden = !issue.hidden;
  raise.setAttribute('aria-expanded', String(!issue.hidden));
  // the one picker of the issue form, moved into this form: the agent the sentinel starts with
  if (!issue.hidden) {
    issue.querySelector('.pickhost').append(summonPicker('raise', {label: 'Agent for the sentinel'}));
    issue.querySelector('textarea').focus();
  }
}
const pill = text => h('span', {class: 'pill'}, text);
/* One ticket on the part: its state, kind and whether it is done, held or reviewed; its note, task and resolution. */
const workRow = record => h('div', {class: 'item work'},
  h('div', {class: 'pills'}, record.condition ? workPill(record.condition) : null,
    pill(KIND_WORDS[record.kind] || record.kind || 'task'), pill(record.done ? 'done' : 'open'),
    record.held ? pill('held') : null, record.reviewed ? pill('reviewed') : null),
  record.note ? h('p', {}, ...linked(record.note)) : null,
  record.task ? h('p', {class: 'fn'}, ...linked(record.task)) : null,
  record.done ? h('p', {class: 'obs'}, 'Resolved: ', ...linked(record.resolution)) : null);
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
    h('button', {class: 'btn sm quiet tobrief', type: 'button', 'aria-controls': 'p-brief',
      title: 'The brief an agent working here is handed, and the memories, messages and work numbered here',
      onclick: () => { showTab('brief'); $('#t-brief').focus(); }},
    'What an agent reads here', h('i', {class: 'i i-chev', 'aria-hidden': 'true'})),
    h('div', {id: 'work'}),
    h('div', {id: 'items'}),
    h('div', {class: 'eyebrow'}, 'Joins held by this element'),
    held.length ? held.map(join => joinCard(join, 'provider'))
      : h('p', {class: 'empty'}, 'This element receives nothing here.'),
    serves.length ? h('div', {class: 'eyebrow'}, 'Serves') : null,
    serves.map(join => joinCard(join, 'receiver')));
  renderWork(`element:${id}`, id);
  try {
    // While the page follows an intake being recorded, the element is shown as the building layer records it; that
    // layer is in no reading context until it finishes, LAYER-007, so a node read could only find nothing and is not
    // made.
    const node = following() ? {layers: []} : await read('node', {target: `element:${id}`, ...viewLayers()});
    if (S.selected !== id) return;
    const box = $('#items');
    for (const group of node.layers || []) layerItems(box, group);
    memoryItems(box, node.memory || {});
    const context = await read('context', {address: element.address, limit: 0, ...viewLayers()});
    if (S.selected !== id) return;
    const kinds = [['Properties that apply here', context.applying],
      ['Properties attached toward the leaves', context.visible]];
    for (const [title, found] of kinds) properties(box, title, found, element);
  } catch (error) {  // nothing in the layers turned on, such as an intake still being built, is not an error
    if (error.status !== 404) toast(error.message);
  }
}
/* A layer's items at the element, under the layer's name. */
function layerItems(box, group) {
  const items = group.items || [];
  if (!items.length) return;
  box.append(h('div', {class: 'eyebrow'}, group.kind === 'memory' ? 'Memory' : group.layer),
    ...items.map(item => h('div', {class: 'item' + (item.orphaned ? ' orphaned' : ''),
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
    box.append(h('div', {class: 'eyebrow'}, 'Memory'), ...memory.entities.map(remembered),
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
