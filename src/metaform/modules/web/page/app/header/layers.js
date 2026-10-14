/* Layers colored by position, the side column's splitters and side, the roots of the project's edges, and the Layers
 * checklist with Apply. */
import '/page/app/core/reads.js';  // the part before runs first, so the parts run in the page's order
import {$, css, reduced, h, fill} from '/page/app/core/dom.js';
import {S} from '/page/app/core/reads.js';
import {draw3D} from '/page/app/map3d/draw3d.js';
import {EASE, durFor} from '/page/app/camera/fly3d.js';
import {renderLegend} from '/page/app/views/lens.js';
import {build2D} from '/page/app/map2d/build.js';
import {loadGraph} from '/page/app/loading/load.js';

/* ---------- layers: color by position, the Layers checklist, apply ---------- */
const KNOWLEDGE = ['--k1', '--k2', '--k3', '--k4', '--k5', '--k6'];
export function colorVar(layerName) {
  const layer = S.layers.find(item => item.name === layerName);
  if (!layer) return '--intake';
  if (layer.kind === 'base') return '--intake';  // the base layer, kind base, keeps the intake color
  if (layer.kind === 'memory') return '--memory';
  const knowledge = S.layers.filter(item => !['base', 'memory'].includes(item.kind));
  return KNOWLEDGE[knowledge.indexOf(layer) % KNOWLEDGE.length];
}
export const layerColor = name => css(colorVar(name));
const folderOn = () => new Set(S.layers.filter(layer => layer.on).map(layer => layer.name));
export const shownOn = () => S.view ?? folderOn();
const same = (a, b) => a.size === b.size && [...a].every(x => b.has(x));

/* The edges of the project, upstream entries, what the project depends on, and downstream entries,
 * who it serves, are records under those roots, not layers; the page lists each root beside the layers as a toggle
 * that hides every record under it, so the product's own parts stand alone. Remembered per viewer. */
const ROOTS = ['upstream', 'downstream'];
/* The side column's width and the split between its small map and its panes are dragged: each is
 * remembered by this browser, and a double-click puts it back. The maps follow the new size as they follow the
 * window. */
const SIZES = {
  side: ['metaform.sideWidth', '--side-width', 320, () => innerWidth - 320],  // never narrower than a phone
  // the small area never shorter than its bar and 160 px of map, so a selected name has room to be read in it
  small: ['metaform.smallHeight', '--small-height', 200, () => $('aside').clientHeight - 140]};
function sized(which, pixels) {
  const [key, name, least, most] = SIZES[which];
  const app = document.querySelector('.app');
  if (pixels === null) app.style.removeProperty(name);
  else app.style.setProperty(name, Math.round(Math.max(least, Math.min(most(), pixels))) + 'px');
  try { pixels === null ? localStorage.removeItem(key) : localStorage.setItem(key, String(Math.round(pixels))); }
  catch (error) { /* storage can be blocked; the size still changes */ }
  dispatchEvent(new Event('resize'));
}
function splitter(handle, which, measure) {
  handle.addEventListener('pointerdown', event => {
    event.preventDefault();
    handle.classList.add('dragging');
    const move = moved => sized(which, measure(moved));
    const end = () => {
      handle.classList.remove('dragging');
      removeEventListener('pointermove', move);
      removeEventListener('pointerup', end);
    };
    addEventListener('pointermove', move);
    addEventListener('pointerup', end);
  });
  handle.addEventListener('dblclick', () => sized(which, null));
  let kept = null;
  try { kept = localStorage.getItem(SIZES[which][0]); } catch (error) { /* storage can be blocked */ }
  if (kept) sized(which, Number(kept));
}
/* The side column moves to the other side only when a drag brings the pointer to that edge of the window, within
 * FLIP_SIDE pixels of it, so a wide resize never flips it by surprise; once moved, it goes back only when the pointer
 * returns past the middle. */
const FLIP_SIDE = 40;
const nearRight = x => x > innerWidth - FLIP_SIDE, nearLeft = x => x < FLIP_SIDE;
/* The side column's splitter resizes it; dragged on to the far edge, away from the column's own side, it moves the
 * column to that side, keeping the width it had when the drag began, as dragging its top bar does, and back again if
 * the pointer returns past the middle. While held the splitter shows its grip, the cursor says resize, and once
 * across, move. */
const SIDE_DRAG = {width: 0, right: true, across: false};
function startSideSplit() {
  SIDE_DRAG.width = $('aside').getBoundingClientRect().width;
  SIDE_DRAG.right = document.querySelector('.app').classList.contains('side-right');
  SIDE_DRAG.across = false;
  document.body.classList.add('sizing-side');
  const end = () => {
    document.body.classList.remove('sizing-side', 'moving-side-split');
    $('#sideSplit').classList.remove('across');
    for (const type of ['pointerup', 'pointercancel', 'blur']) removeEventListener(type, end);
  };
  for (const type of ['pointerup', 'pointercancel', 'blur']) addEventListener(type, end);
}
/* The side column's width while its splitter is dragged, or the width it had once the drag goes across. */
function measureSide(moved) {
  const right = document.querySelector('.app').classList.contains('side-right');
  const x = moved.clientX, back = SIDE_DRAG.right ? x > innerWidth / 2 : x < innerWidth / 2;
  const across = SIDE_DRAG.across = SIDE_DRAG.across ? !back : SIDE_DRAG.right ? nearLeft(x) : nearRight(x);
  $('#sideSplit').classList.toggle('across', across);
  document.body.classList.toggle('moving-side-split', across);
  const want = across ? !SIDE_DRAG.right : SIDE_DRAG.right;
  if (want !== right) sideAt(want, true);
  if (across) return SIDE_DRAG.width;
  const edge = $('aside').getBoundingClientRect();
  return want ? edge.right - moved.clientX : moved.clientX - edge.left;
}
$('#sideSplit').addEventListener('pointerdown', startSideSplit, true);
splitter($('#sideSplit'), 'side', measureSide);
/* The side column goes on the left or the right of the page: its top bar, whichever map is in the small area, is
 * dragged across and the column follows the pointer once it reaches the other edge, `FLIP_SIDE`; a press that does
 * not move is an ordinary click. The View menu chooses the side too. The side is kept in this browser. */
const SIDE_AT = 'metaform.sideAt';
export function sideAt(right, ease = false) {
  const app = document.querySelector('.app');
  $('#sideat').value = right ? 'right' : 'left';
  if (app.classList.contains('side-right') === right) return;
  // with `ease`, the column and the maps glide from where they stood to their new places, on the shared move curve
  const moving = ease && !reduced() ? [$('aside'), $('main')].filter(Boolean) : [];
  const before = moving.map(one => one.getBoundingClientRect().left);
  app.classList.toggle('side-right', right);
  try { localStorage.setItem(SIDE_AT, right ? 'right' : 'left'); } catch { /* storage can be blocked */ }
  moving.forEach((one, index) => {
    const by = before[index] - one.getBoundingClientRect().left;
    if (by) one.animate([{transform: `translateX(${by}px)`}, {transform: 'translateX(0)'}],
      {duration: durFor(Math.abs(by)), easing: `cubic-bezier(${EASE.move.join(',')})`});
  });
  dispatchEvent(new Event('resize'));
}
function dragSideByBar(event) {
  if (event.button !== 0 || !event.target.closest('aside .bar2d, aside .bar3d')) return;
  if (event.target.closest('button, input, select, textarea, a, nav')) return;
  if (matchMedia('(max-width: 820px)').matches) return;
  const from = event.clientX, pointer = event.pointerId;
  let moving = false;
  const move = moved => {
    if (moved.pointerId !== pointer) return;
    if (!moving && Math.abs(moved.clientX - from) < 6) return;
    moving = true;
    document.body.classList.add('moving-side');
    const right = document.querySelector('.app').classList.contains('side-right'), x = moved.clientX;
    sideAt(right ? !nearLeft(x) : nearRight(x), true);
  };
  // a drag ends however the pointer is let go: released, cancelled by the system, or the window losing focus
  const end = () => {
    document.body.classList.remove('moving-side');
    removeEventListener('pointermove', move);
    for (const type of ['pointerup', 'pointercancel', 'blur']) removeEventListener(type, end);
  };
  addEventListener('pointermove', move);
  for (const type of ['pointerup', 'pointercancel', 'blur']) addEventListener(type, end);
}
$('aside').addEventListener('pointerdown', dragSideByBar);
$('#sideat').onchange = event => sideAt(event.target.value === 'right', true);
/* The reading column opens on the right, where the person reads without turning to the left; left only when chosen. */
function keptSideRight() {
  try { return localStorage.getItem(SIDE_AT) !== 'left'; } catch { return true; }
}
sideAt(keptSideRight());
splitter($('#smallSplit'), 'small', moved => moved.clientY - $('#small').getBoundingClientRect().top);
export function rootsOff() {
  try { return new Set(JSON.parse(localStorage.getItem('metaform.rootsOff') || '[]')); } catch { return new Set(); }
}
const rootOf = address => (address || '').split('.')[0];
export const underHiddenRoot = address => rootsOff().has(rootOf(address));
/* The layers: a checklist opened from the header's Layers button, one row each, VIEW-007. The edges of the project,
 * upstream and downstream, are listed apart under their own heading, VIEW-046, since they are records and not layers
 * and the button counts layers only. */
export function renderChips() {
  const on = shownOn();
  const box = $('#layers');
  fill(box);
  const listed = S.layers;
  let count = 0;
  const off = rootsOff();
  box.append(h('div', {class: 'section'}, 'Layers'));
  for (const layer of listed) {
    const usable = layer.ready && !layer.hidden, checked = usable && on.has(layer.name);
    if (checked) count++;
    box.append(layerRow(layer, usable, checked));
  }
  box.append(h('div', {class: 'section'}, 'Edges of the project'));
  for (const root of ROOTS) box.append(rootRow(root, !off.has(root)));
  $('#layersBtn .lbl').textContent = `Layers · ${count} of ${listed.length}`;
  $('#apply').disabled = S.view === null;
  const folder = S.projects.find(item => item.id === S.project)?.path || '';
  $('#note').textContent = S.view === null
    ? `Viewing only. These are the layers of ${folder}. `
      + 'What you toggle changes this view, not the folder, until you apply it.'
    : S.view.size === 0 ? 'No layer is chosen, which reads as every layer, as an empty --layers does.'
    : `This view differs from ${folder}. Apply to folder runs: metaform set --layers ${[...S.view].join(',')}`;
}
/* A layer's row of the checklist: turning it on or off changes this view only, and the map is read again. */
function layerRow(layer, usable, checked) {
  const input = h('input', {type: 'checkbox', 'data-layer': layer.name, disabled: !usable, onchange: () => {
    const next = new Set(shownOn());
    input.checked ? next.add(layer.name) : next.delete(layer.name);
    S.view = same(next, folderOn()) ? null : next;
    renderChips();
    loadGraph();
  }});
  input.checked = checked;
  const state = layer.hidden ? 'hidden' : !layer.ready ? 'building' : 'ready';
  const meta = [layer.kind, ...(layer.tags || []), state].join(' · ');
  return h('label', {class: 'layerrow', style: {'--c': `var(${colorVar(layer.name)})`},
    title: layer.hidden ? 'Hidden: it stays out even when turned on.' : !layer.ready ? 'Still building.' : null},
    input, h('i'), h('span', {class: 'name'}, layer.name), ' ', h('span', {class: 'meta'}, meta));
}
/* A root's row, upstream or downstream: turned off, every record under it is hidden, kept in this browser. */
function rootRow(root, checked) {
  const input = h('input', {type: 'checkbox', 'data-root': root, onchange: () => {
    const next = rootsOff();
    input.checked ? next.delete(root) : next.add(root);
    try { localStorage.setItem('metaform.rootsOff', JSON.stringify([...next])); }
    catch (error) { /* storage can be blocked; the view still changes */ }
    renderChips();
    draw3D(); renderLegend(); build2D();
  }});
  input.checked = checked;
  const title = root === 'upstream' ? 'What the project depends on: records under upstream.'
    : 'Who the project serves: records under downstream.';
  return h('label', {class: 'layerrow root', style: {'--c': 'var(--muted)'}, title},
    input, h('i'), h('span', {class: 'name'}, root), ' ', h('span', {class: 'meta'}, 'root · records'));
}
