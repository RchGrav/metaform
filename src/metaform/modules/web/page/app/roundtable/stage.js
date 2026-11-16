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
 * are the question, the table's state and original turns, with links that open cited messages and files.
 * After discussion ends, follow-through shows each
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
import {drawPermissions} from '/page/app/agents/permissions.js';
import {posted} from '/page/app/intake/intake.js';
import {G, wake3d} from '/page/app/map3d/graph3d.js';
import {SEATS, Seated, LOOK, bubbleText} from '/page/app/figures/bubble3d.js';
import {bubbleSeconds} from '/page/app/figures/bubble.js';
import {glyphOfType} from '/page/app/figures/walk.js';
import {swap} from '/page/app/camera/flight.js';
import {calledOf} from '/page/app/board/messages.js';
import {wrote, movable} from '/page/app/board/history.js';
import {getJson} from '/page/app/panel/prompts.js';
import {WS} from '/page/app/workspace/workspace.js';
import {referenceParts} from '/page/app/roundtable/references.js';

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
const BUDGET = {value: 0, dirty: false, setupDirty: false};
const PHASE_BUDGET = {project: null, table: null, stage: null};
const LINEUP = {project: null, saving: false};
const LAUNCH = {project: null, agents: new Map()};

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
  'Send back for planning');
UI.pipelineText = h('div', {class: 'rt-pipeline-text', hidden: true, style: {'white-space': 'pre-wrap'}});
UI.pipelineQuestion = h('p', {class: 'rt-pipeline-question'});
UI.pipeline = h('section', {class: 'rt-pipeline', hidden: true}, h('h3', {}, 'Follow-through'), UI.pipelineState,
  UI.pipelineError, UI.pipelineLink, UI.review, UI.pipelineText, UI.pipelineQuestion, UI.comment, UI.sendComment,
  UI.revise, UI.yes, UI.approve, UI.no);
/* The table's notes folder: every file the seats wrote there, listed by name; a click shows its text below. */
UI.noteList = h('ul', {class: 'rt-list rt-notelist'});
UI.noteFallback = h('p', {class: 'rt-note-fallback', hidden: true});
/* The notes in a window of their own: opened by the Notes button, moved by its title, closed with its button. */
UI.notesWin = h('div', {class: 'window movable rt-noteswin', role: 'dialog', 'aria-label': 'Notes', hidden: true},
  h('div', {class: 'bar'}, h('span', {class: 'title'}, 'Notes'),
    h('button', {class: 'close btn icon sm quiet', type: 'button', 'aria-label': 'Close', title: 'Close',
      onclick: () => { UI.notesWin.hidden = true; UI.notesButton.setAttribute('aria-pressed', 'false'); }},
    h('i', {class: 'i i-close', 'aria-hidden': 'true'}))),
  h('div', {class: 'body'}, UI.noteList, UI.noteFallback));
document.body.append(UI.notesWin);
movable(UI.notesWin);
UI.notesButton = h('button', {class: 'btn sm quiet rt-notes-button', type: 'button', 'aria-pressed': 'false',
  title: "Open the table's notes folder", onclick: () => {
    UI.notesWin.hidden = !UI.notesWin.hidden;
    UI.notesButton.setAttribute('aria-pressed', String(!UI.notesWin.hidden));
    if (!UI.notesWin.hidden) readNotes();
  }}, 'Notes');
UI.board = h('div', {class: 'rt-board', 'aria-live': 'polite'}, UI.ideasBox, UI.rankingsBox, UI.results,
  UI.answerBox, UI.records, UI.pipeline);
/* The ideas and rankings at the top: closed with their own button and opened again from the Results button below. */
const showBoard = shown => {
  UI.board.classList.toggle('closed', !shown);
  UI.resultsButton.setAttribute('aria-pressed', String(shown));
};
UI.boardClose = h('button', {class: 'close btn icon sm quiet rt-board-close', type: 'button', 'aria-label': 'Close',
  title: 'Close the ideas and rankings; Results opens them again', onclick: () => showBoard(false)},
  h('i', {class: 'i i-close', 'aria-hidden': 'true'}));
UI.board.prepend(UI.boardClose);
UI.resultsButton = h('button', {class: 'btn sm quiet rt-results-button', type: 'button', 'aria-pressed': 'true',
  title: 'Show or hide the ideas and rankings at the top',
  onclick: () => showBoard(UI.board.classList.contains('closed'))}, 'Results');
const NOTES = {busy: false, again: false};
/* The notes folder listed again: as the stage starts watching a table and after each turn, a burst read once. */
async function readNotes() {
  if (NOTES.busy) { NOTES.again = true; return; }
  NOTES.busy = true;
  try {
    do {
      NOTES.again = false;
      const id = TABLE.id;
      if (!id) return;
      const found = await getJson(`/api/roundtable?project=${encodeURIComponent(S.project)}&table=${
        encodeURIComponent(id)}&notes=1`);
      if (id !== TABLE.id) return;
      const listed = found.notes || [];
      fill(UI.noteList, ...listed.map(one => h('li', {}, h('button', {type: 'button', class: 'btn sm quiet',
        onclick: () => viewNote(one.path)},
        one.path), h('small', {class: 'rt-why'}, ` ${one.bytes} bytes`))));
      UI.notesButton.textContent = listed.length ? `Notes (${listed.length})` : 'Notes';
      if (!listed.length) fill(UI.noteList, h('li', {class: 'rt-why'}, 'No notes yet.'));
    } while (NOTES.again);
  } catch (error) { toast(error.message); }
  finally { NOTES.busy = false; }
}
/* A note opens synchronously from its click, in its own full-size browser reading window. */
function viewNote(path) {
  const query = new URLSearchParams({project: S.project, table: TABLE.id, note: path});
  const url = `/page/roundtable-note.html?${query}`;
  const name = `metaform-roundtable-note-${encodeURIComponent(JSON.stringify([S.project, TABLE.id, path]))}`;
  const opened = window.open(url, name, `popup,width=${screen.availWidth},height=${screen.availHeight},left=0,top=0`);
  UI.noteFallback.hidden = !!opened;
  if (opened) { opened.opener = null; opened.focus(); }
  else fill(UI.noteFallback, 'Your browser blocked the reading window. ',
    h('a', {href: url, target: '_blank', rel: 'noopener'}, 'Open the note in a new tab'));
}
UI.canvas = h('canvas', {class: 'rt-canvas', 'aria-hidden': 'true'});
UI.seats = h('div', {class: 'rt-seats'});
UI.band = h('div', {class: 'rt-band'}, UI.canvas, UI.seats);
UI.topic = h('b', {class: 'rt-question', tabindex: '0', 'aria-label': 'Roundtable question'});
UI.state = h('span', {class: 'rt-state', role: 'status'});
UI.leave = h('button', {class: 'btn sm quiet rt-leave', type: 'button', onclick: () => leaveStage(),
  title: 'Back to the map; the table runs on (Escape)'}, 'Leave');
UI.newTable = h('button', {class: 'btn sm quiet rt-new', type: 'button', hidden: true,
  onclick: () => openRoundtable(true)}, 'New table');
UI.hold = h('button', {class: 'btn sm rt-hold', type: 'button', hidden: true,
  onclick: () => chairControl(TABLE.state === 'held' ? 'continue' : 'hold')}, 'Hold');
UI.endDiscussion = h('button', {class: 'btn sm rt-end-discussion', type: 'button', hidden: true,
  onclick: () => chairControl('advance')}, 'End discussion');
UI.endSession = h('button', {class: 'btn sm rt-end-session', type: 'button', hidden: true,
  title: 'End the entire session and save its documents and current record',
  onclick: () => chairControl('end')}, 'End session');
UI.continueDiscussion = h('button', {class: 'btn sm rt-continue-discussion', type: 'button', hidden: true,
  onclick: () => chairControl('continue')}, 'Continue discussion');
/* Abort: ends the table at once, a stuck one included, with no report, no further turn and no next table; its
 * transcript and notes stay saved. */
UI.endTable = h('button', {class: 'btn sm quiet rt-end-table', type: 'button', hidden: true,
  title: 'Abort this table now: no report, no further turn, nothing more spent; its transcript and notes stay saved',
  onclick: () => {
    if (confirm('Abort this table now? It ends at once with no report and nothing more spent.')) chairControl('abort');
  }}, 'Abort');
UI.discussionComment = h('textarea', {class: 'rt-discussion-comment', rows: 2,
  'aria-label': 'Discussion comment', placeholder: 'Add to the discussion', oninput: renderChair});
UI.sendDiscussion = h('button', {class: 'btn sm', type: 'submit'}, 'Send comment');
UI.discussion = h('form', {class: 'rt-discussion', hidden: true,
  onsubmit: event => { event.preventDefault(); chairControl('comment'); }},
  UI.discussionComment, UI.sendDiscussion,
  h('small', {}, 'Comments enter at the next gap. Hold pauses AI turns. Continue resumes them.'));
UI.liveTokenBudget = h('input', {type: 'number', min: 0, max: Number.MAX_SAFE_INTEGER, step: 1, value: 0,
  name: 'token_budget', required: true, 'aria-describedby': 'rt-live-budget-hint',
  oninput: () => { BUDGET.dirty = true; }});
UI.saveBudget = h('button', {class: 'btn sm', type: 'submit'}, 'Update budget');
UI.currentBudget = h('span', {class: 'rt-budget-current', role: 'status'}, 'Current: disabled');
UI.topicSelectionStatus = h('p', {class: 'rt-topic-selection-status', role: 'status', hidden: true});
UI.phaseBudgetLabel = h('b', {class: 'rt-phase-budget-label'});
UI.phaseBudgetState = h('span', {class: 'rt-phase-budget-state', role: 'status'});
UI.phaseBudgetRows = h('ul', {class: 'rt-phase-budget-rows'});
UI.phaseBudgetBasis = h('small', {class: 'rt-phase-budget-basis'}, tokenBasisLabel('all'));
UI.phaseBudget = h('section', {class: 'rt-phase-budget', hidden: true, 'aria-label': 'Current phase token usage'},
  h('div', {class: 'rt-phase-budget-head'}, UI.phaseBudgetLabel, UI.phaseBudgetState), UI.phaseBudgetRows,
  UI.phaseBudgetBasis,
  h('small', {}, 'Reported usage across model calls. Each discussion starts at 0. '
    + 'Totals update after usage reports or completed turns.'));
UI.budget = h('form', {class: 'rt-budget', hidden: true,
  onsubmit: event => { event.preventDefault(); chairControl('budget'); }},
  h('label', {}, 'Token budget per agent, per discussion', UI.liveTokenBudget), UI.saveBudget, UI.currentBudget,
  h('small', {id: 'rt-live-budget-hint'}, 'The same limit applies to each discussion. '
    + '0 disables. Changing the limit keeps tokens already counted.'), UI.phaseBudget);
UI.transcript = h('ol', {class: 'rt-transcript', tabindex: '0', 'aria-label': 'The transcript'});
UI.permissions = h('div', {class: 'rt-permissions', 'aria-label': 'Agent permission requests', hidden: true});
const PERMISSIONS = new Map();
/* The harness supplies the request and its choices. The page relays the person's selected option unchanged. */
function permissionIs(event) {
  const previous = PERMISSIONS.get(event.request);
  if (previous) previous.remove();
  PERMISSIONS.delete(event.request);
  if (event.state === 'waiting') {
    const controls = h('div', {class: 'rt-permission-options'});
    const panel = h('div', {class: 'rt-permission'}, h('b', {}, event.name || event.seat || 'Agent'),
      h('p', {}, event.title || 'Permission requested'),
      event.description ? h('p', {}, event.description) : null,
      event.subject ? h('pre', {}, typeof event.subject === 'string' ? event.subject : JSON.stringify(event.subject, null, 2)) : null,
      controls);
    for (const option of event.options || []) {
      const button = h('button', {class: 'btn sm', type: 'button', onclick: async () => {
        for (const choice of controls.children) choice.disabled = true;
        try {
          await wrote('/api/roundtable-control', {project: S.project, table: TABLE.id, action: 'permit',
            request: event.request, option: option.optionId});
        } catch (error) {
          toast(error.message);
        } finally {
          for (const choice of controls.children) choice.disabled = false;
        }
      }}, option.name);
      controls.append(button);
    }
    PERMISSIONS.set(event.request, panel);
    UI.permissions.append(panel);
  }
  UI.permissions.hidden = PERMISSIONS.size === 0;
}
/* The bottom pane's grip: dragged up or down, it sets the transcript's height; the press is the grip's alone, so the
 * 3D map behind never takes it for a camera turn. */
UI.grip = h('div', {class: 'rt-grip', role: 'separator', 'aria-orientation': 'horizontal',
  title: 'Drag to resize the transcript', onpointerdown: dragGrip});
function dragGrip(event) {
  event.preventDefault();
  event.stopPropagation();
  const pane = UI.transcript;
  const grip = event.currentTarget, from = event.clientY, start = pane.getBoundingClientRect().height;
  grip.setPointerCapture(event.pointerId);
  const move = moved => {
    const most = window.innerHeight * 0.7;
    pane.style.height = `${Math.max(48, Math.min(most, start + from - moved.clientY))}px`;
  };
  const done = () => { grip.removeEventListener('pointermove', move); grip.removeEventListener('pointerup', done);
    grip.removeEventListener('pointercancel', done); };
  grip.addEventListener('pointermove', move);
  grip.addEventListener('pointerup', done);
  grip.addEventListener('pointercancel', done);
}
UI.foot = h('div', {class: 'rt-foot'}, UI.grip, h('div', {class: 'rt-head'}, UI.topic, UI.state, UI.hold,
  UI.endDiscussion, UI.endSession, UI.continueDiscussion, UI.endTable, UI.newTable, UI.notesButton, UI.resultsButton, UI.leave),
  UI.permissions, UI.topicSelectionStatus, UI.budget, UI.transcript, UI.discussion);
UI.question = h('textarea', {rows: 3, 'aria-label': 'Your question to the table',
  placeholder: 'What should the table answer?'});
UI.seatList = h('ol', {class: 'rt-seatlist', 'aria-label': 'The seats, in speaking order'});
UI.addSeat = h('button', {type: 'button', class: 'btn sm quiet', onclick: () => addSeat('claude/opus')}, 'Add a seat');
UI.saveParticipants = h('button', {type: 'button', class: 'btn sm quiet', onclick: saveParticipants},
  'Save participants');
UI.where = h('span', {class: 'rt-where'});
UI.launchPermissions = h('div', {class: 'rt-launch-permissions'});
UI.replyLimit = h('input', {type: 'number', min: 1, max: Number.MAX_SAFE_INTEGER, step: 1, value: 512,
  name: 'reply_limit', required: true});
UI.tokenBudget = h('input', {type: 'number', min: 0, max: Number.MAX_SAFE_INTEGER, step: 1, value: 0,
  name: 'token_budget', required: true, 'aria-describedby': 'rt-token-budget-hint',
  oninput: () => { BUDGET.setupDirty = true; }});
UI.setupBudgetBasis = h('span', {class: 'rt-setup-budget-basis'}, tokenBasisLabel('uncached'));
UI.setupBudgetCache = h('span', {}, ' Cache writes count as input.');
UI.automate = h('input', {type: 'checkbox', name: 'automate_ticket_creation',
  'aria-describedby': 'rt-automate-description'});
UI.judging = h('input', {type: 'checkbox', name: 'judging', checked: true});
UI.compressBetweenTopics = h('input', {type: 'checkbox', name: 'compress_between_topics',
  'aria-describedby': 'rt-compression-description'});
UI.tables = h('input', {type: 'number', min: 1, max: 20, step: 1, value: 1, name: 'chain', required: true});
UI.start = h('button', {class: 'btn primary rt-start', type: 'submit'}, 'Start');
UI.setup = h('form', {class: 'rt-setup', onsubmit: event => { event.preventDefault(); startTable(); }},
  h('h2', {}, 'Roundtable', UI.where), UI.question,
  h('div', {class: 'rt-seatsetup'}, 'Seats', UI.seatList, UI.addSeat, UI.saveParticipants,
    h('small', {}, 'Start remembers this browser’s lineup. Save participants sets this project’s defaults.')),
  UI.launchPermissions,
  h('label', {}, 'Number of roundtables', UI.tables),
  h('small', {}, 'Between roundtables, each participant privately proposes a topic. Jev compares the proposals '
    + 'to choose the next roundtable.'),
  h('label', {}, UI.compressBetweenTopics, 'Compress conversations between topics'),
  h('small', {id: 'rt-compression-description'},
    'Keep the same conversations and retain context for the selected next topic.'),
  h('label', {}, 'Base reply allowance (characters)', UI.replyLimit),
  h('small', {}, 'Base allowance for discussion replies. Saved PASS and missed-message credits can increase '
    + 'a participant’s next allowance.'),
  h('label', {}, 'Token budget per agent, per discussion', UI.tokenBudget),
  h('small', {id: 'rt-token-budget-hint'}, '0 disables. Each discussion starts a fresh count '
    + 'for each agent. The first agent at 50% or 80% warns the group, at 100% asks it to close, and at 120% forces '
    + 'the next phase without waiting for everyone to finish. Counting basis: ', UI.setupBudgetBasis, '.',
  UI.setupBudgetCache, ' Totals update after reports or turns.'),
  h('label', {}, UI.judging, 'Judge contributions with Jev'),
  h('small', {}, 'Checks new information, usefulness and topic relevance. Off keeps substantive replies without '
    + 'filtering. Between roundtables, Jev still compares the private topic proposals.'),
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
  if (TABLE.id && fresh !== true && !TABLE.ended) { showStage(); UI.setup.hidden = true; readTable(true); return; }
  if (fresh !== true) {  // a table running in this project, such as the next of a planning session: watched, not asked
    let running = null;
    try { running = (await getJson(`/api/roundtable?project=${encodeURIComponent(S.project)}`)).running || null; }
    catch { running = null; }
    if (running) {
      resetTable();
      TABLE.id = running;
      TABLE.kind = `roundtables:${running}`;
      showStage();
      UI.setup.hidden = true;
      await readTable(true);
      return;
    }
  }
  const entry = S.selected ? S.elements.get(S.selected) : null;
  TABLE.address = '';  // the person's question alone opens the table: the node selected on the map is never attached
  UI.where.textContent = '';
  resetTable();
  showStage();
  UI.setup.hidden = false;
  UI.automate.checked = false;
  UI.compressBetweenTopics.checked = false;
  UI.start.disabled = true;  // wait for the project's budget before offering Start
  UI.question.focus();
  UI.tokenBudget.value = 0;
  UI.setupBudgetBasis.textContent = tokenBasisLabel('uncached');
  UI.setupBudgetCache.textContent = ' Cache writes count as input.';
  BUDGET.setupDirty = false;
  const project = S.project;
  if (LAUNCH.project !== project) {
    LAUNCH.project = project;
    LAUNCH.agents.clear();
    fill(UI.launchPermissions);
  }
  try {
    const found = await getJson(`/api/roundtable?project=${encodeURIComponent(project)}`);
    if (project !== S.project) return;
    UI.judging.checked = found.judging !== false;
    const basis = found.token_basis || 'uncached';
    UI.setupBudgetBasis.textContent = tokenBasisLabel(basis);
    UI.setupBudgetCache.textContent = basis === 'uncached' ? ' Cache writes count as input.' : '';
    if (!BUDGET.setupDirty && Number.isSafeInteger(found.token_budget) && found.token_budget >= 0) {
      UI.tokenBudget.value = found.token_budget;
    }
    OFFERED.clear();  // each agent's models read again, as it offers them now
    if (LINEUP.project !== project || !UI.seatList.children.length) {
      fill(UI.seatList);
      LINEUP.project = project;
      for (const seat of rememberedParticipants(project, found.seats || [])) addSeat(String(seat));
    }
    drawSetupPermissions();
  } catch (error) { toast(error.message); }
  finally { if (project === S.project && !TABLE.id) UI.start.disabled = false; }
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
  fill(UI.noteList);
  fill(UI.noteFallback);
  UI.noteFallback.hidden = true;
  fill(UI.permissions);
  UI.permissions.hidden = true;
  PERMISSIONS.clear();
  UI.transcript.hidden = false;
  UI.topicSelectionStatus.hidden = true;
  UI.topicSelectionStatus.textContent = '';
  UI.results.hidden = UI.records.hidden = UI.newTable.hidden = UI.notesWin.hidden = true;
  UI.notesButton.textContent = 'Notes';
  UI.notesButton.setAttribute('aria-pressed', 'false');
  Object.assign(PIPELINE, {value: null, reviewed: '', text: '', version: PIPELINE.version + 1, reading: false,
    writing: false});
  renderPipeline();
  UI.answer.textContent = '';
  UI.ideasBox.hidden = UI.rankingsBox.hidden = UI.answerBox.hidden = true;
  UI.topic.textContent = ''; UI.state.textContent = '';
  UI.discussionComment.value = '';
  BUDGET.dirty = false;
  Object.assign(PHASE_BUDGET, {project: null, table: null, stage: null});
  resetPhaseBudget();
  budgetIs(0);
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
  const tables = Number(UI.tables.value);
  if (!Number.isSafeInteger(tables) || tables < 1 || tables > 20) { UI.tables.reportValidity(); return; }
  const tokenBudget = Number(UI.tokenBudget.value);
  if (UI.tokenBudget.value === '' || !Number.isSafeInteger(tokenBudget) || tokenBudget < 0) {
    UI.tokenBudget.reportValidity(); return;
  }
  if (listed.length) rememberParticipants(S.project, listed);
  UI.start.disabled = true;
  UI.state.textContent = 'Opening the table: its seats are starting…';
  UI.topic.textContent = topic;
  const permissions = chosenPermissions(listed);
  const answer = await wrote('/api/roundtable-open', {topic, reply_limit: replyLimit, chain: tables,
    token_budget: tokenBudget,
    judging: UI.judging.checked,
    compress_between_topics: UI.compressBetweenTopics.checked,
    automate_ticket_creation: UI.automate.checked,
    ...(Object.keys(permissions).length ? {permissions} : {}),
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
 * gave no list, as one that needs a login, has its model typed and checked as the table opens, and Ask it again
 * starts it once, with no prompt, to read it. */
const SEAT_AGENTS = ['claude', 'codex', 'antigravity'];
const OFFERED = new Map();  // each agent's model picks, read once each time the stage opens
function addSeat(seat) {
  const [first, ...rest] = seat.replace(/^acp:/, '').split('/');
  const agent = SEAT_AGENTS.includes(first) && rest.length ? first : '';
  const who = h('select', {'aria-label': 'Agent', onchange: () => {
    modelPicker(row, who.value, '');
    drawSetupPermissions();
  }},
    SEAT_AGENTS.map(one => h('option', {value: one, selected: one === agent}, agentName(one))),
    h('option', {value: '', selected: !agent}, 'OpenRouter model'));
  const row = h('li', {class: 'rt-pick'}, who, h('span', {class: 'rt-model'}),
    h('button', {type: 'button', class: 'btn sm quiet', title: 'Remove this seat', 'aria-label': 'Remove this seat',
      onclick: () => { row.remove(); drawSetupPermissions(); }}, '×'));
  UI.seatList.append(row);
  modelPicker(row, agent, agent ? rest.join('/') : seat);
  drawSetupPermissions();
}
/* One standard launch panel per ACP agent, shared by every seat using it. Kept panels retain their choices when
 * another seat is added; a removed agent or changed project drops its launch choices. OpenRouter has no ACP modes. */
function drawSetupPermissions() {
  const project = S.project;
  if (LAUNCH.project !== project) {
    LAUNCH.project = project;
    LAUNCH.agents.clear();
  }
  const agents = new Set([...UI.seatList.children].map(row => row.querySelector('select').value).filter(Boolean));
  for (const agent of LAUNCH.agents.keys()) if (!agents.has(agent)) LAUNCH.agents.delete(agent);
  for (const agent of agents) {
    if (LAUNCH.agents.has(agent)) continue;
    const panel = h('div', {class: 'field permissions', 'data-agent': agent},
      h('span', {}, `${agentName(agent)} permissions`, h('small', {}, ' · this launch only')),
      h('div', {class: 'controls'}), h('p', {class: 'hint'}), h('p', {class: 'risk warnline', hidden: true}));
    const entry = {own: {prompts: '', mode: ''}, panel};
    LAUNCH.agents.set(agent, entry);
    drawPermissions(panel, agent, entry.own, () => LAUNCH.project === project && LAUNCH.agents.get(agent) === entry);
  }
  fill(UI.launchPermissions, ...[...agents].map(agent => LAUNCH.agents.get(agent).panel));
}
function chosenPermissions(seats) {
  if (LAUNCH.project !== S.project) return {};
  const agents = new Set(seats.map(seat => seat.replace(/^acp:/, '').split('/')[0]));
  return Object.fromEntries([...LAUNCH.agents].flatMap(([agent, entry]) => {
    const own = Object.fromEntries(Object.entries(entry.own).filter(([, value]) => value));
    return agents.has(agent) && Object.keys(own).length ? [[agent, own]] : [];
  }));
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
      placeholder: 'opus', title: `${agentName(agent)} did not say which models it offers`}),
    h('button', {type: 'button', class: 'btn sm quiet', title: 'Starts it once, with no prompt, and reads the models '
      + 'it offers', onclick: () => readModels(row, agent)}, 'Ask it again'));
    return;
  }
  const listed = model && !picks.some(one => one.value === model)
    ? [{value: model, label: model, group: null, description: null}, ...picks] : picks;
  fill(box, h('select', {'aria-label': `${agentName(agent)} model`},
    pickerOptions(listed, model || picks.find(one => one.value !== 'default')?.value)));
}
async function readModels(row, agent) {
  toast(`Asking ${agentName(agent)} which models it offers…`);
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
  let id = TABLE.id, project = S.project;
  try {
    do {
      TABLE.again = false;
      id = TABLE.id; project = S.project;
      watchPhaseBudget(project, id);
      const found = await getJson(`/api/roundtable?project=${encodeURIComponent(project)}&table=${
        encodeURIComponent(id)}&after=${TABLE.seq}${whole || !SEAT.n ? '&whole=1' : ''}`);
      if (id !== TABLE.id || project !== S.project) {
        if (TABLE.id) { TABLE.again = true; continue; }
        return;
      }
      // State and final results show immediately; speaking turns keep their pacing.
      let wrote = whole;
      for (const event of found.events || []) {
        if (event.kind === 'turn' || event.kind === 'veto' || event.kind === 'end') wrote = true;
        if (event.kind === 'permission') permissionIs(event);
        else if (event.kind === 'state') stateIs(event.state, event.reason);
        else if (event.kind === 'end') ended(event);
        else if (event.kind === 'pipeline') pipelineIs(event.pipeline);
        else TOLD.list.push(event);
      }
      if (found.status) seated(found.status);
      if (found.status && Object.hasOwn(found.status, 'phase_budget')) phaseBudgetIs(found.status.phase_budget);
      else if (Object.hasOwn(found, 'phase_budget')) phaseBudgetIs(found.phase_budget);
      if (found.status && Object.hasOwn(found.status, 'topic_selection')) topicSelectionIs(found.status.topic_selection);
      else if (Object.hasOwn(found, 'topic_selection')) topicSelectionIs(found.topic_selection);
      TABLE.seq = Math.max(TABLE.seq, found.latest || 0);
      tell();
      if (wrote) readNotes();  // a seat writes notes on its turn, so the folder is read again after one
    } while (TABLE.again);
  } catch (error) {
    if (id === TABLE.id && project === S.project) {
      toast(error.message);
    }
  } finally { TABLE.busy = false; }
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
  if (Object.hasOwn(status, 'stage')) liveStageIs(status.stage);
  budgetIs(status.token_budget);
  if (!SEAT.n) {
    TABLE.seats = status.seats || [];
    TABLE.names = status.seated || TABLE.seats.map(one => String(one).split('/').at(-1));
    seatAll();
  }
  if (status.state === 'ended') ended(status);
  else { TABLE.ended = false; stateIs(status.state, status.reason); }
}
function heard(event) {
  if (event.kind === 'turn' || event.kind === 'veto') return turn(event);
  if (event.kind === 'stage') { TABLE.stage = PHASE_BUDGET.stage ?? event.stage;
    if (event.stage !== 'discussion') TABLE.floor = -1;
    renderChair(); }
  else if (event.kind === 'ideas') ideas(event.ideas || []);
  else if (event.kind === 'rankings') rankings(event.rankings || []);
  else if (event.kind === 'summary') summary(event.text, event.name, event.created || event.at);
  else if (event.kind === 'minutes' || event.kind === 'running_summary') {
    said('rt-note', event.seat || 'Saved explanation', event.text || '', '', event.created || event.at);
  }
  else if (event.kind === 'seat_lost') lost(event);
  else if (event.kind === 'operational') {
    let text = event.budget?.text;
    if (typeof text !== 'string') {
      text = event.text || '';
      if (event.what === 'budget') {
        try {
          const budget = JSON.parse(text);
          if (typeof budget?.text === 'string') text = budget.text;
        } catch { /* Older followers may send plain text rather than a budget object. */ }
      }
    }
    said('rt-note', event.what || 'note', text, '', event.created || event.at);
  }
  nextUp();
}
const seatOf = name => TABLE.names.indexOf(name) >= 0 ? TABLE.names.indexOf(name) : TABLE.seats.indexOf(name);
const VETO_REASONS = {
  on_topic: 'The topic relevance criterion was not met.',
  new_context: 'The new-information criterion was not met.',
  repeat: 'The contribution was marked as repeated material.',
  new: 'The new-idea criterion was not met.',
  valuable: 'The usefulness criterion was not met.',
  relevant: 'The relevance criterion was not met.',
  keep: 'The retain criterion was not met.'};
function vetoReason(event) {
  if (typeof event.veto_reason === 'string' && event.veto_reason.trim()) return event.veto_reason.trim();
  if (typeof event.reason === 'string' && event.reason.trim()) return event.reason.trim();
  const failed = Array.isArray(event.failed) ? event.failed : [];
  const reasons = failed.filter(key => typeof key === 'string' && Object.hasOwn(VETO_REASONS, key)).map(key => VETO_REASONS[key]);
  return reasons.length ? reasons.join(' ') : 'No veto reason was recorded';
}
/* A turn: its seat takes the floor and says it; a vetoed one fades from its bubble and is struck in the transcript. */
function turn(event) {
  const n = seatOf(event.seat), vetoed = event.kind === 'veto';
  const name = !vetoed && /^R[1-9]\d*-[1-9]\d*$/.test(event.message_id || '')
    ? `${event.message_id} · ${event.seat}` : event.seat;
  said(vetoed ? 'rt-turn vetoed' : 'rt-turn', name, event.text || '',
    vetoed ? ` (vetoed: ${vetoReason(event)})`
      : event.outcome === 'unjudged' ? ' (never judged: the table ended first)' : '', event.created || event.at);
  if (event.outcome === 'handoff' || event.outcome === 'carry') return;
  if (n < 0 || TABLE.ended) return;
  TABLE.floor = n;
  const seat = SEATS.list[n];
  seat.text = bubbleText(event.text || '', LOOK.seat.most, true);
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
function summary(text, name, at) {
  if (!text) return;
  if (!TABLE.ended) {
    UI.answer.textContent = text;
    UI.answerBox.querySelector('h3').textContent = name ? `Answer, from ${name}` : 'Answer';
    UI.answerBox.hidden = false;
  }
  said('rt-summary', name || 'Host', text, '', at);
}
function lost(event) {
  const n = seatOf(event.seat);
  said('rt-note', event.seat || 'A seat', event.text || event.what || 'left the table', '', event.created || event.at);
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
/* Phase counts come from the engine's current phase, independently of paced turns and unsaved budget edits. */
function tokenBasisLabel(basis) {
  if (basis === 'uncached') return 'Uncached input + output; cached reads excluded';
  if (basis === 'output') return 'Generated output only';
  return 'Input + cached input + output';
}
function liveStageIs(stage) {
  PHASE_BUDGET.stage = stage || 'discussion';
  TABLE.stage = PHASE_BUDGET.stage;
  UI.topicSelectionStatus.hidden = TABLE.stage !== 'topic_selection';
  if (UI.topicSelectionStatus.hidden) UI.topicSelectionStatus.textContent = '';
  else if (!UI.topicSelectionStatus.textContent) UI.topicSelectionStatus.textContent = 'Choosing the next topic privately.';
  if (TABLE.state === 'running') UI.state.textContent = runningWords();
  renderChair();
}
function runningWords() {
  return {topic_selection: 'Choosing the next topic', scoring: 'Scoring', farewell: 'Farewells'}[TABLE.stage]
    || 'The table is talking';
}
function topicSelectionIs(snapshot) {
  if (TABLE.stage !== 'topic_selection' || !['running', 'held'].includes(TABLE.state)) return;
  UI.topicSelectionStatus.hidden = false;
  if (!snapshot) { UI.topicSelectionStatus.textContent = 'Choosing the next topic privately.'; return; }
  const requested = Number(snapshot.requested), completed = Number(snapshot.completed);
  const count = Number.isSafeInteger(requested) && requested > 0 && Number.isSafeInteger(completed) && completed >= 0
    ? ` ${Math.min(completed, requested)} of ${requested} proposals received.` : '';
  UI.topicSelectionStatus.textContent = snapshot.state === 'compressing'
    ? 'Compressing conversations for the next topic.' : snapshot.state === 'judging'
    ? `Comparing the private proposals to choose the next topic.${count}`
    : `Choosing the next topic privately.${count}`;
}
function resetPhaseBudget() {
  UI.phaseBudget.hidden = true;
  UI.phaseBudgetLabel.textContent = UI.phaseBudgetState.textContent = '';
  fill(UI.phaseBudgetRows);
}
function watchPhaseBudget(project, table) {
  if (PHASE_BUDGET.project === project && PHASE_BUDGET.table === table) return;
  resetPhaseBudget();
  PHASE_BUDGET.project = project;
  PHASE_BUDGET.table = table;
  PHASE_BUDGET.stage = null;
  UI.topicSelectionStatus.hidden = true;
  UI.topicSelectionStatus.textContent = '';
}
function phaseBudgetIs(snapshot) {
  if (snapshot && Object.hasOwn(snapshot, 'stage')) liveStageIs(snapshot.stage);
  else if (snapshot?.phase === 'panel') liveStageIs('discussion');
  if (!snapshot || snapshot.phase !== 'panel') { resetPhaseBudget(); return; }
  const maximum = Number(snapshot.limit || 0), topic = snapshot.topic;
  budgetIs(maximum);
  UI.phaseBudget.hidden = false;
  UI.phaseBudgetBasis.textContent = tokenBasisLabel(snapshot.basis);
  UI.phaseBudgetBasis.title = snapshot.basis === 'uncached' ? 'Cache writes count as input.' : '';
  UI.phaseBudgetLabel.textContent = `Panel${topic ? ` ${topic}` : ''}`;
  const notices = snapshot.notices || [], last = notices.at(-1);
  UI.phaseBudgetState.textContent = snapshot.forced ? 'Hard limit reached.'
    : snapshot.closing ? 'Closing statements requested.'
    : last ? `${last.percent}% notice sent.` : '';
  fill(UI.phaseBudgetRows, ...(snapshot.participants || []).map(one => {
    const tokens = Number(one.tokens || 0), fraction = maximum ? tokens / maximum : 0;
    const name = one.name || `Participant ${Number(one.position) + 1}`;
    const count = maximum ? `${tokens.toLocaleString()} / ${maximum.toLocaleString()} tokens (${Math.round(fraction * 100)}%)`
      : `${tokens.toLocaleString()} tokens · limit disabled`;
    return h('li', {'data-position': one.position}, h('span', {class: 'rt-phase-budget-name'}, name),
      h('span', {class: 'rt-phase-budget-count'}, count),
      maximum ? h('progress', {max: maximum, value: Math.min(tokens, maximum), 'aria-label': `${name} phase token use`}) : null,
      one.reported === false ? h('small', {}, 'Usage not yet reported.') : null,
      one.closing ? h('small', {}, 'Closing statement requested.') : null,
      one.unreported ? h('small', {}, `Usage missing for ${one.unreported} ${one.unreported === 1 ? 'reply' : 'replies'}; `
        + 'the reported total is incomplete.') : null);
  }));
}
/* Status refreshes report the current limit while an unsaved edit stays in the person's input. */
function budgetIs(value) {
  if (!Number.isSafeInteger(value) || value < 0) return;
  BUDGET.value = value;
  UI.currentBudget.textContent = value ? `Current: ${value.toLocaleString()} tokens` : 'Current: disabled';
  if (!BUDGET.dirty) UI.liveTokenBudget.value = value;
}
function renderChair() {
  const active = !!TABLE.id && (TABLE.state === 'running' || TABLE.state === 'held');
  if (!active) { UI.topicSelectionStatus.hidden = true; UI.topicSelectionStatus.textContent = ''; }
  UI.hold.hidden = UI.discussion.hidden = UI.budget.hidden = !active;
  UI.liveTokenBudget.disabled = UI.saveBudget.disabled = CHAIR.writing;
  const advanceable = !TABLE.stage || TABLE.stage === 'discussion';
  UI.endDiscussion.hidden = !active;
  UI.endDiscussion.disabled = CHAIR.writing || !advanceable;
  UI.endDiscussion.title = advanceable ? 'Finish the current discussion'
    : TABLE.stage === 'topic_selection' ? 'Wait for private topic selection, or use End session to finish the session.'
      : 'Only discussion can advance. Use End session to finish the session.';
  UI.endSession.hidden = !TABLE.id || !['running', 'held', 'ending'].includes(TABLE.state);
  UI.endSession.disabled = CHAIR.writing;
  UI.continueDiscussion.hidden = TABLE.state !== 'ended';
  UI.continueDiscussion.disabled = CHAIR.writing;
  UI.endTable.hidden = !TABLE.id || ['ended', 'refused'].includes(TABLE.state);
  UI.endTable.disabled = CHAIR.writing;
  UI.hold.textContent = TABLE.state === 'held' ? 'Continue' : 'Hold';
  UI.hold.disabled = CHAIR.writing;
  UI.discussionComment.disabled = CHAIR.writing;
  UI.sendDiscussion.disabled = CHAIR.writing || !UI.discussionComment.value.trim();
}
async function chairControl(action) {
  if (!TABLE.id || CHAIR.writing || (!['running', 'held'].includes(TABLE.state)
      && !(action === 'continue' && TABLE.state === 'ended')
      && !(action === 'end' && TABLE.state === 'ending')
      && !(action === 'abort' && !['ended', 'refused'].includes(TABLE.state)))) return;
  if (action === 'advance' && TABLE.stage && TABLE.stage !== 'discussion') return;
  const table = TABLE.id, project = S.project, text = UI.discussionComment.value;
  if (action === 'comment' && !text.trim()) return;
  const tokenBudget = Number(UI.liveTokenBudget.value);
  if (action === 'budget' && (UI.liveTokenBudget.value === '' || !Number.isSafeInteger(tokenBudget) || tokenBudget < 0)) {
    UI.liveTokenBudget.reportValidity(); return;
  }
  CHAIR.writing = true;
  renderChair();
  try {
    const found = await wrote('/api/roundtable-control', {table, action,
      ...(action === 'comment' ? {text} : {}),
      ...(action === 'budget' ? {token_budget: tokenBudget} : {})});
    if (!found || TABLE.id !== table || S.project !== project) return;
    if (action === 'budget') {
      BUDGET.dirty = false;
      budgetIs(Number.isSafeInteger(found.token_budget) ? found.token_budget : tokenBudget);
    }
    if (action === 'continue' && TABLE.ended) {
      TABLE.ended = false;
      liveStageIs('discussion');
    }
    if (Object.hasOwn(found, 'stage')) liveStageIs(found.stage);
    if (found.state) stateIs(found.state, found.reason);
    if (action === 'abort') {  // an aborted table leaves the stage: the empty form opens for a new one
      CHAIR.writing = false;
      await openRoundtable(true);
      return;
    }
    if (action === 'comment') {
      UI.discussionComment.value = '';
      toast('Comment queued for the next gap between turns.');
    }
  } finally { CHAIR.writing = false; renderChair(); }
}
function stateIs(state, reason) {
  TABLE.state = state || TABLE.state;
  if (TABLE.state === 'running' || TABLE.state === 'held') TABLE.ended = false;
  const words = {running: runningWords(), held: 'Held', ended: 'Ended', ending: 'Ending', opening: 'Opening',
    refused: 'Refused'}[TABLE.state] || TABLE.state;
  UI.state.textContent = reason && TABLE.state !== 'running' ? `${words}: ${reason}` : words;
  UI.root.dataset.state = TABLE.state;
  renderChair();
}
/* One line of the transcript, whole, the newest kept in view unless the person has scrolled up to read. */
const TRANSCRIPT_TIME = {
  clock: new Intl.DateTimeFormat(undefined, {hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23'}),
  full: new Intl.DateTimeFormat(undefined, {dateStyle: 'full', timeStyle: 'long'})};
function transcriptTime(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/i.test(value)) return null;
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return null;
  return h('time', {class: 'rt-time', datetime: date.toISOString(), title: TRANSCRIPT_TIME.full.format(date)},
    TRANSCRIPT_TIME.clock.format(date));
}
function said(kind, who, text, after = '', at = null) {
  const box = UI.transcript, bottom = box.scrollHeight - box.scrollTop - box.clientHeight < 24;
  const timestamp = transcriptTime(at);
  const linked = value => referenceParts(value, {project: S.project, table: TABLE.id}).map(part => part.href
    ? h('a', {class: 'rt-reference', href: part.href, target: '_blank', rel: 'noopener noreferrer'}, part.text) : part.text);
  box.append(h('li', {class: kind}, ...(timestamp ? [timestamp, ' '] : []), h('b', {}, ...linked(who)), ' ', ...linked(text),
    after ? h('span', {class: 'rt-why'}, after) : null));
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
