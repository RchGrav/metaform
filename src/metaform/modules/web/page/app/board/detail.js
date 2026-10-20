/* Ticket inspection is pinned to its project/base, including every save after another tab or project opens. */
import {h, fill} from '/page/app/core/dom.js';
import {overlay} from '/page/app/core/overlays.js';
import {S, read} from '/page/app/core/reads.js';
import {wrote} from '/page/app/board/history.js';
import {richText} from '/page/app/session/text.js';

const DETAIL = {box: null, body: null, serial: 0};

const label = value => String(value ?? '').replace(/[&<>"\n\r]/g,
  char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', '\n': ' ', '\r': ' '})[char]);

/* Observations are distinct graph nodes; relations keep their recorded direction and type. */
export function memoryMarkdown(graph) {
  const names = new Map(), lines = ['```mermaid', 'flowchart LR'];
  const entity = name => {
    if (!names.has(name)) {
      names.set(name, `e${names.size}`);
      lines.push(`  ${names.get(name)}["${label(name)}"]`);
    }
    return names.get(name);
  };
  let fact = 0;
  for (const one of graph.entities || []) {
    const id = entity(one.name);
    for (const observation of one.observations || []) {
      const node = `o${fact++}`;
      lines.push(`  ${node}["${label(typeof observation === 'string' ? observation : observation.content)}"]`);
      lines.push(`  ${id} -->|observation| ${node}`);
    }
  }
  for (const relation of graph.relations || []) {
    const from = entity(relation.from), to = entity(relation.to);
    lines.push(`  ${from} -->|"${label(relation.relationType)}"| ${to}`);
  }
  lines.push('```');
  return names.size ? lines.join('\n') : '';
}

export async function ticketDetail(workId, project = S.project, base = S.base || '') {
  const serial = ++DETAIL.serial, scope = {project, base};
  if (!DETAIL.box) {
    DETAIL.body = h('div', {class: 'body'});
    DETAIL.ref = h('span', {class: 'ref hint'});
    DETAIL.reload = h('button', {class: 'btn sm quiet reload', type: 'button', title: 'Read the ticket again'}, 'Reload');
    DETAIL.box = h('section', {id: 'ticketDetail', class: 'window dialog wide', role: 'dialog',
      'aria-label': 'Ticket details', hidden: true},
    h('div', {class: 'titlebar'}, h('strong', {class: 'title'}, 'Ticket details'), DETAIL.ref, h('span', {class: 'grow'}),
      DETAIL.reload,
      h('button', {class: 'btn close', type: 'button', 'aria-label': 'Close ticket',
        onclick: () => { DETAIL.box.hidden = true; }}, '×')), DETAIL.body);
    document.body.append(DETAIL.box);
    overlay(DETAIL.box, {kind: 'window', close: () => { DETAIL.box.hidden = true; }});
  }
  fill(DETAIL.body, h('p', {}, 'Loading ticket…'));
  DETAIL.box.hidden = false;
  try {
    const data = await read('ticket-detail', {...scope, work_id: workId});
    if (serial !== DETAIL.serial) return;
    let revision = data.revision;
    const ticket = data.ticket;
    DETAIL.ref.textContent = `${scope.project} · ${data.item || workId}`;
    DETAIL.reload.onclick = () => ticketDetail(workId, scope.project, scope.base);
    const title = h('input', {name: 'title', value: ticket.title || '', placeholder: 'Title'});
    // the task and the note take the room their words need, within the window, instead of a strip that scrolls
    const rowsFor = (text, least, most) => String(Math.max(least, Math.min(most, (text || '').split('\n').length + 1)));
    const task = h('textarea', {name: 'task', rows: rowsFor(ticket.task, 8, 24)}, ticket.task || '');
    const note = h('textarea', {name: 'note', rows: rowsFor(ticket.note, 3, 12)}, ticket.note || '');
    const kind = h('select', {name: 'kind'}, ['', 'broken', 'flawed', 'enhancement'].map(value =>
      h('option', {value, selected: value === (ticket.kind || '')}, value || 'Task')));
    const status = h('p', {role: 'status'});
    const save = h('button', {class: 'btn primary', type: 'submit'}, 'Save changes');
    const form = h('form', {onsubmit: async event => {
      event.preventDefault(); save.disabled = true; status.textContent = '';
      try {
        const result = await wrote('/api/ticket', {...scope, work_id: workId, revision,
          title: title.value, task: task.value, note: note.value, kind: kind.value});
        if (result) { revision = result.revision; status.textContent = 'Saved.'; }
      } finally { save.disabled = false; }
    }}, h('label', {}, 'Title', title), h('label', {}, 'Task', task), h('label', {}, 'Note', note),
    h('div', {class: 'row'}, h('label', {class: 'kind'}, 'Kind', kind), h('span', {class: 'grow'}), status, save));
    const memory = memoryMarkdown(data.memories);
    // the node the ticket is at and who works it, on one line; the diagrams below the form, each a pane opened on
    // purpose with room to read, never a strip a few lines tall (the person's report, 2026-10-20)
    const expertise = data.routing ? h('span', {class: 'pill expertise',
      title: data.routing.role ? 'The specialist expertise assigned to this ticket' : 'How a specialist is being chosen'},
    data.routing.role ? ['Expertise: ', h('code', {}, data.routing.role.replace('metaform://role/', ''))]
      : ['Specialist: ', data.routing.reason || data.routing.state]) : null;
    fill(DETAIL.body,
      h('div', {class: 'head'}, h('strong', {}, data.functionality.name),
        h('code', {class: 'address'}, data.functionality.address || ''), h('span', {class: 'grow'}), expertise),
      form,
      h('details', {class: 'pane'}, h('summary', {}, 'Functional context'),
        h('div', {class: 'ticket-graph'}, ...richText(data.functionality.markdown))),
      h('details', {class: 'pane'}, h('summary', {}, 'Memory graph'), memory
        ? h('div', {class: 'ticket-graph'}, ...richText(memory))
        : h('p', {class: 'hint'}, data.memories.unavailable || 'No memories are attached here.')));
  } catch (error) {
    if (serial === DETAIL.serial) fill(DETAIL.body, h('p', {role: 'alert'}, error.message));
  }
}
