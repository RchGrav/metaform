/* Authored responsibility and its recorded delivery relationships, shared by the chat and the Agents menu. */
import {h, fill} from '/page/app/core/dom.js';
import {roleCallForm} from '/page/app/agents/roles.js';

export const notificationState = state => state?.notification === true || state?.role === 'notification';
export const assignmentOf = state => state?.orchestration || state?.assignment || null;
export function authoredRole(state) {
  const role = String(assignmentOf(state)?.authored_role_uri || state?.authored_role_uri || '')
    .replace(/^metaform:\/\/role\//, '');
  return role === 'gc' ? 'GC' : role === 'functionality' ? 'Functional Quality Critic'
    : role.replace(/_/g, ' ');
}
export function assignmentSummary(state) {
  const assignment = assignmentOf(state), role = authoredRole(state);
  return [role, assignment?.state, assignment?.reviewed_assignment_id ? 'independent assessment' : '']
    .filter(Boolean).join(' · ');
}

/* Details stay closed or open as the person left them. Unchanged records leave the existing DOM in place. */
export function drawAssignment(box, state, openSession = null) {
  const assignment = assignmentOf(state), role = authoredRole(state);
  box.hidden = !role && !assignment;
  if (box.hidden) { box.dataset.drawn = ''; return; }
  const text = JSON.stringify([role, assignment, state?.parent_work_id, state?.parent_session_id,
    state?.reviewed_work_id, state?.reviewed_session_id]);
  if (box.dataset.drawn === text) return;
  const open = box.querySelector('details')?.open || false;
  box.dataset.drawn = text;
  const row = (label, value) => value ? [h('dt', {}, label), h('dd', {}, String(value))] : [];
  const reviewed = assignment?.reviewed_assignment_id;
  const directions = assignment?.pending_direction || [];
  const transitions = assignment?.continuations || [];
  const previousForm = box.querySelector('.rolecall');
  const form = assignment && !assignment.stop && !['returned', 'delivered', 'stopped'].includes(assignment.state)
    ? previousForm?.dataset.assignment === assignment.assignment_id ? previousForm
      : roleCallForm(assignment, openSession) : null;
  fill(box, h('details', {open}, h('summary', {}, assignmentSummary(state) || 'Assignment'),
    h('dl', {}, ...row('Responsibility', role),
      ...row('Requested outcome', assignment?.requested_result),
      ...row('Delivery', assignment?.state),
      ...row(reviewed ? 'Accountable GC' : 'GC owning this swarm', assignment?.gc_assignment_id),
      ...row('Swarm', assignment?.team_id),
      ...row('Owner session', assignment?.owner_session_id),
      ...row('Immediate caller', assignment?.parent_assignment_id),
      ...row('Handoff successor', assignment?.successor_assignment_id),
      ...row('Reviewed assignment', reviewed),
      ...row('Root ticket', assignment?.root_work_id),
      ...row('Specification mode', assignment?.mode)),
    reviewed ? h('p', {class: 'hint'}, 'This assessment has its own swarm identity. Its findings return to the '
      + 'accountable GC and remain visible to the PM.') : null,
    openSession && (state?.parent_work_id || state?.reviewed_work_id) ? h('section', {class: 'relations'},
      state.parent_work_id ? h('button', {class: 'btn sm', type: 'button',
        onclick: () => openSession(state.parent_work_id, state.parent_session_id)}, 'Open caller') : null,
      state.reviewed_work_id ? h('button', {class: 'btn sm', type: 'button',
        onclick: () => openSession(state.reviewed_work_id, state.reviewed_session_id)}, 'Open reviewed GC') : null) : null,
    directions.length ? h('section', {class: 'directions'}, h('b', {}, 'Recorded direction'),
      directions.map(one => h('p', {}, typeof one === 'string' ? one : one.body || one.direction || one.text
        || JSON.stringify(one)))) : null,
    transitions.length ? h('section', {class: 'continuations'}, h('b', {}, 'Delivery continuations'),
      h('ul', {}, transitions.map(one => h('li', {},
        `${one.kind}: ${one.delivery?.state || one.state || 'pending'}`)))) : null, form));
}
