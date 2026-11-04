/* Explicit tasks and selected skills. Reading a definition starts no agent. */
import {h, fill} from '/page/app/core/dom.js';
import {S} from '/page/app/core/reads.js';
import {toast} from '/page/app/core/controls.js';
import {getJson} from '/page/app/panel/prompts.js';
import {wrote} from '/page/app/board/history.js';

export function taskAssignForm(openSession = null) {
  const project = S.project;
  const box = h('section', {class: 'taskassign'});
  const button = h('button', {class: 'btn sm', type: 'button'}, 'Assign task');
  button.onclick = async () => {
    button.disabled = true;
    try {
      const catalog = await getJson(`/api/tasks?project=${encodeURIComponent(project)}`);
      fill(box, assignmentForm(project, catalog, openSession));
    } catch (error) { toast(error.message); button.disabled = false; }
  };
  box.append(button);
  return box;
}

function assignmentForm(project, catalog, openSession) {
  const definition = h('select', {'aria-label': 'Task definition'},
    h('option', {value: ''}, 'Explicit assignment'),
    (catalog.tasks || []).map(task => h('option', {value: task.name}, task.name)));
  const purpose = h('p', {class: 'hint'});
  const instructions = h('details', {hidden: true}, h('summary', {}, 'Task instructions'), h('pre'));
  const text = h('textarea', {'aria-label': 'Task assignment', rows: 4,
    placeholder: 'Describe the objective, relevant context and expected result.'});
  const skillInputs = (catalog.skills || []).map(skill => {
    const input = h('input', {type: 'checkbox', value: skill.name});
    return {input, label: h('label', {title: skill.description || ''}, input, skill.name)};
  });
  const skills = h('fieldset', {}, h('legend', {}, 'Skills'),
    skillInputs.length ? skillInputs.map(skill => skill.label) : h('p', {class: 'hint'}, 'No skills available.'));
  const start = h('button', {class: 'btn sm', type: 'submit', disabled: true}, 'Start task');
  const note = h('p', {class: 'hint'});
  const form = h('form', {class: 'task-form'},
    h('label', {}, 'Task', definition), purpose, instructions,
    h('label', {}, 'Assignment and context', text), skills, start, note);
  let valid = true, busy = false;
  const ready = () => { start.disabled = busy || !valid || (!definition.value && !text.value.trim()); };
  text.oninput = ready;
  definition.onchange = async () => {
    const selected = definition.value;
    valid = !selected;
    instructions.hidden = true;
    fill(instructions.querySelector('pre'));
    fill(note);
    fill(purpose, (catalog.tasks || []).find(task => task.name === selected)?.description || '');
    ready();
    if (!selected) return;
    try {
      const read = await getJson(`/api/task-definition?project=${encodeURIComponent(project)}`
        + `&name=${encodeURIComponent(selected)}`);
      if (definition.value !== selected) return;
      fill(instructions.querySelector('pre'), read.instructions);
      instructions.hidden = false;
      valid = true;
      ready();
    } catch (error) { if (definition.value === selected) fill(note, error.message); }
  };
  form.onsubmit = async event => {
    event.preventDefault();
    if (!valid || busy || (!definition.value && !text.value.trim())) return;
    busy = true; ready();
    try {
      const made = await wrote('/api/task-assign', {project,
        ...(definition.value ? {name: definition.value} : {}),
        ...(text.value ? {text: text.value} : {}),
        skills: skillInputs.filter(skill => skill.input.checked).map(skill => skill.input.value)});
      if (!made) return;
      fill(note, `Task recorded (${made.state || 'starting'}).`,
        made.work_id && openSession ? h('button', {class: 'btn sm', type: 'button',
          onclick: () => openSession(made.work_id, made.session_id)}, 'Open task') : null);
      text.value = '';
    } finally { busy = false; ready(); }
  };
  return form;
}
