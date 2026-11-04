import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import test from 'node:test';

const source = readFileSync(new URL('../page/app/roundtable/stage.js', import.meta.url), 'utf8');
const setupControl = source.slice(source.indexOf('UI.tokenBudget ='), source.indexOf('UI.automate ='));
const liveControl = source.slice(source.indexOf('UI.liveTokenBudget ='), source.indexOf('UI.transcript ='));
const setupForm = source.slice(source.indexOf('UI.setup ='), source.indexOf('UI.root ='));
const start = source.slice(source.indexOf('async function startTable('), source.indexOf('/* ---------- the seats'));
const open = source.slice(source.indexOf('export async function openRoundtable('), source.indexOf('function showStage('))
  .replace('export ', '');
const chair = source.slice(source.indexOf('function budgetIs('), source.indexOf('/* One line of the transcript, whole'));
const status = source.slice(source.indexOf('function seated('), source.indexOf('function heard('));
const plain = value => JSON.parse(JSON.stringify(value));
function node(tag, attributes = {}, ...children) {
  return {tag, attributes, children: children.flat(Infinity), value: attributes.value ?? '', textContent: '',
    hidden: attributes.hidden ?? false, disabled: false, checked: false, invalid: 0, dataset: {},
    focus() {}, reportValidity() { this.invalid++; }};
}
const textOf = value => typeof value === 'string' ? value : (value?.children || []).map(textOf).join(' ');
function fixture(options = {}) {
  const writes = [], reads = [], messages = [];
  const BUDGET = {value: 0, dirty: false, setupDirty: false}, CHAIR = {writing: false};
  const S = {project: 'project', selected: null};
  const TABLE = {id: null, state: '', stage: '', ended: false, address: ''};
  const UI = Object.fromEntries(['question', 'replyLimit', 'tables', 'start', 'state', 'topic', 'judging', 'automate', 'where',
    'seatList', 'addSeat', 'saveParticipants', 'launchPermissions', 'hold', 'discussion', 'discussionComment',
    'sendDiscussion', 'endDiscussion', 'continueDiscussion', 'endTable', 'root'].map(key => [key, node('div')]));
  UI.question.value = 'Plan a project'; UI.replyLimit.value = '512'; UI.tables.value = '1';
  const api = runInNewContext(`${setupControl}\n${liveControl}\n${setupForm}\n${start}\n${open}\n${chair}\n${status}
    ({startTable, openRoundtable, renderChair, chairControl, budgetIs, seated})`, {
    UI, TABLE, S, BUDGET, CHAIR, G: {}, SEAT: {n: 1}, h: node,
    LAUNCH: {project: 'project'}, LINEUP: {project: 'project'}, OFFERED: new Map(),
    getJson: async path => { reads.push(path); return options.get ? options.get(path) : {seats: [], token_budget: 0}; },
    wrote: async (path, body) => {
      writes.push({path, body: plain(body)});
      return options.write ? options.write(path, body) : {table: 'opened', token_budget: body.token_budget};
    },
    toast: message => { messages.push(message); },
    chosenPermissions: () => ({}), seatsChosen: () => ['claude/opus', 'codex/sol'],
    rememberParticipants: () => {}, rememberedParticipants: (_, defaults) => defaults,
    fill: () => {}, addSeat: () => {}, drawSetupPermissions: () => {},
    showStage: () => {}, resetTable: () => { TABLE.id = null; }, leaveStage: () => {},
    readTable: async () => {}, seatAll: () => {}, ended: () => {},
  });
  const running = (state = 'running', stage = 'discussion') => {
    Object.assign(TABLE, {id: 'active-table', state, stage});
    api.renderChair();
  };
  const edit = value => { UI.liveTokenBudget.value = String(value); UI.liveTokenBudget.attributes.oninput(); };
  return {api, UI, TABLE, BUDGET, CHAIR, S, writes, reads, messages, running, edit};
}

test('setup explains independent phase counts, disabled default and all thresholds', () => {
  const f = fixture(), description = textOf(f.UI.setup);
  assert.equal(f.UI.tokenBudget.value, 0);
  assert.equal(f.UI.tokenBudget.attributes.min, 0);
  assert.equal(f.UI.tokenBudget.attributes.step, 1);
  assert.equal(f.UI.tokenBudget.attributes.required, true);
  assert.match(description, /Token budget per agent, per phase/);
  assert.match(description, /0 disables/);
  assert.match(description, /Each panel and collaboration phase starts a fresh count for each agent/);
  assert.match(description, /50% or 80% warns.*100% asks it to close.*120% forces.*without waiting for everyone to finish/);
  assert.match(description, /input, cached input and output.*updated after reports or turns/);
  assert.match(textOf(f.UI.budget), /Changing the limit keeps tokens already counted/);
});

test('setup reads the project limit and forwards an explicit budget or zero without enabling another limit', async () => {
  const f = fixture({get: async () => ({seats: [], token_budget: 12000})});
  await f.api.openRoundtable(true);
  assert.equal(f.reads[0], '/api/roundtable?project=project');
  assert.equal(f.UI.tokenBudget.value, 12000);
  await f.api.startTable();
  assert.equal(f.writes[0].path, '/api/roundtable-open');
  assert.equal(f.writes[0].body.token_budget, 12000);
  assert.equal(f.writes[0].body.chain, 1);
  f.UI.tokenBudget.value = '0';
  await f.api.startTable();
  assert.equal(f.writes[1].body.token_budget, 0);
});

test('setup rejects negative, fractional, empty and unsafe token budgets before opening', async () => {
  for (const value of ['-1', '1.25', '', 'NaN', 'Infinity', String(Number.MAX_SAFE_INTEGER + 1)]) {
    const f = fixture();
    f.UI.tokenBudget.value = value;
    await f.api.startTable();
    assert.equal(f.writes.length, 0, value);
    assert.equal(f.UI.tokenBudget.invalid, 1, value);
  }
});

test('an edit made while project defaults load is retained', async () => {
  let resolve;
  const f = fixture({get: () => new Promise(done => { resolve = done; })});
  const opening = f.api.openRoundtable(true);
  assert.equal(f.UI.start.disabled, true, 'Start waits for the project default');
  f.UI.tokenBudget.value = '4000';
  f.UI.tokenBudget.attributes.oninput();
  resolve({seats: [], token_budget: 12000});
  await opening;
  assert.equal(f.UI.tokenBudget.value, '4000');
  assert.equal(f.UI.start.disabled, false);
});

test('budget control remains available during running or held panel and collaboration phases', () => {
  const f = fixture();
  assert.equal(f.UI.budget.hidden, true);
  for (const state of ['running', 'held']) for (const phase of ['discussion', 'collaboration']) {
    f.running(state, phase);
    assert.equal(f.UI.budget.hidden, false, `${state}/${phase}`);
    assert.equal(f.UI.liveTokenBudget.disabled, false);
  }
  for (const state of ['opening', 'ending', 'ended', 'refused']) {
    f.running(state);
    assert.equal(f.UI.budget.hidden, true, state);
  }
});

test('live budget edits use the existing table control and can disable a limit', async () => {
  let resolve;
  const f = fixture({write: () => new Promise(done => { resolve = done; })});
  f.running('held', 'collaboration');
  f.edit(7000);
  const saving = f.api.chairControl('budget');
  assert.deepEqual(f.writes[0], {path: '/api/roundtable-control',
    body: {table: 'active-table', action: 'budget', token_budget: 7000}});
  assert.equal(f.UI.liveTokenBudget.disabled, true);
  assert.equal(f.UI.saveBudget.disabled, true);
  resolve({token_budget: 7000});
  await saving;
  assert.equal(f.BUDGET.value, 7000);
  assert.equal(f.BUDGET.dirty, false);
  assert.equal(f.UI.liveTokenBudget.disabled, false);
  f.edit(0);
  const disabling = f.api.chairControl('budget');
  resolve({token_budget: 0});
  await disabling;
  assert.equal(f.writes[1].body.token_budget, 0);
  assert.equal(f.UI.currentBudget.textContent, 'Current: disabled');
});

test('status refreshes update the current limit while keeping an unsaved draft', async () => {
  const f = fixture();
  f.running();
  f.api.seated({topic: 'A question', state: 'running', token_budget: 10000});
  assert.equal(f.UI.liveTokenBudget.value, 10000);
  f.edit(6000);
  f.api.seated({topic: 'A question', state: 'running', token_budget: 0});
  assert.equal(f.UI.liveTokenBudget.value, '6000');
  assert.equal(f.UI.currentBudget.textContent, 'Current: disabled');
  await f.api.chairControl('budget');
  assert.equal(f.BUDGET.dirty, false);
  f.api.seated({topic: 'A question', state: 'held', token_budget: 8000});
  assert.equal(f.UI.liveTokenBudget.value, 8000);
});

test('live validation and failed saves retain the draft and prevent invalid writes', async () => {
  const f = fixture({write: async () => null});
  f.running();
  for (const value of ['-1', '0.5', '', 'Infinity']) {
    f.edit(value);
    await f.api.chairControl('budget');
  }
  assert.equal(f.writes.length, 0);
  assert.equal(f.UI.liveTokenBudget.invalid, 4);
  f.edit(5000);
  await f.api.chairControl('budget');
  assert.equal(f.BUDGET.dirty, true);
  assert.equal(f.UI.liveTokenBudget.value, '5000');
  assert.equal(f.UI.saveBudget.disabled, false);
});

test('late budget responses do not change another table or project', async () => {
  for (const changed of ['table', 'project']) {
    let resolve;
    const f = fixture({write: () => new Promise(done => { resolve = done; })});
    f.running();
    f.edit(5000);
    const saving = f.api.chairControl('budget');
    if (changed === 'table') f.TABLE.id = 'other-table';
    else f.S.project = 'other-project';
    resolve({token_budget: 5000});
    await saving;
    assert.equal(f.BUDGET.value, 0, changed);
    assert.equal(f.BUDGET.dirty, true, changed);
  }
});
