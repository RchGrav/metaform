/* The localized view of an element: what an agent assigned to it receives, drawn small in the panel, with what it
 * wants and what wants it opened beneath. */
import {$, h, fill} from '/page/app/core/dom.js';
import {S, read} from '/page/app/core/reads.js';
import {colorVar} from '/page/app/header/layers.js';
import {select} from '/page/app/selection/select.js';

/* The section is drawn from the `project` tool's own answer at the element's address, `/api/local-view`, so it shows
 * exactly what an agent working there is given. The picture: on the left the elements that want this one, in the
 * middle the element, on the right what it wants; every line points the way its information goes, and a name selects
 * its element. Under it, Wants and Wanted by each open a list of those elements with which way the information goes,
 * why and how, and for a want the code that makes it. The answer lists what wants this element by address alone, so
 * each of those wants is read from the map the page holds, the same store. */
const NS = 'http://www.w3.org/2000/svg';
const ROW = 20, WIDE = 320, MID = 160, BOX = 16, REACH = 60, NAME = 18;  // REACH: from the middle to a name
const OPEN = {wants: false, wanted: false};  // which lists the person opened, kept as they move from part to part
function svg(tag, props, ...children) {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(props)) if (value !== null && value !== undefined) node.setAttribute(key, value);
  for (const child of children.flat(Infinity)) if (child) node.append(child);
  return node;
}
const named = (lead, address) => address.startsWith(lead) ? address.slice(lead.length) : address;
function nameOf(id) {
  const element = S.elements.get(id)?.element;
  return element?.short_name || element?.name || id.split('.').slice(-2).reverse().join(' ');
}
const cut = text => text.length > NAME ? text.slice(0, NAME - 1) + '…' : text;
// a join's direction in the store's words, as its receiver states it, and the page's words for the same
const WAY = {sends: 'send', receives: 'receive', both: 'both'};
/* Which way a want's information goes, by name: from the element that wants (`wanter`) to the one wanted when it
 * sends, back when it receives, both ways for both. */
const wayText = (wanter, wanted, way) => way === 'send' ? `${wanter} → ${wanted}`
  : way === 'receive' ? `${wanted} → ${wanter}` : way === 'both' ? `${wanter} ↔ ${wanted}` : '';
const goTo = id => event => { event.preventDefault(); select(id, true); };

export async function renderLocalView(id) {
  const box = $('#localview');
  if (!box) return;
  let found = null;
  try { found = await read('local-view', {address: id}); } catch { found = null; }
  if (S.selected !== id || !box.isConnected) return;  // another part was chosen meanwhile
  if (!found) { box.hidden = true; return; }
  const {lead, answer} = found;
  const wants = (answer.wants || []).map(want => ({id: named(lead, String(want.element)), why: want.why,
    how: want.how, way: String(want.direction || ''), ref: want.ref, layer: null}));
  // each element that wants this one, with its want of it: why, how and the way its information goes
  const wantedBy = (answer.wanted_by || []).map(address => {
    const other = named(lead, String(address));
    const join = S.joins.find(one => one.receiver === other && one.providers.includes(id));
    return {id: other, why: join?.purpose, how: join?.ef, way: WAY[join?.ifd] || '', ref: null, layer: join?.layer};
  });
  const overlays = answer.overlays || [];
  fill(box, h('div', {class: 'eyebrow'}, 'What an agent assigned here receives'),
    picture(id, wants, wantedBy),
    list(id, 'wanted', 'Wanted by', wantedBy, 'Nothing wants this element.', true),
    list(id, 'wants', 'Wants', wants, 'This element wants nothing.', false),
    overlays.length ? h('p', {class: 'hint'}, 'Overlays here:', overlays.map(key => h('span', {class: 'pill'}, key)))
      : null);
  box.hidden = false;
}
/* Wants or Wanted by: a button with its count that opens the list, each entry the element by name, which way the
 * information goes from this element's side, why, how, and the code that makes it where the answer gives one. */
function list(id, key, title, entries, none, theirs) {
  const body = h('div', {class: 'lv-list', hidden: !OPEN[key]},
    entries.length ? entries.map(entry => h('div', {class: 'join lv-entry'},
      h('div', {class: 'row'},
        h('a', {href: '#', class: 'lv-go', onclick: goTo(entry.id)}, nameOf(entry.id)),
        entry.way ? h('span', {class: 'lv-way', title: 'Which way its information goes'}, theirs
          ? wayText(nameOf(entry.id), nameOf(id), entry.way) : wayText(nameOf(id), nameOf(entry.id), entry.way))
          : null,
        entry.layer ? h('span', {class: 'lay', style: {'--c': `var(${colorVar(entry.layer)})`}}, entry.layer) : null),
      entry.why ? h('p', {}, entry.why) : null,
      entry.how ? h('p', {class: 'fn'}, entry.how) : null,
      entry.ref ? h('p', {class: 'lv-ref'}, entry.ref) : null))
      : h('p', {class: 'empty'}, none));
  const button = h('button', {class: 'btn sm quiet lv-toggle', type: 'button', 'aria-expanded': String(OPEN[key]),
    onclick: () => {
      OPEN[key] = !OPEN[key];
      body.hidden = !OPEN[key];
      button.setAttribute('aria-expanded', String(OPEN[key]));
    }}, `${title} · ${entries.length}`, h('i', {class: 'i i-chev', 'aria-hidden': 'true'}));
  return h('div', {class: 'lv-part'}, button, body);
}
/* The picture: what wants this element on the left, the element, what it wants on the right. The element is a bar as
 * tall as the rows, so each line runs straight across at its own row and no two arrowheads meet. A line's arrow points
 * the way information goes: toward the element that takes it, both ends for both. */
function picture(id, wants, wantedBy) {
  const rows = Math.max(wants.length, wantedBy.length, 1);
  const high = rows * ROW + 8, middle = high / 2;
  const at = (count, index) => middle + (index - (count - 1) / 2) * ROW;
  const said = entry => [entry.why, entry.how && `how: ${entry.how}`].filter(Boolean).join('\n') || nameOf(entry.id);
  const line = (x1, y1, x2, y2, start, end, title) => svg('line', {class: 'lv-line', x1, y1, x2, y2,
    'marker-start': start ? 'url(#lv-arrow)' : null, 'marker-end': end ? 'url(#lv-arrow)' : null},
  svg('title', {}, title));
  const label = (entry, x, y, anchor) => {
    const text = svg('text', {class: 'lv-name', x, y: y + 4, 'text-anchor': anchor, tabindex: 0, role: 'button'},
      cut(nameOf(entry.id)), svg('title', {}, said(entry)));
    text.addEventListener('click', () => select(entry.id, true));
    text.addEventListener('keydown', event => { if (event.key === 'Enter') select(entry.id, true); });
    return text;
  };
  return svg('svg', {class: 'lv-map', viewBox: `0 0 ${WIDE} ${high}`, role: 'img',
    'aria-label': `${nameOf(id)}: wanted by ${wantedBy.length}, wants ${wants.length}`},
  svg('defs', {}, svg('marker', {id: 'lv-arrow', viewBox: '0 0 8 8', refX: 7, refY: 4, markerWidth: 7, markerHeight: 7,
    orient: 'auto-start-reverse'}, svg('path', {d: 'M0,0 L8,4 L0,8 z', class: 'lv-head'}))),
  // a line runs from the element that wants to the element wanted: its end is the wanted one, its start the wanter
  wantedBy.map((entry, index) => {
    const y = at(wantedBy.length, index);
    return [line(MID - REACH, y, MID - BOX, y, entry.way === 'receive' || entry.way === 'both',
      entry.way === 'send' || entry.way === 'both', said(entry)), label(entry, MID - REACH - 4, y, 'end')];
  }),
  wants.map((entry, index) => {
    const y = at(wants.length, index);
    return [line(MID + BOX, y, MID + REACH, y, entry.way === 'receive' || entry.way === 'both',
      entry.way === 'send' || entry.way === 'both', said(entry)), label(entry, MID + REACH + 4, y, 'start')];
  }),
  svg('rect', {class: 'lv-self', x: MID - BOX, y: at(rows, 0) - 9, width: BOX * 2, height: (rows - 1) * ROW + 18,
    rx: 4}, svg('title', {}, nameOf(id))));
}
