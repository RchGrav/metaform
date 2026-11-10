/* Every key the page takes, in one table, the reference `?` opens, and the page's keydown handler. */
import '/classic/app/keys/walk.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/classic/app/core/dom.js';
import {S, MEM} from '/classic/app/core/reads.js';
import {stepFlow} from '/classic/app/views/bar.js';
import {M} from '/classic/app/map2d/build.js';
import {entryOf} from '/classic/app/map2d/fit.js';
import {IN} from '/classic/app/map2d/inside.js';
import {MAC, resetZoom} from '/classic/app/map2d/camera.js';
import {deselect, step} from '/classic/app/map2d/wire.js';
import {across, below, besideDrawn, besideOnLevel, childrenOf, parentOf, roots, goInside, levelUp, mapKeys,
  stepDepth} from '/classic/app/keys/walk.js';
import {select} from '/classic/app/selection/select.js';
import {openSearch} from '/classic/app/search/search.js';

/* Every key the page takes, in one table: the reference `?` opens is drawn from it, grouped and searchable, and the
 * map's keys run from it, `KEY_RUN`, so the two never part. `keys` is what the reference shows, `match` the keys that
 * run `run`, a key held with Alt matched as `Alt+` and its name; an entry with no `run` is a key another handler takes,
 * written here so it is listed. The maps have no bar: these keys do what its buttons did. */
const KEYS = [
  {group: 'Anywhere', keys: ['/'], what: 'Search the map', match: ['/'], run: () => openSearch()},
  {group: 'Anywhere', keys: ['?'], what: 'Keyboard shortcuts', match: ['?'], run: () => openHelp()},
  {group: 'Anywhere', keys: ['Esc'], what: 'Close, or deselect'},
  {group: 'Maps', keys: ['↑', '↓', '←', '→'], what: 'Move between nodes'},
  {group: 'Maps', keys: ['Enter'], what: 'Go inside'},
  {group: 'Maps', keys: ['Shift', 'Enter'], what: 'Go out'},
  {group: 'Maps', keys: [MAC ? '⌥' : 'Alt', '←'], what: 'Back to the node selected before', match: ['Alt+ArrowLeft'],
    run: () => step(-1)},
  {group: 'Maps', keys: [MAC ? '⌥' : 'Alt', '→'], what: 'Forward again', match: ['Alt+ArrowRight'],
    run: () => step(1)},
  // each digit cycles one setting, and each press says its new value at the map's corner; the map is fit-all, zooming
  // by the wheel at any time, VIEW-041
  {group: 'Zoom', keys: ['0'], what: 'Full fit', match: ['0', 'Home'], run: () => resetZoom()},
  {group: 'Looks', keys: ['2'], what: 'Flow: off, hover, selection, all, then each with edges hidden',
    match: ['2'], run: () => stepFlow()},
  {group: 'Looks', keys: ['4'], what: "Depth: the map's own levels, from the first that draws a line, or all", match: ['4'], run: () => stepDepth()},
];
const KEY_RUN = new Map(KEYS.filter(entry => entry.run).flatMap(entry => entry.match.map(key => [key, entry])));
/* The reference, drawn from `KEYS`, centered over the page: its tabs, the everyday keys first, then the developer's,
 * then the looks and the zoom; each group a card of what a key does with its keys beside it; and a search that keeps
 * the keys whose words match, across every tab. A tab with no keys is not offered. */
const HELP_TABS = [['Shortcuts', ['Anywhere', 'Maps', 'Agents', 'Chat', 'Tools']], ['Dev keys', ['Developer']],
  ['Visuals', ['Zoom', 'Looks']]];
const HELP = {tab: 'Shortcuts'};
export function openHelp() {
  $('#settingsbox').hidden = true;
  const find = $('#help .keyfind');
  const draw = () => drawHelp(find, draw);
  find.oninput = draw;
  draw();
  $('#help').hidden = false;
  find.focus();
}
/* The reference as the search box and the tab leave it: the tabs that have keys, and the keys of the tab chosen, or of
 * every tab whose words match the search, a card for each group. */
function drawHelp(find, draw) {
  const box = $('#help .keys'), tabs = $('#help .helptabs');
  const words = find.value.trim().toLowerCase();
  const all = KEYS;
  const offered = HELP_TABS.filter(([, groups]) => all.some(entry => groups.includes(entry.group)));
  if (!offered.some(([name]) => name === HELP.tab)) HELP.tab = offered[0]?.[0];
  fill(tabs, offered.map(([name]) => h('button', {type: 'button', role: 'tab',
    'aria-selected': String(!words && name === HELP.tab), onclick: () => { HELP.tab = name; find.value = ''; draw(); }},
  name)));
  const shown = words ? null : HELP_TABS.find(([name]) => name === HELP.tab)?.[1];
  const said = entry => `${entry.group} ${entry.keys.join(' ')} ${entry.what}`.toLowerCase();
  const rows = all.filter(entry => words ? said(entry).includes(words) : shown?.includes(entry.group));
  const groups = [...new Set(rows.map(entry => entry.group))];
  fill(box, groups.length ? groups.map(group => keyCard(group, rows)) : h('p', {class: 'empty'}, 'No key does that.'));
}
/* One group's card: what each key does, its keys beside it. */
function keyCard(group, rows) {
  const chip = key => /^(Click|click)$/.test(key) ? h('span', {}, key) : h('kbd', {}, key);
  return h('section', {class: 'keycard'}, h('h3', {}, group),
    rows.filter(entry => entry.group === group).map(entry => h('div', {class: 'keyrow'},
      h('span', {class: 'what'}, entry.what), h('span', {class: 'chips'}, entry.keys.map(chip)))));
}
/* The maps' keys: those of the key table, `KEYS`, each run by its entry, so the reference `?` opens says what each
 * does; Escape and Shift+Enter; and the arrows and Enter, which walk the map. */
function mapKey(event) {
  if (!mapKeys(event)) return;
  // The keys of the key table, `KEYS`, each run by its entry, so the reference `?` opens says what each does.
  const entry = KEY_RUN.get(event.altKey ? `Alt+${event.key}` : event.key);
  if (entry) { event.preventDefault(); entry.run(event.key); return; }
  if (event.altKey) return;  // only the Alt keys of the table are the maps'
  // Escape lets go of the selection, and with nothing selected backs out one level; Shift+Enter always backs out.
  if (event.key === 'Escape') {
    event.preventDefault();
    if (S.selected) deselect(); else levelUp();
    return;
  }
  if (event.key === 'Enter' && event.shiftKey) { event.preventDefault(); levelUp(); return; }
  if (!S.selected) {  // with nothing selected, an arrow starts from the level's own node, or on the map its entry
    const start = event.key.startsWith('Arrow') ? (IN.length ? IN.at(-1).key : MEM.key || entryOf()) : null;
    if (start) { event.preventDefault(); select(start, true, true); }
    return;
  }
  const here = S.selected;
  if (event.key === 'Enter') { event.preventDefault(); goInside(here); return; }
  // inside a node or a memory network the arrows go through its graph in order
  if ((IN.length || MEM.key) && event.key.startsWith('Arrow')) {
    event.preventDefault();
    const order = across(M.nodes.keys()), at = order.indexOf(here);
    const by = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : -1;
    if (order.length) select(order[at < 0 ? 0 : (at + by + order.length) % order.length], true, true);
    return;
  }
  walkTree(event, here);
}
/* Translate physical arrows to the top-to-bottom tree actions when the rendered map runs left to right.
 * History keys and the ordered walks inside a node or memory network are handled before this translation. */
const ACROSS_KEYS = {ArrowRight: 'ArrowDown', ArrowLeft: 'ArrowUp', ArrowUp: 'ArrowLeft', ArrowDown: 'ArrowRight'};
/* Walk the join tree along its rendered axes: deeper, back along the trail or to the parent, or between siblings
 * and on past the ends of their row. */
function walkTree(event, here) {
  const key = M.vertical ? event.key : ACROSS_KEYS[event.key];
  if (key === 'ArrowDown') {
    event.preventDefault();
    const next = below(here);
    if (next) { S.trail.push(here); select(next, true, true); }
  } else if (key === 'ArrowUp') {
    event.preventDefault();
    const parent = S.trail.length ? S.trail.pop() : parentOf(here);
    if (parent) select(parent, true, true);
  } else if (key === 'ArrowLeft' || key === 'ArrowRight') {
    event.preventDefault();
    const parent = S.trail.length ? S.trail[S.trail.length - 1] : parentOf(here);
    const row = parent ? childrenOf(parent) : roots();
    const at = row.indexOf(here), by = key === 'ArrowRight' ? 1 : -1;
    if (at >= 0 && row[at + by]) { select(row[at + by], true, true); return; }
    // past the end of the row: the node drawn nearest beside it that way, whatever its parent, whose row it is in
    // then; with nothing drawn beyond, round the level of the tree
    const drawn = besideDrawn(here, by);
    const beside = drawn ? {next: drawn, parent: parentOf(drawn)} : besideOnLevel(here, parent, by);
    if (!beside) return;
    if (S.trail.length && beside.parent) S.trail[S.trail.length - 1] = beside.parent;
    select(beside.next, true, true);
  }
}
document.addEventListener('keydown', mapKey);
