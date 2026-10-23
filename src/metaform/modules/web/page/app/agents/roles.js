/* Native, generated and installed BMAD responsibilities, selected from public providers and called by assignment. */
import {h, fill} from '/page/app/core/dom.js';
import {S} from '/page/app/core/reads.js';
import {toast} from '/page/app/core/controls.js';
import {getJson} from '/page/app/panel/prompts.js';
import {wrote} from '/page/app/board/history.js';

const titleOf = role => role === 'gc' ? 'GC' : role === 'functionality' ? 'Functional Quality Critic'
  : role.replace(/_/g, ' ');
const uses = role => role.launch === 'claim' ? 'starts with a ticket claim'
  : role.launch === 'commission' ? 'commissioned by the GC from a role request' : '';

/* Loading and inspecting this menu starts nothing. The person explicitly requests a contribution after seeing
 * its authored purpose and actual installed source; dispatch owns the launch and the recorded return. */
export function roleCallForm(assignment, openSession = null) {
  const box = h('section', {class: 'rolecall', 'data-assignment': assignment.assignment_id});
  const button = h('button', {class: 'btn sm', type: 'button'}, 'Choose specialist');
  button.onclick = async () => {
    button.disabled = true;
    try {
      const menu = await getJson(`/api/agent-roles?project=${encodeURIComponent(S.project)}`);
      fill(box, menu.launch_available ? contributionForm(assignment, menu, openSession)
        : h('p', {class: 'hint'}, 'Managed specialist calls are unavailable on this project.'));
    } catch (error) { toast(error.message); button.disabled = false; }
  };
  box.append(button);
  return box;
}

function contributionForm(assignment, menu, openSession) {
  const role = h('select', {'aria-label': 'Specialist responsibility'});
  const specialists = menu.specialists || [];
  const choices = [...specialists, ...menu.roles];
  const groups = [...new Set(menu.roles.map(one => one.source_kind))];
  fill(role, h('option', {value: ''}, 'Choose a responsibility'),
    specialists.length ? h('optgroup', {label: 'Specialists'}, specialists.map(one =>
      h('option', {value: one.uri}, titleOf(one.role)))) : null, groups.map(source =>
    h('optgroup', {label: source}, menu.roles.filter(one => one.source_kind === source).map(one =>
      h('option', {value: one.uri, disabled: Boolean(uses(one))},
        `${titleOf(one.role)}${uses(one) ? ` — ${uses(one)}` : ''}`)))));
  const purpose = h('p', {class: 'hint'}), source = h('small', {class: 'source'});
  const installedMenu = h('details', {hidden: true}, h('summary', {}, 'Installed BMAD menu'), h('pre'));
  const versions = h('details', {hidden: true}, h('summary', {}, 'Selected responsibility versions'), h('ul'));
  const task = h('textarea', {'aria-label': 'Requested specialist contribution', rows: 3,
    placeholder: 'Describe the requested contribution. For BMAD, include its menu command and input.'});
  const result = h('input', {'aria-label': 'Expected specialist result', placeholder: 'Expected result (optional)'});
  const start = h('button', {class: 'btn sm', type: 'submit', disabled: true}, 'Start contribution');
  const note = h('p', {class: 'hint'}, 'The result returns to this assignment. Its GC retains delivery ownership.');
  const form = h('form', {class: 'specialist-form'},
    h('label', {}, 'Responsibility', role), purpose, source, installedMenu, versions,
    h('label', {}, 'Requested contribution', task), result, start, note);
  let valid = false, busy = false;
  const ready = () => { start.disabled = busy || !valid || !task.value.trim(); };
  task.oninput = ready;
  role.onchange = async () => {
    const selected = choices.find(one => one.uri === role.value);
    valid = false; ready();
    fill(purpose, selected?.purpose || '');
    fill(source, selected ? [selected.source_kind, selected.installed?.source || selected.provider,
      selected.installed?.installed_version].filter(Boolean).join(' · ') : '');
    installedMenu.hidden = !selected?.installed?.menu;
    fill(installedMenu.querySelector('pre'), selected?.installed?.menu || '');
    versions.hidden = true;
    start.textContent = selected?.launch === 'assessment' ? 'Request independent assessment' : 'Start contribution';
    if (!selected) return;
    try {
      const resolved = await getJson(`/api/agent-role?project=${encodeURIComponent(S.project)}`
        + `&name=${encodeURIComponent(selected.uri)}`);
      if (role.value !== selected.uri) return;
      fill(versions.querySelector('ul'), (resolved.components || []).map(one => h('li', {},
        `${one.name}: ${one.number == null ? one.origin : `version ${one.number} · ${one.origin}`}`)));
      versions.hidden = false;
      valid = !(resolved.problems || []).length;
      fill(note, valid ? selected.launch === 'assessment'
        ? 'This assessment has an independent swarm and returns findings to the responsible GC and PM.'
        : 'The result returns to this assignment. Its GC retains delivery ownership.'
        : resolved.problems.join(' '));
      ready();
    } catch (error) { fill(note, error.message); }
  };
  form.onsubmit = async event => {
    event.preventDefault();
    if (!valid || busy || !task.value.trim()) return;
    busy = true; ready();
    try {
      const made = await wrote('/api/orchestration-call', {assignment: assignment.assignment_id,
        role: role.value, task: task.value.trim(), ...(result.value.trim() ? {result: result.value.trim()} : {})});
      if (!made) return;
      fill(note, `Contribution recorded (${made.state || 'queued'}). Its dispatch continuation observes the configured capacity.`,
        made.work_id && openSession ? h('button', {class: 'btn sm', type: 'button',
          onclick: () => openSession(made.work_id, made.owner_session_id)}, 'Open contribution') : null);
      task.value = ''; result.value = '';
    } finally { busy = false; ready(); }
  };
  return form;
}
