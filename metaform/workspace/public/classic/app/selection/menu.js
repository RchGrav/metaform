/* The menu of a node, opened by a right-click on the map, from `menu` in the earlier page's board/messages.js. The
 * earlier entries were the node's messages, memories, notes, work history, chat, tasks and agents, none of which is
 * part of this page; the entries here are what this page can do with an element. */
import '/classic/app/panel/tabs.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/classic/app/core/dom.js';
import {toast} from '/classic/app/core/controls.js';
import {overlay} from '/classic/app/core/overlays.js';
import {S} from '/classic/app/core/reads.js';
import {IN} from '/classic/app/map2d/inside.js';
import {DEPTH, depthView, toggleDepth, goInside, levelUp} from '/classic/app/keys/walk.js';
import {select} from '/classic/app/selection/select.js';
import {showTab} from '/classic/app/panel/tabs.js';
import {mermaidText} from '/classic/app/header/export.js';

/* A text copied, the clipboard where the browser gives one; `text` is the text or what writes it. */
async function copied(text, what) {
  let written;
  try { written = typeof text === 'function' ? text() : text; } catch (error) { return toast(error.message); }
  try { await navigator.clipboard.writeText(written); toast(`${what} is copied.`); }
  catch { toast('The browser did not let the page copy it.'); }
}
/* The menu of a node, opened by a right-click. An entry that says how many it holds cannot be chosen holding none. It
 * is where further acts on a node are added. */
export function menu(id, x = null, y = null) {
  const element = S.elements.get(id)?.element;
  if (!element) return;  // a record drawn inside an element has no menu
  const box = $('#menu');
  // an entry closes the menu and does its act; one that counts what it holds cannot be chosen holding none
  const item = (kind, text, act, {count = null, disabled = count === 0, title = null} = {}) =>
    h('button', {class: kind, disabled, role: 'menuitem', title, onclick: () => { box.hidden = true; act(); }},
      count === null ? text : [text + ' ', h('b', {}, String(count))]);
  const at = IN.at(-1)?.key === id;  // the map shows the inside of this element now
  const opened = DEPTH.open.has(id), held = IN.length ? 0 : depthView().held.get(id) || 0;
  const tab = name => async () => { await select(id, true); showTab(name); };
  fill(box,
    item('select', 'Select', () => select(id, true), {disabled: S.selected === id}),
    item('inside', 'Go inside', () => goInside(id), {disabled: at,
      title: 'The element with what it relies on, what relies on it and what the layers hold at it'}),
    IN.length ? item('out', 'Back out one level', () => levelUp()) : null,
    opened ? item('branch', 'Fold its branch', () => { toggleDepth(id); select(id, true); })
      : item('branch', 'Show its branch', () => { toggleDepth(id); select(id, true); },
        {count: held, title: 'The parts it holds that the depth of the map leaves out'}),
    item('brief', 'Read its brief', tab('brief'), {title: 'What an agent that goes to this element is handed'}),
    item('prov', 'Read its provenance', tab('prov')),
    item('address', 'Copy its address', () => copied(element.address, element.address)),
    item('mermaid', 'Copy as Mermaid', () => copied(() => mermaidText({address: element.address}), 'The element with '
      + 'its neighbours'), {title: 'This element and those one line away, as Mermaid code'}));
  box.hidden = false;
  const size = box.getBoundingClientRect();
  box.style.left = Math.max(4, Math.min(x ?? 40, innerWidth - size.width - 4)) + 'px';
  box.style.top = Math.max(4, Math.min(y ?? 40, innerHeight - size.height - 4)) + 'px';
}
// a click outside it or Escape closes it, and the focus goes back where it was
overlay($('#menu'), {kind: 'menu'});
