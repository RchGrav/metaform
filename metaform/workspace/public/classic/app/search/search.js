/* Search: find a part, a join or what a layer holds, and go to it. */
import '/classic/app/panel/object.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/classic/app/core/dom.js';
import {overlay, closed} from '/classic/app/core/overlays.js';
import {S} from '/classic/app/core/reads.js';
import {colorVar} from '/classic/app/header/layers.js';
import {labelOf, nameOf} from '/classic/app/map2d/inside.js';
import {flowArrow} from '/classic/app/map2d/flow2d.js';
import {select} from '/classic/app/selection/select.js';
import {itemText} from '/classic/app/panel/object.js';
import {searchRecords} from '/classic/app/adapter.js';

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
/* The eight best parts and the eight best joins drawn, each by its name, where it is, and how well it matched. */
function searchParts(query) {
  const parts = [...S.elements.values()].map(({element}) => ({key: element.id, kind: 'Part', name: labelOf(element),
    where: element.address, layer: element.layer,
    score: matchScore(query, [labelOf(element), element.short_name, element.address])}));
  const joins = S.joins.map(join => foundJoin(join, query));
  const best = list => list.filter(one => one.score > 0)
    .sort((one, two) => two.score - one.score || one.name.localeCompare(two.name)).slice(0, 8);
  return [...best(parts), ...best(joins)];
}
/* A join is found by its purpose, its function, and the parts it joins. */
function foundJoin(join, query) {
  const receiver = S.elements.get(join.receiver)?.element, provider = S.elements.get(join.provider)?.element;
  const ends = `${receiver ? labelOf(receiver) : join.receiver_address} ${flowArrow(join)} `
    + `${provider ? labelOf(provider) : join.provider_address || ''}`;
  return {key: 'p:' + join.id, kind: 'Join', name: join.purpose || ends, where: ends, layer: join.layer,
    score: matchScore(query, [join.purpose, join.ef, ends])};
}
/* A name with the words that matched marked, built as text, never as markup. */
function marked(text, query) {
  const wanted = wordsOf(query);
  const parts = String(text).split(/([^\p{L}\p{N}]+)/u);
  const matched = part => wanted.some(word => part.toLowerCase().startsWith(word)) && part;
  return parts.map(part => matched(part) ? h('mark', {}, part) : part);
}
function drawSearch(query) {
  const box = $('#searchResults'), input = $('#search .query');
  const results = SEARCH.results = [...searchParts(query), ...SEARCH.items];
  SEARCH.active = results.length ? Math.min(Math.max(SEARCH.active, 0), results.length - 1) : -1;
  const groups = ['Part', 'Join', 'Item'].map(kind =>
    [kind, results.map((one, index) => [one, index]).filter(([one]) => one.kind === kind)]);
  const nothing = SEARCH.pending ? 'Searching the layers…' : `Nothing in view matches ${query.trim()}.`;
  fill(box, !query.trim() ? h('p', {class: 'empty'}, 'Type a name, an address or words of a why.')
    : !results.length ? h('p', {class: SEARCH.pending ? 'loading' : 'empty'}, nothing)
    : groups.filter(([, found]) => found.length).map(([kind, found]) => [
      h('div', {class: 'group', role: 'presentation'}, GROUP_TITLES[kind]),
      found.map(([one, index]) => foundRow(one, index, query))]));
  paintSearch();
  input.setAttribute('aria-expanded', String(results.length > 0));
}
const GROUP_TITLES = {Part: 'Parts', Join: 'Relies on', Item: 'In the layers'};
const KIND_SAID = {Part: 'Part', Join: 'Relies on', Item: 'Record'};
/* One result, its matched words marked; the pointer over it makes it the active one, and a click chooses it. */
function foundRow(one, index, query) {
  const point = () => { if (SEARCH.active !== index) { SEARCH.active = index; paintSearch(); } };
  return h('div', {role: 'option', id: `found${index}`, 'aria-selected': String(index === SEARCH.active),
    style: {'--c': `var(${colorVar(one.layer)})`}, onpointermove: point, onclick: () => chooseFound(index)},
  h('i'), h('span', {class: 'name'}, ...marked(one.name, query)),
  h('span', {class: 'where'}, one.where), h('span', {class: 'kind'}, KIND_SAID[one.kind]));
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
  SEARCH.pending = Boolean(query.trim());
  if (!SEARCH.pending) return;
  SEARCH.timer = setTimeout(() => readItems(query, generation), 180);
}
async function readItems(query, generation) {
  let found = [];
  found = searchRecords(query, 8);  // the layers' records, from the map already on the page, adapter.js
  if (generation !== SEARCH.generation) return;
  SEARCH.pending = false;
  SEARCH.items = found.map(foundItem).filter(one => one.key);
  drawSearch($('#search .query').value);
}
/* An item found goes to itself where it is drawn, else to the node or join it is at. */
function foundItem(item) {
  const at = item.target ? (item.target.kind === 'join' ? 'p:' + item.target.id : item.target.id) : null;
  const drawn = S.items.has('i:' + item.id) ? 'i:' + item.id : null;
  return {key: drawn || at, kind: 'Item', name: itemText(item.value).split('\n')[0].slice(0, 140) || item.id,
    where: `${item.layer}${at ? ' · at ' + nameOf(at, at) : ''}`, layer: item.layer};
}
function chooseFound(index) {
  const one = SEARCH.results[index];
  if (!one) return;
  $('#search').hidden = true;
  closed($('#search'));  // closed now, so the selection below finds the focus out of it and gives it to the map
  select(one.key, true);
}
export function openSearch() {
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
function typed(event) {
  SEARCH.active = 0;
  searchItems(event.target.value);
  drawSearch(event.target.value);
}
/* The arrows move through the results, round from the last to the first, and Enter chooses the active one. */
function searchKeys(event) {
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
}
$('#search .query').addEventListener('input', typed);
$('#search .query').addEventListener('keydown', searchKeys);
