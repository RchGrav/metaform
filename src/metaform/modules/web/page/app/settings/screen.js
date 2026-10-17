/* Agent prompts and the Agents menu, and the settings screen: each module and setting as a row with its control,
 * saved with Undo. */
import '/page/app/memory/manage.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {expandCut} from '/page/app/core/expand.js';
import {overlay} from '/page/app/core/overlays.js';
import {toast, undoable, confirmAct} from '/page/app/core/controls.js';
import {S, read} from '/page/app/core/reads.js';
import {renderChips} from '/page/app/header/layers.js';
import {toggler} from '/page/app/header/menus.js';
import {PLAIN, setTheme} from '/page/app/map3d/draw3d.js';
import {renderBoard} from '/page/app/board/board.js';
import {wrote} from '/page/app/board/history.js';
import {AUTO, PROMPT_WORDS, readAutostart, renderAgents, cancelStarting} from '/page/app/agents/dispatch.js';
import {HARNESS, readHarnesses, paintPickers, makeDefault, agentPicker, PICKERS} from '/page/app/agents/pickers.js';
import {posted} from '/page/app/intake/intake.js';
import {WS} from '/page/app/workspace/workspace.js';
import {VIEW} from '/page/app/views/settings.js';
import {drawHelpdesk} from '/page/app/dock/helpdesk.js';
import {CHATWORK} from '/page/app/session/apps.js';

/* Agent prompts, VIEW-039: how agents' permission prompts are answered, dispatch_prompts, chosen in the Agents menu and
 * shown there as the settings hold it, read again each time the menu opens and whenever the settings screen changes
 * it, so the administrator's choice is the one every agent follows and never reverts. Each choice reads in plain
 * words with its setting's value, and approving every prompt says what it risks. A choice is saved as it is made,
 * through metaform set; a refused save puts back the one in force and says why. */
const PROMPTS = {value: null, saving: false, risky: []};
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
  PROMPTS.risky = found.risky || [];
  const listed = found.choices.includes(found.value) ? found.choices : [found.value, ...found.choices];
  fill(pick, listed.map(choice => h('option', {value: choice, selected: choice === found.value},
    `${promptWords(choice)} · ${choice}`)));
  pick.disabled = false;
  sayPrompts(PROMPT_WORDS[found.value]?.[1] || '', Boolean(PROMPT_WORDS[found.value]?.[1]));
}
async function choosePrompts(event) {
  const pick = event.target, before = PROMPTS.value, choice = pick.value;
  const risky = PROMPTS.risky.includes(choice);
  if (risky && !await confirmRisk('Agent prompts', promptWords(choice), PROMPT_WORDS[choice]?.[1])) {
    pick.value = before;
    return;
  }
  pick.disabled = PROMPTS.saving = true;
  const done = await posted('/api/dispatch-prompts', {value: choice, ...(risky ? {confirm: true} : {})});
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
/* A choice that lets agents act without asking is stored only once the person confirms it, here and in the settings
 * screen alike, as metaform set asks for --confirm. */
function confirmRisk(label, choice, risk) {
  return confirmAct({title: `Let agents act without asking?`, text: [`${label}: ${choice}.`,
    risk || 'Agents take actions without asking you first.'],
  verb: 'Yes, set it', cancel: 'Keep it as it is'});
}
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
  if (AUTO.most) $('#agentCount').max = AUTO.most;  // the server's own maximum, so the page refuses what it refuses
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
/* How many agents a new count starts at once while Autostart is on: the tickets waiting, up to the slots the new
 * count leaves free and the machine's room, as dispatch's gate counts them; null when the slots cannot be read. UX
 * review round 1, 2026-10-17 (web-gui-controls F4): raising the count started every newly allowed agent in the same
 * second, unsaid. */
async function startsNow(count) {
  if (!AUTO.value) return 0;
  const slots = (await readHarnesses()).slots;
  if (!slots) return null;
  const waiting = (S.tickets || []).filter(ticket => !ticket.done && !ticket.taken && !ticket.held
    && (ticket.task || '').trim()).length;
  return Math.min(waiting, Math.max(0, count - slots.used), slots.machine_free);
}
async function saveAgentCount(event) {
  const control = event.target;  // kept before the first await
  const count = Number(control.value), was = AUTO.agents ?? 5, most = AUTO.most || count;
  if (!Number.isInteger(count) || count < 1 || count > most) {
    if (count > most) toast(`Agents at once is at most ${most}.`);
    control.value = was; return;
  }
  const more = count > was ? await startsNow(count) : 0;
  if (more === null || more > 0) {
    const said = more === null ? 'Autostart agents is on and the agent slots could not be read, so this may start '
      + 'agents on waiting tickets at once.' : `Autostart agents is on, so this starts ${more} more agent`
      + `${more === 1 ? '' : 's'} now, one for each waiting ticket the new slots allow.`;
    if (!await confirmAct({title: `Allow ${count} agents at once?`, text: said, verb: 'Yes, allow them',
      cancel: 'Keep it as it is'})) { control.value = was; return; }
  }
  control.disabled = true;
  try {
    const saved = await wrote('/api/dispatch-autostart', {agents: count});
    if (!saved) control.value = was;
    else {
      Object.assign(AUTO, saved);
      control.value = saved.agents;
      toast(`Agents at once: ${saved.agents}.`);
    }
  } finally { control.disabled = false; }
}
$('#agentCount').onchange = saveAgentCount;
/* Stop all agents: every agent of the project, or of every project on this machine, ends as the person's stop ends
 * it, and Autostart agents is turned off first, so nothing starts in their place. Asked first, with the count.
 * UX review round 1, 2026-10-17 (dispatch-concurrency F5, web-gui-controls F5). */
async function stopAll(event, every) {
  const control = event.currentTarget;  // kept before the first await, which clears currentTarget
  showAgentMenu(false);
  const slots = (await readHarnesses()).slots;
  const here = slots ? slots.workers + slots.summoned : null;
  const count = every ? slots?.machine_used ?? null : here;
  if (!await confirmAct({title: every ? 'Stop every agent on this machine?' : 'Stop every agent of this project?',
    text: `${count === null ? 'Every agent' : `${count} agent${count === 1 ? '' : 's'}`} running `
      + (every ? 'across every project' : 'on this project') + ' will be stopped.',
    lost: ['Each agent stops where it is, as your Stop stops it',
      `Autostart agents is turned off${every ? ' in each project' : ''}`,
      'Your system agent stops too, and Stay connected is turned off'],
    kept: ['Every ticket stays taken by its agent, with its steps and its thread', 'Each one can be resumed'],
    verb: 'Stop them'})) return;
  control.disabled = true;
  const run = cancelStarting();  // before the stop, so the run starts nothing more; the server refuses the rest
  try {
    const done = await wrote('/api/dispatch-stop-all', every ? {home: true} : {});
    if (done) {
      toast(`${done.stopped.length} agent${done.stopped.length === 1 ? '' : 's'} stopped.`
        + (run ? ' The Start all run is stopped too; nothing of it starts now.' : '')
        + (done.failed.length ? ` ${done.failed.length} could not be stopped: ${done.failed[0].error}` : '')
        + (done.notice ? ` ${done.notice}` : ''));
      await readAutostart(); await renderBoard(); await renderAgents();
    }
  } finally { control.disabled = false; }
}
$('#stopAllBtn').onclick = event => stopAll(event, false);
$('#stopHomeBtn').onclick = event => stopAll(event, true);
/* Reset agents ends the sessions of agents that died; it cannot be undone, so it is asked first, saying what it does
 * and what it leaves. */
async function resetAgents(event) {
  showAgentMenu(false);
  if (!await confirmAct({title: 'Reset agents?',
    text: 'Use it after a crash, when an agent stopped without letting go of its ticket.',
    lost: ['The sessions of agents that are no longer running are closed, and what their runners left running ends',
      'The tickets they still hold go back on the board'],
    kept: ['Agents at work are left alone', 'A ticket whose agent you stopped stays yours',
      'Nothing is deleted: every ticket, its steps and its log stay'],
    verb: 'Reset agents'})) return;
  event.target.disabled = true;
  try {
    const done = await wrote('/api/dispatch-reset', {});
    if (done) {
      toast(`Reset: ${done.released.length} ticket(s) back on the board, ${done.sessions_ended.length} dead session(s) `
        + `closed; ${done.still_working.length} agent(s) still working.`
        + ((done.kept_for_you || []).length ? ` ${done.kept_for_you.length} ticket(s) you stopped stay taken; drag `
          + 'them to To do to start them again.' : '')
        + ((done.deferred || []).length ? ` ${done.deferred.length} stay taken: ${done.deferred[0].reason}.` : ''));
      await renderBoard(); await renderAgents();
    }
  } finally { event.target.disabled = false; }
}
$('#resetAgentsBtn').onclick = resetAgents;
/* ---------- the settings screen ----------
 * Every setting of the project's folder, as metaform config shows them, and every module with whether it is on, laid
 * out as an app's settings are: the categories down the side and the one chosen on the right, the only part that
 * scrolls. It opens on Essentials, one short page of what a person needs to set Metaform up and run it day to day, the
 * settings declared `essential` in their order with the colour theme, the voice, the phone's check and the project
 * folder among them; then each category a setting declares, or its module's, with its settings under small headings;
 * Advanced, everything rarely changed, each module folded; and Modules last, under Advanced, each switched on or off
 * as metaform enable and disable do. Find a setting searches every category, and Enter goes to the first found.
 * A setting reads with its label in plain words, one line of help, whether it is set here, inherited and from where,
 * or the default, and whether only the person sets it; its key and the rest of its help are under More. A line cut
 * short opens in place at a click. Its control stands at the row's right edge, the control its kind needs: a switch,
 * a list of its choices, a number with its unit, a checklist, or text, a list as its items one per line. A change is
 * saved as it is made, through metaform set and unset in the project's folder, so it is checked as the command line
 * checks it, and a refusal is said under the setting with its next step; a risky choice is marked and asked once
 * before it is stored. The screen reads again whenever a setting changes elsewhere, so it never shows a value that no
 * longer holds. Left and Right change a switch or a choice, as on the terminal's settings screen. */
const CONFIG = {data: null, filter: '', errors: new Map(), page: 'essentials', folded: new Map(), saving: 0,
  again: false, reading: null, found: null, phone: null, voices: null, speech: null, more: new Set(), unfolded: new Set()};
const SHOWN_MODULES = 'modules';  // the chassis setting shown with the modules: which of them this folder shows
const LONG_PAGE = 10;  // a page with more settings than this opens its first heading and folds the rest
export async function openSettings() {
  showAgentMenu(false);
  $('#settingsbox').hidden = true;
  if (!S.project) return toast('Choose a project first: the settings shown are those of its folder.');
  CONFIG.page = 'essentials';  // it always opens on Essentials, never on Modules
  CONFIG.filter = '';
  $('#settings .search').value = '';
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
    const [found, speech] = await Promise.all([read('settings'), read('voice/status').catch(() => null)]);
    if (S.project !== project) return;
    CONFIG.data = found;
    CONFIG.speech = speech;
  } catch (error) { fill($('#settings .body'), refusalBox(error.body || {error: error.message})); return; }
  renderSettings();
}
/* A setting changed elsewhere, from the command line, an agent or another page: the screen reads again once its own
 * saves are in, so a control never acts on a value that no longer holds. */
function settingsHeard() {
  if ($('#settings').hidden || !CONFIG.data || !S.project) return;
  if (CONFIG.saving) { CONFIG.again = true; return; }
  clearTimeout(CONFIG.reading);
  CONFIG.reading = setTimeout(readSettings, 150);
}
document.addEventListener('metaform:settings', settingsHeard);
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
  const scroll = body.querySelector('.setmain')?.scrollTop || 0;
  const searching = Boolean(CONFIG.filter.trim());
  const pages = settingsPages(data);
  if (!pages.some(one => one.name === CONFIG.page)) CONFIG.page = 'essentials';
  const main = h('div', {class: 'setmain', role: 'region', 'aria-label': 'Settings'},
    searching ? searchPage(data, pages) : pageOf(data, pages.find(one => one.name === CONFIG.page)));
  fill(body, h('div', {class: 'setframe'}, sidebar(pages, searching), main));
  markCut();
  main.scrollTop = scroll;
  if (focused) body.querySelector(`[data-focus="${CSS.escape(focused)}"]`)?.focus({preventScroll: true});
  if (CONFIG.found) reveal(CONFIG.found);
}
/* ---------- pages ----------
 * Essentials, then each category in the order the declarations give, then Advanced, and Modules last under it. A
 * category with no setting here is left out; Essentials, General and Modules always show. */
function settingsPages(data) {
  const shown = data.settings.filter(row => row.key !== SHOWN_MODULES || row.owner !== 'chassis');
  const pages = [{name: 'essentials', title: 'Essentials', about: 'What Metaform needs to be set up and run day to '
    + 'day. Each links to its whole page.', rows: shown.filter(row => row.essential > 0)}];
  for (const category of data.categories || []) {
    const rows = shown.filter(row => (row.category || 'advanced') === category.name);
    if (rows.length || category.name === 'general') pages.push({...category, rows});
  }
  const shownRow = data.settings.find(row => row.key === SHOWN_MODULES && row.owner === 'chassis');
  pages.push({name: 'modules', title: 'Modules', under: 'advanced', rows: shownRow ? [shownRow] : [],
    about: 'On or off for every project, as metaform enable and disable turn them. A module turned off keeps its '
      + 'settings.'});
  return pages;
}
function sidebar(pages, searching) {
  const words = CONFIG.filter.trim().toLowerCase();
  const go = page => { CONFIG.page = page.name; CONFIG.filter = ''; $('#settings .search').value = ''; renderSettings();
    $('#settings .setmain')?.scrollTo({top: 0}); };
  const keys = event => {  // Up and Down move between the categories
    if (!['ArrowUp', 'ArrowDown'].includes(event.key)) return;
    event.preventDefault();
    const all = [...event.currentTarget.querySelectorAll('button')];
    all[(all.indexOf(document.activeElement) + (event.key === 'ArrowDown' ? 1 : all.length - 1)) % all.length]
      ?.focus();
  };
  return h('nav', {class: 'setside', 'aria-label': 'Settings categories', onkeydown: keys},
    pages.map(page => {
      // while searching, each category says how many it holds; Essentials' are counted in their categories
      const count = searching && page.name !== 'essentials' ? matchesOf(page, words).length : null;
      return h('button', {type: 'button', class: page.under ? 'under' : null, 'data-page': page.name,
        'data-focus': `page:${page.name}`, 'aria-current': !searching && page.name === CONFIG.page ? 'page' : null,
        disabled: count === 0, onclick: () => go(page)},
      h('span', {}, page.title), count !== null ? h('span', {class: 'setcount'}, String(count)) : null);
    }));
}
function pageHead(page) {
  return h('div', {class: 'sethead'}, h('h2', {}, page.title), page.about ? h('p', {}, page.about) : null);
}
function pageOf(data, page) {
  if (page.name === 'essentials') return essentialsPage(data, page);
  if (page.name === 'modules') return modulesPage(data, page);
  const parts = [pageHead(page)];
  if (page.name === 'general') parts.push(generalPart(data));
  parts.push(...headed(page, page.rows, {folded: page.name === 'advanced'}));
  return parts;
}
/* A page's settings under their headings: a setting's heading, else its section less a first heading that is the
 * page's own name, else its module's name. The declaration's shared order decides the headings and rows, as on the
 * command line. On Advanced each heading is folded until opened; on a long page the first is
 * open and the rest folded; the person's own opening and folding is kept while the page is open. */
function headed(page, rows, {folded = false} = {}) {
  const groups = new Map();
  rows.forEach(row => {
    const title = headingOf(row, page);
    const group = groups.get(title) || {title, rows: []};
    group.rows.push(row);
    groups.set(title, group);
  });
  const long = rows.length > LONG_PAGE;
  return [...groups.values()].map((group, index) => {
    const id = `${page.name}/${group.title}`;
    const open = CONFIG.folded.has(id) ? CONFIG.folded.get(id) : !(folded || (long && index > 0));
    const list = h('div', {class: 'setlist'}, group.rows.map(row => settingRow(row)));
    if (!folded && !long) return setGroup(group.title, list);
    const box = h('details', {class: 'setgroup fold', open, 'data-group': group.title},
      h('summary', {}, h('h3', {}, group.title), h('span', {class: 'setcount'}, String(group.rows.length))), list);
    box.addEventListener('toggle', () => CONFIG.folded.set(id, box.open));
    return box;
  });
}
const OWNER_WORDS = {chassis: 'Metaform', mcp: 'MCP', elevenlabs: 'ElevenLabs'};
const ownerWords = owner => OWNER_WORDS[owner] || owner.charAt(0).toUpperCase() + owner.slice(1).replaceAll('_', ' ');
function headingOf(row, page) {
  const parts = String(row.heading || row.section || '').split('/').filter(Boolean);
  if (parts[0] === page.title) parts.shift();
  if (page.name === 'advanced') parts.unshift(ownerWords(row.owner));
  return parts.length ? parts.join(' · ') : ownerWords(row.owner);
}
const setGroup = (title, ...kids) => h('section', {class: 'setgroup', 'data-group': title}, h('h3', {}, title), kids);
const titleOf = name => CONFIG.data.categories.find(one => one.name === name)?.title || name;
/* A link from a row to the whole page of its category. */
function toCategory(name, key) {
  return h('button', {type: 'button', class: 'tocat', 'data-focus': `to:${key}`, title: `Every ${titleOf(name)} `
    + 'setting', onclick: () => jump(name, key)}, `${titleOf(name)} ›`);
}
/* ---------- Essentials ----------
 * The settings declared essential, in their order, with what the page itself holds put among them by place: the colour
 * theme after the agents', the voice after who speaks, the phone's check after its number, and the project folder
 * last. The page fits one screen. */
const PAGE_ROWS = [
  {at: 60, row: () => themeRow()},
  {at: 75, row: data => voiceRow(data)},
  {at: 105, row: data => phoneRow(data)},
  {at: 1000, row: data => folderRow(data)},
];
function essentialsPage(data, page) {
  const declared = page.rows.map(row => ({at: row.essential, row: () => settingRow(row, {link: true})}));
  const all = [...declared, ...PAGE_ROWS].sort((one, two) => one.at - two.at);
  return [pageHead(page), h('div', {class: 'setlist essentials'}, all.map(one => one.row(data)).filter(Boolean))];
}
/* A row the page itself holds, laid out as a setting's is. */
function pageRow(name, label, help, control, {link = null, title = null} = {}) {
  return h('div', {class: 'setrow', 'data-key': name},
    h('div', {class: 'what'}, h('div', {class: 'name'}, h('span', {class: 'label', title}, label)),
      h('div', {class: 'helpline'}, h('span', {class: 'help', title: help}, help), link)),
    h('div', {class: 'control'}, control));
}
/* The colour theme: the View menu's Colors, the same choices and the same act. */
function themeRow() {
  const theme = $('#theme');
  if (!theme) return null;
  const pick = h('select', {'aria-label': 'Colour theme', 'data-focus': 'page:theme',
    onchange: () => { theme.value = pick.value; setTheme(pick.value); }},
  [...theme.options].map(option => h('option', {value: option.value, selected: option.value === theme.value},
    option.textContent)));
  return pageRow('page:theme', 'Colour theme', 'The colours of this page and its maps, as the View menu sets them.',
    pick);
}
/* The voice the person's agent speaks with, for their mascot's character: one of this browser's voices, or, when
 * ElevenLabs speaks, one of its voices, listed from the account only when asked, since that asks ElevenLabs. */
function voiceRow(data) {
  const row = key => data.settings.find(one => one.key === key);
  const tts = row('voice_tts'), mascot = row('web_mascot');
  if (!tts) return null;
  const character = mascot && mascot.value && mascot.value !== 'none' ? String(mascot.value) : null;
  const help = character ? `The voice of your ${character}.` : 'Choose your mascot under Map and display to give it '
    + 'a voice of its own.';
  if (!character || tts.value === 'off') {
    return pageRow('page:voice', 'Voice', tts.value === 'off' ? 'Nothing is spoken: Speaks with is off.' : help, null,
      {link: toCategory('voice', 'page:voice')});
  }
  const eleven = tts.value === 'elevenlabs', list = row(eleven ? 'elevenlabs_voices' : 'voice_voices');
  if (!list || (!eleven && tts.value !== 'browser')) {  // an engine another module brings has its own voices
    return pageRow('page:voice', 'Voice', `${tts.value} speaks with its own voices.`, null,
      {link: toCategory('voice', 'page:voice')});
  }
  const chosen = (list.value || []).find(one => one.startsWith(`${character}=`))?.split('=').slice(1).join('=') || '';
  const names = eleven ? (CONFIG.voices || []).map(one => one.name).filter(Boolean)
    : 'speechSynthesis' in window ? speechSynthesis.getVoices().map(one => one.name) : [];
  if (!eleven && !names.length && 'speechSynthesis' in window) {  // the browser lists its voices once it has them
    speechSynthesis.addEventListener('voiceschanged', renderSettings, {once: true});
  }
  const listed = [...new Set([...(chosen ? [chosen] : []), ...names])];
  const pick = h('select', {'aria-label': 'Voice', 'data-focus': 'page:voice', onchange: () => {
    const kept = (list.value || []).filter(one => !one.startsWith(`${character}=`));
    saveSetting(list, pick.value ? [...kept, `${character}=${pick.value}`] : kept);
  }}, h('option', {value: '', selected: !chosen}, eleven ? 'Its own voice' : 'Chosen for it'),
  listed.map(name => h('option', {value: name, selected: name === chosen}, name)));
  const more = eleven && !CONFIG.voices ? h('button', {type: 'button', class: 'btn sm quiet', 'data-focus':
    'page:voices', title: 'Ask ElevenLabs for the voices on your account', onclick: listVoices}, 'List voices') : null;
  return pageRow('page:voice', 'Voice', help, h('span', {class: 'pair'}, pick, more),
    {link: toCategory('voice', 'page:voice'), title: list.switch});
}
async function listVoices() {
  try {
    const found = await read('speech-voices');
    CONFIG.voices = found.account || [];
    if (!found.account) toast(found.next || 'ElevenLabs gave no voices.');
  } catch (error) { toast(`The voices could not be listed: ${error.message}`); }
  renderSettings();
}
/* Whether the phone can work, checked only when asked: metaform twilio status, which reads the settings and the
 * environment the bridge runs in, and the last `metaform twilio check` of where Twilio sends the number's calls. */
function phoneRow(data) {
  const on = data.settings.find(one => one.key === 'twilio_enabled');
  if (!on) return null;
  const checked = CONFIG.phone;
  const twilio = checked?.check?.problems || [];  // the number's own addresses, as the last check found them
  const said = !on.value ? 'The phone is off.' : !checked ? 'Not checked yet.'
    : checked.error ? checked.error
      : checked.problems?.length ? `${checked.problems[0].problem} Next: ${checked.problems[0].next}`
        : twilio.length ? `${twilio[0].problem} Next: ${twilio[0].next}`
          : checked.running ? 'Ready: the bridge is running.' : 'Ready: set up, and the bridge starts with the page.';
  const check = h('button', {type: 'button', class: 'btn sm', 'data-focus': 'page:phone-check', disabled: !on.value,
    title: 'Check now whether the phone is set up', onclick: checkPhone}, 'Check');
  return pageRow('page:phone', 'Phone status', said, check, {link: toCategory('phone', 'page:phone')});
}
async function checkPhone() {
  try { CONFIG.phone = await read('phone-check'); } catch (error) { CONFIG.phone = {error: error.message}; }
  renderSettings();
}
/* The project these settings are kept for: the page's own project, chosen as the header chooses it, and its folder. */
function folderRow(data) {
  const projects = S.projects?.length ? S.projects : [{id: S.project}];
  const pick = h('select', {'aria-label': 'Project', 'data-focus': 'page:project', onchange: async () => {
    $('#proj').value = pick.value;
    $('#proj').dispatchEvent(new Event('change'));
    await readSettings();
  }}, projects.map(one => h('option', {value: one.id, selected: one.id === S.project}, one.id)));
  return pageRow('page:project', 'Project folder', data.folder, pick, {link: toCategory('general', 'page:project'),
    title: 'A folder setting applies to this folder and every folder below it; a global one applies everywhere.'});
}
/* General: the folder the settings are kept for, and what folder and global mean. */
function generalPart(data) {
  return h('p', {class: 'hint folder'}, `The settings of ${S.project}, kept for `, h('code', {}, data.folder),
    '. A folder setting applies to this folder and every folder below it; one marked Global applies everywhere. '
    + 'They are the settings metaform config shows, and each change is saved as metaform set saves it.');
}
/* ---------- Modules ---------- */
function modulesPage(data, page) {
  const modules = [...data.modules].sort((one, two) => one.id.localeCompare(two.id));
  return [pageHead(page), data.modules_refused ? refusalBox(data.modules_refused) : null,
    h('div', {class: 'setlist modules'}, modules.map(moduleRow)),
    page.rows.length ? setGroup('This folder', h('div', {class: 'setlist'},
      settingRow(page.rows[0], {label: 'Modules shown in this folder'}))) : null];
}
/* ---------- search ----------
 * Every category's settings and the modules, matched on their label, key, help, details and heading; a page's count
 * shows in the side. Enter goes to the first found, and a found setting's label goes to it in its category. */
function matchesOf(page, words) {
  if (!words) return page.rows;
  const has = (...texts) => texts.some(text => String(text || '').toLowerCase().includes(words));
  if (page.name === 'modules') {
    return [...page.rows.filter(row => has(row.key, row.help, 'modules shown in this folder')),
      ...CONFIG.data.modules.filter(module => has(module.id, module.summary, module.problem))];
  }
  return page.rows.filter(row => has(row.key, row.label, row.help, row.details, row.heading, row.section,
    page.title));
}
function searchPage(data, pages) {
  const words = CONFIG.filter.trim().toLowerCase();
  const found = pages.filter(page => page.name !== 'essentials').map(page => ({page, rows: matchesOf(page, words)}))
    .filter(one => one.rows.length);
  if (!found.length) return h('p', {class: 'empty'}, `No setting matches ${CONFIG.filter.trim()}.`);
  return found.map(({page, rows}) => h('section', {class: 'setgroup', 'data-group': page.title},
    h('h3', {}, h('button', {type: 'button', class: 'tocat', onclick: () => jump(page.name)}, `${page.title} ›`)),
    h('div', {class: 'setlist'}, rows.map(row => row.key ? settingRow(row, {go: page.name}) : moduleRow(row)))));
}
function firstFound() {
  const words = CONFIG.filter.trim().toLowerCase();
  for (const page of settingsPages(CONFIG.data).filter(one => one.name !== 'essentials')) {
    const row = matchesOf(page, words)[0];
    if (row) return [page.name, row.key ? `setting:${row.key}` : `module:${row.id}`];
  }
  return null;
}
/* To a category's page, and to one setting on it: shown, opened under its heading, and its control focused. */
function jump(name, key = null) {
  CONFIG.page = name;
  CONFIG.filter = '';
  $('#settings .search').value = '';
  CONFIG.found = key && !key.startsWith('page:') ? key : null;
  renderSettings();
  if (!CONFIG.found) $('#settings .setmain')?.scrollTo({top: 0});
}
function reveal(key) {
  CONFIG.found = null;
  const [kind, name] = [key.slice(0, key.indexOf(':')), key.slice(key.indexOf(':') + 1)];
  const row = $(`#settings .setmain .setrow[data-${kind === 'module' ? 'module' : 'key'}="${CSS.escape(name)}"]`);
  if (!row) return;
  const control = row.querySelector('[data-focus]:not(.morebtn):not(.tocat)');
  const fold = row.closest('details');
  if (fold) fold.open = true;
  row.scrollIntoView({block: 'center'});
  row.classList.add('found');
  setTimeout(() => row.classList.remove('found'), 1600);
  control?.focus({preventScroll: true});
}
/* ---------- rows and controls ---------- */
/* Left and Right turn a switch off and on, and step a list of choices back and on, saving as a click does. */
function arrowSwitch(event, input) {
  if (!['ArrowLeft', 'ArrowRight'].includes(event.key) || input.disabled) return;
  event.preventDefault();
  const on = event.key === 'ArrowRight';
  if (input.checked === on) return;
  input.checked = on;
  input.dispatchEvent(new Event('change'));
}
function arrowSelect(event, select, risky = []) {
  if (!['ArrowLeft', 'ArrowRight'].includes(event.key) || select.disabled) return;
  event.preventDefault();
  const next = select.selectedIndex + (event.key === 'ArrowRight' ? 1 : -1);
  if (next < 0 || next >= select.options.length || select.options[next].disabled) return;
  if (risky.includes(select.options[next].value)) {  // never stepped onto: picked from the list, then confirmed
    toast(`${select.options[next].value} lets agents act without asking: pick it from the list to confirm it.`);
    return;
  }
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
        module.problem ? h('span', {class: 'badge warn'}, 'not loaded') : null,
        h('span', {class: 'help', title: module.problem || module.summary}, module.problem || module.summary))),
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
/* Whether the value is set here, inherited from a folder above (named), glued, or the default, at a glance. */
const STATE_BADGES = {default: ['badge off', 'Default', 'The default: nothing is saved for it'],
  set: ['badge ok', 'Set here', 'Saved for this folder'],
  glued: ['badge warn', 'Glued', 'Set here, and kept through metaform unset all until it is unglued'],
  inherited: ['badge', 'Inherited', 'Set by a folder above this one']};
const folderName = path => String(path || '').split(/[\\/]/).filter(Boolean).pop() || String(path || '');
function stateBadge(row) {
  const [style, words, said] = STATE_BADGES[row.state] || ['badge', row.state, ''];
  if (row.state === 'inherited' && row.from) {
    return h('span', {class: `${style} state`, title: `Inherited from ${row.from}, which sets it for every folder `
      + 'below it; change or reset it there'}, `From ${folderName(row.from)}`);
  }
  return h('span', {class: `${style} state`, title: said}, words);
}
/* One setting: `link` adds the way to its category's page, as on Essentials; `go`, in a search, makes its label go
 * to it there. */
function settingRow(row, {label = row.label, link = false, go = null} = {}) {
  const id = `setting:${row.key}`;
  const error = CONFIG.errors.get(id);
  const control = settingControl(row, id, label);
  const risky = (row.risky || []).includes(row.value);
  const named = go ? h('button', {type: 'button', class: 'label', title: `${row.switch}: show it in ${titleOf(go)}`,
    onclick: () => jump(go, id)}, label) : h('span', {class: 'label', title: row.switch}, label);
  const open = CONFIG.more.has(row.key);
  const ready = row.key === 'voice_tts' ? Object.entries(CONFIG.speech?.tts?.engines || {})
    .filter(([name, engine]) => engine.ready === true && name !== row.value)
    .map(([name]) => `${ownerWords(name)} ready, unused: ${row.switch}=${name}.`).join(' ') : '';
  const help = ready || row.help;
  const more = h('button', {type: 'button', class: 'morebtn', 'aria-expanded': String(open), 'data-focus':
    `more:${row.key}`, title: 'Its switch, all its help, and Glue', onclick: () => {
    if (!CONFIG.more.delete(row.key)) CONFIG.more.add(row.key);
    renderSettings();
  }}, 'More');
  return h('div', {class: `setrow${risky ? ' risky' : ''}`, 'data-key': row.key},
    h('div', {class: 'what'},
      h('div', {class: 'name'}, named, stateBadge(row),
        row.scope === 'global' ? h('span', {class: 'badge', title: 'Applies in every folder'}, 'Global') : null,
        row.person_only ? h('span', {class: 'badge mine', title: 'Only you change it, here or on the command line; '
          + 'an agent is refused it over MCP'}, 'Yours') : null,
        risky ? h('span', {class: 'badge warn', title: row.choice_help?.[row.value] || 'Agents act without asking'},
          'Risky') : null, more),
      h('div', {class: 'helpline'}, help ? h('span', {class: `help${ready ? ' readyhint' : ''}`, title: help}, help) : null,
        link ? toCategory(row.category, id) : null),
      open ? h('div', {class: 'morebox'},
        h('p', {}, h('code', {}, row.switch), row.key !== row.switch.slice(2).replaceAll('-', '_')
          ? [' ', h('code', {}, row.key)] : null, glueButton(row)),
        h('p', {}, 'Default: ', h('code', {}, shownValue(row.key, row.default)),
          row.state === 'inherited' && row.from ? [' · inherited from ', h('code', {}, row.from)] : null),
        String(row.help || '').length > 90 ? h('p', {}, row.help) : null,
        row.details ? h('p', {}, row.details) : null) : null),
    h('div', {class: 'control'}, resetButton(row), control.main),  // the control itself at the row's right edge
    link && control.wide?.matches('.hint') ? null : control.wide || null,  // Essentials stays one line a setting
    error ? refusalBox(error) : null);
}
/* Glue, for a value set and not glued yet, as metaform set --glue keeps it. */
function glueButton(row) {
  const empty = Array.isArray(row.value) && !row.value.length && CONFIG.data.all_when_empty.includes(row.key);
  if (row.state === 'glued' || row.state === 'inherited' || row.value === null || row.value === undefined || empty) {
    return null;
  }
  return h('button', {class: 'btn sm quiet glue', type: 'button', 'data-focus': `glue:${row.key}`,
    title: 'Keep this value through metaform unset all, as metaform set --glue does',
    onclick: () => saveSetting(row, row.value, {glue: true})}, 'Glue');
}
/* Reset, or Unglue for a glued value, back to its default as metaform unset does; shown only for a value set here. */
function resetButton(row) {
  if (row.state !== 'set' && row.state !== 'glued') return null;
  const glued = row.state === 'glued';
  return h('button', {class: 'btn sm quiet reset', type: 'button', 'data-focus': `reset:${row.key}`,
    onclick: () => resetSetting(row),
    title: glued ? `Unglue it and return it to its default, as metaform unset --unglue ${row.switch} does`
      : `Return it to its default, as metaform unset ${row.switch} does`}, glued ? 'Unglue' : 'Reset');
}
/* A number's unit, beside it; cents are said in the currency too. */
function unitOf(row, value) {
  if (!row.unit) return null;
  const amount = Number(value);
  const said = row.unit === 'cents' && Number.isFinite(amount) && amount > 0 ? `cents ($${(amount / 100).toFixed(2)})`
    : row.unit === 'cents' && amount === 0 ? 'cents (no limit)' : row.unit;
  return h('span', {class: 'unit'}, said);
}
/* A choice as a person reads it: of a setting that says its choices in words, ask_all reads Ask all; any other, such
 * as a project or a model, is its own name. The value saved is the choice itself. */
function choiceWords(choice, worded) {
  if (choice === '' || choice === null || choice === undefined) return '(none)';
  if (!worded) return String(choice);
  const words = String(choice).replace(/[_-]+/g, ' ').trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
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
    return {main: h('span', {class: 'pair'}, input, unitOf(row, row.value))};
  }
  const choices = Array.isArray(row.choices) && row.choices.length ? row.choices : null;
  if (row.kind === 'select' && choices) {
    const listed = choices.includes(row.value) ? choices : [row.value ?? '', ...choices];
    const said = row.choice_help || {};  // each choice in plain words, the one in force said under the row
    const risky = row.risky || [], worded = Object.keys(said).length > 0;
    const chosen = async () => {
      const choice = select.value;
      if (!risky.includes(choice)) return save(choice);
      if (!await confirmRisk(label, choice, said[choice])) { select.value = row.value ?? ''; return; }
      saveSetting(row, choice, {confirm: true});
    };
    const select = h('select', {'aria-label': label, 'data-focus': id, onchange: chosen,
      onkeydown: event => arrowSelect(event, select, risky)},
      listed.map(choice => h('option', {value: choice, selected: choice === row.value, title: said[choice] || null,
        disabled: !choices.includes(choice)}, choiceWords(choice, worded)
        + (risky.includes(choice) ? ' (risky: asks first)' : ''))));
    // while it offers no more than its default, the command that reads its choices from their source, such as an
    // agent's models, is a button beside it
    const reads = row.choices_from ? h('button', {type: 'button', class: 'btn sm quiet',
      'data-focus': `choices:${row.key}`, title: `Runs ${row.choices_from}: it starts the agent once, with no prompt, and reads the choices it offers`,
      onclick: () => readChoices(row)}, 'Read choices') : null;
    return {main: reads ? h('span', {class: 'pair'}, select, reads) : select,
      wide: said[row.value] ? h('p', {class: 'hint'}, said[row.value]) : null};
  }
  if (row.kind === 'list' && choices) return {main: null, wide: checklist(row, choices, id, label)};
  if (row.kind === 'list') return {main: itemsBox(row, id, label, save)};
  const input = h('input', {type: 'text', value: String(row.value ?? ''), 'aria-label': label, 'data-focus': id,
    spellcheck: 'false', autocomplete: 'off', placeholder: '(none)', onchange: () => save(input.value)});
  return {main: input};
}
/* A list without choices, one item per line, saved as the list of its lines: an item may hold a comma. */
function itemsBox(row, id, label, save) {
  const items = Array.isArray(row.value) ? row.value : [];
  const all = CONFIG.data.all_when_empty.includes(row.key);
  const box = h('textarea', {rows: Math.max(2, items.length), 'aria-label': label, 'data-focus': id,
    spellcheck: 'false', autocomplete: 'off', placeholder: all ? 'all' : 'one per line',
    onchange: () => save(box.value.split('\n').map(item => item.trim()).filter(Boolean))});
  box.value = items.join('\n');
  return box;
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
/* A select's choices read from their source by its declared command, then the screen drawn with them. */
async function readChoices(row) {
  const id = `setting:${row.key}`;
  toast(`Reading the choices of ${row.label}…`);
  const done = await posting(() => posted('/api/settings/choices', {key: row.key}));
  if (!done.ok) { CONFIG.errors.set(id, done.body); renderSettings(); return; }
  CONFIG.errors.delete(id);
  CONFIG.data = done.body;
  renderSettings();
  const now = done.body.settings.find(one => one.key === row.key);
  toast((now?.choices || []).length > 1 ? `${row.label}: ${now.choices.length} choices read.`
    : `${row.label} still offers only ${now?.choices?.[0] ?? 'its default'}.`);
}
/* ---------- saving ---------- */
/* Save one setting, or glue it, and say so with Undo; Undo puts back what it was. A refusal is said under it. */
async function saveSetting(row, value, {glue = false, quiet = false, confirm = false} = {}) {
  const id = `setting:${row.key}`;
  const before = {state: row.state, value: row.value};
  const done = await posting(() => posted('/api/settings', {key: row.key, value, ...(glue ? {glue: true} : {}),
    ...(confirm ? {confirm: true} : {})}));
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
    : restoreSetting(now || row, before.value));
  return true;
}
/* A save in flight holds back a read for a change heard meanwhile, its own among them, until it is in. */
async function posting(write) {
  CONFIG.saving++;
  try { return await write(); } finally {
    CONFIG.saving--;
    if (!CONFIG.saving && CONFIG.again) { CONFIG.again = false; settingsHeard(); }
  }
}
/* Undo puts back what it was; a risky choice put back is confirmed as choosing it is. */
async function restoreSetting(row, value, {glue = false} = {}) {
  const risky = (row.risky || []).includes(value);
  if (risky && !await confirmRisk(row.label, value, row.choice_help?.[value])) return false;
  return saveSetting(row, value, {glue, quiet: true, confirm: risky});
}
async function resetSetting(row, {quiet = false} = {}) {
  const id = `setting:${row.key}`, glued = row.state === 'glued';
  if (glued && !quiet && !await confirmAct({title: `Unglue ${row.label}?`,
    text: 'A glued setting keeps its value through metaform unset all. Unglued, it returns to its default.',
    verb: 'Unglue and reset', danger: false})) return false;
  const before = row.value;
  const done = await posting(() => posted('/api/settings/reset', {key: row.key, ...(glued ? {unglue: true} : {})}));
  if (!done.ok) { CONFIG.errors.set(id, done.body); renderSettings(); return false; }
  CONFIG.errors.delete(id);
  CONFIG.data = done.body;
  renderSettings();
  afterSetting(row.key);
  if (quiet) return true;
  const now = done.body.settings.find(one => one.key === row.key);
  undoable(`${row.label}: back to its default, ${shownValue(row.key, now?.value)}.`,
    () => restoreSetting(now || row, before, {glue: glued}));
  return true;
}
/* What the rest of the page shows from a setting follows it: the Autostart switch, the agent pickers, Agent prompts,
 * and the folder's layers. */
function afterSetting(key) {
  if (key.startsWith('dispatch_')) readAutostart();
  if (key === 'dispatch_agent') readHarnesses().then(paintPickers);  // every picker's default follows
  if (key === 'dispatch_prompts') readPrompts();
  if (key === 'layers' && S.view === null) {
    read('layers', {limit: 0}).then(found => { S.layers = found.results; renderChips(); })
      .catch(error => toast(error.message));
  }
  // ULTRA: the 3D map fades to the graphics chosen, as U does
  if (key === 'web_chat_details') {  // saved here, it rules over W's choice on this page, and every thread follows
    VIEW.chatDetails = CONFIG.data?.settings?.find(one => one.key === key)?.value === true;
    CHATWORK.shown = null;
    drawHelpdesk();
  }
  if (key === 'web_theme') {  // set on the Settings screen: the page takes the theme at once
    const theme = CONFIG.data?.settings?.find(one => one.key === key)?.value;
    if (theme && theme !== document.documentElement.dataset.theme) setTheme(String(theme), false);
  }
}
/* ---------- text cut short ----------
 * A label, a line of help or a unit cut short by its row's width opens in place at a click or Enter on it, the
 * page's `expandCut`; the rows opened stay open through the screen's redraws. */
const rowKey = row => row.dataset.key || `module:${row.dataset.module}`;
const markCut = expandCut($('#settings .body'), {row: '.setrow', text: ':is(.help, span.label, .unit)', key: rowKey,
  kept: CONFIG.unfolded});
$('#allSettingsBtn').onclick = openSettings;
$('#settingsGearBtn').onclick = openSettings;
$('#settings .search').addEventListener('input', event => { CONFIG.filter = event.target.value; renderSettings(); });
$('#settings .search').addEventListener('keydown', event => {  // Enter goes to the first setting found
  if (event.key !== 'Enter' || !CONFIG.filter.trim() || !CONFIG.data) return;
  event.preventDefault();
  const first = firstFound();
  if (first) jump(...first);
});
$('#settings .close').onclick = () => { $('#settings').hidden = true; };
overlay($('#settings'), {kind: 'dialog', close: () => { $('#settings').hidden = true; }});
