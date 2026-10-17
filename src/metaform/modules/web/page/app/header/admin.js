/* Administration: clearing or removing a project, asked on the page, backups restored, the map exported as Markdown,
 * Mermaid or XML, the empty panel's acts, and a tester's problem report. */
import '/page/app/header/menus.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {overlay} from '/page/app/core/overlays.js';
import {toast, undoable, confirmAct} from '/page/app/core/controls.js';
import {S, reach, read, viewLayers} from '/page/app/core/reads.js';
import {reportWith} from '/page/app/core/errors.js';
import {rootsOff, renderChips} from '/page/app/header/layers.js';
import {toggler} from '/page/app/header/menus.js';
import {M} from '/page/app/map2d/build.js';
import {wrote} from '/page/app/board/history.js';
import {getJson} from '/page/app/panel/prompts.js';
import {intakeRunning, openIntake} from '/page/app/intake/intake.js';
import {loadProject, toProject, fillProjects, goToProject} from '/page/app/loading/load.js';

/* ---------- clearing the project: what goes and what stays, asked on the page, VIEW-019 ----------
 * The warning is the command's own caution and the clear is the command's own operation, PROJ-025; every open page,
 * this one among them, follows it by the push, VIEW-018. */
/* The Administration menu, VIEW-019: acts on the project as a whole, reached on purpose; what reads first, then what
 * changes something, and what removes something last and in the danger color. */
// The Window menu and its Workspaces submenu, drawn by the workspace, workspace.js; Left closes the submenu.
overlay($('#windowbox'), {kind: 'menu'});
toggler($('#windowBtn'), $('#windowbox'));
overlay($('#wsworkspaces'), {kind: 'menu'});
function leaveWorkspaces(event) {
  if (event.key !== 'ArrowLeft') return;
  event.preventDefault();
  $('#wsworkspaces').hidden = true;
  $('#workspacesBtn')?.focus();
}
$('#wsworkspaces').addEventListener('keydown', leaveWorkspaces);
export function showAdmin(open) { $('#adminbox').hidden = !open; }
overlay($('#adminbox'), {kind: 'menu'});
const backupsOf = async project => (await getJson(`/api/backups?project=${encodeURIComponent(project)}`)).results;
/* Restore is offered only while the project has a backup to restore from. */
async function offerRestore() {
  try { $('#restoreBtn').disabled = !(await backupsOf(S.project)).length; }
  catch (error) { $('#restoreBtn').disabled = true; }
}
toggler($('#adminBtn'), $('#adminbox'), offerRestore);
/* The panel under Administration that its acts open in: a clear's warning, the backups, the ignore list. */
function showClear(open) { $('#clearbox').hidden = !open; }
overlay($('#clearbox'), {kind: 'popover'});
const closeButton = (label = 'Close') =>
  h('button', {class: 'btn keep', type: 'button', onclick: () => showClear(false)}, label);
/* One of the page's writes: a POST of JSON, answered with the response and its body, empty when it is not JSON. */
async function postJson(url, data) {
  const response = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data)});
  return {response, body: await response.json().catch(() => ({}))};
}
/* A file the browser saves, made from a text or a blob, under `name`. */
function saveFile(contents, name, type) {
  const link = h('a', {href: URL.createObjectURL(new Blob([contents], {type})), download: name});
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}
/* A backup restored: the project's own backup of what it held is made first, so the restore is undone by restoring
 * that one. */
async function restoreFrom(project, backup, confirm = false) {
  const {response, body} = await postJson('/api/restore', {project, backup, ...(confirm ? {confirm: true} : {})});
  // a restore clears first, which stops the agents at work: the server names them and the person decides, PROJ-030
  if (response.status === 409 && body.caution) {
    if (!await confirmAct({title: `Restore ${project} from ${backup}?`, text: body.caution, verb: 'Restore',
      cancel: 'Keep it as it is'})) return false;
    return restoreFrom(project, backup, true);
  }
  if (!response.ok) { toast(body.error || 'The backup was not restored.'); return false; }
  fill($('#clearbox'), h('div', {class: 'sheet'}, h('p', {class: 'restored'}, body.said),
    body.held_before ? h('p', {class: 'next'}, `What the project held was backed up as ${body.held_before}.`) : null,
    h('div', {class: 'acts'}, closeButton())));
  if (body.held_before) undoable(`Restored ${project} from ${backup}.`, () => restoreFrom(project, body.held_before));
  return true;
}
/* A backup's name is the time it was made, 20261010T112014Z, said as a person reads a time: the day and the hour
 * here, and how long ago. */
function backupTime(name) {
  const found = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z/.exec(name || '');
  if (!found) return null;
  const [, year, month, day, hour, minute, second] = found.map(Number);
  const at = new Date(Date.UTC(year, month - 1, day, hour, minute, second));
  const days = Math.round((new Date().setHours(0, 0, 0, 0) - new Date(at).setHours(0, 0, 0, 0)) / 86400000);
  const date = days === 0 ? 'Today' : days === 1 ? 'Yesterday'
    : at.toLocaleDateString([], {day: 'numeric', month: 'short', year: 'numeric'});
  return `${date} ${at.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})} · ${timeAgo(at)}`;
}
function timeAgo(at) {
  const seconds = Math.max(0, (Date.now() - at) / 1000);
  return seconds < 60 ? 'just now' : seconds < 3600 ? `${Math.floor(seconds / 60)} min ago`
    : seconds < 86400 ? `${Math.floor(seconds / 3600)} h ago` : `${Math.floor(seconds / 86400)} days ago`;
}
/* One backup in the list: its name, when it was made, what it holds, and Restore. */
const backupRow = kept => h('li', {},
  h('span', {class: 'name', title: kept.name}, kept.name),
  h('span', {class: 'when'}, backupTime(kept.name) || kept.name), h('span', {class: 'held'}, kept.held),
  h('button', {class: 'btn sm', type: 'button', onclick: () => restoreFrom(S.project, kept.name)}, 'Restore'));
async function openRestore() {
  showAdmin(false);
  let found;
  try { found = await backupsOf(S.project); }
  catch (error) { return toast(error.message); }
  const newest = [...found].sort((one, two) => two.name.localeCompare(one.name));
  fill($('#clearbox'), h('div', {class: 'sheet'}, h('h3', {}, `Restore ${S.project} from a backup`),
    h('p', {}, 'What the project holds now is backed up first, so a restore can be undone.'),
    h('ul', {class: 'backups'}, newest.map(backupRow)),
    h('div', {class: 'acts'}, closeButton())));
  showClear(true);
}
$('#restoreBtn').onclick = openRestore;
/* The export menu saves the map as a document the command writes: Markdown, MAP-052, or XML, MAP-059; VIEW-024. */
function showExport(open) { $('#exportbox').hidden = !open; }
overlay($('#exportbox'), {kind: 'menu'});
toggler($('#exportBtn'), $('#exportbox'));
async function exportAs(format, extension, type) {
  showExport(false);
  const query = new URLSearchParams({project: S.project, ...(S.base ? {base: S.base} : {}), ...viewLayers()});
  const response = await fetch(`/api/${format}?${query}`);
  if (!response.ok) return toast((await response.json().catch(() => ({}))).error || 'The map could not be exported.');
  saveFile(await response.text(), `${S.project}-map.${extension}`, type);
}
$('#exportMarkdown').onclick = () => exportAs('markdown', 'md', 'text/markdown');
/* The error a JSON answer gives, or nothing for an answer that is not JSON. */
function errorIn(text) {
  try { return JSON.parse(text).error; } catch { return ''; }
}
/* The 2D map as a Mermaid flowchart, P063: the writer `metaform map mermaid` uses, given the layers and metaform the
 * page shows, the way its 2D map runs and the roots it leaves out, so the diagram holds the elements and joins drawn
 * here, each join pointing the way its information goes as the 2D map's arrowheads do, and asks for the 2D map's
 * layout, ELK by network simplex, ELK2D, in its frontmatter. With an address, that node and those one join away. A
 * diagram too long for Mermaid's default limits is said, since GitHub or mermaid.live would draw nothing of it. */
export async function mermaidText(given = {}) {
  const query = new URLSearchParams({project: S.project, ...(S.base ? {base: S.base} : {}), ...viewLayers(),
    direction: M.base && !M.base.vertical ? 'LR' : 'TB', leave_out: [...rootsOff()].join(','), ...given});
  const response = await reach(`/api/mermaid?${query}`, {});
  const text = await response.text();
  if (!response.ok) throw new Error(errorIn(text) || 'The map could not be written as Mermaid.');
  const notice = response.headers.get('X-Metaform-Notice');
  if (notice) setTimeout(() => toast(notice), 1200);  // after the toast saying it was saved or copied
  return text;
}
async function exportMermaid() {
  showExport(false);
  let text;
  try { text = await mermaidText(); } catch (error) { return toast(error.message); }
  saveFile(text, `${S.project}-map.mmd`, 'text/plain');
}
async function copyMermaid() {
  showExport(false);
  try { await navigator.clipboard.writeText(await mermaidText()); toast('The map is copied as Mermaid.'); }
  catch (error) { toast(error.message || 'The browser did not let the page copy it.'); }
}
$('#exportMermaid').onclick = exportMermaid;
$('#copyMermaid').onclick = copyMermaid;
$('#exportXml').onclick = () => exportAs('xml', 'xml', 'application/xml');
/* The intake's ignore list, .metaform/ignore.txt: what is not the project, said by the person up front, so the
 * intake never reads it and never judges it. */
async function editIgnores() {
  showAdmin(false);
  let found;
  try { found = await read('ignore'); } catch (error) { return toast(error.message); }
  const text = h('textarea', {class: 'ignore', rows: 8, spellcheck: 'false', 'data-autofocus': '',
    'aria-label': 'Intake ignores (one pattern per line, like .gitignore)'});
  text.value = found.text || '';
  const save = async () => {
    if (await wrote('/api/ignore', {text: text.value})) { toast('Ignore list saved.'); showClear(false); }
  };
  fill($('#clearbox'), h('div', {class: 'sheet'}, h('h3', {}, 'Intake ignores'),
    h('p', {}, `One pattern per line, like .gitignore. Kept in ${found.file}; the intake never reads what these name.`),
    text, h('div', {class: 'acts'}, closeButton('Cancel'),
      h('button', {class: 'btn primary', type: 'button', onclick: save}, 'Save'))));
  showClear(true);
}
$('#ignoreBtn').onclick = editIgnores;
async function askClear() {
  showAdmin(false);
  let found;
  try { found = await getJson(`/api/clear-preview?project=${encodeURIComponent(S.project)}`); }
  catch (error) { return toast(error.message); }
  if (await confirmAct({title: 'Are you sure?', text: [found.caution, 'It is backed up first.'], verb: 'Clear it',
    cancel: 'Keep it', typed: true, host: $('#clearbox')})) clearProject(found.project);
}
$('#clearBtn').onclick = askClear;
async function clearProject(project) {
  const {response, body} = await postJson('/api/clear-project', {project, confirm: true});
  if (!response.ok) { showClear(false); return toast(body.error || 'The project was not cleared.'); }
  const left = body.not_removed || [];
  fill($('#clearbox'), h('div', {class: 'sheet'}, h('p', {class: 'said'}, body.said),
    body.backup ? h('p', {class: 'backed'}, `Backed up as ${body.backup}.`) : null,
    left.length ? [h('b', {}, 'Not removed, still on disk:'),
      h('ul', {class: 'left'}, left.map(item => h('li', {}, `${item.path}: ${item.reason}`)))] : null,
    (body.notices || []).map(notice => h('p', {class: 'next'}, notice.message)),
    h('div', {class: 'acts'}, closeButton())));
}
/* Remove project takes an empty project off the list, PROJ-031: one that still holds metaforms or reports is named
   with what it holds, since a clear backs it up first. */
async function askRemove() {
  showAdmin(false);
  let found;
  try { found = await getJson(`/api/remove-preview?project=${encodeURIComponent(S.project)}`); }
  catch (error) { return toast(error.message); }
  if (found.held) {
    fill($('#clearbox'), h('div', {class: 'sheet'}, h('p', {class: 'held'}, found.held),
      h('p', {class: 'next'}, 'Use Clear project first.'), h('div', {class: 'acts'}, closeButton())));
    return showClear(true);
  }
  if (await confirmAct({title: 'Are you sure?', text: found.caution, verb: 'Remove it', cancel: 'Keep it', typed: true,
    host: $('#clearbox')})) removeProject(found.project);
}
$('#removeBtn').onclick = askRemove;
$('#mapFolderBtn').onclick = () => openMapFolder();
async function removeProject(project) {
  const {response, body} = await postJson('/api/remove-project', {project, confirm: true});
  showClear(false);
  if (!response.ok) return toast(body.error || 'The project was not removed.');
  toast(body.said);
  S.projects = ((await getJson('/api/projects')).projects || []);
  if (!S.projects.length) return location.reload();
  toProject(S.projects[0].id);
  fillProjects();
  await loadProject();
}
/* Map a folder…, from Administration or a page with no project: a folder of the person's registered as a project of its own, named by the
 * folder as metaform start names it, then shown, with the intake window open on it when it has no map yet (UX review
 * round 2, 2026-10-17, new-project-intake PROPOSED-VIEW-D). An act the person chooses, never a screen over the
 * workbench; nothing is written into the folder itself. */
export function openMapFolder() {
  showAdmin(false);
  const field = h('input', {type: 'text', class: 'folderpath', placeholder: '/path/to/your/project',
    'aria-label': 'Folder to map', autocomplete: 'off', spellcheck: 'false'});
  const failed = h('p', {class: 'next', role: 'alert', hidden: true});
  const go = h('button', {class: 'btn primary', type: 'button'}, 'Map it');
  async function send() {
    const path = field.value.trim();
    if (!path) return field.focus();
    go.disabled = true;
    const {response, body} = await postJson('/api/add-project', {path});
    go.disabled = false;
    if (!response.ok) {
      failed.textContent = (body.error || 'The folder was not registered.') + (body.next ? ` Next: ${body.next}.` : '');
      failed.hidden = false;
      return;
    }
    showClear(false);
    await goToProject(body.project, body.created ? `${body.project} is registered for ${body.path}.`
      : `${body.path} is ${body.project}, registered already.`);
    if (!S.elements.size && !intakeRunning()) openIntake();
  }
  go.onclick = send;
  field.onkeydown = event => { if (event.key === 'Enter') send(); };
  fill($('#clearbox'), h('div', {class: 'sheet'}, h('h3', {}, 'Map a folder'),
    h('p', {}, 'The folder becomes a project of its own, named after it, and the intake window opens on it. '
      + 'Nothing is written into the folder.'),
    h('label', {class: 'gate'}, 'Folder to map:', field), failed,
    h('div', {class: 'acts'}, closeButton('Cancel'), go)));
  showClear(true);
  setTimeout(() => field.focus(), 0);
}
/* After a clear the project has no metaform until the next intake, or anything else written to it, makes one. */
export const noMetaform = () => !S.bases.length;
export const noneYet = () => `${S.project} has no metaform yet. The next intake creates one.`;
/* The panel of a project with no map: what it is, and the intake, which makes one, as the thing to do. */
export function emptyPanel() {
  const said = noMetaform() ? noneYet() : 'Nothing to show in these layers yet.';
  const box = h('div', {class: 'emptypanel'}, h('p', {class: 'empty'}, said), h('div', {class: 'acts'}));
  emptyActs(box);
  return box;
}
/* Its act: Start the intake, or while one starts or runs, that one: its chat once its session is made. */
export function emptyActs(box) {
  const running = intakeRunning();
  fill(box.querySelector('.acts'), S.elements.size ? null : running
    ? h('button', {class: 'btn', type: 'button', onclick: () => openIntake()}, 'An intake is under way · show it')
    : h('button', {class: 'btn primary', type: 'button', onclick: () => openIntake()},
      h('i', {class: 'i i-spark', 'aria-hidden': 'true'}), 'Start the intake'));
}
/* Apply writes the layers this view shows into the folder's own setting. */
async function applyLayers() {
  if (S.view === null) return;
  const {response, body} = await postJson('/api/apply-layers', {project: S.project, layers: [...S.view]});
  if (!response.ok) return toast(body.error || 'The folder was not changed.');
  S.view = null;
  S.layers = (await read('layers', {limit: 0})).results;
  renderChips();
  toast(['Applied to the folder.', ...(body.notices || []).map(notice => notice.message)].join(' '));
}
$('#apply').onclick = applyLayers;
/* Report a problem, from the View menu: the report `metaform report` makes, BASE-045, with this browser and the page's
 * console errors besides. The server builds it and this page saves it as a download; nothing is sent anywhere. */
overlay($('#report'), {kind: 'dialog', close: () => { $('#report').hidden = true; }, focus: () => $('#reportWhat')});
$('#report .close').onclick = () => { $('#report').hidden = true; };
function openReport(description = '') {
  $('#settingsbox').hidden = true;
  if (typeof description === 'string' && description) $('#reportWhat').value = description.slice(0, 500);
  $('#reportSaid').textContent = '';
  $('#reportMake').disabled = false;
  $('#report').hidden = false;
}
$('#reportBtn').onclick = () => openReport();
reportWith(openReport);  // the error surface's banners open it with the problem's words
async function makeReport(event) {
  event.preventDefault();
  const description = $('#reportWhat').value.trim();
  if (!description) { $('#reportWhat').focus(); return; }
  $('#reportMake').disabled = true;
  $('#reportSaid').textContent = 'Making the report…';
  const {response, body} = await postJson('/api/report', {project: S.project, description,
    files: $('#reportFiles').checked, browser: navigator.userAgent, console: window.METAFORM_CONSOLE || []})
    .catch(error => ({response: {ok: false}, body: {error: error.message}}));
  $('#reportMake').disabled = false;
  if (!response.ok) { $('#reportSaid').textContent = body.error || 'The report was not made.'; return; }
  saveFile(Uint8Array.from(atob(body.data), letter => letter.charCodeAt(0)), body.name, 'application/zip');
  $('#reportSaid').textContent = [`Saved ${body.name} to your downloads. ${body.send_to}`, 'It holds:',
    ...body.held.map(line => `  ${line}`)].join('\n');
}
$('#reportForm').addEventListener('submit', makeReport);
