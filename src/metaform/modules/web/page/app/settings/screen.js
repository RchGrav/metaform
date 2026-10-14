/* Agent prompts and the Agents menu, and the settings screen: each module and setting as a row with its control,
 * saved with Undo. */
import '/page/app/memory/manage.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {overlay} from '/page/app/core/overlays.js';
import {toast, undoable, confirmAct} from '/page/app/core/controls.js';
import {S, read} from '/page/app/core/reads.js';
import {renderChips} from '/page/app/header/layers.js';
import {toggler} from '/page/app/header/menus.js';
import {PLAIN, setTheme} from '/page/app/map3d/draw3d.js';
import {renderBoard} from '/page/app/board/board.js';
import {wrote} from '/page/app/board/history.js';
import {AUTO, readAutostart, renderAgents} from '/page/app/agents/dispatch.js';
import {HARNESS, readHarnesses, paintPickers, makeDefault, agentPicker, PICKERS} from '/page/app/agents/pickers.js';
import {posted} from '/page/app/intake/intake.js';
import {WS} from '/page/app/workspace/workspace.js';

/* Agent prompts, VIEW-039: how agents' permission prompts are answered, dispatch_prompts, chosen in the Agents menu and
 * shown there as the settings hold it, read again each time the menu opens and whenever the settings screen changes
 * it, so the administrator's choice is the one every agent follows and never reverts. Each choice reads in plain
 * words with its setting's value, and approving every prompt says what it risks. A choice is saved as it is made,
 * through metaform set; a refused save puts back the one in force and says why. */
const PROMPT_WORDS = {
  'approve-all': ['Approve every prompt',
    'Agents run any tool without asking, including ones that change or delete files.'],
  'approve-reads': ['Approve reads and searches; ask for the rest', ''],
  ask_all: ['Ask every prompt as a question at the ticket', '']};
const PROMPTS = {value: null, saving: false};
const promptWords = choice => (PROMPT_WORDS[choice] || [choice, ''])[0];
function sayPrompts(text, risky = false) {
  $('#promptsSaid').textContent = text;
  $('#promptsSaid').classList.toggle('risk', risky);
}
async function readPrompts() {
  const pick = $('#promptsPick');
  if (PROMPTS.saving) return;  // a choice is being saved: its answer draws it
  let found;
  try { found = await read('dispatch-prompts'); } catch (error) {
    pick.disabled = true;
    fill(pick);
    PROMPTS.value = null;
    return sayPrompts(error.body?.next ? `${error.message} Next: ${error.body.next}` : error.message);
  }
  PROMPTS.value = found.value;
  const listed = found.choices.includes(found.value) ? found.choices : [found.value, ...found.choices];
  fill(pick, listed.map(choice => h('option', {value: choice, selected: choice === found.value},
    `${promptWords(choice)} · ${choice}`)));
  pick.disabled = false;
  sayPrompts(PROMPT_WORDS[found.value]?.[1] || '', Boolean(PROMPT_WORDS[found.value]?.[1]));
}
async function choosePrompts(event) {
  const pick = event.target, before = PROMPTS.value, choice = pick.value;
  pick.disabled = PROMPTS.saving = true;
  const done = await posted('/api/dispatch-prompts', {value: choice});
  pick.disabled = PROMPTS.saving = false;
  if (!done.ok) {
    pick.value = before;
    const why = [done.body.error || 'It was not saved.', done.body.next ? `Next: ${done.body.next}` : ''].join(' ');
    sayPrompts(`Not changed, still ${promptWords(before)}: ${why.trim()}`, true);
    return toast(`Agent prompts not changed: ${why.trim()}`);
  }
  PROMPTS.value = choice;
  const risk = PROMPT_WORDS[choice]?.[1] || '';
  sayPrompts(risk || `Saved: ${choice}.`, Boolean(risk));
  toast(`Agent prompts: ${promptWords(choice)}.`);
}
$('#promptsPick').onchange = choosePrompts;
/* The Agents menu: the agents' own settings and repair, kept apart from Administration's project-wide removals. */
export function showAgentMenu(open) { $('#agentbox').hidden = !open; }
overlay($('#agentbox'), {kind: 'menu', focus: '#agentCount'});
async function openAgentMenu() {
  // the default agent, chosen here as in every picker: what chats, issues and intakes start with unless another is
  // chosen
  if (!$('#defaultAgentPick').firstChild) $('#defaultAgentPick').append(PICKERS.default ||= defaultPicker());
  readHarnesses();
  readPrompts();  // the saved setting, as it is now
  await readAutostart();
  $('#agentCount').value = AUTO.agents ?? 5;  // the saved setting, as it is now
}
toggler($('#agentsMenuBtn'), $('#agentbox'), openAgentMenu);
/* The default as dispatch has it, and while one chosen is being made the default, that one. */
function defaultPicker() {
  const holder = {chosen: false, asked: null};
  Object.defineProperty(holder, 'agent', {get: () => holder.asked ?? HARNESS.default,
    set: agent => { holder.asked = agent; }});
  const choose = async agent => { await makeDefault(agent); holder.asked = null; paintPickers(); };
  return agentPicker({label: 'Default agent', star: false, kept: true, exact: true, holder, onchange: choose});
}
async function saveAgentCount(event) {
  const count = Number(event.target.value);
  if (!Number.isInteger(count) || count < 1) { event.target.value = AUTO.agents ?? 5; return; }
  event.target.disabled = true;
  try {
    const saved = await wrote('/api/dispatch-autostart', {agents: count});
    if (!saved) event.target.value = AUTO.agents ?? 5;
    else {
      Object.assign(AUTO, saved);
      event.target.value = saved.agents;
      toast(`Agents at once: ${saved.agents}.`);
    }
  } finally { event.target.disabled = false; }
}
$('#agentCount').onchange = saveAgentCount;
/* Reset agents ends the sessions of agents that died; it cannot be undone, so it is asked first, saying what it does
 * and what it leaves. */
async function resetAgents(event) {
  showAgentMenu(false);
  if (!await confirmAct({title: 'Reset agents?',
    text: 'Use it after a crash, when an agent stopped without letting go of its ticket.',
    lost: ['The sessions of agents that are no longer running are closed',
      'The tickets they still hold go back on the board'],
    kept: ['Agents at work are left alone', 'Nothing is deleted: every ticket, its steps and its log stay'],
    verb: 'Reset agents'})) return;
  event.target.disabled = true;
  try {
    const done = await wrote('/api/dispatch-reset', {});
    if (done) {
      toast(`Reset: ${done.released.length} ticket(s) back on the board, ${done.sessions_ended.length} dead session(s) `
        + `closed; ${done.still_working.length} agent(s) still working.`);
      await renderBoard(); await renderAgents();
    }
  } finally { event.target.disabled = false; }
}
$('#resetAgentsBtn').onclick = resetAgents;
/* ---------- the settings screen ----------
 * Every setting of the project's folder, as metaform config shows them, and every module with whether it is on. The
 * modules come first, each switched on or off as metaform enable and disable do, with the modules setting under them
 * as the modules this folder shows; then the chassis's settings and each module's. A setting reads with its label, its
 * help, its state (default, set or glued), Glue and Reset, and takes the control its kind needs: a switch, a number, a
 * list of its choices, a checklist, or text, a list as its items separated by commas. A change is saved as it is made,
 * through metaform set and unset in the project's folder, so it is checked as the command line checks it, and a
 * refusal is said under the setting with its next step. Left and Right change a switch or a choice, as on the
 * terminal's settings screen. */
const CONFIG = {data: null, filter: '', errors: new Map()};
const SHOWN_MODULES = 'modules';  // the chassis setting shown with the modules: which of them this folder shows
export async function openSettings() {
  showAgentMenu(false);
  $('#settingsbox').hidden = true;
  if (!S.project) return toast('Choose a project first: the settings shown are those of its folder.');
  if (WS.reveal('settings')) return;  // a pane in the workspace: it shows there and reads as it shows
  await showSettings();
}
export async function showSettings() {
  CONFIG.errors.clear();
  fill($('#settings .body'), h('p', {class: 'loading'}, 'Reading the settings…'));
  $('#settings').hidden = false;
  await readSettings();
}
async function readSettings() {
  const project = S.project;
  try {
    const found = await read('settings');
    if (S.project !== project) return;
    CONFIG.data = found;
  } catch (error) { fill($('#settings .body'), refusalBox(error.body || {error: error.message})); return; }
  renderSettings();
}
/* A refusal in place: what was refused and the next step, as the command line says them. */
export function refusalBox(body) {
  return h('div', {class: 'failed setfail', role: 'alert'}, h('p', {}, body.error || 'It was not saved.'),
    body.next ? h('p', {class: 'next'}, 'Next: ', h('code', {}, body.next)) : null);
}
/* A value as the screen says it: on or off, a list's items, all for an empty list that means all, (none) for none. */
function shownValue(key, value) {
  if (typeof value === 'boolean') return value ? 'on' : 'off';
  if (Array.isArray(value)) {
    return value.length ? value.join(', ') : CONFIG.data?.all_when_empty.includes(key) ? 'all' : '(none)';
  }
  return value === null || value === undefined || value === '' ? '(none)' : String(value);
}
function renderSettings() {
  const data = CONFIG.data;
  if (!data) return;
  const body = $('#settings .body');
  const focused = document.activeElement?.closest?.('#settings .body [data-focus]')?.dataset.focus;
  const scroll = body.scrollTop;
  const sections = settingsSections(data);
  if (sections.length === 1) sections.push(h('p', {class: 'empty'}, `No setting matches ${CONFIG.filter.trim()}.`));
  fill(body, sections);
  body.scrollTop = scroll;
  if (focused) body.querySelector(`[data-focus="${CSS.escape(focused)}"]`)?.focus({preventScroll: true});
}
/* The screen's sections, as the filter leaves them: a word on what the settings are, the modules with the setting of
 * which are shown, then the chassis's settings and each module's. */
function settingsSections(data) {
  const query = CONFIG.filter.trim().toLowerCase();
  const matches = (...texts) => !query || texts.some(text => String(text || '').toLowerCase().includes(query));
  const shownRow = data.settings.find(row => row.key === SHOWN_MODULES && row.owner === 'chassis');
  const sections = [h('p', {class: 'hint'}, `The settings of ${S.project}, kept for ${data.folder}. A folder setting `
    + 'applies to this folder and every folder below it; a global one applies everywhere. They are the settings '
    + 'metaform config shows, and each change is saved as metaform set saves it.')];
  const modules = data.modules.filter(module => matches(module.id, module.summary, module.problem));
  const modulePart = [data.modules_refused ? refusalBox(data.modules_refused) : null,
    modules.length ? h('div', {class: 'setlist'}, modules.map(moduleRow)) : null,
    shownRow && matches(shownRow.key, shownRow.help, 'Modules shown in this folder')
      ? h('div', {class: 'setlist'}, settingRow(shownRow, 'Modules shown in this folder')) : null].filter(Boolean);
  if (modulePart.length) sections.push(setGroup('Modules', 'On or off for every project, as metaform enable and '
    + 'disable turn them. A module turned off keeps its settings.', modulePart));
  const owners = new Set(['chassis', ...data.modules.map(module => module.id), ...data.settings.map(row => row.owner)]);
  for (const owner of owners) {
    const own = data.settings.filter(row => row.owner === owner && row !== shownRow
      && matches(row.key, row.label, row.help, row.details));
    if (!own.length) continue;
    const about = owner === 'chassis' ? 'Settings of the chassis itself.'
      : data.modules.find(module => module.id === owner)?.summary || '';
    sections.push(setGroup(owner === 'chassis' ? 'Chassis' : owner, about,
      h('div', {class: 'setlist'}, own.map(row => settingRow(row)))));
  }
  return sections;
}
const setGroup = (title, about, kids) => h('section', {class: 'setgroup'},
  h('div', {class: 'head'}, h('h3', {}, title), about ? h('span', {class: 'hint'}, about) : null), kids);
/* Left and Right turn a switch off and on, and step a list of choices back and on, saving as a click does. */
function arrowSwitch(event, input) {
  if (!['ArrowLeft', 'ArrowRight'].includes(event.key) || input.disabled) return;
  event.preventDefault();
  const on = event.key === 'ArrowRight';
  if (input.checked === on) return;
  input.checked = on;
  input.dispatchEvent(new Event('change'));
}
function arrowSelect(event, select) {
  if (!['ArrowLeft', 'ArrowRight'].includes(event.key) || select.disabled) return;
  event.preventDefault();
  const next = select.selectedIndex + (event.key === 'ArrowRight' ? 1 : -1);
  if (next < 0 || next >= select.options.length || select.options[next].disabled) return;
  select.selectedIndex = next;
  select.dispatchEvent(new Event('change'));
}
function moduleRow(module) {
  const id = `module:${module.id}`;
  const input = h('input', {type: 'checkbox', role: 'switch', checked: module.enabled, 'data-focus': id,
    'aria-label': `The ${module.id} module`, onchange: () => switchModule(module, input),
    onkeydown: event => arrowSwitch(event, input)});
  const error = CONFIG.errors.get(id);
  return h('div', {class: 'setrow module', 'data-module': module.id},
    h('div', {class: 'what'},
      h('div', {class: 'name'}, h('code', {class: 'id'}, module.id),
        module.place !== 'system'
          ? h('span', {class: 'badge', title: `Found in the ${module.place} place`}, module.place) : null,
        module.problem ? h('span', {class: 'badge warn'}, 'not loaded') : null),
      h('span', {class: 'help'}, module.problem || module.summary)),
    h('div', {class: 'control'}, h('label', {class: 'switch'}, input, module.enabled ? 'On' : 'Off')),
    error ? refusalBox(error) : null);
}
async function switchModule(module, input) {
  const id = `module:${module.id}`, on = input.checked;
  if (!on && module.id === 'web' && !await keepWeb()) {
    input.checked = true;
    return;
  }
  input.disabled = true;
  const done = await posted('/api/modules', {module: module.id, enabled: on});
  if (!done.ok) {
    input.checked = !on;
    input.disabled = false;
    CONFIG.errors.set(id, done.body);
    renderSettings();
    return;
  }
  CONFIG.errors.delete(id);
  toast(`Module ${module.id}: ${on ? 'on' : 'off'}.`);
  await readSettings();
  readAutostart();
}
/* Turning off the module that serves this page is asked first. */
function keepWeb() {
  return confirmAct({title: 'Turn off the web module?', text: 'It serves this page. Turned off, metaform web does not '
    + 'start the page again until it is turned back on: metaform enable web.',
  kept: ['Its settings keep their saved values'], verb: 'Turn it off', cancel: 'Keep it on'});
}
function settingRow(row, label = row.label) {
  const id = `setting:${row.key}`;
  const error = CONFIG.errors.get(id);
  const control = settingControl(row, id, label);
  const glue = glueButton(row), reset = resetButton(row), state = STATE_BADGES[row.state] || ['badge', ''];
  return h('div', {class: 'setrow', 'data-key': row.key},
    h('div', {class: 'what'},
      h('div', {class: 'name'}, h('span', {class: 'label'}, label), h('code', {}, row.switch),
        h('span', {class: `${state[0]} state`, title: state[1]}, row.state),
        row.scope === 'global' ? h('span', {class: 'badge', title: 'Applies in every folder'}, 'global') : null,
        row.person_only ? h('span', {class: 'badge', title: 'Only you change it, here or on the command line; '
          + 'an agent is refused it over MCP'}, 'yours') : null),
      row.help ? h('span', {class: 'help'}, row.help) : null,
      row.details ? h('details', {}, h('summary', {}, 'More'), h('p', {}, row.details)) : null),
    h('div', {class: 'control'}, control.main, glue, reset),
    control.wide || null,
    error ? refusalBox(error) : null);
}
const STATE_BADGES = {default: ['badge off', 'The default: nothing is saved for it'],
  set: ['badge ok', 'Saved for this folder'],
  glued: ['badge warn', 'Kept through metaform unset all until it is unglued']};
/* Glue, for a value set and not glued yet, as metaform set --glue keeps it. */
function glueButton(row) {
  const empty = Array.isArray(row.value) && !row.value.length && CONFIG.data.all_when_empty.includes(row.key);
  if (row.state === 'glued' || row.value === null || row.value === undefined || empty) return null;
  return h('button', {class: 'btn sm quiet glue', type: 'button', 'data-focus': `glue:${row.key}`,
    title: 'Keep this value through metaform unset all, as metaform set --glue does',
    onclick: () => saveSetting(row, row.value, {glue: true})}, 'Glue');
}
/* Reset, or Unglue for a glued value, back to its default as metaform unset does. */
function resetButton(row) {
  const glued = row.state === 'glued';
  return h('button', {class: 'btn sm quiet reset', type: 'button', disabled: row.state === 'default',
    'data-focus': `reset:${row.key}`, onclick: () => resetSetting(row),
    title: glued ? `Unglue it and return it to its default, as metaform unset --unglue ${row.switch} does`
      : `Return it to its default, as metaform unset ${row.switch} does`}, glued ? 'Unglue' : 'Reset');
}
/* The control a setting's kind takes; `wide` goes under the row, as a checklist does. */
function settingControl(row, id, label) {
  const save = value => saveSetting(row, value);
  if (row.kind === 'bool') {
    const input = h('input', {type: 'checkbox', role: 'switch', checked: Boolean(row.value), 'aria-label': label,
      'data-focus': id, onchange: () => save(input.checked), onkeydown: event => arrowSwitch(event, input)});
    return {main: h('label', {class: 'switch'}, input, row.value ? 'On' : 'Off')};
  }
  if (row.kind === 'int') {
    const input = h('input', {type: 'number', step: '1', min: row.min ?? null, max: row.max ?? null,
      value: row.value ?? '', 'aria-label': label, 'data-focus': id, onchange: () => save(input.value.trim())});
    return {main: input};
  }
  const choices = Array.isArray(row.choices) && row.choices.length ? row.choices : null;
  if (row.kind === 'select' && choices) {
    const listed = choices.includes(row.value) ? choices : [row.value ?? '', ...choices];
    const select = h('select', {'aria-label': label, 'data-focus': id, onchange: () => save(select.value),
      onkeydown: event => arrowSelect(event, select)},
      listed.map(choice => h('option', {value: choice, selected: choice === row.value,
        disabled: !choices.includes(choice)}, choice === '' ? '(none)' : choice)));
    return {main: select};
  }
  if (row.kind === 'list' && choices) return {main: null, wide: checklist(row, choices, id, label)};
  const all = CONFIG.data.all_when_empty.includes(row.key);
  const text = Array.isArray(row.value) ? row.value.join(',') : String(row.value ?? '');
  const input = h('input', {type: 'text', value: text, 'aria-label': label, 'data-focus': id, spellcheck: 'false', autocomplete: 'off',
    placeholder: row.kind === 'list' ? (all ? 'all' : 'names, separated by commas') : '(none)',
    onchange: () => save(input.value)});
  return {main: input};
}
/* A list's choices, each checked or not. A list that means all when it is empty shows every choice checked then, and
 * is saved empty when every one is checked again; one choice at least stays checked, since none would mean all. */
function checklist(row, choices, id, label) {
  const all = CONFIG.data.all_when_empty.includes(row.key);
  const value = Array.isArray(row.value) ? row.value : [];
  const chosen = new Set(all && !value.length ? choices : value);
  const listed = [...choices, ...value.filter(name => !choices.includes(name))];
  const boxes = listed.map(choice => h('input', {type: 'checkbox', value: choice, checked: chosen.has(choice),
    'data-focus': `${id}:${choice}`}));
  // A list holding one value per name, `<name><exclusive><value>`: checking one unchecks the others of its name.
  const nameOf = value => row.exclusive ? value.split(row.exclusive)[0] : null;
  const changed = event => {
    const box = event?.target;
    if (row.exclusive && box?.checked) {
      for (const other of boxes) if (other !== box && nameOf(other.value) === nameOf(box.value)) other.checked = false;
    }
    const picked = boxes.filter(box => box.checked).map(box => box.value);
    if (all && !picked.length) {
      CONFIG.errors.set(id, {error: 'Keep one checked at least. With every one checked, all are shown.'});
      return renderSettings();
    }
    saveSetting(row, all && choices.every(choice => picked.includes(choice)) ? [] : picked);
  };
  for (const box of boxes) box.addEventListener('change', changed);
  return h('div', {class: 'checks', role: 'group', 'aria-label': label},
    boxes.map((box, index) => h('label', {class: 'check'}, box, h('code', {}, listed[index]))),
    all ? h('span', {class: 'hint'}, 'Every one checked, the default, shows them all.') : null);
}
/* Save one setting, or glue it, and say so with Undo; Undo puts back what it was. A refusal is said under it. */
async function saveSetting(row, value, {glue = false, quiet = false} = {}) {
  const id = `setting:${row.key}`;
  const before = {state: row.state, value: row.value};
  const done = await posted('/api/settings', {key: row.key, value, ...(glue ? {glue: true} : {})});
  if (!done.ok) { CONFIG.errors.set(id, done.body); renderSettings(); return false; }
  CONFIG.errors.delete(id);
  CONFIG.data = done.body;
  renderSettings();
  afterSetting(row.key);
  if (quiet) return true;
  const now = done.body.settings.find(one => one.key === row.key);
  const told = `${row.label}: ${shownValue(row.key, now?.value)}${glue ? ', glued' : ''}.`;
  const said = [told, ...(done.body.notices || [])].join(' ');
  if (glue) toast(said);
  else undoable(said, () => before.state === 'default' ? resetSetting(now || row, {quiet: true})
    : saveSetting(now || row, before.value, {quiet: true}));
  return true;
}
async function resetSetting(row, {quiet = false} = {}) {
  const id = `setting:${row.key}`, glued = row.state === 'glued';
  if (glued && !quiet && !await confirmAct({title: `Unglue ${row.label}?`,
    text: 'A glued setting keeps its value through metaform unset all. Unglued, it returns to its default.',
    verb: 'Unglue and reset', danger: false})) return false;
  const before = row.value;
  const done = await posted('/api/settings/reset', {key: row.key, ...(glued ? {unglue: true} : {})});
  if (!done.ok) { CONFIG.errors.set(id, done.body); renderSettings(); return false; }
  CONFIG.errors.delete(id);
  CONFIG.data = done.body;
  renderSettings();
  afterSetting(row.key);
  if (quiet) return true;
  const now = done.body.settings.find(one => one.key === row.key);
  undoable(`${row.label}: back to its default, ${shownValue(row.key, now?.value)}.`,
    () => saveSetting(now || row, before, {glue: glued, quiet: true}));
  return true;
}
/* What the rest of the page shows from a setting follows it: the Autostart switch, Agent prompts, and the folder's
 * layers. */
function afterSetting(key) {
  if (key.startsWith('dispatch_')) readAutostart();
  if (key === 'dispatch_prompts') readPrompts();
  if (key === 'layers' && S.view === null) {
    read('layers', {limit: 0}).then(found => { S.layers = found.results; renderChips(); })
      .catch(error => toast(error.message));
  }
  // ULTRA: the 3D map fades to the graphics chosen, as U does
  if (key === 'web_graphics') {  // set on the Settings screen: the theme follows, space for ultra
    const ultra = CONFIG.data?.settings?.find(one => one.key === key)?.value === 'ultra';
    if (ultra !== (document.documentElement.dataset.theme === 'space')) setTheme(ultra ? 'space' : PLAIN.last, false);
  }
}
$('#allSettingsBtn').onclick = openSettings;
$('#viewAllSettingsBtn').onclick = openSettings;
$('#settings .search').addEventListener('input', event => { CONFIG.filter = event.target.value; renderSettings(); });
$('#settings .close').onclick = () => { $('#settings').hidden = true; };
overlay($('#settings'), {kind: 'dialog', close: () => { $('#settings').hidden = true; }});
