import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import test from 'node:test';

const source = readFileSync(new URL('../page/app/roundtable/stage.js', import.meta.url), 'utf8');
const setupControl = source.slice(source.indexOf('UI.tokenBudget ='), source.indexOf('UI.automate ='));
const endSessionControl = source.slice(source.indexOf('UI.endSession ='), source.indexOf('UI.continueDiscussion ='));
const liveControl = source.slice(source.indexOf('UI.liveTokenBudget ='), source.indexOf('UI.transcript ='));
const setupForm = source.slice(source.indexOf('UI.setup ='), source.indexOf('UI.root ='));
const start = source.slice(source.indexOf('async function startTable('), source.indexOf('/* ---------- the seats'));
const open = source.slice(source.indexOf('export async function openRoundtable('), source.indexOf('function showStage('))
  .replace('export ', '');
const phase = source.slice(source.indexOf('function tokenBasisLabel('), source.indexOf('/* Status refreshes report'));
const chair = source.slice(source.indexOf('function budgetIs('), source.indexOf('/* One line of the transcript, whole'));
const status = source.slice(source.indexOf('function seated('), source.indexOf('function heard('));
const heard = source.slice(source.indexOf('function heard('), source.indexOf('const seatOf ='));
const plain = value => JSON.parse(JSON.stringify(value));
function node(tag, attributes = {}, ...children) {
  return {tag, attributes, children: children.flat(Infinity), value: attributes.value ?? '', textContent: '',
    hidden: attributes.hidden ?? false, disabled: false, checked: false, invalid: 0, dataset: {},
    focus() {}, reportValidity() { this.invalid++; }};
}
const textOf = value => typeof value === 'string' ? value
  : value?.textContent || (value?.children || []).map(textOf).join(' ');
function fixture(options = {}) {
  const writes = [], reads = [], messages = [];
  const BUDGET = {value: 0, dirty: false, setupDirty: false}, CHAIR = {writing: false};
  const S = {project: 'project', selected: null};
  const TABLE = {id: null, state: '', stage: '', ended: false, address: ''};
  const UI = Object.fromEntries(['question', 'replyLimit', 'tables', 'start', 'state', 'topic', 'judging', 'automate', 'where',
    'seatList', 'addSeat', 'saveParticipants', 'launchPermissions', 'hold', 'discussion', 'discussionComment',
    'sendDiscussion', 'endDiscussion', 'continueDiscussion', 'endTable', 'root'].map(key => [key, node('div')]));
  UI.question.value = 'Plan a project'; UI.replyLimit.value = '512'; UI.tables.value = '1';
  const api = runInNewContext(`${setupControl}\n${endSessionControl}\n${liveControl}\n${setupForm}\n${start}\n${open}\n${phase}\n${chair}\n${status}\n${heard}
    ({startTable, openRoundtable, renderChair, chairControl, budgetIs, seated, phaseBudgetIs, watchPhaseBudget, topicSelectionIs, heard})`, {
    UI, TABLE, S, BUDGET, CHAIR, PHASE_BUDGET: {project: null, table: null, stage: null}, G: {}, SEAT: {n: 1}, h: node,
    LAUNCH: {project: 'project'}, LINEUP: {project: 'project'}, OFFERED: new Map(),
    getJson: async path => { reads.push(path); return options.get ? options.get(path) : {seats: [], token_budget: 0}; },
    wrote: async (path, body) => {
      writes.push({path, body: plain(body)});
      return options.write ? options.write(path, body) : {table: 'opened', token_budget: body.token_budget};
    },
    toast: message => { messages.push(message); },
    chosenPermissions: () => ({}), seatsChosen: () => ['claude/opus', 'codex/sol'],
    rememberParticipants: () => {}, rememberedParticipants: (_, defaults) => defaults,
    fill: (box, ...children) => { box.children = children.flat(Infinity).filter(Boolean); }, addSeat: () => {}, drawSetupPermissions: () => {},
    showStage: () => {}, resetTable: () => { TABLE.id = null; }, leaveStage: () => {},
    readTable: async () => {}, seatAll: () => {}, ended: () => {}, nextUp: () => {},
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
  assert.match(description, /Token budget per agent, per discussion/);
  assert.match(description, /0 disables/);
  assert.match(description, /Each discussion starts a fresh count for each agent/);
  assert.match(description, /50% or 80% warns.*100% asks it to close.*120% forces.*without waiting for everyone to finish/);
  assert.match(description, /Uncached input \+ output; cached reads excluded/);
  assert.match(description, /Cache writes count as input/);
  assert.match(description, /Totals update after reports or turns/);
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

test('budget control remains available during running or held discussion and private topic selection', () => {
  const f = fixture();
  assert.equal(f.UI.budget.hidden, true);
  for (const state of ['running', 'held']) for (const phase of ['discussion', 'topic_selection']) {
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
  f.running('held', 'topic_selection');
  f.edit(7000);
  const saving = f.api.chairControl('budget');
  assert.equal('token_basis' in f.writes[0].body, false, 'Saving a limit must not convert the counting basis.');
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

const phaseSnapshot = (phase = 'panel', topic = 3, tokens = 0) => ({limit: 500000, phase, topic,
  participants: [
    {position: 0, name: 'Alpha', tokens, reported: !!tokens, unreported: 0, closing: false},
    {position: 1, name: 'Beta', tokens: 0, reported: false, unreported: 0, closing: false}],
  notices: [], closing: false, forced: false});

test('current phase keeps valid advancement available before delayed transcript stages arrive', async () => {
  for (const stage of ['discussion', 'topic_selection', 'scoring', 'farewell']) {
    const f = fixture();
    f.running('held', '');
    f.api.seated({topic: 'Keep this session', state: 'held', stage});
    assert.equal(f.TABLE.stage, stage);
    assert.equal(f.UI.endDiscussion.hidden, false);
    assert.equal(f.UI.endDiscussion.disabled, stage !== 'discussion');
    assert.equal(f.UI.endSession.hidden, false);
    assert.equal(f.UI.endSession.disabled, false);
    assert.equal(f.UI.hold.hidden, false);
    assert.equal(f.UI.hold.textContent, 'Continue');
    f.api.heard({kind: 'stage', stage: 'discussion'});
    assert.equal(f.TABLE.stage, stage, 'Historical playback cannot change the live phase.');
    assert.equal(f.UI.endDiscussion.hidden, false);
    assert.equal(f.UI.endDiscussion.disabled, stage !== 'discussion');
    await f.api.chairControl('advance');
    assert.equal(f.writes.length, stage === 'discussion' ? 1 : 0);
    if (stage === 'discussion') assert.equal(f.writes[0].body.action, 'advance');
    else assert.match(f.UI.endDiscussion.title, /[Uu]se End session/);
  }
});

test('phase updates refresh discussion controls without new transcript events or a status snapshot', () => {
  const f = fixture();
  f.running('held', 'discussion');
  f.api.phaseBudgetIs({phase: null, stage: 'topic_selection'});
  assert.equal(f.UI.endDiscussion.hidden, false);
  assert.equal(f.UI.endDiscussion.disabled, true);
  f.api.heard({kind: 'stage', stage: 'discussion'});
  assert.equal(f.TABLE.stage, 'topic_selection');
  assert.equal(f.UI.endDiscussion.hidden, false);
  assert.equal(f.UI.endDiscussion.disabled, true);
  f.api.phaseBudgetIs({...phaseSnapshot('panel', 5), stage: 'discussion'});
  assert.equal(f.TABLE.stage, 'discussion');
  assert.equal(f.UI.endDiscussion.hidden, false);
  assert.equal(f.UI.endDiscussion.disabled, false);
  f.api.heard({kind: 'stage', stage: 'topic_selection'});
  assert.equal(f.TABLE.stage, 'discussion');
  assert.equal(f.UI.endDiscussion.hidden, false);
});

test('each new discussion displays authoritative zero counters for every agent', () => {
  const f = fixture();
  f.api.phaseBudgetIs(phaseSnapshot('panel', 3, 479477));
  assert.equal(f.UI.phaseBudgetLabel.textContent, 'Panel 3');
  assert.match(textOf(f.UI.phaseBudgetRows), /Alpha 479,477 \/ 500,000 tokens \(96%\)/);
  assert.match(textOf(f.UI.phaseBudgetRows), /Beta 0 \/ 500,000 tokens \(0%\)/);
  for (const [phase, topic, label] of [['panel', 4, 'Panel 4'], ['panel', 5, 'Panel 5']]) {
    f.api.phaseBudgetIs(phaseSnapshot(phase, topic));
    assert.equal(f.UI.phaseBudgetLabel.textContent, label);
    assert.equal(f.UI.phaseBudgetRows.children.length, 2);
    assert.doesNotMatch(textOf(f.UI.phaseBudgetRows), /479,477/);
    for (const row of f.UI.phaseBudgetRows.children) {
      assert.match(textOf(row), /0 \/ 500,000 tokens \(0%\)/);
      assert.equal(row.children.find(child => child.tag === 'progress').attributes.value, 0);
    }
  }
  assert.match(textOf(f.UI.phaseBudget), /Input \+ cached input \+ output/);
});

test('phase progress preserves the draft limit, chair hold and discussion comment', () => {
  const f = fixture();
  f.running('held');
  f.edit(700000);
  f.UI.discussionComment.value = 'Keep the current phase held.';
  f.api.phaseBudgetIs(phaseSnapshot('panel', 3, 479477));
  assert.equal(f.UI.liveTokenBudget.value, '700000');
  assert.equal(f.BUDGET.dirty, true);
  assert.equal(f.TABLE.state, 'held');
  assert.equal(f.UI.discussionComment.value, 'Keep the current phase held.');
  assert.equal(f.writes.length, 0);
});

test('missing reports and phase closing state stay explicit alongside the usage totals', () => {
  const f = fixture(), snapshot = phaseSnapshot();
  snapshot.participants[0].unreported = 1;
  snapshot.participants[0].closing = true;
  snapshot.closing = true;
  f.api.phaseBudgetIs(snapshot);
  assert.match(textOf(f.UI.phaseBudgetRows), /Usage missing for 1 reply; the reported total is incomplete/);
  assert.match(textOf(f.UI.phaseBudgetRows), /Closing statement requested/);
  assert.equal(f.UI.phaseBudgetState.textContent, 'Closing statements requested.');
  snapshot.forced = true;
  f.api.phaseBudgetIs(snapshot);
  assert.equal(f.UI.phaseBudgetState.textContent, 'Hard limit reached.');
  snapshot.limit = 0;
  f.api.phaseBudgetIs(snapshot);
  assert.match(textOf(f.UI.phaseBudgetRows), /0 tokens · limit disabled/);
  f.api.phaseBudgetIs({phase: null});
  assert.equal(f.UI.phaseBudget.hidden, true);
  assert.equal(f.UI.phaseBudgetRows.children.length, 0);
});

function phaseReader(f, get) {
  const TABLE = {id: 'active-table', seq: 17, busy: false, again: false}, S = {project: 'project'};
  const code = source.slice(source.indexOf('async function readTable('), source.indexOf('function tell('));
  const read = runInNewContext(`${code}\nreadTable`, {TABLE, S, UI: f.UI, SEAT: {n: 1}, TOLD: {list: []},
    getJson: get, phaseBudgetIs: f.api.phaseBudgetIs, watchPhaseBudget: f.api.watchPhaseBudget,
    topicSelectionIs: f.api.topicSelectionIs, seated: () => {}, tell: () => {}, readNotes: () => {},
    toast: message => { throw new Error(message); },
  });
  return {read, TABLE, S};
}

test('private topic selection shows only aggregate progress independently of transcript delivery', async () => {
  const f = fixture();
  f.running('held', 'topic_selection');
  let snapshot = {requested: 4, completed: 2, state: 'collecting',
    author: 'Private proposer', proposals: ['Private proposed topic']};
  const reader = phaseReader(f, async () => ({events: [], latest: 17,
    phase_budget: {phase: null, stage: 'topic_selection'}, topic_selection: snapshot}));
  await reader.read();
  assert.equal(f.UI.topicSelectionStatus.hidden, false);
  assert.match(f.UI.topicSelectionStatus.textContent, /Choosing the next topic privately.*2 of 4 proposals received/);
  assert.doesNotMatch(f.UI.topicSelectionStatus.textContent, /Private proposer|Private proposed topic/);
  assert.equal(f.UI.endDiscussion.disabled, true);
  assert.equal(f.UI.endSession.hidden, false);
  await f.api.chairControl('advance');
  assert.equal(f.writes.length, 0, 'End discussion cannot skip or restart private topic selection.');
  snapshot = {...snapshot, completed: 4, state: 'judging'};
  await reader.read();
  assert.match(f.UI.topicSelectionStatus.textContent, /Comparing the private proposals.*4 of 4/);
  assert.equal(reader.TABLE.seq, 17);
  assert.equal(f.UI.phaseBudget.hidden, true, 'Selection does not invent another token-budget phase.');
  f.api.phaseBudgetIs({...phaseSnapshot('panel', 4), stage: 'discussion'});
  assert.equal(f.UI.topicSelectionStatus.hidden, true);
  assert.equal(f.UI.topicSelectionStatus.textContent, '');
  assert.equal(f.UI.endDiscussion.disabled, false);
  assert.equal(f.writes.length, 0);
});

test('a changed table clears private topic-selection progress without sending controls', () => {
  const f = fixture();
  f.running('running', 'topic_selection');
  f.api.topicSelectionIs({requested: 4, completed: 3, state: 'collecting'});
  f.api.watchPhaseBudget('other-project', 'other-table');
  assert.equal(f.UI.topicSelectionStatus.hidden, true);
  assert.equal(f.UI.topicSelectionStatus.textContent, '');
  assert.equal(f.writes.length, 0);
});

test('phase usage updates independently of the transcript cursor and clears when the selected table changes', async () => {
  const f = fixture();
  let snapshot = phaseSnapshot('panel', 3, 0);
  const reader = phaseReader(f, async () => ({events: [], latest: 17, phase_budget: snapshot}));
  await reader.read();
  assert.match(textOf(f.UI.phaseBudgetRows), /0 \/ 500,000/);
  snapshot = phaseSnapshot('panel', 3, 479477);
  await reader.read();
  assert.equal(reader.TABLE.seq, 17);
  assert.match(textOf(f.UI.phaseBudgetRows), /479,477/);
  snapshot = phaseSnapshot('panel', 4, 0);
  await reader.read();
  assert.equal(reader.TABLE.seq, 17);
  assert.equal(f.UI.phaseBudgetLabel.textContent, 'Panel 4');
  assert.doesNotMatch(textOf(f.UI.phaseBudgetRows), /479,477/);
  reader.TABLE.id = 'another-table';
  f.api.watchPhaseBudget(reader.S.project, reader.TABLE.id);
  assert.equal(f.UI.phaseBudget.hidden, true);
});

test('a stale project response cannot replace the selected table phase counters', async () => {
  const f = fixture();
  let resolve;
  const reader = phaseReader(f, path => path.includes('project=project&table=active-table&')
    ? new Promise(done => { resolve = done; })
    : {events: [], latest: 17, phase_budget: phaseSnapshot('panel', 4, 0)});
  const first = reader.read();
  reader.S.project = 'other-project'; reader.TABLE.id = 'other-table';
  await reader.read();
  resolve({events: [], latest: 17, phase_budget: phaseSnapshot('panel', 3, 479477)});
  await first;
  assert.equal(f.UI.phaseBudgetLabel.textContent, 'Panel 4');
  assert.doesNotMatch(textOf(f.UI.phaseBudgetRows), /479,477/);
});

test('a whole response uses the phase counters bundled with its newer table status', async () => {
  const f = fixture();
  f.running('held', 'topic_selection');
  const reader = phaseReader(f, async () => ({events: [], latest: 17,
    phase_budget: phaseSnapshot('panel', 3, 479477),
    status: {state: 'held', phase_budget: phaseSnapshot('panel', 4, 0)}}));
  await reader.read(true);
  assert.equal(f.UI.phaseBudgetLabel.textContent, 'Panel 4');
  assert.doesNotMatch(textOf(f.UI.phaseBudgetRows), /479,477/);
  assert.match(textOf(f.UI.phaseBudgetRows), /0 \/ 500,000 tokens \(0%\)/);
  assert.equal(f.TABLE.state, 'held');
  assert.equal(f.writes.length, 0);
});

test('explicit null phase snapshots clear stale usage with status taking precedence', async () => {
  const f = fixture();
  f.running('held');
  f.api.phaseBudgetIs(phaseSnapshot('panel', 3, 479477));
  let response = {events: [], latest: 17, phase_budget: phaseSnapshot('panel', 3, 479477),
    status: {phase_budget: null}};
  const reader = phaseReader(f, async () => response);
  await reader.read(true);
  assert.equal(f.UI.phaseBudget.hidden, true);
  assert.equal(f.UI.phaseBudgetRows.children.length, 0);
  f.api.phaseBudgetIs(phaseSnapshot('panel', 3, 479477));
  response = {events: [], latest: 17, phase_budget: null};
  await reader.read();
  assert.equal(f.UI.phaseBudget.hidden, true);
  assert.equal(f.UI.phaseBudgetRows.children.length, 0);
  assert.equal(f.TABLE.state, 'held');
  assert.equal(f.writes.length, 0);
});

test('progress names the server counting basis and keeps a legacy all-tokens snapshot unchanged', () => {
  const f = fixture();
  f.running('held');
  f.edit(700000);
  f.UI.discussionComment.value = 'Keep the current phase held.';
  for (const [basis, label] of [
    ['all', 'Input + cached input + output'],
    ['uncached', 'Uncached input + output; cached reads excluded'],
    ['output', 'Generated output only'],
    [undefined, 'Input + cached input + output'],
  ]) {
    f.api.phaseBudgetIs({...phaseSnapshot('panel', 3, 479477), basis});
    assert.equal(f.UI.phaseBudgetBasis.textContent, label);
    assert.match(textOf(f.UI.phaseBudgetRows), /479,477 \/ 500,000 tokens \(96%\)/);
    assert.equal(f.UI.liveTokenBudget.value, '700000');
    assert.equal(f.UI.discussionComment.value, 'Keep the current phase held.');
    assert.equal(f.TABLE.state, 'held');
  }
  assert.equal(f.writes.length, 0);
});

test('setup help uses the project counting basis without adding a hidden conversion to limit saves', async () => {
  for (const [token_basis, label] of [
    ['uncached', 'Uncached input + output; cached reads excluded'],
    ['output', 'Generated output only'],
    ['all', 'Input + cached input + output'],
  ]) {
    const f = fixture({get: async () => ({seats: [], token_budget: 12000, token_basis})});
    await f.api.openRoundtable(true);
    assert.equal(f.UI.setupBudgetBasis.textContent, label);
    assert.equal(f.UI.setupBudgetCache.textContent, token_basis === 'uncached' ? ' Cache writes count as input.' : '');
    await f.api.startTable();
    assert.equal('token_basis' in f.writes[0].body, false, 'The new table follows the backend project default.');
  }
});

test('End session remains separate from End discussion during running or held private topic selection', async () => {
  const f = fixture({write: async () => ({table: 'active-table', state: 'ending'})});
  for (const state of ['running', 'held']) for (const stage of ['discussion', 'topic_selection', 'scoring', 'farewell']) {
    f.running(state, stage);
    assert.equal(textOf(f.UI.endSession), 'End session');
    assert.equal(f.UI.endSession.hidden, false);
    assert.equal(f.UI.endDiscussion.hidden, false);
    assert.equal(f.UI.endDiscussion.disabled, stage !== 'discussion');
    assert.match(f.UI.endSession.attributes.title, /entire session.*documents and current record/);
    await f.UI.endSession.attributes.onclick();
    assert.deepEqual(f.writes.at(-1), {path: '/api/roundtable-control', body: {table: 'active-table', action: 'end'}});
    assert.equal(f.TABLE.id, 'active-table');
    assert.equal(f.TABLE.state, 'ending');
    assert.equal(f.TABLE.stage, stage);
  }
});

test('End session can retry ending and stays hidden after completion without opening another setup', async () => {
  const f = fixture({write: async () => ({table: 'active-table', state: 'ended'})});
  f.running('ending', 'topic_selection');
  f.UI.setup.hidden = true;
  assert.equal(f.UI.endSession.hidden, false);
  await f.UI.endSession.attributes.onclick();
  assert.equal(f.writes[0].body.action, 'end');
  assert.equal(f.TABLE.id, 'active-table');
  assert.equal(f.TABLE.state, 'ended');
  assert.equal(f.UI.endSession.hidden, true);
  assert.equal(f.UI.setup.hidden, true, 'The handler keeps the existing record and does not open setup.');
  for (const state of ['opening', 'refused', 'ended']) {
    f.running(state);
    assert.equal(f.UI.endSession.hidden, true, state);
  }
});
