/* The ops since the drawn sequence applied to what is drawn, STORE-046, reads spaced while agents write, tickets and
 * agents changed, and the stream. */
import '/page/app/live/stream.js';  // the part before runs first, so the parts run in the page's order
import {$, h, writingInPanel} from '/page/app/core/dom.js';
import {toast} from '/page/app/core/controls.js';
import {S, MEM, FRAMED, read} from '/page/app/core/reads.js';
import {moduleNotices, readFailed} from '/page/app/core/errors.js';
import {askHealth, healthMayBeBack} from '/page/app/core/health.js';
import {withProviders, joinOf} from '/page/app/graph/data.js';
import {figures} from '/page/app/figures/agents.js';
import {mascotEvent} from '/page/app/figures/attention.js';
import {flowEvent, flowWritten} from '/page/app/flow/flow.js';
import {draw3D, markWork3d} from '/page/app/map3d/draw3d.js';
import {renderChips} from '/page/app/header/layers.js';
import {renderLegend} from '/page/app/views/lens.js';
import {build2DSoon, markWork2d} from '/page/app/map2d/build.js';
import {select, workPill, MERGE, renderMerges} from '/page/app/selection/select.js';
import {drawHelpdesk} from '/page/app/dock/helpdesk.js';
import {drawAgentList} from '/page/app/dock/threads.js';
import {Q, renderMessages} from '/page/app/board/messages.js';
import {B, unshown} from '/page/app/board/refs.js';
import {drawBoard, boardTickets} from '/page/app/board/board.js';
import {renderAgents} from '/page/app/agents/dispatch.js';
import {renderWork} from '/page/app/panel/object.js';
import {buildEvent} from '/page/app/build/build.js';
import {LIVE, following, recordingNow, changed} from '/page/app/live/stream.js';
import {progressOf, progressFrom} from '/page/app/loading/load.js';
import {debugAt, dlog, traced, loadWorkspace} from '/page/app/workspace/workspace.js';
import {banner} from '/page/app/core/banner.js';

/* The ops since the drawn sequence, applied to what is drawn, STORE-046 and VIEW-018: an element or a join added,
 * changed or removed, an item or a property of a layer in view. The map, the panel and the board are drawn from what
 * changed, not read again. A change to a layer's declaration or to a selection changes what is in view, and so does an
 * op of a layer the page cannot place; those fall back to the whole read. Returns whether the ops were applied. */
const plainWords = address => address.split('.').reverse().map(part => part.replace(/_/g, ' ')).join(' ');
const shortName = (address, length) => {
  const parts = address.split('.');
  return !length || length > parts.length ? plainWords(address) : plainWords(parts.slice(-length).join('.'));
};
function layerInView(layerId) {
  const layer = S.layers.find(item => item.id === layerId);
  if (!layer || !layer.ready) return null;
  if (layer.kind === 'base') return layer;
  const shown = S.view === null ? layer.on : S.view.has(layer.name);
  return shown ? layer : false;
}
/* An element's parent: the element that holds it, when the intake recorded it; otherwise the
 * nearest address it starts with. */
function holderOf(element, byAddress = addressesNow()) {
  if (element.within && byAddress.has(element.within)) return element.within;
  return nearestParent(element.address, byAddress);
}
/* The elements' ids by their addresses, made once for a batch of ops and not once for each element. */
function addressesNow() {
  const byAddress = new Map();
  for (const entry of S.elements.values()) byAddress.set(entry.element.address, entry.element.id);
  return byAddress;
}
function nearestParent(address, byAddress) {
  const parts = address.split('.');
  for (let n = parts.length - 1; n > 0; n--) {
    const prefix = parts.slice(0, n).join('.');
    if (byAddress.has(prefix)) return prefix;
  }
  return null;
}
function heldOf(ids) {
  return ids.map(id => {
    const entry = S.elements.get(id);
    const element = entry ? entry.element : {address: null, name_length: null, name: null, role: null};
    return {element_id: id, address: element.address, short_name: entry ? element.short_name : '',
      name_length: element.name_length, name: element.name, role: element.role};
  });
}
export async function appliedOps() {
  if (following() || !S.whole || typeof S.seq !== 'number') return false;
  const ops = await read('ops', {after: S.seq, limit: 0});
  if (!Array.isArray(ops) || !ops.length) return true;  // nothing of the map changed, so nothing is drawn
  if (ops.every(noted)) {  // what is said of a layer changed, not what is drawn: its record and its chip, no map read
    if (!ops.every(noteLayer)) return false;
    S.seq = ops[ops.length - 1].seq;
    renderChips();
    if ($('#p-prov').hidden === false) import('/page/app/panel/agentview.js').then(part => part.renderProv());
    return true;
  }
  let mine = false;  // whether an op concerns the selected node, whose panel is then drawn again
  for (const op of ops) {
    if (noted(op) && noteLayer(op)) continue;
    if (op.kind === 'layer' || op.kind === 'selection') return false;  // what is in view may have changed
    if (op.kind === 'type') continue;
    const layer = layerInView(op.layer_id);
    if (layer === null && op.op !== 'remove') return false;  // a layer this page has not read yet
    if (layer === false) continue;  // not in view: nothing to draw
    if (!applyOp(op, layer)) return false;
    mine ||= concernsSelected(op);
    if (op.kind === 'element' || op.kind === 'join') B.names++;  // the board's cards name their nodes
  }
  const byAddress = addressesNow();
  for (const entry of S.elements.values()) entry.parent = holderOf(entry.element, byAddress);
  S.whole = {elements: S.elements, joins: S.joins};
  S.seq = ops[ops.length - 1].seq;
  flowWritten(ops);  // what was written on a node lands there as a record, `FLOW`
  draw3D();
  renderLegend();
  await build2DSoon();
  // the Object tab is drawn again only for a change to its node, or when its node is gone; agents writing elsewhere
  // leave it as it is, so it neither flickers nor loses the person's place (2026-10-18)
  if (mine || !(S.selected && (S.elements.has(S.selected) || joinOf(S.selected)))) await reselect();
  return true;
}
/* Whether an applied op concerns the selected node: the element itself, the join selected, a join it receives or
 * holds, or an item or property on either. A removed item cannot be placed any more, so it is taken as concerning. */
function concernsSelected(op) {
  const id = S.selected;
  if (!id) return false;
  if (op.kind === 'element') return op.id === id;
  if (op.kind === 'join') {
    if ('p:' + op.id === id) return true;
    const join = S.joins.find(one => one.id === op.id);
    return Boolean(join) && (join.receiver === id || join.elements.some(one => one.element_id === id));
  }
  if (op.kind !== 'item' && op.kind !== 'property') return false;
  const item = S.items.get((op.kind === 'item' ? 'i:' : 'r:') + op.id)?.item;
  if (!item) return true;
  if (op.kind === 'property') return item.element_id === id;
  return Boolean(item.target) && (item.target.kind === 'join' ? 'p:' + item.target.id : item.target.id) === id;
}
/* A layer's tags and the pairs it holds for re-examination are what is said of the layer, shown on its chip and in its
 * provenance, never what the map draws from it, so a change to them alone reads no map again. */
const LAYER_NOTES = new Set(['tags', 'reexamine']);
const noted = op => op.kind === 'layer' && op.op === 'change' && Object.keys(op.data || {}).length > 0
  && Object.keys(op.data).every(key => LAYER_NOTES.has(key));
// the page's record of the layer takes the change; false when the page has not read that layer
function noteLayer(op) {
  const layer = S.layers.find(item => item.id === (op.layer_id ?? op.id));
  if (!layer) return false;
  Object.assign(layer, op.data);
  return true;
}
/* One op applied to what is drawn; false when the page cannot place it, and the whole map is read again. */
function applyOp(op, layer) {
  if (op.kind === 'element') return applyElement(op, layer);
  if (op.kind === 'join') { applyJoin(op, layer); return true; }
  if (op.kind === 'item' || op.kind === 'property') return applyItem(op, layer);
  return true;
}
/* The fields an op wrote, of those named; the others are kept as they were. */
const written = (data, names) => Object.fromEntries(names.filter(name => name in data).map(name => [name, data[name]]));
function applyElement(op, layer) {
  const data = op.data || {};
  if (op.op === 'remove') { S.elements.delete(op.id); return true; }
  const kept = S.elements.get(op.id)?.element || {};
  const element = {...kept, id: op.id, layer_id: op.layer_id, layer: layer.name,
    ...written(data, ['address', 'name', 'name_length', 'role', 'within', 'note'])};
  if (!element.address) return false;
  element.reading = plainWords(element.address);
  element.short_name = shortName(element.address, element.name_length);
  element.open_work = kept.open_work || [];
  S.elements.set(op.id, {element, parent: null});  // its parent is found with every other once the batch is in
  return true;
}
function applyJoin(op, layer) {
  const data = op.data || {};
  S.joins = S.joins.filter(join => join.id !== op.id);
  if (op.op === 'remove') return;
  const before = S.whole.joins.find(join => join.id === op.id) || {};
  const held = 'held' in data ? data.held : before.providers || [];
  const receiver = 'receiver' in data ? data.receiver : before.receiver;
  const join = {id: op.id, layer_id: op.layer_id, layer: layer.name, type: data.type ?? before.type ?? 'purpose',
    receiver, receiver_address: S.elements.get(receiver)?.element.address ?? null,
    purpose: 'purpose' in data ? data.purpose : before.purpose ?? null, ef: 'ef' in data ? data.ef : before.ef ?? null,
    ifd: 'ifd' in data ? data.ifd : before.ifd ?? null, elements: heldOf(held), open_work: before.open_work || [],
    element: 'element' in data ? data.element : before.element ?? null};
  S.joins.push(withProviders(join));
}
/* An item of a layer, or a property: an item needs its target to be drawn. */
function applyItem(op, layer) {
  const data = op.data || {};
  const key = (op.kind === 'item' ? 'i:' : 'r:') + op.id;
  if (op.op === 'remove') { S.items.delete(key); return true; }
  const kept = S.items.get(key)?.item || {};
  const value = 'value' in data ? JSON.parse(data.value) : kept.value;
  const refs = 'refs' in data ? data.refs.map(([k, v]) => ({key: k, value: v})) : kept.refs || [];
  const extra = 'extra' in data ? (data.extra ? JSON.parse(data.extra) : null) : kept.extra ?? null;
  const common = {...kept, id: op.id, layer_id: op.layer_id, layer: layer.name, value, refs, extra};
  const item = op.kind === 'item' ? itemOf(common, data, kept) : propertyOf(common, data, kept);
  if (op.kind === 'item' && !item.target) return false;
  S.items.set(key, {kind: op.kind, key, item, value, layer: layer.name, layerKind: layer.kind});
  return true;
}
const itemOf = (common, data, kept) => ({...common,
  target: 'target_kind' in data ? {kind: data.target_kind, id: data.target_id} : kept.target,
  link: 'link_kind' in data ? (data.link_kind ? {kind: data.link_kind, id: data.link_id} : null) : kept.link ?? null,
  read_first: 'read_first' in data ? !!data.read_first : !!kept.read_first,
  always_show: 'always_show' in data ? !!data.always_show : !!kept.always_show});
function propertyOf(common, data, kept) {
  const elementId = 'element_id' in data ? data.element_id : kept.element_id;
  return {...common, element_id: elementId, address: S.elements.get(elementId)?.element.address ?? null};
}
/* The selection kept when its node still stands; else the map's DE, or its first node, is selected in its place. */
async function reselect() {
  if (S.selected && (S.elements.has(S.selected) || joinOf(S.selected))) {
    if (writingInPanel()) return;  // the person is writing there: their words stay, the panel catches up after
    await select(S.selected, false, false, false, true);
  } else if (S.selected) {
    const start = [...S.elements.values()].find(entry => entry.element.role === 'DE')?.element.id
      || S.elements.keys().next().value;
    if (start) await select(start, false, false, false, true);
  }
}
/* Agents write several times a second. The whole map is read again at most once every SPACING, and nothing is drawn
 * while the person is zooming or dragging, so nothing moves under their hands; the changes in between are read
 * together. */
const QUIET = 800, SPACING = 3000;
const HANDS = {at: 0, down: false};
addEventListener('wheel', () => { HANDS.at = performance.now(); }, {passive: true, capture: true});
addEventListener('pointerdown', () => { HANDS.down = true; HANDS.at = performance.now(); }, true);
addEventListener('pointerup', () => { HANDS.down = false; HANDS.at = performance.now(); }, true);
export async function settled(after = LIVE.drawn + SPACING) {
  for (;;) {
    const now = performance.now();
    const wait = Math.max(HANDS.at + QUIET - now, after - now, HANDS.down ? QUIET : 0);
    if (wait <= 0) return;
    await new Promise(done => setTimeout(done, wait));
  }
}
/* The tables a ticket or a message is written in, as map.changed names them, VIEW-018, with the map module's numbers
 * of the items at an address and their titles and whys, MCP-037. A change to these alone adds or removes no node and
 * no link, so the map, its layers' items and its memories are not read again for it. */
const TICKET_TABLES = new Set(['work', 'work_links', 'work_steps', 'messages', 'map.glyphs', 'map.ticket_settings',
  'map.question_work', 'map.numbered', 'map.numbering']);
/* Whether a change can change a node's brief: what is numbered at an address, the memory, the work and the messages
 * counted in it, or the map itself, a change naming no tables or one of the map's own. An agent's thread does not. */
const BRIEF_TABLES = new Set(['work', 'work_links', 'work_steps', 'messages', 'map.numbered', 'map.numbering']);
export function briefTouched(named) {
  if (!Array.isArray(named)) return named !== 'dispatch';
  return named.some(table => BRIEF_TABLES.has(table) || /^(memory|jev)\./.test(table)
    || !TICKET_TABLES.has(table) && !/^(dispatch|web|workflow)\./.test(table));
}
export const ticketsOnly = payload => Array.isArray(payload.tables) && payload.tables.length > 0
  && payload.tables.every(table => TICKET_TABLES.has(table) || String(table).startsWith('dispatch.'));
/* A change the page can apply from the ops alone, STORE-046: the log, the objects registry, the kinds of op, and the
 * tickets' tables; a module's own table, such as the memory graph's, is read again whole. */
export const opsOnly = named => Array.isArray(named) && named.length > 0 && named.every(table => table === 'ops'
  || table === 'objects' || String(table).startsWith('op:') || TICKET_TABLES.has(table)
  || String(table).startsWith('dispatch.'));
/* What the changes heard since the last ticket read said of tickets and messages, gathered over the batch from each
 * change's own words, map.changed's work_ids and kinds: the tickets they named, whether one named none and so may
 * have changed any (`every`), and whether one may have changed a message. */
export const TICKETS = {named: new Set(), every: false, messages: false};
const MESSAGE_KINDS = ['message', 'question'];
const messageTable = table => table === 'messages' || table === 'map.question_work';
export function ticketsHeard(payload) {
  const ids = payload.work_ids;
  if (!Array.isArray(ids)) TICKETS.every = true;
  else for (let at = 0; at < ids.length; at++) TICKETS.named.add(ids[at]);
  const kinds = payload.kinds, tables = payload.tables;
  if (Array.isArray(kinds)) { if (holdsAny(kinds, MESSAGE_KINDS)) TICKETS.messages = true; }
  else if (!Array.isArray(tables) || tables.some(messageTable)) TICKETS.messages = true;
}
/* A whole read of the map took the tickets and the messages: what was gathered is spent. */
export function ticketsRead() { TICKETS.named.clear(); TICKETS.every = false; TICKETS.messages = false; }
/* The tickets a change named, read alone and put in S.tickets in place of what was held, a ticket gone taken out;
 * those that differ from what was held, as they were and as they are, so only their nodes are drawn again. */
async function namedTickets(ids) {
  const project = S.project, metaform = S.base, changed = [];
  let found = [];
  try { found = (await read('work', {ids: ids.join(','), limit: 0})).results || []; }
  catch (error) { readFailed(error); return changed; }
  if (S.project !== project || S.base !== metaform) return changed;
  for (const id of ids) {
    const now = found.find(one => one.id === id) || null, at = S.tickets.findIndex(one => one.id === id);
    const before = at < 0 ? null : S.tickets[at];
    if (JSON.stringify(now, unshown) === JSON.stringify(before, unshown)) continue;  // the same, but for its age
    if (before) changed.push(before);
    if (now) changed.push(now);
    if (now && at >= 0) S.tickets[at] = now;
    else if (now) S.tickets.push(now);  // a new ticket, last in row order as a whole read gives it
    else S.tickets.splice(at, 1);
  }
  return changed;
}
/* A change to tickets or messages alone: the tickets the changes named, or all of them when one named none, and the
 * open messages when a change may have changed one, each read once, and the nodes' lights, the figures, the board and
 * the selected node's panel drawn from them, VIEW-035 and VIEW-037. Tickets read as they were held draw nothing. */
export async function ticketsChanged() {
  const project = S.project, metaform = S.base;
  const every = TICKETS.every || !S.tickets, ids = every ? [] : [...TICKETS.named], messages = TICKETS.messages;
  ticketsRead();
  if (!every && !ids.length && !messages) return;
  // the whole read gives the progress; the tickets named, those that differ from what was held
  const [got] = await Promise.all([every ? progressOf() : ids.length ? namedTickets(ids) : [],
    messages ? renderMessages() : null]);
  if (S.project !== project || S.base !== metaform) return;
  if (!every && !got.length && !messages) return;
  S.progress = every ? got : progressFrom(S.tickets);
  // A change to tickets adds and removes no node and no edge: each map marks the nodes whose work changed where they
  // are drawn, and neither is drawn again, VIEW-018.
  const changed = openWork();
  // and those whose ticket's steps changed, which pace their light; every one when every ticket was read
  if (every) for (const id of S.elements.keys()) changed.add(id);
  else for (const ticket of got) changed.add(ticket.node_kind === 'join' ? joinOf('p:' + ticket.node_id)?.receiver
    : ticket.node_id);
  markWork3d(changed);
  markWork2d(changed);
  renderLegend();
  figures(S.tickets || []);
  boardFromTickets();
  drawAgentList();  // the full-size dock's rows say each ticket's steps
  if (every || messages || got.some(atSelected)) workInPanel();
}
export function boardFromTickets() {
  if ($('#board').hidden || !S.tickets) return;
  B.tickets = boardTickets(S.tickets);
  drawBoard();
}
/* Each node's open work as the map read gives it, MAP-050: the states its open records hold, in row order, then what
 * waits for the person there; rebuilt from the tickets and open messages read. A plain task adds nothing. */
function openWork() {
  const open = new Map(), add = (key, what) => open.set(key, [...(open.get(key) || []), what]);
  for (const ticket of S.tickets || []) {
    if (!ticket.done && ticket.condition) add(`${ticket.node_kind}:${ticket.node_id}`, ticket.condition);
  }
  for (const message of Q.open) add(`${message.node_kind}:${message.node_id}`, message.kind);
  // the elements whose open work as the maps show it changed: their own, or that of a join they receive
  const changed = new Set();
  for (const entry of S.elements.values()) {
    const now = open.get(`element:${entry.element.id}`) || [];
    if (!sameWork(entry.element.open_work, now)) changed.add(entry.element.id);
    entry.element.open_work = now;
  }
  for (const join of S.joins) {
    const now = open.get(`join:${join.id}`) || [];
    if (!sameWork(join.open_work, now)) changed.add(join.receiver);
    join.open_work = now;
  }
  return changed;
}
function sameWork(one, two) {
  if (!one || one.length !== two.length) return false;
  for (let at = 0; at < one.length; at++) if (one[at] !== two[at]) return false;
  return true;
}
/* Whether a ticket is in the selected node's Work box: on it, or, for an element, on a join it receives or holds,
 * as the box's read with joins gives it. */
function atSelected(ticket) {
  const id = S.selected;
  if (!id) return false;
  if (id.startsWith('p:')) return ticket.node_kind === 'join' && 'p:' + ticket.node_id === id;
  if (ticket.node_kind === 'element') return ticket.node_id === id;
  const join = joinOf('p:' + ticket.node_id);
  return !!join && (join.receiver === id || join.elements.some(one => one.element_id === id));
}
/* The selected node's open work pills and its Work box drawn again, the rest of its panel kept as it is. */
function workInPanel() {
  if (writingInPanel()) return;  // an issue being raised is never redrawn away
  const id = S.selected, join = id && !MEM.key && id.startsWith('p:') ? joinOf(id) : null;
  const element = id && !MEM.key && !join ? S.elements.get(id)?.element : null;
  const pane = $('#p-object');
  if (!(join || element) || !pane.querySelector(':scope > #work')) return;
  let pills = pane.querySelector(':scope > .pills');
  if (!pills && join) { pills = h('div', {class: 'pills'}); pane.querySelector(':scope > .join')?.before(pills); }
  if (pills) {
    for (const pill of pills.querySelectorAll('.pill[class*="work-"]')) pill.remove();
    const before = pills.querySelector('.pill.layer');
    for (const condition of (join || element).open_work || []) pills.insertBefore(workPill(condition), before);
  }
  renderWork(join ? `join:${join.id}` : `element:${id}`, id);
}
/* A line an agent wrote, or its session begun or ended: what it concerns is read again, at most once every BATCH and
 * never under the person's hands, once for however many lines came meanwhile. The agents key, the sessions read whole,
 * only for a change to a session, a signal, a permission or a question (`sessions`); the open chat only for a change
 * to its own ticket, or one that does not say whose (`works`, map.changed's work_ids). An agent streams about five
 * lines a second, and reading every session for each one kept the page, and the server, always reading. Only a change
 * that concerns merges, `whole` (`mergesConcerned`), reads the merges again, as does the stream opening again. */
const BATCH = 500;
const AGENTS = {busy: false, again: false, whole: false, sessions: false, everyone: false, works: new Set(), chat: false,
  at: -Infinity};
/* Whether no agents read is pending or running, for a check that must count reads a change of its own causes. */
export const agentsIdle = () => !AGENTS.busy && !AGENTS.sessions && !AGENTS.chat && !AGENTS.whole;
// a thread's own lines, the project's, and the signals beside the map, dispatch's THREAD_TABLES
const THREAD_TABLES = ['dispatch.session_lines', 'dispatch.lines'];
export const linesOnly = payload => payload.tables === 'dispatch' && Array.isArray(payload.dispatch_tables)
  && payload.dispatch_tables.length > 0 && payload.dispatch_tables.every(table => THREAD_TABLES.includes(table));
const SESSION_KINDS = ['session', 'signal', 'permission', 'question'];
/* Whether `kinds` holds one of `wanted`, walked by index, so an event allocates nothing. */
export function holdsAny(kinds, wanted) {
  for (let at = 0; at < kinds.length; at++) if (wanted.includes(kinds[at])) return true;
  return false;
}
/* Whether a change concerns the agents' sessions, from its kinds when it names them; one that does not, as a runner
 * older than map.changed's kinds says, may concern anything. */
export const sessionsConcerned = payload => !Array.isArray(payload.kinds) || holdsAny(payload.kinds, SESSION_KINDS);
/* Whether a change may have put a merge up for review or taken one down, as the server's merge_change decides it: it
 * names the merges table, its kinds name a merge, or it says neither its kinds nor its tables. A runner's session,
 * permission, spending and progress writes say they are not about merges. */
const MERGE_KINDS = ['merge'], MERGES = ['dispatch.merges'];
export function mergesConcerned(payload) {
  const kinds = Array.isArray(payload.kinds) ? payload.kinds : null;
  const tables = payload.tables === 'dispatch' ? payload.dispatch_tables : payload.tables;
  const named = Array.isArray(tables) && tables.length > 0 ? tables : null;
  if (kinds !== null && holdsAny(kinds, MERGE_KINDS) || named !== null && holdsAny(named, MERGES)) return true;
  return kinds === null && named === null;
}
export async function agentsChanged(whole = false, sessions = true, works = null) {
  if (whole) AGENTS.whole = true;
  if (sessions) {  // the tickets the changes named, gathered over the batch; one that names none reads every one
    AGENTS.sessions = true;
    if (works === null || !works.length) AGENTS.everyone = true;
    else for (let at = 0; at < works.length; at++) AGENTS.works.add(works[at]);
  }
  if (works === null || (MERGE.chat && works.includes(MERGE.chat))) AGENTS.chat = true;
  if (!AGENTS.sessions && !AGENTS.chat && !AGENTS.whole) return;
  if (AGENTS.busy) { AGENTS.again = true; return; }
  AGENTS.busy = true;
  try {
    do {
      await settled(AGENTS.at + BATCH);
      AGENTS.again = false;
      AGENTS.at = performance.now();
      if (AGENTS.whole) { AGENTS.whole = false; renderMerges(); }
      const agents = AGENTS.sessions, chat = AGENTS.chat, only = AGENTS.everyone ? null : [...AGENTS.works];
      AGENTS.sessions = false;
      AGENTS.everyone = false;
      AGENTS.works.clear();
      AGENTS.chat = false;
      await Promise.all([agents ? renderAgents(only) : null, chat && MERGE.chat ? drawHelpdesk() : null]);
    } while (AGENTS.again);
  } catch (error) { toast(error.message); } finally { AGENTS.busy = false; }
}
/* On every open of the stream the agents and the open agent window are also read again: a line written while the
 * stream was down, as when an agent restarts this server, was announced to no page, work 109ae725, and so was one
 * written between the load's read of the agents and the first open, as a runner dying then, work f7cd3522. */
let STREAM = null;
export function listen() {
  // the stream names the project this page shows: agents are started only for a project some page has open
  if (STREAM) STREAM.close();
  const source = STREAM = new EventSource(`/api/events?project=${encodeURIComponent(S.project || '')}`);
  let opens = 0;
  source.onmessage = heard;
  source.onerror = () => askHealth();  // the stream lost the server: the banner says whether it answers, and why not
  source.onopen = () => {
    healthMayBeBack();  // the first open, and the browser's own reconnect after the server was gone
    // with no project there is nothing being recorded here to read; an intake elsewhere is heard as it starts
    if (S.project) recordingNow().catch(error => toast(error.message));
    // what modules say needs the person, such as a phone number Twilio sends where nothing answers, core/errors.js
    if (S.project && !FRAMED) read('notices').then(found => moduleNotices(found.notices)).catch(readFailed);
    // the merges too on a reopen, since one may have been put up while the stream was down; the load read them first
    agentsChanged(opens > 0);
    // the browser's own reconnect, as after the server was restarted, VIEW-002: what changed while the stream was
    // down was announced to no page, so the layers and the map are read again, keeping the view and the selection
    if (opens++ && S.project) changed({topic: 'map.changed', payload: {project: S.project}});
    // and the parts outside the map that read the server once, such as voice.js's engine, read it again
    if (opens > 1) document.dispatchEvent(new CustomEvent('metaform:reconnected'));
  };
}
/* The topics the page takes apart from the map's changes. */
/* The code the server runs, said first on every stream, VIEW-002: the first is the code this page opened with. A later
 * one that differs means the server was updated while the page stayed open on the old code: the page says so, with
 * Reload, and reloads itself only when it is out of view, so nothing the person is doing is taken from them. */
const CODE = {opened: null, told: false};
function codeHeard(code) {
  if (!code) return;
  if (CODE.opened === null) { CODE.opened = code; return; }
  if (code === CODE.opened || CODE.told) return;
  CODE.told = true;
  if (document.hidden) { location.reload(); return; }
  banner('updated', {tone: 'info', title: 'Metaform was updated', closable: true,
    text: 'This page still runs the version it opened with. Reload to use the new one.',
    actions: [{label: 'Reload', primary: true, run: () => location.reload()}]});
  document.addEventListener('visibilitychange', () => { if (document.hidden) location.reload(); }, {once: true});
}
const TOPICS = {
  hello: payload => codeHeard(payload.code),  // the server's code, first on each stream, `CODE`
  build: payload => buildEvent(payload),  // the build panel's progress, BASE-060
  'map.flow': payload => flowEvent(payload),  // where agents' tool calls reached, `FLOW`
  mascot: payload => mascotEvent(payload),  // the system agent moves the mascot, `MASCOT`
  workspace: () => loadWorkspace(),  // arranged on another page, or in the settings
  // what a voice model's download has fetched, for its bar, page/voice.js
  'voice.download': payload => document.dispatchEvent(new CustomEvent('metaform:voice-download', {detail: payload})),
};
const HEARD = {count: 0};  // the stream's messages so far, for a check that waits for one it caused
export const heardCount = () => HEARD.count;
function heard(message) {
  HEARD.count++;
  const event = JSON.parse(message.data);
  if (Object.hasOwn(TOPICS, event.topic)) return TOPICS[event.topic](event.payload);
  if (debugAt('verbose')) {
    traced({kind: 'event', what: event.topic, raw: debugAt('trace') ? message.data : null});
    dlog('verbose', 'event', event);
  }
  changed(event);
}
