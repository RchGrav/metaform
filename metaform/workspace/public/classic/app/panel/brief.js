/* The brief, what an agent reads about the selected element, from the earlier page's panel/brief.js. */
import '/classic/app/search/search.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/classic/app/core/dom.js';
import {toast} from '/classic/app/core/controls.js';
import {S, MEM} from '/classic/app/core/reads.js';
import {mermaidText} from '/classic/app/header/export.js';
import {joinOf} from '/classic/app/graph/data.js';
import {labelOf} from '/classic/app/map2d/inside.js';
import {select} from '/classic/app/selection/select.js';
import {readBrief} from '/classic/app/adapter.js';

/* ---------- the brief: what an agent reads about the selected element ----------
 * The element's brief is the host's answer to the `project-map` command `{"goto": "<address>"}`, read through
 * adapter.js `readBrief`, so the person sees what an agent that goes there is handed: the element, what it relies on
 * and what relies on it, each with why, how and direction, how many records each layer holds there, and the
 * instructions of those layers. Its size is said in characters. A line between two elements has no address of its
 * own, so a line shows the brief of the element that holds it. Below the brief is the answer exactly as the host sent
 * it. The earlier page's brief also listed the memories, messages and work numbered at the address, walked from one
 * to the next, and held the brief to a size setting; the new server has none of those, so they are not part of this
 * page. */
const BR = {address: null, generation: 0, data: null};
export const counted = (count, unit = 'characters') => `${Number(count).toLocaleString('en')} ${unit}`;
export function briefAddress(id = S.selected) {
  if (!id || MEM.key) return null;
  if (id.startsWith('p:')) return joinOf(id)?.receiver_address || null;
  return S.elements.get(id)?.element.address || null;
}
export const elementAt = address => [...S.elements.values()]
  .find(entry => entry.element.address === address)?.element || null;
/* A text to copy in one press, the clipboard where the browser gives one. */
export function briefCopy(label, text, words = 'Copy') {
  async function copy() {
    try { await navigator.clipboard.writeText(typeof text === 'function' ? await text() : text); toast('Copied.'); }
    catch { toast('The browser did not let the page copy it.'); }
  }
  return h('button', {class: 'btn sm quiet copy', type: 'button', 'aria-label': `Copy ${label}`, title: `Copy ${label}`,
    onclick: copy}, h('i', {class: 'i i-copy', 'aria-hidden': 'true'}), words);
}
/* How much of what holds it a text takes: a bar with the count in words beside it, over the limit said in words too.
 * The new server sets no limit on a brief, so this page gives none and the count stands alone. */
export function budgetMeter(label, used, budget, unit = 'characters') {
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
export function briefTo(id) {
  select(id, true);
  requestAnimationFrame(() => $('#p-brief h2')?.focus({preventScroll: true}));  // the walk goes on in the brief
}
/* The brief as a tree of the element and its neighbours: the element's address, then what it relies on and what
 * relies on it, each neighbour's line followed by the why of its want, set apart as the earlier page set a purpose
 * apart, then how many records each layer holds there. Each address is a link to its node. */
function aroundTree(brief, address) {
  const branch = (title, entries, said) => {
    const lines = [`\n${title} ${entries.length}`];
    entries.forEach(([key, value], at) => lines.push(`\n ${at === entries.length - 1 ? '└' : '├'} `, ...said(key, value)));
    return lines;
  };
  const want = (to, each) => [addressLink(to), each?.why ? h('span', {class: 'purpose'}, `  · ${each.why}`) : null];
  const records = (name, each) => [`${name} · ${counted(each?.records ?? 0, 'records')}`];
  return [addressLink(address),
    ...branch('relies on', Object.entries(brief.wants || {}), want),
    ...branch('relied on by', Object.entries(brief.wanted_by || {}), want),
    ...branch('layers', Object.entries(brief.layers || {}), records),
    brief.memory ? `\nmemory · ${counted(brief.memory.records ?? 0, 'records')}` : null];
}
export async function renderBrief() {
  const pane = $('#p-brief'), address = briefAddress();
  if (address !== BR.address) Object.assign(BR, {address, data: null});
  if (!address) {
    BR.generation++;
    return fill(pane, h('p', {class: 'empty'},
      'Select an element on the map to read its brief: what an agent that goes there is handed.'));
  }
  const generation = ++BR.generation;
  if (!BR.data) fill(pane, h('p', {class: 'loading'}, 'Reading the brief…'));
  let data;
  try { data = await readBrief(S.project, address); } catch (error) {
    if (generation === BR.generation) {
      fill(pane, h('div', {class: 'eyebrow'}, 'Agent brief'), h('h2', {tabindex: '-1'}, address),
        h('p', {class: 'failed', role: 'alert'}, error.message));
    }
    return;
  }
  if (generation !== BR.generation || address !== briefAddress()) return;
  BR.data = {address, ...data};
  drawBrief();
}
function drawBrief() {
  const pane = $('#p-brief'), data = BR.data, brief = data.body;
  const element = brief.element || {}, scroll = pane.scrollTop;
  const join = S.selected?.startsWith('p:') ? joinOf(S.selected) : null;
  const asked = JSON.stringify({goto: data.address});
  const rules = Object.entries(brief.instructions || {});
  fill(pane,
    h('div', {class: 'head'}, h('div', {class: 'eyebrow'}, 'Agent brief'),
      h('h2', {tabindex: '-1'}, element.name || element.technical_name || data.address),
      h('div', {class: 'uri'}, h('code', {}, asked), briefCopy('the command that reads this brief', asked, ''))),
    join ? h('p', {class: 'hint'}, 'A line has no address of its own, so this is the brief of the element that '
      + 'holds it.') : null,
    budgetMeter('Brief', data.text.length, null),
    h('p', {class: 'hint'}, 'What an agent that goes to this address is handed, read as it reads it: the answer to ',
      h('code', {}, 'goto'), ' of the ', h('code', {}, 'project-map'), ' tool.'),
    element.role || element.status ? h('div', {class: 'pills'},
      element.role ? h('span', {class: 'pill'}, element.role) : null,
      element.status ? h('span', {class: 'pill work-unbuilt'}, element.status === 'un_built' ? 'not built'
        : element.status) : null) : null,
    h('pre', {class: 'brieftext tree', tabindex: '0',
      'aria-label': 'What is held at the element and around it, as the agent reads it, with the why of each neighbour'},
    aroundTree(brief, data.address)),
    rules.length ? [h('div', {class: 'eyebrow'}, 'Instructions'),
      rules.map(([layer, text]) => h('p', {class: 'hint'}, h('code', {}, layer), ' · ', text))] : null,
    h('details', {class: 'sent'}, h('summary', {}, `Exactly as sent · ${counted(data.text.length)}`),
      h('pre', {class: 'brieftext raw', tabindex: '0', 'aria-label': 'The brief exactly as an agent receives it'},
        data.text),
      briefCopy('the brief as sent', data.text)),
    briefActs(data.address));
  pane.scrollTop = scroll;
}
/* The node with its neighbours copied as Mermaid. */
function briefActs(address) {
  return h('div', {class: 'acts'},
    briefCopy('this element and its neighbours as Mermaid', () => mermaidText({address}), 'Copy as Mermaid'));
}
