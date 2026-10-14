/* Notes, VIEW-034, adding an element, VIEW-033, and the floating windows' wiring. */
import '/page/app/task/task.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {overlay} from '/page/app/core/overlays.js';
import {toast} from '/page/app/core/controls.js';
import {S, read} from '/page/app/core/reads.js';
import {shownOn, renderChips} from '/page/app/header/layers.js';
import {O} from '/page/app/memory/manage.js';
import {targetOf, calledOf} from '/page/app/board/messages.js';
import {when, F, wrote, movable} from '/page/app/board/history.js';
import {startAgent} from '/page/app/agents/dispatch.js';
import {named, discard} from '/page/app/task/task.js';
import {agentPicker, PICKERS} from '/page/app/agents/pickers.js';
import {loadGraph} from '/page/app/loading/load.js';

/* Notes, VIEW-034: one single note, not a list, of at most 2048 characters, edited in place.
 * One note at the node, kept by the memory module and read and written with
 * `memory note`, whatever layers are in view. Writing it replaces what it held, and writing it empty clears it. A note
 * asks for nothing: it is not a message, it does not glow, and it stays. */
const N = {node: null};
const NOTE_LIMIT = 2048;
export async function noteOf(id) { return (await read('memory-note', {node: targetOf(id)})).note; }
export function noteBy(note) {
  if (!note) return 'No note here yet.';
  return `Written by ${note.by === 'user' ? 'you' : note.by || 'an agent'}, ${when(note.at)}`;
}
function noteCount() { $('#notes .count').textContent = `${$('#notes textarea').value.length} / ${NOTE_LIMIT}`; }
export async function notesAt(id) {
  N.node = id;
  $('#notes .title').textContent = `Notes · ${calledOf(id)}`;
  let note = null;
  try { note = await noteOf(id); } catch (error) { toast(error.message); }
  if (N.node !== id) return;
  $('#notes .by').textContent = noteBy(note);
  $('#notes textarea').value = N.text = note ? note.text : '';
  noteCount();
  $('#notes').hidden = false;
}
$('#notes textarea').setAttribute('maxlength', String(NOTE_LIMIT));
$('#notes textarea').addEventListener('input', noteCount);
/* Save: a note of only spaces is written empty, which clears it. */
async function saveNote() {
  const text = $('#notes textarea').value.trim() ? $('#notes textarea').value : '';
  if (!await wrote('/api/note', {node: targetOf(N.node), text})) return;
  await notesAt(N.node);
}
$('#notes .save').onclick = saveNote;
$('#notes .close').onclick = () => { $('#notes').hidden = true; N.node = null; };
overlay($('#notes'), {kind: 'window', close: () => $('#notes .close').click(), focus: 'textarea',
  guard: () => $('#notes textarea').value === N.text || discard('the changes to this note', 'Keep editing')});
movable($('#notes'));
/* Adding an element, VIEW-033: a person gives it its address and joins it to the node the window was opened at. */
const E = {node: null, from: ''};
export function addElement(id) {
  const element = S.elements.get(id)?.element;
  if (!element) { toast('An element is added at an element.'); return; }
  E.node = id;
  $('#element .title').textContent = `Add Element · joined to ${named(element)}`;
  $('#element .receives option[value="node"]').textContent = `${named(element)}, and the new element serves it`;
  $('#element .receives option[value="new"]').textContent = `the new element, and ${named(element)} serves it`;
  for (const name of ['.purpose', '.ef', '.name']) $('#element ' + name).value = '';
  // It is written on from the address of the node: a part added beside a part mostly shares its trunk.
  E.from = element.address.includes('.') ? element.address.slice(0, element.address.lastIndexOf('.') + 1) : '';
  $('#element .address').value = E.from;
  fill($('#addresses'), [...S.elements.values()].map(entry => h('option', {value: entry.element.address + '.'})));
  if (!$('#element .pickhost').firstChild) {
    $('#element .pickhost').append(PICKERS.element ||= agentPicker({label: 'Agent', kept: true}));
  }
  $('#element').hidden = false;
  $('#element .address').focus();
}
/* Add: the element written with its address, joined to the node, and validated by an agent when that is asked; the
 * map is then read again with its layer in view. */
async function addWritten() {
  const written = $('#element .address').value.trim();
  const address = written === E.from || written.endsWith('.') ? '' : written;  // what it was started from is no address
  if (!address || S.elements.size && [...S.elements.values()].some(entry => entry.element.address === address)) {
    toast(address ? `There is an element at ${address} already.` : 'An element has an address.');
    return;
  }
  const given = elementGiven(address);
  const {response, body} = await postElement(given);
  if (!response.ok) { toast(body.error || 'The element was not written.'); return; }
  for (const notice of body.notices || []) toast(notice.message);
  $('#element').hidden = true;
  if (given.validate) await startAgent(body.work.id, PICKERS.element?.value());
  // What a person adds is shown: where the layers in view are chosen by name, the layer of what is added by hand
  // is put among them.
  S.layers = (await read('layers', {limit: 0})).results;
  const on = new Set(shownOn());
  if (!on.has(body.element.layer)) { on.add(body.element.layer); S.view = on; }
  renderChips();
  await loadGraph();
}
/* The element as the window gives it. */
function elementGiven(address) {
  return {address, node: `element:${E.node}`, receives: $('#element .receives').value,
    name_length: Number($('#element .length').value) || 1, name: $('#element .name').value.trim(),
    role: $('#element .role').value,
    purpose: $('#element .purpose').value.trim(), ef: $('#element .ef').value.trim(),
    validate: $('#element .validate').checked};
}
async function postElement(given) {
  const response = await fetch('/api/element', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({project: S.project, base: S.base, ...given})});
  const body = await response.json().catch(() => ({error: 'The server did not answer with JSON.'}));
  return {response, body};
}
$('#element .add').onclick = addWritten;
$('#element .close').onclick = () => { $('#element').hidden = true; };
/* Nothing is written yet when the fields are empty and the address is the one it started from. */
const elementUnwritten = () => !['.purpose', '.ef', '.name'].some(name => $('#element ' + name).value.trim())
  && [E.from, ''].includes($('#element .address').value.trim());
overlay($('#element'), {kind: 'dialog', close: () => $('#element .close').click(), focus: '.address',
  guard: () => elementUnwritten() || discard('this element', 'Keep writing')});
movable($('#element'));
movable($('#task'));
movable($('#float'));
function closeFloat() {
  $('#float').hidden = true;
  O.open = false;
  Object.assign(F, {id: null, which: null, ids: new Set(), drawn: new Map()});
}
$('#float .close').onclick = closeFloat;
overlay($('#float'), {kind: 'window', close: () => $('#float .close').click()});
