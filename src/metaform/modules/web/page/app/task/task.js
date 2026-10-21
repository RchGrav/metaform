/* Giving work, VIEW-032: the task written as a person writes, its linked nodes, workflows, the editor's own chart
 * and the cursor kept. */
import '/page/app/agents/dispatch.js';  // the part before runs first, so the parts run in the page's order
import {$, SVG, h, fill} from '/page/app/core/dom.js';
import {overlay} from '/page/app/core/overlays.js';
import {toast, confirmAct} from '/page/app/core/controls.js';
import {S, read} from '/page/app/core/reads.js';
import {MAP2D, plain2d, mermaidReady} from '/page/app/map2d/build.js';
import {labelOf} from '/page/app/map2d/inside.js';
import {defaultAgent, eligibilityPicker, renderBoard} from '/page/app/board/board.js';
import {wrote} from '/page/app/board/history.js';
import {requestHoldReason} from '/page/app/board/holds.js';
import {startAgent} from '/page/app/agents/dispatch.js';
import {agentPicker, PICKERS} from '/page/app/agents/pickers.js';

/* Giving work, VIEW-032: the task is written as a person writes, the nodes it concerns are linked to it, and a node
 * inserted into the text reads there as its proper noun and carries its address. */
const K = {nodes: [], chosen: null, at: null, generation: 0, project: null, base: null, eligible: []};
const partOf = address => [...S.elements.values()].map(entry => entry.element)
  .find(element => element.address === address);
export const named = element => labelOf(element);
function chip(element, remove = null) {
  return h('span', {'data-address': element.address, title: element.address, contenteditable: 'false'},
    named(element), remove ? h('button', {title: 'Take it off this task', onclick: remove}, 'x') : null);
}
/* The nodes linked to the task; the first, the node it is given at, cannot be taken off. */
function linkedNodes() {
  fill($('#task .linked'), K.nodes.map((address, index) => chip(partOf(address),
    index ? () => unlink(address) : null)));
}
function unlink(address) {
  K.nodes = K.nodes.filter(one => one !== address);
  linkedNodes();
}
async function taskWorkflows() {
  const generation = ++K.generation, picker = $('#task .workflow'), project = S.project, metaform = S.base;
  const stale = () => generation !== K.generation || $('#task').hidden || project !== S.project || metaform !== S.base;
  picker.disabled = true;
  fill(picker, h('option', {value: ''}, 'Loading workflows…'));
  $('#task .workflow-entry').hidden = true;
  $('#task .workflow-call').value = '';
  if (!S.bases.some(map => map.active && map.id === metaform)) {
    fill(picker, h('option', {value: ''}, 'Choose the active map to run workflows'));
    return;
  }
  try {
    const found = await read('workflows');
    if (stale()) return;
    const calls = found.workflows.flatMap(workflowCalls);
    const none = found.enabled ? (calls.length ? 'No workflow' : 'No stored workflows') : 'Workflows unavailable';
    fill(picker, h('option', {value: ''}, none), ...calls);
    picker.disabled = !calls.length;
  } catch (error) {
    if (stale()) return;
    fill(picker, h('option', {value: ''}, 'Workflows could not load'));
    toast(error.message);
  }
}
/* Each entry of a stored workflow, offered as a call to start it with. */
const workflowCalls = workflow => workflow.prompt.map(name =>
  h('option', {value: `${workflow.address}.${name}`}, `${workflow.name || workflow.address} · ${name}`));
function chooseWorkflow() {
  const chosen = $('#task .workflow').value;
  $('#task .workflow-entry').hidden = !chosen;
  $('#task .workflow-call').value = chosen ? `${chosen}()` : '';
}
$('#task .workflow').onchange = chooseWorkflow;
export function giveWork(id, text = '') {
  const element = S.elements.get(id)?.element;
  if (!element) { toast('Work is given at an element.'); return; }
  Object.assign(K, {nodes: [element.address], chosen: null, at: null, project: S.project, base: S.base, eligible: []});
  $('#task .condition').value = '';
  $('#task .ticket-kind').value = '';
  $('#task .backlog').checked = false;
  $('#task .start-agent').checked = false;
  // the agent the ticket prefers, Claude for front-end and GUI work and Codex for the rest as dispatch chooses it,
  // in the picker every start shares; the one it shows is what the ticket keeps and what Start an agent now starts
  if (!$('#task .pickhost').firstChild) {
    $('#task .pickhost').append(PICKERS.task ||= agentPicker({label: 'Preferred agent', kept: true}));
  }
  PICKERS.task.set(defaultAgent());
  fill($('#task .eligibility'), eligibilityPicker([], agents => { K.eligible = agents; }));
  $('#task .title').textContent = `Add Task · ${named(element)}`;
  $('#task .text').replaceChildren(...(text ? [text] : []));
  $('#task .browser input').value = '';
  linkedNodes();
  const parts = [...S.elements.values()].map(entry => entry.element)
    .sort((one, two) => one.address < two.address ? -1 : 1);
  fill($('#task .rows'), parts.map(partRow));
  $('#task .insert').disabled = $('#task .link').disabled = true;
  $('#task').hidden = false;
  taskWorkflows();
  $('#task .text').focus();
  chart(parts);
}
/* A part in the browser of the namespace, by its name and its address. */
const partRow = part => h('button', {'data-address': part.address, onclick: () => choose(part.address)},
  named(part), h('small', {}, part.address));
/* A part is chosen in the list or in the chart, and is then chosen in both. */
function choose(address) {
  K.chosen = address;
  for (const one of $('#task').querySelectorAll('.rows [data-address], .chart g[data-address]')) {
    one.classList.toggle('chosen', one.dataset.address === address);
    if (one.dataset.address === address && one.closest('.rows')) one.scrollIntoView({block: 'nearest'});
  }
  $('#task .insert').disabled = $('#task .link').disabled = false;
}
/* The editor's own chart of the project, VIEW-032: the parts and their joins, looked around by dragging and by the
 * wheel, apart from the two maps of the page, which it does not move and which do not move it. */
const C = {generation: 0, cam: null, whole: null};
function camera(cam) {
  C.cam = cam;
  $('#task .chart svg')?.setAttribute('viewBox', `${cam.x} ${cam.y} ${cam.w} ${cam.h}`);
}
async function chart(parts) {
  const host = $('#task .chart'), generation = ++C.generation;
  const unable = text => fill(host, h('p', {class: 'empty', style: {padding: '12px'}}, text));
  if (!window.mermaid || !mermaidReady) return unable('The chart could not load.');
  if (parts.length > MAP2D) return unable(`The chart lays out at most ${MAP2D} parts.`);
  const keys = new Map(parts.map((part, index) => [part.id, `c${index}`]));
  let result;
  try { result = await window.mermaid.render(`pick${generation}`, chartLines(parts, keys).join('\n'), $('#draw')); }
  catch (error) { return unable('The chart could not be drawn.'); }
  if (generation !== C.generation) return;
  const svg = document.importNode(new DOMParser().parseFromString(result.svg, 'image/svg+xml').documentElement, true);
  svg.removeAttribute('style'); svg.removeAttribute('width'); svg.removeAttribute('height');
  host.replaceChildren(svg);
  for (const part of parts) markPart(svg, part, keys.get(part.id));
  const whole = svg.viewBox.baseVal;
  C.whole = {x: whole.x, y: whole.y, w: whole.width, h: whole.height};
  openChart(svg, host);
  if (K.chosen) choose(K.chosen);
}
/* The chart as mermaid writes it: each part by its name, and each join from its receiver to its providers. */
function chartLines(parts, keys) {
  const joined = join => join.providers.filter(id => keys.has(id))
    .map(provider => `${keys.get(join.receiver)} --> ${keys.get(provider)}`);
  return ['flowchart TB', ...parts.map(part => `${keys.get(part.id)}["${plain2d(named(part))}"]`),
    ...S.joins.filter(join => keys.has(join.receiver)).flatMap(joined)];
}
/* A part drawn in the chart carries its address, shows it on hover, and is chosen by a click. */
function markPart(svg, part, key) {
  const group = svg.querySelector(`[id*="-flowchart-${key}-"]`);
  if (!group) return;
  group.dataset.address = part.address;
  group.append(Object.assign(document.createElementNS(SVG, 'title'), {textContent: part.address}));
  group.addEventListener('click', event => { event.stopPropagation(); choose(part.address); });
}
/* It opens on the part the task is added at, at the size its names are written in, so they are read at once; the
 * whole of a project's chart in so small an area is boxes too small to read. */
function openChart(svg, host) {
  const first = svg.querySelector(`g[data-address="${CSS.escape(K.nodes[0])}"]`), area = host.getBoundingClientRect();
  if (first && area.width) {
    const box = first.getBBox(), matrix = first.transform.baseVal.consolidate()?.matrix || new DOMMatrix();
    const middle = new DOMPoint(box.x + box.width / 2, box.y + box.height / 2).matrixTransform(matrix);
    camera({x: middle.x - area.width / 2, y: middle.y - area.height / 2, w: area.width, h: area.height});
  } else camera(C.whole);
}
$('#task .whole').onclick = () => { if (C.whole) camera(C.whole); };
/* The chart is looked around by dragging it and zoomed by the wheel about the pointer. */
function wireChart() {
  const host = $('#task .chart');
  let drag = null;
  function startDrag(event) {
    if (C.cam) drag = {x: event.clientX, y: event.clientY, cam: {...C.cam}, moving: false};
  }
  function dragChart(event) {
    if (!drag) return;
    if (!drag.moving) {  // captured only once it is a drag, so a click still reaches the part under it
      if (Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 4) return;
      drag.moving = true; host.setPointerCapture(event.pointerId);
    }
    const scale = C.cam.w / host.getBoundingClientRect().width;
    camera({...drag.cam, x: drag.cam.x - (event.clientX - drag.x) * scale,
      y: drag.cam.y - (event.clientY - drag.y) * scale});
  }
  function zoomChart(event) {
    if (!C.cam) return;
    event.preventDefault();
    const by = event.deltaY > 0 ? 1.15 : 0.87, box = host.getBoundingClientRect(), cam = C.cam;
    const px = (event.clientX - box.left) / box.width, py = (event.clientY - box.top) / box.height;
    camera({x: cam.x + (cam.w - cam.w * by) * px, y: cam.y + (cam.h - cam.h * by) * py,
      w: cam.w * by, h: cam.h * by});
  }
  host.addEventListener('pointerdown', startDrag);
  host.addEventListener('pointermove', dragChart);
  host.addEventListener('pointerup', () => { drag = null; });
  host.addEventListener('wheel', zoomChart, {passive: false});
}
wireChart();
function toggleFull() {
  const full = $('#task').classList.toggle('full');
  $('#task .full').textContent = full ? 'Window' : 'Full screen';
}
$('#task .full').onclick = toggleFull;
/* Where the cursor was in the text, kept as the text loses it to the browser's buttons. It is kept as a node and a
 * count into it and not as a range, since a range is moved to the start of a text the browser writes again, which
 * it does to a space typed at the end of a line. */
function keepCursor() {
  const chosen = getSelection();
  if (chosen.rangeCount && $('#task .text').contains(chosen.anchorNode)) {
    const range = chosen.getRangeAt(0);
    K.at = {node: range.endContainer, count: range.endOffset};
  }
}
// It is read at each change of the text and as the text is left: the browser tells of a moved cursor a moment after
// it moved, which can be after the person has gone on to the browser of the namespace.
document.addEventListener('selectionchange', keepCursor);
for (const kind of ['input', 'keyup', 'mouseup', 'blur']) $('#task .text').addEventListener(kind, keepCursor);
function filterParts(event) {
  const wanted = event.target.value.trim().toLowerCase();
  for (const row of $('#task .rows').children) {
    row.hidden = Boolean(wanted) && !row.textContent.toLowerCase().includes(wanted);
  }
}
$('#task .browser input').oninput = filterParts;
/* The part chosen is written into the task where the cursor was, as its name carrying its address, and the cursor
 * is put after it. */
function insertPart() {
  const text = $('#task .text'), made = chip(partOf(K.chosen));
  if (K.at && text.contains(K.at.node)) {
    const node = K.at.node, at = document.createRange();
    const most = node.nodeType === Node.TEXT_NODE ? node.length : node.childNodes.length;
    at.setStart(node, Math.min(K.at.count, most));
    at.collapse(true);
    at.insertNode(made);
  } else text.append(made);
  // A text of no width after the name, for the cursor to stand in: the browser cannot put a cursor after a part
  // of the text that is not typed into when nothing follows it, and what is typed there is lost.
  const hold = document.createTextNode('\u200b');
  made.after(hold);
  const after = document.createRange();
  after.setStart(hold, 1);
  after.collapse(true);
  getSelection().removeAllRanges();
  getSelection().addRange(after);
  text.focus();
}
$('#task .insert').onclick = insertPart;
$('#task .link').onclick = () => { if (!K.nodes.includes(K.chosen)) { K.nodes.push(K.chosen); linkedNodes(); } };
/* The task as text: an inline node is written `[[name|address]]`, so an agent has the name and the address. */
const taskText = () => [...$('#task .text').childNodes].map(function told(node) {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent;
  if (node.dataset?.address) return `[[${node.textContent}|${node.dataset.address}]]`;
  return (node.tagName === 'DIV' || node.tagName === 'BR' ? '\n' : '') + [...node.childNodes].map(told).join('');
}).join('').replace(/\u200b/g, '').replace(/\u00a0/g, ' ').trim();
/* The task with the stored workflow it runs: the agent is told to run it with the workflow module and to complete the
 * ticket with what the entry call returns. */
const withWorkflow = (task, input) => (task ? task + '\n\n' : '')
  + 'Run this stored workflow using the workflow module\'s run command with the following input. '
  + 'Follow the returned instructions and use the workflow commands for calls, handoffs and returns. '
  + 'Complete this ticket with the result when the entry call returns. Report any workflow failure on this ticket.\n'
  + `Workflow input: ${JSON.stringify(input)}`;
/* Put: one ticket saved for the task, and its agent started at once when that is asked. */
async function putTask() {
  if (K.project !== S.project || K.base !== S.base) {
    toast('This task belongs to the map you left. Reopen Add Task at its target.');
    return;
  }
  let task = taskText();
  if (!task.trim() && !$('#task .workflow').value) { toast('Say what is to be done.'); return; }
  if ($('#task .workflow').value) {
    const call = $('#task .workflow-call').value.trim();
    if (!call) { toast('Give the workflow an entry call.'); return; }
    task = withWorkflow(task, {call, element: K.nodes[0]});
  }
  if (!task) { toast('A task says what is to be done.'); return; }
  // One ticket on the node it is assigned to, the first listed; every other node of the task, linked or named
  // inline, is linked for reference, VIEW-035.
  const inline = [...$('#task .text').querySelectorAll('[data-address]')].map(node => node.dataset.address);
  const all = [...new Set([...K.nodes, ...inline])].filter(address => partOf(address));
  const nodes = all.map(address => `element:${partOf(address).id}`);
  const project = S.project, metaform = S.base, generation = K.generation;
  const agent = PICKERS.task?.value(), startNow = $('#task .start-agent').checked;
  const eligible = [...K.eligible];
  const held = $('#task .backlog').checked, hold_reason = held ? requestHoldReason() : null;
  if (held && hold_reason === null) return;
  const written = await wrote('/api/task', {task, nodes, condition: $('#task .condition').value || null,
    kind: $('#task .ticket-kind').value || null, held, hold_reason, agent, eligible});
  if (project !== S.project || metaform !== S.base || generation !== K.generation) {
    if (written) toast(`Task saved in ${project}. Open that map to start its agent.`);
    return;
  }
  if (written) {
    $('#task').hidden = true;
    if (startNow) await startAgent(written.results[0].id,
      !eligible.length || eligible.includes(agent) ? agent : eligible[0]);
    renderBoard();
  }
}
$('#task .put').onclick = putTask;
$('#task .close').onclick = () => { $('#task').hidden = true; K.generation++; };
/* Escape or a click beside it does not throw away a task being written without asking. */
export const discard = (what, kept) => confirmAct({title: `Discard ${what}?`, text: 'What you wrote here is not kept.',
  verb: 'Discard', cancel: kept, danger: true});
overlay($('#task'), {kind: 'dialog', close: () => $('#task .close').click(), focus: '.text',
  guard: () => !taskText() || discard('this task', 'Keep writing')});
