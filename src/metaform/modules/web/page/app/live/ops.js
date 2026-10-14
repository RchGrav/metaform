/* The ops since the drawn sequence applied to what is drawn, STORE-046, reads spaced while agents write, tickets and
 * agents changed, and the stream. */
import '/page/app/live/stream.js';  // the part before runs first, so the parts run in the page's order
import {$, h} from '/page/app/core/dom.js';
import {toast} from '/page/app/core/controls.js';
import {S, MEM, read} from '/page/app/core/reads.js';
import {withProviders, joinOf} from '/page/app/graph/data.js';
import {figures} from '/page/app/figures/agents.js';
import {mascotEvent} from '/page/app/figures/attention.js';
import {flowEvent, flowWritten} from '/page/app/flow/flow.js';
import {draw3D} from '/page/app/map3d/draw3d.js';
import {renderLegend} from '/page/app/views/lens.js';
import {build2D} from '/page/app/map2d/build.js';
import {select, workPill, MERGE, renderMerges} from '/page/app/selection/select.js';
import {drawHelpdesk} from '/page/app/dock/helpdesk.js';
import {Q, renderMessages} from '/page/app/board/messages.js';
import {B} from '/page/app/board/refs.js';
import {drawBoard} from '/page/app/board/board.js';
import {renderAgents} from '/page/app/agents/dispatch.js';
import {renderWork} from '/page/app/panel/object.js';
import {buildEvent} from '/page/app/build/build.js';
import {LIVE, following, recordingNow, changed} from '/page/app/live/stream.js';
import {progressOf} from '/page/app/loading/load.js';
import {debugAt, dlog, traced, loadWorkspace} from '/page/app/workspace/workspace.js';

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
function holderOf(element) {
  if (element.within && [...S.elements.values()].some(entry => entry.element.address === element.within)) {
    return element.within;
  }
  return nearestParent(element.address);
}
function nearestParent(address) {
  const parts = address.split('.');
  const byAddress = new Map([...S.elements.values()].map(entry => [entry.element.address, entry.element.id]));
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
  if (!Array.isArray(ops) || !ops.length) return true;  // nothing of the map changed: the tickets are read beside
  for (const op of ops) {
    if (op.kind === 'layer' || op.kind === 'selection') return false;  // what is in view may have changed
    if (op.kind === 'type') continue;
    const layer = layerInView(op.layer_id);
    if (layer === null && op.op !== 'remove') return false;  // a layer this page has not read yet
    if (layer === false) continue;  // not in view: nothing to draw
    if (!applyOp(op, layer)) return false;
  }
  for (const entry of S.elements.values()) entry.parent = holderOf(entry.element);
  S.whole = {elements: S.elements, joins: S.joins};
  S.seq = ops[ops.length - 1].seq;
  flowWritten(ops);  // what was written on a node lands there as a record, `FLOW`
  draw3D();
  renderLegend();
  await build2D();
  await reselect();
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
  S.elements.set(op.id, {element, parent: holderOf(element)});
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
/* A change to tickets or messages alone: work and the open messages are read once each, and the nodes' lights, the
 * figures, the board and the selected node's panel are drawn from them, VIEW-035 and VIEW-037. */
export async function ticketsChanged() {
  const project = S.project, metaform = S.base;
  const [progress] = await Promise.all([progressOf(), renderMessages()]);
  if (S.project !== project || S.base !== metaform) return;
  S.progress = progress;
  openWork();
  draw3D();
  renderLegend();
  figures(S.tickets || []);
  boardFromTickets();
  workInPanel();
  await build2D();
}
export function boardFromTickets() {
  if ($('#board').hidden || !S.tickets) return;
  B.tickets = S.tickets;
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
  for (const entry of S.elements.values()) entry.element.open_work = open.get(`element:${entry.element.id}`) || [];
  for (const join of S.joins) join.open_work = open.get(`join:${join.id}`) || [];
}
/* The selected node's open work pills and its Work box drawn again, the rest of its panel kept as it is. */
function workInPanel() {
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
/* A line an agent wrote, or its session begun or ended: the agents key, the open agent window and the open chat are
 * read again, at most once every BATCH and never under the person's hands, once for however many lines came
 * meanwhile. An agent streams about five lines a second, and drawing each one kept the page always reading and its
 * windows always redrawn. Only a change beyond the threads, `whole`, reads the merges and the advice again. */
const BATCH = 500;
const AGENTS = {busy: false, again: false, whole: false, at: -Infinity};
export const linesOnly = payload => payload.tables === 'dispatch' && Array.isArray(payload.dispatch_tables)
  && payload.dispatch_tables.length > 0 && payload.dispatch_tables.every(table => table === 'dispatch.lines');
export async function agentsChanged(whole = false) {
  if (whole) AGENTS.whole = true;
  if (AGENTS.busy) { AGENTS.again = true; return; }
  AGENTS.busy = true;
  try {
    do {
      await settled(AGENTS.at + BATCH);
      AGENTS.again = false;
      AGENTS.at = performance.now();
      if (AGENTS.whole) { AGENTS.whole = false; renderMerges(); }
      await Promise.all([renderAgents(), MERGE.chat ? drawHelpdesk() : null]);
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
  source.onmessage = heard;
  source.onopen = () => {
    recordingNow().catch(error => toast(error.message));
    agentsChanged();
  };
}
/* The topics the page takes apart from the map's changes. */
const TOPICS = {
  build: payload => buildEvent(payload),  // the build panel's progress, BASE-060
  'map.flow': payload => flowEvent(payload),  // where agents' tool calls reached, `FLOW`
  mascot: payload => mascotEvent(payload),  // the system agent moves the mascot, `MASCOT`
  workspace: () => loadWorkspace(),  // arranged on another page, or in the settings
};
function heard(message) {
  const event = JSON.parse(message.data);
  if (Object.hasOwn(TOPICS, event.topic)) return TOPICS[event.topic](event.payload);
  if (debugAt('verbose')) {
    traced({kind: 'event', what: event.topic, raw: debugAt('trace') ? message.data : null});
    dlog('verbose', 'event', event);
  }
  changed(event);
}
