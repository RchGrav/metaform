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
    {key: 'model', current: 'gpt-6', choices: [{value: 'gpt-6', name: 'GPT 6'}, {value: 'small', name: 'Small'}]},
    {key: 'thought_level', chosen: 'high', choices: [{value: 'medium', name: 'Medium'}, {value: 'high', name: 'High'}]},
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
