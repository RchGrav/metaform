/* Every key the page takes, in one table, the reference `?` opens, and the page's keydown handler. */
import '/page/app/keys/walk.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {S, MEM} from '/page/app/core/reads.js';
import {G, touched} from '/page/app/map3d/graph3d.js';
import {PLAIN, setTheme} from '/page/app/map3d/draw3d.js';
import {fit3d} from '/page/app/camera/flight.js';
import {small3d} from '/page/app/camera/fly3d.js';
import {peek} from '/page/app/views/settings.js';
import {stepFlow, PHYS, choosePhysics} from '/page/app/views/bar.js';
import {toggleNodeZoom} from '/page/app/views/lens.js';
import {M} from '/page/app/map2d/build.js';
import {entryOf} from '/page/app/map2d/fit.js';
import {IN} from '/page/app/map2d/inside.js';
import {MAC} from '/page/app/map2d/camera.js';
import {deselect} from '/page/app/map2d/wire.js';
import {across, below, besideDrawn, besideOnLevel, childrenOf, parentOf, roots, goInside, levelUp, mapKeys,
  largeKey} from '/page/app/keys/walk.js';
import {select} from '/page/app/selection/select.js';
import {dockGoingAway, dockState} from '/page/app/dock/embody.js';
import {putChatAway} from '/page/app/dock/helpdesk.js';
import {openSearch} from '/page/app/search/search.js';
import {chatDocked, WS} from '/page/app/workspace/workspace.js';

/* Every key the page takes, in one table: the reference `?` opens is drawn from it, grouped and searchable, and the
 * map's keys run from it, `KEY_RUN`, so the two never part. `keys` is what the reference shows, `match` the keys that
 * run `run`; an entry with no `run` is a key another handler takes, written here so it is listed. The Alt digits are
 * the physics presets, `PHYSICS`, run by their own listener by the key's place. */
const KEYS = [
  {group: 'Anywhere', keys: ['/'], what: 'Search the map', match: ['/'], run: () => openSearch()},
  {group: 'Anywhere', keys: ['?'], what: 'Keyboard shortcuts', match: ['?'], run: () => openHelp()},
  {group: 'Anywhere', keys: ['V'], what: 'View menu', match: ['v', 'V'], run: () => $('#settingsBtn').click()},
  {group: 'Anywhere', keys: ['Esc'], what: 'Close, or deselect'},
  {group: 'Maps', keys: ['↑', '↓', '←', '→'], what: 'Move between nodes'},
  {group: 'Maps', keys: ['Enter'], what: 'Go inside'},
  {group: 'Maps', keys: ['Shift', 'Enter'], what: 'Go out'},
  // the 2D map zooms by the wheel at any time, VIEW-041; 3 and Z turn auto zoom, web_node_zoom, on and off for both
  {group: 'Zoom', keys: ['3', 'Z'], what: 'Auto zoom on/off, both maps', match: ['3', 'z', 'Z'],
    run: () => toggleNodeZoom()},
  {group: 'Zoom', keys: ['4', '5', '6'], what: '3D zoom: 25%, 50%, 75%', match: ['4', '5', '6'], run: largeKey},
  {group: 'Zoom', keys: ['0'], what: '2D full fit, 3D zoom reset', match: ['0', 'Home'], run: largeKey},
  {group: 'Zoom', keys: ['F'], what: 'Fit once (3D)', match: ['f', 'F'],
    run: () => { if (G && !small3d()) { fit3d(); peek('key'); } }},
  {group: 'Zoom', keys: ['7', '8', '9'], what: '2D direction', match: ['7', '8', '9'], run: largeKey},
  {group: 'Looks', keys: ['L'], what: 'Layout: Organic or Flat', match: ['l', 'L'],
    run: () => choosePhysics(PHYS.name === 'flat' ? 'organic' : 'flat')},
  {group: 'Looks', keys: ['D'], what: 'Flow: hover, selection, all, then each with edges hidden', match: ['d', 'D'],
    run: () => stepFlow()},
  {group: 'Looks', keys: ['U'], what: 'Space theme on/off', match: ['u', 'U'],  // the space theme or the last plain one
    run: () => setTheme(document.documentElement.dataset.theme === 'space' ? PLAIN.last : 'space')},
  {group: 'Chat', keys: ['C'], what: 'Open or hide chat', match: ['c', 'C'], run: toggleChat},
  {group: 'Chat', keys: ['Enter'], what: 'Send'},
  {group: 'Chat', keys: ['Shift', 'Enter'], what: 'New line'},
  {group: 'Chat', keys: [MAC ? '⌘' : 'Ctrl', '.'], what: 'Interrupt the agent'},
  {group: 'Chat', keys: [MAC ? '⌥' : 'Ctrl', 'Space'], what: 'Talk'},
];
function toggleChat() {
  const open = $('#dock').className.startsWith('open') && !chatDocked() && !dockGoingAway();
  return open ? putChatAway() : dockState('open');
}
const KEY_RUN = new Map(KEYS.filter(entry => entry.run).flatMap(entry => entry.match.map(key => [key, entry])));
/* The reference, drawn from `KEYS`, centered over the page: its tabs, the everyday keys first, then the developer's,
 * then the looks and the zoom; each group a card of what a key does with its keys beside it; and a search that keeps
 * the keys whose words match, across every tab. A tab with no keys is not offered. */
const HELP_TABS = [['Shortcuts', ['Anywhere', 'Maps', 'Chat', 'Tools']], ['Dev keys', ['Developer']],
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
  // the toolbar's tools with a key, as the modules declare them and the workspace runs them, in the same reference
  const tools = WS.active ? WS.toolKeys().map(tool => ({group: 'Tools', keys: tool.shortcut.split('+'),
    what: `${tool.title}: ${tool.description}`})) : [];
  const all = [...KEYS, ...tools];
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
  touched();  // a map key holds an agent start's auto zoom off for a while, `TOUCHED`, VIEW-041
  // The keys of the key table, `KEYS`, each run by its entry, so the reference `?` opens says what each does.
  const entry = KEY_RUN.get(event.key);
  if (entry) { event.preventDefault(); entry.run(event.key); return; }
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
/* On the map the arrows walk the join tree: Down to the node drawn nearest under, Up back the way it came or to the
 * parent, Left and Right along the parent's row and on past its ends. */
function walkTree(event, here) {
  if (event.key === 'ArrowDown') {
    event.preventDefault();
    const next = below(here);
    if (next) { S.trail.push(here); select(next, true, true); }
  } else if (event.key === 'ArrowUp') {
    event.preventDefault();
    const parent = S.trail.length ? S.trail.pop() : parentOf(here);
    if (parent) select(parent, true, true);
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    event.preventDefault();
    const parent = S.trail.length ? S.trail[S.trail.length - 1] : parentOf(here);
    const row = parent ? childrenOf(parent) : roots();
    const at = row.indexOf(here), by = event.key === 'ArrowRight' ? 1 : -1;
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
