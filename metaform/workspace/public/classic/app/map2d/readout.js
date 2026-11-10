/* The hover readout across the top of the map's window, what it says for a node, an edge or a figure, and the detail
 * card at the lower left. */
import '/classic/app/graph/data.js';  // the part before runs first, so the parts run in the page's order
import {$, reduced, h, fill} from '/classic/app/core/dom.js';
import {S} from '/classic/app/core/reads.js';
import {joinOf} from '/classic/app/graph/data.js';
import {VIEW} from '/classic/app/views/settings.js';
import {M} from '/classic/app/map2d/build.js';
import {labelOf} from '/classic/app/map2d/inside.js';
import {directionWord} from '/classic/app/adapter.js';

/* ---------- the hover readout: what the pointer is on, said across the top of the map's window ----------
 * Over anything a click picks, a node, a join's edge by the nearest-edge choice, a purpose vertex, an agent's figure
 * or a memory, the cursor is a pointing finger and the readout at the top of that map's window says what it is: its
 * name, its kind and its address, and for an edge the receiver → provider with the join's purpose. It eases in on
 * hover and fades a moment after the pointer leaves; it lies over the map, takes no room and no click, so nothing
 * jumps. Its text grows with the window between a floor and a ceiling, wraps to three lines at most and ends with an
 * ellipsis; in the small pane it is one line. It is #tip3d in the 3D map and #tip2d in the 2D one. */
/* It holds steady: a name shows once what the pointer is on has stayed the same for `settle` ms, stays `stay` ms after
 * the pointer leaves it before it fades, and a new name takes the place of one on view by crossfading in place. It is
 * decided when the pointer moves and when the camera comes to rest, `rehover3d`, never frame by frame, so the camera's
 * motion, ultra's quality steps and a sign's occlusion changing under a still pointer never toggle it. */
const READOUT = {timers: {}, now: {}, want: {}, settle: 120, stay: 400};
export function readoutBox(which) {
  let box = $('#tip2d');
  if (!box) {
    box = h('div', {id: 'tip2d', class: 'readout', role: 'status', 'aria-live': 'polite', hidden: true});
    $('#map2d').append(box);
  }
  return box;
}
/* What the pointer is on, said in two places: its name across the top, only where the map shows none that can be read,
 * `top`, and its details in the card at the lower left, `card`, for anything a click picks. `info` null: nothing. */
export function readout(which, info) {
  const hovering = Boolean(info), shows = VIEW.hoverInfo || 'name+summary';  // web_hover_info
  const parts = shows === 'summary' || shows === 'off' ? null : Array.isArray(info) ? info : info?.top || null;
  hoverCard(which, shows === 'name' || shows === 'off' || Array.isArray(info) ? null : info?.card || null);
  const box = readoutBox(which);
  if (!box) return;
  box.classList.add('readout');
  const host = $('#viewport');
  host?.classList.toggle('pickable', hovering);
  const key = parts ? JSON.stringify(parts.map(part => part?.textContent ?? part)) : null;  // a part left out is null
  if (key === READOUT.want[which]) return;  // the same as asked already: its timer runs on
  READOUT.want[which] = key;
  clearTimeout(READOUT.timers[which]);
  if (!parts) {  // gone: kept a moment, then faded and put away
    if (READOUT.now[which] === null) return;
    READOUT.timers[which] = setTimeout(() => fadeReadout(which, box), reduced() ? 0 : READOUT.stay);
    return;
  }
  if (READOUT.now[which] === key) { box.classList.add('on'); return; }  // back to the name on view before it went
  READOUT.timers[which] = setTimeout(() => showReadout(which, box, parts, key), reduced() ? 0 : READOUT.settle);
}
function fadeReadout(which, box) {
  READOUT.now[which] = null;
  box.classList.remove('on');
  const putAway = () => { if (!box.classList.contains('on')) box.hidden = true; };
  READOUT.timers[which] = setTimeout(putAway, reduced() ? 0 : 400);
}
/* A name shown: in place of one on view, the old fading out over the new; else eased in from where it stands away. */
function showReadout(which, box, parts, key) {
  const said = h('span', {class: 'said'}, h('span', {class: 'line'}, parts));
  const showing = box.classList.contains('on') && !box.hidden && READOUT.now[which];
  READOUT.now[which] = key;
  if (showing && !reduced()) {
    for (const old of box.querySelectorAll('.said')) {
      old.classList.add('leaving');
      setTimeout(() => old.remove(), 220);
    }
    said.classList.add('arriving');
    box.append(said);
  } else fill(box, said);
  box.hidden = false;
  void box.offsetWidth;  // from where it stands away, so it eases in
  box.classList.add('on');
}
/* What the readout says, the name alone, and only where the map shows no name that can be read: for an edge, which
 * has no label of its own, the names it joins, receiver → provider; for a node, only while its own label is drawn
 * smaller than READABLE CSS pixels on the screen, as a far one is, perspective alone sizing it, or not drawn at all,
 * as when the labels are hidden; for an agent's
 * figure, its agent's name. A node whose name can be read gets the finger and its highlight, and no readout. */
const READABLE = 11;
function labelReadable(id, which) {
  return readable2d(id);
}
/* A 2D label drawn and shown, its text at least READABLE pixels tall on the screen. */
function readable2d(id) {
  const g = M.nodes.get(id)?.g, label = g?.querySelector('.nodeLabel, text');
  if (!label || !label.getBoundingClientRect().height || getComputedStyle(label).visibility === 'hidden') return false;
  return parseFloat(getComputedStyle(label).fontSize) * Math.abs(g.getScreenCTM()?.a || 0) >= READABLE;
}
/* The readout of a node of either map, by its id, or of a 3D graph node: null where its own name can be read. */
export function readoutOf(node, which = '3d') {
  const id = typeof node === 'string' ? node : node.id, given = typeof node === 'object';
  const purpose = given && node.t === 'purpose' ? S.joins.find(one => one.id === node.join) : null;
  const join = id.startsWith('p:') ? joinOf(id) : purpose;
  if (join) return edgeWords(join);
  const entry = S.elements.get(id);
  if (entry) return elementWords(id, entry.element, labelReadable(id, which));
  const name = (given && node.name) || id;
  return {top: [h('b', {}, name)], card: {title: name, kind: 'node'}};
}
/* An element's readout: its name on top unless its own label can be read, and its card with what it does, or else
 * what it needs, and its open work. */
function elementWords(id, element, readable) {
  const serves = S.joins.find(one => one.providers.includes(id) && (one.ef || one.purpose));
  const holds = S.joins.find(one => one.receiver === id && one.purpose);
  return {top: readable ? null : [h('b', {}, labelOf(element))], card: {title: labelOf(element),
    kind: ['element', element.role, element.address?.split('.')[0]].filter(Boolean).join(' · '),
    address: element.address, text: serves ? (serves.ef || serves.purpose) : holds ? `Needs: ${holds.purpose}` : '',
    work: (element.open_work || []).join(' · ')}};
}
export function edgeWords(join) {
  const named = item => S.elements.has(item) ? labelOf(S.elements.get(item).element) : item;
  const from = named(join.receiver) || join.receiver_address || '';
  const ends = `${from} → ${join.providers.map(named).join(', ') || join.provider_address || ''}`;
  return {top: [h('b', {}, ends)], card: {title: ends, kind: ['relies on', directionWord(join)].filter(Boolean).join(' · '),
    address: join.receiver_address || '', text: join.purpose || '', more: join.ef || ''}};
}
/* The detail card at the lower left of the map's window, in the legend's corner, the legend easing out while it shows:
 * the name as its title, a quiet line of its kind and role, the address in mono, its purpose or EF in a line or two,
 * for an edge the join's purpose, and for an agent what it works on and its status. It eases in for anything hovered
 * and fades a moment after; it sits above the map's count and clear of the legend, takes no click, and in the small
 * pane is its title and one line. */
const CARD = {timers: {}, now: {}};
function cardBox(which) {
  const id = 'card2d';
  let box = document.getElementById(id);
  if (!box) {
    box = h('div', {id, class: 'hovercard', role: 'status', 'aria-live': 'polite', hidden: true});
    $('#map2d')?.append(box);
  }
  return box;
}
function hoverCard(which, card) {
  const box = cardBox(which);
  if (!box) return;
  clearTimeout(CARD.timers[which]);
  if (!card) {
    CARD.now[which] = null;
    box.classList.remove('on');
    const putAway = () => { if (!box.classList.contains('on')) box.hidden = true; };
    CARD.timers[which] = setTimeout(putAway, reduced() ? 0 : 900);
    return;
  }
  const key = JSON.stringify([card.title, card.kind, card.address, card.text, card.more, card.work]);
  if (CARD.now[which] !== key) {
    CARD.now[which] = key;
    fill(box, cardBody(card));
  }
  box.hidden = false;
  void box.offsetWidth;  // from where it stands away, so it eases in
  box.classList.add('on');
}
/* A card's lines; no title: the name is said once, at the top left where the map shows none to read, or on its own
 * sign. */
function cardBody(card) {
  const kind = card.kind ? h('div', {class: 'kind'}, card.kind) : null;
  return [kind, card.address ? h('code', {class: 'address'}, card.address) : null,
    card.text ? h('p', {class: 'text'}, card.text) : null,
    card.more && card.more !== card.text ? h('p', {class: 'more'}, card.more) : null,
    card.work ? h('p', {class: 'work'}, card.work) : null];
}
/* The readout stands across the top of the map's window, not at the node, so nothing follows the node each frame. */
export function placeTip() {}
export const short = (text, most) => text.length > most ? text.slice(0, most - 1) + '…' : text;
/* A node's reach, from the earlier page's map3d/pick3d.js: around its centre a node takes half the distance to the
 * nearest node's centre, at most REACH.most CSS pixels, so a node alone does not take the empty space around it. Where
 * reaches overlap, the node whose centre is nearest the pointer takes it; an edge is picked only where no node
 * reaches, `edgeAt2d`. A neighbour farther than twice the most a reach can be never shortens it, so each node looks
 * only at the cells of a grid around it. */
export const REACH = {most: 60, d2: null};
export function reachOf(list) {  // list: {x, y, r} in CSS pixels, r the node as drawn; sets each one's `reach`
  const cell = 2 * REACH.most, grid = new Map(), at = (x, y) => `${x},${y}`;
  for (const one of list) {
    const key = at(Math.floor(one.x / cell), Math.floor(one.y / cell));
    (grid.get(key) || grid.set(key, []).get(key)).push(one);
  }
  for (const one of list) {
    const cx = Math.floor(one.x / cell), cy = Math.floor(one.y / cell);
    let nearest = Infinity;
    for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) {
      for (const other of grid.get(at(cx + dx, cy + dy)) || []) {
        if (other !== one) nearest = Math.min(nearest, Math.hypot(other.x - one.x, other.y - one.y));
      }
    }
    one.reach = Math.max(one.r, Math.min(nearest / 2, REACH.most));
  }
  return list;
}
