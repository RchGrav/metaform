/* Provenance, from the Provenance tab of the earlier page's panel/agentview.js. The earlier tab said how a layer was
 * made, from the server's record of the workflow and the prompt that wrote it. The new map records where an element
 * comes from on the element itself: its source reference, and its records of the `sources` layer and the `review`
 * layer. So this tab says those for the selected element, in the earlier tab's form: a heading, then one list of
 * facts. */
import '/classic/app/panel/brief.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/classic/app/core/dom.js';
import {S} from '/classic/app/core/reads.js';
import {colorVar, layerOn} from '/classic/app/header/layers.js';
import {joinOf} from '/classic/app/graph/data.js';
import {labelOf} from '/classic/app/map2d/inside.js';

/* ---------- provenance ---------- */
const PROV_LAYERS = ['sources', 'review'];
const said = value => value === true ? 'yes' : value === false ? 'no'
  : value && typeof value === 'object' ? JSON.stringify(value) : String(value);
const filled = value => value !== null && value !== undefined && value !== ''
  && !(Array.isArray(value) && !value.length);
/* One record of a layer as a list of its facts, empty fields left out; a record that is a text alone is that text. */
function recordFacts(layer, record) {
  const facts = record && typeof record === 'object' && !Array.isArray(record)
    ? h('dl', {class: 'prov'}, Object.entries(record).filter(([, value]) => filled(value))
      .flatMap(([key, value]) => [h('dt', {}, key), h('dd', {}, said(value))]))
    : h('p', {class: 'itemtext'}, said(record));
  return h('div', {class: 'item', style: {'--c': `var(${colorVar(layer)})`}}, facts);
}
export function renderProv() {
  const pane = $('#p-prov'), id = S.selected;
  const join = id?.startsWith('p:') ? joinOf(id) : null;
  const element = S.elements.get(join ? join.receiver : id)?.element;
  if (!element) {
    return fill(pane, h('p', {class: 'empty'},
      'Select an element on the map to read its provenance: its source reference, its sources and its reviews.'));
  }
  // One list of facts for the element, so every label lines up.
  const facts = h('dl', {class: 'prov'}, ...[['address', element.address], ['technical name', element.short_name],
    ['source reference', element.uri || 'not recorded']].filter(([, value]) => value)
    .flatMap(([key, value]) => [h('dt', {}, key), h('dd', {}, value)]));
  fill(pane, h('div', {class: 'eyebrow'}, 'Where it comes from'), h('h2', {}, labelOf(element)),
    join ? h('p', {class: 'hint'}, 'A line has no records of its own, so this is the provenance of the element that '
      + 'holds it.') : null,
    facts);
  let held = 0;
  for (const layer of PROV_LAYERS) {
    const records = element.records[layer] || [];
    if (!records.length) continue;
    held++;
    const title = S.layers.find(one => one.name === layer)?.title || layer;
    pane.append(h('div', {class: 'eyebrow'}, `${title} · ${records.length}`));
    if (!layerOn(layer)) {
      pane.append(h('p', {class: 'empty'}, `The ${layer} layer is unchecked in Layers, so its records are hidden.`));
    } else pane.append(...records.map(record => recordFacts(layer, record)));
  }
  if (!held) {
    pane.append(h('p', {class: 'empty'}, 'This element holds no record of the sources layer or the review layer.'));
  }
}
