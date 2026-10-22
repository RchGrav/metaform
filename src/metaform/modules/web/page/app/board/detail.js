/* Ticket inspection is pinned to its project/base, including every save after another tab or project opens. The
 * ticket's words are written on the left; beside them the node it is at, the specialist working it, whose prompt opens
 * on a click, and the node's joins, drawn as a small graph that opens whole on a click. */
import {h, fill} from '/page/app/core/dom.js';
import {overlay} from '/page/app/core/overlays.js';
import {S, read} from '/page/app/core/reads.js';
import {wrote, movable, COLUMN_NAMES} from '/page/app/board/history.js';
import {holdReason} from '/page/app/board/holds.js';
import {ticketIntegration} from '/page/app/board/integration.js';
import {diagramOf, svgOf, enlargeDiagram} from '/page/app/session/text.js';
import {authoredRole} from '/page/app/session/orchestration.js';

const DETAIL = {box: null, body: null, ref: null, reload: null, serial: 0};
const ROLE = {box: null, title: null, body: null, serial: 0};

const roleName = uri => authoredRole({authored_role_uri: uri});
const closeButton = close => h('button', {class: 'close btn icon sm quiet', type: 'button', 'aria-label': 'Close',
  title: 'Close (Escape)', onclick: close}, h('i', {class: 'i i-close', 'aria-hidden': 'true'}));

/* The prompt the specialist role is sent, read when the person asks for it, in the ticket's own project. */
async function specialistPrompt(role, scope) {
  const serial = ++ROLE.serial;
  if (!ROLE.box) {
    const close = () => { ROLE.box.hidden = true; };
    ROLE.title = h('span', {class: 'title'});
    ROLE.body = h('div', {class: 'body'});
    ROLE.box = h('section', {id: 'specialistPrompt', class: 'window', role: 'dialog', 'aria-label': 'Specialist prompt',
      hidden: true}, h('div', {class: 'bar'}, ROLE.title, closeButton(close)), ROLE.body);
    document.body.append(ROLE.box);
    movable(ROLE.box);
    overlay(ROLE.box, {kind: 'window', close});
  }
  ROLE.title.textContent = `Specialist · ${roleName(role)}`;
  fill(ROLE.body, h('p', {}, 'Loading the prompt…'));
  ROLE.box.hidden = false;
  try {
    const found = await read('agent-role', {...scope, name: role});
    if (serial !== ROLE.serial) return;
    const problems = found.problems || [];
    fill(ROLE.body, found.purpose ? h('p', {class: 'purpose'}, found.purpose) : null,
      problems.length ? h('p', {role: 'alert'}, problems.join(' ')) : null,
      found.text ? h('pre', {class: 'prompt', tabindex: '0'}, found.text) : null);
  } catch (error) {
    if (serial === ROLE.serial) fill(ROLE.body, h('p', {role: 'alert'}, error.message));
  }
}

/* Who works the ticket: the specialist's name, a button to its prompt, or how one is being chosen. */
function specialist(routing, scope) {
  if (!routing) return h('p', {class: 'quiet'}, 'No specialist assigned.');
  if (!routing.role) return h('p', {class: 'quiet'}, routing.reason || routing.state || 'Choosing a specialist.');
  return h('button', {class: 'specialist', type: 'button', title: 'Read the prompt this specialist is sent',
    onclick: () => specialistPrompt(routing.role, scope)}, roleName(routing.role));
}

/* The node's joins as a small graph; a click opens it whole in a window of its own. */
function graphThumb(functionality, serial) {
  const code = /```mermaid\n([\s\S]*?)\n```/.exec(functionality.markdown || '')?.[1];
  if (!code) return h('p', {class: 'quiet'}, functionality.markdown || 'No graph for this node.');
  const figure = h('span', {class: 'figure', 'aria-hidden': 'true'}, h('span', {class: 'quiet'}, 'Drawing…'));
  const thumb = h('button', {class: 'graph-thumb', type: 'button', disabled: true,
    title: 'Open the graph', 'aria-label': `Open the graph of ${functionality.name}`,
    onclick: () => enlargeDiagram(figure, `Graph · ${functionality.name}`)}, figure);
  diagramOf(code).then(drawn => {
    if (serial !== DETAIL.serial) return;
    if (!drawn.svg) { fill(figure, h('span', {class: 'quiet'}, `The graph could not be drawn: ${drawn.error}`)); return; }
    fill(figure, svgOf(drawn.svg));
    thumb.disabled = false;
  });
  return thumb;
}

/* The joins in words: what the node requires and from whom, and what relies on it. */
function joinList(functionality) {
  const names = new Map((functionality.nodes || []).map(one => [one.address, one.name]));
  const named = address => names.get(address) || address;
  const list = (joins, line) => joins.length ? h('ul', {class: 'joins'}, joins.map(line))
    : h('p', {class: 'quiet'}, 'None recorded.');
  return [
    h('h4', {}, 'Requires'),
    list(functionality.requirements || [], join => h('li', {}, join.purpose || 'No purpose recorded',
      h('small', {}, join.providers.map(named).join(', ') || 'No provider recorded'))),
    h('h4', {}, 'Relied on by'),
    list(functionality.dependents || [], join => h('li', {}, named(join.receiver),
      h('small', {}, join.purpose || 'No purpose recorded')))];
}

export async function ticketDetail(workId, project = S.project, base = S.base || '') {
  const serial = ++DETAIL.serial, scope = {project, base};
  if (!DETAIL.box) {
    const close = () => { DETAIL.box.hidden = true; };
    DETAIL.body = h('div', {class: 'body'});
    DETAIL.ref = h('span', {class: 'ref'});
    DETAIL.reload = h('button', {class: 'btn sm quiet reload', type: 'button', title: 'Read the ticket again'}, 'Reload');
    DETAIL.box = h('section', {id: 'ticketDetail', class: 'window dialog wide', role: 'dialog',
      'aria-label': 'Ticket details', hidden: true},
    h('div', {class: 'bar'}, h('span', {class: 'title'}, 'Ticket ', DETAIL.ref), DETAIL.reload, closeButton(close)),
    DETAIL.body);
    document.body.append(DETAIL.box);
    overlay(DETAIL.box, {kind: 'window', close});
  }
  fill(DETAIL.body, h('p', {}, 'Loading ticket…'));
  DETAIL.box.hidden = false;
  try {
    const data = await read('ticket-detail', {...scope, work_id: workId});
    if (serial !== DETAIL.serial) return;
    let revision = data.revision;
    const ticket = data.ticket, functionality = data.functionality;
    DETAIL.ref.textContent = `${data.item || workId} · ${scope.project}`;
    DETAIL.reload.onclick = () => ticketDetail(workId, scope.project, scope.base);
    const title = h('input', {name: 'title', class: 'ticket-title', value: ticket.title || '', placeholder: 'Title'});
    // the task and the note take the room their words need, within the window, instead of a strip that scrolls
    const rowsFor = (text, least, most) => String(Math.max(least, Math.min(most, (text || '').split('\n').length + 1)));
    const task = h('textarea', {name: 'task', rows: rowsFor(ticket.task, 8, 24)}, ticket.task || '');
    const note = h('textarea', {name: 'note', rows: rowsFor(ticket.note, 3, 12)}, ticket.note || '');
    const kind = h('select', {name: 'kind'}, ['', 'broken', 'flawed', 'enhancement'].map(value =>
      h('option', {value, selected: value === (ticket.kind || '')}, value || 'Task')));
    const status = h('p', {role: 'status'});
    const boardColumn = h('span', {class: 'board-column'}, ` · ${COLUMN_NAMES[ticket.column] || ''}`);
    const save = h('button', {class: 'btn primary', type: 'submit'}, 'Save changes');
    const form = h('form', {class: 'ticket-main', onsubmit: async event => {
      event.preventDefault(); save.disabled = true; status.textContent = '';
      try {
        const result = await wrote('/api/ticket', {...scope, work_id: workId, revision,
          title: title.value, task: task.value, note: note.value, kind: kind.value});
        if (result) { revision = result.revision; status.textContent = 'Saved.'; }
      } finally { save.disabled = false; }
    }}, h('label', {}, 'Title', title), h('label', {}, 'Task', task), h('label', {}, 'Note', note),
    h('div', {class: 'row'}, h('label', {class: 'kind'}, 'Kind', kind), h('span', {class: 'grow'}), status, save));
    fill(DETAIL.body, form, h('div', {class: 'ticket-side'},
      h('section', {}, h('h4', {}, 'Node'), h('strong', {}, functionality.name),
        h('code', {class: 'address'}, functionality.address || '')),
      h('section', {}, h('h4', {}, 'Board'), h('strong', {class: 'board-name'}, data.board || 'First board'),
        boardColumn),
      ticketIntegration(ticket, scope, found => {
        revision = found.revision;
        boardColumn.textContent = ` · ${COLUMN_NAMES[found.ticket.column] || ''}`;
      }),
      holdReason(ticket),
      h('section', {}, h('h4', {}, 'Specialist'), specialist(data.routing, scope)),
      h('section', {}, h('h4', {}, 'Graph'), graphThumb(functionality, serial), ...joinList(functionality))));
  } catch (error) {
    if (serial === DETAIL.serial) fill(DETAIL.body, h('p', {role: 'alert'}, error.message));
  }
}
