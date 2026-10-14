/* The overlay stack: every window, menu, popover, dialog and the chat dock registered once, stacked as they open,
 * with Escape, outside clicks, focus and Tab handled the same everywhere, and where a window opens. */
import '/page/app/core/dom.js';  // the part before runs first, so the parts run in the page's order
import {$, h} from '/page/app/core/dom.js';

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
export const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]):not([type=hidden]),'
  + 'select:not([disabled]),textarea:not([disabled]),[contenteditable="true"],[tabindex]:not([tabindex="-1"])';
export const OVERLAY = {stack: [], known: new Map(), base: 1000, closing: new Map(), trail: []};
/* The controls the person last reached, by the focus or by a press, so the one that opened an overlay is known even
 * when the overlay takes the focus at once or a browser does not focus a button pressed. */
function rememberReached(node) {
  const control = node instanceof Element ? node.closest(FOCUSABLE) : null;
  if (!control) return;
  OVERLAY.trail = [...OVERLAY.trail.filter(one => one !== control), control].slice(-8);
}
document.addEventListener('focusin', event => rememberReached(event.target), true);
document.addEventListener('pointerdown', event => rememberReached(event.target), true);
export const shown = node => Boolean(node && node.isConnected && node.getClientRects().length
  && !node.closest('[hidden],[inert]'));
const focusables = box => [...box.querySelectorAll(FOCUSABLE)].filter(shown);
/* Register an element as an overlay. `close` hides it as its own close button does, `guard` may keep it open (it
 * returns false to keep it), `focus` names what takes the focus as it opens (a selector, a function, or false). */
export function overlay(box, {kind = 'window', close = null, guard = null, focus = null} = {}) {
  OVERLAY.known.set(box, {box, kind, close, guard, focus});
  if (!box.hidden) opened(box);
  return box;
}
const overlayOf = box => OVERLAY.stack.find(entry => entry.box === box) || null;
const topOverlay = () => OVERLAY.stack.at(-1) || null;
/* Whether the maps' keys rest: an overlay that is not a window or the dock is open, or the focus is in one. */
export function overlayHolds(target = document.activeElement) {
  if (OVERLAY.stack.some(entry => !['window', 'dock'].includes(entry.kind))) return true;
  return Boolean(target && OVERLAY.stack.some(entry => entry.box.contains(target)));
}
export function opened(box) {
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
  requestAnimationFrame(() => focusInto(box, known));  // once it is drawn, so its controls can take the focus
}
const TEXT_FIELD = 'input:not([type=checkbox]):not([type=radio]),textarea,select,[contenteditable="true"]';
/* The focus moves into an overlay just opened: what its `focus` names, else a control marked to take it, a menu's
 * first item, its first text field, its first control other than Close, or the overlay itself. */
function focusInto(box, known) {
  if (box.hidden || box.contains(document.activeElement)) return;
  const wanted = typeof known.focus === 'function' ? known.focus()
    : known.focus ? box.querySelector(known.focus) : null;
  if (wanted === false) return;
  const fields = focusables(box);
  const first = wanted || box.querySelector('[data-autofocus]')
    || (known.kind === 'menu' ? fields.find(one => one.matches('button,[role=menuitem]')) : null)
    || fields.find(one => one.matches(TEXT_FIELD))
    || fields.find(one => !one.classList.contains('close')) || fields[0];
  if (first) first.focus({preventScroll: true});
  else { if (!box.hasAttribute('tabindex')) box.setAttribute('tabindex', '-1'); box.focus({preventScroll: true}); }
}
export function closed(box) {
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
export function onClosed(box, hook) { OVERLAY.closing.set(box, [...(OVERLAY.closing.get(box) || []), hook]); }
/* The stack's order is its stacking order, and a modal overlay makes everything under it inert behind a backdrop. */
const SCRIM = h('div', {id: 'scrim', hidden: true, 'aria-hidden': 'true'});
document.body.append(SCRIM);
export function restack() {
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
/* The stack follows each overlay's `hidden`, wherever in the page it is shown or hidden. */
function followHidden(changes) {
  for (const change of changes) {
    const box = change.target;
    if (!OVERLAY.known.has(box)) continue;
    if (box.hidden) closed(box); else opened(box);
  }
}
new MutationObserver(followHidden)
  .observe(document.body, {attributes: true, attributeFilter: ['hidden'], subtree: true});
/* Escape closes the top overlay and only that one; the chat dock counts only while the focus is in it, so the chat
 * left open at the side never takes an Escape meant for the map. With none open it reaches the maps. A search box of
 * the prompt editor takes its own Escape. */
function escapeTop(event) {
  if (event.key !== 'Escape' || event.isComposing || !OVERLAY.stack.length) return;
  if (event.target.closest?.('.CodeMirror-dialog')) return;
  const active = document.activeElement;
  const target = [...OVERLAY.stack].reverse().find(entry => entry.kind !== 'dock' || entry.box.contains(active));
  if (!target) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  closeOverlay(target);
}
document.addEventListener('keydown', escapeTop, true);
/* A click outside a menu or a popover closes it; its own button toggles it. Pressed outside, it closes before the
 * click acts, so the click reaches what it was meant for. */
function closeOutside(event) {
  for (const entry of [...OVERLAY.stack].reverse()) {
    if (!['menu', 'popover'].includes(entry.kind)) continue;
    if (entry.box.contains(event.target)) break;  // a click inside the top popover leaves those under it as they are
    const toggle = entry.opener?.getAttribute?.('aria-controls') === entry.box.id ? entry.opener : null;
    if (toggle?.contains(event.target)) continue;
    if (event.target.closest?.('#toast')) continue;
    closeOverlay(entry);
  }
}
document.addEventListener('pointerdown', closeOutside, true);
/* Tab stays inside a modal overlay and the ones open over it. */
function trapTab(event) {
  if (event.key !== 'Tab') return;
  const modal = OVERLAY.stack.findLastIndex(entry => entry.kind === 'dialog');
  if (modal < 0) return;
  const open = OVERLAY.stack.slice(modal).map(entry => entry.box);
  const fields = open.flatMap(focusables);
  if (!fields.length) return;
  const at = fields.indexOf(document.activeElement), last = fields.length - 1;
  if (at < 0 || (event.shiftKey && at === 0) || (!event.shiftKey && at === last)) {
    event.preventDefault();
    fields[event.shiftKey ? (at <= 0 ? last : at - 1) : (at < 0 || at === last ? 0 : at + 1)].focus();
  }
}
document.addEventListener('keydown', trapTab);
/* A menu is walked with Up, Down, Home and End, as menus are; a field in it keeps its own keys. */
function walkMenu(event) {
  const entry = topOverlay();
  if (!entry || entry.kind !== 'menu' || !entry.box.contains(document.activeElement)) return;
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
  if (event.target.matches('input,select,textarea')) return;
  const items = focusables(entry.box).filter(one => one.matches('button,[role=menuitem]'));
  if (!items.length) return;
  event.preventDefault();
  const at = items.indexOf(document.activeElement);
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1
    : (at + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
  items[next].focus();
}
document.addEventListener('keydown', walkMenu);
/* Where a window opens: where the person last put it, kept in this browser; otherwise a window read beside the map
 * stands just beside the side column, on the map's side, under the header, a step down from another one open there,
 * and any other window in the middle of the page. A dialog is placed by its styles. Every place is kept inside the
 * window's view. */
const PLACES = 'metaform.places';
function places() { try { return JSON.parse(localStorage.getItem(PLACES) || '{}'); } catch { return {}; } }
export function place(box) {
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
  const right = innerWidth - Math.min(size.width, innerWidth - 16) - 8;
  box.style.left = Math.round(Math.max(8, Math.min(left, right))) + 'px';
  box.style.top = Math.round(Math.max(8, Math.min(top, innerHeight - 48))) + 'px';
}
export function keepPlace(box) {
  if (!box.id) return;
  const kept = places();
  kept[box.id] = {left: parseFloat(box.style.left) || 0, top: parseFloat(box.style.top) || 0};
  try { localStorage.setItem(PLACES, JSON.stringify(kept)); } catch { /* storage can be blocked; it opens as usual */ }
}
