/* The page's small controls: toasts with Undo, the confirmation asked before anything is taken away, segmented
 * choices, progress bars, copy fields and the choice list. */
import '/classic/app/core/overlays.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/classic/app/core/dom.js';
import {overlay, onClosed} from '/classic/app/core/overlays.js';

/* Toasts: what happened, said near the bottom, as long as it takes to read, and kept while it is pointed at or has
 * the focus. One that can be undone carries Undo. */
const TOAST = {timer: null, held: false, ms: 0};
export function toast(message, {action = null, run = null, ms = null} = {}) {
  const box = $('#toast');
  const act = async () => { box.hidden = true; await run(); };
  fill(box, h('span', {class: 'msg'}, message),
    action ? h('button', {class: 'btn sm', type: 'button', onclick: act}, action) : null);
  box.hidden = false;
  TOAST.ms = ms ?? Math.min(12000, Math.max(action ? 8000 : 4200, 1800 + String(message).length * 45));
  toastLater(TOAST.ms);
}
function toastLater(ms) {
  clearTimeout(TOAST.timer);
  if (!TOAST.held) TOAST.timer = setTimeout(() => { $('#toast').hidden = true; }, ms);
}
/* A toast stays while it is pointed at or has the focus, and goes a little after it is left. */
function holdToast(held) {
  TOAST.held = held;
  if (held) clearTimeout(TOAST.timer); else toastLater(2500);
}
for (const [kind, held] of [['pointerenter', true], ['pointerleave', false], ['focusin', true], ['focusout', false]]) {
  $('#toast').addEventListener(kind, () => holdToast(held));
}
/* What was just done, with Undo: `undo` writes it back and says whether it could. */
export function undoable(message, undo) {
  toast(message, {action: 'Undo', run: async () => { if (await undo()) toast('Undone.'); }});
}

/* The confirmation, the same everywhere a person is asked before something is taken away: what is asked, the one fact
 * that matters, what is lost and what stays, for an act that removes a project the word confirm typed, as the command
 * takes --confirm, and the two answers, the safe one first. It is a dialog of its own, or it fills `host`, a panel
 * the act belongs to, as clearing a project fills the panel under Administration, VIEW-019. It answers true for the
 * act and false for anything else, Escape and a click away among them. */
export function confirmAct({title = 'Are you sure?', text = '', lost = [], kept = [], verb = 'Remove',
  cancel = 'Cancel', typed = false, danger = true, host = null}) {
  const box = host || $('#confirm');
  const into = host || $('#confirm .body');
  return new Promise(answer => {
    let done = false;
    const settle = value => { if (done) return; done = true; answer(value); };
    const field = typed ? h('input', {class: 'typed', type: 'text', placeholder: 'confirm', autocomplete: 'off',
      spellcheck: 'false', 'aria-label': 'Type confirm to go on', 'data-autofocus': ''}) : null;
    const go = h('button', {class: `btn confirm ${danger ? 'danger solid' : 'primary'}`, type: 'button',
      disabled: typed, onclick: () => { settle(true); if (!host) box.hidden = true; }}, verb);
    const keep = h('button', {class: 'btn keep', type: 'button', 'data-autofocus': typed ? null : '',
      onclick: () => { settle(false); box.hidden = true; }}, cancel);
    if (field) {
      field.oninput = () => { go.disabled = field.value.trim().toLowerCase() !== 'confirm'; };
      field.onkeydown = event => { if (event.key === 'Enter' && !go.disabled) go.click(); };
    }
    fill(into, h('div', {class: `confirm${danger ? ' warn' : ''}`},
      h('h3', {class: 'ask', id: host ? null : 'confirmTitle'}, title),
      text ? [text].flat().map(line => h('p', {}, line)) : null,
      confirmList('What is lost', lost, 'lost'), confirmList('What stays', kept, 'kept'),
      field ? h('label', {class: 'gate'}, 'Type confirm to go on:', field) : null,
      h('div', {class: 'acts'}, keep, go)));
    box.hidden = false;
    onClosed(box, () => settle(false));
    if (host && field) setTimeout(() => field.focus(), 0);
  });
}
/* A list of the confirmation, what is lost or what stays, under its heading; nothing when it is empty. */
function confirmList(heading, items, kind) {
  if (!items.length) return null;
  return [h('div', {class: 'heading'}, heading), h('ul', {class: kind}, items.map(item => h('li', {}, item)))];
}

/* A segmented control: one choice of a few, as a row of buttons that act as radios, walked with the arrow keys.
 * options: [{value, label, title, disabled}]. */
export function segmented({label, options, value, onchange}) {
  const group = h('div', {class: 'segmented', role: 'radiogroup', 'aria-label': label});
  const paint = chosen => {
    value = chosen;
    for (const button of group.children) {
      const on = button.dataset.value === String(chosen);
      button.setAttribute('aria-checked', String(on));
      button.tabIndex = on ? 0 : -1;
    }
  };
  const choose = chosen => {
    if (String(value) === String(chosen)) return;
    paint(chosen);
    onchange?.(chosen);
  };
  const walk = event => {  // the arrow keys step to the next usable choice, round the ends
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
    event.preventDefault();
    const buttons = [...group.children].filter(button => !button.disabled);
    const at = buttons.findIndex(button => button.dataset.value === String(value));
    const step = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : -1;
    const next = buttons[(at + step + buttons.length) % buttons.length];
    next.click(); next.focus();
  };
  for (const option of options) group.append(h('button', {type: 'button', role: 'radio', 'data-value': option.value,
    title: option.title, disabled: option.disabled, onclick: () => choose(option.value)}, option.label));
  group.addEventListener('keydown', walk);
  paint(value);
  group.set = paint;
  return group;
}
/* A progress bar with how far along in words. `value` from 0 to 1, or null while it cannot be told. */
export function progressBar({label, value = null, words = ''}) {
  const fillPart = h('div', {class: 'fill'}), said = h('span', {class: 'said'}, words);
  const share = h('span', {class: 'share'});
  const bar = h('div', {class: 'progressbar', role: 'progressbar', 'aria-label': label, 'aria-valuemin': '0',
    'aria-valuemax': '100'}, h('div', {class: 'track'}, fillPart), h('div', {class: 'words'}, said, share));
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
    const valueText = [text, next === null ? '' : `${Math.round(next * 100)}%`].filter(Boolean).join(', ');
    bar.setAttribute('aria-valuetext', valueText);
  };
  bar.set(value, words);
  return bar;
}
/* A text to copy, shown whole and read-only, with Copy beside it; the clipboard where the browser gives one, and the
 * text selected for a copy by hand where it does not. With `rows`, a text of many lines, shown in that many. */
export function copyField({label, text, rows = 0}) {
  const selectAll = event => event.target.select();
  const field = rows
    ? h('textarea', {readonly: true, rows, 'aria-label': label, spellcheck: 'false', onfocus: selectAll})
    : h('input', {type: 'text', readonly: true, value: text, 'aria-label': label, onfocus: selectAll});
  if (rows) field.value = text;
  const copyNow = async () => {
    try { await navigator.clipboard.writeText(field.value); toast('Copied.'); }
    catch { field.focus(); field.select(); toast('Press Ctrl+C or Cmd+C to copy it.'); }
  };
  const copy = h('button', {class: rows ? 'btn' : 'btn icon', type: 'button', 'aria-label': `Copy ${label}`,
    title: 'Copy', onclick: copyNow}, h('i', {class: 'i i-copy', 'aria-hidden': 'true'}), rows ? 'Copy' : null);
  const box = h('div', {class: `copyfield${rows ? ' lines' : ''}`}, field, copy);
  box.set = value => { field.value = value; };
  return box;
}
/* A choice of one, each option with a badge saying whether it can be used here, such as an agent found on this
 * machine or not; an option that cannot be chosen says why. options: [{value, label, badge, ok, disabled, hint}].
 * It is a button that opens a list box, walked with the arrow keys, Home and End, and typed into to jump. The list
 * floats over the page from its button, below it or, where there is more room or the choice is `.up`, above it, so a
 * window's scrolling body never cuts it off; a scroll elsewhere or a resize closes it. */
export function choice({label, options, value, onchange}) {
  const id = `choice${++choice.made}`;
  const shownLabel = h('span', {class: 'lbl'});
  const shownBadge = h('span');
  const shown = h('span', {style: {display: 'flex', gap: '8px', 'align-items': 'center', 'min-width': '0'}},
    shownLabel, shownBadge);
  const button = h('button', {class: 'btn', type: 'button', 'aria-haspopup': 'listbox', 'aria-expanded': 'false',
    'aria-controls': id, 'aria-label': label}, shown, h('i', {class: 'i i-chev', 'aria-hidden': 'true'}));
  const list = h('div', {class: 'listbox', id, role: 'listbox', hidden: true, tabindex: '-1', 'aria-label': label});
  const box = h('div', {class: 'choice'}, button, list);
  let active = -1;
  const paint = () => {
    const chosen = options.find(option => option.value === value) || options[0];
    shownLabel.textContent = chosen ? chosen.label : '';
    fill(shownBadge, chosen ? choiceBadge(chosen) : null);
    fill(list, options.map((option, index) => h('div', {role: 'option', id: `${id}-${index}`,
      'data-value': option.value, 'aria-selected': String(option.value === value),
      'aria-disabled': option.disabled ? 'true' : null, class: index === active ? 'active' : null,
      onclick: () => pick(index), onpointermove: () => { active = index; mark(); }},
      h('span', {}, option.label), choiceBadge(option), option.hint ? h('small', {}, option.hint) : null)));
  };
  const mark = () => {
    [...list.children].forEach((row, index) => row.classList.toggle('active', index === active));
    if (active < 0) return;
    list.setAttribute('aria-activedescendant', `${id}-${active}`);
    list.children[active]?.scrollIntoView({block: 'nearest'});
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
    const left = Math.max(8, Math.min(at.left, innerWidth - width - 8));
    Object.assign(list.style, {position: 'fixed', left: `${left}px`, width: `${width}px`, right: 'auto',
      top: up ? 'auto' : `${at.bottom + 4}px`, bottom: up ? `${innerHeight - at.top + 4}px` : 'auto',
      maxHeight: `${Math.max(120, Math.min(320, up ? above : below))}px`});
  };
  const toggle = () => {
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
  const keys = event => {  // Up and Down, Home and End, Enter or Space to choose, a letter to jump
    const usable = options.map((option, index) => option.disabled ? -1 : index).filter(index => index >= 0);
    const at = usable.indexOf(active);
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      active = usable[(at + (event.key === 'ArrowDown' ? 1 : -1) + usable.length) % usable.length];
      mark();
    } else if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault();
      active = event.key === 'Home' ? usable[0] : usable.at(-1);
      mark();
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      pick(active);
    } else if (event.key.length === 1 && /\S/.test(event.key)) {
      const found = usable.find(index => options[index].label.toLowerCase().startsWith(event.key.toLowerCase()));
      if (found !== undefined) { active = found; mark(); }
    }
  };
  button.onclick = toggle;
  list.addEventListener('keydown', keys);
  overlay(list, {kind: 'popover', focus: () => list});
  box.set = (nextOptions, nextValue = value) => { options = nextOptions; value = nextValue; paint(); };
  box.value = () => value;
  paint();
  return box;
}
/* An option's badge, ok, off or plain, or nothing for an option without one. */
function choiceBadge(option) {
  if (!option.badge) return null;
  return h('span', {class: `badge ${option.ok === false ? 'off' : option.ok ? 'ok' : ''}`}, option.badge);
}
choice.made = 0;
choice.open = new Set();
/* An open list floats from its button, so a resize, or a scroll anywhere but in the list, closes it. */
function closeChoices(event = null) {
  for (const list of choice.open) if (!event || !list.contains(event.target)) list.hidden = true;
}
addEventListener('resize', () => closeChoices());
document.addEventListener('scroll', closeChoices, true);
