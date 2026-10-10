/* Metaform's web GUI, the viewer: the whole map in 3D and in 2D, kept in sync, and the selected object below.
 * Every piece of data comes from the server's reads, VIEW-004; the page never decides what is visible. Text from the
 * store is always set as text, never as HTML, VIEW-009. */
'use strict';

// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
import ForceGraph3D from '3d-force-graph';
import {createAgent, drawGlyph, releaseGlyph, orientAgent} from '/page/agents3d.js';
// drei's transmission material in its vanilla form, the glass itself, VIEW-025. It imports three.js as `three`, which
// the page's import map names as the same file, so both share one three.js.
import {MeshTransmissionMaterial} from '/vendor/drei-vanilla/MeshTransmissionMaterial.js';

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
 * stands just right of the side column, under the header, a step down from another one open there, and any other
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
    left = $('aside').getBoundingClientRect().right + 24 + others * 28;
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
const S = {
  projects: [], project: null, bases: [], base: null, layers: [], view: null,
  elements: new Map(), joins: [], items: new Map(), selected: null, neighbors: new Set(), trail: [], history: [], at: -1, loading: 0, opening: 0,
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
  small: ['metaform.smallHeight', '--small-height', 120, () => $('aside').clientHeight - 140]};
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
splitter($('#sideSplit'), 'side', moved => moved.clientX - $('aside').getBoundingClientRect().left);
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
$('#shortcutsBtn').onclick = () => { $('#settingsbox').hidden = true; $('#help').hidden = false; };
overlay($('#help'), {kind: 'dialog', close: () => { $('#help').hidden = true; }});
$('#help .close').onclick = () => { $('#help').hidden = true; };
/* The page's text size, VIEW-023: A down and A up step every size token of the page, the type, the spacing and the
 * heights of controls, through --ui, so the header, the menus, the panel and the windows follow; the maps draw their
 * own text and are not scaled. The size is kept in this browser and put back before the page draws, `theme.js`. */
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
  $('#textDown').disabled = at === 0;
  $('#textUp').disabled = at === TEXTSIZE.steps.length - 1;
  dispatchEvent(new Event('resize'));  // the panes and the maps' areas changed size with it, and the header folds if it must
}
$('#textDown').onclick = () => textSize(textStep() - 1);
$('#textUp').onclick = () => textSize(textStep() + 1);
textSize(textStep());
/* Reset puts every size and zoom back as the page opens: the text, the side column and the split under the small map,
 * the 2D map's least text and its whole view, and the 3D map fitted, each through its own reset. */
$('#sizesReset').onclick = () => {
  textSize(TEXTSIZE.start);
  sized('side', null);
  sized('small', null);
  MODE.key = 5;  // the least text of the 2D map's Zoom, VIEW-041
  fitAll();
  toast('Sizes and zoom are back to their defaults.');
};
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
window.metaform = {graph: () => graphData(), selected: () => S.selected, select: id => select(id, true),
  click3d: id => clicked3d(G?.graphData().nodes.find(node => node.id === id)),
  drawn: () => G ? {nodes: G.graphData().nodes.length, links: G.graphData().links.length} : null,
  curves: () => G ? G.graphData().links.map(link => ({k: link.k, curve: accessed(G.linkCurvature(), link)})) : [],
  linkColors: () => G ? G.graphData().links.map(link => ({join: link.join || null, k: link.k,
    target: link.target?.id ?? link.target, color: linkColor(link)})) : [],
  layouts: () => V3.layouts, drawnWork: id => (G?.graphData().nodes.find(node => node.id === id)?.work || []).length,
  loaded: () => !S.loading && !S.opening, editor: () => P.editor, live: () => LIVE.layer, changes: () => LIVE.done,
  inside: () => IN.length && M.drawn === IN.at(-1) ? [...M.nodes.keys()] : [], vertical: () => M.vertical,
  at2d: id => M.nodes.has(id) ? {x: M.nodes.get(id).x, y: M.nodes.get(id).y} : null,
  look: id => look(id), fit: () => fit2D(), menu: id => menu(id), task: id => giveWork(id), element: id => addElement(id), note: id => notesAt(id),
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
  view3d: (from, to) => { if (G) G.cameraPosition(from, to, 0); },
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
    $('#tip3d').hidden = !hovered; if (hovered) { fill($('#tip3d'), tipFor(hovered)); placeTip(); } },
  figures2d: () => [...ROAM2D.figures.values()].map(figure => ({work_id: figure.id, glyph: figure.glyph, stage: figure.stage,
    target: figure.target, home: figure.home, x: figure.x, y: figure.y, size: figure.size, angle: figure.angle,
    shown: Boolean(figure.g.isConnected && M.svg && M.svg.contains(figure.g)), icon: figure.g.querySelector('image').getAttribute('href')})),
  figures: () => [...ROAM.figures.values()].map(figure => ({work_id: figure.id, glyph: figure.glyph, stage: figure.stage,
    target: figure.target, home: figure.home, x: figure.mesh.position.x, y: figure.mesh.position.y, z: figure.mesh.position.z,
    scale: figure.mesh.scale.x, angle: figure.angle, clock: figure.clock, px: onScreen(figure.mesh)})),
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
 * agents3d.js, drawn so that no two at work look alike. It moves as a body does: along a smooth curve through the
 * nodes of its way, setting off and arriving gently and slowing into sharp turns, facing the way it goes and, if it
 * flies or swims, leaning into its turns; it swings out onto its orbit carrying on the way it came, and leaves it from
 * where it is. With reduced motion it stands at the node. */
const ROAM = {figures: new Map(), seen: new Set(), last: 0, speed: 70, size: 2.6, share: 0.11, orbit: 1.5, lap: 12,
  recent: 120, appear: 0.8, touch: 0.9, vanish: 0.6,
  // how it moves along its way: units a second it speeds up and slows down by, and how much of its speed a turn
  // straight back takes off, a gentler turn less; how long it takes to settle from its way onto its orbit; and how
  // fast the size it is drawn at follows the map's span, so a layout that spreads never makes it jump
  accel: 70, corner: 0.6, settle: 1.1, grow: 10, drawn: 0, sized: 0};
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
const liveWork = () => new Set(D.sessions.filter(one => one.activity === 'working')
  .map(one => one.work_id));
function figures(tickets) {
  figures2d(tickets);
  if (!G) return;
  const data = G.graphData(), home = primaryOf(data);
  if (!home) return;
  const live = liveWork();
  for (const ticket of tickets) {
    const figure = ROAM.figures.get(ticket.id), target = ticketNode(ticket);
    if (figure) { figure.done = Boolean(ticket.done) || !live.has(ticket.id); continue; }
    const working = live.has(ticket.id) && !ticket.done;
    if (working && !ROAM.seen.has(ticket.id) && nodeById(data, target)) {
      const glyph = drawGlyph(ticket.id, ownGlyph(ticket)), mesh = createAgent(glyph);
      mesh.scale.setScalar(0.001);
      G.scene().add(mesh);
      ROAM.seen.add(ticket.id);
      ROAM.figures.set(ticket.id, {id: ticket.id, glyph, mesh, home: home.id, target, stage: 'arriving',
        way: routeOf(data, home.id, target).map(id => ({id})), u: 0, speed: 0, clock: 0, angle: Math.random() * Math.PI * 2,
        points: [], curve: new THREE.CatmullRomCurve3([], false, 'centripetal'), from: new THREE.Vector3(),
        heading: new THREE.Vector3(0, 0, 1), done: Boolean(ticket.done)});
    }
  }
  for (const [id, figure] of ROAM.figures) if (!tickets.some(ticket => ticket.id === id)) figure.done = true;
  wake3d();
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
function walk(figure, passed) {
  const points = figure.points, legs = points.length - 1, lengths = [];
  let total = 0;
  for (let k = 0; k < legs; k++) { lengths.push(Math.max(1e-3, points[k].distanceTo(points[k + 1]))); total += lengths[k]; }
  const leg = Math.min(legs - 1, Math.floor(figure.u));
  let done = (figure.u - leg) * lengths[leg];
  for (let k = 0; k < leg; k++) done += lengths[k];
  const least = ROAM.speed * 0.12, reach = (limit, away) => Math.sqrt(limit * limit + 2 * ROAM.accel * Math.max(0, away));
  let speed = Math.min(ROAM.speed, reach(least, done), reach(least, total - done));
  for (let k = 1, at = lengths[0]; k < legs; at += lengths[k], k++) {
    const turn = HEAD.subVectors(points[k], points[k - 1]).normalize().dot(NEXT.subVectors(points[k + 1], points[k]).normalize());
    speed = Math.min(speed, reach(ROAM.speed * (1 - ROAM.corner * (1 - turn) / 2), Math.abs(at - done)));
  }
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
const AHEAD = new THREE.Vector3(), ORBIT = new THREE.Vector3();
const easeBoth = k => k * k * (3 - 2 * k);  // from rest to rest
function roam3d(data) {
  const now = performance.now() / 1000, passed = Math.min(0.1, Math.max(0, now - (ROAM.last || now)));
  ROAM.last = now;
  // The size follows the map's span gently, so a layout still spreading never makes a figure jump in size.
  const real = Math.min(1, Math.max(0, now - (ROAM.sized || now)));
  ROAM.sized = now;
  const size = ROAM.drawn = ROAM.figures.size
    ? (ROAM.drawn ? ROAM.drawn + (sizeOf(data) - ROAM.drawn) * (1 - Math.exp(-real * ROAM.grow)) : sizeOf(data)) : 0;
  const lift = size * 0.6;
  for (const [id, figure] of ROAM.figures) {
    const {mesh} = figure;
    const gone = () => { G.scene().remove(mesh); releaseGlyph(id); ROAM.figures.delete(id); };
    figure.clock += passed;
    const target = nodeById(data, figure.target), home = nodeById(data, figure.home);
    if (!target || target.x === undefined || !home || home.x === undefined) continue;
    if (reduced()) {  // no walking: the figure stands on its node while the ticket is worked
      mesh.position.set(target.x, target.y + ballOf(target) + size, target.z);
      mesh.scale.setScalar(size);
      if (figure.done) gone();
      continue;
    }
    if (figure.stage === 'arriving') {  // it materializes on the most primary node
      const grown = Math.min(1, figure.clock / ROAM.appear), over = 1 + 1.7 * Math.pow(grown - 1, 3) + 0.7 * Math.pow(grown - 1, 2);
      mesh.position.set(home.x, home.y + lift, home.z);
      mesh.scale.setScalar(size * Math.max(0.001, over));
      if (grown >= 1) Object.assign(figure, {stage: 'going', u: 0, clock: 0});
    } else if (figure.stage === 'going' || figure.stage === 'returning') {  // along the map's own edges
      const going = figure.stage === 'going';
      if (!placed(figure, data, lift)) {  // a node of its way left the map: it goes on to what comes next
        onOrbit(figure, target);
        Object.assign(figure, going ? {stage: figure.done ? 'touching' : 'circling'} : {stage: 'leaving'}, {clock: 0});
        continue;
      }
      const arrived = walk(figure, passed), along = figure.u / (figure.points.length - 1);
      figure.curve.getPoint(along, mesh.position);
      figure.curve.getTangent(along, AHEAD);
      if (AHEAD.lengthSq() > 1e-8) figure.heading.copy(AHEAD);
      mesh.scale.setScalar(size);
      orientAgent(mesh, figure.heading, 0.25, passed);
      if (arrived) {
        if (going) onOrbit(figure, target);
        Object.assign(figure, {clock: 0, stage: !going ? 'leaving' : figure.done ? 'touching' : 'circling'});
      }
    } else if (figure.stage === 'circling') {  // on the node, around it, slowly at one steady pace
      figure.angle += passed * 2 * Math.PI / ROAM.lap;
      const turn = figure.angle, reach = ballOf(target) + size * ROAM.orbit;
      // It swings out from where it arrived onto its orbit, carrying on the way it came, and then holds the orbit.
      const settled = easeBoth(Math.min(1, figure.clock / ROAM.settle));
      ORBIT.set(Math.cos(turn) * reach, Math.sin(turn * 2) * reach * 0.18 + size * 0.3, Math.sin(turn) * reach);
      ORBIT.lerpVectors(figure.from, ORBIT, settled);
      mesh.position.set(target.x, target.y, target.z).add(ORBIT);
      mesh.scale.setScalar(size);
      AHEAD.set(-Math.sin(turn), Math.cos(turn * 2) * 0.36, Math.cos(turn));
      figure.heading.lerp(AHEAD, settled);
      orientAgent(mesh, figure.heading, 0.3, passed);
      if (figure.done) {  // it leaves its orbit from where it is, on the fewest edges back
        const back = routeOf(data, figure.target, figure.home);
        Object.assign(figure, {stage: 'returning', u: 0, clock: 0,
          way: [{point: mesh.position.clone()}, ...(back.length > 1 ? back.slice(1) : [figure.home]).map(id => ({id}))]});
      }
    } else if (figure.stage === 'touching') {  // finished before it got there: it still touches the node, then leaves
      const dip = Math.sin(Math.PI * Math.min(1, figure.clock / ROAM.touch));
      ORBIT.copy(figure.from);
      ORBIT.y += (ballOf(target) * 0.4 + size * 0.4 - ORBIT.y) * dip;
      mesh.position.set(target.x, target.y, target.z).add(ORBIT);
      if (figure.clock >= ROAM.touch) {
        const back = routeOf(data, figure.target, figure.home);
        Object.assign(figure, {stage: 'returning', u: 0, clock: 0,
          way: [{point: mesh.position.clone()}, ...(back.length > 1 ? back.slice(1) : [figure.home]).map(id => ({id}))]});
      }
    } else if (figure.stage === 'leaving') {  // home again, it is gone
      const faded = Math.min(1, figure.clock / ROAM.vanish);
      mesh.position.set(home.x, home.y + lift, home.z);
      mesh.scale.setScalar(size * Math.max(0.001, 1 - faded * faded));
      if (faded >= 1) { gone(); continue; }
    }
    mesh.userData.update(passed);
  }
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
    const working = live.has(ticket.id) && !ticket.done, target = working && target2d(base, ticket);
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
      ROAM2D.figures.set(ticket.id, {id: ticket.id, glyph, g, home, target: target.key, last: target.last, stage: 'arriving',
        way: way.map(key => ({key})), u: 0, speed: 0, clock: 0, angle: Math.random() * Math.PI * 2, stride: 0, lean: 0,
        from: {x: 0, y: 0}, heading: {x: 1, y: 0}, x: 0, y: 0, size: 0, drawn: '', done: Boolean(ticket.done)});
    }
  }
  for (const [id, figure] of ROAM2D.figures) if (!tickets.some(ticket => ticket.id === id)) figure.done = true;
  again2d();
}
function again2d() { if (ROAM2D.figures.size && !ROAM2D.frame) ROAM2D.frame = requestAnimationFrame(roam2d); }
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
  const legs = points.length - 1, lengths = [];
  let total = 0;
  for (let k = 0; k < legs; k++) { lengths.push(Math.max(1e-3, Math.hypot(points[k + 1].x - points[k].x, points[k + 1].y - points[k].y))); total += lengths[k]; }
  const leg = Math.min(legs - 1, Math.floor(figure.u));
  let done = (figure.u - leg) * lengths[leg];
  for (let k = 0; k < leg; k++) done += lengths[k];
  const least = ROAM2D.speed * 0.12, reach = (limit, away) => Math.sqrt(limit * limit + 2 * ROAM2D.accel * Math.max(0, away));
  let speed = Math.min(ROAM2D.speed, reach(least, done), reach(least, total - done));
  for (let k = 1, at = lengths[0]; k < legs; at += lengths[k], k++) {
    const turn = ((points[k].x - points[k - 1].x) * (points[k + 1].x - points[k].x) + (points[k].y - points[k - 1].y) * (points[k + 1].y - points[k].y))
      / (lengths[k - 1] * lengths[k]);
    speed = Math.min(speed, reach(ROAM2D.speed * (1 - ROAM2D.corner * (1 - turn) / 2), Math.abs(at - done)));
  }
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
    let x = target.x, y = target.y, scale = 1, lift = 0, lean = 0;
    if (reduced()) {  // no walking: it stands above its node while the ticket is worked
      y = target.y - target.h / 2 - size / 2;
      if (figure.done) { gone(); continue; }
    } else if (figure.stage === 'arriving') {  // it appears on the DE
      const grown = Math.min(1, figure.clock / ROAM2D.appear);
      ({x, y} = home); scale = Math.max(0.001, 1 + 1.7 * Math.pow(grown - 1, 3) + 0.7 * Math.pow(grown - 1, 2));
      if (grown >= 1) Object.assign(figure, {stage: 'going', u: 0, clock: 0});
    } else if (figure.stage === 'going' || figure.stage === 'returning') {  // along the map's own edges
      const going = figure.stage === 'going';
      const points = figure.way.map(step => step.point || spot2d(base, step.key));
      if (points.length < 2 || points.some(point => !point)) {  // a node of its way left the map
        Object.assign(figure, going ? {stage: figure.done ? 'touching' : 'circling'} : {stage: 'leaving'}, {clock: 0, from: {x: 0, y: 0}});
        continue;
      }
      const arrived = walk2d(figure, points, passed), at = curve2d(points, figure.u), ahead = curve2d(points, Math.min(points.length - 1, figure.u + 0.02));
      ({x, y} = at);
      if (Math.hypot(ahead.x - x, ahead.y - y) > 1e-3) figure.heading = {x: ahead.x - x, y: ahead.y - y};
      // a step's bounce, and a lean the way it goes, as fast as it goes
      lift = Math.abs(Math.sin(figure.stride / (size * 0.9) * Math.PI)) * size * 0.07 * Math.min(1, figure.speed / ROAM2D.speed);
      lean = Math.sign(figure.heading.x) * Math.min(1, figure.speed / ROAM2D.speed) * ROAM2D.lean;
      if (arrived) {
        if (going) {  // onto its orbit from where it arrived, on the side that carries it straight on
          const across = target.w / 2 + size * ROAM2D.orbit, down = target.h / 2 + size * ROAM2D.orbit;
          figure.from = {x: x - target.x, y: y - target.y};
          figure.angle = Math.atan2(-figure.heading.x / across, figure.heading.y / down);
        }
        Object.assign(figure, {clock: 0, stage: !going ? 'leaving' : figure.done ? 'touching' : 'circling'});
      }
    } else if (figure.stage === 'circling') {  // around its box, slowly at one steady pace
      figure.angle += passed * 2 * Math.PI / ROAM2D.lap;
      const settled = easeBoth(Math.min(1, figure.clock / ROAM2D.settle));  // it swings out from where it arrived
      const across = target.w / 2 + size * ROAM2D.orbit, down = target.h / 2 + size * ROAM2D.orbit;
      x = target.x + figure.from.x + (Math.cos(figure.angle) * across - figure.from.x) * settled;
      y = target.y + figure.from.y + (Math.sin(figure.angle) * down - figure.from.y) * settled;
      lift = Math.sin(figure.clock * 2.4) * size * 0.025;   // at rest on its orbit it bobs, gently
      lean = -Math.sin(figure.angle) * ROAM2D.lean * 0.5 * settled;
      if (figure.done) Object.assign(figure, {stage: 'returning', way: home2dFrom(base, {...figure, x, y}), u: 0, clock: 0, stride: 0});
    } else if (figure.stage === 'touching') {  // finished before it got there: it still touches the node
      const dip = Math.min(1, figure.clock / ROAM2D.touch);
      ({x, y} = {x: target.x + figure.from.x, y: target.y + figure.from.y});
      scale = 1 - 0.3 * Math.sin(Math.PI * dip);
      if (dip >= 1) Object.assign(figure, {stage: 'returning', way: home2dFrom(base, {...figure, x, y}), u: 0, clock: 0, stride: 0});
    } else if (figure.stage === 'leaving') {  // home again, it is gone
      const faded = Math.min(1, figure.clock / ROAM2D.vanish);
      ({x, y} = home); scale = Math.max(0.001, 1 - faded * faded);
      if (faded >= 1) { gone(); continue; }
    }
    figure.lean += (lean - figure.lean) * (1 - Math.exp(-passed * 8));
    Object.assign(figure, {x, y, size: size * scale});
    const drawn = size * scale, top = y - lift;
    const placed = [x - drawn / 2, top - drawn / 2, drawn, figure.lean].map(value => Math.round(value * 100) / 100).join(' ');
    if (placed === figure.drawn) continue;   // nothing to draw again
    figure.drawn = placed;
    moving = true;
    const image = figure.g.firstChild;
    image.setAttribute('x', x - drawn / 2); image.setAttribute('y', top - drawn / 2);
    image.setAttribute('width', drawn); image.setAttribute('height', drawn);
    image.setAttribute('transform', `rotate(${figure.lean.toFixed(2)} ${x} ${top})`);
  }
  // With reduced motion a figure stands still, so the frames stop once each is drawn; a redraw or a change asks again.
  if (ROAM2D.figures.size && (moving || !reduced())) ROAM2D.frame = requestAnimationFrame(roam2d);
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
  return new THREE.Mesh(ballShape(radius), material);
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
 * When the part is built its node comes up to solid over GHOST.solid seconds; with reduced motion at once. Why: the
 * characters that stood here moved all the time and drew the eye from everything else on the map; a ghost says the
 * same, that the part is still to come, and is quiet. */
const GHOST = {opacity: 0.25, solid: 1.2};
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
    const object = isGlass(node) && glass ? bead(node)
      : new THREE.Mesh(ballShape(Math.cbrt(nodeSize(node)) * 3), new THREE.MeshLambertMaterial({color: colorOf(node)}));
    object.material.userData.own = true;
    ghostly(object.material, GHOST.opacity);
    object.userData.ghost = true;
    return object;
  }
  return glass && isGlass(node) ? bead(node) : false;
}
/* Each frame: a part built since it was drawn as a ghost comes up to solid. */
function ghost3d(data, now) {
  for (const node of data.nodes) {
    if (unbuilt(node)) { GHOSTS.now.add(node.id); continue; }
    if (GHOSTS.now.delete(node.id) && !reduced()) GHOSTS.built.set(node.id, now);
  }
  for (const [id, since] of GHOSTS.built) {
    const node = nodeById(data, id), material = node?.__threeObj?.material;
    const risen = Math.min(1, (now - since) / 1000 / GHOST.solid);
    if (material && !node.__threeObj.userData.ghost) ghostly(material, GHOST.opacity + (1 - GHOST.opacity) * risen * risen * (3 - 2 * risen));
    if (risen >= 1 || !node) GHOSTS.built.delete(id);
  }
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
  busy: false, flowing: false, grace: 700, idle: 30000, idleRate: 15, rest: null};
const DAMPING = 0.12;
const DRAG_FRICTION = 0.65;  // the share of its speed a node loses each tick while one is dragged; 0.4 otherwise  // the share of a turn of the camera a hand gave that it loses each 60th of a second: it coasts
function wake3d(ms = FRAMES.grace) {
  const now = performance.now();
  FRAMES.until = Math.max(FRAMES.until, now + ms);
  FRAMES.active = now;
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
        V3.auto = name === 'zoomToFit';
        wake3d(FRAMES.grace + (Number(args[name === 'zoomToFit' ? 0 : 2]) || 0));
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
    .onNodeHover(node => hover3d(node))
    .linkColor(linkColor)
    .linkOpacity(Number(css('--link-opacity')))
    .linkMaterial(fiberOf)
    .linkWidth(link => link.k === 'tree' ? 0.4 : link.k === 'layer' || link.k === 'item' ? 0.25 : link.k === 'relation' ? 0.5 : 0.9)
    .linkCurvature(0)
    .linkDirectionalParticles(link => !reduced() && (link.k === 'purpose' || link.k === 'encounter') ? 2 : 0)
    .linkDirectionalParticleSpeed(0)  // the page moves the dots itself, by the time that passed, `flow3d`
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
    .onNodeDrag(() => { G.d3AlphaMin(0).d3VelocityDecay(DRAG_FRICTION); })
    .onNodeDragEnd(() => { G.d3AlphaMin(0.001).d3VelocityDecay(0.4); })
    .onNodeClick(clicked3d)
    .onNodeRightClick((node, event) => { if (node) menu(node.id, event.clientX, event.clientY); });
  grounded();
  G.scene().onBeforeRender = solid;
  addBehind();
  addBloom();
  // The page's own work for each frame runs first in the render chain: after the layout's tick and the controls, before
  // anything is drawn, so the camera's flight, the labels, the dots and the tooltip are all of the same frame.
  G.postProcessingComposer().insertPass({isPass: true, enabled: true, needsSwap: false, clear: false, renderToScreen: false,
    setSize() {}, render() { prepare3d(); }, dispose() {}}, 0);
  G.d3Force('charge').strength(node => node.t === 'el' ? -140 : node.t === 'item' ? -10 : -18);
  G.d3Force('link').distance(link => link.k === 'layer' ? 8 : link.k === 'item' ? 12 : link.k === 'tree' ? 60 : 34);
  // The camera coasts after a hand lets it go, and the wheel zooms toward the point under the pointer.
  const controls = G.controls();
  Object.assign(controls, {enableDamping: true, dampingFactor: DAMPING, zoomToCursor: true});
  controls.addEventListener('start', () => {
    FLIGHT.on = false; V3.auto = false; hover3d(null);
    if (MEET.on) { MEET.released = true; meetEnds(); }
  });
  controls.addEventListener('end', () => {  // let go after a meeting: back out to the node's usual close view
    if (!MEET.released || !MEET.back) return;
    MEET.released = false;
    const node = G.graphData().nodes.find(item => item.id === MEET.back.id), here = cameraNow();
    if (node && node.x !== undefined) flyTo({x: node.x, y: node.y, z: node.z, turn: here.turn, tilt: here.tilt, far: MEET.back.far});
  });
  controls.addEventListener('change', () => { FRAMES.moved = true; });
  const stage = $('#stage');
  for (const type of ['pointerdown', 'wheel', 'keydown']) stage.addEventListener(type, () => wake3d(), {passive: true});
  for (const type of ['pointerenter', 'pointermove']) stage.addEventListener(type, () => { TIP.out = false; wake3d(); }, {passive: true});
  stage.addEventListener('pointerleave', () => { TIP.out = true; hover3d(null); });
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
/* A click on any vertex selects that object itself: an element or a join's purpose vertex. */
function clicked3d(node) {
  if (!node) return;
  if (large()) MODE.mode = 'readable';  // a click on a node goes to mode two, VIEW-041
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
  hovered = TIP.out ? null : node || null;
  $('#tip3d').hidden = !hovered;
  if (hovered) { fill($('#tip3d'), tipFor(hovered)); placeTip(); }
}
function placeTip() {
  const tip = $('#tip3d');
  if (!G || !hovered || hovered.x === undefined) return;
  const point = G.graph2ScreenCoords(hovered.x, hovered.y, hovered.z);
  const camera = G.camera(), box = $('#stage').getBoundingClientRect();
  const distance = Math.hypot(camera.position.x - hovered.x, camera.position.y - hovered.y, camera.position.z - hovered.z);
  const radius = Math.cbrt(nodeSize(hovered)) * 3 / (distance * Math.tan(camera.fov * Math.PI / 360)) * box.height / 2;
  const above = point.y - radius - 10 - tip.offsetHeight >= 0;
  tip.style.left = point.x + 'px';
  tip.style.top = (above ? point.y - radius - 10 : point.y + radius + 10) + 'px';
  tip.style.transform = `translate(-${Math.min(100, Math.max(0, point.x / box.width * 100))}%, ${above ? '-100%' : '0'})`;
}
const short = (text, most) => text.length > most ? text.slice(0, most - 1) + '…' : text;
/* The labels of the 3D map, VIEW-038, are drawn inside the scene, each its element's whole name, wrapped at word
 * breaks, painted on a canvas and shown as a sign in the scene, its face turned out from the map's middle. Its size and its opacity say how near it is:
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
const LABEL = {size: 11, chosen: 13, wide: 9, line: 1.15, padX: 6, padY: 4, stroke: 2, after: 10,
  out: 12,  // how far a label stands out from its ball's surface, away from the map's middle, in the map's units
  // the size of a label's letters in the map, in its units, about an element's height; painted sharper at each
  // `sharper` step of the size it is seen at, up to `largest`; and the farthest label's opacity, the nearest solid
  letters: 10, largest: 4, sharper: 0.5, farthest: 0.34};
const tags = new Map();   // by node id: the label's sprite, its canvas, what it shows and where it is on the screen
const LABELS = {group: null, plane: null, on: true, only: null, pen: null, measured: new Map()};
const OUT = new THREE.Vector3(), UP = new THREE.Vector3(), AT = new THREE.Vector3(), middle = new THREE.Vector3();
const Y_UP = new THREE.Vector3(0, 1, 0);
const fontOf = look => `${look.weight} ${look.size}px ${look.family}`;
/* The name in lines no wider than the label's width, broken only between words, as the page wraps text; a word longer
 * than the width keeps its own line whole. Measured once for each name and look. */
function wrapped(text, look) {
  const key = fontOf(look) + '\n' + text;
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
  // A sign in the scene, its face turned out from the map's middle and seen from either side, so from behind the
  // map its name reads backward, as a sign does. `sprite` is the name it has always had in the page's reads.
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
  const camera = G.camera(), area = $('#stage').getBoundingClientRect(), height = area.height || 1;
  const spread = camera.projectionMatrix.elements[5], ratio = G.renderer().getPixelRatio();
  const perPixel = depth => 2 * depth / (spread * height);   // world units a pixel spans at a depth
  const depthOf = node => -AT.set(node.x, node.y, node.z).applyMatrix4(camera.matrixWorldInverse).z;
  const palette = {text: css('--text'), muted: css('--muted'), signal: css('--signal'), broken: css('--broken'),
    exclude: css('--exclude'), ground: css('--ground'), sans: css('--sans')};  // read once a frame, not once a label
  if (LABELS.group) LABELS.group.visible = LABELS.on;
  UP.set(0, 1, 0).applyQuaternion(camera.quaternion);
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
    if (node.t !== 'el') continue;
    const tag = labelFor(node);
    tag.text = node.name || '';
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
    const shape = wrapped(tag.text, look);
    tag.shape = shape;
    // Pinned in the map a set distance from its node, on the side away from the map's middle, so it is a thing of the
    // scene: it swings round its node as the map turns and goes behind the node as anything behind it does, and the
    // outer names stand outside the map, over the least of it.
    const ball = radius;
    OUT.set(node.x - middle.x, node.y - middle.y, node.z - middle.z);
    if (OUT.lengthSq() < 1e-6) OUT.copy(UP); else OUT.normalize();
    tag.sprite.position.set(node.x, node.y, node.z).addScaledVector(OUT, ball + LABEL.out);
    // turned to face out from the map's middle, upright in the map, or upright to the eye where it would face
    // straight up or down
    tag.sprite.up.copy(Math.abs(OUT.y) > 0.98 ? UP : Y_UP);
    tag.sprite.lookAt(AT.copy(tag.sprite.position).add(OUT));
    const seen = grown, size = LABEL.letters / LABEL.size;
    tag.sprite.scale.set(shape.width * size, shape.height * size, 1);
    const anchor = G.graph2ScreenCoords(tag.sprite.position.x, tag.sprite.position.y, tag.sprite.position.z);
    tag.rect = {left: anchor.x - shape.width * seen / 2, right: anchor.x + shape.width * seen / 2,
      top: anchor.y - shape.height * seen / 2, bottom: anchor.y + shape.height * seen / 2};
    tag.grown = seen;
    shown.push({tag, far: depth, look, back});
  }
  shown.sort((one, two) => one.far - two.far);
  shown.forEach((label, index) => {
    // the nearest label solid, the farthest at LABEL.farthest of it, the rest between by their depth
    label.tag.sprite.material.opacity = 1 - (1 - LABEL.farthest) * label.back;
    const box = label.tag.rect;
    const behind = spheres.some(sphere => sphere.id !== label.tag.id && sphere.far < label.far &&
      Math.hypot(Math.max(box.left, Math.min(sphere.x, box.right)) - sphere.x,
                 Math.max(box.top, Math.min(sphere.y, box.bottom)) - sphere.y) < sphere.r);
    const covered = shown.slice(0, index).some(({tag: other}) => !(box.right <= other.rect.left ||
      other.rect.right <= box.left || box.bottom <= other.rect.top || other.rect.bottom <= box.top));
    const tag = label.tag;
    tag.under = behind || covered;
    tag.z = shown.length - index;
    if (tag.under) tag.classes.push('under');
    const look = lookOf(tag.classes, palette);
    // painted for the size it is drawn at, in steps, so a near label is as sharp as one at its own size
    const sharp = ratio * Math.min(LABEL.largest, Math.max(1, Math.ceil(tag.grown / LABEL.sharper) * LABEL.sharper));
    const key = [tag.text, fontOf(look), look.color, look.ground, look.glow, sharp].join('|');
    if (key !== tag.key) { painted(tag, look, sharp, tag.shape); tag.key = key; }
  });
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
  if (BLOOM) BLOOM.enabled = Boolean(R.key) || signaled;
  placeTip();
  showModes3d();
  FRAMES.busy = !reduced() && (Boolean(R.key) || ROAM.figures.size > 0 || GHOSTS.built.size > 0 || signaled);
  FRAMES.flowing = !reduced() && FLOW.count > 0 && FLOW.held === null;
}
/* The dots that travel each join, VIEW-005: two to a link, flowing the way the join's information goes, its ifd,
 * `flowOf`: from the receiver to the purpose vertex and on to each element the join holds when it sends, back when it
 * receives, and one each way when both. The page moves them by the time that passed, so they flow at one speed at any frame
 * rate. The purpose link and the encounter links of one join share one phase: a dot reaches the purpose vertex as
 * the next leaves it for every element the join holds, so the flow runs through the join as one, receiver to
 * providers. A dot grows out of the receiver and shrinks into the provider, so it neither appears nor vanishes at
 * once. Each join has its own phase, so the map's joins never pulse in step. `held`, a share of the way, holds every
 * dot there, `dots3d`. */
const FLOW = {period: 2.8, clock: 0, last: 0, held: null, count: 0, ends: 0.08};
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
  FLOW.clock += Math.min(0.1, Math.max(0, (now - (FLOW.last || now)) / 1000));
  FLOW.last = now;
  let count = 0;
  const ways = new Map(S.joins.map(join => [join.id, flowOf(join)]));
  for (const link of data.links) {
    const dots = link.__photonsObj?.children, from = link.source, to = link.target;
    if (!dots?.length || from?.x === undefined || to?.x === undefined) continue;
    count++;
    const offset = phaseOf(link.join), way = ways.get(link.join) || ['forth'];
    dots.forEach((dot, index) => {
      // the way the join's information goes: back, from the elements served to the receiver, runs the relay in reverse
      const forth = (FLOW.clock / FLOW.period + offset + index / dots.length) % 1, back = way[index % way.length] === 'back';
      const along = FLOW.held ?? (back ? 1 - forth : forth);
      dot.__progressRatio = along;
      dot.position.set(from.x + (to.x - from.x) * along, from.y + (to.y - from.y) * along, from.z + (to.z - from.z) * along);
      const through = link.k === 'purpose' ? along / 2 : 0.5 + along / 2;  // its share of the whole join's way
      dot.scale.setScalar(FLOW.held === null ? Math.max(0.001, Math.min(1, through / FLOW.ends, (1 - through) / FLOW.ends)) : 1);
    });
  }
  FLOW.count = count;
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
function setTheme(name) {
  document.documentElement.dataset.theme = name;
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
const MODE = {mode: 'whole', key: 5, zoom: 3, most: 0.6};  // the 2D camera's mode in the large area, VIEW-041; see modeTarget
/* The two views change places, VIEW-028: the 2D map takes the large area and the 3D map the small one, and back.
 * Each is then drawn for the area it has. The choice is the viewer's own, kept in this browser. */
async function swap(on, remember = true) {
  $('.app').classList.toggle('swapped', on);
  if (on) MODE.mode = 'whole';  // the 2D map comes to the large area in mode one, VIEW-041
  (on ? $('main') : $('#small')).append($('#map2d'));
  (on ? $('#small') : $('main')).append($('#big3d'));
  $('#swapBtn').title = on ? 'Put the 3D map back in the large area' : 'Put this map in the large area, and the 3D map here';
  $('#swap3dBtn').title = on ? 'Put this map back in the large area' : 'Put this map in the small area, and the 2D map here';
  if (remember) try { localStorage.setItem('metaform.swapped', on ? '1' : ''); } catch (error) { /* storage can be blocked; the swap still shows */ }
  resize();
  if (G) setTimeout(() => fit3d(600, on ? 24 : 60), 50);  // the whole 3D map in its new area
  if (S.loading || !S.elements.size) return;
  await build2D(false);  // drawn for its new area, opening as it does on loading
  if (S.selected) select(S.selected, false, true);
}
$('#swapBtn').onclick = $('#swap3dBtn').onclick = () => swap(!$('.app').classList.contains('swapped'));
/* The 3D map's own Fit goes between two views: the whole map, and close on the selected node. It moves the 3D map
 * only, as the 2D map's Fit moves the 2D map only. `auto` says the camera still shows the whole map as the page last
 * fitted it, with no hand and no selection having moved it since, so the layout may fit it again once it settles. */
const V3 = {whole: 0, fits: 0, layouts: 0, ticks: 0, auto: true, followed: 0, asked: false};  // the whole map's distance, the fits ended, the layouts
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
  const across = tall * camera.aspect * spare(room, width), down = tall * spare(room + LABEL.size, height);
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
    const far = Math.max((high[0] - low[0]) / 2 / across, (high[1] - low[1]) / 2 / down);
    return {x: middle.x, y: middle.y, z: middle.z, turn: here.turn, tilt: here.tilt, far: Math.log(Math.max(far, 1))};
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
  return {x: middle.x, y: middle.y, z: middle.z, turn: here.turn, tilt: here.tilt, far: Math.log(Math.max(far, 1))};
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
  // In the small area the map is read by its selected node, framed by its name, VIEW-005: the whole map is too small
  // there to read, so its fit is the node's name across NAME.out of the width.
  if (small3d() && S.selected && fly3d(S.selected, true, NAME.out)) return;
  const balls = fitBalls(G.graphData());
  Object.assign(V3, {auto: true, asked: true});
  if (!balls.length) return;
  flyTo(framed(balls, {room, mass: fitTrim()}), {length: time / 1000, done: () => { V3.whole = away3d(); V3.fits++; }});
}
/* A selected node is turned to face the eye: the camera swings round the map's middle to the side the node stands
 * out on, so the node is in front, its sign turned to the eye, VIEW-038, as if the whole map had turned to present it.
 * It stays right side up: the camera keeps the map's up as its own and is never more than TILT off level, so it never
 * looks straight down on the map. Only a selection turns it; a hand on the camera, or a drag, moves it as the hand
 * does. Swinging the camera round the middle shows what turning the whole map would, and keeps every node where the
 * layout put it. */
const TILT = 0.85;  // the most the camera rises above or falls below level, in radians, when it turns to a node
function facingOf(node, balls) {
  const middle = balls.reduce((sum, one) => ({x: sum.x + one.x / balls.length, y: sum.y + one.y / balls.length,
    z: sum.z + one.z / balls.length}), {x: 0, y: 0, z: 0});
  const dx = node.x - middle.x, dy = node.y - middle.y, dz = node.z - middle.z, away = Math.hypot(dx, dy, dz);
  if (away < 1e-3) return null;  // the node at the middle: seen from where the camera is
  return {turn: Math.atan2(dx, dz), tilt: Math.min(Math.PI / 2 + TILT, Math.max(Math.PI / 2 - TILT, Math.acos(dy / away)))};
}
/* A selection turns the map to the node and comes in on it, VIEW-008: the node at the center of the view, facing the
 * eye, `facingOf`, close enough that its three nearest neighbors frame it, at most four tenths of the whole map's
 * distance, never so near that the node fills the screen; the 3D map's Zoom and Fit go to the same view. Without
 * `close` it keeps the zoom the camera has. */
// The share of the small area's width the selected node's name spans: framed out, and in close on it.
const NAME = {out: 0.3, in: 0.8};
const small3d = () => $('.app').classList.contains('swapped');
/* How far the camera stands, as a log, for the node's name, at its real size in the map, to span `share` of the
 * view's width; null while the name is not drawn yet. */
function nameFar(node, share) {
  const sign = tags.get(node.id)?.sprite;
  if (!sign?.scale.x) return null;
  const camera = G.camera(), across = 2 * Math.tan(camera.fov * Math.PI / 360) * camera.aspect;
  const out = Math.hypot(sign.position.x - node.x, sign.position.y - node.y, sign.position.z - node.z);
  return Math.log(sign.scale.x / (share * across) + out);
}
function fly3d(id, close = true, share = NAME.in) {
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
  view.far = close ? Math.min(Math.max(view.far, Math.log(ballOf(node) * 7)), whole + Math.log(0.4))
    : (FLIGHT.on ? FLIGHT.to.far : cameraNow().far);  // a selection keeps the zoom the person has
  // In the small area the camera stands where the node's own name spans `share` of the window, so the name is read
  // there because the eye is that near it, not because it was drawn larger than the map holds it.
  const named = close && small3d() ? nameFar(node, share) : null;
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
      const reach = Math.max(Math.exp(view.far) - out, sign.scale.y * 2);
      MEET.back = {id, far: view.far};
      flyTo({x: sign.position.x, y: sign.position.y, z: sign.position.z, turn: Math.atan2(face.x, face.z),
        tilt: Math.acos(Math.max(-1, Math.min(1, face.y))), far: Math.log(reach)}, {done: () => meetBegins(reach)});
      return true;
    }
  }
  flyTo(view);
  return true;
}
/* Meeting a sign, VIEW-005: the camera's near plane is moved out to just short of the sign, so the nodes, signs and
 * edges between the eye and it are not drawn and it is read whole; it eases there and back. The plane is the camera's
 * own, set back to its value when the meeting ends. */
const MEET = {on: false, back: null, own: null, from: 0, to: 0, start: 0, released: false};
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
function meetBegins(reach) {
  MEET.on = true;
  // The sign is square to the eye, so its whole face is at one depth: the plane stops a hair short of it, and
  // nothing in front of it, an edge crossing the last stretch included, is drawn.
  easeNear(reach - Math.max(0.05, reach * 0.004));
}
function meetEnds() {
  if (MEET.own === null || (!MEET.on && G.camera().near === MEET.own && MEET.to === MEET.own)) return;
  MEET.on = false;
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
// Where the camera stands decides it, and not which button was clicked last, since the person also moves the camera
// by hand: standing back with the whole map in view it goes in on the selected node, and from anywhere nearer it
// goes out to the whole map.
/* The 3D map's own Whole and Zoom, as the 2D map has, beside its Fit: the whole map, or close on the selected node,
 * facing the eye; whichever the camera is at is checked. */
const MODES3D = {box: null, whole: null, zoom: null, said: ''};
MODES3D.box = h('div', {class: 'segmented modes3d', role: 'radiogroup', 'aria-label': 'How the 3D map is framed'},
  MODES3D.whole = h('button', {type: 'button', role: 'radio', title: 'The whole map in view',
    onclick: event => { event.stopPropagation(); fit3d(); }}, 'Whole'),
  MODES3D.zoom = h('button', {type: 'button', role: 'radio', title: 'Close on the selected node, turned to face you',
    onclick: event => { event.stopPropagation(); if (S.selected) fly3d(S.selected, true); }}, 'Zoom'));
$('#big3d .mapbtns').prepend(MODES3D.box);
function showModes3d() {  // each frame, from where the camera stands or is flying to
  // the small area has no whole map to show, only the selected node framed out or in, which its Fit moves between
  MODES3D.box.hidden = small3d();
  const far = FLIGHT.on ? Math.exp(FLIGHT.to.far) : away3d(), whole = V3.whole && far >= V3.whole * 0.8;
  const said = V3.whole ? (whole ? 'whole' : 'zoom') : '';
  if (said === MODES3D.said) return;
  MODES3D.said = said;
  MODES3D.whole.setAttribute('aria-checked', String(said === 'whole'));
  MODES3D.zoom.setAttribute('aria-checked', String(said === 'zoom'));
}
$('#fit3dBtn').onclick = () => {
  if (!G) return;
  const node = small3d() && S.selected ? G.graphData().nodes.find(item => item.id === S.selected) : null;
  const out = node ? nameFar(node, NAME.out) : null, near = node ? nameFar(node, NAME.in) : null;
  if (out !== null && near !== null) {  // in the small area Fit goes between the name framed out and in close
    const here = Math.log(Math.max(away3d(), 1e-3));
    fly3d(S.selected, true, Math.abs(here - near) < Math.abs(here - out) ? NAME.out : NAME.in);
    return;
  }
  const back = V3.whole && away3d() >= V3.whole * 0.8;
  if (back && S.selected && fly3d(S.selected, true)) return;
  fit3d();
};
// The 2D map opens in the large area, where its names are read, unless this browser has put the 3D map there: the
// chart is the map a person reads, and the 3D map keeps the whole in view beside it, VIEW-028.
{
  let kept = null;
  try { kept = localStorage.getItem('metaform.swapped'); } catch (error) { /* storage can be blocked: the default */ }
  if (kept === null || kept === '1') swap(true, false);
}
function resize() { if (G) { const box = $('#stage').getBoundingClientRect(); G.width(box.width).height(box.height); } }
addEventListener('resize', resize);

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
const M = {svg: null, nodes: new Map(), edges: [], cam: null, to: null, fit: null, frame: 0, generation: 0};
const MAP2D = 5000;  // the most elements Mermaid lays out; above it the 2D map is not drawn, BUILD-QUESTIONS Q52
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
async function build2D(keep = true) {
  const generation = ++M.generation;
  const host = $('#viewport');
  if (!window.mermaid) { fill(host, h('p', {class: 'empty', style: {padding: '16px'}}, 'The 2D map could not load.')); return; }
  if (!mermaidReady) {
    window.mermaid.initialize({startOnLoad: false, securityLevel: 'strict', theme: 'base', htmlLabels: false,
      flowchart: {htmlLabels: false, useMaxWidth: false, curve: 'basis', nodeSpacing: 28, rankSpacing: 45},
      themeVariables: {background: css('--ground'), primaryColor: css('--node'), primaryBorderColor: css('--node-line'),
        primaryTextColor: css('--text'), lineColor: css('--edge'), fontFamily: 'IBM Plex Sans, sans-serif', fontSize: '13px',
        tertiaryColor: css('--group')}});
    mermaidReady = true;
  }
  const shown2d = [...S.elements].filter(([, {element}]) => !underHiddenRoot(element.address));
  const keys = new Map(shown2d.map(([id], index) => [id, `n${index}`]));
  // One edge from a join's receiver to each element it holds.
  const drawn = S.joins.filter(join => keys.has(join.receiver))
    .flatMap(join => join.providers.filter(id => keys.has(id)).map(provider => ({join, provider})));
  const vertical = S.elements.size > 5;
  const lines = [vertical ? 'flowchart TB' : 'flowchart LR'];
  for (const [id, {element}] of shown2d) lines.push(`${keys.get(id)}["${plain2d(labelOf(element))}"]`);
  drawn.forEach(({join, provider}, index) => lines.push(`${keys.get(join.receiver)} e${index}@--> ${keys.get(provider)}`));
  if (!S.elements.size || S.elements.size > MAP2D) { IN.length = 0; M.base = null; renderCrumbs(); }
  if (!S.elements.size) { fill(host, h('p', {class: 'empty', style: {padding: '16px'}}, noMetaform() ? noneYet() : 'This metaform has no elements in these layers.')); return; }
  if (S.elements.size > MAP2D) {
    M.svg = null; M.nodes = new Map(); M.edges = [];
    fill(host, h('p', {class: 'empty', style: {padding: '16px'}}, `The 2D map lays out at most ${MAP2D} elements; these layers show ${S.elements.size}. The 3D view shows them all.`));
    return;
  }
  let result;
  try { result = await window.mermaid.render(`map2d${generation}`, lines.join('\n'), $('#draw')); }
  catch (error) { fill(host, h('p', {class: 'empty', style: {padding: '16px'}}, 'The 2D map could not be drawn.')); return; }
  if (generation !== M.generation) return;
  // The whole map drawn again keeps its camera and eases from there, VIEW-041, with the zoom the person has, VIEW-008.
  const was = keep && M.base && M.svg === M.base.svg && M.cam ? {cam: {...M.cam}, zoom: M.zoom} : null;
  const inside = IN.length > 0 || Boolean(MEM.key);
  const before = was && !inside ? drawnAt(M.base) : null;  // where each node is drawn now, to move it from there
  const svg = mountSvg(result, host, inside);
  const nodes = new Map();
  for (const [id, key] of keys) {
    const group = svg.querySelector(`[id*="-flowchart-${key}-"]`);
    if (group) placeIn(nodes, id, group, S.elements.get(id).element.address, S.elements.get(id).element.open_work);
  }
  const edges = drawn.map(({join, provider}, index) => ({join, provider, path: svg.querySelector(`[data-id="e${index}"]`)
    || svg.querySelectorAll('.edgePaths path')[index]}));
  for (const edge of edges) for (const condition of edge.join.open_work || []) edge.path?.classList.add(`work-${condition}`);
  for (const edge of edges) pointed(edge);
  // The base map is kept while a node is entered and shown again as it was, VIEW-016.
  M.base = {svg, nodes, edges, fit: fitOf(svg), vertical, cam: null};
  figures2d(S.tickets || []);
  if (MEM.key) { svg.remove(); svg.style.visibility = ''; await drawMemory2d(); return; }
  if (inside) { svg.remove(); svg.style.visibility = ''; await drawInside(); return; }
  showBase();
  paintInUse();
  if (was) { setCam(was.cam, false); M.zoom = was.zoom; }
  if (before) settle2D(before, nodes, svg);
  if (S.selected) focus2D(S.selected); else applyMode();
}
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
function placeIn(nodes, id, group, title, work) {
  const box = group.getBBox();
  const matrix = group.transform.baseVal.consolidate()?.matrix;
  const center = new DOMPoint(box.x + box.width / 2, box.y + box.height / 2).matrixTransform(matrix || new DOMMatrix());
  nodes.set(id, {g: group, x: center.x, y: center.y, w: box.width, h: box.height});
  group.dataset.key = id;  // what the node stands for, kept from one drawing to the next as the mermaid id is not
  for (const condition of work || []) group.classList.add(`work-${condition}`);  // the node's condition, MAP-046
  const paced = S.progress?.get(id);
  if (paced) group.style.setProperty('--pace', `${paceOf({id})}s`);
  const text = document.createElementNS(SVG, 'title');
  text.textContent = title;
  group.append(text);
  group.addEventListener('click', event => { event.stopPropagation(); clicked2d(id); });
  group.addEventListener('contextmenu', event => { event.preventDefault(); event.stopPropagation(); menu(id, event.clientX, event.clientY); });
}
/* Where the camera opens on a node's own graph, VIEW-016: the whole graph when its labels can be read at that size,
 * otherwise the node entered, at the size its labels are written in. Fit still shows the whole graph. */
function readable(fit, center) {
  const view = $('#viewport').getBoundingClientRect();
  if (!center || !view.width || view.width / frame(fit).w >= 1) return fitted(fit);
  const w = view.width, height = view.height || w;
  const x = Math.min(Math.max(center.x - w / 2, fit.x), Math.max(fit.x, fit.x + fit.w - w));
  const y = Math.min(Math.max(center.y - height / 2, fit.y), Math.max(fit.y, fit.y + fit.h - height));
  return {x, y, w, h: height};
}
/* The whole drawing framed with its margin, zoomed in or out as it needs, but in the panel never past 1.6 times its
 * natural size, so a map of a node or two does not fill it. The large area keeps VIEW-041's mode one, the whole
 * diagram as large as the area allows. */
function fitted(box) {
  const area = $('#viewport').getBoundingClientRect(), least = area.width / 1.6;
  if (!area.width || large() || box.w >= least) return box;
  const height = box.h * least / box.w;
  return {x: box.x + box.w / 2 - least / 2, y: box.y + box.h / 2 - height / 2, w: least, h: height};
}
function fitOf(svg) {
  const scene = svg.querySelector('g').getBBox();
  return {x: scene.x - 30, y: scene.y - 30, w: scene.width + 60, h: scene.height + 60};
}
function showBase(left = null) {
  const base = M.base;
  renderCrumbs();
  if (!base) return;
  stopCam();  // a camera still easing on the level left must not move this one
  Object.assign(M, {svg: base.svg, nodes: base.nodes, edges: base.edges, fit: base.fit, vertical: base.vertical, drawn: null});
  fill($('#viewport'), base.svg);
  const node = left ? base.nodes.get(left) : null;
  if (node && !reduced()) {  // back from inside the node: the map returns zoomed on it and fades in, VIEW-016
    const kept = base.cam || frame(readable(base.fit, node));  // the zoom held before going inside
    setCam(frame(into(node)), false);
    M.zoom = {w: kept.w, h: kept.h};
    arrive(base.svg);
    moveCam(moded() ? modeTarget() : {x: node.x - kept.w / 2, y: node.y - kept.h / 2, w: kept.w, h: kept.h});
    return;
  }
  base.svg.style.transition = ''; base.svg.style.opacity = '';  // a map faded on the way in shows whole again
  const entry = [...S.elements.values()].find(item => item.element.role === 'DE')?.element.id;
  setCam(base.cam || (moded() ? frame(modeTarget()) : frame(readable(base.fit, base.nodes.get(S.selected)
    || base.nodes.get(entry) || base.nodes.values().next().value))));
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
    placeIn(nodes, thingKey, group, thing.value !== undefined ? itemText(thing.value) : thing.label, null);
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
  Object.assign(M, {svg, nodes, edges: [], fit: fitOf(svg), vertical, drawn: level});
  setCam(frame(insideView(M.fit, nodes.get(level.key), svg)));  // the node's own graph fades in where it opens, VIEW-016
  renderCrumbs();
  if (S.selected && nodes.has(S.selected)) focus2D(S.selected);
}
/* Where the camera opens on a node's own graph: `readable`, and in the large area never larger than the size at which
 * its text is drawn at the readable mode's minimum, VIEW-041, so a small graph sits in the middle of the area at a size
 * it reads at, rather than filling it with text three times that size. */
function insideView(fit, center, svg) {
  const view = readable(fit, center), area = $('#viewport').getBoundingClientRect();
  if (!large() || !area.width || !area.height) return view;
  const shown = frame(view), most = (6 + 2 * MODE.key) / smallestText(svg);
  if (area.width / shown.w <= most) return view;
  const w = area.width / most, height = area.height / most;
  return {x: shown.x + shown.w / 2 - w / 2, y: shown.y + shown.h / 2 - height / 2, w, h: height};
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
  if (M.fit && M.drawn === MEM) { stopCam(); setCam(frame(M.fit)); }  // it opens with the whole memory network in view
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
  Object.assign(M, {svg, nodes, edges: [], fit: fitOf(svg), vertical, drawn: MEM});
  setCam(frame(M.fit));
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
/* M.zoom is the zoom the person has: the size the view opened at, what Fit set, or what they set by wheel. A
 * selection moves the view at that size; a camera still easing toward it never changes it, VIEW-008. */
function setCam(cam, settled = true) {
  M.cam = cam;
  if (settled) M.zoom = {w: cam.w, h: cam.h};
  M.svg?.setAttribute('viewBox', `${cam.x} ${cam.y} ${cam.w} ${cam.h}`);
  again2d();  // a figure keeps its least size on the screen as the zoom changes
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
  M.zoom = {w: to.w, h: to.h};
  if (reduced()) return setCam(to);
  M.to = to;
  Object.assign(MOVE, {from: camParts(M.cam), to: camParts(to), start: null, length, dive,
    rate: under && !dive ? under.rate : Object.fromEntries(CAM_PARTS.map(part => [part, 0]))});
  const step = now => {
    MOVE.start ??= now;
    const {cam, s} = camAt(now);
    setCam(cam, false);
    if (s < 1) M.frame = requestAnimationFrame(step); else M.to = null;
  };
  M.frame = requestAnimationFrame(step);
}
/* The two modes of the 2D map in the large area, VIEW-041: `whole` keeps the whole diagram fitted to the area, and
 * `readable` fits it the same way but never draws its text below the minimum the keys 1 to 9 set, 8 to 24 px, holding
 * the selected node at the center when the minimum wins. The wheel leaves both, null, until a click or Fit. They set
 * the camera of the whole map; a node's own graph and a memory network keep theirs, and the small area keeps the zoom
 * VIEW-008 gives it. */
const large = () => $('.app').classList.contains('swapped');
const moded = () => large() && Boolean(MODE.mode) && Boolean(M.base) && M.svg === M.base.svg;
const at2d = id => !id ? null : M.nodes.get(id) || (id.startsWith('p:') ? M.nodes.get(joinOf(id)?.provider) : null);
function smallestText(svg) {  // the smallest font size of the diagram's labels, in its own units
  let least = Infinity;
  for (const text of svg.querySelectorAll('text, tspan'))
    if ([...text.childNodes].some(node => node.nodeType === 3 && node.textContent.trim()))
      least = Math.min(least, parseFloat(getComputedStyle(text).fontSize) || Infinity);
  return isFinite(least) ? least : 13;
}
/* Mode two, Zoom: the whole diagram's view zoomed MODE.zoom times, but never with its text below the minimum the keys
 * 1 to 9 set, and never so close that the selected node's box takes more than MODE.most of the area, centered on the
 * selected node. Why: holding only a minimum size of text did nothing on a small map, whose whole diagram already draws
 * its text that large, and a zoom is wanted on every map; the cap keeps a node of a small map from filling the area. */
function modeTarget() {
  const fit = frame(fitted(M.fit)), area = M.svg.getBoundingClientRect();
  if (MODE.mode !== 'readable' || !area.width || !area.height) return fit;
  M.base.text ??= smallestText(M.base.svg);
  const entry = [...S.elements.values()].find(item => item.element.role === 'DE')?.element.id;
  const node = at2d(S.selected) || M.nodes.get(entry);
  const center = node || {x: fit.x + fit.w / 2, y: fit.y + fit.h / 2};
  // screen pixels for a unit of the diagram: zoomed in from the whole, at least the minimum text, at most the node cap
  let scale = Math.max(MODE.zoom * area.width / fit.w, (6 + 2 * MODE.key) / M.base.text);
  if (node?.w && node?.h) scale = Math.min(scale, MODE.most * area.width / node.w, MODE.most * area.height / node.h);
  const w = area.width / scale, height = area.height / scale;
  if (w >= fit.w) return fit;
  return {x: center.x - w / 2, y: center.y - height / 2, w, h: height};
}
function applyMode() { if (moded()) moveCam(modeTarget()); showModes(); }
/* The two modes of the large area, VIEW-041, shown in the 2D map's bar, so a person sees which one holds and changes it
 * without knowing the keys: Whole, mode one, and Zoom, mode two, `modeTarget`. Neither is
 * pressed after the wheel, which leaves both. */
const MODES = {box: null, whole: null, readable: null, said: ''};
function showModes() {
  if (!MODES.box) return;
  // In the large area on the whole map they are VIEW-041's two modes; elsewhere Whole fits and Zoom goes in close on
  // the selected node, VIEW-008, and whichever view the camera is in is the one checked.
  const moding = large() && Boolean(M.base) && M.svg === M.base.svg, least = 6 + 2 * MODE.key;
  const mode = moding ? MODE.mode : M.view === 'out' ? 'whole' : M.view === 'in' ? 'readable' : null;
  const said = [Boolean(M.svg), mode, least].join();
  if (said === MODES.said) return;
  MODES.said = said;
  MODES.box.hidden = !M.svg;
  MODES.whole.setAttribute('aria-checked', String(mode === 'whole'));
  MODES.readable.setAttribute('aria-checked', String(mode === 'readable'));
  MODES.readable.textContent = 'Zoom';
  MODES.readable.title = `In ${MODE.zoom} times on the selected node, its text never smaller than ${least} px and the node never more than ${Math.round(MODE.most * 100)}% of the view; the keys 1 to 9 set the least text, 8 to 24 px`;
}
/* Fit, F and Whole show the whole map and leave the selection as it is, its node and its joins still marked, so the
 * whole map is seen with what the selected node is joined to: clearing it threw away what the person had chosen to
 * look at. Backing out to the whole map, Escape, and Home clear the marks, `fitAll`. */
function fit2D() {
  if (large()) MODE.mode = 'whole';
  showModes();
  M.view = 'out';
  if (M.fit) moveCam(fitted(M.fit));
}
function unmark2D() {
  $('#map2d').classList.remove('focused');
  for (const edge of M.edges) edge.path?.classList.remove('on');
  flows2d();
  for (const node of M.nodes.values()) node.g.classList.remove('sel', 'near');
}
/* A join's information flow direction, its ifd, MAP-020, as the receiver has it: it sends to the elements that serve
 * it, receives from them, or both. The 2D map's arrows and flow and the 3D map's dots go the way the information goes. */
const flowOf = join => join?.ifd === 'receives' ? ['back'] : join?.ifd === 'both' ? ['forth', 'back'] : ['forth'];
/* An edge of the 2D map points the way its join's information goes: at the element served when the receiver sends, at
 * the receiver when it receives, at both ends when it goes both ways. Mermaid draws the arrow at the served end. */
function pointed(edge) {
  const path = edge.path, end = path?.getAttribute('marker-end');
  if (!end) return;
  const start = end.replace('pointEnd', 'pointStart'), ways = flowOf(edge.join);
  if (ways.includes('back')) path.setAttribute('marker-start', start);
  if (!ways.includes('forth')) path.removeAttribute('marker-end');
}
/* The selected node's joins in the 2D map carry its flow, as the dots carry it along every join in 3D, VIEW-005:
 * pulses running along each of its edges the way the join's information goes, `flowOf`, both ways for both.
 * Only the selected node's, so the map stays still to read and the flow says what the selection takes from where.
 * Each is a copy of its edge drawn over it in dashes that move, `.flow` in the styles; with reduced motion they stand. */
function flows2d() {
  for (const old of M.svg?.querySelectorAll('g.flows2d') || []) old.remove();
  const on = M.edges.filter(edge => edge.path?.classList.contains('on'));
  if (!on.length) return;
  // a group of their own just over the edges, so the edges stay what they are
  const flows = document.createElementNS(SVG, 'g'), edges = on[0].path.closest('.edgePaths') || on[0].path.parentNode;
  flows.setAttribute('class', 'flows2d');
  edges.after(flows);
  for (const edge of on) for (const way of flowOf(edge.join)) {
    const flow = edge.path.cloneNode(false);
    for (const name of ['id', 'marker-end', 'marker-start', 'data-id', 'style']) flow.removeAttribute(name);
    flow.setAttribute('class', way === 'back' ? 'flow back' : 'flow');
    flows.append(flow);
  }
}
function focus2D(id, framing = 'around', zoom = false) {
  const join = id.startsWith('p:') ? joinOf(id) : null;
  const node = M.nodes.get(id) || (join ? M.nodes.get(join.provider) : null);
  if (!M.svg) return;
  if (!node) return applyMode();
  showModes();
  if (IN.length) {
    for (const [key, value] of M.nodes) value.g.classList.toggle('sel', key === id);
  } else {
    $('#map2d').classList.add('focused');
    for (const [key, value] of M.nodes) { value.g.classList.toggle('sel', key === id); value.g.classList.toggle('near', key !== id && S.neighbors.has(key)); }
    for (const edge of M.edges) edge.path?.classList.toggle('on', join ? edge.join === join
      : edge.join.receiver === id || edge.provider === id);
  }
  flows2d();
  if (moded()) return moveCam(modeTarget());  // in the large area the mode sets the camera, VIEW-041
  // Selecting moves the view to the node at the zoom it has; the zoom changes only when Fit asks, VIEW-008. Inside a
  // node, a node already in view stays where it is, since the view was framed for the node's whole graph and moving it
  // to the middle would push the rest of that graph out of view, VIEW-016.
  const held = M.zoom || M.cam;
  if (!zoom && IN.length && inView(node, M.to || M.cam)) return;
  if (!zoom) return moveCam({x: node.x - held.w / 2, y: node.y - held.h / 2, w: held.w, h: held.h});
  // 'around' shows the node with its joined nodes; 'inside' frames the node so the nodes it holds fill the view;
  // 'close' moves nearer to a node that holds nothing.
  M.view = framing === 'around' ? 'around' : 'in';
  const [w, height] = framing === 'inside' ? [node.w * 1.25, node.h * 1.25]
    : framing === 'close' ? [Math.max(node.w * 1.8, 160), Math.max(node.h * 2.6, 110)]
    : [Math.max(node.w * 3.4, 380), Math.max(node.h * 5, 260)];
  moveCam({x: node.x - w / 2, y: node.y - height / 2, w, h: height});
}
/* One click selects; a click on the selected node goes inside it; a group's "more" node shows the next ones. In the
 * large area a click on a node goes to mode two, VIEW-041. */
function clicked2d(id) {
  if (large()) MODE.mode = 'readable';
  if (!MEM.key && (id === S.selected || id.startsWith('m:'))) goInside(id); else select(id, true);
}
const inView = (node, cam) => Boolean(cam) && node.x - node.w / 2 >= cam.x && node.x + node.w / 2 <= cam.x + cam.w
  && node.y - node.h / 2 >= cam.y && node.y + node.h / 2 <= cam.y + cam.h;
(function wire2D() {
  const host = $('#map2d');
  MODES.box = h('div', {class: 'segmented modes2d', role: 'radiogroup', 'aria-label': 'How the whole map is sized'},
    MODES.whole = h('button', {type: 'button', role: 'radio', title: 'The whole diagram fitted to the area (Home)',
      onclick: event => { event.stopPropagation(); fit2D(); }}, 'Whole'),
    MODES.readable = h('button', {type: 'button', role: 'radio', onclick: event => {
      event.stopPropagation();
      if (large() && M.base && M.svg === M.base.svg) { MODE.mode = 'readable'; applyMode(); }
      else if (S.selected) focus2D(S.selected, 'close', true);
      showModes();
    }}, 'Zoom'));
  $('#map2d .mapbtns').prepend(MODES.box);
  showModes();
  $('#fitBtn').onclick = event => { event.stopPropagation(); cycleView(); };
  $('#backBtn').onclick = event => { event.stopPropagation(); step(-1); };
  $('#forwardBtn').onclick = event => { event.stopPropagation(); step(1); };
  let drag = null;
  host.addEventListener('pointerdown', event => {
    if (event.target.closest('button, a') || !M.cam) return;
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
    const box = $('#viewport').getBoundingClientRect(), scale = M.cam.w / box.width;
    setCam({...drag.cam, x: drag.cam.x - (event.clientX - drag.x) * scale, y: drag.cam.y - (event.clientY - drag.y) * scale});
  });
  host.addEventListener('pointerup', () => { drag = null; });
  host.addEventListener('wheel', event => {
    if (!M.cam) return;
    event.preventDefault();
    if (large()) MODE.mode = null;  // the wheel leaves both modes, VIEW-041
    // The wheel zooms at once, by how far it turned: flat steps on a mouse wheel, its own acceleration on a trackpad.
    // No easing: a zoom that lags the wheel and lands after it stops is not how a mouse works.
    stopCam();
    const lines = event.deltaMode === 1 ? event.deltaY * 16 : event.deltaMode === 2 ? event.deltaY * 400 : event.deltaY;
    const f = Math.exp(Math.max(-200, Math.min(200, lines)) * 0.0015), box = $('#viewport').getBoundingClientRect();
    const px = (event.clientX - box.left) / box.width, py = (event.clientY - box.top) / box.height, c = M.cam;
    const w = c.w * f, height = c.h * f;
    const to = frame({x: c.x + (c.w - w) * px, y: c.y + (c.h - height) * py, w, h: height});
    M.zoom = {w: to.w, h: to.h};
    setCam(to);
  }, {passive: false});
  new ResizeObserver(() => applyMode()).observe($('#viewport'));  // the area changes size: the new fit, VIEW-041
})();
function fitAll() { unmark2D(); fit2D(); fit3d(); }
/* Fit and F go through three views, zoomed out to the whole map, zoomed in on the selected node,
 * with the nodes inside it when it holds any, and regular, the node with its joined nodes. In the large area they go
 * back to mode one, VIEW-041. */
function cycleView() {
  const here = S.selected;
  if (large()) {  // the whole diagram, then back in: the readable view, or the selected node when the whole is readable
    if (MODE.mode !== 'whole' || !here || !M.base || M.svg !== M.base.svg) return fit2D();
    MODE.mode = 'readable';
    const readableView = frame(modeTarget());
    if (!near(readableView, frame(fitted(M.fit)))) return moveCam(readableView);
    MODE.mode = null;
    M.view = 'around';
    return focus2D(here, 'around', true);
  }
  const next = {around: 'out', out: 'in', in: 'around'}[M.view || 'around'];
  if (!here || next === 'out') return fit2D();  // its own map only; the 3D map has a Fit of its own, VIEW-028
  if (next === 'in') return focus2D(here, 'close', true);
  focus2D(here, 'around', true);
}
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
function backOut() {
  if (MEM.key) return leaveMemories();
  if (IN.length) return goTo(IN.length - 1);
  const here = S.selected;
  if (!here) return;
  if (here.startsWith('p:')) {
    const up = S.trail.length ? S.trail.pop() : parentOf(here);
    if (up) select(up, true, true);
  } else fitAll();
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
document.addEventListener('keydown', event => {
  if (!mapKeys(event)) return;
  // The page's own keys: / searches the map and ? shows every key.
  if (event.key === '/') { event.preventDefault(); openSearch(); return; }
  if (event.key === '?') { event.preventDefault(); $('#help').hidden = false; return; }
  if (event.key === 'f' || event.key === 'F') { event.preventDefault(); cycleView(); return; }
  if (event.key === 'Home') { event.preventDefault(); fitAll(); return; }
  // In the large area the keys 1 to 9 set the minimum text, 8 to 24 px, and go to mode two, VIEW-041.
  if (/^[1-9]$/.test(event.key) && !event.ctrlKey && !event.metaKey && !event.altKey && large()) {
    event.preventDefault(); Object.assign(MODE, {mode: 'readable', key: Number(event.key)}); applyMode(); return;
  }
  if (!S.selected) return;
  const here = S.selected;
  if (event.key === 'Escape' || (event.key === 'Enter' && event.shiftKey)) { event.preventDefault(); backOut(); return; }
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
    if (fly && node) fly3d(id);
  }
  focus2D(id);
  if (!again) showTab('object');
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
  if (!S.project) return;
  try { MERGE.rows = (await read('merges')).merges || []; } catch { MERGE.rows = []; }
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
    openHelpdesk(workId);
    if (!await wrote('/api/merge-assist', {work_id: workId})) drawHelpdesk('The agent could not be started.');
  };
  $('#mergeAsk .no').onclick = () => { $('#mergeAsk').hidden = true; toast('The merge is yours to handle; its countdown is off.'); };
  OVERLAY.known.get($('#mergeAsk')).close = () => $('#mergeAsk .no').click();
  $('#mergeAsk').hidden = false;
}
/* The chat dock: a thin sliver at the lower right that lifts when the pointer comes near and opens, on a click, into a
 * customer-service chat. Call reaches the person's system agent, the +1 outside the agent limit; /list and /chat <n>
 * talk with an agent at work instead, and each open chat is a tab, VIEW-045. Bubbles alternate: the person's on the right, the agent's on the left. A file
 * attached with the paperclip is saved in the project and the agent is told where. Live monitoring stays in the agent
 * window; this is only the conversation. */
const DOCK = {target: null, session: null, label: '', since: 0, notes: [], list: [], files: [], mine: null, waiting: '',
  calling: null, chats: []};  // chats: every open conversation, one a tab; the fields above are the one on view
const STANDBY = 'Please stand by while we contact an agent for you.';
function dockState(state) {
  const was = !$('#helpdesk').hidden;
  $('#dock').className = state;
  $('#helpdesk').hidden = state !== 'open' && state !== 'open big';
  if (!was && !$('#helpdesk').hidden) drawHelpdesk();  // opened, even empty, it says what it is and how to start
}
function dockNote(text) { DOCK.notes.push({at: Date.now(), text}); drawHelpdesk(); }
/* session: the session the chat is with, when it is known. The chat stays with it, so a later session of the same
 * ticket never swaps the conversation; with none known yet, the chat waits for the ticket's running session and then
 * stays with that one. */
function openHelpdesk(workId, label = 'an agent', waiting = 'Waiting for the next available agent.', session = null) {
  let chat = DOCK.chats.find(one => one.target === workId);
  if (chat) Object.assign(chat, {label, waiting, ...(session ? {session} : {})});
  else DOCK.chats.push(chat = {target: workId, session, label, waiting, mine: DOCK.mine === workId, since: Date.now()});
  showChat(chat);
  if (!$('#dock').className.startsWith('open')) dockState('open');
}
/* Several chats are open at once, a sentinel for each issue raised and anyone talked with, each a tab; the one on
 * view is the dock's target, and switching keeps each conversation and its session. */
function showChat(chat) {
  Object.assign(DOCK, {target: chat.target, session: chat.session, label: chat.label, waiting: chat.waiting,
    since: chat.since});
  MERGE.chat = chat.target;
  $('#helpdesk .call').textContent = 'Dismiss';
  drawTabs();
  drawHelpdesk();
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
          if (await wrote('/api/dispatch-message', {work_id: DOCK.target, text: `I choose proposal ${index + 1}: ${one.title}.`})) {
            INUSE.preview = new Set(); paintInUse(); drawHelpdesk();
          }
        }}, 'Choose')));
  }));
}
function drawTabs() {
  const tabs = $('#helpdesk .tabs');
  tabs.hidden = DOCK.chats.length < 2;
  fill(tabs, DOCK.chats.map(chat => h('button', {class: chat.target === DOCK.target ? 'tab on' : 'tab', role: 'tab',
    'aria-selected': String(chat.target === DOCK.target), title: chat.label, onclick: () => showChat(chat)},
    chat.label.replace(/^the /, ''))));
}
function chatActivity(session) {
  if (!session) return {label: 'Connecting', busy: false, interruptible: false};
  if (session.state !== 'running') return {label: 'Ended', busy: false, interruptible: false};
  const busy = session.activity === 'working' || session.activity === 'waiting';
  const label = session.interrupting ? 'Interrupting'
    : ({working: 'Busy', waiting: 'Waiting for permission', idle: 'Ready'}[session.activity] || 'Status unavailable');
  const note = session.interrupting ? 'Interrupting the current task.'
    : session.activity === 'working' ? 'Agent is working on a task. A message is read when its current step ends; Interrupt stops the step.'
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
  const target = DOCK.target, openedSession = DOCK.session;
  if (target) {
    try {
      const found = await read('dispatch-sessions', {id: target});
      if (DOCK.target !== target || DOCK.session !== openedSession) return;  // the chat moved on while this was read
      const sessions = found.sessions || [];
      session = DOCK.session ? sessions.find(one => one.session_id === DOCK.session)
        : sessions.filter(one => one.state === 'running').at(-1);
      if (session) {
        DOCK.session = session.session_id;
        const chat = DOCK.chats.find(one => one.target === target);
        if (chat) chat.session = session.session_id;
        state = (found.states || {})[session.session_id] || null;
      }
      lines = session ? (found.lines || []).filter(line => line.session_id === session.session_id) : [];
    } catch (error) { trouble = error.message; }
  }
  DOCK.state = state;
  DOCK.agent = session?.agent || null;
  drawProposals();
  drawSession($('#helpdesk .sessionbar'), {work: target, session, state});
  drawPlan($('#helpdesk .planbox'), target ? state?.plan : null);
  const activity = chatActivity(session);
  const waiting = DOCK.target && !session;
  const busy = DOCK.target && activity.busy && session?.activity !== 'waiting';
  // one line says whom the chat is with, or that it is online; the other what that agent is doing, while there is one
  $('#helpdesk .status').textContent = DOCK.target ? activity.label : '';
  $('#helpdesk .status').hidden = !DOCK.target;
  $('#helpdesk').classList.toggle('asks', Boolean(session && session.activity === 'waiting'));
  $('#helpdesk .interrupt').disabled = !DOCK.target || !activity.interruptible;
  $('#helpdesk .with').textContent = DOCK.target ? `With ${DOCK.label}` : 'Online';
  const intro = 'You are connected to Metaform Support. Start a chat with your system agent below, or type / for the commands.';
  const system = (key, text) => ({key, text, make: () => h('div', {class: 'system'}, text)});
  const log = $('#helpdesk .log');
  // with no chat on view, each agent waiting for the person's permission, so the dock's count leads somewhere
  const asking = DOCK.target ? [] : (D.asking || []).map(one => ({key: `asks:${one.work_id}:${one.request}`, text: `${one.work_id}\n${one.tool}`,
    make: () => h('div', {class: 'system asking'}, `${agentName(one.agent)} on ${workPart(one.work_id)} asks to ${one.tool || 'use a tool'}.`,
      h('button', {class: 'btn sm primary', type: 'button', onclick: () => isIntake(one.work_id) ? openIntakeChat(one.work_id, one.session_id)
        : openHelpdesk(one.work_id, `${agentName(one.agent)} on ${workPart(one.work_id)}`, 'It answers when its current step ends.', one.session_id)}, 'Open'))}));
  const changed = keyedFill(log, [
    system('intro', intro),
    ...asking,
    ...DOCK.notes.filter(note => note.at >= DOCK.since - 1).map((note, index) => system(`note:${note.at}:${index}`, note.text)),
    ...threadRows(lines, {work: target, agent: session?.agent, dock: true}),
    ...(waiting || busy ? [{key: 'waiting', text: waiting ? DOCK.waiting : activity.note || activity.label, make: () => h('div', {class: 'system waiting'}, waiting ? DOCK.waiting : activity.note || activity.label,
      h('span', {class: 'typing', 'aria-hidden': 'true'}, h('i'), h('i'), h('i')))}] : []),
    ...(trouble ? [system('trouble', trouble)] : [])]);
  if (changed) log.scrollTop = log.scrollHeight;
}
/* The chat's own commands, offered with the agent's when the person types / in the message box. */
const DOCK_COMMANDS = [{name: 'help', description: 'What the chat\'s commands do'},
  {name: 'list', description: 'The agents at work, numbered'}, {name: 'chat', hint: '<number>', description: 'Talk with an agent at work, by its number in /list'},
  {name: 'system', description: 'Start a chat with your system agent'}];
const dockOffered = () => {
  const agents = commandsOf(DOCK.target ? DOCK.state : null, DOCK.agent);
  return [...agents, ...DOCK_COMMANDS.filter(one => !agents.some(agent => agent.name === one.name)).map(one => ({...one, from: 'This chat'}))];
};
async function dockCommand(text) {
  const [command, ...rest] = text.slice(1).trim().split(/\s+/);
  // a command the agent on view offers is the agent's: it goes to the agent as the message it is
  if (DOCK.target && commandsOf(DOCK.state, DOCK.agent).some(one => one.name === command)) {
    if (await wrote('/api/dispatch-message', {work_id: DOCK.target, text})) drawHelpdesk();
    return;
  }
  if (command === 'help') return dockNote('/list shows the agents at work · /chat <number> talks with one of them · /system calls your system agent · the agent\'s own commands are offered as you type /.');
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
      chosen.session_id);
    return dockNote(`You are now talking with ${DOCK.label}. Its work goes on while you talk.`);
  }
  if (command === 'system') return callSystem();
  dockNote(`${text} is not a command here. Type /help.`);
}
async function callSystem() {
  dockState($('#dock').className.startsWith('open') ? $('#dock').className : 'open');
  Object.assign(DOCK, {since: Date.now()});
  $('#helpdesk .call').textContent = 'Dismiss';
  dockNote(STANDBY);
  const call = DOCK.calling = {};
  const agent = summonAgent();
  const started = await wrote('/api/system-chat', agent ? {agent} : {});
  if (DOCK.calling !== call) {  // dismissed while it was being reached: it is stopped as soon as it answers
    if (started) await wrote('/api/dispatch-stop', {work_id: started.work_id});
    return;
  }
  DOCK.calling = null;
  if (!started) { $('#helpdesk .call').textContent = 'Call'; return; }
  DOCK.mine = started.work_id;
  openHelpdesk(started.work_id, 'your system agent', STANDBY, started.session_id);
}
/* Chat on anything the page shows, VIEW-042: a ticket, open or done, a node, a question, or an agent's session. An
 * agent at work on it is talked to directly; otherwise one starts to talk, and Dismiss stops it. */
async function talkAbout(given, label) {
  // an intake's agent is a conversation already, never a ticket: its chat opens on its session
  if (isIntake(given.id)) return openIntakeChat(given.id, null);
  const agent = summonAgent();  // the agent a new chat starts with; one at work on it is talked to as it is
  const started = await wrote('/api/talk', {...given, ...(agent ? {agent} : {})});
  if (!started) return;
  if (started.conversation) DOCK.mine = started.work_id;
  openHelpdesk(started.work_id, label, started.state === 'running' ? 'It answers when its current step ends.' : STANDBY,
    started.session_id);
}
const chatButton = (given, label) => h('button', {class: 'chat', title: `Talk with an agent about ${label}`,
  onclick: event => { event.stopPropagation(); talkAbout(given, label); }}, 'Chat');
/* What a node is called to the agent: an element's address, or a join's receiver, which holds it. */
function nodeTalk(id) {
  const join = id.startsWith('p:') ? joinOf(id) : null;
  return {node: join ? join.receiver_address : S.elements.get(id)?.element.address || id};
}
async function dismiss() {
  if (DOCK.calling) {
    DOCK.calling = null;
    $('#helpdesk .call').textContent = 'Call';
    return dockNote('The call was cancelled.');
  }
  const chat = DOCK.chats.find(one => one.target === DOCK.target);
  if (chat && (chat.mine || chat.target === DOCK.mine)) await wrote('/api/dispatch-stop', {work_id: chat.target});
  if (DOCK.target === DOCK.mine) DOCK.mine = null;
  DOCK.chats = DOCK.chats.filter(one => one !== chat);
  dockNote('The agent was dismissed.');
  if (DOCK.chats.length) return showChat(DOCK.chats.at(-1));  // the next open chat comes on view
  Object.assign(DOCK, {target: null, session: null, label: ''});
  MERGE.chat = null;
  $('#helpdesk .call').textContent = 'Call';
  drawTabs();
}
$('#helpdesk .interrupt').onclick = () => interruptChat(DOCK.target, DOCK.session, $('#helpdesk .interrupt'));
$('#helpdesk .call').onclick = () => (DOCK.target || DOCK.calling ? dismiss() : callSystem());
$('#helpdesk .compose').onsubmit = async event => {
  event.preventDefault();
  const box = $('#helpdesk .say'), text = box.value.trim();
  if (!text && !DOCK.files.length) return;
  box.value = '';
  if (text.startsWith('/')) return dockCommand(text);
  if (!DOCK.target) return dockNote('Press Call to reach an agent first, or type /list to talk with one at work.');
  const attached = DOCK.files.length ? '\n\nAttached files, saved in the project:\n' + DOCK.files.map(file => `- ${file}`).join('\n') : '';
  if (await wrote('/api/dispatch-message', {work_id: DOCK.target, text: text + attached})) {
    DOCK.files = []; fill($('#helpdesk .files')); drawHelpdesk();
  } else box.value = text;
};
$('#helpdesk .say').addEventListener('keydown', event => {  // Enter sends, Shift+Enter starts a new line
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); $('#helpdesk .compose').requestSubmit(); }
});
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
$('#helpdesk .min').onclick = () => dockState('resting');
// On the overlay stack as the dock: Escape puts it away only from inside it, and it stays usable over the board.
overlay($('#helpdesk'), {kind: 'dock', close: () => dockState('resting'), focus: '.say'});
$('#helpdesk .big').onclick = () => dockState($('#dock').className === 'open big' ? 'open' : 'open big');
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
  $('#board .start-all').disabled = D.starting || !B.tickets.some(waiting);
}
async function renderBoard() {
  if ($('#board').hidden || !S.project) return;
  const project = S.project, metaform = S.base;  // the agents are read on dispatch events only, VIEW-018
  try { B.tickets = (await read('work', {limit: 0})).results || []; } catch (error) { toast(error.message); return; }
  if (S.project !== project || S.base !== metaform) return;
  drawBoard();
}
$('#boardBtn').onclick = async () => { $('#board').hidden = false; await renderBoard(); };
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
    // each agent sent to work it, and its session's log, VIEW-036 and VIEW-039
    ...dispatched.filter(one => one.work_id === ticket.id).map(one => h('div', {class: 'dispatch'},
      h('span', {}, `${agentName(one.agent)} sent ${when(one.started)} · `
        + (one.state === 'running' ? 'working' : `ended${one.how ? `, ${one.how}` : ''}`)),
      chatButton(one.state === 'running' ? {id: one.work_id} : {session: `${one.work_id}:${one.session_id}`},
        `${agentName(one.agent)} on ${ticketPart(ticket)}`),
      h('button', {class: 'btn sm log', type: 'button', title: "The session's whole thread", onclick: async () => {
        await renderAgents();
        agentAt(one.work_id, one.session_id);
      }}, 'Open log')))))
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
/* A floating window is moved by its title, and opens where the person last put it. */
function movable(box) {
  box.classList.add('movable');
  box.querySelector('.bar').addEventListener('pointerdown', event => {
    if (event.target.closest('button, input, select, textarea, a') || box.classList.contains('full')) return;
    const from = box.getBoundingClientRect(), start = [event.clientX - from.left, event.clientY - from.top];
    Object.assign(box.style, {transform: 'none', left: from.left + 'px', top: from.top + 'px'});  // a centered dialog moves from where it is
    const move = moved => {
      box.style.left = Math.max(0, Math.min(moved.clientX - start[0], innerWidth - 60)) + 'px';
      box.style.top = Math.max(0, Math.min(moved.clientY - start[1], innerHeight - 40)) + 'px';
    };
    const end = () => { removeEventListener('pointermove', move); removeEventListener('pointerup', end); keepPlace(box); };
    addEventListener('pointermove', move);
    addEventListener('pointerup', end);
    event.preventDefault();
  });
}
/* ---------- agents dispatched on tickets, VIEW-039 ----------
 * The dispatch module starts, messages and stops an agent on a ticket, BASE-052; the page asks it to through three
 * writes, VIEW-011. What an agent does is read from the dispatch layer at its ticket's node with each map change. */
const DOING = {agent_message_chunk: 'said', agent_thought_chunk: 'thought', user_message_chunk: 'was told',
  tool_call: 'ran', tool_call_update: 'ran', plan: 'plan', turn: 'turn', failed: 'failed', person: 'you', approved: 'approved'};
/* How each line of an agent's thread reads: what it says, what it thinks, what it runs, and what the person said. */
const THREAD = {agent_message_chunk: 'said', agent_thought_chunk: 'thought', user_message_chunk: 'told', tool_call: 'tool',
  tool_call_update: 'tool', plan: 'plan', turn: 'turn', failed: 'failed', person: 'you'};
const D = {sessions: [], notes: [], work: null, session: null, drawn: new Map(), starting: false, chat: null};
const AUTO = {value: false, agents: null};
async function readAutostart() {
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
const glyphFor = workId => drawGlyph(workId, ownGlyph(ticketOf(workId)));
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
  D.claims = claimed.claims || [];
  D.proposals = claimed.proposals || {};
  // the permission requests waiting for the person, one per agent session, counted on the chat's tab
  const asking = (found.signals || []).filter(one => one.signal === 'permission-waiting' && one.active !== false);
  D.asking = asking.map(one => ({...one, agent: D.sessions.find(row => row.session_id === one.session_id)?.agent}))
    .filter(one => D.sessions.some(row => row.session_id === one.session_id && row.state === 'running'));
  drawDockTab();
  readIntake(found.signals || []);
  if (D.chat) {
    const pending = D.chat;
    const session = D.sessions.find(one => one.work_id === pending.work && one.state === 'running'
      && (pending.session ? one.session_id === pending.session : !pending.known.has(one.session_id)));
    if (session) { D.chat = null; agentAt(session.work_id, session.session_id); }
  }
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
  $('#agents').hidden = !working.length;
  paintInUse();
  figures(S.tickets || []);  // the map's figures follow the same sessions
  if (D.work) await drawAgent();
}
function agentAt(workId, sessionId = null) {
  D.session = sessionId;
  if (D.work !== workId) { $('#agent .say').value = ''; D.drawn = new Map(); PINNED.agent = true; }
  D.work = workId;
  $('#agent').hidden = false;
  drawAgent();
}
/* One agent's window: what its session wrote on the dispatch layer, in order, with its plan as a checklist, its tool
 * calls opening to their diffs, its permission requests answered with the agent's own options, its settings and its
 * usage in the session bar, its other open questions, answered as every question is, VIEW-021, a message to send it,
 * and Stop. The text being written is part of the page and is never drawn again, so a map change keeps it, VIEW-018. */
async function drawAgent() {
  const work = D.work;
  const session = D.sessions.filter(one => one.work_id === work && (!D.session || one.session_id === D.session)).at(-1);
  const {agent, session_id: sessionId, state} = session || {};
  const ticket = ticketOf(work);
  $('#agent .icon').src = glyphOf(work);
  $('#agent .icon').alt = glyphFor(work);
  const activity = chatActivity(session);
  // the window's state is drawn at once and together: its title, what it is doing and what can be pressed
  $('#agent .title').textContent = `${agentName(agent)} · ${workPart(work)} · ${activity.label}`;
  $('#agent .state').textContent = activity.note;
  $('#agent .state').hidden = !activity.note;
  $('#agent').classList.toggle('asks', session?.activity === 'waiting');
  $('#agent .interrupt').disabled = !activity.interruptible;
  $('#agent .send').disabled = $('#agent .stop').disabled = state !== 'running';
  const task = ticket ? ticket.task || ticket.note || '' : isIntake(work) ? `The intake of ${S.project}: it records the map as it reads the project.` : '';
  if ($('#agent .task').textContent !== task) $('#agent .task').classList.remove('open');  // a new ticket starts short
  $('#agent .task').textContent = task;
  $('#agent .task').title = 'Click to show all of the task, and again to fold it';
  // A chat: newest at the bottom, kept in view while the person is reading the end of it, VIEW-039.
  const project = S.project, metaform = S.base;
  let notes = D.notes, states = D.states || {};
  try { const found = await read('dispatch-sessions', {id: work}); notes = found.lines || []; states = found.states || {}; }
  catch (error) { toast(error.message); }
  if (D.work !== work || S.project !== project || S.base !== metaform) return;
  D.notes = notes;
  D.states = states;
  D.state = sessionId ? states[sessionId] || null : null;
  D.agent = agent || null;
  drawSession($('#agent .sessionbar'), {work, session, state: D.state});
  drawPlan($('#agent .planbox'), D.state?.plan);
  const lines = D.notes.filter(line => line.work_id === work && (!sessionId || line.session_id === sessionId));
  const thread = $('#agent .activity');
  const following = PINNED.agent;
  keyedFill(thread, threadRows(lines, {work, agent, dock: false}));
  if (following) thread.scrollTop = thread.scrollHeight;
  let open = [];
  if (ticket && sessionId) {
    try { open = (await messagesOf(ticketNode(ticket))).unread.filter(record => record.kind === 'question' && record.by === `${agent} ${sessionId}`); }
    catch (error) { toast(error.message); }
  }
  if (D.work !== work) return;
  // a permission request is answered from its own card in the thread; its question at the node is the same request
  const permits = new Set(lines.filter(line => line.kind === 'permission').map(line => line.data?.message_id).filter(Boolean));
  open = open.filter(record => !permits.has(record.id));
  const drawn = new Map(open.map(record => [record.id, D.drawn.get(record.id) || asked(record)]));
  D.drawn = drawn;
  keepFill($('#agent .asked'), [...drawn.values()]);
}
/* The thread keeps its newest line in view while the person reads its end: it is pinned there until they scroll up,
 * and stays pinned as the window around it changes, as a question drawn under it or a resize takes room from it. */
const PINNED = {agent: true};
$('#agent .activity').addEventListener('scroll', () => {
  const thread = $('#agent .activity');
  PINNED.agent = thread.scrollTop + thread.clientHeight >= thread.scrollHeight - 24;
});
new ResizeObserver(() => {
  const thread = $('#agent .activity');
  if (PINNED.agent) thread.scrollTop = thread.scrollHeight;
}).observe($('#agent .activity'));
// The task shows in three lines, so the conversation always has the window; a click unfolds it, within a third.
$('#agent .task').onclick = () => $('#agent .task').classList.toggle('open');
$('#agent .chat').onclick = () => {
  const session = D.sessions.filter(one => one.work_id === D.work && (!D.session || one.session_id === D.session)).at(-1);
  const label = `${agentName(session?.agent)} on ${workPart(D.work)}`;
  if (isIntake(D.work)) return openIntakeChat(D.work, session?.session_id || null);
  talkAbout(!session || session.state === 'running' ? {id: D.work} : {session: `${D.work}:${session.session_id}`}, label);
};
$('#agent .send').onclick = async () => {
  const text = $('#agent .say').value.trim();
  if (!text) { toast('A message says something.'); return; }
  $('#agent .send').disabled = true;
  if (await wrote('/api/dispatch-message', {work_id: D.work, text})) { $('#agent .say').value = ''; toast('Sent to the agent.'); }
  $('#agent .send').disabled = false;
};
$('#agent .say').addEventListener('keydown', event => {  // Enter sends, Shift+Enter starts a new line
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); $('#agent .send').click(); }
});
$('#agent .interrupt').onclick = () => {
  const session = D.sessions.filter(one => one.work_id === D.work && (!D.session || one.session_id === D.session)).at(-1);
  return interruptChat(D.work, session?.session_id, $('#agent .interrupt'));
};
$('#agent .stop').onclick = async () => {
  $('#agent .stop').disabled = true;
  if (await wrote('/api/dispatch-stop', {work_id: D.work})) toast('The agent was stopped.');
  else $('#agent .stop').disabled = false;
};
$('#agent .close').onclick = () => { $('#agent').hidden = true; D.work = null; };
overlay($('#agent'), {kind: 'window', close: () => $('#agent .close').click(), focus: '.say'});
movable($('#agent'));
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
      openHelpdesk(started.work_id, `the sentinel on ${calledOf(key) || 'this node'}`, queued, started.session_id);
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
    h('h2', {}, `${called(join.receiver) || join.receiver_address} ← ${providers || join.provider_address}`),
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
const TABS = {object: '#p-object', prov: '#p-prov', prompt: '#p-prompt'};
function showTab(tab) {
  if (tab !== 'prompt' && $('#p-prompt').classList.contains('full')) promptFull(false);
  for (const [key, selector] of Object.entries(TABS)) {
    $(selector).hidden = key !== tab;
    $('#t-' + key).setAttribute('aria-selected', String(key === tab));
    $('#t-' + key).tabIndex = key === tab ? 0 : -1;
  }
  if (tab === 'prov') renderProv();
  if (tab === 'prompt' && !P.editor) renderPrompt();
  if (tab === 'prompt' && P.editor) setTimeout(() => P.editor.refresh(), 0);
}
for (const key of Object.keys(TABS)) $('#t-' + key).onclick = () => showTab(key);
$('.tabs[role=tablist]').addEventListener('keydown', event => {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  event.preventDefault();
  const keys = Object.keys(TABS), at = keys.findIndex(key => $('#t-' + key).getAttribute('aria-selected') === 'true');
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? keys.length - 1
    : (at + (event.key === 'ArrowRight' ? 1 : -1) + keys.length) % keys.length;
  showTab(keys[next]);
  $('#t-' + keys[next]).focus();
});
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
    const ends = `${receiver ? labelOf(receiver) : join.receiver_address} ← ${provider ? labelOf(provider) : join.provider_address || ''}`;
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
  if (!project) return HARNESS;
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

/* The chat's tab says when agents wait for the person's permission, and how many. */
function drawDockTab() {
  const waiting = (D.asking || []).length, tab = $('#dockTab');
  tab.classList.toggle('asks', waiting > 0);
  fill(tab, h('span', {}, 'Chat'), waiting ? h('b', {class: 'asking', 'aria-hidden': 'true'}, String(waiting)) : null);
  tab.setAttribute('aria-label', waiting ? `Open the chat: ${plural(waiting, 'agent waits', 'agents wait')} for your permission`
    : 'Open the chat with an agent');
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
/* A signal a session raised, said in words; a permission waiting is its card, so it is not said twice. */
function signalWords(text) {
  try { const found = JSON.parse(text); return found.signal === 'permission-waiting' ? null : `Signal: ${String(found.signal || '').replace(/-/g, ' ')}${found.active === false ? ', cleared' : ''}.`; }
  catch { return text; }
}
const QUIET_KINDS = new Set(['setting', 'approved', 'notice']);  // drawn small, in the thread's quiet color
/* The rows of a thread for keyedFill: in the dock, the conversation, its tool calls and its requests; in the agent
 * window, everything the session wrote. The plan is drawn apart, as a checklist. */
function threadRows(lines, {work, agent, dock}) {
  const rows = [];
  const tag = dock ? 'div' : 'li';
  for (const line of lines) {
    const key = `${line.session_id}:${line.name ?? line.seq}`;
    const kind = line.kind;
    const text = `${kind}\n${line.text}\n${line.data ? JSON.stringify(line.data) : ''}`;
    if (kind === 'plan' || kind === 'state' || kind === 'tool_detail') continue;
    if (kind === 'tool_call' || kind === 'tool_call_update') { rows.push({key, text, make: () => toolRow(line, tag, key)}); continue; }
    if (kind === 'permission') { rows.push({key, text, make: () => permissionCard(line, work, tag, agent)}); continue; }
    if (kind === 'signal') {
      const words = signalWords(line.text);
      if (words) rows.push({key, text, make: () => dock ? h('div', {class: 'system'}, words) : h('li', {class: 'signal'}, h('small', {}, 'signal'), words)});
      continue;
    }
    if (dock) {
      if (kind === 'agent_message_chunk') rows.push({key, text, make: () => h('div', {class: 'bubble theirs'}, ...linked(line.text))});
      else if (kind === 'person' || kind === 'user_message_chunk') rows.push({key, text, make: () => h('div', {class: 'bubble mine'}, line.text)});
      else if (['setting', 'approved', 'failed', 'notice'].includes(kind)) rows.push({key, text, make: () => h('div', {class: `system ${kind}`}, line.text)});
      continue;
    }
    rows.push({key, text, make: () => h('li', {class: THREAD[kind] || (QUIET_KINDS.has(kind) ? kind : 'note'), 'data-kind': kind},
      h('small', {}, DOING[kind] || String(kind || '').replace(/_/g, ' ')), ...linked(line.text))});
  }
  return rows;
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
  if (box.dataset.drawn === text || box.contains(document.activeElement) && box.dataset.work === work) return;
  box.dataset.drawn = text;
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
  box.hidden = !(controls.length || used || resume);
  fill(box, controls, h('span', {class: 'grow'}), used, resume);
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
  INTAKE.waiting = session ? signals.filter(one => one.signal === 'permission-waiting' && one.active !== false
    && one.work_id === session.work_id).length : 0;
  drawIntake();
}
/* The bar over the map while an intake runs or is being recorded: what is happening, its agent, and its acts. */
function drawIntake() {
  const bar = $('#intakeBar');
  const running = intakeRunning(), recording = LIVE.layer !== null;
  bar.hidden = !(running || recording);
  drawEmpty();
  if (bar.hidden) return;
  const parts = S.elements.size;
  const doing = INTAKE.waiting ? `${agentName(INTAKE.agent)} waits for your permission`
    : recording ? `Recording ${LIVE.layer} · ${plural(parts, 'part')} so far`
    : INTAKE.session?.activity === 'working' ? 'Reading the project' : 'Starting';
  bar.classList.toggle('asks', INTAKE.waiting > 0);
  fill(bar, h('span', {class: 'pulse', 'aria-hidden': 'true'}),
    h('span', {class: 'what'}, h('b', {}, running ? `Intake · ${agentName(INTAKE.agent)}` : 'Intake'),
      h('span', {class: 'doing'}, running ? doing : `Recording ${LIVE.layer} · ${plural(parts, 'part')} so far · by an agent outside the page`)),
    running ? h('button', {class: `btn sm ${INTAKE.waiting ? 'primary' : ''}`, type: 'button', onclick: () => openIntakeChat()},
      INTAKE.waiting ? 'Answer' : 'Chat') : null,
    running ? h('button', {class: 'btn sm danger', type: 'button', onclick: stopIntake}, 'Stop')
      : h('button', {class: 'btn sm', type: 'button', title: 'Start an agent that goes on with this intake, once no agent is still recording it',
        onclick: () => openIntake({resume: true})}, 'Take over…'));
}
/* The intake's chat in the dock: it is already a conversation, so it is opened on its session, never through a ticket. */
function openIntakeChat(work = INTAKE.work, session = INTAKE.session?.session_id || null) {
  if (!work) return;
  openHelpdesk(work, `the intake agent (${agentName(INTAKE.agent)})`, STANDBY, session);
  const chat = DOCK.chats.find(one => one.target === work);
  if (chat) chat.mine = true;
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
  if (kind.takes_project) given.project = S.project;
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
// The message boxes offer the commands as / is typed: the dock's own and the agent's, and in the agent window the agent's.
slashCommands($('#helpdesk .say'), dockOffered);
slashCommands($('#agent .say'), () => commandsOf(D.state, D.agent));
// The chat dock's own picker: the agent its new chats start with, beside Call.
$('#helpdesk .summon').append(summonPicker('dock', {up: true, label: 'Agent for new chats'}));

/* ---------- live: the server pushes what modules publish, and the page redraws; nothing polls, VIEW-018 ----------
 * An intake being recorded is drawn as each object arrives, BASE-039; any other write to the metaform shown is read
 * again. Events that come while the page reads are drawn once, when it is done. */
const LIVE = {layer: null, base: null, seen: '', busy: false, again: false, whole: false, named: null, done: 0, drawn: -Infinity};
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
  const start = keep || [...S.elements.values()].find(entry => entry.element.role === 'DE')?.element.id
    || S.elements.keys().next().value;
  if (start) select(start, false, false, false, true);
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
  const named = event.payload.tables;
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
  } catch (error) { toast(error.message); } finally { LIVE.busy = false; LIVE.done++; }
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
/* The tables a ticket or a message is written in, as map.changed names them, VIEW-018. A change to these alone adds or
 * removes no node and no link, so the map, its layers' items and its memories are not read again for it. */
const TICKET_TABLES = new Set(['work', 'work_links', 'work_steps', 'messages', 'map.glyphs', 'map.ticket_settings',
  'map.question_work']);
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
  const start = keep || MEM.key || [...S.elements.values()].find(entry => entry.element.role === 'DE')?.element.id
    || S.elements.keys().next().value;
  if (!start) fill($('#p-object'), emptyPanel());
  else {
    if (!keep) setTimeout(() => { if (G) fit3d(800, 60); }, 2200);
    await select(start, false, false, false, true);
  }
  await told;
  drawIntake();
}
async function loadMetaform() {
  S.view = null; S.selected = null; IN.length = 0; M.base = null; dropMemories(); renderCrumbs();
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
  Object.assign(D, {sessions: [], notes: [], work: null, session: null, drawn: new Map(), chat: null});
  $('#autostartAgents').checked = false;
  $('#autostartAgents').disabled = true;
  $('#agent').hidden = true;
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

async function main() {
  const response = await reach('/api/projects');
  const listed = await response.json();
  S.projects = listed.projects || [];
  if (!S.projects.length) {
    fill($('#p-object'), h('p', {class: 'empty'}, 'No project is registered. Register one with: metaform add project <id> <path>'));
    listen();  // still hears what modules publish: an intake started in a project registered later takes the page there
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
  listen();
  renderMerges();  // VIEW-044
}
// What a browser check reads of the page's controls, the overlays open, bottom to top, and the controls themselves,
// for the views built on them.
Object.assign(window.metaform, {overlays: () => OVERLAY.stack.map(entry => entry.box.id || entry.box.className),
  harnesses: () => ({...HARNESS, pickers: undefined, reading: undefined}), build: () => BUILD.job, intake: () => ({...INTAKE}),
  // an agent's session opened in the chat dock or in its window, as its chat button and its entry in the key open it
  chat: (work, session = null) => isIntake(work) ? openIntakeChat(work, session)
    : openHelpdesk(work, `${agentName(D.sessions.find(one => one.session_id === session)?.agent)} on ${workPart(work)}`, STANDBY, session),
  agent: (work, session = null) => agentAt(work, session),
  ui: {overlay, confirmAct, undoable, toast, segmented, progressBar, copyField, choice}});
main();
