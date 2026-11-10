/* The side column's object, from the earlier page's panel/object.js: the selected element with what it relies on,
 * what relies on it and what the layers hold at it, and a selected line between two elements. The earlier file also
 * held the part's open work, its tickets, its memories and the chat; those are not part of this page. The words are
 * the new map's: relies on, why, how, direction and the four role names. */
import '/classic/app/selection/select.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/classic/app/core/dom.js';
import {S} from '/classic/app/core/reads.js';
import {colorVar} from '/classic/app/header/layers.js';
import {labelOf} from '/classic/app/map2d/inside.js';
import {flowArrow} from '/classic/app/map2d/flow2d.js';
import {select} from '/classic/app/selection/select.js';
import {directionWord, recordsShown} from '/classic/app/adapter.js';

/* A part of the column under one line with its count; it opens as drawn, and a person may fold it. */
function folded(title, count, ...body) {
  return h('details', {class: 'fold', open: true}, h('summary', {}, counted(title, count)), ...body);
}
const counted = (title, count) => (count === null ? title : `${title} · ${count}`);
const pill = text => h('span', {class: 'pill'}, text);
const STATUS_WORDS = {un_built: 'not built'};
export function layerPill(name) {
  return h('span', {class: 'pill layer', style: {'--c': `var(${colorVar(name)})`}}, name);
}
function elementLink(id, address) {
  const entry = S.elements.get(id);
  return h('a', {class: 'link', href: '#', onclick: event => { event.preventDefault(); select(id, true); }},
    entry ? labelOf(entry.element) : address);
}
/* Why, how and direction of one want, each under its word. */
function wantFacts(why, how, direction) {
  return h('dl', {class: 'fields'},
    why ? [h('dt', {}, 'Why'), h('dd', {}, why)] : null,
    how ? [h('dt', {}, 'How'), h('dd', {class: 'fn'}, how)] : null,
    direction ? [h('dt', {}, 'Direction'), h('dd', {}, direction)] : null);
}
/* One want as a card. `side` says which end the card names: `relies` names the element relied on, seen from the
 * element that holds the want; `relied` names the element that holds the want, seen from the one relied on. */
function joinCard(join, side) {
  const other = side === 'relies' ? elementLink(join.provider, join.provider_address)
    : elementLink(join.receiver, join.receiver_address);
  return h('div', {class: 'join'},
    h('div', {class: 'row'},
      h('span', {class: 'dir'}, side === 'relies' ? 'relies on · ' : 'relied on by · ', other),
      h('span', {class: 'lay', style: {'--c': `var(${colorVar(join.layer)})`}}, flowArrow(join))),
    wantFacts(join.purpose, join.ef, directionWord(join)));
}
/* A want whose element this map does not hold: its address as text, with what the want says. */
function looseCard(address, want) {
  return h('div', {class: 'join'},
    h('div', {class: 'row'}, h('span', {class: 'dir'}, 'relies on · ', address),
      h('span', {class: 'lay'}, 'not on this map')),
    wantFacts(want?.why, want?.how, want?.direction));
}
/* An item's value as text: an object as one `field: value` line per field it holds, empty fields left out, so a
 * record reads as fields, not as raw data. */
const filled = value => value !== null && value !== undefined && value !== ''
  && !(Array.isArray(value) && !value.length);
const fieldText = value => value && typeof value === 'object' ? JSON.stringify(value) : String(value);
export function itemText(value) {
  if (Array.isArray(value)) return value.map(fieldText).join('\n');
  if (value && typeof value === 'object') {
    return Object.entries(value).filter(([, each]) => filled(each))
      .map(([key, each]) => `${key}: ${fieldText(each)}`).join('\n');
  }
  return String(value ?? '');
}
/* The same value for the panel: an object as a table of its fields. */
export function itemView(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return itemText(value);
  return h('dl', {class: 'fields'}, Object.entries(value).filter(([, each]) => filled(each))
    .flatMap(([key, each]) => [h('dt', {}, key), h('dd', {}, fieldText(each))]));
}
/* One layer record: a block that has a text, as the specification's blocks have, is its title and its text as text;
 * any other record is its fields. */
function recordView(layer, record) {
  const block = record && typeof record === 'object' && typeof record.text === 'string';
  return h('div', {class: 'item', style: {'--c': `var(${colorVar(layer)})`}},
    block ? [record.title ? h('strong', {class: 'recordtitle'}, record.title) : null,
      h('p', {class: 'itemtext recordtext'}, record.text)] : itemView(record));
}
/* A selected line between two elements shows the want it stands for. */
export function renderJoin(join) {
  const called = id => S.elements.has(id) ? labelOf(S.elements.get(id).element) : null;
  fill($('#p-object'),
    h('div', {class: 'eyebrow'}, 'Relies on'),
    h('h2', {}, `${called(join.receiver) || join.receiver_address} ${flowArrow(join)} `
      + `${called(join.provider) || join.provider_address}`),
    h('p', {class: 'meta'}, elementLink(join.receiver, join.receiver_address), ' relies on ',
      elementLink(join.provider, join.provider_address), '.'),
    joinCard(join, 'relies'));
}
export function renderObject(id) {
  const {element} = S.elements.get(id);
  const held = S.joins.filter(join => join.receiver === id);
  const serves = S.joins.filter(join => join.providers.includes(id));
  const loose = Object.entries(element.wants).filter(([to]) => !S.elements.has(to));
  const layers = recordsShown(element);  // the layers the Layers checklist leaves on
  fill($('#p-object'),
    h('div', {class: 'eyebrow'}, 'Element'),
    h('h2', {}, labelOf(element)),
    h('dl', {class: 'facts'},
      element.short_name ? [h('dt', {}, 'Technical name'), h('dd', {class: 'canonical'}, element.short_name)] : null,
      h('dt', {}, 'Address'), h('dd', {class: 'addr'}, element.address),
      element.uri ? [h('dt', {}, 'Source reference'), h('dd', {class: 'addr'}, element.uri)] : null),
    h('div', {class: 'pills'}, element.role ? pill(element.role) : null,
      element.status ? h('span', {class: 'pill work-unbuilt'}, STATUS_WORDS[element.status] || element.status) : null,
      pill(`relies on ${held.length + loose.length} · relied on by ${serves.length}`)),
    folded('Relies on', held.length + loose.length,
      held.length + loose.length ? [held.map(join => joinCard(join, 'relies')),
        loose.map(([to, want]) => looseCard(to, want))]
        : h('p', {class: 'empty'}, 'This element relies on nothing on this map.')),
    folded('Relied on by', serves.length,
      serves.length ? serves.map(join => joinCard(join, 'relied'))
        : h('p', {class: 'empty'}, 'Nothing on this map relies on this element.')),
    layers.map(([layer, records]) => folded(S.layers.find(one => one.name === layer)?.title || layer, records.length,
      records.map(record => recordView(layer, record)))),
    h('p', {class: 'meta'}, 'Enter, or a second click on the map, goes inside this element. Shift+Enter, or "map" '
      + "in the line at the map's top left, goes back out."));
}
