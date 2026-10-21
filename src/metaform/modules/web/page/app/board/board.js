/* The board, VIEW-037: each ticket's agent, controls and card, the columns, and the board's buttons. */
import '/page/app/board/refs.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill, keyedFill} from '/page/app/core/dom.js';
import {overlay} from '/page/app/core/overlays.js';
import {toast, undoable, confirmAct} from '/page/app/core/controls.js';
import {S, read} from '/page/app/core/reads.js';
import {ROAM} from '/page/app/figures/agents.js';
import {plural} from '/page/app/memory/manage.js';
import {select} from '/page/app/selection/select.js';
import {ticketStatus, statusChip, cancelTicket, removeTicket, rememberStop} from '/page/app/dock/threads.js';
import {chatButton} from '/page/app/dock/send.js';
import {B, KINDS, BOARD, conditionLabel, partAt, chipShown, nodeChip, linked, taskWords, ago}
  from '/page/app/board/refs.js';
import {COLUMN_NAMES, columnOf, history, ageOf, wrote, takenWords} from '/page/app/board/history.js';
import {D, AUTO, waiting, ticketPart, ownGlyph, startWindow, renderAgents} from '/page/app/agents/dispatch.js';
import {giveWork} from '/page/app/task/task.js';
import {HARNESS, agentName, agentSelect} from '/page/app/agents/pickers.js';
import {WS} from '/page/app/workspace/workspace.js';

/* Show the agent dispatch will start before the ticket runs: its saved choice, then its area, then the
 * person's default only when the area is unknown. Helpers retain their explicitly assigned agents. */
const FRONTEND = new Set(['gui', 'web', 'page', 'viewer', 'view', 'board', 'ui', 'frontend', 'graphical',
  'interface', 'graphic', 'display', 'render', 'css', 'figures', 'figure', 'chat', 'dock', 'map2d', 'map3d']);
export const defaultAgent = (address, paths = []) => {
  if (paths.some(path => typeof path === 'string' && path.replaceAll('\\', '/').startsWith('src/metaform/modules/web/page/')))
    return 'claude';
  if (!address) return HARNESS.default || 'claude';
  const parts = address.split('.');
  return parts.some(part => FRONTEND.has(part)) || address === 'code.assistant.navigation'
    || address.startsWith('code.assistant.navigation.') ? 'claude' : 'codex';
};
export const eligibleAgents = ticket => Array.isArray(ticket?.map?.eligible) ? ticket.map.eligible : [];
export const allowsAgent = (ticket, agent) => !eligibleAgents(ticket).length || eligibleAgents(ticket).includes(agent);
export function eligibilityPicker(agents, save) {
  let chosen = [...agents];
  const summary = h('summary', {}), options = h('div', {class: 'choices'});
  const box = h('details', {class: 'eligible', onclick: event => event.stopPropagation()}, summary, options);
  // the agents dispatch knows, VIEW-039
  const names = [...new Set([...HARNESS.agents.map(one => one.agent), ...chosen])];
  const paint = () => {
    summary.textContent = 'Eligible agents: ' + (chosen.length ? chosen.map(agentName).join(', ') : 'Any agent');
    for (const input of options.querySelectorAll('input')) input.checked = input.classList.contains('any')
      ? !chosen.length : chosen.includes(input.dataset.agent);
  };
  const change = async event => {
    const before = [...chosen], input = event.target;
    chosen = input.classList.contains('any') ? [] : input.checked
      ? [...new Set([...chosen, input.dataset.agent])] : chosen.filter(name => name !== input.dataset.agent);
    paint();
    for (const control of options.querySelectorAll('input')) control.disabled = true;
    try { if (await save([...chosen]) === false) { chosen = before; paint(); } }
    finally { for (const control of options.querySelectorAll('input')) control.disabled = false; }
  };
  options.append(h('label', {}, h('input', {type: 'checkbox', class: 'any', onchange: change}), 'Any agent'),
    ...names.map(name => h('label', {}, h('input', {type: 'checkbox', 'data-agent': name, onchange: change}),
      agentName(name))));
  paint();
  return box;
}
const FIVE_AGENTS = ['jelly', 'gearling', 'kite', 'moth', 'drone'];  // five agents at work at most
function ticketControls(ticket) {
  const kept = ticket.map || {};
  const change = async (fields, control) => {
    control.disabled = true;
    try { if (await wrote('/api/ticket', {work_id: ticket.id, ...fields})) await renderBoard(); }
    finally { control.disabled = false; }
  };
  const chosen = kept.agent || defaultAgent(ticket.address || ticket.receiver_address, kept.paths || []);
  const saveEligible = async agents => {
    if (!await wrote('/api/eligible', {work_id: ticket.id, agents})) return false;
    await renderBoard();
    return true;
  };
  const box = h('div', {class: 'ticket-controls', onclick: event => event.stopPropagation()},
    h('label', {title: 'The agent this ticket prefers; change it any time, even while one works on it'}, 'Agent ',
      agentSelect(chosen, agent => change({agent}, box.querySelector('select.agent')))),
    eligibilityPicker(eligibleAgents(ticket), saveEligible),
    glyphPick(kept, change),
    // only while an agent runs on it: an ended agent's ticket offers Back to To do on its card (UX recheck 2026-10-17)
    ticket.taken && !ticket.done && D.sessions.some(one => one.work_id === ticket.id && one.state === 'running')
      ? recallButton(ticket) : null,
    ticket.done ? null : holdButton(kept, change));
  return box;
}
/* Which agent works this ticket, by its glyph: the tickets with one glyph are one agent's, done one at a time. */
function glyphPick(kept, change) {
  const glyphs = kept.glyph && !FIVE_AGENTS.includes(kept.glyph) ? [...FIVE_AGENTS, kept.glyph] : FIVE_AGENTS;
  const pick = h('select', {class: 'glyph-pick', onchange: event => change({glyph: event.target.value}, event.target)},
    h('option', {value: '', selected: !kept.glyph}, 'any'),
    glyphs.map(glyph => h('option', {value: glyph, selected: glyph === kept.glyph}, glyph)));
  return h('label', {
    title: "Which agent works this ticket: the tickets with one glyph are one agent's, done one at a time"},
  'Glyph ', pick);
}
/* Recall the agent working the ticket; the ticket goes back on the board, and its session goes in the dock's stops so
 * the person can resume it if the recall was a mistake. */
function recallButton(ticket) {
  const recall = async event => {
    event.target.disabled = true;
    const session = D.sessions.filter(one => one.work_id === ticket.id && one.state === 'running').at(-1);
    const stopped = await wrote('/api/dispatch-stop', {work_id: ticket.id,
      ...(session ? {session: session.session_id} : {})});
    if (stopped) {
      if (session) rememberStop(session.session_id, new Date().toISOString());
      if (stopped.autostart === false) {  // dispatch's `paused`: the person's stop turned Full Auto off
        $('#autostartAgents').checked = false;
        toast(stopped.notice);
      } else toast(`${agentName(session?.agent)} recalled. Its ticket stays on the board; Back to To do on its card gives it to another agent.`);
      await renderAgents();
      await renderBoard();
    } else event.target.disabled = false;
  };
  return h('button', {class: 'btn sm recall', type: 'button',
    title: 'Recall the agent working this ticket; the ticket goes back on the board', onclick: recall}, 'Recall agent');
}
/* Hold hides the ticket from agents and automatic starts; Release shows it to them again. */
function holdButton(kept, change) {
  return h('button', {class: kept.hold ? 'btn sm hold on' : 'btn sm hold', type: 'button',
    title: kept.hold ? 'Release it: agents and automatic starts see it again'
      : 'Hold it: hidden from agents and automatic starts',
    onclick: event => change({hold: !kept.hold}, event.target)}, kept.hold ? 'Release hold' : 'Hold');
}
/* A card's node chips: the part it is assigned and those it links for reference. */
const assignedOf = ticket => ({kind: ticket.node_kind, id: ticket.node_id, address: ticket.address,
  ends: [ticket.receiver_address, ticket.provider_address]});
function card(ticket, place, total, find) {
  // the place counted when it is clicked, not when it was made: a card a move elsewhere left as it was is not made again
  const move = async (to, by = 0) => {
    const column = columnOf(ticket);
    const at = B.tickets.filter(one => columnOf(one) === column).sort(cardOrder).findIndex(one => one.id === ticket.id);
    const position = to ?? Math.max(0, at + by);
    if (await wrote('/api/move', {work_id: ticket.id, column, position})) await renderBoard();
  };
  const open = () => {
    const project = S.project, base = S.base || '';
    import('/page/app/board/detail.js').then(({ticketDetail}) => ticketDetail(ticket.id, project, base));
  };
  const box = h('div', {class: 'card', draggable: 'true', 'data-id': ticket.id, 'data-kind': ticket.kind || 'none',
    onclick: open},
    cardTop(ticket),
    h('div', {class: 'text'}, ...taskWords(ticket.task || ticket.note || '')),
    h('div', {class: 'nodes'}, nodeChip(assignedOf(ticket), 'assigned', find),
      ...(ticket.links || []).map(link => nodeChip(link, 'ref', find))),
    cardProgress(ticket),
    cardEnded(ticket),
    ticket.resolution ? h('div', {class: 'resolution'}, ...linked(ticket.resolution)) : null,
    cardActs(ticket, place, total, move),
    h('details', {class: 'ticket-settings', onclick: event => event.stopPropagation()},
      h('summary', {}, ticket.map?.hold ? 'Held · agent and glyph' : 'Agent, glyph and hold'), ticketControls(ticket)));
  if (ticket.map?.hold) box.classList.add('on-hold');
  box.addEventListener('dragstart', event => {
    event.dataTransfer.setData('text/plain', ticket.id);
    box.classList.add('dragging');
  });
  box.addEventListener('dragend', () => box.classList.remove('dragging'));
  return box;
}
/* A card's top line: its agent's glyph, VIEW-040, its own or, while its agent is at work, the one its figure is drawn
 * as; its kind; how it closed when not completed; its agent's status with the reason, the same words as the chat's
 * thread; who took it; and how long since it was opened, taken or done. */
function cardTop(ticket) {
  const glyph = ownGlyph(ticket) || ROAM.figures.get(ticket.id)?.glyph;
  return h('div', {class: 'top'}, glyph ? h('img', {class: 'glyph', src: `/page/agent-glyphs/${glyph}.svg`, alt: glyph,
    title: `Agent ${glyph}: the tickets with this glyph are one agent's, done one at a time`}) : null,
  conditionLabel(ticket),
  ticket.done && ticket.outcome && ticket.outcome !== 'completed' ? h('span', {class: `outcome ${ticket.outcome}`,
    title: `Closed ${ticket.outcome}, not completed`}, ticket.outcome === 'cancelled' ? 'Cancelled' : ticket.outcome)
    : null,
  !ticket.done ? statusChip(ticketStatus(ticket)) : null,
  waitsOn(ticket).length ? h('span', {class: 'statechip submitted waiting-on',
    title: 'No agent starts it by itself until these are done'},
  `Waiting on ${waitsOn(ticket).map(handleOf).join(', ')}`) : null,
  takenWords(ticket, Boolean(endedStatus(ticket))),
  ageOf(ticket));
}
/* The open tickets a ticket waits on, `after_work`: no agent starter starts it until they are done, VIEW-042. */
export const waitsOn = ticket => (Array.isArray(ticket?.map?.after_work) ? ticket.map.after_work : [])
  .filter(id => B.tickets.some(other => other.id === id && !other.done));
const handleOf = id => {
  const other = B.tickets.find(one => one.id === id);
  return other?.map?.item || other?.map?.title || id.slice(0, 8);
};
/* Whether Start all and autostart start a ticket by themselves: waiting in To do, not held in Backlog, not held from
 * agents, and waiting on no open ticket. A held ticket is the person's to release or start on its own card, UX review
 * round 1 (orchestrator F5). */
export const startsByItself = ticket => waiting(ticket) && !ticket.held && !ticket.map?.hold && !waitsOn(ticket).length;
/* Why a ticket taken by an agent whose session has ended stands still, in words on the card, not only on hover, and
 * the one act that puts it back: its session's own end, as the chat's thread says it, UX review round 1
 * (web-gui-controls F11). */
function cardEnded(ticket) {
  const status = endedStatus(ticket);
  if (!status) return null;
  const back = async event => {
    event.stopPropagation();
    event.currentTarget.disabled = true;
    if (await wrote('/api/move', {work_id: ticket.id, column: 'todo', by: 'user'})) await renderBoard();
  };
  return h('div', {class: 'ended'}, h('span', {class: 'why'}, status.why || status.words),
    h('button', {class: 'btn sm back', type: 'button', title: 'Put the ticket back in To do, its steps and log kept',
      onclick: back}, 'Back to To do'));
}
/* The state of a taken ticket whose session has ended, or null: the session that holds it now, the one its taking
 * names or, for a start's reservation, one begun since it, read once for the card's top line and its ended row, so
 * the two never say different things. */
function endedStatus(ticket) {
  if (ticket.done || !ticket.taken) return null;
  const session = D.sessions.filter(one => one.work_id === ticket.id).at(-1);
  const by = String(ticket.taken_by || '');
  if (!session || !(by.endsWith(` ${session.session_id}`)
    || (by.startsWith('dispatch starting ') && String(session.started || '') >= String(ticket.taken)))) return null;
  const status = ticketStatus(ticket);
  return !status || ['running', 'input_required', 'completed'].includes(status.state) ? null : status;
}
/* How many of its planned steps have been filed, as a bar. */
function cardProgress(ticket) {
  const steps = ticket.steps || 0, filed = ticket.steps_done || 0;
  if (!steps && !filed) return null;
  const share = Math.min(100, 100 * filed / Math.max(steps, filed, 1));
  return h('div', {class: 'progress'}, h('span', {style: {width: `${share}%`}}),
    h('small', {}, `${filed}/${steps || filed}`));
}
/* Its acts in one row: start and chat, anything can be talked about, a done ticket too, VIEW-042; Cancel, VIEW-037
 * and P232: asked first, with an optional reason; dispatch cancel stops its agent as the person's own stop, so nothing
 * retries it, and closes the ticket with the outcome cancelled, never completed. Moving a card to Done is completing
 * it. Then its place in the column. */
function cardActs(ticket, place, total, move) {
  const start = event => { event.stopPropagation(); startWindow(`Start an agent · ${ticketPart(ticket)}`, [ticket]); };
  const cancel = async event => { event.stopPropagation(); await cancelTicket(ticket, event.currentTarget); };
  const remove = async event => { event.stopPropagation(); await removeTicket(ticket, event.currentTarget); };
  return h('div', {class: 'acts'},
    waiting(ticket) ? h('button', {class: 'btn sm primary start', type: 'button',
      title: 'Start an agent on this ticket', onclick: start}, 'Start agent') : null,
    chatButton({id: ticket.id}, ticketPart(ticket)),
    h('button', {class: 'btn sm quiet', type: 'button'}, 'Inspect'),
    ticket.done ? null : h('button', {class: 'btn sm quiet cancel', type: 'button',
      title: 'Cancel this ticket: its agent stops and the ticket is closed as cancelled', onclick: cancel}, 'Cancel'),
    h('button', {class: 'btn sm quiet remove', type: 'button',
      title: 'Delete this ticket for good, with its steps, links and settings', onclick: remove}, 'Delete'),
    B.boards.length ? boardSelect(ticket) : null,
    h('span', {class: 'grow'}),
    h('div', {class: 'priority', role: 'group', 'aria-label': 'Card order'},
      [['Top', 'Move to top', 0, 0, place === 0], ['↑', 'Move up', null, -1, place === 0],
        ['↓', 'Move down', null, 1, place === total - 1]].map(([text, label, to, by, disabled]) =>
        h('button', {class: 'btn sm quiet', type: 'button', title: label, 'aria-label': label, disabled,
          onclick: event => { event.stopPropagation(); move(to, by); }}, text))));
}
/* Move to another board: the ticket's board, chosen among the project's; the change is one write every open page
 * hears as a change to this ticket, and the card leaves this board on the next draw. */
function boardSelect(ticket) {
  const current = String(ticket.map?.board || '');
  const moveTo = async event => {
    event.stopPropagation();
    const select = event.currentTarget, board = select.value;  // currentTarget is gone once the handler awaits
    if (board === current) return;
    if (!(await wrote('/api/ticket', {work_id: ticket.id, board}))) select.value = current;
  };
  return h('select', {class: 'board-of', title: 'Move to another board', 'aria-label': 'The board this ticket is on',
    onclick: event => event.stopPropagation(), onchange: moveTo},
  h('option', {value: '', selected: current === ''}, 'Board (first)'),
  ...B.boards.map(one => h('option', {value: one.name, selected: current === one.name}, one.name)));
}
function shownOnBoard(box, words) {
  const hidden = B.off.has(box.dataset.kind) || Boolean(words && !box.textContent.toLowerCase().includes(words));
  if (box.hidden !== hidden) box.hidden = hidden;  // a card that stays as it was is not written
}
const searched = () => $('#board .search').value.trim().toLowerCase();
/* The board's order of cards in a column: by their position, else as they were read; the sort is stable, so cards
 * with no position keep the order of `B.tickets`. */
const cardOrder = (one, two) => (one.position ?? 1e9) - (two.position ?? 1e9);
/* The board's columns, made once, each with its cards' list and its tally. */
const COLUMNS = new Map();
/* A ticket's fields as a card compares them: its place in the column, which a move above it renumbers, is not shown,
 * nor the age the server counts in seconds, which differs on every read; the page shows its own, `ago`. */
const unshownOnCard = (key, value) => (key === 'position' || key === 'age_seconds' ? undefined : value);
/* Everything a card shows: a card whose text is as it was keeps its node. Of its place only whether it is first or
 * last shows, on its order buttons; its chips' names are the names drawn, so a node renamed draws only its cards. */
function cardText(ticket, place, total, shared, find) {
  const status = ticket.done ? null : ticketStatus(ticket), ended = endedStatus(ticket);
  return JSON.stringify([shared, ticket, place === 0, place === total - 1, Boolean(waiting(ticket)), status, ended,
    waitsOn(ticket).map(handleOf), ROAM.figures.get(ticket.id)?.glyph || null,
    ago(ticket.done || ticket.taken || ticket.created),
    Boolean(ticket.taken && !ticket.done && D.sessions.some(one => one.work_id === ticket.id
      && one.state === 'running')),
    chipShown(assignedOf(ticket), find), (ticket.links || []).map(link => chipShown(link, find))], unshownOnCard);
}
/* The part at each address of the map shown, the first one there as `partAt` finds it, made once a draw. */
function addressIndex() {
  const index = new Map();
  for (const entry of S.elements.values()) if (!index.has(entry.element.address)) index.set(entry.element.address,
    entry.element);
  return address => index.get(address);
}
export function drawBoard() {
  // A card is drawn again only when what it shows changed, so an event that changes one ticket, or none, rebuilds
  // one card, or none, not all of them: every card drawn anew on each agent event, five or six times as an agent
  // started, held the page for seconds and the browser called it not responding (2026-10-19). A move renumbers the
  // places below it, and each map op counted up a number in every card's text, so one move or one op still made
  // every card again: 400 of 500 per move (2026-10-20). A card made again keeps open what the person opened.
  const opened = new Set([...$('#board').querySelectorAll('.card details[open]')]
    .map(box => `${box.closest('.card').dataset.id} ${box.className}`));
  fill($('#board .kinds'), [...KINDS, 'none'].map(kindToggle));
  if (!COLUMNS.size) fill($('#board .columns'), BOARD.map(([column, title]) => columnBox(column, title)));
  const shared = JSON.stringify([HARNESS.agents, HARNESS.default]), find = addressIndex();
  for (const [column, {cards, tally}] of COLUMNS) {
    const tickets = B.tickets.filter(ticket => columnOf(ticket) === column).sort(cardOrder);
    tally.textContent = String(tickets.length);
    keyedFill(cards, tickets.map((ticket, place) => ({key: ticket.id,
      text: cardText(ticket, place, tickets.length, shared, find),
      make: () => card(ticket, place, tickets.length, find)})));
  }
  const words = searched();
  for (const box of $('#board').querySelectorAll('.card')) shownOnBoard(box, words);
  if (opened.size) {
    for (const box of $('#board').querySelectorAll('.card details')) {
      if (opened.has(`${box.closest('.card').dataset.id} ${box.className}`)) box.open = true;
    }
  }
  $('#board .start-all').disabled = D.starting || !B.tickets.some(startsByItself);
}
/* A kind shown or hidden on the board. */
function kindToggle(kind) {
  const flip = () => { B.off.has(kind) ? B.off.delete(kind) : B.off.add(kind); drawBoard(); };
  return h('button', {class: `kindtoggle${B.off.has(kind) ? ' off' : ''}`, 'data-kind': kind,
    'aria-pressed': String(!B.off.has(kind)), onclick: flip}, kind === 'none' ? 'task' : kind);
}
/* One column of cards, made once, which takes a card dragged onto it; its cards and tally are filled by drawBoard. */
function columnBox(column, title) {
  const cards = h('div', {class: 'cards'}), tally = h('span', {class: 'tally'}, '0');
  cards.addEventListener('dragover', event => { event.preventDefault(); cards.classList.add('over'); });
  cards.addEventListener('dragleave', () => cards.classList.remove('over'));
  cards.addEventListener('drop', event => dropCard(event, cards, column));
  COLUMNS.set(column, {cards, tally});
  return h('div', {class: 'column', 'data-column': column}, h('div', {class: 'head'}, h('span', {}, title), tally),
    cards);
}
/* A card dropped in a column moves its ticket there, to the place it was dropped. Where it was is kept, so a move to
 * another column, which takes, finishes or opens the ticket again, can be undone. */
async function dropCard(event, cards, column) {
  event.preventDefault();
  cards.classList.remove('over');
  const id = event.dataTransfer.getData('text/plain');
  const others = [...cards.querySelectorAll('.card')].filter(box => box.dataset.id !== id);
  const above = box => { const at = box.getBoundingClientRect(); return event.clientY < at.top + at.height / 2; };
  const after = others.findIndex(above);
  const moved = B.tickets.find(ticket => ticket.id === id), from = moved ? columnOf(moved) : null;
  const was = moved ? B.tickets.filter(ticket => columnOf(ticket) === from).sort(cardOrder).indexOf(moved) : -1;
  if (!await wrote('/api/move', {work_id: id, column, position: after < 0 ? others.length : after, by: 'user'})) return;
  await renderBoard();
  if (from && from !== column) undoable(`Moved to ${COLUMN_NAMES[column]}.`, async () => {
    const back = await wrote('/api/move', {work_id: id, column: from, position: Math.max(0, was), by: 'user'});
    await renderBoard();
    return Boolean(back);
  });
}
/* The tickets the board draws, one card per finding: only work, a record the server marks is_work, one with a task or
 * a trouble, broken or missing marker, never a record with neither, such as a condition the intake once wrote for a
 * part that works, MAP-046; a record the intake closed as replaced by a newer condition is left out, and a finding
 * written with the same condition and note on an element and on a purpose record it holds or receives is drawn once,
 * at the element. */
export function boardTickets(records) {
  // done before the board's cutoff, it is in the Archive: the tickets the map holds are not all the board's; and only
  // the tickets on the board shown, the first board's being those on no named board
  records = records.filter(ticket => ticket.is_work && (!ticket.done || ticket.done >= B.cutoff)
    && String(ticket.map?.board || '') === B.board);
  const finding = ticket => !ticket.task && ticket.condition
    ? [ticket.condition, ticket.note || '', Boolean(ticket.done)].join('\n') : null;
  const atElements = new Set(records.filter(ticket => ticket.node_kind === 'element' && finding(ticket))
    .map(ticket => `${ticket.address}\n${finding(ticket)}`));
  const repeated = ticket => ticket.node_kind === 'join' && finding(ticket)
    && [ticket.receiver_address, ticket.provider_address].some(end => atElements.has(`${end}\n${finding(ticket)}`));
  return records.filter(ticket => !(ticket.done && (ticket.resolution || '').startsWith('Replaced by '))
    && !repeated(ticket));
}
/* The named boards, the person's need of 2026-10-20: a board gets a name, a new one can be made, a past one opened
 * again, and a ticket moved from one board to another, so work for a new effort goes to that effort's board. The first
 * board has no name. The board shown is kept per project in this browser; the boards and what is on them are the
 * project's, read from the server. One board is the project's active board, the map setting `board`, 2026-10-21:
 * tickets filed with no board land on it and only its tickets start by themselves. Activate and Remove beside the
 * select work as the base's Activate and Remove on the main page: a browser that never chose a board shows the active
 * one. */
const BOARD_KEY = project => `metaform.board.${project}`;
export async function drawBoards() {
  const box = $('#board .boards');
  if (B.boardsOf !== S.project) {
    B.boardsOf = S.project;
    let kept = null;
    try { kept = localStorage.getItem(BOARD_KEY(S.project)); } catch (error) { kept = null; }
    B.board = kept;
  }
  let all = null;
  try { all = (await read('boards')).boards || []; } catch (error) { all = null; }
  if (all === null) {  // a read that failed changes nothing: the board shown stays, with the names it had
    if (B.board === null) B.board = '';
    boardButtons();
    return;
  }
  B.boards = all.filter(one => !one.first);
  B.active = (all.find(one => one.active) || {name: ''}).name;
  // never chosen in this browser, or the board chosen was removed meanwhile: the active board is shown
  if (B.board === null || (B.board && !B.boards.some(one => one.name === B.board))) B.board = B.active;
  const activeMark = name => (name === B.active ? ' · active' : '');
  fill(box, [h('option', {value: ''}, `Board${B.boards.length ? ' (first)' : ''}${activeMark('')}`),
    ...B.boards.map(one => h('option', {value: one.name}, `${one.name} · ${one.open}${activeMark(one.name)}`)),
    h('option', {value: '', 'data-new': '1'}, 'New board…')]);
  box.value = B.board;
  boardButtons();
}
/* Activate is offered for a board that is not the active one; Remove for a named board that is not active. */
function boardButtons() {
  $('#board .board-activate').disabled = B.board === B.active;
  $('#board .board-remove').disabled = !B.board || B.board === B.active;
}
async function activateBoard() {
  const name = B.board, shown = name || 'the first board';
  if (name === B.active) return;
  if (!await confirmAct({title: `Make ${shown} the active board?`,
    text: 'Tickets filed with no board land on it, and only its tickets start by themselves. Every other board is '
      + 'set aside until it is activated.', verb: 'Activate', cancel: 'Keep it'})) return;
  $('#board .board-activate').disabled = true;
  const made = await wrote('/api/settings', {key: 'board', value: name});
  if (made) toast(`${shown} is the active board.`);
  await drawBoards();
}
async function removeBoard() {
  const name = B.board;
  if (!name || name === B.active) return;
  if (!await confirmAct({title: `Remove board ${name}?`,
    text: 'A board with tickets on it is refused: move them to another board first.', verb: 'Remove board',
    cancel: 'Keep it'})) return;
  const made = await wrote('/api/board-remove', {name});
  if (!made) return;
  B.board = '';
  try { localStorage.setItem(BOARD_KEY(S.project), ''); } catch (error) { /* a browser that keeps nothing */ }
  await renderBoard();
}
$('#board .board-activate').onclick = activateBoard;
$('#board .board-remove').onclick = removeBoard;
const NEW_BOARD = Symbol('new board');
async function chooseBoard(value) {
  if (value === NEW_BOARD) {
    const name = (window.prompt('Name the new board') || '').trim();
    $('#board .boards').value = B.board;
    if (!name) return;
    const made = await wrote('/api/board-add', {name});
    if (!made) return;
    value = name;
  }
  B.board = value;
  try { localStorage.setItem(BOARD_KEY(S.project), value); } catch (error) { /* a browser that keeps nothing */ }
  await renderBoard();
}
$('#board .boards').onchange = event => {
  const chosen = event.currentTarget.selectedOptions[0];
  chooseBoard(chosen?.dataset.new ? NEW_BOARD : event.currentTarget.value);
};
document.addEventListener('metaform:boards', () => { if (!$('#board').hidden) drawBoards(); });
export async function renderBoard() {
  if ($('#board').hidden || !S.project) return;
  // Distribute's count starts at Agents at once, dispatch_agents, until the person changes it here
  const count = $('#board .distribute input');
  if (!count.dataset.chosen && AUTO.agents) count.value = String(AUTO.agents);
  const project = S.project, metaform = S.base;  // the agents are read on dispatch events only, VIEW-018
  await drawBoards();
  if (S.project !== project) return;
  let found;
  // the server reads what the board shows, the open tickets and those done since its cutoff, never every ticket
  try { found = await read('work', {limit: 0, board: 'shown', on: B.board}); }
  catch (error) { toast(error.message); return; }
  if (S.project !== project || S.base !== metaform) return;  // a later choice's read draws its own tickets
  B.cutoff = found.cutoff || '';
  B.tickets = boardTickets(found.results || []);
  drawBoard();
  if (!$('#board .archive').hidden) await renderArchive();
}
/* The Archive: the tickets done before the board's cutoff, each still a record at its part of the map, read from the
 * server a page at a time in the order they were written, More reading the next; a row opens its part's history. */
const ARCHIVE_PAGE = 50;
async function renderArchive(after = null) {
  const list = $('#board .archive .rows'), more = $('#board .archive .more');
  const project = S.project, metaform = S.base;
  let found;
  try { found = await read('work', {limit: ARCHIVE_PAGE, board: 'archive', on: B.board, ...(after ? {after} : {})}); }
  catch (error) { toast(error.message); return; }
  if (S.project !== project || S.base !== metaform) return;
  const rows = (found.results || []).filter(ticket => ticket.is_work).map(archiveRow);
  if (after) list.append(...rows); else fill(list, rows);
  if (!list.children.length) fill(list, [h('p', {class: 'empty'}, 'Nothing is archived yet.')]);
  more.hidden = !found.next;
  more.dataset.after = found.next || '';
  $('#board .archive .since').textContent = found.cutoff ? `Done before ${found.cutoff.replace('T', ' ')}` : '';
}
function archiveRow(ticket) {
  const open = () => {
    const element = partAt(ticket.address);
    if (element) { select(element.id, true); history(element.id); }
  };
  return h('div', {class: 'row', 'data-id': ticket.id, onclick: open},
    h('span', {class: 'item'}, ticket.map?.item || ticket.map?.title || ticket.id.slice(0, 8)),
    h('span', {class: 'text'}, ...taskWords(ticket.task || ticket.note || '')),
    h('span', {class: 'address'}, ticket.address || ''),
    h('small', {class: 'when'}, `Done ${String(ticket.done).replace('T', ' ')}`),
    h('button', {class: 'btn sm quiet remove', type: 'button', title: 'Delete this ticket for good',
      onclick: async event => { event.stopPropagation(); const row = event.currentTarget.closest('.row');
        if (await removeTicket(ticket, event.currentTarget)) row?.remove(); }}, 'Delete'),
    ticket.resolution ? h('div', {class: 'resolution'}, ...linked(ticket.resolution)) : null);
}
$('#board .archive-toggle').onclick = async () => {
  const box = $('#board .archive'), showing = box.hidden;
  box.hidden = !showing;
  $('#board .columns').hidden = showing;
  $('#board .archive-toggle').setAttribute('aria-pressed', String(showing));
  if (showing) await renderArchive();
};
$('#board .archive .more').onclick = event => renderArchive(event.currentTarget.dataset.after || null);
/* Archive done tickets: every ticket done up to now goes to the Archive in one step; nothing is deleted, and Undo puts the
 * line that was before back. */
$('#board .line-in-sand').onclick = async () => {
  const board = B.board;  // the board shown keeps its own Archive and line
  const set = await wrote('/api/board-line', {board});
  if (!set) return;
  await renderBoard();
  undoable('Everything done up to now is in the Archive.', async () => {
    const back = await wrote('/api/board-line', {line: set.was, board});
    await renderBoard();
    return Boolean(back);
  });
};
$('#boardBtn').onclick = async () => {
  if (WS.reveal('board')) return;
  $('#board').hidden = false;
  await renderBoard();
};
$('#board .close').onclick = () => { $('#board').hidden = true; };
overlay($('#board'), {kind: 'dialog', focus: '.search'});
$('#board .start-all').onclick = async () => {
  await renderBoard();
  const tickets = B.tickets.filter(startsByItself).sort((one, two) => (one.position ?? 1e9) - (two.position ?? 1e9));
  startWindow('Start all agents', tickets, true);
};
// Distribute, VIEW-040: the tickets that start by themselves get the first N agents' glyphs in turn, in board order;
// a held Backlog ticket gets none, since it waits for the person to release it.
// The glyphs the tickets had before are kept, so Undo gives each back its own.
async function distribute() {
  const agents = Number($('#board .distribute input').value);
  if (!Number.isInteger(agents) || agents < 1) return toast('Work is distributed over a whole number of agents.');
  const before = new Map(B.tickets.map(ticket => [ticket.id, ownGlyph(ticket) || '']));
  if (!await wrote('/api/distribute', {agents})) return;
  await renderBoard();
  const moved = ticket => before.has(ticket.id) && before.get(ticket.id) !== (ownGlyph(ticket) || '');
  const changed = B.tickets.filter(moved);
  const putBack = async () => {
    let all = true;
    for (const ticket of changed) {
      all = Boolean(await wrote('/api/ticket', {work_id: ticket.id, glyph: before.get(ticket.id)})) && all;
    }
    await renderBoard();
    return all;
  };
  const said = `Distributed ${plural(changed.length, 'ticket')} over ${plural(agents, 'agent')}.`;
  if (changed.length) undoable(said, putBack);
}
$('#board .distribute button').onclick = distribute;
$('#board .distribute input').addEventListener('input', event => { event.target.dataset.chosen = '1'; });
$('#board .search').oninput = () => {
  const words = searched();
  for (const box of $('#board').querySelectorAll('.card')) shownOnBoard(box, words);
};
$('#board .add').onclick = () => {
  const first = S.selected && S.elements.has(S.selected) ? S.selected : [...S.elements.keys()][0];
  if (first) giveWork(first); else toast('Add a card once the project has a map.');
};
