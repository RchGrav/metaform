/* The localized view of an element: what an agent assigned to it receives, drawn small in the panel. */
import {$, h, fill} from '/page/app/core/dom.js';
import {S, read} from '/page/app/core/reads.js';
import {select} from '/page/app/selection/select.js';

/* The picture is drawn from the `project` tool's own answer at the element's address, `/api/local-view`, so it shows
 * exactly what an agent working there is given: on the left the elements that want this one, in the middle the
 * element, on the right what it wants, each want's line pointing the way its information goes (send, receive or
 * both), with the why and the how on hover; under it the overlays that hold records here. A name selects its element. */
const NS = 'http://www.w3.org/2000/svg';
const ROW = 20, WIDE = 320, MID = 160, BOX = 22, NAME = 18;
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

export async function renderLocalView(id) {
  const box = $('#localview');
  if (!box) return;
  let found = null;
  try { found = await read('local-view', {address: id}); } catch { found = null; }
  if (S.selected !== id || !box.isConnected) return;  // another part was chosen meanwhile
  if (!found) { box.hidden = true; return; }
  const {lead, answer} = found;
  const wants = (answer.wants || []).map(want => ({...want, id: named(lead, String(want.element))}));
  const wantedBy = (answer.wanted_by || []).map(address => named(lead, String(address)));
  const rows = Math.max(wants.length, wantedBy.length, 1);
  const high = rows * ROW + 8, middle = high / 2;
  const at = (count, index) => middle + (index - (count - 1) / 2) * ROW;
  const link = (x1, y1, x2, y2, start, end, title) => svg('line', {class: 'lv-line', x1, y1, x2, y2,
    'marker-start': start ? 'url(#lv-arrow)' : null, 'marker-end': end ? 'url(#lv-arrow)' : null},
  title ? svg('title', {}, title) : null);
  const label = (id, x, y, anchor, title) => {
    const text = svg('text', {class: 'lv-name', x, y: y + 4, 'text-anchor': anchor, tabindex: 0, role: 'button'},
      cut(nameOf(id)), svg('title', {}, title));
    text.addEventListener('click', () => select(id, true));
    text.addEventListener('keydown', event => { if (event.key === 'Enter') select(id, true); });
    return text;
  };
  const picture = svg('svg', {class: 'lv-map', viewBox: `0 0 ${WIDE} ${high}`, role: 'img',
    'aria-label': `${nameOf(id)}: wanted by ${wantedBy.length}, wants ${wants.length}`},
  svg('defs', {}, svg('marker', {id: 'lv-arrow', viewBox: '0 0 8 8', refX: 7, refY: 4, markerWidth: 6, markerHeight: 6,
    orient: 'auto-start-reverse'}, svg('path', {d: 'M0,0 L8,4 L0,8 z', class: 'lv-head'}))),
  wantedBy.map((one, index) => {
    const y = at(wantedBy.length, index);
    return [link(MID - 52, y, MID - BOX, middle, false, false, `${nameOf(one)} wants ${nameOf(id)}`),
      label(one, MID - 56, y, 'end', `${nameOf(one)} wants this element`)];
  }),
  wants.map((want, index) => {
    const y = at(wants.length, index), way = String(want.direction || '');
    const said = [want.why, want.how && `how: ${want.how}`, way && `information: ${way}`].filter(Boolean).join('\n');
    return [link(MID + BOX, middle, MID + 52, y, way === 'receive' || way === 'both', way === 'send' || way === 'both',
      said), label(want.id, MID + 56, y, 'start', said)];
  }),
  // the element itself, named by the panel's heading above
  svg('rect', {class: 'lv-self', x: MID - BOX, y: middle - 9, width: BOX * 2, height: 18, rx: 4},
    svg('title', {}, nameOf(id))));
  const overlays = answer.overlays || [];
  fill(box, h('div', {class: 'eyebrow'}, 'What an agent assigned here receives'),
    h('p', {class: 'hint'}, `Wanted by ${wantedBy.length} · wants ${wants.length}`
      + (overlays.length ? ' · overlays here:' : ''), overlays.map(key => h('span', {class: 'pill'}, key))),
    picture);
  box.hidden = false;
}
