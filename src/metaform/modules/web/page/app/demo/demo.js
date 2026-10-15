/* The demo's own part, `metaform demo`, CLI-042: in the home the demo runs, one small card saying what the person is
 * looking at, in two lines, and the next steps, each a command to copy; and the person's mascot, the demo's system
 * agent, given its body as soon as its conversation runs, so it walks out and greets them. In any other home the
 * server says there is no demo, and this part does nothing more. */
import '/page/app/workspace/workspace.js';  // the part before runs first, so the parts run in the page's order
import {GLYPHS} from '/page/agents3d.js';
import {h} from '/page/app/core/dom.js';
import {copyField} from '/page/app/core/controls.js';
import {S, reach} from '/page/app/core/reads.js';
import {ROAM, bodyOf, embody, isSystemTalk} from '/page/app/figures/agents.js';
import {mascotGlyph, preferredGlyph} from '/page/app/figures/mascot.js';
import {D} from '/page/app/agents/dispatch.js';

const HIDDEN = 'metaform.demo-card-hidden';  // the person closed the card: kept for this tab
export const DEMO = {card: null, given: false};

async function demoCard() {
  try {
    const response = await reach('/api/demo', {headers: {Accept: 'application/json'}});
    return response.ok ? (await response.json()).demo : null;
  } catch { return null; }
}
/* The card: its two lines, then each next step with its command to copy; the person can close it. */
function showCard(demo) {
  if (sessionStorage.getItem(HIDDEN)) return;
  const close = h('button', {class: 'btn icon demo-close', type: 'button', 'aria-label': 'Hide this card',
    title: 'Hide', onclick: () => { DEMO.card?.remove(); sessionStorage.setItem(HIDDEN, '1'); }},
    h('i', {class: 'i i-close', 'aria-hidden': 'true'}));
  const lines = (demo.lines || []).slice(0, 2).map(line => h('p', {}, line));
  const steps = (demo.next || []).map(([label, command]) =>
    h('div', {class: 'demo-step'}, h('span', {}, label), copyField({label, text: command})));
  DEMO.card = h('aside', {id: 'demo-card', class: 'demo-card', role: 'note', 'aria-label': 'About this demo'},
    close, ...lines, h('div', {class: 'demo-next'}, ...steps));
  document.body.append(DEMO.card);
}
/* The person's mascot: the demo's system agent, given a body once its conversation runs, the person's own character
 * when they chose one, else the first no figure at work has. */
function giveMascot() {
  const ticket = (S.tickets || []).find(isSystemTalk);
  if (!ticket || mascotGlyph() || bodyOf(ticket.id)) return;
  if (!D.sessions.some(one => one.work_id === ticket.id && one.state === 'running')) return;
  const busy = new Set([...ROAM.figures.values()].map(figure => figure.glyph));
  const glyph = preferredGlyph() || GLYPHS.find(name => !busy.has(name));
  if (glyph && !embody(ticket.id, glyph, 'person').error) DEMO.given = true;
}
demoCard().then(demo => {
  if (!demo) return;
  showCard(demo);
  setInterval(giveMascot, 1500);
});
