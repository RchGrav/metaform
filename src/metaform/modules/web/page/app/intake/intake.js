/* The intake started from the page, VIEW-045 and BASE-039: its agent, its bar over the map, its chat, start and
 * stop, and an empty project's prompt. */
import '/page/app/session/settings.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {overlay} from '/page/app/core/overlays.js';
import {toast, confirmAct} from '/page/app/core/controls.js';
import {S, MEM, reach, read} from '/page/app/core/reads.js';
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
import {LIVE} from '/page/app/live/stream.js';

/* ---------- the intake, started from the page, VIEW-045 and BASE-039 ----------
 * An agent the person chooses runs the project's intake and records the map as it goes; the page follows the intake
 * being recorded, so the map grows here. A project with no map offers it first; Administration offers it again, to map
 * the project anew or to check the map against it. While it runs, a bar over the map says so, with its chat and Stop.
 * Its work id, `intake-…`, is never a ticket. */
export const INTAKE = {work: null, session: null, agent: null, waiting: 0, reading: false, started: null};
const STARTING = 180000;  // how long an intake's launch may take before its session is made, dispatch's STALE_START
const INTAKE_KEY = project => `metaform.intake.${project}`;
function keptIntake(project = S.project) {
  try { return localStorage.getItem(INTAKE_KEY(project)); } catch { return null; }
}
function keepIntake(work, project = S.project) {
  try {
    if (work) localStorage.setItem(INTAKE_KEY(project), work);
    else localStorage.removeItem(INTAKE_KEY(project));
  } catch { /* storage can be blocked; the sessions read finds a running intake all the same */ }
}
export const intakeRunning = () => Boolean(INTAKE.session && INTAKE.session.state === 'running');
/* The intake agent of this project: a running intake session among those read, or the one this page started, read by
 * its id wherever it is kept, since an intake that activates a new metaform keeps its session in the one it began in.
 */
export async function readIntake(signals = []) {
  const project = S.project;
  let session = D.sessions.filter(one => isIntake(one.work_id) && one.state === 'running').at(-1) || null;
  const kept = keptIntake(project);
  // launched by this page and not yet made: its runner is starting, so it is shown as starting until its session is
  // made or its launch would have been given up
  const launching = INTAKE.started && INTAKE.started.project === project && Date.now() - INTAKE.started.at < STARTING
    ? INTAKE.started : null;
  if (!session && kept && !INTAKE.reading) {
    const found = await keptSession(kept, project, launching);
    if (!found) return;
    session = found.session;
    signals = [...signals, ...found.signals];
  }
  if (S.project !== project) return;
  if (session) INTAKE.started = null;
  else if (launching) {
    session = {work_id: launching.work, agent: launching.agent, state: 'running', session_id: null, activity: null};
  }
  INTAKE.session = session;
  INTAKE.work = session?.work_id || null;
  INTAKE.agent = session?.agent || null;
  INTAKE.waiting = session ? signals.filter(one => WAITS_ON_PERSON.includes(one.signal) && one.active !== false
    && one.work_id === session.work_id).length : 0;
  // what the intake's guard and its runner say of it, such as no first record yet or reading earlier conclusions
  INTAKE.signals = session ? signals.filter(one => one.active !== false && one.work_id === session.work_id
    && !WAITS_ON_PERSON.includes(one.signal)) : [];
  drawIntake();
}
/* The intake session this page kept the id of, read wherever it is kept; none once it no longer runs, and then its id
 * is forgotten unless its launch is still under way. Nothing when the page has left the project meanwhile. */
async function keptSession(kept, project, launching) {
  INTAKE.reading = true;
  let session = null, signals = [];
  try {
    const found = await read('dispatch-sessions', {id: kept, thread: 'false'});
    if (S.project !== project) return null;
    session = (found.sessions || []).at(-1) || null;
    signals = found.signals || [];
    if (session && session.state !== 'running') session = null;
    if (!session && !(launching && launching.work === kept)) keepIntake(null, project);
  } catch { session = null; } finally { INTAKE.reading = false; }
  return {session, signals};
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
/* The bar over the map while an intake runs or is being recorded: what is happening, its agent, and its acts. */
export function drawIntake() {
  const bar = $('#intakeBar');
  const running = intakeRunning(), recording = LIVE.layer !== null;
  bar.hidden = !(running || recording);
  drawEmpty();
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
  const doing = INTAKE.waiting ? `${agentName(INTAKE.agent)} waits for your permission`
    : recording ? `Recording ${LIVE.layer} · ${plural(parts, 'part')} so far`
    : firstWait || (activity === 'working' ? 'Reading the project'
      : activity === 'idle' && INTAKE.session?.session_id ? 'Idle · its turn has ended, and nothing is being recorded'
        : 'Starting');
  bar.classList.toggle('asks', INTAKE.waiting > 0);
  const said = (INTAKE.signals || []).map(signalChip);
  const outside = `Recording ${LIVE.layer} · ${plural(parts, 'part')} so far · by an agent outside the page`;
  fill(bar, h('span', {class: 'pulse', 'aria-hidden': 'true'}),
    h('span', {class: 'what'}, h('b', {}, running ? `Intake · ${agentName(INTAKE.agent)}` : 'Intake'),
      h('span', {class: 'doing'}, running ? doing : outside),
      said.length ? h('span', {class: 'signals'}, said) : null),
    ...intakeActs(running));
}
const intakeSignal = signal => Object.hasOwn(INTAKE_SIGNALS, signal) ? INTAKE_SIGNALS[signal] : undefined;
/* A signal on the intake's bar: its words, its status, and why, as the signal itself says it or else as named here. */
const signalChip = one => h('span', {class: `statechip ${intakeSignal(one.signal)?.[1] || 'waiting'}`,
  title: one.detail || one.message || one.reason || intakeSignal(one.signal)?.[2] || ''},
intakeSignal(one.signal)?.[0] || String(one.signal || '').replace(/-/g, ' '));
/* While it runs: its chat, or Answer while it waits on the person, and Stop; recorded from outside: Take over. */
function intakeActs(running) {
  if (!running) {
    return [null, h('button', {class: 'btn sm', type: 'button',
      title: 'Start an agent that goes on with this intake, once no agent is still recording it',
      onclick: () => openIntake({resume: true})}, 'Take over…')];
  }
  return [h('button', {class: `btn sm ${INTAKE.waiting ? 'primary' : ''}`, type: 'button',
    onclick: () => openIntakeChat()}, INTAKE.waiting ? 'Answer' : 'Chat'),
  h('button', {class: 'btn sm danger', type: 'button', onclick: stopIntake}, 'Stop')];
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
  if (await wrote('/api/dispatch-stop', {work_id: work, ...(session ? {session} : {})})) {
    if (session) rememberStop(session, new Date().toISOString());
    toast('The intake agent was stopped.');
    keepIntake(null);
    INTAKE.started = null;
    await renderAgents();
  }
}
/* The window an intake starts from: the agent, an optional note for it, and Start; a refusal is said with its next
 * step, and the step offered as a button where the page can take it: taking over an intake left being recorded, or
 * opening the one already at work. */
export async function openIntake({resume = false} = {}) {
  showAdmin(false);
  const box = $('#intake'), mapped = !noMetaform() && S.elements.size > 0;
  if (intakeRunning() && !resume) {
    openIntakeChat();
    return toast(`An intake is running: ${agentName(INTAKE.agent)}. Its chat is open.`);
  }
  $('#intake .title').textContent = mapped ? `Run the intake again · ${S.project}` : `Map ${S.project}`;
  fill($('#intake .lead'), mapped
    ? `An agent runs the intake on ${S.project} as it is now and records what it finds. `
      + 'The map follows it as it records.'
    : `An agent reads ${S.project} and records its map as it goes. You watch the map grow here, part by part.`);
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
  $('#intake .start').textContent = resume ? 'Take over the intake' : 'Start the intake';
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
  const sent = await posted('/api/dispatch-intake',
    {agent, text: note.value.trim() || undefined, resume: INTAKE.resume || undefined});
  button.disabled = false;
  if (!sent.ok) return showIntakeRefusal(sent.body);
  const started = sent.body;
  $('#intake').hidden = true;
  note.value = '';
  keepIntake(started.work_id);
  INTAKE.started = {project: S.project, work: started.work_id, agent: started.agent, at: Date.now()};
  INTAKE.work = started.work_id;
  INTAKE.agent = started.agent;
  INTAKE.session = {work_id: started.work_id, agent: started.agent, state: 'running', session_id: started.session_id,
    activity: null};
  drawIntake();
  toast(`${agentName(started.agent)} is starting on the intake. The map grows here as it records.`);
  await renderAgents();
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
  $('#intake .start').textContent = 'Take over the intake';
  fill(box); box.hidden = true;
  $('#intake .start').focus();
}
/* The intake already at work: its chat opened in place of a second one. */
function openRunning(work) {
  $('#intake').hidden = true;
  INTAKE.work = work;
  openIntakeChat(work, null);
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
/* The first screen, onboard/welcome.js, set by that later part: given whether the project has no map and whether the
 * page has finished reading it, it shows the welcome in place of the card below, or a map's first hints, and says
 * whether the welcome shows. */
export const FIRST = {drawn: null};
/* A project with no map yet says so over the map, with the intake as the one thing to do; the welcome takes its place
 * while the person has not chosen the workbench. */
export function drawEmpty() {
  const panel = $('#p-object > .emptypanel');
  if (panel) emptyActs(panel);
  const settled = !S.loading && !S.opening;
  const empty = settled && S.project && !S.elements.size && LIVE.layer === null && !intakeRunning() && !MEM.key;
  const welcomed = Boolean(FIRST.drawn?.(Boolean(empty), settled));
  $('#emptyStage').hidden = !empty || welcomed;
  if (!empty || welcomed) return;
  fill($('#emptyStage .what'), noMetaform() ? `${S.project} has no map yet.` : `${S.project}'s map is empty.`);
}
$('#emptyStage .start').onclick = () => openIntake();
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
