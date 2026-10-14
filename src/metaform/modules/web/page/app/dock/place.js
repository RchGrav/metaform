/* Where the dock stands: its corner, sides and floating place and size, moved by its head and sized by its edges. */
import '/page/app/dock/send.js';  // the part before runs first, so the parts run in the page's order
import {$, reduced, h} from '/page/app/core/dom.js';
import {foldHeader} from '/page/app/header/menus.js';
import {durFor} from '/page/app/camera/fly3d.js';
import {DOCKMOTION, dockState} from '/page/app/dock/embody.js';
import {dockCurve} from '/page/app/dock/helpdesk.js';
import {chatDocked} from '/page/app/workspace/workspace.js';

/* Where the dock stands: in the corner at its first size; docked at the left or the right of the page, which makes
 * room for it, as wide as its inner edge is dragged; or floating where its head was dragged, VIEW-048, at the size its
 * edges and corners were dragged to. It is kept wholly on the screen and settles gently against an edge it is let go
 * near; let go with the pointer at the page's very side it docks there. The head's Dock button docks it at the right,
 * and from a side puts it back in the corner; a double-click on the head puts it back in the corner at its first
 * size. Its place and size are kept in this browser. On a narrow screen it is always the sheet at the bottom. */
export const DOCK_PLACE = 'metaform.dock', DOCK_BOX = 'metaform.dockBox';
const DOCK_MIN = {width: 340, height: 360}, DOCK_EDGE = 12, DOCK_SNAP = 28;
export const narrowPage = () => matchMedia('(max-width: 820px)').matches;
function keptBox() {
  try { return JSON.parse(localStorage.getItem(DOCK_BOX) || 'null'); } catch { return null; }
}
/* A floating place and size, inside the window: never larger than it, never past its edges. */
function fitBox({left, top, width, height}) {
  width = Math.round(Math.max(DOCK_MIN.width, Math.min(width, innerWidth - 2 * DOCK_EDGE)));
  height = Math.round(Math.max(DOCK_MIN.height, Math.min(height, innerHeight - 2 * DOCK_EDGE)));
  left = Math.round(Math.max(0, Math.min(left, innerWidth - width)));
  top = Math.round(Math.max(0, Math.min(top, innerHeight - height)));
  return {left, top, width, height};
}
export function setBox(given, keep = true) {
  const box = $('#helpdesk'), fitted = fitBox(given);
  for (const side of ['left', 'top', 'width', 'height']) box.style[side] = `${fitted[side]}px`;
  box.style.transform = '';
  if (keep) {
    try { localStorage.setItem(DOCK_BOX, JSON.stringify(fitted)); } catch { /* storage can be blocked */ }
  }
  return fitted;
}
export function placeDock(place, keep = true) {
  const box = $('#helpdesk');
  place = ['corner', 'left', 'right', 'float'].includes(place) ? place : 'corner';
  $('#dock').dataset.place = place;
  if (place !== 'float') for (const side of ['left', 'top', 'width', 'height', 'transform']) box.style[side] = '';
  else if (!box.style.left) {  // floating again where the person last put it, at the size they gave it
    const now = box.getBoundingClientRect();
    const first = {left: innerWidth - now.width - 24, top: 80, width: now.width || 460, height: now.height || 640};
    setBox(keptBox() || first, false);
  }
  if (keep) {
    try { localStorage.setItem(DOCK_PLACE, place); } catch { /* storage can be blocked; it opens in the corner */ }
  }
  const side = place === 'left' || place === 'right', button = $('#helpdesk .place');
  button.title = side ? 'Put the chat back in the corner' : 'Dock the chat at the side of the page';
  button.setAttribute('aria-label', button.title);
  button.setAttribute('aria-pressed', String(side));
  dockLayout();
}
/* A dock at a side takes its width from the page while the chat is open, so the maps are never under it. */
export function dockLayout() {
  const place = $('#dock').dataset.place, open = $('#dock').className === 'open' && !narrowPage();
  $('.app').classList.toggle('docked-left', open && place === 'left');
  $('.app').classList.toggle('docked-right', open && place === 'right');
  foldHeader();  // the header's row is narrower beside a docked chat, and folds when it no longer holds everything
}
$('#helpdesk .place').onclick = () => {
  placeDock(['left', 'right'].includes($('#dock').dataset.place) ? 'corner' : 'right');
};
/* A change of place shown as motion: the chat drawn where it now is, eased there from where it was by a transform
 * alone, on the arriving curve. */
function settleFrom(before) {
  const box = $('#helpdesk'), after = box.getBoundingClientRect();
  if (reduced() || !before || box.hidden) return;
  const dx = before.left - after.left, dy = before.top - after.top;
  const sx = before.width / after.width, sy = before.height / after.height;
  if (Math.abs(dx) < 1 && Math.abs(dy) < 1 && Math.abs(sx - 1) < 0.01 && Math.abs(sy - 1) < 0.01) return;
  box.animate([{transformOrigin: '0 0', transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})`},
    {transformOrigin: '0 0', transform: 'none'}], {duration: durFor(Math.hypot(dx, dy)), easing: dockCurve('arrive')});
}
const dockMovable = () => !narrowPage() && !chatDocked() && $('#dock').className === 'open' && !DOCKMOTION.anim;
/* A press followed until it lets go, however it ends: `move` on each move, `done` once with the last event. */
function follow(move, done) {
  const end = last => {
    removeEventListener('pointermove', move);
    removeEventListener('pointerup', end);
    removeEventListener('pointercancel', end);
    done(last);
  };
  addEventListener('pointermove', move);
  addEventListener('pointerup', end);
  addEventListener('pointercancel', end);
}
/* The head moves it: a press that moves more than a few pixels takes it, a click leaves it where it is. Off a side it
 * floats at its floating size, still under the pointer; let go at the page's very side it docks there, and near an
 * edge it settles against it. */
function dragDock(event) {
  if (event.button || !dockMovable()) return;
  if (event.target.closest('button, input, select, textarea, a, [role=button]')) return;
  const box = $('#helpdesk'), at = [event.clientX, event.clientY];
  let grip = null, size = null;
  const move = moved => {
    if (!grip) {
      if (Math.hypot(moved.clientX - at[0], moved.clientY - at[1]) < 4) return;
      const from = box.getBoundingClientRect(), side = ['left', 'right'].includes($('#dock').dataset.place);
      const kept = keptBox();
      size = side
        ? {width: kept?.width || Math.min(from.width, 520), height: kept?.height || Math.min(from.height, 680)}
        : {width: from.width, height: from.height};
      grip = [Math.min(at[0] - from.left, size.width - 48), Math.min(at[1] - from.top, 40)];
      $('#dock').dataset.place = 'float';
      box.classList.add('dragging');
      dockLayout();
    }
    setBox({left: moved.clientX - grip[0], top: moved.clientY - grip[1], ...size}, false);
  };
  const done = last => {
    box.classList.remove('dragging');
    if (!grip) return;
    if (last.clientX >= innerWidth - 8 || last.clientX <= 8) return placeDock(last.clientX <= 8 ? 'left' : 'right');
    const before = box.getBoundingClientRect();
    setBox(snapped(before));
    placeDock('float');
    settleFrom(before);
  };
  follow(move, done);
  event.preventDefault();
}
/* A floating place near an edge settled against it, a small margin in. */
function snapped(before) {
  const near = {...fitBox(before)};
  if (near.left < DOCK_SNAP) near.left = DOCK_EDGE;
  if (near.top < DOCK_SNAP) near.top = DOCK_EDGE;
  if (innerWidth - (near.left + near.width) < DOCK_SNAP) near.left = innerWidth - near.width - DOCK_EDGE;
  if (innerHeight - (near.top + near.height) < DOCK_SNAP) near.top = innerHeight - near.height - DOCK_EDGE;
  return near;
}
$('#helpdesk .head').addEventListener('pointerdown', dragDock);
/* Back to the corner at its first size, from wherever it is: a double-click on the head. */
export function resetDock() {
  if (narrowPage() || chatDocked()) return;
  const before = $('#helpdesk').getBoundingClientRect();
  try { localStorage.removeItem(DOCK_BOX); } catch { /* storage can be blocked */ }
  if ($('#dock').className === 'open big') dockState('open');
  placeDock('corner');
  settleFrom(before);
}
$('#helpdesk .head').addEventListener('dblclick', event => {
  if (!event.target.closest('button, [role=button]')) resetDock();
});
/* Every edge and corner sizes it, floating or in its corner; in the corner it floats from where it stands. */
function sizeFrom(edge, event) {
  if (event.button || !dockMovable() || ['left', 'right'].includes($('#dock').dataset.place)) return;
  event.preventDefault();
  event.stopPropagation();
  const box = $('#helpdesk'), start = box.getBoundingClientRect(), at = [event.clientX, event.clientY];
  $('#dock').dataset.place = 'float';
  setBox(start, false);
  box.classList.add('sizing');
  const move = moved => setBox(sizedBox(edge, start, moved.clientX - at[0], moved.clientY - at[1]), false);
  follow(move, () => {
    box.classList.remove('sizing');
    setBox(box.getBoundingClientRect());
    placeDock('float');
  });
}
/* The box dragged by an edge or corner, its far sides where they were, never smaller than DOCK_MIN. */
function sizedBox(edge, start, dx, dy) {
  let {left, top, width, height} = start;
  if (edge.includes('e')) width = Math.min(start.width + dx, innerWidth - start.left);
  if (edge.includes('s')) height = Math.min(start.height + dy, innerHeight - start.top);
  if (edge.includes('w')) {
    left = Math.max(0, Math.min(start.left + dx, start.right - DOCK_MIN.width));
    width = start.right - left;
  }
  if (edge.includes('n')) {
    top = Math.max(0, Math.min(start.top + dy, start.bottom - DOCK_MIN.height));
    height = start.bottom - top;
  }
  return {left, top, width: Math.max(DOCK_MIN.width, width), height: Math.max(DOCK_MIN.height, height)};
}
for (const edge of ['n', 'e', 's', 'w', 'ne', 'nw', 'se', 'sw']) {
  const grip = h('div', {class: `grip grip-${edge}`, 'data-edge': edge, 'aria-hidden': 'true'});
  $('#helpdesk').append(grip);
  grip.addEventListener('pointerdown', event => sizeFrom(edge, event));
}
/* A smaller window keeps the floating chat whole and on it. */
function keepDockOnScreen() {
  if ($('#dock').dataset.place === 'float' && $('#helpdesk').style.left && !$('#helpdesk').hidden && !DOCKMOTION.anim) {
    setBox($('#helpdesk').getBoundingClientRect(), false);
  }
  dockLayout();
}
addEventListener('resize', keepDockOnScreen);
try { placeDock(localStorage.getItem(DOCK_PLACE), false); } catch { placeDock('corner', false); }
/* Near the sliver it lifts enough to click; away, it settles back. */
function liftTab(event) {
  const dock = $('#dock');
  if (dock.className.startsWith('open')) return;
  const box = $('#dockTab').getBoundingClientRect();
  const away = Math.hypot(Math.max(box.left - event.clientX, 0, event.clientX - box.right),
                          Math.max(box.top - event.clientY, 0, event.clientY - box.bottom));
  const state = away < 60 ? 'near' : 'resting';
  if (dock.className !== state) dock.className = state;
}
document.addEventListener('pointermove', liftTab);
