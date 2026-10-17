/* The intake started from the page, VIEW-045 and BASE-039: its agent, its bar over the map, its chat, start and
 * stop, and an empty project's prompt. */
import '/page/app/session/settings.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {overlay} from '/page/app/core/overlays.js';
import {toast, confirmAct} from '/page/app/core/controls.js';
import {S, MEM, reach} from '/page/app/core/reads.js';
import {mapUnread} from '/page/app/core/errors.js';
import {showAdmin, noMetaform, emptyActs} from '/page/app/header/admin.js';
import {plural} from '/page/app/memory/manage.js';
import {DOCK, STANDBY, dockState} from '/page/app/dock/embody.js';
import {openHelpdesk, rememberStop} from '/page/app/dock/threads.js';
import {ago} from '/page/app/board/refs.js';
import {wrote} from '/page/app/board/history.js';
import {D, WAITS_ON_PERSON, renderAgents} from '/page/app/agents/dispatch.js';
import {HARNESS, readHarnesses, agentName, summonAgent, summonPicker} from '/page/app/agents/pickers.js';
import {isIntake} from '/page/app/session/tools.js';
import {drawIntakeSettings} from '/page/app/session/settings.js';
import {LIVE, following, recordingNow} from '/page/app/live/stream.js';

/* ---------- the intake, started from the page, VIEW-045 and BASE-039 ----------
 * An agent the person chooses runs the project's intake and records the map as it goes; the page follows the intake
 * being recorded, so the map grows here. A project with no map offers it first; Administration offers it again, to map
 * the project anew or to check the map against it. While it runs, a bar over the map says so, with its chat and Stop.
 * Its work id, `intake-…`, is never a ticket. */
export const INTAKE = {work: null, session: null, agent: null, waiting: 0, closed: new Set(), resume: false,
  refines: false};
// closed: the runs whose bar the person closed with its ×
/* An intake agent under way: starting, launched and its session not made yet, or running. The server's one record of
 * it is read with the sessions, `dispatch sessions` listing a launch as starting, so every tab and every surface agrees
 * whichever surface launched it, UX review round 1 (2026-10-17) cross-surface F1. */
const underWay = one => isIntake(one.work_id) && (one.state === 'running' || one.state === 'starting');
export const intakeRunning = () => Boolean(INTAKE.session && underWay(INTAKE.session));
/* The intake agent of this project, as the sessions read says it: one starting or running. */
export async function readIntake(signals = []) {
  const session = D.sessions.filter(underWay).at(-1) || null;
  const was = intakeRunning();
  INTAKE.session = session;
  INTAKE.work = session?.work_id || null;
  INTAKE.agent = session?.agent || null;
  INTAKE.waiting = session ? signals.filter(one => WAITS_ON_PERSON.includes(one.signal) && one.active !== false
    && one.work_id === session.work_id).length : 0;
  // what the intake's guard and its runner say of it, such as no first record yet or reading earlier conclusions
  INTAKE.signals = session ? signals.filter(one => one.active !== false && one.work_id === session.work_id
    && !WAITS_ON_PERSON.includes(one.signal)) : [];
  drawIntake();
  // its agent stopped: what is building is read again, so the bar closes, or the intake shows as left unfinished
  if (was && !intakeRunning()) recordingNow().catch(error => toast(error.message));
}
/* The signals an intake's session raises, said in words on its bar: [words, status class, why]. A signal not named here
 * is said by its own name. */
const NO_RECORD = 'The intake has read for a while and recorded nothing: open its chat to see what it is doing.';
const READS_CONCLUSIONS = 'It reads earlier reports and notes in place of the project itself, and inherits their '
  + 'errors.';
const INTAKE_SIGNALS = {
  'no-first-record': ['No record yet', 'input_required', NO_RECORD],
  'first-record-late': ['No record yet', 'input_required', NO_RECORD],
  'intake-conclusions': ['Reading conclusions', 'input_required', 'It reached for a report, review, log or notes drawn '
    + 'earlier in place of the project itself, and would inherit their errors.'],
  'conclusion-reading': ['Reading conclusions', 'input_required', READS_CONCLUSIONS],
  conclusions: ['Reading conclusions', 'input_required', READS_CONCLUSIONS],
  silent: ['Silent', 'waiting', 'It has said nothing for a while.'],
  'spinning-calls': ['Repeating calls', 'failed', 'It makes the same calls again and again.'],
  'spinning-time': ['Long turn', 'waiting', 'Its turn has run long.'],
  'repeated-failure': ['Failing', 'failed', 'The same step fails again and again.'],
  'login-needed': ['Needs a login', 'login', 'Its agent needs a login, which only you can give.'],
  budget: ['Budget reached', 'failed', 'It reached a spend budget.'],
};
/* The run the bar is for: the intake agent's work, or the layer an agent outside the page records. */
const runKey = () => intakeRunning() ? `work:${INTAKE.work}` : `layer:${S.project}/${LIVE.base}/${LIVE.layer}`;
/* The bar over the map while an intake agent runs or one records the intake now, BASE-039: what is happening, its
 * agent, its acts and its ×. It goes the moment its agent stops; closed with its ×, it stays closed for that run, unless
 * the agent waits on the person. */
export function drawIntake() {
  const bar = $('#intakeBar');
  const running = intakeRunning(), recording = LIVE.layer !== null;
  bar.hidden = !(running || recording) || INTAKE.closed.has(runKey()) && !INTAKE.waiting;
  drawEmpty();
  drawLeft();
  if (bar.hidden) return;
  const parts = S.elements.size;
  // the intake guard's page side: no record yet is said with how long the agent has been at it, from its session's
  // start, said again at each change the page hears, never by a timer of its own
  // the runner's own word on it first, its `intake` state, M04: the phase and when it began
  const guard = (D.states || {})[INTAKE.session?.session_id]?.intake || null;
  const since = guard?.began || INTAKE.session?.started || null;
  const waitingFirst = guard ? guard.phase === 'waiting for first record' : INTAKE.session?.activity === 'working';
  const firstWait = running && !recording && !INTAKE.waiting && since && waitingFirst && !parts
    ? `Waiting for the first record · ${ago(since) === 'now' ? 'just started' : `${ago(since)} since it started`}`
      + (guard?.steered ? ' · told to record' : '') : null;
  // a session made and between turns is idle, not starting: its agent stays to talk after a turn, so an intake agent
  // that has stopped working, or was used for something else, would otherwise read Starting for as long as it runs
  const activity = INTAKE.session?.activity;
  const launching = INTAKE.session?.state === 'starting';
  const doing = INTAKE.waiting ? `${agentName(INTAKE.agent)} waits for your permission`
    : launching ? `Starting${since ? ` · since ${ago(since) === 'now' ? 'just now' : `${ago(since)} ago`}` : ''}`
    : recording ? `Recording ${LIVE.layer} · ${following() ? `${plural(parts, 'part')} so far` : 'in a base of its own'}`
    : firstWait || (activity === 'working' ? 'Reading the project'
      : activity === 'idle' && INTAKE.session?.session_id ? 'Idle · its turn has ended, and nothing is being recorded'
        : 'Starting');
  bar.classList.toggle('asks', INTAKE.waiting > 0);
  const said = (INTAKE.signals || []).map(signalChip);
  const outside = `Recording ${LIVE.layer} · ${following() ? `${plural(parts, 'part')} so far` : 'in a base of its own'}`
    + ' · by an agent outside the page';
  fill(bar, h('span', {class: 'pulse', 'aria-hidden': 'true'}),
    h('span', {class: 'what'}, h('b', {}, running ? `Intake · ${agentName(INTAKE.agent)}` : 'Intake'),
      h('span', {class: 'doing'}, running ? doing : outside),
      said.length ? h('span', {class: 'signals'}, said) : null),
    ...intakeActs(running),
    h('button', {class: 'x', type: 'button', title: 'Close', 'aria-label': 'Close',
      onclick: () => { INTAKE.closed.add(runKey()); drawIntake(); }}, '×'));
}
const intakeSignal = signal => Object.hasOwn(INTAKE_SIGNALS, signal) ? INTAKE_SIGNALS[signal] : undefined;
/* A signal on the intake's bar: its words, its status, and why, as the signal itself says it or else as named here. */
const signalChip = one => h('span', {class: `statechip ${intakeSignal(one.signal)?.[1] || 'waiting'}`,
  title: one.detail || one.message || one.reason || intakeSignal(one.signal)?.[2] || ''},
intakeSignal(one.signal)?.[0] || String(one.signal || '').replace(/-/g, ' '));
/* While it runs: its chat, or Answer while it waits on the person, and Stop. An agent outside the page that records it
 * is the person's own, stopped where it runs. */
function intakeActs(running) {
  if (!running) return [];
  // a launch has no session yet, so no chat: only its Stop, which ends it before its agent starts
  const chat = INTAKE.session?.session_id ? h('button', {class: `btn sm ${INTAKE.waiting ? 'primary' : ''}`,
    type: 'button', onclick: () => openIntakeChat()}, INTAKE.waiting ? 'Answer' : 'Chat') : null;
  return [chat, h('button', {class: 'btn sm danger', type: 'button', onclick: stopIntake}, 'Stop')]
    .filter(Boolean);
}
/* The intake's chat in the dock: it is already a conversation, so it is opened on its session, never through a ticket.
 */
export function openIntakeChat(work = INTAKE.work, session = INTAKE.session?.session_id || null, {focus = false} = {}) {
  if (!work) return;
  const agent = INTAKE.work === work ? INTAKE.agent : D.sessions.find(one => one.work_id === work)?.agent;
  openHelpdesk(work, `the intake agent (${agentName(agent)})`, STANDBY, session, 'intake', {focus});
  if (DOCK.chat) DOCK.chat.mine = true;
}
export async function stopIntake() {
  const work = INTAKE.work;
  if (!work || !await confirmAct({title: 'Stop the intake?',
    text: `${agentName(INTAKE.agent)} stops and its chat ends.`,
    lost: ['The agent and its session; what it was about to record next'],
    kept: ['Everything it recorded so far, in its layer', 'A new intake can take this one over and go on with it'],
    verb: 'Stop the intake', cancel: 'Keep it running'})) return;
  const session = INTAKE.session?.session_id;
  const stopped = await wrote('/api/dispatch-stop', {work_id: work, ...(session ? {session} : {})});
  if (stopped) {
    if (session) rememberStop(session, new Date().toISOString());
    if (stopped.autostart === false) $('#autostartAgents').checked = false;  // dispatch's `paused`
    toast(stopped.gone ? 'The intake agent had ended already; what it recorded is kept.'
      : `The intake agent was stopped.${stopped.autostart === false ? ` ${stopped.notice}` : ''}`);
  }
  // redrawn from the server's record after any answer, a refusal too, so the bar never stays on an agent that is gone
  await renderAgents();
}
/* The window an intake starts from: the agent, an optional note for it, and Start; a refusal is said with its next
 * step, and the step offered as a button where the page can take it: taking over an intake left being recorded, or
 * opening the one already at work. */
export async function openIntake({resume = false} = {}) {
  showAdmin(false);
  const box = $('#intake'), mapped = !noMetaform() && S.elements.size > 0;
  if (intakeRunning()) {  // one intake at a time: the one under way is shown, never a second offered
    if (INTAKE.session?.session_id) openIntakeChat();
    return toast(INTAKE.session?.state === 'starting'
      ? `An intake is starting: ${agentName(INTAKE.agent)}. Its bar over the map has Stop.`
      : `An intake is running: ${agentName(INTAKE.agent)}. Its chat is open.`);
  }
  $('#intake .title').textContent = mapped ? `Run the intake again · ${S.project}` : `Map ${S.project}`;
  fill($('#intake .lead'), mapped
    ? `An agent runs the intake on ${S.project} as it is now: it checks the map in use against the project and `
      + 'refines it, adding what the map lacks and correcting what has changed. Its memories, tickets and knowledge '
      + 'stay where they are.'
    : `An agent reads ${S.project} and records its map as it goes. You watch the map grow here, part by part.`);
  // a mapped project is refined, never mapped again beside the map in use (refinement first, 2026-10-17): the
  // window sends map=extend, so the agent's intake start opens a verification pass on the map in use
  INTAKE.refines = mapped && !resume;
  const host = $('#intake .pickhost');
  if (!host.firstChild) {
    host.append(summonPicker('intake', {label: 'Agent for the intake', onchange: () => drawIntakeSettings()}));
  }
  drawIntakeSettings();
  const note = $('#intake textarea.note');
  $('#intake .suggest').hidden = !mapped;
  fill($('#intake .failed'));
  $('#intake .failed').hidden = true;
  $('#intake .resume').hidden = !resume;
  INTAKE.resume = resume;
  drawStart();
  box.hidden = false;
  readHarnesses();
  if (!note.value) note.focus();
}
async function startIntake() {
  const button = $('#intake .start'), note = $('#intake textarea.note'), agent = summonAgent();
  if (!agent) {
    return showIntakeRefusal({error: 'No agent can start here.', next: HARNESS.next || 'metaform dispatch agents'});
  }
  button.disabled = true;
  const sent = await posted('/api/dispatch-intake', {agent, text: note.value.trim() || undefined,
    resume: INTAKE.resume || undefined, map: INTAKE.refines ? 'extend' : undefined});
  button.disabled = false;
  if (!sent.ok) return showIntakeRefusal(sent.body);
  const started = sent.body;
  $('#intake').hidden = true;
  note.value = '';
  toast(`${agentName(started.agent)} is starting on the intake`
    + (started.map === 'extend' ? ', checking and refining the map in use.' : '.')
    + ' The map grows here as it records.');
  await renderAgents();  // the server's record says it is starting: the bar is drawn from that read
}
function showIntakeRefusal(body) {
  const box = $('#intake .failed'), next = body?.next || '';
  const acts = [];
  const running = /dispatch stop (intake-[0-9a-f]+)/.exec(next);
  if (/resume=true/.test(next)) {
    acts.push(h('button', {class: 'btn sm', type: 'button', onclick: () => takeOver(box)}, 'Take it over'));
  }
  if (running) {
    acts.push(h('button', {class: 'btn sm', type: 'button', onclick: () => openRunning(running[1])}, 'Open its chat'));
  }
  fill(box, h('p', {}, h('b', {}, body?.error || 'The intake did not start.')),
    next ? h('p', {class: 'next'}, 'Next: ', h('code', {}, next)) : null,
    acts.length ? h('div', {class: 'acts'}, acts) : null);
  box.hidden = false;
}
/* The intake left being recorded is taken over: the window turns to Take over, and the refusal goes. */
function takeOver(box) {
  INTAKE.resume = true;
  $('#intake .resume').hidden = false;
  INTAKE.refines = false;
  drawStart();
  fill(box); box.hidden = true;
  $('#intake .start').focus();
}
/* The intake already at work: its chat opened in place of a second one. */
function openRunning(work) {
  $('#intake').hidden = true;
  INTAKE.work = work;
  openIntakeChat(work, null);
}
/* Start says what it starts. */
function drawStart() {
  $('#intake .start').textContent = INTAKE.resume ? 'Take over the intake'
    : INTAKE.refines ? 'Check and refine the map' : 'Start the intake';
}
$('#intake .close').onclick = $('#intake .cancel').onclick = () => { $('#intake').hidden = true; };
$('#intake .start').onclick = startIntake;
/* A suggestion pressed is written as the note for the agent. */
function suggest(button) {
  const note = $('#intake textarea.note');
  note.value = button.dataset.text;
  note.focus();
}
for (const button of document.querySelectorAll('#intake .suggest button')) button.onclick = () => suggest(button);
overlay($('#intake'), {kind: 'dialog', close: () => { $('#intake').hidden = true; },
  focus: () => $('#intake textarea.note')});
$('#intakeBtn').onclick = () => openIntake();
/* A first-time person's welcome, onboard/hints.js, set by that later part: told each time the page settles on a project
 * or leaves one, so the welcome shows once it is theirs. It never changes what is shown here. */
export const FIRST = {drawn: null};
/* A project with no map yet says so over the map, with the intake as the one thing to do. */
export function drawEmpty() {
  const panel = $('#p-object > .emptypanel');
  if (panel) emptyActs(panel);
  const settled = !S.loading && !S.opening;
  // a map that could not be read is not an empty one: the error surface says why it is not drawn
  // nor beside an intake left unfinished, whose card offers what to do with it, cross-surface F3
  const empty = settled && S.project && !S.elements.size && LIVE.layer === null && !intakeRunning() && !MEM.key
    && !mapUnread() && !(LIVE.left && LIVE.left.project === S.project);
  FIRST.drawn?.(Boolean(empty), settled);
  $('#emptyStage').hidden = !empty;
  if (!empty) return;
  // A base shown empty beside others that hold maps says they are kept and offers first, ahead of a new intake, the
  // one the person last made active: the base list says which hold a map, `mapped`, and when each was last active,
  // so it never offers another empty base (UX review round 2, 2026-10-17, project-scope F3).
  const others = S.bases.filter(item => item.id !== S.base);
  const maps = others.filter(item => item.mapped), empties = others.filter(item => !item.mapped);
  const names = list => list.map(item => item.name).join(', ');
  fill($('#emptyStage .what'), noMetaform() ? `${S.project} has no map yet.` : maps.length
    ? `This base of ${S.project} is empty. ${maps.length === 1 ? 'Its map is' : 'Its maps are'} kept in `
      + `${names(maps)}${empties.length ? `; ${names(empties)} ${empties.length === 1 ? 'is' : 'are'} empty too` : ''}.`
    : others.length ? `This base of ${S.project} is empty, and so ${others.length === 1 ? 'is its other base'
      : 'are its other bases'}, ${names(others)}.`
    : `${S.project}'s map is empty.`);
  const back = maps.reduce((best, item) => !best || (item.activated || '') > (best.activated || '')
    || (item.activated || '') === (best.activated || '') && item.created > best.created ? item : best, null);
  fill($('#emptyStage .other'), back ? h('button', {class: 'btn', type: 'button', onclick: () => showBase(back.id)},
    `Show ${back.name}`) : null);
}
/* Show another base, as choosing it in the base list does: nothing is activated. */
function showBase(id) {
  $('#mf').value = id;
  $('#mf').onchange();
}
$('#emptyStage .start').onclick = () => openIntake();
/* An intake left unfinished, BASE-039: no agent records it, so it is never shown as being recorded nor followed. One
 * notice in its own project says what it is and offers Resume, an agent that goes on with it, Finish, with what it
 * recorded, and Discard, after one confirmation; its × puts it away for good in this browser. */
const LEFT_KEY = left => `metaform.intake-left.${left.project}/${left.base_id}/${left.layer.id}`;
function leftClosed(left) {
  try { return localStorage.getItem(LEFT_KEY(left)) === 'closed'; } catch { return false; }
}
function closeLeft(left) {
  try { localStorage.setItem(LEFT_KEY(left), 'closed'); } catch { /* storage can be blocked; closed for now */ }
  LIVE.left = null;
  drawLeft();
}
export function drawLeft() {
  const left = LIVE.left, shown = $('#intakeLeft');
  const show = left && left.project === S.project && !intakeRunning() && LIVE.layer === null && !leftClosed(left);
  const said = show ? `An intake of ${S.project} was left unfinished: base ${left.base}, layer ${left.layer.name}, `
    + `${plural(left.parts, 'part')}${left.last ? `, last recorded ${ago(left.last) === 'now' ? 'just now'
      : `${ago(left.last)} ago`}` : ''}. No agent of Metaform's is recording it now.` : '';
  if (shown && shown.dataset.said === said) return;  // drawn already: left as it is, keeping the focus in it
  shown?.remove();
  if (!show) return;
  const card = h('div', {id: 'intakeLeft', class: 'nextcard', role: 'status', 'data-said': said},
    h('p', {class: 'text'}, said),
    h('div', {class: 'acts'},
      h('button', {class: 'btn primary', type: 'button', title: 'Start an agent that goes on with this intake',
        onclick: () => openIntake({resume: true})}, 'Resume…'),
      h('button', {class: 'btn', type: 'button', title: `Finish it with the ${plural(left.parts, 'part')} recorded`,
        onclick: () => finishLeft(left)}, 'Finish'),
      h('button', {class: 'btn danger', type: 'button', title: 'Drop it and the parts it recorded',
        onclick: () => discardLeft(left)}, 'Discard…'),
      h('button', {class: 'x', type: 'button', title: 'Dismiss', 'aria-label': 'Dismiss',
        onclick: () => closeLeft(left)}, '×')));
  document.body.append(card);
}
/* The intake left unfinished, finished with what it recorded, as `metaform intake finish` does. */
async function finishLeft(left) {
  const sent = await posted('/api/intake-finish', {});
  if (!sent.ok) return toast(`${sent.body?.error || 'The intake was not finished.'}`
    + (sent.body?.next ? ` Next: ${sent.body.next}` : ''));
  toast(`The intake of ${left.project} was finished with ${plural(sent.body.elements ?? left.parts, 'part')}.`);
  LIVE.left = null;
  drawLeft();
}
/* An agent outside Metaform, on the command line or over HTTP, holds no lock the page can read: a record made lately
 * is said as a fact before a Discard, never as a gate, cross-surface F3. */
const LATELY = 15 * 60 * 1000;
function lateRecorder(left) {
  const at = left.last ? Date.parse(left.last) : NaN;
  if (!(Date.now() - at < LATELY)) return [];
  return [`An agent may still be recording it from the command line or over HTTP: its last record was ${
    ago(left.last) === 'now' ? 'just now' : `${ago(left.last)} ago`}`];
}
/* The intake left unfinished, dropped after the person confirms, as `metaform intake discard --confirm` does. */
async function discardLeft(left) {
  if (!await confirmAct({title: 'Discard the unfinished intake?',
    text: `The intake in layer ${left.layer.name} of base ${left.base} is removed.`,
    lost: [`The ${plural(left.parts, 'part')} it recorded`,
      ...(left.active ? [] : [`The base ${left.base}, opened for this intake alone; a copy is kept`]),
      ...lateRecorder(left)],
    kept: ['Every other base and its map', 'The project, its settings and its tickets'],
    verb: 'Discard it', cancel: 'Keep it'})) return;
  const sent = await posted('/api/intake-discard', {confirm: true});
  if (!sent.ok) return toast(`${sent.body?.error || 'The intake was not discarded.'}`
    + (sent.body?.next ? ` Next: ${sent.body.next}` : ''));
  toast(`The unfinished intake of ${left.project} was discarded.`);
  LIVE.left = null;
  drawLeft();
}
/* When an intake the page followed finishes, one card over the map offers the next step, CLI-041: an agent on a
 * ticket, from the board, or a chat with the system agent. Either choice, or its ×, puts it away. */
export function offerNext() {
  $('#nextStep')?.remove();
  const card = h('div', {id: 'nextStep', class: 'nextcard', role: 'status'},
    h('p', {class: 'text'}, `The map of ${S.project} is ready. What next?`),
    h('div', {class: 'acts'},
      h('button', {class: 'btn primary', type: 'button', onclick: () => { card.remove(); $('#boardBtn').click(); }},
        'Start an agent on a ticket'),
      h('button', {class: 'btn', type: 'button', onclick: () => { card.remove(); dockState('open'); }},
        'Chat with your system agent'),
      h('button', {class: 'x', type: 'button', title: 'Dismiss', 'aria-label': 'Dismiss',
        onclick: () => card.remove()}, '×')));
  document.body.append(card);
}

/* A write whose refusal the page shows in place, with its next step, rather than in a toast. */
export async function posted(path, given) {
  try {
    const response = await reach(path, {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({project: S.project, base: S.base, ...given})}, 0);
    const body = await response.json().catch(() => ({error: 'The server did not answer with JSON.'}));
    return {ok: response.ok, status: response.status, body};
  } catch (error) { return {ok: false, status: 0, body: {error: error.message}}; }
}
