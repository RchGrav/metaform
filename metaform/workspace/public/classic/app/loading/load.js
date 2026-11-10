/* Loading: the projects, a project's map read and drawn, the map followed as it changes, and the header's own
 * controls. It does the work of the earlier page's loading/load.js and workspace/workspace.js `main` for this page;
 * the reads are adapter.js's. */
import '/classic/app/header/export.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/classic/app/core/dom.js';
import {toast} from '/classic/app/core/controls.js';
import {S} from '/classic/app/core/reads.js';
import {listProjects, readMap, follow} from '/classic/app/adapter.js';
import {M, build2D, build2DSoon, setMermaidReady} from '/classic/app/map2d/build.js';
import {entryOf} from '/classic/app/map2d/fit.js';
import {IN, renderCrumbs} from '/classic/app/map2d/inside.js';
import {deselect, noneSelected} from '/classic/app/map2d/wire.js';
import {DEPTH, FOCUS, nudgeDepth, depthWords} from '/classic/app/keys/walk.js';
import {select} from '/classic/app/selection/select.js';
import {readView} from '/classic/app/views/settings.js';
import {renderChips} from '/classic/app/header/layers.js';
import {foldHeader} from '/classic/app/header/menus.js';

const LOAD = {unfollow: null, reading: null, again: false};
const PROJECT_KEY = 'classic.project';
/* The page shown once it is laid out, two frames after the map is drawn, `booting` in theme.js. */
function revealed() {
  requestAnimationFrame(() => requestAnimationFrame(() => document.documentElement.classList.remove('booting')));
}
/* The map read from the server into the page's state. Says whether it was read. */
async function readGraph() {
  S.loading++;
  try {
    const project = S.project, found = await readMap(project);
    if (project !== S.project) return false;  // another project was chosen meanwhile
    Object.assign(S, found);
    renderChips();  // the Layers checklist lists the layers this map holds
    return true;
  } catch (error) {
    toast(error.message);
    return false;
  } finally { S.loading--; }
}
/* A project shown: its map read, its entry selected as the earlier page selected it, and the map drawn. */
export async function loadProject(id) {
  LOAD.unfollow?.();
  Object.assign(S, {project: id, elements: new Map(), joins: [], selected: null, cleared: false, panelFor: null,
    panelPrint: null, trail: [], history: [], at: -1, neighbors: new Set()});
  IN.length = 0; M.base = null; M.svg = null; M.nodes = new Map(); M.edges = []; M.cam = null;
  DEPTH.open.clear(); FOCUS.selected = null; FOCUS.sig = '';
  renderCrumbs();
  fill($('#viewport'));
  fill($('#p-object'), h('p', {class: 'loading'}, 'Reading the map…'));
  try { localStorage.setItem(PROJECT_KEY, id); } catch { /* storage can be blocked */ }
  if (!await readGraph()) {
    fill($('#p-object'), h('p', {class: 'empty'}, 'The map of this project could not be read.'));
    return;
  }
  S.loading++;  // the selection opens its branch without a drawing of its own; the build below draws it
  try {
    const start = S.elements.size ? entryOf() : null;
    if (start) await select(start, false, false, false, true); else noneSelected();
  } finally { S.loading--; }
  await build2D(false);
  showDepth();
  LOAD.unfollow = follow(id, mapChanged);
}
/* The map changed on the server: it is read again, once for the changes that come while it is read, the selection
 * kept where its part is still on the map, and the map drawn again, each node easing to its new place. */
async function mapChanged() {
  if (LOAD.reading) { LOAD.again = true; return; }
  LOAD.reading = (async () => {
    do {
      LOAD.again = false;
      if (!await readGraph()) continue;
      const kept = S.selected && (S.elements.has(S.selected)
        || S.joins.some(join => 'p:' + join.id === S.selected));
      if (S.selected && !kept) deselect();
      S.loading++;
      try { if (kept) await select(S.selected, false, true, true, true); } finally { S.loading--; }
      await build2DSoon();
      showDepth();
    } while (LOAD.again);
  })();
  try { await LOAD.reading; } finally { LOAD.reading = null; }
}
/* The header's depth: the depth drawn in words, between Less and More. */
function showDepth() { $('#depthNow').textContent = depthWords(); }
document.addEventListener('classic:depth', showDepth);
$('#depthLess').onclick = () => nudgeDepth(-1);
$('#depthMore').onclick = () => nudgeDepth(1);
/* The page's colours, kept in this browser as the earlier page kept them; the map is drawn again in them. */
$('#theme').value = document.documentElement.dataset.theme || 'space';
$('#theme').onchange = event => {
  document.documentElement.dataset.theme = event.target.value;
  try { localStorage.setItem('metaform.theme', event.target.value); } catch { /* storage can be blocked */ }
  setMermaidReady(false);
  if (S.elements.size) build2D(false);
};
export async function main() {
  readView();
  const select2 = $('#proj');
  try { S.projects = await listProjects(); } catch (error) {
    fill($('#p-object'), h('p', {class: 'empty'}, error.message));
    revealed();
    return;
  }
  fill(select2, S.projects.map(project => h('option', {value: project.id, title: project.folder || ''}, project.name)));
  foldHeader();  // the project's name is in the header now
  select2.onchange = () => { loadProject(select2.value); $('#map2d').focus({preventScroll: true}); };
  let wanted = new URLSearchParams(location.search).get('project');
  try { wanted ||= localStorage.getItem(PROJECT_KEY); } catch { /* storage can be blocked */ }
  const first = S.projects.find(project => project.id === wanted || project.name === wanted) || S.projects[0];
  if (!first) {
    fill($('#p-object'), h('p', {class: 'empty'}, 'The Metaform host lists no project.'));
    revealed();
    return;
  }
  select2.value = first.id;
  try { await loadProject(first.id); } finally { revealed(); }
  $('#map2d').focus({preventScroll: true});
}
