/* The launch permission controls shared by dispatch and roundtable setup. Choices apply only to the launches
 * opened from their window; project defaults remain in force when no explicit value is chosen. */
import {h, fill} from '/page/app/core/dom.js';
import {S, read} from '/page/app/core/reads.js';
import {agentName} from '/page/app/agents/pickers.js';

/* How each dispatch_prompts choice reads, and what approving every prompt risks; the Agents menu and the start window
 * say them alike. */
export const PROMPT_WORDS = {
  'approve-all': ['Approve every prompt',
    'Agents run any tool without asking, including ones that change or delete files.'],
  'approve-reads': ['Approve reads and searches; ask for the rest', ''],
  ask_all: ['Ask every prompt as a question at the ticket', '']};
/* The harness modes that let the agent act without asking, whatever the prompts answer. */
const OPEN_MODES = ['bypassPermissions', 'agent-full-access'];
const promptWords = choice => PROMPT_WORDS[choice]?.[0] || choice;
/* The caller keeps the launch choices and identifies whether its controls are still current after reads. */
export async function drawPermissions(box, agent, own, current) {
  const project = S.project;
  let prompts = null, found = null;
  try { prompts = await read('dispatch-prompts'); } catch { prompts = null; }
  try { found = agent ? (await read('dispatch-options', {agent})).agents?.[0] || null : null; } catch { found = null; }
  if (S.project !== project || !current()) return;
  const choices = prompts?.choices || Object.keys(PROMPT_WORDS);
  const promptsPick = h('select', {'aria-label': 'Permission prompts', class: 'prompts',
    onchange: () => { own.prompts = promptsPick.value; sayRisk(); }},
  h('option', {value: ''}, `Project setting: ${prompts ? promptWords(prompts.value) : 'unknown'}`),
  choices.map(choice => h('option', {value: choice, selected: choice === own.prompts},
    promptWords(choice))));
  const setting = (found?.settings || []).find(one => one.key === 'mode');
  const modes = setting?.choices || [];
  const named = value => modes.find(one => one.value === value)?.name || value;
  const projectMode = setting ? setting.chosen ?? setting.current : null;
  const modePick = setting ? h('select', {'aria-label': 'Agent mode', class: 'mode',
    onchange: () => { own.mode = modePick.value; sayRisk(); }},
  h('option', {value: ''}, `Project setting: ${named(projectMode)}`),
  modes.map(one => h('option', {value: one.value, title: one.description || '', selected: one.value === own.mode},
    one.name || one.value))) : null;
  fill(box.querySelector('.controls'), h('label', {class: 'setting'}, h('span', {}, 'Permission prompts'), promptsPick),
    modePick ? h('label', {class: 'setting'}, h('span', {}, 'Mode'), modePick) : null);
  box.querySelector('.hint').textContent = (modePick ? '' : found?.next
    ? `${agentName(agent)} offers its modes once it has run here: ${found.next}. `
    : agent ? `${agentName(agent)} offers no mode to choose. ` : '')
    + 'Left at the project setting, each start follows the settings; a choice here is for the agents this window '
    + 'starts, and the settings stay as they are.';
  const sayRisk = () => {
    const prompting = own.prompts || prompts?.value, mode = own.mode || projectMode;
    const said = [prompting === 'approve-all' ? PROMPT_WORDS['approve-all'][1] : '',
      OPEN_MODES.includes(mode) ? `In ${named(mode)} mode the agent acts without asking: `
        + `${modes.find(one => one.value === mode)?.description || 'it accepts every permission'}.` : '']
      .filter(Boolean);
    const risk = box.querySelector('.risk');
    risk.textContent = said.length ? `${said.join(' ')} Nothing stops a wrong or harmful action.` : '';
    risk.hidden = !said.length;
  };
  sayRisk();
}
