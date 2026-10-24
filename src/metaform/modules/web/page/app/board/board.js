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
import {B, KINDS, BOARD, conditionLabel, partAt, chipShown, nodeChip, linked, taskWords, ago, dated, ticketHead}
  from '/page/app/board/refs.js';
import {COLUMN_NAMES, columnOf, ageOf, wrote, takenWords} from '/page/app/board/history.js';
import {requestHoldReason, holdReason} from '/page/app/board/holds.js';
import {ticketIntegration} from '/page/app/board/integration.js';
import {D, waiting, ticketPart, ownGlyph, startWindow, renderAgents} from '/page/app/agents/dispatch.js';
import {giveWork, named} from '/page/app/task/task.js';
import {HARNESS, agentName, agentSelect, pickerOptions} from '/page/app/agents/pickers.js';
import {posted} from '/page/app/intake/intake.js';
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
function ticketControls(ticket, settings = null) {
  const kept = ticket.map || {};
  const change = async (fields, control) => {
    control.disabled = true;
    try {
      const saved = await wrote('/api/ticket', {work_id: ticket.id, ...fields});
      if (saved) await renderBoard();
      return Boolean(saved);
    }
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
    runtimeControls(ticket, chosen, change, settings),
    eligibilityPicker(eligibleAgents(ticket), saveEligible),
    glyphPick(kept, change),
    // only while an agent runs on it: an ended agent's ticket offers Back to To do on its card (UX recheck 2026-10-17)
    ticket.taken && !ticket.done && D.sessions.some(one => one.work_id === ticket.id && one.state === 'running')
      ? recallButton(ticket) : null,
    ticket.done ? null : holdButton(ticket, change));
  return box;
}
/* Runtime choices belong to this ticket. Read the agent's offered values only when its settings are opened. */
function runtimeControls(ticket, agent, change, settings) {
  const kept = ticket.map || {}, project = S.project, base = S.base;
  const fields = ['model', 'effort', 'fast'];
  const picks = fields.map(key => h('select', {class: key,
    'aria-label': key === 'model' ? 'Model' : key === 'fast' ? 'Fast mode' : 'Thinking level',
    disabled: true, onchange: async event => {
      const pick = event.currentTarget;
      if (!await change({[key]: pick.value || 'none'}, pick)) pick.value = kept[key] || '';
    }}, h('option', {value: kept[key] || ''}, kept[key] || 'Project setting')));
  const hint = h('small', {class: 'runtime-hint'}, 'Open settings to load runtime choices.');
  const box = h('div', {class: 'runtime-settings'},
    fields.map((key, index) => h('label', {}, key === 'model' ? 'Model ' : key === 'fast' ? 'Fast ' : 'Thinking ',
      picks[index])), hint);
  let reading = null;
  const load = async () => {
    try {
      const found = (await read('dispatch-options', {agent})).agents?.find(one => one.agent === agent);
      if (S.project !== project || S.base !== base) return;
      fields.forEach((key, index) => {
        if (key === 'fast') {
          const option = found?.settings?.find(one => one.type === 'boolean'
            && (one.key === 'model_config' || one.category === 'model_config'));
          const chosen = kept.fast ?? '';
          const current = option?.chosen ?? option?.current;
          const name = current === true || current === 'true' ? 'On'
            : current === false || current === 'false' ? 'Off' : null;
          const unavailable = found?.next ? 'Fast availability is unknown until its list is read.'
            : 'This agent does not advertise Fast mode.';
          fill(picks[index], h('option', {value: '', selected: !chosen}, option
            ? name ? `Project setting: ${name}` : 'Project setting' : 'Unavailable'),
          chosen || option ? ['true', 'false'].map(value => h('option', {value, selected: value === chosen},
            value === 'true' ? 'On' : 'Off')) : null);
          picks[index].disabled = !option;
          picks[index].title = option ? 'Changes apply to this ticket’s next start.' : unavailable;
          return;
        }
        const option = found?.settings?.find(one => key === 'effort'
          ? ['effort', 'thought_level'].includes(one.key) || one.category === 'thought_level'
          : one.key === 'model' || one.category === 'model');
        const choices = option?.choices || [], current = option?.chosen ?? option?.current;
        // the agent's own default is a ticket's choice only where the agent offers one; Project setting sends nothing
        const listed = (option?.picks || []).filter(one => one.value !== 'default'
          || choices.some(choice => choice.value === 'default'));
        const name = listed.find(one => one.value === current)?.label || current;
        const chosen = kept[key] || '';
        fill(picks[index], h('option', {value: '', selected: !chosen},
          name ? `Project setting: ${name}` : 'Project setting'),
        chosen && !listed.some(one => one.value === chosen)
          ? h('option', {value: chosen, selected: true}, chosen) : null,
        pickerOptions(listed, chosen));
        picks[index].disabled = !choices.length;
      });
      fill(hint, found?.next ? [`${agentName(agent)} has not run here, so its models are not known yet. `,
        h('button', {type: 'button', class: 'btn sm quiet', title: 'Starts it once, with no prompt, and reads the '
          + 'models and thinking levels it offers', onclick: readOffered}, 'Read its list')]
        : 'Changes apply to this ticket’s next start.');
    } catch (error) { hint.textContent = error.message; reading = null; }
  };
  const readOffered = async event => {
    event.currentTarget.disabled = true;
    hint.textContent = `Starting ${agentName(agent)} once to read its list…`;
    const done = await posted('/api/settings/choices', {key: `dispatch_${agent}_model`});
    if (!done.ok) { hint.textContent = done.body.error || 'Its list could not be read.'; return; }
    reading = load();
  };
  settings?.addEventListener('toggle', () => {
    if (settings.open && !reading) reading = load();
  });
  return box;
}
/* Three compact words expose the saved launch choice. Decision provenance stays available on hover. */
function runtimeSummary(ticket) {
  const kept = ticket.map || {}, decision = kept.decision;
  const agent = kept.agent || defaultAgent(ticket.address || ticket.receiver_address, kept.paths || []);
  const confidence = Number.isFinite(decision?.confidence) ? ` (${Math.round(decision.confidence * 100)}%)` : '';
  const title = decision ? `Chosen by ${decision.decider}${confidence}. ${decision.reason || ''}`.trim()
    : 'Agent, model and thinking level. Default follows the project setting.';
  return h('span', {class: 'runtime-choice', title}, `${agent} ${kept.model || 'default'} ${kept.effort || 'default'}`);
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
      toast(`${agentName(session?.agent)} recalled. Its ticket stays on the board.`);
      await renderAgents();
      await renderBoard();
    } else event.target.disabled = false;
  };
  return h('button', {class: 'btn sm recall', type: 'button',
    title: 'Recall the agent working this ticket; the ticket goes back on the board', onclick: recall}, 'Recall agent');
}
/* Hold hides the ticket from agents and automatic starts; Release shows it to them again. */
function holdButton(ticket, change) {
  const held = ticket.held || ticket.map?.hold;
  return h('button', {class: held ? 'btn sm hold on' : 'btn sm hold', type: 'button',
    title: held ? 'Release it: agents and automatic starts see it again'
      : 'Hold it: hidden from agents and automatic starts',
    onclick: event => {
      const hold = !held, hold_reason = hold ? requestHoldReason() : null;
      if (hold && hold_reason === null) return;
      change(hold ? {hold, hold_reason} : {hold: false, held: false}, event.currentTarget);
    }}, held ? 'Release hold' : 'Hold');
}
/* A card's node chips: the part it is assigned and those it links for reference. */
const assignedOf = ticket => ({kind: ticket.node_kind, id: ticket.node_id, address: ticket.address,
  ends: [ticket.receiver_address, ticket.provider_address]});
function card(ticket, place, total, find) {
  const settings = h('details', {class: 'ticket-settings', onclick: event => event.stopPropagation()},
    h('summary', {}, ticket.held || ticket.map?.hold ? 'Held · agent settings' : 'Agent settings'));
  settings.append(ticketControls(ticket, settings));
  // the place counted when it is clicked, not when it was made: a card a move elsewhere left as it was is not made again
  const move = async (to, by = 0) => {
    const column = columnOf(ticket);
    const at = B.tickets.filter(one => columnOf(one) === column).sort(cardOrder).findIndex(one => one.id === ticket.id);
    const position = to ?? Math.max(0, at + by);
    const hold_reason = column === 'backlog' ? requestHoldReason() : null;
    if (column === 'backlog' && hold_reason === null) return;
    if (await wrote('/api/move', {work_id: ticket.id, column, position, hold_reason})) await renderBoard();
  };
  const open = () => {
    const project = S.project, base = S.base || '';
    import('/page/app/board/detail.js').then(({ticketDetail}) => ticketDetail(ticket.id, project, base));
  };
  const box = h('div', {class: 'card', draggable: 'true', 'data-id': ticket.id, 'data-kind': ticket.kind || 'none',
    onclick: open},
    // its number and one-line title first, so a ticket is found by either at a glance; the body shows on Inspect
    h('div', {class: 'lead'}, ticketHead(ticket)),
    cardTop(ticket),
    holdReason(ticket),
    h('div', {class: 'nodes'}, nodeChip(assignedOf(ticket), 'assigned', find),
      ...(ticket.links || []).map(link => nodeChip(link, 'ref', find))),
    cardProgress(ticket),
    cardEnded(ticket),
    ticket.resolution ? h('div', {class: 'resolution'}, ...linked(ticket.resolution)) : null,
    ticketIntegration(ticket),
    cardActs(ticket, place, total, move),
    settings);
  if (ticket.held || ticket.map?.hold) box.classList.add('on-hold');
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
  runtimeSummary(ticket), conditionLabel(ticket),
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
/* Whether an explicit Start all selection includes a ticket: waiting in To do, not held in Backlog, not held from
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
  const hold_reason = column === 'backlog' ? requestHoldReason() : null;
  if (column === 'backlog' && hold_reason === null) return;
  if (!await wrote('/api/move', {work_id: id, column, position: after < 0 ? others.length : after,
    by: 'user', hold_reason})) return;
  await renderBoard();
  if (from && from !== column) undoable(`Moved to ${COLUMN_NAMES[column]}.`, async () => {
    const hold_reason = from === 'backlog' ? requestHoldReason() : null;
    if (from === 'backlog' && hold_reason === null) return false;
    const back = await wrote('/api/move', {work_id: id, column: from, position: Math.max(0, was),
      by: 'user', hold_reason});
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
  records = records.filter(ticket => ticket.is_work
    && (!ticket.done || ticket.done >= B.cutoff || ticket.integration?.action)
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
const BOARDS = {all: [], wipes: []};
export async function drawBoards(wiped = false) {
  const box = $('#board .boards');
  if (B.boardsOf !== S.project) {
    B.boardsOf = S.project;
    let kept = null;
    try { kept = localStorage.getItem(BOARD_KEY(S.project)); } catch (error) { kept = null; }
    B.board = kept;
  }
  let found = null;
  try { found = await read('boards'); } catch (error) { found = null; }
  if (found === null) {  // a read that failed changes nothing: the board shown stays, with the names it had
    if (B.board === null) B.board = '';
    boardButtons();
    return;
  }
  const all = found.boards || [];
  BOARDS.all = all;
  BOARDS.wipes = found.wipes || [];
  B.boards = all.filter(one => !one.first);
  B.active = (all.find(one => one.active) || {name: ''}).name;
  if (wiped) {
    B.board = '';
    try { localStorage.setItem(BOARD_KEY(S.project), ''); } catch (error) { /* a browser that keeps nothing */ }
  }
  // never chosen in this browser, or the board chosen was removed meanwhile: the active board is shown
  if (B.board === null || (B.board && !B.boards.some(one => one.name === B.board))) B.board = B.active;
  const activeMark = name => (name === B.active ? ' · active' : '');
  fill(box, [h('option', {value: ''}, `Board${B.boards.length ? ' (first)' : ''}${activeMark('')}`),
    ...B.boards.map(one => h('option', {value: one.name}, `${one.name} · ${one.open}${activeMark(one.name)}`)),
    h('option', {value: '', 'data-new': '1'}, 'New board…'),
    h('option', {value: '', 'data-wipe': '1'}, 'Wipe this board…'),
    BOARDS.wipes.length ? h('optgroup', {label: 'Wiped boards'}, ...BOARDS.wipes.map(one =>
      h('option', {value: `restore:${one.stamp}`, 'data-backup': one.stamp, 'data-board': one.board},
        `Restore ${one.board || 'Board (first)'} · ${one.tickets} tickets · ${one.stamp}`))) : null]);
  box.value = B.board;
  B.cutoff = all.find(one => one.name === B.board)?.cutoff || B.cutoff;
  boardButtons();
  // One bulk refresh reads the visible time window once, keeping open tickets on other boards for map progress.
  return all.reduce((cutoff, one) => one.cutoff && (!cutoff || one.cutoff < cutoff) ? one.cutoff : cutoff, '');
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
$('#board .unhold-all').onclick = async event => {
  const button = event.currentTarget;
  const scope = {project: S.project, base: S.base};
  button.disabled = true;
  try {
    const preview = await read('held-work', scope), held = preview.results || [];
    const review = held.map(ticket => h('span', {class: 'held-work-review', 'data-id': ticket.id},
      h('strong', {}, ticket.title || ticket.task || ticket.id), h('br'),
      h('small', {}, `${ticket.id} · ${ticket.map?.board || 'First board'} · ${ticket.base}`), h('br'),
      ticket.map?.hold_reason?.trim() ? `Reason and release risk: ${ticket.map.hold_reason}`
        : 'No hold reason or release-risk explanation was recorded.'));
    if (!await confirmAct({title: `Release ${held.length} work hold${held.length === 1 ? '' : 's'}?`,
      text: [held.length ? 'Review every hold before releasing it. Autostart controls automatic starts.'
        : 'No open work tickets are held.', ...review], verb: 'Unhold all', cancel: 'Keep holds', danger: false})) return;
    const result = await wrote('/api/unhold-all', {...scope, revision: preview.revision, hold_preview: held});
    if (result) toast(result.review_changed > 0
      ? `Released ${result.changed} held tickets. ${result.review_changed} holds remain for another review.`
      : `Released ${result.changed} held ticket${result.changed === 1 ? '' : 's'}.`);
  } catch (error) { toast(error.message); }
  finally { button.disabled = false; }
};
async function wipeBoard() {
  const name = B.board, board = BOARDS.all.find(one => one.name === name), box = $('#board .boards');
  box.value = name;
  if (!board) return;
  const counts = BOARD.map(([column, label]) => `${label}: ${board.columns?.[column] || 0}`).join('\n');
  if (!window.confirm(`Wipe ${name ? `board "${name}"` : 'the first board'}?\n\n${counts}\n\n`
    + 'A backup is kept. Running sessions stop. The map stays.')) return;
  box.disabled = true;
  try {
    const made = await wrote('/api/board-wipe', {name});
    if (made) toast(`Board wiped. Backup ${made.backup}. Sessions stopped: ${made.sessions_stopped.length}.`);
  } finally { box.disabled = false; }
}
async function restoreBoard(chosen) {
  const box = $('#board .boards');
  box.value = B.board;
  box.disabled = true;
  try {
    const made = await wrote('/api/board-restore', {name: chosen.dataset.board || '', backup: chosen.dataset.backup});
    if (made) toast(`Restored ${chosen.dataset.board || 'the first board'}.`);
  } finally { box.disabled = false; }
}
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
  if (chosen?.dataset.wipe) return wipeBoard();
  if (chosen?.dataset.backup) return restoreBoard(chosen);
  chooseBoard(chosen?.dataset.new ? NEW_BOARD : event.currentTarget.value);
};
document.addEventListener('metaform:boards', () => { if (!$('#board').hidden) drawBoards(); });
export async function renderBoard() {
  if ($('#board').hidden || !S.project) return;
  // Distribute's count starts at Agents at once, dispatch_agents, until the person changes it here
  const count = $('#board .distribute input');
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
  await renderAgents(B.tickets.map(ticket => ticket.id));
  if (S.project !== project || S.base !== metaform) return;
  drawBoard();
}
/* The Archive: the project folder's git history, VIEW-037, since a done ticket becomes its commit and is shed after.
 * One row per commit, newest first, read from the server a page at a time, More reading the next: its number
 * (<address>#<n>), its subject, its node, which opens it on the map, its agent and when. A commit made by hand carries no
 * trailer and is listed too, marked so, so the history is whole. Filtered by board, node and its leaves, days, and words
 * in the message. A row opened shows the commit's message, the map parts its files belong to, and each file's diff as
 * an agent's tool call shows it. A commit Metaform makes reaches an open Archive on the live stream, `metaform:commits`:
 * its first page is read again and the commits new since are put on top. */
const ARCHIVE = {busy: false, again: false};
const archiveBox = () => $('#board .archive');
function archiveFilters() {
  const box = archiveBox(), value = name => box.querySelector(name).value.trim();
  const board = box.querySelector('.by-board').value;
  return {...(board === '*' ? {} : {board}), ...(value('.by-node') ? {node: value('.by-node')} : {}),
    ...(value('.since') ? {since: value('.since')} : {}), ...(value('.until') ? {until: value('.until')} : {}),
    ...(value('.words') ? {words: value('.words')} : {})};
}
/* The board filter's choices: every board, the first, and each named board, the one chosen kept. */
function archiveBoards() {
  const pick = archiveBox().querySelector('.by-board'), chosen = pick.value || '*';
  fill(pick, [h('option', {value: '*'}, 'Every board'), h('option', {value: ''}, 'First board'),
    ...B.boards.map(one => h('option', {value: one.name}, one.name))]);
  pick.value = [...pick.options].some(option => option.value === chosen) ? chosen : '*';
}
async function renderArchive(after = null) {
  const list = archiveBox().querySelector('.rows'), more = archiveBox().querySelector('.more');
  const project = S.project;
  let found;
  try { found = await read('commits', {...archiveFilters(), ...(after ? {after} : {})}); }
  catch (error) { toast(error.message); fill(list, [h('p', {class: 'empty'}, error.message)]); more.hidden = true; return; }
  if (S.project !== project) return;
  const rows = (found.commits || []).map(commitRow);
  if (after) list.append(...rows); else fill(list, rows);
  if (!list.children.length) fill(list, [h('p', {class: 'empty'}, 'No commits match.')]);
  more.hidden = !found.next;
  more.dataset.after = found.next || '';
}
/* A commit made while the Archive is open: its first page read again, and the commits not listed yet put on top, in
 * order, so the rows the person paged to and opened stay. A burst of commits reads once more, never once each. */
async function archiveHeard() {
  if (ARCHIVE.busy) { ARCHIVE.again = true; return; }
  ARCHIVE.busy = true;
  try {
    do {
      ARCHIVE.again = false;
      const project = S.project, list = archiveBox().querySelector('.rows');
      const found = await read('commits', archiveFilters()).catch(() => null);
      if (!found || S.project !== project || archiveBox().hidden) return;
      const listed = new Set([...list.querySelectorAll('.row')].map(row => row.dataset.sha));
      const fresh = (found.commits || []).filter(one => !listed.has(one.sha));
      if (!fresh.length) continue;
      if (!listed.size) { await renderArchive(); continue; }
      list.prepend(...fresh.map(commitRow));
    } while (ARCHIVE.again);
  } finally { ARCHIVE.busy = false; }
}
document.addEventListener('metaform:commits', () => {
  if (!$('#board').hidden && !archiveBox().hidden) archiveHeard();
});
/* A node named by a commit, by its name on the map shown; a press opens it there. One not on this map is its address. */
function commitNode(address) {
  if (!address) return h('span', {class: 'node none'});
  const element = partAt(address);
  return h('button', {class: 'node', type: 'button', disabled: !element,
    title: element ? `Open ${address} on the map` : `${address}: not on the map shown`,
    onclick: event => { event.stopPropagation(); select(element.id, true); }}, element ? named(element) : address);
}
function commitRow(one) {
  // reading and selecting in an opened commit never closes its row
  const detail = h('div', {class: 'commit', hidden: true, onclick: event => event.stopPropagation()});
  const open = () => {
    detail.hidden = !detail.hidden;
    row.classList.toggle('open', !detail.hidden);
    if (!detail.hidden && !detail.childElementCount) commitDetail(one.sha, detail);
  };
  const row = h('div', {class: one.hand ? 'row hand' : 'row', 'data-sha': one.sha, onclick: open},
    one.number ? h('span', {class: 'item'}, one.number)
      : one.hand ? h('span', {class: 'item by-hand', title: 'Made by hand: it carries no ticket trailer'}, 'by hand')
        : h('span', {class: 'item', title: `Ticket ${one.ticket}`}, `ticket ${one.ticket.slice(0, 8)}`),
    h('span', {class: 'text'}, one.subject),
    commitNode(one.node),
    h('small', {class: 'agent'}, one.agent || one.author || ''),
    h('small', {class: 'when', title: dated(one.when)}, ago(one.when)),
    detail);
  return row;
}
/* One commit opened: its message whole, the parts of the map its files belong to, and each file's diff as an agent's
 * tool call shows it, read once. A long commit draws its first files' diffs and offers the rest, each drawn when asked
 * for, so the page never stalls on a commit of thousands of lines. */
const OPENED_DIFF = 200_000;  // characters of diff drawn at once when a commit opens
async function commitDetail(sha, box) {
  const project = S.project;
  fill(box, [h('p', {class: 'hint'}, 'Reading the commit…')]);
  let found;
  try { found = await read('commit', {sha}); }
  catch (error) { fill(box, [h('p', {class: 'empty'}, error.message)]); return; }
  if (S.project !== project) return;
  const {fileDetail, nodeChips} = await import('/page/app/session/tools.js');
  let drawn = 0;
  const file = diff => {
    const now = drawn < OPENED_DIFF;
    drawn += (diff.patch || '').length;
    if (now || !diff.patch) return fileDetail(diff);
    const held = fileDetail({...diff, patch: ''});
    held.append(h('button', {class: 'btn sm quiet', type: 'button',
      onclick: () => held.replaceWith(fileDetail(diff))}, 'Show the diff'));
    return held;
  };
  fill(box, [h('div', {class: 'meta'}, h('code', {class: 'sha'}, found.sha), h('span', {}, found.author),
    h('span', {}, dated(found.when))),
  h('pre', {class: 'message'}, ...linked(found.message)),
  found.nodes?.length ? h('div', {class: 'chips'}, h('small', {}, 'Map parts'), nodeChips(found.nodes)) : null,
  h('div', {class: 'files'}, (found.files || []).map(file))]);
}
$('#board .archive-toggle').onclick = async () => {
  const box = archiveBox(), showing = box.hidden;
  box.hidden = !showing;
  $('#board .columns').hidden = showing;
  $('#board .archive-toggle').setAttribute('aria-pressed', String(showing));
  if (showing) { archiveBoards(); await renderArchive(); }
};
$('#board .archive .more').onclick = event => renderArchive(event.currentTarget.dataset.after || null);
for (const control of ['.by-board', '.by-node', '.since', '.until', '.words']) {
  $(`#board .archive ${control}`).addEventListener('change', () => renderArchive());
}
/* Completed commits retain archived tickets. Missing Git proof keeps their records. */
$('#board .line-in-sand').onclick = async () => {
  const board = B.board;  // the board shown keeps its own Archive and line
  const set = await wrote('/api/board-line', {board});
  if (!set) return;
  await renderBoard();
  const kept = set.kept || [];
  toast(`${(set.removed || []).length} tickets archived in Git.` +
    (kept.length ? ` ${kept.length} kept: ${kept.map(one => `${one.item}: ${one.fault}`).join(' ')}` : ''));
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
