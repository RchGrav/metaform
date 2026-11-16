import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import test from 'node:test';

const source = readFileSync(new URL('../page/app/board/board.js', import.meta.url), 'utf8');
const dispatch = readFileSync(new URL('../page/app/agents/dispatch.js', import.meta.url), 'utf8');
const area = source.slice(source.indexOf('const FRONTEND'), source.indexOf('export const eligibleAgents'))
  .replaceAll('export ', '');
const controls = source.slice(source.indexOf('function ticketControls('), source.indexOf('/* Which agent works'));
function fixture(defaultAgent = 'other', options = {agents: []}) {
  let selected;
  const reads = [], writes = [];
  const api = runInNewContext(`${area}\n${controls}\n({defaultAgent, ticketControls, runtimeControls, runtimeSummary})`, {
    HARNESS: {default: defaultAgent},
    S: {project: 'project', base: 'base'},
    h: (tag, attributes, ...children) => ({tag, attributes, children}),
    fill: (box, ...children) => { box.children = children; },
    pickerOptions: (picks, chosen) => picks.map(one => ({tag: 'option',
      attributes: {value: one.value, selected: one.value === chosen}, children: [one.label]})),
    agentName: agent => agent,
    read: async (name, params) => { reads.push({name, ...params}); return options; },
    wrote: async (path, body) => { writes.push({path, body}); return true; },
    renderBoard: async () => {},
    agentSelect: chosen => { selected = chosen; },
    eligibilityPicker: () => null, eligibleAgents: () => [], glyphPick: () => null,
  });
  return {api, reads, writes, selected: () => selected};
}

test('card predicts area agent before start', () => {
  const f = fixture();
  for (const address of ['code.interface.graphical', 'code.assistant.navigation.camera',
    'code.page.board', 'code.figures', 'code.chat.dock', 'code.css', 'code.map2d', 'code.map3d']) {
    f.api.ticketControls({address, map: {}, done: true});
    assert.equal(f.selected(), 'claude', address);
  }
  f.api.ticketControls({address: 'code.dispatch.admission', map: {}, done: true});
  assert.equal(f.selected(), 'codex');
});

test('card preserves explicit agent and uses receiver address or page references', () => {
  const f = fixture();
  f.api.ticketControls({address: 'code.interface.graphical', map: {agent: 'other'}, done: true});
  assert.equal(f.selected(), 'other');
  f.api.ticketControls({receiver_address: 'code.assistant.navigation', map: {}, done: true});
  assert.equal(f.selected(), 'claude');
  f.api.ticketControls({address: 'code.unknown', map: {paths: ['src/metaform/modules/web/page/app/board/board.js']},
    done: true});
  assert.equal(f.selected(), 'claude');
});

test('card uses configured default only when area is unknown', () => {
  const f = fixture();
  f.api.ticketControls({map: {}, done: true});
  assert.equal(f.selected(), 'other');
  assert.equal(f.api.defaultAgent('code.backend'), 'codex');
});

test('card shows saved launch choices and decision confidence', () => {
  const {api} = fixture();
  const summary = api.runtimeSummary({address: 'code.web', map: {agent: 'codex', model: 'gpt-6', effort: 'high',
    decision: {decider: 'jev', confidence: 0.94, reason: 'Backend implementation.'}}});
  assert.equal(summary.children[0], 'codex gpt-6 high');
  assert.match(summary.attributes.title, /Chosen by jev \(94%\)/);
  assert.match(summary.attributes.title, /Backend implementation\./);
  const changed = api.runtimeSummary({map: {agent: 'claude', model: 'opus', effort: 'max',
    decision: {decider: 'person', confidence: null}}});
  assert.equal(changed.children[0], 'claude opus max');
  assert.match(changed.attributes.title, /Chosen by person/);
  assert.doesNotMatch(changed.attributes.title, /%/);
});

test('card loads offered runtime choices on expansion and saves ticket overrides', async () => {
  const f = fixture('codex', {agents: [{agent: 'codex', settings: [
    {key: 'model', current: 'gpt-6', choices: [{value: 'gpt-6', name: 'GPT 6'}, {value: 'small', name: 'Small'}],
      picks: [{value: 'gpt-6', label: 'GPT 6'}, {value: 'small', label: 'Small'}]},
    {key: 'thought_level', chosen: 'high', choices: [{value: 'medium', name: 'Medium'}, {value: 'high', name: 'High'}],
      picks: [{value: 'medium', label: 'Medium'}, {value: 'high', label: 'High'}]},
  ]}]});
  let toggle;
  const settings = {open: false, addEventListener: (name, callback) => { assert.equal(name, 'toggle'); toggle = callback; }};
  const ticket = {map: {model: 'gpt-6', effort: 'medium'}};
  const changes = [];
  const box = f.api.runtimeControls(ticket, 'codex', async fields => { changes.push(fields); return true; }, settings);
  assert.equal(f.reads.length, 0);
  settings.open = true;
  toggle();
  await new Promise(setImmediate);
  const labels = box.children[0], model = labels[0].children[1], effort = labels[1].children[1];
  assert.equal(f.reads.length, 1);
  assert.equal(f.reads[0].name, 'dispatch-options');
  assert.equal(f.reads[0].agent, 'codex');
  assert.equal(model.disabled, false);
  assert.equal(effort.disabled, false);
  assert.equal(model.children[0].children[0], 'Project setting: GPT 6');
  assert.equal(effort.children[0].children[0], 'Project setting: High');
  assert.equal(effort.children[2][0].attributes.selected, true);
  effort.value = 'high';
  await effort.attributes.onchange({currentTarget: effort});
  assert.equal(changes[0].effort, 'high');
  model.value = '';
  await model.attributes.onchange({currentTarget: model});
  assert.equal(changes[1].model, 'none');
  toggle();
  assert.equal(f.reads.length, 1);
});

test('starts keep each assigned agent until person changes current picker', () => {
  const state = {agentChanged: false};
  const choice = dispatch.match(/^const startAgentFor = .+;$/m)?.[0];
  assert.ok(choice, 'startAgentFor declaration must exist');
  const startable = dispatch.slice(dispatch.indexOf('function startable('), dispatch.indexOf('/* How many of the tickets'));
  const api = runInNewContext(`${choice}\n${startable}\n({startAgentFor, startable})`, {
    START: state,
    allowsAgent: (ticket, agent) => !ticket.map?.eligible || ticket.map.eligible.includes(agent),
    ownGlyph: ticket => ticket.map?.glyph,
  });
  const backend = {map: {agent: 'codex', eligible: ['codex']}}, frontend = {map: {agent: 'claude'}};
  assert.equal(api.startAgentFor(backend, 'claude'), 'codex');
  assert.equal(api.startAgentFor(frontend, 'codex'), 'claude');
  assert.equal(api.startAgentFor({map: {}}, 'claude'), 'claude');
  assert.equal(api.startable([backend, frontend], 'claude').length, 2);
  state.agentChanged = true;
  assert.equal(api.startAgentFor(backend, 'claude'), 'claude');
  assert.equal(api.startable([backend, frontend], 'claude').length, 1);
});

test('Fast keeps explicit Off distinct from project inheritance', async () => {
  const f = fixture('codex', {agents: [{agent: 'codex', settings: [
    {key: 'speed', id: 'fast-mode', category: 'model_config', type: 'boolean', chosen: 'true'},
  ]}]});
  let toggle;
  const settings = {open: true, addEventListener: (_, callback) => { toggle = callback; }};
  const changes = [];
  const box = f.api.runtimeControls({map: {fast: 'false'}}, 'codex',
    async fields => { changes.push(fields); return true; }, settings);
  toggle();
  await new Promise(setImmediate);
  const fast = box.children[0][2].children[1];
  assert.equal(fast.disabled, false);
  assert.equal(fast.children[0].children[0], 'Project setting: On');
  assert.equal(fast.children[1][1].attributes.selected, true);
  fast.value = 'false';
  await fast.attributes.onchange({currentTarget: fast});
  assert.equal(changes[0].fast, 'false');
  fast.value = '';
  await fast.attributes.onchange({currentTarget: fast});
  assert.equal(changes[1].fast, 'none');
});

/* The page's conversation lookup, figures/agents.js: a running user agent task session is a system conversation,
 * named by its work id, as the legacy conversation-system is; its body goes through the same figure lifecycle. */
const SYSTEM_TALK = 'Conversation with the system agent';
const agents = readFileSync(new URL('../page/app/figures/agents.js', import.meta.url), 'utf8');
const conversations = agents.slice(agents.indexOf('const SYSTEM_TALK'), agents.indexOf('function keptBodies()'))
  .replaceAll('export ', '');
function conversationFixture(sessions, tickets = []) {
  const elements = new Map([['el-2', {element: {id: 'el-2', role: 'DE'}}], ['el-1', {element: {id: 'el-1'}}]]);
  return runInNewContext(`${conversations}\n({conversationOf, systemTalk, figureTickets})`, {
    D: {sessions}, S: {tickets, elements},
    ticketOf: work => tickets.find(ticket => ticket.id === work),
    isSystemTalk: ticket => Boolean(ticket?.held && ticket.task === SYSTEM_TALK),
  });
}

test('a running user agent task is a system conversation on the page', () => {
  const sessions = [
    {work_id: 'conversation-system', state: 'ended', task_name: null},
    {work_id: 'task-36e454f8e6b54867bf43e5867642f997', state: 'running', task_name: 'user_agent'}];
  const api = conversationFixture(sessions);
  const found = api.conversationOf('task-36e454f8e6b54867bf43e5867642f997');
  assert.deepEqual({...found}, {id: 'task-36e454f8e6b54867bf43e5867642f997', node_kind: 'element', node_id: null,
    held: true, done: null, task: SYSTEM_TALK});
  assert.equal(api.systemTalk(), found);
  assert.equal(api.conversationOf('conversation-system'), null, 'the legacy conversation is not running');
  const drawn = api.figureTickets([{id: 'work-1'}]);
  assert.deepEqual(Array.from(drawn, ticket => ticket.id), ['work-1', 'task-36e454f8e6b54867bf43e5867642f997']);
  assert.equal(found.node_id, 'el-2', 'its home is the primary element');
});

test('a user agent task that is not running, and a worker session, are no conversation', () => {
  const api = conversationFixture([
    {work_id: 'task-old', state: 'ended', task_name: 'user_agent'},
    {work_id: 'work-9', state: 'running', task_name: 'worker'}], [{id: 'work-9', held: false}]);
  assert.equal(api.conversationOf('task-old'), null);
  assert.equal(api.conversationOf('task-unknown'), undefined, 'no ticket holds it');
  assert.deepEqual(api.conversationOf('work-9'), {id: 'work-9', held: false}, 'a worker keeps its ticket');
  assert.equal(api.systemTalk(), undefined);
  assert.deepEqual(Array.from(api.figureTickets([{id: 'work-9', held: false}]), ticket => ticket.id), ['work-9']);
});

test('the legacy system conversation still answers when it runs', () => {
  const api = conversationFixture([{work_id: 'conversation-system', state: 'running', task_name: null}]);
  assert.equal(api.conversationOf('conversation-system').id, 'conversation-system');
  assert.equal(api.systemTalk().task, SYSTEM_TALK);
});
