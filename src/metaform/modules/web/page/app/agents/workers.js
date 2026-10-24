/* Worker panels read the task board when the existing page event path asks for a redraw. */
import {h, fill} from '/page/app/core/dom.js';
import {S, read} from '/page/app/core/reads.js';

const percent = value => typeof value === 'number' && Number.isFinite(value) ? `${value}%` : '—';
const phrase = task => {
  if (!task) return '—';
  const nodes = Array.isArray(task.nodes) ? task.nodes.join(', ') : '';
  return `${task.phrase || '—'}${nodes ? ` (${nodes})` : ''}`;
};

export async function renderWorkerBoard(container) {
  const project = S.project;
  if (!project) { fill(container); return container; }
  const board = await read('worker-board');
  if (S.project !== project) return container;
  const entries = (board.agents || []).map(agent => h('section', {class: 'worker-entry'},
    h('div', {class: 'worker-heading'},
      h('span', {}, agent.name || '—'), ' ',
      h('span', {}, percent(agent.rating)), ' ',
      h('span', {}, percent(agent.context)), ' ',
      h('span', {}, percent(agent.complete))),
    h('div', {}, 'Next'),
    h('div', {}, phrase(agent.next)),
    h('div', {}, 'Current'),
    h('div', {}, phrase(agent.current)),
    h('div', {}, 'Past'),
    h('div', {class: 'worker-history'},
      agent.past?.length ? agent.past.map(task => h('div', {}, `${phrase(task)} ${percent(task.rating)}`))
        : h('div', {}, '—'))));
  fill(container, h('div', {class: 'worker-board'}, entries));
  return container;
}
