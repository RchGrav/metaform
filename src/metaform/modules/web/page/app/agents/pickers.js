/* The agents a person starts, VIEW-039: harnesses read from dispatch, the default agent, the pickers, and the chat's
 * tab. */
import '/page/app/search/search.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {toast, undoable, choice} from '/page/app/core/controls.js';
import {FRAMED, S} from '/page/app/core/reads.js';
import {plural} from '/page/app/memory/manage.js';
import {DOCK} from '/page/app/dock/embody.js';
import {drawBoard} from '/page/app/board/board.js';
import {wrote} from '/page/app/board/history.js';
import {D} from '/page/app/agents/dispatch.js';
import {getJson} from '/page/app/panel/prompts.js';

/* ---------- the agents a person starts: one list, from the dispatch module, VIEW-039 ----------
 * Which agents there are, which of them this machine can run, which is the default and how many more may be summoned
 * now are the dispatch module's answer, `GET /api/dispatch-agents`; the page keeps no list of its own. Every place an
 * agent is started offers the same picker: an agent not found is shown with how to set it up, the default is marked,
 * and the star beside the picker makes the chosen agent the default in one click. */
export const HARNESS = {project: null, enabled: null, default: null, room: null, free: null, slots: null, agents: [],
  next: null,
  error: null, reading: null, read: 0, pickers: new Set(), frontend: new Set()};  // frontend: dispatch's front-end address words
// the agent new chats, issues and intakes start with; none chosen is the default
const SUMMON = {agent: null, chosen: false};
export async function readHarnesses() {
  const project = S.project;
  if (!project || FRAMED) return HARNESS;
  if (HARNESS.reading && HARNESS.project === project) return HARNESS.reading;
  const reading = HARNESS.reading = readAgents(project);
  HARNESS.project = project;
  try { return await reading; } finally { if (HARNESS.reading === reading) HARNESS.reading = null; }
}
/* One read of the agents for the project, kept only while the page is still on it. */
async function readAgents(project) {
  try {
    const found = await getJson(`/api/dispatch-agents?project=${encodeURIComponent(project)}`);
    if (S.project === project) {
      Object.assign(HARNESS, {project, enabled: found.enabled !== false, default: found.default ?? null,
        room: found.room ?? null, free: found.free ?? null, slots: found.slots ?? null, agents: found.agents || [],
        next: found.next || null,
        error: null, read: Date.now(), frontend: new Set(found.frontend || [])});
      if (!$('#board').hidden) drawBoard();  // a card's own agent select lists them too
    }
  } catch (error) {
    if (S.project === project) Object.assign(HARNESS, {project, error: error.message, read: Date.now()});
  }
  paintPickers();
  return HARNESS;
}
export function forgetHarnesses() {
  Object.assign(HARNESS, {project: null, enabled: null, default: null, room: null, free: null, slots: null, agents: [],
    next: null,
    error: null, reading: null, read: 0});
  Object.assign(SUMMON, {agent: null, chosen: false});
  paintPickers();
}
const harness = agent => HARNESS.agents.find(one => one.agent === agent) || null;
export const agentName = agent => harness(agent)?.label || agent || 'An agent';
/* The agent a start uses when the person has chosen none: the one offered when this machine runs it, else the
 * default, else the first it runs. An agent the person chose stays chosen, found or not, so nothing they did not
 * choose is started in its place. */
function usableAgent(chosen) {
  const found = [chosen, HARNESS.default].map(harness).find(one => one?.available);
  return found?.agent || HARNESS.agents.find(one => one.available)?.agent || chosen || HARNESS.default || null;
}
export function paintPickers() {
  for (const box of HARNESS.pickers) {
    if (box.isConnected || box.kept) box.paint(); else HARNESS.pickers.delete(box);
  }
}
/* Make one agent the default, kept as `metaform set --dispatch-agent` keeps it; Undo gives the one before back. */
export async function makeDefault(agent, {undo = true} = {}) {
  const before = HARNESS.default;
  if (!agent || agent === before) return false;
  const saved = await wrote('/api/dispatch-agents', {default: agent});
  if (!saved) return false;
  Object.assign(HARNESS, {enabled: saved.enabled !== false, default: saved.default ?? agent,
    room: saved.room ?? HARNESS.room, agents: saved.agents || HARNESS.agents, read: Date.now()});
  paintPickers();
  const said = `${agentName(agent)} is the default agent.`;
  if (undo && before) undoable(said, () => makeDefault(before, {undo: false}));
  else toast(said);
  return true;
}
/* The picker. `holder` keeps its choice, {agent, chosen}, so pickers that share one, as the starts that summon an agent
 * do, show the same; `chosen` says the person picked it, and an agent only offered, the default or a ticket's area's,
 * gives way to one this machine runs. `room` says how many more agents may be summoned now, `star` offers to make the
 * chosen agent the default, `up` opens the list upward. `kept`: the picker lives on outside the page, moved into each
 * form that shows it. `exact` shows the agent held as it is, found or not, as the default itself is shown. */
export function agentPicker({label = 'Agent', holder = null, onchange = null, room = false, star = true, up = false,
  kept = false, exact = false} = {}) {
  const slot = holder || {agent: null, chosen: false};
  const choose = value => { Object.assign(slot, {agent: value, chosen: true}); paintPickers(); onchange?.(value); };
  const pick = choice({label, options: [], value: null, onchange: choose});
  if (up) pick.classList.add('up');
  const make = h('button', {class: 'btn icon quiet star', type: 'button', 'aria-pressed': 'false',
    onclick: () => makeDefault(box.value())}, h('i', {class: 'i i-star', 'aria-hidden': 'true'}));
  const note = h('small', {class: 'pickernote'});
  const box = h('div', {class: 'agentpicker'}, h('div', {class: 'pickerrow'}, pick, star ? make : null), note);
  box.kept = kept;
  let held = false;  // while what it starts is being started, the choice waits
  box.hold = on => { held = on; box.paint(); };
  box.set = value => { Object.assign(slot, {agent: value, chosen: false}); box.paint(); };  // offered, not chosen
  box.value = () => HARNESS.enabled === false ? null : exact || slot.chosen ? slot.agent : usableAgent(slot.agent);
  box.paint = () => {
    const off = HARNESS.enabled === false, none = !off && HARNESS.project && !HARNESS.agents.some(one => one.available);
    pick.hidden = off;
    const options = HARNESS.agents.map(pickerOption);
    const value = box.value();
    pick.set(options, value);
    pick.querySelector(':scope > .btn').disabled = !options.length || held;
    const chosen = harness(value);
    make.hidden = off || !chosen;
    make.disabled = !chosen?.available || chosen.default;
    make.setAttribute('aria-pressed', String(Boolean(chosen?.default)));
    make.classList.toggle('on', Boolean(chosen?.default));
    const said = chosen?.default ? `${chosen.label} is the default agent`
      : chosen ? `Make ${chosen.label} the default agent` : 'Make it the default';
    make.title = said;
    make.setAttribute('aria-label', said);
    pickerNote(note, off, none, room);
  };
  HARNESS.pickers.add(box);
  box.paint();
  if (HARNESS.project !== S.project || Date.now() - HARNESS.read > 15000) readHarnesses();
  return box;
}
/* An agent in the picker: the default marked, one not found disabled with how to set it up. */
function pickerOption(one) {
  return {value: one.agent, label: one.label,
    badge: one.default ? 'Default' : one.available ? null : 'Not found',
    ok: one.available ? (one.default || undefined) : false,
    disabled: !one.available,
    hint: one.available ? null : ['Not found on this machine. Set its start command with ',
      h('code', {}, one.next || `metaform set --dispatch-${one.agent} "<command>"`)]};
}
/* The line under the picker: agents off, a failed read, none found, or how many more may start now. */
function pickerNote(note, off, none, room) {
  note.className = 'pickernote';
  if (off) {
    note.classList.add('off');
    fill(note, 'Agents are off here: ', h('code', {}, HARNESS.next || 'metaform enable dispatch'));
  } else if (HARNESS.error) { note.classList.add('off'); fill(note, HARNESS.error); }
  else if (none) {
    note.classList.add('off');
    fill(note, 'No agent is found on this machine. Set one up with ',
      h('code', {}, HARNESS.agents[0]?.next || 'metaform dispatch agents'));
  } else if (room && HARNESS.room !== null) {
    fill(note, HARNESS.room > 0 ? `${plural(HARNESS.room, 'more agent')} can start now.`
      : 'Every agent slot is in use: it starts when one is free.');
  } else fill(note);
  note.hidden = !note.textContent;
  note.title = note.textContent;
}
/* A plain select of the same agents, for a ticket's own preferred agent on its card, which starts nothing. */
export function agentSelect(value, onchange, label = 'Preferred agent') {
  const options = [...HARNESS.agents.map(one => [one.agent, one.available ? one.label : `${one.label} (not found)`]),
    ...(value && !harness(value) ? [[value, value]] : [])];
  return h('select', {class: 'agent', 'aria-label': label, onchange: event => onchange(event.target.value)},
    options.map(([agent, text]) => h('option', {value: agent, selected: agent === value}, text)));
}
export const summonAgent = () => HARNESS.enabled === false ? null
  : SUMMON.chosen ? SUMMON.agent : usableAgent(SUMMON.agent);
/* The pickers that live on: the chat dock's, the one of the issue form, the default in the Agents menu. */
export const PICKERS = {};
export function summonPicker(name, options = {}) {
  return PICKERS[name] ||= agentPicker({label: 'Agent for new chats', holder: SUMMON, room: true, kept: true,
    ...options});
}

/* The chat's tab says when agents wait for the person's permission or answer, and how many. */
export function drawDockTab() {
  const waiting = (D.asking || []).length, tab = $('#dockTab');
  tab.classList.toggle('asks', waiting > 0);
  const unread = !waiting && DOCK.unread;  // the agent wrote while the chat was put away
  tab.classList.toggle('unread', unread);
  fill(tab, h('span', {}, 'Chat'), waiting ? h('b', {class: 'asking', 'aria-hidden': 'true'}, String(waiting))
    : unread ? h('i', {class: 'newdot', 'aria-hidden': 'true'}) : null);
  tab.setAttribute('aria-label', waiting ? `Open the chat: ${plural(waiting, 'agent waits', 'agents wait')} for you`
    : unread ? 'Open the chat: a new message' : 'Open the chat with an agent');
}
