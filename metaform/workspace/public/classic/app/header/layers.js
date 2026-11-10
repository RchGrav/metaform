/* Layers colored by position, the roots of the project's edges, and the Layers checklist, from the earlier page's
 * header/layers.js. The earlier page read the map again from its server in the layers checked, and could apply the
 * choice to the folder; the new server gives the whole map in one read, so a layer unchecked is hidden on this page
 * alone: its records leave the side column, the view inside an element and the search. The side column's own width
 * and its side, which that file also held, are not part of this page; the split between the small map and the panes
 * is. */
import '/classic/app/adapter.js';  // the part before runs first, so the parts run in the page's order
import {$, css, h, fill} from '/classic/app/core/dom.js';
import {S} from '/classic/app/core/reads.js';
import {viewValue, saveView} from '/classic/app/views/settings.js';
import {draw3D} from '/classic/app/map3d/draw3d.js';
import {renderLegend} from '/classic/app/views/lens.js';
import {build2D} from '/classic/app/map2d/build.js';
import {IN, drawInside} from '/classic/app/map2d/inside.js';
import {select} from '/classic/app/selection/select.js';

/* ---------- layers: color by position, the Layers checklist ---------- */
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
/* The layers a person unchecked, kept in this browser with the other view settings as web_layers_off. */
export const layersOff = () => new Set(viewValue('web_layers_off', []));
export const layerOn = name => !layersOff().has(name);

/* The edges of the project, upstream entries, what the project depends on, and downstream entries,
 * who it serves, are records under those roots, not layers; the page lists each root beside the layers as a toggle
 * that hides every record under it, so the product's own parts stand alone. Remembered per viewer, as
 * web_roots_off. */
const ROOTS = ['upstream', 'downstream'];
export function rootsOff() { return new Set(viewValue('web_roots_off', [])); }
const rootOf = address => (address || '').split('.')[0];
export const underHiddenRoot = address => rootsOff().has(rootOf(address));
/* The split between the side column's small map and its panes is dragged: it is remembered by this browser, and a
 * double-click puts it back. The maps follow the new size as they follow the window. */
const SIZES = {
  // the small area never shorter than its bar and 160 px of map, so a selected name has room to be read in it
  small: ['classic.smallHeight', '--small-height', 200, () => $('aside').clientHeight - 140]};
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
splitter($('#smallSplit'), 'small', moved => moved.clientY - $('#small').getBoundingClientRect().top);
/* How many elements hold records of a layer. */
const holders = name => [...S.elements.values()].filter(({element}) => element.records[name]?.length).length;
/* The layers: a checklist opened from the header's Layers button, one row each, VIEW-007. The edges of the project,
 * upstream and downstream, are listed apart under their own heading, VIEW-046, since they are records and not layers
 * and the button counts layers only. */
export function renderChips() {
  const off = layersOff();
  const box = $('#layers');
  fill(box);
  const listed = S.layers.filter(layer => layer.kind !== 'base');
  let count = 0;
  const hidden = rootsOff();
  box.append(h('div', {class: 'section'}, 'Layers'));
  for (const layer of listed) {
    const checked = !off.has(layer.name);
    if (checked) count++;
    box.append(layerRow(layer, checked));
  }
  if (!listed.length) box.append(h('p', {class: 'empty'}, 'No layer is recorded on this map yet.'));
  box.append(h('div', {class: 'section'}, 'Edges of the project'));
  for (const root of ROOTS) box.append(rootRow(root, !hidden.has(root)));
  $('#layersBtn .lbl').textContent = `Layers · ${count} of ${listed.length}`;
  $('#note').textContent = 'Viewing only. What you uncheck is hidden on this page, in this browser. '
    + 'The map on the server does not change.';
}
/* A layer's row of the checklist: turning it on or off changes this view only, and what shows its records is drawn
 * again. */
function layerRow(layer, checked) {
  const input = h('input', {type: 'checkbox', 'data-layer': layer.name, onchange: async () => {
    const next = layersOff();
    input.checked ? next.delete(layer.name) : next.add(layer.name);
    await saveView('web_layers_off', next.size ? [...next] : null);
    renderChips();
    layersShown();
  }});
  input.checked = checked;
  const held = holders(layer.name);
  const meta = `records at ${held} element${held === 1 ? '' : 's'}`;
  return h('label', {class: 'layerrow', style: {'--c': `var(${colorVar(layer.name)})`},
    title: layer.title && layer.title !== layer.name ? layer.title : null},
    input, h('i'), h('span', {class: 'name'}, layer.name), ' ', h('span', {class: 'meta'}, meta));
}
/* The layers checked changed: the side column and the view inside an element are drawn again from them. */
function layersShown() {
  S.panelPrint = null;  // the Object tab is drawn again, `selectNow`
  if (S.selected) select(S.selected, false, true, true, true);
  if (IN.length) drawInside();
}
/* A root's row, upstream or downstream: turned off, every record under it is hidden, kept in this browser. */
function rootRow(root, checked) {
  const input = h('input', {type: 'checkbox', 'data-root': root, onchange: async () => {
    const next = rootsOff();
    input.checked ? next.delete(root) : next.add(root);
    await saveView('web_roots_off', next.size ? [...next] : null);
    renderChips();
    draw3D(); renderLegend(); build2D(true, false, true);
    document.dispatchEvent(new CustomEvent('classic:depth'));  // the map's levels are counted without the root
  }});
  input.checked = checked;
  const title = root === 'upstream' ? 'What the project depends on: records under upstream.'
    : 'Who the project serves: records under downstream.';
  const held = [...S.elements.values()].filter(({element}) => rootOf(element.address) === root).length;
  return h('label', {class: 'layerrow root', style: {'--c': 'var(--muted)'}, title},
    input, h('i'), h('span', {class: 'name'}, root), ' ',
    h('span', {class: 'meta'}, `root · ${held} element${held === 1 ? '' : 's'}`));
}
