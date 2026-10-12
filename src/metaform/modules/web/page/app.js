/* Metaform's web GUI, the viewer: the whole map in 3D and in 2D, kept in sync, and the selected object below.
 * Every piece of data comes from the server's reads, VIEW-004; the page never decides what is visible. Text from the
 * store is always set as text, never as HTML, VIEW-009. */
'use strict';

// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
import ForceGraph3D from '3d-force-graph';
import {createAgent, drawGlyph, releaseGlyph, orientAgent, motionOf, strokeOf, reserveGlyph, eyeOf, GLYPHS, MOTION} from '/page/agents3d.js';
// drei's transmission material in its vanilla form, the glass itself, VIEW-025. It imports three.js as `three`, which
// the page's import map names as the same file, so both share one three.js.
import {MeshTransmissionMaterial} from '/vendor/drei-vanilla/MeshTransmissionMaterial.js';
import {RoundedBoxGeometry} from 'three/addons/geometries/RoundedBoxGeometry.js';
// the forces the 3D map's physics presets add, from the same library the graph runs, `applyPhysics`
import {forceX, forceY, forceZ, forceRadial} from 'd3-force-3d';
// The toolbar, the panes and their places, and the views the page draws only as panes.
import {createWorkspace} from '/page/workspace.js';
import {createViews} from '/page/views.js';
import {voiceAudio} from '/page/voice.js';  // speech to text in the boxes a person writes to agents in, the voice module
// Ultra graphics, web_graphics: the 3D map in outer space, drawn by its own module through the hooks marked ULTRA.
import * as ULTRA from '/page/ultra.js';

const $ = selector => document.querySelector(selector);
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const SVG = 'http://www.w3.org/2000/svg';

/* A DOM node from a tag, its properties and its children; strings become text nodes, never markup. */
function h(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'style') for (const [name, v] of Object.entries(value)) node.style.setProperty(name, v);
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? '' : value);
  }
  return put(node, children, false);
}
/* Fill a node with children: nested lists are flattened, empty ones dropped, strings kept as text. */
function put(node, children, replace = true) {
  const kids = [children].flat(Infinity).filter(child => child !== null && child !== undefined && child !== false)
    .map(child => child instanceof Node ? child : String(child));
  if (replace) node.replaceChildren(...kids); else node.append(...kids);
  return node;
}
const fill = (node, ...children) => put(node, children);
/* Fill a node with these children, leaving in place each one already there in its place, so a text being typed into
 * keeps its text, its cursor and the focus. */
function keepFill(node, kids) {
  for (const child of [...node.childNodes]) if (!kids.includes(child)) child.remove();
  kids.forEach((kid, index) => { if (node.childNodes[index] !== kid) node.insertBefore(kid, node.childNodes[index] || null); });
}
/* Fill a list from rows {key, text, make}: a row whose key and text are unchanged keeps its node, a changed one is made
 * again, a new one is added, so a thread that grows only appends and never flashes. Says whether anything changed. */
function keyedFill(node, rows) {
  const before = node.keyed || new Map(), now = new Map();
  let changed = rows.length !== before.size;
  for (const row of rows) {
    const had = before.get(row.key);
    if (had && had.text === row.text) now.set(row.key, had);
    else { changed = true; now.set(row.key, {text: row.text, node: row.make()}); }
  }
  node.keyed = now;
  keepFill(node, [...now.values()].map(one => one.node));
  return changed;
}

/* ---------- the page's controls: every window, menu and popover on one stack; confirmation and undo; toasts ----------
 * Each overlay is registered once with its kind, and opening or closing it is only showing or hiding it, wherever in
 * the page that is done: the stack follows the element's `hidden`. The overlay last opened is on top. Escape closes
 * the top one and nothing else; focus moves into an overlay as it opens, stays inside a modal one, and goes back to
 * the control that opened it as it closes. A popover or a menu also closes on a click outside it. While a menu, a
 * popover or a modal window is open, or the focus is in any overlay or a text field, the maps' keys rest, so a key
 * meant for a window never moves the map behind it.
 * The kinds: `menu` and `popover` float under their button and close on a click outside; `window` floats over the
 * map and stays while the person looks around it, VIEW-030; `dialog` is modal, with a backdrop, and the rest of the
 * page cannot be used until it closes; `dock` is the chat, which Escape closes only from inside it. */
const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]):not([type=hidden]),select:not([disabled]),'
  + 'textarea:not([disabled]),[contenteditable="true"],[tabindex]:not([tabindex="-1"])';
const OVERLAY = {stack: [], known: new Map(), base: 1000, closing: new Map(), trail: []};
/* The controls the person last reached, by the focus or by a press, so the one that opened an overlay is known even
 * when the overlay takes the focus at once or a browser does not focus a button pressed. */
function rememberReached(node) {
  const control = node instanceof Element ? node.closest(FOCUSABLE) : null;
  if (!control) return;
  OVERLAY.trail = [...OVERLAY.trail.filter(one => one !== control), control].slice(-8);
}
document.addEventListener('focusin', event => rememberReached(event.target), true);
document.addEventListener('pointerdown', event => rememberReached(event.target), true);
const shown = node => Boolean(node && node.isConnected && node.getClientRects().length && !node.closest('[hidden],[inert]'));
const focusables = box => [...box.querySelectorAll(FOCUSABLE)].filter(shown);
/* Register an element as an overlay. `close` hides it as its own close button does, `guard` may keep it open (it
 * returns false to keep it), `focus` names what takes the focus as it opens (a selector, a function, or false). */
function overlay(box, {kind = 'window', close = null, guard = null, focus = null} = {}) {
  OVERLAY.known.set(box, {box, kind, close, guard, focus});
  if (!box.hidden) opened(box);
  return box;
}
const overlayOf = box => OVERLAY.stack.find(entry => entry.box === box) || null;
const topOverlay = () => OVERLAY.stack.at(-1) || null;
/* Whether the maps' keys rest: an overlay that is not a window or the dock is open, or the focus is in one. */
function overlayHolds(target = document.activeElement) {
  if (OVERLAY.stack.some(entry => !['window', 'dock'].includes(entry.kind))) return true;
  return Boolean(target && OVERLAY.stack.some(entry => entry.box.contains(target)));
}
function opened(box) {
  const known = OVERLAY.known.get(box);
  if (!known) return;
  const active = document.activeElement;
  const had = overlayOf(box);
  OVERLAY.stack = OVERLAY.stack.filter(entry => entry.box !== box);
  const opener = had ? had.opener : active && active !== document.body && !box.contains(active) ? active
    : [...OVERLAY.trail].reverse().find(one => one.isConnected && !box.contains(one)) || null;
  OVERLAY.stack.push({...known, opener});
  if (box.classList.contains('window') && !had) place(box);
  $('#tip3d').hidden = true;  // a node's name shown under the pointer does not stay over what opens
  if (opener?.getAttribute?.('aria-controls') === box.id) opener.setAttribute('aria-expanded', 'true');
  restack();
  if (had || known.focus === false) return;
  requestAnimationFrame(() => {  // once it is drawn, so its controls can take the focus
    if (box.hidden || box.contains(document.activeElement)) return;
    const wanted = typeof known.focus === 'function' ? known.focus() : known.focus ? box.querySelector(known.focus) : null;
    if (wanted === false) return;
    const fields = focusables(box);
    const first = wanted || box.querySelector('[data-autofocus]')
      || (known.kind === 'menu' ? fields.find(one => one.matches('button,[role=menuitem]')) : null)
      || fields.find(one => one.matches('input:not([type=checkbox]):not([type=radio]),textarea,select,[contenteditable="true"]'))
      || fields.find(one => !one.classList.contains('close')) || fields[0];
    if (first) first.focus({preventScroll: true});
    else { if (!box.hasAttribute('tabindex')) box.setAttribute('tabindex', '-1'); box.focus({preventScroll: true}); }
  });
}
function closed(box) {
  const entry = overlayOf(box);
  if (!entry) return;
  OVERLAY.stack = OVERLAY.stack.filter(one => one !== entry);
  const opener = entry.opener;
  if (opener?.getAttribute?.('aria-controls') === box.id) opener.setAttribute('aria-expanded', 'false');
  restack();
  for (const hook of OVERLAY.closing.get(box) || []) hook();
  OVERLAY.closing.delete(box);
  // The focus goes back to the control that opened it, unless the person has put it somewhere else since.
  const active = document.activeElement;
  if (active && active !== document.body && !box.contains(active)) return;
  const back = shown(opener) ? opener : topOverlay() ? focusables(topOverlay().box)[0] || null : null;
  back?.focus({preventScroll: true});
}
/* Close an overlay as its own close button would, unless its guard keeps it. */
async function closeOverlay(entry) {
  if (!entry) return false;
  if (entry.guard && !(await entry.guard())) return false;
  if (entry.close) entry.close(); else entry.box.hidden = true;
  return true;
}
/* Run `hook` once when an open overlay next closes, however it closes. */
function onClosed(box, hook) { OVERLAY.closing.set(box, [...(OVERLAY.closing.get(box) || []), hook]); }
/* The stack's order is its stacking order, and a modal overlay makes everything under it inert behind a backdrop. */
const SCRIM = h('div', {id: 'scrim', hidden: true, 'aria-hidden': 'true'});
document.body.append(SCRIM);
function restack() {
  // the chat is stacked as its dock, which holds the tab and the chat in one layer of the page
  const dock = $('#dock');
  dock.style.zIndex = '';
  OVERLAY.stack.forEach((entry, index) => {
    (dock.contains(entry.box) ? dock : entry.box).style.zIndex = String(OVERLAY.base + index * 2 + 1);
  });
  const modal = OVERLAY.stack.findLastIndex(entry => entry.kind === 'dialog');
  SCRIM.hidden = modal < 0;
  if (modal >= 0) SCRIM.style.zIndex = String(OVERLAY.base + modal * 2);
  // what is under the top modal overlay cannot be used; what is open over it can
  OVERLAY.stack.forEach((entry, index) => { entry.box.inert = modal >= 0 && index < modal; });
  for (const [box] of OVERLAY.known) if (!overlayOf(box)) box.inert = false;
  $('.app').inert = modal >= 0;
  const docked = OVERLAY.stack.findIndex(entry => dock.contains(entry.box));
  dock.inert = modal >= 0 && docked < modal;
  $('#reviewNotice').inert = modal >= 0;
}
new MutationObserver(changes => {
  for (const change of changes) {
    const box = change.target;
    if (!OVERLAY.known.has(box)) continue;
    if (box.hidden) closed(box); else opened(box);
  }
}).observe(document.body, {attributes: true, attributeFilter: ['hidden'], subtree: true});
/* Escape closes the top overlay and only that one; the chat dock counts only while the focus is in it, so the chat
 * left open at the side never takes an Escape meant for the map. With none open it reaches the maps. A search box of
 * the prompt editor takes its own Escape. */
document.addEventListener('keydown', event => {
  if (event.key !== 'Escape' || event.isComposing || !OVERLAY.stack.length) return;
  if (event.target.closest?.('.CodeMirror-dialog')) return;
  const active = document.activeElement;
  const target = [...OVERLAY.stack].reverse().find(entry => entry.kind !== 'dock' || entry.box.contains(active));
  if (!target) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  closeOverlay(target);
}, true);
/* A click outside a menu or a popover closes it; its own button toggles it. Pressed outside, it closes before the
 * click acts, so the click reaches what it was meant for. */
document.addEventListener('pointerdown', event => {
  for (const entry of [...OVERLAY.stack].reverse()) {
    if (!['menu', 'popover'].includes(entry.kind)) continue;
    if (entry.box.contains(event.target)) break;  // a click inside the top popover leaves those under it as they are
    const toggle = entry.opener?.getAttribute?.('aria-controls') === entry.box.id ? entry.opener : null;
    if (toggle?.contains(event.target)) continue;
    if (event.target.closest?.('#toast')) continue;
    closeOverlay(entry);
  }
}, true);
/* Tab stays inside a modal overlay and the ones open over it. */
document.addEventListener('keydown', event => {
  if (event.key !== 'Tab') return;
  const modal = OVERLAY.stack.findLastIndex(entry => entry.kind === 'dialog');
  if (modal < 0) return;
  const open = OVERLAY.stack.slice(modal).map(entry => entry.box);
  const fields = open.flatMap(focusables);
  if (!fields.length) return;
  const at = fields.indexOf(document.activeElement);
  if (at < 0 || (event.shiftKey && at === 0) || (!event.shiftKey && at === fields.length - 1)) {
    event.preventDefault();
    fields[event.shiftKey ? (at <= 0 ? fields.length - 1 : at - 1) : (at < 0 || at === fields.length - 1 ? 0 : at + 1)].focus();
  }
});
/* A menu is walked with Up, Down, Home and End, as menus are; a field in it keeps its own keys. */
document.addEventListener('keydown', event => {
  const entry = topOverlay();
  if (!entry || entry.kind !== 'menu' || !entry.box.contains(document.activeElement)) return;
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key) || event.target.matches('input,select,textarea')) return;
  const items = focusables(entry.box).filter(one => one.matches('button,[role=menuitem]'));
  if (!items.length) return;
  event.preventDefault();
  const at = items.indexOf(document.activeElement);
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1
    : (at + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
  items[next].focus();
});
/* Where a window opens: where the person last put it, kept in this browser; otherwise a window read beside the map
 * stands just beside the side column, on the map's side, under the header, a step down from another one open there, and any other
 * window in the middle of the page. A dialog is placed by its styles. Every place is kept inside the window's view. */
const PLACES = 'metaform.places';
function places() { try { return JSON.parse(localStorage.getItem(PLACES) || '{}'); } catch { return {}; } }
function place(box) {
  if (box.classList.contains('dialog') || box.id === 'board' || matchMedia('(max-width: 820px)').matches) return;
  const kept = box.id ? places()[box.id] : null;
  const size = box.getBoundingClientRect(), head = $('header').getBoundingClientRect().bottom;
  let left, top;
  if (kept) [left, top] = [kept.left, kept.top];
  else if (box.classList.contains('beside')) {
    const others = OVERLAY.stack.filter(entry => entry.box !== box && entry.box.classList.contains('beside')).length;
    const column = $('aside').getBoundingClientRect();
    left = document.querySelector('.app').classList.contains('side-right')
      ? column.left - 24 - size.width - others * 28 : column.right + 24 + others * 28;
    top = head + 16 + others * 28;
  } else [left, top] = [(innerWidth - size.width) / 2, Math.max(head + 8, (innerHeight - size.height) / 2.4)];
  box.style.left = Math.round(Math.max(8, Math.min(left, innerWidth - Math.min(size.width, innerWidth - 16) - 8))) + 'px';
  box.style.top = Math.round(Math.max(8, Math.min(top, innerHeight - 48))) + 'px';
}
function keepPlace(box) {
  if (!box.id) return;
  const kept = places();
  kept[box.id] = {left: parseFloat(box.style.left) || 0, top: parseFloat(box.style.top) || 0};
  try { localStorage.setItem(PLACES, JSON.stringify(kept)); } catch { /* storage can be blocked; it opens in its usual place */ }
}

/* Toasts: what happened, said near the bottom, as long as it takes to read, and kept while it is pointed at or has
 * the focus. One that can be undone carries Undo. */
const TOAST = {timer: null, held: false, ms: 0};
function toast(message, {action = null, run = null, ms = null} = {}) {
  const box = $('#toast');
  fill(box, h('span', {class: 'msg'}, message),
    action ? h('button', {class: 'btn sm', type: 'button', onclick: async () => { box.hidden = true; await run(); }}, action) : null);
  box.hidden = false;
  TOAST.ms = ms ?? Math.min(12000, Math.max(action ? 8000 : 4200, 1800 + String(message).length * 45));
  toastLater(TOAST.ms);
}
function toastLater(ms) {
  clearTimeout(TOAST.timer);
  if (!TOAST.held) TOAST.timer = setTimeout(() => { $('#toast').hidden = true; }, ms);
}
for (const [kind, held] of [['pointerenter', true], ['pointerleave', false], ['focusin', true], ['focusout', false]]) {
  $('#toast').addEventListener(kind, () => { TOAST.held = held; held ? clearTimeout(TOAST.timer) : toastLater(2500); });
}
/* What was just done, with Undo: `undo` writes it back and says whether it could. */
function undoable(message, undo) {
  toast(message, {action: 'Undo', run: async () => { if (await undo()) toast('Undone.'); }});
}

/* The confirmation, the same everywhere a person is asked before something is taken away: what is asked, the one fact
 * that matters, what is lost and what stays, for an act that removes a project the word confirm typed, as the command
 * takes --confirm, and the two answers, the safe one first. It is a dialog of its own, or it fills `host`, a panel
 * the act belongs to, as clearing a project fills the panel under Administration, VIEW-019. It answers true for the
 * act and false for anything else, Escape and a click away among them. */
function confirmAct({title = 'Are you sure?', text = '', lost = [], kept = [], verb = 'Remove', cancel = 'Cancel',
  typed = false, danger = true, host = null}) {
  const box = host || $('#confirm');
  const into = host || $('#confirm .body');
  return new Promise(answer => {
    let done = false;
    const settle = value => { if (done) return; done = true; answer(value); };
    const field = typed ? h('input', {class: 'typed', type: 'text', placeholder: 'confirm', autocomplete: 'off', spellcheck: 'false',
      'aria-label': 'Type confirm to go on', 'data-autofocus': ''}) : null;
    const go = h('button', {class: `btn confirm ${danger ? 'danger solid' : 'primary'}`, type: 'button', disabled: typed,
      onclick: () => { settle(true); if (!host) box.hidden = true; }}, verb);
    const keep = h('button', {class: 'btn keep', type: 'button', 'data-autofocus': typed ? null : '',
      onclick: () => { settle(false); box.hidden = true; }}, cancel);
    if (field) {
      field.oninput = () => { go.disabled = field.value.trim().toLowerCase() !== 'confirm'; };
      field.onkeydown = event => { if (event.key === 'Enter' && !go.disabled) go.click(); };
    }
    const list = (heading, items, kind) => items.length ? [h('div', {class: 'heading'}, heading),
      h('ul', {class: kind}, items.map(item => h('li', {}, item)))] : null;
    fill(into, h('div', {class: `confirm${danger ? ' warn' : ''}`},
      h('h3', {class: 'ask', id: host ? null : 'confirmTitle'}, title),
      text ? [text].flat().map(line => h('p', {}, line)) : null,
      list('What is lost', lost, 'lost'), list('What stays', kept, 'kept'),
      field ? h('label', {class: 'gate'}, 'Type confirm to go on:', field) : null,
      h('div', {class: 'acts'}, keep, go)));
    box.hidden = false;
    onClosed(box, () => settle(false));
    if (host && field) setTimeout(() => field.focus(), 0);
  });
}

/* A segmented control: one choice of a few, as a row of buttons that act as radios, walked with the arrow keys.
 * options: [{value, label, title, disabled}]. */
function segmented({label, options, value, onchange}) {
  const group = h('div', {class: 'segmented', role: 'radiogroup', 'aria-label': label});
  const paint = chosen => {
    value = chosen;
    for (const button of group.children) {
      const on = button.dataset.value === String(chosen);
      button.setAttribute('aria-checked', String(on));
      button.tabIndex = on ? 0 : -1;
    }
  };
  for (const option of options) group.append(h('button', {type: 'button', role: 'radio', 'data-value': option.value,
    title: option.title, disabled: option.disabled, onclick: () => { if (String(value) !== String(option.value)) { paint(option.value); onchange?.(option.value); } }},
    option.label));
  group.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
    event.preventDefault();
    const buttons = [...group.children].filter(button => !button.disabled);
    const at = buttons.findIndex(button => button.dataset.value === String(value));
    const next = buttons[(at + (event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length];
    next.click(); next.focus();
  });
  paint(value);
  group.set = paint;
  return group;
}
/* A progress bar with how far along in words. `value` from 0 to 1, or null while it cannot be told. */
function progressBar({label, value = null, words = ''}) {
  const fillPart = h('div', {class: 'fill'}), said = h('span', {class: 'said'}, words), share = h('span', {class: 'share'});
  const bar = h('div', {class: 'progressbar', role: 'progressbar', 'aria-label': label, 'aria-valuemin': '0', 'aria-valuemax': '100'},
    h('div', {class: 'track'}, fillPart), h('div', {class: 'words'}, said, share));
  bar.set = (next, text = said.textContent) => {
    bar.classList.toggle('indeterminate', next === null);
    if (next === null) { bar.removeAttribute('aria-valuenow'); share.textContent = ''; }
    else {
      const percent = Math.round(Math.max(0, Math.min(1, next)) * 100);
      bar.style.setProperty('--value', String(percent / 100));
      bar.setAttribute('aria-valuenow', String(percent));
      share.textContent = `${percent}%`;
    }
    said.textContent = text;
    bar.setAttribute('aria-valuetext', [text, next === null ? '' : `${Math.round(next * 100)}%`].filter(Boolean).join(', '));
  };
  bar.set(value, words);
  return bar;
}
/* A text to copy, shown whole and read-only, with Copy beside it; the clipboard where the browser gives one, and the
 * text selected for a copy by hand where it does not. With `rows`, a text of many lines, shown in that many. */
function copyField({label, text, rows = 0}) {
  const field = rows ? h('textarea', {readonly: true, rows, 'aria-label': label, spellcheck: 'false', onfocus: event => event.target.select()})
    : h('input', {type: 'text', readonly: true, value: text, 'aria-label': label, onfocus: event => event.target.select()});
  if (rows) field.value = text;
  const copy = h('button', {class: rows ? 'btn' : 'btn icon', type: 'button', 'aria-label': `Copy ${label}`, title: 'Copy',
    onclick: async () => {
      try { await navigator.clipboard.writeText(field.value); toast('Copied.'); }
      catch { field.focus(); field.select(); toast('Press Ctrl+C or Cmd+C to copy it.'); }
    }}, h('i', {class: 'i i-copy', 'aria-hidden': 'true'}), rows ? 'Copy' : null);
  const box = h('div', {class: `copyfield${rows ? ' lines' : ''}`}, field, copy);
  box.set = value => { field.value = value; };
  return box;
}
/* A choice of one, each option with a badge saying whether it can be used here, such as an agent found on this
 * machine or not; an option that cannot be chosen says why. options: [{value, label, badge, ok, disabled, hint}].
 * It is a button that opens a list box, walked with the arrow keys, Home and End, and typed into to jump. The list
 * floats over the page from its button, below it or, where there is more room or the choice is `.up`, above it, so a
 * window's scrolling body never cuts it off; a scroll elsewhere or a resize closes it. */
function choice({label, options, value, onchange}) {
  const id = `choice${++choice.made}`;
  const shownLabel = h('span', {class: 'lbl'});
  const shownBadge = h('span');
  const button = h('button', {class: 'btn', type: 'button', 'aria-haspopup': 'listbox', 'aria-expanded': 'false',
    'aria-controls': id, 'aria-label': label}, h('span', {style: {display: 'flex', gap: '8px', 'align-items': 'center', 'min-width': '0'}},
    shownLabel, shownBadge), h('i', {class: 'i i-chev', 'aria-hidden': 'true'}));
  const list = h('div', {class: 'listbox', id, role: 'listbox', hidden: true, tabindex: '-1', 'aria-label': label});
  const box = h('div', {class: 'choice'}, button, list);
  let active = -1;
  const badge = option => option.badge ? h('span', {class: `badge ${option.ok === false ? 'off' : option.ok ? 'ok' : ''}`}, option.badge) : null;
  const paint = () => {
    const chosen = options.find(option => option.value === value) || options[0];
    shownLabel.textContent = chosen ? chosen.label : '';
    fill(shownBadge, chosen ? badge(chosen) : null);
    fill(list, options.map((option, index) => h('div', {role: 'option', id: `${id}-${index}`, 'data-value': option.value,
      'aria-selected': String(option.value === value), 'aria-disabled': option.disabled ? 'true' : null,
      class: index === active ? 'active' : null, onclick: () => pick(index), onpointermove: () => { active = index; mark(); }},
      h('span', {}, option.label), badge(option), option.hint ? h('small', {}, option.hint) : null)));
  };
  const mark = () => {
    [...list.children].forEach((row, index) => row.classList.toggle('active', index === active));
    if (active >= 0) { list.setAttribute('aria-activedescendant', `${id}-${active}`); list.children[active]?.scrollIntoView({block: 'nearest'}); }
  };
  const pick = index => {
    const option = options[index];
    if (!option || option.disabled) return;
    list.hidden = true;
    if (option.value !== value) { value = option.value; paint(); onchange?.(value); }
  };
  const float = () => {
    const at = button.getBoundingClientRect(), below = innerHeight - at.bottom - 12, above = at.top - 12;
    const up = box.classList.contains('up') ? above >= 140 || above > below : below < 180 && above > below;
    const width = Math.min(Math.max(at.width, 240), innerWidth - 16);
    Object.assign(list.style, {position: 'fixed', left: `${Math.max(8, Math.min(at.left, innerWidth - width - 8))}px`, width: `${width}px`,
      right: 'auto', top: up ? 'auto' : `${at.bottom + 4}px`, bottom: up ? `${innerHeight - at.top + 4}px` : 'auto',
      maxHeight: `${Math.max(120, Math.min(320, up ? above : below))}px`});
  };
  button.onclick = () => {
    if (!list.hidden) { list.hidden = true; return; }
    active = Math.max(0, options.findIndex(option => option.value === value));
    paint();
    document.body.append(list);
    float();
    list.hidden = false;
    choice.open.add(list);
    onClosed(list, () => { choice.open.delete(list); box.append(list); });
    mark();
  };
  list.addEventListener('keydown', event => {
    const usable = options.map((option, index) => option.disabled ? -1 : index).filter(index => index >= 0);
    const at = usable.indexOf(active);
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); active = usable[(at + (event.key === 'ArrowDown' ? 1 : -1) + usable.length) % usable.length]; mark(); }
    else if (event.key === 'Home' || event.key === 'End') { event.preventDefault(); active = event.key === 'Home' ? usable[0] : usable.at(-1); mark(); }
    else if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); pick(active); }
    else if (event.key.length === 1 && /\S/.test(event.key)) {
      const found = usable.find(index => options[index].label.toLowerCase().startsWith(event.key.toLowerCase()));
      if (found !== undefined) { active = found; mark(); }
    }
  });
  overlay(list, {kind: 'popover', focus: () => list});
  box.set = (nextOptions, nextValue = value) => { options = nextOptions; value = nextValue; paint(); };
  box.value = () => value;
  paint();
  return box;
}
choice.made = 0;
choice.open = new Set();
addEventListener('resize', () => { for (const list of choice.open) list.hidden = true; });
document.addEventListener('scroll', event => {
  for (const list of choice.open) if (!list.contains(event.target)) list.hidden = true;
}, true);

/* ---------- reads ---------- */
/* The page in an AI tool's frame, the MCP Apps map view, MCP-037: it shows the maps and the panel only, so the agents,
 * their merges and autostart, which it does not show, are not read. */
const FRAMED = document.documentElement.classList.contains('frame');
// In a frame, the view's bar the host's code adds to the page, #viewbar, stands in the frame's header slot, #viewslot.
if (FRAMED) {
  const adopt = () => { const bar = document.getElementById('viewbar'); if (bar && bar.parentElement !== $('#viewslot')) $('#viewslot').append(bar); };
  new MutationObserver(adopt).observe(document.body, {childList: true});
  adopt();
}
const S = {
  projects: [], project: null, bases: [], base: null, layers: [], view: null,
  elements: new Map(), joins: [], items: new Map(), selected: null, neighbors: new Set(), trail: [], history: [], at: -1, loading: 0, opening: 0, shown: false,
  cleared: false,  // the person let go of the selection, VIEW-008, so a map read again selects nothing in its place
  whole: null,  // the last map read whole, {elements, joins}, put back when a read of it fails
  memory: {entities: new Map(), relations: [], joins: [], at: new Map(), age: 0, orphaned: 0},  // LAYER-013
};
/* The memory network open in both views, VIEW-031: the node it belongs to, what is drawn of it, and what the map was
 * when it gave way, to go back to: the levels entered in 2D and where each node of the 3D map stood. */
const MEM = {key: null, network: null, drawn: false, levels: [], positions: null, generation: 0};

/* The server restarts to take new code, and for the second it takes, the browser can reach nothing: a read waits
 * through that and asks again, and a write, which may not be repeated safely, says so in words. */
const DOWN = 'The server was restarting and did not get that. Try again in a moment.';
async function reach(url, options, again = 10) {
  for (let tries = 0; ; tries++) {
    try { return await fetch(url, options); }
    catch (error) {
      if (tries >= again) throw new Error(DOWN);
      await new Promise(done => setTimeout(done, 1000));
    }
  }
}
async function read(name, params = {}) {
  const query = new URLSearchParams({project: S.project, ...(S.base ? {base: S.base} : {}), ...params});
  const response = await reach(`/api/${name}?${query}`, {headers: {Accept: 'application/json'}});
  const body = await response.json().catch(() => ({error: 'The server did not answer with JSON.'}));
  if (!response.ok) throw Object.assign(new Error(body.error || `${name} failed`), {status: response.status, body});
  return body;
}
const viewLayers = () => S.view === null ? {} : {layers: [...S.view].join(',')};

/* ---------- layers: color by position, the Layers checklist, apply ---------- */
const KNOWLEDGE = ['--k1', '--k2', '--k3', '--k4', '--k5', '--k6'];
function colorVar(layerName) {
  const layer = S.layers.find(item => item.name === layerName);
  if (!layer) return '--intake';
  if (layer.kind === 'base') return '--intake';  // the base layer, kind base, keeps the intake color
  if (layer.kind === 'memory') return '--memory';
  const knowledge = S.layers.filter(item => !['base', 'memory'].includes(item.kind));
  return KNOWLEDGE[knowledge.indexOf(layer) % KNOWLEDGE.length];
}
const layerColor = name => css(colorVar(name));
const folderOn = () => new Set(S.layers.filter(layer => layer.on).map(layer => layer.name));
const shownOn = () => S.view ?? folderOn();
const same = (a, b) => a.size === b.size && [...a].every(x => b.has(x));

/* The edges of the project, upstream entries, what the project depends on, and downstream entries,
 * who it serves, are records under those roots, not layers; the page lists each root beside the layers as a toggle
 * that hides every record under it, so the product's own parts stand alone. Remembered per viewer. */
const ROOTS = ['upstream', 'downstream'];
/* The side column's width and the split between its small map and its panes are dragged: each is
 * remembered by this browser, and a double-click puts it back. The maps follow the new size as they follow the window. */
const SIZES = {side: ['metaform.sideWidth', '--side-width', 320, () => innerWidth - 320],  // never narrower than a phone
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
    const end = () => { handle.classList.remove('dragging'); removeEventListener('pointermove', move); removeEventListener('pointerup', end); };
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
$('#sideSplit').addEventListener('pointerdown', () => {
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
}, true);
splitter($('#sideSplit'), 'side', moved => {
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
});
/* The side column goes on the left or the right of the page: its top bar, whichever map is in the small area, is
 * dragged across and the column follows the pointer once it reaches the other edge, `FLIP_SIDE`; a press that does not move is
 * an ordinary click. The View menu chooses the side too. The side is kept in this browser. */
const SIDE_AT = 'metaform.sideAt';
function sideAt(right, ease = false) {
  const app = document.querySelector('.app');
  $('#sideat').value = right ? 'right' : 'left';
  if (app.classList.contains('side-right') === right) return;
  // with `ease`, the column and the maps glide from where they stood to their new places, on the shared move curve
  const moving = ease && !reduced() ? [$('aside'), $('main')].filter(Boolean) : [];
  const before = moving.map(one => one.getBoundingClientRect().left);
  app.classList.toggle('side-right', right);
  try { localStorage.setItem(SIDE_AT, right ? 'right' : 'left'); } catch { /* storage can be blocked; it moves for now */ }
  moving.forEach((one, index) => {
    const by = before[index] - one.getBoundingClientRect().left;
    if (by) one.animate([{transform: `translateX(${by}px)`}, {transform: 'translateX(0)'}],
      {duration: durFor(Math.abs(by)), easing: `cubic-bezier(${EASE.move.join(',')})`});
  });
  dispatchEvent(new Event('resize'));
}
$('aside').addEventListener('pointerdown', event => {
  if (event.button !== 0 || !event.target.closest('aside .bar2d, aside .bar3d')
    || event.target.closest('button, input, select, textarea, a, nav') || matchMedia('(max-width: 820px)').matches) return;
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
});
$('#sideat').onchange = event => sideAt(event.target.value === 'right', true);
/* The reading column opens on the right, where the person reads without turning to the left; left only when chosen. */
sideAt((() => { try { return localStorage.getItem(SIDE_AT) !== 'left'; } catch { return true; } })());
splitter($('#smallSplit'), 'small', moved => moved.clientY - $('#small').getBoundingClientRect().top);
const rootsOff = () => { try { return new Set(JSON.parse(localStorage.getItem('metaform.rootsOff') || '[]')); } catch { return new Set(); } };
const rootOf = address => (address || '').split('.')[0];
const underHiddenRoot = address => rootsOff().has(rootOf(address));
/* The layers: a checklist opened from the header's Layers button, one row each, VIEW-007. The edges of the project,
 * upstream and downstream, are listed apart under their own heading, VIEW-046, since they are records and not layers
 * and the button counts layers only. */
function renderChips() {
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
    const input = h('input', {type: 'checkbox', 'data-layer': layer.name, disabled: !usable, onchange: () => {
      const next = new Set(shownOn());
      input.checked ? next.add(layer.name) : next.delete(layer.name);
      S.view = same(next, folderOn()) ? null : next;
      renderChips();
      loadGraph();
    }});
    input.checked = checked;
    const state = layer.hidden ? 'hidden' : !layer.ready ? 'building' : 'ready';
    box.append(h('label', {class: 'layerrow', style: {'--c': `var(${colorVar(layer.name)})`},
      title: layer.hidden ? 'Hidden: it stays out even when turned on.' : !layer.ready ? 'Still building.' : null},
      input, h('i'), h('span', {class: 'name'}, layer.name), ' ', h('span', {class: 'meta'}, [layer.kind, ...(layer.tags || []), state].join(' · '))));
  }
  box.append(h('div', {class: 'section'}, 'Edges of the project'));
  for (const root of ROOTS) {
    const input = h('input', {type: 'checkbox', 'data-root': root, onchange: () => {
      const next = rootsOff();
      input.checked ? next.delete(root) : next.add(root);
      try { localStorage.setItem('metaform.rootsOff', JSON.stringify([...next])); } catch (error) { /* storage can be blocked; the view still changes */ }
      renderChips();
      draw3D(); renderLegend(); build2D();
    }});
    input.checked = !off.has(root);
    box.append(h('label', {class: 'layerrow root', style: {'--c': 'var(--muted)'},
      title: root === 'upstream' ? 'What the project depends on: records under upstream.' : 'Who the project serves: records under downstream.'},
      input, h('i'), h('span', {class: 'name'}, root), ' ', h('span', {class: 'meta'}, 'root · records')));
  }
  $('#layersBtn .lbl').textContent = `Layers · ${count} of ${listed.length}`;
  $('#apply').disabled = S.view === null;
  const folder = S.projects.find(item => item.id === S.project)?.path || '';
  $('#note').textContent = S.view === null
    ? `Viewing only. These are the layers of ${folder}. What you toggle changes this view, not the folder, until you apply it.`
    : S.view.size === 0 ? 'No layer is chosen, which reads as every layer, as an empty --layers does.'
    : `This view differs from ${folder}. Apply to folder runs: metaform set --layers ${[...S.view].join(',')}`;
}

/* The header's menus and popovers, each on the overlay stack: its button opens and closes it, a click outside or
 * Escape closes it, and the focus goes back to its button. */
function toggler(button, box, open = () => {}) {
  button.addEventListener('click', async () => {
    if (!box.hidden) { box.hidden = true; return; }
    box.hidden = false;
    await open();
  });
}
function showLayers(open) { $('#layerlist').hidden = !open; }
overlay($('#layerlist'), {kind: 'popover', focus: () => $('#layerlist input:not(:disabled)')});
toggler($('#layersBtn'), $('#layerlist'));
overlay($('#settingsbox'), {kind: 'popover', focus: '#theme'});
toggler($('#settingsBtn'), $('#settingsbox'));
/* Where the header ends, `--head-bottom`, kept as the header changes height, as when it folds: the configuration
 * surfaces, the View panel and the settings screen, open at the window's right edge just below it, wherever the side
 * column, the maps or the workspace's panes stand. */
const headBottom = () => document.documentElement.style.setProperty('--head-bottom',
  `${Math.round($('header').getBoundingClientRect().bottom)}px`);
new ResizeObserver(headBottom).observe($('header'));
addEventListener('resize', headBottom);
headBottom();
$('#shortcutsBtn').onclick = () => openHelp();
overlay($('#help'), {kind: 'dialog', close: () => { $('#help').hidden = true; }});
$('#help .close').onclick = () => { $('#help').hidden = true; };
/* The page's text size, VIEW-023: chosen from the View menu's list or stepped with Alt and =, Alt and -, and Alt and 0
 * for the default. It steps every size token of the page, the type, the spacing and the heights of controls, through
 * --ui, so the header, the menus, the panel and the windows follow; the maps draw their own text and are not scaled.
 * There is no button for it in the header: a button that grows with the text it sizes moves out from under the mouse.
 * The size is kept in this browser and put back before the page draws, `theme.js`; it touches this page only. */
const TEXTSIZE = {steps: [0.84, 0.92, 1, 1.08, 1.17, 1.27, 1.38, 1.5], start: 3, key: 'metaform.textSize'};
function textStep() {
  const now = Number(getComputedStyle(document.documentElement).getPropertyValue('--ui')) || TEXTSIZE.steps[TEXTSIZE.start];
  return TEXTSIZE.steps.reduce((best, step, index) => Math.abs(step - now) < Math.abs(TEXTSIZE.steps[best] - now) ? index : best, 0);
}
function textSize(index) {
  const at = Math.max(0, Math.min(TEXTSIZE.steps.length - 1, index));
  document.documentElement.style.setProperty('--ui', String(TEXTSIZE.steps[at]));
  try { at === TEXTSIZE.start ? localStorage.removeItem(TEXTSIZE.key) : localStorage.setItem(TEXTSIZE.key, String(TEXTSIZE.steps[at])); }
  catch (error) { /* storage can be blocked; the size still changes */ }
  $('#textsize').value = String(at);
  dispatchEvent(new Event('resize'));  // the panes and the maps' areas changed size with it, and the header folds if it must
}
for (const [index, step] of TEXTSIZE.steps.entries()) {
  $('#textsize').append(h('option', {value: String(index)}, `${Math.round(step / TEXTSIZE.steps[TEXTSIZE.start] * 100)}%`
    + (index === TEXTSIZE.start ? ' (default)' : '')));
}
$('#textsize').onchange = event => textSize(Number(event.target.value));
// The text size is chosen in the View menu; no Alt shortcut, which the system takes on some machines.
textSize(textStep());
/* The header folds its rest behind the menu button below 1100 px, by the styles, and on a wider window whenever its
 * one row does not hold everything, as at a larger text size: it is measured unfolded, in the same frame, so nothing
 * flashes. */
function foldHeader() {
  const header = $('header');
  header.classList.remove('fold');
  if (innerWidth <= 1100) return;  // the styles fold it there
  header.classList.add('measure');  // each part at its own width, so a row too full shows as overflow
  const over = header.scrollWidth > header.clientWidth + 1;
  header.classList.remove('measure');
  header.classList.toggle('fold', over);
}
addEventListener('resize', foldHeader);
document.fonts?.ready.then(foldHeader);
/* Below 820 px the header's rest folds behind the menu button. */
$('#moreBtn').onclick = () => {
  const open = !$('header').classList.contains('expanded');
  $('header').classList.toggle('expanded', open);
  $('#moreBtn').setAttribute('aria-expanded', String(open));
};
/* The skip links take the focus to the large map or to the panel. */
for (const link of document.querySelectorAll('.skip')) link.addEventListener('click', event => {
  event.preventDefault();
  const to = link.dataset.skip === 'panel' ? $('#p-object') : largeView();
  to.focus();
});
const largeView = () => $('.app').classList.contains('swapped') ? $('#map2d') : $('#stage');
// The pointer leaving the 3D map takes the name it showed there with it.
$('#stage').addEventListener('pointerleave', () => { $('#tip3d').hidden = true; });

/* ---------- clearing the project: what goes and what stays, asked on the page, VIEW-019 ----------
 * The warning is the command's own caution and the clear is the command's own operation, PROJ-025; every open page,
 * this one among them, follows it by the push, VIEW-018. */
/* The Administration menu, VIEW-019: acts on the project as a whole, reached on purpose; what reads first, then what
 * changes something, and what removes something last and in the danger color. */
// The Window menu and its Workspaces submenu, drawn by the workspace, workspace.js; Left closes the submenu.
overlay($('#windowbox'), {kind: 'menu'});
toggler($('#windowBtn'), $('#windowbox'));
overlay($('#wsworkspaces'), {kind: 'menu'});
$('#wsworkspaces').addEventListener('keydown', event => {
  if (event.key !== 'ArrowLeft') return;
  event.preventDefault();
  $('#wsworkspaces').hidden = true;
  $('#workspacesBtn')?.focus();
});
function showAdmin(open) { $('#adminbox').hidden = !open; }
overlay($('#adminbox'), {kind: 'menu'});
toggler($('#adminBtn'), $('#adminbox'), async () => {
  try { $('#restoreBtn').disabled = !(await getJson(`/api/backups?project=${encodeURIComponent(S.project)}`)).results.length; }
  catch (error) { $('#restoreBtn').disabled = true; }
});
/* The panel under Administration that its acts open in: a clear's warning, the backups, the ignore list. */
function showClear(open) { $('#clearbox').hidden = !open; }
overlay($('#clearbox'), {kind: 'popover'});
/* A backup restored: the project's own backup of what it held is made first, so the restore is undone by restoring
 * that one. */
async function restoreFrom(project, backup) {
  const response = await fetch('/api/restore', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({project, backup})});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) { toast(body.error || 'The backup was not restored.'); return false; }
  fill($('#clearbox'), h('div', {class: 'sheet'}, h('p', {class: 'restored'}, body.said),
    body.held_before ? h('p', {class: 'next'}, `What the project held was backed up as ${body.held_before}.`) : null,
    h('div', {class: 'acts'}, h('button', {class: 'btn keep', type: 'button', onclick: () => showClear(false)}, 'Close'))));
  if (body.held_before) undoable(`Restored ${project} from ${backup}.`, () => restoreFrom(project, body.held_before));
  return true;
}
/* A backup's name is the time it was made, 20261010T112014Z, said as a person reads a time: the day and the hour
 * here, and how long ago. */
function backupTime(name) {
  const found = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z/.exec(name || '');
  if (!found) return null;
  const [, year, month, day, hour, minute, second] = found.map(Number);
  const at = new Date(Date.UTC(year, month - 1, day, hour, minute, second));
  const days = Math.round((new Date().setHours(0, 0, 0, 0) - new Date(at).setHours(0, 0, 0, 0)) / 86400000);
  const date = days === 0 ? 'Today' : days === 1 ? 'Yesterday' : at.toLocaleDateString([], {day: 'numeric', month: 'short', year: 'numeric'});
  const seconds = Math.max(0, (Date.now() - at) / 1000);
  const ago = seconds < 60 ? 'just now' : seconds < 3600 ? `${Math.floor(seconds / 60)} min ago`
    : seconds < 86400 ? `${Math.floor(seconds / 3600)} h ago` : `${Math.floor(seconds / 86400)} days ago`;
  return `${date} ${at.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})} · ${ago}`;
}
$('#restoreBtn').onclick = async () => {
  showAdmin(false);
  let found;
  try { found = (await getJson(`/api/backups?project=${encodeURIComponent(S.project)}`)).results; }
  catch (error) { return toast(error.message); }
  fill($('#clearbox'), h('div', {class: 'sheet'}, h('h3', {}, `Restore ${S.project} from a backup`),
    h('p', {}, 'What the project holds now is backed up first, so a restore can be undone.'),
    h('ul', {class: 'backups'}, [...found].sort((one, two) => two.name.localeCompare(one.name)).map(kept => h('li', {},
      h('span', {class: 'name', title: kept.name}, kept.name), h('span', {class: 'when'}, backupTime(kept.name) || kept.name),
      h('span', {class: 'held'}, kept.held),
      h('button', {class: 'btn sm', type: 'button', onclick: () => restoreFrom(S.project, kept.name)}, 'Restore')))),
    h('div', {class: 'acts'}, h('button', {class: 'btn keep', type: 'button', onclick: () => showClear(false)}, 'Close'))));
  showClear(true);
};
/* The export menu saves the map as a document the command writes: Markdown, MAP-052, or XML, MAP-059; VIEW-024. */
function showExport(open) { $('#exportbox').hidden = !open; }
overlay($('#exportbox'), {kind: 'menu'});
toggler($('#exportBtn'), $('#exportbox'));
async function exportAs(format, extension, type) {
  showExport(false);
  const query = new URLSearchParams({project: S.project, ...(S.base ? {base: S.base} : {}), ...viewLayers()});
  const response = await fetch(`/api/${format}?${query}`);
  if (!response.ok) return toast((await response.json().catch(() => ({}))).error || 'The map could not be exported.');
  const link = h('a', {href: URL.createObjectURL(new Blob([await response.text()], {type})),
    download: `${S.project}-map.${extension}`});
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}
$('#exportMarkdown').onclick = () => exportAs('markdown', 'md', 'text/markdown');
/* The 2D map as a Mermaid flowchart, P063: the writer `metaform map mermaid` uses, given the layers and metaform the
 * page shows, the way its 2D map runs and the roots it leaves out, so the diagram holds the elements and joins drawn
 * here, each join pointing the way its information goes as the 2D map's arrowheads do, and asks for the 2D map's
 * layout, ELK by network simplex, ELK2D, in its frontmatter. With an address, that node and those one join away. A
 * diagram too long for Mermaid's default limits is said, since GitHub or mermaid.live would draw nothing of it. */
async function mermaidText(given = {}) {
  const query = new URLSearchParams({project: S.project, ...(S.base ? {base: S.base} : {}), ...viewLayers(),
    direction: M.base && !M.base.vertical ? 'LR' : 'TB', leave_out: [...rootsOff()].join(','), ...given});
  const response = await reach(`/api/mermaid?${query}`, {});
  const text = await response.text();
  if (!response.ok) throw new Error((() => { try { return JSON.parse(text).error; } catch { return ''; } })() || 'The map could not be written as Mermaid.');
  const notice = response.headers.get('X-Metaform-Notice');
  if (notice) setTimeout(() => toast(notice), 1200);  // after the toast saying it was saved or copied
  return text;
}
$('#exportMermaid').onclick = async () => {
  showExport(false);
  let text;
  try { text = await mermaidText(); } catch (error) { return toast(error.message); }
  const link = h('a', {href: URL.createObjectURL(new Blob([text], {type: 'text/plain'})), download: `${S.project}-map.mmd`});
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
};
$('#copyMermaid').onclick = async () => {
  showExport(false);
  try { await navigator.clipboard.writeText(await mermaidText()); toast('The map is copied as Mermaid.'); }
  catch (error) { toast(error.message || 'The browser did not let the page copy it.'); }
};
$('#exportXml').onclick = () => exportAs('xml', 'xml', 'application/xml');
/* The intake's ignore list, .metaform/ignore.txt: what is not the project, said by the person up front, so the
 * intake never reads it and never judges it. */
$('#ignoreBtn').onclick = async () => {
  showAdmin(false);
  let found;
  try { found = await read('ignore'); } catch (error) { return toast(error.message); }
  const text = h('textarea', {class: 'ignore', rows: 8, spellcheck: 'false', 'data-autofocus': '',
    'aria-label': 'Intake ignores (one pattern per line, like .gitignore)'});
  text.value = found.text || '';
  fill($('#clearbox'), h('div', {class: 'sheet'}, h('h3', {}, 'Intake ignores'),
    h('p', {}, `One pattern per line, like .gitignore. Kept in ${found.file}; the intake never reads what these name.`), text,
    h('div', {class: 'acts'}, h('button', {class: 'btn keep', type: 'button', onclick: () => showClear(false)}, 'Cancel'),
      h('button', {class: 'btn primary', type: 'button', onclick: async () => {
        if (await wrote('/api/ignore', {text: text.value})) { toast('Ignore list saved.'); showClear(false); }
      }}, 'Save'))));
  showClear(true);
};
$('#clearBtn').onclick = async () => {
  showAdmin(false);
  let found;
  try { found = await getJson(`/api/clear-preview?project=${encodeURIComponent(S.project)}`); }
  catch (error) { return toast(error.message); }
  if (await confirmAct({title: 'Are you sure?', text: [found.caution, 'It is backed up first.'], verb: 'Clear it',
    cancel: 'Keep it', typed: true, host: $('#clearbox')})) clearProject(found.project);
};
async function clearProject(project) {
  const response = await fetch('/api/clear-project', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({project, confirm: true})});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) { showClear(false); return toast(body.error || 'The project was not cleared.'); }
  const left = body.not_removed || [];
  fill($('#clearbox'), h('div', {class: 'sheet'}, h('p', {class: 'said'}, body.said),
    body.backup ? h('p', {class: 'backed'}, `Backed up as ${body.backup}.`) : null,
    left.length ? [h('b', {}, 'Not removed, still on disk:'),
      h('ul', {class: 'left'}, left.map(item => h('li', {}, `${item.path}: ${item.reason}`)))] : null,
    (body.notices || []).map(notice => h('p', {class: 'next'}, notice.message)),
    h('div', {class: 'acts'}, h('button', {class: 'btn keep', type: 'button', onclick: () => showClear(false)}, 'Close'))));
}
/* Remove project takes an empty project off the list, PROJ-031: one that still holds metaforms or reports is named
   with what it holds, since a clear backs it up first. */
$('#removeBtn').onclick = async () => {
  showAdmin(false);
  let found;
  try { found = await getJson(`/api/remove-preview?project=${encodeURIComponent(S.project)}`); }
  catch (error) { return toast(error.message); }
  if (found.held) {
    fill($('#clearbox'), h('div', {class: 'sheet'}, h('p', {class: 'held'}, found.held), h('p', {class: 'next'}, 'Use Clear project first.'),
      h('div', {class: 'acts'}, h('button', {class: 'btn keep', type: 'button', onclick: () => showClear(false)}, 'Close'))));
    return showClear(true);
  }
  if (await confirmAct({title: 'Are you sure?', text: found.caution, verb: 'Remove it', cancel: 'Keep it', typed: true,
    host: $('#clearbox')})) removeProject(found.project);
};
async function removeProject(project) {
  const response = await fetch('/api/remove-project', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({project, confirm: true})});
  const body = await response.json().catch(() => ({}));
  showClear(false);
  if (!response.ok) return toast(body.error || 'The project was not removed.');
  toast(body.said);
  S.projects = ((await getJson('/api/projects')).projects || []);
  if (!S.projects.length) return location.reload();
  toProject(S.projects[0].id);
  fill($('#proj'), ...S.projects.map(item => h('option', {value: item.id, selected: item.id === S.project}, item.id)));
  await loadProject();
}
/* After a clear the project has no metaform until the next intake, or anything else written to it, makes one. */
const noMetaform = () => !S.bases.length;
const noneYet = () => `${S.project} has no metaform yet. The next intake creates one.`;
/* The panel of a project with no map: what it is, and the intake, which makes one, as the thing to do. */
function emptyPanel() {
  const box = h('div', {class: 'emptypanel'}, h('p', {class: 'empty'}, noMetaform() ? noneYet() : 'Nothing to show in these layers yet.'),
    h('div', {class: 'acts'}));
  emptyActs(box);
  return box;
}
/* Its act: Start the intake, or while one runs, its chat. */
function emptyActs(box) {
  const running = intakeRunning();
  fill(box.querySelector('.acts'), S.elements.size ? null : running
    ? h('button', {class: 'btn', type: 'button', onclick: () => openIntakeChat()}, 'The intake is running · open its chat')
    : h('button', {class: 'btn primary', type: 'button', onclick: () => openIntake()},
      h('i', {class: 'i i-spark', 'aria-hidden': 'true'}), 'Start the intake'));
}
$('#apply').onclick = async () => {
  if (S.view === null) return;
  const response = await fetch('/api/apply-layers', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({project: S.project, layers: [...S.view]})});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) return toast(body.error || 'The folder was not changed.');
  S.view = null;
  S.layers = (await read('layers', {limit: 0})).results;
  renderChips();
  toast(['Applied to the folder.', ...(body.notices || []).map(notice => notice.message)].join(' '));
};

/* ---------- the graph data ---------- */
/* The graph as the approved prototype draws it: each join uncollapsed as its receiver, a purpose vertex and the
 * encounter, a link on to each element the join holds; the namespace joins each element to
 * its nearest parent element, VIEW-005. */
function graphData() {
  const nodes = [], links = [];
  const byAddress = new Map([...S.elements.values()].map(entry => [entry.element.address, entry.element.id]));
  for (const {element, parent} of S.elements.values()) {
    if (underHiddenRoot(element.address)) continue;  // an edge of the project the viewer turned off
    nodes.push({id: element.id, t: 'el', name: labelOf(element), address: element.address,
      role: element.role, work: element.open_work || [], layer: element.layer});
    if (parent && byAddress.has(parent)) links.push({source: byAddress.get(parent), target: element.id, k: 'tree'});
  }
  const ids = new Set(nodes.map(node => node.id));
  for (const join of S.joins) {
    const drawnTo = join.providers.filter(id => ids.has(id));
    if (!ids.has(join.receiver) || !drawnTo.length) continue;
    const purpose = 'p:' + join.id;
    nodes.push({id: purpose, t: 'purpose', join: join.id, layer: join.layer, work: join.open_work || []});
    links.push({source: join.receiver, target: purpose, k: 'purpose', layer: join.layer, join: join.id,
      work: join.open_work || []});
    for (const provider of drawnTo)
      links.push({source: purpose, target: provider, k: 'encounter', layer: join.layer, join: join.id,
        work: join.open_work || []});
  }
  // Every item and property of the layers turned on is its own node, hung from its node; a link runs on, VIEW-017.
  const drawnIds = new Set(nodes.map(node => node.id));
  const at = thing => thing.kind === 'property' ? thing.item.element_id : keyOf(thing.item.target);
  // The sources layer's refs are shown in the panel and never hung on the map, the map is the design.
  const hung = [...S.items.values()].filter(thing => drawnIds.has(at(thing)) && thing.layer !== 'sources');
  for (const thing of hung) {
    nodes.push({id: thing.key, t: 'item', layer: thing.layer, text: itemText(thing.value)});
    drawnIds.add(thing.key);
  }
  for (const thing of hung) {
    links.push({source: at(thing), target: thing.key, k: 'item', layer: thing.layer});
    const to = keyOf(thing.item.link);
    if (to && drawnIds.has(to)) links.push({source: thing.key, target: to, k: 'relation', layer: thing.layer});
  }
  // Every memory shown at a node is its own node, hung from each node it is kept at, and each relation between two
  // memories drawn is a link, LAYER-013 and VIEW-017.
  const memory = memoryLayer();
  for (const [key, names] of S.memory.at) {
    if (!drawnIds.has(key)) continue;
    for (const name of names) {
      if (!drawnIds.has(memoryKey(name))) {
        nodes.push({id: memoryKey(name), t: 'item', layer: memory, text: name});
        drawnIds.add(memoryKey(name));
      }
      links.push({source: key, target: memoryKey(name), k: 'item', layer: memory});
    }
  }
  for (const relation of S.memory.relations) if (drawnIds.has(memoryKey(relation.from)) && drawnIds.has(memoryKey(relation.to)))
    links.push({source: memoryKey(relation.from), target: memoryKey(relation.to), k: 'relation', layer: memory,
      relation: relation.relationType});
  return {nodes, links};
}
/* A selection is an element's id or a join as 'p:<id>', the same keys the 3D view uses. */
/* A join as the metaform's shape holds it, D115: `providers` are the ids of every element it holds, each a provider;
 * `provider` and `provider_address` name the first, the one that names the join beside its receiver. */
const withProviders = join => ({...join, providers: (join.elements || []).map(each => each.element_id),
  provider: join.elements?.[0]?.element_id, provider_address: join.elements?.[0]?.address});
const accessed = (value, item) => typeof value === 'function' ? value(item) : value;
const joinOf = key => S.joins.find(join => 'p:' + join.id === key);
/* The Address a selection stands for: an element's own, or for a join its receiving element's, since what is known
 * about a join is attached to its RE. */
const addressOf = id => {
  const join = id.startsWith('p:') ? joinOf(id) : null;
  return join ? join.receiver_address : S.elements.get(id)?.element.address;
};
/* What a view that hosts the page waits on, MCP Apps among them: `ready`, a promise kept once the first map is drawn,
 * and `selectAddress`, which selects the node at an Address once it is, as `select` selects a node by its id. */
const READY = {done: null};
READY.promise = new Promise(resolve => { READY.done = () => { READY.done = null; resolve(true); }; });
window.metaform = {graph: () => graphData(), selected: () => S.selected, select: id => select(id, true),
  ready: READY.promise,
  selectAddress: async address => {
    await READY.promise;
    const wanted = String(address || '').replace(/^metaform:\/\//, '').split('#')[0];
    const found = [...S.elements.values()].find(entry => entry.element.address === wanted)?.element.id;
    if (found) select(found, true);
    return Boolean(found);
  },
  viewSlot: () => $('#viewslot'),
  find: address => [...S.elements.values()].find(entry => entry.element.address === address)?.element.id ?? null,
  click3d: id => clicked3d(G?.graphData().nodes.find(node => node.id === id)),
  drawn: () => G ? {nodes: G.graphData().nodes.length, links: G.graphData().links.length} : null,
  curves: () => G ? G.graphData().links.map(link => ({k: link.k, curve: accessed(G.linkCurvature(), link)})) : [],
  linkColors: () => G ? G.graphData().links.map(link => ({join: link.join || null, k: link.k,
    target: link.target?.id ?? link.target, color: linkColor(link)})) : [],
  layouts: () => V3.layouts, drawnWork: id => (G?.graphData().nodes.find(node => node.id === id)?.work || []).length,
  loaded: () => S.shown && !S.loading && !S.opening, editor: () => P.editor, live: () => LIVE.layer, changes: () => LIVE.done,
  inside: () => IN.length && M.drawn === IN.at(-1) ? [...M.nodes.keys()] : [], vertical: () => M.vertical,
  at2d: id => M.nodes.has(id) ? {x: M.nodes.get(id).x, y: M.nodes.get(id).y} : null,
  // What the base 2D map draws, by address: its nodes and each edge, from, to and its arrow as Mermaid writes it, P063.
  drawn2d: () => { const at = id => S.elements.get(id)?.element.address; return M.base ? {nodes: [...M.base.nodes.keys()].map(at),
    edges: M.base.edges.map(edge => [...ends2d(edge.join, edge.provider).map(at), edge.join.ifd === 'both' ? '<-->' : '-->'])} : null; },
  look: id => look(id), fit: () => setFit('all'), fit2d: name => setFit(name), zoom2d: name => setZoom(name), distance2d: px => { MODE.distance = px; aim2d(center2d(S.selected)); }, view2d: () => ({fit: MODE.fit, zoom: MODE.zoom, distance: distance2d(), setting: Boolean(MODE.setting)}), peek: () => peek(), embodyState: () => ({target: DOCK.target, session: DOCK.session, open: EMBODY.open, hooks: embodyHooks(), setting: VIEW.embody, turns: VIEW.embodyTurns}), fov3d: () => G ? Math.round(G.camera().fov * 10) / 10 : null, cameraAt: () => G ? cameraNow() : null, foot2d: () => Math.min(foot2d(), area2d().height / 3), lens: () => LENS.name, agentsWindow: count => agentsWindow(count), physics: () => PHYS.name,
  // the screen middles of the 3D map's join edges in view, and the edge a pointer at x, y would take
  links3d: () => !G ? [] : G.graphData().links.filter(link => link.join && link.source.x !== undefined).map(link => {
    const box = $('#stage').getBoundingClientRect(), mid = new THREE.Vector3((link.source.x + link.target.x) / 2,
      (link.source.y + link.target.y) / 2, (link.source.z + link.target.z) / 2).project(G.camera());
    return [box.left + (mid.x + 1) / 2 * box.width, box.top + (1 - mid.y) / 2 * box.height];
  }).filter(([x, y]) => { const box = $('#stage').getBoundingClientRect(); return x > box.left + 30 && x < box.right - 30 && y > box.top + 60 && y < box.bottom - 30; }),
  edgeAt: (x, y) => { const edge = edgeAt2d(x, y); return edge ? 'p:' + edge.join.id : null; },
  linkAt3d: (x, y) => { const link = linkAt3d(x, y); return link ? purposeOf(link) : null; }, mode3d: (name, level) => setMode3d(name, level), menu: id => menu(id), task: id => giveWork(id), element: id => addElement(id), note: id => notesAt(id),
  // The memory network of a node, VIEW-031: opened as the menu's entry opens it, and what both views draw of it, or
  // null on the map.
  memories: id => memories(id),
  memory: () => MEM.key && MEM.drawn ? {key: MEM.key, nodes: G ? G.graphData().nodes.map(node => node.id) : [],
    links: G ? G.graphData().links.map(link => ({source: endOf(link.source), target: endOf(link.target), relation: link.relation})) : [],
    nodes2d: [...M.nodes.keys()]} : null,
  away3d: () => G ? G.camera().position.distanceTo(G.controls().target) : 0, fits3d: () => V3.fits,
  samples3d: () => G ? G.postProcessingComposer().renderTarget1.samples : 0,
  samplesFor: name => samplesFor(name), drawnBy: () => G ? drawnBy() : '',
  // The samples a pixel are set, so a browser check can compare the picture with the smoothing and without it.
  smooth3d: samples => { if (!G) return; const chain = G.postProcessingComposer();
    for (const target of [chain.renderTarget1, chain.renderTarget2]) { target.samples = samples; target.dispose(); } wake3d(); },
  // The 3D map stops drawing, or draws again, so a browser check that steps the page's clock frame by frame to read
  // the 2D camera does not draw the 3D map at every step.
  pause3d: on => { FRAMES.held = Boolean(on); if (on) { cancelAnimationFrame(FRAMES.id); clearTimeout(FRAMES.timer); FRAMES.id = FRAMES.timer = 0; } else wake3d(); },
  // The frames the 3D map has drawn, which stop once nothing on it moves.
  frames3d: () => FRAMES.drawn,
  zoom3d: share => { if (G) { const at = G.camera().position; G.cameraPosition({x: at.x * share, y: at.y * share, z: at.z * share}, undefined, 0); } },
  glass: (on, options = {}, segments = 16) => {  // to measure what it costs
    if (!G) return;
    Object.assign(GLASS, options);
    SEGMENTS = segments;
    shapes.clear();
    G.nodeThreeObject(node => nodeObject(node, on));
  }, bloom: () => ({pass: Boolean(BLOOM), levels: BLOOM ? BLOOM.levels : 0, on: Boolean(BLOOM?.enabled)}),
  wave: () => ({dots: W.dots.length, shapes: G ? G.renderer().info.memory.geometries : 0,
    lit: G ? G.graphData().nodes.filter(node => node.__threeObj?.material?.userData.pulsed).map(node => node.id) : []}),
  // A node put where given and held there, the camera pointed, and where a node is on the page with its radius, so a
  // browser check can read a picture of the 3D map at known points.
  pin3d: (id, x, y, z) => {
    const node = G?.graphData().nodes.find(item => item.id === id);
    if (node) { Object.assign(node, {x, y, z, fx: x, fy: y, fz: z}); G.d3ReheatSimulation(); }
  },
  // the camera put at a view, as a hand would move it there: a meeting is released, as a hand releases it
  view3d: (from, to) => { if (G) { meetEnds(); G.cameraPosition(from, to, 0); } },
  screen3d: id => {
    const node = G?.graphData().nodes.find(item => item.id === id);
    if (!node || node.x === undefined) return null;
    const point = G.graph2ScreenCoords(node.x, node.y, node.z), camera = G.camera(), box = $('#stage').getBoundingClientRect();
    const distance = Math.hypot(camera.position.x - node.x, camera.position.y - node.y, camera.position.z - node.z);
    return {x: box.left + point.x, y: box.top + point.y,
      r: Math.cbrt(nodeSize(node)) * 3 / (distance * Math.tan(camera.fov * Math.PI / 360)) * box.height / 2};
  },
  waveTimes: times => { Object.assign(TIMES, times, {gaussian: times.gaussian === false ? [] : times.gaussian || TIMES.gaussian}); W.next = W.clock; wake3d(); },
  reach: () => ({property: R.key, edges: R.edges,
    elements: [...S.elements.values()].map(entry => entry.element).filter(element => R.nodes.has(element.id)).map(element => element.address)}),
  own: id => { const node = G ? G.graphData().nodes.find(item => item.id === id) : null; return node ? ownColor(node).toLowerCase() : null; },
  box2d: id => { const box = M.nodes.get(id)?.g.getBoundingClientRect(); return box ? {left: box.left, right: box.right, top: box.top, bottom: box.bottom} : null; },
  edge2d: join => [...(M.base?.edges.find(edge => edge.join.id === join)?.path?.classList || [])]
    .filter(name => name.startsWith('work-')),
  // The dots that travel the joins held still at a share of the way along each link, and where on the page each
  // link's dots are, so a browser check can read a picture of a dot passing through a node.
  // What the flow draws this frame, `FLOW`: the 3D map's points and line ends, the agents' trips under way, and the
  // shapes shown on the 2D map's selected edges; `live` draws one trip as the event stream would, `flowLive`.
  flow: () => ({points: FX.n, lines: FX.m, live: FLOW.live.length, clock: FLOW.clock,
    shapes2d: M.svg ? [...M.svg.querySelectorAll('g.flows2d > *')].filter(shape => shape.style.display !== 'none')
      .map(shape => shape.getAttribute('class')) : []}),
  flowLive: (kind, from, to, edit) => flowLive(kind, from, to, edit),
  // which joins flow, web_flow_mode: read with no name, or changed for the page with one; and the modes offered
  flowMode: name => flowMode(name),
  get flowModes() { return FLOW_MODE_LIST.map(one => ({...one})); },
  // each node's reach on the screen, `REACH`, in the 3D map or the 2D one: its centre, its box in 2D, and its reach
  reaches: which => (which === '2d' ? (M.svg ? reaches2d() : []).map(one => ({id: one.key, x: one.x, y: one.y, reach: one.reach,
    left: one.box.left, top: one.box.top, right: one.box.right, bottom: one.box.bottom}))
    : (G ? reaches3d() : []).map(one => ({id: one.node.id, x: one.x, y: one.y, r: one.r, reach: one.reach}))),
  dots3d: along => {
    if (!G) return [];
    FLOW.held = along;
    wake3d();
    const box = $('#stage').getBoundingClientRect();
    return G.graphData().links.filter(link => link.__photonsObj?.children.length).map(link => {
      const from = link.source, to = link.target;
      const point = G.graph2ScreenCoords(from.x + (to.x - from.x) * along, from.y + (to.y - from.y) * along,
        from.z + (to.z - from.z) * along);
      return {source: from.id, target: to.id, x: box.left + point.x, y: box.top + point.y};
    });
  },
  // Each label of the 3D map: its text and lines, where it is on the page, its rank by depth, higher nearer, whether it
  // is under a nearer node or label, its color and its opacity, and whether it is in the scene and drawn with the depth
  // test, which orders it with the nodes nearer than it, and whether it writes depth, VIEW-038.
  labels3d: () => { const area = $('#stage').getBoundingClientRect();
    return [...tags.values()].map(tag => ({id: tag.id, text: tag.text, lines: tag.lines, hidden: tag.hidden, z: tag.z,
      under: tag.under, color: tag.color.toLowerCase(), opacity: tag.sprite.material.opacity, scene: tag.sprite.parent?.parent === G.scene(),
      depthTest: tag.sprite.material.depthTest, depthWrite: tag.sprite.material.depthWrite, left: area.left + (tag.rect?.left ?? 0), right: area.left + (tag.rect?.right ?? 0),
      top: area.top + (tag.rect?.top ?? 0), bottom: area.top + (tag.rect?.bottom ?? 0)})); },
  // `only`, a list of node ids, shows those labels alone, so a picture of one label is not changed by another's.
  showLabels3d: (on, only = null) => { LABELS.on = Boolean(on); LABELS.only = only ? new Set(only) : null;
    if (LABELS.group) LABELS.group.visible = LABELS.on; wake3d(); },
  hover3d: id => { const node = G?.graphData().nodes.find(item => item.id === id); hovered = node || null;
    readout('3d', hovered ? readoutOf(hovered) : null); },
  figures2d: () => [...ROAM2D.figures.values()].map(figure => ({work_id: figure.id, glyph: figure.glyph, stage: figure.stage,
    target: figure.target, home: figure.home, x: figure.x, y: figure.y, size: figure.size, angle: figure.angle,
    shown: Boolean(figure.g.isConnected && M.svg && M.svg.contains(figure.g)), icon: figure.g.querySelector('image').getAttribute('href')})),
  figures: () => [...ROAM.figures.values()].map(figure => ({work_id: figure.id, glyph: figure.glyph, stage: figure.stage,
    target: figure.target, home: figure.home, x: figure.mesh.position.x, y: figure.mesh.position.y, z: figure.mesh.position.z,
    scale: figure.mesh.scale.x, angle: figure.angle, clock: figure.clock, px: onScreen(figure.mesh),
    focused: ROAM.focus === figure.id, mood: figure.mood, act: figure.act?.kind || null, lane: figure.lane})),
  // the person's mascot, `MASCOT`: its character, where it is in 3D and on the screen, and in 2D
  mascot: () => ({glyph: mascotGlyph(), shown: Boolean(MASCOT.mesh), sleeping: MASCOT.sleeping,
    driven: mascotDriven(), held: MASCOT.held?.reason ?? null, job: MASCOT.job?.kind || null, holding: MASCOT.holding?.id || null,
    x: MASCOT.pos.x, y: MASCOT.pos.y, z: MASCOT.pos.z, px: MASCOT.mesh ? onScreen(MASCOT.mesh) : 0,
    shown2d: Boolean(MASCOT2D.g?.isConnected), x2d: MASCOT2D.x, y2d: MASCOT2D.y, ...mascotScreen(),
    bubble: BUBBLE.el?.classList.contains('on') ? BUBBLE.el.textContent : null,
    cards: [...document.querySelectorAll('.mascot-card')].map(card => card.textContent), told: [...ATTN.seen]}),
  // the voice's hooks into the mascot, `MASCOT`: what it says, shown in its bubble, and whether it is speaking now,
  // which makes it talk in its own way; and a feeling or a walk as its system agent asks, as the event stream does
  mascotSaid: text => say(String(text || '').slice(0, 280), Math.min(12, 3 + String(text || '').length / 18)),
  mascotSpeaking: on => { MASCOT.speaking = Boolean(on); wake3d(); },
  mascotEvent: payload => mascotEvent({project: S.project, ...payload}),
  // a body for a conversation agent, `BODIES`: give one, list them, and the characters to choose among
  embody: (workId, glyph) => embody(workId, glyph, 'person'), bodies: () => bodies(), characters: () => characters(),
  // the large 3D view through the mascot's eyes and back, E; the eye anchors and gazes drawn, for a check of look
  mascotEyes: on => mascotEyes(on), eyeDebug: on => { EYE.debug = Boolean(on); wake3d(); return EYE.debug; },
  // the keys the mascot and the flow add, for the page's list of keys
  mascotKeys: [{key: 'E', label: "Mascot's eyes", help: "See the 3D map through the mascot's eyes, and back"},
    {key: 'X', label: 'Scissors', help: 'Cut an edge with a click; the mascot mends it. Escape puts it back'}],
  // the scissors, `CUT`: on or off, and a cut of the join edge between two nodes, as a click on it with them out
  scissors: on => cutMode(on), cut: (source, target) => cutLink(G?.graphData().links.find(link =>
    endOf(link.source) === source && endOf(link.target) === target)),
  cutStage: () => CUT.job?.stage || (CUT.saved ? 'restoring' : null),
  // the figure under a point of the screen, as a click there finds it
  figureAt: (x, y) => figureAt(x, y),
  at3d: id => { const node = G ? G.graphData().nodes.find(item => item.id === id) : null;
    return node && node.x !== undefined ? {x: node.x, y: node.y, z: node.z, r: Math.cbrt(nodeSize(node)) * 3} : null; },
  ground: () => G ? G.backgroundColor() : null};

/* How a node is drawn for its condition, MAP-046, readable by a browser check: its open work, the 2D group's work
 * classes, computed opacity and whether its box is animating, and the 3D sphere's material opacity and whether it is
 * red at this frame. */
const BOX = new THREE.Box3();
function onScreen(mesh) {  // how many pixels a figure spans in the 3D view, across or up, VIEW-035
  BOX.setFromObject(mesh);
  const xs = [], ys = [];
  for (const x of [BOX.min.x, BOX.max.x]) for (const y of [BOX.min.y, BOX.max.y]) for (const z of [BOX.min.z, BOX.max.z]) {
    const point = G.graph2ScreenCoords(x, y, z);
    xs.push(point.x); ys.push(point.y);
  }
  return Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
}
const toHex = color => { const found = (color || '').match(/\d+/g);
  return found ? '#' + found.slice(0, 3).map(part => Number(part).toString(16).padStart(2, '0')).join('') : null; };
function look(id) {
  const node = G ? G.graphData().nodes.find(item => item.id === id) : null;
  const group = (M.base?.nodes.get(id) || M.nodes.get(id))?.g || null;
  const box = group?.querySelector('rect') || null;
  const material = node?.__threeObj?.material || null;
  return {work: node?.work || [], classes: group ? [...group.classList].filter(name => name.startsWith('work-')) : [],
    opacity2d: group ? Number(getComputedStyle(group).opacity) : null,
    animated2d: box ? getComputedStyle(box).animationName !== 'none' || getComputedStyle(group).animationName !== 'none' : false,
    opacity3d: material ? material.opacity : null,
    light3d: material ? material.emissiveIntensity ?? null : null,
    ghost: Boolean(node?.__threeObj?.userData.ghost), pace: node ? paceOf(node) : null,  // a part not built, VIEW-027
    glow2d: Boolean(box) && ['broken', 'trouble', 'question', 'message'].some(name => group.classList.contains('work-' + name))
      && [group, box].some(part => getComputedStyle(part).filter.includes('drop-shadow')),
    red3d: material ? '#' + material.color.getHexString() === css('--broken').toLowerCase() : false,
    material: material ? (material instanceof MeshTransmissionMaterial ? 'MeshTransmissionMaterial' : material.type) : null,
    // the light the glass lets through: drei's own amount, since three.js's `transmission` stays 0
    transmission: material ? (material._transmission ?? material.transmission) || 0 : 0,
    chromatic: material?.chromaticAberration ?? 0, distortion: material?.distortion ?? 0,
    // the near wall reads the picture that holds the far walls, and its far wall is drawn into it
    backside: Boolean(material?.userData.back && BEHIND.main && material.buffer === BEHIND.main.texture
      && material.userData.back.side === THREE.BackSide),
    shape: node?.__threeObj?.geometry ? node.__threeObj.geometry.uuid : null,
    // what is drawn around the node besides the node itself
    around3d: node?.__threeObj ? node.__threeObj.children.length : null,
    reach3d: R.nodes.has(id), reach2d: Boolean(group?.classList.contains('reach')),

    bloom2d: Boolean(box && getComputedStyle(group).filter.includes('drop-shadow')),
    color3d: material ? '#' + material.color.getHexString() : null,
    label3d: (tags.get(id)?.classes || []).filter(name => name.startsWith('work-')),
    // how strong its name is drawn for its ghost, 1 at full, and the name's opacity as drawn, VIEW-027
    sign3d: tags.get(id)?.ghost ?? null, signOpacity3d: tags.get(id)?.sprite.material.opacity ?? null,
    stroke2d: box ? toHex(getComputedStyle(box).stroke) : null};
}

/* ---------- 3D: a synaptic map, drawn as the approved prototype draws it ---------- */
const CONDITIONS = ['missing', 'unbuilt', 'under-construction', 'broken', 'trouble', 'question', 'message'];  // built draws nothing
/* The agents at work, VIEW-035: a figure for each ticket an agent works, from the moment it is taken until it is
 * closed. It materializes on the most primary node, the DE, makes its way along the map's own edges to the ticket's
 * node, goes onto it and circles it slowly, facing the way it moves, at one steady pace until the ticket is closed;
 * then it makes its way back and is gone. Steps filed never speed it up: the node's flashing, or its text for a part
 * not built, shows how far along the work is. A figure is big enough to see what it is with the whole map in view:
 * its size is a share of the drawn map's span, and never less than ROAM.size. A ticket that was finished before its
 * figure got there is still touched, and then the figure walks back. A figure is one of the seventeen characters of
 * agents3d.js, drawn so that no two at work look alike, or the one the person chose for its agent's type,
 * web_agent_glyphs. It moves as its body would, its character's motion profile, `MOTION` in agents3d.js, varied a
 * little by its ticket so two of one character still differ: its own pace and acceleration, how it takes a corner,
 * its gait (a fish's bursts and glides, a hopper's arcs, a walker's steps in time with the ground it covers), its
 * orbit, lap and way round, how it comes and goes, and its temper, from serious to mischievous. Along a smooth curve
 * through the nodes of its way it sets off and arrives gently and slows into sharp turns, facing the way it goes and,
 * if it flies or swims, leaning into its turns. On its node it does what its session is doing, `onNode`. With reduced
 * motion it stands at the node. */
const ROAM = {figures: new Map(), seen: new Set(), last: 0, speed: 70, size: 2.6, share: 0.11, orbit: 1.5, lap: 12,
  recent: 120, appear: 0.8, touch: 0.9, vanish: 0.6,
  // how it moves along its way: units a second it speeds up and slows down by, and how much of its speed a turn
  // straight back takes off, a gentler turn less; how long it takes to settle from its way onto its orbit; and how
  // fast the size it is drawn at follows the map's span, so a layout that spreads never makes it jump
  accel: 70, corner: 0.6, settle: 1.1, grow: 10, drawn: 0, sized: 0,
  // the work whose thread the person chose in the chat dock: its figure is drawn this much larger, moving as if busy
  focus: null, focused: 1.4,
  // the most pixels a figure stands on the screen, however near the camera is
  most: 110};
const nodeById = (data, id) => data.nodes.find(node => node.id === id);
const primaryOf = data => data.nodes.find(node => node.t === 'el' && node.role === 'DE') || data.nodes.find(node => node.t === 'el');
const ticketNode = ticket => ticket.node_kind === 'join' ? 'p:' + ticket.node_id : ticket.node_id;
const ballOf = node => Math.cbrt(nodeSize(node)) * 3;
function sizeOf(data) {  // a figure's size: a share of half the drawn map's widest side
  const low = [Infinity, Infinity, Infinity], high = [-Infinity, -Infinity, -Infinity];
  for (const node of data.nodes) {
    if (node.x === undefined) continue;
    [node.x, node.y, node.z].forEach((at, axis) => { low[axis] = Math.min(low[axis], at); high[axis] = Math.max(high[axis], at); });
  }
  const half = Math.max(0, ...high.map((top, axis) => (top - low[axis]) / 2).filter(Number.isFinite));
  return Math.max(ROAM.size, ROAM.share * half);
}
function routeOf(data, from, to) {  // the fewest edges of the drawn map from one node to another
  const near = new Map(), add = (one, two) => { if (!near.has(one)) near.set(one, []); near.get(one).push(two); };
  for (const link of data.links) { add(endOf(link.source), endOf(link.target)); add(endOf(link.target), endOf(link.source)); }
  const back = new Map([[from, null]]), queue = [from];
  while (queue.length && !back.has(to)) {
    const at = queue.shift();
    for (const next of near.get(at) || []) if (!back.has(next)) { back.set(next, at); queue.push(next); }
  }
  if (!back.has(to)) return [from, to];
  const path = [];
  for (let at = to; at !== null; at = back.get(at)) path.unshift(at);
  return path;
}
/* The figures, VIEW-035: one for each ticket an agent is working in a live session, the agents key's own list, so an
 * agent that is not active is not on the map, whatever its ticket says; when its session ends the figure walks back
 * and is gone. */
const liveWork = () => new Set(D.sessions.filter(one => one.state === 'running'
  && (one.activity === 'working' || one.activity === 'waiting')).map(one => one.work_id));
function figures(tickets) {
  figures2d(tickets);
  flowTickets(tickets);  // a work record written lands on its node as a record, `FLOW`
  if (!G) return;
  const data = G.graphData(), home = primaryOf(data);
  if (!home) return;
  const live = liveWork();
  for (const ticket of tickets) {
    const figure = ROAM.figures.get(ticket.id), target = ticket.held ? talkTarget(ticket, data) : ticketNode(ticket);
    const working = drawnWorking(ticket, live);
    if (figure) {
      figure.done = !working;
      reglyph(figure);
      continue;
    }
    if (working && (!ROAM.seen.has(ticket.id) || ticket.held) && nodeById(data, target)) {
      const glyph = glyphFor(ticket.id), mesh = createAgent(glyph), motion = motionOf(glyph, ticket.id);
      mesh.userData.motion = motion;
      mesh.scale.setScalar(0.001);
      G.scene().add(mesh);
      ROAM.seen.add(ticket.id);
      flowLive('start', home.id, [target]);  // the session's request goes ahead of the figure, `FLOW`
      ROAM.figures.set(ticket.id, {id: ticket.id, glyph, mesh, motion, home: home.id, target, stage: 'arriving',
        way: routeOf(data, home.id, target).map(id => ({id})), u: 0, speed: 0, clock: 0,
        angle: motion.phase * Math.PI * 2, points: [], curve: new THREE.CatmullRomCurve3([], false, 'centripetal'),
        from: new THREE.Vector3(), heading: new THREE.Vector3(0, 0, 1), done: Boolean(ticket.done),
        stride: 0, steps: 0, pos: new THREE.Vector3(), vel: new THREE.Vector3(), mood: 'working', act: null,
        nextAct: 4 + motion.phase * 6, reach: null, glance: null, nextGlance: 0, lane: 0, talk: Boolean(ticket.held)});
    }
  }
  for (const [id, figure] of ROAM.figures) if (!tickets.some(ticket => ticket.id === id)) figure.done = true;
  wake3d();
}
/* A body for a conversation agent, VIEW-005: the person's system agent, from Call, or an agent the person chats with
 * about a node or a ticket. Unembodied, it is drawn as it always was: no figure while the person has a mascot, else a
 * plain one while it works. Given a body, `embody`, by the person from the chat dock's offer or by the agent itself
 * with web_embody, it walks out from the map's primary node in that character, with its motion and its temper: the
 * system agent to what the person has selected, or beside the mascot, and an agent chatting about something to it.
 * It sees from its own eyes, `seer`, and speaks in its own bubble. The system agent given the mascot's character is
 * the mascot. A body is kept for the conversation, by its ticket, so a resumed conversation comes back in the same
 * body; the person's choice stands over the agent's, and no two figures at work share a character. */
const SYSTEM_TALK = 'Conversation with the system agent';  // the system agent's ticket, dispatch's SYSTEM_TASK
const BODIES = {chosen: (() => { try { return JSON.parse(localStorage.getItem('metaform.bodies') || '{}'); } catch { return {}; } })()};
const bodyKey = work => `${S.project}|${work}`;
// a body is the conversation's it was given in: that session, and the same session resumed; a new conversation has none
function bodyOf(work) {
  const held = BODIES.chosen[bodyKey(work)];
  if (!held?.glyph) return null;
  const live = held.session ? D.sessions.filter(one => one.work_id === work && one.state === 'running').at(-1) : null;
  return !live || live.session_id === held.session ? held.glyph : null;
}
const isSystemTalk = ticket => Boolean(ticket?.held && ticket.task === SYSTEM_TALK);
const talking = ticket => D.sessions.some(one => one.work_id === ticket.id && one.state === 'running');
/* Whether a ticket's agent is drawn as a figure now. */
function drawnWorking(ticket, live = liveWork()) {
  if (ticket.done) return false;
  if (!ticket.held) return live.has(ticket.id);
  if (isSystemTalk(ticket)) return false;  // the system agent is drawn only as the mascot, once it has a body
  const body = bodyOf(ticket.id);
  if (body) return talking(ticket);
  return live.has(ticket.id) && !mascotGlyph();
}
/* Where an embodied conversation agent goes: the system agent to the selection, or beside the mascot; another to what
 * it talks about. */
function talkTarget(ticket, data) {
  if (!isSystemTalk(ticket)) return ticketNode(ticket);
  if (S.selected && nodeById(data, S.selected)) return S.selected;
  if (MASCOT.mesh) {
    let best = null, nearest = Infinity;
    for (const node of data.nodes) {
      if (node.t !== 'el' || node.x === undefined) continue;
      const away = MASCOT.pos.distanceTo(AT.set(node.x, node.y, node.z));
      if (away < nearest) { nearest = away; best = node.id; }
    }
    if (best) return best;
  }
  return ticketNode(ticket);
}
/* An embodied conversation figure follows what it is about: it walks on to a new selection, along the map's edges. */
function retarget(figure, data) {
  if (!figure.talk || figure.stage !== 'circling' || figure.done) return;
  const ticket = ticketOf(figure.id), wanted = ticket && talkTarget(ticket, data);
  if (!wanted || wanted === figure.target || !nodeById(data, wanted)) return;
  const way = routeOf(data, figure.target, wanted);
  Object.assign(figure, {target: wanted, stage: 'going', u: 0, clock: 0,
    way: [{point: figure.mesh.position.clone()}, ...(way.length > 1 ? way.slice(1) : [wanted]).map(id => ({id}))]});
}
/* Give a conversation agent a body: `by` the person, whose choice stands, or the agent, `web_embody`. */
function embody(work, glyph, by = 'person') {
  const ticket = ticketOf(work), key = bodyKey(work), held = BODIES.chosen[key];
  if (!GLYPHS.includes(glyph)) return {error: `${glyph} is not a character.`};
  if (!ticket) return {error: 'There is no such conversation on this page.'};
  if (by === 'agent' && held?.by === 'person' && held.glyph !== glyph) return {error: `The person gave you the ${held.glyph}; it stays.`};
  // the system agent's body is the mascot; the mascot's character is no other agent's while it is drawn
  const mascot = isSystemTalk(ticket);
  if (glyph === mascotGlyph() && !mascot) return {error: `The ${glyph} is the person's mascot.`};
  const other = [...ROAM.figures.values()].find(figure => figure.id !== work && figure.glyph === glyph && figure.stage !== 'leaving');
  if (other) return {error: `The ${glyph} is at work already on this map.`};
  // kept with the session it was given in, so the same conversation resumed comes back in it and a new one is asked
  const live = D.sessions.filter(one => one.work_id === work && one.state === 'running').at(-1);
  BODIES.chosen[key] = {glyph, by, session: live?.session_id || null};
  try { localStorage.setItem('metaform.bodies', JSON.stringify(BODIES.chosen)); } catch { /* kept for this page only */ }
  releaseGlyph(work);
  const figure = ROAM.figures.get(work);
  if (figure) { if (mascot) figure.done = true; else reglyph(figure); }
  figures(S.tickets || []);
  // the mascot walks out from the map's primary node and greets the person
  say(by === 'agent' ? 'A body of my own. Thank you.' : 'Here I am.', 3, null, mascot ? null : work, mascot ? glyph : '');
  wake3d(3000);
  if (typeof wake2d === 'function') wake2d();
  return {character: glyph, mascot, figure: !mascot};
}
/* Each conversation agent and its body, for the chat dock's offer. */
function bodies() {
  return (S.tickets || []).filter(ticket => ticket.held && talking(ticket)).map(ticket => ({work: ticket.id,
    system: isSystemTalk(ticket), character: bodyOf(ticket.id), by: bodyOf(ticket.id) ? BODIES.chosen[bodyKey(ticket.id)]?.by || null : null,
    drawn: isSystemTalk(ticket) ? Boolean(MASCOT.mesh) && Boolean(bodyOf(ticket.id)) : ROAM.figures.has(ticket.id),
    mascot: isSystemTalk(ticket) && Boolean(bodyOf(ticket.id))}));
}
/* The characters a body can be, for the picker: each with its name, its temper and a word for it, how it moves, whether
 * it is free now, and `preview(canvas)`, which draws it moving in its own way on a small canvas until the function it
 * returns is called; with reduced motion it stands still. */
const TEMPERS = [[0.2, 'serious'], [0.45, 'steady'], [0.7, 'playful'], [1.01, 'mischievous']];
function characters() {
  const busy = new Set([...ROAM.figures.values()].map(figure => figure.glyph));
  return GLYPHS.map(name => ({name, temper: MOTION[name].temper, temperament: TEMPERS.find(([most]) => MOTION[name].temper < most)[1],
    moves: MOTION[name].go, free: !busy.has(name) && name !== mascotGlyph(), mascot: name === mascotGlyph(),
    preferred: name === preferredGlyph(),  // web_mascot: the person's own character, suggested first
    preview: canvas => previewOf(canvas, name)}));
}
function previewOf(canvas, name) {
  const pen = canvas.getContext('2d'), image = new Image(), motion = {...MOTION[name], phase: 0};
  image.src = `/page/agent-glyphs/${name}.svg`;
  let id = 0, stride = 0, last = performance.now(), landed = 9, was = 0;
  const draw = now => {
    const passed = Math.min(0.1, (now - last) / 1000), w = canvas.width, h = canvas.height, size = Math.min(w, h) * 0.7;
    last = now;
    stride += reduced() ? 0 : passed * motion.speed * 1.4;
    const stroke = strokeOf(motion, stride);
    if (was < 0.75 && stroke.phase >= 0.75) landed = 0;
    landed += passed; was = stroke.phase;
    let lift = 0, squash = 0, lean = 0;
    if (motion.go === 'hop') {
      lift = stroke.air * motion.lift * 0.5;
      squash = (stroke.phase >= 0.75 ? Math.sin((stroke.phase - 0.75) / 0.25 * Math.PI) * 0.2 : 0) + Math.exp(-landed * 14) * 0.12;
    } else if (motion.go === 'walk' || motion.go === 'creep') lift = Math.abs(Math.sin(stroke.phase * Math.PI * 2)) * 0.05;
    else if (motion.go === 'swim' || motion.go === 'pulse') lean = Math.sin(stroke.phase * Math.PI * 2) * 0.12 * stroke.thrust;
    else lift = Math.sin(now / 1000 * 2.2) * 0.04;
    pen.clearRect(0, 0, w, h);
    if (image.complete && image.naturalWidth) {
      pen.save();
      pen.translate(w / 2, h * 0.9 - lift * h);
      pen.rotate(lean);
      pen.scale(1 + squash * 0.6, 1 - squash);
      pen.drawImage(image, -size / 2, -size, size, size);
      pen.restore();
    }
    if (!reduced()) id = requestAnimationFrame(draw);
  };
  image.onload = () => { cancelAnimationFrame(id); id = requestAnimationFrame(draw); };
  id = requestAnimationFrame(draw);
  return () => cancelAnimationFrame(id);
}
/* A figure drawn before the page knew its agent's type takes the character chosen for the type, web_agent_glyphs,
 * where it stands, in both maps. */
function reglyph(figure) {
  const glyph = glyphFor(figure.id);
  if (glyph === figure.glyph) return;
  const mesh = createAgent(glyph), motion = motionOf(glyph, figure.id);
  mesh.userData.motion = motion;
  mesh.position.copy(figure.mesh.position); mesh.quaternion.copy(figure.mesh.quaternion); mesh.scale.copy(figure.mesh.scale);
  G.scene().remove(figure.mesh);
  G.scene().add(mesh);
  Object.assign(figure, {glyph, mesh, motion});
  const flat = ROAM2D.figures.get(figure.id);
  if (flat) {
    Object.assign(flat, {glyph, motion: motionOf(glyph, figure.id)});
    flat.g.dataset.glyph = glyph;
    flat.g.querySelector('image')?.setAttribute('href', `/page/agent-glyphs/${glyph}.svg`);
  }
}
/* The places a figure's way passes: each node a little above its center, or the point where the figure left its orbit.
 * Read again each frame, so a figure on its way moves with the map as the layout moves it. False while a node of the
 * way is not drawn. */
function placed(figure, data, lift) {
  const points = figure.points;
  points.length = figure.way.length;
  for (let k = 0; k < figure.way.length; k++) {
    const step = figure.way[k];
    points[k] = points[k] || new THREE.Vector3();
    if (step.point) { points[k].copy(step.point); continue; }
    const node = nodeById(data, step.id);
    if (!node || node.x === undefined) return false;
    points[k].set(node.x, node.y + lift, node.z);
  }
  figure.curve.points = points;
  return points.length >= 2;
}
/* A figure walks its way as one smooth curve through its places. It sets off from rest, speeding up by ROAM.accel to
 * ROAM.speed, takes each turn slower the sharper it is, and slows to rest as it arrives, so it never starts, stops or
 * turns at once. Its place on the way is its leg and how far along that leg it is, so it keeps to the edge it is on
 * while the layout moves the nodes. Says whether it has arrived. */
const HEAD = new THREE.Vector3(), NEXT = new THREE.Vector3();
// How each way of taking a corner slows a figure into it, and how quickly it turns to face its way, `MOTION`
const CORNERS = {bank: {slow: 0.35, turn: 0.16}, pivot: {slow: 0.9, turn: 0.45}, drift: {slow: 0.25, turn: 0.08},
  flit: {slow: 0.5, turn: 0.3}, bend: {slow: 0.45, turn: 0.14}, hop: {slow: 0.6, turn: 0.35}};
function walk(figure, passed, size = ROAM.size) {
  const points = figure.points, legs = points.length - 1, lengths = [], motion = figure.motion;
  const top = ROAM.speed * (motion?.speed ?? 1), accel = ROAM.accel * (motion?.accel ?? 1);
  const corner = CORNERS[motion?.corner]?.slow ?? ROAM.corner;
  let total = 0;
  for (let k = 0; k < legs; k++) { lengths.push(Math.max(1e-3, points[k].distanceTo(points[k + 1]))); total += lengths[k]; }
  const leg = Math.min(legs - 1, Math.floor(figure.u));
  let done = (figure.u - leg) * lengths[leg];
  for (let k = 0; k < leg; k++) done += lengths[k];
  const least = top * 0.12, reach = (limit, away) => Math.sqrt(limit * limit + 2 * accel * Math.max(0, away));
  let speed = Math.min(top, reach(least, done), reach(least, total - done));
  for (let k = 1, at = lengths[0]; k < legs; at += lengths[k], k++) {
    const turn = HEAD.subVectors(points[k], points[k - 1]).normalize().dot(NEXT.subVectors(points[k + 1], points[k]).normalize());
    speed = Math.min(speed, reach(top * (1 - corner * (1 - turn) / 2), Math.abs(at - done)));
  }
  // a swimmer surges on each push and glides between, a hopper covers ground in the air, `strokeOf`
  if (motion) speed *= strokeOf(motion, figure.stride || 0).pace;
  figure.top = top;
  figure.stride = (figure.stride || 0) + speed * passed / size;
  let step = speed * passed;
  while (step > 0 && figure.u < legs) {
    const now = Math.min(legs - 1, Math.floor(figure.u)), room = (now + 1 - figure.u) * lengths[now];
    if (step < room) { figure.u += step / lengths[now]; step = 0; } else { step -= room; figure.u = now + 1; }
  }
  figure.speed = speed;
  return figure.u >= legs - 1e-6;
}
/* The point a figure circles its node from, measured from the node, and its first turn on the orbit: the side of the
 * node that lets it carry straight on the way it came, so it swings out onto its orbit with no turn back. */
function onOrbit(figure, target) {
  figure.from.copy(figure.mesh.position).sub(AT.set(target.x, target.y, target.z));
  const across = Math.hypot(figure.heading.x, figure.heading.z);
  if (across > 1e-3) figure.angle = Math.atan2(-figure.heading.x / across, figure.heading.z / across);
}
const AHEAD = new THREE.Vector3(), ORBIT = new THREE.Vector3(), WANT = new THREE.Vector3(), PULL = new THREE.Vector3();
const TOWARD = new THREE.Vector3(), SPOT = new THREE.Vector3();
const easeBoth = k => k * k * (3 - 2 * k);  // from rest to rest
/* How each figure behaves on its node, VIEW-035, in its character's way, `MOTION` in agents3d.js. Where it means to be
 * is worked out each frame and it follows that place on a critically damped spring, `springTo`, so every move eases in
 * and out and any of them can be turned aside at once; how stiffly it follows is its character's, `STIFF`: a comet
 * snaps, a wisp drifts. What it does there comes from its session, `moodOf`:
 *  - working: it circles in its own orbit, lap and direction, and every so often does something with the node in its
 *    own way, its `act`: perches on top, pokes it, nudges it so the node sways, peeks in close;
 *  - a tool call, told by the event stream, `figureReached`: a quick, purposeful move toward the part touched, a lean and a
 *    reach, and back; on its own node, a poke;
 *  - waiting for the person: it settles beside the node and turns toward the chat dock, idling patiently;
 *  - a spinning or stuck signal: restless, uneven circling, kept calm;
 *  - done: a small flourish of its own before it walks home.
 * Two figures on one node take lanes apart, notice each other with a glance and a pause, and make room. Figures leave
 * a faint trail on the way, footprints, ripples or hop marks, that fades within seconds, `MARKS`. */
const STIFF = {dart: 40, roll: 30, walk: 26, hover: 24, flutter: 30, flap: 20, glide: 14, float: 10, pulse: 12, swim: 14,
  creep: 18, hop: 22};
const RESTLESS = ['spinning-calls', 'spinning-time', 'repeated-failure', 'drift'];
const ACTS = {perch: 4.5, peek: 3, poke: 1.6, nudge: 2.2, circle: 0};  // how long each act lasts, in seconds
// The wait before a figure's next act with its node, by its temper: a serious one keeps to its task and plays now and
// then, about every 25 seconds; a mischievous one about every 6.
const actGap = (motion, clock) => (6 + 20 * (1 - (motion.temper ?? 0.5))) * (0.6 + 0.8 * ((motion.phase * 7.13 + clock * 0.37) % 1));
function moodOf(workId) {
  const session = D.sessions.filter(one => one.work_id === workId && one.state === 'running').at(-1);
  if (!session) return 'working';
  if ((D.signals || []).some(one => one.session_id === session.session_id && one.active !== false
    && RESTLESS.includes(one.signal))) return 'restless';
  return session.activity === 'waiting' ? 'waiting' : 'working';
}
// the person chose a character for an agent's type, web_agent_glyphs: entries such as claude=owl
function typeGlyph(workId) {
  const agent = String(D.sessions.filter(one => one.work_id === workId).at(-1)?.agent || '');
  if (!agent) return null;
  for (const entry of (WS.view().agent_glyphs || []).flatMap(one => String(one).split(/[,\s]+/))) {
    const [type, glyph] = String(entry).split('=').map(part => part.trim());
    if (type && glyph && (agent === type || agent.startsWith(type + '-'))) return glyph;
  }
  return null;
}
/* A tool call of a running agent reached these nodes, `flowEvent`: its figure reaches toward the first. */
function figureReached(workId, to) {
  const figure = ROAM.figures.get(workId), figure2d = ROAM2D.figures.get(workId);
  if (figure && to) figure.reach = {to, at: figure.clock};
  if (figure2d && to) figure2d.reach = {to, at: figure2d.clock};
}
function springTo(figure, want, passed, stiff) {  // a critically damped spring toward where it means to be
  const damp = 2 * Math.sqrt(stiff);
  PULL.subVectors(want, figure.pos).multiplyScalar(stiff).addScaledVector(figure.vel, -damp);
  figure.vel.addScaledVector(PULL, passed);
  figure.pos.addScaledVector(figure.vel, passed);
}
/* A node a figure pokes or nudges sways a little and settles; only the drawn object turns, the layout is untouched. */
const SWAYS = new Map();
function nudgeNode(node, k) {
  const object = node?.__threeObj;
  if (!object || reduced()) return;
  const held = SWAYS.get(node.id);
  SWAYS.set(node.id, {node, k, at: performance.now() / 1000, base: held?.base || {x: object.rotation.x, z: object.rotation.z}});
}
function sway3d() {
  const now = performance.now() / 1000;
  for (const [id, one] of SWAYS) {
    const object = one.node.__threeObj, t = now - one.at;
    if (!object) { SWAYS.delete(id); continue; }
    if (t > 2.6) { object.rotation.x = one.base.x; object.rotation.z = one.base.z; SWAYS.delete(id); continue; }
    const swing = one.k * Math.exp(-t * 2.2) * Math.sin(t * 9);
    object.rotation.z = one.base.z + swing;
    object.rotation.x = one.base.x + swing * 0.4;
  }
}
/* The trail a figure leaves: a mark where each step, push or hop lands, faint and gone within seconds, drawn with the
 * flow, `fxMarks`. Fliers leave none. */
const MARKS = [];
function markTrail(figure, size) {
  const m = figure.motion, steps = Math.floor((figure.stride || 0) / Math.max(0.05, m.stride));
  if (steps === figure.steps) return;
  figure.steps = steps;
  const kind = m.go === 'walk' || m.go === 'creep' || m.go === 'roll' ? 'step' : m.go === 'swim' || m.go === 'pulse' ? 'ripple'
    : m.go === 'hop' ? 'hop' : null;
  if (!kind) return;
  const p = figure.mesh.position, side = steps % 2 ? 1 : -1;
  AHEAD.set(-figure.heading.z, 0, figure.heading.x).normalize().multiplyScalar(kind === 'step' ? side * size * 0.18 : 0);
  MARKS.push({x: p.x + AHEAD.x, y: p.y - size * 0.55, z: p.z + AHEAD.z, kind, size, at: FLOW.clock});
  if (MARKS.length > 90) MARKS.shift();
}
function fxMarks(color) {
  while (MARKS.length && FLOW.clock - MARKS[0].at > 2.6) MARKS.shift();
  for (const one of MARKS) {
    const u = (FLOW.clock - one.at) / 2.6, fade = Math.pow(1 - u, 2) * 0.4;
    if (one.kind === 'step') fxDot(one, one.size * 0.22, color, fade, 0, 2, 5);
    else fxDot(one, one.size * (one.kind === 'hop' ? 0.5 + 0.4 * u : 0.4 + 1.1 * u), color, fade, 2, 4, 40);
  }
}
/* Where the chat dock is, as a point in the scene at the depth of `near`, so a figure waiting on the person faces it. */
const DOCKAT = new THREE.Vector3();
function dockPoint(near) {
  const area = G.renderer().domElement.getBoundingClientRect(), dock = $('#helpdesk');
  const box = dock && !dock.hidden ? dock.getBoundingClientRect() : null;
  const x = box && box.width ? box.left + box.width / 2 : area.right - 40, y = box && box.height ? box.top + box.height / 2 : area.bottom - 20;
  DOCKAT.set(near.x, near.y, near.z).project(G.camera());
  DOCKAT.x = (x - area.left) / area.width * 2 - 1;
  DOCKAT.y = -(y - area.top) / area.height * 2 + 1;
  return DOCKAT.unproject(G.camera());
}
/* Where a figure means to be on its node this frame, and what it looks at, if anything but the way it goes. */
function onNode(figure, target, size, data) {
  const m = figure.motion, ball = ballOf(target), c = figure.clock;
  // the angle always grows at its lap's pace; which way round it goes is its character's, `dir`
  let rate = 2 * Math.PI / m.lap, reach = ball + size * (m.orbit + figure.lane * 0.8);
  if (figure.mood === 'restless') {  // uneven, never frantic
    rate *= 1 + 0.55 * Math.sin(c * 1.7) * Math.sin(c * 0.63 + 1);
    reach *= 1 + 0.12 * Math.sin(c * 1.1);
  }
  if (figure.glance && c < figure.glance.until) rate *= 0.15;
  if (figure.mood === 'waiting') rate = 0;
  figure.angle += rate * figure.passed;
  const turn = m.dir * figure.angle + figure.lane * Math.PI;
  WANT.set(target.x + Math.cos(turn) * reach, target.y + Math.sin(turn * 2) * reach * 0.18 + size * 0.3,
    target.z + Math.sin(turn) * reach);
  let face = null;
  if (figure.mood === 'waiting') {  // beside its node, toward the chat dock, patient
    const dock = dockPoint(target);
    TOWARD.subVectors(dock, AT.set(target.x, target.y, target.z)).normalize();
    WANT.set(target.x, target.y + size * 0.2, target.z).addScaledVector(TOWARD, ball + size * (1.1 + figure.lane * 0.8));
    face = SPOT.copy(dock);
  }
  // now and then while it works, something of its own with the node
  if (figure.mood === 'working' && !figure.act && c > figure.nextAct && ACTS[m.act])
    figure.act = {kind: m.act, at: c, long: ACTS[m.act], hit: false};
  const act = figure.act;
  if (act) {
    const u = (c - act.at) / act.long;
    if (u >= 1 || figure.mood !== 'working') {
      figure.act = null;
      figure.nextAct = c + actGap(m, c);
    } else {
      const k = Math.sin(Math.PI * u), center = AT.set(target.x, target.y, target.z);
      TOWARD.subVectors(WANT, center).normalize();
      if (act.kind === 'perch') {  // it settles on top and looks about
        WANT.lerp(SPOT.set(target.x, target.y + ball + size * 0.42, target.z), easeBoth(Math.min(1, k * 1.6)));
      } else if (act.kind === 'peek') {  // in close at its side, looking in
        WANT.lerp(SPOT.copy(center).addScaledVector(TOWARD, ball + size * 0.6), easeBoth(Math.min(1, k * 1.5)));
        face = AT.set(target.x, target.y, target.z);
      } else {  // a poke darts in to touch it; a nudge leans in and pushes, and the node sways
        WANT.lerp(SPOT.copy(center).addScaledVector(TOWARD, ball + size * 0.35), k * k);
        face = AT.set(target.x, target.y, target.z);
        if (!act.hit && u > 0.45) { act.hit = true; nudgeNode(target, act.kind === 'nudge' ? 0.14 : 0.07); }
      }
    }
  }
  // a tool call: a quick, purposeful reach toward what it touched, and back
  if (figure.reach) {
    const u = (c - figure.reach.at) / 1.3, to = nodeById(data, figure.reach.to);
    if (u >= 1 || !to || to.x === undefined) figure.reach = null;
    else {
      const k = Math.sin(Math.PI * Math.min(1, u)) ** 2;
      if (to === target) {
        TOWARD.subVectors(WANT, AT.set(target.x, target.y, target.z)).normalize();
        WANT.lerp(SPOT.set(target.x, target.y, target.z).addScaledVector(TOWARD, ball + size * 0.4), k);
        if (u > 0.45 && !figure.reach.hit) { figure.reach.hit = true; nudgeNode(target, 0.05); }
      } else WANT.lerp(SPOT.set(to.x, to.y, to.z), 0.32 * k);
      face = AT.set(to.x, to.y, to.z);
    }
  }
  if (figure.lookAt && c < figure.lookAt.until) {  // asked to look at something, `sight`
    const toward = nodeById(data, figure.lookAt.node);
    if (toward && toward.x !== undefined) face = AT.set(toward.x, toward.y, toward.z);
  }
  if (figure.glance && c < figure.glance.until) {
    const loose = CUT.job?.loose && CUT.job.bodies.get(CUT.job.loose);
    const other = ROAM.figures.get(figure.glance.other)?.mesh.position || (figure.glance.other === 'mascot' ? MASCOT.mesh?.position
      : figure.glance.other === 'cut' && loose ? AT.set(loose.x, loose.y, loose.z) : null);
    if (other) face = AT.copy(other);
  }
  return face;
}
/* A figure's flourish when its work is done, before it walks home: where it is this moment, around where it stood. */
const FLOURISH = 1.4;
function flourish(figure, size, u) {
  const kind = figure.motion.flourish, k = Math.sin(Math.PI * u), spin = easeBoth(u) * Math.PI * 2;
  WANT.copy(figure.from);
  let turn = 0, scale = 1;
  if (kind === 'spin' || kind === 'twirl') { turn = spin; if (kind === 'twirl') WANT.y += k * size * 0.8; }
  else if (kind === 'loop') { WANT.y += (1 - Math.cos(spin)) * size * 0.7; WANT.addScaledVector(figure.heading, Math.sin(spin) * size * 0.7); }
  else if (kind === 'hop' || kind === 'flap') { WANT.y += k * size * (kind === 'hop' ? 1.2 : 0.8); figure.stride += figure.passed * 3; }
  else if (kind === 'puff') scale = 1 + 0.3 * k;
  else if (kind === 'bow') turn = 0;
  return {turn, scale, bow: kind === 'bow' ? k * 0.6 : 0};
}
/* How a figure comes and goes, its character's `arrive`: where it is and how large, a share `k` of the way in. */
function arrival(figure, at, size, k, leaving) {
  const style = figure.motion.arrive, e = leaving ? 1 - easeBoth(1 - k) : easeBoth(k);
  WANT.copy(at);
  let scale = 1, tall = 1;
  if (style === 'drop') { WANT.y += (1 - e) * size * 5; scale = Math.min(1, k * 3); }
  else if (style === 'swoop') { WANT.y += (1 - e) * size * 4; WANT.x += (1 - e) * size * 3; scale = Math.min(1, k * 2); }
  else if (style === 'rise') { WANT.y -= (1 - e) * size * 3; scale = Math.min(1, k * 2.5); }
  else if (style === 'sprout') { tall = Math.max(0.001, e); WANT.y -= (1 - e) * size * 0.5; }
  else if (style === 'fade') scale = Math.max(0.001, e);
  else scale = Math.max(0.001, leaving ? 1 - (1 - k) * (1 - k) : 1 + 1.7 * Math.pow(k - 1, 3) + 0.7 * Math.pow(k - 1, 2));
  return {scale, tall};
}
function roam3d(data) {
  const now = performance.now() / 1000, passed = Math.min(0.1, Math.max(0, now - (ROAM.last || now)));
  ROAM.last = now;
  // The size follows the map's span gently, so a layout still spreading never makes a figure jump in size.
  const real = Math.min(1, Math.max(0, now - (ROAM.sized || now)));
  ROAM.sized = now;
  const size = ROAM.drawn = ROAM.figures.size || mascotGlyph() || MASCOT.mesh
    ? (ROAM.drawn ? ROAM.drawn + (sizeOf(data) - ROAM.drawn) * (1 - Math.exp(-real * ROAM.grow)) : sizeOf(data)) : 0;
  const lift = size * 0.6;
  sway3d();
  // figures on one node take lanes apart, and notice each other as they pass
  const lanes = new Map();
  for (const figure of [...ROAM.figures.values()].sort((one, two) => one.id < two.id ? -1 : 1)) {
    if (figure.stage !== 'circling') continue;
    figure.lane = lanes.get(figure.target) || 0;
    lanes.set(figure.target, figure.lane + 1);
  }
  for (const one of ROAM.figures.values()) for (const two of ROAM.figures.values()) {
    if (one.id >= two.id || one.stage !== 'circling' || two.stage !== 'circling' || one.target !== two.target) continue;
    if (one.clock < one.nextGlance || one.mesh.position.distanceTo(two.mesh.position) > size * 3) continue;
    one.glance = {other: two.id, until: one.clock + 1.1}; two.glance = {other: one.id, until: two.clock + 1.1};
    one.nextGlance = one.clock + 9; two.nextGlance = two.clock + 9;
  }
  for (const [id, figure] of ROAM.figures) {
    if ((figure.checked = (figure.checked || 0) + passed) > 1) { figure.checked = 0; reglyph(figure); retarget(figure, data); }
    const {mesh} = figure, m = figure.motion;
    const gone = () => { G.scene().remove(mesh); releaseGlyph(id); ROAM.figures.delete(id); };
    figure.clock += passed;
    figure.passed = passed;
    const target = nodeById(data, figure.target), home = nodeById(data, figure.home);
    if (!target || target.x === undefined || !home || home.x === undefined) continue;
    const grown = ROAM.focus === id ? ROAM.focused : 1;
    if (reduced()) {  // no walking: the figure stands on its node while the ticket is worked
      mesh.position.set(target.x, target.y + ballOf(target) + size, target.z);
      mesh.scale.setScalar(size * grown);
      if (figure.done) gone();
      continue;
    }
    figure.mood = moodOf(id);
    let state = 'travel', scale = 1, tall = 1, turn = 0, bow = 0, face = null;
    if (figure.stage === 'arriving') {  // it comes onto the most primary node in its own way
      const k = Math.min(1, figure.clock / ROAM.appear);
      ({scale, tall} = arrival(figure, AT.set(home.x, home.y + lift, home.z), size, k, false));
      mesh.position.copy(WANT);
      if (k >= 1) Object.assign(figure, {stage: 'going', u: 0, clock: 0});
    } else if (figure.stage === 'going' || figure.stage === 'returning') {  // along the map's own edges
      const going = figure.stage === 'going';
      if (!placed(figure, data, lift)) {  // a node of its way left the map: it goes on to what comes next
        figure.pos.copy(mesh.position); figure.vel.set(0, 0, 0);
        figure.from.copy(mesh.position);
        Object.assign(figure, going ? {stage: figure.done ? 'flourish' : 'circling'} : {stage: 'leaving'}, {clock: 0});
        continue;
      }
      const arrived = walk(figure, passed, size), along = figure.u / (figure.points.length - 1);
      figure.curve.getPoint(along, mesh.position);
      figure.curve.getTangent(along, AHEAD);
      if (AHEAD.lengthSq() > 1e-8) figure.heading.copy(AHEAD);
      if (m.corner === 'flit') {  // a moth jinks from side to side as it goes
        TOWARD.set(-figure.heading.z, 0, figure.heading.x).normalize();
        mesh.position.addScaledVector(TOWARD, Math.sin(figure.stride * 5.3) * size * 0.25 * Math.min(1, figure.speed / figure.top));
      }
      // a mischievous one takes a little detour as it goes, pokes a node it passes, and teases a figure it meets
      const temper = m.temper ?? 0.5;
      if (temper > 0.55 && m.corner !== 'flit') {
        TOWARD.set(-figure.heading.z, 0, figure.heading.x).normalize();
        mesh.position.addScaledVector(TOWARD, Math.sin(figure.stride * 0.9 + m.phase * 6) * size * 0.45 * (temper - 0.5)
          * Math.min(1, figure.speed / figure.top));
      }
      if (temper > 0.6 && figure.clock > (figure.poked || 0)) {
        const brush = data.nodes.find(node => node.t === 'el' && node.x !== undefined && node.id !== figure.target
          && mesh.position.distanceTo(AT.set(node.x, node.y, node.z)) < ballOf(node) + size * 0.7);
        if (brush) { nudgeNode(brush, 0.05 * temper); figure.poked = figure.clock + 12 - 6 * temper; }
      }
      if (temper > 0.6 && figure.clock > (figure.teased || 0)) for (const other of ROAM.figures.values()) {
        if (other === figure || mesh.position.distanceTo(other.mesh.position) > size * 2.5) continue;
        figure.glance = {other: other.id, until: figure.clock + 0.8};
        figure.stride += m.stride * 0.6;  // a little hop at it
        figure.teased = figure.clock + 15;
        break;
      }
      markTrail(figure, size);
      // an agent passing the mascot notices it
      if (MASCOT.mesh && mesh.position.distanceTo(MASCOT.mesh.position) < size * 4 && figure.clock > (figure.noticed || 0)) {
        figure.noticed = figure.clock + 12;
        figure.glance = {other: 'mascot', until: figure.clock + 0.9};
      }
      if (figure.glance?.other === 'mascot' && figure.clock < figure.glance.until && MASCOT.mesh)
        face = AT.copy(MASCOT.mesh.position);
      if (arrived) {
        figure.pos.copy(mesh.position); figure.vel.copy(figure.heading).multiplyScalar(figure.speed * 0.5);
        figure.from.copy(mesh.position);
        // onto its orbit from where it arrived, so it swings straight out onto it
        figure.angle = m.dir * Math.atan2(mesh.position.z - target.z, mesh.position.x - target.x) - figure.lane * Math.PI;
        Object.assign(figure, {clock: 0, stage: !going ? 'leaving' : figure.done ? 'flourish' : 'circling'});
      }
    } else if (figure.stage === 'circling') {  // on its node, in its own way, `onNode`
      face = onNode(figure, target, size, data);
      springTo(figure, WANT, passed, STIFF[m.go] || 20);
      mesh.position.copy(figure.pos);
      state = figure.mood === 'waiting' ? 'wait' : figure.mood;
      if (figure.vel.lengthSq() > 1e-4) figure.heading.lerp(AHEAD.copy(figure.vel).normalize(), 0.2);
      figure.stride += figure.vel.length() * passed / size;
      // a hopper hops in place now and then while it idles
      if (m.go === 'hop' && figure.vel.length() < size * 0.3 && Math.sin(figure.clock * 0.6 + m.phase * 6) > 0.2)
        figure.stride += passed * m.stride * 0.8;
      markTrail(figure, size);
      if (figure.done) { figure.from.copy(mesh.position); Object.assign(figure, {stage: 'flourish', clock: 0}); }
    } else if (figure.stage === 'flourish') {  // done: a little flourish of its own, then home
      const u = Math.min(1, figure.clock / FLOURISH);
      ({turn, scale, bow} = flourish(figure, size, u));
      springTo(figure, WANT, passed, 40);
      mesh.position.copy(figure.pos);
      state = 'flourish';
      if (u >= 1) {
        const back = routeOf(data, figure.target, figure.home);
        Object.assign(figure, {stage: 'returning', u: 0, clock: 0,
          way: [{point: mesh.position.clone()}, ...(back.length > 1 ? back.slice(1) : [figure.home]).map(one => ({id: one}))]});
      }
    } else if (figure.stage === 'leaving') {  // home again, it goes in its own way
      const k = Math.min(1, figure.clock / ROAM.vanish);
      ({scale, tall} = arrival(figure, AT.set(home.x, home.y + lift, home.z), size, 1 - k, true));
      mesh.position.copy(WANT);
      if (k >= 1) { gone(); continue; }
    }
    // how large it is drawn: its size, its arrival, the thread on view drawn larger
    mesh.scale.set(size * scale * grown, size * scale * tall * grown, size * scale * grown);
    // never more than ROAM.most pixels tall close up, so a figure the camera has flown near stays a figure
    const far = Math.max(1, G.camera().position.distanceTo(mesh.position));
    const most = ROAM.most * 2 * far * Math.tan((G.camera().fov || 50) * Math.PI / 360)
      / Math.max(1, G.renderer().domElement.clientHeight) / 1.6;
    if (mesh.scale.x > most) mesh.scale.multiplyScalar(most / mesh.scale.x);
    // which way it faces: what it looks at, or the way it goes; turned by a flourish's spin and tipped by a bow
    if (face) AHEAD.subVectors(face, mesh.position); else AHEAD.copy(figure.heading);
    if (turn) AHEAD.applyAxisAngle(THREE.Object3D.DEFAULT_UP, turn);
    orientAgent(mesh, AHEAD, CORNERS[m.corner]?.turn ?? 0.25, passed);
    if (bow) mesh.rotateX(bow);
    const top = figure.top || ROAM.speed * m.speed;
    const speed = figure.stage === 'circling' || figure.stage === 'flourish' ? figure.vel.length() : figure.speed;
    mesh.userData.update(passed, {busy: grown !== 1 ? 1 : 0,
      move: {speed: Math.min(1, speed / Math.max(1, top)), stride: figure.stride, state}});
  }
  cut3d(size, passed);
  mascot3d(data, size, passed);
  eyes3d(passed);  // the person watching through the mascot's eyes, `EYE`
  placeBubble();
}
/* The person's mascot, web_mascot: one of the characters, standing for the person on the map, never given to an agent
 * and never picked by a click. It goes to what the person selects, in its own way, and waits beside it, on the side
 * away from its name; when the person chats with an agent at work it goes to that agent and the two greet each other;
 * agents passing notice it. Left alone, it wanders now and then, web_mascot_mischief playful or chaotic, nudging a
 * node it passes, and dodges a pointer that chases it; calm, it only goes where it is needed. Once the page has been
 * left alone as long as the flow lasts, web_flow_seconds, it falls asleep where it is, and wakes with the person. It
 * moves by steering, setting off and arriving gently at its own pace, and with reduced motion it just stands there. */
const MASCOT = {glyph: null, mesh: null, motion: null, pos: new THREE.Vector3(), vel: new THREE.Vector3(),
  heading: new THREE.Vector3(0, 0, 1), stride: 0, clock: 0, state: 'idle', greeted: null, wander: null, nextWander: 20,
  nudged: 0, dodge: null, pointer: {x: -1e4, y: -1e4, at: 0, speed: 0}, sleeping: false, most: 64};
const ASIDE = new THREE.Vector3(), UPWARD = new THREE.Vector3(), FACEAT = new THREE.Vector3();
/* web_mascot is the person's preferred character, the one the body picker suggests first; it draws nothing. The
 * mascot is the person's system agent once it has a body: no figure is on the map until the system agent offers to
 * take one and the person accepts, or the person gives it one. It is drawn while that conversation runs, and a
 * resumed conversation, the same session again, comes back in the same body; a new one is offered a body afresh. */
const preferredGlyph = () => { const chosen = WS.view().mascot; return GLYPHS.includes(chosen) ? chosen : null; };
function mascotGlyph() {
  const ticket = (S.tickets || []).find(isSystemTalk);
  const held = ticket ? BODIES.chosen[bodyKey(ticket.id)] : null;
  if (!held || !GLYPHS.includes(held.glyph)) return null;
  const live = D.sessions.filter(one => one.work_id === ticket.id && one.state === 'running').at(-1);
  return live && (!held.session || held.session === live.session_id) ? held.glyph : null;
}
/* The mascot as it is drawn: its body while its conversation runs, then, once that ends, the same body walking home
 * for a few seconds before it goes; with reduced motion it goes at once. */
const MASCOT_GONE = {glyph: null, since: 0};
function mascotFigure() {
  const glyph = mascotGlyph();
  if (glyph) { Object.assign(MASCOT_GONE, {glyph, since: 0}); return {glyph, leaving: false}; }
  if (!MASCOT_GONE.glyph) return {glyph: null, leaving: false};
  if (!MASCOT_GONE.since) MASCOT_GONE.since = performance.now();
  if (reduced() || performance.now() - MASCOT_GONE.since > 7000) { MASCOT_GONE.glyph = null; return {glyph: null, leaving: false}; }
  return {glyph: MASCOT_GONE.glyph, leaving: true};
}
/* Who leads the mascot: its own will, wandering, following the selection and going where it is needed, by its
 * temper; or its system agent, through its body's verbs. Each verb holds it for DRIVE_HOLD after the last, or until
 * the agent's turn ends; web_take holds it longer, with a reason, until web_release. While the agent drives, the
 * person's selection waits for it, and nothing else sends the mascot anywhere. Let go, it takes up its own way again
 * from where it stands. */
const DRIVE_HOLD = 20000, DRIVE_TAKEN = 600000;
function mascotDriven() {
  const now = performance.now();
  if (!MASCOT.driven || now >= MASCOT.driven) { if (MASCOT.driven) releaseMascot(); return false; }
  if (!MASCOT.held && now - (MASCOT.drivenAt || 0) > 3000) {  // its turn has ended: the agent let it go
    const ticket = (S.tickets || []).find(isSystemTalk);
    const live = ticket && D.sessions.filter(one => one.work_id === ticket.id && one.state === 'running').at(-1);
    if (!live || live.activity !== 'working') { releaseMascot(); return false; }
  }
  return true;
}
function driveMascot(take = null) {
  const now = performance.now();
  if (take) MASCOT.held = {reason: take.reason || '', at: now};
  MASCOT.drivenAt = now;
  MASCOT.driven = Math.max(MASCOT.driven || 0, now + (MASCOT.held ? DRIVE_TAKEN : DRIVE_HOLD));
}
function releaseMascot() {
  Object.assign(MASCOT, {driven: 0, held: null, facing: null});
  if (MASCOT.call?.agent) MASCOT.call = null;  // where the agent sent it; what the person selected meanwhile is next
  wake3d(1500);
  if (typeof wake2d === 'function') wake2d();
}
const mischief = () => WS.view().mascot_mischief || 'playful';
function mascotAwake() {  // it keeps the 3D map drawing only while it is up and about
  return Boolean(MASCOT.mesh) && !reduced() && !MASCOT.sleeping;
}
function steer(body, want, passed, top, accel) {  // toward a place, as fast as it can still stop there gently
  TOWARD.subVectors(want, body.pos);
  const away = TOWARD.length(), speed = Math.min(top, Math.sqrt(2 * accel * Math.max(0, away - 0.05)));
  TOWARD.multiplyScalar(away > 1e-4 ? speed / away : 0);
  PULL.subVectors(TOWARD, body.vel);
  const most = accel * passed * 1.5;
  if (PULL.length() > most) PULL.setLength(most);
  body.vel.add(PULL);
  body.pos.addScaledVector(body.vel, passed);
  return away;
}
function besideNode(node, size, out) {  // beside a node on the screen's right, below where its name is drawn
  const camera = G.camera();
  ASIDE.setFromMatrixColumn(camera.matrixWorld, 0).normalize();
  UPWARD.setFromMatrixColumn(camera.matrixWorld, 1).normalize();
  // below and to the right, clear of the name drawn across the node
  return out.set(node.x, node.y, node.z).addScaledVector(ASIDE, ballOf(node) + size * 0.6).addScaledVector(UPWARD, -(ballOf(node) + size * 0.7));
}
/* Where a call sends the mascot: beside its node, or a viewpoint as far from it and as high as asked, facing it. */
function callSpot(data, size) {
  const node = nodeById(data, MASCOT.call?.node), call = MASCOT.call;
  if (!node || node.x === undefined) return null;
  if (call.distance == null && call.height == null) return {want: besideNode(node, size, SPOT), face: null};
  TOWARD.subVectors(MASCOT.pos, AT.set(node.x, node.y, node.z)).setY(0);
  if (TOWARD.lengthSq() < 1e-6) TOWARD.set(1, 0, 0);
  const want = SPOT.set(node.x, node.y + Number(call.height || 0), node.z)
    .addScaledVector(TOWARD.normalize(), Math.max(ballOf(node) + size, Number(call.distance ?? size * 3)));
  return {want, face: FACEAT.set(node.x, node.y, node.z)};
}
/* A wander of its own: anywhere in the scene around the map, not only beside a node, as its character moves there,
 * a flyer through the air, a swimmer through the water, a walker hopping or floating; now and then to a node. */
function wanderTo(data, size) {
  const nodes = data.nodes.filter(node => node.t === 'el' && node.x !== undefined);
  if (!nodes.length) return null;
  if (Math.random() < 0.35) return {id: nodes[Math.floor(Math.random() * nodes.length)].id, until: MASCOT.clock + 9};
  const low = [Infinity, Infinity, Infinity], high = [-Infinity, -Infinity, -Infinity];
  for (const node of nodes) [node.x, node.y, node.z].forEach((at, axis) => { low[axis] = Math.min(low[axis], at); high[axis] = Math.max(high[axis], at); });
  const point = new THREE.Vector3(...[0, 1, 2].map(axis => low[axis] - size * 2 + Math.random() * (high[axis] - low[axis] + size * 4)));
  return {point, until: MASCOT.clock + 9};
}
/* Its own mischief, by its temper: now and then a wander anywhere in the scene, rarer while it keeps the person
 * company beside a selection, and now and then a shove at a node, more often the more mischievous it is. Returns
 * whether it is on a wander now. */
function mischiefDue(data, size, m, keeping) {
  const chaotic = mischief() === 'chaotic';
  if (MASCOT.wander && MASCOT.clock > MASCOT.wander.until) MASCOT.wander = null;
  if (!MASCOT.wander && MASCOT.clock > MASCOT.nextWander) {
    MASCOT.wander = wanderTo(data, size);
    MASCOT.nextWander = MASCOT.clock + (chaotic ? 10 : 24) * (keeping ? 1.8 : 1) + Math.random() * 14;
  }
  if (!MASCOT.job && MASCOT.clock > (MASCOT.nextPush ?? 24 - 12 * m.temper)) {
    MASCOT.nextPush = MASCOT.clock + 70 - 55 * m.temper + Math.random() * 30;
    const free = data.nodes.filter(node => node.t === 'el' && node.x !== undefined && pushable(node));
    const pick = free[Math.floor(Math.random() * free.length)];
    if (pick) MASCOT.job = {kind: 'push', node: pick.id, dir: null, strength: 0.25 + 0.35 * m.temper, agent: false};
  }
  return Boolean(MASCOT.wander);
}
/* The node the person drags by hand, which the mascot never pushes or takes. */
const HANDDRAG = {node: null};
const pushable = node => node && node.id !== S.selected && node !== HANDDRAG.node && node.fx === undefined && !CUT.job;
/* A node the mascot holds, pinned where it carries it; one at a time. Let go, it goes back to the layout, which
 * settles round it. Only the layout's positions change, as when the person drags a node: never the map. */
function dropHeld() {
  const held = MASCOT.holding;
  if (!held) return;
  MASCOT.holding = null;
  Object.assign(held, {fx: undefined, fy: undefined, fz: undefined});
  if (G) { G.d3VelocityDecay(DRAG_FRICTION).d3ReheatSimulation(); setTimeout(() => G?.d3VelocityDecay(PHYS.decay), 1500); }
}
/* A shove: a kick of speed along `dir`, capped so the map is never flung apart; its joins pull its neighbours after
 * it and the layout settles, against more friction for a moment so it follows gently. Under reduced motion the node
 * is simply where the shove leaves it. */
function shove(node, dir, strength, size) {
  const kick = Math.min(1, Math.max(0.05, strength)) * size * 1.2;
  if (reduced()) { node.x += dir.x * kick * 2.5; node.y += dir.y * kick * 2.5; node.z += dir.z * kick * 2.5; }
  else { node.vx = (node.vx || 0) + dir.x * kick; node.vy = (node.vy || 0) + dir.y * kick; node.vz = (node.vz || 0) + dir.z * kick; }
  nudgeNode(node, 0.12);
  G.d3VelocityDecay(DRAG_FRICTION).d3ReheatSimulation();
  setTimeout(() => G?.d3VelocityDecay(PHYS.decay), 1500);
}
/* What the mascot is doing with its body, `MASCOT.job`: going to a point, pushing a node, or carrying one. Returns
 * where it steers this frame, or null once the job is done. A job of the agent's runs while the agent drives. */
function mascotJob(data, size, passed) {
  const job = MASCOT.job;
  if (job.kind === 'move') {
    const node = job.node ? nodeById(data, job.node) : null;
    const want = node && node.x !== undefined ? besideNode(node, size, SPOT) : job.point ? SPOT.copy(job.point) : null;
    if (!want || MASCOT.pos.distanceTo(want) < size * 0.3 && !job.agent) { MASCOT.job = null; return null; }
    return {want, fast: 1};
  }
  const node = nodeById(data, job.node);
  if (!node || node.x === undefined || (!job.agent && !pushable(node) && MASCOT.holding !== node)) { MASCOT.job = null; return null; }
  AT.set(node.x, node.y, node.z);
  if (job.kind === 'push') {
    // from the side away from where it shoves, then a run at it; its own shoves go wherever it came from
    const dir = job.dir ? new THREE.Vector3(...job.dir) : TOWARD.subVectors(AT, MASCOT.pos).normalize().clone();
    if (dir.lengthSq() < 1e-6) dir.set(1, 0, 0);
    dir.normalize();
    const reach = ballOf(node) + size * 0.5;
    if (!job.charging) {
      const start = SPOT.copy(AT).addScaledVector(dir, -(reach + size * 1.5));
      if (MASCOT.pos.distanceTo(start) < size * 0.6 || reduced()) job.charging = true;
      return {want: start, face: FACEAT.copy(AT), fast: 1};
    }
    if (MASCOT.pos.distanceTo(AT) <= reach * 1.15 || reduced()) {
      shove(node, dir, job.strength ?? 0.5, size);
      MASCOT.hello = MASCOT.clock;  // a little hop as it lands the shove
      MASCOT.job = job.agent ? {kind: 'move', point: MASCOT.pos.clone(), agent: true} : null;
      return {want: SPOT.copy(MASCOT.pos), face: FACEAT.copy(AT)};
    }
    return {want: SPOT.copy(AT), face: FACEAT.copy(AT), fast: 1.8};
  }
  if (job.kind === 'drag') {
    if (MASCOT.holding !== node) {  // to it first, then it takes hold
      const grip = besideNode(node, size, SPOT);
      if (MASCOT.pos.distanceTo(grip) > size * 0.7 && !reduced()) return {want: grip, face: FACEAT.copy(AT)};
      dropHeld();
      MASCOT.holding = node;
      job.offset = new THREE.Vector3().subVectors(AT, MASCOT.pos);
      G.d3VelocityDecay(DRAG_FRICTION);
    }
    const beside = job.beside ? nodeById(data, job.beside) : null;
    const to = beside && beside.x !== undefined ? new THREE.Vector3(beside.x, beside.y, beside.z).addScaledVector(
      TOWARD.subVectors(AT, new THREE.Vector3(beside.x, beside.y, beside.z)).normalize(), ballOf(beside) + ballOf(node) + size)
      : job.point ? new THREE.Vector3(...job.point) : null;
    const want = to ? SPOT.copy(to).sub(job.offset) : SPOT.copy(MASCOT.pos);
    if (reduced()) MASCOT.pos.copy(want);
    // the node rides along with it, pinned where it carries it, and the map follows through its joins
    const at = AT.copy(MASCOT.pos).add(job.offset);
    Object.assign(node, {fx: at.x, fy: at.y, fz: at.z});
    G.d3ReheatSimulation();
    return {want, face: null, fast: 0.8};
  }
  MASCOT.job = null;
  return null;
}
/* Who leads it, shown quietly: a faint ring at its feet while its agent drives it. */
function ringMascot(size, on) {
  if (!MASCOT.mesh) return;
  if (!MASCOT.ring) {
    MASCOT.ring = new THREE.Mesh(new THREE.RingGeometry(0.42, 0.5, 40), new THREE.MeshBasicMaterial({
      color: new THREE.Color(css('--signal')), transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide}));
    MASCOT.ring.rotation.x = -Math.PI / 2;
    MASCOT.ring.raycast = () => {};
  }
  if (MASCOT.ring.parent !== MASCOT.mesh) MASCOT.mesh.add(MASCOT.ring);
  const material = MASCOT.ring.material;
  material.opacity += ((on ? 0.45 : 0) - material.opacity) * 0.12;  // eased in and out
  MASCOT.ring.visible = material.opacity > 0.01;
}
function mascot3d(data, size, passed) {
  const {glyph, leaving} = mascotFigure();
  reserveGlyph(glyph);
  if (MASCOT.mesh && MASCOT.glyph !== glyph) { dropHeld(); G.scene().remove(MASCOT.mesh); MASCOT.mesh = null; MASCOT.job = null; }
  const home = primaryOf(data);
  if (!glyph || !size || !home || home.x === undefined) return;
  if (!MASCOT.mesh && leaving) return;  // a conversation that ended before its body was drawn: nothing to walk home
  if (!MASCOT.mesh) {
    const mesh = createAgent(glyph);
    mesh.traverse(object => { object.raycast = () => {}; });  // never in the way of a click
    mesh.userData.motion = MASCOT.motion = motionOf(glyph, 'mascot');
    G.scene().add(mesh);
    Object.assign(MASCOT, {glyph, mesh, clock: 0, greeted: null, wander: null, fade: undefined, ring: null});
    besideNode(home, size, MASCOT.pos);
    MASCOT.vel.set(0, 0, 0);
  }
  const m = MASCOT.motion, mesh = MASCOT.mesh, now = performance.now();
  m.temper = {calm: 0.1, playful: 0.6, chaotic: 0.95}[mischief()] ?? 0.6;  // its own temper, web_mascot_mischief
  MASCOT.clock += passed;
  // as large as an agent with the whole map in view, and never more than MASCOT.most pixels tall close up
  const camera = G.camera(), far = Math.max(1, camera.position.distanceTo(MASCOT.pos));
  const perPixel = 2 * far * Math.tan((camera.fov || 50) * Math.PI / 360) / Math.max(1, G.renderer().domElement.clientHeight);
  mesh.scale.setScalar(Math.min(size * 0.95, MASCOT.most * perPixel / 1.6));
  // where it goes: an agent the person chats with, what the person selected, a wander of its own, or home
  const chatting = !$('#helpdesk')?.hidden && DOCK.target ? ROAM.figures.get(DOCK.target) : null;
  const selected = S.selected ? nodeById(data, S.selected) : null;
  let want = null, face = null, state = 'idle', fast = 1, spin = 0, puff = 1;
  const driven = !leaving && mascotDriven();
  MASCOT.sleeping = !leaving && !driven && now - FRAMES.active > FRAMES.idle + 2500 && !MASCOT.call && !CUT.job && !MASCOT.job;
  if (MASCOT.call && now > MASCOT.call.until) MASCOT.call = null;
  const job = !leaving && MASCOT.job && (driven || !MASCOT.job.agent) ? mascotJob(data, size, passed) : null;
  if (MASCOT.job?.agent && !driven) { dropHeld(); MASCOT.job = null; }  // let go: what the agent had it do ends
  const mending = leaving || driven || job ? null : mascotForCut(size);  // an edge the person cut, `CUT`
  ringMascot(size, driven);  // a faint ring at its feet while its agent leads it
  if (leaving) {  // its conversation has ended: it walks home and goes
    want = besideNode(home, size, SPOT);
    // home, it shrinks away on the leaving curve and is gone
    if (MASCOT.pos.distanceTo(want) < size * 0.6) MASCOT.fade = Math.max(0, (MASCOT.fade ?? 1) - passed * 2.2);
    if (MASCOT.fade === 0) MASCOT_GONE.glyph = null;
    else if (MASCOT.fade !== undefined) puff = Math.max(0.01, 1 - easeBoth(1 - MASCOT.fade));
  } else if (job) {
    ({want = null, face = null, fast = 1} = job);
  } else if (driven) {  // its system agent leads it: where it was sent, or it stays where it was taken
    const spot = MASCOT.call?.agent ? callSpot(data, size) : null;
    if (spot) ({want, face = null} = spot); else want = SPOT.copy(MASCOT.pos);
  } else if (mending) {
    ({want = null, fast = 1, spin = 0, puff = 1} = mending);
    if (mending.face) face = mending.face;
    if (mending.stomp) { state = 'cross'; MASCOT.stride += passed * m.stride * 2.2; }
  } else if (MASCOT.call?.node && !MASCOT.call.agent) {  // calling the person's attention, `ATTN`
    const spot = callSpot(data, size);
    if (spot) ({want, face = null} = spot);
  } else if (now - FRAMES.active > FRAMES.idle) {
    state = 'sleep';
  } else if (chatting && chatting.mesh) {
    want = SPOT.copy(chatting.mesh.position).addScaledVector(ASIDE.setFromMatrixColumn(G.camera().matrixWorld, 0), size * 1.8);
    face = chatting.mesh.position;
    if (MASCOT.greeted !== chatting.id && MASCOT.pos.distanceTo(want) < size * 1.5) {  // they greet each other
      MASCOT.greeted = chatting.id;
      MASCOT.hello = MASCOT.clock;
      chatting.glance = {other: 'mascot', until: chatting.clock + 1.6};
    }
  } else if (mischief() !== 'calm' && mischiefDue(data, size, m, Boolean(selected))) {  // off on a wander of its own
    const node = MASCOT.wander?.id && nodeById(data, MASCOT.wander.id);
    want = MASCOT.wander?.point ? SPOT.copy(MASCOT.wander.point) : besideNode(node && node.x !== undefined ? node : home, size, SPOT);
  } else if (selected && selected.x !== undefined) {
    want = besideNode(selected, size, SPOT);
  } else want = besideNode(home, size, SPOT);
  if (reduced()) {  // it just stands there
    if (want) MASCOT.pos.copy(want);
    mesh.position.copy(MASCOT.pos);
    mesh.userData.update(0, {move: {speed: 0, stride: 0, state: 'idle'}});
    return;
  }
  // a pointer that chases it: it hops aside
  if (MASCOT.dodge && MASCOT.clock < MASCOT.dodge.until && want) want = SPOT.copy(want).add(MASCOT.dodge.by);
  const top = ROAM.speed * m.speed * 0.9 * fast * strokeOf(m, MASCOT.stride).pace, accel = ROAM.accel * m.accel * fast;
  if (state !== 'sleep' && want) steer(MASCOT, want, passed, top, accel);
  else MASCOT.vel.multiplyScalar(Math.exp(-passed * 4));
  mesh.position.copy(MASCOT.pos);
  const speed = MASCOT.vel.length();
  MASCOT.stride += speed * passed / size;
  if (m.go === 'hop' && speed < size * 0.3 && state !== 'sleep' && Math.sin(MASCOT.clock * 0.5) > 0.4) MASCOT.stride += passed * m.stride * 0.8;
  if (MASCOT.hello && MASCOT.clock - MASCOT.hello < 1.2) MASCOT.stride += passed * m.stride * 1.5;  // a little hop of hello
  if (MASCOT.speaking) { MASCOT.stride += passed * m.stride * 1.1; puff = 1 + 0.04 * Math.sin(MASCOT.clock * 18); }  // talking
  // what its system agent asks of it, `mascotEvent`: a way to face, a turn and a gesture toward a part, a feeling shown
  if (MASCOT.facing && now < (MASCOT.driven || 0)) {  // an explicit turn wins over the viewpoint's own
    const toward = MASCOT.facing.node ? nodeById(data, MASCOT.facing.node) : null;
    if (toward && toward.x !== undefined) face = AT.set(toward.x, toward.y, toward.z);
    else if (MASCOT.facing.dir) face = AT.copy(MASCOT.pos).add(MASCOT.facing.dir);
  }
  const pointing = MASCOT.point && MASCOT.clock - MASCOT.point.at < MASCOT.point.long ? nodeById(data, MASCOT.point.node) : null;
  if (pointing && pointing.x !== undefined) { face = AT.set(pointing.x, pointing.y, pointing.z); MASCOT.stride += passed * m.stride * 0.6; }
  const feeling = MASCOT.emote && MASCOT.clock - MASCOT.emote.at < MASCOT.emote.long ? MASCOT.emote : null;
  if (feeling) {
    const u = (MASCOT.clock - feeling.at) / feeling.long;
    if (feeling.kind === 'wave') { spin = Math.sin(u * Math.PI * 6) * 0.35; MASCOT.stride += passed * m.stride * 0.8; }
    else if (feeling.kind === 'celebrate') { spin = easeBoth(u) * Math.PI * 2; MASCOT.stride += passed * m.stride * 2; puff = 1 + 0.12 * Math.sin(Math.PI * u); }
    else if (feeling.kind === 'shrug') puff = 1 + 0.06 * Math.sin(Math.PI * u);
    else if (feeling.kind === 'think') { spin = Math.sin(u * Math.PI) * 0.5; face = face || G.camera().position; }
    else if (feeling.kind === 'sleep') state = 'sleep';
  }
  // light mischief: a node it passes sways
  if (mischief() !== 'calm' && speed > size && MASCOT.clock > MASCOT.nudged) {
    const brush = data.nodes.find(node => node.t === 'el' && node.x !== undefined
      && MASCOT.pos.distanceTo(AT.set(node.x, node.y, node.z)) < ballOf(node) + size * 0.8);
    if (brush) { nudgeNode(brush, 0.06); MASCOT.nudged = MASCOT.clock + (mischief() === 'chaotic' ? 3 : 8); }
  }
  if (speed > 1e-2) MASCOT.heading.lerp(AHEAD.copy(MASCOT.vel).normalize(), 0.25);
  AHEAD.copy(face ? TOWARD.subVectors(face, MASCOT.pos) : MASCOT.heading);
  if (!face && speed < size * 0.2 && state !== 'sleep' && !EYE.view && !EYE.saved)  // at rest it half turns to the person
    AHEAD.lerp(TOWARD.subVectors(G.camera().position, MASCOT.pos).normalize(), 0.5);
  if (spin) AHEAD.applyAxisAngle(THREE.Object3D.DEFAULT_UP, spin);
  orientAgent(mesh, AHEAD, spin ? 0.6 : 0.15, passed);
  if (puff !== 1) mesh.scale.multiplyScalar(puff);
  markTrail(MASCOT, size);
  mesh.userData.update(passed, {move: {speed: Math.min(1, speed / Math.max(1, top)), stride: MASCOT.stride, state}});
}
// the pointer over the 3D map: where it is and how fast it moves, so the mascot can dodge one that chases it
$('#stage').addEventListener('pointermove', event => {
  const pointer = MASCOT.pointer, now = performance.now(), passed = Math.max(1, now - pointer.at);
  pointer.speed = Math.hypot(event.clientX - pointer.x, event.clientY - pointer.y) / passed;
  Object.assign(pointer, {x: event.clientX, y: event.clientY, at: now});
  if (!MASCOT.mesh || !G || mischief() === 'calm' || pointer.speed < 0.8) return;
  const area = G.renderer().domElement.getBoundingClientRect(), at = SPOT.copy(MASCOT.mesh.position).project(G.camera());
  const x = area.left + (at.x + 1) / 2 * area.width, y = area.top + (1 - at.y) / 2 * area.height;
  if (Math.hypot(x - event.clientX, y - event.clientY) > 60 || (MASCOT.dodge && MASCOT.clock < MASCOT.dodge.until)) return;
  ASIDE.setFromMatrixColumn(G.camera().matrixWorld, 0);
  MASCOT.dodge = {until: MASCOT.clock + 1.4, by: ASIDE.clone().multiplyScalar((x < event.clientX ? -1 : 1) * ROAM.drawn * 2.5)};
  MASCOT.stride += MASCOT.motion.stride * 0.5;
  wake3d();
}, {passive: true});
/* A word bubble over the mascot, in 3D and 2D: a short line in its voice, eased in and out, placed over the figure
 * each frame so it reads at any angle; one at a time, never piled up. `say` shows one for a while; a click on it does
 * what `onClick` says. */
const BUBBLE = {el: null, text: '', until: 0, click: null};
function bubble() {
  if (BUBBLE.el) return BUBBLE.el;
  BUBBLE.el = h('div', {class: 'mascot-bubble', role: 'status', 'aria-live': 'polite'});
  BUBBLE.el.addEventListener('click', event => { event.stopPropagation(); const act = BUBBLE.click; if (act) { hush(); act(); } });
  document.body.append(BUBBLE.el);
  return BUBBLE.el;
}
function say(text, seconds = 4, onClick = null, who = null, name = '') {  // `who`: an embodied agent's figure, else the mascot
  const el = bubble();
  el.dataset.name = name;  // the agent speaking through it, named quietly over its words; its own words go unnamed
  Object.assign(BUBBLE, {text, until: performance.now() + seconds * 1000, click: onClick, who});
  el.textContent = text;
  el.classList.toggle('clickable', Boolean(onClick));
  el.classList.add('on');
  wake3d(seconds * 1000);
}
function hush() { BUBBLE.until = 0; BUBBLE.el?.classList.remove('on'); }
function placeBubble() {  // over the mascot as it is drawn: the large map's figure, else the 2D one
  if (!BUBBLE.el) return;
  if (performance.now() > BUBBLE.until) { BUBBLE.el.classList.remove('on'); return; }
  let x = null, y = null;
  const speaker = (BUBBLE.who && ROAM.figures.get(BUBBLE.who)?.mesh) || MASCOT.mesh;  // the figure that speaks
  if (G && speaker) {
    const area = G.renderer().domElement.getBoundingClientRect(), at = SPOT.copy(speaker.position).project(G.camera());
    if (area.width && Math.abs(at.z) < 1) { x = area.left + (at.x + 1) / 2 * area.width; y = area.top + (1 - at.y) / 2 * area.height - onScreen(speaker) * 0.6; }
  }
  if (x === null && MASCOT2D.g?.isConnected) {
    const box = MASCOT2D.g.getBoundingClientRect();
    if (box.width) { x = box.left + box.width / 2; y = box.top; }
  }
  if (x === null) { BUBBLE.el.classList.remove('on'); return; }
  BUBBLE.at = {x, y};
  BUBBLE.el.style.left = `${Math.round(x)}px`;
  BUBBLE.el.style.top = `${Math.round(y)}px`;
}
/* Cut an edge, VIEW-005, a playful mode of the 3D map: X turns scissors on, and a click cuts the join edge the pointer
 * marks, the edge the page's own picking chooses, `EDGE_PICK`. The edge snaps, its halves whipping back, and whatever
 * has lost its way back to the map's primary node through the joins and namespace links left falls: the group hangs
 * together on its strings like a mobile, swinging as it drops, and lands softly at the foot of the view. The mascot
 * notices, runs over in its own gait, is cross with the person in its own words, picks up the loose end, carries it
 * back with the rest dangling from it, reties the edge with a little flourish, and everything springs back into place.
 * Nearby agents glance over. It is all drawn: no join is changed and nothing is written. Escape, or X again, puts
 * everything back at once. With reduced motion the cut and the repair happen without the swing or the run. */
const CUT = {on: false, job: null, saved: null};
const CROSS = {jelly: 'Hey! I felt that one in every tentacle.', gearling: 'Clunk! That was load-bearing.',
  kite: 'You cut my string! Rude.', moth: 'Who turned off that light?!', drone: 'Delivery interrupted. Not cool.',
  snail: 'I am going as fast as I can, and you do this?', crystal: 'That join was flawless. Was.',
  wisp: 'Ooh, that sent a chill right through me.', comet: 'Whoa! Did you see that fall?', beetle: 'Hmph. I will push it back.',
  slime: 'Splat. Really? Really?', plane: 'Mayday! Mayday! Who did that?', puffer: 'I am puffed up and I am not happy.',
  owl: 'Whoo cut that? Hoo-hum. I saw you.', cubebot: 'ERROR: edge severed. Fixing your mess.',
  mushroom: 'Stomp! That was holding things up!', seahorse: 'Now I have to tie that with my tail.'};
function cutMode(on) {
  if (!G) return;
  if (!on) restoreCut();
  CUT.on = on;
  $('#stage').classList.toggle('scissors', on);
  if (on) say('Scissors out. Careful…', 2.2);
  wake3d();
}
function restoreCut() {  // everything back where it was, at once
  const saved = CUT.saved;
  CUT.job = null;
  if (!saved) return;
  for (const [node, place] of saved.nodes) Object.assign(node, place);
  for (const link of saved.hidden) if (link.__lineObj) link.__lineObj.visible = true;
  // the layout stops where everything was, with no warmth left to move it and no fit of the view after
  const decay = G.d3AlphaDecay();
  G.d3AlphaDecay(1).d3AlphaMin(0.001).cooldownTime(saved.cooldown);
  V3.ticks = 0;
  setTimeout(() => G?.d3AlphaDecay(decay), 400);
  CUT.saved = null;
  wake3d();
}
function supportedFrom(data, start, cut) {  // what still reaches the primary node through the links left
  const near = new Map(), add = (one, two) => { if (!near.has(one)) near.set(one, []); near.get(one).push(two); };
  for (const link of data.links) {
    if (cut.has(link) || typeof link.source !== 'object') continue;
    add(link.source, link.target); add(link.target, link.source);
  }
  const held = new Set([start]), queue = [start];
  while (queue.length) for (const next of near.get(queue.shift()) || []) if (!held.has(next)) { held.add(next); queue.push(next); }
  return held;
}
function cutLink(link) {
  const data = G.graphData(), home = primaryOf(data);
  if (!link || !home || CUT.job) return;
  // the layout holds every node where it is; the page moves the fallen ones itself, through where they are held
  if (!CUT.saved) {
    CUT.saved = {nodes: new Map(data.nodes.map(node => [node, {x: node.x, y: node.y, z: node.z, fx: node.fx, fy: node.fy, fz: node.fz,
      vx: 0, vy: 0, vz: 0}])), hidden: [], cooldown: G.cooldownTime()};
    for (const node of data.nodes) Object.assign(node, {fx: node.x, fy: node.y, fz: node.z});
    G.cooldownTime(Infinity).d3AlphaMin(0);
    G.d3ReheatSimulation();
  }
  CUT.saved.hidden.push(link);
  if (link.__lineObj) link.__lineObj.visible = false;
  const held = supportedFrom(data, home, new Set([link]));
  const loose = held.has(link.source) ? link.target : link.source, anchor = loose === link.source ? link.target : link.source;
  const falling = data.nodes.filter(node => !held.has(node) && node.x !== undefined);
  const span = Math.max(40, sizeOf(data) / ROAM.share);
  CUT.job = {link, loose: falling.includes(loose) ? loose : null, anchor, falling, at: performance.now() / 1000, stage: 'fall',
    clock: 0, span, ropes: data.links.filter(one => typeof one.source === 'object' && falling.includes(one.source) && falling.includes(one.target)
      && one !== link).map(one => ({one: one.source, two: one.target, long: Math.hypot(one.source.x - one.target.x,
      one.source.y - one.target.y, one.source.z - one.target.z)})),
    bodies: new Map(falling.map((node, index) => [node, {x: node.x, y: node.y, z: node.z, px: node.x, py: node.y, pz: node.z,
      drag: 0.985 - (index % 3) * 0.006, home: {x: node.x, y: node.y, z: node.z}}])),
    ends: [{x: link.source.x, y: link.source.y, z: link.source.z}, {x: link.target.x, y: link.target.y, z: link.target.z}]};
  // the agents nearby look over
  for (const figure of ROAM.figures.values()) figure.glance = {other: 'cut', until: figure.clock + 1.5};
  if (reduced()) for (const [node, body] of CUT.job.bodies) { body.y = floorAt(body) + ballOf(node); body.py = body.y; }
  wake3d(20000);
}
function floorAt(at) {  // the foot of the view, at the depth of a point
  const camera = G.camera();
  SPOT.set(at.x, at.y, at.z).project(camera);
  SPOT.set(0, -0.86, SPOT.z).unproject(camera);
  return SPOT.y;
}
/* Each frame of a cut: the fall and its swing, the mascot's run, its cross words, the carry, the knot and the spring
 * back, with the halves of the cut edge whipping back as it snaps. */
function cut3d(size, passed) {
  const job = CUT.job;
  if (!job) return;
  job.clock += passed;
  if (!MASCOT.mesh) mascotForCut(size);  // with no mascot the cut mends itself
  const g = job.span * 1.4, steps = 3;
  // the fallen group: verlet bodies under gravity, its own strings holding it together, landing softly
  if (job.stage !== 'spring') {
    for (const [node, body] of job.bodies) {
      if (job.carried === node) continue;
      if (reduced()) continue;
      const vx = (body.x - body.px) * body.drag, vy = (body.y - body.py) * body.drag, vz = (body.z - body.pz) * body.drag;
      Object.assign(body, {px: body.x, py: body.y, pz: body.z});
      body.x += vx; body.y += vy - g * passed * passed; body.z += vz;
      const floor = floorAt(body.home) + ballOf(node);
      if (body.y < floor) { body.y = floor; body.py = floor + (body.y - body.py) * -0.25; body.px = body.x - vx * 0.6; body.pz = body.z - vz * 0.6; }
    }
    if (job.carried) {  // the loose end rides above the mascot, and the rest dangles from it
      const at = job.bodies.get(job.carried);
      Object.assign(at, {x: MASCOT.pos.x, y: MASCOT.pos.y + size * 1.1, z: MASCOT.pos.z});
      Object.assign(at, {px: at.x, py: at.y, pz: at.z});
    }
    for (let round = 0; round < steps; round++) for (const rope of job.ropes) {  // a string pulls only when taut
      const one = job.bodies.get(rope.one), two = job.bodies.get(rope.two);
      const dx = two.x - one.x, dy = two.y - one.y, dz = two.z - one.z, long = Math.hypot(dx, dy, dz);
      if (long <= rope.long || long < 1e-6) continue;
      const fix = (long - rope.long) / long / 2, pinOne = job.carried === rope.one, pinTwo = job.carried === rope.two;
      const a = pinOne ? 0 : pinTwo ? 2 : 1, b = pinTwo ? 0 : pinOne ? 2 : 1;
      one.x += dx * fix * a; one.y += dy * fix * a; one.z += dz * fix * a;
      two.x -= dx * fix * b; two.y -= dy * fix * b; two.z -= dz * fix * b;
    }
  } else {  // everything springs back into place
    const u = Math.min(1, (job.clock) / 1.1), k = 1 - Math.exp(-u * 6) * Math.cos(u * 5);
    for (const body of job.bodies.values()) {
      body.x = body.from.x + (body.home.x - body.from.x) * k;
      body.y = body.from.y + (body.home.y - body.from.y) * k;
      body.z = body.from.z + (body.home.z - body.from.z) * k;
    }
    if (u >= 1) { restoreCut(); return; }
  }
  for (const [node, body] of job.bodies) Object.assign(node, {fx: body.x, fy: body.y, fz: body.z, x: body.x, y: body.y, z: body.z});
  // the halves of the cut edge whip back to their ends as it snaps
  const snap = Math.min(1, job.clock / 0.55);
  if (snap < 1 && !reduced()) {
    const back = 1 - (1 + 2.2 * Math.pow(snap - 1, 3) + 1.2 * Math.pow(snap - 1, 2)), color = tintOf(linkColor(job.link));
    const [a, b] = [job.link.source, job.link.target], mid = {x: (job.ends[0].x + job.ends[1].x) / 2,
      y: (job.ends[0].y + job.ends[1].y) / 2, z: (job.ends[0].z + job.ends[1].z) / 2};
    for (const end of [a, b]) {
      const tip = {x: end.x + (mid.x - end.x) * back, y: end.y + (mid.y - end.y) * back, z: end.z + (mid.z - end.z) * back};
      fxLine(end, tip, color, 0.9, 0.5);
    }
  }
  if (job.carried) fxLine(job.anchor, job.carried, tintOf(linkColor(job.link)), 0.8, 0.8);  // the loose end in hand
}
/* What the mascot does about a cut, `mascot3d` asks it each frame: where it goes, what it faces, and how it moves. */
function mascotForCut(size) {
  const job = CUT.job;
  if (!job) return null;
  const loose = job.loose ? job.bodies.get(job.loose) : null;
  if (!mascotGlyph() || !MASCOT.mesh || !loose) {  // no mascot, or nothing fell: it springs back by itself
    if (job.stage === 'fall' && job.clock > 2.4) startSpring(job);
    return null;
  }
  if (job.stage === 'fall' && job.clock > (reduced() ? 0.2 : 0.7)) Object.assign(job, {stage: 'run', clock: 0});
  if (job.stage === 'run') {
    if (reduced() || MASCOT.pos.distanceTo(AT.set(loose.x, loose.y, loose.z)) < size * 1.6) {
      Object.assign(job, {stage: 'cross', clock: 0});
      say(CROSS[MASCOT.glyph] || 'Hey! Who cut that?', 2.8);
    }
    return {want: SPOT.set(loose.x + size, loose.y, loose.z), fast: 1.7};
  }
  if (job.stage === 'cross') {  // it stomps and puffs up, facing the person
    if (job.clock > 2.4) Object.assign(job, {stage: 'carry', clock: 0, carried: job.loose});
    return {want: null, face: G.camera().position, stomp: true, puff: 1 + 0.12 * Math.max(0, Math.sin(job.clock * 5))};
  }
  if (job.stage === 'carry') {  // back to where the loose end belongs, the rest dangling from it
    const home = job.bodies.get(job.loose).home;
    if (reduced() || MASCOT.pos.distanceTo(AT.set(home.x, home.y - size * 1.1, home.z)) < size * 0.5) {
      Object.assign(job, {stage: 'tie', clock: 0});
      say('There. Knotted.', 1.6);
    }
    return {want: SPOT.set(home.x, home.y - size * 1.1, home.z), fast: 0.8};
  }
  if (job.stage === 'tie') {  // a little knot flourish
    if (job.clock > 1 || reduced()) startSpring(job);
    return {want: null, spin: easeBoth(Math.min(1, job.clock)) * Math.PI * 2};
  }
  return null;
}
function startSpring(job) {
  job.carried = null;
  for (const body of job.bodies.values()) body.from = {x: body.x, y: body.y, z: body.z};
  for (const link of CUT.saved?.hidden || []) if (link.__lineObj) link.__lineObj.visible = true;
  Object.assign(job, {stage: 'spring', clock: reduced() ? 9 : 0});
}
document.addEventListener('keydown', event => {
  if (!G || event.ctrlKey || event.metaKey || event.altKey || event.target.closest?.('input, textarea, select, [contenteditable="true"]')) return;
  if (event.key === 'x' || event.key === 'X') cutMode(!CUT.on);
  else if ((event.key === 'e' || event.key === 'E') && MASCOT.mesh) mascotEyes();  // the mascot's eyes, and back
  else if (event.key === 'Escape' && CUT.on) { event.stopImmediatePropagation(); cutMode(false); }
}, true);
/* The mascot calls the person's attention, VIEW-005: when something needs them, an agent waiting for an answer, a
 * ticket done, a spinning or stuck agent, an intake finished or a merge to review, it goes there, says so in its
 * bubble, and brings a small note card into view, set down near the pointer, that takes the person to it on a click
 * and goes on its ×. Driven by what the page already reads as it happens, never by a model. It speaks rarely and
 * briefly: one call at a time, ATTN.gap apart, each thing once, at most ATTN.most waiting, the oldest dropped. */
const ATTN = {seen: new Set(), queue: [], last: 0, timer: 0, card: null, gap: 6000, most: 3, held: 25000};
function attend(key, text, node, open) {
  if (!mascotGlyph() || ATTN.seen.has(key)) return;
  ATTN.seen.add(key);
  ATTN.queue = [...ATTN.queue.filter(one => one.text !== text), {text, node, open}].slice(-ATTN.most);
  pumpAttention();
}
function pumpAttention() {
  clearTimeout(ATTN.timer);
  const wait = ATTN.last + ATTN.gap - Date.now();
  if (!ATTN.queue.length) return;
  if (wait > 0 || ATTN.card) { ATTN.timer = setTimeout(pumpAttention, Math.max(500, wait)); return; }
  const call = ATTN.queue.shift();
  ATTN.last = Date.now();
  // while its agent drives it the card still comes, but the mascot goes nowhere on its own
  if (!mascotDriven()) MASCOT.call = call.node ? {node: call.node, until: performance.now() + 9000} : null;
  wake3d(9000);
  say(call.text, 6, call.open);
  bringCard(call);
}
function bringCard(call) {  // a note card, carried from the mascot to near the pointer, eased in and out
  const card = ATTN.card = h('div', {class: 'mascot-card', role: 'alert'},
    h('button', {class: 'go', type: 'button', onclick: () => { done(); call.open?.(); }}, call.text),
    h('button', {class: 'x', type: 'button', title: 'Dismiss', 'aria-label': 'Dismiss', onclick: () => done()}, '×'));
  const from = BUBBLE.at || {x: innerWidth - 120, y: innerHeight - 80};
  const recent = performance.now() - MASCOT.pointer.at < 30000;
  const to = recent ? {x: Math.min(innerWidth - 160, Math.max(160, MASCOT.pointer.x + 24)), y: Math.min(innerHeight - 60, Math.max(80, MASCOT.pointer.y + 28))}
    : {x: innerWidth - 200, y: innerHeight - 140};
  Object.assign(card.style, {left: `${from.x}px`, top: `${from.y}px`});
  document.body.append(card);
  requestAnimationFrame(() => requestAnimationFrame(() => {
    card.classList.add('on');
    Object.assign(card.style, {left: `${to.x}px`, top: `${to.y}px`});
  }));
  const timer = setTimeout(() => done(), ATTN.held);
  function done() {
    clearTimeout(timer);
    card.classList.remove('on');
    setTimeout(() => card.remove(), 400);
    if (ATTN.card === card) ATTN.card = null;
    if (MASCOT.call?.node === call.node) MASCOT.call = null;
    pumpAttention();
  }
}
/* What needs the person now, read from what the page has just read: an agent waiting for them, one spinning or stuck,
 * and a merge waiting for review. A ticket done is told by `flowTickets`, an intake finished where the page learns it. */
function noticeAttention() {
  if (ASKING.pending) flushAsk();  // words to the system agent waiting for its session to start
  for (const one of D.asking || []) {
    const session = D.sessions.find(row => row.session_id === one.session_id);
    if (session) attend(`ask:${one.session_id}:${one.signal}:${one.key || ''}`, `${agentName(session.agent)} is waiting on you`,
      ticketOf(session.work_id) ? ticketNode(ticketOf(session.work_id)) : null, () => agentAt(session.work_id, session.session_id));
  }
  for (const one of D.signals || []) {
    if (one.active === false || !RESTLESS.includes(one.signal)) continue;
    const session = D.sessions.find(row => row.session_id === one.session_id && row.state === 'running');
    if (session) attend(`stuck:${one.session_id}:${one.signal}`, `${agentName(session.agent)} seems stuck`,
      ticketOf(session.work_id) ? ticketNode(ticketOf(session.work_id)) : null, () => agentAt(session.work_id, session.session_id));
  }
  for (const row of MERGE.rows || []) {
    const ticket = ticketOf(row.work_id);
    attend(`merge:${row.work_id}`, 'A merge is waiting for your review', ticket ? ticketNode(ticket) : null,
      () => takeReview(row.work_id, null));
  }
}
/* What the person's system agent, as the mascot, and every agent, as its figure, do on the page, VIEW-005: the web
 * module's verbs reach the page as `mascot` events with an id, and what they ask, what a figure sees, a picture from
 * its eyes, what the person is looking at, is answered to /api/mascot-result under that id. Every act shows on the
 * page as the mascot doing it: it walks to what it selects, gestures at what it opens, and says so in a word. */
function mascotEvent(payload) {
  if (!payload || payload.project !== S.project) return;
  const act = payload.act, node = nodeOfAddress(payload.address);
  const answer = result => payload.id && wrote('/api/mascot-result', {id: payload.id, result});
  if (act === 'see' || act === 'look') {  // the system agent looking through the mascot's eyes leads it too
    if (mascotGlyph() && (!payload.work || isSystemTalk(ticketOf(payload.work)))) driveMascot();
    return sight(payload, node, answer);
  }
  if (act === 'viewing') return answer(viewing());
  if (act === 'embody') return answer(payload.work ? embody(payload.work, payload.character, 'agent')
    : {error: 'Only an agent in a conversation can take a body: run it from that agent.'});
  const own = payload.work && ROAM.figures.get(payload.work)?.talk ? payload.work : null;  // an embodied agent's own figure
  // the body's acts need a body; the page's own acts, the camera, a tab, a pane, the maps, are done with or without one
  const bodily = ['say', 'go', 'turn', 'point', 'emote', 'move', 'push', 'drag', 'drop', 'take', 'release'].includes(act);
  const body = Boolean(mascotGlyph());
  if (bodily && !body && !own) {
    if (payload.id) answer({error: 'The mascot has no body on the map yet: it is drawn once your system agent has one.'});
    return;
  }
  // its system agent leads it now: autonomy pauses until the agent lets go, `mascotDriven`
  if (body && !own) driveMascot(act === 'take' ? {reason: String(payload.reason || '')} : null);
  const tell = (words, seconds = 2.4) => say(words, seconds);
  if (act === 'release') { releaseMascot(); dropHeld(); MASCOT.job = null; }
  else if (act === 'take') { if (payload.reason) say(String(payload.reason).slice(0, 140), 4, null, null, MASCOT.glyph || ''); }
  else if (act === 'say') say(String(payload.text || '').slice(0, 280), Math.min(12, 3 + String(payload.text || '').length / 18), null,
    own, own ? '' : MASCOT.glyph || '');  // an embodied agent speaks in its own bubble; the mascot's agent is named in it
  else if (act === 'go' && node) {
    MASCOT.call = {node, until: MASCOT.driven, distance: payload.distance, height: payload.height, agent: true};
    MASCOT.facing = null;
    MASCOT.job = null;
  }
  else if (act === 'move') {  // to a point, an address, or by a step relative to its heading
    const point = Array.isArray(payload.point) ? new THREE.Vector3(...payload.point.map(Number)) : null;
    const step = ['forward', 'right', 'up'].some(key => payload[key] != null) ? (() => {
      const ahead = MASCOT.heading.clone().setY(0).normalize(), side = new THREE.Vector3().crossVectors(ahead, THREE.Object3D.DEFAULT_UP).normalize();
      return MASCOT.pos.clone().addScaledVector(ahead, Number(payload.forward || 0)).addScaledVector(side, Number(payload.right || 0))
        .add(new THREE.Vector3(0, Number(payload.up || 0), 0));
    })() : null;
    MASCOT.call = null;
    MASCOT.job = {kind: 'move', node: point || step ? null : node, point: point || step, agent: true};
  }
  else if (act === 'push' && node) {
    const toward = payload.toward ? nodeOfAddress(payload.toward) : null, at = nodeById(G?.graphData() || {nodes: []}, node);
    const dir = {up: [0, 1, 0], down: [0, -1, 0]}[payload.direction] || (toward && at ? (() => {
      const other = nodeById(G.graphData(), toward);
      return other ? [other.x - at.x, other.y - at.y, other.z - at.z] : null;
    })() : null);
    MASCOT.call = null;
    MASCOT.job = {kind: 'push', node, dir, strength: Number(payload.strength ?? 0.5), agent: true};
  }
  else if (act === 'drag' && node) {
    MASCOT.call = null;
    if (MASCOT.holding && MASCOT.holding.id !== node) dropHeld();  // one node held at a time
    MASCOT.job = {kind: 'drag', node, point: Array.isArray(payload.point) ? payload.point.map(Number) : null,
      beside: payload.beside ? nodeOfAddress(payload.beside) : null, agent: true};
  }
  else if (act === 'drop') { dropHeld(); MASCOT.job = null; }
  else if (act === 'turn') turnMascot(node, payload.degrees);
  else if (act === 'point' && node) MASCOT.point = {node, at: MASCOT.clock, long: 2.4};
  else if (act === 'emote') MASCOT.emote = {kind: payload.emote, at: MASCOT.clock, long: payload.emote === 'sleep' ? 6 : 1.8};
  else if (act === 'select' && node) {  // it walks over, and the selection follows it
    if (body) MASCOT.call = {node, until: MASCOT.driven, agent: true};
    setTimeout(() => select(node, true), reduced() || !body ? 0 : 900);
  } else if (act === 'camera') {
    if (payload.mode) setMode3d(payload.mode);
    if (node) { MASCOT.point = {node, at: MASCOT.clock, long: 2}; fly3d(node, true); }
    tell(payload.mode ? `${payload.mode[0].toUpperCase()}${payload.mode.slice(1)} view.` : 'Over here.');
  } else if (act === 'tab') {
    showTab(payload.tab === 'provenance' ? 'prov' : payload.tab);
    MASCOT.emote = {kind: 'wave', at: MASCOT.clock, long: 1.2};
    tell(`The ${payload.tab} tab.`);
  } else if (act === 'open') opened(payload, tell);
  else if (act === 'swap') { swap(payload.large === '2d'); tell(`The ${payload.large.toUpperCase()} map, large.`); }
  else if (act === 'flow') { flowMode(payload.mode); if (typeof showFlow === 'function') showFlow(payload.mode); tell(`Flow: ${payload.mode}.`); }
  else if (act === 'physics') {
    if (PHYSICS.some(([name]) => name === payload.preset)) { applyPhysics(payload.preset); tell(`Physics: ${payload.preset}.`); }
    else tell(`I don't know the ${payload.preset} physics.`);
  }
  answer({done: true});
  wake3d(4000);
  wake2d();
}
function openFor(payload, tell) {  // what the agent opens on the page for the person
  if (payload.what === 'board') { if ($('#board').hidden) $('#boardBtn').click(); tell('The board.'); }
  else if (payload.what === 'settings') { openSettings(); tell('Settings.'); }
  else if (payload.what === 'pane' && payload.id && WS.on) { WS.reveal(payload.id); tell('There.'); }
  else if (payload.what === 'ticket' && payload.id) {  // its node, its work in the panel
    const ticket = ticketOf(payload.id);
    if (!ticket) return tell('I cannot find that ticket.');
    const node = ticketNode(ticket);
    MASCOT.call = {node, until: MASCOT.driven, agent: true};
    setTimeout(() => { select(node, true); showTab('object'); }, reduced() ? 0 : 900);
    tell(`Ticket on ${ticketPart(ticket)}.`);
  }
}
// an element by its address, or a join written receiver>provider, as the node the maps draw for it
function nodeOfAddress(address) {
  if (!address) return null;
  const [receiver, provider] = String(address).split('>').map(part => part.trim());
  if (provider) {
    const one = partAt(receiver)?.id, two = partAt(provider)?.id;
    const join = S.joins.find(item => item.receiver === one && item.providers.includes(two));
    return join ? 'p:' + join.id : null;
  }
  return partAt(receiver)?.id ?? null;
}
function turnMascot(node, degrees) {
  if (node) MASCOT.facing = {node};
  else if (Number.isFinite(Number(degrees))) {
    const by = -Number(degrees) * Math.PI / 180;  // right is clockwise seen from above
    MASCOT.facing = {dir: MASCOT.heading.clone().setY(0).normalize().applyAxisAngle(THREE.Object3D.DEFAULT_UP, by)};
  }
  MASCOT.driven = performance.now() + 120000;
}
/* Who sees: the calling agent's own figure, by the work its runner gave it, or else the person's mascot, which is the
 * system agent's figure and the person's. A refusal says why. */
function seer(work, role) {
  const figure = work ? ROAM.figures.get(work) : null;  // its own figure, an embodied conversation agent's too
  if (figure?.mesh) return {mesh: figure.mesh, who: figure.glyph, figure};
  if (role === 'system' && MASCOT.mesh) return {mesh: MASCOT.mesh, who: MASCOT.glyph, mascot: true};  // the person's own agent
  if (work && ticketOf(work)?.held && !isSystemTalk(ticketOf(work)))
    return {refuse: 'You have no body on the map yet: the person can give you one, or ask for one with web_embody.'};
  if (work && ticketOf(work) && !ticketOf(work).held) return {refuse: 'No figure is drawn for your ticket on this page yet: it walks onto the map once your session is working there.'};
  if (MASCOT.mesh) return {mesh: MASCOT.mesh, who: MASCOT.glyph, mascot: true};
  return {refuse: mascotGlyph() ? 'The mascot is not drawn yet: the 3D map is not open.' : 'No mascot is chosen: web_mascot is none.'};
}
/* A figure's eyes as a camera: at its eye anchor, facing its gaze, with its own field of view, `eyeOf`. */
const EYE = {camera: new THREE.PerspectiveCamera(68, 1.5, 0.05, 1e6), at: new THREE.Vector3(), dir: new THREE.Vector3(),
  look: new THREE.Vector3(), width: 768, height: 512, target: null, debug: false, view: false, saved: null, k: 0};
function eyeCamera(mesh, aspect = EYE.width / EYE.height) {
  eyeOf(mesh, EYE.at, EYE.dir);
  const camera = EYE.camera;
  camera.fov = mesh.userData.fov || 68;
  camera.aspect = aspect;
  camera.near = Math.max(0.01, mesh.scale.x * 0.05);
  camera.far = G.camera().far || 1e6;
  camera.position.copy(EYE.at);
  camera.up.set(0, 1, 0);
  camera.lookAt(EYE.look.copy(EYE.at).add(EYE.dir));
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld(true);
  return camera;
}
/* What a figure sees now: every element in its field of view, with how far, which way, whether something nearer hides
 * it, and whether it is selected or being worked; the figures in view; and the elements nearest it, seen or not. */
function seeFrom(mesh, camera) {
  const data = G.graphData(), eye = EYE.at, seen = [], near = [], figures = [];
  const balls = data.nodes.filter(node => node.x !== undefined && node.__threeObj?.visible !== false && shownNode(node));
  const hidden = (point, away, own) => balls.some(other => {  // a nearer node across the line of sight
    if (other === own) return false;
    AT.set(other.x, other.y, other.z);
    const along = TOWARD.subVectors(AT, eye).dot(SPOT.subVectors(point, eye).normalize());
    if (along <= 0 || along >= away - ballOf(own || other)) return false;
    return AT.distanceTo(PULL.copy(eye).addScaledVector(SPOT, along)) < ballOf(other);
  });
  const bearing = v => [v.x < -0.33 ? 'left' : v.x > 0.33 ? 'right' : 'ahead', v.y > 0.45 ? 'above' : v.y < -0.45 ? 'below' : null]
    .filter(Boolean).join(', ');
  for (const node of balls) {
    if (node.t !== 'el' && node.t !== 'purpose') continue;
    const point = new THREE.Vector3(node.x, node.y, node.z), away = point.distanceTo(eye), v = point.clone().project(camera);
    const join = node.t === 'purpose' ? joinOf(node.id) : null;
    const entry = {address: join ? `${partAddress(join.receiver)}>${partAddress(join.providers[0])}` : node.address,
      name: join ? (join.purpose || 'a join') : node.name, kind: join ? 'join' : 'element', distance: Math.round(away * 10) / 10,
      selected: S.selected === node.id, active: INUSE.parts.get(node.id) === true || Boolean(node.work?.length)
        || [...ROAM.figures.values()].some(figure => figure.target === node.id)};
    if (node.t === 'el') near.push(entry);
    if (v.z > -1 && v.z < 1 && Math.abs(v.x) <= 1 && Math.abs(v.y) <= 1)
      seen.push({...entry, bearing: bearing(v), visible: !hidden(point, away, node)});
  }
  for (const figure of [...ROAM.figures.values(), ...(MASCOT.mesh ? [{mesh: MASCOT.mesh, glyph: MASCOT.glyph, mascot: true}] : [])]) {
    if (figure.mesh === mesh) continue;
    const point = figure.mesh.position, v = point.clone().project(camera);
    if (v.z > -1 && v.z < 1 && Math.abs(v.x) <= 1 && Math.abs(v.y) <= 1)
      figures.push({character: figure.glyph, who: figure.mascot ? "the person's mascot" : `the agent on ${partAddress(figure.target) || 'its ticket'}`,
        distance: Math.round(point.distanceTo(eye) * 10) / 10, bearing: bearing(v)});
  }
  seen.sort((one, two) => one.distance - two.distance);
  near.sort((one, two) => one.distance - two.distance);
  const ahead = seen.filter(one => one.visible).sort((one, two) => (one.bearing === 'ahead' ? 0 : 1) - (two.bearing === 'ahead' ? 0 : 1))[0];
  return {fov: Math.round(camera.fov), facing: ahead?.address || null, in_view: seen, figures, nearest: near.slice(0, 6)};
}
const partAddress = id => S.elements.get(id)?.element.address || (String(id).startsWith('p:') ? joinOf(id)?.receiver_address : null) || null;
/* A picture from a figure's eyes, the scene as the page draws it, everything a module adds to it included, the figure
 * itself left out: a PNG, EYE.width by EYE.height, as base64. */
function lookFrom(mesh, camera) {
  const renderer = G.renderer();
  if (!EYE.target) {
    EYE.target = new THREE.WebGLRenderTarget(EYE.width, EYE.height, {samples: 4});
    EYE.target.texture.colorSpace = THREE.SRGBColorSpace;
  }
  const was = renderer.getRenderTarget(), shown = mesh.visible;
  mesh.visible = false;
  try {
    renderer.setRenderTarget(EYE.target);
    renderer.clear();
    renderer.render(G.scene(), camera);
    const pixels = new Uint8Array(EYE.width * EYE.height * 4);
    renderer.readRenderTargetPixels(EYE.target, 0, 0, EYE.width, EYE.height, pixels);
    const canvas = document.createElement('canvas');
    canvas.width = EYE.width; canvas.height = EYE.height;
    const pen = canvas.getContext('2d'), image = pen.createImageData(EYE.width, EYE.height);
    for (let row = 0; row < EYE.height; row++)  // the target is read bottom row first
      image.data.set(pixels.subarray((EYE.height - 1 - row) * EYE.width * 4, (EYE.height - row) * EYE.width * 4), row * EYE.width * 4);
    pen.putImageData(image, 0, 0);
    return canvas.toDataURL('image/png').split(',')[1];
  } finally {
    renderer.setRenderTarget(was);
    mesh.visible = shown;
  }
}
/* see and look: from the caller's own figure; turned first toward an address when one is given. */
function sight(payload, node, answer) {
  if (!G) return answer({error: 'The 3D map is not open on this page.'});
  const who = seer(payload.work, payload.role);
  if (who.refuse) return answer({error: who.refuse});
  let wait = 0;
  if (node) {
    if (who.mascot) { turnMascot(node); wait = reduced() ? 0 : 900; }
    else if (who.figure) { who.figure.lookAt = {node, until: who.figure.clock + 3}; wait = reduced() ? 0 : 900; }
  }
  wake3d(wait + 1500);
  setTimeout(() => {
    const camera = eyeCamera(who.mesh), seen = seeFrom(who.mesh, camera);
    const from = {character: who.who, as: who.mascot ? "the person's mascot" : 'your figure',
      eye: EYE.at.toArray().map(one => Math.round(one * 10) / 10), gaze: EYE.dir.toArray().map(one => Math.round(one * 100) / 100)};
    answer(payload.act === 'look' ? {from, ...seen, png: lookFrom(who.mesh, camera)} : {from, ...seen});
  }, wait);
}
/* What the person is looking at now: the selection, the large map, each map's mode, the side tab, the flow, the
 * physics, the panes open, and the elements in the 3D view. */
function viewing() {
  const chosen = S.selected, on = chosen ? (S.elements.get(chosen)?.element || null) : null, join = chosen?.startsWith('p:') ? joinOf(chosen) : null;
  const inView = [];
  if (G) for (const node of G.graphData().nodes) {
    if (node.t !== 'el' || node.x === undefined) continue;
    const v = SPOT.set(node.x, node.y, node.z).project(G.camera());
    if (v.z > -1 && v.z < 1 && Math.abs(v.x) <= 1 && Math.abs(v.y) <= 1) inView.push({address: node.address, name: node.name});
  }
  return {selected: on ? {address: on.address, name: labelOf(on)} : join ? {join: join.purpose, receiver: join.receiver_address} : null,
    large: $('.app').classList.contains('swapped') ? '2d' : '3d', mode3d: V3.mode, fit2d: MODE.fit, zoom2d: MODE.zoom, tab: tabNow(),
    flow: flowModeNow(), physics: PHYS.name, board: !$('#board').hidden, chat: !$('#helpdesk').hidden,
    panes: WS.on ? WS.layout() : null, in_view_3d: inView, mascot_eyes: EYE.view};
}
/* The mascot's eyes, for the person: the large 3D view eases to where the mascot sees from and follows it, and back
 * to where the camera was. */
function mascotEyes(on = !EYE.view) {
  if (!G || !MASCOT.mesh) return false;
  const camera = G.camera(), controls = G.controls();
  if (on && !EYE.view) EYE.saved = {at: camera.position.clone(), turn: camera.quaternion.clone(), fov: camera.fov};
  EYE.view = Boolean(on);
  EYE.k = 0;
  controls.enabled = !EYE.view && !EYE.saved;
  wake3d(1500);
  return EYE.view;
}
const EYEQ = new THREE.Quaternion();
function eyes3d(passed) {  // each frame: the large camera toward the mascot's eyes, or back to where it was
  if (!G || (!EYE.view && !EYE.saved)) return;
  const camera = G.camera();
  EYE.k = reduced() ? 1 : Math.min(1, EYE.k + passed / 0.9);
  const k = 1 - Math.pow(1 - EYE.k, 3);
  if (MASCOT.mesh) MASCOT.mesh.visible = !(EYE.view || (EYE.saved && EYE.k < 0.6));  // never seen from inside
  if (EYE.view && MASCOT.mesh) {
    const eye = eyeCamera(MASCOT.mesh, camera.aspect);
    camera.position.lerp(eye.position, Math.max(k, 0.25));
    camera.quaternion.slerp(EYEQ.copy(eye.quaternion), Math.max(k, 0.25));
    camera.fov += (eye.fov - camera.fov) * Math.max(k, 0.25);
  } else if (EYE.saved) {
    camera.position.lerp(EYE.saved.at, k);
    camera.quaternion.slerp(EYE.saved.turn, k);
    camera.fov += (EYE.saved.fov - camera.fov) * k;
    if (EYE.k >= 1) { EYE.saved = null; G.controls().enabled = true; if (MASCOT.mesh) MASCOT.mesh.visible = true; }
  }
  camera.updateProjectionMatrix();
  FRAMES.moved = true;
}
function eyeDebug3d() {  // the eye anchor and the gaze ray of every figure, drawn for a check of `look`
  for (const mesh of [MASCOT.mesh, ...[...ROAM.figures.values()].map(figure => figure.mesh)]) {
    if (!mesh) continue;
    eyeOf(mesh, EYE.at, EYE.dir);
    const far = mesh.scale.x * 6, tip = {x: EYE.at.x + EYE.dir.x * far, y: EYE.at.y + EYE.dir.y * far, z: EYE.at.z + EYE.dir.z * far};
    fxLine(EYE.at, tip, tintOf(css('--debug')), 1, 0.4);
    fxDot(EYE.at, mesh.scale.x * 0.12, tintOf(css('--debug')), 1, 0, 6, 10);
  }
}
/* Chat with the mascot: a click on it, where no node takes the click, opens a small reply field under its bubble. What
 * the person writes goes to their system agent, the one the chat dock's Call starts, and the answer comes back in the
 * bubble, in full in the chat dock's thread. */
const ASKING = {open: false, sent: 0, heard: null, base: null, pending: null};
function mascotScreen() {  // where the 3D mascot is on the page, for a click on it
  if (!G || !MASCOT.mesh) return {};
  const area = G.renderer().domElement.getBoundingClientRect(), at = SPOT.copy(MASCOT.mesh.position).project(G.camera());
  return {sx: area.left + (at.x + 1) / 2 * area.width, sy: area.top + (1 - at.y) / 2 * area.height};
}
function mascotAt(x, y) {
  if (!G || !MASCOT.mesh) return false;
  const area = G.renderer().domElement.getBoundingClientRect(), at = SPOT.copy(MASCOT.mesh.position).project(G.camera());
  const px = area.left + (at.x + 1) / 2 * area.width, py = area.top + (1 - at.y) / 2 * area.height;
  return Math.abs(at.z) < 1 && Math.hypot(px - x, py - y) < Math.max(18, onScreen(MASCOT.mesh) * 0.6);
}
function replyField() {
  const el = bubble(), field = h('input', {class: 'reply', type: 'text', placeholder: 'Ask your system agent…',
    'aria-label': 'Ask your system agent through the mascot'});
  ASKING.open = true;
  el.replaceChildren(h('span', {}, BUBBLE.text && performance.now() < BUBBLE.until ? BUBBLE.text : 'Yes?'), field);
  Object.assign(BUBBLE, {until: performance.now() + 60000, click: null});
  el.classList.add('on', 'asking');
  field.addEventListener('keydown', async event => {
    event.stopPropagation();
    if (event.key === 'Escape') return closeReply();
    if (event.key !== 'Enter' || !field.value.trim()) return;
    const text = field.value.trim();
    closeReply();
    say('Asking…', 30);
    await mascotAsk(text);
  });
  field.addEventListener('blur', () => setTimeout(() => { if (ASKING.open && document.activeElement !== field) closeReply(); }, 200));
  setTimeout(() => field.focus(), 30);
}
function closeReply() {
  ASKING.open = false;
  BUBBLE.el?.classList.remove('asking');
  hush();
}
async function mascotAsk(text) {
  const live = DOCK.mine && D.sessions.some(one => one.work_id === DOCK.mine && one.state === 'running' && one.session_id);
  ASKING.pending = text;
  if (!live) await callSystem();
  if (!DOCK.mine) { ASKING.pending = null; say('I could not reach your system agent.', 4); return; }
  await flushAsk();
}
/* The person's words to the system agent go once its session is up: at once when it is, or when the agents are next
 * read, `noticeAttention`, after the Call that starts it. */
async function flushAsk() {
  const text = ASKING.pending, session = D.sessions.filter(one => one.work_id === DOCK.mine && one.state === 'running'
    && one.session_id).at(-1);
  if (!text || !session) return;
  ASKING.pending = null;
  Object.assign(ASKING, {sent: Date.now(), heard: null, base: null});
  if (!await wrote('/api/dispatch-message', {work_id: DOCK.mine, session: session.session_id, text})) say('That did not go through.', 4);
}
/* The system agent's answer, the newest of its words after the person asked, said in the bubble in short; the chat
 * dock's thread, where it is read in full, calls this as it draws. */
function mascotHeard(target, lines) {
  if (!ASKING.sent || target !== DOCK.mine) return;
  const spoken = lines.filter(line => line.kind === 'agent_message_chunk');
  if (ASKING.base === null) { ASKING.base = Math.max(-1, ...spoken.map(line => Number(line.seq) || 0)); return; }
  const last = spoken.filter(line => (Number(line.seq) || 0) > ASKING.base).at(-1);
  const words = String(last?.text || '').replace(/\s+/g, ' ').trim();
  if (!words || words === ASKING.heard) return;
  ASKING.heard = words;
  say(words.length > 160 ? words.slice(0, 157) + '…' : words, Math.min(12, 3 + words.length / 25), () => agentAt(DOCK.mine),
    ROAM.figures.get(DOCK.mine)?.talk ? DOCK.mine : null);  // an embodied system agent answers from its own figure
}
$('#stage').addEventListener('click', event => {  // a click on the mascot where no node takes it: a word with it
  if (CUT.on || hovered || !mascotAt(event.clientX, event.clientY)) return;
  event.stopPropagation();
  replyField();
}, true);
/* A figure in 3D is the agent at work on its ticket: a click on it opens that session's thread in the chat dock. A
 * figure is taken anywhere within a ball of its size, so one moving on its orbit is easy to catch. */
const FIGURE_PICK = {ray: new THREE.Raycaster(), at: new THREE.Vector2(), ball: new THREE.Sphere(), down: null};
function figureAt(x, y) {
  if (!G || !ROAM.figures.size) return null;
  const area = G.renderer().domElement.getBoundingClientRect();
  if (!area.width || !area.height) return null;
  FIGURE_PICK.at.set((x - area.left) / area.width * 2 - 1, -(y - area.top) / area.height * 2 + 1);
  FIGURE_PICK.ray.setFromCamera(FIGURE_PICK.at, G.camera());
  let best = null;
  for (const [id, figure] of ROAM.figures) {
    if (figure.stage === 'leaving') continue;
    FIGURE_PICK.ball.set(figure.mesh.position, Math.max(0.5, figure.mesh.scale.x));
    if (!FIGURE_PICK.ray.ray.intersectsSphere(FIGURE_PICK.ball)) continue;
    const distance = FIGURE_PICK.ray.ray.origin.distanceTo(figure.mesh.position);
    if (!best || distance < best.distance) best = {id, distance};
  }
  return best?.id || null;
}
function openFigure(workId) {
  const session = D.sessions.filter(one => one.work_id === workId && one.state === 'running').at(-1);
  agentAt(workId, session?.session_id || null);
}
/* The agents in 2D, VIEW-035: the same agents as the 3D map's figures, each drawn as its flat glyph,
 * page/agent-glyphs/<glyph>.svg, the glyph its 3D figure is drawn with. It appears on the DE, walks the 2D map's own
 * edges to its ticket's node, circles the node's box while the ticket is open, and when the ticket closes walks back
 * and is gone; a join's ticket is circled at the middle of the join's edge. Its size is a share of a node's height,
 * so it keeps its place beside the boxes at any zoom, and never so few pixels that it is lost with a large map
 * whole in view. It walks as the 3D figures do, on a smooth curve, setting off and arriving gently, with a step's
 * bounce and a lean the way it goes, and swings onto its orbit the way it came. With reduced motion it stands above
 * its node. */
const ROAM2D = {figures: new Map(), seen: new Set(), frame: 0, last: 0, speed: 240, size: 1.2, orbit: 0.45, lap: 12,
  appear: 0.8, touch: 0.9, vanish: 0.6,
  // as the 3D figures move, `ROAM`, in the map's own units; the most it leans the way it goes, in degrees; and the
  // fewest pixels it spans on the screen, so it is still seen with the whole of a large map in view
  accel: 300, corner: 0.6, settle: 1.1, lean: 9, least: 22};
const home2d = () => [...S.elements.values()].find(item => item.element.role === 'DE')?.element.id
  || S.elements.keys().next().value;
function route2d(base, from, to) {  // the fewest edges of the 2D map from one element to another
  const near = new Map(), add = (one, two) => { if (!near.has(one)) near.set(one, []); near.get(one).push(two); };
  for (const {join, provider} of base.edges) { add(join.receiver, provider); add(provider, join.receiver); }
  const back = new Map([[from, null]]), queue = [from];
  while (queue.length && !back.has(to)) {
    const at = queue.shift();
    for (const next of near.get(at) || []) if (!back.has(next)) { back.set(next, at); queue.push(next); }
  }
  if (!back.has(to)) return [from, to];
  const path = [];
  for (let at = to; at !== null; at = back.get(at)) path.unshift(at);
  return path;
}
function spot2d(base, key) {  // where a 2D figure stands: an element's box, or the middle of a join's edge
  if (!key) return null;  // no node, as while the map is read again and has no elements yet
  if (!key.startsWith('p:')) { const node = base.nodes.get(key); return node && {x: node.x, y: node.y, w: node.w, h: node.h}; }
  const path = base.edges.find(edge => edge.join.id === key.slice(2))?.path;
  if (!path?.getTotalLength) return null;
  const middle = path.getPointAtLength(path.getTotalLength() / 2);
  return {x: middle.x, y: middle.y, w: 0, h: 0};
}
function target2d(base, ticket) {  // the ticket's place, and the element its walk ends at
  if (ticket.node_kind !== 'join') return base.nodes.has(ticket.node_id) ? {key: ticket.node_id, last: ticket.node_id} : null;
  const edge = base.edges.find(one => one.join.id === ticket.node_id);
  return edge ? {key: 'p:' + ticket.node_id, last: edge.join.receiver} : null;
}
function back2d(base, figure) {  // the way home, from the middle of a join's edge through its receiver
  const way = route2d(base, figure.last, figure.home);
  return figure.target === figure.last ? way : [figure.target, ...way];
}
function figures2d(tickets) {
  const base = M.base, home = base && home2d();
  if (!base || !home || !base.nodes.has(home)) return;
  const live = liveWork();
  for (const ticket of tickets) {
    const figure = ROAM2D.figures.get(ticket.id);
    if (figure) { figure.done = Boolean(ticket.done) || !live.has(ticket.id); continue; }
    const working = drawnWorking(ticket, live), target = working && target2d(base, ticket);
    if (target && !ROAM2D.seen.has(ticket.id)) {
      const glyph = ROAM.figures.get(ticket.id)?.glyph || glyphFor(ticket.id);
      const g = document.createElementNS(SVG, 'g'), image = document.createElementNS(SVG, 'image');
      g.setAttribute('class', 'agent2d');
      g.dataset.glyph = glyph;
      image.setAttribute('href', `/page/agent-glyphs/${glyph}.svg`);
      g.append(image);
      ROAM2D.seen.add(ticket.id);
      // a join's figure walks on from its receiver onto the middle of the join's edge
      const way = [...route2d(base, home, target.last), ...(target.key !== target.last ? [target.key] : [])];
      const motion = motionOf(glyph, ticket.id);
      ROAM2D.figures.set(ticket.id, {id: ticket.id, glyph, g, home, target: target.key, last: target.last, stage: 'arriving',
        way: way.map(key => ({key})), u: 0, speed: 0, clock: 0, angle: motion.phase * Math.PI * 2, stride: 0, lean: 0, motion,
        from: {x: 0, y: 0}, heading: {x: 1, y: 0}, x: 0, y: 0, size: 0, drawn: '', done: Boolean(ticket.done)});
    }
  }
  for (const [id, figure] of ROAM2D.figures) if (!tickets.some(ticket => ticket.id === id)) figure.done = true;
  again2d();
}
function again2d() { if ((ROAM2D.figures.size || mascotGlyph() || MASCOT2D.g) && !ROAM2D.frame) ROAM2D.frame = requestAnimationFrame(roam2d); }
function layer2d(base) {  // the figures are drawn over the boxes, in the boxes' own coordinates
  if (base.agents?.isConnected || (base.agents && base.svg.contains(base.agents))) return base.agents;
  const holder = base.nodes.values().next().value?.g.parentNode;
  if (!holder) return null;
  base.agents = document.createElementNS(SVG, 'g');
  base.agents.setAttribute('class', 'agents2d');
  holder.append(base.agents);
  const heights = [...base.nodes.values()].map(node => node.h).sort((one, two) => one - two);
  base.agentSize = ROAM2D.size * (heights[Math.floor(heights.length / 2)] || 40);
  return base.agents;
}
/* A point of the curve through a 2D figure's places at `u`, its leg and how far along it, a Catmull-Rom curve, which
 * passes through every place and turns smoothly at each. */
function curve2d(points, u) {
  const last = points.length - 1, leg = Math.min(last - 1, Math.max(0, Math.floor(u))), t = u - leg;
  const one = points[leg], two = points[leg + 1];
  const zero = points[leg - 1] || {x: 2 * one.x - two.x, y: 2 * one.y - two.y};
  const three = points[leg + 2] || {x: 2 * two.x - one.x, y: 2 * two.y - one.y};
  const t2 = t * t, t3 = t2 * t;
  const at = (a, b, c, d) => 0.5 * (2 * b + (c - a) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (3 * b - a - 3 * c + d) * t3);
  return {x: at(zero.x, one.x, two.x, three.x), y: at(zero.y, one.y, two.y, three.y)};
}
/* A 2D figure walks its way as the 3D figures do, `walk`: from rest up to ROAM2D.speed, slower into each sharp turn,
 * and to rest as it arrives. Says whether it has arrived. */
function walk2d(figure, points, passed) {
  const legs = points.length - 1, lengths = [], motion = figure.motion;
  const top = ROAM2D.speed * (motion?.speed ?? 1), accel = ROAM2D.accel * (motion?.accel ?? 1);
  const corner = CORNERS[motion?.corner]?.slow ?? ROAM2D.corner;
  let total = 0;
  for (let k = 0; k < legs; k++) { lengths.push(Math.max(1e-3, Math.hypot(points[k + 1].x - points[k].x, points[k + 1].y - points[k].y))); total += lengths[k]; }
  const leg = Math.min(legs - 1, Math.floor(figure.u));
  let done = (figure.u - leg) * lengths[leg];
  for (let k = 0; k < leg; k++) done += lengths[k];
  const least = top * 0.12, reach = (limit, away) => Math.sqrt(limit * limit + 2 * accel * Math.max(0, away));
  let speed = Math.min(top, reach(least, done), reach(least, total - done));
  for (let k = 1, at = lengths[0]; k < legs; at += lengths[k], k++) {
    const turn = ((points[k].x - points[k - 1].x) * (points[k + 1].x - points[k].x) + (points[k].y - points[k - 1].y) * (points[k + 1].y - points[k].y))
      / (lengths[k - 1] * lengths[k]);
    speed = Math.min(speed, reach(top * (1 - corner * (1 - turn) / 2), Math.abs(at - done)));
  }
  if (motion) speed *= strokeOf(motion, figure.stride / Math.max(1, figure.size || 40)).pace;
  figure.top = top;
  let step = speed * passed;
  figure.stride += step;
  while (step > 0 && figure.u < legs) {
    const now = Math.min(legs - 1, Math.floor(figure.u)), room = (now + 1 - figure.u) * lengths[now];
    if (step < room) { figure.u += step / lengths[now]; step = 0; } else { step -= room; figure.u = now + 1; }
  }
  figure.speed = speed;
  return figure.u >= legs - 1e-6;
}
/* Where a 2D figure leaves its orbit, or the place it last stood, and the way home from there. */
function home2dFrom(base, figure) {
  const way = back2d(base, figure).slice(1);
  return [{point: {x: figure.x, y: figure.y}}, ...(way.length ? way : [figure.home]).map(key => ({key}))];
}
/* How a flat glyph carries its character's gait, `MOTION`, from its stride in glyph sizes: how high it is off its
 * line, how much it is squashed (less than 0 stretched), and the sway of a swimmer's push. */
function gait2d(figure, moving) {
  const m = figure.motion, stroke = strokeOf(m, figure.stride / Math.max(1, figure.size || 40));
  if (m.go === 'hop') {
    if (figure.wasPhase < 0.75 && stroke.phase >= 0.75) figure.landed = figure.clock;
    figure.wasPhase = stroke.phase;
    const crouch = stroke.phase >= 0.75 ? Math.sin((stroke.phase - 0.75) / 0.25 * Math.PI) : 0;
    const land = Math.exp(-(figure.clock - (figure.landed ?? -9)) * 14);
    return {lift: stroke.air * m.lift * 1.2, squash: crouch * 0.2 - (stroke.phase < 0.375 ? stroke.air * 0.12 : 0) + land * 0.12, sway: 0};
  }
  if (m.go === 'walk' || m.go === 'creep') return {lift: moving ? Math.abs(Math.sin(stroke.phase * Math.PI * 2)) * Math.max(0.04, m.lift) : 0, squash: 0, sway: 0};
  if (m.go === 'swim' || m.go === 'pulse') return {lift: 0, squash: m.go === 'pulse' && moving ? (stroke.thrust - 0.5) * 0.12 : 0,
    sway: moving ? Math.sin(stroke.phase * Math.PI * 2) * 7 * stroke.thrust : 0};
  if (m.go === 'flap') return {lift: moving ? stroke.thrust * 0.05 : 0, squash: 0, sway: 0};
  return {lift: 0, squash: 0, sway: 0};
}
function roam2d() {
  ROAM2D.frame = 0;
  const now = performance.now() / 1000, passed = Math.min(0.1, Math.max(0, now - (ROAM2D.last || now)));
  ROAM2D.last = now;
  const base = M.base, layer = base && layer2d(base);
  // A figure keeps its share of a box's height, and never less than ROAM2D.least pixels on the screen, so it is seen
  // with the whole of a large map in view.
  const view = $('#viewport').getBoundingClientRect(), perPixel = M.cam && view.width && M.svg === base?.svg ? M.cam.w / view.width : 0;
  let moving = false;
  for (const [id, figure] of ROAM2D.figures) {
    const gone = () => { figure.g.remove(); ROAM2D.figures.delete(id); if (!ROAM.figures.has(id)) releaseGlyph(id); };
    if (!layer) { if (figure.done) gone(); continue; }
    if (figure.g.parentNode !== layer) layer.append(figure.g);
    figure.clock += passed;
    const size = Math.max(base.agentSize, ROAM2D.least * perPixel), target = spot2d(base, figure.target), home = spot2d(base, figure.home);
    if (!target || !home) { if (figure.done) gone(); continue; }
    const m = figure.motion;
    let x = target.x, y = target.y, scale = 1, lift = 0, lean = 0, squash = 0, spin = 0, going = false;
    if (reduced()) {  // no walking: it stands above its node while the ticket is worked
      y = target.y - target.h / 2 - size / 2;
      if (figure.done) { gone(); continue; }
    } else if (figure.stage === 'arriving') {  // it appears on the DE, in its own way
      const k = Math.min(1, figure.clock / ROAM2D.appear), e = easeBoth(k);
      ({x, y} = home);
      if (m.arrive === 'drop') y -= (1 - e) * size * 3;
      else if (m.arrive === 'swoop') { y -= (1 - e) * size * 2.5; x -= (1 - e) * size * 2; }
      else if (m.arrive === 'rise') y += (1 - e) * size * 1.5;
      scale = m.arrive === 'pop' ? Math.max(0.001, 1 + 1.7 * Math.pow(k - 1, 3) + 0.7 * Math.pow(k - 1, 2)) : Math.max(0.001, Math.min(1, k * 2));
      if (m.arrive === 'sprout') { scale = 1; squash = 1 - Math.max(0.001, e); }
      if (k >= 1) Object.assign(figure, {stage: 'going', u: 0, clock: 0});
    } else if (figure.stage === 'going' || figure.stage === 'returning') {  // along the map's own edges
      going = true;
      const out = figure.stage === 'going';
      const points = figure.way.map(step => step.point || spot2d(base, step.key));
      if (points.length < 2 || points.some(point => !point)) {  // a node of its way left the map
        Object.assign(figure, out ? {stage: figure.done ? 'flourish' : 'circling'} : {stage: 'leaving'}, {clock: 0, from: {x: 0, y: 0}});
        continue;
      }
      const arrived = walk2d(figure, points, passed), at = curve2d(points, figure.u), ahead = curve2d(points, Math.min(points.length - 1, figure.u + 0.02));
      ({x, y} = at);
      if (Math.hypot(ahead.x - x, ahead.y - y) > 1e-3) figure.heading = {x: ahead.x - x, y: ahead.y - y};
      if (m.corner === 'flit') {  // a moth jinks from side to side
        const across = Math.hypot(figure.heading.x, figure.heading.y) || 1;
        const jink = Math.sin(figure.stride / size * 5.3) * size * 0.2 * Math.min(1, figure.speed / figure.top);
        x += -figure.heading.y / across * jink; y += figure.heading.x / across * jink;
      }
      lean = Math.sign(figure.heading.x) * Math.min(1, figure.speed / figure.top) * ROAM2D.lean * (m.corner === 'bank' ? 1.6 : 1);
      if (arrived) {
        if (out) {  // onto its orbit from where it arrived, on the side that carries it straight on
          const across = target.w / 2 + size * ROAM2D.orbit * m.orbit / 1.5, down = target.h / 2 + size * ROAM2D.orbit * m.orbit / 1.5;
          figure.from = {x: x - target.x, y: y - target.y};
          figure.angle = m.dir * Math.atan2(figure.from.y / down, figure.from.x / across);
        }
        Object.assign(figure, {clock: 0, stage: !out ? 'leaving' : figure.done ? 'flourish' : 'circling'});
      }
    } else if (figure.stage === 'circling') {  // around its box, in its own way and at its own lap
      const mood = moodOf(id), c = figure.clock;
      let rate = 2 * Math.PI / m.lap;
      if (mood === 'restless') rate *= 1 + 0.55 * Math.sin(c * 1.7) * Math.sin(c * 0.63 + 1);
      if (mood === 'waiting') rate = 0;
      figure.angle += rate * passed;
      const settled = easeBoth(Math.min(1, c / ROAM2D.settle));  // it swings out from where it arrived
      const across = target.w / 2 + size * ROAM2D.orbit * m.orbit / 1.5, down = target.h / 2 + size * ROAM2D.orbit * m.orbit / 1.5;
      const turn = m.dir * figure.angle;
      let wx = target.x + Math.cos(turn) * across, wy = target.y + Math.sin(turn) * down;
      if (mood === 'waiting') { wx = target.x + target.w / 2 + size * 0.7; wy = target.y + target.h / 2; lean = 8; }  // toward the chat dock
      // a tool call: a quick reach toward the part it touched, and back
      if (figure.reach) {
        const u = (c - figure.reach.at) / 1.3, to = spot2d(base, figure.reach.to);
        if (u >= 1 || !to) figure.reach = null;
        else { const k = Math.sin(Math.PI * u) ** 2, share = to === target || figure.reach.to === figure.target ? 0.5 : 0.3;
          wx += (to.x - wx) * share * k; wy += (to.y - wy) * share * k; }
      }
      // now and then while it works, something of its own with its box: perched on top, or in close at its side
      if (mood === 'working' && !figure.act && c > (figure.nextAct ?? 5) && ACTS[m.act]) figure.act = {kind: m.act, at: c, long: ACTS[m.act]};
      if (figure.act) {
        const u = (c - figure.act.at) / figure.act.long;
        if (u >= 1 || mood !== 'working') { figure.act = null; figure.nextAct = c + actGap(m, c); }
        else {
          const k = easeBoth(Math.min(1, Math.sin(Math.PI * u) * 1.6));
          const [px, py] = figure.act.kind === 'perch' ? [target.x, target.y - target.h / 2 - size * 0.35]
            : [target.x + Math.cos(turn) * (target.w / 2 + size * 0.15), target.y + Math.sin(turn) * (target.h / 2 + size * 0.15)];
          wx += (px - wx) * k; wy += (py - wy) * k;
        }
      }
      x = target.x + figure.from.x + (wx - target.x - figure.from.x) * settled;
      y = target.y + figure.from.y + (wy - target.y - figure.from.y) * settled;
      // its stride goes on with the distance it covers, and a hopper hops in place now and then as it waits
      const covered = Math.hypot(x - figure.x, y - figure.y);
      figure.stride += covered;
      if (m.go === 'hop' && covered < size * 0.01 && Math.sin(c * 0.6 + m.phase * 6) > 0.2) figure.stride += passed * m.stride * size * 0.8;
      going = covered > size * 0.003;
      if (!lean) lean = -Math.sin(turn) * ROAM2D.lean * 0.5 * settled;
      if (figure.done) Object.assign(figure, {stage: 'flourish', clock: 0, from: {x: x - target.x, y: y - target.y}});
    } else if (figure.stage === 'flourish') {  // done: its little flourish, then home
      const u = Math.min(1, figure.clock / FLOURISH), k = Math.sin(Math.PI * u);
      ({x, y} = {x: target.x + figure.from.x, y: target.y + figure.from.y});
      const kind = m.flourish;
      if (kind === 'spin' || kind === 'twirl' || kind === 'loop') spin = easeBoth(u) * 360;
      if (kind === 'hop' || kind === 'flap' || kind === 'twirl') lift = k * 0.9;
      if (kind === 'puff') scale = 1 + 0.3 * k;
      if (kind === 'bow') squash = k * 0.25;
      if (u >= 1) Object.assign(figure, {stage: 'returning', way: home2dFrom(base, {...figure, x, y}), u: 0, clock: 0, stride: 0});
    } else if (figure.stage === 'leaving') {  // home again, it is gone
      const faded = Math.min(1, figure.clock / ROAM2D.vanish);
      ({x, y} = home); scale = Math.max(0.001, 1 - faded * faded);
      if (faded >= 1) { gone(); continue; }
    }
    if (!reduced() && figure.stage !== 'leaving' && figure.stage !== 'arriving') {
      const step = gait2d(figure, going);
      lift += step.lift; squash += step.squash; lean += step.sway;
      if (!going && m.idle.includes('bob') && figure.stage === 'circling') lift += Math.sin(figure.clock * 2.4 + m.phase * 6) * 0.025;
    }
    figure.lean += (lean - figure.lean) * (1 - Math.exp(-passed * 8));
    Object.assign(figure, {x, y, size: size * scale});
    const drawn = size * scale, foot = y + drawn / 2 - lift * size;
    const placed = [x - drawn / 2, foot, drawn, figure.lean, squash, spin].map(value => Math.round(value * 100) / 100).join(' ');
    if (placed === figure.drawn) continue;   // nothing to draw again
    figure.drawn = placed;
    moving = true;
    const image = figure.g.firstChild;
    image.setAttribute('x', x - drawn / 2); image.setAttribute('y', foot - drawn);
    image.setAttribute('width', drawn); image.setAttribute('height', drawn);
    // it leans the way it goes, squashes and stretches from its feet, and turns about its middle in a flourish
    image.setAttribute('transform', `rotate(${(figure.lean + spin).toFixed(2)} ${x} ${foot - drawn / 2}) `
      + `translate(${x} ${foot}) scale(${(1 + squash * 0.6).toFixed(3)} ${(1 - squash).toFixed(3)}) translate(${-x} ${-foot})`);
  }
  const awake = mascot2d(base, layer, perPixel, passed);
  // With reduced motion a figure stands still, so the frames stop once each is drawn; a redraw or a change asks again.
  // The mascot alone keeps them going only while it is awake, so a page left alone rests.
  if ((ROAM2D.figures.size && (moving || !reduced())) || awake) ROAM2D.frame = requestAnimationFrame(roam2d);
}
/* The mascot on the 2D map, `MASCOT`: its flat glyph goes to the selected box, waits at its right, below the name,
 * walks over to the figure of the agent the person chats with, and sleeps while the person is away. */
const MASCOT2D = {g: null, glyph: null, x: null, y: null, vx: 0, vy: 0, stride: 0, clock: 0, lean: 0, drawn: '', size: 0};
function mascot2d(base, layer, perPixel, passed) {
  const {glyph, leaving} = mascotFigure();
  if (MASCOT2D.g && (MASCOT2D.glyph !== glyph || !layer)) { MASCOT2D.g.remove(); MASCOT2D.g = null; }
  if (!glyph || !layer || !base || (leaving && !MASCOT2D.g)) return false;
  const size = Math.max(base.agentSize, ROAM2D.least * perPixel) * 0.95;
  if (!MASCOT2D.g) {
    const g = document.createElementNS(SVG, 'g'), image = document.createElementNS(SVG, 'image');
    g.setAttribute('class', 'agent2d mascot2d');
    g.style.pointerEvents = 'none';  // never in the way of a click
    image.setAttribute('href', `/page/agent-glyphs/${glyph}.svg`);
    g.append(image);
    Object.assign(MASCOT2D, {g, glyph, motion: motionOf(glyph, 'mascot'), x: null});
  }
  if (MASCOT2D.g.parentNode !== layer) layer.append(MASCOT2D.g);
  MASCOT2D.clock += passed;
  const m = MASCOT2D.motion, chat = !$('#helpdesk')?.hidden && DOCK.target ? ROAM2D.figures.get(DOCK.target) : null;
  // its agent leading it: where it sent it, or the node its body works on, else it stays; the selection waits
  const driven = !leaving && mascotDriven(), job = driven ? MASCOT.job : null;
  MASCOT2D.g.classList.toggle('driven', driven);
  const call = MASCOT.call?.node && (driven || !MASCOT.call.agent) ? spot2d(base, MASCOT.call.node) : null;
  const working = job?.node ? spot2d(base, job.node) : null;
  const chosen = S.selected && spot2d(base, S.selected), home = spot2d(base, home2d());
  const stay = driven && MASCOT2D.x !== null ? {x: MASCOT2D.x - size * 0.75, y: MASCOT2D.y + size * 0.15, w: 0, h: 0} : null;
  const at = leaving ? home : driven ? call || working || stay || home
    : call || (chat ? {x: chat.x + size * 1.1, y: chat.y, w: 0, h: 0} : null) || chosen || home;
  if (!at) return false;
  const wx = at.x + at.w / 2 + size * 0.75, wy = at.y + at.h / 2 - size * 0.15;
  if (MASCOT2D.x === null || reduced()) Object.assign(MASCOT2D, {x: wx, y: wy, vx: 0, vy: 0});
  const asleep = !leaving && !driven && performance.now() - FRAMES.active > FRAMES.idle && !MASCOT.call;
  if (!reduced() && !asleep) {  // steering, as the 3D mascot does: off gently, and to rest gently
    const top = ROAM2D.speed * m.speed * 0.9, accel = ROAM2D.accel * m.accel, dx = wx - MASCOT2D.x, dy = wy - MASCOT2D.y;
    const away = Math.hypot(dx, dy), speed = Math.min(top, Math.sqrt(2 * accel * Math.max(0, away - 0.5)));
    const want = away > 1e-3 ? [dx / away * speed, dy / away * speed] : [0, 0];
    let ax = want[0] - MASCOT2D.vx, ay = want[1] - MASCOT2D.vy;
    const most = accel * passed * 1.5, push = Math.hypot(ax, ay);
    if (push > most) { ax *= most / push; ay *= most / push; }
    MASCOT2D.vx += ax; MASCOT2D.vy += ay;
    MASCOT2D.x += MASCOT2D.vx * passed; MASCOT2D.y += MASCOT2D.vy * passed;
  }
  const speed = Math.hypot(MASCOT2D.vx, MASCOT2D.vy);
  MASCOT2D.stride += speed * passed;
  MASCOT2D.size = size;
  const step = reduced() ? {lift: 0, squash: 0, sway: 0} : gait2d(MASCOT2D, speed > size * 0.05);
  const lean = asleep ? 6 : Math.sign(MASCOT2D.vx) * Math.min(1, speed / (ROAM2D.speed * m.speed)) * ROAM2D.lean + step.sway;
  MASCOT2D.lean += (lean - MASCOT2D.lean) * (1 - Math.exp(-passed * 8));
  const squash = asleep ? 0.08 + Math.sin(MASCOT2D.clock * 0.9) * 0.03 : step.squash;
  const x = MASCOT2D.x, foot = MASCOT2D.y + size / 2 - step.lift * size;
  const placed = [x, foot, size, MASCOT2D.lean, squash].map(value => Math.round(value * 100) / 100).join(' ');
  const awake = !reduced() && (!asleep || placed !== MASCOT2D.drawn);
  if (placed === MASCOT2D.drawn) return awake;
  MASCOT2D.drawn = placed;
  const image = MASCOT2D.g.firstChild;
  image.setAttribute('x', x - size / 2); image.setAttribute('y', foot - size);
  image.setAttribute('width', size); image.setAttribute('height', size);
  image.setAttribute('transform', `rotate(${MASCOT2D.lean.toFixed(2)} ${x} ${foot - size / 2}) `
    + `translate(${x} ${foot}) scale(${(1 + squash * 0.6).toFixed(3)} ${(1 - squash).toFixed(3)}) translate(${-x} ${-foot})`);
  return awake;
}
/* A part's light, VIEW-035 and MAP-046: broken flashes red. Flashing lets the node's own
 * color show between flashes, and each step filed makes it faster: from FLASH.slow a beat while it waits, to
 * FLASH.fast as the steps planned are filed, or a little faster with each step when none were planned. */
const LIGHTS = [['broken', '--broken'], ['trouble', '--broken']];  // the one fault a built part can have, MAP-046
const FLASH = {slow: 1.2, fast: 0.24, step: 0.35};
function paceOf(node) {
  const done = S.progress?.get(node.id);
  if (!done || !done.filed) return FLASH.slow;
  const share = done.planned ? Math.min(1, done.filed / done.planned) : 1 - 1 / (1 + FLASH.step * done.filed);
  return FLASH.slow + (FLASH.fast - FLASH.slow) * share;
}
/* The part of the map each agent's work is using, VIEW-045: the node of the ticket it took, until work claims reserve
 * wider areas, LAYER-029. Checked beside the agent it shows in white; unchecked it is hidden, so the rest of the map
 * can be reviewed without it. `parts` holds node id → true when shown, false when hidden. */
const INUSE = {off: new Set(), parts: new Map(), preview: new Set()};
/* The element ids of addresses, as the map holds them. */
function idsAt(addresses) {
  const wanted = new Set(addresses || []);
  return [...S.elements.values()].filter(entry => wanted.has(entry.element.address)).map(entry => entry.element.id);
}
function paintInUse() {
  const parts = new Map();
  for (const one of D.sessions) {
    const ticket = one.state === 'running' ? ticketOf(one.work_id) : null;
    if (!ticket || !ticket.taken || ticket.done) continue;
    const shown = !INUSE.off.has(one.work_id);
    // a ticket inside an active work claim is using all the claim reserves, LAYER-029; else the node it is on
    const held = (D.claims || []).find(claim => claim.state === 'active' && claim.work.includes(one.work_id));
    for (const node of held ? [ticketNode(ticket), ...idsAt(held.nodes)] : [ticketNode(ticket)]) {
      parts.set(node, parts.get(node) === true || shown);
    }
  }
  for (const node of INUSE.preview) parts.set(node, true);  // a proposal's reach, shown while it is reviewed
  const same = parts.size === INUSE.parts.size && [...parts].every(([id, shown]) => INUSE.parts.get(id) === shown);
  INUSE.parts = parts;
  if (G && !same) G.nodeColor(G.nodeColor()).nodeVisibility(G.nodeVisibility()).linkVisibility(G.linkVisibility());
  for (const [id, node] of M.base?.nodes || []) {
    node.g.classList.toggle('inuse', parts.get(id) === true);
    node.g.classList.toggle('reserved', parts.get(id) === false);
  }
  for (const edge of M.base?.edges || []) {
    edge.path?.classList.toggle('reserved', parts.get(edge.join.receiver) === false || parts.get(edge.provider) === false);
  }
}
const shownNode = node => INUSE.parts.get(typeof node === 'object' ? node.id : node) !== false;
const lightOf = node => LIGHTS.find(([condition]) => has(node, condition));
const has = (node, condition) => (node.work || []).includes(condition);
function colorOf(node) {
  if (INUSE.parts.get(node.id) === true) return css('--in-use');  // the part an agent's work is using, VIEW-045
  if (node.t === 'el') return node.role === 'CQU' ? css('--signal') : node.role === 'DE' ? css('--de') : layerColor(node.layer);
  if (node.t === 'purpose') return css('--text');
  return layerColor(node.layer);
}
/* The color an object has apart from any condition. */
const ownColor = node => colorOf({...node, work: []});
/* A dimmed node keeps its own hue: its color with part of the background mixed in, the share set by the theme. */
function dim(color) {
  const keep = Number(css('--dim-keep')), channels = hex => [1, 3, 5].map(at => parseInt(hex.slice(at, at + 2), 16));
  const back = channels(css('--ground'));
  return '#' + channels(color).map((own, at) => Math.round(keep * own + (1 - keep) * back[at]).toString(16).padStart(2, '0')).join('');
}
const dimmed = node => S.selected && node.t === 'el' && node.id !== S.selected && !S.neighbors.has(node.id);
/* A node's color, given to whatever it is made of: glass takes it as its tint, as the color light takes on inside
 * it, and as the light it gives off. */
function colored(material, color) {
  material.color.set(color);
  if (material.isMeshPhysicalMaterial) { material.attenuationColor.set(color); material.emissive.set(color); }
}
/* Glass, VIEW-025: in every theme an element is made of a material that obeys reality. Light passes through it and
 * is tinted by it, so the theme's background shows through the node. It gives off a little of its own color, since
 * clear glass on a dark background with nothing to reflect shows as black. It is drei's transmission material: the
 * light behind it is read `samples` times, each color at its own index of refraction, which parts the colors at the
 * edges, `chromaticAberration`; the surface bends it by a noise, `distortion` at `distortionScale`, drifting at
 * `temporalDistortion`; the reads spread along the ray blur it, `anisotropicBlur`. What is behind the glass is drawn
 * by `addBehind`, as drei's own component draws it, with the far wall of every node in it: a node shows its own far
 * wall and the glass behind it, the backside. The drei values are a start and are not settled: with the frosting and
 * the absorption above, what is behind a node is blurred and tinted almost to its own color, so they hardly show. One
 * shape serves every node of a size. */
const GLASS = {transmission: 0.7, thickness: 9, roughness: 0.3, ior: 1.35, attenuationDistance: 7, clearcoat: 0.6,
  clearcoatRoughness: 0.25, emissiveIntensity: 0.45, metalness: 0,
  chromaticAberration: 0.06, distortion: 0.25, distortionScale: 0.35, temporalDistortion: 0.1, anisotropicBlur: 0.1,
  samples: 6};
const DRIFT = {value: 0};  // the one clock the distortion of every node drifts by; still with reduced motion
const shapes = new Map();
let SEGMENTS = 16;  // as the graph draws its own nodes; 32 halves the frame rate where there is no graphics card
const isGlass = node => node.t === 'el';
const ballShape = radius => shapes.get(radius) || shapes.set(radius, new THREE.SphereGeometry(radius, SEGMENTS, SEGMENTS)).get(radius);
/* An element's shape tells its artifact type, the first segment of its address, before any text is read, P042: code a
 * box, a document a page, media a screen, data a cylinder, a collection a stack, upstream a cone pointing up, toward
 * what feeds the project, and downstream one pointing down, toward who it serves. Each is about the size of the sphere it
 * replaces, so sizes still compare; anything else stays a sphere. The web_node_shapes setting turns them off. The 2D
 * map draws the same types as Mermaid shapes, SHAPES2D. One shape serves every node of a type and size. */
const VIEW_SETTINGS = {shapes: true};
const TYPE_ROOTS = ['code', 'document', 'media', 'data', 'collection', 'upstream', 'downstream'];
const typeOf = node => {
  const root = String(node?.address || '').split('.')[0];
  return VIEW_SETTINGS.shapes && TYPE_ROOTS.includes(root) ? root : null;
};
function stacked(parts) {
  const loose = parts.map(part => part.index ? part.toNonIndexed() : part);
  const merged = new THREE.BufferGeometry();
  for (const name of ['position', 'normal', 'uv']) {
    const size = loose[0].getAttribute(name).itemSize;
    const all = new Float32Array(loose.reduce((sum, part) => sum + part.getAttribute(name).array.length, 0));
    let at = 0;
    for (const part of loose) { all.set(part.getAttribute(name).array, at); at += part.getAttribute(name).array.length; }
    merged.setAttribute(name, new THREE.BufferAttribute(all, size));
  }
  return merged;
}
function typeShape(type, radius) {
  const key = `${type}:${radius}`;
  if (shapes.has(key)) return shapes.get(key);
  const r = radius, box = (w, hh, d) => new RoundedBoxGeometry(w * r, hh * r, d * r, 2, Math.min(w, hh, d) * r * 0.2);
  const made = type === 'code' ? box(1.55, 1.55, 1.55)
    : type === 'document' ? box(1.35, 1.85, 0.45)
    : type === 'media' ? box(2.05, 1.3, 0.35)
    : type === 'data' ? new THREE.CylinderGeometry(r, r, 1.5 * r, SEGMENTS)
    : type === 'collection' ? stacked([-0.62, 0, 0.62].map(y => box(1.8, 0.42, 1.8).translate(0, y * r, 0)))
    : type === 'upstream' ? new THREE.ConeGeometry(1.1 * r, 1.9 * r, SEGMENTS)
    : type === 'downstream' ? new THREE.ConeGeometry(1.1 * r, 1.9 * r, SEGMENTS).rotateX(Math.PI)
    : null;
  shapes.set(key, made);
  return made;
}
const nodeShape = (node, radius) => (typeOf(node) && typeShape(typeOf(node), radius)) || ballShape(radius);
/* The shapes turned on or off: each element's node drawn again in its shape. */
function shapes3d() {
  if (!G) return;
  for (const node of G.graphData().nodes) {
    const object = node.__threeObj;
    if (object?.isMesh && isGlass(node)) object.geometry = nodeShape(node, Math.cbrt(nodeSize(node)) * 3);
  }
  wake3d();
}
function bead(node) {
  const radius = Math.cbrt(nodeSize(node)) * 3;  // as the graph sizes a node: the cube root of its value, times 3

  const {transmission, thickness, roughness, attenuationDistance, chromaticAberration, distortion, distortionScale,
    temporalDistortion, anisotropicBlur, samples, ...physical} = GLASS;
  // drei's amount of light let through is `_transmission`; three.js's own `transmission` stays 0, since the page
  // draws what is behind the glass itself.
  const made = side => Object.assign(new MeshTransmissionMaterial({samples, _transmission: transmission, thickness,
    roughness, attenuationDistance, chromaticAberration, distortion, distortionScale, temporalDistortion,
    anisotropicBlur}), physical, {side});
  // The near wall reads the picture with every far wall in it. The far wall is a material of its own, since three.js
  // keeps a material's program when only its side changes; it shares every setting of the near wall but the picture
  // it reads, which is the scene with no glass in it.
  const material = made(THREE.FrontSide), back = made(THREE.BackSide);
  material.uniforms.time = DRIFT;
  material.uniforms.buffer.value = BEHIND.main?.texture ?? null;
  back.uniforms = {...material.uniforms, buffer: {value: BEHIND.back?.texture ?? null}};
  material.userData.back = back;
  back.userData.front = material;
  material.userData.own = true;
  colored(material, colorOf(node));
  return new THREE.Mesh(nodeShape(node, radius), material);
}
/* What is behind the glass, drawn each frame as drei's component draws it, once for every node, VIEW-025: the scene
 * with the glass hidden, into `back`; then with the far wall of every node, which reads `back`, into `main`; and the
 * near walls read `main` in the frame itself. Both are drawn at `scale` of the view's size, drei's `resolution` and
 * `backsideResolution`. It runs before the frame in the graph's own render chain. */
const BEHIND = {back: null, main: null, scale: 0.5};
function addBehind() {
  const composer = G.postProcessingComposer();
  if (!composer?.insertPass) return;
  const type = THREE.HalfFloatType;  // light over full brightness, seen through glass, is still spread by the bloom
  BEHIND.back = new THREE.WebGLRenderTarget(1, 1, {type});
  BEHIND.main = new THREE.WebGLRenderTarget(1, 1, {type});
  composer.insertPass({isPass: true, enabled: true, needsSwap: false, clear: false, renderToScreen: false,
    setSize(width, height) {
      const size = [Math.max(1, Math.round(width * BEHIND.scale)), Math.max(1, Math.round(height * BEHIND.scale))];
      BEHIND.back.setSize(...size);
      BEHIND.main.setSize(...size);
    },
    render(renderer) {
      const scene = G.scene(), camera = G.camera(), glass = [], was = renderer.getRenderTarget();
      scene.traverseVisible(object => { if (object.material?.userData.back) glass.push(object); });
      if (!glass.length) return;
      for (const object of glass) object.visible = false;
      renderer.setRenderTarget(BEHIND.back);
      renderer.render(scene, camera);
      // The far wall takes the node's tint and gives off no light toward the eye: a node's light leaves its glass
      // outward, so the far wall's light goes away from the eye, and the node is as bright as its near wall makes it.
      for (const object of glass) {
        const near = object.material, far = near.userData.back;
        far.color.copy(near.color);
        Object.assign(far, {emissiveIntensity: 0, opacity: near.opacity, transparent: near.transparent});
        Object.assign(object, {material: far, visible: true});
      }
      renderer.setRenderTarget(BEHIND.main);
      renderer.render(scene, camera);
      for (const object of glass) object.material = object.material.userData.front;
      renderer.setRenderTarget(was);
    },
    dispose() { BEHIND.back.dispose(); BEHIND.main.dispose(); }}, 0);
}
/* The light a node gives off, VIEW-029: the glass's own little light, VIEW-025, raised toward LIGHT in the given
 * color by `lit`, from 0 to 1. Above full brightness it is spread by the bloom pass past the node's outline, behind
 * whatever is nearer the eye. A node the graph draws itself, a join's purpose node, gives off none of its own. */
const LIGHT = 2.6;  // the light a node gives off when it is lit, chosen by eye; full brightness on a screen is 1
function shine(material, color, lit) {
  if (!material.emissive) return;
  const own = material.isMeshPhysicalMaterial ? GLASS.emissiveIntensity : 0;
  if (lit > 0 && color) material.emissive.set(color);
  material.emissiveIntensity = own + (LIGHT - own) * lit;
}

/* A property's reach, VIEW-022 and VIEW-026. Clicking a property node sends a wave out from the element it is linked
 * to, toward the leaves where it applies and toward the trunk where it is visible. A dot travels each namespace edge
 * away from that element; a node pulses when a dot arrives, holds it, and sends it on. The dots carry the property's
 * color and give off light at more than full brightness, which the bloom pass spreads; the edges keep their own
 * look. Selecting anything else puts the map back. */
const R = {key: null, color: null, home: null, nodes: new Set(), edges: 0};
const endOf = end => end?.id ?? end;
const inReach = link => R.key && link.k === 'tree' && R.nodes.has(endOf(link.source)) && R.nodes.has(endOf(link.target));
/* The wave's times in seconds, chosen by eye and not settled, VIEW-026: how often a wave leaves, how long a dot takes
 * to cross an edge, which is the same for every edge since an edge's length on screen carries no meaning, and how
 * long a node holds a dot, which is how long it pulses. `gaussian` names the timers multiplied by rnd + rnd each time
 * they are used: that runs from 0 to 2 and is 1 on average, so a timer averages its time and never repeats.
 * `opacity` is how much a node tints the light passing through it; the node is drawn solid whatever it is. */
const TIMES = {every: 3, cross: 1, hold: 0.25, opacity: 0.6, gaussian: ['every']};
const timed = name => TIMES[name] * (TIMES.gaussian.includes(name) ? Math.random() + Math.random() : 1);
const W = {clock: 0, last: 0, next: 0, dots: [], held: [], pulses: new Map(), glows: new Map()};
function setReach(key) {
  const thing = key?.startsWith('r:') ? S.items.get(key) : null;
  const home = thing ? [...S.elements.values()].find(entry => entry.element.id === thing.item.element_id)?.element : null;
  if (!home && !R.key) return;
  R.key = home ? key : null;
  R.color = home ? layerColor(thing.layer) : null;
  R.home = home ? home.id : null;
  R.nodes = new Set(home ? [...S.elements.values()].map(entry => entry.element)
    .filter(({address}) => address === home.address || home.address.startsWith(address + '.') || address.startsWith(home.address + '.'))
    .map(element => element.id) : []);
  R.edges = G ? G.graphData().links.filter(inReach).length : 0;
  for (const dot of W.dots) G.scene().remove(dot.mesh);
  if (G) for (const node of G.graphData().nodes) pulse3d(node, 0);  // no node is left lit
  Object.assign(W, {dots: [], held: [], next: W.clock, pulses: new Map()});
  if (G) G.nodeColor(G.nodeColor());  // every node back to its own color
  for (const [id, node] of M.base?.nodes || []) {
    node.g.classList.toggle('reach', R.nodes.has(id));
    node.g.style.setProperty('--reach', R.color || '');
  }
}
/* One material for each color, shared by every dot of that color, and one shape for every dot: a shape or a
 * material made for each dot would fill the graphics card's memory as the waves run. */
function glowOf(color) {
  if (!W.glows.has(color)) {
    const made = new THREE.MeshBasicMaterial({toneMapped: false});
    made.color.set(color).multiplyScalar(2.6);  // more than full brightness, which the bloom pass spreads
    W.glows.set(color, made);
  }
  return W.glows.get(color);
}
const channels = color => [1, 3, 5].map(at => parseInt(color.slice(at, at + 2), 16) / 255);
const colorFrom = parts => '#' + parts.map(part => Math.round(Math.min(1, Math.max(0, part)) * 255).toString(16).padStart(2, '0')).join('');
/* A dot arrives: the node pulses for as long as it holds the dot, then sends it on. */
function reached(id, from, outward) {
  const hold = Math.max(0.017, timed('hold'));
  W.pulses.set(id, {start: W.clock, length: hold});
  W.held.push({at: W.clock + hold, id, from, outward});
}
/* From the element the property is linked to the wave goes both ways; past it, it keeps its way, on toward the
 * leaves or on toward the trunk, and never out along a branch the property does not reach. */
function send(data, id, from, outward) {
  const template = data.nodes.find(node => node.id === id)?.__threeObj;
  if (!template || !template.material) return;
  for (const link of data.links) {
    if (!inReach(link)) continue;
    const down = endOf(link.source) === id, up = endOf(link.target) === id;
    if (!down && !up) continue;
    const to = down ? endOf(link.target) : endOf(link.source);
    if (to === from || (outward !== null && down !== outward)) continue;
    const mesh = template.clone(false);
    mesh.material = glowOf(R.color);
    mesh.scale.setScalar(0.32);
    G.scene().add(mesh);
    W.dots.push({mesh, link, back: up, to, from: id, outward: down, start: W.clock, length: Math.max(0.034, timed('cross'))});
  }
}
/* The pulse through a node, VIEW-026. Its depth is 0 as the dot enters, 1 at the node's center and 0 as it leaves.
 * The node tints the pulse as colored glass tints light; its body moves from its own color toward that tinted color
 * by the depth, and the glow is the body's own color given off as light, brighter with the depth, so the two are
 * never apart. */
function pulse3d(node, depth) {
  const object = node.__threeObj;
  if (!object || !object.material) return;
  if (!depth) {
    if (object.material.userData.pulsed) {
      colored(object.material, colorOf(node));
      shine(object.material, null, 0);
      object.material.userData.pulsed = false;
    }
    return;
  }
  const own = channels(ownColor(node)), light = channels(R.color);
  const body = colorFrom(own.map((part, at) => part + (light[at] * (1 - TIMES.opacity + TIMES.opacity * part) - part) * depth));
  if (!object.material.userData.own) { object.material = object.material.clone(); object.material.userData.own = true; }
  colored(object.material, body);
  shine(object.material, body, depth);
  object.material.userData.pulsed = true;
}
function wave3d(data) {
  const now = performance.now() / 1000;
  W.clock += Math.min(0.1, Math.max(0, now - (W.last || now)));
  W.last = now;
  if (!R.key) return;
  if (reduced()) {  // no wave: the reach is shown lit and still
    for (const node of data.nodes) if (R.nodes.has(node.id)) pulse3d(node, 1);
    return;
  }
  if (W.clock >= W.next) { W.next = W.clock + Math.max(0.2, timed('every')); reached(R.home, null, null); }
  const leaving = W.held.filter(item => item.at <= W.clock);
  W.held = W.held.filter(item => item.at > W.clock);
  for (const item of leaving) send(data, item.id, item.from, item.outward);
  const still = [];
  for (const dot of W.dots) {
    const through = (W.clock - dot.start) / dot.length;
    if (through >= 1) { G.scene().remove(dot.mesh); reached(dot.to, dot.from, dot.outward); continue; }
    const along = dot.back ? 1 - through : through, from = dot.link.source, to = dot.link.target;
    const place = dot.link.__curve ? dot.link.__curve.getPoint(along)
      : {x: from.x + (to.x - from.x) * along, y: from.y + (to.y - from.y) * along, z: from.z + (to.z - from.z) * along};
    dot.mesh.position.set(place.x, place.y, place.z);
    still.push(dot);
  }
  W.dots = still;
  for (const node of data.nodes) {
    if (!R.nodes.has(node.id)) continue;
    const pulse = W.pulses.get(node.id), gone = pulse ? (W.clock - pulse.start) / pulse.length : 2;
    pulse3d(node, gone >= 0 && gone <= 1 ? Math.sin(Math.PI * gone) : 0);
  }
}
/* The bloom pass, added to the graph's own render chain: what is over full brightness is kept in its hue, blurred at
 * a half, a quarter and an eighth of the size, and added to the picture. It runs while anything on the map is lit
 * above full brightness: a property's reach, a signal on text, a node that needs attention. The glow is put behind
 * whatever is nearer the eye, VIEW-029: the bright part of the picture carries its distance from the eye through the
 * blur, and the glow is added to a point only where what is drawn there is no nearer than the light that reaches it.
 * It is built from the classes of the objects the chain already holds, since the graph library keeps its 3D classes
 * to itself; the depth of the scene is kept in a depth texture of the page's own copy of three.js. */
let BLOOM = null;
const SOFT = 12;  // over how many units nearer than a light its glow fades out
const SAMPLES = 4;
const samplesFor = name => /swiftshader|llvmpipe|software|basic render/i.test(name) ? 0 : SAMPLES;
function drawnBy() {
  const gl = G.renderer().getContext(), told = gl.getExtension('WEBGL_debug_renderer_info');
  return String(told ? gl.getParameter(told.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
}
function addBloom() {
  const composer = G.postProcessingComposer(), copy = composer?.copyPass;
  if (!copy || !composer.renderTarget1) return;
  const Target = composer.renderTarget1.constructor, Material = copy.material.constructor, Quad = copy.fsQuad.constructor;
  // The scene's depth is kept beside its picture, in both of the chain's buffers, since they take turns.
  // The scene is drawn into these buffers and not onto the screen, so the smoothing of edges the screen has does
  // not reach it: each buffer takes four samples a pixel of its own. Without them a link thinner than a pixel,
  // as every link is with the whole map in view, breaks into dots. Where the drawing is done by the processor and
  // not by a graphics card the samples are left out: measured 2026-09-29 they took the page from 10 frames a
  // second to 6 there, and changed nothing that could be seen.
  for (const target of [composer.renderTarget1, composer.renderTarget2]) {
    target.depthTexture = new THREE.DepthTexture(target.width, target.height);
    target.samples = samplesFor(drawnBy());
    target.dispose();
  }
  const vertex = 'varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }';
  const shader = (fragmentShader, uniforms) => new Material({uniforms, vertexShader: vertex, fragmentShader, depthTest: false, depthWrite: false});
  const eye = {sceneDepth: {value: null}, cameraNear: {value: 1}, cameraFar: {value: 1}};
  // How far a point of the picture is from the eye, from the depth the scene was drawn with.
  const away = `#include <packing>
    uniform sampler2D sceneDepth; uniform float cameraNear; uniform float cameraFar;
    float away(vec2 at) { return -perspectiveDepthToViewZ(texture2D(sceneDepth, at).x, cameraNear, cameraFar); }`;
  // The part over full brightness, and in its fourth channel its distance from the eye weighted by its brightness, so
  // the blur carries the distance with the light; divided by the far distance, so it fits the buffer.
  const over = shader(`${away} uniform sampler2D tDiffuse; varying vec2 vUv;
    void main() { vec3 c = texture2D(tDiffuse, vUv).rgb; float top = max(c.r, max(c.g, c.b));
      vec3 bright = top > 1.0 ? c * (1.0 - 1.0 / top) : vec3(0.0);
      gl_FragColor = vec4(bright, (bright.r + bright.g + bright.b) * away(vUv) / cameraFar); }`,
  {tDiffuse: {value: null}, ...eye});
  const blur = shader(`uniform sampler2D tDiffuse; uniform vec2 along; varying vec2 vUv;
    void main() { vec4 sum = texture2D(tDiffuse, vUv) * 0.227027;
      sum += (texture2D(tDiffuse, vUv + along * 1.0) + texture2D(tDiffuse, vUv - along * 1.0)) * 0.1945946;
      sum += (texture2D(tDiffuse, vUv + along * 2.0) + texture2D(tDiffuse, vUv - along * 2.0)) * 0.1216216;
      sum += (texture2D(tDiffuse, vUv + along * 3.0) + texture2D(tDiffuse, vUv - along * 3.0)) * 0.054054;
      sum += (texture2D(tDiffuse, vUv + along * 4.0) + texture2D(tDiffuse, vUv - along * 4.0)) * 0.016216;
      gl_FragColor = sum; }`, {tDiffuse: {value: null}, along: {value: [0, 0]}});
  const mix = shader(`${away} uniform sampler2D tDiffuse; uniform sampler2D near; uniform sampler2D mid; uniform sampler2D far;
    uniform float strength; uniform float soft; varying vec2 vUv;
    // The glow of one level at this point, kept where what is drawn here is no nearer the eye than the light that
    // reaches it, and faded out over a short distance nearer than that, so a nearer node covers the glow.
    vec3 behind(vec4 light, float here) {
      float weight = light.r + light.g + light.b;
      if (weight <= 0.0) return vec3(0.0);
      return light.rgb * clamp((here - light.a / weight * cameraFar) / soft + 1.0, 0.0, 1.0);
    }
    void main() { vec4 base = texture2D(tDiffuse, vUv); float here = away(vUv);
      vec3 glow = behind(texture2D(near, vUv), here) + behind(texture2D(mid, vUv), here) * 1.2
        + behind(texture2D(far, vUv), here) * 1.4;
      // The picture and the glow are added as light and then made ready for the screen, so whatever the pass does
      // not light is drawn as it is without the pass.
      gl_FragColor = linearToOutputTexel(vec4(base.rgb + strength * glow, base.a));
    }`, {tDiffuse: {value: null}, near: {value: null}, mid: {value: null}, far: {value: null}, strength: {value: 0.8},
    soft: {value: SOFT}, ...eye});
  const quad = new Quad(over), type = composer.renderTarget1.texture.type;
  const levels = [2, 4, 8].map(() => ({across: new Target(1, 1, {type}), down: new Target(1, 1, {type})}));
  const draw = (renderer, material, target) => { quad.material = material; renderer.setRenderTarget(target); quad.render(renderer); };
  BLOOM = {isPass: true, enabled: false, needsSwap: true, clear: false, renderToScreen: false, levels: levels.length,
    setSize(width, height) {
      levels.forEach((level, index) => {
        const size = [Math.max(1, Math.round(width / 2 ** (index + 1))), Math.max(1, Math.round(height / 2 ** (index + 1)))];
        level.across.setSize(...size); level.down.setSize(...size);
      });
    },
    render(renderer, writeBuffer, readBuffer) {
      const camera = G.camera();
      eye.sceneDepth.value = readBuffer.depthTexture;
      eye.cameraNear.value = camera.near;
      eye.cameraFar.value = camera.far;
      let from = readBuffer.texture;
      levels.forEach((level, index) => {
        if (index === 0) { over.uniforms.tDiffuse.value = from; draw(renderer, over, level.down); from = level.down.texture; }
        blur.uniforms.tDiffuse.value = from; blur.uniforms.along.value = [1 / level.across.width, 0];
        draw(renderer, blur, level.across);
        blur.uniforms.tDiffuse.value = level.across.texture; blur.uniforms.along.value = [0, 1 / level.down.height];
        draw(renderer, blur, level.down);
        from = level.down.texture;
      });
      mix.uniforms.tDiffuse.value = readBuffer.texture;
      [mix.uniforms.near.value, mix.uniforms.mid.value, mix.uniforms.far.value] = levels.map(level => level.down.texture);
      draw(renderer, mix, this.renderToScreen ? null : writeBuffer);
    },
    dispose() { for (const level of levels) { level.across.dispose(); level.down.dispose(); } }};
  composer.addPass(BLOOM);
}
/* A part not built yet is a ghost, VIEW-027: its own node in its own color, three quarters clear, so it is seen to be in
 * the design and not yet there, and hides nothing behind it. A signal on it lights it as it lights any node, VIEW-029.
 * Its name is as faint as its node, `sign`, a little above it so it can still be read up close, and comes up to full
 * while the node is hovered, selected, met, beside the selection, or near enough that the name is large on the screen,
 * from `near` to `close` screen pixels for each pixel of its painted letters, `ghostSign`.
 * When the part is built its node and its name come up to solid over GHOST.solid seconds; with reduced motion at once.
 * Why: the characters that stood here moved all the time and drew the eye from everything else on the map; a ghost
 * says the same, that the part is still to come, and is quiet; and its name at full strength, on a map with many
 * parts still to come, filled the view with text. */
const GHOST = {opacity: 0.25, solid: 1.2, sign: 0.35, near: 2, close: 3};
const unbuilt = node => has(node, 'missing') || has(node, 'unbuilt') || has(node, 'under-construction');  // missing is absent, so not built
const GHOSTS = {now: new Set(), built: new Map()};   // the ids drawn as ghosts, and those built since, by when
/* A material made a ghost's: clear by `opacity`, and writing no depth, so what is behind it shows through whole. */
function ghostly(material, opacity) {
  Object.assign(material, {transparent: true, opacity, depthWrite: opacity >= 1});
  if (material.userData.back) Object.assign(material.userData.back, {transparent: true, opacity, depthWrite: opacity >= 1});
}
/* What a node is drawn as: a ghost while its part is not built, glass if it is an element, else the graph's own
 * sphere. A join's purpose node, which the graph draws itself, is made a ghost of its own here. */
function nodeObject(node, glass = true) {
  if (unbuilt(node)) {
    const object = ULTRA.body(node) || (isGlass(node) && glass ? bead(node)  // ULTRA: a body in outer space
      : new THREE.Mesh(nodeShape(node, Math.cbrt(nodeSize(node)) * 3), new THREE.MeshLambertMaterial({color: colorOf(node)})));
    object.material.userData.own = true;
    ghostly(object.material, GHOST.opacity);
    object.userData.ghost = true;
    return object;
  }
  return ULTRA.body(node) || (glass && isGlass(node) ? bead(node) : false);  // ULTRA
}
/* Each frame: a part built since it was drawn as a ghost comes up to solid. */
const eased = share => share * share * (3 - 2 * share);
const risenOf = (id, now) => Math.min(1, (now - GHOSTS.built.get(id)) / 1000 / GHOST.solid);
function ghost3d(data, now) {
  for (const node of data.nodes) {
    if (unbuilt(node)) { GHOSTS.now.add(node.id); continue; }
    if (GHOSTS.now.delete(node.id) && !reduced()) GHOSTS.built.set(node.id, now);
  }
  for (const id of GHOSTS.built.keys()) {
    const node = nodeById(data, id), material = node?.__threeObj?.material;
    const risen = risenOf(id, now);
    if (material && !node.__threeObj.userData.ghost) ghostly(material, GHOST.opacity + (1 - GHOST.opacity) * eased(risen));
    if (risen >= 1 || !node) GHOSTS.built.delete(id);
  }
}
/* How strong a node's name is drawn for its ghost, 1 for a built part's: GHOST.sign while its part is not built, full
 * while it is hovered, selected, met, beside the selection or lit in a reach, and rising to full as its letters grow
 * on the screen from GHOST.near to GHOST.close, `grown`; a part built since rises with its node. */
function ghostSign(node, grown, now) {
  const rising = GHOSTS.built.has(node.id);
  if (!rising && !unbuilt(node)) return 1;
  const shown = node.id === S.selected || node.id === hovered?.id || S.neighbors.has(node.id) || R.nodes.has(node.id)
    || (MEET.on && MEET.back?.id === node.id);
  if (shown) return 1;
  const near = eased(Math.min(1, Math.max(0, (grown - GHOST.near) / (GHOST.close - GHOST.near))));
  const faint = GHOST.sign + (1 - GHOST.sign) * near;
  return rising ? faint + (1 - faint) * eased(risenOf(node.id, now)) : faint;
}
const SIGNALS = [['broken', '--broken'], ['trouble', '--broken'], ['question', '--question'], ['message', '--question']];
/* The condition of a node in 3D, MAP-046, VIEW-005 and VIEW-029: an open broken record flashes it red, steady red
 * with reduced motion; an open question or message keeps its color. While it is
 * lit the node gives off light in the color of what it signals, which the bloom spreads past its outline: a flash is
 * lit on its beat, a pulse swells for half its period and rests for the other half. The sphere takes its own material
 * first, so no other node of its color changes. Called every frame for the nodes that carry a record, and for a node
 * still lit when its record has closed, to put its light back. */
function paint3d(node) {
  const object = node.__threeObj;
  if (!object || !object.material) return;
  const light = lightOf(node);
  // An open question glows in the question's color, pulsating, so it is seen with the whole map zoomed out, VIEW-021.
  const asked = has(node, 'question') || has(node, 'message');  // a message waits for the user, VIEW-030
  if (R.nodes.has(node.id) || (!light && !asked)) {  // a wave shows on it, or nothing to signal
    if (object.material.userData.lit) { shine(object.material, null, 0); object.material.userData.lit = false; }
    return;
  }
  if (!object.material.userData.own) {
    object.material = object.material.clone();
    object.material.userData.own = true;
    object.material.transparent = true;
  }
  const period = light ? paceOf(node) : 1;
  const beat = reduced() || (performance.now() / 1000) % period < period / 2;
  const shown = light ? (beat ? css(light[1]) : ownColor(node)) : colorOf(node);
  colored(object.material, dimmed(node) && !light ? dim(shown) : shown);
  const swell = reduced() ? 1 : Math.max(0, Math.sin(performance.now() / 1600 * 2 * Math.PI));
  const lit = light ? (beat ? 1 : 0) : swell;
  shine(object.material, light ? css(light[1]) : css('--question'), lit);
  object.material.userData.lit = true;
}

/* An encounter takes its layer's color. */
function linkColor(link) {
  if (link.k === 'tree') return css('--tree');
  return layerColor(link.layer);
}
/* The links are fibers, VIEW-005, shaded as the nodes are rather than flat: the graph library drew each as a matte
 * tube that light falls on evenly, beside nodes of glass that give off light, so the two did not look of one map. A
 * fiber gives off its color with a bright core along its middle, where the tube faces the eye, and dims toward its
 * rim, so it reads as a round strand of light at any width. It is never brighter than full, so the bloom never takes
 * it: light that spreads on the map means a node needs attention, VIEW-029, and fibers that glowed with it made the
 * whole map hazy whenever one did. One material for each color and opacity, shared by every link of them. */
const FIBERS = new Map();
function fiberOf(link) {
  const color = linkColor(link), opacity = Number(css('--link-opacity')), key = color + '|' + opacity;
  if (!FIBERS.has(key)) FIBERS.set(key, new THREE.ShaderMaterial({transparent: true, depthWrite: true,
    uniforms: {tint: {value: new THREE.Color(color)}, opacity: {value: opacity}},
    vertexShader: `varying vec3 vNormal; varying vec3 vView;
      void main() { vec4 at = modelViewMatrix * vec4(position, 1.0); vNormal = normalize(normalMatrix * normal);
        vView = normalize(-at.xyz); gl_Position = projectionMatrix * at; }`,
    fragmentShader: `uniform vec3 tint; uniform float opacity; varying vec3 vNormal; varying vec3 vView;
      void main() { float facing = abs(dot(normalize(vNormal), normalize(vView)));
        float core = pow(facing, 1.6), spark = pow(facing, 12.0);
        gl_FragColor = vec4(tint * min(1.0, 0.4 + 0.5 * core + 0.3 * spark), opacity * (0.25 + 0.75 * core)); }`}));
  return FIBERS.get(key);
}
let G = null;
const nodeSize = node => node.t === 'el' ? (node.role === 'DE' ? 9 : node.role === 'CQU' ? 7 : 4) : node.t === 'purpose' ? 0.9
  : node.t === 'item' ? 0.3 : 0.35;
/* The background is part of the scene as well as the graph's clear color. The render chain clears its buffer before
 * three.js draws into it, with the clear color last converted for the screen; three.js clears a scene's background
 * itself in the color space of whatever it draws into, so with the bloom on the background is the one drawn without
 * it, VIEW-022. */
function grounded() { G.scene().background = new THREE.Color(css('--ground')); }
/* The dots that travel a join are drawn solid, VIEW-005, as the approved prototype draws them. The graph library gives
 * a dot three times the opacity of the links, which a picture drawn on the screen holds at 1. The pictures this page
 * draws for the glass, and for the bloom while it is on, keep light over full brightness and hold no such limit: with
 * links at 0.8 a dot there was drawn as 2.4 times its color less 1.4 times what was behind it, so a dot passing through
 * a white node, or in front of it, turned it dark. The library makes the dots' materials again
 * whenever the map or the theme changes, so each is held at 1 as the scene is drawn. */
function solid() {
  for (const link of G.graphData().links) for (const dot of link.__photonsObj?.children || [])
    if (dot.material.opacity > 1) dot.material.opacity = 1;
}
/* The 3D view is started by trying it, never by asking the browser whether it can: a browser can say it has WebGL
 * and still fail when it is used, as Moli's answers null for the scissor box and three.js stops on it. When anything in
 * the start fails, the 2D map takes the large area and the small one says why, so the map still works there. */
function start3D() {
  try {
    if (typeof ForceGraph3D !== 'function') throw new Error('the 3D library did not load');
    create3D();
  } catch (error) {
    G = null;
    fill($('#stage'), h('p', {class: 'empty', style: {padding: '24px'}},
      `The 3D view could not start in this browser (${error.message}). The 2D map works as usual.`));
    swap(true, false);
  }
}
/* The 3D map draws a frame only when something on it moves, so a page left alone costs the machine nothing. The page
 * runs the graph's frames itself, `frame3d`, in place of the library's own loop, which draws every frame forever. A
 * frame is drawn while the layout settles, the camera flies or coasts, the pointer is on the map, a part flashes or
 * pulses, a property's wave, a part's text or an agent moves, and for `grace` after anything changes what is drawn:
 * every setter of the graph and every act on the map wakes it, `wake3d`. The dots that flow along the joins are the
 * one motion that never ends: they keep flowing, and once nothing has been done or changed for `idle` they are drawn
 * `idleRate` times a second, a flow nobody is watching closely, at its own speed. `rest`, when set, is how long after
 * that the flow stops until the next act or change; null keeps it flowing, as VIEW-005 draws it. With reduced motion
 * nothing flows, so an idle map draws nothing at all. */
const FRAMES = {id: 0, timer: 0, held: false, until: 0, active: 0, last: 0, drawn: 0, engine: false, moved: false,
  busy: false, flowing: false, grace: 700, idle: 30000, idleRate: 15, rest: 0};
// `idle` and `rest` are the web module's settings, web_flow_seconds and web_idle_flow, read with the workspace: the
// flow lasts web_flow_seconds after the last act or change and then stops, so an idle page costs nothing; with
// web_idle_flow on it goes on slowly, `rest` null, as the map was drawn before.
const DAMPING = 0.12;
const DRAG_FRICTION = 0.65;  // the share of its speed a node loses each tick while one is dragged; 0.4 otherwise  // the share of a turn of the camera a hand gave that it loses each 60th of a second: it coasts
function wake3d(ms = FRAMES.grace) {
  const now = performance.now();
  FRAMES.until = Math.max(FRAMES.until, now + ms);
  FRAMES.active = now;
  wake2d();  // the selected node's flow in the 2D map goes on with any act, as the 3D map's does
  if (!G || FRAMES.held || FRAMES.id) return;
  clearTimeout(FRAMES.timer);
  FRAMES.timer = 0;
  FRAMES.id = requestAnimationFrame(frame3d);
}
function frame3d(now) {
  // While a frame is drawn `id` holds a mark, so a wake from inside the frame asks for no frame of its own: the frame
  // asks for one next frame at its end, and only one, or every wake would start a second run of frames beside it.
  FRAMES.id = -1;
  if (!G || FRAMES.held) { FRAMES.id = 0; return; }
  const passed = Math.min(0.1, Math.max(0.001, (now - (FRAMES.last || now - 16)) / 1000));
  FRAMES.last = now;
  FRAMES.engine = FRAMES.moved = false;
  const controls = G.controls();  // the camera coasts for the same time at any frame rate
  if (controls.enableDamping) controls.dampingFactor = 1 - Math.pow(1 - DAMPING, passed * 60);
  try { G._animationCycle(); }  // the layout's tick, the dots, the controls, the picture and what the pointer is over
  finally { G.pauseAnimation(); FRAMES.id = 0; }  // which asks for the library's next frame; the page asks for its own
  FRAMES.drawn++;
  const still = now - FRAMES.active;
  if (now < FRAMES.until || FRAMES.engine || FRAMES.moved || FLIGHT.on || FRAMES.busy || (FRAMES.flowing && still < FRAMES.idle)) {
    FRAMES.id = requestAnimationFrame(frame3d);
  } else if (FRAMES.flowing && (FRAMES.rest === null || still < FRAMES.idle + FRAMES.rest)) {
    FRAMES.timer = setTimeout(() => {
      FRAMES.timer = 0;
      if (!FRAMES.id && !FRAMES.held) FRAMES.id = requestAnimationFrame(frame3d);
    }, 1000 / FRAMES.idleRate);
  }
}
/* The library's setters and the methods that change what is drawn wake the map, as does every camera move asked for
 * from outside the page's own flights; such a move also ends a flight under way and, unless it fits the whole map,
 * tells the settled layout not to fit it again, since someone put the camera where it is. */
const WAKERS = new Set(['refresh', 'd3ReheatSimulation', 'resumeAnimation', 'emitParticle']);
const READERS = new Set(['graph2ScreenCoords', 'screen2GraphCoords', 'getGraphBbox', 'getPointerPos', 'pauseAnimation']);
function wakeful(graph) {
  for (const [name, method] of Object.entries(graph)) {
    if (typeof method !== 'function' || name.startsWith('_') || READERS.has(name)) continue;
    graph[name] = function (...args) {
      // a getter, a force asked for by its name, or a reading of where something is drawn changes nothing
      if ((!args.length && !WAKERS.has(name)) || (name === 'd3Force' && args.length < 2)) return method.apply(this, args);
      if (name === 'cameraPosition' || name === 'zoomToFit') {
        FLIGHT.on = false;
        V3.focus = null;
        V3.auto = name === 'zoomToFit';
        const takes = Number(args[name === 'zoomToFit' ? 0 : 2]) || 0;
        wake3d(FRAMES.grace + takes);
        setTimeout(rehover3d, takes);  // the readout decided again once the flight is done
      } else wake3d();
      return method.apply(this, args);
    };
  }
}
function create3D() {
  G = ForceGraph3D({controlType: 'orbit'})($('#stage'));
  G.pauseAnimation();  // the page runs the frames, `frame3d`
  wakeful(G);
  G.backgroundColor(css('--ground'))
    .showNavInfo(false)
    .nodeRelSize(3)
    .nodeVal(nodeSize)
    .nodeThreeObject(node => nodeObject(node))
    .nodeColor(node => dimmed(node) ? dim(colorOf(node)) : colorOf(node))
    .nodeVisibility(shownNode)
    .linkVisibility(link => shownNode(link.source) && shownNode(link.target))
    .nodeOpacity(0.95)
    .nodeResolution(16)
    .nodeLabel(() => '')  // the page shows its own tooltip, anchored above the node, not under the pointer
    .onNodeHover(() => {})  // the hover is the page's nearest-node choice, `nodeAt3d`
    .linkColor(linkColor)
    .linkOpacity(Number(css('--link-opacity')))
    .linkMaterial(link => ULTRA.fiber(link) || fiberOf(link))  // ULTRA: a filament of light in outer space
    .linkWidth(link => link.k === 'tree' ? 0.4 : link.k === 'layer' || link.k === 'item' ? 0.25 : link.k === 'relation' ? 0.5 : 0.9)
    .linkCurvature(0)
    .linkDirectionalParticles(link => !reduced() && (link.k === 'purpose' || link.k === 'encounter') ? 1 : 0)
    .linkDirectionalParticleSpeed(0)  // the page draws the flow itself, `flow3d`; this dot shows only held, `dots3d`
    .linkDirectionalParticleWidth(1.6)
    .linkDirectionalParticleColor(linkColor)
    // The layout settles once its energy is spent rather than after a fixed time, and the map is then fitted to the
    // view if nobody has moved the camera, `settled3d`.
    .d3AlphaMin(0.001)
    .onEngineTick(() => { FRAMES.engine = true; V3.ticks++; })
    .onEngineStop(() => { if (V3.ticks > 30) settled3d(); V3.ticks = 0; })
    // A node dragged gives the layout energy, so the nodes joined to it follow and the map settles again once it is
    // let go: a settled layout would stop at once and leave the map rigid, so it is kept running while a node is held.
    // The graph library warms it to 0.3 for a drag, which throws the whole map about; the nodes move against more
    // friction while one is held, DRAG_FRICTION, so the map follows gently.
    .onNodeDrag(node => {  // the mascot never pushes the node in the person's hand, and lets go of one taken from it
      HANDDRAG.node = node;
      if (MASCOT.holding === node) { MASCOT.holding = null; MASCOT.job = null; }
      G.d3AlphaMin(0).d3VelocityDecay(DRAG_FRICTION);
    })
    .onNodeDragEnd(() => { HANDDRAG.node = null; G.d3AlphaMin(0.001).d3VelocityDecay(PHYS.decay); })
    .onNodeClick((node, event) => clickedAt3d(event))
    // a click on no node takes the nearest join's edge within reach, `linkAt3d`, as the 2D map does
    .onLinkClick((link, event) => clickedAt3d(event))
    .onBackgroundClick(event => clickedAt3d(event))
    .onNodeRightClick((node, event) => { if (node) menu(node.id, event.clientX, event.clientY); });
  grounded();
  G.scene().onBeforeRender = solid;
  addBehind();
  addBloom();
  ULTRA.attach(G, {wake: wake3d, reduced, css, selected: () => S.selected, hovered: () => hovered?.id ?? null,  // ULTRA
    dimmed: node => Boolean(dimmed(node)), idle:() => performance.now() - FRAMES.active > FRAMES.idle, toast,
    chained: () => FRAMES.id > 0, settings: async () => (await read('settings')).settings || [],
    save: value => posted('/api/settings', {key: 'web_graphics', value}), shapes: () => VIEW_SETTINGS.shapes});
  // The page's own work for each frame runs first in the render chain: after the layout's tick and the controls, before
  // anything is drawn, so the camera's flight, the labels, the dots and the tooltip are all of the same frame.
  G.postProcessingComposer().insertPass({isPass: true, enabled: true, needsSwap: false, clear: false, renderToScreen: false,
    setSize() {}, render() { prepare3d(); }, dispose() {}}, 0);
  applyPhysics(PHYS.name, false);  // the forces of the physics chosen, `PHYSICS`
  // The camera coasts after a hand lets it go, and the wheel zooms toward the point under the pointer.
  const controls = G.controls();
  Object.assign(controls, {enableDamping: true, dampingFactor: DAMPING, zoomToCursor: true});
  controls.addEventListener('start', () => {
    FLIGHT.on = false; V3.auto = false; V3.focus = null; hover3d(null);
    // A hand on the camera releases a meeting: the sign goes back into the scene, the map behind comes back into
    // focus, and the camera stays where the hand leaves it, so the small area is a map to look around, until the
    // next selection meets a sign again.
    if (MEET.on) meetEnds();
  });
  controls.addEventListener('change', () => { FRAMES.moved = true; rehover3d(); });  // the readout decided again at rest
  const stage = $('#stage');
  for (const type of ['pointerdown', 'wheel', 'keydown']) stage.addEventListener(type, () => wake3d(), {passive: true});
  for (const type of ['pointerenter', 'pointermove']) stage.addEventListener(type, () => { TIP.out = false; wake3d(); }, {passive: true});
  stage.addEventListener('pointerleave', () => { TIP.out = true; hover3d(null); pick3d(null); });
  // the edge a click would take, marked once a frame as the pointer moves; a node under the pointer takes the click
  stage.addEventListener('pointermove', event => {
    if (EDGE_PICK.frame3d || event.buttons) return;
    const {clientX: x, clientY: y} = event;
    EDGE_PICK.frame3d = requestAnimationFrame(() => {
      EDGE_PICK.frame3d = 0;
      // the node nearest the pointer within reach, then the nearest edge: what a click will take, `pickAt3d`
      if (!TIP.out) hover3d(nodeAt3d(x, y));
      const link = hovered ? null : linkAt3d(x, y);
      pick3d(link);
      $('#stage').classList.toggle('picking', Boolean(hovered || link));
      // an agent's figure under the pointer, with no node or edge, is said in the readout and takes the click
      const work = !hovered && !link ? figureAt(x, y) : null;
      if (work) readout('3d', figureWords(work));
      else if (!hovered && !link) readout('3d', null);
    });
  }, {passive: true});
  // a click on an agent's figure, not a drag of the camera, opens its thread
  stage.addEventListener('pointerdown', event => { FIGURE_PICK.down = [event.clientX, event.clientY]; }, true);
  stage.addEventListener('click', event => {
    const down = FIGURE_PICK.down;
    if (!down || Math.hypot(event.clientX - down[0], event.clientY - down[1]) > 5) return;
    const work = figureAt(event.clientX, event.clientY);
    if (work) openFigure(work);
  });
  // A press anywhere else, or a key, ends the tooltip: a menu or a window may now cover the node it named.
  document.addEventListener('pointerdown', event => { if (!stage.contains(event.target)) hover3d(null); }, true);
  document.addEventListener('keydown', () => hover3d(null), true);
  resize();
  wake3d();
  $('#pauseBtn').onclick = () => {  // pausing pins every vertex where it is; resuming frees them and warms the layout
    const paused = $('#pauseBtn').dataset.paused === 'true';
    for (const node of G.graphData().nodes) Object.assign(node, paused ? {fx: undefined, fy: undefined, fz: undefined}
      : {fx: node.x, fy: node.y, fz: node.z});
    if (paused) G.d3ReheatSimulation(); else wake3d();
    $('#pauseBtn').dataset.paused = String(!paused);
    $('#pauseBtn').textContent = paused ? 'Pause layout' : 'Resume layout';
  };
  $('#relayoutBtn').onclick = () => {
    const data = G.graphData();
    for (const node of data.nodes) for (const key of ['x', 'y', 'z', 'vx', 'vy', 'vz', 'fx', 'fy', 'fz']) delete node[key];
    $('#pauseBtn').dataset.paused = 'false';
    $('#pauseBtn').textContent = 'Pause layout';
    V3.auto = true;  // the new layout is fitted to the view as it settles
    G.graphData(data);  // the layout gives vertices without a position new ones and settles again
  };
}
/* The join edge nearest the pointer on the screen, within EDGE_PICK.most CSS pixels, each edge projected to the screen as the
 * camera sees it, VIEW-008: the edge a click on no node takes and the one the pointer marks. A join's edges run from
 * its receiver to its purpose vertex and on to each element serving it; either selects the join. */
const LINK_ENDS = [new THREE.Vector3(), new THREE.Vector3()];
function linkAt3d(x, y) {
  if (!G) return null;
  const box = $('#stage').getBoundingClientRect(), camera = G.camera(), [one, two] = LINK_ENDS;
  const px = x - box.left, py = y - box.top;
  let best = null, nearest = EDGE_PICK.most;
  for (const link of G.graphData().links) {
    const from = link.source, to = link.target;
    if (!link.join || (link.k !== 'purpose' && link.k !== 'encounter') || typeof from !== 'object' || from.x === undefined
      || to.x === undefined || !shownNode(from) || !shownNode(to)) continue;
    one.set(from.x, from.y, from.z).project(camera);
    two.set(to.x, to.y, to.z).project(camera);
    if (Math.abs(one.z) > 1 || Math.abs(two.z) > 1) continue;  // behind the eye or past the far plane
    const away = segmentAway(px, py, (one.x + 1) / 2 * box.width, (1 - one.y) / 2 * box.height,
      (two.x + 1) / 2 * box.width, (1 - two.y) / 2 * box.height);
    if (away < nearest) { nearest = away; best = link; }
  }
  return best;
}
const purposeOf = link => endOf(link.k === 'purpose' ? link.target : link.source);
/* Each node's reach, in both maps: the area of the screen where the pointer takes it. It reaches half the distance to
 * its nearest neighbour on the screen, centre to centre, so neighbours share the room between them evenly; never less
 * than the node as drawn, and never more than REACH.most CSS pixels, so a node alone does not take the empty space
 * around it. Where reaches overlap, the node whose centre is nearest the pointer takes it; an edge is picked only where
 * no node reaches, `linkAt3d` and `edgeAt2d`. The reaches are measured again at most once a frame, as the camera, the
 * layout or the zoom moves the nodes on the screen. A neighbour farther than twice the most a reach can be never
 * shortens it, so each node looks only at the cells of a grid around it. */
const REACH = {most: 60, d3: null, d2: null};
function reachOf(list) {  // list: {x, y, r} in CSS pixels, r the node as drawn; sets each one's `reach`
  const cell = 2 * REACH.most, grid = new Map(), at = (x, y) => `${x},${y}`;
  for (const one of list) {
    const key = at(Math.floor(one.x / cell), Math.floor(one.y / cell));
    (grid.get(key) || grid.set(key, []).get(key)).push(one);
  }
  for (const one of list) {
    const cx = Math.floor(one.x / cell), cy = Math.floor(one.y / cell);
    let nearest = Infinity;
    for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) for (const other of grid.get(at(cx + dx, cy + dy)) || []) {
      if (other !== one) nearest = Math.min(nearest, Math.hypot(other.x - one.x, other.y - one.y));
    }
    one.reach = Math.max(one.r, Math.min(nearest / 2, REACH.most));
  }
  return list;
}
/* The 3D map's nodes on the screen with their reaches, measured at most once a frame. */
const NODE_AT = new THREE.Vector3();
function reaches3d() {
  const now = performance.now();
  if (REACH.d3 && now - REACH.d3.at < 16) return REACH.d3.list;
  const box = $('#stage').getBoundingClientRect(), camera = G.camera(), across = Math.tan(camera.fov * Math.PI / 360), list = [];
  for (const node of G.graphData().nodes) {
    if (node.x === undefined || !shownNode(node)) continue;
    NODE_AT.set(node.x, node.y, node.z);
    const far = NODE_AT.distanceTo(camera.position);
    NODE_AT.project(camera);
    if (Math.abs(NODE_AT.z) > 1) continue;  // behind the eye or past the far plane
    list.push({node, x: box.left + (NODE_AT.x + 1) / 2 * box.width, y: box.top + (1 - NODE_AT.y) / 2 * box.height,
      r: Math.cbrt(nodeSize(node)) * 3 / (far * across) * box.height / 2});
  }
  REACH.d3 = {at: now, list: reachOf(list)};
  return list;
}
/* The node the pointer takes on the 3D map: of those whose reach covers it, the one whose centre is nearest, so a large
 * node close to the eye does not swallow the small ones drawn over it. */
function nodeAt3d(x, y) {
  if (!G) return null;
  let best = null, nearest = Infinity;
  for (const one of reaches3d()) {
    const middle = Math.hypot(one.x - x, one.y - y);
    if (middle <= one.reach && middle < nearest) { nearest = middle; best = one.node; }
  }
  return best;
}
/* A click on the 3D map takes what the pointer marks: with the scissors out the nearest edge, `CUT`; an agent's figure
 * keeps its own click; then the nearest node within reach, then the nearest edge. */
function clickedAt3d(event) {
  if (!event) return;
  if (CUT.on) return clickedLink3d(event);
  if (figureAt(event.clientX, event.clientY)) return;
  const node = nodeAt3d(event.clientX, event.clientY);
  if (node) return clicked3d(node);
  clickedLink3d(event);
}
function clickedLink3d(event) {
  const link = linkAt3d(event.clientX, event.clientY);
  if (CUT.on) return cutLink(link);  // with the scissors out a click cuts the edge, `CUT`
  if (link) select(purposeOf(link), true);
}
/* The edge the pointer would take, drawn as a bright strand while it is the one. */
let PICKED_FIBER = null;
function pick3d(link) {
  if (EDGE_PICK.link3d === link) return;
  const was = EDGE_PICK.link3d;
  if (link) readout('3d', edgeWords(joinOf(purposeOf(link)) || {receiver: '', providers: []}));
  if (was?.__lineObj && was.__pickedFrom) { was.__lineObj.material = was.__pickedFrom; delete was.__pickedFrom; }
  EDGE_PICK.link3d = link;
  if (link?.__lineObj) {
    if (!PICKED_FIBER) {
      PICKED_FIBER = fiberOf(link).clone();
      PICKED_FIBER.uniforms.tint.value = new THREE.Color(css('--text'));
      PICKED_FIBER.uniforms.opacity.value = 1;
    }
    link.__pickedFrom = link.__lineObj.material;
    link.__lineObj.material = PICKED_FIBER;
  }
  $('#stage').classList.toggle('picking', Boolean(link));
  wake3d();
}
/* A click on any vertex selects that object itself: an element or a join's purpose vertex. */
function clicked3d(node) {
  if (!node) return;
  select(node.id, true);
}
/* A node takes the pointer anywhere on its sphere, not only at its center, a ghost of a part not built as every
 * other node. Each node is picked by a ball of its size on the screen around its center. */
const PICK = {edge: 2};  // the pixels past a sphere that the picture smooths its edge over, measured 2026-10-03
const PICKED = {center: new THREE.Vector3(), at: new THREE.Vector3(), ball: new THREE.Sphere(), size: new THREE.Vector2()};
function picked(raycaster, hits) {
  const node = this.__data, camera = raycaster.camera;
  if (!node || !camera?.isPerspectiveCamera) return;
  const {center, at, ball, size} = PICKED;
  this.getWorldPosition(center);
  const depth = -at.copy(center).applyMatrix4(camera.matrixWorldInverse).z;
  if (depth <= 0) return;
  const unit = 2 * depth / (camera.projectionMatrix.elements[5] * G.renderer().getSize(size).y);  // world units a pixel spans there
  if (!raycaster.ray.intersectSphere(ball.set(center, Math.cbrt(nodeSize(node)) * 3 + PICK.edge * unit), at)) return;
  const distance = raycaster.ray.origin.distanceTo(at);
  if (distance >= raycaster.near && distance <= raycaster.far) hits.push({distance, point: at.clone(), object: this});
}
function tipFor(node) {
  if (node.t === 'el') return [h('b', {}, node.name), ...servedBy(node)];
  if (node.t === 'item') return [h('b', {}, node.layer), h('span', {}, short(node.text, 160))];
  const join = S.joins.find(item => item.id === node.join);
  if (node.t === 'purpose') return [h('span', {}, join?.purpose || 'purpose')];
  return [h('b', {}, node.name || '')];
}
/* What an element does, which its label does not say, VIEW-038: the ef of each join it provides, as written, with
 * no subject chosen, MAP-020. Its address is not shown, since that is its name read the other way. */
function servedBy(node) {
  return S.joins.filter(join => join.providers.includes(node.id) && (join.ef || join.purpose)).slice(0, 3).map(join =>
    h('span', {class: 'why'}, short(join.ef || join.purpose, 160)));
}
/* The tooltip sits above the hovered node, clear of its sphere at any zoom, so the pointer never covers it; it goes
 * below the node only where it would leave the top of the view. */
let hovered = null;
/* The tooltip names the node under the pointer and nothing else: it goes when the pointer leaves the map, when a hand
 * turns the camera, and when a press elsewhere or a key may have put a menu or a window over the node. The graph
 * reports what is under the pointer's last place on the map, so while the pointer is off the map, `TIP.out`, nothing
 * is. */
const TIP = {out: true};
function hover3d(node) {
  const was = hovered;
  hovered = TIP.out ? null : node || null;
  if (hovered !== was && [was, hovered].some(one => one && unbuilt(one))) wake3d();  // a ghost's name comes up, VIEW-027
  if (hovered === was && hovered) return;
  readout('3d', hovered ? readoutOf(hovered) : null);
}
/* ---------- the hover readout: what the pointer is on, said across the top of the map's window ----------
 * Over anything a click picks, a node, a join's edge by the nearest-edge choice, a purpose vertex, an agent's figure
 * or a memory, the cursor is a pointing finger and the readout at the top of that map's window says what it is: its
 * name, its kind and its address, and for an edge the receiver → provider with the join's purpose. It eases in on
 * hover and fades a moment after the pointer leaves; it lies over the map, takes no room and no click, so nothing
 * jumps. Its text grows with the window between a floor and a ceiling, wraps to three lines at most and ends with an
 * ellipsis; in the small pane it is one line. It is #tip3d in the 3D map and #tip2d in the 2D one. */
/* It holds steady: a name shows once what the pointer is on has stayed the same for `settle` ms, stays `stay` ms after
 * the pointer leaves it before it fades, and a new name takes the place of one on view by crossfading in place. It is
 * decided when the pointer moves and when the camera comes to rest, `rehover3d`, never frame by frame, so the camera's
 * motion, ultra's quality steps and a sign's occlusion changing under a still pointer never toggle it. */
const READOUT = {timers: {}, now: {}, want: {}, settle: 120, stay: 400};
function readoutBox(which) {
  if (which === '3d') return $('#tip3d');
  let box = $('#tip2d');
  if (!box) { box = h('div', {id: 'tip2d', class: 'readout', role: 'status', 'aria-live': 'polite', hidden: true}); $('#map2d').append(box); }
  return box;
}
/* What the pointer is on, said in two places: its name across the top, only where the map shows none that can be read,
 * `top`, and its details in the card at the lower left, `card`, for anything a click picks. `info` null: nothing. */
function readout(which, info) {
  const hovering = Boolean(info), shows = VIEW.hoverInfo || 'name+summary';  // web_hover_info
  const parts = shows === 'summary' || shows === 'off' ? null : Array.isArray(info) ? info : info?.top || null;
  hoverCard(which, shows === 'name' || shows === 'off' || Array.isArray(info) ? null : info?.card || null);
  const box = readoutBox(which);
  if (!box) return;
  box.classList.add('readout');
  const host = which === '3d' ? $('#stage') : $('#viewport');
  host?.classList.toggle('pickable', hovering);
  const key = parts ? JSON.stringify(parts.map(part => part?.textContent ?? part)) : null;  // a part left out is null
  if (key === READOUT.want[which]) return;  // the same as asked already: its timer runs on
  READOUT.want[which] = key;
  clearTimeout(READOUT.timers[which]);
  if (!parts) {  // gone: kept a moment, then faded and put away
    if (READOUT.now[which] === null) return;
    READOUT.timers[which] = setTimeout(() => {
      READOUT.now[which] = null;
      box.classList.remove('on');
      READOUT.timers[which] = setTimeout(() => { if (!box.classList.contains('on')) box.hidden = true; }, reduced() ? 0 : 400);
    }, reduced() ? 0 : READOUT.stay);
    return;
  }
  if (READOUT.now[which] === key) { box.classList.add('on'); return; }  // back to the name on view before it went
  READOUT.timers[which] = setTimeout(() => {
    const said = h('span', {class: 'said'}, h('span', {class: 'line'}, parts));
    const showing = box.classList.contains('on') && !box.hidden && READOUT.now[which];
    READOUT.now[which] = key;
    if (showing && !reduced()) {  // one name gives way to the next in place, the old fading out over the new
      for (const old of box.querySelectorAll('.said')) {
        old.classList.add('leaving');
        setTimeout(() => old.remove(), 220);
      }
      said.classList.add('arriving');
      box.append(said);
    } else fill(box, said);
    box.hidden = false;
    void box.offsetWidth;  // from where it stands away, so it eases in
    box.classList.add('on');
  }, reduced() ? 0 : READOUT.settle);
}
/* The 3D map's readout decided again once the camera rests, a wheel's zoom or a flight done, for the node or edge the
 * pointer is still on: its sign may now be read, or no longer. */
function rehover3d() {
  clearTimeout(READOUT.rest3d);
  READOUT.rest3d = setTimeout(() => {
    if (TIP.out) return;
    if (hovered) readout('3d', readoutOf(hovered));
  }, 250);
}
/* What the readout says, the name alone, and only where the map shows no name that can be read: for an edge, which
 * has no label of its own, the names it joins, receiver → provider; for a node, only while its own label is drawn
 * smaller than READABLE CSS pixels on the screen or not drawn at all, as when labels are decluttered; for an agent's
 * figure, its agent's name. A node whose name can be read gets the finger and its highlight, and no readout. */
const READABLE = 11;
function labelReadable(id, which) {
  if (which === '2d') {
    const g = M.nodes.get(id)?.g, label = g?.querySelector('.nodeLabel, text');
    if (!label || !label.getBoundingClientRect().height || getComputedStyle(label).visibility === 'hidden') return false;
    return parseFloat(getComputedStyle(label).fontSize) * Math.abs(g.getScreenCTM()?.a || 0) >= READABLE;
  }
  const tag = tags.get(id);
  if (!tag || tag.hidden) return false;
  if (MEET.on && MEET.back?.id === id) return true;  // the met name, drawn over the map
  if (tag.under || !tag.sprite.visible || !LABELS.on || (tag.sprite.material.opacity ?? 1) < 0.35) return false;
  // its letters as drawn on the screen: the sign's four corners projected as the scene draws them, `signRect`, so an
  // outward sign seen at a slant is measured as small as it reads; on the screen at all, and tall enough to read
  const rect = window.metaform.signRect(id), area = $('#stage').getBoundingClientRect();
  if (!rect || !tag.height) return false;
  const middle = {x: (rect.left + rect.right) / 2, y: (rect.top + rect.bottom) / 2};
  if (middle.x < area.left || middle.x > area.right || middle.y < area.top || middle.y > area.bottom) return false;
  // the lesser of its height and its width as drawn against its own, so a sign turned edge on, its letters squeezed
  // thin, does not count as read
  const scale = Math.min((rect.bottom - rect.top) / tag.height, tag.width ? (rect.right - rect.left) / tag.width : Infinity);
  return scale * (tag.lookNow?.size ?? LABEL.size) >= READABLE;
}
/* The readout of a node of either map, by its id, or of a 3D graph node: null where its own name can be read. */
function readoutOf(node, which = '3d') {
  const id = typeof node === 'string' ? node : node.id;
  const join = id.startsWith('p:') ? joinOf(id) : (typeof node === 'object' && node.t === 'purpose' ? S.joins.find(one => one.id === node.join) : null);
  if (join) return edgeWords(join);
  const top = name => labelReadable(id, which) ? null : [h('b', {}, name)];
  const entry = S.elements.get(id);
  if (entry) {
    const element = entry.element;
    const serves = S.joins.find(one => one.providers.includes(id) && (one.ef || one.purpose));
    const holds = S.joins.find(one => one.receiver === id && one.purpose);
    return {top: top(labelOf(element)), card: {title: labelOf(element),
      kind: ['element', element.role, element.address?.split('.')[0]].filter(Boolean).join(' · '), address: element.address,
      text: serves ? (serves.ef || serves.purpose) : holds ? `Needs: ${holds.purpose}` : '', work: (element.open_work || []).join(' · ')}};
  }
  if (typeof node === 'object' && node.t === 'item') {
    return {top: [h('b', {}, short(node.text || '', 120))], card: {title: short(node.text || '', 80), kind: `item · ${node.layer}`, text: node.text}};
  }
  const thing = memoryThing?.(id);
  if (thing) return {top: [h('b', {}, thing.name || thing.title || id)], card: {title: thing.name || thing.title || id, kind: 'memory',
    text: (thing.observations || []).slice(0, 2).join(' ') || thing.entityType || ''}};
  const name = (typeof node === 'object' && node.name) || id;
  return {top: [h('b', {}, name)], card: {title: name, kind: 'node'}};
}
function edgeWords(join) {
  const named = item => S.elements.has(item) ? labelOf(S.elements.get(item).element) : item;
  const ends = `${named(join.receiver) || join.receiver_address || ''} → ${join.providers.map(named).join(', ') || join.provider_address || ''}`;
  return {top: [h('b', {}, ends)], card: {title: ends, kind: ['join', join.layer].filter(Boolean).join(' · '),
    address: join.receiver_address || '', text: join.purpose || '', more: join.ef || ''}};
}
function figureWords(workId) {
  const session = D.sessions.filter(one => one.work_id === workId).at(-1);
  return {top: [h('b', {}, agentName(session?.agent))], card: {title: agentName(session?.agent), kind: 'agent',
    text: `On ${workPart(workId)}`, status: sessionStatus(session)}};
}
/* The detail card at the lower left of the map's window, in the legend's corner, the legend easing out while it shows: the name as its title, a quiet line
 * of its kind and role, the address in mono, its purpose or EF in a line or two, for an edge the join's purpose, and
 * for an agent what it works on and its status. It eases in for anything hovered and fades a moment after; it sits
 * above the map's count and clear of the legend, takes no click, and in the small pane is its title and one line. */
const CARD = {timers: {}, now: {}};
function cardBox(which) {
  const id = which === '3d' ? 'card3d' : 'card2d';
  let box = document.getElementById(id);
  if (!box) {
    box = h('div', {id, class: 'hovercard', role: 'status', 'aria-live': 'polite', hidden: true});
    (which === '3d' ? $('#big3d .view3d') : $('#map2d'))?.append(box);
  }
  return box;
}
function hoverCard(which, card) {
  const box = cardBox(which);
  if (!box) return;
  clearTimeout(CARD.timers[which]);
  if (!card) {
    CARD.now[which] = null;
    box.classList.remove('on');
    CARD.timers[which] = setTimeout(() => { if (!box.classList.contains('on')) box.hidden = true; }, reduced() ? 0 : 900);
    return;
  }
  const key = JSON.stringify([card.title, card.kind, card.address, card.text, card.more, card.work, card.status?.words]);
  if (CARD.now[which] !== key) {
    CARD.now[which] = key;
    // no title: the name is said once, at the top left where the map shows none to read, or on its own sign
    fill(box, card.kind || card.status ? h('div', {class: 'kind'}, card.kind || '', card.status ? statusChip(card.status) : null) : null,
      card.address ? h('code', {class: 'address'}, card.address) : null,
      card.text ? h('p', {class: 'text'}, card.text) : null,
      card.more && card.more !== card.text ? h('p', {class: 'more'}, card.more) : null,
      card.work ? h('p', {class: 'work'}, card.work) : null);
  }
  box.hidden = false;
  void box.offsetWidth;  // from where it stands away, so it eases in
  box.classList.add('on');
}
/* The readout stands across the top of the map's window, not at the node, so nothing follows the node each frame. */
function placeTip() {}
const short = (text, most) => text.length > most ? text.slice(0, most - 1) + '…' : text;
/* The labels of the 3D map, VIEW-038, are drawn inside the scene, each its element's whole name, wrapped at word
 * breaks, painted on a canvas and shown as a sign in the scene, standing out from the map's middle and facing the eye. Its size and its opacity say how near it is:
 * a label grows and shrinks with the map as it is zoomed, and from the front of the map in view to its back it goes
 * from its full size to a fifth of it; the nearest label is solid and the farthest two thirds clear, so the near names stand
 * out where the map is dense and the depth of the map reads from its names as well as its nodes. Each
 * stands a set distance out from its node on the side away from the map's middle, and is drawn with the depth test
 * as the nodes are, so the
 * depth buffer orders labels and nodes together: a node nearer the eye hides the part of a label behind it, a label
 * behind a glass node is seen through the glass as the material lets it through, VIEW-025, since what is behind the
 * glass is drawn with the labels in it, and a nearer label is drawn over a farther one. Nothing ranks over depth, the
 * selected node, its neighbors and a lit or blinking node included. A label that falls on a nearer node's sphere or
 * on a nearer label keeps its own color: what is in front hides it by depth or shows it through the glass.
 * Every element keeps its label, VIEW-005; the text is in the theme's
 * text color, each letter outlined in the background's color, `stroke`, in place of a box behind the name, so the
 * name reads over what is behind it without a bar hiding the map; the outline fades with the label by its depth. A
 * label is painted again only when what it shows changes. */
/* How each physics preset treats the names, so a name can be read in every shape the map takes: `place`, where it
 * stands from its node, away from the map's middle ('out'), above it ('above'), or beside it, to the side of the way
 * service flows ('beside'); `least` and `most`, the screen pixels its letters are held between, so a map seen whole
 * never shrinks them to specks nor a near one blows them up; `declutter`, whether a name that would overlap one ranked
 * above it, the selection, its neighbours, then the hubs, then the rest, is left out until there is room; `farthest`,
 * how faint the farthest name is drawn, lower in a tight preset so the near ones stand out. Organic keeps the names as
 * they have always been drawn, held only from shrinking past reading. Every name faces the eye, never edge on or
 * mirrored. */
const LABEL_PRESETS = {
  organic: {place: 'out', least: 9, most: Infinity, declutter: false, farthest: 0.34},
  clusters: {place: 'above', least: 11, most: 22, declutter: true, farthest: 0.18},
  spread: {place: 'out', least: 12, most: 24, declutter: true, farthest: 0.4},
  calm: {place: 'out', least: 10, most: 22, declutter: true, farthest: 0.3},
  down: {place: 'beside', least: 11, most: 22, declutter: true, farthest: 0.4},
  across: {place: 'above', least: 11, most: 22, declutter: true, farthest: 0.4},
  radial: {place: 'out', least: 11, most: 22, declutter: true, farthest: 0.4},
  depth: {place: 'beside', least: 11, most: 22, declutter: true, farthest: 0.25},
  flat: {place: 'above', least: 11, most: 22, declutter: true, farthest: 0.6},
};
const RIGHT = new THREE.Vector3();
/* Outward signs, as they have always been drawn: away from the map's middle, sized by perspective, the far ones fading
 * to LABEL.farthest, none left out; their letters raised only where they would fall below `least` screen pixels, so a
 * map seen whole, as Spread leaves it, never shrinks them past reading. */
const OUTWARD_SIGNS = {place: 'out', least: 7, most: Infinity, declutter: false, farthest: 0.34};
const LABEL = {size: 11, chosen: 13, wide: 9, line: 1.15, padX: 6, padY: 4, stroke: 2, after: 10, titleStep: 0.06,
  out: 12,  // how far a label stands out from its ball's surface, away from the map's middle, in the map's units
  // the size of a label's letters in the map, in its units, about an element's height; painted sharper at each
  // `sharper` step of the size it is seen at, up to `largest`; and the farthest label's opacity, the nearest solid
  letters: 10, largest: 4, sharper: 0.5, farthest: 0.34};
const tags = new Map();   // by node id: the label's sprite, its canvas, what it shows and where it is on the screen
const LABELS = {group: null, plane: null, on: true, only: null, pen: null, measured: new Map()};
const OUT = new THREE.Vector3(), UP = new THREE.Vector3(), AT = new THREE.Vector3(), middle = new THREE.Vector3();
const Y_UP = new THREE.Vector3(0, 1, 0);  // the map's own up, which an outward sign keeps
const fontOf = look => `${look.weight} ${look.size}px ${look.family}`;
/* The name in lines no wider than the label's width, broken only between words, as the page wraps text; a word longer
 * than the width keeps its own line whole. Measured once for each name and look. */
function wrapped(text, look, oneLine = false) {
  const key = fontOf(look) + '\n' + text + (oneLine ? '\n1' : '');
  if (LABELS.measured.has(key)) return LABELS.measured.get(key);
  LABELS.pen = LABELS.pen || document.createElement('canvas').getContext('2d');
  LABELS.pen.font = fontOf(look);
  const most = LABEL.wide * look.size, lines = [];
  for (const word of text.split(/\s+/).filter(Boolean)) {
    const joined = lines.length ? lines.at(-1) + ' ' + word : null;
    if (joined !== null && LABELS.pen.measureText(joined).width <= most) lines[lines.length - 1] = joined;
    else lines.push(word);
  }
  if (!lines.length) lines.push('');
  if (oneLine && lines.length > 1) {  // one line, ended with an ellipsis where it runs past twice the usual width
    let line = text.trim();
    while (line.length > 1 && LABELS.pen.measureText(line + '…').width > most * 2) line = line.slice(0, -1).trimEnd();
    lines.splice(0, lines.length, line === text.trim() ? line : line + '…');
  }
  const widest = Math.max(...lines.map(line => LABELS.pen.measureText(line).width));
  const made = {lines, width: Math.ceil(widest) + 2 * LABEL.padX, height: Math.ceil(lines.length * look.size * LABEL.line) + 2 * LABEL.padY};
  LABELS.measured.set(key, made);
  return made;
}
function painted(tag, look, ratio, shape) {
  const canvas = tag.texture.image, pen = canvas.getContext('2d');
  canvas.width = Math.ceil(shape.width * ratio); canvas.height = Math.ceil(shape.height * ratio);
  pen.scale(ratio, ratio);
  pen.font = fontOf(look); pen.textAlign = 'center'; pen.textBaseline = 'middle';
  const step = look.size * LABEL.line, at = index => LABEL.padY + step * (index + 0.5);
  // each letter outlined in the background's color, so the name reads over the lines and nodes behind it, and
  // nothing more: a shadow, or a wide glow, around the letters hid every edge that ran behind them
  Object.assign(pen, {lineWidth: LABEL.stroke, lineJoin: 'round', strokeStyle: look.ground, shadowColor: 'transparent'});
  shape.lines.forEach((line, index) => pen.strokeText(line, shape.width / 2, at(index)));
  for (const blur of [...look.glow, 0]) {   // a reached part's glow of the background under it, then the text itself
    pen.shadowColor = blur ? look.ground : 'transparent'; pen.shadowBlur = blur * ratio;
    pen.fillStyle = look.color;
    shape.lines.forEach((line, index) => pen.fillText(line, shape.width / 2, at(index)));
  }
  tag.texture.dispose();                    // the canvas may have changed size
  tag.texture.needsUpdate = true;
  Object.assign(tag, {lines: shape.lines, width: shape.width, height: shape.height, color: look.color});
}
function labelFor(node) {
  let tag = tags.get(node.id);
  if (tag) return tag;
  if (!LABELS.group) {
    LABELS.group = new THREE.Group();
    G.scene().add(LABELS.group);
    // Measured and painted again once the page's face is there.
    Promise.all([500, 600].map(weight => document.fonts.load(`${weight} ${LABEL.size}px ${css('--sans')}`))).then(() => {
      LABELS.measured.clear();
      for (const each of tags.values()) each.key = '';
      wake3d();
    }, () => {});
  }
  const texture = new THREE.CanvasTexture(document.createElement('canvas'));
  Object.assign(texture, {colorSpace: THREE.SRGBColorSpace, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter,
    generateMipmaps: false});
  // A sign in the scene, standing out from the map's middle and turned to face the eye, so its name always reads as
  // written. `sprite` is the name it has always had in the page's reads.
  LABELS.plane ??= new THREE.PlaneGeometry(1, 1);
  // It is tested against what is nearer, so a nearer node or edge hides it, but writes no depth of its own and is
  // drawn after the map, so it never cuts out an edge or a node behind it: written into the depth, each letter and
  // its outline hid every edge drawn after it, however far behind.
  const sprite = new THREE.Mesh(LABELS.plane, new THREE.MeshBasicMaterial({map: texture, side: THREE.DoubleSide,
    depthTest: true, depthWrite: false, transparent: true, alphaTest: 0.02, toneMapped: false}));
  sprite.renderOrder = LABEL.after;
  sprite.raycast = () => {};                // a label is never picked in place of the node
  LABELS.group.add(sprite);
  tag = {id: node.id, text: node.name || '', sprite, texture, key: '', classes: [], lines: [], width: 0, height: 0,
    under: false, z: 0, hidden: true, rect: null, color: ''};
  tags.set(node.id, tag);
  return tag;
}
function dropLabel(id) {
  const tag = tags.get(id);
  if (!tag) return;
  LABELS.group?.remove(tag.sprite);
  tag.texture.dispose(); tag.sprite.material.dispose();
  tags.delete(id);
}
/* What a label shows from its classes, as the page's own styles would give it. */
function lookOf(classes, palette) {
  const is = name => classes.includes(name);
  const chosen = is('sel'), reach = is('reach');
  const color = is('work-broken') ? palette.broken
    : reach ? palette.text : is('dim') ? palette.muted : chosen ? palette.signal : palette.text;
  return {size: chosen ? LABEL.chosen : LABEL.size, weight: chosen || reach ? 600 : 500, family: palette.sans, color,
    ground: palette.ground, glow: reach ? [10, 6, 3] : []};  // a reached part's name glows; the rest have a shadow
}
/* Each frame: every label is put above its node at the node's depth and sized for the screen, and the labels that
 * fall on a nearer sphere or a nearer label are marked under. */
function layered() {
  const now = performance.now(), camera = G.camera(), area = $('#stage').getBoundingClientRect(), height = area.height || 1;
  const spread = camera.projectionMatrix.elements[5], ratio = G.renderer().getPixelRatio();
  const perPixel = depth => 2 * depth / (spread * height);   // world units a pixel spans at a depth
  const depthOf = node => -AT.set(node.x, node.y, node.z).applyMatrix4(camera.matrixWorldInverse).z;
  const palette = {text: css('--text'), muted: css('--muted'), signal: css('--signal'), broken: css('--broken'),
    exclude: css('--exclude'), ground: css('--ground'), sans: css('--sans')};  // read once a frame, not once a label
  if (LABELS.group) LABELS.group.visible = LABELS.on;
  UP.set(0, 1, 0).applyQuaternion(camera.quaternion);
  RIGHT.set(1, 0, 0).applyQuaternion(camera.quaternion);
  // outward signs, web_signs' default, are drawn as they always were, held only from dropping below a readable floor;
  // facing signs take their physics preset's treatment, `LABEL_PRESETS`
  const how = signsFacing() ? LABEL_PRESETS[PHYS.name] || LABEL_PRESETS.organic : OUTWARD_SIGNS;
  const degree = new Map();  // a hub is a node with many joins: its name ranks after the selection and its neighbours
  if (how.declutter) for (const link of G.graphData().links) for (const end of [endOf(link.source), endOf(link.target)]) degree.set(end, (degree.get(end) || 0) + 1);
  const spheres = [], shown = [];
  let nearest = Infinity, deepest = -Infinity, placed = 0;
  middle.set(0, 0, 0);  // the map's middle, its nodes' mean place, which the names stand away from
  for (const node of G.graphData().nodes) {
    if (node.x === undefined) continue;
    const point = G.graph2ScreenCoords(node.x, node.y, node.z), depth = depthOf(node);
    spheres.push({id: node.id, x: point.x, y: point.y, far: depth, r: Math.cbrt(nodeSize(node)) * 3 / perPixel(depth)});
    middle.x += node.x; middle.y += node.y; middle.z += node.z; placed++;
    // the front and back of the map are those of the names in view, not of parts off the screen
    if (node.t === 'el' && depth > 0 && point.x >= 0 && point.x <= area.width && point.y >= 0 && point.y <= height) {
      nearest = Math.min(nearest, depth); deepest = Math.max(deepest, depth);
    }
  }
  if (placed) middle.divideScalar(placed);
  for (const node of G.graphData().nodes) {
    // A join has no name of its own on the map; selected, its title fades in on it, its receiver and the parts that
    // serve it, VIEW-038, and fades out when it is no longer selected.
    const titled = node.t === 'purpose' && (node.id === S.selected || tags.get(node.id)?.fade > 0);
    if (node.t !== 'el' && !titled) continue;
    const tag = labelFor(node);
    tag.text = titled ? joinTitle(node) : node.name || '';
    if (titled) {
      tag.fade = Math.max(0, Math.min(1, (tag.fade || 0) + (node.id === S.selected ? 1 : -1) * LABEL.titleStep));
      if (tag.fade > 0 && tag.fade < 1) wake3d();
    }
    tag.hidden = node.x === undefined;
    tag.sprite.visible = !tag.hidden && (!LABELS.only || LABELS.only.has(node.id));
    if (tag.hidden) continue;
    tag.classes = [node.id === S.selected ? 'sel' : S.neighbors.has(node.id) ? 'near' : S.selected ? 'dim' : '',
      ...(node.work || []).map(condition => `work-${condition}`), R.nodes.has(node.id) ? 'reach' : ''].filter(Boolean);
    const look = lookOf(tag.classes, palette);
    const depth = depthOf(node), unit = perPixel(Math.max(depth, 1e-3)), radius = Math.cbrt(nodeSize(node)) * 3;
    // Its letters are a set size in the map, in a set ratio to the balls, so the eye's own perspective makes it larger
    // near and smaller far as it does the nodes; `grown` is the size it is seen at, the pixels on the screen for one of
    // its canvas. From the front of the map in view to its back it fades, `back`.
    const back = deepest > nearest ? Math.min(1, Math.max(0, (depth - nearest) / (deepest - nearest))) : 0;
    const grown = LABEL.letters / LABEL.size / unit;
    const shape = wrapped(tag.text, look, tag.id === SMALL_NAME.id && small3d());
    tag.lookNow = look;
    tag.shape = shape;
    // Pinned in the map a set distance from its node, on the side away from the map's middle, so it is a thing of the
    // scene: it swings round its node as the map turns and goes behind the node as anything behind it does, and the
    // outer names stand outside the map, over the least of it.
    const ball = radius;
    // its letters held between the preset's least and most screen pixels, `how`, so they are read at any zoom
    const onScreen = grown * LABEL.size, held = Math.min(how.most, Math.max(how.least, onScreen)) / onScreen;
    const seen = grown * held, size = LABEL.letters / LABEL.size * held;
    const wide = shape.width * size, tall = shape.height * size;
    if (how.place === 'above') {  // over the node, as a cluster's names sit over its knot
      tag.sprite.position.set(node.x, node.y, node.z).addScaledVector(UP, ball + LABEL.out * 0.4 + tall / 2);
    } else if (how.place === 'beside') {  // to the side of a tree's flow, clear of the edges along it
      tag.sprite.position.set(node.x, node.y, node.z).addScaledVector(RIGHT, ball + LABEL.out * 0.4 + wide / 2);
    } else {
      OUT.set(node.x - middle.x, node.y - middle.y, node.z - middle.z);
      if (OUT.lengthSq() < 1e-6) OUT.copy(UP); else OUT.normalize();
      tag.sprite.position.set(node.x, node.y, node.z).addScaledVector(OUT, ball + LABEL.out);
    }
    // web_signs: outward, each sign facing away from the map's middle, upright in the map, and turned round on its
    // upright axis when the eye is on the map's side of it, so its letters read as written and are never mirrored; or
    // facing, each sign turned to the eye and upright to it, read the same from any side and at any angle
    if (signsFacing()) tag.sprite.quaternion.copy(G.camera().quaternion);
    else {
      OUT.set(node.x - middle.x, node.y - middle.y, node.z - middle.z);
      if (OUT.lengthSq() < 1e-6) OUT.copy(UP); else OUT.normalize();
      tag.sprite.up.copy(Math.abs(OUT.y) > 0.98 ? UP : Y_UP);
      const eye = G.camera().position, at = tag.sprite.position;
      const behind = (eye.x - at.x) * OUT.x + (eye.y - at.y) * OUT.y + (eye.z - at.z) * OUT.z < 0;
      tag.sprite.lookAt(AT.copy(at).addScaledVector(OUT, behind ? -1 : 1));
    }
    tag.sprite.scale.set(wide, tall, 1);
    const anchor = G.graph2ScreenCoords(tag.sprite.position.x, tag.sprite.position.y, tag.sprite.position.z);
    tag.rect = {left: anchor.x - shape.width * seen / 2, right: anchor.x + shape.width * seen / 2,
      top: anchor.y - shape.height * seen / 2, bottom: anchor.y + shape.height * seen / 2};
    tag.grown = seen;
    tag.ghost = titled ? 1 : ghostSign(node, seen, now);  // a part not built has a faint name, VIEW-027
    const rank = node.id === S.selected ? 0 : S.neighbors.has(node.id) ? 1 : 2;
    shown.push({tag, far: depth, look, back, rank, hub: degree.get(node.id) || 0});
  }
  // A preset that declutters leaves out a name that would overlap one ranked above it: the selection first, then its
  // neighbours, then the hubs by their joins, then the rest, nearest first; the selection and its neighbours always
  // keep theirs.
  if (how.declutter) {
    const kept = [];
    for (const label of [...shown].sort((one, two) => one.rank - two.rank || two.hub - one.hub || one.far - two.far)) {
      const box = label.tag.rect;
      const clash = kept.some(other => !(box.right <= other.left || other.right <= box.left || box.bottom <= other.top || other.bottom <= box.top));
      if (clash && label.rank > 1) { label.tag.sprite.visible = false; label.out = true; continue; }
      kept.push(box);
    }
  }
  shown.sort((one, two) => one.far - two.far);
  shown.forEach((label, index) => {
    // the nearest label solid, the farthest at the preset's `farthest` of it, the rest between by their depth
    // and a part not built's name as faint as its ghost, `ghostSign`
    label.tag.sprite.material.opacity = (1 - (1 - how.farthest) * label.back) * (label.tag.fade ?? 1) * label.tag.ghost;
    const box = label.tag.rect;
    const behind = spheres.some(sphere => sphere.id !== label.tag.id && sphere.far < label.far &&
      Math.hypot(Math.max(box.left, Math.min(sphere.x, box.right)) - sphere.x,
                 Math.max(box.top, Math.min(sphere.y, box.bottom)) - sphere.y) < sphere.r);
    const covered = shown.slice(0, index).some(({tag: other, out}) => !out && !(box.right <= other.rect.left ||
      other.rect.right <= box.left || box.bottom <= other.rect.top || other.rect.bottom <= box.top));
    const tag = label.tag;
    tag.under = (behind || covered) && !(MEET.on && tag === tags.get(MEET.back?.id));
    tag.z = shown.length - index;
    if (tag.under) tag.classes.push('under');
    const look = lookOf(tag.classes, palette);
    // painted for the size it is drawn at, in steps, so a near label is as sharp as one at its own size
    const sharp = ratio * Math.min(LABEL.largest, Math.max(1, Math.ceil(tag.grown / LABEL.sharper) * LABEL.sharper));
    const key = [tag.text, fontOf(look), look.color, look.ground, look.glow, sharp, tag.shape.lines.length].join('|');
    if (key !== tag.key) { painted(tag, look, sharp, tag.shape); tag.key = key; }
  });
  metSign(MEET.on ? tags.get(MEET.back?.id) : null);
}
/* The met sign on the canvas, VIEW-005: while the camera meets a sign square on, the sign in the scene and its face
 * drawn flat on the screen look the same, so it is drawn on a layer over the map at the very rectangle its four
 * corners project to, frame by frame, and the sign in the scene is hidden. An edge passing through the sign's plane in
 * the map then never crosses its letters; when the meeting ends the sign in the scene is shown again where it was. */
const MET = {box: null, pen: null, corner: new THREE.Vector3()};
function metSign(tag) {
  if (!MET.box) {
    MET.box = h('canvas', {class: 'metsign', 'aria-hidden': 'true'});
    MET.box.hidden = true;
    $('#stage').append(MET.box);
    MET.pen = MET.box.getContext('2d');
  }
  const box = MET.box, pen = MET.pen;
  if (!tag || tag.hidden || !tag.texture.image.width) { if (!box.hidden) box.hidden = true; return; }
  const area = $('#stage').getBoundingClientRect(), ratio = window.devicePixelRatio || 1;
  const wide = Math.round(area.width * ratio), tall = Math.round(area.height * ratio);
  if (box.width !== wide || box.height !== tall) Object.assign(box, {width: wide, height: tall});
  tag.sprite.updateMatrixWorld();
  let left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
  for (const [x, y] of [[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]]) {
    const at = tag.sprite.localToWorld(MET.corner.set(x, y, 0)), seen = G.graph2ScreenCoords(at.x, at.y, at.z);
    left = Math.min(left, seen.x); right = Math.max(right, seen.x); top = Math.min(top, seen.y); bottom = Math.max(bottom, seen.y);
  }
  pen.setTransform(ratio, 0, 0, ratio, 0, 0);
  pen.clearRect(0, 0, area.width, area.height);
  pen.globalAlpha = tag.sprite.material.opacity ?? 1;
  pen.drawImage(tag.texture.image, left, top, right - left, bottom - top);
  tag.sprite.visible = false;
  box.hidden = false;
}
/* The page's work for each frame of the 3D map, run in the render chain before anything is drawn, `create3D`: the
 * camera's flight, the colors, the wave, the figures, the text, the lights, the labels, the dots and the tooltip. It
 * says whether the next frame has something of its own to show, `FRAMES.busy`, and whether the dots flow,
 * `FRAMES.flowing`. */
function prepare3d() {
  const now = performance.now(), data = G.graphData();
  frameWhileSpreading(now, data);
  flight(now);
  G.camera().updateMatrixWorld();
  // A glass node is colored by the page, since the graph colors only the nodes it draws itself.
  for (const node of data.nodes) if (isGlass(node) && node.__threeObj?.material && !node.__threeObj.material.userData.pulsed)
    colored(node.__threeObj.material, dimmed(node) ? dim(colorOf(node)) : colorOf(node));
  DRIFT.value = reduced() ? 0 : now / 1000;  // the distortion of the glass drifts, VIEW-025
  wave3d(data);
  roam3d(data);
  ghost3d(data, now);
  let signaled = false;
  for (const node of data.nodes) {
    if (node.__threeObj && node.__threeObj.raycast !== picked) node.__threeObj.raycast = picked;
    if ((node.work && node.work.length) || node.__threeObj?.material?.userData.lit) paint3d(node);
    signaled = signaled || SIGNALS.some(([condition]) => has(node, condition));
  }
  layered();
  flow3d(now, data);
  // The bloom runs while a reach is lit and while any part has a record that gives off light, VIEW-029, for as long
  // as the record is open and not only at the moments of its flash: the glass's highlights are over full brightness
  // too, and a pass switched with each flash would make them blink with it.
  // ULTRA: in outer space ultra's own bloom glows on everything bright, and its sky, bodies and governor run here.
  if (BLOOM) BLOOM.enabled = !ULTRA.on() && (Boolean(R.key) || signaled);
  ULTRA.frame(now, data);
  placeTip();
  showModes3d();
  FRAMES.busy = !reduced() && (Boolean(R.key) || ROAM.figures.size > 0 || GHOSTS.built.size > 0 || signaled || mascotAwake());
  FRAMES.flowing = !reduced() && FLOW.count > 0 && FLOW.held === null;
}
/* What travels the map, VIEW-005, drawn so the map reads as a working system: who asks whom, which way the data goes,
 * and what gets written down because of it. Only the selected node's joins flow, those it receives on and those it
 * serves, through their purpose vertex, as in the 2D map; with nothing selected no join flows and a large map costs
 * nothing. Three things travel, each with a look of its own so they tell apart at a glance, and each smaller than
 * any node:
 *  - a request: one tiny white dot that glimmers, from the receiver through the join's purpose vertex to each element
 *    the join holds. A join asks when its information flow direction, its ifd, has the receiver take something:
 *    receives, or both.
 *  - the reply: a train of small separate dots, evenly spaced, in the colour of the element the data comes from, the
 *    last few fading, `fxTrain`, leaving the moment the request arrives and running the way the data goes: back to the
 *    receiver when it receives, one train each way when both. So a request reads as one dot going out and a reply as a
 *    stream coming back; the number of dots can carry how much data later.
 *  - a record: a small card in the record colour, --record, on a join whose receiver sends (ifd sends, or none
 *    recorded, which the 2D arrows also draw as sending): what an element pushes on to the store or the log it feeds.
 *    It lands with a ring that opens on the element that takes it.
 * An element that answers a request sends its records the moment it answers, so a request, its answer and the records
 * it leaves behind run as one chain: a data-access element that is asked and writes to the database shows its writes
 * landing there as it answers. An element nobody asks sends on a clock of its own. All of it is read from the joins
 * and their ifd; no element is named.
 * A join's cycle is its request, `ask` seconds, the reply, `reply` seconds, then a wait of (random + random) times the
 * setting web_pulse_ms, a fresh wait every cycle, bunched about it with now and then a quick one or a slow one; a
 * record takes `send` seconds and its ring `burst`. Each join keeps its own clock, so the map never pulses in step.
 * Everything moves by the time that passed, on FLOW.clock, so it flows at one speed at any frame rate, and only while
 * the map draws frames, `FRAMES`, so a page left alone rests; with reduced motion nothing flows.
 * What agents really do is drawn in the same looks, `bright` times larger and brighter so it reads as real, wherever it
 * happens, selected or not, `flowLive`: an agent's session starting sends a request from the map's primary node to its
 * ticket's node; each tool call of a running agent sends a request from its ticket's node to every part of the map the
 * call touched and the reply back, and an edit leaves a record there; a note, an item or a work record written on a
 * node lands there as a record. They come from the page's event stream as they happen; web_live_flow turns them off.
 * The 3D map draws all of it as two objects of its scene, points and line segments filled again each frame, so a
 * larger map adds no objects; a point is sized in map units but held between a few pixels, so nothing swells near the
 * camera. The selected node's edges in the 2D map carry the same, `flows2d`. The graph library's own particle, one to
 * a link, is never drawn while the page draws the flow: `held`, a share of the way, shows it held there instead,
 * `dots3d`, so a browser check can read a dot over a node. */
const FLOW = {clock: 0, last: 0, held: null, count: 0, ask: 0.45, reply: 1.6, send: 0.8, burst: 0.55, mean: 3,
  streak: 0.3, trail: 0.06, bright: 1.35, live: [], net: null, mode: null, fades: new Map(), liveFade: 1, ease: 6};
const cycles = new Map();  // each join's current cycle: when it began on FLOW.clock, its wait, and whether it answered
/* A join's cycle at this moment; `active` is how long a cycle shows. A `driven` join sends its records only when its
 * receiver answers a request, `recorded`, so it has no clock of its own. */
function cycleOf(join, active, driven = false) {
  let cycle = cycles.get(join);
  if (!cycle || cycle.driven !== driven) cycles.set(join, cycle = driven
    ? {at: -Infinity, wait: Infinity, driven, answered: true}
    : {at: FLOW.clock - Math.random() * 2 * pulseMean(), wait: 0, driven, answered: false, amount: dataAmount()});
  while (FLOW.clock - cycle.at > active + cycle.wait) {
    cycle.at += active + cycle.wait;
    cycle.wait = (Math.random() + Math.random()) * pulseMean();
    cycle.answered = false;
    cycle.amount = dataAmount();
  }
  return cycle;
}
// how much data a reply carries, a fresh amount each cycle: 6 to 18 dots, bunched about 12, like the waits, so a
// reply is plainly more than the one spark of its request and the way the data goes can be read
const dataAmount = () => 6 + Math.floor((Math.random() + Math.random()) * 6.5);
const asksOf = join => join?.ifd === 'receives' || join?.ifd === 'both';
// the usual wait between a join's cycles, web_pulse_ms, `mean` until the page has read it
const pulseMean = () => (Number(WS.view().pulse_ms) || FLOW.mean * 1000) / 1000;
/* Whether a join's flow is drawn: only the selected node's joins, those it receives on and those it serves, through
 * their purpose vertex, as the 2D map draws them; with nothing selected no join flows, so a large map costs nothing. */
function flowShown(join) {
  const mode = flowModeNow(), chosen = S.selected;
  if (mode === 'all') return Boolean(join);
  if (mode !== 'selected') return false;
  return Boolean(chosen && join && (join.receiver === chosen || join.providers.includes(chosen) || chosen === 'p:' + join.id));
}
/* Which joins flow, web_flow_mode: off, none and no agents' activity either; selected, the selected node's joins, the
 * default; all, every join; live, only what agents really do. `window.metaform.flowMode` changes it for the page, and
 * the mode bar and the View menu offer it; a change eases the dots in or out, `FLOW.fades`, never cutting them. */
const FLOW_MODE_LIST = [{name: 'off', label: 'Off', help: 'No dots flow, and agents\' activity is not drawn.'},
  {name: 'selected', label: 'Selection', help: "Dots flow along the selected node's joins, and agents' activity shows."},
  {name: 'all', label: 'All', help: "Dots flow along every join, and agents' activity shows."},
  {name: 'live', label: 'Live', help: 'Only what agents really do is drawn.'}];
const flowModeNow = () => FLOW.mode || (FLOW_MODE_LIST.some(one => one.name === WS.view().flow_mode) ? WS.view().flow_mode : 'selected');
function flowMode(name) {
  if (FLOW_MODE_LIST.some(one => one.name === name) && name !== FLOW.mode) {
    FLOW.mode = name;
    wake3d(1500);
    wake2d();
  }
  return flowModeNow();
}
/* Who asks whom, read again only when the joins change: each join by its id, the elements some join asks, which
 * answer, and the joins each element sends records on. */
function flowNet() {
  if (FLOW.net?.joins === S.joins && FLOW.net.size === S.joins.length) return FLOW.net;
  const byId = new Map(), answering = new Set(), sends = new Map();
  for (const join of S.joins) {
    byId.set(join.id, join);
    if (asksOf(join)) for (const id of join.providers) answering.add(id);
    else sends.set(join.receiver, [...(sends.get(join.receiver) || []), join.id]);
  }
  return FLOW.net = {joins: S.joins, size: S.joins.length, byId, answering, sends};
}
/* One join's flow at this moment: whether it asks, and how long since its cycle began. The moment its request reaches
 * the elements it holds they answer, and each sends its records then. */
function flowAt(join) {
  const net = flowNet();
  if (asksOf(join)) {
    const cycle = cycleOf(join.id, FLOW.ask + FLOW.reply), since = FLOW.clock - cycle.at;
    if (since >= FLOW.ask && !cycle.answered) {
      cycle.answered = true;
      if (since < FLOW.ask + FLOW.reply)
        for (const id of join.providers) for (const sent of net.sends.get(id) || []) recorded(sent);
    }
    return {asks: true, since, amount: cycle.amount};
  }
  const cycle = cycleOf(join.id, FLOW.send + FLOW.burst, net.answering.has(join.receiver));
  return {asks: false, since: FLOW.clock - cycle.at};
}
function recorded(join) {  // a record leaves on the join now, unless one is still on its way
  const cycle = cycleOf(join, FLOW.send + FLOW.burst, true);
  if (FLOW.clock - cycle.at >= FLOW.send) cycle.at = FLOW.clock;
}
function flowTick(now) {  // the clock moves on by the time that passed, once a frame whichever map draws it
  if (now <= FLOW.last) return;
  FLOW.clock += Math.min(0.1, (now - (FLOW.last || now)) / 1000);
  FLOW.last = now;
}
/* What an agent really did, drawn in the flow's looks, VIEW-005: `start`, a request from the map's primary node to
 * the ticket's node as the agent's session begins; `touch`, a request from the agent's node to each node its tool
 * call touched and the answer back, with a record landing there too when the call wrote, `edit`; `record`, a record
 * landing on a node something was written to. Nodes are the map's node ids. */
function flowLive(kind, from, to, edit = false) {
  if (reduced() || WS.view().live_flow === false || flowModeNow() === 'off') return;
  const targets = (Array.isArray(to) ? to : [to]).filter(Boolean);
  if (!targets.length) return;
  const long = kind === 'start' ? 2 * FLOW.ask + FLOW.burst : kind === 'record' ? FLOW.send + FLOW.burst
    : FLOW.ask + Math.max(FLOW.reply, edit ? FLOW.send + FLOW.burst : FLOW.burst);
  FLOW.live.push({kind, from, to: targets, edit, at: FLOW.clock, long});
  if (FLOW.live.length > 120) FLOW.live.splice(0, FLOW.live.length - 120);
  wake3d(1000 * long + 200);
  wake2d();
}
const flowNode = place => place ? (place.kind === 'join' ? 'p:' + place.id : place.id) : null;
/* Where a running agent's tool calls reached, as its runner tells the page, `map.flow`: a request from the ticket's
 * node, or from the map's primary node for an agent with no ticket, to each part reached; a call that changes files
 * leaves a record there too. */
function flowEvent(payload) {
  if (!payload || payload.project !== S.project) return;
  const primary = G ? primaryOf(G.graphData())?.id : null;
  for (const flow of payload.flows || []) {
    flowLive('touch', flowNode(flow.from) || primary, (flow.to || []).map(flowNode), /^(edit|delete|move)$/.test(flow.action));
    figureReached(flow.work_id, flowNode(flow.to?.[0]));  // its figure reaches toward what the call touched
  }
}
/* A note, an item or a property written on a node, read from the ops the page applies, lands there as a record. */
function flowWritten(ops) {
  const at = new Set();
  for (const op of ops) {
    if (op.op === 'remove' || (op.kind !== 'item' && op.kind !== 'property')) continue;
    const held = S.items.get((op.kind === 'item' ? 'i:' : 'r:') + op.id)?.item;
    const place = op.kind === 'item' ? held?.target : held?.element_id ? {kind: 'element', id: held.element_id} : null;
    if (place) at.add(flowNode(place));
  }
  if (at.size) flowLive('record', null, [...at]);
}
/* A work record opened or changed on a node, each step an agent reports among them, lands there as a record. The first
 * read only learns the records. */
const WORKED = {seen: null, of: null};
function flowTickets(tickets) {
  const now = new Map(tickets.map(ticket => [ticket.id,
    [ticket.condition, ticket.note, ticket.task, ticket.steps_done, ticket.said?.length, ticket.done].join('|')]));
  const before = WORKED.of === `${S.project}|${S.base}` ? WORKED.seen : null, held = WORKED.tickets || new Map();
  Object.assign(WORKED, {seen: now, of: `${S.project}|${S.base}`, tickets: new Map(tickets.map(ticket => [ticket.id, ticket]))});
  if (!before) return;
  // a ticket the open work no longer holds was closed: the mascot says it is done
  for (const [id, ticket] of held) if (!now.has(id) && before.has(id))
    attend(`done:${id}`, `Ticket done: ${ticketPart(ticket)}`, ticketNode(ticket), () => select(ticketNode(ticket), true));
  const at = new Set(tickets.filter(ticket => before.get(ticket.id) !== now.get(ticket.id)).map(ticketNode));
  if (at.size) flowLive('record', null, [...at]);
  for (const ticket of tickets) if (ticket.done && before.has(ticket.id) && !String(before.get(ticket.id)).endsWith('|' + ticket.done))
    attend(`done:${ticket.id}`, `Ticket done: ${ticketPart(ticket)}`, ticketNode(ticket), () => select(ticketNode(ticket), true));
}
/* The 3D flow's two objects: points, each a dot, a card or a ring by its shape, and line segments for the streaks'
 * tails, both added to what is behind them so they read as light. Their buffers grow as needed and are filled again
 * each frame. A point's size is in map units, held between a few pixels and its own most, `look`. */
const FX = {scene: null, points: null, lines: null, n: 0, m: 0, cap: 0, capL: 0, tints: new Map(), fade: 1};
const WHITE = new THREE.Color(1, 1, 1), LIT = new THREE.Color();
function tintOf(color) {
  if (!FX.tints.has(color)) FX.tints.set(color, color ? new THREE.Color(color) : WHITE.clone());
  return FX.tints.get(color);
}
function fxMake() {
  const scene = G.scene();
  if (FX.scene === scene) return;
  FX.scene = scene;
  const light = {transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false};
  // What travels runs along the middle of a link, inside its fiber, which is drawn with depth: each point is set a
  // little toward the eye for the depth test alone, where it is drawn on the screen unchanged, so the fiber never
  // hides it and a node still does.
  const NEAR = `
      vec4 near(vec4 at) { float far = length(at.xyz); at.xyz *= max(0.01, far - 1.5) / far; return at; }`;
  FX.points = new THREE.Points(new THREE.BufferGeometry(), new THREE.ShaderMaterial({...light,
    uniforms: {scale: {value: 1}, ratio: {value: 1}},
    vertexShader: `attribute vec4 tint; attribute vec4 look; uniform float scale; uniform float ratio;
      varying vec4 vTint; varying float vShape;${NEAR}
      void main() {
        vec4 at = near(modelViewMatrix * vec4(position, 1.0));
        gl_Position = projectionMatrix * at;
        gl_PointSize = clamp(look.x * scale / max(0.001, -at.z), look.z * ratio, max(look.z, look.w) * ratio);
        vTint = tint; vShape = look.y;
      }`,
    // a dot is a white-hot core in a glow of its colour; a card, a small lit rectangle with two lines across it; a
    // ring, a thin circle
    fragmentShader: `varying vec4 vTint; varying float vShape;
      void main() {
        vec2 c = gl_PointCoord * 2.0 - 1.0;
        float d = length(c), a = 1.0;
        vec3 color = vTint.rgb;
        if (vShape < 0.5) {
          a = max(smoothstep(0.6, 0.35, d), 0.7 * pow(max(0.0, 1.0 - d), 1.5));
          color = mix(color, vec3(1.0), 0.25 + 0.75 * smoothstep(0.6, 0.1, d));
        } else if (vShape < 1.5) {
          vec2 q = abs(c) / vec2(0.86, 0.64);
          float edge = max(q.x, q.y);
          if (edge > 1.0) discard;
          float line = step(abs(abs(c.y) - 0.2), 0.08) * step(abs(c.x), 0.55);
          color = mix(color, vec3(1.0), 0.35 * smoothstep(0.7, 0.95, edge)) * (1.0 - 0.5 * line);
        } else {
          a = smoothstep(0.14, 0.0, abs(d - 0.84));
        }
        if (a * vTint.a < 0.004) discard;
        gl_FragColor = vec4(color, a * vTint.a);
      }`}));
  FX.lines = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.ShaderMaterial({...light,
    vertexShader: `attribute vec3 shade; varying vec3 vShade;${NEAR}
      void main() { gl_Position = projectionMatrix * near(modelViewMatrix * vec4(position, 1.0)); vShade = shade; }`,
    fragmentShader: `varying vec3 vShade; void main() { gl_FragColor = vec4(vShade, 1.0); }`}));
  for (const object of [FX.points, FX.lines]) { object.frustumCulled = false; object.renderOrder = 10; scene.add(object); }
  FX.cap = FX.capL = 0;
  fxGrow(true); fxGrow(false);
}
function fxGrow(points) {
  const grown = (old, size) => { const made = new Float32Array(size); if (old) made.set(old.subarray(0, Math.min(old.length, size))); return made; };
  const geometry = (points ? FX.points : FX.lines).geometry;
  const put = (name, array, width) => geometry.setAttribute(name, new THREE.BufferAttribute(array, width).setUsage(THREE.DynamicDrawUsage));
  if (points) {
    FX.cap = Math.max(512, FX.cap * 2);
    put('position', FX.pos = grown(FX.pos, FX.cap * 3), 3);
    put('tint', FX.tint = grown(FX.tint, FX.cap * 4), 4);
    put('look', FX.look = grown(FX.look, FX.cap * 4), 4);
  } else {
    FX.capL = Math.max(1024, FX.capL * 2);
    put('position', FX.lpos = grown(FX.lpos, FX.capL * 3), 3);
    put('shade', FX.lcol = grown(FX.lcol, FX.capL * 3), 3);
  }
}
// shape: 0 a dot, 1 a card, 2 a ring; `size` across in map units, held between `least` and `most` pixels
function fxDot(at, size, color, alpha, shape, least, most) {
  if (FX.n === FX.cap) fxGrow(true);
  const i = FX.n++;
  FX.pos[i * 3] = at.x; FX.pos[i * 3 + 1] = at.y; FX.pos[i * 3 + 2] = at.z;
  FX.tint[i * 4] = color.r; FX.tint[i * 4 + 1] = color.g; FX.tint[i * 4 + 2] = color.b; FX.tint[i * 4 + 3] = alpha * FX.fade;
  FX.look[i * 4] = size; FX.look[i * 4 + 1] = shape; FX.look[i * 4 + 2] = least; FX.look[i * 4 + 3] = most;
}
function fxLine(a, b, color, glowA, glowB) {  // a segment fading from glowA to glowB, its colour toward white as it glows
  if (FX.m + 2 > FX.capL) fxGrow(false);
  for (const [at, shown] of [[a, glowA], [b, glowB]]) {
    const glow = shown * FX.fade, i = FX.m++, white = 0.6 * glow;
    FX.lpos[i * 3] = at.x; FX.lpos[i * 3 + 1] = at.y; FX.lpos[i * 3 + 2] = at.z;
    FX.lcol[i * 3] = (color.r + (1 - color.r) * white) * glow;
    FX.lcol[i * 3 + 1] = (color.g + (1 - color.g) * white) * glow;
    FX.lcol[i * 3 + 2] = (color.b + (1 - color.b) * white) * glow;
  }
}
function fxDone() {
  if (!FX.points) return;
  const renderer = G.renderer(), camera = G.camera();
  FX.scale = FX.points.material.uniforms.scale.value = renderer.domElement.height / (2 * Math.tan((camera.fov || 50) * Math.PI / 360));
  FX.ratio = FX.points.material.uniforms.ratio.value = renderer.getPixelRatio();
  for (const [object, count] of [[FX.points, FX.n], [FX.lines, FX.m]]) {
    object.visible = count > 0;
    object.geometry.setDrawRange(0, count);
    for (const attribute of Object.values(object.geometry.attributes)) attribute.needsUpdate = count > 0;
  }
}
/* The point a share of the way along a way of nodes, each leg an equal share: a join's way is its receiver, its
 * purpose vertex and one element it holds, so the purpose vertex is half way. */
function wayAt(way, share, out = {x: 0, y: 0, z: 0}) {
  const legs = way.length - 1, s = Math.min(1, Math.max(0, share)) * legs, i = Math.min(legs - 1, Math.floor(s)), u = s - i;
  const a = way[i], b = way[i + 1];
  out.x = a.x + (b.x - a.x) * u; out.y = a.y + (b.y - a.y) * u; out.z = a.z + (b.z - a.z) * u;
  return out;
}
const TAIL = Array.from({length: 11}, () => ({x: 0, y: 0, z: 0}));
function fxRequest(way, t, live) {  // tiny, white, glimmering, with a short faint trail that says which way it goes
  const k = live ? FLOW.bright : 1, glimmer = 0.75 + 0.25 * Math.sin(FLOW.clock * 16);
  const head = wayAt(way, t, TAIL[0]), tail = wayAt(way, t - FLOW.trail, TAIL[1]);
  if (t > FLOW.trail) fxLine(tail, head, WHITE, 0, 0.5 * k);
  fxDot(head, 0.6 * k, WHITE, glimmer, 0, 6 * k, 8 * k);
}
/* A reply: a burst of separate dots, evenly spaced, one after another along the join the way the data goes, in the
 * colour of the element it comes from, the last few fading; each dot about twice a request's spark, so the two are
 * never confused. `count` is how much data it carries. The dots are spaced on the screen at least a little more than
 * twice their size apart, so the burst reads as dots at any zoom; a join too short for all of them shows fewer. */
function fxTrain(way, t, back, color, live, count = 12) {
  const k = live ? FLOW.bright : 1, dot = 10 * k;
  color = LIT.copy(color).lerp(WHITE, 0.35);  // a little lighter than the element, so it reads over the fibers
  let long = 0;
  for (let i = 1; i < way.length; i++) long += Math.hypot(way[i].x - way[i - 1].x, way[i].y - way[i - 1].y, way[i].z - way[i - 1].z);
  const middle = wayAt(way, 0.5, TAIL[1]), far = Math.max(1e-3, G.camera().position.distanceTo(AT.set(middle.x, middle.y, middle.z)));
  const across = long * (FX.scale || 800) / (FX.ratio || 1) / far;  // the whole way in pixels on the screen
  const spacing = Math.max(0.03, dot * 2.3 / Math.max(1, across));
  const shown = Math.max(3, Math.min(count, Math.floor(0.9 / spacing) + 1));
  const head = t * (1 + spacing * (shown - 1));  // the last dot arrives as the reply ends
  for (let i = 0; i < shown; i++) {
    const s = head - spacing * i;
    if (s < 0 || s > 1) continue;
    const fade = i < shown - 3 ? 1 : 1 - (i - (shown - 4)) / 4;  // the last few fade
    fxDot(wayAt(way, back ? 1 - s : s, TAIL[0]), 1.3 * k, color, fade, 0, dot, dot * 1.4);
  }
}
function fxBurst(node, u, color, live) {  // a ring that opens on a node as something lands on it, and a brief flash
  const k = live ? FLOW.bright : 1, ball = node.t ? ballOf(node) : 3;
  fxDot(node, ball * 2.4 * (1 + 0.9 * u) * k, color, Math.pow(1 - u, 1.5) * (live ? 1 : 0.85), 2, 20 * (1 + u) * k, 260);
  fxDot(node, ball * 1.4, color, Math.pow(1 - u, 3) * 0.45 * k, 0, 8 * k, 160);
  if (live && u > 0.3)
    fxDot(node, ball * 2.4 * (1 + 1.4 * (u - 0.3)), color, Math.pow(1 - u, 2) * 0.6, 2, 12 * (1 + 2 * (u - 0.3)), 300);
}
function fxRecord(way, since, color, live) {  // a card on its way, then the ring where it lands
  const k = live ? FLOW.bright : 1;
  if (since < FLOW.send) {
    const t = since / FLOW.send, eased = t * t * (3 - 2 * t);
    return fxDot(wayAt(way, eased, TAIL[0]), 2.4 * k, color, 1, 1, 12 * k, 16 * k);
  }
  const u = (since - FLOW.send) / FLOW.burst;
  if (u < 1) fxBurst(way[way.length - 1], u, color, live);
}
/* What agents really did, as it came from the event stream, `flowLive`: each trip drawn until it is over. */
function live3d(data, colors) {
  FLOW.live = FLOW.live.filter(trip => FLOW.clock - trip.at < trip.long);
  if (!FLOW.live.length) return;
  const nodes = new Map(data.nodes.map(node => [node.id, node]));
  for (const trip of FLOW.live) {
    const since = FLOW.clock - trip.at, from = nodes.get(trip.from);
    for (const id of trip.to) {
      const to = nodes.get(id);
      if (!to || to.x === undefined) continue;
      if (trip.kind === 'record') {  // dropped onto the node from just above it
        fxRecord([{x: to.x, y: to.y + ballOf(to) * 4, z: to.z}, to], since, colors.record, true);
        continue;
      }
      const way = from && from.x !== undefined && from !== to ? [from, to] : null;
      const going = trip.kind === 'start' ? 2 * FLOW.ask : FLOW.ask;
      if (since < going) { if (way) fxRequest(way, since / going, true); continue; }
      const after = since - going;
      if (trip.kind === 'start') { if (after < FLOW.burst) fxBurst(to, after / FLOW.burst, colors.signal, true); continue; }
      if (way && after < FLOW.reply) fxTrain(way, after / FLOW.reply, true, tintOf(colorOf(to)), true);
      if (trip.edit) fxRecord(way || [to, to], after, colors.record, true);
      else if (!way && after < FLOW.burst) fxBurst(to, after / FLOW.burst, colors.signal, true);
    }
  }
}
const phases = new Map();
function phaseOf(join) {
  if (!phases.has(join)) {
    let hash = 0x811c9dc5;  // FNV-1a over the join's id, so a join keeps its phase on every load
    for (const char of String(join)) { hash ^= char.codePointAt(0); hash = Math.imul(hash, 0x01000193) >>> 0; }
    phases.set(join, hash / 0x100000000);
  }
  return phases.get(join);
}
function flow3d(now, data) {
  flowTick(now);
  if (FLOW.held === null) fxMake();
  FX.n = FX.m = 0;
  let count = 0;
  const ways = new Map();  // each join drawn: its receiver, its purpose vertex, the elements drawn that it holds
  for (const link of data.links) {
    const dots = link.__photonsObj?.children, from = link.source, to = link.target;
    if (!dots?.length || !link.__photonsObj.parent || from?.x === undefined || to?.x === undefined) continue;
    count++;
    if (FLOW.held !== null) {
      const dx = to.x - from.x, dy = to.y - from.y, dz = to.z - from.z;
      for (const dot of dots) {
        Object.assign(dot, {visible: true, __progressRatio: FLOW.held});
        dot.position.set(from.x + dx * FLOW.held, from.y + dy * FLOW.held, from.z + dz * FLOW.held);
        dot.scale.setScalar(1);
      }
      continue;
    }
    for (const dot of dots) dot.visible = false;
    let way = ways.get(link.join);
    if (!way) ways.set(link.join, way = {receiver: null, purpose: null, providers: [], color: dots[0].material.color});
    if (link.k === 'purpose') Object.assign(way, {receiver: from, purpose: to}); else way.providers.push(to);
  }
  FLOW.count = FLOW.held !== null ? count : 0;
  if (FLOW.held === null && !reduced()) {
    const colors = {record: tintOf(css('--record')), signal: tintOf(css('--signal'))}, net = flowNet();
    // a join's dots ease in as it starts to flow, and out as it stops, by the flow's own clock
    const ease = 1 - Math.exp(-Math.max(0, FLOW.clock - (FLOW.fadedAt ?? FLOW.clock)) * FLOW.ease);
    FLOW.fadedAt = FLOW.clock;
    for (const [id, way] of ways) {
      const join = net.byId.get(id);
      if (!join || !way.receiver) continue;
      const fade = (FLOW.fades.get(id) ?? 0) + ((flowShown(join) ? 1 : 0) - (FLOW.fades.get(id) ?? 0)) * ease;
      if (fade < 0.01) { FLOW.fades.delete(id); continue; }  // only the joins the mode shows flow, `flowShown`
      FLOW.fades.set(id, fade);
      FX.fade = fade;
      FLOW.count++;
      const {asks, since, amount} = flowAt(join);
      for (const to of way.providers) {
        const path = [way.receiver, way.purpose, to];
        if (!asks) fxRecord(path, since, colors.record, false);
        else if (since < FLOW.ask) fxRequest(path, since / FLOW.ask, false);
        else if (since < FLOW.ask + FLOW.reply) for (const back of join.ifd === 'both' ? [true, false] : [true])
          fxTrain(path, (since - FLOW.ask) / FLOW.reply, back, tintOf(colorOf(back ? to : way.receiver)), false, amount);
      }
    }
    FLOW.liveFade += ((flowModeNow() === 'off' ? 0 : 1) - FLOW.liveFade) * ease;
    FX.fade = FLOW.liveFade;
    live3d(data, colors);
    FX.fade = 1;
    fxMarks(tintOf(css('--muted')));  // the trails the figures leave
    if (EYE.debug) eyeDebug3d();  // each figure's eye anchor and gaze, for a check of `look`
  }
  fxDone();
}
/* The 3D view draws the map, or the memory network of a node while one is open, VIEW-031. `previous` holds where
 * each node stood, the positions of what is drawn now unless given. */
function draw3D(previous = null) {
  if (!G) return;
  if (MEM.key && S.loading) return;  // a memory network is drawn once the map and its items are read again
  previous = previous || new Map(G.graphData().nodes.map(node => [node.id, node]));
  const data = MEM.key ? memoryData() : graphData();
  for (const node of data.nodes) {  // keep drawn positions, so the picture does not jump as pages arrive
    const known = previous.get(node.id);
    if (known) Object.assign(node, {x: known.x, y: known.y, z: known.z, vx: known.vx, vy: known.vy, vz: known.vz,
      fx: known.fx, fy: known.fy, fz: known.fz});
  }
  arrivals(data);
  const named = new Set(data.nodes.filter(node => node.t === 'el').map(node => node.id));
  for (const id of [...tags.keys()]) if (!named.has(id)) dropLabel(id);
  if (hovered) hovered = data.nodes.find(node => node.id === hovered.id) || null;
  $('#tip3d').hidden = !hovered;
  if (inPlace(data)) return;
  // A memory network is laid out before it is shown, so it opens settled and whole in view; the map keeps its own
  // layout running from where each node stands.
  G.warmupTicks(MEM.key ? 120 : 0);
  G.graphData(data);
  applyPhysics(PHYS.name, false);  // its chains of service and its parts read again
  V3.layouts++;
}
/* A node new to a map already laid out starts beside a node it is linked to, a little way off in a direction its id
 * gives, so it grows out of the part it belongs to and the layout only eases it into place: started where the layout
 * puts a node with no place, around the middle of the map, it was pulled across the whole map and the nodes it passed
 * were shaken. Nodes linked to nothing placed, and every node of a map with nothing placed yet or with much of it new,
 * are left to the layout, which warms itself for the share of nodes it has to place. */
function arrivals(data) {
  const fresh = data.nodes.filter(node => node.x === undefined).length;
  if (!fresh || fresh === data.nodes.length || fresh > Math.max(3, data.nodes.length * 0.15)) return;
  const byId = new Map(data.nodes.map(node => [node.id, node])), linked = new Map();
  for (const link of data.links) {
    const one = endOf(link.source), two = endOf(link.target);
    (linked.get(one) || linked.set(one, []).get(one)).push(two);
    (linked.get(two) || linked.set(two, []).get(two)).push(one);
  }
  for (let round = 0, placedSome = true; placedSome && round < 8; round++) {  // a chain of new nodes, one link at a time
    placedSome = false;
    for (const node of data.nodes) {
      if (node.x !== undefined) continue;
      const beside = (linked.get(node.id) || []).map(id => byId.get(id)).find(other => other && other.x !== undefined);
      if (!beside) continue;
      const turn = phaseOf(node.id) * 2 * Math.PI, rise = phaseOf(node.id + '^') * 2 - 1, out = Math.sqrt(1 - rise * rise);
      const apart = ballOf(beside) + ballOf(node) + 6;
      Object.assign(node, {x: beside.x + Math.cos(turn) * out * apart, y: beside.y + rise * apart, z: beside.z + Math.sin(turn) * out * apart,
        vx: 0, vy: 0, vz: 0});
      placedSome = true;
    }
  }
}
/* New data starts the 3D layout again at full strength, which shakes the map, so a change that adds or removes no node
 * and no link is copied onto what is drawn, which is drawn again where it stands, VIEW-018. */
const PLACE = new Set(['x', 'y', 'z', 'vx', 'vy', 'vz', 'fx', 'fy', 'fz', 'index', '__threeObj', 'source', 'target']);
const end = value => value && typeof value === 'object' ? value.id : value;
const linkKey = link => `${end(link.source)}>${end(link.target)}>${link.k}`;
function inPlace(data) {
  const shown = G.graphData();
  if (shown.nodes.length !== data.nodes.length || shown.links.length !== data.links.length) return false;
  const nodes = new Map(shown.nodes.map(node => [node.id, node]));
  if (data.nodes.some(node => !nodes.has(node.id))) return false;
  const links = new Map();
  for (const link of shown.links) (links.get(linkKey(link)) || links.set(linkKey(link), []).get(linkKey(link))).push(link);
  const pairs = [];
  for (const link of data.links) {
    const same = links.get(linkKey(link));
    if (!same?.length) return false;
    pairs.push([same.shift(), link]);
  }
  const copy = (into, from) => { for (const [key, value] of Object.entries(from)) if (!PLACE.has(key)) into[key] = value; };
  for (const node of data.nodes) copy(nodes.get(node.id), node);
  for (const [into, from] of pairs) copy(into, from);
  G.refresh();
  return true;
}
/* A theme recolors both views in place, VIEW-023: the 3D view rereads its colors, the 2D map is drawn again. The
 * choice is the viewer's own, kept in this browser. */
/* The theme is the one choice of look: space draws the 3D map in outer space, ULTRA, and every other theme flat. */
const PLAIN = {last: 'black'};
function setTheme(name, keep = true) {
  document.documentElement.dataset.theme = name;
  if (name !== 'space') PLAIN.last = name;
  if ($('#theme') && $('#theme').value !== name) $('#theme').value = name;
  ULTRA.setting(name === 'space' ? 'ultra' : 'clean');
  if (keep && S.project) posted('/api/settings', {key: 'web_graphics', value: name === 'space' ? 'ultra' : 'clean'});
  try { localStorage.setItem('metaform.theme', name); } catch (error) { /* storage can be blocked; the theme still shows */ }
  if (G) G.backgroundColor(css('--ground')).linkOpacity(Number(css('--link-opacity'))).nodeColor(G.nodeColor())
    .linkColor(G.linkColor()).linkDirectionalParticleColor(G.linkDirectionalParticleColor());
  if (G) grounded();
  mermaidReady = false;
  build2D();
}
$('#theme').value = document.documentElement.dataset.theme;
if ($('#theme').selectedIndex < 0) $('#theme').value = document.documentElement.dataset.theme = 'space';  // a kept name that is no longer a theme
$('#theme').onchange = () => setTheme($('#theme').value);
/* The 2D map's framing, VIEW-041, the same in the large area, the small one and inside a node: its fit, 2, the whole
 * map, its width or its height in the pane; its zoom on a selection, 3, Neighbors, the node and every part one join
 * away filling the view, Distance, the node at the distance set with 1, or Off, the fit kept; and that distance, set
 * by example: 1, the wheel, and 1 again keep the height the map's text is then drawn at. Letting go of the selection
 * goes back to the fit; 0 puts the fit and the zoom back. A choice shows a moment at the map's top right and is kept in
 * the web module's settings, web_map_fit, web_map_zoom and web_map_distance. `page` holds the page's text sizes the
 * default distance is read from, `pageText`, and `labels` each drawing's own label size. The 3D map's zoom is its own,
 * VIEW-005. */
const FITS2D = [['all', 'Fit all'], ['width', 'Fit width'], ['height', 'Fit height']];
const ZOOMS2D = [['neighbors', 'Zoom: neighbors'], ['distance', 'Zoom: distance'], ['off', 'Zoom off']];
/* 7, 8 and 9 choose the 2D map's direction, Auto, left to right and top to bottom, kept in the web_map_direction
 * setting, which the 2D layout reads; the map is drawn again in it. */
const DIRECTION_KEYS = {7: 'auto', 8: 'across', 9: 'down'};
async function chooseDirection(direction) {
  if (!S.project) return;
  const done = await posted('/api/settings', {key: 'web_map_direction', value: direction});
  if (!done.ok) return toast(done.body.error || 'The direction was not saved.');
  PEEK.direction = direction;
  peekParts();
  toast(`The 2D map runs ${{auto: 'as suits its pane', across: 'left to right', down: 'top to bottom'}[direction]}.`);
  await build2D(false);
  if (S.selected) select(S.selected, false, true);
}
const MODE = {fit: 'all', zoom: 'neighbors', distance: 0, chosen: false, setting: null, box: null, note: 0, page: null,
  labels: new WeakMap()};
const MARGIN = 40;  // the most screen pixels shown beyond the map's edge where it runs past the pane, VIEW-041
/* The two views change places, VIEW-028: the 2D map takes the large area and the 3D map the small one, and back.
 * Each is then drawn for the area it has. The choice is the viewer's own, kept in this browser. */
async function swap(on, remember = true) {
  $('.app').classList.toggle('swapped', on);
  (on ? $('main') : $('#small')).append($('#map2d'));
  (on ? $('#small') : $('main')).append($('#big3d'));
  $('#swapBtn').title = on ? 'Put the 3D map back in the large area' : 'Put this map in the large area, and the 3D map here';
  $('#swap3dBtn').title = on ? 'Put this map back in the large area' : 'Put this map in the small area, and the 2D map here';
  if (remember) try { localStorage.setItem('metaform.swapped', on ? '1' : ''); } catch (error) { /* storage can be blocked; the swap still shows */ }
  resize();
  peekParts();  // the large map's bar holds the modes of the map now in the large area
  if (G) setTimeout(() => {
    // Keep a met name at the new area's share; an unfocused map still opens whole.
    if (S.selected && (on || V3.mode === 'zoom') && fly3d(S.selected)) return;
    if (on || V3.mode !== 'free') fit3d(600, on ? 24 : 60);
  }, 50);
  if (S.loading || !S.elements.size) return;
  await build2D(false);  // drawn for its new area, opening as it does on loading
  if (S.selected) select(S.selected, false, true);
}
// with the workspace, the two map panes exchange their places, saved with the layout
$('#swapBtn').onclick = $('#swap3dBtn').onclick = () => WS.swapMaps() || swap(!$('.app').classList.contains('swapped'));
/* The 3D map's own Fit goes between two views: the whole map, and close on the selected node. It moves the 3D map
 * only, as the 2D map's Fit moves the 2D map only. `auto` says the camera still shows the whole map as the page last
 * fitted it, with no hand and no selection having moved it since, so the layout may fit it again once it settles. */
const V3 = {whole: 0, fits: 0, layouts: 0, ticks: 0, auto: true, followed: 0, asked: false, focus: null, lens: null,
  mode: 'zoom'};  // `mode`, the large area's Whole, Zoom or Free, `setMode3d`
const away3d = () => G.camera().position.distanceTo(G.controls().target);
/* The 3D camera's flights, VIEW-008 and VIEW-028. A flight moves the point looked at and the camera's place around it
 * together: the point in a straight line, the camera around it by its turn, its tilt and the log of its distance, so it
 * swings round and moves in or out at an even pace rather than cutting through the map. Each part comes to rest as
 * the flight ends and starts at the speed it has, so a flight asked for while another runs carries on from it without
 * a jolt, and one from rest eases in. Between places far apart the camera draws back on the way, so where it goes is
 * in sight before it arrives. A flight is run each frame before anything is drawn, `prepare3d`, so the labels and the
 * tooltip follow it in the same frame. A hand on the camera ends it; with reduced motion the camera is put there at
 * once. */
const FLIGHT = {on: false, from: null, to: null, rate: null, start: 0, length: 1, back: 0, done: null};
const PARTS = ['x', 'y', 'z', 'turn', 'tilt', 'far'];
function cameraNow() {
  const camera = G.camera().position, target = G.controls().target;
  const dx = camera.x - target.x, dy = camera.y - target.y, dz = camera.z - target.z, far = Math.max(1e-6, Math.hypot(dx, dy, dz));
  return {x: target.x, y: target.y, z: target.z, turn: Math.atan2(dx, dz), tilt: Math.acos(Math.max(-1, Math.min(1, dy / far))),
    far: Math.log(far)};
}
function putCamera(at) {
  const camera = G.camera(), target = G.controls().target, far = Math.exp(at.far), across = Math.sin(at.tilt) * far;
  target.set(at.x, at.y, at.z);
  camera.position.set(at.x + across * Math.sin(at.turn), at.y + Math.cos(at.tilt) * far, at.z + across * Math.cos(at.turn));
  camera.lookAt(target);
  camera.updateMatrixWorld();
}
/* A cubic from `from`, leaving at `rate` a second, to rest at `to` after `length` seconds: its value and rate at `s`,
 * the share of the time gone. From rest it eases in and out. */
function hermite(from, to, rate, length, s) {
  const s2 = s * s, s3 = s2 * s;
  return [(2 * s3 - 3 * s2 + 1) * from + (s3 - 2 * s2 + s) * rate * length + (3 * s2 - 2 * s3) * to,
    ((6 * s2 - 6 * s) * from + (3 * s2 - 4 * s + 1) * rate * length + (6 * s - 6 * s2) * to) / length];
}
function flightAt(now) {
  const s = Math.min(1, Math.max(0, (now - FLIGHT.start) / 1000 / FLIGHT.length)), at = {}, rate = {};
  for (const part of PARTS) [at[part], rate[part]] = hermite(FLIGHT.from[part], FLIGHT.to[part], FLIGHT.rate[part], FLIGHT.length, s);
  // drawing back on the way, nothing at either end and at rest there
  at.far += FLIGHT.back * 16 * s * s * (1 - s) * (1 - s);
  rate.far += FLIGHT.back * 32 * s * (1 - s) * (1 - 2 * s) / FLIGHT.length;
  return {at, rate, s};
}
function flyTo(to, {length = null, done = null} = {}) {
  if (!G) return;
  V3.focus = null;
  meetEnds();  // every flight starts with the whole scene drawn again; a meeting clears its foreground on arrival
  const now = performance.now(), under = FLIGHT.on ? flightAt(now) : null, here = under ? under.at : cameraNow();
  const goal = {...to, turn: here.turn + Math.atan2(Math.sin(to.turn - here.turn), Math.cos(to.turn - here.turn)),
    tilt: Math.min(Math.PI - 0.05, Math.max(0.05, to.tilt))};
  const moved = Math.hypot(goal.x - here.x, goal.y - here.y, goal.z - here.z) / Math.exp(Math.max(here.far, goal.far));
  const turned = Math.abs(goal.turn - here.turn) + Math.abs(goal.tilt - here.tilt) + Math.abs(goal.far - here.far);
  if (reduced()) {
    Object.assign(FLIGHT, {on: false, done: null});
    putCamera(goal);
    wake3d();
    return done?.();
  }
  Object.assign(FLIGHT, {on: true, from: here, to: goal, start: now, done,
    rate: under ? under.rate : Object.fromEntries(PARTS.map(part => [part, 0])),
    length: length ?? Math.min(1.6, Math.max(0.6, 0.5 + 0.45 * Math.sqrt(moved + turned * 0.6))),
    back: Math.min(Math.log(1.7), 0.3 * Math.max(0, moved - 0.25))});
  wake3d();
}
function flight(now) {
  if (!FLIGHT.on) return;
  const {at, s} = flightAt(now);
  putCamera(at);
  if (s < 1) return;
  const done = FLIGHT.done;
  Object.assign(FLIGHT, {on: false, done: null});
  done?.();
}
/* Where the camera stands to show the given balls, {x, y, z, r}, whole on the screen with `room` pixels to spare and
 * room above for the labels, seen the way the camera looks now: the point looked at, which is the middle of what is
 * shown, or `toward` of the way from there to the ball `on`, and the distance, the least at which every ball is in
 * view. */
const LOOK = {back: new THREE.Vector3(), right: new THREE.Vector3(), up: new THREE.Vector3(), at: new THREE.Vector3()};
function framed(balls, {room = 60, on = null, toward = 0, facing = null, mass = 0} = {}) {
  // seen the way the camera looks now, or from `facing`, a turn and a tilt
  const here = {...cameraNow(), ...(facing || {})}, camera = G.camera(), box = $('#stage').getBoundingClientRect();
  const {back, right, up, at} = LOOK;
  back.set(Math.sin(here.tilt) * Math.sin(here.turn), Math.cos(here.tilt), Math.sin(here.tilt) * Math.cos(here.turn));
  right.crossVectors(camera.up, back);
  if (right.lengthSq() < 1e-8) right.set(1, 0, 0);
  right.normalize();
  up.crossVectors(back, right);
  const tall = Math.tan(camera.fov * Math.PI / 360), height = Math.max(1, box.height), width = Math.max(1, box.width);
  const spare = (pixels, of) => Math.max(0.25, 1 - 2 * pixels / of);
  // the room kept at the foot, `foot3d`: the frame fits the height above it, and is raised by half of it, below
  const foot = Math.min(foot3d(), height / 3);
  const across = tall * camera.aspect * spare(room, width), down = tall * spare(room + LABEL.size, height) * (1 - foot / height);
  const raise = result => {
    if (!foot) return result;
    const distance = Math.exp(result.far), lift = foot / height * tall * distance;  // half the room, in map units there
    at.set(result.x, result.y, result.z).addScaledVector(up, -lift);
    return {...result, x: at.x, y: at.y, z: at.z};
  };
  // the middle of what is shown, as seen from the camera's way
  let low = [Infinity, Infinity], high = [-Infinity, -Infinity];
  const middle = new THREE.Vector3();
  for (const ball of balls) middle.add(at.set(ball.x, ball.y, ball.z));
  middle.divideScalar(Math.max(1, balls.length));
  for (const ball of balls) {
    at.set(ball.x, ball.y, ball.z).sub(middle);
    const x = at.dot(right), y = at.dot(up);
    low = [Math.min(low[0], x - ball.r), Math.min(low[1], y - ball.r)];
    high = [Math.max(high[0], x + ball.r), Math.max(high[1], y + ball.r)];
  }
  if (mass && balls.length >= 6) {
    // The map's mass: across and up as the camera sees them, the spread between the `mass` quantile and its mirror on
    // each axis, so the few nodes far out on their own do not set the frame and may run off the edges.
    const xs = [], ys = [];
    for (const ball of balls) { at.set(ball.x, ball.y, ball.z).sub(middle); xs.push(at.dot(right)); ys.push(at.dot(up)); }
    const cut = (values, share) => { values.sort((a, b) => a - b); return values[Math.round(share * (values.length - 1))]; };
    low = [cut(xs, mass), cut(ys, mass)];
    high = [cut(xs, 1 - mass), cut(ys, 1 - mass)];
    middle.addScaledVector(right, (low[0] + high[0]) / 2).addScaledVector(up, (low[1] + high[1]) / 2);
    // Each node's own need, with its size and its depth as the camera sees it, and only the `mass` share of the
    // nodes that need the most left out, so a small map is framed whole, every node and its ball in view.
    const needs = balls.map(ball => {
      at.set(ball.x, ball.y, ball.z).sub(middle);
      const ahead = -at.dot(back);
      return Math.max((Math.abs(at.dot(right)) + ball.r) / across - ahead, (Math.abs(at.dot(up)) + ball.r) / down - ahead, ball.r * 2 - ahead);
    }).sort((a, b) => b - a);
    const far = needs[Math.min(needs.length - 1, Math.floor(mass * needs.length))];
    return raise({x: middle.x, y: middle.y, z: middle.z, turn: here.turn, tilt: here.tilt, far: Math.log(Math.max(far, 1))});
  }
  middle.addScaledVector(right, (low[0] + high[0]) / 2).addScaledVector(up, (low[1] + high[1]) / 2);
  if (on) middle.lerp(at.set(on.x, on.y, on.z), toward);
  let far = 0;
  for (const ball of balls) {
    at.set(ball.x, ball.y, ball.z).sub(middle);
    const ahead = -at.dot(back);  // how much farther from the camera than the point looked at
    far = Math.max(far, (Math.abs(at.dot(right)) + ball.r) / across - ahead, (Math.abs(at.dot(up)) + ball.r) / down - ahead,
      ball.r * 2 - ahead);
  }
  return raise({x: middle.x, y: middle.y, z: middle.z, turn: here.turn, tilt: here.tilt, far: Math.log(Math.max(far, 1))});
}
/* The room kept free at the foot of the 3D map's window, in screen pixels, as `foot2d` keeps it in 2D: the legend and
 * the count where they stand now, and the hover card at rest, so a card that grows while it shows never moves the
 * camera; and a small gap. */
function foot3d() {
  const view = $('#stage')?.closest('.view3d');
  if (!view) return 0;
  const bottom = view.getBoundingClientRect().bottom, shows = VIEW.hoverInfo || 'name+summary';
  let most = shows === 'name' || shows === 'off' ? 0 : FOOT2D.card || restingCard(view);
  for (const one of view.querySelectorAll(':scope > .legend, :scope > .count')) {
    const box = one.getBoundingClientRect();
    if (one.hidden || !box.height || getComputedStyle(one).display === 'none' || bottom - box.bottom > 60) continue;
    most = Math.max(most, bottom - box.top);
  }
  return most ? most + FOOT2D.gap : 0;
}
const ball = node => ({x: node.x, y: node.y, z: node.z, r: ballOf(node)});
const drawnBalls = data => data.nodes.filter(node => node.x !== undefined && shownNode(node)).map(ball);
/* What a fit of the whole map frames: its mass, every drawn node with the outer FIT share of their spread trimmed
 * from each side as the camera sees it, `framed`'s `mass`, so the map is seen close enough to read and the few nodes
 * far out on their own may run off the edges; a little more is trimmed in the small area, where room is short. */
const FIT = {large: 0.1, small: 0.12};
const fitTrim = () => $('.app').classList.contains('swapped') ? FIT.small : FIT.large;
const fitBalls = data => drawnBalls(data);
function fit3d(time = 700, room = 60) {
  if (!G) return;
  // In the small area the map is read by its selected node, met at its sign, VIEW-005: the whole map is too small to
  // read there, so with a selection there is one view, and the mouse looks around it.
  if (small3d() && S.selected && fly3d(S.selected)) return;
  const balls = fitBalls(G.graphData());
  Object.assign(V3, {auto: true, asked: true});
  if (!balls.length) return;
  // in Flat a fit faces the plane, so the fits that follow the nodes as they flatten finish the turn instead of ending it
  flyTo(framed(balls, {room, mass: fitTrim(), facing: flatNow() ? flatFacing() : null}),
    {length: time / 1000, done: () => { V3.whole = away3d(); V3.fits++; }});
}
/* A selected node is turned to face the eye: the camera swings round the map's middle to the side the node stands
 * out on, so the node is in front, its sign turned to the eye, VIEW-038, as if the whole map had turned to present it.
 * It stays right side up: the camera keeps the map's up as its own and is never more than TILT off level, so it never
 * looks straight down on the map. Only a selection turns it; a hand on the camera, or a drag, moves it as the hand
 * does. Swinging the camera round the middle shows what turning the whole map would, and keeps every node where the
 * layout put it. */
const TILT = 0.85;  // the most the camera rises above or falls below level, in radians, when it turns to a node
function facingOf(node, balls) {
  if (flatNow()) return flatFacing();  // the plane is faced square on, whichever node is chosen
  const middle = balls.reduce((sum, one) => ({x: sum.x + one.x / balls.length, y: sum.y + one.y / balls.length,
    z: sum.z + one.z / balls.length}), {x: 0, y: 0, z: 0});
  const dx = node.x - middle.x, dy = node.y - middle.y, dz = node.z - middle.z, away = Math.hypot(dx, dy, dz);
  if (away < 1e-3) return null;  // the node at the middle: seen from where the camera is
  return {turn: Math.atan2(dx, dz), tilt: Math.min(Math.PI / 2 + TILT, Math.max(Math.PI / 2 - TILT, Math.acos(dy / away)))};
}
/* A selection meets its name at a fixed share of the panel's width, VIEW-005. The large area's levels are a quarter,
 * a half and three quarters, opening at 2; the small area always uses four fifths. Unnamed nodes use their neighbors
 * for framing. Without `close` the camera keeps its distance. */
const NAME = {in: 0.8, level: 2, tall: 0.8, floor: 12};  // the small pane: the name block fills 80% of the width or of the height, whichever binds
const small3d = () => $('.app').classList.contains('swapped');
/* How far the camera stands, as a log, for the node's name, at its real size in the map, to span `share` of the
 * view's width; null while the name is not drawn yet. */
/* The selected name at `share` of the view's width, VIEW-005: in the small area four fifths, NAME.in, unless at that
 * size it would be taller than the pane, when it fits NAME.tall of the pane's height instead, every wrapped line in
 * view. The camera's distance does the framing; the name is drawn as it is. In the small
 * area, where even the floor would not fit its lines, the name is drawn on one line ending in an ellipsis,
 * `SMALL_NAME`. */
const SMALL_NAME = {id: null};
function nameFar(node, share) {
  const tag = tags.get(node.id), sign = tag?.sprite;
  if (!sign?.scale.x) return null;
  const camera = G.camera(), tall = 2 * Math.tan(camera.fov * Math.PI / 360), across = tall * camera.aspect;
  const out = Math.hypot(sign.position.x - node.x, sign.position.y - node.y, sign.position.z - node.z);
  const high = Math.max(1, $('#stage').clientHeight), size = LABEL.letters / LABEL.size;
  const reachFor = shape => {
    const width = shape.width * size, height = shape.height * size;
    // the small area fits the name's height too; the large area's levels are a share of its width alone
    const reach = Math.max(width / (share * across), small3d() ? height / (NAME.tall * tall) : 0);
    return reach;  // the camera moves to frame the name; the name itself is never capped
  };
  // the sign as drawn now, its letters raised where they would fall below reading, `layered`
  const shape = {width: sign.scale.x / size, height: sign.scale.y / size, lines: tag.shape?.lines || ['']};
  // In the small pane the whole name block fits, every line inside with a margin: 80% of the width unless its height
  // needs the camera farther, so the farther of the two fits wins and a name of two lines stays two lines; the camera
  // distance alone sizes it. Measured in a 150 px pane, 2026-10-12, where a name of two lines was clipped.
  const reach = reachFor(shape);
  SMALL_NAME.id = null;
  void high;
  return Math.log(reach + out);
}
function fly3d(id, close = true) {
  const data = G ? G.graphData() : null, node = data?.nodes.find(item => item.id === id);
  if (!node || node.x === undefined) return false;
  const near = new Set(node.id === S.selected ? S.neighbors : []);
  for (const link of data.links) {
    const one = endOf(link.source), two = endOf(link.target);
    if (one === id) near.add(two);
    if (two === id) near.add(one);
  }
  near.delete(id);
  const reach = item => Math.hypot(item.x - node.x, item.y - node.y, item.z - node.z);
  const around = data.nodes.filter(item => near.has(item.id) && item.x !== undefined && shownNode(item))
    .sort((one, two) => reach(one) - reach(two)).slice(0, 3);
  const facing = facingOf(node, fitBalls(data));
  const view = framed([ball(node), ...around.map(ball)], {room: 70, on: node, toward: 1, facing});
  const whole = framed(fitBalls(data), {facing, mass: fitTrim()}).far;
  // `close` 'whole': turned to the node at the whole map's distance, the map around it, `follow3d`
  if (close === 'whole') { view.far = whole; V3.auto = false; flyTo(view); V3.focus = null; return true; }
  view.far = close ? Math.min(Math.max(view.far, Math.log(ballOf(node) * 7)), whole + Math.log(0.4))
    : (FLIGHT.on ? FLIGHT.to.far : cameraNow().far);  // a selection keeps the zoom the person has
  // Measure the selected font and any newly selected join title before choosing the distance. Measuring the old
  // label lets it grow past the intended framing on the next frame.
  if (close) layered();
  const named = close ? nameFar(node, small3d() ? NAME.in : NAME.level / 4) : null;
  if (named !== null) view.far = named;
  V3.auto = false;
  const sign = close ? tags.get(id)?.sprite : null;
  if (sign?.scale.x && !MEM.key) {
    // The camera meets the node's sign: square on to it, along the way it faces, so its letters are level and whole,
    // at the distance the view above chose for the node; on arrival what stands between the eye and the sign is
    // cleared, `meetBegins`. A hand on the camera ends the meeting and the camera eases back to `view`.
    const face = new THREE.Vector3(sign.position.x - node.x, sign.position.y - node.y, sign.position.z - node.z);
    const out = face.length();
    if (out > 1e-6) {
      face.divideScalar(out);
      const reach = Math.max(Math.exp(view.far) - out, 1e-3);
      // How near the agents circling the node come to the eye: their orbit, its rise and fall, and a figure's size.
      const size = ROAM.drawn || sizeOf(data), ring = (ballOf(node) + size * ROAM.orbit) * 1.05 + size * 1.3;
      MEET.back = {id, far: view.far};
      // in Flat the sign stands above its node and faces the eye, so the camera meets it facing the plane
      const square = flatNow() ? flatFacing()
        : {turn: Math.atan2(face.x, face.z), tilt: Math.acos(Math.max(-1, Math.min(1, face.y)))};
      flyTo({x: sign.position.x, y: sign.position.y, z: sign.position.z, ...square, far: Math.log(reach)},
      {done: () => meetBegins(reach, reach + out - ring)});
      V3.focus = id;
      return true;
    }
  }
  flyTo(view);
  return true;
}
/* Meeting a sign, VIEW-005: the camera's near plane is moved out to just short of the sign, so the nodes, signs and
 * edges between the eye and it are not drawn and it is read whole; it eases there and back. The plane is the camera's
 * own, set back to its value when the meeting ends. */
const MEET = {on: false, back: null, own: null, from: 0, to: 0, start: 0};
function easeNear(to, length = 0.35) {
  const camera = G.camera();
  if (MEET.own === null) MEET.own = camera.near;
  Object.assign(MEET, {from: camera.near, to, start: performance.now()});
  const step = now => {
    const s = reduced() ? 1 : Math.min(1, (now - MEET.start) / (length * 1000)), e = s * s * (3 - 2 * s);
    camera.near = MEET.from + (MEET.to - MEET.from) * e;
    camera.updateProjectionMatrix();
    wake3d();
    if (s < 1 && MEET.to === to) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}
function meetBegins(reach, clear = reach) {
  MEET.on = true;
  // in the small area the map behind the met sign goes soft, as a lens focused on the sign sees it
  $('#big3d').classList.toggle('met', small3d());
  // The sign is square to the eye, so its whole face is at one depth: the plane stops a hair short of it, and
  // nothing in front of it, an edge crossing the last stretch included, is drawn. Where the node's agents circle
  // nearer the eye than the sign, the plane stops short of their orbit, so an agent passing in front is drawn whole;
  // it never comes nearer than the camera's own plane.
  const own = MEET.own ?? G.camera().near;
  easeNear(Math.max(own, Math.min(reach - Math.max(0.05, reach * 0.004), clear)));
}
function meetEnds() {
  if (MEET.own === null || (!MEET.on && G.camera().near === MEET.own && MEET.to === MEET.own)) return;
  MEET.on = false;
  if (MET.box) MET.box.hidden = true;
  $('#big3d').classList.remove('met');
  easeNear(MEET.own);
}
/* While a map opens and its layout first spreads out, the camera keeps it framed, easing after it four times a second,
 * so the map unfolds in view rather than off the edge of it or as a speck in the middle; the page's first fit then has
 * little left to do. It stops once a fit is asked for, at a hand on the camera, or when the layout rests. */
function frameWhileSpreading(now, data) {
  if (V3.asked || !V3.auto || !FRAMES.engine || MEM.key || reduced() || now - V3.followed < 250) return;
  V3.followed = now;
  const balls = fitBalls(data);
  if (balls.length > 1) flyTo(framed(balls, {mass: fitTrim()}), {length: 0.9});
}
/* Once the layout has settled, the map is fitted to the view, so the shape it settled into is seen whole, unless a
 * hand or a selection has moved the camera since the page last fitted it, or the layout is held, or the camera already
 * shows it so. */
function settled3d() {
  if (!G || !V3.auto || FLIGHT.on || MEM.key || $('#pauseBtn').dataset.paused === 'true') return;
  const balls = fitBalls(G.graphData());
  if (!balls.length) return;
  const view = framed(balls, {mass: fitTrim()}), here = cameraNow();
  const off = Math.hypot(view.x - here.x, view.y - here.y, view.z - here.z) / Math.exp(here.far);
  if (Math.abs(view.far - here.far) > 0.06 || off > 0.04) fit3d(1100);
}
/* The 3D map's modes in the large area, VIEW-005: Whole keeps the whole map framed through selections, layout changes
 * and new sizes; Zoom follows the selection close up, at the name level 4, 5 or 6 chose; Free moves the camera only by
 * hand. The mode chosen is the one checked, whatever the camera does meanwhile. A hand on the camera always takes
 * over: the mode moves it again at the next selection or change. Fit, beside them, fits the whole map once and leaves
 * the mode as it is. The small area is not configured: it has neither these nor Fit, takes no keys, and meets each
 * selection on its own, while the hand still moves it. */
const MODES3D = {box: null, buttons: new Map(), said: ''};
const MODES3D_LIST = [['whole', 'Whole', '1', 'The whole map in view, kept so through selections and layout changes (1, Home)'],
  ['zoom', 'Zoom', '4–6', 'Close on each node selected, turned to face you; 4, 5 and 6 stand far, medium and close'],
  ['free', 'Free', '0', 'The camera moves only by hand (0)']];
MODES3D.box = h('div', {class: 'segmented modes3d', role: 'radiogroup', 'aria-label': 'How the 3D map is framed'},
  MODES3D_LIST.map(([name, word, key, title]) => {
    const button = h('button', {type: 'button', role: 'radio', 'aria-checked': 'false', title,
      'aria-keyshortcuts': key === '4–6' ? '4 5 6' : key, onclick: event => { event.stopPropagation(); setMode3d(name); }},
    h('span', {class: 'long'}, word), h('kbd', {}, key));
    MODES3D.buttons.set(name, button);
    return button;
  }));
/* The page's easing tokens: one set for every motion, defined once here and as CSS custom properties in app.css's
 * :root (--ease-arrive, --ease-leave, --ease-move, --dur-1 to --dur-3), the same curves. What arrives settles with a
 * spring's ease-out and no overshoot; what leaves goes with a gentle ease-in; a move from one place to another eases
 * both ways; a larger move takes a little longer, `durFor`. CSS transitions carry an interrupted move on from where
 * it is. With reduced motion every state still changes, without moving. The maps' cameras ease as before, aim2d,
 * settle2D and the 3D flights, on curves of the same feel; the agents' figures take these. */
const EASE = {arrive: [0.16, 1, 0.3, 1], leave: [0.5, 0, 0.75, 0], move: [0.45, 0, 0.2, 1], short: 180, medium: 320, long: 520};
const durFor = pixels => Math.round(Math.min(EASE.long, EASE.short + Math.sqrt(Math.max(0, pixels)) * 9));
/* A token's curve as a function of the share of time gone, for motion drawn on a canvas or in the 3D scene. */
function easeCurve([x1, y1, x2, y2]) {
  const at = (t, one, two) => 3 * one * t * (1 - t) ** 2 + 3 * two * t * t * (1 - t) + t ** 3;
  return s => {
    if (s <= 0 || s >= 1) return Math.min(1, Math.max(0, s));
    let low = 0, high = 1, t = s;
    for (let step = 0; step < 24; step++) { t = (low + high) / 2; if (at(t, x1, x2) < s) low = t; else high = t; }
    return at(t, y1, y2);
  };
}
window.metaformEase = {...EASE, durFor, curve: name => easeCurve(EASE[name])};  // for the flow's figures, the same curves

/* The view settings of the web module that the page follows, read once a project is shown: the agents window,
 * web_agents_window; the 3D map's physics, web_physics; the 2D map's direction,
 * web_map_direction. Whether the page is drawn from its workspace is web_panes, which the workspace reads itself. A
 * change made here is saved to the setting, so every project and every reload opens the same way. */
const VIEW = {agents: 'auto', physics: 'organic', read: null, reading: null};
const INFOSET = {buttons: new Map()};  // the bar's Info choice, web_hover_info, `showInfo`, drawn as the view is read
// declared before the view settings are read, which shows them: the flow modes and the node zoom switch
const FLOWSET = {name: null, buttons: new Map()};
const NODEZOOM = {button: null};
const LENS = {name: 'natural', button: null, frame: 0};
const LENS_NEXT = {natural: 'wide', wide: 'fisheye', fisheye: 'natural'};
/* The signs, web_signs: outward, the map's names standing out from its middle as signs in the scene, or facing, each
 * turned to the eye. S switches them, as do the large map's bar and the View menu. */
const SIGNS = {button: null, words: {outward: 'Outward', facing: 'Facing'}};
const FOV3D = {least: 30, most: 55};  // the 3D map's field of view in degrees, top to bottom, `resize`
const LENSES = {natural: 55, wide: 80, fisheye: 120};  // web_lens: the widest the view opens
const LENS_WORDS = {natural: 'Natural', wide: 'Wide', fisheye: 'Fisheye'};
function readView() {
  const project = S.project;
  if (!project) return Promise.resolve();
  if (VIEW.read === project) return VIEW.reading;
  VIEW.read = project;
  VIEW.reading = (async () => {
    let rows = [];
    try { rows = (await read('settings')).settings || []; } catch { return; }
    if (S.project !== project) return;
    const value = (key, otherwise) => rows.find(row => row.key === key)?.value ?? otherwise;
    VIEW.agents = value('web_agents_window', 'auto');
    if (!MODE.chosen) {  // a key pressed before the settings were read is the person's later choice
      MODE.fit = String(value('web_map_fit', 'all'));
      MODE.zoom = String(value('web_map_zoom', 'neighbors'));
      MODE.distance = Number(value('web_map_distance', 0)) || 0;
      showModes();
      aim2d(center2d(S.selected));
    }
    PEEK.direction = value('web_map_direction', 'auto');
    VIEW.signs = String(value('web_signs', 'outward'));
    VIEW.embody = String(value('web_embody', 'offer'));
    VIEW.embodyTurns = Number(value('web_embody_turns', 8));
    VIEW.embodyMinutes = Number(value('web_embody_minutes', 20));
    showSigns();
    LENS.name = String(value('web_lens', 'natural'));
    lens3d(LENS.name);
    showLens();
    // the theme decides the look, and web_graphics records it, so the settings say what the map shows
    const look = document.documentElement.dataset.theme === 'space' ? 'ultra' : 'clean';
    ULTRA.setting(look);
    if (value('web_graphics', 'clean') !== look) saveView('web_graphics', look);
    const physics = value('web_physics', 'organic');
    if (physics !== PHYS.name) applyPhysics(physics);
    showFlow(String(value('web_flow_mode', flowNow())));
    VIEW.nodeZoom = value('web_node_zoom', true) !== false;
    showNodeZoom();
    VIEW.hoverInfo = String(value('web_hover_info', 'name+summary'));
    showInfo();
    agentsWindow();
    peekParts();
  })();
  return VIEW.reading;
}
async function saveView(key, value) {
  const done = await posted('/api/settings', {key, value});
  if (!done.ok) toast(done.body.error || 'That choice was not kept.');
  return done.ok;
}

/* Each map's own controls, in its bar row beside Swap and always in view, so nothing slides out over the map: the 2D
 * map's modes and direction, and the 3D map's framings, Fit and layout. Only the large map's show; the small area is
 * not configured. */
const PEEK = {two: null, three: null, physics: null, direction: null};
const FIT3D = $('#fit3dBtn');
PEEK.two = h('div', {class: 'peekpart two'});
PEEK.three = h('div', {class: 'peekpart three'}, MODES3D.box, FIT3D);
PEEK.physics = h('div', {class: 'peekpart physics'});
FIT3D.title = 'Fit the whole map in view once, leaving the mode as it is (F)';
FIT3D.setAttribute('aria-keyshortcuts', 'F');
PEEK.directions = new Map();
PEEK.two.append(h('div', {class: 'segmented directions', role: 'radiogroup', 'aria-label': "The 2D map's direction"},
  Object.entries(DIRECTION_KEYS).map(([key, direction]) => {
    const words = {auto: ['Auto', 'As suits the pane'], across: ['→', 'Left to right'], down: ['↓', 'Top to bottom']}[direction];
    const button = h('button', {type: 'button', role: 'radio', 'aria-checked': 'false', 'aria-label': words[1],
      'aria-keyshortcuts': key, title: `${words[1]} (${key})`, onclick: event => { event.stopPropagation(); chooseDirection(direction); }},
    h('span', {class: 'long'}, words[0]), h('kbd', {}, key));
    PEEK.directions.set(direction, button);
    return button;
  })));
$('#big3d .bar3d .mapbtns').prepend(PEEK.three);
$('.bar2d .mapbtns').prepend(PEEK.two);
PEEK.three.append(PEEK.physics);
function peekParts() {
  PEEK.two.hidden = !small3d();  // `small3d`: the 3D map in the small area, the 2D map in the large one
  PEEK.three.hidden = small3d();
  for (const [direction, button] of PEEK.directions) button.setAttribute('aria-checked', String(direction === PEEK.direction));
  for (const [name, button] of PHYS.buttons) button.setAttribute('aria-checked', String(name === PHYS.name));
  if (PHYS.shown) showPhysics();
  if (PEEK.ultra) showUltra();  // U pressed elsewhere: the bar names the look the map has now
}
/* A choice changed, by a key or a click: the bars name it at once. */
function peek() { peekParts(); }
$('#agentsat').onchange = event => chooseAgents(event.target.value);

/* The window of the agents at work, web_agents_window: auto slides it out as an agent starts work and keeps it while
 * any is at work, and slides it away completely a few seconds after the last one stops; open pins it out, saying when
 * none is at work, and hidden pins it away. A, and the View menu, change it. */
const AGENTS_WINDOW = {timer: 0, working: 0};
function agentsWindow(count = AGENTS_WINDOW.working) {
  AGENTS_WINDOW.working = count;
  const box = $('#agents');
  box.querySelector('.none')?.toggleAttribute('hidden', count > 0);
  const want = VIEW.agents === 'open' || (VIEW.agents === 'auto' && count > 0);
  clearTimeout(AGENTS_WINDOW.timer);
  if (want) slideIn(box);
  else if (VIEW.agents === 'auto' && !box.hidden) AGENTS_WINDOW.timer = setTimeout(() => slideOut(box), 4000);
  else slideOut(box);
  if ($('#agentsat')) $('#agentsat').value = VIEW.agents;
}
function slideIn(box) {
  if (!box.hidden && !box.classList.contains('away')) return;
  box.classList.add('away');
  box.hidden = false;
  void box.offsetWidth;  // from where it stands away, so it slides in
  box.classList.remove('away');
}
function slideOut(box) {
  if (box.hidden || box.classList.contains('away')) return;
  box.classList.add('away');
  setTimeout(() => { if (box.classList.contains('away')) box.hidden = true; }, reduced() ? 0 : EASE.medium + 60);
}
function chooseAgents(choice) {
  VIEW.agents = choice;
  agentsWindow();
  toast({auto: 'The agents window shows while agents are at work.', open: 'The agents window stays out.',
    hidden: 'The agents window stays away.'}[choice]);
  saveView('web_agents_window', choice);
}

/* Which joins the dots flow along, web_flow_mode, the flow's own setting: off, the selection's joins, all of them, or
 * live, only what agents really do. The flow draws it, `window.metaform.flowMode`; this is its choice in the map's bar,
 * the View menu and the key D, which steps through them, the new one shown as the bar peeks. */
const FLOW_MODES = [['off', 'Off', 'No dots flow'], ['selected', 'Selection', "Dots flow along the selection's joins"],
  ['all', 'All', 'Dots flow along every join'], ['live', 'Live', 'Dots show only what agents really do']];
function flowModes() {
  const offered = window.metaform?.flowModes;
  const names = Array.isArray(offered) ? offered.map(one => (typeof one === 'string' ? one : one?.name)) : null;
  return names?.length ? FLOW_MODES.filter(([name]) => names.includes(name)) : FLOW_MODES;
}
function flowNow() {
  const asked = typeof window.metaform?.flowMode === 'function' ? window.metaform.flowMode() : null;
  return (typeof asked === 'string' && asked) || FLOWSET.name || 'all';
}
function chooseFlow(name) {
  FLOWSET.name = name;
  if (typeof window.metaform?.flowMode === 'function') window.metaform.flowMode(name);
  for (const [one, button] of FLOWSET.buttons) button.setAttribute('aria-checked', String(one === name));
  if ($('#flowat')) $('#flowat').value = name;
  peek('key');
  saveView('web_flow_mode', name);
}
FLOWSET.box = h('div', {class: 'segmented flowset', role: 'radiogroup', 'aria-label': 'Which joins the dots flow along (D)'},
  FLOW_MODES.map(([name, word, why]) => {
    const button = h('button', {type: 'button', role: 'radio', 'aria-checked': 'false', 'aria-keyshortcuts': 'D',
      title: `${why} (D steps through them)`, onclick: event => { event.stopPropagation(); chooseFlow(name); }}, word);
    FLOWSET.buttons.set(name, button);
    return button;
  }));
PEEK.three.append(h('span', {class: 'peekpair'}, h('span', {class: 'peeklabel', 'aria-hidden': 'true'}, 'Flow'), FLOWSET.box));
/* What the maps say of what the pointer is on, web_hover_info: the name and the card, the name alone, the card alone,
 * or nothing; in the bar as Info, the View menu and the key I, which steps through them, applied at once. */
const HOVER_INFO = [['name+summary', 'Both', 'The name where it cannot be read on the map, and the card of its details'],
  ['name', 'Name', 'Only the name, where it cannot be read on the map'], ['summary', 'Card', 'Only the card of its details'],
  ['off', 'Off', 'Nothing said of what the pointer is on']];
function chooseInfo(name) {
  VIEW.hoverInfo = name;
  showInfo();
  readout('3d', null); readout('2d', null);
  peek('key');
  saveView('web_hover_info', name);
}
function showInfo() {
  const now = VIEW.hoverInfo || 'name+summary';
  INFOSET.pick?.show(now);
  if ($('#infoat')) $('#infoat').value = now;
}
/* A choice of the large map's bar made less often: one compact button naming the choice in force, "Lens Natural L ▾",
 * opening a small menu of every choice with what it does, as the physics opens; the frequent ones, Node zoom, the
 * modes, Fit and Flow, stay segmented controls, so the bar keeps one row. `list` is [name, word, why]; `choose` takes
 * a name; `show(name)` names it on the button and checks it in the menu. */
function barPick({id, label, key, title, list, choose}) {
  const items = new Map();
  const pick = {items, button: null, menu: null, show: null};
  pick.menu = h('div', {class: 'menu physicsmenu barmenu', id, role: 'menu', hidden: true, 'aria-label': title},
    list.map(([name, word, why]) => {
      const item = h('button', {type: 'button', role: 'menuitemradio', 'aria-checked': 'false', title: why,
        onclick: event => { event.stopPropagation(); pick.menu.hidden = true; choose(name); }},
      h('span', {class: 'wsitem'}, h('i', {class: 'i i-check wscheck', 'aria-hidden': 'true'}), word));
      items.set(name, item);
      return item;
    }));
  document.body.append(pick.menu);
  overlay(pick.menu, {kind: 'menu'});
  pick.button = h('button', {class: `btn sm quiet barpick ${id.replace(/menu$/, '')}btn`, type: 'button', 'aria-haspopup': 'menu',
    'aria-controls': id, 'aria-expanded': 'false', 'aria-keyshortcuts': key, title: `${title} (${key})`,
    onclick: event => {
      event.stopPropagation();
      if (!pick.menu.hidden) { pick.menu.hidden = true; return; }
      pick.menu.hidden = false;
      const at = pick.button.getBoundingClientRect(), size = pick.menu.getBoundingClientRect();
      Object.assign(pick.menu.style, {position: 'fixed', top: `${at.bottom + 4}px`,
        left: `${Math.max(8, Math.min(at.right - size.width, innerWidth - size.width - 8))}px`});
    }});
  pick.show = name => {
    const word = (list.find(([one]) => one === name) || list[0])[1];
    // drawn again only when the choice changed: the bar names its parts on every press in it, and a button whose
    // contents are made again between the press and the release takes no click
    if (pick.drawn === word) return;
    pick.drawn = word;
    // the key stays in the title and aria-keyshortcuts, and the reference ? lists it, so the button keeps its room
    fill(pick.button, h('span', {class: 'peeklabel'}, label), h('span', {class: 'value'}, word),
      h('i', {class: 'i i-chev', 'aria-hidden': 'true'}));
    pick.button.setAttribute('aria-label', `${label}: ${word}`);
    for (const [one, item] of items) item.setAttribute('aria-checked', String(one === name));
  };
  return pick;
}
INFOSET.pick = barPick({id: 'infomenu', label: 'Info', key: 'I', title: 'What is said of what the pointer is on',
  list: HOVER_INFO, choose: name => chooseInfo(name)});
INFOSET.buttons = INFOSET.pick.items;
INFOSET.pick.show(VIEW.hoverInfo || 'name+summary');
if ($('#infoat')) $('#infoat').onchange = event => chooseInfo(event.target.value);
function stepInfo() {
  const names = HOVER_INFO.map(([name]) => name), at = names.indexOf(VIEW.hoverInfo || 'name+summary');
  chooseInfo(names[(at + 1) % names.length]);
}
// Node zoom, in the bar beside the modes, as pressed while each selection is flown to (Z)
NODEZOOM.button = h('button', {class: 'btn sm quiet nodezoom', type: 'button', 'aria-pressed': 'true', 'aria-keyshortcuts': 'Z',
  'aria-label': 'Node zoom', title: 'Node zoom: fly to each node selected and frame it with its neighbours; off, a selection leaves the camera (Z)',
  onclick: event => { event.stopPropagation(); toggleNodeZoom(); }}, h('span', {class: 'state'}, 'On'), h('kbd', {}, 'Z'));
$('#nodezoomat').onchange = event => toggleNodeZoom(event.target.checked);
$('#flowat').onchange = event => chooseFlow(event.target.value);
function stepFlow() {
  const modes = flowModes().map(([name]) => name), now = modes.indexOf(flowNow());
  chooseFlow(modes[(now + 1) % modes.length]);
}
function showFlow(name = flowNow()) {
  FLOWSET.name = name;
  const offered = new Set(flowModes().map(([one]) => one));
  for (const [one, button] of FLOWSET.buttons) { button.hidden = !offered.has(one); button.setAttribute('aria-checked', String(one === name)); }
  if ($('#flowat')) $('#flowat').value = name;
}
/* The 3D map's layout, web_physics, VIEW-005: Organic or Flat, chosen in the bar's Layout menu, and L switches between
 * them. Each is a named way for the layout to move, with what it helps the reader see. The forces are d3-force-3d's,
 * which the graph runs: a change is only new forces and a warmed layout, so the nodes ease to their new places from
 * where they stand. */
const PHYSICS = [
  ['organic', 'Organic', 'The natural layout', {}],
  ['flat', 'Flat', 'Everything on one plane', {flat: true, facing: true}],
];
const PHYS = {name: 'organic', decay: 0.4, buttons: new Map()};
/* The views whose layout turns outward signs sideways to the eye face their signs forward instead, those views only. */
const signsFacing = () => VIEW.signs === 'facing' || Boolean(PHYSICS.find(([name]) => name === PHYS.name)?.[3].facing);
const baseCharge = node => node.t === 'el' ? -140 : node.t === 'item' ? -10 : -18;
const baseDistance = link => link.k === 'layer' ? 8 : link.k === 'item' ? 12 : link.k === 'tree' ? 60 : 34;
/* Each node's step along the chains of service: 0 for an element that serves no one, a join's purpose half a step on
 * from its receiver, and each part serving it a whole step. A node off every chain has none and is not pulled. */
function serviceSteps(data) {
  const next = new Map(), served = new Set(), steps = new Map();
  for (const link of data.links) {
    if (link.k !== 'purpose' && link.k !== 'encounter') continue;
    const from = endOf(link.source), to = endOf(link.target);
    (next.get(from) || next.set(from, []).get(from)).push(to);
    served.add(to);
  }
  const queue = data.nodes.filter(node => node.t === 'el' && !served.has(node.id)).map(node => node.id);
  for (const id of queue) steps.set(id, 0);
  while (queue.length) {
    const id = queue.shift();
    for (const to of next.get(id) || []) if (!steps.has(to)) { steps.set(to, steps.get(id) + 0.5); queue.push(to); }
  }
  return steps;
}
/* A weak gravity on each connected part of the map as a whole: each part's middle is drawn toward the map's middle,
 * every node of it by the same amount, so a part joined to nothing of the rest stays near it instead of drifting off,
 * and no part is squeezed. Its parts are read again whenever the graph's nodes change. */
function partsGravity(strength) {
  let parts = null;
  const force = alpha => {
    if (!parts) {
      const owner = new Map(), find = id => { while (owner.get(id) !== id) id = owner.set(id, owner.get(owner.get(id))).get(id); return id; };
      for (const node of force.nodes) owner.set(node.id, node.id);
      for (const link of G.graphData().links) {
        const one = endOf(link.source), two = endOf(link.target);
        if (owner.has(one) && owner.has(two)) owner.set(find(one), find(two));
      }
      const groups = new Map();
      for (const node of force.nodes) (groups.get(find(node.id)) || groups.set(find(node.id), []).get(find(node.id))).push(node);
      parts = [...groups.values()];
    }
    const pull = strength * alpha;
    for (const part of parts) {
      let x = 0, y = 0, z = 0;
      for (const node of part) { x += node.x || 0; y += node.y || 0; z += node.z || 0; }
      x /= part.length; y /= part.length; z /= part.length;
      for (const node of part) { node.vx -= x * pull; node.vy -= y * pull; if (node.vz !== undefined) node.vz -= z * pull; }
    }
  };
  force.initialize = nodes => { force.nodes = nodes; parts = null; };
  force.nodes = [];
  return force;
}
function applyPhysics(name, warm = true) {
  const preset = PHYSICS.find(([one]) => one === name) || PHYSICS[0], how = preset[3];
  PHYS.name = preset[0];
  peekParts();
  if (!G) return;
  const steps = how.axis || how.radial ? serviceSteps(G.graphData()) : null, gap = 52;
  const at = node => (steps?.get(node.id) ?? 0) * gap, pulled = node => steps?.has(node.id) ? 0.22 : 0;
  // Spread pushes within a part, not part from part: the push reaches no farther than PHYSICS_REACH
  G.d3Force('charge').strength(node => baseCharge(node) * (how.charge || 1)).distanceMax(how.reach || Infinity);
  G.d3Force('parts', partsGravity(how.gravity ?? 0.06));
  G.d3Force('link').distance(link => baseDistance(link) * (how.distance || 1));
  G.d3Force('serviceX', how.axis === 'x' ? forceX(node => at(node) * how.sign).strength(pulled) : null);
  G.d3Force('serviceY', how.axis === 'y' ? forceY(node => at(node) * how.sign).strength(pulled) : null);
  G.d3Force('serviceZ', how.axis === 'z' ? forceZ(node => at(node) * how.sign).strength(pulled)
    : how.flat ? forceZ(0).strength(0.35) : null);
  G.d3Force('serviceR', how.radial ? forceRadial(node => at(node) + gap * 0.25).strength(pulled) : null);
  PHYS.decay = how.decay || 0.4;
  G.d3VelocityDecay(PHYS.decay);
  if (warm) G.d3ReheatSimulation();
}
/* Flat lays the map on one plane, z = 0. Choosing it turns the camera to face that plane square on, from whichever
 * side it is nearer, so the map is seen flat at once; a drag turns it from there as ever. */
const flatNow = () => Boolean(PHYSICS.find(([name]) => name === PHYS.name)?.[3].flat);
const flatFacing = () => ({turn: Math.cos(cameraNow().turn) >= 0 ? 0 : Math.PI, tilt: Math.PI / 2});
function faceFlat() {
  if (!G) return;
  const balls = fitBalls(G.graphData()).map(one => ({...one, z: 0}));  // where Flat is taking them
  if (balls.length) flyTo(framed(balls, {mass: fitTrim(), facing: flatFacing()}));
}
function choosePhysics(name) {
  if (name === PHYS.name) return peek('key');
  applyPhysics(name);
  if (flatNow()) faceFlat();
  peek('key');
  saveView('web_physics', name);
}
/* The layout in the bar: one button naming the layout in force, opening the list of both, each by its name and what it
 * helps the reader see, so the bar stays one quiet row; L switches between them. */
PHYS.list = h('div', {class: 'menu physicsmenu', id: 'physicsmenu', role: 'menu', hidden: true, 'aria-label': "The 3D map's layout"},
  PHYSICS.map(([name, word, why]) => {
    const button = h('button', {type: 'button', role: 'menuitemradio', 'aria-checked': String(name === PHYS.name),
      'aria-keyshortcuts': 'L', title: `${why} (L)`,
      onclick: event => { event.stopPropagation(); PHYS.list.hidden = true; choosePhysics(name); }},
    h('span', {class: 'wsitem'}, h('i', {class: 'i i-check wscheck', 'aria-hidden': 'true'}), word));
    PHYS.buttons.set(name, button);
    return button;
  }));
document.body.append(PHYS.list);
overlay(PHYS.list, {kind: 'menu'});
PHYS.shown = h('button', {class: 'btn sm quiet physicsbtn', type: 'button', 'aria-haspopup': 'menu', 'aria-controls': 'physicsmenu',
  'aria-expanded': 'false', title: "How the 3D map is laid out, Organic or Flat; L switches between them",
  onclick: event => {
    event.stopPropagation();
    if (!PHYS.list.hidden) { PHYS.list.hidden = true; return; }
    PHYS.list.hidden = false;
    const at = PHYS.shown.getBoundingClientRect(), size = PHYS.list.getBoundingClientRect();
    Object.assign(PHYS.list.style, {position: 'fixed', top: `${at.bottom + 4}px`, left: `${Math.max(8, Math.min(at.right - size.width, innerWidth - size.width - 8))}px`});
  }});
PEEK.physics.append(PHYS.shown);
// the 3D map's lens, its names and its graphics, each a compact choice of the bar beside the modes, `barPick`; L, S
// and U still step through them
LENS.pick = barPick({id: 'lensmenu', label: 'Lens', key: 'L', title: "The 3D map's lens: how far its view opens as its pane grows tall",
  list: [['natural', 'Natural', 'The view opens no wider than the eye sees, 55°'], ['wide', 'Wide', 'The view opens to 80° as the pane grows tall'],
    ['fisheye', 'Fisheye', 'The view opens to 120°, the whole map close around you']], choose: name => chooseLens(name)});
LENS.button = LENS.pick.button;
$('#lensat').onchange = event => chooseLens(event.target.value);
showLens();
SIGNS.pick = barPick({id: 'signsmenu', label: 'Signs', key: 'S', title: "How the 3D map's names stand",
  list: [['outward', 'Outward', "Each name a sign standing out from the map's middle, turned round when seen from behind"],
    ['facing', 'Facing', 'Each name turned to face you']], choose: name => chooseSigns(name)});
SIGNS.button = SIGNS.pick.button;
$('#signsat').onchange = event => chooseSigns(event.target.value);
// Ultra graphics, U, page/ultra.js: the 3D map in outer space or clean; the button names the look the map has
PEEK.ultra = barPick({id: 'ultramenu', label: 'Ultra', key: 'U', title: "How the 3D map is drawn: clean, or in outer space",
  list: [['clean', 'Off', 'The map as it has always been drawn'], ['ultra', 'On', 'The map in outer space: a starfield, bodies and filaments of light']],
  choose: name => { setTheme(name === 'ultra' ? 'space' : PLAIN.last); showUltra(); peek('key'); }});
function showUltra() { PEEK.ultra.show(ULTRA.stats().mode === 'ultra' ? 'ultra' : 'clean'); }
showUltra();
function chooseSigns(name) {
  VIEW.signs = name === 'facing' ? 'facing' : 'outward';
  showSigns();
  wake3d();
  peek('key');
  saveView('web_signs', VIEW.signs);
}
function showSigns() {
  SIGNS.pick?.show(VIEW.signs === 'facing' ? 'facing' : 'outward');
  if ($('#signsat')) $('#signsat').value = VIEW.signs || 'outward';
}
showSigns();
function showPhysics() {
  const at = PHYSICS.findIndex(([one]) => one === PHYS.name), preset = PHYSICS[Math.max(0, at)];
  if (PHYS.drawn === preset[0]) return;  // as `barPick`: made again only on a change, so a press on it is never lost
  PHYS.drawn = preset[0];
  fill(PHYS.shown, h('span', {class: 'peeklabel'}, 'Layout'), h('span', {class: 'value'}, preset[1]),
    h('i', {class: 'i i-chev', 'aria-hidden': 'true'}));  // each preset's key is in its menu
  PHYS.shown.setAttribute('aria-label', `Physics: ${preset[1]}`);
}
showPhysics();
// No Alt shortcuts: Alt with a digit is taken by the system on some machines; L switches the layout.
function setMode3d(mode, level = null) {
  if (!G || small3d()) return;
  V3.mode = mode;
  if (level) NAME.level = level;
  showModes3d();
  if (mode === 'whole') fit3d();
  else if (mode === 'zoom' && S.selected) fly3d(S.selected, true);
  else if (mode === 'free') V3.auto = false;  // the layout no longer refits it either
}
/* What a selection does to the 3D camera: in the small area it is met; in the large one, as the mode says. */
/* Node zoom, web_node_zoom, on unless the person turns it off: every selection flies the camera to the node and frames
 * it with its neighbours, in either pane, whatever Whole, Zoom, Free or physics is in force; Whole and Free frame the
 * map while nothing is being flown to. Off, a selection never moves the camera. Found 2026-10-12: with Whole or Free
 * chosen, by 1, 0 or the bar, a selection in the large pane no longer flew to its node, which hid what the map is for. */
function follow3d(id) {
  if (VIEW.nodeZoom === false) return true;
  if (!small3d() && V3.mode === 'free') return true;  // Free leaves the camera to the hand
  // Whole turns the map round the node so it faces the eye near the middle, labelled, at the whole map's distance,
  // so the map shows around it; Zoom, and the small pane, fly close
  if (!small3d() && V3.mode === 'whole') return fly3d(id, 'whole');
  return fly3d(id);
}
function toggleNodeZoom(on = VIEW.nodeZoom === false) {
  VIEW.nodeZoom = on;
  showNodeZoom();
  if (on && S.selected && G) fly3d(S.selected);
  peek('key');
  toast(on ? 'Node zoom on: each node selected is flown to.' : 'Node zoom off: a selection leaves the camera where it is.');
  saveView('web_node_zoom', on);
}
function showNodeZoom() {
  NODEZOOM.button?.setAttribute('aria-pressed', String(VIEW.nodeZoom !== false));
  const state = NODEZOOM.button?.querySelector('.state');
  if (state) state.textContent = VIEW.nodeZoom !== false ? 'On' : 'Off';
  if ($('#nodezoomat')) $('#nodezoomat').checked = VIEW.nodeZoom !== false;
}
function showModes3d() {
  MODES3D.box.hidden = small3d();
  FIT3D.hidden = small3d();
  const said = small3d() ? '' : V3.mode;
  if (said === MODES3D.said) return;
  MODES3D.said = said;
  for (const [name, button] of MODES3D.buttons) button.setAttribute('aria-checked', String(name === said));
}
FIT3D.onclick = () => { if (G && !small3d()) fit3d(); };
// The 2D map opens in the large area, where its names are read, unless this browser has put the 3D map there: the
// chart is the map a person reads, and the 3D map keeps the whole in view beside it, VIEW-028.
{
  let kept = null;
  try { kept = localStorage.getItem('metaform.swapped'); } catch (error) { /* storage can be blocked: the default */ }
  if (kept === null || kept === '1') swap(true, false);
}
/* The lens chosen in the page, web_lens: L steps through natural, wide and fisheye, as do the large map's bar and the
 * View menu. The field of view eases to the new one on the arrival curve, `EASE`, rather than jumping; with reduced
 * motion it changes at once. */
function chooseLens(name, keep = true) {
  if (!(name in LENSES)) return;
  LENS.name = name;
  showLens();
  const camera = G?.camera(), from = camera?.fov;
  lens3d(name);
  if (camera && from !== undefined && camera.fov !== from && !reduced()) {
    const to = camera.fov, start = performance.now(), curve = easeCurve(EASE.arrive);
    cancelAnimationFrame(LENS.frame);
    camera.fov = from;
    const step = now => {
      const s = Math.min(1, (now - start) / EASE.medium);
      camera.fov = from + (to - from) * curve(s);
      camera.updateProjectionMatrix();
      wake3d();
      if (s < 1) LENS.frame = requestAnimationFrame(step);
    };
    LENS.frame = requestAnimationFrame(step);
  }
  if (keep) { peek('key'); saveView('web_lens', name); }
}
function showLens() {
  LENS.pick?.show(LENS.name in LENS_WORDS ? LENS.name : 'natural');
  if ($('#lensat')) $('#lensat').value = LENS.name;
}
function lens3d(name) {  // the lens chosen, its widest field of view, applied at once
  FOV3D.most = LENSES[name] ?? LENSES.natural;
  if (!G || V3.lensFirst === undefined) return;
  V3.lens = V3.lensFirst;  // from the lens it opened with, so a wider choice opens as far as it allows
  G.width(G.width() + 1);  // `resize` acts only on a change of size
  resize();
}
function resize() {
  if (!G) return;
  const box = $('#stage').getBoundingClientRect(), width = G.width(), height = G.height();
  if (!box.width || !box.height || (width === box.width && height === box.height)) return;
  const camera = G.camera();
  // Keep the lens's pixels per world unit independent of panel height. A shorter panel crops vertically without
  // changing a name's width or moving the camera. Width changes reframe the name at the selected share below.
  V3.lensFirst ??= Math.tan(camera.fov * Math.PI / 360) / box.height;  // the lens the 3D map opened with
  V3.lens ??= V3.lensFirst;
  G.width(box.width).height(box.height);
  // The library applies its size asynchronously; framing must use the new projection immediately.
  camera.aspect = box.width / box.height;
  // Within a natural lens only: a pane that grows a lot, such as the 3D map swapped from the small area into the large
  // one, would otherwise widen the view into a fisheye. Held at the edge, the lens starts again from there.
  const fov = Math.atan(V3.lens * box.height) * 360 / Math.PI, held = Math.min(FOV3D.most, Math.max(FOV3D.least, fov));
  if (held !== fov) V3.lens = Math.tan(held * Math.PI / 360) / box.height;
  camera.fov = held;
  camera.updateProjectionMatrix();
  if (S.selected && V3.focus === S.selected) {
    // a new width, a lens held at its edge, or in the small area any new size, where the name is framed both ways,
    // reframes the name
    if (width !== box.width || held !== fov || small3d()) fly3d(S.selected);
  } else if ((V3.auto || (V3.mode === 'whole' && !small3d())) && fitBalls(G.graphData()).length) fit3d();
  wake3d();
}
addEventListener('resize', resize);
new ResizeObserver(resize).observe($('#stage'));

function renderLegend() {
  const inView = new Set([...S.elements.values()].map(entry => entry.element.layer).concat(S.joins.map(join => join.layer)));
  const rows = [['--intake', 'purpose · receiver to join', ''],
    ['--tree', 'namespace', ''], ...[...inView].map(name => [colorVar(name), name, ''])];
  const legend = $('#legend');
  fill(legend, ...rows.map(([color, text, kind]) =>
    h('span', {style: {'--c': `var(${color})`}}, h('i', {class: kind}), text)));
  const open = new Set([...S.elements.values()].flatMap(entry => entry.element.open_work || [])
    .concat(S.joins.flatMap(join => join.open_work || [])));
  for (const condition of CONDITIONS) if (open.has(condition))
    legend.append(h('span', {style: {'--c': condition === 'missing' || condition === 'unbuilt' || condition === 'under-construction' ? 'var(--text)'
      : `var(--${condition === 'message' ? 'question' : condition})`}},
      h('i', {class: {missing: 'dot bloom', unbuilt: 'dot bloom', 'under-construction': 'dot bloom pulse', question: 'dot bloom pulse', message: 'dot bloom pulse'}[condition] || 'dot'}),
      condition === 'question' || condition === 'message' ? `waiting: ${condition}` : `part: ${condition.replace('-', ' ')}`));
  const shown = G ? G.graphData().nodes.length : 0;
  $('#count').textContent = noMetaform() ? 'no metaform yet'
    : `${S.elements.size} elements · ${S.joins.length} joins · ${shown} nodes shown` + (S.loading ? ' · loading' : '')
    + (following() ? ' · intake being recorded' : '');
}

/* ---------- 2D: the whole map, short names, no text on the edges; the camera moves node to node ---------- */
const M = {svg: null, nodes: new Map(), edges: [], cam: null, to: null, bounds: null, frame: 0, generation: 0};
const MAP2D = 5000;  // the most elements Mermaid lays out; above it the 2D map is not drawn, BUILD-QUESTIONS Q52
/* Mermaid lays the 2D map out with ELK, the Eclipse Layout Kernel bundled in its release and its default layout, P043.
 * Its nodes are placed by network simplex, which keeps the edges short and straight; its crossings are reduced by ELK's
 * own default, the layer sweep, which Mermaid leaves as it is. Mermaid refuses a diagram over 500 edges or 50,000
 * characters, so its limits are raised to the most the 2D map writes: MAP2D labels of at most 40 characters a line
 * and EDGES2D edges of at most 32. */
const EDGES2D = MAP2D * 10;
const ELK2D = {layout: 'elk', elk: {nodePlacementStrategy: 'NETWORK_SIMPLEX'}, maxEdges: EDGES2D,
  maxTextSize: MAP2D * 40 + EDGES2D * 32};
/* The 2D map fills its pane as well as ELK can draw it, P043. ELK lays the map out a few ways off screen: left to
 * right and top to bottom, and, for a map more than three layers deep, each of those folded, so a long run goes on in
 * rows or columns as text runs on in lines. A run is folded only where one edge alone joins its two halves, so a
 * branching part is never cut and a small tree is never folded on its own. The parts of the map not joined to each
 * other are laid out apart and packed together to a width to height ELK is given, `fitOptions2d`.
 *
 * ELK reaches the width to height it is given only roughly, so each way is first laid out for the pane's, and the way
 * that comes out best is laid out again for the width to height that corrects what it missed by, at most `refine`
 * times. The drawing kept is the one whose whole map can be drawn largest in the pane. A folded way is kept only when
 * it is `fold` times larger, as its runs turn back across the map, and the way drawn now is kept unless another is
 * `keep` times larger, so a pane near the point between two ways never turns the map back and forth. The setting
 * web_map_direction holds the map to one direction, across or down, unfolded, its parts still packed to the pane.
 *
 * The pane's shape is taken in steps, `fitStep2d`, each a quarter wider or narrower than the last, and a step is held
 * until the pane is well into the next, so a pane resized within one is not laid out again. The way chosen for each
 * step is kept with the map's layers when it was chosen, and the last `most` drawings with the map's text, so a pane
 * swapped back and forth gets its own picture again at once. A map whose layers change by a quarter is chosen for
 * again. Laying out stops after `budget` ms once one way is drawn, so a large map costs about that and no more. */
const FIT2D = {config: null, step: Math.log(1.25), stay: 0.75, keep: 1.12, fold: 1.15, refine: 2, budget: 2000, most: 16,
  chosen: new Map(), drawn: new Map()};
/* A name as a 2D label: the characters Mermaid would read as its own taken out, and a name longer than `most` cut at the
 * last break between words that keeps most of it, with an ellipsis, so a label never ends in half a word and always
 * says it goes on. The whole name is in the panel and in the 3D map's tooltip. */
function plain2d(text, most = 30) {
  const plain = String(text || '').replace(/["[\]{}()<>|#;`]/g, '').trim();
  if (plain.length <= most) return plain;
  const cut = plain.slice(0, most - 1), space = cut.lastIndexOf(' ');
  return (space >= most * 0.6 ? cut.slice(0, space) : cut).replace(/[\s,.;:–—-]+$/, '') + '…';
}
let mermaidReady = false;
/* The Mermaid shape of each artifact type, as the 3D map's: a process box for code, a document, a display for media,
 * a database cylinder for data, stacked boxes for a collection, input and output parallelograms for upstream and
 * downstream. */
const SHAPES2D = {code: 'rect', document: 'doc', media: 'curv-trap', data: 'cyl', collection: 'st-rect', upstream: 'lean-r',
  downstream: 'lean-l'};
async function build2D(keep = true) {
  const generation = ++M.generation;
  const host = $('#viewport');
  if (!window.mermaid) { fill(host, h('p', {class: 'empty', style: {padding: '16px'}}, 'The 2D map could not load.')); return; }
  if (!mermaidReady) {
    FIT2D.config = {startOnLoad: false, securityLevel: 'strict', theme: 'base', htmlLabels: false, ...ELK2D,
      flowchart: {htmlLabels: false, useMaxWidth: false, curve: 'basis', nodeSpacing: 28, rankSpacing: 45},
      themeVariables: {background: css('--ground'), primaryColor: css('--node'), primaryBorderColor: css('--node-line'),
        primaryTextColor: css('--text'), lineColor: css('--edge'), fontFamily: 'IBM Plex Sans, sans-serif', fontSize: '13px',
        tertiaryColor: css('--group')}};
    window.mermaid.initialize(FIT2D.config);
    FIT2D.drawn.clear();  // the drawings kept were drawn in the colors before
    mermaidReady = true;
  }
  const shown2d = [...S.elements].filter(([, {element}]) => !underHiddenRoot(element.address));
  const keys = new Map(shown2d.map(([id], index) => [id, `n${index}`]));
  // One edge between a join's receiver and each element it holds, drawn the way its information goes, as the Mermaid
  // export writes it: from the element served to the receiver when the receiver receives, `ends2d`.
  const drawn = S.joins.filter(join => keys.has(join.receiver))
    .flatMap(join => join.providers.filter(id => keys.has(id)).map(provider => ({join, provider})));
  const shape = shape2d(keys, drawn);
  const lines = [];  // the map without its direction, which the layout chosen for the pane gives it, `fitPick2d`
  for (const [id, {element}] of shown2d) {
    const shape = typeOf(element) && SHAPES2D[typeOf(element)];
    lines.push(shape ? `${keys.get(id)}@{ shape: ${shape}, label: "${plain2d(labelOf(element))}" }` : `${keys.get(id)}["${plain2d(labelOf(element))}"]`);
  }
  drawn.forEach(({join, provider}, index) => { const [from, to] = ends2d(join, provider);
    lines.push(`${keys.get(from)} e${index}@--> ${keys.get(to)}`); });
  if (!S.elements.size || S.elements.size > MAP2D) { IN.length = 0; M.base = null; renderCrumbs(); }
  if (!S.elements.size) { fill(host, h('p', {class: 'empty', style: {padding: '16px'}}, noMetaform() ? noneYet() : 'This metaform has no elements in these layers.')); return; }
  if (S.elements.size > MAP2D) {
    M.svg = null; M.nodes = new Map(); M.edges = []; showModes();
    fill(host, h('p', {class: 'empty', style: {padding: '16px'}}, `The 2D map lays out at most ${MAP2D} elements; these layers show ${S.elements.size}. The 3D view shows them all.`));
    return;
  }
  let picked = null, layout = 'elk';
  try { picked = await fitPick2d(lines.join('\n'), shape, generation); }
  catch (error) {
    // ELK failing never leaves the pane empty: the same map is drawn with Mermaid's other layout, dagre, P043
    layout = 'dagre';
    const pin = fitPin2d(), down = pin === 'down' || (pin !== 'across' && vertical2d(shape, M.way?.vertical ?? null));
    try { picked = {way: {vertical: down, wrap: false}, result: await window.mermaid.render(`map2d${generation}d`,
      `---\nconfig:\n  layout: dagre\n---\n${down ? 'flowchart TB' : 'flowchart LR'}\n${lines.join('\n')}`, $('#draw'))}; }
    catch (again) { fill(host, h('p', {class: 'empty', style: {padding: '16px'}}, 'The 2D map could not be drawn.')); return; }
  }
  if (generation !== M.generation || !picked) return;
  const {result, way} = picked, vertical = way.vertical;
  M.way = way;  // the way the whole map is drawn now, which a later choice keeps unless another is clearly better
  // The whole map drawn again keeps its camera and eases from there to its mode's framing, VIEW-041.
  const was = keep && M.base && M.svg === M.base.svg && M.cam ? {...M.cam} : null;
  const inside = IN.length > 0 || Boolean(MEM.key);
  const before = was && !inside ? drawnAt(M.base) : null;  // where each node is drawn now, to move it from there
  const svg = mountSvg(result, host, inside);
  // what laid it out, which way, and whether its layers run on in rows or columns
  Object.assign(svg.dataset, {layout, direction: vertical ? 'TB' : 'LR', wrapped: String(way.wrap)});
  const nodes = new Map();
  for (const [id, key] of keys) {
    const group = svg.querySelector(`[id*="-flowchart-${key}-"]`);
    const {element} = S.elements.get(id);
    if (group) placeIn(nodes, id, group, element.address, element.open_work,
      labelOf(element) === element.address ? element.address : `${labelOf(element)}\n${element.address}`);
  }
  const edges = drawn.map(({join, provider}, index) => ({join, provider, path: svg.querySelector(`[data-id="e${index}"]`)
    || svg.querySelectorAll('.edgePaths path')[index]}));
  for (const edge of edges) for (const condition of edge.join.open_work || []) edge.path?.classList.add(`work-${condition}`);
  for (const edge of edges) pointed(edge);
  hits2d(edges);
  // The base map is kept while a node is entered and shown again as it was, VIEW-016.
  M.base = {svg, nodes, edges, bounds: boundsOf(svg), vertical, cam: null};
  figures2d(S.tickets || []);
  if (MEM.key) { svg.remove(); svg.style.visibility = ''; await drawMemory2d(); return; }
  if (inside) { svg.remove(); svg.style.visibility = ''; await drawInside(); return; }
  showBase();
  paintInUse();
  if (was) setCam(was);
  if (before) settle2D(before, nodes, svg);
  if (S.selected) focus2D(S.selected); else aim2d();
}
/* The map's layers as ELK ranks them, near enough to choose its direction before it is drawn, P043: each element at
 * the longest path to it from an element nothing points to, with the edges that close a loop left out, as ELK breaks
 * loops. `layers` is how many there are and `widest` the most elements in one. */
function shape2d(keys, drawn) {
  const out = new Map([...keys.keys()].map(id => [id, []])), kept = new Map([...keys.keys()].map(id => [id, []]));
  const into = new Map([...keys.keys()].map(id => [id, 0])), seen = new Map();
  for (const {join, provider} of drawn) out.get(join.receiver).push(provider);
  for (const root of keys.keys()) {  // depth first, without recursion, so a long chain does not overflow the stack
    if (seen.has(root)) continue;
    const stack = [[root, 0]];
    seen.set(root, 'open');
    while (stack.length) {
      const top = stack.at(-1), next = out.get(top[0])[top[1]++];
      if (next === undefined) { seen.set(top[0], 'done'); stack.pop(); continue; }
      if (seen.get(next) === 'open') continue;  // it closes a loop
      kept.get(top[0]).push(next);
      into.set(next, into.get(next) + 1);
      if (!seen.has(next)) { seen.set(next, 'open'); stack.push([next, 0]); }
    }
  }
  const rank = new Map(), queue = [...keys.keys()].filter(id => !into.get(id));
  for (const id of queue) rank.set(id, 0);
  for (let at = 0; at < queue.length; at++) for (const next of kept.get(queue[at])) {
    rank.set(next, Math.max(rank.get(next) ?? 0, rank.get(queue[at]) + 1));
    into.set(next, into.get(next) - 1);
    if (!into.get(next)) queue.push(next);
  }
  const counts = new Map();
  for (const layer of rank.values()) counts.set(layer, (counts.get(layer) || 0) + 1);
  return {layers: Math.max(1, counts.size), widest: Math.max(1, ...counts.values())};
}
/* Which direction, top to bottom or left to right, is likelier to fit the pane, reckoned before anything is drawn: the
 * way ELK lays out first, `fitPick2d`, and the direction dagre draws if ELK fails. Each drawing's width to height is
 * reckoned from its layers, at the size Mermaid draws a 2D label and about the room ELK leaves between nodes and
 * between layers. Once drawn one way, the other must fit clearly better. */
const BOX2D = {w: 152, h: 45, across: 40, between: 50, clearly: 0.15};
function vertical2d(shape, was = null) {
  const area = area2d();
  if (!shape || !area.width || !area.height) return was ?? true;
  const {layers, widest} = shape, {w, h: tall, across, between, clearly} = BOX2D;
  const down = (widest * w + (widest - 1) * across) / (layers * tall + (layers - 1) * between);
  const side = (layers * w + (layers - 1) * between) / (widest * tall + (widest - 1) * across);
  const pane = area.width / area.height, miss = ratio => Math.abs(Math.log(ratio / pane));
  return miss(down) <= miss(side) + (was === null ? 0 : was ? clearly : -clearly);
}
/* The step of the pane's width to height, `FIT2D`: the drawn step `was` is held until the pane is `stay` steps from it. */
function fitStep2d(area, was = null) {
  if (!area.width || !area.height) return was ?? 0;
  const at = Math.log(area.width / area.height) / FIT2D.step;
  return was !== null && Math.abs(at - was) < FIT2D.stay ? was : Math.round(at);
}
/* ELK's options for one way, laid out for the width to height `aim`. The map has no subgraphs, so its root is laid out
 * on its own rather than with its children, which lets ELK lay out each part not joined to the rest apart, pack the
 * parts together to `aim` and close the gaps between them. A folded way also cuts each part's layers into rows or
 * columns for `aim`, ELK's single-edge wrapping: only where one edge alone crosses between two layers, so a long run
 * is folded and a branching part, or a part that fits as it is, is left whole. Mermaid passes on its own few ELK
 * options; these reach the layout as `elk.rootLayoutOptions` in its configuration, which the vendored mermaid.min.js
 * was changed to forward, vendor/README.md. */
function fitOptions2d({wrap, aim}) {
  return {'elk.hierarchyHandling': 'SEPARATE_CHILDREN', 'elk.aspectRatio': String(aim),
    'elk.separateConnectedComponents': 'true', 'elk.layered.compaction.connectedComponents': 'true',
    ...(wrap ? {'elk.layered.wrapping.strategy': 'SINGLE_EDGE'} : {})};
}
/* One drawing with ELK's options given, Mermaid's configuration put back as it was once it is drawn, so the graph
 * inside a node and the memory network are laid out as before. */
async function fitDraw2d(id, text, options) {
  window.mermaid.initialize({...FIT2D.config, elk: {...FIT2D.config.elk, rootLayoutOptions: options}});
  try { return await window.mermaid.render(id, text, $('#draw')); }
  finally { window.mermaid.initialize(FIT2D.config); }
}
/* How large the whole drawing is drawn in the pane, in screen pixels to a unit of it, with the margin a fit leaves,
 * `scaleFor`. */
function fitScale2d({w, h}, area) {
  const room = side => Math.min(MARGIN, side / 10);
  return Math.min((area.width - 2 * room(area.width)) / Math.max(1, w), (area.height - 2 * room(area.height)) / Math.max(1, h));
}
// a way apart from the width to height it was laid out for: its direction, and whether it is folded
const fitWay2d = ({vertical, wrap}) => `${vertical ? 'TB' : 'LR'}${wrap ? 'w' : ''}`;
/* web_map_direction as this page last read it, kept with the bar's direction buttons, `PEEK`: auto, across or down,
 * its directions also taken as Mermaid names them, LR and TB. */
const fitPin2d = () => ({LR: 'across', TB: 'down'})[PEEK.direction] || PEEK.direction || 'auto';
const fitNear2d = (a, b) => Boolean(a && b) && [a.layers / b.layers, a.widest / b.widest].every(part => part > 0.8 && part < 1.25);
function fitHash2d(text) {  // the map's text in a few characters, to know a drawing of it again
  let hash = 0x811c9dc5;
  for (let at = 0; at < text.length; at++) hash = Math.imul(hash ^ text.charCodeAt(at), 0x01000193);
  return `${text.length}.${(hash >>> 0).toString(36)}`;
}
/* The map's text laid out for the pane, `FIT2D`: the drawing and its way, or null once a later drawing has begun. The
 * project's settings are waited for while the page reads them, so a map held to one direction is drawn that way from
 * the first, and a direction changed while the map is laid out lays it out again. It fails only when ELK lays out
 * none of the ways. */
async function fitPick2d(body, shape, generation) {
  if (S.project && VIEW.read === S.project) await VIEW.reading;
  if (generation !== M.generation) return null;
  const area = area2d(), step = M.bucket = fitStep2d(area, M.bucket ?? null), pane = Math.exp(step * FIT2D.step);
  const pin = fitPin2d(), mark = `${pin} ${step}`, held = FIT2D.chosen.get(mark), reuse = fitNear2d(held?.shape, shape);
  const first = vertical2d(shape, M.way?.vertical ?? null), aim = Number(pane.toPrecision(3));
  const ways = reuse ? [held.way] : pin === 'across' || pin === 'down' ? [{vertical: pin === 'down', wrap: false, aim}]
    : [{vertical: first, wrap: false, aim},
      ...(shape.layers > 3 ? [{vertical: first, wrap: true, aim}, {vertical: !first, wrap: true, aim}] : []),
      {vertical: !first, wrap: false, aim}];
  const text = fitHash2d(body), start = performance.now(), tried = new Set();
  let best = null, again = reuse ? 0 : FIT2D.refine;
  for (let at = 0; at < ways.length; at++) {
    const way = ways[at], key = `${text} ${step} ${fitWay2d(way)} ${way.aim}`;
    if (best && performance.now() - start > FIT2D.budget) break;
    if (tried.has(key)) continue;
    tried.add(key);
    let drawing = FIT2D.drawn.get(key);
    FIT2D.drawn.delete(key);
    if (!drawing) {
      try {
        const {svg} = await fitDraw2d(`map2d${generation}n${at}`, `flowchart ${way.vertical ? 'TB' : 'LR'}\n${body}`,
          fitOptions2d(way));
        const box = (svg.match(/viewBox="([^"]+)"/)?.[1] || '').split(/[\s,]+/).map(Number);
        drawing = {result: {svg}, w: box[2] || 1, h: box[3] || 1};
      } catch (error) { if (generation !== M.generation) return null; continue; }  // the other ways may still be laid out
      if (generation !== M.generation) return null;
    }
    FIT2D.drawn.set(key, drawing);  // the latest last, and the oldest let go
    while (FIT2D.drawn.size > FIT2D.most) FIT2D.drawn.delete(FIT2D.drawn.keys().next().value);
    const score = fitScale2d(drawing, area) / (way.wrap ? FIT2D.fold : 1)
      * (M.way && fitWay2d(M.way) === fitWay2d(way) ? FIT2D.keep : 1);
    if (!best || score > best.score) best = {...drawing, way, score};
    // every way laid out, the best is laid out again for the width to height that makes up what it missed the pane by
    const miss = Math.log(pane / (best.w / best.h));
    if (at === ways.length - 1 && again > 0 && Math.abs(miss) > FIT2D.step / 2) {
      again--;
      ways.push({...best.way, aim: Number(Math.min(pane * 4, Math.max(pane / 4, best.way.aim * Math.exp(miss))).toPrecision(3))});
    }
  }
  if (!best) throw new Error('ELK laid out none of the ways.');
  if (!reuse) FIT2D.chosen.set(mark, {way: best.way, shape});
  if (fitPin2d() !== pin) return fitPick2d(body, shape, generation);  // its direction was changed meanwhile
  return {result: best.result, way: best.way};
}
/* A pane reshaped into another step of width to height, `fitStep2d`, lays the map out again, P043: 150 ms after it
 * stops changing, keeping the selection and the mode's framing, each node easing to its new place, `settle2D`. A
 * pane resized within its step keeps its layout; its mode refits it, `aim2d`. */
const RELAYOUT2D = {timer: 0};
new ResizeObserver(() => {
  clearTimeout(RELAYOUT2D.timer);
  RELAYOUT2D.timer = setTimeout(() => {
    if (M.base && !S.loading && fitStep2d(area2d(), M.bucket ?? null) !== M.bucket) build2D();
  }, 150);
}).observe($('#viewport'));
/* web_map_direction as the page reads it again, `fitPin2d`: a change draws the map in it and checks the bar's button.
 * It is read with the workspace, and again whenever the page is looked at, its window focused or its tab shown, since
 * a direction set with `metaform set` while the page is open is not announced to it; the page takes it up then. */
function fitDirection2d(direction) {
  if (!direction || direction === (PEEK.direction || 'auto')) return;
  PEEK.direction = direction;
  if (PEEK.two) peekParts();
  if (M.base) build2D();
}
async function fitRecheck2d() {
  if (!S.project || FRAMED || document.hidden) return;
  let found = null;
  try { found = await getJson(`/api/workspace?project=${encodeURIComponent(S.project)}`); } catch { return; }
  fitDirection2d(found?.view?.map_direction);
}
addEventListener('focus', fitRecheck2d);
document.addEventListener('visibilitychange', fitRecheck2d);
/* Where each node of a drawn map stands, by its element id, in the map's own units, counting any move it is still
 * making, so a map drawn again mid-move starts from where its nodes are and not where they were going. */
function drawnAt(base) {
  const held = new Map();
  for (const [id, node] of base.nodes) {
    const [dx = 0, dy = 0] = String(node.g.style.translate || '').split(' ').map(parseFloat)
      .filter(value => !isNaN(value));
    held.set(id, {x: node.x + dx, y: node.y + dy, g: node.g});
  }
  return held;
}
/* The map moves between layouts, VIEW-041: the camera starts where it was, each node starts where it was drawn and
 * eases to its new place, a new node grows from where its parent stood, a node gone fades out, and the edges fade in
 * as the nodes arrive. It runs on animation frames, as the camera does, so the two move as one. With reduced motion
 * the new drawing only fades in. */
const SETTLE = {frame: 0};
function settle2D(before, nodes, svg) {
  cancelAnimationFrame(SETTLE.frame);
  if (reduced()) { svg.animate([{opacity: 0}, {opacity: 1}], {duration: 160}); return; }
  const byAddress = new Map([...before.keys()].map(id => [S.elements.get(id)?.element.address, before.get(id)]));
  const moving = [];
  for (const [id, node] of nodes) {
    const old = before.get(id) || byAddress.get(S.elements.get(id)?.parent);
    moving.push({g: node.g, dx: old ? old.x - node.x : 0, dy: old ? old.y - node.y : 0, grow: !before.has(id)});
  }
  const layer = svg.querySelector('.nodes') || svg.querySelector('g');
  const ghosts = layer ? [...before].filter(([id]) => !nodes.has(id)).map(([, old]) => {
    const ghost = layer.appendChild(old.g.cloneNode(true));
    ghost.style.pointerEvents = 'none';
    return ghost;
  }) : [];
  const edges = [...svg.querySelectorAll('.edgePaths, .edgeLabels')];
  const ease = k => 1 - Math.pow(1 - k, 3);  // cubic ease-out
  const draw = (moved, faded, shown) => {
    for (const one of moving) {
      const left = 1 - ease(moved);
      one.g.style.translate = left ? `${one.dx * left}px ${one.dy * left}px` : '';
      if (one.grow) { one.g.style.scale = left ? String(0.4 + 0.6 * (1 - left)) : ''; one.g.style.opacity = left ? String(1 - left) : ''; }
    }
    for (const ghost of ghosts) ghost.style.opacity = String(1 - faded);
    for (const part of edges) part.style.opacity = shown < 1 ? String(Math.max(0, (shown - 0.55) / 0.45)) : '';
  };
  draw(0, 0, 0);  // the first frame shows the map as it stood
  let start = null;
  const step = now => {
    start ??= now;
    const gone = now - start, moved = Math.min(1, gone / 520), faded = Math.min(1, gone / 300), shown = Math.min(1, gone / 780);
    draw(moved, faded, shown);
    if (shown < 1) SETTLE.frame = requestAnimationFrame(step); else for (const ghost of ghosts) ghost.remove();
  };
  SETTLE.frame = requestAnimationFrame(step);
}
/* Mermaid's strict SVG, the only markup parsed; hidden when it is measured without being shown. */
function mountSvg(result, host, hidden) {
  const parsed = new DOMParser().parseFromString(result.svg, 'image/svg+xml');
  const svg = document.importNode(parsed.documentElement, true);
  svg.removeAttribute('height'); svg.removeAttribute('width'); svg.removeAttribute('style');
  svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  if (hidden) { svg.style.visibility = 'hidden'; host.append(svg); } else fill(host, svg);
  return svg;
}
/* `title` names the node in full, kept on it as `data-title`; `tip` is its hovertext, shown only while the map's text is
 * drawn smaller than Small, `hover2d`. */
function placeIn(nodes, id, group, title, work, tip = title) {
  const box = group.getBBox();
  const matrix = group.transform.baseVal.consolidate()?.matrix;
  const center = new DOMPoint(box.x + box.width / 2, box.y + box.height / 2).matrixTransform(matrix || new DOMMatrix());
  nodes.set(id, {g: group, x: center.x, y: center.y, w: box.width, h: box.height, tip});
  group.dataset.key = id;  // what the node stands for, kept from one drawing to the next as the mermaid id is not
  group.dataset.title = title;
  for (const condition of work || []) group.classList.add(`work-${condition}`);  // the node's condition, MAP-046
  const paced = S.progress?.get(id);
  if (paced) group.style.setProperty('--pace', `${paceOf({id})}s`);
  group.addEventListener('click', event => { event.stopPropagation(); clicked2d(id, event); });
  group.addEventListener('contextmenu', event => { event.preventDefault(); event.stopPropagation(); menu(id, event.clientX, event.clientY); });
}
/* The drawing's own bounds, the map's edge in its own units, VIEW-041. */
function boundsOf(svg) {
  const scene = svg.querySelector('g').getBBox();
  return {x: scene.x, y: scene.y, w: scene.width, h: scene.height};
}
const entryOf = () => [...S.elements.values()].find(item => item.element.role === 'DE')?.element.id || S.elements.keys().next().value;
function showBase(left = null) {
  const base = M.base;
  renderCrumbs();
  if (!base) return;
  stopCam();  // a camera still easing on the level left must not move this one
  Object.assign(M, {svg: base.svg, nodes: base.nodes, edges: base.edges, bounds: base.bounds, vertical: base.vertical, drawn: null});
  fill($('#viewport'), base.svg);
  const node = left ? base.nodes.get(left) : null;
  if (node && !reduced()) {  // back from inside the node: the map returns zoomed on it, fades in and eases out, VIEW-016
    setCam(frame(into(node)));
    arrive(base.svg);
    aim2d(node);  // to the mode's framing, the node left centered as far as the limits allow
    return;
  }
  base.svg.style.transition = ''; base.svg.style.opacity = '';  // a map faded on the way in shows whole again
  aim2d(node || (base.cam ? focus2d(base.cam) : center2d(S.selected) || base.nodes.get(entryOf())
    || base.nodes.values().next().value), true);
}

/* ---------- inside a node: the 2D map is replaced by the node's own graph, VIEW-016 ----------
 * Every node can be entered. Inside are the node, what it holds, one group for each layer turned on with what that
 * layer attaches to the node, and the nodes those items link to, which can be entered in turn. */
const IN = [];  // the levels entered from the base map: {key, label, more, things}
const GROUP = 20;
const PURPOSE2D = 64;  // a join's purpose in its box inside a node, VIEW-016: about three lines as Mermaid wraps it
let insideGen = 0;
const kindOf = key => key.startsWith('p:') ? 'join' : 'element';
const bareId = key => key.replace(/^p:/, '');
const keyOf = node => !node ? null : node.kind === 'join' ? 'p:' + node.id : node.kind === 'element' ? node.id : null;
const label2d = (text, most = 30) => plain2d(String(text ?? '').replace(/\s+/g, ' '), most) || '·';
const samePath = (a, b) => a.length === b.length && a.every((level, index) => level.key === b[index].key);
/* An element is labeled with its name, the project's name for it, or else its short namespace name, its address read
 * through name_length, MAP-012. A join has no name of its own, since a name belongs to the element it holds; its box
 * shows its purpose, the operative purpose it records, so a drill-in never draws a blank box. */
const labelOf = element => element.name || element.short_name || element.address;
const joinLabel = join => join?.purpose || '';
// A join's title, its receiver and the parts that serve it, as the 3D map shows it on a selected join, VIEW-038.
function joinTitle(node) {
  const join = S.joins.find(item => item.id === node.join);
  return join ? `${nameOf(join.receiver)} ${flowArrow(join)} ${join.providers.map(id => nameOf(id)).join(', ')}` : '';
}
function nameOf(key, fallback = key) {
  if (key.startsWith('p:')) { const found = joinOf(key); return found ? joinLabel(found) : fallback; }
  const found = S.elements.get(key)?.element;
  return found ? labelOf(found) : fallback;
}
async function drawInside(arriving = false) {
  const level = IN.at(-1);
  if (!level) return showBase();
  const generation = ++insideGen;
  const target = `${kindOf(level.key)}:${bareId(level.key)}`;
  let view = null, incoming = [];
  try {
    view = await read('node', {target, ...viewLayers()});
    incoming = (await read('links-to', {target, limit: 0, ...viewLayers()})).results || [];
  } catch (error) { if (error.status !== 404) toast(error.message); }
  if (generation !== insideGen) return;
  const vertical = M.base ? M.base.vertical : true;  // the whole map's orientation, so going inside never turns it
  const lines = [vertical ? 'flowchart TB' : 'flowchart LR'], edges = [], ids = new Map(), things = new Map(), groups = new Map();
  const add = (key, label, kind, thing = null) => {
    if (ids.has(key)) return ids.get(key);
    const id = `v${ids.size}`;
    ids.set(key, id);
    things.set(key, thing || {kind, key, label});
    lines.push(`${id}["${label2d(label, kind === 'purpose' ? PURPOSE2D : 30)}"]:::${kind}`);
    return id;
  };
  const key = level.key, center = add(key, level.label, 'center');
  if (key.startsWith('p:')) {
    const join = joinOf(key);
    if (join) {
      edges.push(`${add(join.receiver, nameOf(join.receiver), 'stub')} --> ${center}`);
      for (const provider of join.providers) edges.push(`${center} --> ${add(provider, nameOf(provider), 'stub')}`);
    }
  } else {
    // each join the node receives, as its purpose, with the elements that serve it drawn under it
    for (const join of S.joins.filter(item => item.receiver === key)) {
      const purpose = add('p:' + join.id, joinLabel(join), 'purpose');
      edges.push(`${center} --> ${purpose}`);
      for (const provider of join.providers) edges.push(`${purpose} --> ${add(provider, nameOf(provider), 'stub')}`);
    }
  }
  const linked = [];
  for (const found of view?.layers || []) {
    const all = [...(found.items || []).map(item => ({kind: 'item', key: 'i:' + item.id, item})),
      ...(found.properties || []).map(item => ({kind: 'property', key: 'r:' + item.id, item}))]
      .map(thing => ({...thing, value: thing.item.value, layer: found.layer, layerKind: found.kind}));
    if (!all.length) continue;
    const shown = level.more[found.layer] || GROUP, gid = `g${groups.size}`;
    groups.set(gid, found.layer);
    lines.push(`subgraph ${gid} ["${label2d(found.kind === 'memory' ? 'memory' : found.layer)}"]`, 'direction TB');
    for (const thing of all.slice(0, shown)) {
      add(thing.key, itemText(thing.value) + (thing.item.state ? ` · ${thing.item.state}` : ''), 'item', thing);
      if (thing.item.link) linked.push(thing);
    }
    if (all.length > shown) add(`m:${found.layer}`, `${all.length - shown} more`, 'more');
    lines.push('end');
    edges.push(`${center} --- ${gid}`);
  }
  for (const thing of linked) {
    const to = keyOf(thing.item.link);
    if (to) edges.push(`${ids.get(thing.key)} --> ${add(to, nameOf(to, thing.item.link.id), 'stub')}`);
  }
  // The memories kept at the node, in memory's group; each relation of theirs runs to the memory it names, and a memory
  // kept elsewhere leads on to the nodes it is kept at, LAYER-013.
  const kept = [...new Set(memoriesAt(key))];
  if (kept.length) {
    const gid = `g${groups.size}`;
    groups.set(gid, memoryLayer());
    lines.push(`subgraph ${gid} ["memory"]`, 'direction TB');
    for (const name of kept) add(memoryKey(name), name, 'item', memoryThing(memoryKey(name)));
    lines.push('end');
    edges.push(`${center} --- ${gid}`);
    const there = name => [...S.memory.at].filter(([, names]) => names.includes(name)).map(([at]) => at);
    for (const relation of S.memory.relations) {
      if (!kept.includes(relation.from) && !kept.includes(relation.to)) continue;
      for (const name of [relation.from, relation.to]) if (!ids.has(memoryKey(name))) {
        add(memoryKey(name), name, 'item', memoryThing(memoryKey(name)));
        for (const at of there(name)) if (at !== key) edges.push(`${ids.get(memoryKey(name))} --> ${add(at, nameOf(at), 'stub')}`);
      }
      edges.push(`${ids.get(memoryKey(relation.from))} -->|"${label2d(relation.relationType)}"| ${ids.get(memoryKey(relation.to))}`);
    }
  }
  const coming = incoming.filter(item => !ids.has('i:' + item.id));
  if (coming.length) {
    const gid = `g${groups.size}`;
    groups.set(gid, null);
    lines.push(`subgraph ${gid} ["linked here"]`, 'direction TB');
    for (const item of coming) add('i:' + item.id, itemText(item.value), 'item', {kind: 'item', key: 'i:' + item.id,
      item, value: item.value, layer: item.layer, layerKind: S.layers.find(layer => layer.name === item.layer)?.kind});
    lines.push('end');
    for (const item of coming) {
      const from = keyOf(item.target);
      if (from) edges.push(`${add(from, nameOf(from, item.target.id), 'stub')} --> ${ids.get('i:' + item.id)}`);
    }
    edges.push(`${gid} --> ${center}`);
  }
  lines.push(...edges, ...['center', 'item', 'stub', 'more', 'purpose'].map(kind => `classDef ${kind} font-size:11px`));
  let result;
  try { result = await window.mermaid.render(`inside${generation}`, lines.join('\n'), $('#draw')); }
  catch (error) { fill($('#viewport'), h('p', {class: 'empty', style: {padding: '16px'}}, 'This node could not be drawn.')); return; }
  if (generation !== insideGen || IN.at(-1) !== level) return;
  const svg = mountSvg(result, $('#viewport'), false);
  if (arriving) arrive(svg);  // the node's own graph fades in, VIEW-016
  const nodes = new Map();
  for (const [thingKey, id] of ids) {
    const group = svg.querySelector(`[id*="-flowchart-${id}-"]`), thing = things.get(thingKey);
    if (!group) continue;
    const title = thing.value !== undefined ? itemText(thing.value) : thing.label;
    placeIn(nodes, thingKey, group, title, null, nameOf(thingKey, title));  // its hovertext its name in full
    group.classList.add(`in-${thing.kind}`);
  }
  for (const [gid, layer] of groups) {
    const cluster = svg.querySelector(`g.cluster[id="${gid}"], g.cluster[id$="-${gid}"]`);
    if (!cluster) continue;
    cluster.classList.add('layergroup');
    if (layer) cluster.style.setProperty('--c', `var(${colorVar(layer)})`);
  }
  level.things = things;
  stopCam();  // a camera still easing on the level left must not move this one
  Object.assign(M, {svg, nodes, edges: [], bounds: boundsOf(svg), vertical, drawn: level});
  aim2d(nodes.get(level.key), true);  // the node's own graph fades in framed by the mode, on the node, VIEW-016
  renderCrumbs();
  if (S.selected && nodes.has(S.selected)) focus2D(S.selected);
}
function renderCrumbs() {
  const bar = $('#crumbs');
  bar.hidden = !IN.length && !MEM.key;
  if (MEM.key) {  // a memory network, VIEW-031: each part goes back to the map, at that level of it
    const back = (depth, text) => h('a', {href: '#', onclick: event => { event.preventDefault(); leaveMemories(depth); }}, text);
    return fill(bar, back(0, 'map'), MEM.levels.map((level, index) => [h('span', {class: 'sep'}, ' › '), back(index + 1, level.label)]),
      h('span', {class: 'sep'}, ' › '), h('b', {}, `memories of ${nameOf(MEM.key)}`));
  }
  const to = (depth, text) => h('a', {href: '#', onclick: event => { event.preventDefault(); goTo(depth); }}, text);
  fill(bar, ...(IN.length ? [to(0, 'map'), ...IN.flatMap((level, index) => [h('span', {class: 'sep'}, ' › '),
    index === IN.length - 1 ? h('b', {}, level.label) : to(index + 1, level.label)])] : []));
}
/* Enter a node, or the node an item links to; a group's "more" node shows the next ones. */
async function enter(key) {
  const level = IN.at(-1), thing = level?.things?.get(key);
  if (key.startsWith('m:')) { level.more[key.slice(2)] = (level.more[key.slice(2)] || GROUP) + GROUP; return drawInside(); }
  if (key.startsWith('e:')) {  // a memory has no inside; Enter goes to the node it is kept at, as an item's link does
    const at = [...S.memory.at].find(([, names]) => names.includes(memoryName(key)))?.[0];
    return at && at !== level?.key ? enter(at) : undefined;
  }
  if (thing && (thing.kind === 'item' || thing.kind === 'property')) {
    const to = keyOf(thing.item.link);
    if (!to) return;
    return enter(to);
  }
  if (level?.key === key) return;
  if (!IN.length && M.base) M.base.cam = {...M.cam};
  const node = M.nodes.get(key);
  if (M.svg && node && !reduced()) {  // the camera dives into the node as the view it is on fades, VIEW-016
    moveCam(into(node), {length: 0.48, dive: true});
    await fade(M.svg, 0);
  }
  IN.push({key, label: nameOf(key, thing?.label || key), more: {}, things: new Map()});
  await drawInside(true);
  select(key, false, true);
}
/* Up to a level: 0 is the base map. The node left is selected where it shows. */
async function goTo(depth) {
  if (depth >= IN.length) return;
  const left = IN[depth].key, here = M.drawn === IN.at(-1) ? M.nodes.get(IN.at(-1).key) : null;
  if (M.svg && !reduced()) {  // the node's graph gathers onto the node and fades as it is left, VIEW-016
    if (here) moveCam(into(here), {length: 0.48});
    await fade(M.svg, 0);
  }
  IN.length = depth;
  if (depth) await drawInside(true); else showBase(left);
  select(left, true, true);
}
function renderThing(thing) {
  const pane = $('#p-object');
  if (thing.kind === 'memory') return renderEntity(thing.name);
  if (thing.kind === 'item' || thing.kind === 'property') {
    const link = keyOf(thing.item.link);
    fill(pane,
      h('div', {class: 'eyebrow'}, thing.layerKind === 'memory' ? 'Memory' : thing.kind === 'property' ? 'Property' : 'Item'),
      h('div', {class: 'pills'}, thing.layer ? layerPill(thing.layer) : null, thing.item.state ? h('span', {class: 'pill'}, thing.item.state) : null),
      h('div', {class: 'itemtext'}, itemView(thing.value)),
      link ? h('p', {class: 'meta'}, 'Links to ', h('a', {class: 'link', href: '#', onclick: event => { event.preventDefault(); enter(link); }},
        nameOf(link, thing.item.link.id)), '; Enter goes there.') : null,
      refsOf(thing.item.refs));
    return;
  }
  fill(pane, h('div', {class: 'eyebrow'}, thing.kind === 'more' ? 'More' : 'Node'), h('h2', {}, thing.label),
    h('p', {class: 'meta'}, thing.kind === 'more' ? 'Enter shows the next ones.' : 'Enter goes inside it.'));
}

/* ---------- the memory graph, LAYER-013: a graph of its own, tied to the map's nodes by joins of type memory ----------
 * Read whole from the memory module's `graph`, each join saying whether its memory shows at its node in the layers in
 * view, VIEW-031. A memory is drawn as `e:<name>`, at each node it shows
 * at; a join the map no longer holds is orphaned and listed in the orphaned menu. */
const emptyMemory = () => ({entities: new Map(), relations: [], joins: [], at: new Map(), orphaned: 0});
const memoryLayer = () => S.layers.find(layer => layer.kind === 'memory')?.name || 'memory';
const memoryKey = name => 'e:' + name;
const memoryName = key => key.slice(2);
/* The node of the map a memory join names: an element by its address, and a map join by its receiver's address and the
 * address of an element it holds, STORE-020. */
function nodeAt(join) {
  const addressOf = id => S.elements.get(id)?.element.address;
  if (join.address !== undefined) {
    const found = [...S.elements.values()].find(entry => entry.element.address === join.address);
    return found ? found.element.id : null;
  }
  const parent = S.joins.find(one => addressOf(one.receiver) === join.receiver
    && (one.elements || []).some(each => each.address === join.provider));
  return parent ? 'p:' + parent.id : null;
}
async function memoryOf() {
  let whole;
  try { whole = await read('memory-graph', viewLayers()); } catch (error) { return emptyMemory(); }
  const at = new Map(), joins = whole.joins.map(join => ({...join, key: join.orphaned ? null : nodeAt(join)}));
  for (const join of joins) {
    if (!join.shows || !join.key) continue;
    if (!at.has(join.key)) at.set(join.key, []);
    if (!at.get(join.key).includes(join.entity)) at.get(join.key).push(join.entity);
  }
  return {entities: new Map(whole.entities.map(entity => [entity.name, entity])), relations: whole.relations, joins, at,
    orphaned: joins.filter(join => join.orphaned).length};
}
/* The memories shown at a node, and a memory as the panel and the inside of a node take it. */
const memoriesAt = key => S.memory.at.get(key) || [];
function memoryThing(key) {
  if (!key?.startsWith('e:') || !S.memory.entities.has(memoryName(key))) return null;
  return {kind: 'memory', key, name: memoryName(key), value: memoryName(key), layer: memoryLayer(), layerKind: 'memory'};
}
/* The memory network of a node, VIEW-031: the memories kept at it, the memories their relations name, and every
 * relation between those; a relation one of them holds to a memory outside them is not drawn. */
function networkOf(key) {
  const own = memoriesAt(key), names = new Set(own);
  for (const relation of S.memory.relations) if (own.includes(relation.from) || own.includes(relation.to)) {
    names.add(relation.from); names.add(relation.to);
  }
  const relations = S.memory.relations.filter(relation => names.has(relation.from) && names.has(relation.to))
    .map(relation => ({from: memoryKey(relation.from), to: memoryKey(relation.to), type: relation.relationType}));
  return {key, own, entities: [key, ...[...names].map(memoryKey)], relations};
}
/* The node is drawn as the map draws it: an element as its glass and a join as its purpose; each memory as a memory is
 * drawn in the map. */
function entityNode(key) {
  if (key.startsWith('e:')) return {id: key, t: 'item', layer: memoryLayer(), text: memoryName(key), work: []};
  const element = S.elements.get(key)?.element;
  if (element) return {id: key, t: 'el', name: labelOf(element), address: element.address,
    role: element.role, work: element.open_work || [], layer: element.layer};
  const join = joinOf(key);
  if (join) return {id: key, t: 'purpose', join: join.id, layer: join.layer, work: join.open_work || []};
  return {id: key, t: 'el', name: key, address: key, work: []};  // a node the layers in view do not draw
}
function memoryData() {
  const network = MEM.network = networkOf(MEM.key), layer = memoryLayer();
  return {nodes: network.entities.map(entityNode), links: [
    ...network.own.map(name => ({source: network.key, target: memoryKey(name), k: 'item', layer, relation: null})),
    ...network.relations.map(relation => ({source: relation.from, target: relation.to, k: 'relation', layer,
      relation: relation.type}))]};
}
/* The view zooms into the node as the map gives way to it: each camera goes up to the node while its view fades
 * toward the background. With reduced motion the views change at once. */
function into3d(key) {
  if (!G || reduced()) return Promise.resolve();
  const node = G.graphData().nodes.find(item => item.id === key);
  if (node && node.x !== undefined) {
    const eye = G.camera().position, away = Math.hypot(eye.x - node.x, eye.y - node.y, eye.z - node.z) || 1;
    const share = Math.min(1, Math.cbrt(nodeSize(node)) * 3 * 2.5 / away);  // near enough that the node fills the view
    G.cameraPosition({x: node.x + (eye.x - node.x) * share, y: node.y + (eye.y - node.y) * share,
      z: node.z + (eye.z - node.z) * share}, {x: node.x, y: node.y, z: node.z}, 480);
  }
  return shown3d(0);
}
function into2d(key) {
  if (!M.svg || reduced()) return Promise.resolve();
  const node = M.nodes.get(key);
  if (node) moveCam(into(node));
  return fade(M.svg, 0);
}
const shown3d = to => fade($('#stage'), to);  // the labels are drawn in the 3D view, VIEW-038
/* The whole memory network in the 3D view, once the graph has taken its nodes. */
async function whole3d() {
  if (!G) return;
  for (let frames = 0; frames < 2; frames++) await new Promise(resolve => requestAnimationFrame(resolve));
  G.zoomToFit(0, 60);
  V3.whole = away3d();
}
/* Open the memory network of a node in both views. From the map, what the map was is kept to go back to: the levels
 * entered in 2D and where each node of the 3D map stood. From a memory network, the network of another of its nodes
 * takes its place. */
async function memories(key) {
  if (!key) return;
  const generation = ++MEM.generation;
  if (!MEM.key) {
    if (!IN.length && M.base) M.base.cam = {...M.cam};
    MEM.levels = IN.splice(0);
    MEM.positions = G ? new Map(G.graphData().nodes.map(node => [node.id, node])) : null;
  }
  await Promise.all([into2d(key), into3d(key)]);
  if (generation !== MEM.generation) return;
  Object.assign(MEM, {key, drawn: false, network: networkOf(key)});
  draw3D();
  renderLegend();
  await drawMemory2d(true);
  if (generation !== MEM.generation) return;
  MEM.drawn = true;
  select(key, false, true);
  if (M.bounds && M.drawn === MEM) { stopCam(); aim2d(M.nodes.get(key), true); }  // it opens framed by the mode, VIEW-041
  await whole3d();
  if (generation !== MEM.generation) return;
  renderCrumbs();
  if (!reduced()) { if (M.drawn === MEM) fade(M.svg, 1); shown3d(1); }
}
/* Going back returns to the map: to the level of the 2D map the network was opened from, or to `depth` of it, with
 * each node of the 3D map where it stood, and the node the network belongs to selected. */
async function leaveMemories(depth = null) {
  if (!MEM.key) return;
  const key = MEM.key, generation = ++MEM.generation;
  const levels = MEM.levels.slice(0, depth ?? MEM.levels.length);
  if (!reduced()) await Promise.all([M.svg ? fade(M.svg, 0) : null, shown3d(0)]);
  if (generation !== MEM.generation) return;
  const positions = MEM.positions;
  Object.assign(MEM, {key: null, network: null, drawn: false, levels: [], positions: null});
  draw3D(positions);
  renderLegend();
  IN.push(...levels);
  if (IN.length) await drawInside(true); else showBase(key);
  select(key, true, true);
  if (!reduced()) shown3d(1);
}
/* Another metaform or project is shown: its map, at once. */
function dropMemories() {
  MEM.generation++;
  Object.assign(MEM, {key: null, network: null, drawn: false, levels: [], positions: null});
  Object.assign($('#stage').style, {transition: '', opacity: ''});
}
/* The memory network in 2D: the node, each memory by its name, a dotted line from the node to each memory kept at it,
 * and each relation a line in memory's color from the memory that holds it to the memory it names, with its relation
 * type on it. `hidden` puts it in place unseen, to fade in with the 3D view. */
async function drawMemory2d(hidden = false) {
  const network = MEM.network = networkOf(MEM.key);
  const generation = ++insideGen;  // a render still running for a level left is dropped
  const vertical = M.base ? M.base.vertical : true;
  const ids = new Map(network.entities.map((key, index) => [key, `v${index}`]));
  const label = key => key.startsWith('e:') ? memoryName(key) : nameOf(key);
  const lines = [vertical ? 'flowchart TB' : 'flowchart LR',
    ...network.entities.map(key => `${ids.get(key)}["${label2d(label(key))}"]:::${key === network.key ? 'center' : 'entity'}`),
    ...network.own.map(name => `${ids.get(network.key)} -.- ${ids.get(memoryKey(name))}`),
    ...network.relations.map((relation, index) =>
      `${ids.get(relation.from)} e${index}@-->|"${label2d(relation.type)}"| ${ids.get(relation.to)}`),
    ...['center', 'entity'].map(kind => `classDef ${kind} font-size:11px`)];
  let result;
  try { result = await window.mermaid.render(`memory${generation}`, lines.join('\n'), $('#draw')); }
  catch (error) { fill($('#viewport'), h('p', {class: 'empty', style: {padding: '16px'}}, 'These memories could not be drawn.')); return; }
  if (generation !== insideGen || !MEM.key) return;
  const svg = mountSvg(result, $('#viewport'), false);
  if (hidden && !reduced()) Object.assign(svg.style, {transition: '', opacity: '0'});
  const nodes = new Map();
  for (const [key, id] of ids) {
    const group = svg.querySelector(`[id*="-flowchart-${id}-"]`);
    if (!group) continue;
    placeIn(nodes, key, group, S.elements.get(key)?.element.address || label(key), entityNode(key).work);
    group.classList.add(key === network.key ? 'in-center' : 'in-entity');
  }
  network.relations.forEach((relation, index) => svg.querySelector(`path[data-id="e${index}"]`)?.classList.add('relation'));
  stopCam();  // a camera still easing on the view left must not move this one
  Object.assign(M, {svg, nodes, edges: [], bounds: boundsOf(svg), vertical, drawn: MEM});
  aim2d(nodes.get(MEM.key), true);
  $('#map2d').classList.add('focused');
  for (const [key, value] of nodes) {
    value.g.classList.toggle('sel', key === S.selected);
    value.g.classList.toggle('near', key !== S.selected && S.neighbors.has(key));
  }
  renderCrumbs();
}
/* In a memory network the panel shows the node with the memories kept at it, each with its observations and its
 * relations, or the memory selected, as the memory module reads them, VIEW-009 and STORE-020. */
function renderMemories(id) {
  if (id.startsWith('e:')) return renderEntity(memoryName(id));
  const own = memoriesAt(id), kept = {class: 'item', style: {'--c': `var(${colorVar(memoryLayer())})`}};
  fill($('#p-object'),
    h('div', {class: 'eyebrow'}, 'Memories'),
    h('h2', {}, nameOf(id)),
    S.elements.has(id) ? h('div', {class: 'addr'}, S.elements.get(id).element.address) : null,
    own.length ? own.map(name => {
      const entity = S.memory.entities.get(name);
      const related = S.memory.relations.filter(relation => relation.from === name || relation.to === name);
      return h('div', kept, h('a', {class: 'link', href: '#', onclick: event => { event.preventDefault(); select(memoryKey(name), true); }}, name),
        entity ? h('small', {}, ` · ${entity.entityType}`) : null,
        (entity?.observations || []).map(one => h('p', {class: 'itemtext'}, one.content)),
        related.map(relation => h('p', {class: 'meta'}, `${relation.from} ${relation.relationType} ${relation.to}`)));
    }) : h('p', {class: 'empty'}, 'No memories are kept here in the layers in view.'));
}
/* ---------- managing the memories, VIEW-031: memories can harm a project, so the person manages them here ----------
 * A memory in the panel, as the memory module keeps it: its type, its observations, its relations and the nodes it is
 * joined to, each edited or deleted in place. Every change is written with the memory module's commands through
 * /api/memory; an edit writes the new before it deletes the old, so a failure loses nothing. The page is told of the
 * change by map.changed, VIEW-018, and reads the memories again. */
async function memoryWrite(...steps) {
  return wrote('/api/memory', {steps: steps.map(([command, args]) => ({command, arguments: args}))});
}
/* What is typed in the panel's editors survives the panel drawn again, with the focus, VIEW-018. */
function keepDrafts(pane, draw) {
  const drafts = new Map([...pane.querySelectorAll('[data-draft]')].map(field => [field.dataset.draft, field.value]));
  const focused = document.activeElement?.closest('[data-draft]')?.dataset.draft;
  draw();
  for (const field of pane.querySelectorAll('[data-draft]')) if (drafts.has(field.dataset.draft)) field.value = drafts.get(field.dataset.draft);
  if (focused) pane.querySelector(`[data-draft="${CSS.escape(focused)}"]`)?.focus();
}
const EDITING = new Set();  // the editors open in the memory panel, kept open when it is drawn again
function joinPlace(join) {
  return join.address !== undefined ? join.address : `${join.receiver} → ${join.provider}`;
}
function renderEntity(name, pane = $('#p-object')) {
  const entity = S.memory.entities.get(name);
  if (!entity) return fill(pane, h('div', {class: 'eyebrow'}, 'Memory'), h('p', {class: 'empty'}, `No memory named ${name}.`));
  const joins = S.memory.joins.filter(join => join.entity === name);
  const related = S.memory.relations.filter(relation => relation.from === name || relation.to === name);
  const others = [...S.memory.entities.keys()].filter(other => other !== name);
  const color = {'--c': `var(${colorVar(memoryLayer())})`};
  const draft = key => `${name}\u0000${key}`;
  const observation = one => {
    const row = h('div', {class: 'item obs', style: color}), editing = draft('obs:' + one.content);
    const show = () => { EDITING.delete(editing); fill(row, h('p', {class: 'itemtext'}, one.content),
      h('div', {class: 'acts'}, h('button', {class: 'btn sm quiet edit', type: 'button', onclick: edit}, 'Edit'),
        h('button', {class: 'btn sm danger delete', type: 'button', onclick: async () => {
          if (await memoryWrite(['delete_observations', {deletions: [{entityName: name, observations: [one.content]}]}]))
            undoable('Deleted the observation.', async () => Boolean(await memoryWrite(['add_observations',
              {observations: [{entityName: name, contents: [one.content]}]}])));
        }}, 'Delete'))); };
    const edit = () => {
      EDITING.add(editing);
      const text = h('textarea', {'data-draft': editing, 'aria-label': 'The observation'}, one.content);  // its text, so the row is found by it
      fill(row, text, h('div', {class: 'acts'}, h('button', {class: 'btn sm primary save', type: 'button', onclick: async () => {
        const changed = text.value.trim();
        if (!changed || changed === one.content) return show();
        EDITING.delete(editing);
        await memoryWrite(['add_observations', {observations: [{entityName: name, contents: [changed]}]}],
          ['delete_observations', {deletions: [{entityName: name, observations: [one.content]}]}]);
      }}, 'Save'), h('button', {class: 'btn sm cancel', type: 'button', onclick: show}, 'Cancel')));
    };
    if (EDITING.has(editing)) edit(); else show();
    return row;
  };
  const relation = one => h('div', {class: 'item rel', style: color},
    one.from === name ? h('b', {}, name) : h('a', {class: 'link', href: '#', onclick: event => { event.preventDefault(); select(memoryKey(one.from), true); }}, one.from),
    ` ${one.relationType} `,
    one.to === name ? h('b', {}, name) : h('a', {class: 'link', href: '#', onclick: event => { event.preventDefault(); select(memoryKey(one.to), true); }}, one.to),
    h('div', {class: 'acts'}, h('button', {class: 'btn sm danger delete', type: 'button', onclick: async () => {
      const relations = [{from: one.from, to: one.to, relationType: one.relationType}];
      if (await memoryWrite(['delete_relations', {relations}]))
        undoable(`Deleted the relation ${one.from} ${one.relationType} ${one.to}.`,
          async () => Boolean(await memoryWrite(['create_relations', {relations}])));
    }}, 'Delete')));
  const joined = one => h('div', {class: 'item join', style: color},
    one.key ? h('a', {class: 'link', href: '#', onclick: event => { event.preventDefault(); enter(one.key); }}, nameOf(one.key))
      : h('b', {}, joinPlace(one)),
    one.orphaned ? h('small', {}, ' · orphaned, the map no longer holds it') : one.key ? h('small', {}, '; Enter goes there.') : null,
    h('div', {class: 'acts'}, h('button', {class: 'btn sm danger unjoin', type: 'button', onclick: () => unjoin(one)}, 'Take away')));
  const renaming = draft('rename');
  const naming = h('div', {class: 'naming', hidden: !EDITING.has(renaming)},
    h('input', {class: 'name', 'data-draft': draft('name'), value: name, 'aria-label': 'Name'}),
    h('input', {class: 'type', 'data-draft': draft('type'), value: entity.entityType, 'aria-label': 'Type'}),
    h('button', {class: 'btn sm primary save-entity', type: 'button', onclick: () => renameEntity(name, naming.querySelector('.name').value.trim(),
      naming.querySelector('.type').value.trim())}, 'Save'),
    h('button', {class: 'btn sm cancel', type: 'button', onclick: () => { EDITING.delete(renaming); naming.hidden = true; }}, 'Cancel'));
  const adding = h('textarea', {class: 'add-obs', 'data-draft': draft('add'), placeholder: 'A new observation'});
  const relating = h('input', {class: 'add-rel-type', 'data-draft': draft('reltype'), placeholder: 'relation, in active voice'});
  const target = h('select', {class: 'add-rel-to', 'aria-label': 'To'}, others.map(other => h('option', {value: other}, other)));
  keepDrafts(pane, () => fill(pane,
    h('div', {class: 'eyebrow'}, 'Memory'),
    h('h2', {}, name),
    h('div', {class: 'pills'}, h('span', {class: 'pill'}, entity.entityType), layerPill(memoryLayer())),
    h('div', {class: 'acts'}, h('button', {class: 'btn sm rename', type: 'button', onclick: () => { EDITING.add(renaming); naming.hidden = false; naming.querySelector('.name').focus(); }}, 'Rename or retype'),
      h('button', {class: 'btn sm danger forget', type: 'button', onclick: () => forget(name)}, 'Delete memory')),
    naming,
    h('div', {class: 'eyebrow'}, 'Observations'),
    entity.observations.length ? entity.observations.map(observation) : h('p', {class: 'empty'}, 'No observations.'),
    adding, h('button', {class: 'btn sm add-obs', type: 'button', onclick: async () => {
      const text = adding.value.trim();
      if (!text) return;
      adding.value = '';  // emptied before the write, so the panel drawn again for it does not keep it
      if (!await memoryWrite(['add_observations', {observations: [{entityName: name, contents: [text]}]}])) adding.value = text;
    }}, 'Add observation'),
    h('div', {class: 'eyebrow'}, 'Relations'),
    related.length ? related.map(relation) : h('p', {class: 'empty'}, 'No relations.'),
    others.length ? h('div', {class: 'add-rel'}, relating, target, h('button', {class: 'btn sm add-rel', type: 'button', onclick: async () => {
      const type = relating.value.trim();
      if (!type) return;
      relating.value = '';
      if (!await memoryWrite(['create_relations', {relations: [{from: name, to: target.value, relationType: type}]}])) relating.value = type;
    }}, 'Add relation')) : null,
    h('div', {class: 'eyebrow'}, 'Kept at'),
    joins.length ? joins.map(joined) : h('p', {class: 'empty'}, 'Joined to no node.')));
}
/* A memory renamed or retyped: the reference server has no command for it, so it is made again under its new name and
 * type with its observations, joined again to each node of the map it was joined to, its relations made again, and the
 * old one deleted. A join the map no longer holds cannot be made again. */
async function renameEntity(name, next, type) {
  const entity = S.memory.entities.get(name);
  EDITING.delete(`${name}\u0000rename`);
  if (!entity || !next || !type || (next === name && type === entity.entityType)) return renderEntity(name);
  const made = {name: next, entityType: type, observations: entity.observations.map(one => one.content)};
  const again = S.memory.joins.filter(join => join.entity === name && join.key)
    .map(join => ['create_entities', {entities: [made], node: targetOf(join.key)}]);
  const swap = value => value === name ? next : value;
  const related = S.memory.relations.filter(relation => relation.from === name || relation.to === name)
    .map(relation => ({from: swap(relation.from), to: swap(relation.to), relationType: relation.relationType}));
  const steps = [['create_entities', {entities: [made]}], ...again,
    ...(related.length ? [['create_relations', {relations: related}]] : [])];
  const gone = ['delete_entities', {entityNames: [name]}];
  if (next === name ? await memoryWrite(gone, ...steps) : await memoryWrite(...steps, gone)) S.selected = memoryKey(next);
}
/* Taking a memory away, VIEW-031: a wrong memory misleads every agent that reads it, and so does one deleted by a slip.
 * What the map still holds is made again by Undo: the memory with its observations, its joins to the nodes drawn and
 * its relations. A join the map no longer holds cannot be made again, so taking that away is asked first, naming what
 * is lost. */
const plural = (count, one, many = one + 's') => `${count} ${count === 1 ? one : many}`;
function remade(name) {
  const entity = S.memory.entities.get(name);
  const made = {name, entityType: entity.entityType, observations: entity.observations.map(one => one.content)};
  const joins = S.memory.joins.filter(join => join.entity === name);
  const relations = S.memory.relations.filter(relation => relation.from === name || relation.to === name)
    .map(relation => ({from: relation.from, to: relation.to, relationType: relation.relationType}));
  const held = joins.filter(join => !join.orphaned && join.key);
  return {entity, relations, lost: joins.filter(join => !held.includes(join)), steps: [['create_entities', {entities: [made]}],
    ...held.map(join => ['create_entities', {entities: [made], node: targetOf(join.key)}]),
    ...(relations.length ? [['create_relations', {relations}]] : [])]};
}
async function forget(name, after = () => {}) {
  if (!S.memory.entities.has(name)) return;
  const again = remade(name), gone = ['delete_entities', {entityNames: [name]}];
  if (again.lost.length) {
    const sure = await confirmAct({title: `Delete the memory ${name}?`,
      text: 'No agent reads it again. It cannot be brought back from here, since the map no longer holds a node it was kept at.',
      lost: [`${name}, ${again.entity.entityType}, with ${plural(again.entity.observations.length, 'observation')}`,
        ...again.relations.map(relation => `The relation ${relation.from} ${relation.relationType} ${relation.to}`),
        ...again.lost.map(join => `Its join to ${joinPlace(join)}, which the map no longer holds`)],
      verb: 'Delete memory'});
    if (sure && await memoryWrite(gone)) after();
    return;
  }
  if (!await memoryWrite(gone)) return;
  after();
  undoable(`Deleted the memory ${name}.`, async () => Boolean(await memoryWrite(...again.steps)));
}
async function unjoin(join, after = () => {}) {
  const entity = S.memory.entities.get(join.entity);
  if (join.orphaned || !join.key) {
    const sure = await confirmAct({title: 'Take this join away?',
      text: `The memory stays. The join cannot be made again, since the map no longer holds ${joinPlace(join)}.`,
      lost: [`The join from ${join.entity} to ${joinPlace(join)}`],
      kept: [entity ? `${join.entity}, with ${plural(entity.observations.length, 'observation')}` : join.entity],
      verb: 'Take away the join'});
    if (sure && await memoryWrite(['unjoin', {id: join.join_id}])) after();
    return;
  }
  if (!await memoryWrite(['unjoin', {id: join.join_id}])) return;
  after();
  undoable(`Took ${join.entity} away from ${nameOf(join.key)}.`, async () => Boolean(await memoryWrite(['create_entities',
    {entities: [{name: join.entity, entityType: entity?.entityType || 'memory', observations: []}], node: targetOf(join.key)}])));
}
/* ---------- the orphaned menu, LAYER-013: memories that lost their node show what they were
 * attached to ----------
 * The memory joins the map no longer holds, from `memory orphaned`, each with what it was attached to, and the memories
 * joined to no node at all; a join is taken away or its memory deleted from here. */
const O = {open: false};
async function orphans() {
  let lost;
  try { lost = (await read('memory-orphaned')).joins; } catch (error) { toast(error.message); return; }
  Object.assign(F, {id: null, which: null, ids: new Set(), drawn: new Map()});
  O.open = true;
  const loose = [...S.memory.entities.keys()].filter(name => !S.memory.joins.some(join => join.entity === name));
  $('#float .title').textContent = 'Orphaned memories';
  fill($('#float .body'),
    lost.length ? lost.map(join => h('div', {class: 'ticket orphan'}, h('b', {}, join.entity),
      h('p', {class: 'note'}, `was attached to ${joinPlace(join)}`),
      h('div', {class: 'acts'}, h('button', {class: 'btn sm unjoin', type: 'button',
        onclick: () => unjoin({...join, orphaned: true}, orphans)}, 'Take away the join'),
        h('button', {class: 'btn sm danger forget', type: 'button', onclick: () => forget(join.entity, orphans)}, 'Delete memory'))))
      : h('p', {class: 'empty'}, 'No memory join is orphaned.'),
    loose.length ? [h('div', {class: 'eyebrow'}, 'Joined to no node'), loose.map(name => h('div', {class: 'ticket loose'},
      h('b', {}, name), h('div', {class: 'acts'}, h('button', {class: 'btn sm danger forget', type: 'button',
        onclick: () => forget(name, orphans)}, 'Delete memory'))))] : null);
  $('#float').hidden = false;
}
function renderOrphans() {
  $('#orphanBtn').textContent = `Orphaned memories ${S.memory.orphaned}`;
  if (O.open && !$('#float').hidden && $('#float .title').textContent === 'Orphaned memories') orphans();
}
$('#orphanBtn').onclick = () => { showAdmin(false); orphans(); };
/* Agent prompts, VIEW-039: how agents' permission prompts are answered, read from the settings each time the window
 * opens and written back to them, so the administrator's choice is the one every agent follows and never reverts.
 * Each choice reads in plain words, its setting's value under it, and approving every prompt says what it risks. A
 * choice is saved as it is made, and the window says so. */
const PROMPT_WORDS = {'approve-all': ['Approve every prompt', 'Agents run any tool without asking, including ones that change or delete files.'],
  'approve-reads': ['Approve reads and searches; ask for the rest', ''], ask_all: ['Ask every prompt as a question at the ticket', '']};
$('#promptsBtn').onclick = async () => {
  showAgentMenu(false);
  let found;
  try { found = await read('dispatch-prompts'); } catch (error) { return toast(error.message); }
  fill($('#prompts .choices'), found.choices.map(choice => h('label', {class: 'choice'},
    h('input', {type: 'radio', name: 'prompts', value: choice, checked: choice === found.value,
                onchange: async () => {
                  if (await wrote('/api/dispatch-prompts', {value: choice})) $('#prompts .saved').textContent = `Saved: ${choice}`;
                  else $(`#prompts input[value="${found.value}"]`).checked = true;
                }}),
    h('b', {}, (PROMPT_WORDS[choice] || [choice])[0]), h('code', {}, choice),
    (PROMPT_WORDS[choice] || [])[1] ? h('span', {class: 'risk'}, PROMPT_WORDS[choice][1]) : null)));
  $('#prompts .saved').textContent = `Now: ${found.value}`;
  await readAutostart();
  $('#prompts').hidden = false;
};
/* The Agents menu: the agents' own settings and repair, kept apart from Administration's project-wide removals. */
function showAgentMenu(open) { $('#agentbox').hidden = !open; }
overlay($('#agentbox'), {kind: 'menu', focus: '#agentCount'});
toggler($('#agentsMenuBtn'), $('#agentbox'), async () => {
  // the default agent, chosen here as in every picker: what chats, issues and intakes start with unless another is chosen
  if (!$('#defaultAgentPick').firstChild) {
    // the default as dispatch has it, and while one chosen is being made the default, that one
    const holder = {chosen: false, asked: null};
    Object.defineProperty(holder, 'agent', {get: () => holder.asked ?? HARNESS.default, set: agent => { holder.asked = agent; }});
    $('#defaultAgentPick').append(PICKERS.default ||= agentPicker({label: 'Default agent', star: false, kept: true, exact: true,
      holder, onchange: async agent => { await makeDefault(agent); holder.asked = null; paintPickers(); }}));
  }
  readHarnesses();
  await readAutostart();
  $('#agentCount').value = AUTO.agents ?? 5;  // the saved setting, as it is now
});
$('#agentCount').onchange = async event => {
  const count = Number(event.target.value);
  if (!Number.isInteger(count) || count < 1) { event.target.value = AUTO.agents ?? 5; return; }
  event.target.disabled = true;
  try {
    const saved = await wrote('/api/dispatch-autostart', {agents: count});
    if (saved) { Object.assign(AUTO, saved); event.target.value = saved.agents; toast(`Agents at once: ${saved.agents}.`); }
    else event.target.value = AUTO.agents ?? 5;
  } finally { event.target.disabled = false; }
};
/* Reset agents ends the sessions of agents that died; it cannot be undone, so it is asked first, saying what it does
 * and what it leaves. */
$('#resetAgentsBtn').onclick = async event => {
  showAgentMenu(false);
  if (!await confirmAct({title: 'Reset agents?',
    text: 'Use it after a crash, when an agent stopped without letting go of its ticket.',
    lost: ['The sessions of agents that are no longer running are closed', 'The tickets they still hold go back on the board'],
    kept: ['Agents at work are left alone', 'Nothing is deleted: every ticket, its steps and its log stay'],
    verb: 'Reset agents'})) return;
  event.target.disabled = true;
  try {
    const done = await wrote('/api/dispatch-reset', {});
    if (done) {
      toast(`Reset: ${done.released.length} ticket(s) back on the board, ${done.sessions_ended.length} dead session(s) closed; ${done.still_working.length} agent(s) still working.`);
      await renderBoard(); await renderAgents();
    }
  } finally { event.target.disabled = false; }
};
$('#prompts .close').onclick = () => { $('#prompts').hidden = true; };
overlay($('#prompts'), {kind: 'dialog'});
/* ---------- the settings screen ----------
 * Every setting of the project's folder, as metaform config shows them, and every module with whether it is on. The
 * modules come first, each switched on or off as metaform enable and disable do, with the modules setting under them
 * as the modules this folder shows; then the chassis's settings and each module's. A setting reads with its label, its
 * help, its state (default, set or glued), Glue and Reset, and takes the control its kind needs: a switch, a number, a
 * list of its choices, a checklist, or text, a list as its items separated by commas. A change is saved as it is made,
 * through metaform set and unset in the project's folder, so it is checked as the command line checks it, and a
 * refusal is said under the setting with its next step. Left and Right change a switch or a choice, as on the
 * terminal's settings screen. */
const CONFIG = {data: null, filter: '', errors: new Map()};
const SHOWN_MODULES = 'modules';  // the chassis setting shown with the modules: which of them this folder shows
async function openSettings() {
  showAgentMenu(false);
  $('#settingsbox').hidden = true;
  if (!S.project) return toast('Choose a project first: the settings shown are those of its folder.');
  if (WS.reveal('settings')) return;  // a pane in the workspace: it shows there and reads as it shows
  await showSettings();
}
async function showSettings() {
  CONFIG.errors.clear();
  fill($('#settings .body'), h('p', {class: 'loading'}, 'Reading the settings…'));
  $('#settings').hidden = false;
  await readSettings();
}
async function readSettings() {
  const project = S.project;
  try {
    const found = await read('settings');
    if (S.project !== project) return;
    CONFIG.data = found;
  } catch (error) { fill($('#settings .body'), refusalBox(error.body || {error: error.message})); return; }
  renderSettings();
}
/* A refusal in place: what was refused and the next step, as the command line says them. */
function refusalBox(body) {
  return h('div', {class: 'failed setfail', role: 'alert'}, h('p', {}, body.error || 'It was not saved.'),
    body.next ? h('p', {class: 'next'}, 'Next: ', h('code', {}, body.next)) : null);
}
/* A value as the screen says it: on or off, a list's items, all for an empty list that means all, (none) for none. */
function shownValue(key, value) {
  if (typeof value === 'boolean') return value ? 'on' : 'off';
  if (Array.isArray(value)) return value.length ? value.join(', ') : CONFIG.data?.all_when_empty.includes(key) ? 'all' : '(none)';
  return value === null || value === undefined || value === '' ? '(none)' : String(value);
}
function renderSettings() {
  const data = CONFIG.data;
  if (!data) return;
  const body = $('#settings .body');
  const focused = document.activeElement?.closest?.('#settings .body [data-focus]')?.dataset.focus;
  const scroll = body.scrollTop;
  const query = CONFIG.filter.trim().toLowerCase();
  const matches = (...texts) => !query || texts.some(text => String(text || '').toLowerCase().includes(query));
  const shownRow = data.settings.find(row => row.key === SHOWN_MODULES && row.owner === 'chassis');
  const group = (title, about, kids) => h('section', {class: 'setgroup'},
    h('div', {class: 'head'}, h('h3', {}, title), about ? h('span', {class: 'hint'}, about) : null), kids);
  const sections = [h('p', {class: 'hint'}, `The settings of ${S.project}, kept for ${data.folder}. A folder setting `
    + 'applies to this folder and every folder below it; a global one applies everywhere. They are the settings '
    + 'metaform config shows, and each change is saved as metaform set saves it.')];
  const modules = data.modules.filter(module => matches(module.id, module.summary, module.problem));
  const modulePart = [data.modules_refused ? refusalBox(data.modules_refused) : null,
    modules.length ? h('div', {class: 'setlist'}, modules.map(moduleRow)) : null,
    shownRow && matches(shownRow.key, shownRow.help, 'Modules shown in this folder')
      ? h('div', {class: 'setlist'}, settingRow(shownRow, 'Modules shown in this folder')) : null].filter(Boolean);
  if (modulePart.length) sections.push(group('Modules', 'On or off for every project, as metaform enable and disable '
    + 'turn them. A module turned off keeps its settings.', modulePart));
  const owners = new Set(['chassis', ...data.modules.map(module => module.id), ...data.settings.map(row => row.owner)]);
  for (const owner of owners) {
    const own = data.settings.filter(row => row.owner === owner && row !== shownRow
      && matches(row.key, row.label, row.help, row.details));
    if (!own.length) continue;
    sections.push(group(owner === 'chassis' ? 'Chassis' : owner, owner === 'chassis' ? 'Settings of the chassis itself.'
      : data.modules.find(module => module.id === owner)?.summary || '', h('div', {class: 'setlist'}, own.map(row => settingRow(row)))));
  }
  if (sections.length === 1) sections.push(h('p', {class: 'empty'}, `No setting matches ${CONFIG.filter.trim()}.`));
  fill(body, sections);
  body.scrollTop = scroll;
  if (focused) body.querySelector(`[data-focus="${CSS.escape(focused)}"]`)?.focus({preventScroll: true});
}
/* Left and Right turn a switch off and on, and step a list of choices back and on, saving as a click does. */
function arrowSwitch(event, input) {
  if (!['ArrowLeft', 'ArrowRight'].includes(event.key) || input.disabled) return;
  event.preventDefault();
  const on = event.key === 'ArrowRight';
  if (input.checked === on) return;
  input.checked = on;
  input.dispatchEvent(new Event('change'));
}
function arrowSelect(event, select) {
  if (!['ArrowLeft', 'ArrowRight'].includes(event.key) || select.disabled) return;
  event.preventDefault();
  const next = select.selectedIndex + (event.key === 'ArrowRight' ? 1 : -1);
  if (next < 0 || next >= select.options.length || select.options[next].disabled) return;
  select.selectedIndex = next;
  select.dispatchEvent(new Event('change'));
}
function moduleRow(module) {
  const id = `module:${module.id}`;
  const input = h('input', {type: 'checkbox', role: 'switch', checked: module.enabled, 'data-focus': id,
    'aria-label': `The ${module.id} module`, onchange: () => switchModule(module, input),
    onkeydown: event => arrowSwitch(event, input)});
  const error = CONFIG.errors.get(id);
  return h('div', {class: 'setrow module', 'data-module': module.id},
    h('div', {class: 'what'},
      h('div', {class: 'name'}, h('code', {class: 'id'}, module.id),
        module.place !== 'system' ? h('span', {class: 'badge', title: `Found in the ${module.place} place`}, module.place) : null,
        module.problem ? h('span', {class: 'badge warn'}, 'not loaded') : null),
      h('span', {class: 'help'}, module.problem || module.summary)),
    h('div', {class: 'control'}, h('label', {class: 'switch'}, input, module.enabled ? 'On' : 'Off')),
    error ? refusalBox(error) : null);
}
async function switchModule(module, input) {
  const id = `module:${module.id}`, on = input.checked;
  if (!on && module.id === 'web' && !await confirmAct({title: 'Turn off the web module?',
    text: 'It serves this page. Turned off, metaform web does not start the page again until it is turned back on: metaform enable web.',
    kept: ['Its settings keep their saved values'], verb: 'Turn it off', cancel: 'Keep it on'})) {
    input.checked = true;
    return;
  }
  input.disabled = true;
  const done = await posted('/api/modules', {module: module.id, enabled: on});
  if (!done.ok) {
    input.checked = !on;
    input.disabled = false;
    CONFIG.errors.set(id, done.body);
    renderSettings();
    return;
  }
  CONFIG.errors.delete(id);
  toast(`Module ${module.id}: ${on ? 'on' : 'off'}.`);
  await readSettings();
  readAutostart();
}
function settingRow(row, label = row.label) {
  const id = `setting:${row.key}`;
  const error = CONFIG.errors.get(id);
  const control = settingControl(row, id, label);
  const empty = Array.isArray(row.value) && !row.value.length && CONFIG.data.all_when_empty.includes(row.key);
  const glue = row.state === 'glued' || row.value === null || row.value === undefined || empty ? null
    : h('button', {class: 'btn sm quiet glue', type: 'button', 'data-focus': `glue:${row.key}`,
      title: 'Keep this value through metaform unset all, as metaform set --glue does',
      onclick: () => saveSetting(row, row.value, {glue: true})}, 'Glue');
  const reset = h('button', {class: 'btn sm quiet reset', type: 'button', disabled: row.state === 'default',
    'data-focus': `reset:${row.key}`, onclick: () => resetSetting(row),
    title: row.state === 'glued' ? `Unglue it and return it to its default, as metaform unset --unglue ${row.switch} does`
      : `Return it to its default, as metaform unset ${row.switch} does`}, row.state === 'glued' ? 'Unglue' : 'Reset');
  const state = {default: ['badge off', 'The default: nothing is saved for it'], set: ['badge ok', 'Saved for this folder'],
    glued: ['badge warn', 'Kept through metaform unset all until it is unglued']}[row.state] || ['badge', ''];
  return h('div', {class: 'setrow', 'data-key': row.key},
    h('div', {class: 'what'},
      h('div', {class: 'name'}, h('span', {class: 'label'}, label), h('code', {}, row.switch),
        h('span', {class: `${state[0]} state`, title: state[1]}, row.state),
        row.scope === 'global' ? h('span', {class: 'badge', title: 'Applies in every folder'}, 'global') : null,
        row.person_only ? h('span', {class: 'badge', title: 'Only you change it, here or on the command line; '
          + 'an agent is refused it over MCP'}, 'yours') : null),
      row.help ? h('span', {class: 'help'}, row.help) : null,
      row.details ? h('details', {}, h('summary', {}, 'More'), h('p', {}, row.details)) : null),
    h('div', {class: 'control'}, control.main, glue, reset),
    control.wide || null,
    error ? refusalBox(error) : null);
}
/* The control a setting's kind takes; `wide` goes under the row, as a checklist does. */
function settingControl(row, id, label) {
  const save = value => saveSetting(row, value);
  if (row.kind === 'bool') {
    const input = h('input', {type: 'checkbox', role: 'switch', checked: Boolean(row.value), 'aria-label': label, 'data-focus': id,
      onchange: () => save(input.checked), onkeydown: event => arrowSwitch(event, input)});
    return {main: h('label', {class: 'switch'}, input, row.value ? 'On' : 'Off')};
  }
  if (row.kind === 'int') {
    const input = h('input', {type: 'number', step: '1', min: row.min ?? null, max: row.max ?? null, value: row.value ?? '',
      'aria-label': label, 'data-focus': id, onchange: () => save(input.value.trim())});
    return {main: input};
  }
  const choices = Array.isArray(row.choices) && row.choices.length ? row.choices : null;
  if (row.kind === 'select' && choices) {
    const listed = choices.includes(row.value) ? choices : [row.value ?? '', ...choices];
    const select = h('select', {'aria-label': label, 'data-focus': id, onchange: () => save(select.value),
      onkeydown: event => arrowSelect(event, select)},
      listed.map(choice => h('option', {value: choice, selected: choice === row.value, disabled: !choices.includes(choice)},
        choice === '' ? '(none)' : choice)));
    return {main: select};
  }
  if (row.kind === 'list' && choices) return {main: null, wide: checklist(row, choices, id, label)};
  const all = CONFIG.data.all_when_empty.includes(row.key);
  const input = h('input', {type: 'text', value: Array.isArray(row.value) ? row.value.join(',') : String(row.value ?? ''),
    'aria-label': label, 'data-focus': id, spellcheck: 'false', autocomplete: 'off',
    placeholder: row.kind === 'list' ? (all ? 'all' : 'names, separated by commas') : '(none)',
    onchange: () => save(input.value)});
  return {main: input};
}
/* A list's choices, each checked or not. A list that means all when it is empty shows every choice checked then, and
 * is saved empty when every one is checked again; one choice at least stays checked, since none would mean all. */
function checklist(row, choices, id, label) {
  const all = CONFIG.data.all_when_empty.includes(row.key);
  const value = Array.isArray(row.value) ? row.value : [];
  const chosen = new Set(all && !value.length ? choices : value);
  const listed = [...choices, ...value.filter(name => !choices.includes(name))];
  const boxes = listed.map(choice => h('input', {type: 'checkbox', value: choice, checked: chosen.has(choice),
    'data-focus': `${id}:${choice}`}));
  // A list holding one value per name, `<name><exclusive><value>`: checking one unchecks the others of its name.
  const nameOf = value => row.exclusive ? value.split(row.exclusive)[0] : null;
  const changed = event => {
    const box = event?.target;
    if (row.exclusive && box?.checked) {
      for (const other of boxes) if (other !== box && nameOf(other.value) === nameOf(box.value)) other.checked = false;
    }
    const picked = boxes.filter(box => box.checked).map(box => box.value);
    if (all && !picked.length) {
      CONFIG.errors.set(id, {error: 'Keep one checked at least. With every one checked, all are shown.'});
      return renderSettings();
    }
    saveSetting(row, all && choices.every(choice => picked.includes(choice)) ? [] : picked);
  };
  for (const box of boxes) box.addEventListener('change', changed);
  return h('div', {class: 'checks', role: 'group', 'aria-label': label},
    boxes.map((box, index) => h('label', {class: 'check'}, box, h('code', {}, listed[index]))),
    all ? h('span', {class: 'hint'}, 'Every one checked, the default, shows them all.') : null);
}
/* Save one setting, or glue it, and say so with Undo; Undo puts back what it was. A refusal is said under it. */
async function saveSetting(row, value, {glue = false, quiet = false} = {}) {
  const id = `setting:${row.key}`;
  const before = {state: row.state, value: row.value};
  const done = await posted('/api/settings', {key: row.key, value, ...(glue ? {glue: true} : {})});
  if (!done.ok) { CONFIG.errors.set(id, done.body); renderSettings(); return false; }
  CONFIG.errors.delete(id);
  CONFIG.data = done.body;
  renderSettings();
  afterSetting(row.key);
  if (quiet) return true;
  const now = done.body.settings.find(one => one.key === row.key);
  const said = [`${row.label}: ${shownValue(row.key, now?.value)}${glue ? ', glued' : ''}.`, ...(done.body.notices || [])].join(' ');
  if (glue) toast(said);
  else undoable(said, () => before.state === 'default' ? resetSetting(now || row, {quiet: true})
    : saveSetting(now || row, before.value, {quiet: true}));
  return true;
}
async function resetSetting(row, {quiet = false} = {}) {
  const id = `setting:${row.key}`, glued = row.state === 'glued';
  if (glued && !quiet && !await confirmAct({title: `Unglue ${row.label}?`,
    text: 'A glued setting keeps its value through metaform unset all. Unglued, it returns to its default.',
    verb: 'Unglue and reset', danger: false})) return false;
  const before = row.value;
  const done = await posted('/api/settings/reset', {key: row.key, ...(glued ? {unglue: true} : {})});
  if (!done.ok) { CONFIG.errors.set(id, done.body); renderSettings(); return false; }
  CONFIG.errors.delete(id);
  CONFIG.data = done.body;
  renderSettings();
  afterSetting(row.key);
  if (quiet) return true;
  const now = done.body.settings.find(one => one.key === row.key);
  undoable(`${row.label}: back to its default, ${shownValue(row.key, now?.value)}.`,
    () => saveSetting(now || row, before, {glue: glued, quiet: true}));
  return true;
}
/* What the rest of the page shows from a setting follows it: the Autostart switch, and the folder's layers. */
function afterSetting(key) {
  if (key.startsWith('dispatch_')) readAutostart();
  if (key === 'layers' && S.view === null) {
    read('layers', {limit: 0}).then(found => { S.layers = found.results; renderChips(); }).catch(error => toast(error.message));
  }
  // ULTRA: the 3D map fades to the graphics chosen, as U does
  if (key === 'web_graphics') {  // set on the Settings screen: the theme follows, space for ultra
    const ultra = CONFIG.data?.settings?.find(one => one.key === key)?.value === 'ultra';
    if (ultra !== (document.documentElement.dataset.theme === 'space')) setTheme(ultra ? 'space' : PLAIN.last, false);
  }
}
$('#allSettingsBtn').onclick = openSettings;
$('#viewAllSettingsBtn').onclick = openSettings;
$('#settings .search').addEventListener('input', event => { CONFIG.filter = event.target.value; renderSettings(); });
$('#settings .close').onclick = () => { $('#settings').hidden = true; };
overlay($('#settings'), {kind: 'dialog', close: () => { $('#settings').hidden = true; }});
function aspect() { const box = $('#viewport').getBoundingClientRect(); return Math.max(0.2, box.width / Math.max(1, box.height)); }
function frame(box) {
  let {x, y, w, h: height} = box; const a = aspect();
  if (w / height > a) { const nh = w / a; y -= (nh - height) / 2; height = nh; } else { const nw = height * a; x -= (nw - w) / 2; w = nw; }
  return {x, y, w, h: height};
}
/* A view fades in or out, and the promise settles once the browser has run the fade's time, which starts late when
 * frames come late; a fade that changes nothing settles on the timer. With reduced motion it changes at once,
 * VIEW-016. */
function fade(svg, to, ms = 480) {
  if (reduced()) { svg.style.transition = ''; svg.style.opacity = ''; return Promise.resolve(); }
  svg.style.transition = `opacity ${ms}ms ease`;
  svg.getBoundingClientRect();  // the fade starts from the opacity the view has now
  svg.style.opacity = String(to);
  const run = svg.getAnimations().find(one => one.transitionProperty === 'opacity');
  if (!run) return new Promise(resolve => setTimeout(resolve, ms));
  return run.finished.then(() => {}, () => {});  // a fade cut by another, or by its view leaving the page, settles too
}
/* A view that has just been put in place, faded in from nothing. */
function arrive(svg) {
  if (reduced()) return;
  svg.style.transition = ''; svg.style.opacity = '0';
  fade(svg, 1);
}
const into = node => ({x: node.x - node.w * 0.6, y: node.y - node.h * 0.6, w: node.w * 1.2, h: node.h * 1.2});
/* The camera is the map's viewBox; the zoom in it is the one the mode sets, VIEW-041. */
function setCam(cam) {
  M.cam = cam;
  M.svg?.setAttribute('viewBox', `${cam.x} ${cam.y} ${cam.w} ${cam.h}`);
  // In the small area an edge is never thinner than a pixel on the screen, VIEW-008: the map's units one pixel spans,
  // which the edges' width is held to at least; in the large area they keep the width the map gives them. Every edge
  // takes a click a pixel wider than it is drawn, `--unit2d`.
  const wide = M.svg?.getBoundingClientRect().width;
  M.svg?.style.setProperty('--pixel2d', !$('.app').classList.contains('swapped') && wide ? String(cam.w / wide) : '0');
  M.svg?.style.setProperty('--unit2d', wide ? String(cam.w / wide) : '0');
  again2d();  // a figure keeps its least size on the screen as the zoom changes
  hover2d(wide ? wide / cam.w : 0);
  showModes();
}
const near = (a, b) => Boolean(a && b) && ['x', 'y', 'w', 'h'].every(k => Math.abs(a[k] - b[k]) <= Math.max(a.w, b.w) * 1e-4);
function stopCam() { cancelAnimationFrame(M.frame); M.to = null; }
/* Every move of the 2D camera eases in and out and is never set at once, VIEW-041; with reduced motion it moves at
 * once, VIEW-016. A move to where the camera is already going goes on as it is. The middle of the view moves in a
 * straight line and its size by its log, so a zoom runs at one pace however far it goes, as the eye takes a zoom; a
 * move asked for while another runs leaves at the speed that one had, so the camera never jolts, and one from rest
 * eases in and out, `hermite`. `dive` speeds up all the way, the camera going into a node as its map fades out,
 * VIEW-016; `length` is its time in seconds. Its time starts at its first frame, so work the page does before that
 * frame is not skipped over in one step. */
const MOVE = {from: null, to: null, rate: null, start: null, length: 0.7, dive: false};
const CAM_PARTS = ['x', 'y', 'w', 'h'];
const camParts = cam => ({x: cam.x + cam.w / 2, y: cam.y + cam.h / 2, w: Math.log(cam.w), h: Math.log(cam.h)});
function camAt(now) {  // the camera of the move under way at `now`, how fast each part moves, and the share gone
  const s = MOVE.start === null ? 0 : Math.min(1, Math.max(0, (now - MOVE.start) / 1000 / MOVE.length)), at = {}, rate = {};
  for (const part of CAM_PARTS) {
    const from = MOVE.from[part], to = MOVE.to[part];
    if (MOVE.dive) [at[part], rate[part]] = [from + (to - from) * s * s * s, 3 * s * s * (to - from) / MOVE.length];
    else [at[part], rate[part]] = hermite(from, to, MOVE.rate[part], MOVE.length, s);
  }
  const w = Math.exp(at.w), height = Math.exp(at.h);
  return {cam: {x: at.x - w / 2, y: at.y - height / 2, w, h: height}, rate, s};
}
function moveCam(target, {length = 0.7, dive = false} = {}) {
  if (!M.svg) return;
  const to = frame(target);
  if (!M.cam) return setCam(to);
  if (near(M.to || M.cam, to)) return;
  const under = M.to && MOVE.start !== null && !MOVE.dive ? camAt(performance.now()) : null;
  stopCam();
  if (reduced()) return setCam(to);
  M.to = to;
  Object.assign(MOVE, {from: camParts(M.cam), to: camParts(to), start: null, length, dive,
    rate: under && !dive ? under.rate : Object.fromEntries(CAM_PARTS.map(part => [part, 0]))});
  const step = now => {
    MOVE.start ??= now;
    const {cam, s} = camAt(now);
    setCam(cam);
    if (s < 1) M.frame = requestAnimationFrame(step); else M.to = null;
  };
  M.frame = requestAnimationFrame(step);
}
/* The 2D map's camera, VIEW-041: the mode sets its zoom, `scaleFor`, and the limits where it stands, `place2d`.
 * Changing mode eases there, `setMode`; after that the zoom holds, a selection only moving the view within the limits,
 * and a fit refitting, eased, when the pane or the map changes size, `aim2d`. */
const at2d = id => !id ? null : M.nodes.get(id) || (id.startsWith('p:') ? M.nodes.get(joinOf(id)?.provider) : null);
const area2d = () => $('#viewport').getBoundingClientRect();
const mid2d = box => ({x: box.x + box.w / 2, y: box.y + box.h / 2});
const MAC = /Mac|iPhone|iPad/.test(navigator.userAgentData?.platform || navigator.platform || '');
function smallestText(svg) {  // the smallest font size of the diagram's labels, in its own units
  let least = Infinity;
  for (const text of svg.querySelectorAll('text, tspan'))
    if ([...text.childNodes].some(node => node.nodeType === 3 && node.textContent.trim()))
      least = Math.min(least, parseFloat(getComputedStyle(text).fontSize) || Infinity);
  return isFinite(least) ? least : 13;
}
function labelSize(svg) {  // read once for each drawing, while it is on the page
  if (!MODE.labels.has(svg) && svg.isConnected) MODE.labels.set(svg, smallestText(svg));
  return MODE.labels.get(svg) || 12;
}
/* The text the text modes are measured from, read from the page so they move with its text size, VIEW-023: the
 * smallest text shown outside the maps, Small, and the panel's heading, Medium. Read again when the page changes
 * size, as a change of its text size does. */
function pageText() {
  if (MODE.page) return MODE.page;
  let small = Infinity;
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let text = walk.nextNode(); text; text = walk.nextNode()) {
    const box = text.parentElement;
    if (!box || !text.textContent.trim() || box.closest('#viewport, #stage, #draw, svg, script, style')) continue;
    if (box.checkVisibility ? !box.checkVisibility({checkOpacity: true, checkVisibilityCSS: true}) : !box.getClientRects().length) continue;
    const size = parseFloat(getComputedStyle(box).fontSize);
    if (size > 0) small = Math.min(small, size);
  }
  const probe = $('#p-object').appendChild(h('h2', {style: {position: 'absolute', visibility: 'hidden'}}, 'M'));
  const heading = parseFloat(getComputedStyle(probe).fontSize) || 20;
  probe.remove();
  return MODE.page = {small: isFinite(small) ? small : 11, heading};
}
addEventListener('resize', () => { MODE.page = null; });
/* The zoom a fit sets, in screen pixels to a unit of the map. A fit leaves a margin of MARGIN pixels, less on a pane
 * too small to spare it, on the sides it fits. */
function scaleFor(fit, area = area2d()) {
  const box = M.bounds, room = side => Math.min(MARGIN, side / 10);
  const across = (area.width - 2 * room(area.width)) / Math.max(1, box.w);
  const down = (area.height - Math.min(foot2d(), area.height / 3) - 2 * room(area.height)) / Math.max(1, box.h);
  return fit === 'height' ? down : fit === 'width' ? across : Math.min(across, down);
}
/* The zoom the map is drawn at now: the distance being set, while 1 is held open; else, on a selection, its zoom,
 * never further out than the fit; else the fit. Neighbors frames the node and the parts one join away from it, or a
 * join with its receiver and the parts serving it, and comes no closer than the distance. */
function scale2d(area = area2d()) {
  if (MODE.setting) return MODE.setting.scale;
  const fit = scaleFor(MODE.fit, area), center = S.selected ? center2d(S.selected) : null;
  if (MODE.zoom === 'off' || !center) return fit;
  const most = Math.max(fit, distance2d() / labelSize(M.svg));
  if (MODE.zoom === 'distance') return most;
  let across = 0, down = 0;
  for (const node of neighbors2d(S.selected)) {
    across = Math.max(across, Math.abs(node.x - center.x) + node.w / 2);
    down = Math.max(down, Math.abs(node.y - center.y) + node.h / 2);
  }
  const room = side => Math.min(MARGIN, side / 10), usable = area.height - Math.min(foot2d(), area.height / 3);
  const frames = Math.min((area.width / 2 - room(area.width)) / Math.max(1, across),
    (usable / 2 - room(usable)) / Math.max(1, down));
  return Math.max(fit, Math.min(most, frames));
}
/* The distance, as the height in screen pixels the map's text is drawn at: the one set with 1, else twice the page's
 * smallest text. */
const distance2d = () => MODE.distance || 2 * pageText().small;
function neighbors2d(id) {
  const join = id.startsWith('p:') ? joinOf(id) : null, ids = new Set([id]);
  if (join) [join.receiver, ...join.providers].forEach(one => ids.add(one));
  else for (const edge of M.edges) {
    if (edge.join.receiver === id) ids.add(edge.provider);
    if (edge.provider === id) ids.add(edge.join.receiver);
  }
  return [...ids].map(one => M.nodes.get(one)).filter(Boolean);
}
/* The room kept free at the foot of the 2D map's window, in screen pixels, so no node is fitted under what stands
 * there: the hover card at rest, as tall as it is with a line of words, so a card that grows while it shows never
 * moves the map, and any other overlay standing at the window's foot, measured as it is now; and a small gap. */
const FOOT2D = {card: 0, gap: 8};
function foot2d() {
  const root = $('#map2d');
  if (!root) return 0;
  const bottom = root.getBoundingClientRect().bottom, shows = VIEW.hoverInfo || 'name+summary';
  let most = shows === 'name' || shows === 'off' ? 0 : FOOT2D.card || restingCard(root);
  for (const one of root.children) {
    if (one.matches('#viewport, .bar2d, .readout, .hovercard') || one.hidden) continue;
    const style = getComputedStyle(one), box = one.getBoundingClientRect();
    if (style.position !== 'absolute' || !box.height || style.display === 'none' || bottom - box.bottom > 48) continue;
    most = Math.max(most, bottom - box.top);
  }
  return most ? most + FOOT2D.gap : 0;
}
/* The card's height at rest, its kind, its address and one line of words, measured once from a copy out of sight. */
function restingCard(root) {
  const probe = h('div', {class: 'hovercard', style: {visibility: 'hidden', transition: 'none'}},
    h('div', {class: 'kind'}, 'element'), h('code', {class: 'address'}, 'a.b'), h('p', {class: 'text'}, 'A line.'));
  root.append(probe);
  const tall = probe.getBoundingClientRect().height, inset = parseFloat(getComputedStyle(probe).bottom) || 0;
  probe.remove();
  if (tall) FOOT2D.card = Math.ceil(tall + inset);
  return FOOT2D.card;
}
addEventListener('resize', () => { FOOT2D.card = 0; });  // its inset and text follow the window's size
/* The view at `scale` with its middle as near `center` as the limits let it be: along an axis where the map runs past
 * the pane, no more than MARGIN screen pixels beyond the map's edge show, and along one where it does not, the map is
 * centered; down the pane, in the part above the room kept at its foot, `foot2d`. */
/* The point `place2d` keeps in the middle of a view: its middle across, and down the middle of the part above the room
 * at its foot, so a view turned back into its center and placed again stands where it stood. */
function focus2d(view, area = area2d()) {
  const foot = Math.min(foot2d(), area.height / 3) * view.w / Math.max(1, area.width);
  return {x: view.x + view.w / 2, y: view.y + (view.h - foot) / 2};
}
function place2d(scale, center, area = area2d()) {
  const box = M.bounds, w = area.width / scale, height = area.height / scale, room = MARGIN / scale;
  const foot = Math.min(foot2d(), area.height / 3) / scale, usable = height - foot;
  const along = (at, start, size, view) => size <= view ? start + size / 2 - view / 2
    : Math.min(Math.max(at - view / 2, start - room), start + size + room - view);
  const down = box.h <= usable ? box.y + box.h / 2 - usable / 2
    : Math.min(Math.max(center.y - usable / 2, box.y - room), box.y + box.h + room + foot - height);
  return {x: along(center.x, box.x, box.w, w), y: down, w, h: height};
}
/* The camera to the mode's framing, with `center` in the middle as far as the limits allow, or the middle of the view
 * where it is going; eased, or with `now` put there at once, for a view that fades in. */
function aim2d(center = null, now = false) {
  const area = area2d(), here = M.to || M.cam;
  if (!M.svg || !M.bounds || !area.width || !area.height) return;
  const view = place2d(scale2d(area), center || (here ? focus2d(here, area) : mid2d(M.bounds)), area);
  if (now || !M.cam) setCam(view); else moveCam(view);
}
/* Where a selection is centered: a node at its middle, and a join of the whole map at the middle of its edge, where a
 * 2D figure stands at it, `spot2d`. */
function center2d(id) {
  const edge = id?.startsWith('p:') && M.base && M.svg === M.base.svg ? spot2d(M.base, id) : null;
  if (edge) return edge;
  const node = at2d(id);
  return node ? {x: node.x, y: node.y} : null;
}
/* A fit or a zoom chosen by its key, its button or a Ctrl-click: the camera eases to its framing, on the selection. */
function setFit(fit) {
  if (!FITS2D.some(([name]) => name === fit)) return;
  MODE.fit = fit;
  MODE.chosen = true;
  MODE.page = null;  // read again, in case the page's text has changed since
  showModes();
  aim2d(center2d(S.selected));
}
function setZoom(zoom) {
  if (!ZOOMS2D.some(([name]) => name === zoom)) return;
  MODE.zoom = zoom;
  MODE.chosen = true;
  showModes();
  aim2d(center2d(S.selected));
}
const stepped = (list, now) => list[(list.findIndex(([name]) => name === now) + 1) % list.length];
function stepFit() {
  const [fit, word] = stepped(FITS2D, MODE.fit);
  setFit(fit);
  note2d(word);
  saveView('web_map_fit', fit);
}
function stepZoom() {
  const [zoom, word] = stepped(ZOOMS2D, MODE.zoom);
  setZoom(zoom);
  note2d(word);
  saveView('web_map_zoom', zoom);
}
/* 1 opens the distance to be set by example: the wheel zooms, on the selection or at the pointer, until 1 again keeps
 * the height the map's text is drawn at; Escape, or ten seconds untouched, leaves it as it was. */
function setDistance() {
  if (!M.cam) return;
  if (MODE.setting) {
    MODE.distance = Math.round(MODE.setting.scale * labelSize(M.svg));
    MODE.chosen = true;
    endSetting();
    saveView('web_map_distance', MODE.distance);
    note2d('Zoom saved');
    return aim2d(center2d(S.selected));
  }
  MODE.setting = {scale: area2d().width / (M.to || M.cam).w, timer: 0};
  showModes();
  note2d('Zoom: scroll, then 1 saves', true);
  armSetting();
}
function armSetting() {
  clearTimeout(MODE.setting.timer);
  MODE.setting.timer = setTimeout(cancelSetting, 10000);
}
function endSetting() {
  clearTimeout(MODE.setting?.timer);
  MODE.setting = null;
  showModes();
}
function cancelSetting() {
  if (!MODE.setting) return false;
  endSetting();
  note2d('Zoom not changed');
  aim2d(center2d(S.selected));
  return true;
}
/* 0, and Home: the 2D map back to Fit all with the Neighbors zoom, and the large 3D map to Zoom at its farthest, the
 * name a quarter of the view's width. The distance set with 1 is kept. */
function resetZoom() {
  if (MODE.setting) endSetting();
  setFit('all');
  setZoom('neighbors');
  saveView('web_map_fit', 'all');
  saveView('web_map_zoom', 'neighbors');
  note2d('Fit all, zoom: neighbors');
  NAME.level = 1;
  setMode3d('zoom', 1);
}
/* The choice made, said at the map's top right a moment, or `held` until it is done, and then faded. */
function note2d(text, held = false) {
  let box = $('#note2d');
  if (!box) { box = h('div', {id: 'note2d', class: 'note2d', role: 'status', 'aria-live': 'polite'}); $('#map2d').append(box); }
  box.textContent = text;
  box.classList.add('on');
  clearTimeout(MODE.note);
  if (!held) MODE.note = setTimeout(() => box.classList.remove('on'), 1600);
}
/* The fit, the zoom and the distance on the 2D map's bar, each button naming what is in force. */
function showModes() {
  if (!MODE.box) return;
  MODE.box.hidden = !M.svg;
  MODE.fitBtn.querySelector('.value').textContent = FITS2D.find(([name]) => name === MODE.fit)[1];
  MODE.zoomBtn.querySelector('.value').textContent = ZOOMS2D.find(([name]) => name === MODE.zoom)[1];
  MODE.setBtn.querySelector('.value').textContent = MODE.setting ? 'Save zoom' : 'Set zoom';
  MODE.setBtn.setAttribute('aria-pressed', String(Boolean(MODE.setting)));
}
/* A node's name is its hovertext only while the map's text is drawn smaller than Small, VIEW-041: there the eye
 * cannot read it, and above it a tip would cover a map that can be read. */
function hover2d() {
  // the readout at the top of the map's window names what the pointer is on at every size, `readout`, so no node
  // carries a hover title of its own
  if (!M.svg) return;
  for (const node of M.nodes.values()) node.g.querySelector(':scope > title')?.remove();
}
/* Each edge of the whole map takes a click, which selects its join, VIEW-008: on a band one screen pixel wider than its
 * line, a copy of it with no paint in a group of their own just over the edges, `.hits2d`. They lie under the nodes, so
 * where a band crosses a node the node takes the click. */
function hits2d(edges) {
  const drawn = edges.filter(edge => edge.path);
  if (!drawn.length) return;
  const hits = document.createElementNS(SVG, 'g'), group = drawn[0].path.closest('.edgePaths') || drawn[0].path.parentNode;
  hits.setAttribute('class', 'hits2d');
  group.after(hits);
  for (const edge of drawn) {
    const hit = edge.hit = edge.path.cloneNode(false);
    for (const name of ['id', 'marker-end', 'marker-start', 'data-id', 'style']) hit.removeAttribute(name);
    hit.setAttribute('class', 'hit');
    hits.append(hit);  // its band shows the selection's edges; which edge a click takes is `edgeAt2d`'s choice
  }
}
/* Which edge a click on the map takes, in both maps alike, VIEW-008: the one nearest the pointer on the screen, within
 * EDGE_PICK.most CSS pixels, so each edge takes all the room up to where the next edge is nearer, and a node under the
 * pointer always wins. The pointer shows it first: the edge it would take is marked as the pointer moves. */
const EDGE_PICK = {most: 24, edge2d: null, node2d: null, link3d: null, frame: 0, frame3d: 0};
const segmentAway = (x, y, x1, y1, x2, y2) => {
  const dx = x2 - x1, dy = y2 - y1, length = dx * dx + dy * dy;
  const t = length ? Math.max(0, Math.min(1, ((x - x1) * dx + (y - y1) * dy) / length)) : 0;
  return Math.hypot(x - x1 - t * dx, y - y1 - t * dy);
};
/* An edge's line as points along it, in its own units, taken again only when its path changes. */
function edgePoints(edge) {
  const path = edge.path, d = path.getAttribute('d');
  if (edge.sampled === d && edge.points) return edge.points;
  const length = path.getTotalLength(), step = Math.max(2, length / 160), points = [];
  for (let at = 0; at < length; at += step) { const one = path.getPointAtLength(at); points.push(one.x, one.y); }
  const end = path.getPointAtLength(length);
  points.push(end.x, end.y);
  return Object.assign(edge, {sampled: d, points}).points;
}
function edgeAt2d(x, y) {
  if (!M.svg) return null;
  let best = null, nearest = EDGE_PICK.most;
  for (const edge of M.edges) {
    const path = edge.path;
    if (!edge.join || !path?.isConnected || path.classList.contains('reserved')) continue;
    const box = path.getBoundingClientRect();
    if (x < box.left - nearest || x > box.right + nearest || y < box.top - nearest || y > box.bottom + nearest) continue;
    const ctm = path.getScreenCTM();
    if (!ctm) continue;
    const local = new DOMPoint(x, y).matrixTransform(ctm.inverse()), scale = Math.hypot(ctm.a, ctm.b), points = edgePoints(edge);
    for (let at = 0; at + 3 < points.length; at += 2) {
      const away = segmentAway(local.x, local.y, points[at], points[at + 1], points[at + 2], points[at + 3]) * scale;
      if (away < nearest) { nearest = away; best = edge; }
    }
  }
  return best;
}
/* The 2D map's nodes on the screen with their reaches, `REACH`, measured at most once a frame. A node is a box: the
 * whole box is its own, as drawn, and around its centre it reaches half the distance to the nearest box's centre, at
 * most REACH.most, which past a small box's edge is the room between it and its neighbours, and leaves the gaps between
 * large boxes to the edges drawn there. A group's box is not one, so the nodes and edges in it come first. */
function reaches2d() {
  const now = performance.now();
  if (REACH.d2 && now - REACH.d2.at < 16) return REACH.d2.list;
  const list = [];
  for (const [key, node] of M.nodes) {
    const g = node.g;
    if (!g?.isConnected || !g.classList.contains('node') || g.classList.contains('reserved')) continue;
    const box = g.getBoundingClientRect();
    if (!box.width) continue;
    list.push({key, box, x: (box.left + box.right) / 2, y: (box.top + box.bottom) / 2, r: 0});
  }
  REACH.d2 = {at: now, list: reachOf(list)};
  return list;
}
/* The node the pointer takes on the 2D map: inside a box, that node; elsewhere, of those whose reach covers the
 * pointer, the one whose centre is nearest. Its key, or null. */
function nodeAt2d(x, y) {
  if (!M.svg) return null;
  let best = null, nearest = Infinity;
  for (const one of reaches2d()) {
    const {box} = one, inside = x >= box.left && x <= box.right && y >= box.top && y <= box.bottom;
    const middle = Math.hypot(one.x - x, one.y - y);
    if (!inside && middle > one.reach) continue;
    const rank = inside ? -1 : middle;  // inside a box it is that node's
    if (rank < nearest) { nearest = rank; best = one.key; }
  }
  return best;
}
function pickNode2d(key) {
  if (EDGE_PICK.node2d === key) return;
  M.nodes.get(EDGE_PICK.node2d)?.g.classList.remove('pick');
  EDGE_PICK.node2d = key;
  M.nodes.get(key)?.g.classList.add('pick');
  HOVER2D.on = key;
  if (key) readout('2d', readoutOf(key, '2d'));
}
function pickEdge2d(edge) {
  if (EDGE_PICK.edge2d === edge) return;
  for (const one of [EDGE_PICK.edge2d, edge]) if (one) { one.path?.classList.toggle('pick', one === edge); one.hit?.classList.toggle('pick', one === edge); }
  EDGE_PICK.edge2d = edge;
  $('#viewport').classList.toggle('picking', Boolean(edge));
  if (edge) readout('2d', edgeWords(edge.join));
  else if (!HOVER2D.on) readout('2d', null);
}
/* The 2D map's hover, as the 3D map's: a node, an agent's figure or a box inside a node said in the readout; the
 * edge under the pointer is `pickEdge2d`'s. */
const HOVER2D = {on: null};
$('#viewport').addEventListener('pointerover', event => {
  const figure = event.target.closest?.('g.agent2d'), node = event.target.closest?.('g.node');
  if (figure) {
    const found = [...ROAM2D.figures.values()].find(one => one.g === figure);
    HOVER2D.on = found ? `figure:${found.id}` : null;
    if (found) readout('2d', figureWords(found.id));
  } else if (node?.dataset.key) {
    HOVER2D.on = node.dataset.key;
    readout('2d', readoutOf(node.dataset.key, '2d'));
  }
});
$('#viewport').addEventListener('pointerout', event => {
  const from = event.target.closest?.('g.agent2d, g.node');
  if (!from || from.contains(event.relatedTarget)) return;
  HOVER2D.on = EDGE_PICK.node2d;  // a node still within reach keeps the readout, `nodeAt2d`
  if (!EDGE_PICK.edge2d && !EDGE_PICK.node2d) readout('2d', null);
});
/* All shows the whole map and leaves the selection as it is, its node and its joins still marked, so the whole map is
 * seen with what the selected node is joined to; letting go of the selection clears the marks, `deselect`. */
function unmark2D() {
  $('#map2d').classList.remove('focused');
  for (const edge of M.edges) { edge.path?.classList.remove('on'); edge.hit?.classList.remove('on'); }
  flows2d();
  for (const node of M.nodes.values()) node.g.classList.remove('sel', 'near');
}
/* A join's information flow direction, its ifd, MAP-020, as the receiver has it: it sends to the elements that serve
 * it, receives from them, or both. The 2D map's arrows and flow and the 3D map's dots go the way the information goes. */
const flowOf = join => join?.ifd === 'receives' ? ['back'] : join?.ifd === 'both' ? ['forth', 'back'] : ['forth'];
/* The arrow between a join's receiver and its providers in its title: the receiver comes first, which says who needs
 * whom, and the arrow says which way the information goes, its ifd, as the 2D map's arrowheads do: ← when the receiver
 * receives, → when it sends or nothing is recorded, as the 2D map's arrowhead points, ↔ both ways. */
const flowArrow = join => join?.ifd === 'both' ? '↔' : join?.ifd === 'receives' ? '←' : '→';
/* An edge of the 2D map runs the way its join's information goes, as `metaform map mermaid` writes it: from the
 * receiver to the element served when the receiver sends or nothing is recorded, from the element served to the
 * receiver when it receives. So the page and the export give ELK the same graph to lay out. */
const ends2d = (join, provider) => join?.ifd === 'receives' ? [provider, join.receiver] : [join.receiver, provider];
/* Mermaid draws the arrowhead at an edge's end, where the information arrives; both ways it gets one at its start. */
function pointed(edge) {
  const path = edge.path, end = path?.getAttribute('marker-end');
  if (end && edge.join?.ifd === 'both') path.setAttribute('marker-start', end.replace('pointEnd', 'pointStart'));
}
/* The selected node's joins in the 2D map carry its flow in the 3D map's looks, on the same clocks, VIEW-005 and
 * `FLOW`: a tiny white request from the receiver to the element served, the answer back as a short bright streak, the
 * way the information goes, and on a join whose receiver sends, a record card that lands with a ring. Only the
 * selected node's, so the map stays still to read and the flow says what the selection takes from where. Each edge
 * gets a group of shapes over it, moved along the edge each frame, `frame2d`, while the page is in use, as the 3D map
 * draws its flow, `FRAMES`; with reduced motion nothing moves and nothing is shown. */
const FLOW2D = {id: 0, edges: []};
// an element's own colour on the map, as the 3D map draws it, for what comes from it
const color2d = id => { const node = G?.graphData().nodes.find(one => one.id === id); return node ? colorOf(node) : css('--signal'); };
function flows2d() {
  for (const old of M.svg?.querySelectorAll('g.flows2d') || []) old.remove();
  FLOW2D.edges = [];
  const on = M.edges.filter(edge => edge.path?.classList.contains('on') && edge.join);
  if (!on.length) return;
  // a group of their own just over the edges, so the edges stay what they are
  const flows = document.createElementNS(SVG, 'g'), edges = on[0].path.closest('.edgePaths') || on[0].path.parentNode;
  flows.setAttribute('class', 'flows2d');
  edges.after(flows);
  const made = (tag, name, attributes = {}) => {
    const shape = document.createElementNS(SVG, tag);
    shape.setAttribute('class', name);
    for (const [key, value] of Object.entries(attributes)) shape.setAttribute(key, value);
    shape.style.display = 'none';
    flows.append(shape);
    return shape;
  };
  for (const edge of on) {
    FLOW2D.edges.push({edge, length: edge.path.getTotalLength(),
      // a reply's train of dots each way, in the colour of the element it comes from, `fxTrain`
      trains: [0, 1].map(way => ({color: color2d(way === 0 ? edge.provider : edge.join.receiver),
        beads: Array.from({length: 18}, () => made('circle', 'bead', {r: 3.4}))})),
      ask: made('circle', 'ask', {r: 1.9}), record: made('rect', 'record', {x: -4.5, y: -3.2, width: 9, height: 6.4, rx: 1.4}),
      ring: made('circle', 'ring', {r: 4})});
  }
  wake2d();
}
function wake2d() {
  if (!FLOW2D.id && FLOW2D.edges.length && !reduced()) FLOW2D.id = requestAnimationFrame(frame2d);
  again2d();  // the figures and the mascot on the 2D map wake with any act too
}
function frame2d(now) {
  FLOW2D.id = 0;
  const shown = FLOW2D.edges.filter(one => one.edge.path.isConnected);
  if (!shown.length || !M.svg?.getClientRects().length) return;
  // it rests as the 3D map's flow rests, once nothing was done for web_flow_seconds, until the next act
  const resting = reduced() || (FRAMES.rest !== null && performance.now() - FRAMES.active > FRAMES.idle);
  flowTick(now);
  // the flow mode, web_flow_mode: off and live draw none of it here; a change eases it in or out
  const wanted = flowModeNow() === 'selected' || flowModeNow() === 'all' ? 1 : 0, was = FLOW2D.fade ?? wanted;
  FLOW2D.fade = was + (wanted - was) * (1 - Math.exp(-Math.max(0, FLOW.clock - (FLOW2D.at ?? FLOW.clock)) * FLOW.ease));
  FLOW2D.at = FLOW.clock;
  const group = shown[0].ask.parentNode;
  if (group) group.style.opacity = FLOW2D.fade.toFixed(3);
  if (FLOW2D.fade < 0.01 && !wanted) { for (const shape of group?.children || []) shape.style.display = 'none'; return; }
  for (const one of shown) {
    const {edge, length, trains, ask, record, ring} = one, join = edge.join, receives = join.ifd === 'receives';
    const along = share => (receives ? 1 - share : share) * length;  // the edge runs the way its information goes
    const at = share => edge.path.getPointAtLength(along(Math.min(1, Math.max(0, share))));
    const put = (shape, point) => { shape.style.display = ''; shape.setAttribute('transform', `translate(${point.x} ${point.y})`); };
    for (const shape of [ask, record, ring, ...trains.flatMap(train => train.beads)]) shape.style.display = 'none';
    if (resting) continue;
    const {asks, since, amount = 7} = flowAt(join);
    if (!asks) {
      if (since < FLOW.send) { const t = since / FLOW.send; put(record, at(t * t * (3 - 2 * t))); }
      else if (since < FLOW.send + FLOW.burst) {
        const u = (since - FLOW.send) / FLOW.burst;
        put(ring, at(1));
        ring.setAttribute('r', String(4 + 14 * u));
        ring.style.opacity = String(Math.pow(1 - u, 1.5));
      }
    } else if (since < FLOW.ask) put(ask, at(since / FLOW.ask));
    else if (since < FLOW.ask + FLOW.reply) {  // the reply: a train of dots the way the data goes
      const t = (since - FLOW.ask) / FLOW.reply;
      (join.ifd === 'both' ? [true, false] : [true]).forEach((back, index) => {
        const {beads, color} = trains[index], spacing = Math.max(0.03, 3.4 * 2 * 2.3 / Math.max(1, length));
        const shown = Math.max(3, Math.min(beads.length, amount, Math.floor(0.9 / spacing) + 1)), head = t * (1 + spacing * (shown - 1));
        beads.forEach((bead, i) => {
          const s = head - spacing * i;
          if (i >= shown || s < 0 || s > 1) return;
          put(bead, at(back ? 1 - s : s));
          bead.style.fill = color;
          bead.style.opacity = String(i < shown - 3 ? 1 : 1 - (i - (shown - 4)) / 4);
        });
      });
    }
  }
  if (!resting) FLOW2D.id = requestAnimationFrame(frame2d);
}
function focus2D(id) {
  const join = id.startsWith('p:') ? joinOf(id) : null;
  const node = M.nodes.get(id) || (join ? M.nodes.get(join.provider) : null);
  if (!M.svg) return;
  if (!node) return aim2d();
  if (IN.length) {
    for (const [key, value] of M.nodes) value.g.classList.toggle('sel', key === id);
  } else {
    $('#map2d').classList.add('focused');
    for (const [key, value] of M.nodes) { value.g.classList.toggle('sel', key === id); value.g.classList.toggle('near', key !== id && S.neighbors.has(key)); }
    for (const edge of M.edges) {
      const on = join ? edge.join === join : edge.join.receiver === id || edge.provider === id;
      edge.path?.classList.toggle('on', on);
      edge.hit?.classList.toggle('on', on);  // its band a pixel wider than the line drawn for a selection
    }
  }
  flows2d();
  // The selection is centered as far as the mode's limits allow, at the zoom the mode holds: a selection never changes
  // it, VIEW-041.
  aim2d(center2d(id));
}
/* A click on the map, VIEW-008: on a node or an edge it selects it, and on the selected one it goes inside it; a
 * group's "more" node shows the next ones. Anywhere on the map, with Shift held it backs out one level, and with Ctrl
 * held, Command on macOS, where a click with Control is the system's right-click, it fits the whole map. */
function clicked2d(id, event) {
  if (modified2d(event)) return;
  if (!MEM.key && (id === S.selected || id.startsWith('m:'))) goInside(id); else select(id, true);
}
function modified2d(event) {
  if (event?.shiftKey) { levelUp(); return true; }
  if (event && (MAC ? event.metaKey : event.ctrlKey)) { setFit('all'); return true; }
  return false;
}
/* Letting go of the selection, by a click on the map's empty space or Escape, VIEW-008: its marks go from both maps,
 * the panel says nothing is selected, and nothing is selected again until the person selects, even as the map is read
 * again. */
function deselect() {
  if (!S.selected) return;
  Object.assign(S, {selected: null, cleared: true, panelFor: null, trail: [], neighbors: new Set()});
  setReach(null);
  unmark2D();
  if (G) { G.nodeColor(G.nodeColor()); meetEnds(); wake3d(); }
  noneSelected();
  aim2d();  // back to the fit
}
function noneSelected() {
  fill($('#p-object'), h('p', {class: 'empty'}, 'Nothing is selected. Click a part on either map, or press an arrow key to start from the map\'s entry.'));
}
(function wire2D() {
  const host = $('#map2d');
  // The fit, the zoom and the distance on the map's bar, VIEW-041, each a button naming what is in force, with its key.
  const button = (key, title, run) => h('button', {type: 'button', class: 'btn sm quiet', 'aria-keyshortcuts': key, title,
    onclick: event => { event.stopPropagation(); run(); }}, h('span', {class: 'value'}), h('kbd', {}, key));
  MODE.box = h('div', {class: 'modes2d', role: 'group', 'aria-label': 'How the 2D map is framed'},
    MODE.fitBtn = button('2', 'The fit: the whole map, its width or its height (2)', stepFit),
    MODE.zoomBtn = button('3', 'On a selection: its neighbors, the distance set with 1, or no zoom (3)', stepZoom),
    MODE.setBtn = button('1', 'Set the zoom distance: the wheel, then 1 again keeps it (1)', setDistance));
  PEEK.two.prepend(MODE.box);
  showModes();
  $('#backBtn').onclick = event => { event.stopPropagation(); step(-1); };
  $('#forwardBtn').onclick = event => { event.stopPropagation(); step(1); };
  // A drag moves the view within the mode's limits, VIEW-041, and is not a click on what it started on.
  let drag = null, dragged = false;
  host.addEventListener('pointerdown', event => {
    dragged = false;
    // the bar across the top is controls and the grip that moves the side column, never a place a pan starts
    if (event.target.closest('button, a, .bar2d') || !M.cam) return;
    drag = {x: event.clientX, y: event.clientY, cam: {...M.cam}, moving: false};
  });
  host.addEventListener('pointermove', event => {
    if (!drag) return;
    if (!drag.moving) {  // captured only once it is a drag, so a click still reaches the node under it
      if (Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 4) return;
      stopCam();
      drag.cam = {...M.cam};
      drag.moving = true; host.setPointerCapture(event.pointerId);
    }
    const area = area2d(), scale = area.width / drag.cam.w, at = focus2d(drag.cam, area);
    setCam(place2d(scale, {x: at.x - (event.clientX - drag.x) / scale, y: at.y - (event.clientY - drag.y) / scale}, area));
  });
  host.addEventListener('pointerup', () => { dragged = Boolean(drag?.moving); drag = null; });
  // The edge a click would take, marked as the pointer moves, once a frame; a node under the pointer takes it instead.
  host.addEventListener('pointermove', event => {
    if (drag?.moving || EDGE_PICK.frame) return;
    const {clientX: x, clientY: y, target} = event;
    EDGE_PICK.frame = requestAnimationFrame(() => {
      EDGE_PICK.frame = 0;
      // the node nearest the pointer within reach, then the nearest edge: what a click will take; a figure keeps its own
      const off = !M.svg || target.closest?.('.bar2d, button, g.agent2d') || !target.closest?.('#viewport');
      const key = off ? null : nodeAt2d(x, y);
      pickNode2d(key);
      pickEdge2d(off || key ? null : edgeAt2d(x, y));
      $('#viewport').classList.toggle('picking', Boolean(key || EDGE_PICK.edge2d));
    });
  });
  host.addEventListener('pointerleave', () => { pickNode2d(null); pickEdge2d(null); });
  // A click takes the nearest node within reach, then the nearest edge, before a group behind them does.
  host.addEventListener('click', event => {
    if (dragged || !M.svg || event.target.closest('.bar2d, button, g.agent2d') || !event.target.closest('#viewport')) return;
    const key = nodeAt2d(event.clientX, event.clientY), edge = key ? null : edgeAt2d(event.clientX, event.clientY);
    if (!key && !edge) return;
    event.stopPropagation();
    clicked2d(key || 'p:' + edge.join.id, event);
  }, true);
  // A click on the map where there is no node and no edge lets go of the selection, VIEW-008.
  host.addEventListener('click', event => {
    if (dragged) { dragged = false; return; }
    if (!M.svg || !event.target.closest('#viewport') || modified2d(event)) return;
    deselect();
  });
  // The wheel, VIEW-041: with the whole map in view it does nothing; where the map runs past the pane it scrolls,
  // along the axis that runs past, or with both, up and down, and across by a sideways scroll or with Shift held, as a
  // page scrolls; while the distance is being set it zooms, on the selection or at the pointer. All at once, as a
  // wheel does, within the map's limits.
  host.addEventListener('wheel', event => {
    if (!M.cam || !M.bounds) return;
    event.preventDefault();
    stopCam();
    const pixels = delta => event.deltaMode === 1 ? delta * 16 : event.deltaMode === 2 ? delta * 400 : delta;
    const area = area2d(), c = M.cam, scale = area.width / c.w;
    if (MODE.setting) {
      // flat steps on a mouse wheel, its own acceleration on a trackpad, toward the selection or the pointer
      const f = Math.exp(Math.max(-200, Math.min(200, pixels(event.deltaY))) * 0.0015);
      const least = scaleFor('all', area) / 2, most = 64 / labelSize(M.svg);
      const zoom = Math.min(most, Math.max(least, scale / f)), w = area.width / zoom, height = area.height / zoom;
      const px = (event.clientX - area.left) / area.width, py = (event.clientY - area.top) / area.height;
      MODE.setting.scale = zoom;
      armSetting();
      const on = S.selected ? center2d(S.selected) : null;
      return setCam(place2d(zoom, on || focus2d({x: c.x + (c.w - w) * px, y: c.y + (c.h - height) * py, w, h: height}, area), area));
    }
    const across = M.bounds.w > c.w, down = M.bounds.h > c.h;
    if (!across && !down) return;
    let dx = pixels(event.deltaX), dy = pixels(event.deltaY);
    if (event.shiftKey && !dx) [dx, dy] = [dy, 0];
    if (!down) [dx, dy] = [dx || dy, 0];
    else if (!across) [dx, dy] = [0, dy || dx];
    const at = focus2d(c, area);
    setCam(place2d(scale, {x: at.x + dx / scale, y: at.y + dy / scale}, area));
  }, {passive: false});
  new ResizeObserver(() => aim2d()).observe($('#viewport'));  // a fit refits as the pane changes size, VIEW-041
})();
/* Back and forward step through the nodes selected, as a browser does; a new selection drops the steps forward. */
async function step(by) {
  if (MEM.key) { if (by < 0) leaveMemories(); return; }  // back from a memory network is back to the map, VIEW-031
  const to = S.at + by;
  if (to < 0 || to >= S.history.length) return;
  S.at = to;
  const entry = S.history[to];
  if (!samePath(entry.path, IN)) {
    if (!IN.length && M.base) M.base.cam = {...M.cam};
    IN.length = 0;
    IN.push(...entry.path.map(level => ({...level, more: {}, things: new Map()})));
    if (IN.length) await drawInside(); else showBase();
  }
  select(entry.id, true, false, true);
}
function showSteps() {
  $('#backBtn').disabled = !MEM.key && S.at <= 0;
  $('#forwardBtn').disabled = Boolean(MEM.key) || S.at >= S.history.length - 1;
}

/* The keys walk the join tree, Down goes deeper, to the providers of the node's joins and then to
 * the nodes inside it; Up goes back to the parent; Left and Right move between the nodes connected to the parent.
 * Enter goes inside a node; Escape or Shift+Enter backs out. F fits. */
function across(keys) {  // in their order across the 2D map
  const at = key => M.nodes.get(key) || {x: Infinity, y: Infinity};
  return [...keys].sort((a, b) => M.vertical ? at(a).x - at(b).x || at(a).y - at(b).y : at(a).y - at(b).y || at(a).x - at(b).x);
}
/* Down goes down an edge to the node drawn nearest under the selected one, across the map's other axis, so with seven
 * below it lands near the middle and not at the far end of the row; the nodes inside a node are gone to when no edge
 * leads down. A row not drawn yet gives its middle node. */
function below(key) {
  const row = childrenOf(key);
  const here = M.nodes.get(key), axis = M.vertical ? 'x' : 'y';
  const drawn = row.filter(child => M.nodes.has(child));
  if (!here || !drawn.length) return row[Math.floor((row.length - 1) / 2)];
  return drawn.reduce((best, child) =>
    Math.abs(M.nodes.get(child)[axis] - here[axis]) < Math.abs(M.nodes.get(best)[axis] - here[axis]) ? child : best);
}
/* Past either end of a parent's row, Left and Right go on to the nodes of the next parent over on the parent's level,
 * the first of them going right and the last going left, and past the last parent of the level round to the first, so
 * every node of a level is reached by Left and Right alone. A level is the children of every node on the level above,
 * in their order across the map, starting from the roots. Returns the node and the parent it is reached under. */
/* The node drawn nearest beside a node on its row of the 2D map, that way. */
function besideDrawn(key, by) {
  const here = M.nodes.get(key);
  if (!here) return null;
  const depth = M.vertical ? 'y' : 'x', across = M.vertical ? 'x' : 'y';
  const onward = [...M.nodes.entries()].filter(([id, node]) => id !== key
    && Math.abs(node[depth] - here[depth]) < 2 && (node[across] - here[across]) * by > 0);
  if (!onward.length) return null;
  return onward.reduce((best, one) => Math.abs(one[1][across] - here[across]) < Math.abs(best[1][across] - here[across]) ? one : best)[0];
}
function besideOnLevel(key, parent, by) {
  if (!parent) return null;  // the roots are one row already
  let level = roots(), seen = new Set(level);
  while (level.length && !level.includes(parent)) {
    level = level.flatMap(node => childrenOf(node)).filter(node => !seen.has(node) && seen.add(node));
  }
  if (!level.length) return null;
  const row = level.flatMap(node => childrenOf(node).map(next => ({next, parent: node})))
    .filter((one, at, all) => all.findIndex(other => other.next === one.next) === at);
  const at = row.findIndex(one => one.next === key && one.parent === parent);
  const from = at >= 0 ? at : row.findIndex(one => one.next === key);
  if (from < 0 || row.length < 2) return null;
  return row[(from + by + row.length) % row.length];
}
function childrenOf(key) {
  if (key.startsWith('p:')) return across((joinOf(key)?.providers || []).filter(id => S.elements.has(id)));
  return across(new Set(S.joins.filter(join => join.receiver === key).flatMap(join => join.providers)
    .filter(id => S.elements.has(id))));
}
function parentOf(key) {
  if (key.startsWith('p:')) return joinOf(key)?.receiver || null;
  return across(new Set(S.joins.filter(join => join.providers.includes(key) && S.elements.has(join.receiver)).map(join => join.receiver)))[0] || null;
}
function roots() {  // the nodes nothing receives from, CQUs first; then any part of the map they do not reach
  const top = [...S.elements.keys()].filter(key => !parentOf(key));
  const ordered = [...across(top.filter(key => S.elements.get(key).element.role === 'CQU')), ...across(top.filter(key => S.elements.get(key).element.role !== 'CQU'))];
  const reached = new Set(ordered), queue = [...ordered];
  while (queue.length) for (const next of childrenOf(queue.shift())) if (!reached.has(next)) { reached.add(next); queue.push(next); }
  for (const key of across([...S.elements.keys()].filter(key => !reached.has(key)))) {
    if (reached.has(key)) continue;
    ordered.push(key); reached.add(key);
    const more = [key];
    while (more.length) for (const next of childrenOf(more.shift())) if (!reached.has(next)) { reached.add(next); more.push(next); }
  }
  return ordered;
}
function goInside(key) { if (!MEM.key) enter(key); }  // a memory network has no inside of its own
/* Out one level, by Shift+Enter, a Shift-click, or Escape with nothing selected, VIEW-008: from a memory network or a
 * node's own graph to the level before; on the whole map there is no level to leave. */
function levelUp() {
  if (MEM.key) return leaveMemories();
  if (IN.length) return goTo(IN.length - 1);
}
/* Which keys the maps take. A key typed into a text is a letter of it and never a shortcut. While a menu, a popover or
 * a modal window is open, or the focus is in any window, the maps' keys rest: the key belongs to what is open, VIEW-030
 * and VIEW-041. Enter and Space on a button or a link press it, and the arrows on a tab, a menu item or a choice move
 * between those; every other control leaves the keys to the maps. Escape that reaches here has closed nothing. */
const ARROWS_OWN = 'select,[role=tab],[role=tablist],[role=menuitem],[role=option],[role=listbox],[role=radio],[role=radiogroup],[role=slider],input[type=range]';
const PRESSABLE = 'button,a[href],summary,[role=button],[role=tab],[role=menuitem],[role=option],[role=switch],[role=checkbox],[role=radio],input[type=checkbox],input[type=radio]';
function mapKeys(event) {
  const target = event.target instanceof Element ? event.target : document.body;
  if (event.defaultPrevented || event.isComposing || event.ctrlKey || event.metaKey || event.altKey) return false;
  if (target.closest('select, input, textarea, .CodeMirror, [contenteditable="true"]') && !target.matches('input[type=checkbox],input[type=radio]')) return false;
  if (overlayHolds(target)) return false;
  const onMap = target.closest('#map2d, #stage') && !target.closest('.bar2d, .bar3d');
  if ((event.key === 'Enter' || event.key === ' ') && !onMap && target.closest(PRESSABLE)) return false;
  if (event.key.startsWith('Arrow') && target.closest(ARROWS_OWN)) return false;
  return true;
}
/* The digits act on the map in the large area, one scheme from the whole map in to close up, VIEW-041 and VIEW-005:
 * 1 the whole map, 2 Width and 3 Height, 4, 5 and 6 Small, Medium and Large, or far, medium and close on the selection
 * in 3D, 0 Free; 7, 8 and 9 the 2D map's direction. Home is 1. The small area takes none of them. The bar peeks with
 * the new choice checked. */
function largeKey(key) {
  // the 2D map's keys, wherever it is: 1 its distance, 2 its fit, 3 its zoom, 7 to 9 its direction
  if (key === '1') return setDistance();
  if (key === '2') return stepFit();
  if (key === '3') return stepZoom();
  if (key === '0' || key === 'Home') return resetZoom();
  if (DIRECTION_KEYS[key]) { chooseDirection(DIRECTION_KEYS[key]); peek('key'); return; }
  const level = {4: 1, 5: 2, 6: 3}[key];  // the large 3D map's zoom, its name a quarter, a half or three quarters wide
  if (level) { setMode3d('zoom', level); peek('key'); }
}
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
  {group: 'Zoom', keys: ['1'], what: 'Set the 2D zoom distance', match: ['1'], run: largeKey},
  {group: 'Zoom', keys: ['2'], what: '2D fit: all, width, height', match: ['2'], run: largeKey},
  {group: 'Zoom', keys: ['3'], what: '2D zoom: neighbors, distance, off', match: ['3'], run: largeKey},
  {group: 'Zoom', keys: ['4', '5', '6'], what: '3D zoom: 25%, 50%, 75%', match: ['4', '5', '6'], run: largeKey},
  {group: 'Zoom', keys: ['0'], what: 'Reset zoom', match: ['0', 'Home'], run: largeKey},
  {group: 'Zoom', keys: ['F'], what: 'Fit once (3D)', match: ['f', 'F'],
    run: () => { if (G && !small3d()) { fit3d(); peek('key'); } }},
  {group: 'Zoom', keys: ['Z'], what: 'Node zoom on/off', match: ['z', 'Z'], run: () => toggleNodeZoom()},
  {group: 'Zoom', keys: ['7', '8', '9'], what: '2D direction', match: ['7', '8', '9'], run: largeKey},
  {group: 'Looks', keys: ['L'], what: 'Layout: Organic or Flat', match: ['l', 'L'],
    run: () => choosePhysics(PHYS.name === 'flat' ? 'organic' : 'flat')},
  {group: 'Looks', keys: ['D'], what: 'Flow: Off, Selection, All, Live', match: ['d', 'D'], run: () => stepFlow()},
  {group: 'Looks', keys: ['U'], what: 'Space theme on/off', match: ['u', 'U'],  // the space theme or the last plain one
    run: () => setTheme(document.documentElement.dataset.theme === 'space' ? PLAIN.last : 'space')},
  {group: 'Chat', keys: ['C'], what: 'Open or hide chat', match: ['c', 'C'],
    run: () => ($('#dock').className.startsWith('open') && !chatDocked() && !dockGoingAway() ? putChatAway() : dockState('open'))},
  {group: 'Chat', keys: ['Enter'], what: 'Send'},
  {group: 'Chat', keys: ['Shift', 'Enter'], what: 'New line'},
  {group: 'Chat', keys: [MAC ? '⌘' : 'Ctrl', '.'], what: 'Interrupt the agent'},
  {group: 'Chat', keys: [MAC ? '⌥' : 'Ctrl', 'Space'], what: 'Talk'},
];
const KEY_RUN = new Map(KEYS.filter(entry => entry.run).flatMap(entry => entry.match.map(key => [key, entry])));
/* The reference, drawn from `KEYS`, centered over the page: its tabs, the everyday keys first, then the developer's,
 * then the looks and the zoom; each group a card of what a key does with its keys beside it; and a search that keeps
 * the keys whose words match, across every tab. A tab with no keys is not offered. */
const HELP_TABS = [['Shortcuts', ['Anywhere', 'Maps', 'Chat', 'Tools']], ['Dev keys', ['Developer']],
  ['Visuals', ['Zoom', 'Looks']]];
const HELP = {tab: 'Shortcuts'};
function openHelp() {
  $('#settingsbox').hidden = true;
  const find = $('#help .keyfind'), box = $('#help .keys'), tabs = $('#help .helptabs');
  const draw = () => {
    const words = find.value.trim().toLowerCase();
    // the toolbar's tools with a key, as the modules declare them and the workspace runs them, in the same reference
    const tools = WS.active ? WS.toolKeys().map(tool => ({group: 'Tools', keys: tool.shortcut.split('+'), what: `${tool.title}: ${tool.description}`})) : [];
    const all = [...KEYS, ...tools], offered = HELP_TABS.filter(([, groups]) => all.some(entry => groups.includes(entry.group)));
    if (!offered.some(([name]) => name === HELP.tab)) HELP.tab = offered[0]?.[0];
    fill(tabs, offered.map(([name]) => h('button', {type: 'button', role: 'tab', 'aria-selected': String(!words && name === HELP.tab),
      onclick: () => { HELP.tab = name; find.value = ''; draw(); }}, name)));
    const shown = words ? null : HELP_TABS.find(([name]) => name === HELP.tab)?.[1];
    const rows = all.filter(entry => words ? `${entry.group} ${entry.keys.join(' ')} ${entry.what}`.toLowerCase().includes(words)
      : shown?.includes(entry.group));
    const groups = [...new Set(rows.map(entry => entry.group))];
    fill(box, groups.length ? groups.map(group => h('section', {class: 'keycard'}, h('h3', {}, group),
      rows.filter(entry => entry.group === group).map(entry => h('div', {class: 'keyrow'}, h('span', {class: 'what'}, entry.what),
        h('span', {class: 'chips'}, entry.keys.map(key => /^(Click|click)$/.test(key) ? h('span', {}, key) : h('kbd', {}, key)))))))
      : h('p', {class: 'empty'}, 'No key does that.'));
  };
  find.oninput = draw;
  draw();
  $('#help').hidden = false;
  find.focus();
}
document.addEventListener('keydown', event => {
  if (!mapKeys(event)) return;
  // The keys of the key table, `KEYS`, each run by its entry, so the reference `?` opens says what each does.
  const entry = KEY_RUN.get(event.key);
  if (entry) { event.preventDefault(); entry.run(event.key); return; }
  // Escape lets go of the selection, and with nothing selected backs out one level; Shift+Enter always backs out.
  if (event.key === 'Escape') { event.preventDefault(); if (cancelSetting()) return; if (S.selected) deselect(); else levelUp(); return; }
  if (event.key === 'Enter' && event.shiftKey) { event.preventDefault(); levelUp(); return; }
  if (!S.selected) {  // with nothing selected, an arrow starts from the level's own node, or on the map its entry
    const start = event.key.startsWith('Arrow') ? (IN.length ? IN.at(-1).key : MEM.key || entryOf()) : null;
    if (start) { event.preventDefault(); select(start, true, true); }
    return;
  }
  const here = S.selected;
  if (event.key === 'Enter') { event.preventDefault(); goInside(here); return; }
  if ((IN.length || MEM.key) && event.key.startsWith('Arrow')) {  // inside a node or a memory network the arrows go through its graph in order
    event.preventDefault();
    const order = across(M.nodes.keys()), at = order.indexOf(here);
    const by = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : -1;
    if (order.length) select(order[at < 0 ? 0 : (at + by + order.length) % order.length], true, true);
    return;
  }
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
});

/* ---------- selection: both views move together; the long text goes in the panel ----------
 * A selection made as the map is loaded or read again, again, leaves open the tab of the panel the person has open,
 * such as the prompt being edited. */
function select(id, fly, keepTrail = false, stepping = false, again = false) {
  if (!id) return;
  const drawn = selectNow(id, fly, keepTrail, stepping, again), moved = S.panelFor !== id;
  if (moved && S.selected === id) { S.panelFor = id; $('#p-object').scrollTop = 0; }  // a new object is read from its top
  // A person who chose a node from elsewhere on the page goes on with the keys on the map; a text being written, an
  // open window and the maps themselves keep the focus.
  const active = document.activeElement;
  const keeps = active && active !== document.body && shown(active)
    && (active.closest('input, textarea, select, [contenteditable="true"], .CodeMirror, #map2d, #stage') || overlayHolds(active));
  if (fly && !again && S.selected === id && !keeps) largeView().focus({preventScroll: true});
  return drawn;
}
function selectNow(id, fly, keepTrail, stepping, again) {
  const join = id.startsWith('p:') ? joinOf(id) : null;
  const entity = Boolean(MEM.network?.entities.includes(id));  // a node of the memory network open, VIEW-031
  const known = join || S.elements.has(id) || entity,
    thing = IN.at(-1)?.things?.get(id) || S.items.get(id) || memoryThing(id);
  if (!known && !thing) return;
  if (!keepTrail) S.trail = [];
  const path = IN.map(({key, label}) => ({key, label})), last = S.history[S.at];
  if (!stepping && !MEM.key && !(last && last.id === id && samePath(last.path, path))) {
    S.history = [...S.history.slice(0, S.at + 1), {id, path}]; S.at = S.history.length - 1;
  }
  showSteps();
  S.selected = id;
  S.cleared = false;
  window.metaform.onSelect?.(addressOf(id));  // the map view in an AI tool tells its agent, MCP-037
  setReach(id);
  if (!known) { S.neighbors = new Set(); focus2D(id); if (!again) showTab('object'); renderThing(thing); return; }
  S.neighbors = MEM.key ? new Set([id, ...(MEM.network?.relations || []).flatMap(relation =>
      relation.from === id ? [relation.to] : relation.to === id ? [relation.from] : [])])
    : join ? new Set([join.receiver, ...join.providers])
    : new Set([id, ...S.joins.filter(item => item.receiver === id).flatMap(item => item.providers),
      ...S.joins.filter(item => item.providers.includes(id)).map(item => item.receiver)]);
  if (G) {
    G.nodeColor(G.nodeColor());
    const node = G.graphData().nodes.find(item => item.id === id);
    if (fly && node) follow3d(id);
  }
  focus2D(id);
  // The brief stays on view while the person walks the map from it; any other tab gives way to the object.
  const briefing = tabNow() === 'brief';
  // in the workspace every pane stays where the person left it, and those shown follow the selection
  if (WS.on) wsSelected();
  else {
    if (WS.active) WS.refresh(true);  // the page as written with the toolbar: its tools follow the selection too
    if (!again) showTab(briefing ? 'brief' : 'object');
    else if (briefing) renderBrief();
  }
  // The panel's reads are returned, so a load waits for them before it says it is loaded.
  return MEM.key ? renderMemories(id) : join ? renderJoin(join) : renderObject(id);
}

function refsOf(refs) {
  return refs && refs.length ? h('div', {class: 'refs'}, refs.map(ref => h('span', {}, h('span', {class: 'k'}, ref.key), ref.value))) : null;
}
/* The work records of the selected object, MAP-046: each with its condition, note and task, held and reviewed,
 * and its resolution once done; read from /api/work for the node and written into the panel's work box. */
function workPill(condition) { return h('span', {class: `pill work-${condition}`}, condition); }
/* A question at the node, MAP-050 and VIEW-021, as the question form wrote it: the question, then each part the agent
 * filled under its heading, each with Create ticket so the person can turn it into work. Open, it takes a typed answer
 * or a click on a choice; answered, the answer stays beside it. */
const FORM_PARTS = [['#1 Specifications reviewed:', 'Investigate why the specifications did not settle this'],
  ['#2 Why this is not a configuration option:', 'Review whether this should be a configuration option'],
  ['#3 Unexplained "Rich said":', 'Decipher this, or delete it and reconstruct a proper, clear specification']];
function formParts(text) {
  const lines = (text || '').split('\n'), parts = [];
  let question = [], current = null;
  for (const line of lines) {
    const part = FORM_PARTS.find(([heading]) => line.trim() === heading);
    if (part) { current = {heading: part[0], task: part[1], lines: []}; parts.push(current); continue; }
    (current ? current.lines : question).push(line);
  }
  return {question: question.join('\n').trim(), parts: parts.map(part => ({...part, text: part.lines.join('\n').trim()}))};
}
function asked(record, metaform = S.base, full = false) {
  const answer = h('textarea', {class: 'answer', placeholder: 'Type an answer or a message'});
  const written = text => wrote('/api/answer', {id: record.id, answer: text, metaform});
  const send = h('button', {class: 'btn sm primary answer', type: 'button', onclick: async () => {
    if (!answer.value.trim()) return;
    send.disabled = true;
    if (!await written(answer.value)) send.disabled = false;
  }}, 'Send');
  // The answers the agent suggests, the one it recommends first: one click answers; the box takes anything else.
  const suggested = record.closed ? [] : (record.suggestions || []).map(String);
  const choices = suggested.length ? h('div', {class: 'choices'},
    suggested.map((text, index) => h('button', {class: index ? 'suggestion' : 'suggestion recommended', type: 'button', onclick: async event => {
      const buttons = [...event.target.parentNode.children];
      for (const button of buttons) button.disabled = true;
      if (!await written(text)) for (const button of buttons) button.disabled = false;
    }}, text))) : null;
  const {question, parts} = formParts(record.text);
  const node = nodeOf(record);
  const sections = parts.map(part => h('div', {class: 'form-part'},
    h('div', {class: 'heading'}, part.heading),
    h('p', {class: 'said'}, ...linked(part.text)),
    h('button', {class: 'btn sm create-ticket', type: 'button', title: 'Write a ticket from this part, at the node of the question', onclick: () => {
      if ($('#qa')) $('#qa').hidden = true;
      giveWork(node, `${part.task}: ${part.text}\n\nFrom question: ${question}`);
    }}, 'Create ticket')));
  const reader = full ? null : h('button', {class: 'btn sm quiet read-full', type: 'button', title: 'Read the whole question in a large window', onclick: () => {
    fill($('#qa .body'), asked(record, metaform, true));
    $('#qa').hidden = false;
  }}, 'Read in full');
  return h('div', {class: full ? 'item work question-form full' : 'item work question-form'},
    h('div', {class: 'pills'}, workPill('question'), h('span', {class: 'pill'}, record.closed ? 'answered' : 'open'),
      record.by ? h('span', {class: 'pill'}, record.by) : null, reader),
    h('p', {class: 'asked'}, ...linked(question)),
    ...sections,
    record.closed ? h('p', {class: 'obs'}, `Answer: ${record.answer || ''}`) : [choices, h('div', {class: 'typed'}, answer, send)],
    // Answered by mistake: Reopen clears the answer and the question waits again with its suggestions, MAP-050.
    record.closed ? h('button', {class: 'btn sm reopen', type: 'button', onclick: async event => {
      event.target.disabled = true;
      if (!await wrote('/api/reopen', {id: record.id, metaform})) event.target.disabled = false;
    }}, 'Reopen') : null);
}
$('#qa .close').onclick = () => { $('#qa').hidden = true; };
overlay($('#qa'), {kind: 'dialog', focus: 'textarea.answer'});
overlay($('#mergeAsk'), {kind: 'dialog', focus: '.yes'});
overlay($('#confirm'), {kind: 'dialog'});
/* The review-or-merge flow, VIEW-044: Review. while done work waits; a click takes it over for good, offers an agent's
 * help, and the help comes in a support window at the lower right. */
const MERGE = {rows: [], chat: null, since: 0};
async function renderMerges() {
  if (!S.project || FRAMED) return;
  try { MERGE.rows = (await read('merges')).merges || []; } catch { MERGE.rows = []; }
  noticeAttention();  // a merge waiting for review: the mascot tells the person, `ATTN`
  const at = seconds => new Date(seconds * 1000).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
  fill($('#reviewNotice'), MERGE.rows.map(row => {
    const ticket = (B.tickets || []).find(one => one.id === row.work_id);
    return h('div', {class: 'notice'}, h('b', {}, 'Review.'),
      h('span', {}, ` ${ticket ? (ticket.task || ticket.note || '').slice(0, 80) : row.branch} · merges by itself at ${at(row.deadline)}`),
      h('button', {class: 'btn sm primary', type: 'button', onclick: event => takeReview(row.work_id, event.target)}, 'Review'));
  }));
  $('#reviewNotice').hidden = !MERGE.rows.length;
}
async function takeReview(workId, button) {
  button.disabled = true;
  if (!await wrote('/api/merge-review', {work_id: workId})) { button.disabled = false; return; }
  await renderMerges();
  $('#mergeAsk .yes').onclick = async () => {
    $('#mergeAsk').hidden = true;
    openHelpdesk(workId, 'an agent', 'Waiting for the next available agent.', null, 'merge');
    if (!await wrote('/api/merge-assist', {work_id: workId})) drawHelpdesk('The agent could not be started.');
  };
  $('#mergeAsk .no').onclick = () => { $('#mergeAsk').hidden = true; toast('The merge is yours to handle; its countdown is off.'); };
  OVERLAY.known.get($('#mergeAsk')).close = () => $('#mergeAsk .no').click();
  $('#mergeAsk').hidden = false;
}
/* The chat dock: a thin sliver at the lower right that lifts when the pointer comes near and opens, on a click, into
 * the page's one place for conversations with agents. Every thread is an ACP session, kept by its session id, and a
 * tab of its own: an agent dispatched on a ticket, the intake, the person's system agent, a chat the person started, a
 * sentinel, each with a chip saying where it comes from. A thread shows the agent's words, its thinking, its tool calls
 * and its permission requests in order, with its plan and its settings above; Call reaches the person's system agent,
 * the +1 outside the agent limit, and /list and /chat <n> talk with an agent at work, VIEW-039 and VIEW-045. Bubbles
 * alternate: the person's on the right, the agent's on the left. A file attached with the paperclip is saved in the
 * project and the agent is told where. The dock rests in the corner, docks at either side of the page, or floats where
 * its head is dragged. */
const DOCK = {target: null, session: null, label: '', since: 0, notes: [], list: [], files: [], mine: null, waiting: '',
  calling: null, chats: [], chat: null, pinned: true,  // chats: every open thread, one a tab; chat: the one on view
  queue: [], unread: false, heard: new Set()};  // queue: messages written before the agent was there, sent in order once it is
/* When the page first saw each message of a thread. A thread's lines carry no time of their own, so those already
 * there when its session was first read have none, and each one after that has the moment it arrived. */
const SEEN = {at: new Map(), sessions: new Set()};
const clockOf = (when, day = false) => {
  const date = new Date(when);
  if (isNaN(date)) return '';
  const today = new Date().toDateString() === date.toDateString();
  return date.toLocaleString([], {hour: '2-digit', minute: '2-digit', ...(day && !today ? {month: 'short', day: 'numeric'} : {})});
};
const STANDBY = 'Please stand by while we contact an agent for you.';
const DOCKMOTION = {anim: null, dir: null};  // the chat going into its tab, 'away', or coming out of it, 'back'
const dockGoingAway = () => Boolean(DOCKMOTION.anim) && (DOCKMOTION.dir === 'away') === (DOCKMOTION.anim.playbackRate > 0);
/* A body for the chat's agent on the map, web_embody: offered once per chat, inline at the top of its thread and never
 * as a window, at a pause after web_embody_turns turns or web_embody_minutes minutes, whichever comes first; always
 * gives it the person's last choice, or the mascot to the system agent; never gives none. The choice folds into the
 * chat's head as a small avatar of the character, which, like B, opens the choice again. The figure is the flow's:
 * `window.metaform.characters()` lists the characters and `window.metaform.embody(workId, glyph)` gives one; until
 * those exist nothing is offered and nothing breaks. */
const EMBODY = {offered: new Set(), given: new Set(), since: new Map(), open: null, last: null, stops: []};
try { Object.assign(EMBODY, {last: localStorage.getItem('metaform.embodied') || null}); } catch { /* storage can be blocked */ }
const embodyHooks = () => ['embody', 'characters', 'bodies'].every(name => typeof window.metaform?.[name] === 'function');
const hooked = (name, ...given) => { try { return window.metaform[name](...given); } catch { return null; } };
/* Only a conversation's agent takes a body this way, the system agent or a chat the person started; an agent at work
 * on a ticket walks as its own figure already. */
const embodiable = chat => Boolean(chat && ['system', 'conversation'].includes(chat.source) && !isIntake(chat.target));
const bodyFor = work => (hooked('bodies') || []).find(one => one.work === work) || null;
function characterList(work) {
  const system = DOCK.chat?.source === 'system', mine = bodyFor(work)?.character;
  // the person's own character, web_mascot, first for their system agent; with none set, none is put first
  const list = (hooked('characters') || []).filter(one => one?.name && (!one.mascot || system)).map(one => ({...one,
    src: `/page/agent-glyphs/${one.name}.svg`, free: one.free !== false || one.name === mine || (one.mascot && system),
    preferred: Boolean(one.preferred && system)}));
  return [...list.filter(one => one.preferred), ...list.filter(one => !one.preferred)];
}
function stopPreviews() { for (const stop of EMBODY.stops.splice(0)) { try { stop(); } catch { /* already still */ } } }
/* Give the chat's agent the character chosen; the flow says no when it is taken, and the chat says why. */
function embodyAs(work, glyph, quiet = false) {
  if (!work || !glyph || !embodyHooks()) return false;
  const done = hooked('embody', work, glyph);
  if (!done || done.error) { if (!quiet) dockNote(done?.error || 'That body could not be given.'); return false; }
  EMBODY.last = glyph;
  try { localStorage.setItem('metaform.embodied', glyph); } catch { /* storage can be blocked */ }
  EMBODY.given.add(work);
  if (EMBODY.open === work) { EMBODY.open = null; stopPreviews(); }
  if (!quiet) dockNote(done.mascot ? `Your system agent walks the map as the ${glyph} now, your mascot while you talk.` : `It walks the map as the ${glyph} now.`);
  else drawHelpdesk();
  return true;
}
/* web_embody: offer asks once per conversation, in its thread, after web_embody_turns turns or web_embody_minutes
 * minutes, whichever comes first, and only at a pause, as a turn ends or a ticket closes, never while it works;
 * always gives each conversation the person's last choice, or the mascot to the system agent; never offers nothing.
 * The person asks at any time with the avatar in the head, the head's menu or B. */
function embodyOffer(work, session, lines, busy) {
  paintAvatar(work);
  if (!work || !session || !embodyHooks() || VIEW.embody === 'never' || !embodiable(DOCK.chat)) return;
  if (!EMBODY.since.has(work)) EMBODY.since.set(work, Date.now());
  const body = bodyFor(work), chosen = Boolean(body?.by);
  if (VIEW.embody === 'always') {
    if (chosen || EMBODY.given.has(work)) return;
    EMBODY.given.add(work);
    const list = characterList(work), free = name => list.find(one => one.name === name && one.free);
    const glyph = [EMBODY.last, list.find(one => one.preferred)?.name, list.find(one => one.free && !one.mascot)?.name].find(free);
    if (glyph) embodyAs(work, glyph, true);
    return;
  }
  if (chosen || EMBODY.offered.has(work)) return;
  const turns = lines.filter(line => line.kind === 'turn').length;
  const minutes = (Date.now() - EMBODY.since.get(work)) / 60000;
  const due = turns >= (VIEW.embodyTurns ?? 8) || minutes >= (VIEW.embodyMinutes ?? 20);
  const ticket = ticketOf(work);
  const pause = !busy && session.state === 'running' && session.activity === 'idle' || Boolean(ticket?.done);
  if (due && (pause || (VIEW.embodyTurns ?? 8) === 0)) { EMBODY.offered.add(work); EMBODY.open = work; }
}
/* Open the choice now, as the person asked: in the thread, where the offer stands. */
function askEmbody() {
  const work = DOCK.target;
  if (!embodyHooks()) return toast('Bodies on the map are not ready on this page yet.');
  if (!work || !embodiable(DOCK.chat)) return toast('Open a chat with your system agent, or one you started, first.');
  EMBODY.open = EMBODY.open === work ? null : work;
  EMBODY.offered.add(work);
  if (!EMBODY.open) stopPreviews();
  if (!$('#dock').className.startsWith('open')) dockState('open');
  drawHelpdesk().then(() => { if (EMBODY.open) followLog(true); });
}
/* The offer in the thread, a row of the conversation: each character moving in its own way on a small canvas, with
 * its name and temper, those taken by another agent unavailable, and Not now. */
function embodyRows(work) {
  if (!work || EMBODY.open !== work || !embodyHooks()) { if (EMBODY.stops.length) stopPreviews(); return []; }
  const body = bodyFor(work), list = characterList(work);
  return [{key: `embody:${work}`, text: `${body?.character || ''}:${list.map(one => `${one.name}${one.free ? '' : '-'}`).join(',')}`, make: () => {
    stopPreviews();
    const choices = list.map(one => {
      const canvas = h('canvas', {width: '96', height: '96', 'aria-hidden': 'true'});
      const stop = typeof one.preview === 'function' ? (() => { try { return one.preview(canvas); } catch { return null; } })() : null;
      if (typeof stop === 'function') EMBODY.stops.push(stop);
      const on = body?.by && body.character === one.name;
      return h('button', {type: 'button', class: `character${on ? ' on' : ''}`, disabled: !one.free,
        title: `${one.name}: ${one.temperament || ''}${one.moves ? `, it ${one.moves}s` : ''}${one.free ? '' : ' · at work already'}`,
        'aria-pressed': String(Boolean(on)), onclick: () => embodyAs(work, one.name)},
      canvas, h('span', {class: 'name'}, one.name), h('small', {}, one.preferred ? 'your character' : one.temperament || ''));
    });
    return h('div', {class: 'embody', role: 'group', 'aria-label': 'Give this agent a body on the map'},
      h('p', {class: 'ask'}, h('b', {}, body?.by ? 'Change its body?' : `Give ${DOCK.label || 'this agent'} a body on the map?`),
        h('small', {}, 'It walks the map in that shape as it works. Change it at any time with its avatar or B.')),
      h('div', {class: 'choices'}, choices),
      h('div', {class: 'acts'}, h('button', {type: 'button', class: 'btn sm quiet notnow',
        onclick: () => { EMBODY.open = null; stopPreviews(); drawHelpdesk(); }}, 'Not now')));
  }}];
}
/* The head's avatar: the agent's body when it has one, else the letter; a click opens the choice. */
function paintAvatar(work) {
  const avatar = $('#helpdesk .head .avatar');
  if (!avatar) return;
  if (!avatar.dataset.letter) avatar.dataset.letter = avatar.textContent;
  const hooks = embodyHooks(), can = hooks && work && embodiable(DOCK.chat);
  const body = can ? bodyFor(work) : null, glyph = body && (body.by || body.drawn) ? body.character : null;
  if (avatar.dataset.glyph !== (glyph || '')) {
    avatar.dataset.glyph = glyph || '';
    fill(avatar, glyph ? h('img', {src: `/page/agent-glyphs/${glyph}.svg`, alt: ''}) : avatar.dataset.letter);
  }
  avatar.classList.toggle('embodied', Boolean(glyph));
  avatar.classList.toggle('choosable', Boolean(can));
  avatar.setAttribute('role', can ? 'button' : 'img');
  avatar.setAttribute('tabindex', can ? '0' : '-1');
  avatar.setAttribute('aria-hidden', String(!can));
  avatar.setAttribute('aria-label', can ? (glyph ? `Its body on the map: the ${glyph}. Change it` : 'Give this agent a body on the map') : '');
  avatar.title = can ? `${glyph ? `Its body on the map: the ${glyph}. Change it` : 'Give this agent a body on the map'} (B)` : '';
  avatar.onclick = can ? () => askEmbody() : null;
  avatar.onkeydown = can ? event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); askEmbody(); } } : null;
}
/* Kept for the flow's own callers: the avatar and the offer are drawn with the chat. */
function drawEmbody() { if ($('#helpdesk') && !$('#helpdesk').hidden) drawHelpdesk(); }
/* Where a thread comes from, said on its chip. The system agent and a chat the person started are the person's own;
 * a session the page did not start is known only as an agent at work, an intake or a sentinel. */
const SOURCES = {agent: 'Agent at work', intake: 'Intake', system: 'Your system agent', conversation: 'Your chat',
  sentinel: 'Sentinel', merge: 'Merge help'};
const sourceOf = workId => isIntake(workId) ? 'intake' : workId === DOCK.mine ? 'system'
  : (D.proposals || {})[workId] ? 'sentinel' : 'agent';
const sourceChip = source => h('span', {class: 'src', 'data-source': source}, SOURCES[source] || SOURCES.agent);
function dockState(state) {
  const box = $('#helpdesk'), was = !box.hidden, open = state === 'open' || state === 'open big';
  const anim = DOCKMOTION.anim;
  if (open && dockGoingAway()) { reverseDock(); if (state === $('#dock').className) return; }  // called back on its way
  if (!open && anim) {  // put away at once, as another project is chosen: no motion left running
    Object.assign(DOCKMOTION, {anim: null, dir: null});
    anim.cancel();
    $('#dockTab').classList.remove('launch');
    Object.assign(box.style, {transformOrigin: '', willChange: ''});
  }
  const from = open && !was && !chatDocked() ? launcherRect() : null;  // measured while the tab still shows
  $('#dock').className = state;
  box.hidden = !open;
  dockLayout();
  if (open && !was) {  // opened, even empty, it says what it is and how to start, and grows out of its tab
    if ($('#dock').dataset.place === 'float' && box.style.left) setBox(box.getBoundingClientRect(), false);  // the window may be smaller now
    DOCK.unread = false;
    drawDockTab();
    drawHelpdesk();
    if (from) growFrom(from);
  }
  if (!open) stopPreviews();
}
function dockNote(text) { DOCK.notes.push({at: Date.now(), text}); drawHelpdesk(); }
/* session: the session the thread is with, when it is known. A thread stays with its session, so a later session of
 * the same ticket opens a thread of its own and never swaps the conversation; with none known yet, the thread waits
 * for the ticket's running session and then stays with that one. `source` says where it comes from, `focus` that the
 * person chose it, so its agent and its part are shown on the maps. */
function openHelpdesk(workId, label = 'an agent', waiting = 'Waiting for the next available agent.', session = null,
  source = null, {focus = false} = {}) {
  const same = DOCK.chats.filter(one => one.target === workId);
  const live = one => !one.session || D.sessions.some(row => row.session_id === one.session && row.state === 'running');
  let chat = session ? DOCK.chats.find(one => one.session === session) || same.find(one => !one.session)
    : same.filter(live).at(-1);
  const kind = source || chat?.source || sourceOf(workId);
  if (chat) Object.assign(chat, {label, waiting, source: kind, ...(session ? {session} : {})});
  else DOCK.chats.push(chat = {target: workId, session, label, waiting, mine: DOCK.mine === workId, since: Date.now(),
    source: kind});
  showChat(chat, {focus});
  if (!$('#dock').className.startsWith('open')) dockState('open');
}
/* Several threads are open at once, each a tab; the one on view is the dock's target, and switching keeps each
 * conversation and its session. A thread the person chooses shows its agent and its part on the maps. */
function showChat(chat, {focus = false} = {}) {
  const moved = DOCK.chat !== chat;
  Object.assign(DOCK, {chat, target: chat.target, session: chat.session, label: chat.label, waiting: chat.waiting,
    since: chat.since});
  if (moved) { DOCK.pinned = true; DOCK.child = null; }  // another thread opens on its own agent, not a subagent
  MERGE.chat = chat.target;
  $('#helpdesk .call').textContent = 'Dismiss';
  drawTabs();
  drawHelpdesk();
  if (focus) focusThread(chat);
}
/* A thread chosen shows where its agent works: its figure stands out among the agents in 3D, and its ticket's part is
 * selected, so both maps move to it. The system agent's held ticket and the intake have no part to show. */
function focusThread(chat) {
  ROAM.focus = chat.target;
  wake3d();
  const ticket = chat.source === 'system' || isIntake(chat.target) ? null : ticketOf(chat.target);
  const key = ticket ? ticketNode(ticket) : null;
  if (key && (S.elements.has(key) || joinOf(key))) select(key, true);
}
/* A sentinel's proposals in its chat, VIEW-045: each with its grounds, its disruption and how much of the map its
 * reach reserves, its benefit and trade-off, a link to its own explanation when it made one, Show on the map, which
 * paints its reach white, and Choose, which tells the sentinel. */
function drawProposals() {
  const box = $('#helpdesk .proposals'), given = (D.proposals || {})[DOCK.target] || [];
  box.hidden = !given.length;
  const total = S.elements.size;
  fill(box, given.map((one, index) => {
    const reach = idsAt(one.reach), on = reach.length && reach.every(id => INUSE.preview.has(id));
    const link = /^https?:\/\//.test(one.view || '') ? h('a', {href: one.view, target: '_blank', rel: 'noopener noreferrer'},
      'Its explanation') : null;
    return h('div', {class: 'proposal'},
      h('b', {}, `${index + 1}. ${one.title}`),
      one.grounds ? h('p', {}, h('small', {}, 'Grounds '), one.grounds) : null,
      h('p', {class: 'disruption'}, h('small', {}, 'Disruption '), `Reserves ${reach.length} of ${total} parts`,
        one.disruption ? ` · ${one.disruption}` : ''),
      one.benefit ? h('p', {}, h('small', {}, 'Benefit '), one.benefit) : null,
      one.tradeoff ? h('p', {}, h('small', {}, 'Trade-off '), one.tradeoff) : null,
      h('div', {class: 'acts'}, link,
        h('button', {type: 'button', class: on ? 'reach on' : 'reach', disabled: !reach.length, onclick: () => {
          INUSE.preview = new Set(on ? [] : reach);
          paintInUse(); drawProposals();
        }}, on ? 'Hide from the map' : 'Show on the map'),
        h('button', {type: 'button', class: 'choose', onclick: async () => {
          if (await wrote('/api/dispatch-message', {work_id: DOCK.target, session: DOCK.session, text: `I choose proposal ${index + 1}: ${one.title}.`})) {
            INUSE.preview = new Set(); paintInUse(); drawHelpdesk();
          }
        }}, 'Choose')));
  }));
}
function drawTabs() {
  const tabs = $('#helpdesk .tabs');
  tabs.hidden = DOCK.chats.length < 2;
  fill(tabs, DOCK.chats.map(chat => h('button', {class: chat === DOCK.chat ? 'tab on' : 'tab', role: 'tab',
    'aria-selected': String(chat === DOCK.chat), 'data-source': chat.source, 'data-session': chat.session || '',
    title: `${SOURCES[chat.source] || SOURCES.agent}: ${chat.label}`, onclick: () => showChat(chat, {focus: true})},
    h('i', {class: 'srcdot', 'aria-hidden': 'true'}), chat.label.replace(/^the /, ''))));
}
/* The thread's own bar: the chip of where it comes from, its agent's glyph and its task, Show on map, Stop while its
 * session runs, and Continue once it has ended, which starts an agent that reads the thread first. */
function drawThreadBar(session) {
  const bar = $('#helpdesk .threadbar'), chat = DOCK.chat, target = DOCK.target;
  bar.hidden = !target || !chat;
  if (bar.hidden) return;
  const ticket = isIntake(target) || chat.source === 'system' ? null : ticketOf(target);
  const icon = bar.querySelector('.icon'), withGlyph = chat.source === 'agent' && Boolean(ticket);
  icon.hidden = !withGlyph;
  if (withGlyph && icon.getAttribute('src') !== glyphOf(target)) { icon.src = glyphOf(target); icon.alt = glyphFor(target); }
  // its status is said once, quietly, in the chat's head, `drawHelpdesk`, with the reason a login or a lost runner gives
  fill(bar.querySelector('.source'), sourceChip(chat.source));
  const task = ticket ? ticket.task || ticket.note || '' : isIntake(target) ? `The intake of ${S.project}: it records the map as it reads the project.` : '';
  const said = bar.querySelector('.task');
  if (said.textContent !== task) { said.classList.remove('open'); said.textContent = task; }
  said.title = task ? 'Click to show all of the task, and again to fold it' : '';
  const key = ticket ? ticketNode(ticket) : null;
  bar.querySelector('.locate').hidden = !(key && (S.elements.has(key) || joinOf(key)));
  const running = session?.state === 'running', ended = Boolean(session) && !running;
  // a session an editor runs through metaform dispatch serve ends in that editor, BASE-062: no Stop, where it runs
  const inEditor = running && DOCK.state?.editor === true;
  let where = bar.querySelector('.where');
  if (!where) {
    where = h('span', {class: 'where meta', title: 'This session runs in your editor: answer it and end it there.'}, 'In your editor');
    bar.querySelector('.stop').before(where);
  }
  where.hidden = !inEditor;
  bar.querySelector('.stop').hidden = !running || inEditor;
  bar.querySelector('.stop').disabled = false;
  bar.querySelector('.again').hidden = !ended || isIntake(target);
  // Cancel, beside Stop: the ticket closed as cancelled, asked first, never a completion
  let cancel = bar.querySelector('.cancel');
  if (!cancel) {
    cancel = h('button', {class: 'btn sm quiet cancel', type: 'button', title: 'Cancel this ticket: its agent stops and the ticket is closed as cancelled, not completed',
      onclick: async () => { const one = ticketOf(DOCK.target); if (one) await cancelTicket(one, cancel); }}, 'Cancel ticket…');
    bar.querySelector('.stop').after(cancel);
  }
  cancel.hidden = !ticket || Boolean(ticket.done) || chat.source !== 'agent';
  // the person's own chat says whom it is with in the head, and Dismiss ends it: no chip, no Stop, and no bar at all
  // when nothing else is left to show in it
  const own = ['system', 'conversation'].includes(chat.source);
  bar.querySelector('.source').hidden = own;
  if (own) bar.querySelector('.stop').hidden = true;
  bar.hidden = own && !task && [...bar.querySelectorAll('button')].every(one => one.hidden);
}
$('#helpdesk .threadbar .task').onclick = event => event.currentTarget.classList.toggle('open');
$('#helpdesk .threadbar .locate').onclick = () => DOCK.chat && focusThread(DOCK.chat);
$('#helpdesk .threadbar .stop').onclick = async event => {
  const button = event.currentTarget, work = DOCK.target;
  if (isIntake(work)) return stopIntake();
  button.disabled = true;
  if (await wrote('/api/dispatch-stop', {work_id: work})) { toast('The agent was stopped.'); await renderAgents(); drawHelpdesk(); }
  else button.disabled = false;
};
$('#helpdesk .threadbar .again').onclick = () => {
  const chat = DOCK.chat;
  if (chat?.session) talkAbout({session: `${chat.target}:${chat.session}`}, chat.label);
};
/* The thread keeps its newest line in view while the person reads its end: it is pinned there until they scroll up. */
$('#helpdesk .log').addEventListener('scroll', () => {
  const log = $('#helpdesk .log');
  DOCK.pinned = log.scrollTop + log.clientHeight >= log.scrollHeight - 24;
  if (DOCK.pinned) $('#helpdesk .latest').hidden = true;
});
new ResizeObserver(() => { const log = $('#helpdesk .log'); if (DOCK.pinned) log.scrollTop = log.scrollHeight; })
  .observe($('#helpdesk .log'));
/* The subagents of the session on view, P016: each a child session with its own thread, opened in place and back to
 * its parent, so the person follows the parent and every child it started from one chat. */
function drawSubagents() {
  let box = $('#helpdesk .subagents');
  if (!box) { box = h('div', {class: 'subagents', role: 'group', 'aria-label': 'Subagents of this session'}); $('#helpdesk .sessionbar').after(box); }
  const kids = DOCK.subagents || [];
  box.hidden = !kids.length;
  if (!kids.length) return fill(box);
  const open = DOCK.child;
  fill(box, h('span', {class: 'eyebrow'}, `Subagents · ${kids.length}`),
    open ? h('button', {class: 'btn sm quiet', type: 'button', title: 'Back to the thread of the agent that started it',
      onclick: () => { DOCK.child = null; drawHelpdesk(); }}, h('i', {class: 'i i-back', 'aria-hidden': 'true'}), 'Parent') : null,
    kids.map(kid => h('button', {class: `btn sm${kid.session_id === open ? ' primary' : ''}`, type: 'button', 'aria-pressed': String(kid.session_id === open),
      title: [kid.description || kid.prompt || '', `Session ${kid.session_id}`].filter(Boolean).join(' · '),
      onclick: () => { DOCK.child = kid.session_id === open ? null : kid.session_id; drawHelpdesk(); }},
    kid.name || kid.title || kid.agent || 'Subagent', statusChip(kid.state ? sessionStatus({...kid, work_id: DOCK.target}) : null))));
}
/* What the ticket on view has spent today, as dispatch spend reads it against the budgets, M01; read again at most every
 * few seconds while the chat is drawn. */
const SPEND = {work: null, at: 0, data: null};
async function drawSpend(work) {
  let box = $('#helpdesk .spend');
  if (!box) { box = h('div', {class: 'spend', role: 'status'}); $('#helpdesk .sessionbar').after(box); }
  // a ticket's agent only: the person's own chat holds a ticket of its own that nobody reads as work
  if (!work || isIntake(work) || ['system', 'conversation'].includes(DOCK.chat?.source)) { box.hidden = true; return; }
  if (SPEND.work !== work || Date.now() - SPEND.at > 5000) {
    SPEND.work = work; SPEND.at = Date.now();
    try { SPEND.data = await read('dispatch-spend', {id: work}); } catch { SPEND.data = null; }
  }
  const ticket = SPEND.data?.ticket;
  box.hidden = !ticket;
  if (!ticket || work !== DOCK.target) return;
  const budgets = ticket.budgets || {};
  const tokens = `${countOf(ticket.tokens || 0)} tokens${budgets.ticket ? ` of ${countOf(budgets.ticket)}` : ''}`;
  const cost = ticket.cost !== null && ticket.cost !== undefined && ticket.currency
    ? ` · ${ticket.currency === 'USD' ? '$' : `${ticket.currency} `}${Number(ticket.cost).toFixed(2)}` : '';
  const blind = (ticket.unmetered?.tokens || []).length ? ' · some sessions report no usage' : '';
  fill(box, h('span', {class: 'eyebrow'}, 'Spent on this ticket'), ` ${tokens}${cost}${blind}`);
  box.title = SPEND.data.measure || '';
}
/* One status for a ticket and its agent, as data/status.py names it for every surface, with the reason the person
 * needs: a cancelled ticket is never shown as completed, a login only the person can give is not an ordinary wait,
 * and a runner that is gone is not an agent at work. {state, reason, words, why}. */
function sessionStatus(session, signals = D.signals || []) {
  if (!session) return null;
  const agent = agentName(session.agent), how = String(session.how || '');
  const login = signals.some(one => one.signal === 'login-needed' && one.active !== false
    && (one.session_id === session.session_id || (!one.session_id && one.work_id === session.work_id)));
  if (login || /needs a login/.test(how)) {
    return {state: 'input_required', reason: 'login', words: 'Needs a login',
      why: `${agent} needs a login, which only you can give: metaform dispatch login ${session.agent || ''}`.trim()};
  }
  if (session.state === 'running') {
    if (session.waiting_on === 'permission') return {state: 'input_required', reason: 'permission', words: 'Needs your permission', why: 'Its request is in the thread, with the agent\'s own choices.'};
    if (session.waiting_on === 'question') return {state: 'input_required', reason: 'question', words: 'Needs your answer', why: 'Its question is in the thread.'};
    if (session.activity === 'working') return {state: 'running', reason: 'working', words: 'Working', why: `${agent} is working a turn.`};
    return {state: 'running', reason: 'idle', words: 'Ready', why: `${agent}'s turn has ended; it reads your next message.`};
  }
  if (/runner is no longer|no longer listening|another session|runner of another/.test(how)) {
    return {state: 'failed', reason: 'dead', words: 'Runner gone', why: `Its runner stopped: ${how}. The ticket goes back to the board for another agent.`};
  }
  if (/ticket is done/.test(how)) return {state: 'completed', reason: 'done', words: 'Ended', why: 'Its ticket is done.'};
  return {state: 'submitted', reason: 'ended', words: 'Ended', why: how ? `It ended: ${how}.` : 'Its session ended.'};
}
function ticketStatus(ticket) {
  if (!ticket) return null;
  if (ticket.done) {
    const outcome = ticket.outcome || 'completed';
    return {state: outcome, reason: outcome, words: {completed: 'Completed', cancelled: 'Cancelled', failed: 'Failed'}[outcome] || outcome,
      why: ticket.resolution || (outcome === 'cancelled' ? 'Cancelled by the person, not completed.' : '')};
  }
  const session = D.sessions.filter(one => one.work_id === ticket.id).at(-1);
  return session ? sessionStatus(session) : null;
}
const statusChip = status => status ? h('span', {class: `statechip ${status.state} ${status.reason || ''}`, title: status.why || status.words,
  'aria-label': `${status.words}${status.why ? `: ${status.why}` : ''}`}, status.words) : null;
/* Cancel a ticket, the person's own: asked first with an optional reason; dispatch cancel stops its agent's turn with
 * session/cancel as the person's own stop, so nothing retries it, and closes the ticket as cancelled, never completed. */
async function cancelTicket(ticket, button = null) {
  const reason = h('input', {type: 'text', class: 'reason', placeholder: 'Why (optional), kept as its resolution',
    'aria-label': 'Why it is cancelled', autocomplete: 'off'});
  const sure = await confirmAct({title: 'Cancel this ticket?', verb: 'Cancel ticket', cancel: 'Keep it',
    text: [ticket.taken ? 'The agent working it is stopped, and nothing retries it.' : 'No agent has taken it.', reason],
    lost: ['The ticket stays on the board only in Done, marked cancelled, not completed.']});
  if (!sure) return false;
  if (button) button.disabled = true;
  const done = await wrote('/api/dispatch-cancel', {work_id: ticket.id, reason: reason.value.trim()});
  if (done) { toast('Ticket cancelled.'); await renderAgents(); if (!$('#board').hidden) await renderBoard(); }
  else if (button) button.disabled = false;
  return Boolean(done);
}
function chatActivity(session) {
  if (!session) return {label: 'Connecting', busy: false, interruptible: false};
  if (session.state !== 'running') return {label: 'Ended', busy: false, interruptible: false};
  const busy = session.activity === 'working' || session.activity === 'waiting';
  const label = session.interrupting ? 'Interrupting'
    : session.activity === 'waiting' && session.waiting_on === 'question' ? 'Waiting for your answer'
    : ({working: 'Busy', waiting: 'Waiting for permission', idle: 'Ready'}[session.activity] || 'Status unavailable');
  const note = session.interrupting ? 'Interrupting the current task.'
    : session.activity === 'working' ? 'Agent is working on a task. A message is read when its current step ends; Interrupt stops the step.'
    : session.activity === 'waiting' && session.waiting_on === 'question' ? 'Waiting for your answer: its question is in the thread.'
    : session.activity === 'waiting' ? 'Waiting for your permission: its request is in the thread, with the agent\'s own choices.' : '';
  return {label, note, busy, interruptible: busy && !session.interrupting};
}
async function interruptChat(work, session, button) {
  button.disabled = true;
  const result = await wrote('/api/dispatch-interrupt', {work_id: work, session});
  if (result) toast(result.requested ? 'Interruption requested.' : 'The agent has no active turn.');
  await renderAgents();
  if (DOCK.target) await drawHelpdesk();
}
/* The chat on view, as ACP gives it: its settings and usage in the session bar, its plan as a checklist, and its
 * thread, the conversation with the agent's tool calls and permission requests in it. With no chat on view, what
 * waits for the person's permission elsewhere is listed, each with Open. */
async function drawHelpdesk(trouble) {
  let lines = [], session = null, state = null;
  const target = DOCK.target, openedSession = DOCK.session, chat = DOCK.chat;
  if (target) {
    try {
      const found = await read('dispatch-sessions', {id: target});
      if (DOCK.target !== target || DOCK.session !== openedSession) return;  // the chat moved on while this was read
      const sessions = found.sessions || [];
      session = DOCK.session ? sessions.find(one => one.session_id === DOCK.session)
        : sessions.filter(one => one.state === 'running').at(-1);
      // a thread waiting for its agent whose start failed takes that session, so it says why instead of waiting on
      let failed = null;
      if (!session && !DOCK.session && chat) {
        failed = sessions.filter(one => one.state !== 'running' && /^it (failed|did not start)/.test(one.how || '')
          && Date.parse(one.started || '') >= chat.since - 5000).at(-1) || null;
        session = failed;
      }
      if (session) {
        // a waiting thread that finds its session already open in another tab gives way to that one
        const other = DOCK.chats.find(one => one !== chat && one.session === session.session_id);
        if (other && chat && !chat.session) {
          DOCK.chats = DOCK.chats.filter(one => one !== chat);
          return showChat(other);
        }
        DOCK.session = session.session_id;
        if (chat) chat.session = session.session_id;
        if (chat && session.state === 'running') chat.starting = 0;  // reached: it reads what waits for it
        state = (found.states || {})[session.session_id] || null;
        // the system agent is known by what its session is about, however it was started: by the page, the phone or
        // the command line. A conversation about a node hangs on the same held ticket and stays the person's chat
        if (chat && state?.about === 'system' && chat.source !== 'system') {
          Object.assign(chat, {source: 'system', label: 'your system agent'});
          DOCK.label = chat.label;
          drawTabs();
        }
        if (failed) startFailed(`${agentName(failed.agent)} did not start: ${String(failed.how).replace(/^it (failed|did not start):?\s*/, '')}`);
      }
      lines = session ? (found.lines || []).filter(line => line.session_id === session.session_id) : [];
      // the subagents this session started, each a child thread of its own; one opened shows its own lines
      DOCK.subagents = session ? (found.subagents || []).filter(one => one.parent === session.session_id) : [];
      const child = DOCK.child && DOCK.subagents.find(one => one.session_id === DOCK.child);
      if (child) lines = child.lines || [];
      else DOCK.child = null;
    } catch (error) { trouble = error.message; }
  } else DOCK.subagents = [];
  drawSubagents();
  drawSpend(target);
  DOCK.state = state;
  DOCK.agent = session?.agent || null;
  DOCK.live = session?.state === 'running';
  drawThreadBar(session);
  drawAsked(target, session, lines);
  mascotHeard(target, lines);  // the system agent's answer to the mascot, said in its bubble too
  drawProposals();
  drawSession($('#helpdesk .sessionbar'), {work: target, session, state});
  drawPlan($('#helpdesk .planbox'), target ? state?.plan : null);
  const activity = chatActivity(session);
  const waiting = DOCK.target && !session;
  const busy = DOCK.target && activity.busy && session?.activity !== 'waiting';
  embodyOffer(target, session, lines, busy);  // a body for this chat's agent on the map, offered at a pause
  // One quiet status in the head, on the line that says whom the chat is with: a login only the person gives and a
  // lost runner said as such, else what the agent is doing; its dot takes the state's color.
  const told = session ? sessionStatus(session) : null;
  const special = told && ['login', 'dead'].includes(told.reason);
  const connecting = Boolean(DOCK.calling) || (DOCK.target && !session);
  const status = $('#helpdesk .status');
  status.textContent = special ? told.words : session ? activity.label : connecting ? 'Connecting' : '';
  status.title = special ? told.why : session ? activity.note || activity.label : connecting ? DOCK.waiting || STANDBY : '';
  status.hidden = !status.textContent;
  $('#helpdesk .head').dataset.state = special ? told.reason : connecting ? 'connecting' : !session ? 'none'
    : session.state !== 'running' ? 'ended' : session.activity === 'waiting' ? 'asks' : busy ? 'working' : 'ready';
  $('#helpdesk').classList.toggle('asks', Boolean(session && session.activity === 'waiting'));
  $('#helpdesk .interrupt').disabled = !DOCK.target || !activity.interruptible;
  $('#helpdesk .interrupt').hidden = !DOCK.target || !(activity.interruptible || session?.interrupting);
  $('#helpdesk .with').textContent = DOCK.target ? `With ${DOCK.label}` : 'Online';
  // whom the chat is with is its title; the line under it then says only what it is doing
  const named = DOCK.target ? String(DOCK.label || 'an agent').replace(/^the /, '') : '';
  $('#helpdesk .who .title').textContent = named ? named[0].toUpperCase() + named.slice(1) : 'Metaform Support';
  $('#helpdesk .with').classList.toggle('visually-hidden', Boolean(DOCK.target || DOCK.calling) && !status.hidden);
  const system = (key, text) => ({key, text, make: () => h('div', {class: 'system'}, text)});
  const log = $('#helpdesk .log');
  // with nothing on view, the chat says what it is and how to start, once, as an empty conversation does
  const intro = DOCK.target || DOCK.calling || DOCK.queue.length ? [] : [{key: 'intro', text: summonAgent() || '',
    make: () => h('div', {class: 'empty'}, h('b', {}, 'Metaform Support'),
      h('p', {}, 'Write a message and press Enter: your system agent starts and reads it. Type / for the chat\'s commands.'),
      h('p', {class: 'hint'}, h('kbd', {}, 'C'), ' opens and puts it away · ', h('kbd', {}, '?'), ' every key'))}];
  // the conversation's start, with its agent and when, above its first line
  const begun = session ? [{key: `start:${session.session_id}`, text: session.started || '', make: () => h('div', {class: 'system begun'},
    `${agentName(session.agent)}${session.started ? ` · ${clockOf(session.started, true)}` : ''}`)}] : [];
  // with no chat on view, each agent waiting for the person's permission, so the dock's count leads somewhere
  const asking = DOCK.target ? [] : (D.asking || []).map(one => ({key: `asks:${one.work_id}:${one.request}`, text: `${one.work_id}\n${one.tool}`,
    make: () => h('div', {class: 'system asking'}, one.signal === 'question-waiting'
      ? `${agentName(one.agent)} on ${workPart(one.work_id)} asks: ${one.question || 'a question'}`
      : `${agentName(one.agent)} on ${workPart(one.work_id)} asks to ${one.tool || 'use a tool'}.`,
      h('button', {class: 'btn sm primary', type: 'button', onclick: () => isIntake(one.work_id) ? openIntakeChat(one.work_id, one.session_id)
        : agentAt(one.work_id, one.session_id)}, 'Open'))}));
  // the agent at work, said as a quiet typing row where its next words will come, its fuller note on hover
  const doing = waiting || connecting ? DOCK.waiting || STANDBY : `${agentName(session?.agent)} is working`;
  const typing = waiting || busy || (DOCK.calling && !DOCK.target) ? [{key: 'waiting', text: doing, make: () => h('div',
    {class: 'waiting typingrow', role: 'status', title: activity.note || ''},
    h('span', {class: 'typing', 'aria-hidden': 'true'}, h('i'), h('i'), h('i')), h('span', {class: 'said'}, doing))}] : [];
  const changed = keyedFill(log, [
    ...intro,
    ...asking,
    ...begun,
    ...DOCK.notes.filter(note => note.at >= DOCK.since - 1).map((note, index) => system(`note:${note.at}:${index}`, note.text)),
    ...threadRows(lines, {work: target, agent: session?.agent}),
    ...queuedRows(),
    ...embodyRows(target),
    ...galleryRows(),
    ...typing,
    ...(trouble ? [system('trouble', trouble)] : [])]);
  if (changed) followLog();
  if (changed && $('#helpdesk').hidden && lines.some(line => line.kind === 'agent_message_chunk')) markUnread();
  deliverQueued(session);  // what was written while the agent was being reached, sent once it is there
  chatAway(session, changed);
}
/* The thread follows its newest line while the person reads its end; scrolled up to read, it stays put and a quiet
 * "New messages" button below says something came, which a click, or Alt+End, goes to. */
function followLog(force = false) {
  const log = $('#helpdesk .log');
  if (force) DOCK.pinned = true;
  const latest = $('#helpdesk .latest');
  if (DOCK.pinned) { log.scrollTop = log.scrollHeight; latest.hidden = true; return; }
  latest.style.bottom = `${$('#helpdesk').getBoundingClientRect().bottom - log.getBoundingClientRect().bottom + 10}px`;  // just above the box
  latest.hidden = false;
}
$('#helpdesk .latest').onclick = () => { followLog(true); $('#helpdesk .say').focus({preventScroll: true}); };
/* What came while the chat was put away: a dot on its tab, cleared as it opens. */
function markUnread() { DOCK.unread = true; drawDockTab(); }
/* The chat puts itself away 15 seconds after its agent is gone, its session ended, stopped or the thread dismissed:
 * it eases away and leaves no gap, and its threads are kept, so opening it again shows the conversation. The count
 * waits while the person types in it, has the focus in it or the pointer over it; a line arriving or the agent back,
 * a resume, stops it. The minus in its head, Escape inside it and C put it away at any time. Docked in a pane of the
 * workspace it stays, as a pane does. */
const CHAT_AWAY = {timer: 0, for: null, had: false, wait: 15000};
function chatAway(session, changed = false) {
  const open = $('#dock').className.startsWith('open') && !chatDocked();
  if (session?.state === 'running') CHAT_AWAY.had = true;
  const gone = open && CHAT_AWAY.had && (session ? session.state !== 'running' : !DOCK.target);
  if (!gone || changed) { clearTimeout(CHAT_AWAY.timer); CHAT_AWAY.timer = 0; CHAT_AWAY.for = null; if (!gone) return; }
  const key = session?.session_id || 'none';
  if (CHAT_AWAY.for === key && CHAT_AWAY.timer) return;
  CHAT_AWAY.for = key;
  clearTimeout(CHAT_AWAY.timer);
  CHAT_AWAY.timer = setTimeout(awayNow, CHAT_AWAY.wait);
}
function awayNow() {
  const box = $('#helpdesk');
  if (box.contains(document.activeElement) || box.matches(':hover') || $('#helpdesk .say')?.value.trim()) {
    CHAT_AWAY.timer = setTimeout(awayNow, CHAT_AWAY.wait);
    return;
  }
  CHAT_AWAY.timer = 0;
  CHAT_AWAY.had = false;
  putChatAway();
}
/* Put away and opened again, the chat shrinks and fades into its tab and grows back out of it along the same path:
 * only a transform, a translation and a scale about the tab's middle, and its opacity, so its own size and place,
 * as moved and sized, are exactly what they were. Away leaves on the leaving curve, back arrives on the arriving one,
 * each about 260 to 340 ms by the way it travels; one interrupted turns back from where it is. The tab answers with
 * a small pulse as the chat lands in it. Under reduced motion only the opacity changes. The minus, Escape, C and the
 * put-away after an agent leaves all go this way, as a chat docked at a side does. */
function launcherRect() {
  const dock = $('#dock');
  dock.classList.add('measure');  // the tab, laid out where it rests but not shown, to be measured
  const rect = $('#dockTab').getBoundingClientRect();
  dock.classList.remove('measure');
  return rect;
}
function towardsTab(panel, tab) {
  const sx = Math.max(0.02, tab.width / panel.width), sy = Math.max(0.02, tab.height / panel.height);
  const ox = tab.left + tab.width / 2 - panel.left, oy = tab.top + tab.height / 2 - panel.top;  // the tab's middle
  return {transform: `translate(${(ox - panel.width / 2) * sx}px, ${(oy - panel.height / 2) * sy}px) scale(${sx}, ${sy})`,
    origin: `${ox}px ${oy}px`, travel: Math.hypot(ox - panel.width / 2, oy - panel.height / 2)};
}
const dockCurve = name => `cubic-bezier(${EASE[name].join(',')})`;
function moveDock(dir, tab) {
  const box = $('#helpdesk'), panel = box.getBoundingClientRect(), path = towardsTab(panel, tab);
  const still = reduced(), duration = still ? 140 : Math.round(Math.min(340, 260 + path.travel * 0.06));
  const shut = still ? {opacity: 0} : {transform: path.transform, opacity: 0.12};
  const full = still ? {opacity: 1} : {transform: 'none', opacity: 1};
  DOCKMOTION.anim?.cancel();
  // on its way out the focus leaves it, so C, or a click on the page, can call it back before it lands
  if (dir === 'away' && box.contains(document.activeElement)) document.activeElement.blur();
  Object.assign(box.style, {transformOrigin: path.origin, willChange: still ? 'opacity' : 'transform, opacity'});
  const anim = box.animate(dir === 'away' ? [full, shut] : [shut, full],
    {duration, easing: dockCurve(dir === 'away' ? 'leave' : 'arrive'), fill: 'both'});
  Object.assign(DOCKMOTION, {anim, dir});
  $('#dockTab').classList.toggle('launch', dir === 'back');  // the tab, not the dock, whose class is its state
  anim.onfinish = () => {
    if (DOCKMOTION.anim !== anim) return;
    const away = (DOCKMOTION.dir === 'away') === (anim.playbackRate > 0);
    Object.assign(DOCKMOTION, {anim: null, dir: null});
    $('#dockTab').classList.remove('launch');
    if (away && $('#dock').className.startsWith('open')) {
      dockState('resting');
      const launcher = $('#dockTab');
      if (!still) launcher.animate([{scale: '1'}, {scale: '1.08'}, {scale: '1'}], {duration: 360, easing: dockCurve('arrive')});
      launcher.focus({preventScroll: true});
    } else if (!away) $('#helpdesk .say').focus({preventScroll: true});
    anim.cancel();
    Object.assign(box.style, {transformOrigin: '', willChange: ''});
  };
}
function reverseDock() {
  const anim = DOCKMOTION.anim;
  if (!anim) return;
  anim.reverse();  // from where it is, back the way it came
  $('#dockTab').classList.toggle('launch', (DOCKMOTION.dir === 'back') === (anim.playbackRate > 0));
}
function growFrom(tab) { moveDock('back', tab); }
function putChatAway() {
  const box = $('#helpdesk');
  if (box.hidden || chatDocked()) return;
  if (DOCKMOTION.anim) { if (!dockGoingAway()) reverseDock(); return; }  // on its way out of the tab: it turns back
  $('#dockMenu').hidden = true;
  if (SESSIONPOP.el) SESSIONPOP.el.hidden = true;
  moveDock('away', launcherRect());
}
/* The open questions an agent at work on a ticket asked at its node, answered as every question is, VIEW-021; a
 * permission request is answered from its own card in the thread, so its question at the node is not shown again. */
const ASKED = {drawn: new Map(), session: null};
async function drawAsked(target, session, lines) {
  const ticket = target && !isIntake(target) ? ticketOf(target) : null, sessionId = session?.session_id || null;
  let open = [];
  if (ticket && sessionId && DOCK.chat?.source === 'agent') {
    try { open = (await messagesOf(ticketNode(ticket))).unread.filter(record => record.kind === 'question' && record.by === `${session.agent} ${sessionId}`); }
    catch (error) { toast(error.message); }
  }
  if (DOCK.target !== target || DOCK.session !== sessionId && sessionId) return;
  const permits = new Set(lines.filter(line => line.kind === 'permission').map(line => line.data?.message_id).filter(Boolean));
  open = open.filter(record => !permits.has(record.id));
  const kept = ASKED.session === sessionId ? ASKED.drawn : new Map();
  ASKED.drawn = new Map(open.map(record => [record.id, kept.get(record.id) || asked(record)]));
  ASKED.session = sessionId;
  keepFill($('#helpdesk .asked'), [...ASKED.drawn.values()]);
}
/* The chat's own commands, offered with the agent's when the person types / in the message box. */
const DOCK_COMMANDS = [{name: 'help', description: 'What the chat\'s commands do'},
  {name: 'list', description: 'The agents at work, numbered'}, {name: 'chat', hint: '<number>', description: 'Talk with an agent at work, by its number in /list'},
  {name: 'system', description: 'Start a chat with your system agent'},
  {name: 'fork', hint: '[text]', description: 'A side conversation with the agent on view that knows all it knows, under Subagents'},
  {name: 'apps', description: 'The views the enabled modules offer, each opened in a panel'}];
const dockOffered = () => {
  const agents = commandsOf(DOCK.target ? DOCK.state : null, DOCK.agent);
  return [...agents, ...DOCK_COMMANDS.filter(one => !agents.some(agent => agent.name === one.name)).map(one => ({...one, from: 'This chat'}))];
};
async function dockCommand(text) {
  const [command, ...rest] = text.slice(1).trim().split(/\s+/);
  // a command the agent on view offers is the agent's: it goes to the agent as the message it is
  if (DOCK.target && commandsOf(DOCK.state, DOCK.agent).some(one => one.name === command)) {
    if (await wrote('/api/dispatch-message', {work_id: DOCK.target, session: DOCK.session, text})) drawHelpdesk();
    return;
  }
  if (command === 'help') return dockNote('/list shows the agents at work · /chat <number> talks with one of them · /system calls your system agent · /fork [text] starts a side conversation with the agent on view · /apps lists the views the modules offer · the agent\'s own commands are offered as you type /.');
  if (command === 'list') {
    let found = [];
    try { found = (await read('dispatch-sessions', {thread: 'false'})).sessions || []; } catch (error) { return dockNote(error.message); }
    DOCK.list = found.filter(one => one.state === 'running');
    return dockNote(DOCK.list.length ? DOCK.list.map((one, index) => `${index + 1}. ${agentName(one.agent)} on ${workPart(one.work_id)}${one.activity ? ' · ' + one.activity : ''}`).join('\n')
      : 'No agent is at work right now.');
  }
  if (command === 'chat') {
    const chosen = DOCK.list[Number(rest[0]) - 1];
    if (!chosen) return dockNote('Type /list first, then /chat with the number of the agent.');
    openHelpdesk(chosen.work_id, `${agentName(chosen.agent)} on ${workPart(chosen.work_id)}`, 'It answers when its current step ends.',
      chosen.session_id, null, {focus: true});
    return dockNote(`You are now talking with ${DOCK.label}. Its work goes on while you talk.`);
  }
  if (command === 'system') return callSystem();
  // a fork keeps the session's whole conversation and leaves the session at its work; what follows /fork, when
  // anything does, is its first turn, and it shows under Subagents once its agent has made it
  if (command === 'fork') {
    if (!DOCK.target || !DOCK.live) return dockNote('A fork is made of an agent at work: open its thread, then type /fork.');
    const first = text.slice(1).trim().slice(command.length).trim();
    const done = await posted('/api/dispatch-fork', {work_id: DOCK.target, session: DOCK.session, ...(first ? {text: first} : {})});
    return dockNote(done.ok ? 'The fork was made; its thread is under Subagents.'
      : `${done.body?.error || 'The fork was not made.'}${done.body?.next ? ` Next: ${done.body.next}` : ''}`);
  }
  if (command === 'apps') return showGallery();
  dockNote(`${text} is not a command here. Type /help.`);
}
/* Call: the person's system agent starts with the agent and settings chosen in the line at the top, resuming the
 * last conversation while Resume is checked, which the server's system chat does. A start that fails says why in
 * the chat, and what was written for it goes back into the box. */
async function callSystem() {
  syncResume();
  dockState($('#dock').className.startsWith('open') ? $('#dock').className : 'open');
  Object.assign(DOCK, {since: Date.now(), waiting: STANDBY});
  $('#helpdesk .call').textContent = 'Dismiss';
  const call = DOCK.calling = {};
  drawHelpdesk();  // the chat says it is reaching the agent, where its first words will come
  const agent = summonAgent();
  const done = await posted('/api/system-chat', agent ? {agent} : {});
  const started = done.ok ? done.body : null;
  if (DOCK.calling !== call) {  // dismissed while it was being reached: it is stopped as soon as it answers
    if (started) stayedOff(await stopOnceStarted(started.work_id));
    return null;
  }
  DOCK.calling = null;
  if (!started) {
    $('#helpdesk .call').textContent = DOCK.target ? 'Dismiss' : 'Call';
    startFailed(done.body?.error || 'The agent did not start.', done.body?.next);
    return null;
  }
  DOCK.mine = started.work_id;
  openHelpdesk(started.work_id, 'your system agent', STANDBY, started.session_id, 'system');
  reaching(started);
  return started;
}
/* An agent dismissed while it was being reached is still starting when the start answers, and a stop sent then finds
 * nothing to stop yet: it is stopped once its session is there, looked for every half second for up to half a
 * minute, or not at all when its start failed. */
async function stopOnceStarted(work) {
  for (let tries = 0; tries < 60; tries++) {
    let rows = [];
    try { rows = (await read('dispatch-sessions', {id: work, thread: 'false'})).sessions || []; } catch { rows = []; }
    if (rows.some(one => one.state === 'running')) return wrote('/api/dispatch-stop', {work_id: work});
    if (rows.some(one => /^it (failed|did not start)/.test(one.how || '') && Date.now() - Date.parse(one.started || '') < 60000)) return null;
    await new Promise(wait => setTimeout(wait, 500));
  }
  return null;
}
/* Chat on anything the page shows, VIEW-042: a ticket, open or done, a node, a question, or an agent's session. An
 * agent at work on it is talked to directly; otherwise one starts to talk, and Dismiss stops it. */
async function talkAbout(given, label) {
  // an intake's agent is a conversation already, never a ticket: its chat opens on its session
  if (isIntake(given.id)) return openIntakeChat(given.id, null);
  const agent = summonAgent();  // the agent a new chat starts with; one at work on it is talked to as it is
  DOCK.talking = true;  // a message written meanwhile waits for this start, and starts no other
  let done;
  try { done = await posted('/api/talk', {...given, ...(agent ? {agent} : {})}); } finally { DOCK.talking = false; }
  const started = done.ok ? done.body : null;
  if (!started) { startFailed(done.body?.error || 'The agent did not start.', done.body?.next); return null; }
  if (started.conversation) DOCK.mine = started.work_id;
  openHelpdesk(started.work_id, label, started.state === 'running' ? 'It answers when its current step ends.' : STANDBY,
    started.session_id, started.conversation ? 'conversation' : null);
  reaching(started);
  return started;
}
/* A start that answered before its session runs: a resume names its session at once, though the session is live only
 * once the resume is done. Until then the thread is being reached, and a message written meanwhile waits for it and
 * starts nothing more; a start that never comes is given up after a minute and a half. */
function reaching(started) {
  if (DOCK.chat && DOCK.chat.target === started.work_id) DOCK.chat.starting = started.state === 'running' ? 0 : Date.now();
}
const beingReached = chat => Boolean(chat?.starting) && Date.now() - chat.starting < 90000;
/* Sending with no agent there starts one, as Call does, or, on a thread whose agent has ended, as Continue does; the
 * message waits in the thread, marked as waiting, and goes as the first message once the session is there, after a
 * resume has finished. What is written meanwhile waits behind it, in order. */
function ensureAgent() {
  if (DOCK.calling || DOCK.talking || (DOCK.target && !DOCK.session) || beingReached(DOCK.chat)) return;  // being reached already
  if (!DOCK.target) { callSystem(); return; }
  if (DOCK.live) return;
  const chat = DOCK.chat;
  if (!chat || isIntake(chat.target)) { startFailed('This conversation has ended; an intake is not taken up again from here.'); return; }
  if (chat.source === 'system' || chat.target === DOCK.mine && chat.source !== 'conversation') { callSystem(); return; }
  talkAbout({session: `${chat.target}:${chat.session}`}, chat.label);
}
function queuedRows() {
  DOCK.queue = DOCK.queue.filter(item => !(item.state === 'sent' && (DOCK.heard.has(item.text.trim()) || Date.now() - item.at > 30000)));
  return DOCK.queue.map((item, index) => ({key: `queued:${item.id}`, text: `${item.state}:${index}`,
    make: () => messageRow(item.text, {mine: true, who: 'You', first: index === 0, at: item.at,
      pending: {waiting: 'Sent once the agent is there', sending: 'Sending…', sent: 'Sent'}[item.state] || ''})}));
}
let QUEUE_ID = 0;
async function deliverQueued(session) {
  if (DOCK.delivering || DOCK.calling || session?.state !== 'running' || session.session_id !== DOCK.session
    || !DOCK.queue.some(one => one.state === 'waiting')) return;
  const work = DOCK.target;
  DOCK.delivering = true;
  try {
    for (const item of DOCK.queue.filter(one => one.state === 'waiting')) {
      if (DOCK.target !== work) return;
      item.state = 'sending';
      const done = await posted('/api/dispatch-message', {work_id: work, session: session.session_id, text: item.text});
      if (!done.ok) { item.state = 'waiting'; startFailed(done.body?.error || 'The message was not sent.', done.body?.next); return; }
      item.state = 'sent';
    }
  } finally { DOCK.delivering = false; }
  drawHelpdesk();
}
/* A start or a send that failed: why, in the chat, and every message still waiting back in the box, so nothing
 * written is lost. */
function startFailed(reason, next = null) {
  const waiting = DOCK.queue.filter(item => item.state !== 'sent').map(item => item.text);
  DOCK.queue = DOCK.queue.filter(item => item.state === 'sent');
  const box = $('#helpdesk .say');
  if (waiting.length) { box.value = [...waiting, box.value.trim()].filter(Boolean).join('\n\n'); growSay(); }
  dockNote(`${reason}${next ? ` Next: ${next}` : ''}${waiting.length ? ' Your message is back in the box.' : ''}`);
}
const chatButton = (given, label) => h('button', {class: 'chat', title: `Talk with an agent about ${label}`,
  onclick: event => { event.stopPropagation(); talkAbout(given, label); }}, 'Chat');
/* What a node is called to the agent: an element's address, or a join's receiver, which holds it. */
function nodeTalk(id) {
  const join = id.startsWith('p:') ? joinOf(id) : null;
  return {node: join ? join.receiver_address : S.elements.get(id)?.element.address || id};
}
async function dismiss() {
  if (DOCK.queue.some(item => item.state !== 'sent')) startFailed('Not sent: the agent was dismissed.');
  if (DOCK.calling) {
    DOCK.calling = null;
    $('#helpdesk .call').textContent = DOCK.target ? 'Dismiss' : 'Call';
    return dockNote('The call was cancelled.');
  }
  const chat = DOCK.chat;
  // the agent the person summoned is stopped; an agent at work on its ticket goes on, and only its thread closes
  const summoned = Boolean(chat && (chat.mine || chat.target === DOCK.mine));
  const stopped = summoned ? await wrote('/api/dispatch-stop', {work_id: chat.target}) : null;
  if (DOCK.target === DOCK.mine) DOCK.mine = null;
  DOCK.chats = DOCK.chats.filter(one => one !== chat);
  if (ROAM.focus === chat?.target) ROAM.focus = null;
  dockNote(summoned || !chat ? 'The agent was dismissed.' + stayedOff(stopped) : 'The thread was closed; its agent works on, under Agent deployed.');
  if (DOCK.chats.length) return showChat(DOCK.chats.at(-1));  // the next open chat comes on view
  // no agent is there now: a message sent next starts one, as Call does, and the chat says how to start again
  Object.assign(DOCK, {target: null, session: null, label: '', chat: null, live: false, state: null, agent: null});
  MERGE.chat = null;
  $('#helpdesk .call').textContent = 'Call';
  drawTabs();
  drawHelpdesk();
}
$('#helpdesk .interrupt').onclick = () => interruptChat(DOCK.target, DOCK.session, $('#helpdesk .interrupt'));
$('#helpdesk .call').onclick = () => (DOCK.target || DOCK.calling ? dismiss() : callSystem());
/* Resume and Stay connected beside Call: the dispatch_resume_chats and dispatch_stay_connected settings of this
 * project, read when the dock opens and saved on a change. */
async function syncResume() {
  const project = S.project, box = $('#helpdesk .resume input'), stay = $('#helpdesk .stay input');
  if (!project) return;  // read with the project's own settings, once one is shown
  try {
    const rows = (await read('settings')).settings || [];
    const row = rows.find(one => one.key === 'dispatch_resume_chats'), kept = rows.find(one => one.key === 'dispatch_stay_connected');
    if (S.project === project && row) box.checked = row.value !== false;
    if (S.project === project && kept) stay.checked = kept.value === true;
  } catch { /* the box keeps what it shows */ }
}
$('#helpdesk .resume input').onchange = async event => {
  const done = await posted('/api/settings', {key: 'dispatch_resume_chats', value: event.target.checked});
  if (!done.ok) { event.target.checked = !event.target.checked; dockNote(done.body.error || 'Resume was not saved.'); }
};
$('#helpdesk .stay input').onchange = async event => {
  const done = await posted('/api/settings', {key: 'dispatch_stay_connected', value: event.target.checked});
  if (!done.ok) { event.target.checked = !event.target.checked; dockNote(done.body.error || 'Stay connected was not saved.'); }
  else if (event.target.checked) dockNote('Your system agent stays connected to this project; closing the chat never stops it, and Dismiss turns this off.');
};
/* The person's stop of their system agent turns Stay connected off for the project, dispatch's `disconnect`: the box
 * follows, and the dock says so. `stopped` is the stop's answer. */
function stayedOff(stopped) {
  if (stopped?.stay_connected !== false) return '';
  $('#helpdesk .stay input').checked = false;
  return ' Stay connected is off for this project until you check it again.';
}
$('#helpdesk .compose').onsubmit = async event => {
  event.preventDefault();
  const box = $('#helpdesk .say'), text = box.value.trim();
  if (!text && !DOCK.files.length) return;
  if (text.startsWith('/')) { box.value = ''; return dockCommand(text); }
  const attached = DOCK.files.length ? '\n\nAttached files, saved in the project:\n' + DOCK.files.map(file => `- ${file}`).join('\n') : '';
  box.value = '';
  growSay();
  followLog(true);  // what the person sends is followed to the end of the thread
  // a fork's thread on view is written to as the fork, which takes the words alone; an agent's own subagent is not
  // written to, so what is written there goes to its parent. Words for a fork never wait for its parent's agent
  const fork = DOCK.child && (DOCK.subagents || []).find(one => one.session_id === DOCK.child)?.fork === true ? DOCK.child : null;
  if (!fork && (!DOCK.live || DOCK.queue.some(item => item.state !== 'sent'))) {  // no agent there yet: it waits, and one is reached
    DOCK.queue.push({id: ++QUEUE_ID, text: text + attached, state: 'waiting', at: Date.now()});
    DOCK.files = []; fill($('#helpdesk .files'));
    ensureAgent();
    drawHelpdesk();
    return;
  }
  if (await wrote('/api/dispatch-message', {work_id: DOCK.target, session: DOCK.session, text: text + attached,
    ...(fork ? {fork} : {}),
    ...await voiceAudio(text, !fork && DOCK.state?.capabilities?.audio === true)})) {  // a spoken message's recording, where taken
    DOCK.files = []; fill($('#helpdesk .files')); drawHelpdesk();
  } else { box.value = text; growSay(); }
};
$('#helpdesk .say').addEventListener('keydown', event => {  // Enter sends, Shift+Enter starts a new line
  // an IME's Enter confirms the word it composes and never sends: isComposing, or Safari's 229 as composition ends
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) { event.preventDefault(); $('#helpdesk .compose').requestSubmit(); }
  // Page Up and Page Down read the conversation without leaving the box
  if ((event.key === 'PageUp' || event.key === 'PageDown') && !event.altKey && !event.ctrlKey && !event.metaKey) {
    event.preventDefault();
    const log = $('#helpdesk .log');
    log.scrollBy({top: (event.key === 'PageUp' ? -1 : 1) * log.clientHeight * 0.85, behavior: reduced() ? 'auto' : 'smooth'});
  }
});
/* The chat's own keys, anywhere in it, each in the `?` reference: interrupt the turn, the thread before or after, the
 * newest message, the agent's settings. */
$('#helpdesk').addEventListener('keydown', event => {
  if (event.isComposing) return;
  const mod = MAC ? event.metaKey : event.ctrlKey;
  if (mod && event.key === '.') {
    event.preventDefault();
    if (!$('#helpdesk .interrupt').disabled) $('#helpdesk .interrupt').click();
    return;
  }
  if (!event.altKey || event.ctrlKey || event.metaKey) return;
  if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
    if (DOCK.chats.length < 2) return;
    event.preventDefault();
    const at = DOCK.chats.indexOf(DOCK.chat), by = event.key === 'ArrowUp' ? -1 : 1;
    showChat(DOCK.chats[(at + by + DOCK.chats.length) % DOCK.chats.length], {focus: true});
  } else if (event.key === 'End') { event.preventDefault(); followLog(true); }
  else if (event.key === ',') { event.preventDefault(); openSessionPop(); }
});
function openSessionPop() {
  const line = $('#helpdesk .sessionline');
  if (!line) return toast('The agent\'s settings show once one is chosen.');
  if (sessionPop().hidden) line.click();
  requestAnimationFrame(() => sessionPop().querySelector(FOCUSABLE)?.focus());
}
/* The head's menu: what is used now and then, each with its key. */
const DOCKMENU = overlay($('#dockMenu'), {kind: 'menu'});
function drawDockMenu() {
  const big = $('#dock').className === 'open big', side = ['left', 'right'].includes($('#dock').dataset.place);
  const item = (label, key, run, shown = true) => shown ? h('button', {type: 'button', role: 'menuitem', onclick: () => {
    DOCKMENU.hidden = true; run(); }}, h('span', {}, label), key ? h('kbd', {}, key) : null) : null;
  fill(DOCKMENU,
    item('Give this agent a body…', 'B', askEmbody, embodyHooks() && embodiable(DOCK.chat)),
    item('Agent and settings…', 'Alt ,', openSessionPop),
    item('Apps…', '/apps', showGallery),
    item(big ? 'Back to its size' : 'Make it large', null, () => $('#helpdesk .big').click(), !narrowPage()),
    item(side ? 'Float it' : 'Dock it at the side', null, () => $('#helpdesk .place').click(), !narrowPage()),
    item('Put it back in its corner', 'Double-click head', resetDock, !narrowPage() && !big),
    h('hr'),
    item('Keyboard shortcuts', '?', () => openHelp()));
}
$('#helpdesk .more').onclick = event => {
  event.stopPropagation();
  if (!DOCKMENU.hidden) { DOCKMENU.hidden = true; return; }
  drawDockMenu();
  DOCKMENU.hidden = false;
};
/* The message box grows with what is typed, from one line to about five, and scrolls only past that. */
function growSay() {
  const box = $('#helpdesk .say'), most = parseFloat(getComputedStyle(box).lineHeight || '20') * 5 + 14;
  box.style.height = 'auto';
  box.style.height = `${Math.min(box.scrollHeight + 2, most)}px`;
  box.style.overflowY = box.scrollHeight + 2 > most ? 'auto' : 'hidden';
}
$('#helpdesk .say').addEventListener('input', growSay);
$('#helpdesk .compose').addEventListener('submit', () => requestAnimationFrame(growSay));
$('#helpdesk .clip input').onchange = async event => {
  for (const file of event.target.files) {
    const data = await new Promise(done => { const r = new FileReader(); r.onload = () => done(String(r.result).split(',')[1] || ''); r.readAsDataURL(file); });
    const saved = await wrote('/api/attach', {name: file.name, data});
    if (saved) { DOCK.files.push(saved.path); }
  }
  event.target.value = '';
  fill($('#helpdesk .files'), DOCK.files.map(file => h('span', {class: 'chip'}, file.split('/').pop())));
};
$('#dockTab').onclick = () => dockState('open');
$('#dockTab').onkeydown = event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); dockState('open'); } };
$('#helpdesk .min').onclick = () => putChatAway();  // eased away; its threads are kept
$('#helpdesk .min').title = 'Put the chat away; its conversation is kept (C, or Escape inside it)';
// On the overlay stack as the dock: Escape puts it away only from inside it, and it stays usable over the board.
overlay($('#helpdesk'), {kind: 'dock', close: () => putChatAway(), focus: '.say'});
$('#helpdesk .big').onclick = () => dockState($('#dock').className === 'open big' ? 'open' : 'open big');
/* Where the dock stands: in the corner at its first size; docked at the left or the right of the page, which makes
 * room for it, as wide as its inner edge is dragged; or floating where its head was dragged, VIEW-048, at the size its
 * edges and corners were dragged to. It is kept wholly on the screen and settles gently against an edge it is let go
 * near; let go with the pointer at the page's very side it docks there. The head's Dock button docks it at the right,
 * and from a side puts it back in the corner; a double-click on the head puts it back in the corner at its first
 * size. Its place and size are kept in this browser. On a narrow screen it is always the sheet at the bottom. */
const DOCK_PLACE = 'metaform.dock', DOCK_BOX = 'metaform.dockBox';
const DOCK_MIN = {width: 340, height: 360}, DOCK_EDGE = 12, DOCK_SNAP = 28;
const narrowPage = () => matchMedia('(max-width: 820px)').matches;
const keptBox = () => { try { return JSON.parse(localStorage.getItem(DOCK_BOX) || 'null'); } catch { return null; } };
/* A floating place and size, inside the window: never larger than it, never past its edges. */
function fitBox({left, top, width, height}) {
  width = Math.round(Math.max(DOCK_MIN.width, Math.min(width, innerWidth - 2 * DOCK_EDGE)));
  height = Math.round(Math.max(DOCK_MIN.height, Math.min(height, innerHeight - 2 * DOCK_EDGE)));
  left = Math.round(Math.max(0, Math.min(left, innerWidth - width)));
  top = Math.round(Math.max(0, Math.min(top, innerHeight - height)));
  return {left, top, width, height};
}
function setBox(given, keep = true) {
  const box = $('#helpdesk'), fitted = fitBox(given);
  for (const side of ['left', 'top', 'width', 'height']) box.style[side] = `${fitted[side]}px`;
  box.style.transform = '';
  if (keep) try { localStorage.setItem(DOCK_BOX, JSON.stringify(fitted)); } catch { /* storage can be blocked */ }
  return fitted;
}
function placeDock(place, keep = true) {
  const box = $('#helpdesk');
  place = ['corner', 'left', 'right', 'float'].includes(place) ? place : 'corner';
  $('#dock').dataset.place = place;
  if (place !== 'float') for (const side of ['left', 'top', 'width', 'height', 'transform']) box.style[side] = '';
  else if (!box.style.left) {  // floating again where the person last put it, at the size they gave it
    const now = box.getBoundingClientRect();
    setBox(keptBox() || {left: innerWidth - now.width - 24, top: 80, width: now.width || 460, height: now.height || 640}, false);
  }
  if (keep) try { localStorage.setItem(DOCK_PLACE, place); } catch { /* storage can be blocked; it opens in the corner */ }
  const side = place === 'left' || place === 'right', button = $('#helpdesk .place');
  button.title = side ? 'Put the chat back in the corner' : 'Dock the chat at the side of the page';
  button.setAttribute('aria-label', button.title);
  button.setAttribute('aria-pressed', String(side));
  dockLayout();
}
/* A dock at a side takes its width from the page while the chat is open, so the maps are never under it. */
function dockLayout() {
  const place = $('#dock').dataset.place, open = $('#dock').className === 'open' && !narrowPage();
  $('.app').classList.toggle('docked-left', open && place === 'left');
  $('.app').classList.toggle('docked-right', open && place === 'right');
  foldHeader();  // the header's row is narrower beside a docked chat, and folds when it no longer holds everything
}
$('#helpdesk .place').onclick = () => placeDock(['left', 'right'].includes($('#dock').dataset.place) ? 'corner' : 'right');
/* A change of place shown as motion: the chat drawn where it now is, eased there from where it was by a transform
 * alone, on the arriving curve. */
function settleFrom(before) {
  const box = $('#helpdesk'), after = box.getBoundingClientRect();
  if (reduced() || !before || box.hidden) return;
  const dx = before.left - after.left, dy = before.top - after.top;
  const sx = before.width / after.width, sy = before.height / after.height;
  if (Math.abs(dx) < 1 && Math.abs(dy) < 1 && Math.abs(sx - 1) < 0.01 && Math.abs(sy - 1) < 0.01) return;
  box.animate([{transformOrigin: '0 0', transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})`},
    {transformOrigin: '0 0', transform: 'none'}], {duration: durFor(Math.hypot(dx, dy)), easing: dockCurve('arrive')});
}
const dockMovable = () => !narrowPage() && !chatDocked() && $('#dock').className === 'open' && !DOCKMOTION.anim;
/* The head moves it: a press that moves more than a few pixels takes it, a click leaves it where it is. */
$('#helpdesk .head').addEventListener('pointerdown', event => {
  if (event.button || event.target.closest('button, input, select, textarea, a, [role=button]') || !dockMovable()) return;
  const box = $('#helpdesk'), at = [event.clientX, event.clientY];
  let grip = null, size = null;
  const move = moved => {
    if (!grip) {
      if (Math.hypot(moved.clientX - at[0], moved.clientY - at[1]) < 4) return;
      const from = box.getBoundingClientRect(), side = ['left', 'right'].includes($('#dock').dataset.place);
      const kept = keptBox();  // off a side it floats at its floating size, still under the pointer
      size = side ? {width: kept?.width || Math.min(from.width, 520), height: kept?.height || Math.min(from.height, 680)}
        : {width: from.width, height: from.height};
      grip = [Math.min(at[0] - from.left, size.width - 48), Math.min(at[1] - from.top, 40)];
      $('#dock').dataset.place = 'float';
      box.classList.add('dragging');
      dockLayout();
    }
    setBox({left: moved.clientX - grip[0], top: moved.clientY - grip[1], ...size}, false);
  };
  const done = last => {
    removeEventListener('pointermove', move); removeEventListener('pointerup', done); removeEventListener('pointercancel', done);
    box.classList.remove('dragging');
    if (!grip) return;
    if (last.clientX >= innerWidth - 8 || last.clientX <= 8) return placeDock(last.clientX <= 8 ? 'left' : 'right');
    const before = box.getBoundingClientRect(), near = {...fitBox(before)};
    // near an edge it settles against it, a small margin in
    if (near.left < DOCK_SNAP) near.left = DOCK_EDGE;
    if (near.top < DOCK_SNAP) near.top = DOCK_EDGE;
    if (innerWidth - (near.left + near.width) < DOCK_SNAP) near.left = innerWidth - near.width - DOCK_EDGE;
    if (innerHeight - (near.top + near.height) < DOCK_SNAP) near.top = innerHeight - near.height - DOCK_EDGE;
    setBox(near);
    placeDock('float');
    settleFrom(before);
  };
  addEventListener('pointermove', move);
  addEventListener('pointerup', done);
  addEventListener('pointercancel', done);
  event.preventDefault();
});
/* Back to the corner at its first size, from wherever it is: a double-click on the head. */
function resetDock() {
  if (narrowPage() || chatDocked()) return;
  const before = $('#helpdesk').getBoundingClientRect();
  try { localStorage.removeItem(DOCK_BOX); } catch { /* storage can be blocked */ }
  if ($('#dock').className === 'open big') dockState('open');
  placeDock('corner');
  settleFrom(before);
}
$('#helpdesk .head').addEventListener('dblclick', event => { if (!event.target.closest('button, [role=button]')) resetDock(); });
/* Every edge and corner sizes it, floating or in its corner; in the corner it floats from where it stands. */
for (const edge of ['n', 'e', 's', 'w', 'ne', 'nw', 'se', 'sw']) {
  const grip = h('div', {class: `grip grip-${edge}`, 'data-edge': edge, 'aria-hidden': 'true'});
  $('#helpdesk').append(grip);
  grip.addEventListener('pointerdown', event => {
    if (event.button || !dockMovable() || ['left', 'right'].includes($('#dock').dataset.place)) return;
    event.preventDefault();
    event.stopPropagation();
    const box = $('#helpdesk'), start = box.getBoundingClientRect(), at = [event.clientX, event.clientY];
    $('#dock').dataset.place = 'float';
    setBox(start, false);
    box.classList.add('sizing');
    const move = moved => {
      const dx = moved.clientX - at[0], dy = moved.clientY - at[1];
      let {left, top, width, height} = start;
      if (edge.includes('e')) width = Math.min(start.width + dx, innerWidth - start.left);
      if (edge.includes('s')) height = Math.min(start.height + dy, innerHeight - start.top);
      if (edge.includes('w')) { left = Math.max(0, Math.min(start.left + dx, start.right - DOCK_MIN.width)); width = start.right - left; }
      if (edge.includes('n')) { top = Math.max(0, Math.min(start.top + dy, start.bottom - DOCK_MIN.height)); height = start.bottom - top; }
      setBox({left, top, width: Math.max(DOCK_MIN.width, width), height: Math.max(DOCK_MIN.height, height)}, false);
    };
    const done = () => {
      removeEventListener('pointermove', move); removeEventListener('pointerup', done); removeEventListener('pointercancel', done);
      box.classList.remove('sizing');
      setBox(box.getBoundingClientRect());
      placeDock('float');
    };
    addEventListener('pointermove', move);
    addEventListener('pointerup', done);
    addEventListener('pointercancel', done);
  });
}
addEventListener('resize', () => {  // a smaller window keeps the floating chat whole and on it
  if ($('#dock').dataset.place === 'float' && $('#helpdesk').style.left && !$('#helpdesk').hidden && !DOCKMOTION.anim) {
    setBox($('#helpdesk').getBoundingClientRect(), false);
  }
  dockLayout();
});
try { placeDock(localStorage.getItem(DOCK_PLACE), false); } catch { placeDock('corner', false); }
document.addEventListener('pointermove', event => {  // near the sliver it lifts enough to click; away, it settles back
  const dock = $('#dock');
  if (dock.className.startsWith('open')) return;
  const box = $('#dockTab').getBoundingClientRect();
  const away = Math.hypot(Math.max(box.left - event.clientX, 0, event.clientX - box.right),
                          Math.max(box.top - event.clientY, 0, event.clientY - box.bottom));
  const state = away < 60 ? 'near' : 'resting';
  if (dock.className !== state) dock.className = state;
});
/* The messages of a node, VIEW-030: what agents say to the user there. A question waits for an answer and a note
 * waits to be read. */
const Q = {open: []};
const nodeOf = record => record.node_kind === 'element' ? record.node_id : 'p:' + record.node_id;
const targetOf = id => id.startsWith('p:') ? `join:${id.slice(2)}` : `element:${id}`;
const calledOf = id => (G ? G.graphData().nodes.find(node => node.id === id) : null)?.name
  || (S.elements.has(id) ? labelOf(S.elements.get(id).element) : null) || 'this node';
async function messagesOf(id) {
  const found = (await read('messages', {node: targetOf(id), limit: 0})).results;
  return {unread: found.filter(record => !record.closed), past: found.filter(record => record.closed), all: found};
}
/* The Messages button, VIEW-021: at the top of the page while anything waits for the user, with the count; a click
 * flies to the node of the oldest and opens its unread messages. */
async function renderMessages() {
  try {
    Q.open = noMetaform() ? [] : (await read('messages', {open: true, limit: 0})).results;
  } catch (error) { Q.open = []; toast(error.message); }
  const button = $('#messages');
  button.hidden = !Q.open.length;
  button.textContent = `Messages ${Q.open.length}`;
  button.onclick = () => {
    if (!Q.open.length) return;
    const id = nodeOf(Q.open[0]);
    select(id, true);
    show(id, 'unread');
  };
  if (F.id) await show(F.id, F.which, true);
}
/* The menu of a node, opened by a right-click in either view. Each entry says how many it holds, and one that holds
 * none cannot be chosen. It is where further acts on a node are added. */
async function menu(id, x = null, y = null) {
  let found = {unread: [], past: []}, note = null, tickets = [];
  try { found = await messagesOf(id); note = await noteOf(id); tickets = await ticketsOf(id); }
  catch (error) { toast(error.message); }
  const box = $('#menu');
  const entry = (which, text, count) => h('button', {class: which, disabled: !count, role: 'menuitem',
    onclick: () => { box.hidden = true; show(id, which); }}, text + ' ', h('b', {}, String(count)));
  const kept = networkOf(id).own.length;  // the memories kept at the node, VIEW-031
  fill(box, entry('unread', 'Unread messages', found.unread.length), entry('past', 'Past messages', found.past.length),
    h('button', {class: 'memories', disabled: !kept, role: 'menuitem', onclick: () => { box.hidden = true; memories(id); }},
      'Memories ', h('b', {}, String(kept))),
    h('button', {class: 'notes', role: 'menuitem', onclick: () => { box.hidden = true; notesAt(id); }}, 'Notes ',
      h('b', {}, note ? '1' : '0')),
    h('button', {class: 'history', disabled: !tickets.length, role: 'menuitem',
      onclick: () => { box.hidden = true; history(id); }}, 'Work history ', h('b', {}, String(tickets.length))),
    h('button', {class: 'chat', role: 'menuitem', onclick: () => { box.hidden = true; talkAbout(nodeTalk(id), calledOf(id) || 'this node'); }},
      'Chat about this'),
    h('button', {class: 'raise', role: 'menuitem', title: 'Say what is wrong with this part; a sentinel investigates and brings you proposals',
      onclick: async () => { box.hidden = true; await select(id, true); const issue = $('#work .issue'); if (issue) { issue.hidden = false; issue.querySelector('textarea').focus(); } }},
      'Raise an issue'),
    h('button', {class: 'task', role: 'menuitem', onclick: () => { box.hidden = true; giveWork(id); }}, 'Add Task'),
    h('button', {class: 'element', role: 'menuitem', onclick: () => { box.hidden = true; addElement(id); }}, 'Add Element'),
    h('button', {class: 'agent', disabled: !tickets.some(waiting), role: 'menuitem', onclick: () => { box.hidden = true;
      startWindow(`Start an agent · ${calledOf(id)}`, tickets.filter(waiting)); }}, 'Start agent ',
      h('b', {}, String(tickets.filter(waiting).length))));
  box.hidden = false;
  if (x === null && G) {  // asked for with no pointer: beside the node in the 3D map
    const node = G.graphData().nodes.find(item => item.id === id), stage = $('#stage').getBoundingClientRect();
    const at = node && node.x !== undefined ? G.graph2ScreenCoords(node.x, node.y, node.z) : {x: 40, y: 40};
    [x, y] = [stage.left + at.x + 12, stage.top + at.y + 12];
  }
  const size = box.getBoundingClientRect();
  box.style.left = Math.max(4, Math.min(x ?? 40, innerWidth - size.width - 4)) + 'px';
  box.style.top = Math.max(4, Math.min(y ?? 40, innerHeight - size.height - 4)) + 'px';
}
overlay($('#menu'), {kind: 'menu'});  // a click outside it or Escape closes it, and the focus goes back where it was
/* The board, VIEW-037: the project's tickets as a classic kanban board, one column for each place a ticket can be,
 * a card for each ticket. A card dragged to a column moves its ticket there and to the place it was dropped. */
const B = {tickets: [], off: new Set()};
const KINDS = ['broken', 'flawed', 'enhancement'];  // a ticket's kind; none is a plain task
const BOARD = [['backlog', 'Backlog'], ['todo', 'To do'], ['doing', 'Doing'], ['done', 'Done']];
/* What a record's condition says about the part it is at, MAP-046: the condition belongs to the element or join, not
   to the ticket; the ticket is the work on it. A record with no condition is a plain task. */
const CONDITION_WORDS = {missing: 'missing', trouble: 'trouble', unbuilt: 'not built yet', 'under-construction': 'under construction', built: 'built', broken: 'broken'};
/* A ticket's label is its kind, what sort of work it is, MAP-046 as amended 2026-10-08: never the part's stage, which
   the map shows on the node. A ticket with no kind is a plain task. */
const KIND_WORDS = {broken: 'broken', flawed: 'flawed', enhancement: 'works, could be better'};
function conditionLabel(ticket, extra = '') {
  const kind = ticket.kind || '';
  const words = kind ? KIND_WORDS[kind] || kind : 'task';
  const title = kind ? `This ticket's kind: ${words} (${kind}). The part's stage shows on its node.`
    : `A plain task at ${ticketPart(ticket)}. The part's stage shows on its node.`;
  return h('span', {class: `kind kind-${kind || 'none'}${extra}`, title}, words);
}
const dated = text => { const d = new Date(text || ''); return isNaN(d) ? '' : d.toLocaleString(); };
const ago = text => {
  const seconds = Math.max(0, (Date.now() - Date.parse(text || '')) / 1000);
  return !isFinite(seconds) ? '' : seconds < 60 ? 'now' : seconds < 3600 ? `${Math.floor(seconds / 60)}m`
    : seconds < 86400 ? `${Math.floor(seconds / 3600)}h` : `${Math.floor(seconds / 86400)}d`;
};
const partAt = address => [...S.elements.values()].map(entry => entry.element).find(element => element.address === address);
function nodeChip(target, role) {
  const element = target.address ? partAt(target.address) : null;
  const key = target.kind === 'join' ? 'p:' + target.id : element?.id || target.id;
  const end = address => (address ? partAt(address) : null) ? named(partAt(address)) : address;
  const name = element ? named(element) : target.kind === 'join'
    ? joinOf('p:' + target.id)?.name || (target.ends?.[0] ? `${end(target.ends[0])} → ${end(target.ends[1])}` : 'a join')
    : target.address || target.id;
  return h('button', {class: `node ${role}`, title: `${role === 'assigned' ? 'Assigned' : 'For reference'}: ${target.address || target.id}`,
    onclick: event => { event.stopPropagation(); select(key, true); }}, name);
}
/* References in what the person reads, VIEW-042: a spec record's code, a ticket's or a message's id or its start, and
 * a path in the project. Each is drawn as plain text; once the server says what it stands for it becomes a link that
 * opens it in place, so an unknown code stays plain. */
// an intake agent's work id, intake-<hex>, is not a ticket, so its hex is never taken for one
const REF = /\b(?:[A-Z]{2,6}-\d{3}|D\d{2,4}|(?<!intake-)[0-9a-f]{8,32}|(?:[\w.-]+\/)+[\w.-]+\.\w{1,6})\b/g;
function linked(text) {
  text = String(text ?? '');
  const parts = [];
  let at = 0;
  for (const found of text.matchAll(REF)) {
    parts.push(text.slice(at, found.index), h('span', {class: 'ref', 'data-ref': found[0]}, found[0]));
    at = found.index + found[0].length;
  }
  parts.push(text.slice(at));
  return parts;
}
const LOOKED = new Map();  // project and reference → what it stands for, or null
const looked = ref => {
  const key = `${S.project}\n${ref}`;
  if (!LOOKED.has(key)) LOOKED.set(key, read('lookup', {ref}).then(found => (found.kind ? found : null)).catch(() => null));
  return LOOKED.get(key);
};
new MutationObserver(() => {
  for (const span of document.querySelectorAll('span.ref:not([data-looked])')) {
    span.dataset.looked = '1';
    looked(span.dataset.ref).then(found => {
      if (!found) return;
      span.classList.add('ref-link');
      Object.assign(span, {tabIndex: 0, title: found.title || span.dataset.ref});
      span.setAttribute('role', 'button');
    });
  }
}).observe(document.body, {childList: true, subtree: true});
const POP = h('div', {id: 'refPop', role: 'dialog', 'aria-label': 'What it refers to', hidden: true});
document.body.append(POP);
async function popRef(span, pinned) {
  const found = await looked(span.dataset.ref);
  if (!found) return;
  const kind = {spec: 'Specification', ticket: 'Ticket', message: found.type === 'question' ? 'Question' : 'Message', file: 'File'}[found.kind];
  const body = found.kind === 'spec' ? [h('h4', {}, found.title), h('p', {class: 'text'}, ...linked(found.text)), h('small', {}, found.file)]
    : found.kind === 'ticket' ? [h('h4', {}, ...linked(found.task || found.note || found.id)),
      h('p', {class: 'pills'}, h('span', {class: 'pill'}, found.condition || 'unsorted'),
        h('span', {class: 'pill'}, COLUMN_NAMES[found.column] || found.column), found.done ? h('span', {class: 'pill'}, 'done') : null),
      found.task && found.note ? h('p', {class: 'text'}, ...linked(found.note)) : null,
      found.resolution ? h('p', {class: 'text'}, h('b', {}, 'Resolved: '), ...linked(found.resolution)) : null,
      chatButton({id: found.id}, `ticket ${found.id.slice(0, 8)}`)]
    : found.kind === 'message' ? [h('p', {class: 'text'}, ...linked(found.text)),
      found.choices.length ? h('ol', {}, found.choices.map(choice => h('li', {}, choice))) : null,
      found.answer ? h('p', {}, h('b', {}, 'Answer: '), found.answer) : null,
      chatButton({node: found.address || ''}, 'its node'),
      ]
    : [h('h4', {}, found.title), h('pre', {class: 'text'}, found.text)];
  fill(POP, h('div', {class: 'eyebrow'}, kind, h('button', {class: 'close btn icon sm quiet', type: 'button', 'aria-label': 'Close', title: 'Close (Escape)',
    onclick: () => { POP.hidden = true; }}, h('i', {class: 'i i-close', 'aria-hidden': 'true'}))), ...body);
  POP.pinned = pinned;
  POP.hidden = false;
  const box = span.getBoundingClientRect(), size = POP.getBoundingClientRect();
  POP.style.left = Math.max(8, Math.min(box.left, innerWidth - size.width - 8)) + 'px';
  POP.style.top = (box.bottom + size.height + 8 < innerHeight ? box.bottom + 6 : Math.max(8, box.top - size.height - 6)) + 'px';
}
// On the overlay stack: a click outside it or Escape closes it; one opened by a click or a key takes the focus, one
// shown by resting the pointer does not.
overlay(POP, {kind: 'popover', focus: () => POP.pinned ? POP.querySelector('.close') : false});
document.addEventListener('click', event => {
  const span = event.target.closest?.('.ref-link');
  if (span) { event.preventDefault(); event.stopPropagation(); popRef(span, true); }
}, true);
document.addEventListener('keydown', event => {
  if ((event.key === 'Enter' || event.key === ' ') && event.target.classList?.contains('ref-link')) { event.preventDefault(); popRef(event.target, true); }
});
if (matchMedia('(hover: hover)').matches) {  // on a desktop, resting the pointer on a reference shows it too
  let resting = null;
  document.addEventListener('mouseover', event => {
    const span = event.target.closest?.('.ref-link');
    clearTimeout(resting);
    if (span) resting = setTimeout(() => { if (POP.hidden || !POP.pinned) popRef(span, false); }, 350);
    else if (!POP.pinned && !POP.hidden && !POP.contains(event.target)) POP.hidden = true;
  });
}
function taskWords(text) {  // a node named inline, [[name|address]], shown as its name
  const parts = [], pattern = /\[\[([^|\]]+)\|([^\]]+)\]\]/g;
  let at = 0;
  for (const found of text.matchAll(pattern)) {
    parts.push(...linked(text.slice(at, found.index)), h('span', {class: 'inline', title: found[2]}, found[1]));
    at = found.index + found[0].length;
  }
  parts.push(...linked(text.slice(at)));
  return parts;
}
/* The agent a ticket prefers by default: Claude for front-end and GUI work, Codex for back-end and system work, as
 * dispatch chooses it; the person can choose another on the card at any time. */
const FRONTEND_WORDS = new Set(['gui', 'web', 'page', 'viewer', 'view', 'board', 'ui', 'frontend']);
const defaultAgent = address => (address || '').split('.').some(word => FRONTEND_WORDS.has(word)) ? 'claude' : 'codex';
const eligibleAgents = ticket => Array.isArray(ticket?.map?.eligible) ? ticket.map.eligible : [];
const allowsAgent = (ticket, agent) => !eligibleAgents(ticket).length || eligibleAgents(ticket).includes(agent);
function eligibilityPicker(agents, save) {
  let chosen = [...agents];
  const summary = h('summary', {}), options = h('div', {class: 'choices'});
  const box = h('details', {class: 'eligible', onclick: event => event.stopPropagation()}, summary, options);
  const names = [...new Set([...HARNESS.agents.map(one => one.agent), ...chosen])];  // the agents dispatch knows, VIEW-039
  const paint = () => {
    summary.textContent = 'Eligible agents: ' + (chosen.length ? chosen.map(agentName).join(', ') : 'Any agent');
    for (const input of options.querySelectorAll('input')) input.checked = input.classList.contains('any')
      ? !chosen.length : chosen.includes(input.dataset.agent);
  };
  const change = async event => {
    const before = [...chosen], input = event.target;
    chosen = input.classList.contains('any') ? [] : input.checked
      ? [...new Set([...chosen, input.dataset.agent])] : chosen.filter(name => name !== input.dataset.agent);
    paint();
    for (const control of options.querySelectorAll('input')) control.disabled = true;
    try { if (await save([...chosen]) === false) { chosen = before; paint(); } }
    finally { for (const control of options.querySelectorAll('input')) control.disabled = false; }
  };
  options.append(h('label', {}, h('input', {type: 'checkbox', class: 'any', onchange: change}), 'Any agent'),
    ...names.map(name => h('label', {}, h('input', {type: 'checkbox', 'data-agent': name, onchange: change}), agentName(name))));
  paint();
  return box;
}
const FIVE_AGENTS = ['jelly', 'gearling', 'kite', 'moth', 'drone'];  // five agents at work at most
function ticketControls(ticket) {
  const kept = ticket.map || {};
  const change = async (fields, control) => {
    control.disabled = true;
    try { if (await wrote('/api/ticket', {work_id: ticket.id, ...fields})) await renderBoard(); }
    finally { control.disabled = false; }
  };
  const chosen = kept.agent || defaultAgent(ticket.address);
  const glyphs = kept.glyph && !FIVE_AGENTS.includes(kept.glyph) ? [...FIVE_AGENTS, kept.glyph] : FIVE_AGENTS;
  const box = h('div', {class: 'ticket-controls', onclick: event => event.stopPropagation()},
    h('label', {title: 'The agent this ticket prefers; change it any time, even while one works on it'}, 'Agent ',
      agentSelect(chosen, agent => change({agent}, box.querySelector('select.agent')))),
    eligibilityPicker(eligibleAgents(ticket), async agents => {
      if (!await wrote('/api/eligible', {work_id: ticket.id, agents})) return false;
      await renderBoard();
      return true;
    }),
    h('label', {title: 'Which agent works this ticket: the tickets with one glyph are one agent\'s, done one at a time'}, 'Glyph ',
      h('select', {class: 'glyph-pick', onchange: event => change({glyph: event.target.value}, event.target)},
        h('option', {value: '', selected: !kept.glyph}, 'any'),
        glyphs.map(glyph => h('option', {value: glyph, selected: glyph === kept.glyph}, glyph)))),
    ticket.taken && !ticket.done ? h('button', {class: 'btn sm recall', type: 'button', title: 'Recall the agent working this ticket; the ticket goes back on the board',
      onclick: async event => {
        event.target.disabled = true;
        if (await wrote('/api/dispatch-stop', {work_id: ticket.id})) await renderBoard(); else event.target.disabled = false;
      }}, 'Recall agent') : null,
    ticket.done ? null : h('button', {class: kept.hold ? 'btn sm hold on' : 'btn sm hold', type: 'button',
      title: kept.hold ? 'Release it: agents and automatic starts see it again' : 'Hold it: hidden from agents and automatic starts',
      onclick: event => change({hold: !kept.hold}, event.target)}, kept.hold ? 'Release hold' : 'Hold'));
  return box;
}
function card(ticket, place, total) {
  const steps = ticket.steps || 0, filed = ticket.steps_done || 0;
  const move = async position => {
    if (await wrote('/api/move', {work_id: ticket.id, column: columnOf(ticket), position})) await renderBoard();
  };
  // its agent's glyph, VIEW-040: its own, or while its agent is at work the one its figure is drawn as
  const glyph = ownGlyph(ticket) || ROAM.figures.get(ticket.id)?.glyph;
  const box = h('div', {class: 'card', draggable: 'true', 'data-id': ticket.id, 'data-kind': ticket.kind || 'none',
    onclick: () => { const element = partAt(ticket.address); if (element) { select(element.id, true); history(element.id); } }},
    h('div', {class: 'top'}, glyph ? h('img', {class: 'glyph', src: `/page/agent-glyphs/${glyph}.svg`, alt: glyph,
      title: `Agent ${glyph}: the tickets with this glyph are one agent's, done one at a time`}) : null,
      conditionLabel(ticket),
      ticket.done && ticket.outcome && ticket.outcome !== 'completed' ? h('span', {class: `outcome ${ticket.outcome}`,
        title: `Closed ${ticket.outcome}, not completed`}, ticket.outcome === 'cancelled' ? 'Cancelled' : ticket.outcome) : null,
      // its agent's status with the reason, the same words as the chat's thread: working, needs a login, runner gone
      !ticket.done ? statusChip(ticketStatus(ticket)) : null,
      ticket.taken_by ? h('span', {class: 'by'}, ticket.taken_by) : null,
      h('span', {class: 'age', title: `${ticket.done ? 'Done' : ticket.taken ? 'Taken' : 'Opened'} ${dated(ticket.done || ticket.taken || ticket.created)}`},
        ago(ticket.done || ticket.taken || ticket.created))),
    h('div', {class: 'text'}, ...taskWords(ticket.task || ticket.note || '')),
    h('div', {class: 'nodes'}, nodeChip({kind: ticket.node_kind, id: ticket.node_id, address: ticket.address,
      ends: [ticket.receiver_address, ticket.provider_address]}, 'assigned'),
      ...(ticket.links || []).map(link => nodeChip(link, 'ref'))),
    steps || filed ? h('div', {class: 'progress'}, h('span', {style: {width: `${Math.min(100, 100 * filed / Math.max(steps, filed, 1))}%`}}),
      h('small', {}, `${filed}/${steps || filed}`)) : null,
    ticket.resolution ? h('div', {class: 'resolution'}, ...linked(ticket.resolution)) : null,
    // its acts in one row: start and chat, then its place in the column; its agent's settings fold away below
    h('div', {class: 'acts'},
      waiting(ticket) ? h('button', {class: 'btn sm primary start', type: 'button', title: 'Start an agent on this ticket', onclick: event => {
        event.stopPropagation(); startWindow(`Start an agent · ${ticketPart(ticket)}`, [ticket]); }}, 'Start agent') : null,
      chatButton({id: ticket.id}, ticketPart(ticket)),  // anything can be talked about, a done ticket too, VIEW-042
      // Cancel, VIEW-037 and P232: asked first, with an optional reason; dispatch cancel stops its agent as the
      // person's own stop, so nothing retries it, and closes the ticket with the outcome cancelled, never completed.
      // Moving a card to Done is completing it.
      ticket.done ? null : h('button', {class: 'btn sm quiet cancel', type: 'button',
        title: 'Cancel this ticket: its agent stops and the ticket is closed as cancelled', onclick: async event => {
          event.stopPropagation();
          await cancelTicket(ticket, event.currentTarget);
        }}, 'Cancel'),
      h('span', {class: 'grow'}),
      h('div', {class: 'priority', role: 'group', 'aria-label': 'Card order'},
        [['Top', 'Move to top', 0, place === 0], ['↑', 'Move up', place - 1, place === 0],
          ['↓', 'Move down', place + 1, place === total - 1]].map(([text, label, position, disabled]) =>
          h('button', {class: 'btn sm quiet', type: 'button', title: label, 'aria-label': label, disabled, onclick: event => {
            event.stopPropagation(); move(position);
          }}, text)))),
    h('details', {class: 'ticket-settings', onclick: event => event.stopPropagation()},
      h('summary', {}, ticket.map?.hold ? 'Held · agent and glyph' : 'Agent, glyph and hold'), ticketControls(ticket)));
  if (ticket.map?.hold) box.classList.add('on-hold');
  box.addEventListener('dragstart', event => { event.dataTransfer.setData('text/plain', ticket.id); box.classList.add('dragging'); });
  box.addEventListener('dragend', () => box.classList.remove('dragging'));
  return box;
}
function shownOnBoard(box) {
  const words = $('#board .search').value.trim().toLowerCase();
  box.hidden = B.off.has(box.dataset.kind) || Boolean(words && !box.textContent.toLowerCase().includes(words));
}
function drawBoard() {
  const order = (one, two) => (one.position ?? 1e9) - (two.position ?? 1e9) || B.tickets.indexOf(one) - B.tickets.indexOf(two);
  // the cards are drawn anew, as the agents are read or the map changes, and a card keeps open what the person opened
  const folds = root => [...root.querySelectorAll('.card details')].map(box => [`${box.closest('.card').dataset.id} ${box.className}`, box]);
  const opened = new Set(folds($('#board')).filter(([, box]) => box.open).map(([key]) => key));
  fill($('#board .kinds'), [...KINDS, 'none'].map(kind => h('button', {class: `kindtoggle${B.off.has(kind) ? ' off' : ''}`,
    'data-kind': kind, 'aria-pressed': String(!B.off.has(kind)),
    onclick: () => { B.off.has(kind) ? B.off.delete(kind) : B.off.add(kind); drawBoard(); }}, kind === 'none' ? 'task' : kind)));
  fill($('#board .columns'), BOARD.map(([column, title]) => {
    const tickets = B.tickets.filter(ticket => columnOf(ticket) === column).sort(order);
    const cards = h('div', {class: 'cards'}, tickets.map((ticket, place) => card(ticket, place, tickets.length)));
    cards.addEventListener('dragover', event => { event.preventDefault(); cards.classList.add('over'); });
    cards.addEventListener('dragleave', () => cards.classList.remove('over'));
    cards.addEventListener('drop', async event => {
      event.preventDefault();
      cards.classList.remove('over');
      const id = event.dataTransfer.getData('text/plain');
      const others = [...cards.querySelectorAll('.card')].filter(box => box.dataset.id !== id);
      const after = others.findIndex(box => { const at = box.getBoundingClientRect(); return event.clientY < at.top + at.height / 2; });
      // where it was, so a move to another column, which takes, finishes or opens the ticket again, can be undone
      const moved = B.tickets.find(ticket => ticket.id === id), from = moved ? columnOf(moved) : null;
      const was = moved ? B.tickets.filter(ticket => columnOf(ticket) === from).sort(order).indexOf(moved) : -1;
      if (!await wrote('/api/move', {work_id: id, column, position: after < 0 ? others.length : after, by: 'user'})) return;
      await renderBoard();
      if (from && from !== column) undoable(`Moved to ${COLUMN_NAMES[column]}.`, async () => {
        const back = await wrote('/api/move', {work_id: id, column: from, position: Math.max(0, was), by: 'user'});
        await renderBoard();
        return Boolean(back);
      });
    });
    return h('div', {class: 'column', 'data-column': column},
      h('div', {class: 'head'}, h('span', {}, title), h('span', {class: 'tally'}, String(tickets.length))), cards);
  }));
  for (const box of $('#board').querySelectorAll('.card')) shownOnBoard(box);
  for (const [key, box] of folds($('#board'))) if (opened.has(key)) box.open = true;
  $('#board .start-all').disabled = D.starting || !B.tickets.some(waiting);
}
async function renderBoard() {
  if ($('#board').hidden || !S.project) return;
  const project = S.project, metaform = S.base;  // the agents are read on dispatch events only, VIEW-018
  try { B.tickets = (await read('work', {limit: 0})).results || []; } catch (error) { toast(error.message); return; }
  if (S.project !== project || S.base !== metaform) return;
  drawBoard();
}
$('#boardBtn').onclick = async () => { if (WS.reveal('board')) return; $('#board').hidden = false; await renderBoard(); };
$('#board .close').onclick = () => { $('#board').hidden = true; };
overlay($('#board'), {kind: 'dialog', focus: '.search'});
$('#board .start-all').onclick = async () => {
  await renderBoard();
  const tickets = B.tickets.filter(waiting).sort((one, two) =>
    Number(Boolean(one.held)) - Number(Boolean(two.held)) || (one.position ?? 1e9) - (two.position ?? 1e9));
  startWindow('Start all agents', tickets, true);
};
// Distribute, VIEW-040: the open tickets not taken get the first N agents' glyphs in turn, To do first, then Backlog.
// The glyphs the tickets had before are kept, so Undo gives each back its own.
$('#board .distribute button').onclick = async () => {
  const agents = Number($('#board .distribute input').value);
  if (!Number.isInteger(agents) || agents < 1) return toast('Work is distributed over a whole number of agents.');
  const before = new Map(B.tickets.map(ticket => [ticket.id, ownGlyph(ticket) || '']));
  if (!await wrote('/api/distribute', {agents})) return;
  await renderBoard();
  const changed = B.tickets.filter(ticket => before.has(ticket.id) && before.get(ticket.id) !== (ownGlyph(ticket) || ''));
  if (changed.length) undoable(`Distributed ${plural(changed.length, 'ticket')} over ${plural(agents, 'agent')}.`, async () => {
    let all = true;
    for (const ticket of changed) all = Boolean(await wrote('/api/ticket', {work_id: ticket.id, glyph: before.get(ticket.id)})) && all;
    await renderBoard();
    return all;
  });
};
$('#board .search').oninput = () => { for (const box of $('#board').querySelectorAll('.card')) shownOnBoard(box); };
$('#board .add').onclick = () => {
  const first = S.selected && S.elements.has(S.selected) ? S.selected : [...S.elements.keys()][0];
  if (first) giveWork(first); else toast('Add a card once the project has a map.');
};
/* A node's work history, VIEW-036: every ticket on it, open and done, newest first, in the floating window. */
const COLUMN_NAMES = {backlog: 'backlog', todo: 'to do', doing: 'doing', done: 'done'};
const columnOf = ticket => ticket.done ? 'done' : ticket.taken ? 'doing' : ticket.held ? 'backlog' : 'todo';
const when = text => (text || '').replace('T', ' ').replace('Z', '');
async function ticketsOf(id) { return (await read('work', {node: targetOf(id), limit: 0})).results || []; }
async function history(id) {
  let tickets, dispatched = [];
  try { tickets = await ticketsOf(id); } catch (error) { toast(error.message); return; }
  try { dispatched = (await read('dispatch-sessions')).sessions || []; } catch (error) { toast(error.message); }
  Object.assign(F, {id: null, which: null, ids: new Set(), drawn: new Map()});
  $('#float .title').textContent = `Work history · ${calledOf(id)}`;
  fill($('#float .body'), tickets.length ? [...tickets].reverse().map(ticket => h('div', {class: 'ticket'},
    h('div', {class: 'head'}, conditionLabel(ticket),
      h('span', {class: 'column'}, COLUMN_NAMES[columnOf(ticket)]),
      ticket.taken_by ? h('span', {class: 'by'}, ticket.taken_by) : null,
      h('span', {class: 'age', title: `${ticket.done ? 'Done' : ticket.taken ? 'Taken' : 'Opened'} ${dated(ticket.done || ticket.taken || ticket.created)}`},
        ago(ticket.done || ticket.taken || ticket.created))),
    ticket.task ? h('p', {class: 'task'}, ...linked(ticket.task)) : null,
    ticket.note ? h('p', {class: 'note'}, ...linked(ticket.note)) : null,
    h('div', {class: 'when'}, `opened ${when(ticket.created)}`, ticket.taken ? ` · taken ${when(ticket.taken)}` : '',
      ticket.done ? ` · done ${when(ticket.done)}` : ''),
    (ticket.said || []).length ? h('ol', {class: 'steps'}, ticket.said.map(step => h('li', {}, ...linked(step.said)))) : null,
    ticket.resolution ? h('p', {class: 'resolution'}, ...linked(ticket.resolution)) : null,
    chatButton({id: ticket.id}, ticketPart(ticket)),
    // each agent sent to work it, and its session's thread, opened in the chat dock, VIEW-036 and VIEW-039; the
    // records stay here, on the node, and only the session's conversation is a thread
    ...dispatched.filter(one => one.work_id === ticket.id).map(one => h('div', {class: 'dispatch'},
      h('span', {}, `${agentName(one.agent)} sent ${when(one.started)} · `
        + (one.state === 'running' ? 'working' : `ended${one.how ? `, ${one.how}` : ''}`)),
      chatButton(one.state === 'running' ? {id: one.work_id} : {session: `${one.work_id}:${one.session_id}`},
        `${agentName(one.agent)} on ${ticketPart(ticket)}`),
      h('button', {class: 'btn sm log', type: 'button', title: "The session's whole thread, in the chat dock", onclick: async () => {
        await renderAgents();
        agentAt(one.work_id, one.session_id);
      }}, 'Open in dock')))))
    : h('p', {class: 'empty'}, 'No work here yet.'));
  $('#float').hidden = false;
}
/* The floating window, VIEW-030. It shows the messages it was opened with, each as it is now, so a question answered
 * in it shows its answer and a note read in it stays in sight until the window is closed. Shown again as the map
 * changes, a message that has not changed keeps the part of the window drawn for it, with whatever is typed there. */
const F = {id: null, which: null, ids: new Set(), drawn: new Map(), base: null};
async function show(id, which, again = false) {
  // Its messages are those of the metaform it was opened in; while another is shown it is left as it is.
  if (again && F.base !== S.base) return;
  let found;
  try { found = await messagesOf(id); } catch (error) { toast(error.message); return; }
  if (!again) Object.assign(F, {id, which, ids: new Set(found[which].map(record => record.id)), drawn: new Map(),
    base: S.base});
  if (F.id !== id) return;
  const shown = found.all.filter(record => F.ids.has(record.id));
  $('#float .title').textContent = `${which === 'unread' ? 'Unread' : 'Past'} messages · ${calledOf(id)}`;
  const drawn = new Map(shown.map(record => {
    const state = JSON.stringify([record.closed, record.answer, record.text, record.suggestions]), had = F.drawn.get(record.id);
    return [record.id, had && had.state === state ? had : {state, node: h('div', {},
      h('div', {class: 'when'}, record.created.replace('T', ' ').replace('Z', '')),
      record.kind === 'question' ? asked(record, F.base) : noted(record))}];
  }));
  F.drawn = drawn;
  keepFill($('#float .body'), shown.length ? [...drawn.values()].map(one => one.node) : [h('p', {class: 'empty'}, 'No messages here.')]);
  $('#float').hidden = false;
  for (const record of shown) if (record.kind === 'message' && !record.closed) wrote('/api/read', {id: record.id});
}
function noted(record) {
  return h('div', {class: 'item work'},
    h('div', {class: 'pills'}, workPill('message'), h('span', {class: 'pill'}, record.closed ? 'read' : 'unread'),
      record.by ? h('span', {class: 'pill'}, record.by) : null),
    h('p', {}, ...linked(record.text)));
}
async function wrote(path, given) {
  let response;
  try {
    response = await reach(path, {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({project: S.project, base: S.base, ...given})}, 0);
  } catch (error) { toast(error.message); return null; }
  const body = await response.json().catch(() => ({error: 'The server did not answer with JSON.'}));
  if (!response.ok) toast(body.error || 'It was not written.');
  return response.ok ? body : null;
}
/* A floating window is moved by its title, and opens where the person last put it. `handle` is the part it is held
 * by; `start` runs as it first moves and `end` as it is let go, with the pointer's last place. */
function movable(box, {handle = '.bar', start = null, end = null} = {}) {
  box.classList.add('movable');
  box.querySelector(handle).addEventListener('pointerdown', event => {
    if (event.button || event.target.closest('button, input, select, textarea, a') || box.classList.contains('full')) return;
    const at = [event.clientX, event.clientY];
    let from = null, grip = null;
    const move = moved => {
      if (!from) {  // held, not yet moved: a click on the title leaves the window where it is
        if (Math.hypot(moved.clientX - at[0], moved.clientY - at[1]) < 4) return;
        from = box.getBoundingClientRect();
        grip = [at[0] - from.left, at[1] - from.top];
        if (start?.(moved) === false) { removeEventListener('pointermove', move); removeEventListener('pointerup', done); from = null; return; }
        Object.assign(box.style, {transform: 'none', left: from.left + 'px', top: from.top + 'px'});  // a centered dialog moves from where it is
      }
      box.style.left = Math.max(0, Math.min(moved.clientX - grip[0], innerWidth - 60)) + 'px';
      box.style.top = Math.max(0, Math.min(moved.clientY - grip[1], innerHeight - 40)) + 'px';
    };
    const done = last => {
      removeEventListener('pointermove', move); removeEventListener('pointerup', done);
      if (!from) return;
      keepPlace(box);
      end?.(last);
    };
    addEventListener('pointermove', move);
    addEventListener('pointerup', done);
    event.preventDefault();
  });
}
/* ---------- agents dispatched on tickets, VIEW-039 ----------
 * The dispatch module starts, messages and stops an agent on a ticket, BASE-052; the page asks it to through three
 * writes, VIEW-011. What an agent does is read from the dispatch layer at its ticket's node with each map change. */
const D = {sessions: [], starting: false};
/* The signals of an agent waiting on the person: a permission request, or a question of its own, ACP's elicitation. */
const WAITS_ON_PERSON = ['permission-waiting', 'question-waiting'];
const AUTO = {value: false, agents: null};
async function readAutostart() {
  if (FRAMED) return;
  const project = S.project, control = $('#autostartAgents');
  control.disabled = true;
  try {
    const found = await read('dispatch-autostart');
    if (S.project !== project) return;
    Object.assign(AUTO, found);
    control.checked = found.value;
    control.disabled = found.available === false;
  } catch (error) { if (S.project === project) toast(error.message); }
}
$('#autostartAgents').onchange = async () => {
  const project = S.project, control = $('#autostartAgents');
  control.disabled = true;
  try {
    // the switch alone: Autostart starts each ticket with the agent its card prefers, and the default agent is the
    // person's own choice, made in a picker, never taken from whatever a window last showed
    const saved = await wrote('/api/dispatch-autostart', {value: control.checked});
    if (S.project !== project) return;
    if (saved) Object.assign(AUTO, saved);
    control.checked = AUTO.value;
  } catch (error) { if (S.project === project) { control.checked = AUTO.value; toast(error.message); } }
  finally { if (S.project === project) control.disabled = false; }
};
const waiting = ticket => !ticket.done && !ticket.taken && (ticket.task || '').trim()
  && !D.sessions.some(one => one.state === 'running'
    && (one.work_id === ticket.id || (ownGlyph(ticket) && ownGlyph(ticketOf(one.work_id)) === ownGlyph(ticket))));
const ticketOf = workId => (S.tickets || []).find(ticket => ticket.id === workId);
function ticketPart(ticket) {
  const element = ticket?.address ? partAt(ticket.address) : null;
  return element ? named(element) : ticket ? calledOf(ticketNode(ticket)) : 'its ticket';
}
// a ticket's own glyph, VIEW-040: the map module keeps it and the work read shows it under `map`, BASE-035
const ownGlyph = ticket => ticket?.map?.glyph;
// the character its 3D figure is, VIEW-035: the ticket's own glyph when it is assigned one, VIEW-040
// and else the character the person chose for the agent's type, web_agent_glyphs, when no agent at work has it
// a body chosen for a conversation agent, `embody`, comes before it
const glyphFor = workId => drawGlyph(workId, ownGlyph(ticketOf(workId)) || bodyOf(workId), typeGlyph(workId));
const glyphOf = workId => `/page/agent-glyphs/${glyphFor(workId)}.svg`;
async function startAgent(workId, agent) {
  if (!await wrote('/api/dispatch-start', {work_id: workId, agent})) return false;
  toast(`${agentName(agent)} is starting on the ticket. It shows under Agent deployed while it is working.`);
  return true;
}
/* The window an agent is started from: the tickets, and the agent chosen once for the window, in the picker every
 * start shares, VIEW-039. */
function startWindow(title, tickets, all = false) {
  if (D.starting) return;
  $('#dispatch .title').textContent = title;
  const pick = PICKERS.start ||= agentPicker({label: 'Agent', kept: true, onchange: () => START.draw?.()});
  if (!$('#dispatch .pickhost').firstChild) $('#dispatch .pickhost').append(pick);
  const startAll = $('#dispatch .start-all');
  const candidates = tickets;
  startAll.hidden = !all;
  startAll.disabled = !tickets.length;
  startAll.onclick = async () => {
    if (D.starting) return;
    D.starting = true;
    const agent = pick.value();
    const buttons = [...$('#dispatch .tickets').querySelectorAll('button.start')];
    const pending = tickets.filter((ticket, i) => !buttons[i].disabled);
    startAll.disabled = true;
    pick.hold(true);
    for (const button of buttons) button.disabled = true;
    drawBoard();
    let started = 0;
    for (const ticket of pending) {
      const button = buttons[tickets.indexOf(ticket)];
      try {
        if (await startAgent(ticket.id, agent)) { started++; button.textContent = 'Starting'; }
        else { button.disabled = false; button.textContent = 'Retry'; }
      } catch (error) { toast(error.message); button.disabled = false; button.textContent = 'Retry'; }
    }
    pick.hold(false);
    D.starting = false;
    startAll.disabled = !buttons.some(button => !button.disabled);
    if (started === pending.length) $('#dispatch').hidden = true;
    toast(`${started} ${agentName(agent)} agent${started === 1 ? '' : 's'} starting.`
      + (started < pending.length ? ` ${pending.length - started} could not start; retry their tickets.` : ''));
    await renderBoard();
  };
  pick.hold(false);
  const draw = () => {
    const agent = pick.value(), glyphs = new Set();
    tickets = all ? candidates.filter(ticket => {
      if (!allowsAgent(ticket, agent)) return false;
      const glyph = ownGlyph(ticket);
      if (glyph && glyphs.has(glyph)) return false;
      if (glyph) glyphs.add(glyph);
      return true;
    }) : candidates;
    startAll.disabled = !tickets.length || !agent;
    fill($('#dispatch .tickets'), tickets.map(ticket => h('div', {class: 'ticket', 'data-id': ticket.id},
    conditionLabel(ticket),
    h('button', {class: 'btn primary start', type: 'button', disabled: !agent || !allowsAgent(ticket, agent),
      title: allowsAgent(ticket, agent) ? 'Start the agent chosen above on this ticket'
        : `Eligible agents: ${eligibleAgents(ticket).map(agentName).join(', ')}`, onclick: async event => {
      const agent = pick.value();
      event.target.disabled = true;
      try {
        if (await startAgent(ticket.id, agent)) { $('#dispatch').hidden = true; await renderBoard(); }
        else event.target.disabled = false;
      } catch (error) { toast(error.message); event.target.disabled = false; }
    }}, 'Start'),
    h('div', {class: 'task'}, ...taskWords(ticket.task || ticket.note || '')))));
  };
  START.draw = draw;
  draw();
  $('#dispatch').hidden = false;
  readHarnesses().then(() => { if (!$('#dispatch').hidden && START.draw === draw) draw(); });
}
const START = {draw: null};  // the start window's tickets, drawn again for the agent chosen
$('#dispatch .close').onclick = () => { $('#dispatch').hidden = true; };
overlay($('#dispatch'), {kind: 'dialog', focus: () => $('#dispatch .choice > .btn'), close: () => { $('#dispatch').hidden = true; START.draw = null; }});
/* The agents key: each agent working in the project now, with its flat icon and in words what it is; a click opens its
 * session's thread. An ended session leaves the key and the map; its log stays in the node's work history, VIEW-036.
 * Sessions are the dispatch module's own tables, never the map. */
async function renderAgents() {
  if (FRAMED) return;
  const project = S.project, metaform = S.base;
  let found = {sessions: []};
  if (!noMetaform()) {
    try { found = await read('dispatch-sessions', {thread: 'false'}); }  // the threads are read for the open window only
    catch (error) { toast(error.message); found = {sessions: D.sessions}; }  // a failed read keeps the agents drawn
  }
  let claimed = {claims: D.claims || [], proposals: D.proposals || {}};
  if (!noMetaform()) {
    try { claimed = await read('dispatch-claims'); } catch (error) { /* drawn as last read */ }
  }
  if (S.project !== project || S.base !== metaform) return;  // the answer for a project the person has left
  D.sessions = found.sessions || [];
  D.signals = found.signals || [];  // a login needed is read from them, `sessionStatus`
  D.states = found.states || {};  // each session's state, the intake guard's phase among it, `drawIntake`
  D.claims = claimed.claims || [];
  D.proposals = claimed.proposals || {};
  D.signals = found.signals || [];  // a spinning or stuck agent's figure circles restlessly, `moodOf`
  noticeAttention();  // and the mascot calls the person to what needs them, `ATTN`
  // the permission requests and the agents' questions waiting for the person, counted on the chat's tab
  const asking = (found.signals || []).filter(one => WAITS_ON_PERSON.includes(one.signal) && one.active !== false);
  D.asking = asking.map(one => ({...one, agent: D.sessions.find(row => row.session_id === one.session_id)?.agent}))
    .filter(one => D.sessions.some(row => row.session_id === one.session_id && row.state === 'running'));
  drawDockTab();
  readIntake(found.signals || []);
  if (!$('#board').hidden) drawBoard();
  // at work: a session whose runner says a turn is executing, the same ones the map's figures follow
  const working = D.sessions.filter(one => one.activity === 'working');
  // an entry drawn the same stays in place, so the one under the pointer is not swapped while it is clicked
  keyedFill($('#agents .list'), working.map(one => ({key: one.session_id,
    text: [one.work_id, one.agent, glyphOf(one.work_id), workPart(one.work_id), agentName(one.agent)].join('\n'),
    make: () => h('div', {class: 'agent-row'}, h('input', {type: 'checkbox', class: 'inuse',
      checked: !INUSE.off.has(one.work_id), 'aria-label': `The part of the map ${agentName(one.agent)} is using`,
      title: 'Checked: the part of the map this work is using shows in white. Unchecked: it is hidden.',
      onchange: event => { INUSE.off[event.target.checked ? 'delete' : 'add'](one.work_id);
        paintInUse(); }}), h('button', {
      class: 'agent working', 'data-id': one.work_id, 'data-session': one.session_id,
      title: `${agentName(one.agent)} on work ${one.work_id}: working`,
      onclick: () => agentAt(one.work_id, one.session_id)},
      h('img', {src: glyphOf(one.work_id), alt: glyphFor(one.work_id)}), h('b', {}, agentName(one.agent)),
      h('small', {}, `on ${workPart(one.work_id)} · working`)),
      chatButton({id: one.work_id}, `${agentName(one.agent)} on ${workPart(one.work_id)}`))})));
  agentsWindow(working.length);  // slides out while any is at work, away a few seconds after
  paintInUse();
  figures(S.tickets || []);  // the map's figures follow the same sessions
}
/* An agent's session opened in the chat dock, as the agents key, a figure in 3D, the node's work history and a
 * request waiting for the person open it: the thread of that session, or of the ticket's newest session, chosen by the
 * person, so its agent and its part are shown on the maps. */
function agentAt(workId, sessionId = null) {
  const sessions = D.sessions.filter(one => one.work_id === workId);
  const session = sessionId ? sessions.find(one => one.session_id === sessionId) || {session_id: sessionId}
    : sessions.filter(one => one.state === 'running').at(-1) || sessions.at(-1) || null;
  if (isIntake(workId)) return openIntakeChat(workId, session?.session_id || null, {focus: true});
  // a thread already open keeps its name and where it comes from: the person's chat about a node and the system agent
  // hang on the same held ticket, and the thread read tells them apart
  const open = session && DOCK.chats.find(one => one.session === session.session_id);
  openHelpdesk(workId, open?.label || `${agentName(session?.agent)} on ${workPart(workId)}`,
    'It answers when its current step ends.', session?.session_id || null, null, {focus: true});
}
/* Giving work, VIEW-032: the task is written as a person writes, the nodes it concerns are linked to it, and a node
 * inserted into the text reads there as its proper noun and carries its address. */
const K = {nodes: [], chosen: null, at: null, generation: 0, project: null, base: null, eligible: []};
const partOf = address => [...S.elements.values()].map(entry => entry.element).find(element => element.address === address);
const named = element => labelOf(element);
function chip(element, remove = null) {
  return h('span', {'data-address': element.address, title: element.address, contenteditable: 'false'}, named(element),
    remove ? h('button', {title: 'Take it off this task', onclick: remove}, 'x') : null);
}
function linkedNodes() {
  fill($('#task .linked'), K.nodes.map((address, index) => chip(partOf(address),
    index ? () => { K.nodes = K.nodes.filter(one => one !== address); linkedNodes(); } : null)));
}
async function taskWorkflows() {
  const generation = ++K.generation, picker = $('#task .workflow'), project = S.project, metaform = S.base;
  const stale = () => generation !== K.generation || $('#task').hidden || project !== S.project || metaform !== S.base;
  picker.disabled = true;
  fill(picker, h('option', {value: ''}, 'Loading workflows…'));
  $('#task .workflow-entry').hidden = true;
  $('#task .workflow-call').value = '';
  if (!S.bases.some(map => map.active && map.id === metaform)) {
    fill(picker, h('option', {value: ''}, 'Choose the active map to run workflows'));
    return;
  }
  try {
    const found = await read('workflows');
    if (stale()) return;
    const calls = found.workflows.flatMap(workflow => workflow.logic.map(name =>
      h('option', {value: `${workflow.address}.${name}`}, `${workflow.name || workflow.address} · ${name}`)));
    fill(picker, h('option', {value: ''}, found.enabled ? (calls.length ? 'No workflow' : 'No stored workflows') : 'Workflows unavailable'), ...calls);
    picker.disabled = !calls.length;
  } catch (error) {
    if (stale()) return;
    fill(picker, h('option', {value: ''}, 'Workflows could not load'));
    toast(error.message);
  }
}
$('#task .workflow').onchange = () => {
  const chosen = $('#task .workflow').value;
  $('#task .workflow-entry').hidden = !chosen;
  $('#task .workflow-call').value = chosen ? `${chosen}()` : '';
};
function giveWork(id, text = '') {
  const element = S.elements.get(id)?.element;
  if (!element) { toast('Work is given at an element.'); return; }
  Object.assign(K, {nodes: [element.address], chosen: null, at: null, project: S.project, base: S.base, eligible: []});
  $('#task .condition').value = '';
  $('#task .ticket-kind').value = '';
  $('#task .backlog').checked = false;
  $('#task .start-agent').checked = false;
  // the agent the ticket prefers, Claude for front-end and GUI work and Codex for the rest as dispatch chooses it,
  // in the picker every start shares; the one it shows is what the ticket keeps and what Start an agent now starts
  if (!$('#task .pickhost').firstChild) $('#task .pickhost').append(PICKERS.task ||= agentPicker({label: 'Preferred agent', kept: true}));
  PICKERS.task.set(defaultAgent(element.address));
  fill($('#task .eligibility'), eligibilityPicker([], agents => { K.eligible = agents; }));
  $('#task .title').textContent = `Add Task · ${named(element)}`;
  $('#task .text').replaceChildren(...(text ? [text] : []));
  $('#task .browser input').value = '';
  linkedNodes();
  const parts = [...S.elements.values()].map(entry => entry.element).sort((one, two) => one.address < two.address ? -1 : 1);
  fill($('#task .rows'), parts.map(part => h('button', {'data-address': part.address, onclick: () => choose(part.address)},
    named(part), h('small', {}, part.address))));
  $('#task .insert').disabled = $('#task .link').disabled = true;
  $('#task').hidden = false;
  taskWorkflows();
  $('#task .text').focus();
  chart(parts);
}
/* A part is chosen in the list or in the chart, and is then chosen in both. */
function choose(address) {
  K.chosen = address;
  for (const one of $('#task').querySelectorAll('.rows [data-address], .chart g[data-address]')) {
    one.classList.toggle('chosen', one.dataset.address === address);
    if (one.dataset.address === address && one.closest('.rows')) one.scrollIntoView({block: 'nearest'});
  }
  $('#task .insert').disabled = $('#task .link').disabled = false;
}
/* The editor's own chart of the project, VIEW-032: the parts and their joins, looked around by dragging and by the
 * wheel, apart from the two maps of the page, which it does not move and which do not move it. */
const C = {generation: 0, cam: null, whole: null};
function camera(cam) {
  C.cam = cam;
  $('#task .chart svg')?.setAttribute('viewBox', `${cam.x} ${cam.y} ${cam.w} ${cam.h}`);
}
async function chart(parts) {
  const host = $('#task .chart'), generation = ++C.generation;
  const unable = text => fill(host, h('p', {class: 'empty', style: {padding: '12px'}}, text));
  if (!window.mermaid || !mermaidReady) return unable('The chart could not load.');
  if (parts.length > MAP2D) return unable(`The chart lays out at most ${MAP2D} parts.`);
  const keys = new Map(parts.map((part, index) => [part.id, `c${index}`]));
  const lines = ['flowchart TB', ...parts.map(part => `${keys.get(part.id)}["${plain2d(named(part))}"]`),
    ...S.joins.filter(join => keys.has(join.receiver)).flatMap(join => join.providers.filter(id => keys.has(id))
      .map(provider => `${keys.get(join.receiver)} --> ${keys.get(provider)}`))];
  let result;
  try { result = await window.mermaid.render(`pick${generation}`, lines.join('\n'), $('#draw')); }
  catch (error) { return unable('The chart could not be drawn.'); }
  if (generation !== C.generation) return;
  const svg = document.importNode(new DOMParser().parseFromString(result.svg, 'image/svg+xml').documentElement, true);
  svg.removeAttribute('style'); svg.removeAttribute('width'); svg.removeAttribute('height');
  host.replaceChildren(svg);
  for (const part of parts) {
    const group = svg.querySelector(`[id*="-flowchart-${keys.get(part.id)}-"]`);
    if (!group) continue;
    group.dataset.address = part.address;
    group.append(Object.assign(document.createElementNS(SVG, 'title'), {textContent: part.address}));
    group.addEventListener('click', event => { event.stopPropagation(); choose(part.address); });
  }
  const whole = svg.viewBox.baseVal;
  C.whole = {x: whole.x, y: whole.y, w: whole.width, h: whole.height};
  // It opens on the part the task is added at, at the size its names are written in, so they are read at once; the
  // whole of a project's chart in so small an area is boxes too small to read.
  const first = svg.querySelector(`g[data-address="${CSS.escape(K.nodes[0])}"]`), area = host.getBoundingClientRect();
  if (first && area.width) {
    const box = first.getBBox(), matrix = first.transform.baseVal.consolidate()?.matrix || new DOMMatrix();
    const middle = new DOMPoint(box.x + box.width / 2, box.y + box.height / 2).matrixTransform(matrix);
    camera({x: middle.x - area.width / 2, y: middle.y - area.height / 2, w: area.width, h: area.height});
  } else camera(C.whole);
  if (K.chosen) choose(K.chosen);
}
$('#task .whole').onclick = () => { if (C.whole) camera(C.whole); };
(() => {
  const host = $('#task .chart');
  let drag = null;
  host.addEventListener('pointerdown', event => { if (C.cam) drag = {x: event.clientX, y: event.clientY, cam: {...C.cam}, moving: false}; });
  host.addEventListener('pointermove', event => {
    if (!drag) return;
    if (!drag.moving) {  // captured only once it is a drag, so a click still reaches the part under it
      if (Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 4) return;
      drag.moving = true; host.setPointerCapture(event.pointerId);
    }
    const scale = C.cam.w / host.getBoundingClientRect().width;
    camera({...drag.cam, x: drag.cam.x - (event.clientX - drag.x) * scale, y: drag.cam.y - (event.clientY - drag.y) * scale});
  });
  host.addEventListener('pointerup', () => { drag = null; });
  host.addEventListener('wheel', event => {
    if (!C.cam) return;
    event.preventDefault();
    const by = event.deltaY > 0 ? 1.15 : 0.87, box = host.getBoundingClientRect(), cam = C.cam;
    const px = (event.clientX - box.left) / box.width, py = (event.clientY - box.top) / box.height;
    camera({x: cam.x + (cam.w - cam.w * by) * px, y: cam.y + (cam.h - cam.h * by) * py, w: cam.w * by, h: cam.h * by});
  }, {passive: false});
})();
$('#task .full').onclick = () => {
  const full = $('#task').classList.toggle('full');
  $('#task .full').textContent = full ? 'Window' : 'Full screen';
};
/* Where the cursor was in the text, kept as the text loses it to the browser's buttons. It is kept as a node and a
 * count into it and not as a range, since a range is moved to the start of a text the browser writes again, which
 * it does to a space typed at the end of a line. */
function keepCursor() {
  const chosen = getSelection();
  if (chosen.rangeCount && $('#task .text').contains(chosen.anchorNode)) {
    const range = chosen.getRangeAt(0);
    K.at = {node: range.endContainer, count: range.endOffset};
  }
}
// It is read at each change of the text and as the text is left: the browser tells of a moved cursor a moment after
// it moved, which can be after the person has gone on to the browser of the namespace.
document.addEventListener('selectionchange', keepCursor);
for (const kind of ['input', 'keyup', 'mouseup', 'blur']) $('#task .text').addEventListener(kind, keepCursor);
$('#task .browser input').oninput = event => {
  const wanted = event.target.value.trim().toLowerCase();
  for (const row of $('#task .rows').children) row.hidden = Boolean(wanted) && !row.textContent.toLowerCase().includes(wanted);
};
$('#task .insert').onclick = () => {
  const text = $('#task .text'), made = chip(partOf(K.chosen));
  if (K.at && text.contains(K.at.node)) {
    const at = document.createRange(), most = K.at.node.nodeType === Node.TEXT_NODE ? K.at.node.length : K.at.node.childNodes.length;
    at.setStart(K.at.node, Math.min(K.at.count, most));
    at.collapse(true);
    at.insertNode(made);
  } else text.append(made);
  // A text of no width after the name, for the cursor to stand in: the browser cannot put a cursor after a part
  // of the text that is not typed into when nothing follows it, and what is typed there is lost.
  const hold = document.createTextNode('\u200b');
  made.after(hold);
  const after = document.createRange();
  after.setStart(hold, 1);
  after.collapse(true);
  getSelection().removeAllRanges();
  getSelection().addRange(after);
  text.focus();
};
$('#task .link').onclick = () => { if (!K.nodes.includes(K.chosen)) { K.nodes.push(K.chosen); linkedNodes(); } };
/* The task as text: an inline node is written `[[name|address]]`, so an agent has the name and the address. */
const taskText = () => [...$('#task .text').childNodes].map(function told(node) {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent;
  if (node.dataset?.address) return `[[${node.textContent}|${node.dataset.address}]]`;
  return (node.tagName === 'DIV' || node.tagName === 'BR' ? '\n' : '') + [...node.childNodes].map(told).join('');
}).join('').replace(/\u200b/g, '').replace(/\u00a0/g, ' ').trim();
$('#task .put').onclick = async () => {
  if (K.project !== S.project || K.base !== S.base) {
    toast('This task belongs to the map you left. Reopen Add Task at its target.');
    return;
  }
  let task = taskText();
  if (!task.trim() && !$('#task .workflow').value) { toast('Say what is to be done.'); return; }
  if ($('#task .workflow').value) {
    const call = $('#task .workflow-call').value.trim();
    if (!call) { toast('Give the workflow an entry call.'); return; }
    const input = {call, element: K.nodes[0]};
    task = (task ? task + '\n\n' : '') + 'Run this stored workflow using the workflow module\'s run command with the following input. ' +
      'Follow the returned instructions and use the workflow commands for calls, handoffs and returns. ' +
      'Complete this ticket with the result when the entry call returns. Report any workflow failure on this ticket.\n' +
      `Workflow input: ${JSON.stringify(input)}`;
  }
  if (!task) { toast('A task says what is to be done.'); return; }
  // One ticket on the node it is assigned to, the first listed; every other node of the task, linked or named
  // inline, is linked for reference, VIEW-035.
  const inline = [...$('#task .text').querySelectorAll('[data-address]')].map(node => node.dataset.address);
  const all = [...new Set([...K.nodes, ...inline])].filter(address => partOf(address));
  const nodes = all.map(address => `element:${partOf(address).id}`);
  const project = S.project, metaform = S.base, generation = K.generation;
  const agent = PICKERS.task?.value(), startNow = $('#task .start-agent').checked;
  const eligible = [...K.eligible];
  const written = await wrote('/api/task', {task, nodes, condition: $('#task .condition').value || null, kind: $('#task .ticket-kind').value || null, held: $('#task .backlog').checked,
    agent, eligible});
  if (project !== S.project || metaform !== S.base || generation !== K.generation) {
    if (written) toast(`Task saved in ${project}. Open that map to start its agent.`);
    return;
  }
  if (written) {
    $('#task').hidden = true;
    if (startNow) await startAgent(written.results[0].id,
      !eligible.length || eligible.includes(agent) ? agent : eligible[0]);
    renderBoard();
  }
};
$('#task .close').onclick = () => { $('#task').hidden = true; K.generation++; };
/* Escape or a click beside it does not throw away a task being written without asking. */
const discard = (what, kept) => confirmAct({title: `Discard ${what}?`, text: 'What you wrote here is not kept.',
  verb: 'Discard', cancel: kept, danger: true});
overlay($('#task'), {kind: 'dialog', close: () => $('#task .close').click(), focus: '.text',
  guard: () => !taskText() || discard('this task', 'Keep writing')});
/* Notes, VIEW-034: one single note, not a list, of at most 2048 characters, edited in place.
 * One note at the node, kept by the memory module and read and written with
 * `memory note`, whatever layers are in view. Writing it replaces what it held, and writing it empty clears it. A note
 * asks for nothing: it is not a message, it does not glow, and it stays. */
const N = {node: null};
const NOTE_LIMIT = 2048;
async function noteOf(id) { return (await read('memory-note', {node: targetOf(id)})).note; }
function noteBy(note) {
  if (!note) return 'No note here yet.';
  return `Written by ${note.by === 'user' ? 'you' : note.by || 'an agent'}, ${when(note.at)}`;
}
function noteCount() { $('#notes .count').textContent = `${$('#notes textarea').value.length} / ${NOTE_LIMIT}`; }
async function notesAt(id) {
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
$('#notes .save').onclick = async () => {
  const text = $('#notes textarea').value.trim() ? $('#notes textarea').value : '';
  if (!await wrote('/api/note', {node: targetOf(N.node), text})) return;
  await notesAt(N.node);
};
$('#notes .close').onclick = () => { $('#notes').hidden = true; N.node = null; };
overlay($('#notes'), {kind: 'window', close: () => $('#notes .close').click(), focus: 'textarea',
  guard: () => $('#notes textarea').value === N.text || discard('the changes to this note', 'Keep editing')});
movable($('#notes'));
/* Adding an element, VIEW-033: a person gives it its address and joins it to the node the window was opened at. */
const E = {node: null, from: ''};
function addElement(id) {
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
  if (!$('#element .pickhost').firstChild) $('#element .pickhost').append(PICKERS.element ||= agentPicker({label: 'Agent', kept: true}));
  $('#element').hidden = false;
  $('#element .address').focus();
}
$('#element .add').onclick = async () => {
  const written = $('#element .address').value.trim();
  const address = written === E.from || written.endsWith('.') ? '' : written;  // what it was started from is no address
  if (!address || S.elements.size && [...S.elements.values()].some(entry => entry.element.address === address)) {
    toast(address ? `There is an element at ${address} already.` : 'An element has an address.');
    return;
  }
  const given = {address, node: `element:${E.node}`, receives: $('#element .receives').value,
    name_length: Number($('#element .length').value) || 1, name: $('#element .name').value.trim(),
    role: $('#element .role').value,
    purpose: $('#element .purpose').value.trim(), ef: $('#element .ef').value.trim(),
    validate: $('#element .validate').checked};
  const response = await fetch('/api/element', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({project: S.project, base: S.base, ...given})});
  const body = await response.json().catch(() => ({error: 'The server did not answer with JSON.'}));
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
};
$('#element .close').onclick = () => { $('#element').hidden = true; };
overlay($('#element'), {kind: 'dialog', close: () => $('#element .close').click(), focus: '.address',
  guard: () => !['.purpose', '.ef', '.name'].some(name => $('#element ' + name).value.trim())
    && [E.from, ''].includes($('#element .address').value.trim()) || discard('this element', 'Keep writing')});
movable($('#element'));
movable($('#task'));
movable($('#float'));
$('#float .close').onclick = () => { $('#float').hidden = true; O.open = false; Object.assign(F, {id: null, which: null, ids: new Set(), drawn: new Map()}); };
overlay($('#float'), {kind: 'window', close: () => $('#float .close').click()});
async function renderWork(target, key, also = null) {
  let records = [];
  try {
    records = (await read('work', {node: target, limit: 0})).results;
    if (also) records = [...records, ...(await read('work', {node: also, limit: 0})).results];
  } catch (error) { toast(error.message); }
  const box = $('#work');
  if (!box || S.selected !== key) return;
  const held = records.find(record => !record.done && record.condition);
  const state = h('select', {class: 'state', 'aria-label': 'The state of this part', title: 'The state of this part: a stage on its way to existing, or broken. Built draws nothing',
    onchange: async event => {
      event.target.disabled = true;
      const written = await wrote('/api/state', {node: target, condition: event.target.value});
      event.target.disabled = false;
      if (written) { toast(`${calledOf(key) || 'The part'} is ${CONDITION_WORDS[event.target.value] || 'built'}.`); renderWork(target, key, also); }
    }}, ...[['', 'state: not set'], ['unbuilt', 'unbuilt'], ['under-construction', 'under construction'], ['built', 'built'], ['broken', 'broken']]
      .map(([value, text]) => h('option', {value, selected: (held ? held.condition : '') === value}, text)));
  // Raise an issue, the person says what is wrong in their words; a sentinel investigates and brings
  // proposals to the chat; what they choose becomes held tickets. The only way work on an issue begins.
  const issue = h('div', {class: 'issue', hidden: true},
    h('textarea', {rows: 4, placeholder: 'What is wrong, what you expected, and how to make it happen.', 'aria-label': 'What is wrong'}),
    h('div', {class: 'issueacts'}, h('button', {class: 'btn sm primary send', type: 'button', onclick: async event => {
      const text = issue.querySelector('textarea').value.trim();
      if (!text) { toast('Say what is wrong.'); return; }
      event.target.disabled = true;
      const agent = summonAgent();
      const started = await wrote('/api/raise', {...nodeTalk(key), text, ...(agent ? {agent} : {})});
      event.target.disabled = false;
      if (!started) return;
      issue.hidden = true;
      if (started.conversation) DOCK.mine = started.work_id;
      const queued = started.state === 'queued' ? (Array.isArray(started.waiting_on)
        ? 'Queued: this part is in use, so the sentinel starts when that work is done.'
        : 'Queued: every agent slot is in use, so the sentinel starts when one is free.') : STANDBY;
      openHelpdesk(started.work_id, `the sentinel on ${calledOf(key) || 'this node'}`, queued, started.session_id, 'sentinel');
    }}, 'Send to the sentinel'), h('span', {class: 'pickhost'})));
  const raise_ = h('button', {class: 'btn sm raise', type: 'button', 'aria-expanded': 'false',
    title: 'Say what is wrong with this part; a sentinel investigates and brings you proposals',
    onclick: () => { issue.hidden = !issue.hidden; raise_.setAttribute('aria-expanded', String(!issue.hidden));
      // the one picker of the issue form, moved into this form: the agent the sentinel starts with
      if (!issue.hidden) { issue.querySelector('.pickhost').append(summonPicker('raise', {label: 'Agent for the sentinel'}));
        issue.querySelector('textarea').focus(); } }}, 'Raise an issue');
  // One row for the part: its state, Raise an issue and one Chat for the node; then one row for each ticket on it.
  fill(box, h('div', {class: 'workhead'}, h('div', {class: 'eyebrow'}, 'Work'), state, raise_,
    chatButton(nodeTalk(key), calledOf(key) || 'this node')), issue,
    records.map(record => h('div', {class: 'item work'},
    h('div', {class: 'pills'}, record.condition ? workPill(record.condition) : null,
      h('span', {class: 'pill'}, KIND_WORDS[record.kind] || record.kind || 'task'), h('span', {class: 'pill'}, record.done ? 'done' : 'open'),
      record.held ? h('span', {class: 'pill'}, 'held') : null, record.reviewed ? h('span', {class: 'pill'}, 'reviewed') : null),
    record.note ? h('p', {}, ...linked(record.note)) : null,
    record.task ? h('p', {class: 'fn'}, ...linked(record.task)) : null,
    record.done ? h('p', {class: 'obs'}, 'Resolved: ', ...linked(record.resolution)) : null)));
}
function layerPill(name) { return h('span', {class: 'pill layer', style: {'--c': `var(${colorVar(name)})`}}, name); }
function elementLink(id, address) {
  const entry = S.elements.get(id);
  return h('a', {class: 'link', href: '#', onclick: event => { event.preventDefault(); select(id, true); }},
    entry ? labelOf(entry.element) : address);
}
function joinCard(join, side) {
  // A join seen from an element it holds names its receiver; seen from its receiver, it names every element it holds.
  const others = side === 'provider' ? (join.elements || []).map(each => elementLink(each.element_id, each.address))
    : [elementLink(join.receiver, join.receiver_address)];
  return h('div', {class: 'join'},
    h('div', {class: 'row'}, h('span', {class: 'dir'}, `${side} · `, ...others.flatMap((link, at) => at ? [', ', link] : [link])),
      h('span', {class: 'lay', style: {'--c': `var(${colorVar(join.layer)})`}}, join.layer)),
    join.purpose ? h('p', {}, join.purpose) : null,
    join.ef ? h('p', {class: 'fn'}, join.ef) : null);
}
/* An item's value as text: an object as one `field: value` line per field it holds, empty fields left out, so a layer
 * such as intake details reads as fields, not as raw data. */
const filled = value => value !== null && value !== undefined && value !== '' && !(Array.isArray(value) && !value.length);
const fieldText = value => value && typeof value === 'object' ? JSON.stringify(value) : String(value);
function itemText(value) {
  if (Array.isArray(value)) return value.map(fieldText).join('\n');
  if (value && typeof value === 'object')
    return Object.entries(value).filter(([, each]) => filled(each)).map(([key, each]) => `${key}: ${fieldText(each)}`).join('\n');
  return String(value ?? '');
}
/* The same value for the panel: an object as a table of its fields. */
function itemView(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return itemText(value);
  return h('dl', {class: 'fields'}, Object.entries(value).filter(([, each]) => filled(each))
    .flatMap(([key, each]) => [h('dt', {}, key), h('dd', {}, fieldText(each))]));
}
/* A selected join shows only itself, so nothing needs finding in its receiver's text. */
function renderJoin(join) {
  // A join has no name of its own, MAP-020: it is headed by the parts it joins, and its purpose and function are read
  // below as text.
  const called = id => S.elements.has(id) ? labelOf(S.elements.get(id).element) : null;
  const providers = (join.elements || []).map(each => called(each.element_id) || each.address).join(', ');
  fill($('#p-object'),
    h('div', {class: 'eyebrow'}, 'Join'),
    h('h2', {}, `${called(join.receiver) || join.receiver_address} ${flowArrow(join)} ${providers || join.provider_address}`),
    h('p', {class: 'meta'}, elementLink(join.receiver, join.receiver_address), ' receives from ',
      ...(join.elements || []).flatMap((each, at) => [at ? ', ' : '', elementLink(each.element_id, each.address)]), '.'),
    (join.open_work || []).length ? h('div', {class: 'pills'}, join.open_work.map(workPill)) : null,
    joinCard(join, 'provider'),
    h('div', {id: 'work'}));
  renderWork(`join:${join.id}`, 'p:' + join.id);
}
async function renderObject(id) {
  const {element} = S.elements.get(id);
  const pane = $('#p-object');
  const held = S.joins.filter(join => join.receiver === id), serves = S.joins.filter(join => join.providers.includes(id));
  // The heading is its short name, the address read through name_length, VIEW-009; what the project calls it and its
  // address follow, each with its label, so neither is taken for the other.
  fill(pane,
    h('div', {class: 'eyebrow'}, 'Element'),
    h('h2', {}, element.short_name || element.address),
    h('dl', {class: 'facts'},
      element.name ? [h('dt', {}, 'Project name'), h('dd', {class: 'canonical'}, element.name)] : null,
      h('dt', {}, 'Address'), h('dd', {class: 'addr'}, element.address)),
    h('div', {class: 'pills'}, element.role ? h('span', {class: 'pill'}, element.role) : null,
      (element.open_work || []).map(workPill), layerPill(element.layer),
      h('span', {class: 'pill'}, `${held.length} held · ${serves.length} served`)),
    h('button', {class: 'btn sm quiet tobrief', type: 'button', 'aria-controls': 'p-brief',
      title: 'The brief an agent working here is handed, and the memories, messages and work numbered here',
      onclick: () => { showTab('brief'); $('#t-brief').focus(); }}, 'What an agent reads here', h('i', {class: 'i i-chev', 'aria-hidden': 'true'})),
    h('div', {id: 'work'}),
    h('div', {id: 'items'}),
    h('div', {class: 'eyebrow'}, 'Joins held by this element'),
    held.length ? held.map(join => joinCard(join, 'provider')) : h('p', {class: 'empty'}, 'This element receives nothing here.'),
    serves.length ? h('div', {class: 'eyebrow'}, 'Serves') : null,
    serves.map(join => joinCard(join, 'receiver')));
  renderWork(`element:${id}`, id);
  try {
    // While the page follows an intake being recorded, the element is shown as the building layer records it; that
    // layer is in no reading context until it finishes, LAYER-007, so a node read could only find nothing and is not made.
    const node = following() ? {layers: []} : await read('node', {target: `element:${id}`, ...viewLayers()});
    if (S.selected !== id) return;
    const box = $('#items');
    for (const group of node.layers || []) {
      const items = group.items || [];
      if (!items.length) continue;
      box.append(h('div', {class: 'eyebrow'}, group.kind === 'memory' ? 'Memory' : group.layer),
        ...items.map(item => h('div', {class: 'item' + (item.orphaned ? ' orphaned' : ''), style: {'--c': `var(${colorVar(group.layer)})`}},
          itemView(item.value), item.state ? ` · ${item.state}` : '', refsOf(item.refs))));
    }
    // What the memory module adds to the node's read, as `map node` gives it, BASE-035: its one note, and while memory
    // shows here, the memories kept at it and those on the joins it receives and provides, LAYER-013 and VIEW-034.
    const memory = node.memory || {}, color = {'--c': `var(${colorVar(memoryLayer())})`};
    const remembered = entity => h('div', {class: 'item', style: color},
      h('a', {class: 'link', href: '#', onclick: event => { event.preventDefault(); select(memoryKey(entity.name), true); }}, entity.name),
      h('small', {}, ` · ${entity.entityType}`), entity.observations.map(text => h('p', {class: 'itemtext'}, text)));
    if (memory.note) box.append(h('div', {class: 'eyebrow'}, 'Note'), h('div', {class: 'item note', style: color},
      h('p', {class: 'itemtext'}, memory.note.text), h('small', {}, noteBy(memory.note))));
    if ((memory.entities || []).length) box.append(h('div', {class: 'eyebrow'}, 'Memory'), ...memory.entities.map(remembered),
      ...(memory.relations || []).map(relation => h('p', {class: 'meta'}, `${relation.from} ${relation.relationType} ${relation.to}`)));
    for (const join of memory.joins || []) box.append(h('div', {class: 'eyebrow'}, `Memory on ${join.receiver} → ${join.provider}`),
      ...join.entities.map(remembered));
    const context = await read('context', {address: element.address, limit: 0, ...viewLayers()});
    if (S.selected !== id) return;
    for (const [title, found] of [['Properties that apply here', context.applying], ['Properties attached toward the leaves', context.visible]]) {
      if (!found.length) continue;
      box.append(h('div', {class: 'eyebrow'}, title), ...found.map(property => h('div', {class: 'item', style: {'--c': `var(${colorVar(property.layer)})`}},
        itemText(property.value), h('div', {class: 'refs'}, `${property.layer}${property.address && property.address !== element.address ? ' · at ' + property.address : ''}`),
        refsOf(property.refs))));
    }
  } catch (error) {  // nothing in the layers turned on, such as an intake still being built, is not an error
    if (error.status !== 404) toast(error.message);
  }
}

/* ---------- the brief: what an agent reads about the selected node ----------
 * The node's brief, MCP-037, read from /api/brief, which runs the read the MCP server serves at metaform://<address>,
 * so the person sees what an agent working there is handed: the element, what relies on it and what it relies on,
 * the counts at it and around it, and its size against the node_summary_bytes setting. A join's items are numbered at
 * its receiver, so a join shows its receiver's brief. Below the brief, the memories, messages and work numbered at the
 * address, newest first, each #n with its title and why. One opened shows its text as an agent reads it at
 * metaform://<address>#<n>; its links to other memories, address#n, open those at their own node, so the memory graph
 * is walked item to item, and Back returns along the walk. An item numbered past the latest this browser was shown at
 * the address is marked unseen: this browser keeps the latest number the person saw at each address. (The agent's own
 * "New" in the brief is another thing: what the last agent session there recorded.) The list is read a page at a time
 * from /api/brief, the list the MCP server's views read too, paged as MCP pages a list: the nextCursor a page gives is
 * passed back unchanged for the next, and a kind chosen is filtered there, through the whole list. */
const BR = {address: null, generation: 0, data: null, kind: 'all', open: null, walk: [], seen: null, items: [],
  cursor: null, cache: new Map(), pending: null};
const BRIEF_SEEN = 'metaform.seen';  // the latest item shown at each address, kept in this browser
function seenAt(project) {
  try { return JSON.parse(localStorage.getItem(BRIEF_SEEN) || '{}')[project] || {}; } catch { return {}; }
}
function keepSeen() {  // the latest number shown at the address the brief is leaving
  if (!BR.address || !BR.data?.latest || !S.project) return;
  try {
    const all = JSON.parse(localStorage.getItem(BRIEF_SEEN) || '{}');
    all[S.project] = {...(all[S.project] || {}), [BR.address]: BR.data.latest.number};
    localStorage.setItem(BRIEF_SEEN, JSON.stringify(all));
  } catch { /* storage can be blocked: then nothing is marked new */ }
}
addEventListener('pagehide', keepSeen);
// each filter with the item kinds it asks /api/brief for, none for all
const ITEM_KINDS = {all: ['All', ''], memory: ['Memories', 'memory'], message: ['Messages', 'question,message'],
  work: ['Work', 'work'], decision: ['Decisions', 'decision'], code: ['Code', 'code']};
const kindAsked = () => ITEM_KINDS[BR.kind][1] ? {kind: ITEM_KINDS[BR.kind][1]} : {};
const hex = number => `#${Number(number).toString(16)}`;
const counted = (count, unit = 'bytes') => `${Number(count).toLocaleString('en')} ${unit}`;
const ITEM_REF = /([^\s#]+)#([0-9a-fA-F]{1,15})\b/;
function briefAddress(id = S.selected) {
  if (!id || MEM.key) return null;
  if (id.startsWith('p:')) return joinOf(id)?.receiver_address || null;
  return S.elements.get(id)?.element.address || null;
}
const elementAt = address => [...S.elements.values()].find(entry => entry.element.address === address)?.element || null;
/* A text to copy in one press, the clipboard where the browser gives one. */
function briefCopy(label, text, words = 'Copy') {
  return h('button', {class: 'btn sm quiet copy', type: 'button', 'aria-label': `Copy ${label}`, title: `Copy ${label}`,
    onclick: async () => {
      try { await navigator.clipboard.writeText(typeof text === 'function' ? await text() : text); toast('Copied.'); }
      catch { toast('The browser did not let the page copy it.'); }
    }}, h('i', {class: 'i i-copy', 'aria-hidden': 'true'}), words);
}
/* How much of what holds it a text takes: a bar with the count in words beside it, over the limit said in words too. */
function budgetMeter(label, used, budget, unit = 'bytes') {
  const share = budget ? used / budget : 0, over = budget && used > budget;
  const said = budget ? `${Number(used).toLocaleString('en')} of ${counted(budget, unit)}` : counted(used, unit);
  return h('div', {class: 'budget' + (over ? ' over' : ''), role: budget ? 'meter' : null, 'aria-label': label,
    'aria-valuemin': budget ? '0' : null, 'aria-valuemax': budget ? String(budget) : null,
    'aria-valuenow': budget ? String(Math.min(used, budget)) : null,
    'aria-valuetext': `${said}${over ? ', over the limit' : ''}`, style: {'--value': String(Math.min(1, share))}},
    budget ? h('div', {class: 'track'}, h('div', {class: 'fill'})) : null,
    h('div', {class: 'words'}, h('span', {}, label), h('span', {}, said, over ? ' · over' : '')));
}
/* An address in a brief as a link that selects its node on the map, keeping the brief on view; one the map does not
 * show is said as text. */
function addressLink(address, label = address) {
  const element = elementAt(address);
  if (!element) return h('code', {class: 'addr'}, label);
  return h('a', {class: 'link addr', href: '#', title: `Read the brief of ${labelOf(element)}`,
    onclick: event => { event.preventDefault(); briefTo(element.id); }}, label);
}
function briefTo(id, open = null) {
  BR.pending = open;
  select(id, true);
  requestAnimationFrame(() => $('#p-brief h2')?.focus({preventScroll: true}));  // the walk goes on in the brief
}
/* The brief's counts as the agent reads them, each address in them a link to its node. */
function linkedAddresses(text) {
  return String(text).split(/(\s+)/).map(word => elementAt(word) ? addressLink(word) : word);
}
/* The brief's tree of the node and its neighbours, as the agent reads it, each neighbour's line followed by the purpose
 * of its join, set apart as the page's: the brief's provides and receives say them, the tree does not. */
function aroundTree(brief) {
  const purposes = new Map();
  for (const one of brief.provides || []) if (one.purpose) purposes.set(one.receiver, one.purpose);
  for (const one of brief.receives || []) for (const provider of one.providers || []) if (one.purpose) purposes.set(provider, one.purpose);
  return String(brief.around).split('\n').flatMap((line, at) => {
    const named = line.match(/^\s*[├└]\s+(\S+)/)?.[1];
    const purpose = named && purposes.get(named);
    return [at ? '\n' : '', ...linkedAddresses(line), purpose ? h('span', {class: 'purpose'}, `  · ${purpose}`) : null];
  });
}
async function renderBrief() {
  const pane = $('#p-brief'), address = briefAddress();
  if (address !== BR.address) {
    keepSeen();
    Object.assign(BR, {address, data: null, items: [], cursor: null, open: BR.pending, pending: null,
      seen: address ? seenAt(S.project)[address] ?? null : null});
  }
  if (!address) {
    return fill(pane, h('p', {class: 'empty'}, noMetaform() ? noneYet()
      : 'Select an element on the map to read its brief: what an agent working there is handed.'));
  }
  const generation = ++BR.generation;
  if (!BR.data) fill(pane, h('p', {class: 'loading'}, 'Reading the brief…'));
  let data;
  try { data = await read('brief', {address, ...kindAsked()}); } catch (error) {
    if (generation === BR.generation) fill(pane, h('div', {class: 'eyebrow'}, 'Agent brief'), h('h2', {tabindex: '-1'}, address),
      refusalBox(error.body || {error: error.message}));
    return;
  }
  if (generation !== BR.generation || address !== briefAddress()) return;
  // a brief read again keeps the older items already listed below its newest page
  const lowest = data.items.length ? data.items.at(-1).number : 0;
  const older = BR.data && lowest ? BR.items.filter(item => item.number < lowest) : [];
  Object.assign(BR, {data, items: [...data.items, ...older], ...(older.length ? {} : {cursor: data.nextCursor ?? null})});
  drawBrief();
  if (BR.open && !BR.cache.has(BR.open)) openItem(BR.open, false);
}
function drawBrief() {
  const pane = $('#p-brief'), data = BR.data, brief = data.brief && typeof data.brief === 'object' ? data.brief : null;
  const element = brief?.element || {}, scroll = pane.scrollTop;
  const join = S.selected?.startsWith('p:') ? joinOf(S.selected) : null;
  fill(pane,
    h('div', {class: 'head'}, h('div', {class: 'eyebrow'}, 'Agent brief'),
      h('h2', {tabindex: '-1'}, element.name || element.short_name || data.address),
      h('div', {class: 'uri'}, h('code', {}, data.uri), briefCopy('the brief\'s address', data.uri, ''))),
    join ? h('p', {class: 'hint'}, 'A join\'s items are numbered at its receiver, so this is the receiver\'s brief.') : null,
    budgetMeter('Brief', data.bytes, data.budget),
    h('p', {class: 'hint'}, 'What an agent assigned here is handed, read as it reads it. Its size is held to the ',
      h('code', {}, 'node_summary_bytes'), ' setting.'),
    brief && (element.role || (element.open_work || []).length) ? h('div', {class: 'pills'},
      element.role ? h('span', {class: 'pill'}, element.role) : null, (element.open_work || []).map(workPill)) : null,
    brief?.around ? h('pre', {class: 'brieftext tree', tabindex: '0', 'aria-label': 'What is held at the node and around it, as the agent reads it, with each neighbour\'s purpose'},
      aroundTree(brief)) : null,
    !brief ? h('pre', {class: 'brieftext', tabindex: '0', 'aria-label': 'The brief, as the agent reads it'}, data.text) : null,
    itemsSection(),
    h('details', {class: 'sent'}, h('summary', {}, `Exactly as sent · ${counted(data.bytes)}`),
      h('pre', {class: 'brieftext raw', tabindex: '0', 'aria-label': 'The brief exactly as an agent receives it'}, data.text),
      briefCopy('the brief as sent', data.text)),
    FRAMED ? null : h('div', {class: 'acts'},
      h('button', {class: 'btn sm seeall', type: 'button', 'aria-controls': 'agentview',
        title: 'The connect message, the glossary with its tools, and this brief, each with its size', onclick: openAgentView},
        'What an agent sees…'),
      briefCopy('this node and its neighbours as Mermaid', () => mermaidText({address: data.address}), 'Copy as Mermaid')));
  pane.scrollTop = scroll;
}
function itemsSection() {
  const latest = BR.data.latest;
  const list = h('ul', {class: 'items', 'aria-label': 'The items numbered here, newest first'});
  const box = h('section', {class: 'itembox', 'aria-label': 'Items here'},
    h('div', {class: 'itemshead'}, h('div', {class: 'eyebrow'}, latest ? `Items here · newest ${hex(latest.number)}` : 'Items here'),
      segmented({label: 'Kinds of item shown', value: BR.kind, options: Object.entries(ITEM_KINDS).map(([value, [label]]) => ({value, label})),
        onchange: kind => { BR.kind = kind; itemsOfKind(list); }})),
    BR.walk.length ? h('nav', {class: 'walk', 'aria-label': 'The items walked to here'},
      h('button', {class: 'btn sm quiet', type: 'button', title: 'Back to the item walked from', onclick: walkBack},
        h('i', {class: 'i i-back', 'aria-hidden': 'true'}), 'Back'),
      h('span', {class: 'trail'}, [...BR.walk, BR.open].filter(Boolean).join(' → '))) : null,
    BR.seen === null && latest ? h('p', {class: 'hint'}, 'First look here in this browser: items numbered after now are marked unseen.') : null,
    newHere(latest, BR.data.last_session),
    list);
  drawItems(list);
  return box;
}
/* What is new at the node, as the brief's line under the node tells the agent, MCP-037: the latest item, its number
 * and title, opened with a click, and the range the last agent session numbered here, the same pointers on every
 * surface that shows the brief. */
function newHere(latest, last) {
  if (!latest) return null;
  const span = last ? (last.first === last.last ? hex(last.first) : `${hex(last.first)}–${hex(last.last)}`) : null;
  return h('dl', {class: 'newhere', 'aria-label': 'What is new here'},
    h('dt', {}, 'Latest'), h('dd', {}, h('button', {class: 'link', type: 'button', title: 'Open the latest item',
      onclick: () => openItem(latest.item)}, h('code', {}, hex(latest.number)), ' ', latest.title || 'untitled')),
    last ? [h('dt', {}, 'Last session'), h('dd', {title: `Session ${last.session}`}, h('code', {}, span),
      last.count !== last.last - last.first + 1 ? ` · ${last.count} of them` : '')] : null);
}
function drawItems(list = $('#p-brief ul.items')) {
  if (!list) return;
  const rows = BR.items.map(item => {
    const open = BR.open === item.item, fresh = BR.seen !== null && item.number > BR.seen;
    const id = `item-${item.number}`;
    return h('li', {class: 'itemrow' + (fresh ? ' new' : '') + (open ? ' open' : '')},
      h('button', {class: 'itemhead', type: 'button', 'aria-expanded': String(open), 'aria-controls': open ? id : null,
        onclick: () => openItem(item.item)},
        h('span', {class: 'num'}, hex(item.number)), h('span', {class: 'title'}, item.title || 'untitled'),
        h('span', {class: `pill kind-${item.kind}`}, item.kind), fresh ? h('span', {class: 'pill fresh', title: 'Numbered since this browser last showed you this node'}, 'unseen') : null),
      item.why ? h('p', {class: 'why'}, h('span', {class: 'k'}, 'why '), item.why) : null,
      open ? h('div', {class: 'itemopen', id}, itemDetail(item.item)) : null);
  });
  fill(list, rows.length ? rows : h('li', {class: 'empty'}, BR.kind !== 'all' && BR.data?.latest ? 'None of this kind is numbered here.'
    : 'Nothing is numbered here yet. A memory, a message or a ticket written here takes the next number.'),
  BR.cursor !== null ? h('li', {}, h('button', {class: 'btn sm quiet more', type: 'button', title: 'List the next items, older than these', onclick: olderItems},
    'Older')) : null);
}
async function olderItems() {
  const address = BR.address, kind = BR.kind;
  if (BR.cursor === null) return;
  let data;
  try { data = await read('brief', {address, cursor: BR.cursor, ...kindAsked()}); } catch (error) { return toast(error.message); }
  if (address !== BR.address || kind !== BR.kind) return;
  const first = BR.items.length;
  Object.assign(BR, {items: [...BR.items, ...data.items], cursor: data.nextCursor ?? null});
  drawItems();
  // the button is gone with the page it closed: the keyboard goes on from the first item read
  document.querySelectorAll('#p-brief ul.items .itemrow .itemhead')[first]?.focus();
}
/* Another kind chosen: its first page read from the whole list, not filtered from the pages already here. */
async function itemsOfKind(list) {
  const address = BR.address, kind = BR.kind;
  list.setAttribute('aria-busy', 'true');
  let data;
  try { data = await read('brief', {address, ...kindAsked()}); } catch (error) { list.removeAttribute('aria-busy'); return toast(error.message); }
  if (address !== BR.address || kind !== BR.kind) return;
  list.removeAttribute('aria-busy');
  Object.assign(BR, {items: data.items, cursor: data.nextCursor ?? null});
  drawItems(list);
}
/* One item as an agent reads it at metaform://<address>#<n>: read once, kept while the page is open. */
async function openItem(ref, toggle = true) {
  if (toggle && BR.open === ref) { BR.open = null; drawItems(); return; }
  BR.open = ref;
  drawItems();
  if (!BR.cache.has(ref)) {
    try { BR.cache.set(ref, await read('item', {item: ref})); } catch (error) { BR.cache.set(ref, {error: error.message}); }
    if (BR.open === ref) drawItems();
  }
  $('#p-brief .itemrow.open')?.scrollIntoView({block: 'nearest'});
}
function itemDetail(ref) {
  const found = BR.cache.get(ref);
  if (!found) return h('p', {class: 'loading'}, 'Reading the item…');
  if (found.error) return h('p', {class: 'empty'}, found.error);
  const links = (found.links || []).map(link => {
    const match = ITEM_REF.exec(String(link));
    if (!match) return h('li', {}, String(link));
    const [whole, address] = match, before = String(link).slice(0, match.index), after = String(link).slice(match.index + whole.length);
    return h('li', {}, before, h('a', {class: 'link addr', href: '#', title: `Open ${whole}`,
      onclick: event => { event.preventDefault(); walkTo(`${address}#${match[2].toLowerCase()}`); }}, whole), after);
  });
  return [
    found.body ? h('pre', {class: 'itemtext', tabindex: '0', 'aria-label': `What ${ref} holds`}, found.body) : null,
    links.length ? h('div', {class: 'eyebrow'}, 'Links') : null, links.length ? h('ul', {class: 'links'}, links) : null,
    h('details', {class: 'sent'}, h('summary', {}, `As an agent reads metaform://${ref}`),
      h('pre', {class: 'brieftext raw', tabindex: '0', 'aria-label': `${ref} exactly as an agent reads it`}, found.text),
      briefCopy(`${ref} as an agent reads it`, found.text))];
}
/* A link from one memory to another followed: the item at its own node, the walk kept for Back. */
function walkTo(ref, back = false) {
  if (!back && BR.open) BR.walk.push(BR.open);
  const address = ref.slice(0, ref.lastIndexOf('#'));
  if (address === BR.address) { openItem(ref, false); drawBrief(); return; }
  const element = elementAt(address);
  if (element) { briefTo(element.id, ref); return; }
  toast(`${address} is not on the map in these layers.`);
}
function walkBack() {
  const ref = BR.walk.pop();
  if (ref) walkTo(ref, true);
}

/* ---------- what an agent connecting here receives ----------
 * Read from the project folder's own MCP server over MCP, as the MCP Inspector reads a server, by /api/agent-view:
 * the instructions sent at connect with the capabilities discover gave, metaform://metaform and metaform://tools, every
 * tool, resource, resource template and prompt the lists give, each entry as received and its size, and the selected
 * node's brief; the connect message against the characters Claude Code keeps of a server's instructions, the brief
 * against node_summary_bytes. What is paid before the first call is said both ways a host loads tools: deferred behind
 * tool search, Claude Code's default, where the names come first, or every tool up front. */
const AV = {generation: 0, tab: 'connect', data: null};
const AV_TABS = [['connect', 'Connect'], ['glossary', 'Glossary'], ['tools', 'Tools'], ['resources', 'Resources'],
  ['prompts', 'Prompts'], ['brief', 'Brief']];
async function openAgentView() {
  showAgentMenu(false);
  if (WS.reveal('agent-view')) return;  // a pane in the workspace: it shows there and reads as it shows
  $('#agentview').hidden = false;
  await readAgentView();
}
async function readAgentView() {
  const body = $('#agentview .body'), generation = ++AV.generation, address = briefAddress();
  fill(body, h('p', {class: 'loading', role: 'status'}, 'Starting this project\'s MCP server and reading it as an agent does…'));
  let data;
  try { data = await read('agent-view', address ? {address} : {}); } catch (error) {
    if (generation === AV.generation) fill(body, refusalBox(error.body || {error: error.message}));
    return;
  }
  if (generation !== AV.generation) return;
  AV.data = {...data, address};
  drawAgentView();
}
function drawAgentView() {
  const data = AV.data, body = $('#agentview .body');
  const tabs = h('div', {class: 'tabs views', role: 'tablist', 'aria-label': 'What the agent receives'});
  const panel = h('div', {class: 'view', role: 'tabpanel', tabindex: '0'});
  const sizes = {connect: counted(data.connect.chars, 'chars'), glossary: counted(data.glossary.bytes),
    tools: String(data.tools.length), resources: String(data.resources.length + data.templates.length),
    prompts: String(data.prompts.length), brief: data.brief ? counted(data.brief.bytes) : '–'};
  const show = key => {
    AV.tab = key;
    for (const button of tabs.children) {
      const on = button.dataset.tab === key;
      button.setAttribute('aria-selected', String(on));
      button.tabIndex = on ? 0 : -1;
    }
    panel.setAttribute('aria-labelledby', `av-${key}`);
    fill(panel, agentPart(key));
  };
  for (const [key, label] of AV_TABS) tabs.append(h('button', {role: 'tab', type: 'button', id: `av-${key}`, 'data-tab': key,
    'aria-controls': 'av-panel', onclick: () => show(key)}, label, h('small', {}, sizes[key])));
  panel.id = 'av-panel';
  tabs.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const keys = AV_TABS.map(([key]) => key), at = keys.indexOf(AV.tab);
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? keys.length - 1
      : (at + (event.key === 'ArrowRight' ? 1 : -1) + keys.length) % keys.length;
    show(keys[next]);
    tabs.children[next].focus();
  });
  const paid = data.paid;
  fill(body, h('p', {class: 'lead'}, 'Read now from this project\'s MCP server, as an agent connecting to it reads it. Only the connect message is pushed; the rest is read when the agent asks.'),
    h('dl', {class: 'paid', 'aria-label': 'What an agent pays before its first call, in bytes as Claude Code sends them to the model'},
      h('dt', {}, 'With tool search'), h('dd', {}, counted(paid.deferred), h('small', {}, ` connect message, the tool names as mcp__${paid.server}__<tool>, and any tool marked to load up front, as Claude Code loads tools by default`)),
      h('dt', {}, 'Tools loaded as asked'), h('dd', {}, counted(paid.loaded), h('small', {}, ' the same with every tool loaded, as the connect message asks the agent to make sure of')),
      h('dt', {}, 'Without it'), h('dd', {}, counted(paid.upfront), h('small', {}, ' connect message and every tool in full: its name, description and input schema')),
      h('dt', {}, 'Then the glossary'), h('dd', {}, counted(paid.glossary), h('small', {}, ` metaform://metaform, read once, as the connect message asks; metaform://tools, ${counted(data.glossary.index.bytes)}, read only where tools are listed by name`))),
    tabs, panel);
  show(AV.tab);
}
/* One entry of a list as the server gave it: its name, size and first line, opened to the entry as received. */
function entryRow(name, bytes, said, entry, marks = []) {
  return h('li', {}, h('details', {class: 'entry' + (marks.includes('over') ? ' over' : '')},
    h('summary', {}, h('code', {}, name), h('span', {class: 'n'}, counted(bytes)),
      ...marks.filter(Boolean).map(mark => h('span', {class: 'pill'}, mark)), h('span', {class: 'said'}, said)),
    h('pre', {class: 'brieftext raw', tabindex: '0', 'aria-label': `${name} as the server gives it`}, JSON.stringify(entry, null, 2))));
}
function agentPart(key) {
  const data = AV.data, text = (label, value) => h('pre', {class: 'brieftext raw', tabindex: '0', 'aria-label': label}, value);
  if (key === 'connect') return [
    budgetMeter('Connect message', data.connect.chars, data.host_limit, 'characters'),
    h('p', {class: 'hint'}, `Capabilities: ${Object.entries(data.capabilities).map(([name, held]) => name === 'extensions' && held && typeof held === 'object'
      ? `extensions (${Object.keys(held).join(', ') || 'none'})` : name).join(', ') || 'none'} · protocol ${data.protocol.join(', ')}${data.server ? ` · ${data.server.name} ${data.server.version || ''}` : ''}`),
    h('p', {class: 'hint'}, `The server's instructions, sent once as the agent connects. Claude Code keeps the first ${counted(data.host_limit, 'characters')} of them.`),
    text('The connect message', data.connect.text), briefCopy('the connect message', data.connect.text)];
  if (key === 'glossary') return [
    budgetMeter('metaform://metaform', data.glossary.bytes, 0),
    budgetMeter('metaform://tools, one line per tool, read apart where tools are listed by name', data.glossary.index.bytes, 0),
    h('p', {class: 'hint'}, 'The terms and rules, then one line per tool: read once, when the connect message tells the agent to.'),
    text('metaform://metaform', data.glossary.text), briefCopy('the glossary', data.glossary.text), text('metaform://tools', data.glossary.index.text)];
  if (key === 'tools') {
    const long = data.tools.filter(tool => tool.description.length > data.host_limit);
    return [
      budgetMeter(`${data.tools.length} tools, with their schemas`, data.tool_bytes, 0),
      h('p', {class: 'hint'}, 'Each tool as tools/list gives it, largest first. With tool search an agent is handed the names and loads a tool\'s description and schema when it needs the tool; a tool marked to load up front is handed whole.'),
      long.length ? h('p', {class: 'warnline'}, `${long.length} description(s) run past the ${counted(data.host_limit, 'characters')} Claude Code keeps.`) : null,
      h('ul', {class: 'entries', 'aria-label': 'Every tool, largest first'}, data.tools.map(tool => entryRow(tool.name, tool.bytes, tool.description.split(/(?<=\.)\s/)[0], tool.entry,
        [tool.description.length > data.host_limit ? 'over' : '', tool.always ? 'up front' : ''])))];
  }
  if (key === 'resources') return [
    h('p', {class: 'hint'}, 'What an agent can read, as resources/list and resources/templates/list give them. It learns of metaform://metaform, metaform://tools and metaform://<address> here.'),
    h('div', {class: 'eyebrow'}, `Resources · ${data.resources.length}`),
    h('ul', {class: 'entries'}, data.resources.map(one => entryRow(one.entry.uri, one.bytes, one.entry.description || one.entry.name || '', one.entry))),
    h('div', {class: 'eyebrow'}, `Templates · ${data.templates.length}`),
    h('ul', {class: 'entries'}, data.templates.map(one => entryRow(one.entry.uriTemplate, one.bytes, one.entry.description || one.entry.name || '', one.entry)))];
  if (key === 'prompts') return [
    h('p', {class: 'hint'}, 'The prompts the server offers, as prompts/list gives them: the host shows each as a slash command the person runs.'),
    data.prompts.length ? h('ul', {class: 'entries'}, data.prompts.map(one => entryRow(one.entry.name, one.bytes, one.entry.description || '', one.entry)))
      : h('p', {class: 'empty'}, 'This server offers no prompts.')];
  if (!data.brief) return h('p', {class: 'empty'}, 'Select an element on the map, then read again, to see the brief an agent working there is handed.');
  return [
    budgetMeter(`metaform://${data.address}`, data.brief.bytes, data.budget),
    h('p', {class: 'hint'}, 'Handed to an agent assigned to this node, and read by any agent at its address.'),
    text('The brief', data.brief.text), briefCopy('the brief', data.brief.text)];
}
$('#agentViewBtn').onclick = openAgentView;
$('#agentview .close').onclick = () => { $('#agentview').hidden = true; };
$('#agentview .again').onclick = readAgentView;
overlay($('#agentview'), {kind: 'dialog', close: () => { $('#agentview').hidden = true; }, focus: () => $('#agentview [role=tab][aria-selected=true]') || $('#agentview .again')});

/* ---------- provenance ---------- */
let provLayer = null;
async function renderProv() {
  const pane = $('#p-prov');
  if (noMetaform()) return fill(pane, h('p', {class: 'empty'}, noneYet()));
  provLayer = provLayer && S.layers.some(layer => layer.name === provLayer) ? provLayer : S.layers[0]?.name;
  const list = h('div', {class: 'layerlist'}, S.layers.map(layer => h('button', {'aria-pressed': String(layer.name === provLayer),
    style: {'--c': `var(${colorVar(layer.name)})`}, onclick: () => { provLayer = layer.name; renderProv(); }},
    h('span', {style: {display: 'flex', gap: '8px', 'align-items': 'center'}}, h('i', {class: 'sw'}), layer.name),
    h('span', {class: 'pill'}, layer.kind))));
  if (!S.layers.length) return fill(pane, h('p', {class: 'empty'}, 'No layer is recorded in this metaform yet.'));
  fill(pane, h('div', {class: 'eyebrow'}, 'Layers in this metaform'), list);
  if (!provLayer) return;
  const layer = S.layers.find(item => item.name === provLayer);
  // One list of facts for the layer, those its provenance record adds joining it, so every label lines up.
  const facts = h('dl', {class: 'prov'}, ...[['kind', layer.kind], ['module', layer.module], ['created', layer.created],
    ['state', layer.ready ? `ready ${layer.ready}` : 'building'], ['tags', (layer.tags || []).join(', ') || 'none'],
    ['holds', layer.variable]].filter(([, value]) => value !== undefined && value !== null && value !== '')
    .flatMap(([key, value]) => [h('dt', {}, key), h('dd', {}, value)]));
  pane.append(h('div', {class: 'eyebrow'}, 'How it was made'), h('h2', {}, layer.name), facts);
  if (layer.kind === 'memory') return pane.append(h('p', {class: 'empty'}, 'Memory has no provenance. Agents write it freely.'));
  try {
    const record = await read('provenance', {layer: layer.name});
    if (provLayer !== layer.name) return;
    const reports = (record.refs || []).map(ref => `${ref.key}: ${ref.value}`);
    facts.append(...[['workflow', record.workflow], ['model', record.model], ['role', record.role],
      ['blinded', record.blinded === null ? '' : record.blinded ? 'yes' : 'no'], ['reports', reports.join(' · ') || 'none']]
      .flatMap(([key, value]) => [h('dt', {}, key), h('dd', {}, value || 'not recorded')]));
    if (record.prompt_version) pane.append(h('div', {class: 'toolbar'}, h('button', {class: 'btn primary open-prompt', type: 'button',
      onclick: () => { showTab('prompt'); renderPrompt(record.prompt_version.name, record.prompt_version.number); }},
      `Open prompt ${record.prompt_version.name}, version ${record.prompt_version.number}`)));
    if (record.prompt) pane.append(h('details', {}, h('summary', {class: 'eyebrow'}, 'The prompt as it was delivered'),
      h('pre', {class: 'prompt'}, record.prompt)));
  } catch (error) { pane.append(h('p', {class: 'failed', role: 'alert'}, error.message)); }
}

/* ---------- prompts: edited in a real editor, saved as a new version, VIEW-013 ---------- */
const P = {editor: null, name: null, number: null, versions: [], asked: 0};
async function getJson(path) {
  const response = await reach(path, {headers: {Accept: 'application/json'}});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `${path} failed`);
  return body;
}
async function renderPrompt(name = P.name, number = P.number) {
  // only the last one asked for is shown: opening a layer's prompt asks twice, and an earlier read coming back after
  // the person has typed would put the stored text back
  const asked = ++P.asked;
  const listed = (await getJson('/api/prompts')).prompts;
  if (asked !== P.asked) return;
  // With no stored prompt there is nothing to choose or edit, so only that is said.
  $('#p-prompt .toolbar').hidden = !listed.length;
  if (!P.editor) $('#editor').hidden = !listed.length;
  if (!listed.length) {
    $('#promptNote').textContent = 'No stored prompts yet. The intake stores its prompt the first time it is served.';
    return;
  }
  const chosen = listed.some(item => item.name === name) ? name : listed[0].name;
  const versions = (await getJson(`/api/prompt-versions?name=${encodeURIComponent(chosen)}`)).versions;
  if (asked !== P.asked) return;
  P.name = chosen;
  P.versions = versions;
  P.number = P.versions.some(item => item.number === number) ? number : P.versions[0].number;
  fill($('#promptSel'), listed.map(item => h('option', {value: item.name, selected: item.name === P.name}, item.name)));
  fill($('#verSel'), P.versions.map(item => h('option', {value: String(item.number), selected: item.number === P.number},
    `version ${item.number} · ${item.origin} · ${item.created}`)));
  const version = P.versions.find(item => item.number === P.number);
  if (!P.editor) P.editor = CodeMirror.fromTextArea($('#editor'), {lineNumbers: true, lineWrapping: true});
  P.editor.setOption('mode', version.format === 'markdown' ? 'markdown' : version.format === 'xml' ? 'xml' : null);
  P.editor.setValue(version.text);
  P.editor.clearHistory();
  $('#diffOut').hidden = true;
  const names = new Map(S.layers.map(layer => [layer.id, layer.name]));
  const made = version.layers.map(use => names.get(use.layer_id) || `a layer of ${use.project_id}`);
  $('#promptNote').textContent = made.length ? `Version ${version.number} made: ${made.join(', ')}.`
    : `No layer was made with version ${version.number}.`;
  setTimeout(() => P.editor.refresh(), 0);
}
$('#promptSel').onchange = () => renderPrompt($('#promptSel').value, null);
$('#verSel').onchange = () => renderPrompt(P.name, Number($('#verSel').value));
function lineDiff(a, b) {
  a = a.split('\n'); b = b.split('\n');
  const n = a.length, m = b.length;
  if (n * m > 4e6) return [{t: 'gap', s: 'Too large to compare here.'}];
  const dp = Array.from({length: n + 1}, () => new Uint32Array(m + 1));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const out = []; let i = 0, j = 0;
  while (i < n && j < m) { if (a[i] === b[j]) { out.push({t: 'same', s: a[i]}); i++; j++; } else if (dp[i + 1][j] >= dp[i][j + 1]) out.push({t: 'del', s: a[i++]}); else out.push({t: 'add', s: b[j++]}); }
  while (i < n) out.push({t: 'del', s: a[i++]});
  while (j < m) out.push({t: 'add', s: b[j++]});
  const keep = new Set();
  out.forEach((row, k) => { if (row.t !== 'same') for (let d = -2; d <= 2; d++) keep.add(k + d); });
  const shown = []; let skipped = false;
  out.forEach((row, k) => { if (keep.has(k)) { shown.push(row); skipped = false; } else if (!skipped) { shown.push({t: 'gap', s: '···'}); skipped = true; } });
  return shown;
}
function showDiff() {
  const base = P.versions.find(item => item.number === P.number).text;
  const rows = lineDiff(base, P.editor.getValue());
  const changed = rows.some(row => row.t === 'add' || row.t === 'del');
  fill($('#diffOut'), changed ? rows.map(row => h('div', {class: row.t}, (row.t === 'add' ? '+ ' : row.t === 'del' ? '- ' : '  ') + row.s))
    : h('div', {class: 'gap'}, `No changes from version ${P.number}.`));
  $('#diffOut').hidden = false;
  return changed;
}
$('#diffBtn').onclick = showDiff;
$('#saveBtn').onclick = async () => {
  if (!showDiff()) return toast(`Nothing to save. The text matches version ${P.number}.`);
  const response = await fetch('/api/save-prompt', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name: P.name, text: P.editor.getValue(), parent: P.number})});
  const saved = await response.json().catch(() => ({}));
  if (!response.ok) return toast(saved.error || 'The prompt was not saved.');
  await renderPrompt(P.name, saved.number);
  toast(`Saved as version ${saved.number}. Layers made with earlier versions still show the version that made them.`);
};

/* ---------- tabs ---------- */
/* The panel's tabs, as tabs are: the open one is in the Tab order, and Left and Right move between them. */
const TABS = {object: '#p-object', brief: '#p-brief', prov: '#p-prov', prompt: '#p-prompt'};
const tabNow = () => WS.on ? (WS.isShown('map.brief') ? 'brief' : 'object')
  : Object.keys(TABS).find(key => $('#t-' + key).getAttribute('aria-selected') === 'true') || 'object';
function showTab(tab) {
  if (tab !== 'prompt' && $('#p-prompt').classList.contains('full')) promptFull(false);
  if (WS.on) WS.reveal(TAB_VIEWS[tab]);  // a pane of the workspace, opened where the person put it
  else for (const [key, selector] of Object.entries(TABS)) {
    $(selector).hidden = key !== tab;
    $('#t-' + key).setAttribute('aria-selected', String(key === tab));
    $('#t-' + key).tabIndex = key === tab ? 0 : -1;
  }
  if (tab === 'prov') renderProv();
  if (tab === 'brief') renderBrief();
  if (tab === 'prompt' && !P.editor) renderPrompt();
  if (tab === 'prompt' && P.editor) setTimeout(() => P.editor.refresh(), 0);
}
for (const key of Object.keys(TABS)) $('#t-' + key).onclick = () => showTab(key);
$('.tabs[role=tablist]').addEventListener('keydown', event => {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  event.preventDefault();
  // in the order the tabs stand, which the panes' declarations set, `nodeTabs`
  const keys = [...$('.tabs[role=tablist]').children].filter(tab => !tab.hidden).map(tab => tab.id.slice(2));
  const at = keys.findIndex(key => $('#t-' + key).getAttribute('aria-selected') === 'true');
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? keys.length - 1
    : (at + (event.key === 'ArrowRight' ? 1 : -1) + keys.length) % keys.length;
  showTab(keys[next]);
  $('#t-' + keys[next]).focus();
});
/* The node's tabs are the panes declared in the node group, one list: the map module's Object, Brief and Provenance
 * and the chassis's Prompt, each a view the page draws, `page=`, in the order, with the titles and descriptions, the
 * declarations and the person's layout give them in /api/workspace. A pane turned off there leaves the strip, unless
 * it is the tab on view. Without the workspace, the strip stays as the page is written. */
const TAB_PAGES = {object: 'object', brief: 'brief', provenance: 'prov', prompt: 'prompt'};
async function nodeTabs() {
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
function classicTabs(panes, tabs, off) {
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
  for (const [key, selector] of Object.entries(TABS)) {
    $(selector).hidden = key !== now;
    $('#t-' + key).setAttribute('aria-selected', String(key === now));
    $('#t-' + key).tabIndex = key === now ? 0 : -1;
  }
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

/* ---------- search: find a part, a join or what a layer holds, and go to it ----------
 * The parts and joins drawn are matched in the page as each letter is typed, by every word of what is typed, each the
 * start of a word of the name, the short name, the address, or the join's purpose and function; the layers' items are
 * found by the store's own search, /api/search, read with the layers in view, VIEW-004, a moment after the typing
 * stops. A result chosen is selected in both views and the cameras go to it, as a click on it does. */
const SEARCH = {generation: 0, results: [], active: -1, timer: null, items: []};
const wordsOf = text => String(text || '').toLowerCase().split(/[^\p{L}\p{N}]+/u).filter(Boolean);
function matchScore(query, fields) {
  const wanted = wordsOf(query);
  if (!wanted.length) return 0;
  let score = 0;
  for (const word of wanted) {
    let best = 0;
    fields.forEach((field, rank) => {
      const have = wordsOf(field);
      if (have.includes(word)) best = Math.max(best, 6 - rank);
      else if (have.some(one => one.startsWith(word))) best = Math.max(best, 4 - rank);
    });
    if (!best) return 0;
    score += best;
  }
  const first = String(fields[0] || '').toLowerCase();
  return score + (first.startsWith(query.trim().toLowerCase()) ? 5 : 0);
}
function searchParts(query) {
  const parts = [...S.elements.values()].map(({element}) => ({key: element.id, kind: 'Part', name: labelOf(element),
    where: element.address, layer: element.layer,
    score: matchScore(query, [labelOf(element), element.short_name, element.address])}));
  const joins = S.joins.map(join => {
    const receiver = S.elements.get(join.receiver)?.element, provider = S.elements.get(join.provider)?.element;
    const ends = `${receiver ? labelOf(receiver) : join.receiver_address} ${flowArrow(join)} ${provider ? labelOf(provider) : join.provider_address || ''}`;
    return {key: 'p:' + join.id, kind: 'Join', name: join.purpose || ends, where: ends, layer: join.layer,
      score: matchScore(query, [join.purpose, join.ef, ends])};
  });
  const best = list => list.filter(one => one.score > 0).sort((one, two) => two.score - one.score || one.name.localeCompare(two.name)).slice(0, 8);
  return [...best(parts), ...best(joins)];
}
/* A name with the words that matched marked, built as text, never as markup. */
function marked(text, query) {
  const wanted = wordsOf(query);
  const parts = String(text).split(/([^\p{L}\p{N}]+)/u);
  return parts.map(part => wanted.some(word => part.toLowerCase().startsWith(word)) && part ? h('mark', {}, part) : part);
}
function drawSearch(query) {
  const box = $('#searchResults'), input = $('#search .query');
  const results = SEARCH.results = [...searchParts(query), ...SEARCH.items];
  SEARCH.active = results.length ? Math.min(Math.max(SEARCH.active, 0), results.length - 1) : -1;
  const row = (one, index) => h('div', {role: 'option', id: `found${index}`, 'aria-selected': String(index === SEARCH.active),
    style: {'--c': `var(${colorVar(one.layer)})`}, onpointermove: () => { if (SEARCH.active !== index) { SEARCH.active = index; paintSearch(); } },
    onclick: () => chooseFound(index)}, h('i'), h('span', {class: 'name'}, ...marked(one.name, query)),
    h('span', {class: 'where'}, one.where), h('span', {class: 'kind'}, one.kind));
  const groups = ['Part', 'Join', 'Item'].map(kind => [kind, results.map((one, index) => [one, index]).filter(([one]) => one.kind === kind)]);
  fill(box, !query.trim() ? h('p', {class: 'empty'}, 'Type a name, an address or words of a purpose.')
    : !results.length ? h('p', {class: SEARCH.pending ? 'loading' : 'empty'}, SEARCH.pending ? 'Searching the layers…' : `Nothing in view matches ${query.trim()}.`)
    : groups.filter(([, found]) => found.length).map(([kind, found]) => [
      h('div', {class: 'group', role: 'presentation'}, {Part: 'Parts', Join: 'Joins', Item: 'In the layers'}[kind]),
      found.map(([one, index]) => row(one, index))]));
  paintSearch();
  input.setAttribute('aria-expanded', String(results.length > 0));
}
function paintSearch() {
  const input = $('#search .query');
  for (const option of $('#searchResults').querySelectorAll('[role=option]')) {
    const on = option.id === `found${SEARCH.active}`;
    option.setAttribute('aria-selected', String(on));
    if (on) option.scrollIntoView({block: 'nearest'});
  }
  if (SEARCH.active >= 0) input.setAttribute('aria-activedescendant', `found${SEARCH.active}`);
  else input.removeAttribute('aria-activedescendant');
}
/* The layers' items, read from the store a moment after the typing stops; an answer for older words is dropped. */
function searchItems(query) {
  clearTimeout(SEARCH.timer);
  const generation = ++SEARCH.generation;
  SEARCH.items = [];
  SEARCH.pending = Boolean(query.trim()) && !noMetaform();
  if (!SEARCH.pending) return;
  SEARCH.timer = setTimeout(async () => {
    let found = [];
    try { found = (await read('search', {text: query, limit: 8, ...viewLayers()})).results || []; } catch (error) { found = []; }
    if (generation !== SEARCH.generation) return;
    SEARCH.pending = false;
    SEARCH.items = found.map(item => {
      const at = item.target ? (item.target.kind === 'join' ? 'p:' + item.target.id : item.target.id) : null;
      const drawn = S.items.has('i:' + item.id) ? 'i:' + item.id : null;
      return {key: drawn || at, kind: 'Item', name: itemText(item.value).split('\n')[0].slice(0, 140) || item.id,
        where: `${item.layer}${at ? ' · at ' + nameOf(at, at) : ''}`, layer: item.layer};
    }).filter(one => one.key);
    drawSearch($('#search .query').value);
  }, 180);
}
function chooseFound(index) {
  const one = SEARCH.results[index];
  if (!one) return;
  $('#search').hidden = true;
  closed($('#search'));  // closed now, so the selection below finds the focus out of it and gives it to the map
  select(one.key, true);
}
function openSearch() {
  const input = $('#search .query');
  input.value = '';
  SEARCH.active = -1;
  SEARCH.items = [];
  SEARCH.pending = false;
  drawSearch('');
  $('#search').hidden = false;
  input.focus();
}
overlay($('#search'), {kind: 'dialog', focus: '.query'});
$('#searchBtn').onclick = openSearch;
$('#search .query').addEventListener('input', event => {
  SEARCH.active = 0;
  searchItems(event.target.value);
  drawSearch(event.target.value);
});
$('#search .query').addEventListener('keydown', event => {
  const count = SEARCH.results.length;
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault();
    if (!count) return;
    SEARCH.active = (SEARCH.active + (event.key === 'ArrowDown' ? 1 : -1) + count) % count;
    paintSearch();
  } else if (event.key === 'Enter') {
    event.preventDefault();
    chooseFound(SEARCH.active);
  }
});

/* ---------- the agents a person starts: one list, from the dispatch module, VIEW-039 ----------
 * Which agents there are, which of them this machine can run, which is the default and how many more may be summoned
 * now are the dispatch module's answer, `GET /api/dispatch-agents`; the page keeps no list of its own. Every place an
 * agent is started offers the same picker: an agent not found is shown with how to set it up, the default is marked,
 * and the star beside the picker makes the chosen agent the default in one click. */
const HARNESS = {project: null, enabled: null, default: null, room: null, agents: [], next: null, error: null,
  reading: null, read: 0, pickers: new Set()};
const SUMMON = {agent: null, chosen: false};  // the agent new chats, issues and intakes start with; none chosen is the default
async function readHarnesses() {
  const project = S.project;
  if (!project || FRAMED) return HARNESS;
  if (HARNESS.reading && HARNESS.project === project) return HARNESS.reading;
  const reading = HARNESS.reading = (async () => {
    try {
      const found = await getJson(`/api/dispatch-agents?project=${encodeURIComponent(project)}`);
      if (S.project === project) {
        Object.assign(HARNESS, {project, enabled: found.enabled !== false, default: found.default ?? null,
          room: found.room ?? null, agents: found.agents || [], next: found.next || null, error: null, read: Date.now()});
        if (!$('#board').hidden) drawBoard();  // a card's own agent select lists them too
      }
    } catch (error) {
      if (S.project === project) Object.assign(HARNESS, {project, error: error.message, read: Date.now()});
    }
    paintPickers();
    return HARNESS;
  })();
  HARNESS.project = project;
  try { return await reading; } finally { if (HARNESS.reading === reading) HARNESS.reading = null; }
}
function forgetHarnesses() {
  Object.assign(HARNESS, {project: null, enabled: null, default: null, room: null, agents: [], next: null, error: null,
    reading: null, read: 0});
  Object.assign(SUMMON, {agent: null, chosen: false});
  paintPickers();
}
const harness = agent => HARNESS.agents.find(one => one.agent === agent) || null;
const agentName = agent => harness(agent)?.label || agent || 'An agent';
/* The agent a start uses when the person has chosen none: the one offered when this machine runs it, else the
 * default, else the first it runs. An agent the person chose stays chosen, found or not, so nothing they did not
 * choose is started in its place. */
function usableAgent(chosen) {
  const found = [chosen, HARNESS.default].map(harness).find(one => one?.available);
  return found?.agent || HARNESS.agents.find(one => one.available)?.agent || chosen || HARNESS.default || null;
}
function paintPickers() {
  for (const box of HARNESS.pickers) {
    if (box.isConnected || box.kept) box.paint(); else HARNESS.pickers.delete(box);
  }
}
/* Make one agent the default, kept as `metaform set --dispatch-agent` keeps it; Undo gives the one before back. */
async function makeDefault(agent, {undo = true} = {}) {
  const before = HARNESS.default;
  if (!agent || agent === before) return false;
  const saved = await wrote('/api/dispatch-agents', {default: agent});
  if (!saved) return false;
  Object.assign(HARNESS, {enabled: saved.enabled !== false, default: saved.default ?? agent, room: saved.room ?? HARNESS.room,
    agents: saved.agents || HARNESS.agents, read: Date.now()});
  paintPickers();
  const said = `${agentName(agent)} is the default agent.`;
  if (undo && before) undoable(said, () => makeDefault(before, {undo: false}));
  else toast(said);
  return true;
}
/* The picker. `holder` keeps its choice, {agent, chosen}, so pickers that share one, as the starts that summon an agent
 * do, show the same; `chosen` says the person picked it, and an agent only offered, the default or a ticket's area's,
 * gives way to one this machine runs. `room` says how many more agents may be summoned now, `star` offers to make the
 * chosen agent the default, `up` opens the list upward. `kept`: the picker lives on outside the page, moved into each
 * form that shows it. `exact` shows the agent held as it is, found or not, as the default itself is shown. */
function agentPicker({label = 'Agent', holder = null, onchange = null, room = false, star = true, up = false,
  kept = false, exact = false} = {}) {
  const slot = holder || {agent: null, chosen: false};
  const pick = choice({label, options: [], value: null, onchange: value => {
    Object.assign(slot, {agent: value, chosen: true}); paintPickers(); onchange?.(value); }});
  if (up) pick.classList.add('up');
  const make = h('button', {class: 'btn icon quiet star', type: 'button', 'aria-pressed': 'false',
    onclick: () => makeDefault(box.value())}, h('i', {class: 'i i-star', 'aria-hidden': 'true'}));
  const note = h('small', {class: 'pickernote'});
  const box = h('div', {class: 'agentpicker'}, h('div', {class: 'pickerrow'}, pick, star ? make : null), note);
  box.kept = kept;
  let held = false;  // while what it starts is being started, the choice waits
  box.hold = on => { held = on; box.paint(); };
  box.set = value => { Object.assign(slot, {agent: value, chosen: false}); box.paint(); };  // offered, not chosen
  box.value = () => HARNESS.enabled === false ? null : exact || slot.chosen ? slot.agent : usableAgent(slot.agent);
  box.paint = () => {
    const off = HARNESS.enabled === false, none = !off && HARNESS.project && !HARNESS.agents.some(one => one.available);
    pick.hidden = off;
    const options = HARNESS.agents.map(one => ({value: one.agent, label: one.label,
      badge: one.default ? 'Default' : one.available ? null : 'Not found', ok: one.available ? (one.default || undefined) : false,
      disabled: !one.available,
      hint: one.available ? null : ['Not found on this machine. Set its start command with ',
        h('code', {}, one.next || `metaform set --dispatch-${one.agent} "<command>"`)]}));
    const value = box.value();
    pick.set(options, value);
    pick.querySelector(':scope > .btn').disabled = !options.length || held;
    const chosen = harness(value);
    make.hidden = off || !chosen;
    make.disabled = !chosen?.available || chosen.default;
    make.setAttribute('aria-pressed', String(Boolean(chosen?.default)));
    make.classList.toggle('on', Boolean(chosen?.default));
    const said = chosen?.default ? `${chosen.label} is the default agent` : chosen ? `Make ${chosen.label} the default agent` : 'Make it the default';
    make.title = said;
    make.setAttribute('aria-label', said);
    note.className = 'pickernote';
    if (off) { note.classList.add('off'); fill(note, 'Agents are off here: ', h('code', {}, HARNESS.next || 'metaform enable dispatch')); }
    else if (HARNESS.error) { note.classList.add('off'); fill(note, HARNESS.error); }
    else if (none) { note.classList.add('off'); fill(note, 'No agent is found on this machine. Set one up with ', h('code', {}, HARNESS.agents[0]?.next || 'metaform dispatch agents')); }
    else if (room && HARNESS.room !== null) fill(note, HARNESS.room > 0 ? `${plural(HARNESS.room, 'more agent')} can start now.`
      : 'Every agent slot is in use: it starts when one is free.');
    else fill(note);
    note.hidden = !note.textContent;
    note.title = note.textContent;
  };
  HARNESS.pickers.add(box);
  box.paint();
  if (HARNESS.project !== S.project || Date.now() - HARNESS.read > 15000) readHarnesses();
  return box;
}
/* A plain select of the same agents, for a ticket's own preferred agent on its card, which starts nothing. */
function agentSelect(value, onchange, label = 'Preferred agent') {
  const options = [...HARNESS.agents.map(one => [one.agent, one.available ? one.label : `${one.label} (not found)`]),
    ...(value && !harness(value) ? [[value, value]] : [])];
  return h('select', {class: 'agent', 'aria-label': label, onchange: event => onchange(event.target.value)},
    options.map(([agent, text]) => h('option', {value: agent, selected: agent === value}, text)));
}
const summonAgent = () => HARNESS.enabled === false ? null : SUMMON.chosen ? SUMMON.agent : usableAgent(SUMMON.agent);
/* The pickers that live on: the chat dock's, the one of the issue form, the default in the Agents menu. */
const PICKERS = {};
function summonPicker(name, options = {}) {
  return PICKERS[name] ||= agentPicker({label: 'Agent for new chats', holder: SUMMON, room: true, kept: true, ...options});
}

/* The chat's tab says when agents wait for the person's permission or answer, and how many. */
function drawDockTab() {
  const waiting = (D.asking || []).length, tab = $('#dockTab');
  tab.classList.toggle('asks', waiting > 0);
  const unread = !waiting && DOCK.unread;  // the agent wrote while the chat was put away
  tab.classList.toggle('unread', unread);
  fill(tab, h('span', {}, 'Chat'), waiting ? h('b', {class: 'asking', 'aria-hidden': 'true'}, String(waiting))
    : unread ? h('i', {class: 'newdot', 'aria-hidden': 'true'}) : null);
  tab.setAttribute('aria-label', waiting ? `Open the chat: ${plural(waiting, 'agent waits', 'agents wait')} for you`
    : unread ? 'Open the chat: a new message' : 'Open the chat with an agent');
}

/* ---------- an agent's session as ACP gives it, VIEW-039 and BASE-052 ----------
 * The thread, the plan as a checklist, each tool call with its diffs and the parts of the map its files belong to,
 * each permission request with the agent's own options, the session's settings, its slash commands and its usage,
 * drawn alike in the chat dock and the agent window from `GET /api/dispatch-sessions`, read again on each dispatch
 * event. Each piece is drawn again only when what it shows changed, so nothing under the person's hand flickers. */
const clip = (text, most) => { const said = String(text ?? ''); return said.length > most ? said.slice(0, most - 1).trimEnd() + '…' : said; };
const isIntake = workId => String(workId || '').startsWith('intake-');
/* What a session works on, in words: the intake, or its ticket's part. An intake's work id is never a ticket. */
const workPart = workId => isIntake(workId) ? 'the intake' : ticketPart(ticketOf(workId));
/* A mode that lets the agent act without asking: named so by the agents that offer one, as bypassPermissions, yolo or
 * full access are, so choosing it is a decision the person sees and confirms. */
const SKIPS = /bypass|yolo|full[-_ ]?access|danger|skip[-_ ]?perm|no[-_ ]?approv|never[-_ ]?ask|without[-_ ]?ask/i;
const skipsPrompts = option => Boolean(option) && SKIPS.test(`${option.value} ${option.name}`);
const OPENED = new Set();  // the tool calls opened to their detail, by session and line, kept as the thread is drawn again
const TOOL_ICON = {read: 'i-file', edit: 'i-pen', delete: 'i-trash', move: 'i-move', search: 'i-search', execute: 'i-terminal',
  think: 'i-spark', fetch: 'i-globe', switch_mode: 'i-gear'};
const STATUS_WORDS = {pending: 'pending', in_progress: 'running', completed: 'done', failed: 'failed'};
const statusOf = line => line.data?.status || /\(([\w ]+)\)\s*$/.exec(line.text || '')?.[1] || 'pending';
const titleOf = line => line.data?.title || String(line.text || '').replace(/\s*\([\w ]+\)\s*$/, '') || 'A tool call';
const countOf = number => number >= 1e6 ? `${(number / 1e6).toFixed(1).replace(/\.0$/, '')}M`
  : number >= 1e3 ? `${(number / 1e3).toFixed(1).replace(/\.0$/, '')}k` : String(number);
/* A unified patch drawn as it reads: each line with its numbers before and after, added and removed in their colors. */
function unifiedDiff(patch) {
  const rows = [];
  let old = 0, now = 0;
  const lines = String(patch || '').split('\n');
  if (lines.at(-1) === '') lines.pop();
  const row = (kind, before, after, sign, text, word) => h('div', {class: `dl ${kind}`},
    h('span', {class: 'ln', 'aria-hidden': 'true'}, before), h('span', {class: 'ln', 'aria-hidden': 'true'}, after),
    h('span', {class: 'sg', 'aria-hidden': 'true'}, sign), word ? h('span', {class: 'visually-hidden'}, word) : null,
    h('code', {}, text || ' '));
  for (const line of lines) {
    if (line.startsWith('--- ') || line.startsWith('+++ ')) continue;
    const hunk = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/.exec(line);
    if (hunk) { old = Number(hunk[1]); now = Number(hunk[2]); rows.push(row('hunk', '', '', '', line)); continue; }
    if (line.startsWith('\\')) { rows.push(row('meta', '', '', '', line.slice(2))); continue; }
    const sign = line[0], text = line.slice(1);
    if (sign === '+') rows.push(row('add', '', now++, '+', text, 'added'));
    else if (sign === '-') rows.push(row('del', old++, '', '−', text, 'removed'));
    else rows.push(row('ctx', old++, now++, '', text));
  }
  return h('div', {class: 'udiff'}, rows);
}
/* The parts of the map a file belongs to, each a chip that selects the part and flies both views to it. */
function nodeChips(nodes = []) {
  return (nodes || []).map(node => {
    const key = node.kind === 'join' ? 'p:' + node.id : node.id;
    const known = node.kind === 'join' ? Boolean(joinOf(key)) : S.elements.has(key);
    const name = known ? nameOf(key, node.address) : node.address || key;
    return h('button', {class: 'chip nodechip', type: 'button', disabled: !known,
      title: known ? `Select ${name} on the map (${node.address})` : `${node.address}: not in the map shown`,
      onclick: event => { event.stopPropagation(); select(key, true); }}, h('i', {class: 'dot', 'aria-hidden': 'true'}), clip(name, 32));
  });
}
function fileDetail(diff) {
  return h('div', {class: 'file'},
    h('div', {class: 'filehead'}, h('i', {class: 'i i-file', 'aria-hidden': 'true'}), h('span', {class: 'path', title: diff.path}, diff.path),
      diff.created ? h('span', {class: 'badge ok'}, 'New file') : null,
      h('span', {class: 'delta'}, h('b', {class: 'add'}, `+${diff.added ?? 0}`), h('b', {class: 'del'}, `−${diff.removed ?? 0}`))),
    (diff.nodes || []).length ? h('div', {class: 'chips'}, nodeChips(diff.nodes)) : null,
    unifiedDiff(diff.patch),
    diff.truncated ? h('p', {class: 'hint'}, 'The diff is cut short here; the file holds the rest.') : null);
}
/* What a tool call acts on: its diffs, the places it reads or writes, and the terminals it runs. */
function toolDetail(data) {
  const located = (data.locations || []).filter(place => !(data.diffs || []).some(diff => diff.path === place.path));
  return [(data.diffs || []).map(fileDetail),
    located.length ? h('ul', {class: 'places'}, located.map(place => h('li', {},
      h('i', {class: 'i i-file', 'aria-hidden': 'true'}), h('span', {class: 'path'}, place.line ? `${place.path}:${place.line}` : place.path),
      (place.nodes || []).length ? h('span', {class: 'chips'}, nodeChips(place.nodes)) : null))) : null,
    (data.terminals || []).length ? h('p', {class: 'hint'}, `Runs in ${plural(data.terminals.length, 'terminal')}: ${data.terminals.join(', ')}`) : null];
}
/* A tool call: one compact row, its kind, title, files and status; one with something to show opens to it. */
function toolRow(line, tag, key) {
  const data = line.data || null, status = statusOf(line), title = titleOf(line);
  const kind = data?.kind || 'other';
  const added = (data?.diffs || []).reduce((sum, diff) => sum + (diff.added || 0), 0);
  const removed = (data?.diffs || []).reduce((sum, diff) => sum + (diff.removed || 0), 0);
  const files = [...new Set([...(data?.diffs || []), ...(data?.locations || [])].map(one => one.path))];
  const more = Boolean(data && ((data.diffs || []).length || (data.locations || []).length || (data.terminals || []).length));
  const open = more && OPENED.has(key);
  const detail = more ? h('div', {class: 'tooldetail', hidden: !open}, open ? toolDetail(data) : null) : null;
  const head = h(more ? 'button' : 'div', {class: 'toolhead', ...(more ? {type: 'button', 'aria-expanded': String(open),
    title: open ? 'Hide what it changed' : 'Show what it changed', onclick: () => {
      const now = detail.hidden;
      detail.hidden = !now;
      if (now && !detail.childNodes.length) fill(detail, toolDetail(data));
      head.setAttribute('aria-expanded', String(now));
      OPENED[now ? 'add' : 'delete'](key);
    }} : {})},
    h('i', {class: `i ${TOOL_ICON[kind] || 'i-tool'} kind`, 'aria-hidden': 'true'}),
    h('span', {class: 'title'}, title),
    files.length ? h('span', {class: 'files', title: files.join('\n')}, files.length === 1 ? files[0].split('/').pop() : `${files.length} files`) : null,
    added || removed ? h('span', {class: 'delta'}, h('b', {class: 'add'}, `+${added}`), h('b', {class: 'del'}, `−${removed}`)) : null,
    h('span', {class: 'toolstate', 'data-status': status}, h('i', {'aria-hidden': 'true'}), STATUS_WORDS[status] || status),
    more ? h('i', {class: 'i i-chev', 'aria-hidden': 'true'}) : null);
  return h(tag, {class: 'tool', 'data-status': status}, head, detail);
}
/* A permission request, as the agent put it: what it would do and the agent's own options, each a button; while it
 * waits it stands out, and once answered it says what was chosen. */
function permissionCard(line, work, tag, agent) {
  const data = line.data || {}, state = data.state || 'waiting';
  const name = agentName(agent);
  const chosen = (data.options || []).find(option => option.option_id === data.chosen);
  const answer = h('div', {class: 'answers', role: 'group', 'aria-label': 'Answer the request'},
    (data.options || []).map(option => h('button', {type: 'button', 'data-option': option.option_id,
      class: `btn sm ${/^allow/.test(option.kind) ? (option.kind === 'allow_once' ? 'primary' : '') : 'danger'}`,
      title: {allow_once: 'Let it do this once', allow_always: 'Let it do this, and the same again without asking',
        reject_once: 'Do not let it do this', reject_always: 'Do not let it, and never ask again'}[option.kind] || option.name,
      onclick: async event => {
        const buttons = [...answer.querySelectorAll('button')];
        for (const button of buttons) button.disabled = true;
        event.currentTarget.classList.add('chosen');
        const done = await wrote('/api/dispatch-permit', {work_id: work, request: data.request, option: option.option_id});
        if (!done) { for (const button of buttons) button.disabled = false; event.currentTarget.classList.remove('chosen'); return; }
        card.classList.replace('waiting', 'answered');
        fill(answer, h('p', {class: 'said'}, h('i', {class: 'i i-check', 'aria-hidden': 'true'}), `${done.answer || option.name}, answered by you.`));
      }}, option.name)));
  const said = state === 'answered' ? `${data.answer || chosen?.name || 'Answered'}: answered.`
    : state === 'cancelled' ? 'Not answered: its turn ended before an answer.'
    : state === 'unmatched' ? `Answered at the node with “${data.answer || ''}”, which none of its options matched, so it was refused.` : '';
  const card = h(tag, {class: `permission ${state}`, 'data-request': data.request},
    h('div', {class: 'ask'}, h('span', {class: 'eyebrow'}, state === 'waiting' ? 'Waiting for you' : 'Permission'),
      h('b', {}, `${name} asks to ${data.title || 'use a tool'}`), data.kind ? h('span', {class: 'chip'}, data.kind) : null),
    data.said ? h('p', {class: 'why'}, ...linked(data.said)) : null,
    data.detail ? h('div', {class: 'tooldetail'}, toolDetail(data.detail)) : null,
    state === 'waiting' ? answer : h('p', {class: 'said'}, h('i', {class: `i ${state === 'answered' && /^allow/.test(chosen?.kind || '') ? 'i-check' : 'i-close'}`, 'aria-hidden': 'true'}), said));
  return card;
}
/* A question the agent put to the person, ACP's elicitation: who asks and what; a one-question form's choices as
 * buttons, with its free-text companion, as claude-agent-acp's "Other", as a field beside them; any other form as a
 * field per question; or a page to open, its full address and host shown, a warning on a host in another script, and
 * a link opened only by the person's own click. The answer goes as the person would write it at the node, through
 * dispatch permit, and the card then says what it became: answered, declined, withdrawn by the agent or completed. */
function elicitationCard(line, work, tag, agent) {
  const data = line.data || {}, state = data.state || 'waiting';
  const fields = data.fields || [], questions = fields.filter(field => !field.note_of);
  const notes = key => fields.filter(field => field.note_of === key);
  const asker = data.subagent ? `${agentName(agent)}'s subagent ${data.subagent}` : agentName(agent);
  const takes = field => (field.choices || []).length ? (field.choices || []).map(([, title]) => title).join(', ')
    : field.note_of ? 'your own words' : field.type || 'text';
  const send = async answer => {
    const controls = [...card.querySelectorAll('button, input, select')];
    for (const control of controls) control.disabled = true;
    const done = await wrote('/api/dispatch-permit', {work_id: work, request: data.request, option: answer});
    if (!done) { for (const control of controls) control.disabled = false; return; }
    card.classList.replace('waiting', 'answered');
    fill(acts, h('p', {class: 'said'}, h('i', {class: 'i i-check', 'aria-hidden': 'true'}),
      done.action === 'decline' ? 'Declined by you.' : data.secret ? 'Answered by you.' : `${answer}: answered by you.`));
  };
  const decline = h('button', {type: 'button', class: 'btn sm danger', title: 'Do not answer; the agent goes on without it',
    onclick: () => send('decline')}, 'Decline');
  let acts;
  if (data.url) {
    const host = data.host || '';
    const coded = host.split('.').some(part => part.startsWith('xn--')) || /[^\x00-\x7f]/.test(host);
    acts = h('div', {class: 'answers', role: 'group', 'aria-label': 'Answer the question'},
      h('a', {class: 'btn sm', href: data.url, target: '_blank', rel: 'noopener noreferrer',
        title: 'Open the page in a new tab; nothing opens it but you'}, h('i', {class: 'i i-globe', 'aria-hidden': 'true'}), 'Open the page'),
      h('button', {type: 'button', class: 'btn sm primary', title: 'You consent: say so to the agent', onclick: () => send('accept')}, 'Accept'),
      decline);
    acts.prepend(h('div', {class: 'address'}, h('p', {class: 'host'}, 'Host: ', h('b', {}, host || 'none')),
      coded ? h('p', {class: 'warn'}, 'The host is written in another script: check it is the one you expect.') : null,
      h('code', {class: 'url'}, data.url)));
  } else if (questions.length === 1 && (questions[0].choices || []).length && !questions[0].many) {
    const own = notes(questions[0].key)[0];
    const words = own ? h('input', {type: 'text', class: 'own', placeholder: own.description || own.title || 'Your own words',
      'aria-label': own.title || 'Your own words', autocomplete: 'off',
      onkeydown: event => { if (event.key === 'Enter' && words.value.trim()) send(words.value.trim()); }}) : null;
    acts = h('div', {class: 'answers', role: 'group', 'aria-label': 'Answer the question'},
      questions[0].choices.map(([, title]) => h('button', {type: 'button', class: 'btn sm',
        onclick: () => send(words && words.value.trim() ? `${title}, ${words.value.trim()}` : title)}, title)),
      words, words ? h('button', {type: 'button', class: 'btn sm primary', title: 'Answer in your own words',
        onclick: () => { if (words.value.trim()) send(words.value.trim()); }}, 'Send') : null, decline);
  } else {
    const inputs = fields.map(field => {
      const label = field.note_of ? `${field.key} (${field.title})` : questions.length === 1 ? field.title : `${field.key} (${field.title})`;
      const input = (field.choices || []).length && !field.many
        ? h('select', {'data-key': field.key}, h('option', {value: ''}, '—'), field.choices.map(([, title]) => h('option', {value: title}, title)))
        : h('input', {type: data.secret && field.secret ? 'password' : 'text', 'data-key': field.key, autocomplete: 'off',
          placeholder: `${field.many ? 'any of ' : ''}${takes(field)}`, value: field.default ?? ''});
      return h('label', {class: 'field'}, h('span', {}, label, field.required ? ' *' : ''), input);
    });
    const submit = () => send(inputs.map(label => label.querySelector('[data-key]'))
      .filter(input => input.value.trim()).map(input => `${input.dataset.key}: ${input.value.trim()}`).join('\n'));
    acts = h('div', {class: 'answers form', role: 'group', 'aria-label': 'Answer the question'}, inputs,
      h('div', {class: 'row'}, h('button', {type: 'button', class: 'btn sm primary', onclick: submit}, 'Send'), decline));
  }
  const said = {answered: data.secret || !data.answer ? 'Answered.' : `${data.answer}: answered.`, declined: 'Declined.',
    cancelled: 'Not answered: its turn ended first.', withdrawn: 'Withdrawn by the agent before an answer.',
    completed: 'Completed in the browser.'}[state] || state;
  const card = h(tag, {class: `permission elicitation ${state}`, 'data-request': data.request},
    h('div', {class: 'ask'}, h('span', {class: 'eyebrow'}, state === 'waiting' ? 'Waiting for your answer' : 'Question'),
      h('b', {}, data.url ? `${asker} asks you to open a page` : `${asker} asks`)),
    h('p', {class: 'why'}, ...linked(data.message || '')),
    data.problem && state === 'waiting' ? h('p', {class: 'hint'}, `The last answer could not be read: ${data.problem}.`) : null,
    data.deadline && state === 'waiting' ? h('p', {class: 'hint'}, `It goes on without your answer at ${dated(data.deadline)}.`) : null,
    data.secret && state === 'waiting' ? h('p', {class: 'hint'}, 'It asks for a secret: the answer is kept out of the thread.') : null,
    state === 'waiting' ? acts : h('p', {class: 'said'}, h('i', {class: `i ${state === 'answered' || state === 'completed' ? 'i-check' : 'i-close'}`, 'aria-hidden': 'true'}), said));
  return card;
}
/* One of ACP's session notices, the agent's own word on its state, such as an MCP server it could not start: a quiet
 * line by severity, info, warning or error, and any other severity plain. */
function noticeRow(line) {
  const data = line.data || {};
  const severity = ['info', 'warning', 'error'].includes(data.severity) ? data.severity : 'other';
  return h('div', {class: `system agent-notice ${severity}`, role: severity === 'error' ? 'alert' : null},
    h('b', {}, data.title || 'Notice'), data.description ? ` ${data.description}` : '');
}
/* A signal a session raised, said in words; a permission waiting is its card, so it is not said twice. */
function signalWords(text) {
  try { const found = JSON.parse(text); return ['permission-waiting', 'question-waiting'].includes(found.signal) ? null : `Signal: ${String(found.signal || '').replace(/-/g, ' ')}${found.active === false ? ', cleared' : ''}.`; }
  catch { return text; }
}
/* The rows of a thread for keyedFill, in the order the session wrote them: the agent's words and the person's as
 * bubbles, its thinking folded to a few quiet lines that open on a click, each tool call one compact row, each
 * permission request a card with the agent's own options, and what Metaform said or noticed as a quiet line. The plan
 * is drawn apart, as a checklist; a turn's end and the session's state are not lines of the conversation. */
/* ---------- the chat as an MCP Apps host, io.modelcontextprotocol/ui (2026-01-26) ----------
 * A Metaform tool that declares a view, `_meta.ui.resourceUri`, shows it in the thread under its call: the view's
 * document, `GET /api/mcp-app`, in a frame sandboxed to scripts alone, so its origin is opaque and it reaches nothing
 * of the page's; its content policy is the one it asks for. The page is its host over postMessage, JSON-RPC as the
 * spec has it: ui/initialize answered with what this host offers, the call's input and result sent once the view is
 * ready, its size followed, tools/call taken to the folder's MCP server as the thread's agent session
 * (`POST /api/mcp-call`), a link opened only once the person agrees. A view pops out into a panel of its own, moved
 * and sized as the person likes, and comes back; /apps, or the head's menu, lists every view the enabled modules
 * offer, each opened in a panel. The views and the tools that show them are read from the server, `GET /api/mcp-apps`. */
const APPS = {project: null, at: 0, tools: {}, views: [], reading: null, panels: 0, gallery: false};
const APPFRAMES = new Map();  // key -> {key, app, scope, frame, holder, panel, mode, ready, fed}
const APP_PROTOCOL = '2026-01-26';
function readApps(force = false) {
  if (!S.project) return Promise.resolve(APPS);
  if (!force && APPS.project === S.project && Date.now() - APPS.at < 300000) return Promise.resolve(APPS);
  if (APPS.reading) return APPS.reading;
  const project = S.project;
  APPS.reading = read('mcp-apps')
    .then(found => { if (S.project === project) Object.assign(APPS, {project, at: Date.now(), tools: found.tools || {}, views: found.views || []}); })
    .catch(() => Object.assign(APPS, {project, at: Date.now(), tools: {}, views: []}))
    .then(() => { APPS.reading = null; if (DOCK.target || APPS.gallery) drawHelpdesk(); return APPS; });
  return APPS.reading;
}
/* The view a tool call shows: its tool's, when the runner kept the call's tool, `data.call`. */
function appOf(line) {
  const call = line.data?.call;
  if (!call?.tool) return null;
  if (APPS.project !== S.project) { readApps(); return null; }  // drawn again once the views are known
  const tool = APPS.tools[call.tool];
  return tool?.uri ? {uri: tool.uri, call, tool: call.tool} : null;
}
const appName = uri => APPS.views.find(one => one.uri === uri)?.name || String(uri).replace(/^ui:\/\//, '');
function appRow(key, app, scope) {
  const holder = h('div', {class: 'appholder'});
  const box = h('div', {class: 'mcpapp', 'data-uri': app.uri},
    h('div', {class: 'appbar'}, h('span', {class: 'name'}, appName(app.uri)), app.tool ? h('small', {}, app.tool) : null,
      h('span', {class: 'grow'}),
      h('button', {class: 'btn sm quiet', type: 'button', title: 'Show it in a panel of its own, moved and sized as you like',
        onclick: () => popApp(key)}, 'Pop out')), holder);
  const had = APPFRAMES.get(key);
  if (had?.panel) {  // shown in its panel: the thread says so, and it comes back here
    had.inline = holder;
    fill(holder, appAway(key));
  } else mountApp(key, holder, app, scope, 'inline');
  return box;
}
const appAway = key => h('p', {class: 'appaway'}, 'Shown in a panel of its own. ',
  h('button', {class: 'btn sm quiet', type: 'button', onclick: () => bringBack(key)}, 'Bring it back'));
function mountApp(key, holder, app, scope, mode) {
  const entry = APPFRAMES.get(key) || {key};
  const meta = APPS.views.find(one => one.uri === app.uri)?.meta?.ui || {};
  const frame = h('iframe', {class: 'appframe', title: `${appName(app.uri)}, a view of the MCP server`,
    sandbox: 'allow-scripts', referrerpolicy: 'no-referrer', ...(meta.permissions?.clipboardWrite ? {allow: 'clipboard-write'} : {}),
    src: `/api/mcp-app?project=${encodeURIComponent(S.project)}&uri=${encodeURIComponent(app.uri)}`});
  Object.assign(entry, {app, scope, frame, holder, mode, ready: false, fed: {input: false, result: false}});
  APPFRAMES.set(key, entry);
  fill(holder, frame);
  for (const [other, one] of APPFRAMES) if (other !== key && !one.panel && !one.frame?.isConnected) APPFRAMES.delete(other);
  return entry;
}
function appPost(entry, message) { entry.frame?.contentWindow?.postMessage({jsonrpc: '2.0', ...message}, '*'); }
/* The call's input, then its result once there is one, each sent once the view is ready, ui/notifications. */
function appFed(key, call) {
  const entry = APPFRAMES.get(key);
  if (!entry) return;
  entry.app.call = call;
  feedApp(entry);
}
function feedApp(entry) {
  const call = entry.app.call;
  if (!entry.ready || !call) return;
  if (!entry.fed.input) { entry.fed.input = true; appPost(entry, {method: 'ui/notifications/tool-input', params: {arguments: call.input || {}}}); }
  if (call.result && !entry.fed.result) {
    entry.fed.result = true;
    appPost(entry, {method: 'ui/notifications/tool-result', params: {content: call.result.content || [], isError: Boolean(call.result.isError)}});
  }
}
function appContext(entry) {
  const box = (entry.panel ? entry.holder : entry.frame)?.getBoundingClientRect();
  const ground = getComputedStyle(document.body).backgroundColor.match(/\d+(\.\d+)?/g)?.map(Number) || [0, 0, 0];
  const light = (0.2126 * ground[0] + 0.7152 * ground[1] + 0.0722 * ground[2]) / 255 > 0.5;
  return {theme: light ? 'light' : 'dark', displayMode: entry.mode, availableDisplayModes: ['inline', 'fullscreen', 'pip'],
    containerDimensions: entry.panel ? {height: Math.round(box?.height || 400), width: Math.round(box?.width || 560)}
      : {maxHeight: 560, width: Math.round(box?.width || 400)},
    locale: navigator.language, platform: 'web', userAgent: 'Metaform web',
    ...(entry.app.call ? {toolInfo: {tool: {name: entry.app.call.tool, inputSchema: {type: 'object'}}}} : {})};
}
addEventListener('message', event => {
  const entry = [...APPFRAMES.values()].find(one => one.frame?.contentWindow && one.frame.contentWindow === event.source);
  const message = event.data;
  if (!entry || !message || message.jsonrpc !== '2.0' || !message.method) return;  // answers to the host's own requests are not awaited
  appMessage(entry, message);
});
async function appMessage(entry, message) {
  const reply = result => message.id !== undefined && appPost(entry, {id: message.id, result});
  const fail = (code, text) => message.id !== undefined && appPost(entry, {id: message.id, error: {code, message: text}});
  const params = message.params || {};
  if (message.method === 'ui/initialize') {
    return reply({protocolVersion: APP_PROTOCOL, hostInfo: {name: 'Metaform web', version: '1'},
      hostCapabilities: {openLinks: {}, serverTools: {listChanged: false}, logging: {}}, hostContext: appContext(entry)});
  }
  if (message.method === 'ui/notifications/initialized') { entry.ready = true; return feedApp(entry); }
  if (message.method === 'ui/notifications/size-changed') {  // inline it is as tall as it asks, within the thread's reach
    if (!entry.panel && Number(params.height) > 0) entry.frame.style.height = `${Math.round(Math.min(560, Math.max(120, Number(params.height))))}px`;
    return;
  }
  if (message.method === 'ping') return reply({});
  if (message.method === 'tools/call') {
    const done = await posted('/api/mcp-call', {tool: params.name, arguments: params.arguments || {},
      ...(entry.scope?.work ? {work_id: entry.scope.work, session: entry.scope.session || null} : {})});
    return done.ok ? reply(done.body) : fail(-32000, done.body?.error || 'The call failed.');
  }
  if (message.method === 'ui/open-link') {
    const url = String(params.url || '');
    if (!/^https?:[/][/]/i.test(url)) return fail(-32602, 'Only a web address is opened.');
    const sure = await confirmAct({title: 'Open this link?', verb: 'Open it', cancel: 'Stay here', danger: false,
      text: [`${appName(entry.app.uri)} asks to open a page in a new tab:`, h('code', {class: 'url'}, url)]});
    if (sure) window.open(url, '_blank', 'noopener,noreferrer');
    return reply(sure ? {} : {isError: true});
  }
  if (message.method === 'ui/request-display-mode') {
    const mode = params.mode;
    if (mode === 'inline' && entry.panel) { reply({mode: 'inline'}); return bringBack(entry.key); }
    if ((mode === 'fullscreen' || mode === 'pip') && !entry.panel) { reply({mode}); return popApp(entry.key, mode); }
    return reply({mode: entry.mode});
  }
  if (message.method === 'notifications/message') return;  // the view's own log
  return fail(-32601, `${message.method} is not offered by this host.`);
}
/* Before a view's frame goes, it is told, ui/resource-teardown, as a host does. */
function teardownApp(entry) { if (entry.frame) appPost(entry, {id: `teardown-${Date.now()}`, method: 'ui/resource-teardown', params: {}}); }
/* A view in a panel of its own: moved by its bar, sized from its corner, kept until put back or closed. */
function popApp(key, mode = 'pip') {
  const entry = APPFRAMES.get(key);
  if (!entry) return;
  if (entry.panel) { entry.panel.hidden = false; return; }
  teardownApp(entry);
  const inline = entry.holder;
  const body = h('div', {class: 'appholder'});
  const panel = h('div', {id: `mcpapp${++APPS.panels}`, class: `window movable mcpwin${mode === 'fullscreen' ? ' large' : ''}`,
    role: 'dialog', 'aria-label': appName(entry.app.uri)},
    h('div', {class: 'bar'}, h('span', {class: 'title'}, appName(entry.app.uri)),
      inline ? h('button', {class: 'btn sm quiet', type: 'button', onclick: () => bringBack(key)}, 'Back into the chat') : null,
      h('button', {class: 'close btn icon sm quiet', type: 'button', 'aria-label': 'Close', title: 'Close (Escape)',
        onclick: () => (inline ? bringBack(key) : closeApp(key))}, h('i', {class: 'i i-close', 'aria-hidden': 'true'}))), body);
  document.body.append(panel);
  movable(panel);
  overlay(panel, {kind: 'window', close: () => (inline ? bringBack(key) : closeApp(key)), focus: false});
  mountApp(key, body, entry.app, entry.scope, mode);
  Object.assign(entry, {panel, inline});
  if (inline?.isConnected) fill(inline, appAway(key));
  new ResizeObserver(() => { if (entry.ready && entry.panel === panel) appPost(entry, {method: 'ui/notifications/host-context-changed', params: {containerDimensions: appContext(entry).containerDimensions}}); }).observe(body);
}
function closeApp(key) {
  const entry = APPFRAMES.get(key);
  if (!entry) return;
  teardownApp(entry);
  const panel = entry.panel;
  APPFRAMES.delete(key);
  if (panel) { panel.hidden = true; setTimeout(() => panel.remove(), 0); }
}
function bringBack(key) {
  const entry = APPFRAMES.get(key);
  if (!entry?.panel) return;
  const {panel, inline} = entry;
  teardownApp(entry);
  entry.panel = null;
  panel.hidden = true;
  setTimeout(() => panel.remove(), 0);
  if (inline?.isConnected) mountApp(key, inline, entry.app, entry.scope, 'inline'); else APPFRAMES.delete(key);
}
/* The gallery, /apps or the head's menu: every view the enabled modules offer, each opened in a panel of its own,
 * its calls made as the agent of the thread on view, or as the person's page when none is. */
function showGallery() {
  APPS.gallery = true;
  readApps(true);
  drawHelpdesk().then(() => followLog(true));
}
function galleryRows() {
  if (!APPS.gallery) return [];
  return [{key: 'gallery', text: JSON.stringify(APPS.views.map(one => one.uri)), make: () => h('div', {class: 'appgallery', role: 'group', 'aria-label': 'The views of the MCP server'},
    h('div', {class: 'appbar'}, h('span', {class: 'name'}, 'Apps'), h('small', {}, 'The views the enabled modules offer'), h('span', {class: 'grow'}),
      h('button', {class: 'btn sm quiet', type: 'button', onclick: () => { APPS.gallery = false; drawHelpdesk(); }}, 'Close')),
    APPS.views.length ? h('ul', {}, APPS.views.map(one => h('li', {},
      h('div', {}, h('b', {}, one.name || one.uri), h('small', {}, one.description || ''), h('code', {}, one.uri)),
      h('button', {class: 'btn sm', type: 'button', onclick: () => {
        const key = `gallery:${one.uri}:${++APPS.panels}`;
        APPFRAMES.set(key, {key, app: {uri: one.uri, call: null}, scope: {work: DOCK.target, session: DOCK.session}});
        popApp(key);
      }}, 'Open'))))
      : h('p', {class: 'hint'}, APPS.reading ? 'Reading the views…' : 'No enabled module offers a view here.'))}];
}
function threadRows(lines, {work, agent}) {
  const rows = [];
  let sender = null;  // who wrote the message before, so a run of one sender's messages is named once
  DOCK.heard = new Set();
  for (const line of lines) {
    const key = `${line.session_id}:${line.name ?? line.seq}`;
    const kind = line.kind;
    const text = `${kind}\n${line.text}\n${line.data ? JSON.stringify(line.data) : ''}`;
    if (kind === 'plan' || kind === 'state' || kind === 'tool_detail' || kind === 'turn') continue;
    if (kind === 'tool_call' || kind === 'tool_call_update') {
      rows.push({key, text, make: () => toolRow(line, 'div', key)});
      // a Metaform tool with a view shows that view under its call, fed the call's input and its result
      const app = appOf(line);
      if (app) {
        rows.push({key: `app:${key}`, text: app.uri, make: () => appRow(`app:${key}`, app, {work, session: line.session_id})});
        appFed(`app:${key}`, app.call);
      }
      continue;
    }
    if (kind === 'permission') { rows.push({key, text, make: () => permissionCard(line, work, 'div', agent)}); continue; }
    if (kind === 'elicitation') {
      rows.push({key, text, make: () => line.data?.request ? elicitationCard(line, work, 'div', agent)
        : h('div', {class: 'system notice'}, `A question, ${line.data?.state || 'declined'}${line.data?.by ? ` by ${line.data.by}` : ''}: ${line.data?.message || ''}`)});
      continue;
    }
    if (kind === 'agent_notice') { rows.push({key, text, make: () => noticeRow(line)}); continue; }
    if (kind === 'signal') {
      const words = signalWords(line.text);
      if (words) rows.push({key, text, make: () => h('div', {class: 'system signal'}, words)});
      continue;
    }
    if (kind === 'agent_message_chunk' || kind === 'person' || kind === 'user_message_chunk') {
      const mine = kind !== 'agent_message_chunk', who = mine ? 'You' : agentName(agent);
      const first = who !== sender, at = SEEN.at.get(key) ?? (SEEN.sessions.has(line.session_id) ? Date.now() : 0);
      SEEN.at.set(key, at);
      sender = who;
      if (mine) DOCK.heard.add(String(line.text).trim());
      rows.push({key, text: `${text}\n${first}`, make: () => messageRow(line.text, {mine, who, first, at})});
    }
    else if (kind === 'agent_thought_chunk') rows.push({key, text, make: () => h('div', {class: 'thought',
      title: 'Its thinking: click to read all of it, and again to fold it',
      onclick: event => { if (!event.target.closest('a, button')) event.currentTarget.classList.toggle('open'); }},
      h('small', {}, 'Thinking'), h('span', {class: 'said'}, ...linked(line.text)))});
    else if (['setting', 'approved', 'failed', 'notice'].includes(kind)) rows.push({key, text, make: () => h('div', {class: `system ${kind}`}, line.text)});
  }
  for (const line of lines) SEEN.sessions.add(line.session_id);  // a line read later than this one arrived now
  return rows;
}
/* A message: who wrote it, named above the first of a run of theirs, its words read as markdown, and on hover or
 * focus the time it arrived and, for the agent's, Copy. The sender is said to a screen reader in the bubble too. */
function messageRow(text, {mine, who, first, at, pending = null}) {
  const bubble = h('div', {class: `bubble ${mine ? 'mine' : 'theirs'}${pending ? ' pending' : ''}`},
    h('span', {class: 'visually-hidden'}, `${who}: `), ...richText(text));
  const time = at ? h('time', {datetime: new Date(at).toISOString(), title: new Date(at).toLocaleString()}, clockOf(at)) : null;
  const tools = h('div', {class: 'tools'}, pending ? h('small', {class: 'pendingnote'}, pending) : time,
    mine ? null : copyButton(() => String(text), 'Copy the message'));
  return h('div', {class: `msg ${mine ? 'mine' : 'theirs'}${first ? ' first' : ''}`},
    first ? h('div', {class: 'who', 'aria-hidden': 'true'}, who) : null, h('div', {class: 'row'}, bubble, tools));
}
/* A small Copy button: the text given goes to the clipboard, and the button says Copied for a moment. */
function copyButton(text, label = 'Copy') {
  const button = h('button', {class: 'copy', type: 'button', title: label, 'aria-label': label, onclick: async event => {
    event.stopPropagation();
    const said = text();
    try { await navigator.clipboard.writeText(said); } catch {
      const field = h('textarea', {style: {position: 'fixed', opacity: '0'}}, said);
      document.body.append(field); field.select();
      try { document.execCommand('copy'); } catch { /* nothing more to try */ }
      field.remove();
    }
    button.classList.add('done');
    button.setAttribute('aria-label', 'Copied');
    setTimeout(() => { button.classList.remove('done'); button.setAttribute('aria-label', label); }, 1400);
  }}, h('i', {class: 'i i-copy', 'aria-hidden': 'true'}), h('i', {class: 'i i-check', 'aria-hidden': 'true'}));
  return button;
}
/* A message's words as written in markdown, read into the page's own elements and never set as HTML, VIEW-009:
 * paragraphs, headings, lists, quotes and rules; fenced code with its language and Copy; inline code, bold, italic
 * and links to web pages, opened in a new tab. References in the words are linked as everywhere else. */
const BLOCK_START = /^\s*(```|~~~|#{1,6}\s|>|[-*+]\s|\d{1,3}[.)]\s|([-*_])(\s*\2){2,}\s*$)/;
function richText(text) {
  const lines = String(text ?? '').replace(/\r\n?/g, '\n').split('\n'), out = [];
  let at = 0;
  while (at < lines.length) {
    const line = lines[at];
    const fence = /^\s*(```+|~~~+)\s*([\w+#.-]*)/.exec(line);
    if (fence) {
      const code = [];
      for (at++; at < lines.length && !lines[at].trim().startsWith(fence[1]); at++) code.push(lines[at]);
      at++;
      out.push(codeBlock(code.join('\n'), fence[2]));
      continue;
    }
    if (!line.trim()) { at++; continue; }
    const head = /^\s*(#{1,6})\s+(.*)$/.exec(line);
    if (head) { out.push(h('p', {class: `mdh h${head[1].length}`}, ...inlineText(head[2]))); at++; continue; }
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { out.push(h('hr')); at++; continue; }
    if (/^\s*>/.test(line)) {
      const said = [];
      for (; at < lines.length && /^\s*>/.test(lines[at]); at++) said.push(lines[at].replace(/^\s*>\s?/, ''));
      out.push(h('blockquote', {}, ...richText(said.join('\n'))));
      continue;
    }
    const item = /^(\s*)([-*+]|\d{1,3}[.)])\s+/;
    if (item.test(line)) {
      const ordered = /\d/.test(item.exec(line)[2]), items = [];
      for (; at < lines.length && (item.test(lines[at]) || (/^\s{2,}\S/.test(lines[at]) && items.length)); at++) {
        const found = item.exec(lines[at]);
        if (found && /\d/.test(found[2]) === ordered) items.push(lines[at].slice(found[0].length));
        else if (found) break;
        else items[items.length - 1] += '\n' + lines[at].trim();
      }
      const start = ordered ? parseInt(item.exec(line)[2], 10) : 1;
      out.push(h(ordered ? 'ol' : 'ul', ordered && start !== 1 ? {start: String(start)} : {}, items.map(one => h('li', {}, ...inlineText(one)))));
      continue;
    }
    const said = [line];
    for (at++; at < lines.length && lines[at].trim() && !BLOCK_START.test(lines[at]); at++) said.push(lines[at]);
    out.push(h('p', {}, ...inlineText(said.join('\n'))));
  }
  return out;
}
const INLINE = /(`+)([^`]|[^`][\s\S]*?[^`])\1(?!`)|\*\*([^*\n]+?)\*\*|__([^_\n]+?)__|(?<![\w*])\*(?!\s)([^*\n]+?)\*(?![\w*])|(?<![\w_])_(?!\s)([^_\n]+?)_(?![\w_])|\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)|(https?:\/\/[^\s<>()]+[^\s<>().,;:!?'"])/g;
function inlineText(text) {
  const parts = [];
  let at = 0;
  for (const found of text.matchAll(INLINE)) {
    parts.push(...linked(text.slice(at, found.index)));
    const [, , code, bold, bold2, em, em2, label, href, bare] = found;
    if (code !== undefined) parts.push(h('code', {}, code));
    else if (bold || bold2) parts.push(h('strong', {}, ...linked(bold || bold2)));
    else if (em || em2) parts.push(h('em', {}, ...linked(em || em2)));
    else parts.push(h('a', {href: href || bare, target: '_blank', rel: 'noopener noreferrer', title: href || bare}, label || bare));
    at = found.index + found[0].length;
  }
  parts.push(...linked(text.slice(at)));
  return parts;
}
function codeBlock(code, lang) {
  return h('div', {class: 'code'}, h('div', {class: 'codehead'}, h('span', {}, lang || 'code'), copyButton(() => code, 'Copy the code')),
    h('pre', {tabindex: '0'}, h('code', {}, code)));
}
/* The plan, a checklist of its entries as the agent keeps it, drawn again only when it changes. */
function drawPlan(box, plan) {
  const entries = Array.isArray(plan) ? plan : [];
  const text = JSON.stringify(entries);
  if (box.dataset.drawn === text) return;
  box.dataset.drawn = text;
  box.hidden = !entries.length;
  if (!entries.length) return fill(box);
  const done = entries.filter(entry => entry.status === 'completed').length;
  // open as it was; at first open in a window, folded to its count in the chat, where the conversation needs the room
  const wasOpen = box.querySelector('details') ? box.querySelector('details').open
    : box.dataset.closed ? box.dataset.closed !== 'true' : !box.closest('#helpdesk');
  const details = h('details', {open: wasOpen, ontoggle: event => { box.dataset.closed = String(!event.target.open); }},
    h('summary', {}, h('span', {class: 'eyebrow'}, 'Plan'), h('span', {class: 'tally'}, `${done} of ${entries.length} done`),
      h('span', {class: 'meter', 'aria-hidden': 'true'}, h('span', {style: {width: `${Math.round(100 * done / entries.length)}%`}}))),
    h('ol', {class: 'steps'}, entries.map(entry => h('li', {class: entry.status || 'pending'},
      h('i', {class: 'mark', 'aria-hidden': 'true'}),
      h('span', {class: 'visually-hidden'}, `${STATUS_WORDS[entry.status] || entry.status}: `),
      h('span', {class: 'what'}, entry.content || ''),
      entry.priority === 'high' ? h('span', {class: 'prio', title: 'High priority'}, 'high') : null))));
  fill(box, details);
}
/* The session's own bar: its settings as the agent offers them, a mode that skips the agent's own permission prompts
 * said as such, its usage, and Resume for a session that ended when its agent can resume it. Drawn again only when
 * what it shows changed, and never while one of its selects is in the person's hand. */
function drawSession(box, {work, session, state}) {
  const settings = state?.settings || [];
  const usage = state?.usage || null;
  const caps = state?.capabilities || {};
  const ended = session && session.state !== 'running';
  const resumable = ended && (caps.load || caps.resume);
  const text = JSON.stringify([work, session?.session_id, session?.state, settings, usage, resumable, state?.tokens || null]);
  if (box.dataset.drawn === text + (session ? '' : summonAgent()) || (box.contains(document.activeElement)
    || SESSIONPOP.el?.contains(document.activeElement)) && box.dataset.work === work) return;
  box.dataset.drawn = text + (session ? '' : summonAgent());
  box.dataset.work = work || '';
  const agent = agentName(session?.agent);
  const controls = ended ? [] : settings.map(setting => {
    if (setting.type === 'boolean') {
      const input = h('input', {type: 'checkbox', role: 'switch', checked: Boolean(setting.current), onchange: async () => {
        input.disabled = true;
        const done = await wrote('/api/dispatch-configure', {work_id: work, setting: setting.id, value: input.checked});
        input.disabled = false;
        if (!done) input.checked = !input.checked;
      }});
      return h('label', {class: 'switch setting', title: setting.description || setting.name}, input, setting.name);
    }
    const current = (setting.options || []).find(option => option.value === setting.current);
    const pick = h('select', {'aria-label': setting.name, title: setting.description || setting.name, onchange: async () => {
      const option = (setting.options || []).find(one => one.value === pick.value);
      if (skipsPrompts(option) && !await confirmAct({title: `Let ${agent} act without asking?`,
        text: [`${option.name}: in this mode ${agent} skips its own permission prompts. It edits files and runs commands without asking you first.`,
          'You can choose another mode at any time.'], verb: `Use ${option.name}`, cancel: 'Keep asking', danger: true})) {
        pick.value = setting.current; return;
      }
      pick.disabled = true;
      const done = await wrote('/api/dispatch-configure', {work_id: work, setting: setting.id, value: pick.value});
      pick.disabled = false;
      if (!done) pick.value = setting.current;
      else toast(`${setting.name}: ${option?.name || pick.value}.`);
    }}, (setting.options || []).map(option => h('option', {value: option.value, selected: option.value === setting.current},
      skipsPrompts(option) ? `${option.name} · skips its permission prompts` : option.name)));
    return h('label', {class: 'setting'}, h('span', {}, setting.name), pick,
      setting.source === 'mode' || setting.category === 'mode' ? (skipsPrompts(current)
        ? h('span', {class: 'badge danger', title: `${agent} does not ask before it acts`}, 'No prompts') : null) : null);
  });
  const used = usage && usage.used !== null && usage.used !== undefined
    ? h('span', {class: 'usage', title: 'The context the session has used of its model\'s window'},
      usage.size ? `${countOf(usage.used)} / ${countOf(usage.size)} tokens` : `${countOf(usage.used)} tokens`,
      usage.cost && usage.cost.amount !== undefined ? ` · ${usage.cost.currency === 'USD' || !usage.cost.currency ? '$' : usage.cost.currency + ' '}${Number(usage.cost.amount).toFixed(2)}` : '') : null;
  const resume = resumable ? h('button', {class: 'btn sm resume', type: 'button',
    title: `${agent} offers to resume its sessions: it goes on where it ended, with its own memory of the work`,
    onclick: async event => {
      event.currentTarget.disabled = true;
      const done = await wrote('/api/dispatch-resume', {work_id: work, session: session.session_id});
      if (!done) { event.currentTarget.disabled = false; return; }
      toast(done.state === 'running' ? `${agent} is running already; talk to it here.` : `${agent} is resuming its session; it waits for your next message.`);
      await renderAgents();
    }}, h('i', {class: 'i i-play', 'aria-hidden': 'true'}), 'Resume') : null;
  if (!session && !ended) { preCallSettings(box); return; }  // before Call: the agent's known options, chosen first
  sessionSummary(box, {agent, settings, usage, controls, used, resume});
}
/* The session's settings folded to one quiet line under the chat's head, "Codex · Sol · High · Fast · 94k/475k": a
 * click opens its controls as a popover over the thread, which stays where it is; a click outside or Escape closes
 * it. Resume, when the agent offers it, stays beside the line. */
const SESSIONPOP = {el: null};
function sessionPop() {
  if (SESSIONPOP.el) return SESSIONPOP.el;
  SESSIONPOP.el = h('div', {id: 'sessionpop', class: 'sessionpop', role: 'dialog', 'aria-label': 'The agent\'s settings', hidden: true});
  $('#helpdesk').append(SESSIONPOP.el);
  overlay(SESSIONPOP.el, {kind: 'popover'});
  return SESSIONPOP.el;
}
function optionWords(setting) {
  if (setting.type === 'boolean') return setting.current ? setting.name : null;
  const chosen = (setting.options || setting.choices || []).find(option => option.value === (setting.current ?? setting.chosen));
  return chosen?.name || null;
}
/* The agent is the line's first word and the popover's first field. Before Call it is the one choice of the agent a
 * call starts, the summon choice every start shares, with its default star; choosing another shows that agent's own
 * options at once. Once an agent runs, the field names it: another one is chosen by Dismiss, then Call. */
const DOCKPICK = {row: null, picker: null};
function dockPicker() {
  if (!DOCKPICK.row) {
    DOCKPICK.picker = summonPicker('dock', {label: 'Agent', onchange: () => refreshPreCall()});
    DOCKPICK.row = h('div', {class: 'setting agent'}, h('span', {}, 'Agent'), DOCKPICK.picker);
  }
  return DOCKPICK.row;
}
function refreshPreCall() {
  PRECALL.at = 0;
  if (!DOCK.target) preCallSettings($('#helpdesk .sessionbar'));
}
function sessionSummary(box, {agent, settings, usage, controls, used, resume, before = false}) {
  const pop = sessionPop();
  const words = settings.map(optionWords).filter(Boolean);
  const tokens = usage && usage.used !== null && usage.used !== undefined
    ? (usage.size ? `${countOf(usage.used)}/${countOf(usage.size)}` : countOf(usage.used)) : null;
  const line = [agent, ...words, tokens].filter(Boolean).join(' · ');
  box.hidden = false;
  const open = h('button', {class: 'sessionline', type: 'button', 'aria-haspopup': 'dialog', 'aria-controls': 'sessionpop',
    'aria-expanded': String(!pop.hidden), title: before ? 'The agent a call starts, and its model, effort, mode and the rest'
      : 'The agent\'s settings: its model, effort, mode and the rest', onclick: event => {
      event.stopPropagation();
      if (!pop.hidden) { pop.hidden = true; return; }
      pop.style.top = `${box.offsetTop + box.offsetHeight + 4}px`;  // just under the line, over the thread
      pop.hidden = false;
    }}, h('span', {class: 'said'}, line || 'Settings'), h('i', {class: 'i i-chev', 'aria-hidden': 'true'}));
  fill(box, open, h('span', {class: 'grow'}), resume);
  const running = h('div', {class: 'setting agent'}, h('span', {}, 'Agent'),
    h('b', {title: 'To talk with another agent, Dismiss this one, choose it here and Call'}, agent));
  // the agent's own row is kept in place, so a choice being made in it keeps the focus as the rest is drawn again;
  // a setting of the same agent just chosen in the open popover keeps its control, and only the line says it
  const same = !pop.hidden && pop.contains(document.activeElement) && pop.dataset.for === `${before}:${agent}`;
  pop.dataset.for = `${before}:${agent}`;
  if (!same) keepFill(pop, [h('div', {class: 'eyebrow'}, before ? 'The next call' : `${agent}'s settings`),
    before ? dockPicker() : running, h('div', {class: 'controls'}, controls),
    used ? h('p', {class: 'hint'}, used) : null,
    !controls.length && !used ? h('p', {class: 'hint'}, before ? `${agent} offers its settings once it has run here.`
      : 'This agent offers no settings to change now.') : null].filter(Boolean));
}
/* Before Call the chat offers what the agent to be called offered at its last session here, `dispatch options`: its
 * model, effort, mode and the rest, chosen now and kept in dispatch_agent_options, which every session it starts is
 * given. An agent that has not run here has none yet. */
const PRECALL = {agent: null, at: 0, data: null};
async function preCallSettings(box) {
  if (S.project && (HARNESS.project !== S.project || !HARNESS.read)) await readHarnesses();  // the agents there are
  const agent = summonAgent() || HARNESS.default;
  if (!S.project && !DOCK.target) {  // opened before the page knows its project: drawn again once it does
    box.hidden = true;
    box.dataset.drawn = '';
    setTimeout(() => { if (!$('#helpdesk').hidden && !DOCK.target) drawHelpdesk(); }, 400);
    return;
  }
  if (!agent || DOCK.target) { box.hidden = true; return; }
  if (PRECALL.agent !== agent || Date.now() - PRECALL.at > 30000) {
    PRECALL.agent = agent; PRECALL.at = Date.now();
    try { PRECALL.data = (await read('dispatch-options', {agent})).agents?.[0] || null; } catch { PRECALL.data = null; }
  }
  if (DOCK.target || agent !== (summonAgent() || HARNESS.default)) return;  // a call began, or another agent was chosen
  const found = PRECALL.data || {};
  const settings = (found.settings || []).map(one => ({...one, options: one.choices, current: one.chosen ?? one.current}));
  const controls = settings.map(setting => {
    if (setting.type === 'boolean') {
      const input = h('input', {type: 'checkbox', role: 'switch', checked: String(setting.current) === 'true',
        onchange: () => keepAgentOption(agent, setting.key, input.checked ? 'true' : 'false')});
      return h('label', {class: 'switch setting', title: setting.description || setting.name}, input, setting.name);
    }
    const pick = h('select', {'aria-label': setting.name, onchange: () => keepAgentOption(agent, setting.key, pick.value)},
      (setting.options || []).map(option => h('option', {value: option.value, selected: option.value === setting.current}, option.name || option.value)));
    return h('label', {class: 'setting'}, h('span', {}, setting.name), pick);
  });
  sessionSummary(box, {agent: found.label || agentName(agent), settings, usage: null, controls,
    used: controls.length ? null : found.next ? `It has not run here yet: ${found.next}` : null, resume: null, before: true});
}
async function keepAgentOption(agent, key, value) {
  let rows = [];
  try { rows = (await read('settings')).settings || []; } catch { /* written as the only entry of its own */ }
  const held = rows.find(row => row.key === 'dispatch_agent_options')?.value;
  const kept = (Array.isArray(held) ? held : String(held || '').split(',')).map(one => String(one).trim()).filter(Boolean)
    .filter(one => !one.startsWith(`${agent}.${key}=`));
  const done = await posted('/api/settings', {key: 'dispatch_agent_options', value: [...kept, `${agent}.${key}=${value}`]});
  if (!done.ok) return toast(done.body.error || 'That choice was not kept.');
  refreshPreCall();  // the line says the choice at once
  toast(`${agentName(agent)} starts with ${key} ${value}.`);
}
/* Slash commands: typing / at the start of a message offers the commands, the chat's own and the agent's, as the
 * agent named them; Up and Down choose, Enter or Tab takes one, Escape closes the list. */
function slashCommands(say, offered) {
  const id = `slash${++slashCommands.made}`;
  const list = h('div', {class: 'slash', id, role: 'listbox', hidden: true, 'aria-label': 'Commands'});
  say.after(list);
  say.setAttribute('aria-controls', id);
  say.setAttribute('aria-autocomplete', 'list');
  let found = [], active = 0;
  const word = () => {
    const before = say.value.slice(0, say.selectionStart ?? say.value.length);
    const typed = /^\/(\S*)$/.exec(before);
    return typed ? typed[1] : null;
  };
  const paint = () => {
    [...list.children].filter(row => row.getAttribute('role') === 'option').forEach((row, index) => {
      row.setAttribute('aria-selected', String(index === active));
      if (index === active) { say.setAttribute('aria-activedescendant', row.id); row.scrollIntoView({block: 'nearest'}); }
    });
  };
  const show = () => {
    const typed = word();
    found = typed === null ? [] : offered().filter(one => one.name.toLowerCase().startsWith(typed.toLowerCase()));
    if (!found.length) { list.hidden = true; say.removeAttribute('aria-activedescendant'); return; }
    active = Math.min(active, found.length - 1);
    const groups = [...new Set(found.map(one => one.from))];
    let index = -1;
    fill(list, groups.map(group => [h('div', {class: 'group', role: 'presentation'}, group),
      found.filter(one => one.from === group).map(one => { index++; const at = index;
        return h('div', {role: 'option', id: `${id}-${at}`, 'aria-selected': 'false',
          onpointerdown: event => { event.preventDefault(); take(at); }, onpointermove: () => { if (active !== at) { active = at; paint(); } }},
          h('b', {}, `/${one.name}`), one.hint ? h('span', {class: 'hint'}, one.hint) : null,
          one.description ? h('small', {}, one.description) : null); })]));
    found = groups.flatMap(group => found.filter(one => one.from === group));
    list.hidden = false;
    paint();
  };
  const take = index => {
    const one = found[index];
    if (!one) return;
    const rest = say.value.slice(say.selectionStart ?? say.value.length).replace(/^\S*/, '');
    say.value = `/${one.name} ${rest.trimStart()}`;
    const at = one.name.length + 2;
    say.setSelectionRange(at, at);
    if (one.hint) say.setAttribute('placeholder', one.hint);
    list.hidden = true;
    say.focus();
  };
  say.addEventListener('input', () => { active = 0; show(); });
  say.addEventListener('click', show);
  say.addEventListener('blur', () => setTimeout(() => { if (document.activeElement !== say) list.hidden = true; }, 120));
  say.addEventListener('keydown', event => {
    if (list.hidden) return;
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault(); event.stopImmediatePropagation();
      active = (active + (event.key === 'ArrowDown' ? 1 : -1) + found.length) % found.length; paint();
    } else if ((event.key === 'Enter' && !event.shiftKey) || event.key === 'Tab') {
      // a command typed whole is sent by Enter as it is; otherwise Enter and Tab take the one chosen
      if (event.key === 'Enter' && found[active]?.name === word()) { list.hidden = true; return; }
      event.preventDefault(); event.stopImmediatePropagation(); take(active);
    }
  }, true);
  overlay(list, {kind: 'popover', focus: false, close: () => { list.hidden = true; }});
  return list;
}
slashCommands.made = 0;
/* The commands a session offers, from its state. */
const commandsOf = (state, agent) => (state?.commands || []).filter(one => one.name)
  .map(one => ({name: one.name, description: one.description, hint: one.hint, from: `${agentName(agent)}'s commands`}));

/* ---------- the intake, started from the page, VIEW-045 and BASE-039 ----------
 * An agent the person chooses runs the project's intake and records the map as it goes; the page follows the intake
 * being recorded, so the map grows here. A project with no map offers it first; Administration offers it again, to map
 * the project anew or to check the map against it. While it runs, a bar over the map says so, with its chat and Stop.
 * Its work id, `intake-…`, is never a ticket. */
const INTAKE = {work: null, session: null, agent: null, waiting: 0, reading: false, started: null};
const STARTING = 180000;  // how long an intake's launch may take before its session is made, dispatch's STALE_START
const INTAKE_KEY = project => `metaform.intake.${project}`;
function keptIntake(project = S.project) { try { return localStorage.getItem(INTAKE_KEY(project)); } catch { return null; } }
function keepIntake(work, project = S.project) {
  try { if (work) localStorage.setItem(INTAKE_KEY(project), work); else localStorage.removeItem(INTAKE_KEY(project)); }
  catch { /* storage can be blocked; the sessions read finds a running intake all the same */ }
}
const intakeRunning = () => Boolean(INTAKE.session && INTAKE.session.state === 'running');
/* The intake agent of this project: a running intake session among those read, or the one this page started, read by
 * its id wherever it is kept, since an intake that activates a new metaform keeps its session in the one it began in. */
async function readIntake(signals = []) {
  const project = S.project;
  let session = D.sessions.filter(one => isIntake(one.work_id) && one.state === 'running').at(-1) || null;
  const kept = keptIntake(project);
  // launched by this page and not yet made: its runner is starting, so it is shown as starting until its session is
  // made or its launch would have been given up
  const launching = INTAKE.started && INTAKE.started.project === project && Date.now() - INTAKE.started.at < STARTING
    ? INTAKE.started : null;
  if (!session && kept && !INTAKE.reading) {
    INTAKE.reading = true;
    try {
      const found = await read('dispatch-sessions', {id: kept, thread: 'false'});
      if (S.project !== project) return;
      session = (found.sessions || []).at(-1) || null;
      signals = [...signals, ...(found.signals || [])];
      if (session && session.state !== 'running') session = null;
      if (!session && !(launching && launching.work === kept)) keepIntake(null, project);
    } catch { session = null; } finally { INTAKE.reading = false; }
  }
  if (S.project !== project) return;
  if (session) INTAKE.started = null;
  else if (launching) session = {work_id: launching.work, agent: launching.agent, state: 'running', session_id: null, activity: null};
  INTAKE.session = session;
  INTAKE.work = session?.work_id || null;
  INTAKE.agent = session?.agent || null;
  INTAKE.waiting = session ? signals.filter(one => WAITS_ON_PERSON.includes(one.signal) && one.active !== false
    && one.work_id === session.work_id).length : 0;
  // what the intake's guard and its runner say of it, such as no first record yet or reading earlier conclusions
  INTAKE.signals = session ? signals.filter(one => one.active !== false && one.work_id === session.work_id
    && !WAITS_ON_PERSON.includes(one.signal)) : [];
  drawIntake();
}
/* The bar over the map while an intake runs or is being recorded: what is happening, its agent, and its acts. */
/* The signals an intake's session raises, said in words on its bar: [words, status class, why]. A signal not named here
 * is said by its own name. */
const INTAKE_SIGNALS = {
  'no-first-record': ['No record yet', 'input_required', 'The intake has read for a while and recorded nothing: open its chat to see what it is doing.'],
  'first-record-late': ['No record yet', 'input_required', 'The intake has read for a while and recorded nothing: open its chat to see what it is doing.'],
  'intake-conclusions': ['Reading conclusions', 'input_required', 'It reached for a report, review, log or notes drawn earlier in place of the project itself, and would inherit their errors.'],
  'conclusion-reading': ['Reading conclusions', 'input_required', 'It reads earlier reports and notes in place of the project itself, and inherits their errors.'],
  conclusions: ['Reading conclusions', 'input_required', 'It reads earlier reports and notes in place of the project itself, and inherits their errors.'],
  silent: ['Silent', 'waiting', 'It has said nothing for a while.'],
  'spinning-calls': ['Repeating calls', 'failed', 'It makes the same calls again and again.'],
  'spinning-time': ['Long turn', 'waiting', 'Its turn has run long.'],
  'repeated-failure': ['Failing', 'failed', 'The same step fails again and again.'],
  'login-needed': ['Needs a login', 'login', 'Its agent needs a login, which only you can give.'],
  budget: ['Budget reached', 'failed', 'It reached a spend budget.'],
};
function drawIntake() {
  const bar = $('#intakeBar');
  const running = intakeRunning(), recording = LIVE.layer !== null;
  bar.hidden = !(running || recording);
  drawEmpty();
  if (bar.hidden) return;
  const parts = S.elements.size;
  // the intake guard's page side: no record yet is said with how long the agent has been at it, from its session's
  // start, said again at each change the page hears, never by a timer of its own
  // the runner's own word on it first, its `intake` state, M04: the phase and when it began
  const guard = (D.states || {})[INTAKE.session?.session_id]?.intake || null;
  const since = guard?.began || INTAKE.session?.started || null;
  const waitingFirst = guard ? guard.phase === 'waiting for first record' : INTAKE.session?.activity === 'working';
  const firstWait = running && !recording && !INTAKE.waiting && since && waitingFirst && !parts
    ? `Waiting for the first record · ${ago(since) === 'now' ? 'just started' : `${ago(since)} since it started`}${guard?.steered ? ' · told to record' : ''}` : null;
  const doing = INTAKE.waiting ? `${agentName(INTAKE.agent)} waits for your permission`
    : recording ? `Recording ${LIVE.layer} · ${plural(parts, 'part')} so far`
    : firstWait || (INTAKE.session?.activity === 'working' ? 'Reading the project' : 'Starting');
  bar.classList.toggle('asks', INTAKE.waiting > 0);
  const said = (INTAKE.signals || []).map(one => h('span', {class: `statechip ${INTAKE_SIGNALS[one.signal]?.[1] || 'waiting'}`,
    title: one.detail || one.message || one.reason || INTAKE_SIGNALS[one.signal]?.[2] || ''},
  INTAKE_SIGNALS[one.signal]?.[0] || String(one.signal || '').replace(/-/g, ' ')));
  fill(bar, h('span', {class: 'pulse', 'aria-hidden': 'true'}),
    h('span', {class: 'what'}, h('b', {}, running ? `Intake · ${agentName(INTAKE.agent)}` : 'Intake'),
      h('span', {class: 'doing'}, running ? doing : `Recording ${LIVE.layer} · ${plural(parts, 'part')} so far · by an agent outside the page`),
      said.length ? h('span', {class: 'signals'}, said) : null),
    running ? h('button', {class: `btn sm ${INTAKE.waiting ? 'primary' : ''}`, type: 'button', onclick: () => openIntakeChat()},
      INTAKE.waiting ? 'Answer' : 'Chat') : null,
    running ? h('button', {class: 'btn sm danger', type: 'button', onclick: stopIntake}, 'Stop')
      : h('button', {class: 'btn sm', type: 'button', title: 'Start an agent that goes on with this intake, once no agent is still recording it',
        onclick: () => openIntake({resume: true})}, 'Take over…'));
}
/* The intake's chat in the dock: it is already a conversation, so it is opened on its session, never through a ticket. */
function openIntakeChat(work = INTAKE.work, session = INTAKE.session?.session_id || null, {focus = false} = {}) {
  if (!work) return;
  const agent = INTAKE.work === work ? INTAKE.agent : D.sessions.find(one => one.work_id === work)?.agent;
  openHelpdesk(work, `the intake agent (${agentName(agent)})`, STANDBY, session, 'intake', {focus});
  if (DOCK.chat) DOCK.chat.mine = true;
}
async function stopIntake() {
  const work = INTAKE.work;
  if (!work || !await confirmAct({title: 'Stop the intake?', text: `${agentName(INTAKE.agent)} stops and its chat ends.`,
    lost: ['The agent and its session; what it was about to record next'],
    kept: ['Everything it recorded so far, in its layer', 'A new intake can take this one over and go on with it'],
    verb: 'Stop the intake', cancel: 'Keep it running'})) return;
  if (await wrote('/api/dispatch-stop', {work_id: work})) {
    toast('The intake agent was stopped.');
    keepIntake(null);
    INTAKE.started = null;
    await renderAgents();
  }
}
/* The window an intake starts from: the agent, an optional note for it, and Start; a refusal is said with its next
 * step, and the step offered as a button where the page can take it: taking over an intake left being recorded, or
 * opening the one already at work. */
async function openIntake({resume = false} = {}) {
  showAdmin(false);
  const box = $('#intake'), mapped = !noMetaform() && S.elements.size > 0;
  if (intakeRunning() && !resume) {
    openIntakeChat();
    return toast(`An intake is running: ${agentName(INTAKE.agent)}. Its chat is open.`);
  }
  $('#intake .title').textContent = mapped ? `Run the intake again · ${S.project}` : `Map ${S.project}`;
  fill($('#intake .lead'), mapped
    ? `An agent runs the intake on ${S.project} as it is now and records what it finds. The map follows it as it records.`
    : `An agent reads ${S.project} and records its map as it goes. You watch the map grow here, part by part.`);
  const host = $('#intake .pickhost');
  if (!host.firstChild) host.append(summonPicker('intake', {label: 'Agent for the intake'}));
  const note = $('#intake textarea.note');
  $('#intake .suggest').hidden = !mapped;
  fill($('#intake .failed'));
  $('#intake .failed').hidden = true;
  $('#intake .resume').hidden = !resume;
  INTAKE.resume = resume;
  $('#intake .start').textContent = resume ? 'Take over the intake' : 'Start the intake';
  box.hidden = false;
  readHarnesses();
  if (!note.value) note.focus();
}
async function startIntake() {
  const button = $('#intake .start'), note = $('#intake textarea.note'), agent = summonAgent();
  if (!agent) return showIntakeRefusal({error: 'No agent can start here.', next: HARNESS.next || 'metaform dispatch agents'});
  button.disabled = true;
  const sent = await posted('/api/dispatch-intake', {agent, text: note.value.trim() || undefined, resume: INTAKE.resume || undefined});
  button.disabled = false;
  if (!sent.ok) return showIntakeRefusal(sent.body);
  const started = sent.body;
  $('#intake').hidden = true;
  note.value = '';
  keepIntake(started.work_id);
  INTAKE.started = {project: S.project, work: started.work_id, agent: started.agent, at: Date.now()};
  INTAKE.work = started.work_id;
  INTAKE.agent = started.agent;
  INTAKE.session = {work_id: started.work_id, agent: started.agent, state: 'running', session_id: started.session_id, activity: null};
  drawIntake();
  toast(`${agentName(started.agent)} is starting on the intake. The map grows here as it records.`);
  await renderAgents();
}
function showIntakeRefusal(body) {
  const box = $('#intake .failed'), next = body?.next || '';
  const acts = [];
  const running = /dispatch stop (intake-[0-9a-f]+)/.exec(next);
  if (/resume=true/.test(next)) acts.push(h('button', {class: 'btn sm', type: 'button', onclick: () => {
    INTAKE.resume = true; $('#intake .resume').hidden = false; $('#intake .start').textContent = 'Take over the intake';
    fill(box); box.hidden = true; $('#intake .start').focus();
  }}, 'Take it over'));
  if (running) acts.push(h('button', {class: 'btn sm', type: 'button', onclick: () => {
    $('#intake').hidden = true; INTAKE.work = running[1]; openIntakeChat(running[1], null);
  }}, 'Open its chat'));
  fill(box, h('p', {}, h('b', {}, body?.error || 'The intake did not start.')),
    next ? h('p', {class: 'next'}, 'Next: ', h('code', {}, next)) : null,
    acts.length ? h('div', {class: 'acts'}, acts) : null);
  box.hidden = false;
}
$('#intake .close').onclick = $('#intake .cancel').onclick = () => { $('#intake').hidden = true; };
$('#intake .start').onclick = startIntake;
for (const button of document.querySelectorAll('#intake .suggest button')) button.onclick = () => {
  const note = $('#intake textarea.note');
  note.value = button.dataset.text;
  note.focus();
};
overlay($('#intake'), {kind: 'dialog', close: () => { $('#intake').hidden = true; }, focus: () => $('#intake textarea.note')});
$('#intakeBtn').onclick = () => openIntake();
/* A project with no map yet says so over the map, with the intake as the one thing to do. */
function drawEmpty() {
  const panel = $('#p-object > .emptypanel');
  if (panel) emptyActs(panel);
  const empty = !S.loading && !S.opening && S.project && !S.elements.size && LIVE.layer === null && !intakeRunning() && !MEM.key;
  $('#emptyStage').hidden = !empty;
  if (!empty) return;
  fill($('#emptyStage .what'), noMetaform() ? `${S.project} has no map yet.` : `${S.project}'s map is empty.`);
}
$('#emptyStage .start').onclick = () => openIntake();

/* A write whose refusal the page shows in place, with its next step, rather than in a toast. */
async function posted(path, given) {
  try {
    const response = await reach(path, {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({project: S.project, base: S.base, ...given})}, 0);
    const body = await response.json().catch(() => ({error: 'The server did not answer with JSON.'}));
    return {ok: response.ok, status: response.status, body};
  } catch (error) { return {ok: false, status: 0, body: {error: error.message}}; }
}

/* ---------- the build panel, BASE-060 ----------
 * Four builds, each a large choice with what it makes: the project as an archive, the project with Metaform for a
 * remote agent, the installer, and the installer with every module. A build that takes modules starts from a shape
 * and lists every module found, each with what it does and whether a remote agent can use it; the project's metaform
 * is always carried by the project builds. The project builds can leave the project's files out, and the remote
 * agent's build takes a task, written in the prompt editor, or onboarding when none is written. One click builds;
 * its stages are a progress bar, the browser saves the file when it is done, and a project wheel's prompt is ready to
 * copy. The panel remembers each project's last choices in this browser. */
const BUILD = {options: null, kind: null, picks: {}, files: true, task: '', job: null, project: null,
  editor: null, docs: null, tab: 'task', saved: {}, heard: new Map(), watching: null};
const BUILD_KEY = project => `metaform.build.${project}`;
function keptBuild(project) { try { return JSON.parse(localStorage.getItem(BUILD_KEY(project)) || '{}') || {}; } catch { return {}; } }
function keepBuild() {
  if (!BUILD.project) return;
  try {
    localStorage.setItem(BUILD_KEY(BUILD.project), JSON.stringify({kind: BUILD.kind, picks: BUILD.picks,
      files: BUILD.files, task: BUILD.task, job: BUILD.job?.build_id || null}));
  } catch { /* storage can be blocked; the panel starts from its defaults */ }
}
const kindOfBuild = () => BUILD.options?.kinds.find(kind => kind.id === BUILD.kind) || null;
const shapeOf = id => BUILD.options?.shapes.find(shape => shape.id === id) || null;
/* The modules chosen for a build that takes them, kept for each build: a project wheel starts from the Remote agent
 * shape and an installer from the modules on at home, as the builds themselves do, BASE-060. */
function pickOf(kind) {
  const known = new Set((BUILD.options?.modules || []).map(module => module.id));
  let pick = BUILD.picks[kind];
  if (!pick || !Array.isArray(pick.modules)) {
    const shape = kind === 'installer' ? 'home' : BUILD.options?.defaults?.shape || 'remote';
    pick = BUILD.picks[kind] = {shape, modules: [...(shapeOf(shape)?.modules || [])]};
  }
  pick.modules = pick.modules.filter(id => known.has(id));  // a module gone since is not offered
  return pick;
}
const sameSet = (one, two) => one.length === two.length && one.every(item => two.includes(item));
const STAGE_WORDS = {resolve: 'Resolve dependencies', collect: 'Collect them', 'pack modules': 'Pack the modules',
  'pack project': 'Pack the project', write: 'Write the file'};
const bytesOf = bytes => bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : bytes >= 1024 ? `${Math.round(bytes / 1024)} KB` : `${bytes} B`;
async function openBuild() {
  const box = $('#build');
  box.hidden = false;
  if (BUILD.project !== S.project) {
    const kept = keptBuild(S.project);
    Object.assign(BUILD, {project: S.project, kind: kept.kind || null, picks: kept.picks && typeof kept.picks === 'object' ? kept.picks : {},
      files: kept.files ?? null, task: kept.task || '', job: null});
    if (kept.job) getJson(`/api/build/${kept.job}`).then(job => { if (BUILD.project === S.project && !BUILD.job) { BUILD.job = job; drawBuildRun(); } })
      .catch(() => { /* a build is kept while the server runs; an older one is gone */ });
  }
  // read on each opening, so a module added or a prompt saved since shows
  if (!BUILD.options) fill($('#build .body'), h('p', {class: 'loading'}, 'Reading what can be built…'));
  try { BUILD.options = await getJson('/api/build/options'); }
  catch (error) { if (!BUILD.options) return fill($('#build .body'), h('div', {class: 'failed', role: 'alert'}, error.message)); }
  const defaults = BUILD.options.defaults || {};
  BUILD.kind = BUILD.options.kinds.some(kind => kind.id === BUILD.kind) ? BUILD.kind : defaults.kind || BUILD.options.kinds[0].id;
  BUILD.files ??= defaults.files ?? true;
  drawBuild();
}
function drawBuild() {
  const options = BUILD.options, kind = kindOfBuild();
  if (!options || !kind) return;
  const takesProject = kind.takes_project;
  const kinds = h('div', {class: 'kinds', role: 'radiogroup', 'aria-label': 'What to build'},
    options.kinds.map(one => h('button', {type: 'button', role: 'radio', class: 'kindcard', 'data-kind': one.id,
      'aria-checked': String(one.id === BUILD.kind), tabindex: one.id === BUILD.kind ? '0' : '-1',
      onclick: () => { BUILD.kind = one.id; keepBuild(); drawBuild(); $(`#build .kindcard[data-kind="${one.id}"]`)?.focus(); }},
      h('i', {class: `i ${{archive: 'i-archive', project: 'i-send', installer: 'i-box', full: 'i-boxes'}[one.id] || 'i-box'}`, 'aria-hidden': 'true'}),
      h('b', {}, one.name), h('span', {}, one.summary))));
  kinds.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
    event.preventDefault();
    const ids = options.kinds.map(one => one.id), at = ids.indexOf(BUILD.kind);
    const next = ids[(at + (['ArrowRight', 'ArrowDown'].includes(event.key) ? 1 : -1) + ids.length) % ids.length];
    BUILD.kind = next; keepBuild(); drawBuild(); $(`#build .kindcard[data-kind="${next}"]`)?.focus();
  });
  const sections = [kinds];
  if (takesProject) sections.push(h('div', {class: 'section project'}, h('div', {class: 'eyebrow'}, 'Project'),
    h('div', {class: 'line'}, h('b', {}, S.project), h('span', {class: 'hint'}, kind.id === 'project'
      ? 'Its map, carried as an archive in the wheel, and its files when they are included.' : 'Its map, and its files when they are included.'))));
  if (kind.takes_files) {
    const files = h('input', {type: 'checkbox', role: 'switch', checked: BUILD.files, onchange: () => { BUILD.files = files.checked; keepBuild(); drawFilesNote(); }});
    const note = h('small', {class: 'hint files-note'});
    const drawFilesNote = () => { note.textContent = BUILD.files
      ? 'The project\'s files go in as they are; version control, virtual environments, caches and build folders never do.'
      : kind.id === 'project' ? 'Left out: the remote agent works on the map alone and returns no file changes.' : 'Left out: the archive holds the map alone.'; };
    drawFilesNote();
    sections.push(h('div', {class: 'section'}, h('label', {class: 'switch'}, files, 'Include the project\'s files'), note));
  }
  if (kind.takes_modules) sections.push(modulesSection(kind));
  else if (kind.id === 'full') sections.push(h('div', {class: 'section'}, h('div', {class: 'eyebrow'}, 'Modules'),
    h('p', {class: 'hint'}, `Every module found: ${options.modules.map(one => one.id).join(', ')}.`)));
  if (kind.takes_prompt) sections.push(promptSection());
  fill($('#build .body'), sections, h('div', {class: 'run', 'aria-live': 'polite'}));
  const go = $('#build .go');
  go.textContent = `Build ${kind.name}`;
  go.disabled = Boolean(BUILD.job && BUILD.job.state === 'running') || (kind.id === 'installer' && !pickOf('installer').modules.length);
  $('#build .stages').textContent = kind.stages.map(stage => STAGE_WORDS[stage] || stage).join(' → ');
  drawBuildRun();
}
function modulesSection(kind) {
  const options = BUILD.options, pick = pickOf(kind.id);
  const shapes = segmented({label: 'Shape', value: options.shapes.find(shape => sameSet(shape.modules, pick.modules))?.id ?? '',
    options: options.shapes.map(shape => ({value: shape.id, label: shape.name, title: shape.modules.length ? `Ticks ${shape.modules.join(', ')}` : 'Ticks none'})),
    onchange: id => { pick.shape = id; pick.modules = [...shapeOf(id).modules]; keepBuild(); drawBuild(); }});
  const tally = h('span', {class: 'hint'}, `${plural(pick.modules.length, 'module')} chosen`);
  const rows = options.modules.map(module => {
    const on = pick.modules.includes(module.id);
    const box = h('input', {type: 'checkbox', checked: on, 'aria-describedby': `mod-${module.id}`, onchange: () => {
      pick.modules = box.checked ? [...new Set([...pick.modules, module.id])] : pick.modules.filter(id => id !== module.id);
      pick.shape = options.shapes.find(shape => sameSet(shape.modules, pick.modules))?.id || null;
      shapes.set(pick.shape ?? '');
      tally.textContent = `${plural(pick.modules.length, 'module')} chosen`;
      keepBuild();
      $('#build .go').disabled = kind.id === 'installer' && !pick.modules.length;
      row.classList.toggle('on', box.checked);
    }});
    const row = h('label', {class: `modrow${on ? ' on' : ''}`},
      box, h('span', {class: 'name'}, module.id),
      h('span', {class: 'about', id: `mod-${module.id}`}, module.summary || ''),
      h('span', {class: 'tags'}, kind.id === 'project' && !module.remote
        ? h('span', {class: 'badge off', title: 'It needs what a hosted agent does not have: a screen, local agents or compiled packages'}, 'Not for a remote agent') : null,
        module.home ? h('span', {class: 'badge', title: 'It is turned on in this home'}, 'On at home') : null));
    return row;
  });
  return h('div', {class: 'section modules'},
    h('div', {class: 'head'}, h('div', {class: 'eyebrow'}, 'Modules'), shapes, tally),
    h('div', {class: 'modlist'},
      kind.id === 'project' ? h('div', {class: 'modrow locked', title: 'A project build always carries the project\'s metaform'},
        h('i', {class: 'i i-lock', 'aria-hidden': 'true'}), h('span', {class: 'name'}, `${S.project}'s metaform`),
        h('span', {class: 'about'}, 'Always included: the map the remote agent works on.'), h('span', {class: 'tags'}, h('span', {class: 'badge ok'}, 'Included'))) : null,
      rows));
}
/* The prompt the remote agent is given: the person's task, or with none written the onboarding, each wrapped in the
 * wrapper, as the build wraps them. */
function promptSection() {
  const prompts = BUILD.options.prompts, task = BUILD.task.trim();
  return h('div', {class: 'section prompt'}, h('div', {class: 'eyebrow'}, 'Prompt'),
    h('div', {class: 'promptcard'},
      h('div', {class: 'which'}, task
        ? [h('b', {}, 'Your task'), h('span', {class: 'first'}, clip(task.split('\n')[0], 120))]
        : [h('b', {}, 'Onboarding'), h('span', {class: 'first'}, `No task written: the agent learns the project, tells you about it and waits for your instructions (${prompts.onboarding.name}, version ${prompts.onboarding.number}).`)],
        h('small', {class: 'hint'}, `Wrapped in ${prompts.wrapper.name}, version ${prompts.wrapper.number}, which tells the agent what the wheel is and how to return its work.`)),
      h('button', {class: 'btn', type: 'button', onclick: () => openBuildPrompt('task')}, h('i', {class: 'i i-pen', 'aria-hidden': 'true'}), task ? 'Edit the task' : 'Write a task')));
}
/* The run: its stages as a bar, then the file, or the stage that failed with its error and next step. */
function drawBuildRun() {
  const host = $('#build .run');
  if (!host) return;
  const job = BUILD.job;
  if (!job) return fill(host);
  if (!job.build_id) return fill(host, h('div', {class: 'eyebrow'}, 'The build did not start'),
    h('div', {class: 'failed', role: 'alert'}, h('b', {}, job.error || 'The build was refused.'),
      job.next ? h('p', {class: 'next'}, 'Next: ', h('code', {}, job.next)) : null));
  const stages = job.stages || kindOfBuild()?.stages || [];
  const at = Math.max(0, stages.indexOf(job.stage));
  const share = job.state === 'done' ? 1 : stages.length ? at / stages.length : 0;
  const bar = progressBar({label: 'Build progress', value: share,
    words: job.state === 'done' ? 'Done' : job.state === 'failed' ? `Stopped at ${STAGE_WORDS[job.stage] || job.stage || 'the start'}` : `${STAGE_WORDS[job.stage] || 'Starting'}…`});
  bar.classList.toggle('stopped', job.state === 'failed');
  const steps = h('ol', {class: 'buildsteps'}, stages.map((stage, index) => {
    const state = job.state === 'done' || index < at ? 'done' : index === at ? (job.state === 'failed' ? 'stopped' : 'now') : 'later';
    return h('li', {class: state}, h('i', {'aria-hidden': 'true'}), h('span', {class: 'visually-hidden'}, `${{done: 'done', stopped: 'stopped here', now: 'under way', later: 'to come'}[state]}: `), STAGE_WORDS[stage] || stage);
  }));
  const parts = [h('div', {class: 'eyebrow'}, job.state === 'done' ? 'Built' : job.state === 'failed' ? 'The build stopped' : 'Building'), bar, steps];
  if (job.state === 'failed') parts.push(h('div', {class: 'failed', role: 'alert'}, h('b', {}, job.error || 'The build failed.'),
    job.next ? h('p', {class: 'next'}, 'Next: ', h('code', {}, job.next)) : null));
  if (job.state === 'done' && job.file) {
    const link = h('a', {class: 'btn sm', href: `/api/build/${job.build_id}/download`, download: job.file},
      h('i', {class: 'i i-download', 'aria-hidden': 'true'}), 'Download again');
    parts.push(h('div', {class: 'result'}, h('i', {class: 'i i-check', 'aria-hidden': 'true'}),
      h('span', {class: 'file'}, h('span', {}, h('b', {}, job.file), job.size ? h('small', {class: 'size'}, ` · ${bytesOf(job.size)}`) : null),
        h('small', {class: 'where'}, 'Saved by your browser; a copy stays in the builds folder of your Metaform home.')), link));
    if (job.prompt) parts.push(h('div', {class: 'wrapped'}, h('div', {class: 'eyebrow'}, 'The prompt for the remote agent'),
      h('p', {class: 'paste'}, `Upload ${job.file} to the agent and paste this as your message:`),
      copyField({label: 'the remote agent\'s prompt', text: job.prompt, rows: 8})));
  }
  fill(host, parts);
}
async function startBuild() {
  const kind = kindOfBuild();
  if (!kind) return;
  const given = {kind: kind.id};
  given.project = kind.takes_project ? S.project : null;  // `posted` sends the page's project with every write
  if (kind.takes_modules) {
    const pick = pickOf(kind.id);
    const shape = pick.shape && sameSet(shapeOf(pick.shape)?.modules || [], pick.modules) ? pick.shape : null;
    if (shape) given.shape = shape; else given.modules = pick.modules;
  }
  if (kind.takes_files) given.files = BUILD.files;
  if (kind.takes_prompt && BUILD.task.trim()) given.prompt = BUILD.task;
  $('#build .go').disabled = true;
  const sent = await posted('/api/build', given);
  if (!sent.ok) {
    BUILD.job = {build_id: null, stages: kind.stages, stage: null, state: 'failed', error: sent.body.error, next: sent.body.next};
    $('#build .go').disabled = false;
    return drawBuildRun();
  }
  BUILD.job = {build_id: sent.body.build_id, stages: sent.body.stages, stage: null, state: 'running', kind: kind.id};
  BUILD.watching = sent.body.build_id;
  keepBuild();
  drawBuildRun();
  showRun();
  // a quick build can be told before its id comes back: what was heard of it meanwhile is taken now, and read once
  // more, so a build that ended while the stream was away still ends here
  const heard = BUILD.heard.get(sent.body.build_id);
  BUILD.heard.clear();
  if (heard) await buildEvent(heard);
  else getJson(`/api/build/${sent.body.build_id}`).then(now => { if (BUILD.job?.build_id === now.build_id && now.state !== 'running' && BUILD.job.state === 'running') buildEvent(now); })
    .catch(() => { /* the stream tells the rest */ });
}
/* A build's progress, pushed on the page's stream as each stage starts and as it ends; the file is saved at its end. */
async function buildEvent(payload) {
  if (!payload) return;
  if (payload.build_id !== BUILD.job?.build_id) {  // another page's build, or this one's before its id came back
    BUILD.heard.set(payload.build_id, payload);
    if (BUILD.heard.size > 16) BUILD.heard.delete(BUILD.heard.keys().next().value);
    return;
  }
  Object.assign(BUILD.job, payload);
  if (payload.state !== 'running') {
    try { Object.assign(BUILD.job, await getJson(`/api/build/${payload.build_id}`)); } catch { /* the event said enough */ }
    if (BUILD.job.build_id !== payload.build_id) return;
    if (payload.state === 'done' && BUILD.watching === payload.build_id) {
      BUILD.watching = null;
      const link = h('a', {href: `/api/build/${payload.build_id}/download`, download: payload.file || ''});
      document.body.append(link); link.click(); link.remove();
      // the panel shows the result; a person who closed it while it built is told in a toast
      if ($('#build').hidden) toast(`Built ${payload.file}. Your browser saves it.`);
    } else if (payload.state === 'failed' && $('#build').hidden) toast(`The build stopped at ${STAGE_WORDS[payload.stage] || 'its start'}: ${String(payload.error || 'it failed').replace(/\.$/, '')}.`);
    if ($('#build .go')) $('#build .go').disabled = false;
    drawBuildRun();
    return showRun();
  }
  drawBuildRun();
}
/* The run is brought into view as it starts and as it ends, where the person looks for it. */
function showRun() {
  requestAnimationFrame(() => $('#build .run')?.scrollIntoView({block: 'nearest', behavior: reduced() ? 'auto' : 'smooth'}));
}
$('#buildBtn').onclick = openBuild;
$('#build .close').onclick = () => { $('#build').hidden = true; };
$('#build .go').onclick = startBuild;
overlay($('#build'), {kind: 'dialog', close: () => { $('#build').hidden = true; }, focus: () => $('#build .kindcard[aria-checked="true"]')});
/* The prompt editor of the remote agent's build, VIEW-013: the task as the person writes it, and the wrapper and the
 * onboarding, the prompt store's own, each saved as its next version; the preview is the prompt as the build makes it,
 * the wheel's name filled in when it is built. */
async function openBuildPrompt(tab = 'task') {
  const box = $('#buildPrompt');
  const prompts = BUILD.options.prompts;
  BUILD.saved = {wrapper: {...prompts.wrapper}, onboarding: {...prompts.onboarding}};
  box.hidden = false;
  if (!BUILD.editor) {
    BUILD.editor = CodeMirror($('#buildPrompt .editor'), {lineNumbers: true, lineWrapping: true, mode: 'markdown'});
    BUILD.editor.on('change', () => buildPromptChanged());
  }
  BUILD.docs = {task: CodeMirror.Doc(BUILD.task, 'markdown'), wrapper: CodeMirror.Doc(prompts.wrapper.text, 'markdown'),
    onboarding: CodeMirror.Doc(prompts.onboarding.text, 'markdown')};
  const tabs = segmented({label: 'What to edit', value: tab, options: [{value: 'task', label: 'Task'},
    {value: 'onboarding', label: 'Onboarding'}, {value: 'wrapper', label: 'Wrapper'}, {value: 'preview', label: 'Preview'}],
    onchange: value => showBuildPrompt(value)});
  fill($('#buildPrompt .tabbar'), tabs);
  showBuildPrompt(tab);
}
function showBuildPrompt(tab) {
  BUILD.tab = tab;
  const preview = tab === 'preview';
  $('#buildPrompt .editor').hidden = preview;
  $('#buildPrompt .preview').hidden = !preview;
  if (preview) fill($('#buildPrompt .preview'), wrappedPreview());
  else {
    BUILD.editor.swapDoc(BUILD.docs[tab]);
    setTimeout(() => { BUILD.editor.refresh(); BUILD.editor.focus(); }, 0);
  }
  buildPromptChanged();
}
function buildPromptChanged() {
  const tab = BUILD.tab, task = BUILD.docs.task.getValue();
  const saved = tab === 'wrapper' || tab === 'onboarding' ? BUILD.saved[tab] : null;
  const changed = saved ? BUILD.docs[tab].getValue() !== saved.text : false;
  const save = $('#buildPrompt .save');
  save.hidden = !saved;
  save.disabled = !changed;
  $('#buildPrompt .revert').hidden = !saved;
  $('#buildPrompt .revert').disabled = !changed;
  fill($('#buildPrompt .about'), tab === 'task'
    ? (task.trim() ? 'The remote agent is given this task, as you write it, inside the wrapper.'
      : `Empty: the remote agent is given the onboarding, ${BUILD.saved.onboarding.name} version ${BUILD.saved.onboarding.number}, inside the wrapper.`)
    : tab === 'preview' ? 'The prompt as the build makes it. The wheel\'s file name is filled in when it is built.'
    : `${saved.name}, version ${saved.number}. Saved as a new version, it is what every build uses from then on; {wheel}, {project} and {task} are filled in by the build.`);
}
function wrappedPreview() {
  const task = BUILD.docs.task.getValue().trim();
  const filled = text => text.replaceAll('{project}', S.project);
  const inner = task || filled(BUILD.docs.onboarding.getValue()).trim();
  const text = filled(BUILD.docs.wrapper.getValue()).replace('{task}', inner).trim();
  return h('pre', {class: 'prompt'}, ...text.split('{wheel}').flatMap((part, index) => index ? [h('mark', {title: 'The wheel\'s file name, filled in when it is built'}, '‹wheel›'), part] : [part]));
}
async function saveBuildPrompt() {
  const tab = BUILD.tab, saved = BUILD.saved[tab];
  if (!saved) return;
  const sent = await posted('/api/save-prompt', {name: saved.name, text: BUILD.docs[tab].getValue(), parent: saved.number});
  if (!sent.ok) return toast(sent.body.error || 'The prompt was not saved.');
  Object.assign(saved, {number: sent.body.number, text: BUILD.docs[tab].getValue()});
  BUILD.options.prompts[tab] = {...saved};
  toast(`Saved ${saved.name} as version ${saved.number}. Every build uses it from now on.`);
  buildPromptChanged();
  if (!$('#build').hidden) drawBuild();
}
$('#buildPrompt .save').onclick = saveBuildPrompt;
$('#buildPrompt .revert').onclick = () => { BUILD.docs[BUILD.tab].setValue(BUILD.saved[BUILD.tab].text); };
// a prompt of the store changed and not saved is asked about before it is left, however the editor is closed
const promptKept = () => !['wrapper', 'onboarding'].some(tab => BUILD.docs && BUILD.saved[tab] && BUILD.docs[tab].getValue() !== BUILD.saved[tab].text)
  || discard('the unsaved changes to the prompts', 'Keep editing');
$('#buildPrompt .done').onclick = $('#buildPrompt .close').onclick = async () => { if (await promptKept()) closeBuildPrompt(); };
function closeBuildPrompt() {
  if (BUILD.docs) { BUILD.task = BUILD.docs.task.getValue(); keepBuild(); }
  $('#buildPrompt').hidden = true;
  if (!$('#build').hidden) drawBuild();
}
overlay($('#buildPrompt'), {kind: 'dialog', close: closeBuildPrompt, guard: promptKept});
// The dock's message box offers the commands as / is typed: the dock's own and those of the agent on view.
slashCommands($('#helpdesk .say'), dockOffered);
// The agent the chat's new chats start with is chosen as the first field of its settings popover, `dockPicker`.
syncResume();

/* ---------- live: the server pushes what modules publish, and the page redraws; nothing polls, VIEW-018 ----------
 * An intake being recorded is drawn as each object arrives, BASE-039; any other write to the metaform shown is read
 * again. Events that come while the page reads are drawn once, when it is done. */
const LIVE = {layer: null, base: null, seen: '', busy: false, again: false, whole: false, named: null, done: 0, drawn: -Infinity,
  brief: false};
const following = () => LIVE.layer !== null && S.base === LIVE.base;
async function loadLive() {
  const page = await read('layer-graph', {layer: LIVE.layer});
  const text = JSON.stringify(page);
  if (text === LIVE.seen || !following()) return;
  LIVE.seen = text;
  S.elements = new Map(page.elements.map(entry => [entry.element.id, entry]));
  S.joins = page.joins.map(withProviders);
  S.items = new Map();
  draw3D(); renderLegend();
  drawIntake();  // the bar over the map counts the parts recorded so far
  await build2D();
  const keep = S.selected && (S.elements.has(S.selected) || joinOf(S.selected)) ? S.selected : null;
  const start = keep || (S.cleared ? null : entryOf());  // a selection let go of stays let go, VIEW-008
  if (start) select(start, false, false, false, true);
  else if (S.cleared && S.elements.size) noneSelected();
  else fill($('#p-object'), h('p', {class: 'empty'}, 'Nothing to show in these layers yet.'));
}
/* Follow the intake being recorded, found = {layer, base_id}, or return to the map when it is no longer being
 * recorded, saying what happened: it finished when its metaform still stands, or it stopped because the project was
 * cleared, the one thing that takes a metaform away, VIEW-019. */
async function follow(found) {
  if (found) ELSEWHERE.followed.add(`${S.project}/${found.base_id}/${found.layer}`);
  if (found && found.layer !== LIVE.layer) {
    Object.assign(LIVE, {layer: found.layer, base: found.base_id, seen: ''});
    if (S.base !== found.base_id) await loadProject(found.base_id);
    else { S.layers = (await read('layers', {limit: 0})).results; renderChips(); }
    drawIntake();
    toast(`An intake is being recorded in ${found.layer}; the map follows it as each object is recorded.`);
  } else if (!found && LIVE.layer) {
    const {base} = LIVE;
    const stands = (await read('bases', {limit: 0})).results.some(item => item.id === base);
    Object.assign(LIVE, {layer: null, base: null, seen: ''});
    renderLegend();
    drawIntake();
    toast(stands ? `The intake finished.` : `The intake stopped: ${S.project} was cleared.`);
    if (stands) attend(`intake:${base}`, 'The intake finished', null, null);  // the mascot says so too, `ATTN`
    await loadProject();
    return;
  }
  if (following()) await loadLive();
}
/* On connecting, and on the browser's own reconnect, what is being recorded now is read once. */
async function recordingNow() {
  const found = (await read('intake-recording')).results[0] || null;
  await follow(found ? {layer: found.layer.name, base_id: found.base_id} : null);
}
/* One push: the chassis fired map.changed for a metaform of this project, or for its metaforms themselves, VIEW-018.
 * The page reads what is being recorded, then follows it, returns to the map when it has finished, shows the active
 * metaform when the project's metaforms changed, or reads the layers and the map again, keeping the view and the
 * selection. A change to tickets or messages alone reads only those, below. */
/* An intake happening in another project takes the page there, as one started in this project takes the map to it:
 * the person watches an intake where it is recorded. Only a change written into the intake being recorded does it,
 * once for that intake, so a person who goes back is left there; nothing else in another project ever switches the
 * page, and a change of tickets or agents elsewhere is not even looked at. */
const ELSEWHERE = {followed: new Set(), busy: false};
async function intakeElsewhere(payload) {
  const named = payload.tables;
  if (ELSEWHERE.busy || named === 'dispatch' || ticketsOnly(payload)) return;
  ELSEWHERE.busy = true;
  try {
    const found = (await getJson(`/api/intake-recording?project=${encodeURIComponent(payload.project)}`)).results?.[0];
    // only a change written into the intake being recorded: an intake happening now, never an old one left unfinished
    if (!found || payload.base_id !== found.base_id) return;
    const key = `${payload.project}/${found.base_id}/${found.layer.name}`;
    if (ELSEWHERE.followed.has(key) || payload.project === S.project) return;
    ELSEWHERE.followed.add(key);
    S.projects = (await getJson('/api/projects')).projects || [];  // a first run registers its folder just before
    if (!G) start3D();  // a page opened with no project has not drawn a 3D map yet
    toProject(payload.project);
    fill($('#proj'), ...S.projects.map(item => h('option', {value: item.id, selected: item.id === S.project}, item.id)));
    await loadProject();
    listen();
    toast(`An intake started in ${payload.project}; the page follows it there.`);
  } catch (error) { /* a project that cannot be read now is not followed */ }
  finally { ELSEWHERE.busy = false; }
}
async function changed(event) {
  if (event.topic !== 'map.changed') return;
  if (event.payload?.project && event.payload.project !== S.project) return intakeElsewhere(event.payload);
  if (event.payload?.project !== S.project) return;
  if (WS.on) {  // the workspace's panes that read the map, its messages and its workflow runs, read again
    WS.refresh();
    for (const page of ['messages', 'runs']) if (WS.isShown(WS.paneOfPage(page)?.id)) PANE_VIEWS[page].show();
  } else if (WS.active) WS.refresh();
  const named = event.payload.tables;
  if (briefTouched(named)) LIVE.brief = true;
  if (Array.isArray(named) && named.length && named.every(table => String(table).startsWith('jev.'))) {
    if (!LIVE.busy) { if (!$('#p-brief').hidden) renderBrief(); LIVE.brief = false; }
    return;  // a Jev decision kept at a node is an item there: its brief changes, the map does not
  }
  const agents = named === 'dispatch' || Array.isArray(named) && named.some(table => String(table).startsWith('dispatch.'));
  if (agents) agentsChanged(!linesOnly(event.payload));
  // an agent's own tables, its thread, sessions and settings, change no map
  if (named === 'dispatch' || Array.isArray(named) && named.length && named.every(table => String(table).startsWith('dispatch.'))) return;
  const tickets = ticketsOnly(event.payload);
  if (tickets && event.payload.base_id && event.payload.base_id !== S.base) return;  // another metaform's
  if (!tickets) { LIVE.whole = true; LIVE.named = LIVE.named && opsOnly(LIVE.named) ? [...LIVE.named, ...(named || [])] : named || null; }
  if (LIVE.busy) { LIVE.again = true; return; }
  LIVE.busy = true;
  try {
    do {
      await settled();
      LIVE.again = false;
      if (!LIVE.whole && S.whole && !LIVE.layer) { await ticketsChanged(); continue; }
      LIVE.whole = false;
      const named = LIVE.named; LIVE.named = null;
      LIVE.drawn = performance.now();  // a whole reload: the next waits SPACING, a ticket change does not
      const found = (await read('intake-recording')).results[0] || null;
      if (found || LIVE.layer) { await follow(found ? {layer: found.layer.name, base_id: found.base_id} : null); continue; }
      const metaforms = (await read('bases', {limit: 0})).results;
      const same = metaforms.length === S.bases.length && metaforms.every(item =>
        S.bases.some(known => known.id === item.id && known.active === item.active));
      if (!same) await loadProject();  // the project's metaforms changed: show the active one, as on opening
      else if (opsOnly(named) && await appliedOps()) { await ticketsChanged(); continue; }  // the ops since the drawn sequence, applied
      else {
        S.layers = (await read('layers', {limit: 0})).results;
        renderChips();
        await loadGraph(false);
      }
      boardFromTickets();  // the work the map's read took, not read again
    } while (LIVE.again);
  } catch (error) { toast(error.message); } finally {
    LIVE.busy = false; LIVE.done++;
    if (LIVE.brief && !$('#p-brief').hidden) renderBrief();  // what is held at the node, and its numbers, changed
    LIVE.brief = false;
  }
}
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
  if (element.within && [...S.elements.values()].some(entry => entry.element.address === element.within)) return element.within;
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
async function appliedOps() {
  if (following() || !S.whole || typeof S.seq !== 'number') return false;
  const ops = await read('ops', {after: S.seq, limit: 0});
  if (!Array.isArray(ops) || !ops.length) return true;  // nothing of the map changed: the tickets are read beside
  for (const op of ops) {
    if (op.kind === 'layer' || op.kind === 'selection') return false;  // what is in view may have changed
    if (op.kind === 'type') continue;
    const layer = layerInView(op.layer_id);
    if (layer === null && op.op !== 'remove') return false;  // a layer this page has not read yet
    if (layer === false) continue;  // not in view: nothing to draw
    const data = op.data || {};
    const gone = op.op === 'remove';
    if (op.kind === 'element') {
      if (gone) { S.elements.delete(op.id); continue; }
      const kept = S.elements.get(op.id)?.element || {};
      const element = {...kept, id: op.id, layer_id: op.layer_id, layer: layer.name,
        ...('address' in data ? {address: data.address} : {}), ...('name' in data ? {name: data.name} : {}),
        ...('name_length' in data ? {name_length: data.name_length} : {}), ...('role' in data ? {role: data.role} : {}),
        ...('within' in data ? {within: data.within} : {}), ...('note' in data ? {note: data.note} : {})};
      if (!element.address) return false;
      element.reading = plainWords(element.address);
      element.short_name = shortName(element.address, element.name_length);
      element.open_work = kept.open_work || [];
      S.elements.set(op.id, {element, parent: holderOf(element)});
    } else if (op.kind === 'join') {
      S.joins = S.joins.filter(join => join.id !== op.id);
      if (gone) continue;
      const before = S.whole.joins.find(join => join.id === op.id) || {};
      const held = 'held' in data ? data.held : before.providers || [];
      const receiver = 'receiver' in data ? data.receiver : before.receiver;
      const join = {id: op.id, layer_id: op.layer_id, layer: layer.name, type: data.type ?? before.type ?? 'purpose',
        receiver, receiver_address: S.elements.get(receiver)?.element.address ?? null,
        purpose: 'purpose' in data ? data.purpose : before.purpose ?? null, ef: 'ef' in data ? data.ef : before.ef ?? null,
        ifd: 'ifd' in data ? data.ifd : before.ifd ?? null, elements: heldOf(held), open_work: before.open_work || [],
        element: 'element' in data ? data.element : before.element ?? null};
      S.joins.push(withProviders(join));
    } else if (op.kind === 'item' || op.kind === 'property') {
      const key = (op.kind === 'item' ? 'i:' : 'r:') + op.id;
      if (gone) { S.items.delete(key); continue; }
      const kept = S.items.get(key)?.item || {};
      const value = 'value' in data ? JSON.parse(data.value) : kept.value;
      const refs = 'refs' in data ? data.refs.map(([k, v]) => ({key: k, value: v})) : kept.refs || [];
      const extra = 'extra' in data ? (data.extra ? JSON.parse(data.extra) : null) : kept.extra ?? null;
      const item = op.kind === 'item'
        ? {...kept, id: op.id, layer_id: op.layer_id, layer: layer.name, value, refs, extra,
           target: 'target_kind' in data ? {kind: data.target_kind, id: data.target_id} : kept.target,
           link: 'link_kind' in data ? (data.link_kind ? {kind: data.link_kind, id: data.link_id} : null) : kept.link ?? null,
           read_first: 'read_first' in data ? !!data.read_first : !!kept.read_first,
           always_show: 'always_show' in data ? !!data.always_show : !!kept.always_show}
        : {...kept, id: op.id, layer_id: op.layer_id, layer: layer.name, value, refs, extra,
           element_id: 'element_id' in data ? data.element_id : kept.element_id,
           address: S.elements.get('element_id' in data ? data.element_id : kept.element_id)?.element.address ?? null};
      if (op.kind === 'item' && !item.target) return false;
      S.items.set(key, {kind: op.kind, key, item, value, layer: layer.name, layerKind: layer.kind});
    }
  }
  for (const entry of S.elements.values()) entry.parent = holderOf(entry.element);
  S.whole = {elements: S.elements, joins: S.joins};
  S.seq = ops[ops.length - 1].seq;
  flowWritten(ops);  // what was written on a node lands there as a record, `FLOW`
  draw3D();
  renderLegend();
  await build2D();
  if (S.selected && (S.elements.has(S.selected) || joinOf(S.selected))) await select(S.selected, false, false, false, true);
  else if (S.selected) { const start = [...S.elements.values()].find(entry => entry.element.role === 'DE')?.element.id || S.elements.keys().next().value; if (start) await select(start, false, false, false, true); }
  return true;
}
/* Agents write several times a second. The whole map is read again at most once every SPACING, and nothing is drawn
 * while the person is zooming or dragging, so nothing moves under their hands; the changes in between are read
 * together. */
const QUIET = 800, SPACING = 3000;
const HANDS = {at: 0, down: false};
addEventListener('wheel', () => { HANDS.at = performance.now(); }, {passive: true, capture: true});
addEventListener('pointerdown', () => { HANDS.down = true; HANDS.at = performance.now(); }, true);
addEventListener('pointerup', () => { HANDS.down = false; HANDS.at = performance.now(); }, true);
async function settled(after = LIVE.drawn + SPACING) {
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
function briefTouched(named) {
  if (!Array.isArray(named)) return named !== 'dispatch';
  return named.some(table => BRIEF_TABLES.has(table) || /^(memory|jev)\./.test(table)
    || !TICKET_TABLES.has(table) && !/^(dispatch|web|workflow)\./.test(table));
}
const ticketsOnly = payload => Array.isArray(payload.tables) && payload.tables.length > 0
  && payload.tables.every(table => TICKET_TABLES.has(table) || String(table).startsWith('dispatch.'));
/* A change the page can apply from the ops alone, STORE-046: the log, the objects registry, the kinds of op, and the
 * tickets' tables; a module's own table, such as the memory graph's, is read again whole. */
const opsOnly = named => Array.isArray(named) && named.length > 0 && named.every(table => table === 'ops'
  || table === 'objects' || String(table).startsWith('op:') || TICKET_TABLES.has(table) || String(table).startsWith('dispatch.'));
/* A change to tickets or messages alone: work and the open messages are read once each, and the nodes' lights, the
 * figures, the board and the selected node's panel are drawn from them, VIEW-035 and VIEW-037. */
async function ticketsChanged() {
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
function boardFromTickets() {
  if ($('#board').hidden || !S.tickets) return;
  B.tickets = S.tickets;
  drawBoard();
}
/* Each node's open work as the map read gives it, MAP-050: the states its open records hold, in row order, then what
 * waits for the person there; rebuilt from the tickets and open messages read. A plain task adds nothing. */
function openWork() {
  const open = new Map(), add = (key, what) => open.set(key, [...(open.get(key) || []), what]);
  for (const ticket of S.tickets || []) if (!ticket.done && ticket.condition)
    add(`${ticket.node_kind}:${ticket.node_id}`, ticket.condition);
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
const linesOnly = payload => payload.tables === 'dispatch' && Array.isArray(payload.dispatch_tables)
  && payload.dispatch_tables.length > 0 && payload.dispatch_tables.every(table => table === 'dispatch.lines');
async function agentsChanged(whole = false) {
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
function listen() {
  // the stream names the project this page shows: agents are started only for a project some page has open
  if (STREAM) STREAM.close();
  const source = STREAM = new EventSource(`/api/events?project=${encodeURIComponent(S.project || '')}`);
  source.onmessage = message => {
    const event = JSON.parse(message.data);
    if (event.topic === 'build') return buildEvent(event.payload);  // the build panel's progress, BASE-060
    if (event.topic === 'map.flow') return flowEvent(event.payload);  // where agents' tool calls reached, `FLOW`
    if (event.topic === 'mascot') return mascotEvent(event.payload);  // the system agent moves the mascot, `MASCOT`
    if (event.topic === 'workspace') return loadWorkspace();  // arranged on another page, or in the settings
    if (debugAt('verbose')) { traced({kind: 'event', what: event.topic, raw: debugAt('trace') ? message.data : null}); dlog('verbose', 'event', event); }
    changed(event);
  };
  source.onopen = () => {
    recordingNow().catch(error => toast(error.message));
    agentsChanged();
  };
}

/* Every item and property of the layers, read as the context sees them, so selection, masks and hidden layers apply
 * as in every read, VIEW-017. */
async function itemsOf(generation) {
  const found = new Map();
  for (const layer of S.layers.filter(item => item.ready && item.kind !== 'base')) {
    let after = null;
    do {
      const page = await read('layer-items', {layer: layer.name, in_context: 'true', limit: 500, ...(after ? {after} : {}), ...viewLayers()});
      if (generation !== S.loading) return found;
      for (const item of page.results) {
        const property = !('target' in item);  // a property sits on an element, an item on a node
        const key = property ? 'r:' + item.id : 'i:' + item.id;
        found.set(key, {kind: property ? 'property' : 'item', key, item, value: item.value, layer: layer.name, layerKind: layer.kind});
      }
      after = page.next;
    } while (after);
  }
  return found;
}

/* ---------- loading: projects, metaforms, layers, then the graph page by page ---------- */
/* The steps filed and planned of each node's open tickets, the most advanced first, VIEW-035: an element's by its
 * id, a join's on its purpose vertex. */
async function progressOf() {
  const found = new Map(), project = S.project, metaform = S.base;
  let tickets = [];
  try { tickets = (await read('work', {limit: 0})).results || []; } catch (error) { return found; }
  if (S.project !== project || S.base !== metaform) return found;  // a late answer for a project the person left
  S.tickets = tickets;
  for (const ticket of tickets) {
    if (!ticket.taken || ticket.done) continue;
    const keys = ticket.node_kind === 'join' ? ['p:' + ticket.node_id] : [ticket.node_id];
    const done = {filed: ticket.steps_done || 0, planned: ticket.steps || 0};
    const share = one => one.planned ? one.filed / one.planned : one.filed;
    for (const key of keys) if (!found.has(key) || share(done) > share(found.get(key))) found.set(key, done);
  }
  return found;
}
/* A load counts as opening from its first read until the panel of what it selects has been read, so loaded() is not
 * true while the page still reads what it loads. */
async function opening(work) {
  S.opening++;
  try { return await work(); } finally { S.opening--; if (!S.opening) drawEmpty(); }
}
/* agents: whether the agents key is read with the map; a map change does not read it, since the agents are read again
 * on dispatch events, VIEW-018. */
function loadGraph(agents = true) { return opening(() => readGraph(agents)); }
async function readGraph(agents) {
  if (following()) { LIVE.seen = ''; S.loading = 0; return loadLive(); }
  const generation = ++S.loading, project = S.project, metaform = S.base;
  // a read is dropped once another has begun or the person has chosen another project or metaform
  const stale = () => generation !== S.loading || S.project !== project || S.base !== metaform;
  S.elements = new Map(); S.joins = [];
  let after = null, whole = false;
  try {
    do {
      const page = await read('graph', {limit: 500, ...(after ? {after} : {}), ...viewLayers()});
      if (stale()) return;
      for (const entry of page.elements) S.elements.set(entry.element.id, entry);
      S.joins.push(...page.joins.map(withProviders));
      draw3D(); renderLegend();
      after = page.next;
    } while (after);
    whole = true;
    S.whole = {elements: S.elements, joins: S.joins};
    S.seq = await read('sequence');  // the sequence the map drawn is at; the ops after it are applied, STORE-046
    if (stale()) return;
    const items = await itemsOf(generation);
    if (stale()) return;
    S.items = items;
    const memory = await memoryOf();
    if (stale()) return;
    S.memory = memory;
    renderOrphans();
    S.progress = await progressOf();
    figures(S.tickets || []);
  } catch (error) {
    toast(error.message);
    // The last whole map read is kept: a read that fails, as every read does while the server restarts, puts it back,
    // and the failure is said. Another metaform's is never put back, since its load begins with none.
    if (!stale() && !whole && S.whole) Object.assign(S, S.whole);
  }
  if (stale()) return;
  S.loading = 0;
  draw3D();
  renderLegend();
  const told = Promise.all([renderMessages(), agents && renderAgents()]);  // read beside the 2D map; the load ends when they are
  await build2D();
  const keep = S.selected && (S.elements.has(S.selected) || joinOf(S.selected)
    || MEM.network?.entities.includes(S.selected) || memoryThing(S.selected)) ? S.selected : null;
  const start = keep || MEM.key || (S.cleared ? null : entryOf());  // a selection let go of stays let go, VIEW-008
  if (!start) S.cleared && S.elements.size ? noneSelected() : fill($('#p-object'), emptyPanel());
  else {
    // the whole map fitted once it has spread, unless a selection has flown the camera to its node meanwhile
    if (!keep) setTimeout(() => { if (G && !V3.focus && S.selected === start) fit3d(800, 60); }, 2200);
    await select(start, false, false, false, true);
  }
  await told;
  drawIntake();
  window.metaform.onLoaded?.();  // the map view in an AI tool then turns to the address its call named, MCP-037
  READY.done?.();  // `window.metaform.ready`, once, the first map drawn
}
async function loadMetaform() {
  S.view = null; S.selected = null; S.cleared = false; IN.length = 0; M.base = null; dropMemories(); renderCrumbs();
  S.elements = new Map(); S.joins = []; S.whole = null;
  S.layers = (await read('layers', {limit: 0})).results;
  renderChips();
  if ($('#p-prov').hidden === false) renderProv();
  await loadGraph();
}
function loadProject(wanted = null) { return opening(() => readProject(wanted)); }
async function readProject(wanted) {
  const project = S.project;
  readHarnesses();
  loadWorkspace();
  await readAutostart();
  const metaforms = (await read('bases', {limit: 0})).results;
  if (S.project !== project) return;  // the metaforms of a project the person has left

  S.bases = metaforms;
  const active = metaforms.find(item => item.id === wanted) || metaforms.find(item => item.active) || metaforms[0];
  S.base = active ? active.id : null;
  fill($('#mf'), ...(metaforms.length ? metaforms.map(item => h('option', {value: item.id, selected: item === active}, item.name + (item.active ? ' · active' : '')))
    : [h('option', {}, 'none yet')]));
  $('#mf').disabled = !metaforms.length;
  baseButtons();
  foldHeader();  // the names chosen take their room
  await loadMetaform();
}
/* Activate and Remove beside the base chooser, STORE-041: the chooser only changes what the page shows; Activate makes
 * the chosen base the active one, and Remove takes it out of the project with a copy kept. Neither acts on the active
 * base, as the command refuses to. */
function baseButtons() {
  const chosen = S.bases.find(item => item.id === $('#mf').value);
  $('#activateBase').disabled = !chosen || chosen.active;
  $('#removeBase').disabled = !chosen || chosen.active;
}
$('#activateBase').onclick = async () => {
  const chosen = S.bases.find(item => item.id === $('#mf').value);
  if (!chosen) return;
  $('#activateBase').disabled = true;
  if (await wrote('/api/activate-base', {name: chosen.name})) toast(`${chosen.name} is the active base.`);
  else baseButtons();
};
/* Removing a base cannot be undone from the page, so it is asked first, saying what goes and what is kept. */
$('#removeBase').onclick = async () => {
  const chosen = S.bases.find(item => item.id === $('#mf').value);
  if (!chosen || !await confirmAct({title: `Remove base ${chosen.name}?`,
    text: `It is taken out of ${S.project}. The page cannot bring it back; a copy of its store is kept.`,
    lost: [`Base ${chosen.name}, from the bases of ${S.project} and from what agents and the page can read`],
    kept: ['A copy of its store, under backups/remove-base in the Metaform home', `The active base and every other base of ${S.project}`],
    verb: 'Remove base'})) return;
  $('#removeBase').disabled = true;
  const done = await wrote('/api/remove-base', {name: chosen.name, confirm: true});
  if (done) toast(`Removed ${chosen.name}; its store is kept at ${done.kept}.`);
  else baseButtons();
};
/* Another project chosen: the agents drawn are the project left's, so its agent window closes and its agents go,
 * VIEW-039, and its figures with them at once, having no map here to walk back on, VIEW-035; the new project's are
 * read with its map. */
function toProject(id) {
  S.project = id;
  S.tickets = []; B.tickets = [];  // nothing of the project left behind shows on the next one
  if (!$('#board').hidden) drawBoard();
  location.hash = 'p=' + encodeURIComponent(id);
  try { localStorage.setItem('metaform.project', id); } catch (error) { /* storage can be blocked; the address keeps it */ }
  Object.assign(LIVE, {layer: null, base: null, seen: ''});
  Object.assign(D, {sessions: []});
  $('#autostartAgents').checked = false;
  $('#autostartAgents').disabled = true;
  // the threads are the sessions of the project left, so they go with it
  Object.assign(DOCK, {chats: [], chat: null, target: null, session: null, label: '', mine: null, calling: null});
  $('#helpdesk .call').textContent = 'Call';
  drawTabs();
  ROAM.focus = null;
  for (const list of document.querySelectorAll('#agents .list')) fill(list);
  $('#agents').hidden = true;
  for (const [work, figure] of ROAM.figures) { G?.scene().remove(figure.mesh); releaseGlyph(work); }
  ROAM.figures.clear(); ROAM.seen.clear();
  Object.assign(MERGE, {rows: [], chat: null});
  $('#reviewNotice').hidden = $('#mergeAsk').hidden = true;
  dockState('resting');  // the chat put away to its tab, so it can be opened again here
  forgetHarnesses();  // the agents another project's folder sets are its own, VIEW-039
  for (const one of [PICKERS.start, PICKERS.task, PICKERS.element]) one?.set(null);  // and so is a choice made there
  Object.assign(INTAKE, {work: null, session: null, agent: null, waiting: 0, started: null});
  D.asking = [];
  drawDockTab();
  for (const id of ['#intake', '#build', '#buildPrompt']) $(id).hidden = true;
  drawIntake();
  renderMerges();  // the merges this project has waiting for review, VIEW-044
}
$('#proj').onchange = () => { toProject($('#proj').value); loadProject(); listen(); };
$('#mf').onchange = () => { S.base = $('#mf').value; baseButtons(); loadMetaform(); };

/* ---------- the developer level: browser-console detail and traces, only with metaform web start --web-debug ----------
 * Off, the default, logs nothing and keeps no trace. info logs each read and write of the page and keeps them for the
 * Traces pane; verbose adds the events heard and each pane drawn; trace adds every raw response. The level comes with
 * the workspace's read, from the web_debug setting or the last start's --web-debug. */
const DEBUG = {level: 'off', rows: [], most: 400};
const DEBUG_LEVELS = ['off', 'info', 'verbose', 'trace'];
const debugAt = level => DEBUG_LEVELS.indexOf(DEBUG.level) >= DEBUG_LEVELS.indexOf(level) && DEBUG.level !== 'off';
function dlog(level, ...said) { if (debugAt(level)) console.info(`[metaform ${level}]`, ...said); }
function traced(row) {
  if (DEBUG.level === 'off') return;
  DEBUG.rows.push({at: Date.now(), ...row});
  if (DEBUG.rows.length > DEBUG.most) DEBUG.rows.splice(0, DEBUG.rows.length - DEBUG.most);
}
{
  const own = window.fetch.bind(window);
  window.fetch = async (input, options = {}) => {
    if (DEBUG.level === 'off') return own(input, options);
    const what = typeof input === 'string' ? input : input.url, method = (options.method || 'GET').toUpperCase(), began = performance.now();
    const response = await own(input, options);
    const ms = Math.round(performance.now() - began);
    let raw = null;
    if (debugAt('trace')) { try { raw = (await response.clone().text()).slice(0, 20000); } catch { raw = null; } }
    traced({kind: method, what, status: response.status, ms, raw});
    dlog('info', method, what, response.status, `${ms} ms`);
    return response;
  };
}

/* ---------- the workspace: the toolbar, the panes and their places, web/README.md "Toolbar and panes" ----------
 * Drawn from /api/workspace by workspace.js, which this part lends the page's own views and commands. In an AI tool's
 * frame, or with no workspace read, the page stays as written. */
const TAB_VIEWS = {object: 'object', brief: 'brief', prov: 'provenance', prompt: 'prompt'};
const PANE_VIEWS = createViews({h, fill, read, wrote, toast, confirmAct, project: () => S.project, debug: () => DEBUG.level,
  trace: () => DEBUG.rows, getJson: workspaceJson,
  openMessages: record => { const id = nodeOf(record); select(id, true); show(id, 'unread'); }});
for (const view of Object.values(PANE_VIEWS)) $('.app').append(view.el);
async function workspaceJson(path) {
  const response = await reach(path, {headers: {Accept: 'application/json'}});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw Object.assign(new Error(body.error || `${path} failed`), {status: response.status, body});
  return body;
}
/* A window of the page shown as a pane leaves the overlay stack while it is docked, so it neither covers the page nor
 * holds its keys, and is a window on the stack again when it floats or closes. */
function overlayDocked(box, on) {
  if (on) {
    const known = OVERLAY.known.get(box);
    if (known) { box.wsOverlay = known; OVERLAY.known.delete(box); }
    OVERLAY.stack = OVERLAY.stack.filter(entry => entry.box !== box);
    box.inert = false;
    restack();
  } else if (box.wsOverlay) {
    OVERLAY.known.set(box, box.wsOverlay);
    delete box.wsOverlay;
  }
}
/* The chat in a pane's body: it stays open there, its tab and its own place left aside; null puts it back in its dock. */
function chatPane(on) {
  const box = $('#helpdesk');
  overlayDocked(box, on);
  if (on) {
    $('#dock').dataset.place = 'pane';
    $('#dock').className = 'open';
    box.hidden = false;
    dockLayout();
    drawHelpdesk();
    return;
  }
  $('#dock').append(box);
  let kept = 'corner';
  try { kept = localStorage.getItem(DOCK_PLACE) || 'corner'; } catch { /* storage can be blocked */ }
  placeDock(kept, false);
  dockState('resting');
}
const chatDocked = () => $('#dock').dataset.place === 'pane';
/* An agent's figure on the 2D map opens the exact session it walks for, as its figure in 3D and its row under Agent
 * deployed do; the click goes to the figure, not to the box under it. */
$('#viewport').addEventListener('click', event => {
  const g = event.target.closest?.('g.agent2d');
  if (!g) return;
  const figure = [...ROAM2D.figures.values()].find(one => one.g === g);
  if (!figure) return;
  event.stopPropagation();
  event.preventDefault();
  const session = D.sessions.filter(one => one.work_id === figure.id && one.state === 'running').at(-1);
  agentAt(figure.id, session?.session_id || null);
}, true);
/* The chat docked at a side of the page is as wide as the person drags its inner edge, kept in this browser as a view
 * preference of the screen; a double-click puts it back. */
{
  const DOCK_WIDTH = 'metaform.dockWidth';
  const set = pixels => {
    if (pixels === null) { document.documentElement.style.removeProperty('--dock-width'); try { localStorage.removeItem(DOCK_WIDTH); } catch { /* blocked */ } }
    else {
      const width = Math.round(Math.max(320, Math.min(innerWidth - 360, pixels)));
      document.documentElement.style.setProperty('--dock-width', `${width}px`);
      try { localStorage.setItem(DOCK_WIDTH, String(width)); } catch { /* storage can be blocked; it is sized for now */ }
    }
    dispatchEvent(new Event('resize'));
  };
  const edge = h('div', {class: 'dockedge', role: 'separator', 'aria-orientation': 'vertical', tabindex: '0',
    'aria-label': 'The docked chat\'s width', title: 'Drag to resize the chat; double-click to reset'});
  $('#helpdesk').append(edge);
  edge.addEventListener('pointerdown', event => {
    event.preventDefault();
    const right = $('#dock').dataset.place === 'right';
    const move = moved => set(right ? innerWidth - moved.clientX : moved.clientX);
    const end = () => { removeEventListener('pointermove', move); removeEventListener('pointerup', end); };
    addEventListener('pointermove', move);
    addEventListener('pointerup', end);
  });
  edge.addEventListener('dblclick', () => set(null));
  edge.addEventListener('keydown', event => {
    const by = {ArrowLeft: 24, ArrowRight: -24}[event.key];
    if (!by) return;
    event.preventDefault();
    const now = $('#helpdesk').getBoundingClientRect().width;
    set(now + ($('#dock').dataset.place === 'right' ? by : -by));
  });
  try { const kept = Number(localStorage.getItem(DOCK_WIDTH)); if (kept) set(kept); } catch { /* the default width */ }
}
const VIEWS = {
  object: {el: $('#p-object'), show: () => { if (S.selected) select(S.selected, false, true, false, true); }},
  brief: {el: $('#p-brief'), show: () => renderBrief()},
  provenance: {el: $('#p-prov'), show: () => renderProv()},
  prompt: {el: $('#p-prompt'), show: () => (P.editor ? setTimeout(() => P.editor.refresh(), 0) : renderPrompt())},
  settings: {el: $('#settings'), show: () => showSettings(), docked: on => overlayDocked($('#settings'), on)},
  'agent-view': {el: $('#agentview'), show: () => readAgentView(), docked: on => overlayDocked($('#agentview'), on)},
  board: {el: $('#board'), show: () => renderBoard(), docked: on => overlayDocked($('#board'), on)},
  dock: {el: $('#helpdesk'), show: () => drawHelpdesk(), docked: on => chatPane(on)},
  ...PANE_VIEWS,
};
const COMMANDS = {
  search: () => openSearch(),
  'export-markdown': () => $('#exportMarkdown').click(), 'export-xml': () => $('#exportXml').click(),
  'export-mermaid': () => $('#exportMermaid').click(), 'copy-mermaid': () => $('#copyMermaid').click(),
  build: () => $('#buildBtn').click(), shortcuts: () => openHelp(),
  layers: () => $('#layersBtn').click(), agents: () => $('#agentsMenuBtn').click(), intake: () => openIntake(),
  orphaned: () => $('#orphanBtn').click(),
  'add-task': address => { const element = elementAt(address); if (element) giveWork(element.id); },
  'add-element': address => addElement(elementAt(address)?.id || S.selected),
  'dispatch-node': address => {
    const element = elementAt(address);
    if (!element) return;
    giveWork(element.id);
    $('#task .start-agent').checked = true;
  },
};
const WS = createWorkspace({h, fill, toast, confirmAct, overlay, movable, place, wrote, getJson: workspaceJson,
  project: () => S.project, selection: () => briefAddress(), layers: () => viewLayers(),
  view: page => (page === 'dev-prompts' || page === 'dev-trace') && DEBUG.level === 'off' ? null : VIEWS[page] || null,
  hasCommand: page => page in COMMANDS, command: (page, address) => COMMANDS[page]?.(address),
  tab: page => ({object: $('#t-object'), brief: $('#t-brief'), provenance: $('#t-prov'), prompt: $('#t-prompt')})[page] || null,
  openAddress: uri => { const element = elementAt(uri.replace(/^metaform:\/\//, '').split('#')[0]); if (element) briefTo(element.id); },
  maps: large => {
    const swapped = $('.app').classList.contains('swapped');
    if ((large === 'map2d') !== swapped) swap(large === 'map2d', false);
    return {large: $('main'), small: $('#small')};
  },
  classic: on => { $('.app').classList.toggle('ws', !on); if (on) $('#toolbar').hidden = true; },
  // the arrangement that is the page as written: its side column at that side with the node's tabs as laid out, its
  // tab open, its windows opened and closed as their own buttons do, and the large map this browser's choice
  classicFrame: ({side, panes, tabs, off}) => { sideAt(side === 'right'); classicTabs(panes, tabs, off); },
  tabOpen: page => $('#t-' + TAB_PAGES[page])?.getAttribute('aria-selected') === 'true',
  showTab: page => showTab(TAB_PAGES[page]),
  largeMap: () => ($('.app').classList.contains('swapped') ? 'map2d' : 'map3d'),
  openWindow: page => ({board: () => $('#boardBtn').click(), settings: () => openSettings(),
    'agent-view': () => openAgentView()})[page]?.(),
  overlayHolds, log: dlog});
/* The workspace read with the project, the page's developer level with it; without it, the node's tabs as the
 * declarations give them, `nodeTabs`. */
async function loadWorkspace() {
  if (FRAMED) return nodeTabs();
  await readView();
  const before = WS.on;  // web_panes off, WS.load keeps the page as written and reads the view settings alone
  const on = await WS.load();
  const view = WS.view();  // read with panes on or off, web_panes
  DEBUG.level = view.debug || 'off';
  const shapes = view.shapes !== false;
  if (shapes !== VIEW_SETTINGS.shapes) { VIEW_SETTINGS.shapes = shapes; shapes3d(); if (M.base) build2D(); }
  Object.assign(FRAMES, {idle: 1000 * Number(view.flow_seconds ?? 30), rest: view.idle_flow ? null : 0});
  fitDirection2d(view.map_direction);  // web_map_direction, the 2D map's way, `fitPin2d`
  if (!on) return nodeTabs();
  if (DEBUG.level !== 'off' && !before) WS.render();  // the developer panes, offered now that the level is known
  dlog('info', 'workspace', WS.state()?.workspace, WS.layout());
}
// Where a node's sign is on the screen, its four corners projected as the scene draws them, for a check of its framing.
window.metaform.signRect = id => {
  const sign = tags.get(id)?.sprite;
  if (!G || !sign) return null;
  sign.updateMatrixWorld();
  const box = $('#stage').getBoundingClientRect(), camera = G.camera();
  let left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
  for (const [x, y] of [[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]]) {
    const at = new THREE.Vector3(x, y, 0).applyMatrix4(sign.matrixWorld).project(camera);
    const sx = box.left + (at.x + 1) / 2 * box.width, sy = box.top + (1 - at.y) / 2 * box.height;
    left = Math.min(left, sx); right = Math.max(right, sx); top = Math.min(top, sy); bottom = Math.max(bottom, sy);
  }
  return {left, top, right, bottom};
};
// What a browser check reads of the agents drawn: the agents read again, and where an agent's figure is on the screen.
Object.assign(window.metaform, {renderAgents: () => renderAgents(),
  figureOnScreen: work => {
    const figure = ROAM.figures.get(work);
    if (!G || !figure?.mesh) return null;
    const box = $('#stage').getBoundingClientRect(), at = figure.mesh.position.clone().project(G.camera());
    return {x: box.left + (at.x + 1) / 2 * box.width, y: box.top + (1 - at.y) / 2 * box.height};
  },
  readout: which => { const box = readoutBox(which); return box && !box.hidden && box.classList.contains('on') ? box.textContent : null; }});
// What a browser check reads of the workspace: whether it is on, the layout drawn, and where a pane stands.
window.metaform.workspace = {on: () => WS.on, layout: () => WS.layout(), toolbar: () => WS.toolbar(), where: id => WS.where(id),
  shown: id => WS.isShown(id), activate: id => WS.activate(id), move: (id, target) => WS.moveTo(id, target)};
/* What changes with a selection in the workspace: the brief and provenance shown read again, and the panes that
 * follow the selection. */
function wsSelected() {
  if (WS.isShown('map.brief')) renderBrief();
  if (WS.isShown('map.provenance')) renderProv();
  WS.refresh(true);
}

async function main() {
  const response = await reach('/api/projects');
  const listed = await response.json();
  S.projects = listed.projects || [];
  if (!S.projects.length) {
    fill($('#p-object'), h('p', {class: 'empty'}, 'No project is registered. Register one with: metaform add project <id> <path>'));
    listen();  // still hears what modules publish: an intake started in a project registered later takes the page there
    revealed();
    return;
  }
  // The project shown first, VIEW-002: the one the address names; else the project of the folder `metaform web` ran
  // in; else the one this browser showed last; else the first.
  let remembered = null;
  try { remembered = localStorage.getItem('metaform.project'); } catch (error) { /* storage can be blocked */ }
  const registered = id => S.projects.some(item => item.id === id);
  S.project = [new URLSearchParams(location.hash.slice(1)).get('p'), listed.opened, remembered].find(registered)
    || S.projects[0].id;
  try { localStorage.setItem('metaform.project', S.project); } catch (error) { /* storage can be blocked */ }
  window.history.replaceState(null, '', '#p=' + encodeURIComponent(S.project));
  fill($('#proj'), ...S.projects.map(item => h('option', {value: item.id, selected: item.id === S.project}, item.id)));
  start3D();
  await loadProject();
  revealed();
  listen();
  renderMerges();  // VIEW-044
}
/* The page shown once it is laid out, two frames after the map is drawn, `booting` in theme.js. */
function revealed() {
  S.shown = true;  // the first project is drawn, or there is none; before it, the page has not loaded
  requestAnimationFrame(() => requestAnimationFrame(() => document.documentElement.classList.remove('booting')));
}
// What a browser check reads of the page's controls, the overlays open, bottom to top, and the controls themselves,
// for the views built on them.
Object.assign(window.metaform, {overlays: () => OVERLAY.stack.map(entry => entry.box.id || entry.box.className),
  harnesses: () => ({...HARNESS, pickers: undefined, reading: undefined}), build: () => BUILD.job, intake: () => ({...INTAKE}),
  // an agent's session opened in the chat dock or in its window, as its chat button and its entry in the key open it
  chat: (work, session = null) => isIntake(work) ? openIntakeChat(work, session)
    : openHelpdesk(work, `${agentName(D.sessions.find(one => one.session_id === session)?.agent)} on ${workPart(work)}`, STANDBY, session),
  agent: (work, session = null) => agentAt(work, session),
  // the dock's threads, each by its session with where it comes from, the one on view, and where the dock stands
  dock: () => ({threads: DOCK.chats.map(chat => ({work_id: chat.target, session: chat.session, source: chat.source,
    label: chat.label})), on: DOCK.chat?.session || null, place: $('#dock').dataset.place || 'corner'}),
  ui: {overlay, confirmAct, undoable, toast, segmented, progressBar, copyField, choice}});
main();
