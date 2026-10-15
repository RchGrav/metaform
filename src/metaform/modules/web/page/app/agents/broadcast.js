/* Broadcast: one message from the person to every agent working on the project, from Broadcast… in the header's
 * Agents menu; a button of its own would not fit the header's row at 1280 px, which would fold the header. */
import '/page/app/demo/demo.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {expandCut} from '/page/app/core/expand.js';
import {overlay} from '/page/app/core/overlays.js';
import {S, read} from '/page/app/core/reads.js';
import {clockOf} from '/page/app/dock/embody.js';
import {wrote, movable} from '/page/app/board/history.js';
import {D, SESSIONS_DRAWN, glyphOf, glyphFor} from '/page/app/agents/dispatch.js';
import {agentName} from '/page/app/agents/pickers.js';
import {isIntake} from '/page/app/session/tools.js';
import {sessionTask} from '/page/app/dock/threads.js';

/* The window stays beside the map while the agents answer, a window and never a dialog. Send gives the text to the
 * dispatch module's broadcast in one request, which tells every running session at once as the person's own message,
 * `message`'s steering rules and all; the person's system agent is told only with "include my chat agent". The
 * window then lists each session told, its glyph, its agent's name and its ticket, delivered or failed with why, and
 * the broadcasts kept on the project below. */
const B = {project: null, sending: false, told: null};
const box = $('#broadcast'), say = $('#broadcast textarea'), send = $('#broadcast .send');
const mineOnly = $('#broadcast .system');
const running = () => D.sessions.filter(one => one.state === 'running');
const isMine = session => D.states?.[session.session_id]?.about === 'system';
/* The sessions a broadcast reaches now: every running one, the person's own chat agent only when ticked. */
const reached = () => running().filter(one => mineOnly.checked || !isMine(one));
function drawBroadcast() {
  if (box.hidden) return;
  if (B.project !== S.project) Object.assign(B, {project: S.project, told: null});
  const all = running(), now = reached();
  $('#broadcast .reach').textContent = !all.length ? 'No agent is working on this project.'
    : !now.length ? 'Only your chat agent is working on this project; include it to tell it.'
    : `It goes to ${now.length === 1 ? 'the one agent' : `the ${now.length} agents`} working on this project, `
      + 'each at its next turn, as your own message.';
  $('#broadcast .mine').hidden = !all.some(isMine);
  send.disabled = B.sending || !now.length || !say.value.trim();
  fill($('#broadcast .told'), B.told ? toldRows(B.told) : []);
}
SESSIONS_DRAWN.push(drawBroadcast);
expandCut($('#broadcast .told'), {row: '.agent-session', text: '.task', key: row => row.dataset.session});
/* Who it went to: each session with its glyph, its agent's name and its ticket, delivered or failed and why. */
function toldRows(kept) {
  return [h('p', {class: 'label'}, `Sent ${clockOf(Date.parse(kept.at))}`), ...kept.recipients.map(one =>
    h('div', {class: `agent-session ${one.delivered ? 'delivered' : 'failed'}`, 'data-session': one.session_id},
      h('img', {src: glyphOf(one.work_id), alt: glyphFor(one.work_id)}),
      h('div', {class: 'details'}, h('b', {}, agentName(one.agent)), h('span', {class: 'task'},
        isIntake(one.work_id) ? 'The intake' : sessionTask(one)),
        h('span', {class: 'meta'}, one.delivered ? 'Delivered' : `Failed: ${one.reason}`))))];
}
/* The broadcasts kept on the project, newest first: when, what, and how many of its agents it reached. */
async function drawEarlier() {
  const project = S.project;
  let found;
  try { found = (await read('dispatch-broadcasts', {limit: 5})).broadcasts || []; } catch { found = []; }
  if (S.project !== project || box.hidden) return;
  const reachedOf = kept => kept.recipients.filter(one => one.delivered).length;
  fill($('#broadcast .earlier'), found.length ? [h('p', {class: 'label'}, 'Kept on this project'),
    ...found.map(kept => h('div', {class: 'kept', title: new Date(kept.at).toLocaleString()},
      h('time', {datetime: kept.at}, clockOf(Date.parse(kept.at), true)), h('span', {class: 'text'}, kept.text),
      h('span', {class: 'meta'}, `${reachedOf(kept)} of ${kept.recipients.length}`)))] : []);
}
export function openBroadcast() {
  box.hidden = false;
  drawBroadcast();
  drawEarlier();
}
async function sendBroadcast() {
  const text = say.value.trim(), project = S.project;
  if (!text || send.disabled) return;
  B.sending = true;
  drawBroadcast();
  let kept;
  try { kept = await wrote('/api/dispatch-broadcast', {text, system: mineOnly.checked}); }
  finally { B.sending = false; }
  if (S.project !== project) return;
  if (kept) { B.told = kept; say.value = ''; drawEarlier(); }
  drawBroadcast();
}
$('#broadcastBtn').onclick = () => { $('#agentbox').hidden = true; openBroadcast(); };
send.onclick = sendBroadcast;
say.addEventListener('input', drawBroadcast);
mineOnly.addEventListener('change', drawBroadcast);
say.addEventListener('keydown', event => {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  sendBroadcast();
});
$('#broadcast .close').onclick = () => { box.hidden = true; };
overlay(box, {kind: 'window', close: () => { box.hidden = true; }, focus: 'textarea'});
movable(box);
