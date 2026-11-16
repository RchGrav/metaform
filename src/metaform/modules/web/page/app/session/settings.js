/* The session's settings on one line, the agent picker of the dock, settings before Call and for the intake, and
 * slash commands. */
import '/page/app/session/text.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill, keepFill} from '/page/app/core/dom.js';
import {overlay} from '/page/app/core/overlays.js';
import {toast, confirmAct} from '/page/app/core/controls.js';
import {S, read} from '/page/app/core/reads.js';
import {DOCK} from '/page/app/dock/embody.js';
import {drawHelpdesk} from '/page/app/dock/helpdesk.js';
import {HARNESS, readHarnesses, agentName, summonAgent, summonPicker, optionWords, pickerOptions}
  from '/page/app/agents/pickers.js';
import {countOf, skipsPrompts} from '/page/app/session/tools.js';
import {posted} from '/page/app/intake/intake.js';

/* The session's settings folded to one quiet line under the chat's head, "Codex · Sol · High · Fast · 94k/475k": a
 * click opens its controls as a popover over the thread, which stays where it is; a click outside or Escape closes
 * it. Resume, when the agent offers it, stays beside the line. */
export const SESSIONPOP = {el: null};
export function sessionPop() {
  if (SESSIONPOP.el) return SESSIONPOP.el;
  SESSIONPOP.el = h('div', {id: 'sessionpop', class: 'sessionpop', role: 'dialog',
    'aria-label': 'The agent\'s settings', hidden: true});
  $('#helpdesk').append(SESSIONPOP.el);
  overlay(SESSIONPOP.el, {kind: 'popover'});
  return SESSIONPOP.el;
}
/* The agent is the line's first word and the popover's first field. Before Call it is the one choice of the agent a
 * call starts, the summon choice every start shares, with its default star; choosing another shows that agent's own
 * options at once. Once an agent runs, the field names it: another one is chosen after Stop agent, then Call. */
const DOCKPICK = {row: null, picker: null};
function dockPicker() {
  if (!DOCKPICK.row) {
    DOCKPICK.picker = summonPicker('dock', {label: 'Harness', onchange: () => refreshPreCall()});
    DOCKPICK.row = h('div', {class: 'setting agent'}, h('span', {}, 'Harness'), DOCKPICK.picker);
  }
  return DOCKPICK.row;
}
function refreshPreCall() {
  PRECALL.at = 0;
  if (!DOCK.target || afterEnd()) preCallSettings($('#helpdesk .sessionbar'), {resume: PRECALL.resume});
}
/* The person's own chat, the lead's, whose agent is not running: it was stopped or it ended. The chat then offers the
 * next call as before any call, its harness chosen first, with the ended session's Resume beside it, so a person who
 * stopped their agent can choose another and Call without reloading the page. */
export const afterEnd = () => Boolean(DOCK.target) && !DOCK.live && !DOCK.calling
  && (DOCK.target === DOCK.mine || DOCK.chat?.source === 'system');
export function sessionSummary(box, {agent, settings, usage, controls, used, resume, before = false}) {
  const pop = sessionPop();
  // the line says the options in ACP's categories, and any switch that is on, such as Ultracode
  const words = settings.filter(one => optionRank(one) >= 0 || one.type === 'boolean').map(optionWords).filter(Boolean);
  const tokens = usage && usage.used !== null && usage.used !== undefined
    ? (usage.size ? `${countOf(usage.used)}/${countOf(usage.size)}` : countOf(usage.used)) : null;
  const line = [agent, ...words, tokens].filter(Boolean).join(' · ');
  box.hidden = false;
  const toggle = event => {
    event.stopPropagation();
    if (!pop.hidden) { pop.hidden = true; return; }
    pop.style.top = `${box.offsetTop + box.offsetHeight + 4}px`;  // just under the line, over the thread
    pop.hidden = false;
  };
  const open = h('button', {class: 'sessionline', type: 'button', 'aria-haspopup': 'dialog',
    'aria-controls': 'sessionpop', 'aria-expanded': String(!pop.hidden),
    title: before ? 'The agent a call starts, and its model, effort, mode and the rest'
      : 'The agent\'s settings: its model, effort, mode and the rest', onclick: toggle},
  h('span', {class: 'said'}, line || 'Settings'), h('i', {class: 'i i-chev', 'aria-hidden': 'true'}));
  fill(box, open, h('span', {class: 'grow'}), resume);
  const running = h('div', {class: 'setting agent'}, h('span', {}, 'Harness'),
    h('b', {title: 'To talk with another agent, Stop this agent, choose another here and Call'}, agent));
  // the agent's own row is kept in place, so a choice being made in it keeps the focus as the rest is drawn again;
  // a setting of the same agent just chosen in the open popover keeps its control, and only the line says it
  const same = !pop.hidden && pop.contains(document.activeElement) && pop.dataset.for === `${before}:${agent}`;
  pop.dataset.for = `${before}:${agent}`;
  if (same) return;
  const none = before ? `${agent} offers its settings once it has run here.`
    : 'This agent offers no settings to change now.';
  keepFill(pop, [h('div', {class: 'eyebrow'}, before ? 'The next call' : `${agent}'s settings`),
    before ? dockPicker() : running, h('div', {class: 'controls'}, controls),
    used ? h('p', {class: 'hint'}, used) : null,
    !controls.length && !used ? h('p', {class: 'hint'}, none) : null].filter(Boolean));
}
/* Before Call the chat offers what the agent to be called offers, `dispatch options`: its model, effort, mode and
 * the rest, each chosen now and kept in its own setting, dispatch_<agent>_<option>, which every session it starts is
 * given. An agent nothing has asked yet is asked by that read, which starts it once with no prompt, so the window
 * says it is asking; one that needs a login or cannot start says why. */
const PRECALL = {agent: null, at: 0, data: null, resume: null};
export async function preCallSettings(box, {resume = null} = {}) {
  PRECALL.resume = resume;
  const called = () => Boolean(DOCK.target) && !afterEnd();  // a call is on: its own settings show instead
  // the agents there are
  if (S.project && (HARNESS.project !== S.project || !HARNESS.read)) await readHarnesses();
  const agent = summonAgent() || HARNESS.default;
  if (!S.project && !DOCK.target) {  // opened before the page knows its project: drawn again once it does
    box.hidden = true;
    box.dataset.drawn = '';
    setTimeout(() => { if (!$('#helpdesk').hidden && !DOCK.target) drawHelpdesk(); }, 400);
    return;
  }
  if (!agent || called()) { box.hidden = true; return; }
  if (PRECALL.agent !== agent || Date.now() - PRECALL.at > 30000) {
    PRECALL.agent = agent; PRECALL.at = Date.now();
    sessionSummary(box, {agent: agentName(agent), settings: [], usage: null, controls: [],
      used: `Asking ${agentName(agent)} what it offers…`, resume, before: true});
    try { PRECALL.data = (await read('dispatch-options', {agent})).agents?.[0] || null; } catch { PRECALL.data = null; }
  }
  // a call began, or another agent was chosen
  if (called() || agent !== (summonAgent() || HARNESS.default)) return;
  const found = PRECALL.data || {};
  const {settings, controls} = agentOptionControls(agent, found);
  sessionSummary(box, {agent: found.label || agentName(agent), settings, usage: null, controls,
    used: found.reason || null, resume,
    before: true});
}
/* An agent's own settings as controls, as it offered them at its last session here, `dispatch options`: its model,
 * effort, mode and the rest, each choice kept in its own setting, dispatch_<agent>_<option>, which every session it
 * starts is given, the chat's and the intake's alike. */
function agentOptionControls(agent, found) {
  const settings = (found.settings || [])
    .map(one => ({...one, options: one.choices, current: one.chosen ?? one.current}));
  const controls = groupedControls(found.label || agentName(agent), settings, settings.map(setting =>
    setting.type === 'boolean' ? optionSwitch(agent, setting) : optionSelect(agent, setting)));
  return {settings, controls};
}
/* An agent's options in ACP's own categories come first, in this order, by the key dispatch names them with. What
 * else a harness reports means what that harness says it means, such as Claude Code's choice to run the whole
 * session as one of its subagents, so it sits under "More from <harness>", closed until the person opens it. */
const MAIN_OPTIONS = ['mode', 'model', 'speed', 'thought_level'];
const MORE = {open: false};  // opened once, it stays open as the window is drawn again on this page
// a session's state kept before dispatch named its settings carries their category and id alone
const optionRank = setting => MAIN_OPTIONS.indexOf(setting.key ?? setting.category ?? setting.id);
export function groupedControls(harness, settings, controls) {
  const main = [], more = [];
  settings.forEach((setting, at) => {
    const rank = optionRank(setting);
    if (rank < 0) more.push(controls[at]); else main.push([rank, controls[at]]);
  });
  main.sort((one, other) => one[0] - other[0]);
  return [...main.map(one => one[1]), more.length ? h('details', {class: 'more', open: MORE.open,
    ontoggle: event => { MORE.open = event.currentTarget.open; }},
  h('summary', {}, `More from ${harness}`), h('div', {class: 'controls'}, more)) : null].filter(Boolean);
}
function optionSwitch(agent, setting) {
  const input = h('input', {type: 'checkbox', role: 'switch', checked: String(setting.current) === 'true',
    disabled: !setting.setting, onchange: () => keepAgentOption(agent, setting, input.checked ? 'true' : 'false')});
  return h('label', {class: 'switch setting', title: setting.description || setting.name}, input, setting.name);
}
function optionSelect(agent, setting) {
  const pick = h('select', {'aria-label': setting.name, disabled: !setting.setting,
    title: setting.setting ? null : 'Metaform has no setting for this option; the agent keeps its own.',
    onchange: () => keepAgentOption(agent, setting, pick.value, pick)},
  // the setting's own list, `picks`: Default, the short names, then each exact value; one not chosen is Default
  pickerOptions(setting.picks || [], setting.chosen ?? 'default'));
  return h('label', {class: 'setting'}, h('span', {}, setting.name), pick);
}
/* The intake's agent's model, thinking and the rest, chosen before it starts, as the chat offers them before a call;
 * an agent that needs a login or cannot start offers none, and the window says why. */
export async function drawIntakeSettings() {
  const box = $('#intake .intakesettings'), agent = summonAgent();
  if (!agent) { box.hidden = true; return; }
  let found = null;
  try { found = (await read('dispatch-options', {agent})).agents?.[0] || null; } catch { found = null; }
  if (agent !== summonAgent()) return;  // another agent was chosen meanwhile
  const {controls} = agentOptionControls(agent, found || {});
  fill(box.querySelector('.controls'), controls);
  box.querySelector('.hint').textContent = controls.length ? ''
    : found?.reason ? found.reason
    : `${agentName(agent)} offers no settings to choose.`;
  box.hidden = false;
}
/* A choice is kept in the option's own setting, dispatch_<agent>_<option>, so keeping one never touches another. A
 * value that skips the agent's own permission prompts is kept for every session it starts only once confirmed, as
 * metaform set asks for --confirm. */
async function keepAgentOption(agent, setting, value, pick) {
  const option = (setting.options || []).find(one => one.value === value);
  const named = (setting.picks || []).find(one => one.value === value)?.label || value;
  const risky = skipsPrompts(option);
  if (risky && !await confirmAct({title: `Let ${agentName(agent)} act without asking?`,
    text: [`${option.name || value}: every session ${agentName(agent)} starts here skips its own permission prompts. `
      + 'It edits files and runs commands without asking you first.'],
    verb: 'Yes, keep it', cancel: 'Keep it as it is'})) {
    pick.value = setting.chosen ?? 'default';
    return;
  }
  const done = await posted('/api/settings', {key: setting.setting, value, ...(risky ? {confirm: true} : {})});
  if (!done.ok) return toast(done.body.error || 'That choice was not kept.');
  refreshPreCall();  // the line says the choice at once
  toast(`${agentName(agent)} starts with ${setting.name} ${named}.`);
}
/* Slash commands: typing / at the start of a message offers the commands, the chat's own and the agent's, as the
 * agent named them; Up and Down choose, Enter or Tab takes one, Escape closes the list. */
export function slashCommands(say, offered) {
  const id = `slash${++slashCommands.made}`;
  const list = h('div', {class: 'slash', id, role: 'listbox', hidden: true, 'aria-label': 'Commands'});
  say.after(list);
  say.setAttribute('aria-controls', id);
  say.setAttribute('aria-autocomplete', 'list');
  let found = [], active = 0;
  const word = () => {
    const before = say.value.slice(0, say.selectionStart ?? say.value.length);
    const typed = /^\/(\S*)$/.exec(before);
    return typed ? typed[1] : null;
  };
  const paint = () => {
    [...list.children].filter(row => row.getAttribute('role') === 'option').forEach((row, index) => {
      row.setAttribute('aria-selected', String(index === active));
      if (index === active) {
        say.setAttribute('aria-activedescendant', row.id);
        row.scrollIntoView({block: 'nearest'});
      }
    });
  };
  /* A command offered: pressed it is taken, and the pointer over it makes it the one chosen. */
  const row = (one, at) => h('div', {role: 'option', id: `${id}-${at}`, 'aria-selected': 'false',
    onpointerdown: event => { event.preventDefault(); take(at); },
    onpointermove: () => { if (active !== at) { active = at; paint(); } }},
  h('b', {}, `/${one.name}`), one.hint ? h('span', {class: 'hint'}, one.hint) : null,
  one.description ? h('small', {}, one.description) : null);
  const show = () => {
    const typed = word();
    found = typed === null ? [] : offered().filter(one => one.name.toLowerCase().startsWith(typed.toLowerCase()));
    if (!found.length) { list.hidden = true; say.removeAttribute('aria-activedescendant'); return; }
    active = Math.min(active, found.length - 1);
    const groups = [...new Set(found.map(one => one.from))];
    let index = -1;
    fill(list, groups.map(group => [h('div', {class: 'group', role: 'presentation'}, group),
      found.filter(one => one.from === group).map(one => row(one, ++index))]));
    found = groups.flatMap(group => found.filter(one => one.from === group));
    list.hidden = false;
    paint();
  };
  const take = index => {
    const one = found[index];
    if (!one) return;
    const rest = say.value.slice(say.selectionStart ?? say.value.length).replace(/^\S*/, '');
    say.value = `/${one.name} ${rest.trimStart()}`;
    const at = one.name.length + 2;
    say.setSelectionRange(at, at);
    if (one.hint) say.setAttribute('placeholder', one.hint);
    list.hidden = true;
    say.focus();
  };
  say.addEventListener('input', () => { active = 0; show(); });
  say.addEventListener('click', show);
  const closeSoon = () => setTimeout(() => { if (document.activeElement !== say) list.hidden = true; }, 120);
  /* Up and Down choose, Enter or Tab takes the one chosen; taken before the field's own keys. */
  const keys = event => {
    if (list.hidden) return;
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault(); event.stopImmediatePropagation();
      active = (active + (event.key === 'ArrowDown' ? 1 : -1) + found.length) % found.length; paint();
    } else if ((event.key === 'Enter' && !event.shiftKey) || event.key === 'Tab') {
      // a command typed whole is sent by Enter as it is; otherwise Enter and Tab take the one chosen
      if (event.key === 'Enter' && found[active]?.name === word()) { list.hidden = true; return; }
      event.preventDefault(); event.stopImmediatePropagation(); take(active);
    }
  };
  say.addEventListener('blur', closeSoon);
  say.addEventListener('keydown', keys, true);
  overlay(list, {kind: 'popover', focus: false, close: () => { list.hidden = true; }});
  return list;
}
slashCommands.made = 0;
/* The commands a session offers, from its state. */
export const commandsOf = (state, agent) => (state?.commands || []).filter(one => one.name)
  .map(one => ({name: one.name, description: one.description, hint: one.hint, from: `${agentName(agent)}'s commands`}));
