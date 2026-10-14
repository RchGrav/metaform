/* Managing memories, VIEW-031: editing, renaming, forgetting and unjoining them, and the orphaned memories menu. */
import '/page/app/memory/graph.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {toast, undoable, confirmAct} from '/page/app/core/controls.js';
import {S, read} from '/page/app/core/reads.js';
import {colorVar} from '/page/app/header/layers.js';
import {showAdmin} from '/page/app/header/admin.js';
import {nameOf, enter} from '/page/app/map2d/inside.js';
import {memoryLayer, memoryKey} from '/page/app/memory/graph.js';
import {select} from '/page/app/selection/select.js';
import {targetOf} from '/page/app/board/messages.js';
import {F, wrote} from '/page/app/board/history.js';
import {layerPill} from '/page/app/panel/object.js';

/* ---------- managing the memories, VIEW-031: memories can harm a project, so the person manages them here ----------
 * A memory in the panel, as the memory module keeps it: its type, its observations, its relations and the nodes it is
 * joined to, each edited or deleted in place. Every change is written with the memory module's commands through
 * /api/memory; an edit writes the new before it deletes the old, so a failure loses nothing. The page is told of the
 * change by map.changed, VIEW-018, and reads the memories again. */
async function memoryWrite(...steps) {
  return wrote('/api/memory', {steps: steps.map(([command, args]) => ({command, arguments: args}))});
}
/* What is typed in the panel's editors survives the panel drawn again, with the focus, VIEW-018. */
function keepDrafts(pane, draw) {
  const drafts = new Map([...pane.querySelectorAll('[data-draft]')].map(field => [field.dataset.draft, field.value]));
  const focused = document.activeElement?.closest('[data-draft]')?.dataset.draft;
  draw();
  for (const field of pane.querySelectorAll('[data-draft]')) {
    if (drafts.has(field.dataset.draft)) field.value = drafts.get(field.dataset.draft);
  }
  if (focused) pane.querySelector(`[data-draft="${CSS.escape(focused)}"]`)?.focus();
}
const EDITING = new Set();  // the editors open in the memory panel, kept open when it is drawn again
function joinPlace(join) {
  return join.address !== undefined ? join.address : `${join.receiver} → ${join.provider}`;
}
export function renderEntity(name, pane = $('#p-object')) {
  const entity = S.memory.entities.get(name);
  if (!entity) {
    return fill(pane, h('div', {class: 'eyebrow'}, 'Memory'), h('p', {class: 'empty'}, `No memory named ${name}.`));
  }
  const joins = S.memory.joins.filter(join => join.entity === name);
  const related = S.memory.relations.filter(relation => relation.from === name || relation.to === name);
  const others = [...S.memory.entities.keys()].filter(other => other !== name);
  const color = {'--c': `var(${colorVar(memoryLayer())})`};
  const draft = key => `${name}\u0000${key}`;
  const renaming = draft('rename'), naming = namingForm(name, entity, draft);
  const adding = h('textarea', {class: 'add-obs', 'data-draft': draft('add'), placeholder: 'A new observation'});
  const relating = h('input', {class: 'add-rel-type', 'data-draft': draft('reltype'),
    placeholder: 'relation, in active voice'});
  const target = h('select', {class: 'add-rel-to', 'aria-label': 'To'},
    others.map(other => h('option', {value: other}, other)));
  const rename = () => { EDITING.add(renaming); naming.hidden = false; naming.querySelector('.name').focus(); };
  keepDrafts(pane, () => fill(pane,
    h('div', {class: 'eyebrow'}, 'Memory'),
    h('h2', {}, name),
    h('div', {class: 'pills'}, h('span', {class: 'pill'}, entity.entityType), layerPill(memoryLayer())),
    h('div', {class: 'acts'},
      h('button', {class: 'btn sm rename', type: 'button', onclick: rename}, 'Rename or retype'),
      h('button', {class: 'btn sm danger forget', type: 'button', onclick: () => forget(name)}, 'Delete memory')),
    naming,
    h('div', {class: 'eyebrow'}, 'Observations'),
    entity.observations.length ? entity.observations.map(one => observationRow(name, one, color, draft))
      : h('p', {class: 'empty'}, 'No observations.'),
    adding, h('button', {class: 'btn sm add-obs', type: 'button', onclick: () => addObservation(name, adding)},
      'Add observation'),
    h('div', {class: 'eyebrow'}, 'Relations'),
    related.length ? related.map(one => relationRow(name, one, color)) : h('p', {class: 'empty'}, 'No relations.'),
    others.length ? h('div', {class: 'add-rel'}, relating, target, h('button', {class: 'btn sm add-rel', type: 'button',
      onclick: () => addRelation(name, relating, target)}, 'Add relation')) : null,
    h('div', {class: 'eyebrow'}, 'Kept at'),
    joins.length ? joins.map(one => joinedRow(one, color)) : h('p', {class: 'empty'}, 'Joined to no node.')));
}
/* One observation: its text with Edit and Delete, Delete undoable; or, while it is edited, its text in an editor with
 * Save, which writes the new before deleting the old, and Cancel. An editor open stays open when the panel is drawn
 * again, `EDITING`. */
function observationRow(name, one, color, draft) {
  const row = h('div', {class: 'item obs', style: color}), editing = draft('obs:' + one.content);
  const remove = async () => {
    if (await memoryWrite(['delete_observations', {deletions: [{entityName: name, observations: [one.content]}]}]))
      undoable('Deleted the observation.', async () => Boolean(await memoryWrite(['add_observations',
        {observations: [{entityName: name, contents: [one.content]}]}])));
  };
  const show = () => {
    EDITING.delete(editing);
    fill(row, h('p', {class: 'itemtext'}, one.content),
      h('div', {class: 'acts'}, h('button', {class: 'btn sm quiet edit', type: 'button', onclick: edit}, 'Edit'),
        h('button', {class: 'btn sm danger delete', type: 'button', onclick: remove}, 'Delete')));
  };
  const edit = () => {
    EDITING.add(editing);
    // its text, so the row is found by it
    const text = h('textarea', {'data-draft': editing, 'aria-label': 'The observation'}, one.content);
    const save = async () => {
      const changed = text.value.trim();
      if (!changed || changed === one.content) return show();
      EDITING.delete(editing);
      await memoryWrite(['add_observations', {observations: [{entityName: name, contents: [changed]}]}],
        ['delete_observations', {deletions: [{entityName: name, observations: [one.content]}]}]);
    };
    fill(row, text, h('div', {class: 'acts'}, h('button', {class: 'btn sm primary save', type: 'button', onclick: save},
      'Save'), h('button', {class: 'btn sm cancel', type: 'button', onclick: show}, 'Cancel')));
  };
  if (EDITING.has(editing)) edit(); else show();
  return row;
}
/* A link that selects a memory. */
const memoryLink = other => h('a', {class: 'link', href: '#',
  onclick: event => { event.preventDefault(); select(memoryKey(other), true); }}, other);
/* One relation of the memory, the other memory a link to it, with Delete, undoable. */
function relationRow(name, one, color) {
  const remove = async () => {
    const relations = [{from: one.from, to: one.to, relationType: one.relationType}];
    if (await memoryWrite(['delete_relations', {relations}]))
      undoable(`Deleted the relation ${one.from} ${one.relationType} ${one.to}.`,
        async () => Boolean(await memoryWrite(['create_relations', {relations}])));
  };
  return h('div', {class: 'item rel', style: color},
    one.from === name ? h('b', {}, name) : memoryLink(one.from), ` ${one.relationType} `,
    one.to === name ? h('b', {}, name) : memoryLink(one.to),
    h('div', {class: 'acts'}, h('button', {class: 'btn sm danger delete', type: 'button', onclick: remove}, 'Delete')));
}
/* One node the memory is kept at, a link into it where the map still holds it, with Take away. */
function joinedRow(one, color) {
  const go = event => { event.preventDefault(); enter(one.key); };
  return h('div', {class: 'item join', style: color},
    one.key ? h('a', {class: 'link', href: '#', onclick: go}, nameOf(one.key)) : h('b', {}, joinPlace(one)),
    one.orphaned ? h('small', {}, ' · orphaned, the map no longer holds it')
      : one.key ? h('small', {}, '; Enter goes there.') : null,
    h('div', {class: 'acts'}, h('button', {class: 'btn sm danger unjoin', type: 'button', onclick: () => unjoin(one)},
      'Take away')));
}
/* The memory's name and type, edited in place and saved as a rename, `renameEntity`. */
function namingForm(name, entity, draft) {
  const renaming = draft('rename');
  const naming = h('div', {class: 'naming', hidden: !EDITING.has(renaming)},
    h('input', {class: 'name', 'data-draft': draft('name'), value: name, 'aria-label': 'Name'}),
    h('input', {class: 'type', 'data-draft': draft('type'), value: entity.entityType, 'aria-label': 'Type'}),
    h('button', {class: 'btn sm primary save-entity', type: 'button',
      onclick: () => renameEntity(name, naming.querySelector('.name').value.trim(),
        naming.querySelector('.type').value.trim())}, 'Save'),
    h('button', {class: 'btn sm cancel', type: 'button',
      onclick: () => { EDITING.delete(renaming); naming.hidden = true; }}, 'Cancel'));
  return naming;
}
/* A new observation written; its box emptied before the write, so the panel drawn again for it does not keep it, and
 * given back its text if the write fails. */
async function addObservation(name, adding) {
  const text = adding.value.trim();
  if (!text) return;
  adding.value = '';
  const observations = [{entityName: name, contents: [text]}];
  if (!await memoryWrite(['add_observations', {observations}])) adding.value = text;
}
async function addRelation(name, relating, target) {
  const type = relating.value.trim();
  if (!type) return;
  relating.value = '';
  const relations = [{from: name, to: target.value, relationType: type}];
  if (!await memoryWrite(['create_relations', {relations}])) relating.value = type;
}
/* A memory renamed or retyped: the reference server has no command for it, so it is made again under its new name and
 * type with its observations, joined again to each node of the map it was joined to, its relations made again, and the
 * old one deleted. A join the map no longer holds cannot be made again. */
async function renameEntity(name, next, type) {
  const entity = S.memory.entities.get(name);
  EDITING.delete(`${name}\u0000rename`);
  if (!entity || !next || !type || (next === name && type === entity.entityType)) return renderEntity(name);
  const made = {name: next, entityType: type, observations: entity.observations.map(one => one.content)};
  const again = S.memory.joins.filter(join => join.entity === name && join.key)
    .map(join => ['create_entities', {entities: [made], node: targetOf(join.key)}]);
  const swap = value => value === name ? next : value;
  const related = S.memory.relations.filter(relation => relation.from === name || relation.to === name)
    .map(relation => ({from: swap(relation.from), to: swap(relation.to), relationType: relation.relationType}));
  const steps = [['create_entities', {entities: [made]}], ...again,
    ...(related.length ? [['create_relations', {relations: related}]] : [])];
  const gone = ['delete_entities', {entityNames: [name]}];
  // the same name: the old goes first, so the new does not meet it; another: the new is made first, so nothing is lost
  const done = next === name ? await memoryWrite(gone, ...steps) : await memoryWrite(...steps, gone);
  if (done) S.selected = memoryKey(next);
}
/* Taking a memory away, VIEW-031: a wrong memory misleads every agent that reads it, and so does one deleted by a slip.
 * What the map still holds is made again by Undo: the memory with its observations, its joins to the nodes drawn and
 * its relations. A join the map no longer holds cannot be made again, so taking that away is asked first, naming what
 * is lost. */
export const plural = (count, one, many = one + 's') => `${count} ${count === 1 ? one : many}`;
function remade(name) {
  const entity = S.memory.entities.get(name);
  const made = {name, entityType: entity.entityType, observations: entity.observations.map(one => one.content)};
  const joins = S.memory.joins.filter(join => join.entity === name);
  const relations = S.memory.relations.filter(relation => relation.from === name || relation.to === name)
    .map(relation => ({from: relation.from, to: relation.to, relationType: relation.relationType}));
  const held = joins.filter(join => !join.orphaned && join.key);
  const steps = [['create_entities', {entities: [made]}],
    ...held.map(join => ['create_entities', {entities: [made], node: targetOf(join.key)}]),
    ...(relations.length ? [['create_relations', {relations}]] : [])];
  return {entity, relations, lost: joins.filter(join => !held.includes(join)), steps};
}
async function forget(name, after = () => {}) {
  if (!S.memory.entities.has(name)) return;
  const again = remade(name), gone = ['delete_entities', {entityNames: [name]}];
  if (again.lost.length) {
    const sure = await confirmAct({title: `Delete the memory ${name}?`,
      text: 'No agent reads it again. It cannot be brought back from here, since the map no longer holds a node it was '
        + 'kept at.',
      lost: [`${name}, ${again.entity.entityType}, with ${plural(again.entity.observations.length, 'observation')}`,
        ...again.relations.map(relation => `The relation ${relation.from} ${relation.relationType} ${relation.to}`),
        ...again.lost.map(join => `Its join to ${joinPlace(join)}, which the map no longer holds`)],
      verb: 'Delete memory'});
    if (sure && await memoryWrite(gone)) after();
    return;
  }
  if (!await memoryWrite(gone)) return;
  after();
  undoable(`Deleted the memory ${name}.`, async () => Boolean(await memoryWrite(...again.steps)));
}
async function unjoin(join, after = () => {}) {
  const entity = S.memory.entities.get(join.entity);
  if (join.orphaned || !join.key) {
    const sure = await confirmAct({title: 'Take this join away?',
      text: `The memory stays. The join cannot be made again, since the map no longer holds ${joinPlace(join)}.`,
      lost: [`The join from ${join.entity} to ${joinPlace(join)}`],
      kept: [entity ? `${join.entity}, with ${plural(entity.observations.length, 'observation')}` : join.entity],
      verb: 'Take away the join'});
    if (sure && await memoryWrite(['unjoin', {id: join.join_id}])) after();
    return;
  }
  if (!await memoryWrite(['unjoin', {id: join.join_id}])) return;
  after();
  const again = {entities: [{name: join.entity, entityType: entity?.entityType || 'memory', observations: []}],
    node: targetOf(join.key)};
  undoable(`Took ${join.entity} away from ${nameOf(join.key)}.`,
    async () => Boolean(await memoryWrite(['create_entities', again])));
}
/* ---------- the orphaned menu, LAYER-013: memories that lost their node show what they were
 * attached to ----------
 * The memory joins the map no longer holds, from `memory orphaned`, each with what it was attached to, and the memories
 * joined to no node at all; a join is taken away or its memory deleted from here. */
export const O = {open: false};
async function orphans() {
  let lost;
  try { lost = (await read('memory-orphaned')).joins; } catch (error) { toast(error.message); return; }
  Object.assign(F, {id: null, which: null, ids: new Set(), drawn: new Map()});
  O.open = true;
  const loose = [...S.memory.entities.keys()].filter(name => !S.memory.joins.some(join => join.entity === name));
  $('#float .title').textContent = 'Orphaned memories';
  fill($('#float .body'),
    lost.length ? lost.map(orphanRow) : h('p', {class: 'empty'}, 'No memory join is orphaned.'),
    loose.length ? [h('div', {class: 'eyebrow'}, 'Joined to no node'), loose.map(looseRow)] : null);
  $('#float').hidden = false;
}
const forgetButton = name => h('button', {class: 'btn sm danger forget', type: 'button',
  onclick: () => forget(name, orphans)}, 'Delete memory');
/* An orphaned join: its memory, what it was attached to, and its join taken away or its memory deleted. */
function orphanRow(join) {
  return h('div', {class: 'ticket orphan'}, h('b', {}, join.entity),
    h('p', {class: 'note'}, `was attached to ${joinPlace(join)}`),
    h('div', {class: 'acts'}, h('button', {class: 'btn sm unjoin', type: 'button',
      onclick: () => unjoin({...join, orphaned: true}, orphans)}, 'Take away the join'), forgetButton(join.entity)));
}
/* A memory joined to no node, deleted from here. */
function looseRow(name) {
  return h('div', {class: 'ticket loose'}, h('b', {}, name), h('div', {class: 'acts'}, forgetButton(name)));
}
export function renderOrphans() {
  $('#orphanBtn').textContent = `Orphaned memories ${S.memory.orphaned}`;
  if (O.open && !$('#float').hidden && $('#float .title').textContent === 'Orphaned memories') orphans();
}
$('#orphanBtn').onclick = () => { showAdmin(false); orphans(); };
