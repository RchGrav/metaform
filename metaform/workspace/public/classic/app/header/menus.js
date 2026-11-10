/* The header's menus and popovers, its text size and its fold, the skip links and the window, workspace and
 * administration menus. */
import '/classic/app/header/layers.js';  // the part before runs first, so the parts run in the page's order
import {$, h} from '/classic/app/core/dom.js';
import {overlay} from '/classic/app/core/overlays.js';
import {openHelp} from '/classic/app/keys/keys.js';

/* The header's menus and popovers, each on the overlay stack: its button opens and closes it, a click outside or
 * Escape closes it, and the focus goes back to its button. */
export function toggler(button, box, open = () => {}) {
  const flip = async () => {
    if (!box.hidden) { box.hidden = true; return; }
    box.hidden = false;
    await open();
  };
  button.addEventListener('click', flip);
}
overlay($('#settingsbox'), {kind: 'popover', focus: () => $('#settingsbox')});  // the menu itself, so no control shows a ring on opening
toggler($('#settingsBtn'), $('#settingsbox'));
/* Where the header ends, `--head-bottom`, kept as the header changes height, as when it folds: the configuration
 * surfaces, the View panel and the settings screen, open at the window's right edge just below it, wherever the side
 * column, the maps or the workspace's panes stand. */
const headBottom = () => document.documentElement.style.setProperty('--head-bottom',
  `${Math.round($('header').getBoundingClientRect().bottom)}px`);
new ResizeObserver(headBottom).observe($('header'));
addEventListener('resize', headBottom);
headBottom();
$('#shortcutsBtn').onclick = () => openHelp();
$('#helpBtn').onclick = () => openHelp();  // the header's Help, beside Settings: the same window
overlay($('#help'), {kind: 'dialog', close: () => { $('#help').hidden = true; }});
$('#help .close').onclick = () => { $('#help').hidden = true; };
/* The page's text size, VIEW-023: chosen from the View menu's list or stepped with Alt and =, Alt and -, and Alt and 0
 * for the default. It steps every size token of the page, the type, the spacing and the heights of controls, through
 * --ui, so the header, the menus, the panel and the windows follow; the maps draw their own text and are not scaled.
 * There is no button for it in the header: a button that grows with the text it sizes moves out from under the mouse.
 * The size is kept in this browser and put back before the page draws, `theme.js`; it touches this page only. */
const TEXTSIZE = {steps: [0.84, 0.92, 1, 1.08, 1.17, 1.27, 1.38, 1.5], start: 3, key: 'metaform.textSize'};
/* The step of the text size in force, the one nearest the page's --ui. */
function textStep() {
  const ui = Number(getComputedStyle(document.documentElement).getPropertyValue('--ui'));
  const now = ui || TEXTSIZE.steps[TEXTSIZE.start];
  const nearer = (best, step, index) => Math.abs(step - now) < Math.abs(TEXTSIZE.steps[best] - now) ? index : best;
  return TEXTSIZE.steps.reduce(nearer, 0);
}
function keepTextSize(at) {
  if (at === TEXTSIZE.start) localStorage.removeItem(TEXTSIZE.key);
  else localStorage.setItem(TEXTSIZE.key, String(TEXTSIZE.steps[at]));
}
function textSize(index) {
  const at = Math.max(0, Math.min(TEXTSIZE.steps.length - 1, index));
  document.documentElement.style.setProperty('--ui', String(TEXTSIZE.steps[at]));
  try { keepTextSize(at); }
  catch (error) { /* storage can be blocked; the size still changes */ }
  $('#textsize').value = String(at);
  // the panes and the maps' areas changed size with it, and the header folds if it must
  dispatchEvent(new Event('resize'));
}
for (const [index, step] of TEXTSIZE.steps.entries()) {
  const percent = Math.round(step / TEXTSIZE.steps[TEXTSIZE.start] * 100);
  const label = `${percent}%` + (index === TEXTSIZE.start ? ' (default)' : '');
  $('#textsize').append(h('option', {value: String(index)}, label));
}
$('#textsize').onchange = event => textSize(Number(event.target.value));
// The text size is chosen in the View menu; no Alt shortcut, which the system takes on some machines.
textSize(textStep());
/* The map is the page's large view. */
export const largeView = () => $('#map2d');
