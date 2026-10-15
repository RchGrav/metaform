/* The first screen: with no project, or a project with no map yet, a welcome in place of the workbench, saying in one
 * sentence what Metaform is and offering two choices, the demo and mapping a project of one's own through a folder
 * picker and the intake; what goes wrong is said as what happened and the one thing to do. */
import '/page/app/loading/load.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {FRAMED, S, reach} from '/page/app/core/reads.js';
import {G, start3D} from '/page/app/map3d/graph3d.js';
import {FIRST, drawEmpty, openIntake, posted} from '/page/app/intake/intake.js';
import {listen} from '/page/app/live/ops.js';
import {loadProject, toProject} from '/page/app/loading/load.js';

/* shown: whether the welcome is up; path: the folder the picker is in; picked: the project that folder already is. */
export const WELCOME = {shown: false, path: null, parent: null, picked: null, workbench: false, asked: 0};
const WORKBENCH = 'metaform.workbench';  // this tab chose the workbench over the welcome; kept for the tab's session
function chosenWorkbench() {
  try { return WELCOME.workbench || sessionStorage.getItem(WORKBENCH) === '1'; } catch { return WELCOME.workbench; }
}

/* Whether the welcome shows: with no project at all, or once the page has read a project with no map, unless the
 * person chose the workbench in this tab. Never in an AI tool's frame, which shows the map alone. */
FIRST.drawn = (empty, settled) => {
  if (FRAMED) return false;
  if (!settled) return WELCOME.shown;  // left as it is while the page still reads
  const on = !S.projects.length || (!!S.project && empty && !chosenWorkbench());
  drawWelcome(on);
  return on;
};
export function drawWelcome(on) {
  const was = WELCOME.shown;
  WELCOME.shown = on;
  $('#welcome').hidden = !on;
  document.documentElement.classList.toggle('welcoming', on);
  $('.app').inert = on;
  if (!on) return;
  const folder = S.projects.find(item => item.id === S.project)?.path;
  // with a project and no map, Map my project maps that one; another folder is a quiet link away
  fill($('#welcome .map .sub'), folder
    ? `${S.project}, at ${folder}. An agent reads it and draws its map while you watch.`
    : "Choose your project's folder. An agent reads it and draws its map while you watch.");
  $('#welcome .other').hidden = !folder || !$('#welcome .picker').hidden;
  $('#welcome .workbench').hidden = !S.project;
  if (!was) {
    showChoices();
    requestAnimationFrame(() => $('#welcome .choice.demo').focus({preventScroll: true}));
  }
}

/* What went wrong, said plainly: what happened and the one thing to do, never a stack or a raw reply. */
export function sayFailed(body = {}, status = 0) {
  const box = $('#welcome .failed');
  const first = text => String(text || '').split('\n')[0].trim();
  const raw = first(body.error);
  const unreachable = status === 0 || /failed to fetch|networkerror|load failed/i.test(raw);
  const what = unreachable ? "Metaform's server did not answer."
    : raw && !/traceback|exception|^\w*error:/i.test(raw) ? raw : 'That did not work.';
  const next = unreachable ? 'Check that metaform web is still running in your terminal, then try again.'
    : first(body.next) || 'Try again.';
  fill(box, h('p', {}, h('b', {}, what)),
    h('p', {class: 'next'}, /^metaform /.test(next) ? ['Run ', h('code', {}, next), ' in a terminal.'] : next));
  box.hidden = false;
}
const clearFailed = () => { fill($('#welcome .failed')); $('#welcome .failed').hidden = true; };

/* ---------- Watch the demo: `metaform demo` started by the server, and the page goes to the address it gives ---- */
async function watchDemo() {
  const button = $('#welcome .choice.demo'), label = $('#welcome .choice.demo b');
  clearFailed();
  button.disabled = true;
  label.textContent = 'Starting the demo…';
  const sent = await posted('/api/first-run/demo', {});
  if (sent.ok && sent.body.address) return location.assign(sent.body.address);
  button.disabled = false;
  label.textContent = 'Watch the demo';
  sayFailed(sent.body, sent.status);
}

/* ---------- Map my project: the project with no map goes to its intake; else a folder is chosen first ---------- */
function mapMine() {
  clearFailed();
  if (S.project && S.projects.some(item => item.id === S.project)) return openIntake();
  return openPicker('');
}
function showChoices() {
  $('#welcome .choices').hidden = false;
  $('#welcome .picker').hidden = true;
  $('#welcome .other').hidden = !S.project;
}
async function openPicker(path) {
  $('#welcome .choices').hidden = true;
  $('#welcome .other').hidden = true;
  $('#welcome .picker').hidden = false;
  await listFolders(path);
}
/* The folders in one folder, drawn in the picker; only the last one asked for is drawn, so a slow listing that comes
 * back late never replaces the folder the person went to since. */
async function listFolders(path) {
  clearFailed();
  const asked = WELCOME.asked = (WELCOME.asked || 0) + 1;
  let response, body;
  try {
    response = await reach(`/api/first-run/folders?path=${encodeURIComponent(path)}`,
      {headers: {Accept: 'application/json'}}, 2);
    body = await response.json().catch(() => ({}));
  } catch (error) { return asked === WELCOME.asked && sayFailed({error: error.message}, 0); }
  if (asked !== WELCOME.asked) return;
  if (!response.ok) return sayFailed(body, response.status);
  Object.assign(WELCOME, {path: body.path, parent: body.parent, picked: body.project});
  $('#welcome .typed').value = '';
  fill($('#welcome .pickhead .at'), body.path);
  const rows = body.folders.map(folder => h('button', {type: 'button', role: 'option', 'data-path': folder.path,
    title: `Open ${folder.path}`, onclick: () => listFolders(folder.path)},
  h('span', {}, folder.name), folder.project ? h('small', {}, `mapped as ${folder.project}`) : null));
  fill($('#welcome .folders'), rows.length ? rows : h('p', {class: 'none'}, 'No folders inside this one.'),
    body.more ? h('p', {class: 'none'}, `And ${body.more} more not shown.`) : null);
  $('#welcome .up').disabled = !body.parent;
  const name = body.path.split(/[\\/]/).filter(Boolean).at(-1) || body.path;
  $('#welcome .pick').textContent = body.project ? `Open ${body.project}` : `Map ${name}`;
}
async function pickFolder() {
  const button = $('#welcome .pick');
  clearFailed();
  button.disabled = true;
  const sent = await posted('/api/first-run/map', {path: WELCOME.path});
  button.disabled = false;
  if (!sent.ok) return sayFailed(sent.body, sent.status);
  await goToProject(sent.body.project);
}
/* The project chosen opened as the page opens one: on the list, drawn, heard; with no map yet, its intake offered. */
async function goToProject(id) {
  try {
    const response = await reach('/api/projects', {headers: {Accept: 'application/json'}}, 2);
    S.projects = (await response.json()).projects || [];
  } catch (error) { return sayFailed({error: error.message}, 0); }
  fill($('#proj'), ...S.projects.map(item => h('option', {value: item.id, selected: item.id === id}, item.id)));
  if (!G) start3D();  // a page opened with no project has not drawn a 3D map yet
  toProject(id);
  await loadProject();
  listen();
  showChoices();
  if (!S.elements.size) openIntake();
}

$('#welcome .choice.demo').onclick = watchDemo;
$('#welcome .choice.map').onclick = mapMine;
$('#welcome .other').onclick = () => { clearFailed(); openPicker(''); };
$('#welcome .back').onclick = () => { clearFailed(); showChoices(); };
$('#welcome .up').onclick = () => { if (WELCOME.parent) listFolders(WELCOME.parent); };
$('#welcome .pick').onclick = pickFolder;
$('#welcome .typed').onkeydown = event => {
  if (event.key !== 'Enter' || !event.target.value.trim()) return;
  event.preventDefault();
  listFolders(event.target.value.trim());
};
$('#welcome .workbench').onclick = () => {
  WELCOME.workbench = true;
  try { sessionStorage.setItem(WORKBENCH, '1'); } catch { /* storage can be blocked; this load keeps it */ }
  drawEmpty();
};
