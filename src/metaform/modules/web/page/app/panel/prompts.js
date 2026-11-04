/* Prompts edited in a real editor and saved as a new version, VIEW-013, and the panel's and side column's tabs. */
import '/page/app/panel/agentview.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {OVERLAY, restack} from '/page/app/core/overlays.js';
import {toast} from '/page/app/core/controls.js';
import {S, reach} from '/page/app/core/reads.js';
import {renderBrief} from '/page/app/panel/brief.js';
import {renderProv} from '/page/app/panel/agentview.js';
import {TAB_VIEWS, WS} from '/page/app/workspace/workspace.js';

/* ---------- prompts: edited in a real editor, saved as a new version, VIEW-013 ---------- */
export const P = {editor: null, name: null, number: null, versions: [], asked: 0};
export async function getJson(path) {
  const response = await reach(path, {headers: {Accept: 'application/json'}});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `${path} failed`);
  return body;
}
export async function renderPrompt(name = P.name, number = P.number) {
  // only the last one asked for is shown: opening a layer's prompt asks twice, and an earlier read coming back after
  // the person has typed would put the stored text back
  const asked = ++P.asked;
  // every prompt the agents of each role are sent, by role, whether or not it was sent yet, then the other stored ones
  const catalog = await getJson(`/api/prompt-catalog?project=${encodeURIComponent(S.project || '')}`);
  if (asked !== P.asked) return;
  const listed = [...catalog.roles.flatMap(role => role.prompts), ...catalog.stored.map(item => item.name)];
  // With no prompt to open there is nothing to choose or edit, so only that is said.
  $('#p-prompt .toolbar').hidden = !listed.length;
  if (!P.editor) $('#editor').hidden = !listed.length;
  if (!listed.length) {
    $('#promptNote').textContent = 'No prompts to open: the agents module, which lists the prompts each agent is '
      + 'sent, is off for this project, and the prompt store holds none yet.';
    return;
  }
  // the system agent's prompt opens first: the tasks module's user agent prompt, by its store name or its short one
  const chosen = listed.includes(name) ? name
    : ['prompt.tasks:user_agent.txt', 'tasks:user_agent.txt'].find(one => listed.includes(one)) || listed[0];
  const read = await getJson(`/api/prompt-versions?name=${encodeURIComponent(chosen)}`);
  if (asked !== P.asked) return;
  P.name = chosen;
  P.versions = read.versions;
  P.number = P.versions.some(item => item.number === number) ? number : P.versions[0].number;
  const option = item => h('option', {value: item, selected: item === P.name}, item);
  fill($('#promptSel'), [
    ...catalog.roles.map(role => h('optgroup', {label: `${role.role} agent`, title: role.purpose},
      role.prompts.map(option))),
    catalog.stored.length ? h('optgroup', {label: 'Other stored prompts'}, catalog.stored.map(item => option(item.name)))
      : null]);
  fill($('#verSel'), P.versions.map(item => h('option',
    {value: String(item.number), selected: item.number === P.number},
    item.number ? `version ${item.number} · ${item.origin} · ${item.created}` : 'shipped text · not sent yet')));
  const version = P.versions.find(item => item.number === P.number);
  if (!P.editor) P.editor = CodeMirror.fromTextArea($('#editor'), {lineNumbers: true, lineWrapping: true});
  // a prompt a module ships is written as plain text, as the agent reads it, and the server encodes it for the file's
  // form when it is saved; any other is shown and saved as stored
  P.editor.setOption('mode', read.written === 'plain' || version.format === 'markdown' ? 'markdown'
    : version.format === 'xml' ? 'xml' : null);
  P.editor.setValue(version.plain ?? version.text);
  P.editor.clearHistory();
  $('#diffOut').hidden = true;
  const names = new Map(S.layers.map(layer => [layer.id, layer.name]));
  const made = version.layers.map(use => names.get(use.layer_id) || `a layer of ${use.project_id}`);
  const said = !version.number ? 'Its shipped text; saving an edit makes it version 1 of the store.'
    : made.length ? `Version ${version.number} made: ${made.join(', ')}.`
    : `No layer was made with version ${version.number}.`;
  $('#promptNote').textContent = read.problem ? `${read.problem}. ${said}` : said;
  setTimeout(() => P.editor.refresh(), 0);
}
$('#promptSel').onchange = () => renderPrompt($('#promptSel').value, null);
$('#verSel').onchange = () => renderPrompt(P.name, Number($('#verSel').value));
/* The lines of two texts compared, the changed ones with two lines around each and the rest folded into gaps. */
function lineDiff(a, b) {
  a = a.split('\n'); b = b.split('\n');
  if (a.length * b.length > 4e6) return [{t: 'gap', s: 'Too large to compare here.'}];
  return foldSame(diffRows(a, b, commonAfter(a, b)));
}
/* The length of the longest run of lines the two share from each pair of places on. */
function commonAfter(a, b) {
  const n = a.length, m = b.length;
  const dp = Array.from({length: n + 1}, () => new Uint32Array(m + 1));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  return dp;
}
/* Each line kept, taken out or added, walking the two texts along the longest run they share. */
function diffRows(a, b, dp) {
  const n = a.length, m = b.length;
  const out = []; let i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { out.push({t: 'same', s: a[i]}); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) out.push({t: 'del', s: a[i++]});
    else out.push({t: 'add', s: b[j++]});
  }
  while (i < n) out.push({t: 'del', s: a[i++]});
  while (j < m) out.push({t: 'add', s: b[j++]});
  return out;
}
function foldSame(out) {
  const keep = new Set();
  out.forEach((row, k) => { if (row.t !== 'same') for (let d = -2; d <= 2; d++) keep.add(k + d); });
  const shown = []; let skipped = false;
  out.forEach((row, k) => {
    if (keep.has(k)) { shown.push(row); skipped = false; }
    else if (!skipped) { shown.push({t: 'gap', s: '···'}); skipped = true; }
  });
  return shown;
}
const DIFF_MARK = {add: '+ ', del: '- '};
function showDiff() {
  const found = P.versions.find(item => item.number === P.number);
  const base = found.plain ?? found.text;
  const rows = lineDiff(base, P.editor.getValue());
  const changed = rows.some(row => row.t === 'add' || row.t === 'del');
  fill($('#diffOut'), changed
    ? rows.map(row => h('div', {class: row.t}, (Object.hasOwn(DIFF_MARK, row.t) ? DIFF_MARK[row.t] : '  ') + row.s))
    : h('div', {class: 'gap'}, `No changes from version ${P.number}.`));
  $('#diffOut').hidden = false;
  return changed;
}
$('#diffBtn').onclick = showDiff;
/* Save: the text as a new version of the prompt, after its changes are shown. */
async function savePrompt() {
  if (!showDiff()) return toast(P.number ? `Nothing to save. The text matches version ${P.number}.`
    : 'Nothing to save. The text matches the shipped text.');
  const response = await fetch('/api/save-prompt', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name: P.name, text: P.editor.getValue(), parent: P.number})});
  const saved = await response.json().catch(() => ({}));
  if (!response.ok) return toast(saved.error || 'The prompt was not saved.');
  await renderPrompt(P.name, saved.number);
  // what the save left out or keeps as written, said with it, so the person knows what the agent is sent
  toast([`Saved as version ${saved.number}.`, ...(saved.said || [])].join(' '));
}
$('#saveBtn').onclick = savePrompt;

/* ---------- tabs ---------- */
/* The panel's tabs, as tabs are: the open one is in the Tab order, and Left and Right move between them. */
const TABS = {object: '#p-object', brief: '#p-brief', prov: '#p-prov', prompt: '#p-prompt'};
export const tabNow = () => WS.on ? (WS.isShown('map.brief') ? 'brief' : 'object')
  : Object.keys(TABS).find(key => $('#t-' + key).getAttribute('aria-selected') === 'true') || 'object';
export function showTab(tab) {
  if (tab !== 'prompt' && $('#p-prompt').classList.contains('full')) promptFull(false);
  if (WS.on) WS.reveal(TAB_VIEWS[tab]);  // a pane of the workspace, opened where the person put it
  else openPane(tab);
  if (tab === 'prov') renderProv();
  if (tab === 'brief') renderBrief();
  if (tab === 'prompt' && !P.editor) renderPrompt();
  if (tab === 'prompt' && P.editor) setTimeout(() => P.editor.refresh(), 0);
}
/* The tab's pane shown and the tab marked open, the others hidden and taken out of the Tab order. */
function openPane(tab) {
  for (const [key, selector] of Object.entries(TABS)) {
    $(selector).hidden = key !== tab;
    $('#t-' + key).setAttribute('aria-selected', String(key === tab));
    $('#t-' + key).tabIndex = key === tab ? 0 : -1;
  }
}
for (const key of Object.keys(TABS)) $('#t-' + key).onclick = () => showTab(key);
function walkPanelTabs(event) {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  event.preventDefault();
  // in the order the tabs stand, which the panes' declarations set, `nodeTabs`
  const keys = [...$('.tabs[role=tablist]').children].filter(tab => !tab.hidden).map(tab => tab.id.slice(2));
  const at = keys.findIndex(key => $('#t-' + key).getAttribute('aria-selected') === 'true');
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? keys.length - 1
    : (at + (event.key === 'ArrowRight' ? 1 : -1) + keys.length) % keys.length;
  showTab(keys[next]);
  $('#t-' + keys[next]).focus();
}
$('.tabs[role=tablist]').addEventListener('keydown', walkPanelTabs);
/* The node's tabs are the panes declared in the node group, one list: the map module's Object, Brief and Provenance
 * and the chassis's Prompt, each a view the page draws, `page=`, in the order, with the titles and descriptions, the
 * declarations and the person's layout give them in /api/workspace. A pane turned off there leaves the strip, unless
 * it is the tab on view. Without the workspace, the strip stays as the page is written. */
export const TAB_PAGES = {object: 'object', brief: 'brief', provenance: 'prov', prompt: 'prompt'};
export async function nodeTabs() {
  let found;
  try { found = await getJson(`/api/workspace?project=${encodeURIComponent(S.project || '')}`); } catch { return; }
  const panes = new Map((found.panes || []).map(pane => [pane.id, pane]));
  const group = Object.values(found.layout?.areas || {}).flatMap(area => area.groups || [])
    .find(one => one.tabs.some(id => TAB_PAGES[panes.get(id)?.content?.page] === 'object'));
  if (group) classicTabs(panes, group.tabs, new Set(found.layout.off || []));
}
/* The side column's tabs as a layout gives them: in its order, with their titles, a tab turned off gone from the strip
 * unless it is the one on view; and each tab's pane shown or hidden by the tab open, as the workspace may have moved
 * them. The workspace's arrangement that is the page as written, `classicFrame`, draws them this way too. */
export function classicTabs(panes, tabs, off) {
  const strip = $('.tabs[role=tablist]'), now = tabNow();
  for (const id of tabs) {
    const pane = panes.get(id), key = TAB_PAGES[pane?.content?.page];
    if (!key) continue;
    const tab = $('#t-' + key);
    tab.textContent = pane.title;
    tab.title = pane.description;
    tab.hidden = off.has(id) && key !== now;
    strip.append(tab);  // in the declared order
  }
  openPane(now);
}
/* The prompt editor fills the screen, and back, VIEW-013; Escape puts it back. */
function promptFull(on) {
  const pane = $('#p-prompt');
  pane.classList.toggle('full', on);
  $('#promptFull').setAttribute('aria-pressed', String(on));
  // on the stack by hand, since the pane's own hidden follows the tabs and not the full screen
  OVERLAY.stack = OVERLAY.stack.filter(entry => entry.box !== pane);
  if (on) OVERLAY.stack.push({box: pane, kind: 'window', close: () => promptFull(false), opener: $('#promptFull')});
  restack();
  if (!on) { pane.style.zIndex = ''; $('#promptFull').focus({preventScroll: true}); }
  if (P.editor) setTimeout(() => { P.editor.refresh(); if (on) P.editor.focus(); }, 0);
}
$('#promptFull').onclick = () => promptFull(!$('#p-prompt').classList.contains('full'));
