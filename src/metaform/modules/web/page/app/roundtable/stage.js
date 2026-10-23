/* The roundtable stage, a mode of the 3D map (code.interface.graphical#131): the person brings a question to a table
 * of agents, about the part of the map they have selected or about nothing on the map at all, and watches the table
 * debate it in front of them until it is answered; its result and saved record stay on the stage. The table itself runs in the Roundtable 2 engine through the roundtables module (code.gateway.messaging#3);
 * this part is what the person sees of it.
 *
 * Entering it, from the Roundtable button of the selected part or the T key, the person asks their question, keeps the
 * last lineup or project defaults (roundtables_seats), or picks their own seats, and starts. The 3D map
 * sinks back, dimmed, pushed away and softly blurred, and goes on moving behind the stage. On the stage each seat is a figure, its agent's character, in a
 * shallow arc across the screen, facing the person, its name under it. The seat with the floor steps forward and says
 * its turn in a word bubble whose tail points at it; each bubble expires by its words, independently of the floor;
 * the seat that speaks next
 * raises its hand; a seat lost dims and says why. Above the arc the table's state grows as it goes: the ideas the
 * synthesizer names, each seat's ranking of them, and the host's summary, the answer to the question. Along the bottom
 * are the question, the table's state and the whole transcript. After discussion ends, follow-through shows each
 * stage's full output and question. The person decides before the next stage starts unless automated ticket creation
 * was selected. Plan review offers comments,
 * revision and approval. Leaving restores the map while the table continues. Returning restores its stage.
 * With reduced motion the figures stand still and
 * nothing moves into place: everything is shown, only the movements are skipped.
 *
 * The table's events reach the page as map.changed of the kinds `roundtables` and `roundtables:<table>`, `tableChange`:
 * the stage reads its own table's events after the last it holds, once for a burst, and nothing else. Each frame of
 * the 3D map runs the stage's frame, `stageFrame`, from the bubbles' (figures/bubble3d.js SEATS), so a seat's head is
 * placed in the same frame its bubble is drawn: it allocates nothing and reads no layout, the stage's place on the page
 * coming from its resize observer; the seats' state is one typed array per field, the labels are written in one pass,
 * each only when it changed, and the figures are kept by character, made once and reused. */
import '/page/app/agents/broadcast.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
import {createAgent, drawGlyph, releaseGlyph, eyeOf, orientAgent} from '/page/agents3d.js';
import {$, h, fill, reduced} from '/page/app/core/dom.js';
import {toast} from '/page/app/core/controls.js';
import {S, read} from '/page/app/core/reads.js';
import {agentName, pickerOptions} from '/page/app/agents/pickers.js';
import {posted} from '/page/app/intake/intake.js';
import {G, wake3d} from '/page/app/map3d/graph3d.js';
import {SEATS, Seated, LOOK, bubbleText} from '/page/app/figures/bubble3d.js';
import {bubbleSeconds} from '/page/app/figures/bubble.js';
import {glyphOfType} from '/page/app/figures/walk.js';
import {swap} from '/page/app/camera/flight.js';
import {calledOf} from '/page/app/board/messages.js';
import {wrote} from '/page/app/board/history.js';
import {getJson} from '/page/app/panel/prompts.js';
import {WS} from '/page/app/workspace/workspace.js';

/* The table on the stage: its id and the kind its changes carry, where it was raised, its question, the last event
 * read, its state and stage, its seats by name and as opened, who has the floor and who speaks next, and whether the
 * stage is shown; `busy` and `again` hold a read and the changes heard during it. */
export const TABLE = {on: false, id: null, kind: '', address: '', topic: '', seq: 0, state: '', stage: '',
  names: [], seats: [], floor: -1, next: -1, ended: false, busy: false, again: false, swapped: false};
const ARC = {fov: 38, far: 10, depth: 0.35, spread: 0.8, low: 0.36, step: 1.25, grow: 0.12, sink: 0.25, dim: 0.35,
  veto: 2200, dwell: 1500, behind: 3, ease: 0.16};  // ms: presentation spacing after a vetoed or accepted turn;
// turns waiting past which the older ones are only written down; s: the time constant of a seat's moves
/* The events read and not yet told, told in order, `tell`: a read can bring several turns at once, after a hold or on
 * a busy page, and each turn holds the floor at least `dwell`, a vetoed one `veto`, so none is skipped; one that
 * has `behind` turns after it is only written in the transcript. Pacing, not a look for a change: each wait fires once
 * for the turn it shows. */
const TOLD = {list: [], at: 0, timer: 0};
/* The seats, one typed array per field, by seat: where it stands, how far it has stepped forward and raised its hand,
 * its size, whether it is lost, and when its bubble expires; grown only as a table opens. */
const SEAT = {n: 0, x: new Float32Array(8), y: new Float32Array(8), z: new Float32Array(8), step: new Float32Array(8),
  hand: new Float32Array(8), lost: new Uint8Array(8), until: new Float64Array(8), size: 1,
  meshes: [], glyphs: [], why: [], labels: [], lx: new Float32Array(8), ly: new Float32Array(8),
  shown: new Uint8Array(8)};
const MADE = new Map();  // each character's figure, made the first time a seat is one and kept for every table after
const HEAD = new THREE.Vector3(), GAZE = new THREE.Vector3(), AHEAD = new THREE.Vector3(), FEET = new THREE.Vector3();
const MOVE = {speed: 0, stride: 0, state: 'idle'}, POSE = {busy: 0, move: MOVE};  // what each figure is told a frame
const CLOCK = {last: 0};
/* The stage's own picture over the 3D map: its scene, camera and renderer, made the first time it opens, and where its
 * canvas is on the page, kept by its resize observer. */
const VIEW = {renderer: null, scene: null, camera: null, left: 0, top: 0, right: 0, bottom: 0, width: 0, height: 0};
const PIPELINE = {value: null, reviewed: '', text: '', version: 0, reading: false, writing: false};
const CHAIR = {writing: false};
const LINEUP = {project: null, saving: false};

/* ---------- the stage's elements, made with the page ---------- */
const UI = {};
UI.ideas = h('ol', {class: 'rt-list'});
UI.rankings = h('ul', {class: 'rt-list'});
UI.answer = h('p', {class: 'rt-answertext'});
UI.ideasBox = h('section', {class: 'rt-ideas', hidden: true}, h('h3', {}, 'Ideas'), UI.ideas);
UI.rankingsBox = h('section', {class: 'rt-rankings', hidden: true}, h('h3', {}, 'Rankings'), UI.rankings);
UI.answerBox = h('section', {class: 'rt-answer', hidden: true}, h('h3', {}, 'Answer'), UI.answer);
UI.results = h('section', {class: 'rt-results', hidden: true});
UI.records = h('section', {class: 'rt-records', hidden: true}, h('h3', {}, 'Saved record'));
UI.pipelineState = h('p', {class: 'rt-pipeline-state', role: 'status'});
UI.pipelineError = h('p', {class: 'rt-pipeline-error', hidden: true});
UI.pipelineLink = h('a', {class: 'rt-pipeline-link', target: '_blank', rel: 'noopener'}, 'Open saved output');
UI.review = h('button', {class: 'btn sm rt-review', type: 'button', onclick: reviewPipeline}, 'Load full output');
UI.yes = h('button', {class: 'btn sm rt-yes', type: 'button', onclick: () => decidePipeline('yes')}, 'Yes');
UI.no = h('button', {class: 'btn sm rt-no', type: 'button', onclick: () => decidePipeline('no')}, 'No, stop');
UI.approve = h('button', {class: 'btn sm rt-approve', type: 'button', onclick: () => decidePipeline('approve')},
  'Approve');
UI.comment = h('textarea', {class: 'rt-comment', 'aria-label': 'Plan comments', placeholder: 'Plan comments'});
UI.sendComment = h('button', {class: 'btn sm rt-send-comment', type: 'button',
  onclick: () => decidePipeline('comment')}, 'Save comment');
UI.revise = h('button', {class: 'btn sm rt-revise', type: 'button', onclick: () => decidePipeline('revise')},
  'Send back to Planner');
UI.pipelineText = h('div', {class: 'rt-pipeline-text', hidden: true, style: {'white-space': 'pre-wrap'}});
UI.pipelineQuestion = h('p', {class: 'rt-pipeline-question'});
UI.pipeline = h('section', {class: 'rt-pipeline', hidden: true}, h('h3', {}, 'Follow-through'), UI.pipelineState,
  UI.pipelineError, UI.pipelineLink, UI.review, UI.pipelineText, UI.pipelineQuestion, UI.comment, UI.sendComment,
  UI.revise, UI.yes, UI.approve, UI.no);
UI.board = h('div', {class: 'rt-board', 'aria-live': 'polite'}, UI.ideasBox, UI.rankingsBox, UI.results,
  UI.answerBox, UI.records, UI.pipeline);
UI.canvas = h('canvas', {class: 'rt-canvas', 'aria-hidden': 'true'});
UI.seats = h('div', {class: 'rt-seats'});
UI.band = h('div', {class: 'rt-band'}, UI.canvas, UI.seats);
UI.topic = h('b', {class: 'rt-question'});
UI.state = h('span', {class: 'rt-state', role: 'status'});
UI.leave = h('button', {class: 'btn sm quiet rt-leave', type: 'button', onclick: () => leaveStage(),
  title: 'Back to the map; the table runs on (Escape)'}, 'Leave');
UI.newTable = h('button', {class: 'btn sm quiet rt-new', type: 'button', hidden: true,
  onclick: () => openRoundtable(true)}, 'New table');
UI.hold = h('button', {class: 'btn sm rt-hold', type: 'button', hidden: true,
  onclick: () => chairControl(TABLE.state === 'held' ? 'continue' : 'hold')}, 'Hold');
UI.discussionComment = h('textarea', {class: 'rt-discussion-comment', rows: 2,
  'aria-label': 'Discussion comment', placeholder: 'Add to the discussion', oninput: renderChair});
UI.sendDiscussion = h('button', {class: 'btn sm', type: 'submit'}, 'Send comment');
UI.discussion = h('form', {class: 'rt-discussion', hidden: true,
  onsubmit: event => { event.preventDefault(); chairControl('comment'); }},
  UI.discussionComment, UI.sendDiscussion,
  h('small', {}, 'Comments enter at the next gap. Hold pauses AI turns. Continue resumes them.'));
UI.transcript = h('ol', {class: 'rt-transcript', tabindex: '0', 'aria-label': 'The transcript'});
UI.foot = h('div', {class: 'rt-foot'}, h('div', {class: 'rt-head'}, UI.topic, UI.state, UI.hold, UI.newTable, UI.leave),
  UI.transcript, UI.discussion);
UI.question = h('textarea', {rows: 3, 'aria-label': 'Your question to the table',
  placeholder: 'What should the table answer?'});
UI.seatList = h('ol', {class: 'rt-seatlist', 'aria-label': 'The seats, in speaking order'});
UI.addSeat = h('button', {type: 'button', class: 'btn sm quiet', onclick: () => addSeat('claude/opus')}, 'Add a seat');
UI.saveParticipants = h('button', {type: 'button', class: 'btn sm quiet', onclick: saveParticipants},
  'Save participants');
UI.where = h('span', {class: 'rt-where'});
UI.replyLimit = h('input', {type: 'number', min: 1, max: Number.MAX_SAFE_INTEGER, step: 1, value: 512,
  name: 'reply_limit', required: true});
UI.automate = h('input', {type: 'checkbox', name: 'automate_ticket_creation',
  'aria-describedby': 'rt-automate-description'});
UI.start = h('button', {class: 'btn primary rt-start', type: 'submit'}, 'Start');
UI.setup = h('form', {class: 'rt-setup', onsubmit: event => { event.preventDefault(); startTable(); }},
  h('h2', {}, 'Roundtable', UI.where), UI.question,
  h('div', {class: 'rt-seatsetup'}, 'Seats', UI.seatList, UI.addSeat, UI.saveParticipants,
    h('small', {}, 'Start remembers this browser’s lineup. Save participants sets this project’s defaults.')),
  h('label', {}, 'Maximum reply length (characters)', UI.replyLimit),
  h('small', {}, 'Applies to each discussion reply.'),
  h('label', {style: {display: 'flex', 'align-items': 'center', gap: '8px'}}, UI.automate,
    'Automate Ticket Creation'),
  h('small', {id: 'rt-automate-description'},
    'Run preparation without decisions. Populate a new inactive board for later review.'),
  h('div', {class: 'rt-setupacts'}, UI.start, h('button', {class: 'btn quiet', type: 'button',
    onclick: () => leaveStage()}, 'Cancel')));
UI.root = h('div', {id: 'roundtable', class: 'roundtable', hidden: true, role: 'region', 'aria-label': 'Roundtable'},
  UI.board, UI.band, UI.foot, UI.setup);
/* Escape leaves the stage wherever the focus is, but in the chat, a window or a menu, which take their own Escape;
 * heard first, so the map does not also let go of its selection. */
addEventListener('keydown', event => {
  if (!TABLE.on || event.key !== 'Escape' || event.target.closest?.('#dock, .window, .menu')) return;
  event.stopPropagation();
  event.preventDefault();
  leaveStage();
}, true);
new ResizeObserver(placed).observe(UI.canvas);
addEventListener('resize', placed, {passive: true});

/* ---------- entering and leaving ---------- */
/* The stage opened: the table it shows still running, or the question asked for a new one, focused on the selected
 * part when there is one and on nothing when there is none. */
export async function openRoundtable(fresh = false) {
  if (!G) { toast('The roundtable is a mode of the 3D map, which this page does not draw.'); return; }
  if (TABLE.id && fresh !== true) { showStage(); UI.setup.hidden = true; readTable(true); return; }
  const entry = S.selected ? S.elements.get(S.selected) : null;
  TABLE.address = entry ? entry.element.address : '';
  UI.where.textContent = entry ? ` on ${calledOf(S.selected) || TABLE.address}` : '';
  resetTable();
  showStage();
  UI.setup.hidden = false;
  UI.automate.checked = false;
  UI.start.disabled = false;
  UI.question.focus();
  const project = S.project;
  try {
    const found = await getJson(`/api/roundtable?project=${encodeURIComponent(project)}`);
    if (project !== S.project) return;
    OFFERED.clear();  // each agent's models read again, as it offers them now
    if (LINEUP.project !== project || !UI.seatList.children.length) {
      fill(UI.seatList);
      LINEUP.project = project;
      for (const seat of rememberedParticipants(project, found.seats || [])) addSeat(String(seat));
    }
  } catch (error) { toast(error.message); }
}
function showStage() {
  if (!TABLE.on && !WS.on && $('.app').classList.contains('swapped')) { TABLE.swapped = true; swap(false, false); }
  TABLE.on = true;
  const view = $('#big3d .view3d');
  if (UI.root.parentElement !== view) view.append(UI.root);
  UI.root.hidden = false;
  $('#big3d').classList.add('roundtable');  // the map sinks back, app.css, and goes on moving behind
  made();
  SEATS.on = true;
  SEATS.frame = stageFrame;
  CLOCK.last = performance.now();
  placed();
  wake3d();
}
/* Back to the map as it was: the stage hidden, the map brought forward, its figures' bubbles back; the table runs
 * on. */
export function leaveStage() {
  if (!TABLE.on) return;
  toldAll();
  TABLE.on = false;
  SEATS.on = false;
  UI.root.hidden = true;
  $('#big3d').classList.remove('roundtable');  // the seats stay in the stage's scene, which is not drawn while away
  if (TABLE.swapped) { TABLE.swapped = false; swap(true, false); }
  if (TABLE.ended || !TABLE.id) unseat();
  wake3d();
}
function resetTable() {
  toldAll();
  unseat();
  Object.assign(TABLE, {id: null, kind: '', topic: '', seq: 0, state: '', stage: '', names: [], seats: [], floor: -1,
    next: -1, ended: false});
  fill(UI.ideas); fill(UI.rankings); fill(UI.results); fill(UI.transcript);
  fill(UI.records, h('h3', {}, 'Saved record'));
  UI.results.hidden = UI.records.hidden = UI.newTable.hidden = true;
  Object.assign(PIPELINE, {value: null, reviewed: '', text: '', version: PIPELINE.version + 1, reading: false,
    writing: false});
  renderPipeline();
  UI.answer.textContent = '';
  UI.ideasBox.hidden = UI.rankingsBox.hidden = UI.answerBox.hidden = true;
  UI.topic.textContent = ''; UI.state.textContent = '';
  UI.discussionComment.value = '';
  renderChair();
}
/* The seats' characters given back, so the agents at work may take them again. */
function unseat() {
  for (let n = 0; n < SEAT.n; n++) {
    releaseGlyph(seatKey(n));
    shade(SEAT.meshes[n], 1);
    VIEW.scene?.remove(SEAT.meshes[n]);
    SEATS.list[n].want = 0;
  }
  SEAT.n = 0;
  for (const label of SEAT.labels) label.el.hidden = true;
}
const seatKey = n => `roundtable:${TABLE.id}:${n}`;

/* The question asked: the table opened, on the part when there is one, with the seats as the person left them, then
 * followed. */
async function startTable() {
  const topic = UI.question.value.trim();
  if (!topic) { toast('Ask the table a question.'); UI.question.focus(); return; }
  const listed = seatsChosen();
  const replyLimit = Number(UI.replyLimit.value);
  if (!Number.isSafeInteger(replyLimit) || replyLimit < 1) { UI.replyLimit.reportValidity(); return; }
  if (listed.length) rememberParticipants(S.project, listed);
  UI.start.disabled = true;
  UI.state.textContent = 'Opening the table: its seats are starting…';
  UI.topic.textContent = topic;
  const answer = await wrote('/api/roundtable-open', {topic, reply_limit: replyLimit,
    automate_ticket_creation: UI.automate.checked,
    ...(TABLE.address ? {address: TABLE.address} : {}),
    ...(listed.length ? {seats: listed} : {})});
  UI.start.disabled = false;
  if (!answer) { UI.state.textContent = ''; return; }
  TABLE.id = answer.table;
  TABLE.kind = `roundtables:${answer.table}`;
  TABLE.topic = topic;
  UI.setup.hidden = true;
  await readTable(true);
}

/* ---------- the seats ---------- */
/* Each seat an agent picker and a model picker. Metaform's agents list their models as every model picker does,
 * `pickerOptions`: the short names, such as sol, which follow the newest release of their family when the table
 * opens, then each exact value under Specific version. Any other seat is an OpenRouter model id, typed. An agent that
 * has not run here has no list yet: its model is typed and checked as the table opens, and Read its list starts it
 * once, with no prompt, to read it. */
const SEAT_AGENTS = ['claude', 'codex', 'antigravity'];
const OFFERED = new Map();  // each agent's model picks, read once each time the stage opens
function addSeat(seat) {
  const [first, ...rest] = seat.replace(/^acp:/, '').split('/');
  const agent = SEAT_AGENTS.includes(first) && rest.length ? first : '';
  const who = h('select', {'aria-label': 'Agent', onchange: () => modelPicker(row, who.value, '')},
    SEAT_AGENTS.map(one => h('option', {value: one, selected: one === agent}, agentName(one))),
    h('option', {value: '', selected: !agent}, 'OpenRouter model'));
  const row = h('li', {class: 'rt-pick'}, who, h('span', {class: 'rt-model'}),
    h('button', {type: 'button', class: 'btn sm quiet', title: 'Remove this seat', 'aria-label': 'Remove this seat',
      onclick: () => row.remove()}, '×'));
  UI.seatList.append(row);
  modelPicker(row, agent, agent ? rest.join('/') : seat);
}
async function modelPicker(row, agent, model) {
  const box = row.querySelector('.rt-model');
  if (!agent) {
    fill(box, h('input', {type: 'text', value: model, 'aria-label': 'OpenRouter model id', spellcheck: 'false',
      placeholder: 'deepseek/deepseek-v4.1-flash'}));
    return;
  }
  if (!OFFERED.has(agent)) {
    OFFERED.set(agent, read('dispatch-options', {agent}).then(found => (found.agents?.[0]?.settings || [])
      .find(one => one.key === 'model')).catch(() => null));
  }
  const offered = await OFFERED.get(agent);
  if (!row.isConnected || row.querySelector('select').value !== agent) return;
  // the agent's own default only where it offers one, as Claude's Default (recommended); the engine sends the value
  const picks = (offered?.picks || []).filter(one => one.value !== 'default'
    || (offered.choices || []).some(choice => choice.value === 'default'));
  if (!picks.length) {
    fill(box, h('input', {type: 'text', value: model, spellcheck: 'false', 'aria-label': `${agentName(agent)} model`,
      placeholder: 'opus', title: `${agentName(agent)} has not run here, so its models are not known yet`}),
    h('button', {type: 'button', class: 'btn sm quiet', title: 'Starts it once, with no prompt, and reads the models '
      + 'it offers', onclick: () => readModels(row, agent)}, 'Read its list'));
    return;
  }
  const listed = model && !picks.some(one => one.value === model)
    ? [{value: model, label: model, group: null, description: null}, ...picks] : picks;
  fill(box, h('select', {'aria-label': `${agentName(agent)} model`},
    pickerOptions(listed, model || picks.find(one => one.value !== 'default')?.value)));
}
async function readModels(row, agent) {
  toast(`Starting ${agentName(agent)} once to read its models…`);
  const done = await posted('/api/settings/choices', {key: `dispatch_${agent}_model`});
  if (!done.ok) { toast(done.body.error || 'Its models could not be read.'); return; }
  OFFERED.delete(agent);
  const typed = row.querySelector('.rt-model input')?.value.trim() || '';
  modelPicker(row, agent, typed);
}
/* The seats as `roundtables open` takes them, in speaking order: agent/model, or an OpenRouter id. */
function seatsChosen() {
  return [...UI.seatList.children].flatMap(row => {
    const agent = row.querySelector('select').value;
    const model = (row.querySelector('.rt-model select, .rt-model input')?.value || '').trim();
    if (!model) return [];
    return agent ? [`${agent}/${model}`] : model.split(/[,\s]+/).filter(Boolean);
  });
}
/* Last-started lineups belong to this browser and project. Explicit saving reuses the project setting. */
const lineupKey = project => `metaform.roundtable.participants.${project}`;
function rememberedParticipants(project, defaults) {
  try {
    const saved = JSON.parse(localStorage.getItem(lineupKey(project)));
    if (Array.isArray(saved) && saved.length && saved.every(seat => typeof seat === 'string' && seat.trim())) {
      return saved;
    }
  } catch { /* unavailable or invalid browser storage falls back to project defaults */ }
  return defaults;
}
function rememberParticipants(project, seats) {
  try { localStorage.setItem(lineupKey(project), JSON.stringify(seats)); }
  catch { toast('This browser could not remember the lineup. Use Save participants for project defaults.'); }
}
async function saveParticipants() {
  if (LINEUP.saving) return;
  const seats = seatsChosen(), project = S.project;
  if (!seats.length) { toast('Choose at least one participant.'); return; }
  LINEUP.saving = true;
  UI.saveParticipants.disabled = true;
  try {
    const saved = await wrote('/api/settings', {key: 'roundtables_seats', value: seats});
    if (!saved) return;
    rememberParticipants(project, seats);
    toast('Participants saved as this project’s roundtable defaults.');
  } finally { LINEUP.saving = false; UI.saveParticipants.disabled = false; }
}

/* ---------- the table's events ---------- */
/* A change written by the roundtables module alone, decided from the event: true when it is, so nothing else of the
 * page reads for it; the stage reads its table's events when the change names that table and the stage is shown. */
export function tableChange(payload) {
  const kinds = payload.kinds;
  if (!Array.isArray(kinds) || !kinds.length) return false;
  let mine = false;
  for (let at = 0; at < kinds.length; at++) {
    const kind = String(kinds[at]);
    if (kind !== 'roundtables' && !kind.startsWith('roundtables:')) return false;
    if (kind === TABLE.kind) mine = true;
  }
  if (mine && TABLE.on) readTable();
  return true;
}
/* The table's events after the last read, told in order; a change heard while a read runs reads once more after it. */
async function readTable(whole = false) {
  if (TABLE.busy) { TABLE.again = true; return; }
  TABLE.busy = true;
  try {
    do {
      TABLE.again = false;
      const id = TABLE.id;
      const found = await getJson(`/api/roundtable?project=${encodeURIComponent(S.project)}&table=${
        encodeURIComponent(id)}&after=${TABLE.seq}${whole || !SEAT.n ? '&whole=1' : ''}`);
      if (id !== TABLE.id) return;
      // State and final results show immediately; speaking turns keep their pacing.
      for (const event of found.events || []) {
        if (event.kind === 'state') stateIs(event.state, event.reason);
        else if (event.kind === 'end') ended(event);
        else if (event.kind === 'pipeline') pipelineIs(event.pipeline);
        else TOLD.list.push(event);
      }
      if (found.status) seated(found.status);
      TABLE.seq = Math.max(TABLE.seq, found.latest || 0);
      tell();
    } while (TABLE.again);
  } catch (error) { toast(error.message); }
  finally { TABLE.busy = false; }
}
function tell() {
  if (TOLD.timer) return;
  while (TOLD.at < TOLD.list.length) {
    const event = TOLD.list[TOLD.at++];
    heard(event);
    if ((event.kind !== 'turn' && event.kind !== 'veto') || turnsAfter() >= ARC.behind) continue;
    TOLD.timer = setTimeout(() => { TOLD.timer = 0; tell(); }, event.kind === 'veto' ? ARC.veto : ARC.dwell);
    return;
  }
  TOLD.list.length = 0;
  TOLD.at = 0;
}
function turnsAfter() {
  let count = 0;
  for (let at = TOLD.at; at < TOLD.list.length; at++) {
    if (TOLD.list[at].kind === 'turn' || TOLD.list[at].kind === 'veto') count++;
  }
  return count;
}
/* Every event read told at once, the floor left where the last turn puts it: as the stage is left or a table reset. */
function toldAll() {
  clearTimeout(TOLD.timer);
  TOLD.timer = 0;
  while (TOLD.at < TOLD.list.length) heard(TOLD.list[TOLD.at++]);
  TOLD.list.length = 0;
  TOLD.at = 0;
}
/* The table as it opened: its question, its state, and a figure for each seat in its arc. */
function seated(status) {
  TABLE.topic = status.topic;
  UI.topic.textContent = status.topic;
  if (!SEAT.n) {
    TABLE.seats = status.seats || [];
    TABLE.names = status.seated || TABLE.seats.map(one => String(one).split('/').at(-1));
    seatAll();
  }
  if (status.state === 'ended') ended(status);
  else stateIs(status.state, status.reason);
}
function heard(event) {
  if (event.kind === 'turn' || event.kind === 'veto') return turn(event);
  if (event.kind === 'stage') { TABLE.stage = event.stage; if (event.stage !== 'discussion') TABLE.floor = -1; }
  else if (event.kind === 'ideas') ideas(event.ideas || []);
  else if (event.kind === 'rankings') rankings(event.rankings || []);
  else if (event.kind === 'summary') summary(event.text, event.name);
  else if (event.kind === 'seat_lost') lost(event);
  else if (event.kind === 'operational') said('rt-note', event.what || 'note', event.text || '');
  nextUp();
}
const seatOf = name => TABLE.names.indexOf(name) >= 0 ? TABLE.names.indexOf(name) : TABLE.seats.indexOf(name);
/* A turn: its seat takes the floor and says it; a vetoed one fades from its bubble and is struck in the transcript. */
function turn(event) {
  const n = seatOf(event.seat), vetoed = event.kind === 'veto';
  said(vetoed ? 'rt-turn vetoed' : 'rt-turn', event.seat, event.text || '',
    vetoed ? ` (vetoed${event.failed?.length ? `: ${event.failed.join(', ')}` : ''})`
      : event.outcome === 'unjudged' ? ' (never judged: the table ended first)' : '');
  if (n < 0 || TABLE.ended) return;
  TABLE.floor = n;
  const seat = SEATS.list[n];
  seat.text = bubbleText(event.text || '');
  seat.lineAt = performance.now();
  SEAT.until[n] = seat.lineAt + 1000 * bubbleSeconds(seat.text, WS.view()?.bubble_seconds ?? 'auto');
  nextUp();
}
/* Who speaks next while the table discusses: the seat after the floor in speaking order, any lost one skipped. */
function nextUp() {
  TABLE.next = -1;
  if (TABLE.ended || TABLE.state === 'held' || (TABLE.stage && TABLE.stage !== 'discussion') || !SEAT.n) return;
  for (let step = 1; step <= SEAT.n; step++) {
    const n = (TABLE.floor + step + SEAT.n) % SEAT.n;
    if (!SEAT.lost[n] && n !== TABLE.floor) { TABLE.next = n; return; }
  }
}
function ideas(listed) {
  fill(UI.ideas, listed.map(one => h('li', {'data-id': one.id}, h('b', {}, one.id), ' ', one.name || '',
    one.summary ? h('span', {class: 'rt-why'}, `: ${one.summary}`) : null)));
  UI.ideasBox.hidden = TABLE.ended || !listed.length;
}
function rankings(listed) {
  for (const one of listed) {
    UI.rankings.append(h('li', {'data-seat': one.name}, h('b', {}, one.name), ' ',
      (one.ranking || []).join(' › ')));
  }
  UI.rankingsBox.hidden = TABLE.ended || !UI.rankings.children.length;
}
function summary(text, name) {
  if (!text) return;
  if (!TABLE.ended) {
    UI.answer.textContent = text;
    UI.answerBox.querySelector('h3').textContent = name ? `Answer, from ${name}` : 'Answer';
    UI.answerBox.hidden = false;
  }
  said('rt-summary', name || 'Host', text);
}
function lost(event) {
  const n = seatOf(event.seat);
  said('rt-note', event.seat || 'A seat', event.text || event.what || 'left the table');
  if (n < 0) return;
  SEAT.lost[n] = 1;
  SEAT.why[n] = event.text || event.what || 'left the table';
  shade(SEAT.meshes[n], ARC.dim);
  if (TABLE.floor === n) TABLE.floor = -1;
}
function ended(event) {
  TABLE.ended = true;
  TABLE.floor = TABLE.next = -1;
  UI.ideasBox.hidden = UI.rankingsBox.hidden = true;
  UI.newTable.hidden = false;
  if (event.topics) {
    fill(UI.results, h('h3', {}, 'Topic results'), event.topics.map(topicResult));
    UI.results.hidden = !event.topics.length;
  }
  UI.answer.textContent = event.answer || 'The table ended without a final answer.';
  UI.answerBox.querySelector('h3').textContent = 'Final answer';
  UI.answerBox.hidden = false;
  if (event.saved) {
    const link = (file, label) => h('a', {href: `/api/roundtable?project=${encodeURIComponent(S.project)}&table=${
      encodeURIComponent(TABLE.id)}&file=${encodeURIComponent(file)}`, target: '_blank', rel: 'noopener'}, label);
    fill(UI.records, h('h3', {}, 'Saved record'), h('ul', {class: 'rt-list'},
      h('li', {}, link('export.json', 'Full transcript and export')),
      h('li', {}, link('mechanical-report.md', 'Mechanical report'))));
    UI.records.hidden = false;
  }
  if (event.pipeline) pipelineIs(event.pipeline);
  stateIs('ended', event.reason);
}
/* Each topic keeps its synthesis and the engine's Borda order; ranks follow that order, never a second tally. */
function topicResult(topic) {
  const listed = topic.synthesis?.ideas || [], borda = topic.borda;
  const byId = new Map(listed.map(idea => [idea.id, idea]));
  const ranked = borda?.order || [];
  return h('article', {class: 'rt-topic-result', 'data-topic': topic.number},
    h('h4', {}, `Topic ${topic.number}: ${topic.title || ''}`),
    h('ol', {class: 'rt-list'}, listed.map(idea => h('li', {'data-id': idea.id},
      h('b', {}, idea.name || idea.id), idea.summary ? `: ${idea.summary}` : ''))),
    ranked.length ? h('table', {class: 'rt-borda'}, h('caption', {}, 'Borda ranking'),
      h('thead', {}, h('tr', {}, h('th', {scope: 'col'}, 'Rank'), h('th', {scope: 'col'}, 'Idea'),
        h('th', {scope: 'col'}, 'Points'))),
      h('tbody', {}, ranked.map((id, rank) => h('tr', {'data-id': id}, h('td', {}, String(rank + 1)),
        h('td', {}, byId.get(id)?.name || id), h('td', {}, String(borda.points?.[id] ?? 0)))))) : null,
    topic.host_summary?.text ? h('p', {}, topic.host_summary.text) : null);
}
/* Each decision binds the full output's stage, revision and digest. Events never carry its body. */
const pipelineKey = pipeline => pipeline ? `${pipeline.stage}:${pipeline.revision}:${pipeline.digest}` : '';
function pipelineIs(pipeline, load = true) {
  const changed = pipelineKey(pipeline) !== pipelineKey(PIPELINE.value);
  if (changed) {
    PIPELINE.version++;
    PIPELINE.reviewed = ''; PIPELINE.text = ''; PIPELINE.reading = false;
    UI.comment.value = '';
  }
  PIPELINE.value = pipeline || null;
  renderPipeline();
  if (load && pipeline?.state === 'awaiting' && !PIPELINE.reviewed && !PIPELINE.reading && !PIPELINE.writing) {
    reviewPipeline();
  }
}
function renderPipeline() {
  const pipeline = PIPELINE.value;
  UI.pipeline.hidden = !pipeline;
  if (!pipeline) { UI.pipelineText.textContent = ''; UI.pipelineText.hidden = true; return; }
  const awaiting = pipeline.state === 'awaiting', busy = PIPELINE.reading || PIPELINE.writing;
  const plan = pipeline.stage === 'plan_review', approval = plan || pipeline.stage === 'execution_outline';
  const stage = {roundtable: 'Roundtable', research: 'Research', architecture: 'Architecture', intake: 'Intake',
    plan_review: 'Plan review', decomposition: 'Decomposition', execution_outline: 'Execution outline',
    facilitation: 'Facilitation'}[pipeline.stage] || pipeline.stage;
  UI.pipelineState.textContent = `${stage}: ${{pending: 'Preparing follow-through', awaiting: 'Awaiting your decision', running: 'Running',
    stopped: 'Stopped', completed: 'Completed'}[pipeline.state] || pipeline.state}`;
  UI.pipelineError.textContent = pipeline.error || '';
  UI.pipelineError.hidden = !pipeline.error;
  UI.pipelineQuestion.textContent = awaiting ? pipeline.question || '' : '';
  UI.pipelineLink.href = `/api/roundtable?project=${encodeURIComponent(S.project)}&table=${
    encodeURIComponent(TABLE.id)}&file=${encodeURIComponent((pipeline.file || '').split('/').at(-1))}`;
  UI.pipelineLink.hidden = !pipeline.file;
  UI.review.hidden = !awaiting || !!PIPELINE.reviewed;
  UI.review.disabled = busy;
  UI.yes.hidden = !awaiting || approval;
  UI.approve.hidden = !awaiting || !approval;
  UI.approve.textContent = plan ? 'Approve plan' : 'Approve execution outline';
  UI.no.hidden = !awaiting;
  UI.comment.hidden = UI.sendComment.hidden = UI.revise.hidden = !awaiting || !plan;
  const disabled = busy || !pipeline.digest || PIPELINE.reviewed !== pipelineKey(pipeline);
  UI.yes.disabled = UI.approve.disabled = UI.no.disabled = UI.comment.disabled = UI.sendComment.disabled
    = UI.revise.disabled = disabled;
  UI.pipelineText.textContent = PIPELINE.text;
  UI.pipelineText.hidden = !PIPELINE.reviewed;
}
async function reviewPipeline() {
  if (PIPELINE.value?.state !== 'awaiting' || PIPELINE.reading || PIPELINE.writing) return;
  const table = TABLE.id, version = PIPELINE.version;
  let applied = false;
  PIPELINE.reading = true;
  renderPipeline();
  try {
    const found = await getJson(`/api/roundtable?project=${encodeURIComponent(S.project)}&table=${
      encodeURIComponent(table)}&pipeline=1`);
    if (TABLE.id !== table || PIPELINE.version !== version) return;
    pipelineIs(found.pipeline, false);
    applied = true;
    if (found.pipeline?.state !== 'awaiting' || !found.pipeline.digest || typeof found.output_text !== 'string') return;
    PIPELINE.reviewed = pipelineKey(found.pipeline);
    PIPELINE.text = found.output_text;
  } catch (error) { toast(error.message); }
  finally { if (TABLE.id === table && (PIPELINE.version === version || applied)) {
    PIPELINE.reading = false; renderPipeline();
  } }
}
async function decidePipeline(action) {
  const pipeline = PIPELINE.value;
  if (pipeline?.state !== 'awaiting' || !pipeline.digest || PIPELINE.reviewed !== pipelineKey(pipeline)
    || PIPELINE.reading || PIPELINE.writing) return;
  const table = TABLE.id, version = PIPELINE.version;
  PIPELINE.writing = true;
  renderPipeline();
  try {
    const found = await wrote('/api/roundtable-decision', {table, action, digest: pipeline.digest,
      revision: pipeline.revision, comment: UI.comment.value});
    if (TABLE.id !== table || PIPELINE.version !== version) return;
    if (found?.pipeline) pipelineIs(found.pipeline, false);
    else if (!found) { PIPELINE.reviewed = ''; PIPELINE.text = ''; }
  } finally { if (TABLE.id === table) {
    PIPELINE.writing = false; renderPipeline();
    if (PIPELINE.value?.state === 'awaiting' && !PIPELINE.reviewed) reviewPipeline();
  } }
}
function renderChair() {
  const active = !!TABLE.id && (TABLE.state === 'running' || TABLE.state === 'held');
  UI.hold.hidden = UI.discussion.hidden = !active;
  UI.hold.textContent = TABLE.state === 'held' ? 'Continue' : 'Hold';
  UI.hold.disabled = CHAIR.writing;
  UI.discussionComment.disabled = CHAIR.writing;
  UI.sendDiscussion.disabled = CHAIR.writing || !UI.discussionComment.value.trim();
}
async function chairControl(action) {
  if (!TABLE.id || CHAIR.writing || !['running', 'held'].includes(TABLE.state)) return;
  const table = TABLE.id, text = UI.discussionComment.value;
  if (action === 'comment' && !text.trim()) return;
  CHAIR.writing = true;
  renderChair();
  try {
    const found = await wrote('/api/roundtable-control', {table, action,
      ...(action === 'comment' ? {text} : {})});
    if (!found || TABLE.id !== table) return;
    if (found.state) stateIs(found.state, found.reason);
    if (action === 'comment') {
      UI.discussionComment.value = '';
      toast('Comment queued for the next gap between turns.');
    }
  } finally { CHAIR.writing = false; renderChair(); }
}
function stateIs(state, reason) {
  TABLE.state = state || TABLE.state;
  const words = {running: 'The table is talking', held: 'Held', ended: 'Ended', ending: 'Ending', opening: 'Opening',
    refused: 'Refused'}[TABLE.state] || TABLE.state;
  UI.state.textContent = reason && TABLE.state !== 'running' ? `${words}: ${reason}` : words;
  UI.root.dataset.state = TABLE.state;
  renderChair();
}
/* One line of the transcript, whole, the newest kept in view unless the person has scrolled up to read. */
function said(kind, who, text, after = '') {
  const box = UI.transcript, bottom = box.scrollHeight - box.scrollTop - box.clientHeight < 24;
  box.append(h('li', {class: kind}, h('b', {}, who), ' ', text, after ? h('span', {class: 'rt-why'}, after) : null));
  if (bottom) box.scrollTop = box.scrollHeight;
}

/* ---------- the figures ---------- */
/* The stage's scene, camera and renderer, made once, the first time it opens. */
function made() {
  if (VIEW.renderer) return;
  VIEW.renderer = new THREE.WebGLRenderer({canvas: UI.canvas, alpha: true, antialias: true});
  VIEW.renderer.setClearColor(0x000000, 0);
  VIEW.scene = new THREE.Scene();
  VIEW.scene.add(new THREE.HemisphereLight(0xffffff, 0x445066, 1.6));
  const sun = new THREE.DirectionalLight(0xffffff, 2.2);
  sun.position.set(3, 6, 8);
  VIEW.scene.add(sun);
  VIEW.camera = new THREE.PerspectiveCamera(ARC.fov, 1, 0.1, 100);
  VIEW.camera.position.set(0, 0, ARC.far);
  VIEW.camera.lookAt(0, 0, 0);
}
/* A figure for each seat, its agent's character: the one the person chose for its agent's type when no other figure
 * has it, else one drawn from the seat, never two alike; then the arc laid out. */
function seatAll() {
  const count = TABLE.seats.length;
  grow(count);
  for (let n = 0; n < count; n++) {
    const seat = String(TABLE.seats[n]), agent = seat.replace(/^acp:/, '').split('/')[0];
    const glyph = drawGlyph(seatKey(n), null, glyphOfType(agent));
    if (!MADE.has(glyph)) MADE.set(glyph, createAgent(glyph, {harness: agent}));
    SEAT.meshes[n] = MADE.get(glyph);
    SEAT.glyphs[n] = glyph;
    SEAT.lost[n] = 0; SEAT.step[n] = 0; SEAT.hand[n] = 0; SEAT.until[n] = 0; SEAT.why[n] = '';
    shade(SEAT.meshes[n], 1);
    VIEW.scene.add(SEAT.meshes[n]);
    const one = SEATS.list[n];
    one.text = ''; one.want = 0; one.lineAt = 0; one.name = TABLE.names[n] || seat;
    const label = SEAT.labels[n];
    label.name.textContent = one.name;
    label.el.title = seat;
    label.el.hidden = false;
    SEAT.shown[n] = 255;
    SEAT.lx[n] = SEAT.ly[n] = NaN;
  }
  SEAT.n = count;
  arc();
  nextUp();
}
/* The pools grown to hold `count` seats: the typed arrays, the bubbles' seats and the name labels. */
function grow(count) {
  if (SEAT.x.length < count) {
    const size = Math.max(count, SEAT.x.length * 2);
    for (const field of ['x', 'y', 'z', 'step', 'hand', 'lx', 'ly']) SEAT[field] = new Float32Array(size);
    SEAT.lost = new Uint8Array(size); SEAT.shown = new Uint8Array(size); SEAT.until = new Float64Array(size);
  }
  while (SEATS.list.length < count) SEATS.list.push(new Seated(SEATS.list.length));
  while (SEAT.labels.length < count) {
    const label = {el: h('div', {class: 'rt-seat', hidden: true}), name: h('span', {class: 'rt-name'}),
      hand: h('span', {class: 'rt-hand', 'aria-label': 'waits to speak'}, '✋'), why: h('span', {class: 'rt-lost'})};
    label.el.append(label.hand, label.name, label.why);
    UI.seats.append(label.el);
    SEAT.labels.push(label);
  }
}
/* The seats in a shallow arc across the stage, the middle nearest and the ends a little farther back, low in the view
 * so their words have the room above them; each as large as the room between them allows. */
function arc() {
  const camera = VIEW.camera, tall = ARC.far * Math.tan(camera.fov * Math.PI / 360), wide = tall * camera.aspect;
  const count = SEAT.n, across = 2 * wide * ARC.spread, gap = count > 1 ? across / (count - 1) : across;
  const height = Math.min(gap * 0.55, tall * 0.42);
  SEAT.size = height / 1.6;
  for (let n = 0; n < count; n++) {
    const x = count > 1 ? -across / 2 + n * gap : 0, share = x / wide;
    SEAT.x[n] = x; SEAT.y[n] = -tall * ARC.low; SEAT.z[n] = -ARC.depth * wide * share * share;
  }
}
/* Where the stage's canvas is on the page, read as it changes size, never in a frame; the camera and the arc follow. */
function placed() {
  if (!VIEW.renderer || !TABLE.on) return;
  const box = UI.canvas.getBoundingClientRect();
  VIEW.left = box.left; VIEW.top = box.top; VIEW.right = box.right; VIEW.bottom = box.bottom;
  VIEW.width = box.width; VIEW.height = box.height;
  if (!box.width || !box.height) return;
  VIEW.renderer.setPixelRatio(window.devicePixelRatio || 1);
  VIEW.renderer.setSize(box.width, box.height, false);
  VIEW.camera.aspect = box.width / box.height;
  VIEW.camera.updateProjectionMatrix();
  VIEW.camera.updateMatrixWorld();
  if (SEAT.n) arc();
}
/* A figure dimmed to `k` of its colours, or back at 1: its materials' own colours kept the first time. Run when a seat
 * is lost or seated, never in a frame. */
function shade(mesh, k) {
  if (!mesh) return;
  if (!mesh.userData.shades) {
    const shades = [];
    mesh.traverse(part => {
      const material = part.material;
      if (material && material.color && !shades.some(one => one.material === material)) {
        shades.push({material, color: material.color.clone(),
          emissive: material.emissive ? material.emissiveIntensity : null});
      }
    });
    mesh.userData.shades = shades;
  }
  for (const one of mesh.userData.shades) {
    one.material.color.copy(one.color).multiplyScalar(k);
    if (one.emissive !== null) one.material.emissiveIntensity = one.emissive * k;
  }
}

/* ---------- each frame ---------- */
/* The stage's frame, run by the bubbles' frame of the 3D map just before the bubbles are placed: each seat eased to its
 * place, the floor's a step forward, facing the person; its head given to its bubble; the stage drawn; and the labels
 * written in one pass, each only where it changed. */
function stageFrame(now) {
  const passed = Math.min(0.1, Math.max(0, (now - CLOCK.last) / 1000));
  CLOCK.last = now;
  const still = reduced(), ease = still ? 1 : 1 - Math.exp(-passed / ARC.ease), camera = VIEW.camera;
  const size = SEAT.size, count = SEAT.n;
  for (let n = 0; n < count; n++) {
    const mesh = SEAT.meshes[n], floor = n === TABLE.floor;
    SEAT.step[n] += ((floor ? 1 : 0) - SEAT.step[n]) * ease;
    SEAT.hand[n] += ((n === TABLE.next ? 1 : 0) - SEAT.hand[n]) * ease;
    const step = SEAT.step[n];
    mesh.position.set(SEAT.x[n], SEAT.y[n] - (SEAT.lost[n] ? ARC.sink * size : 0), SEAT.z[n] + step * ARC.step * size);
    mesh.scale.setScalar(size * (1 + ARC.grow * step));
    AHEAD.subVectors(camera.position, mesh.position);
    orientAgent(mesh, AHEAD, 1);
    if (!still) {
      POSE.busy = floor ? 1 : 0;
      MOVE.state = SEAT.lost[n] ? 'sleep' : 'idle';
      mesh.userData.update(passed, POSE);
    }
    spoken(n, mesh, now);
  }
  if (VIEW.width) VIEW.renderer.render(VIEW.scene, camera);
  for (let n = 0; n < count; n++) label(n);
  wake3d(100);  // the map behind and the stage go on drawing every frame while the stage is shown
}
/* Each seat's words stay until their own expiry, even after the floor moves to another seat. */
function spoken(n, mesh, now) {
  const seat = SEATS.list[n], camera = VIEW.camera;
  seat.want = seat.text && now < SEAT.until[n] ? 1 : 0;
  eyeOf(mesh, HEAD, GAZE);
  HEAD.y += LOOK.lift * mesh.scale.x;
  seat.far = HEAD.distanceTo(camera.position);
  HEAD.project(camera);
  seat.x = VIEW.left + (HEAD.x + 1) / 2 * VIEW.width;
  seat.y = VIEW.top + (1 - HEAD.y) / 2 * VIEW.height;
  seat.left = VIEW.left; seat.top = VIEW.top; seat.right = VIEW.right; seat.bottom = VIEW.bottom;
}
/* A seat's name under its feet, its raised hand and why it was lost: written only when they change. */
function label(n) {
  const mesh = SEAT.meshes[n], one = SEAT.labels[n];
  FEET.copy(mesh.position);
  FEET.y -= 0.62 * mesh.scale.y;
  FEET.project(VIEW.camera);
  const x = Math.round((FEET.x + 1) / 2 * VIEW.width), y = Math.round((1 - FEET.y) / 2 * VIEW.height);
  if (x !== SEAT.lx[n] || y !== SEAT.ly[n]) {
    one.el.style.transform = `translate(${x}px,${y}px)`;
    SEAT.lx[n] = x; SEAT.ly[n] = y;
  }
  const flags = (n === TABLE.floor ? 1 : 0) | (SEAT.hand[n] > 0.5 ? 2 : 0) | (SEAT.lost[n] ? 4 : 0);
  if (flags === SEAT.shown[n]) return;
  one.el.classList.toggle('floor', (flags & 1) !== 0);
  one.el.classList.toggle('hand', (flags & 2) !== 0);
  one.el.classList.toggle('lost', (flags & 4) !== 0);
  one.why.textContent = flags & 4 ? SEAT.why[n] : '';
  SEAT.shown[n] = flags;
}
/* For a check: the stage's camera, its canvas on the page, the seats' figures and names. */
export const stageView = () => ({camera: VIEW.camera, area: [VIEW.left, VIEW.top, VIEW.right, VIEW.bottom],
  meshes: SEAT.meshes.slice(0, SEAT.n), names: TABLE.names.slice(), speakers: SEATS.list.slice(0, SEAT.n)});
