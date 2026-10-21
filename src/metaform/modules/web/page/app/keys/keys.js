/* Every key the page takes, in one table, the reference `?` opens, and the page's keydown handler. */
import '/page/app/keys/walk.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {S, MEM} from '/page/app/core/reads.js';
import {G, touched, pauseLayout, relayout, wake3d} from '/page/app/map3d/graph3d.js';
import {PLAIN, setTheme} from '/page/app/map3d/draw3d.js';
import {fit3d, swapMaps} from '/page/app/camera/flight.js';
import {small3d} from '/page/app/camera/fly3d.js';
import {peek, LENS, LENSES, LENS_WORDS} from '/page/app/views/settings.js';
import {chooseLens} from '/page/app/views/lens.js';
import {ROAM} from '/page/app/figures/agents.js';
import {stepFlow, PHYS, PHYSICS, choosePhysics} from '/page/app/views/bar.js';
import {M} from '/page/app/map2d/build.js';
import {entryOf} from '/page/app/map2d/fit.js';
import {IN} from '/page/app/map2d/inside.js';
import {MAC, resetZoom} from '/page/app/map2d/camera.js';
import {note2d} from '/page/app/map2d/hover.js';
import {deselect, step} from '/page/app/map2d/wire.js';
import {followNext, agentView} from '/page/app/figures/eyes.js';
import {BUBBLE_SIZES, stepBubbleSize} from '/page/app/figures/bubble3d.js';
import {across, below, besideDrawn, besideOnLevel, childrenOf, parentOf, roots, goInside, levelUp, mapKeys,
  zoomKey, stepDepth} from '/page/app/keys/walk.js';
import {select} from '/page/app/selection/select.js';
import {dockGoingAway, dockState} from '/page/app/dock/embody.js';
import {putChatAway} from '/page/app/dock/helpdesk.js';
import {toggleWork} from '/page/app/session/apps.js';
import {openSearch} from '/page/app/search/search.js';
import {chatDocked, WS} from '/page/app/workspace/workspace.js';
import {openRoundtable} from '/page/app/roundtable/stage.js';

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
  {group: 'Maps', keys: ['S'], what: 'Swap the two maps', match: ['s', 'S'], run: () => swapMaps()},
  // A follows an agent, and V sees the large 3D map through its eyes, `followNext` and `agentView` in figures/eyes.js
  {group: 'Agents', keys: ['A'], what: 'Follow an agent: none, then each on the map in turn', match: ['a', 'A'],
    run: () => followNext()},
  {group: 'Agents', keys: ['V'], what: "Your view or the followed agent's view", match: ['v', 'V'],
    run: () => agentView()},
  {group: 'Agents', keys: ['T'], what: 'Roundtable: agents debate your question',
    match: ['t', 'T'], run: () => openRoundtable()},
  // each digit cycles one setting, and each press says its new value at the 2D map's corner; the 2D map is fit-all,
  // zooming by the wheel at any time, VIEW-041, and onto a followed agent's node
  {group: 'Zoom', keys: ['1'], what: '3D camera: work in view, zoom 1/4, 1/2, 3/4', match: ['1'], run: zoomKey},
  {group: 'Zoom', keys: ['0'], what: 'Full fit, both maps', match: ['0', 'Home'], run: () => resetZoom()},
  {group: 'Zoom', keys: ['F'], what: 'Fit once (3D)', match: ['f', 'F'],
    run: () => { if (G && !small3d()) { fit3d(); peek('key'); } }},
  {group: 'Zoom', keys: ['5'], what: 'Speech bubble size: smallest, then larger in four steps',
    match: ['5'], run: () => note2d(`Bubble size: ${stepBubbleSize() + 1} of ${BUBBLE_SIZES.length}`)},
  {group: 'Zoom', keys: ['6'], what: 'Agent size: limited or let grow',
    match: ['6'], run: holdAgentSize},
  {group: 'Zoom', keys: ['7'], what: 'Lens: natural, wide, fisheye', match: ['7'], run: stepLens},
  {group: 'Looks', keys: ['2'], what: 'Flow: off, hover, selection, all, live, then each with edges hidden',
    match: ['2'], run: () => stepFlow()},
  {group: 'Looks', keys: ['3'], what: 'Layout: Organic or Flat', match: ['3'], run: stepLayout},
  {group: 'Looks', keys: ['4'], what: "Depth: the map's own levels, from the first with joins, or all", match: ['4'], run: () => stepDepth()},
  {group: 'Looks', keys: ['P'], what: 'Pause or resume the 3D layout', match: ['p', 'P'], run: () => pauseLayout()},
  {group: 'Looks', keys: ['R'], what: 'Re-run the 3D layout from new places', match: ['r', 'R'],
    run: () => relayout()},
  {group: 'Looks', keys: ['U'], what: 'Space theme on/off', match: ['u', 'U'],  // the space theme or the last plain one
    run: () => setTheme(document.documentElement.dataset.theme === 'space' ? PLAIN.last : 'space')},
  {group: 'Chat', keys: ['C'], what: 'Open or hide chat', match: ['c', 'C'], run: toggleChat},
  // the agent's tool calls and thinking in every thread, on this page until it is reloaded, `toggleWork`
  {group: 'Chat', keys: ['W'], what: "Show the agent's work", match: ['w', 'W'], run: () => toggleWork()},
  {group: 'Chat', keys: ['Enter'], what: 'Send'},
  {group: 'Chat', keys: ['Shift', 'Enter'], what: 'New line'},
  {group: 'Chat', keys: [MAC ? '⌘' : 'Ctrl', '.'], what: 'Interrupt the agent'},
  {group: 'Chat', keys: ['Esc'], what: 'Interrupt the agent, else clear the box (Ctrl+Z takes it back)'},
  {group: 'Chat', keys: ['↑', '↓'], what: 'In an empty box: your earlier messages in this thread'},
  {group: 'Chat', keys: ['Space'], what: 'Hold to talk to the agent; release sends'},
  {group: 'Chat', keys: [MAC ? '⌥' : 'Ctrl', 'Space'], what: 'Talk'},
];
/* 6: the agents' figures and the person's mascot held to their most pixels on the screen however near the camera
 * is, or let grow as near things do; kept in this browser. */
function holdAgentSize() {
  ROAM.held = !ROAM.held;
  try { localStorage.setItem('metaform.agentSizeFree', ROAM.held ? '0' : '1'); } catch { /* storage can be blocked */ }
  wake3d();
  note2d(ROAM.held ? 'Agent size: limited' : 'Agent size: not limited');
}
/* 7: the next lens, natural, wide and fisheye, kept in web_lens as the bar and the View menu keep it. */
function stepLens() {
  const names = Object.keys(LENSES), next = names[(names.indexOf(LENS.name) + 1) % names.length];
  chooseLens(next);
  note2d(`Lens: ${LENS_WORDS[next]}`);
}
function stepLayout() {
  const name = PHYS.name === 'flat' ? 'organic' : 'flat';
  choosePhysics(name);
  note2d(`Layout: ${PHYSICS.find(([one]) => one === name)[1]}`);
}
function toggleChat() {
  const open = $('#dock').className.startsWith('open') && !chatDocked() && !dockGoingAway();
  return open ? putChatAway() : dockState('open');
}
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
/* Translate LR arrows to TB tree actions: Up runs Right, Down runs Left, Left runs Up, Right runs Down.
 * History keys and the ordered walks inside a node or memory network are handled before this translation. */
const ACROSS_KEYS = {ArrowRight: 'ArrowDown', ArrowLeft: 'ArrowUp', ArrowUp: 'ArrowRight', ArrowDown: 'ArrowLeft'};
/* Walk the join tree through its logical actions: deeper, back along the trail or to the parent, or between siblings
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
