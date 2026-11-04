/* Assigned task details and explicit task dispatch, independent of roles or ticket ownership. */
import {h, fill} from '/page/app/core/dom.js';
import {taskAssignForm} from '/page/app/agents/tasks.js';

export const notificationState = state => state?.notification === true || state?.role === 'notification';
export const taskSummary = state => state?.task?.name?.replace(/_/g, ' ') || '';

export function drawTask(box, state, openSession = null) {
  const task = state?.task;
  box.hidden = !task?.task_id;
  if (box.hidden) { box.dataset.drawn = ''; return; }
  const text = JSON.stringify([task.task_id, task.name, task.cwd]);
  if (box.dataset.drawn === text) return;
  const open = box.querySelector('details')?.open || false;
  box.dataset.drawn = text;
  fill(box, h('details', {open}, h('summary', {}, taskSummary(state) || 'Assigned task'),
    h('dl', {}, h('dt', {}, 'Task'), h('dd', {}, task.task_id),
      h('dt', {}, 'Folder'), h('dd', {}, task.cwd || state.cwd || '')),
    taskAssignForm(openSession)));
}
