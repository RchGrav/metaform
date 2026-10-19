/* Chat with the mascot: its reply field, the words the person sends the system agent, its answers in the bubble, and
 * a click on a 3D figure opening its session. */
import '/page/app/figures/eyes.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
import {$, h} from '/page/app/core/dom.js';
import {onScreen} from '/page/app/graph/checks.js';
import {ROAM} from '/page/app/figures/agents.js';
import {SPOT} from '/page/app/figures/walk.js';
import {MASCOT} from '/page/app/figures/mascot.js';
import {BUBBLE, bubble, say, readFor, hush, CUT} from '/page/app/figures/cut.js';
import {G} from '/page/app/map3d/graph3d.js';
import {hovered} from '/page/app/map3d/pick3d.js';
import {DOCK} from '/page/app/dock/embody.js';
import {callSystem} from '/page/app/dock/commands.js';
import {wrote} from '/page/app/board/history.js';
import {D, agentAt} from '/page/app/agents/dispatch.js';
import {drawHelpdesk} from '/page/app/dock/helpdesk.js';
import {bubbleAt, bubbleText} from '/page/app/figures/bubble3d.js';
import {spokenOf, sameWords} from '/page/app/session/apps.js';
import {CLICKED, clickedLine} from '/page/app/figures/eyes.js';

/* Chat with the mascot: a click on it, where no node takes the click, opens a small reply field under its bubble.
 * What the person writes goes to their system agent, the one the chat dock's Call starts, and the answer comes back
 * in the bubble, in full in the chat dock's thread. */
// `told`: the line naming the person's last click, fixed when they ask, so a click while the agent starts never changes it
export const ASKING = {open: false, sent: 0, heard: null, base: null, pending: null, told: ''};
/* Where the 3D mascot is on the page, and its depth in the view, which is outside -1 to 1 behind the eye. */
function mascotOnPage() {
  const area = G.renderer().domElement.getBoundingClientRect();
  const at = SPOT.copy(MASCOT.mesh.position).project(G.camera());
  return {x: area.left + (at.x + 1) / 2 * area.width, y: area.top + (1 - at.y) / 2 * area.height, z: at.z};
}
export function mascotScreen() {  // where the 3D mascot is on the page, for a click on it
  if (!G || !MASCOT.mesh) return {};
  const {x, y} = mascotOnPage();
  return {sx: x, sy: y};
}
function mascotAt(x, y) {
  if (!G || !MASCOT.mesh) return false;
  const at = mascotOnPage();
  return Math.abs(at.z) < 1 && Math.hypot(at.x - x, at.y - y) < Math.max(18, onScreen(MASCOT.mesh) * 0.6);
}
// a click the mascot takes for its ask field: on it, with no node hovered and no cut on; the click record skips the
// same clicks, figures/eyes.js, so what the person asks about is the click before
export const mascotTakes = (x, y) => !CUT.on && !hovered && mascotAt(x, y);
function replyField() {
  const el = bubble(), field = h('input', {class: 'reply', type: 'text', placeholder: 'Ask your system agent…',
    'aria-label': 'Ask your system agent through the mascot'});
  ASKING.open = true;
  el.replaceChildren(h('span', {}, BUBBLE.text && performance.now() < BUBBLE.until ? BUBBLE.text : 'Yes?'), field);
  Object.assign(BUBBLE, {until: performance.now() + 60000, click: null});
  el.classList.add('on', 'asking');
  const send = async event => {  // Enter asks, Escape closes; no key reaches the maps
    event.stopPropagation();
    if (event.key === 'Escape') return closeReply();
    if (event.key !== 'Enter' || !field.value.trim()) return;
    const text = field.value.trim();
    closeReply();
    say('Asking…', 30);
    await mascotAsk(text);
  };
  const leave = () => { if (ASKING.open && document.activeElement !== field) closeReply(); };
  field.addEventListener('keydown', send);
  field.addEventListener('blur', () => setTimeout(leave, 200));
  setTimeout(() => field.focus(), 30);
}
function closeReply() {
  ASKING.open = false;
  BUBBLE.el?.classList.remove('asking');
  hush();
}
async function mascotAsk(text) {
  const live = DOCK.mine && D.sessions.some(one => one.work_id === DOCK.mine && one.state === 'running'
    && one.session_id);
  // a second ask while the first still waits joins it, so no words are lost
  ASKING.pending = ASKING.pending ? `${ASKING.pending}\n\n${text}` : text;
  // what "this" is, as the person asks, as the chat's send fixes it when it queues; a second ask while the first
  // waits keeps the first one's line unless a click came between
  ASKING.told = clickedLine() || ASKING.told;
  if (ASKING.told) CLICKED.told = true;
  if (!live && DOCK.calling) return;  // the agent is being reached already: the words go once it is, `flushAsk`
  if (!live) await callSystem();
  if (!ASKING.pending) return;  // already delivered while the agent was reached
  if (!DOCK.mine) {
    if (ASKING.told) CLICKED.told = false;  // never told: the click is the person's to ask about again
    Object.assign(ASKING, {pending: null, told: ''});
    say('I could not reach your system agent.', 4);
    return;
  }
  await flushAsk();
}
/* The system agent could not be reached for a question asked of the mascot that waited on another start, the
 * chat's: the person is told, and their click is theirs to ask about again, as when the mascot's own start fails. */
export function askFailed() {
  if (!ASKING.pending) return;
  if (ASKING.told) CLICKED.told = false;
  Object.assign(ASKING, {pending: null, told: ''});
  say('I could not reach your system agent.', 4);
}
/* The person's words to the system agent go once its session is up: at once when it is, or when the agents are next
 * read, `noticeAttention`, after the Call that starts it. */
export async function flushAsk() {
  const text = ASKING.pending, session = D.sessions.filter(one => one.work_id === DOCK.mine && one.state === 'running'
    && one.session_id).at(-1);
  if (!text || !session) return;
  ASKING.pending = null;
  Object.assign(ASKING, {sent: Date.now(), heard: null, base: null});
  // the line fixed when the person asked, `mascotAsk`
  const told = ASKING.told;
  ASKING.told = '';
  const sent = await wrote('/api/dispatch-message', {work_id: DOCK.mine, session: session.session_id,
    text: told ? `${told}\n\n${text}` : text});
  if (!sent) {
    if (told) CLICKED.told = false;  // not delivered: the click goes with the next message while it is fresh
    say('That did not go through.', 4);
  }
}
/* The system agent's answer, the newest of its words after the person asked, said in the bubble in short; the chat
 * dock's thread, where it is read in full, calls this as it draws. */
export function mascotHeard(target, lines) {
  if (!ASKING.sent || target !== DOCK.mine) return;
  const spoken = lines.filter(line => line.kind === 'agent_message_chunk');
  if (ASKING.base === null) { ASKING.base = Math.max(-1, ...spoken.map(line => Number(line.seq) || 0)); return; }
  const last = spoken.filter(line => (Number(line.seq) || 0) > ASKING.base).at(-1);
  const words = String(last?.text || '').replace(/\s+/g, ' ').trim();
  if (!words || words === ASKING.heard) return;
  ASKING.heard = words;
  // what the agent said on the map with web_say since the person asked is in the bubble already, and not said twice
  const onMap = lines.filter(line => (Number(line.seq) || 0) > ASKING.base).map(spokenOf).filter(Boolean);
  if (onMap.some(said => sameWords(words).includes(sameWords(said)))) return;
  const short = bubbleText(words);
  const own = ROAM.figures.get(DOCK.mine)?.talk ? DOCK.mine : null;  // an embodied system agent answers from its figure
  say(short, readFor(short), () => agentAt(DOCK.mine), own);
}
function clickMascot(event) {  // a click on the mascot where no node takes it: a word with it
  if (!mascotTakes(event.clientX, event.clientY)) return;
  event.stopPropagation();
  replyField();
}
$('#stage').addEventListener('click', clickMascot, true);
/* A figure in 3D is the agent at work on its ticket: a click on it opens that session's thread in the chat dock. A
 * figure is taken anywhere within a ball of its size, so one moving on its orbit is easy to catch. */
export const FIGURE_PICK = {ray: new THREE.Raycaster(), at: new THREE.Vector2(), ball: new THREE.Sphere(),
  middle: new THREE.Vector3(), down: null};
export function figureAt(x, y) {
  if (!G || !ROAM.figures.size) return null;
  const area = G.renderer().domElement.getBoundingClientRect();
  if (!area.width || !area.height) return null;
  FIGURE_PICK.at.set((x - area.left) / area.width * 2 - 1, -(y - area.top) / area.height * 2 + 1);
  FIGURE_PICK.ray.setFromCamera(FIGURE_PICK.at, G.camera());
  const ray = FIGURE_PICK.ray.ray;
  // of the figures whose ball the ray passes through, the one whose middle it passes closest to, for its size: two
  // figures side by side each take the clicks on themselves, not the one nearer the camera; an agent's speech bubble,
  // drawn over the map, takes the click for its agent wherever it shows
  let best = null;
  for (const [id, figure] of ROAM.figures) {
    if (figure.stage === 'leaving') continue;
    const size = Math.max(0.5, figure.mesh.scale.x), middle = figure.mesh.getWorldPosition(FIGURE_PICK.middle);
    FIGURE_PICK.ball.set(middle, size);
    if (!ray.intersectsSphere(FIGURE_PICK.ball)) continue;
    const off = ray.distanceToPoint(middle) / size;
    if (!best || off < best.off) best = {id, off, distance: ray.origin.distanceTo(middle) - size};
  }
  const said = bubbleAt(x, y);  // a bubble is drawn over everything, so it takes the click where it shows
  if (said) return said;
  return best?.id || null;
}
export function openFigure(workId) {
  const child = ROAM.figures.get(workId)?.child;
  if (child) {  // a subagent's figure opens its own thread, in its parent's chat
    agentAt(child.work, child.parent);
    DOCK.child = child.session;
    drawHelpdesk();
    return;
  }
  const session = D.sessions.filter(one => one.work_id === workId && one.state === 'running').at(-1);
  agentAt(workId, session?.session_id || null);
}
