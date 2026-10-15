/* A first-time person's welcome: one small plain window over a page that stays usable, saying what Metaform is and
 * where help is, with OK, which puts it away for good. It is a first-time person's alone: someone who has used the page
 * before never gets it, nor does the page in an AI tool's frame. Who the person is, and that they have closed it, are
 * kept for them in the Metaform home, /api/hints, and in this browser, so it never comes back in any browser. */
import '/page/app/loading/load.js';  // the part before runs first, so the parts run in the page's order
import {$} from '/page/app/core/dom.js';
import {FRAMED, S, reach} from '/page/app/core/reads.js';
import {FIRST} from '/page/app/intake/intake.js';
import {openHelp} from '/page/app/keys/keys.js';

/* seen: what this person has closed; who: 'newcomer', 'returning', or null until decided; ready: the home read. */
const KEPT = 'metaform.hints';
const PERSON = ['newcomer', 'returning'];
const WELCOME = 'welcome';
export const HINT = {seen: new Set(), who: null, ready: false, read: null};
/* Whether this browser showed a project before this load: read before the page remembers the one it opens. */
const usedHere = (() => {
  try { return localStorage.getItem('metaform.project') !== null; } catch { return false; }
})();

function keptHere() {
  try { return JSON.parse(localStorage.getItem(KEPT) || '[]'); } catch { return []; }
}
function keepHere() {
  // a newcomer is never kept here: every home served at this address shares the browser's storage
  const kept = [...HINT.seen, ...(HINT.who === 'returning' ? ['returning'] : [])];
  try { localStorage.setItem(KEPT, JSON.stringify(kept)); } catch { /* the home keeps them */ }
}
function send(given) {
  return reach('/api/hints', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(given)}, 2).catch(() => { /* this browser keeps it */ });
}
/* What this person has closed, and who they are: from this browser at once, then from the home, which wins. */
function readKept() {
  for (const name of keptHere()) {
    if (name === 'returning') HINT.who = 'returning';
    else if (!PERSON.includes(name)) HINT.seen.add(name);
  }
  HINT.read ||= reach('/api/hints', {headers: {Accept: 'application/json'}}, 2)
    .then(response => response.ok ? response.json() : {dismissed: []})
    .then(body => {
      const names = body.dismissed || [];
      for (const name of names) if (!PERSON.includes(name)) HINT.seen.add(name);
      HINT.who = PERSON.find(one => names.includes(one)) || HINT.who;
      keepHere();
    })
    .catch(() => { /* unread, the browser's own list stands */ })
    .finally(() => { HINT.ready = true; });
  return HINT.read;
}
/* Who this person is, decided once, on the first project the page shows them: a first-time person has this one
 * project and a browser that never showed one; anyone else has used Metaform before. */
function decide() {
  if (HINT.who || !S.project) return;
  HINT.who = S.projects.length === 1 && !usedHere ? 'newcomer' : 'returning';
  keepHere();
  send({hint: HINT.who});
}
/* The welcome, for a first-time person who has not closed it. */
function welcome() {
  $('#welcome').hidden = FRAMED || !HINT.ready || HINT.who !== 'newcomer' || HINT.seen.has(WELCOME);
}
$('#welcome .ok').onclick = () => {
  $('#welcome').hidden = true;
  HINT.seen.add(WELCOME);
  keepHere();
  send({hint: WELCOME});
};
$('#welcome .helpkey').onclick = () => openHelp();

/* Each time the page settles on a project: who this person is, once, and the welcome if it is theirs. */
FIRST.drawn = (empty, settled) => {
  if (!settled || FRAMED) return;
  readKept().then(() => { decide(); welcome(); });
};
if (!FRAMED) readKept();  // the map in an AI tool's frame shows no welcome, and asks nothing for it
