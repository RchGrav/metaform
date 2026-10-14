/* The brief, what an agent reads about the selected node: its counts, tree, items, what is new, and walking between
 * memories. */
import '/page/app/panel/object.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {toast, segmented} from '/page/app/core/controls.js';
import {FRAMED, S, MEM, read} from '/page/app/core/reads.js';
import {mermaidText, noMetaform, noneYet} from '/page/app/header/admin.js';
import {joinOf} from '/page/app/graph/data.js';
import {labelOf} from '/page/app/map2d/inside.js';
import {refusalBox} from '/page/app/settings/screen.js';
import {select, workPill} from '/page/app/selection/select.js';
import {openAgentView} from '/page/app/panel/agentview.js';

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
export const counted = (count, unit = 'bytes') => `${Number(count).toLocaleString('en')} ${unit}`;
const ITEM_REF = /([^\s#]+)#([0-9a-fA-F]{1,15})\b/;
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
/* How much of what holds it a text takes: a bar with the count in words beside it, over the limit said in words too. */
export function budgetMeter(label, used, budget, unit = 'bytes') {
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
export function briefTo(id, open = null) {
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
  for (const one of brief.receives || []) {
    for (const provider of one.providers || []) if (one.purpose) purposes.set(provider, one.purpose);
  }
  return String(brief.around).split('\n').flatMap((line, at) => {
    const named = line.match(/^\s*[├└]\s+(\S+)/)?.[1];
    const purpose = named && purposes.get(named);
    return [at ? '\n' : '', ...linkedAddresses(line), purpose ? h('span', {class: 'purpose'}, `  · ${purpose}`) : null];
  });
}
export async function renderBrief() {
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
    if (generation === BR.generation) {
      fill(pane, h('div', {class: 'eyebrow'}, 'Agent brief'), h('h2', {tabindex: '-1'}, address),
        refusalBox(error.body || {error: error.message}));
    }
    return;
  }
  if (generation !== BR.generation || address !== briefAddress()) return;
  // a brief read again keeps the older items already listed below its newest page
  const lowest = data.items.length ? data.items.at(-1).number : 0;
  const older = BR.data && lowest ? BR.items.filter(item => item.number < lowest) : [];
  Object.assign(BR, {data, items: [...data.items, ...older],
    ...(older.length ? {} : {cursor: data.nextCursor ?? null})});
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
    join ? h('p', {class: 'hint'}, 'A join\'s items are numbered at its receiver, so this is the receiver\'s brief.')
      : null,
    budgetMeter('Brief', data.bytes, data.budget),
    h('p', {class: 'hint'}, 'What an agent assigned here is handed, read as it reads it. Its size is held to the ',
      h('code', {}, 'node_summary_bytes'), ' setting.'),
    brief && (element.role || (element.open_work || []).length) ? h('div', {class: 'pills'},
      element.role ? h('span', {class: 'pill'}, element.role) : null, (element.open_work || []).map(workPill)) : null,
    brief?.around ? h('pre', {class: 'brieftext tree', tabindex: '0',
      'aria-label': 'What is held at the node and around it, as the agent reads it, with each neighbour\'s purpose'},
    aroundTree(brief)) : null,
    !brief ? h('pre', {class: 'brieftext', tabindex: '0', 'aria-label': 'The brief, as the agent reads it'}, data.text)
      : null,
    itemsSection(),
    h('details', {class: 'sent'}, h('summary', {}, `Exactly as sent · ${counted(data.bytes)}`),
      h('pre', {class: 'brieftext raw', tabindex: '0', 'aria-label': 'The brief exactly as an agent receives it'},
        data.text),
      briefCopy('the brief as sent', data.text)),
    FRAMED ? null : briefActs(data.address));
  pane.scrollTop = scroll;
}
/* What an agent sees, and the node with its neighbours copied as Mermaid. */
function briefActs(address) {
  return h('div', {class: 'acts'},
    h('button', {class: 'btn sm seeall', type: 'button', 'aria-controls': 'agentview',
      title: 'The connect message, the glossary with its tools, and this brief, each with its size',
      onclick: openAgentView}, 'What an agent sees…'),
    briefCopy('this node and its neighbours as Mermaid', () => mermaidText({address}), 'Copy as Mermaid'));
}
function itemsSection() {
  const latest = BR.data.latest;
  const list = h('ul', {class: 'items', 'aria-label': 'The items numbered here, newest first'});
  const kinds = segmented({label: 'Kinds of item shown', value: BR.kind,
    options: Object.entries(ITEM_KINDS).map(([value, [label]]) => ({value, label})),
    onchange: kind => { BR.kind = kind; itemsOfKind(list); }});
  const box = h('section', {class: 'itembox', 'aria-label': 'Items here'},
    h('div', {class: 'itemshead'},
      h('div', {class: 'eyebrow'}, latest ? `Items here · newest ${hex(latest.number)}` : 'Items here'), kinds),
    BR.walk.length ? walkTrail() : null,
    BR.seen === null && latest
      ? h('p', {class: 'hint'}, 'First look here in this browser: items numbered after now are marked unseen.') : null,
    newHere(latest, BR.data.last_session),
    list);
  drawItems(list);
  return box;
}
/* The items walked to from one memory to the next, with Back. */
function walkTrail() {
  return h('nav', {class: 'walk', 'aria-label': 'The items walked to here'},
    h('button', {class: 'btn sm quiet', type: 'button', title: 'Back to the item walked from', onclick: walkBack},
      h('i', {class: 'i i-back', 'aria-hidden': 'true'}), 'Back'),
    h('span', {class: 'trail'}, [...BR.walk, BR.open].filter(Boolean).join(' → ')));
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
  const rows = BR.items.map(itemRow);
  const none = BR.kind !== 'all' && BR.data?.latest ? 'None of this kind is numbered here.'
    : 'Nothing is numbered here yet. A memory, a message or a ticket written here takes the next number.';
  fill(list, rows.length ? rows : h('li', {class: 'empty'}, none),
    BR.cursor !== null ? h('li', {}, h('button', {class: 'btn sm quiet more', type: 'button',
      title: 'List the next items, older than these', onclick: olderItems}, 'Older')) : null);
}
/* One item in the list: its number, title and kind, unseen when numbered since this browser last showed the node, its
 * why, and opened, what it holds. */
function itemRow(item) {
  const open = BR.open === item.item, fresh = BR.seen !== null && item.number > BR.seen;
  const id = `item-${item.number}`;
  return h('li', {class: 'itemrow' + (fresh ? ' new' : '') + (open ? ' open' : '')},
    h('button', {class: 'itemhead', type: 'button', 'aria-expanded': String(open), 'aria-controls': open ? id : null,
      onclick: () => openItem(item.item)},
    h('span', {class: 'num'}, hex(item.number)), h('span', {class: 'title'}, item.title || 'untitled'),
    h('span', {class: `pill kind-${item.kind}`}, item.kind),
    fresh ? h('span', {class: 'pill fresh', title: 'Numbered since this browser last showed you this node'}, 'unseen')
      : null),
    item.why ? h('p', {class: 'why'}, h('span', {class: 'k'}, 'why '), item.why) : null,
    open ? h('div', {class: 'itemopen', id}, itemDetail(item.item)) : null);
}
async function olderItems() {
  const address = BR.address, kind = BR.kind;
  if (BR.cursor === null) return;
  let data;
  try { data = await read('brief', {address, cursor: BR.cursor, ...kindAsked()}); }
  catch (error) { return toast(error.message); }
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
  try { data = await read('brief', {address, ...kindAsked()}); }
  catch (error) { list.removeAttribute('aria-busy'); return toast(error.message); }
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
    try { BR.cache.set(ref, await read('item', {item: ref})); }
    catch (error) { BR.cache.set(ref, {error: error.message}); }
    if (BR.open === ref) drawItems();
  }
  $('#p-brief .itemrow.open')?.scrollIntoView({block: 'nearest'});
}
function itemDetail(ref) {
  const found = BR.cache.get(ref);
  if (!found) return h('p', {class: 'loading'}, 'Reading the item…');
  if (found.error) return h('p', {class: 'empty'}, found.error);
  const links = (found.links || []).map(itemLink);
  return [
    found.body ? h('pre', {class: 'itemtext', tabindex: '0', 'aria-label': `What ${ref} holds`}, found.body) : null,
    links.length ? h('div', {class: 'eyebrow'}, 'Links') : null, links.length ? h('ul', {class: 'links'}, links) : null,
    h('details', {class: 'sent'}, h('summary', {}, `As an agent reads metaform://${ref}`),
      h('pre', {class: 'brieftext raw', tabindex: '0', 'aria-label': `${ref} exactly as an agent reads it`},
        found.text),
      briefCopy(`${ref} as an agent reads it`, found.text))];
}
/* A link of an item, its address#n opening that item. */
function itemLink(link) {
  const match = ITEM_REF.exec(String(link));
  if (!match) return h('li', {}, String(link));
  const [whole, address] = match;
  const before = String(link).slice(0, match.index), after = String(link).slice(match.index + whole.length);
  const follow = event => { event.preventDefault(); walkTo(`${address}#${match[2].toLowerCase()}`); };
  return h('li', {}, before, h('a', {class: 'link addr', href: '#', title: `Open ${whole}`, onclick: follow}, whole),
    after);
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
