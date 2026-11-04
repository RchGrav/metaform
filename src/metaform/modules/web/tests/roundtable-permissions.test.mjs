import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import test from 'node:test';

const stage = readFileSync(new URL('../page/app/roundtable/stage.js', import.meta.url), 'utf8');
const dispatch = readFileSync(new URL('../page/app/agents/dispatch.js', import.meta.url), 'utf8');
const shared = readFileSync(new URL('../page/app/agents/permissions.js', import.meta.url), 'utf8')
  .replace(/^import .+;$/gm, '').replaceAll('export ', '');
const setup = stage.slice(stage.indexOf('function drawSetupPermissions('), stage.indexOf('async function modelPicker('));
const start = stage.slice(stage.indexOf('async function startTable('), stage.indexOf('/* ---------- the seats'));
const launch = dispatch.slice(dispatch.indexOf('function drawPermissions('), dispatch.indexOf('/* Start all offers'))
  .replaceAll('drawPermissions(', 'drawDispatchPermissions(');
const plain = value => JSON.parse(JSON.stringify(value));
const settle = () => new Promise(setImmediate);

/* A small DOM with real select defaults and selected options, so inherited settings and explicit choices differ. */
function node(tag, attributes = {}, ...children) {
  const el = {tag, attributes, children: [], value: attributes.value ?? '', hidden: attributes.hidden ?? false,
    textContent: '', parent: null,
    append(...added) {
      for (const child of added.flat(Infinity).filter(child => child != null && child !== false)) {
        this.children.push(child);
        if (typeof child === 'object') child.parent = this;
      }
    },
    remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); },
    querySelector(selector) {
      const matches = child => selector.startsWith('.')
        ? (child.attributes?.class || '').split(' ').includes(selector.slice(1)) : child.tag === selector;
      for (const child of this.children) {
        if (typeof child !== 'object') continue;
        if (matches(child)) return child;
        const nested = child.querySelector(selector);
        if (nested) return nested;
      }
      return null;
    }};
  el.append(children);
  if (tag === 'select') el.value = (el.children.find(child => child.attributes?.selected)
    || el.children[0])?.value ?? '';
  return el;
}
const fill = (box, ...children) => { box.children = []; box.append(children); };
const panel = () => node('div', {}, node('div', {class: 'controls'}), node('p', {class: 'hint'}),
  node('p', {class: 'risk', hidden: true}));
function fixture(readOptions = null) {
  const reads = [], writes = [], renders = [];
  const S = {project: 'project'}, LAUNCH = {project: null, agents: new Map()};
  const START = {own: {prompts: '', mode: ''}, permissionsFor: null};
  const UI = {seatList: node('ol'), launchPermissions: node('div'), question: {value: 'The question'},
    replyLimit: {value: 512}, tables: {value: 1}, start: {disabled: false}, state: {}, topic: {},
    judging: {checked: false}, automate: {checked: false}, setup: {hidden: false}};
  const dispatchPanel = panel();
  const api = runInNewContext(`${shared}\n${setup}\n${start}\n${launch}\n({drawSetupPermissions, chosenPermissions,
    startTable, drawDispatchPermissions, launchOwn, renderShared: drawPermissions})`, {
    S, UI, LAUNCH, START, TABLE: {address: ''}, h: node, fill, agentName: agent => agent,
    $: () => dispatchPanel,
    renderPermissions: (...args) => { renders.push(args); return api.renderShared(...args); },
    read: async (name, params) => {
      reads.push({name, ...params});
      if (readOptions) return readOptions(name, params);
      return name === 'dispatch-prompts' ? {value: 'approve-reads', choices: ['approve-all', 'approve-reads', 'ask_all']}
        : {agents: [{settings: [{key: 'mode', chosen: 'safe', choices: [
          {value: 'safe', name: 'Safe'}, {value: `${params.agent}-mode`, name: 'Agent mode'},
          {value: 'bypassPermissions', name: 'Bypass', description: 'Agent acts freely'}]}]}]};
    },
    wrote: async (path, body) => { writes.push({path, body: plain(body)}); return {table: 'table-id'}; },
    seatsChosen: () => UI.seatList.children.map(row => row.seat),
    rememberParticipants: () => {}, readTable: async () => {},
    toast: message => { throw new Error(message); },
  });
  const seats = (...listed) => {
    fill(UI.seatList, listed.map(seat => {
      const who = /^(?:acp:)?(claude|codex|antigravity)\//.exec(seat)?.[1] || '';
      const row = node('li', {}, node('select', {}, node('option', {value: who})));
      row.seat = seat;
      return row;
    }));
    api.drawSetupPermissions();
  };
  const choose = (agent, key, value) => {
    const pick = LAUNCH.agents.get(agent).panel.querySelector(`.${key}`);
    assert.ok(pick, `${agent} offers ${key}`);
    pick.value = value;
    pick.attributes.onchange();
  };
  return {api, S, UI, LAUNCH, START, reads, writes, renders, dispatchPanel, seats, choose};
}

test('setup reuses standard controls once per ACP type and starts with inherited permissions', async () => {
  const f = fixture();
  f.seats('claude/opus', 'claude/haiku', 'codex/gpt-6', 'openrouter/model');
  await settle();
  assert.equal(f.UI.launchPermissions.children.length, 2);
  assert.deepEqual(f.reads.filter(read => read.name === 'dispatch-options').map(read => read.agent), ['claude', 'codex']);
  for (const agent of ['claude', 'codex']) {
    const box = f.LAUNCH.agents.get(agent).panel;
    assert.equal(box.querySelector('.prompts').children[0].children[0],
      'Project setting: Approve reads and searches; ask for the rest');
    assert.equal(box.querySelector('.mode').children[0].children[0], 'Project setting: Safe');
    assert.equal(box.querySelector('.prompts').value, '');
    assert.equal(box.querySelector('.mode').value, '');
  }
  await f.api.startTable();
  assert.equal(f.writes[0].path, '/api/roundtable-open');
  assert.equal(f.writes[0].body.chain, 1, 'one table still enters the collaboration session');
  assert.equal(f.writes[0].body.reply_limit, 512);
  assert.equal('permissions' in f.writes[0].body, false, 'project settings are inherited');
});

test('explicit policy and native mode stay with their agent and reach the launch request', async () => {
  const f = fixture();
  f.seats('claude/opus', 'codex/gpt-6');
  await settle();
  f.choose('claude', 'prompts', 'approve-reads');
  f.choose('claude', 'mode', 'claude-mode');
  f.choose('codex', 'mode', 'codex-mode');
  f.UI.tables.value = 3;
  await f.api.startTable();
  assert.deepEqual(f.writes[0].body.permissions,
    {claude: {prompts: 'approve-reads', mode: 'claude-mode'}, codex: {mode: 'codex-mode'}});
  assert.equal(f.writes[0].body.chain, 3);
  f.choose('claude', 'prompts', '');
  f.choose('claude', 'mode', '');
  assert.deepEqual(plain(f.api.chosenPermissions(['claude/opus', 'codex/gpt-6'])), {codex: {mode: 'codex-mode'}});
  assert.deepEqual(plain(f.api.chosenPermissions(['claude/opus'])), {});
});

test('adding duplicate seats retains choices and removal or project change discards them', async () => {
  const f = fixture();
  f.seats('claude/opus', 'codex/gpt-6');
  await settle();
  f.choose('claude', 'mode', 'claude-mode');
  const retained = f.LAUNCH.agents.get('claude').panel, reads = f.reads.length;
  f.seats('claude/opus', 'claude/haiku', 'codex/gpt-6');
  assert.equal(f.LAUNCH.agents.get('claude').panel, retained);
  assert.equal(retained.querySelector('.mode').value, 'claude-mode');
  assert.equal(f.reads.length, reads);
  f.seats('claude/haiku', 'codex/gpt-6');
  assert.equal(f.LAUNCH.agents.get('claude').own.mode, 'claude-mode');
  f.seats('codex/gpt-6');
  assert.equal(f.LAUNCH.agents.has('claude'), false);
  f.seats('claude/opus', 'codex/gpt-6');
  await settle();
  assert.equal(f.LAUNCH.agents.get('claude').own.mode, '');
  f.choose('codex', 'mode', 'codex-mode');
  f.S.project = 'another-project';
  assert.deepEqual(plain(f.api.chosenPermissions(['codex/gpt-6'])), {});
  f.api.drawSetupPermissions();
  await settle();
  assert.equal(f.LAUNCH.agents.get('codex').own.mode, '');
});

test('OpenRouter seats render no ACP permission controls', async () => {
  const f = fixture();
  f.seats('openrouter/model');
  await settle();
  assert.equal(f.UI.launchPermissions.children.length, 0);
  assert.equal(f.reads.length, 0);
  assert.deepEqual(plain(f.api.chosenPermissions(['openrouter/model'])), {});
});

test('dispatch keeps policy and resets native mode when its selected agent changes', async () => {
  const f = fixture();
  f.api.drawDispatchPermissions('claude');
  await settle();
  const prompts = f.dispatchPanel.querySelector('.prompts'), mode = f.dispatchPanel.querySelector('.mode');
  prompts.value = 'ask_all'; prompts.attributes.onchange();
  mode.value = 'claude-mode'; mode.attributes.onchange();
  assert.deepEqual(plain(f.api.launchOwn('claude')), {prompts: 'ask_all', mode: 'claude-mode'});
  f.api.drawDispatchPermissions('codex');
  await settle();
  assert.deepEqual(plain(f.api.launchOwn('codex')), {prompts: 'ask_all'});
  assert.equal(f.dispatchPanel.querySelector('.mode').value, '');
  assert.equal(f.renders.length, 2, 'dispatch invokes the shared renderer');
});

test('late native option reads cannot restore removed controls', async () => {
  let resolve;
  const f = fixture(name => name === 'dispatch-prompts' ? {value: 'approve-reads'}
    : new Promise(done => { resolve = done; }));
  f.seats('claude/opus');
  await settle();
  const removed = f.LAUNCH.agents.get('claude').panel;
  f.seats('openrouter/model');
  resolve({agents: [{settings: []}]});
  await settle();
  assert.equal(removed.querySelector('.controls').children.length, 0);
  assert.equal(f.UI.launchPermissions.children.length, 0);
});
