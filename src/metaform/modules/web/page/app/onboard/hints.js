/* A person's first time at a map: one short hint at a time, beside what it is about, the map, the agents and the chat;
 * and the workbench's controls quiet until the person first reaches for them. What a person has dismissed is kept for
 * them in the Metaform home, /api/hints, and in this browser, and never shown again. */
import '/page/app/onboard/welcome.js';  // the part before runs first, so the parts run in the page's order
import {$} from '/page/app/core/dom.js';
import {FRAMED, S, reach} from '/page/app/core/reads.js';
import {FIRST} from '/page/app/intake/intake.js';
import {WELCOME} from '/page/app/onboard/welcome.js';

/* The hints, in the order they are shown, each with where its card stands: [left, top] for a card of this size. */
const TIPS = [
  {name: 'map', text: "This is your project's map. Drag to turn it, scroll to zoom, and click a part to read what it "
    + 'is for.', at: card => {
    const box = $('main').getBoundingClientRect();
    return [box.left + (box.width - card.width) / 2, box.bottom - card.height - 24];
  }},
  {name: 'agents', text: 'Agents work on the map as figures you can watch. Click one to talk to it; the agents at work '
    + 'are listed at the top right.', at: card => {
    const box = $('main').getBoundingClientRect(), list = $('#agents');
    const below = list.hidden ? 0 : list.getBoundingClientRect().height + 12;
    return [box.right - card.width - 24, box.top + 16 + below];
  }},
  {name: 'chat', text: 'Chat with your own agent here: ask it about the project, or ask it to do something.',
    at: card => {
      const tab = ($('#dock').classList.contains('resting') ? $('#dockTab') : $('#dock')).getBoundingClientRect();
      return [tab.right - card.width, tab.top - card.height - 12];
    }},
];
/* The workbench's regions kept quiet until used, each the class it sets on the page and what counts as using it. */
const QUIET = [{name: 'header', region: 'header'}, {name: 'tabs', region: 'aside .tabs'}];
const KEPT = 'metaform.hints';
export const HINT = {dismissed: new Set(), read: null, ready: false, at: null};

function keptHere() {
  try { return JSON.parse(localStorage.getItem(KEPT) || '[]'); } catch { return []; }
}
function keepHere() {
  try { localStorage.setItem(KEPT, JSON.stringify([...HINT.dismissed])); } catch { /* the home keeps them */ }
}
/* What this person dismissed: in this browser at once, and from the home once read. */
function readDismissed() {
  for (const name of keptHere()) HINT.dismissed.add(name);
  HINT.read ||= reach('/api/hints', {headers: {Accept: 'application/json'}}, 2)
    .then(response => response.ok ? response.json() : {dismissed: []})
    .then(body => { for (const name of body.dismissed || []) HINT.dismissed.add(name); keepHere(); })
    .catch(() => { /* unread, the browser's own list stands */ })
    .finally(() => { HINT.ready = true; });
  return HINT.read;
}
/* One hint gone for good, for this person: kept here at once, then in the home. */
function dismiss(name) {
  HINT.dismissed.add(name);
  keepHere();
  reach('/api/hints', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({hint: name})}, 2).catch(() => { /* this browser keeps it */ });
}

/* The quiet regions: quiet while not yet used; the first press or key in one makes it speak for good. */
function drawQuiet() {
  for (const {name} of QUIET) {
    document.documentElement.classList.toggle(`quiet-${name}`, !FRAMED && !HINT.dismissed.has(name));
  }
}
for (const {name, region} of QUIET) {
  const used = event => {
    if (!event.target.closest?.(region) || HINT.dismissed.has(name)) return;
    dismiss(name);
    drawQuiet();
  };
  document.addEventListener('pointerdown', used, true);
  document.addEventListener('keydown', used, true);
}

/* The next hint not yet dismissed, on a map shown with the welcome gone; one at a time, never two, and none while the
 * card that offers the next step after an intake is up: the hint follows once that card goes. */
function nextHint() {
  const card = $('#hint');
  const tip = TIPS.find(one => !HINT.dismissed.has(one.name));
  if (!HINT.ready || FRAMED || WELCOME.shown || !S.elements.size || !tip || $('#nextStep')) {
    card.hidden = true;
    HINT.at = null;
    return;
  }
  HINT.at = tip;
  $('#hint .text').textContent = tip.text;
  $('#hint .tipno').textContent = `${TIPS.indexOf(tip) + 1} of ${TIPS.length}`;
  card.hidden = false;
  placeHint();
}
function placeHint() {
  if (!HINT.at || $('#hint').hidden) return;
  const card = $('#hint'), size = card.getBoundingClientRect();
  const [left, top] = HINT.at.at(size);
  const edge = 8;
  card.style.left = `${Math.round(Math.min(Math.max(left, edge), innerWidth - size.width - edge))}px`;
  card.style.top = `${Math.round(Math.min(Math.max(top, edge), innerHeight - size.height - edge))}px`;
}
addEventListener('resize', placeHint);
$('#hint .ok').onclick = () => {
  if (HINT.at) dismiss(HINT.at.name);
  $('#hint').hidden = true;
  HINT.at = null;
  setTimeout(nextHint, 500);  // a breath between one hint and the next, so they are never read as one
};
$('#hint .skiptips').onclick = () => {
  for (const tip of TIPS) if (!HINT.dismissed.has(tip.name)) dismiss(tip.name);
  nextHint();
};

/* Each time the page settles on a map, or leaves one: the first hint not yet dismissed, or none. */
const welcomed = FIRST.drawn;
FIRST.drawn = (empty, settled) => {
  const shown = welcomed(empty, settled);
  if (settled) readDismissed().then(() => { drawQuiet(); if (!HINT.at || shown || !S.elements.size) nextHint(); });
  return shown;
};
new MutationObserver(() => {
  if ($('#nextStep')) { if (HINT.at) nextHint(); } else if (!HINT.at && S.elements.size) nextHint();
}).observe(document.body, {childList: true});
readDismissed();
drawQuiet();
