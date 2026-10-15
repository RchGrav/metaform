/* Banners: what the page must say until it is dealt with, a failed read, a fault, a server that does not answer, in one
 * strip at the top of the page, over the maps and windows and never modal, so the rest of the page stays usable. */
import '/page/app/core/controls.js';  // the part before runs first, so the parts run in the page's order
import {h, fill} from '/page/app/core/dom.js';

/* banner(key, spec) shows the banner named `key`, or draws that one again in place, never a second copy:
 *   tone      'error', 'warn', 'info' or 'ok'; an error or a warning is an alert, read out at once
 *   title     one short line
 *   text      what happened, in plain words
 *   next      the step to take, shown as "Next: …"
 *   detail    a small line: where, since when, how many times
 *   actions   the buttons, [{label, run, primary}]
 *   closable  a close ×, unless false, for a state the person cannot dismiss
 *   ms        it closes itself after this long; null, it stays
 *   onClose   called once as it goes, with who closed it: 'person', 'code' or 'time'
 * unbanner(key) closes it; bannered(key) says whether it shows. */
const SHOWN = new Map();  // key -> {box, spec, timer}
const STRIP = h('div', {id: 'banners', role: 'region', 'aria-label': 'Problems and notices'});
document.body.append(STRIP);

export function banner(key, spec) {
  const had = SHOWN.get(key);
  const box = had?.box || h('div', {class: 'banner', 'data-key': key});
  const tone = spec.tone || 'error';
  box.className = `banner ${tone}`;
  box.setAttribute('role', tone === 'error' || tone === 'warn' ? 'alert' : 'status');
  const acts = (spec.actions || []).map(act => h('button', {class: `btn sm${act.primary ? ' primary' : ''}`,
    type: 'button', onclick: () => act.run()}, act.label));
  fill(box,
    h('div', {class: 'words'},
      spec.title ? h('strong', {class: 'title'}, spec.title) : null,
      spec.text ? h('p', {class: 'text'}, spec.text) : null,
      spec.next ? h('p', {class: 'next'}, h('span', {class: 'lead'}, 'Next: '), spec.next) : null,
      spec.detail ? h('p', {class: 'detail'}, spec.detail) : null),
    acts.length ? h('div', {class: 'acts'}, acts) : null,
    spec.closable === false ? null : h('button', {class: 'close btn icon sm quiet', type: 'button',
      'aria-label': 'Close', title: 'Close', onclick: () => gone(key, 'person')},
    h('i', {class: 'i i-close', 'aria-hidden': 'true'})));
  clearTimeout(had?.timer);
  const timer = spec.ms ? setTimeout(() => gone(key, 'time'), spec.ms) : null;
  SHOWN.set(key, {box, spec, timer});
  if (!box.isConnected) STRIP.append(box);
  return box;
}
function gone(key, by) {
  const had = SHOWN.get(key);
  if (!had) return;
  SHOWN.delete(key);
  clearTimeout(had.timer);
  had.box.remove();
  had.spec.onClose?.(by);
}
export const unbanner = key => gone(key, 'code');
export const bannered = key => SHOWN.has(key);
