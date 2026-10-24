import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import test from 'node:test';

const read = path => readFileSync(new URL(`../page/app/${path}`, import.meta.url), 'utf8');
const tools = read('session/tools.js'), intake = read('intake/intake.js'), stream = read('live/stream.js');
const classifier = tools.slice(tools.indexOf('export const isIntake'), tools.indexOf('/* Whether a work id is a helper'))
  .replaceAll('export ', '');
const state = intake.slice(intake.indexOf('export const INTAKE'), intake.indexOf('/* The signals an intake'))
  .replaceAll('export ', '');
const controls = intake.slice(intake.indexOf('export function openIntakeChat'),
  intake.indexOf('/* The window an intake starts')).replaceAll('export ', '');

function local(sessions = []) {
  const D = {sessions}, chats = [], writes = [], stopped = [];
  const api = runInNewContext(`${classifier}\n${state}\n${controls}\n`
    + '({isIntake, underWay, INTAKE, readIntake, intakeRunning, openIntakeChat, stopIntake})', {
    D, WAITS_ON_PERSON: ['permission-waiting', 'question-waiting'], drawIntake: () => {},
    recordingNow: async () => {}, toast: () => {}, DOCK: {}, STANDBY: 'waiting', agentName: name => name,
    openHelpdesk: (...args) => chats.push(args), confirmAct: async () => true,
    wrote: async (path, body) => { writes.push({path, body}); return {stopped: true}; },
    rememberStop: session => stopped.push(session), renderAgents: async () => {},
  });
  return {api, D, chats, writes, stopped};
}

function elsewhere(sessions) {
  const S = {project: null}, reads = [], navigation = [], notices = [];
  const area = stream.slice(stream.indexOf('const ELSEWHERE'), stream.indexOf('const PROJECTS'));
  const lines = stream.slice(stream.indexOf('function threadOnly(payload)'),
    stream.indexOf('/* Whether a change names a table passing the test'));
  const api = runInNewContext(`${classifier}\n${lines}\n${area}\n({intakeElsewhere})`, {
    D: {sessions: []}, S, linesOnly: () => false, ticketsOnly: () => false, opTable: name => name === 'ops',
    getJson: async url => { reads.push(url); return {sessions}; },
    goToProject: async (project, message) => { navigation.push({project, message}); S.project = project; },
    toast: message => notices.push(message),
  });
  return {api, S, reads, navigation, notices};
}

test('task metadata identifies intake and generic assignments stay distinct from historical intakes', () => {
  const f = local([{work_id: 'task-intake', task_name: 'intake'}, {work_id: 'task-worker', task_name: 'worker'}]);
  assert.equal(f.api.isIntake('task-intake'), true);
  assert.equal(f.api.isIntake('task-worker'), false);
  assert.equal(f.api.isIntake('task-unknown'), false);
  assert.equal(f.api.isIntake('intake-historical'), true);
  assert.equal(f.api.isIntake('intake-historical', {task_name: 'worker'}), false);
  assert.equal(f.api.underWay({work_id: 'task-starting', task_name: 'intake', state: 'starting'}), true);
  assert.equal(f.api.underWay({work_id: 'task-ended', task_name: 'intake', state: 'ended'}), false);
});

test('the intake bar state and chat/stop controls retain the named task session identity', async () => {
  const current = {work_id: 'task-abcd', task_name: 'intake', state: 'running', session_id: 'session', agent: 'codex'};
  const f = local([current, {work_id: 'task-newer', task_name: 'worker', state: 'running'}]);
  await f.api.readIntake([{work_id: current.work_id, signal: 'permission-waiting'},
    {work_id: 'task-newer', signal: 'question-waiting'}]);
  assert.equal(f.api.intakeRunning(), true);
  assert.equal(f.api.INTAKE.work, current.work_id);
  assert.equal(f.api.INTAKE.waiting, 1);
  f.api.openIntakeChat();
  assert.equal(f.chats[0][0], current.work_id);
  assert.equal(f.chats[0][3], current.session_id);
  await f.api.stopIntake();
  assert.equal(f.writes[0].path, '/api/dispatch-stop');
  assert.equal(f.writes[0].body.work_id, current.work_id);
  assert.equal(f.writes[0].body.session, current.session_id);
  assert.deepEqual(f.stopped, ['session']);
});

test('a launch refusal opens the exact running intake for both task and historical work ids', () => {
  const area = intake.slice(intake.indexOf('function showIntakeRefusal('),
    intake.indexOf('/* The intake left being recorded is taken over'));
  const box = {}, opened = [];
  const api = runInNewContext(`${area}\n({showIntakeRefusal})`, {
    $: () => box, fill: (target, ...children) => { target.children = children; },
    h: (tag, attributes, ...children) => ({tag, attributes, children}),
    openRunning: work => opened.push(work), takeOver: () => {},
  });
  const buttons = node => Array.isArray(node) ? node.flatMap(buttons)
    : node && typeof node === 'object' ? [...(node.tag === 'button' ? [node] : []), ...buttons(node.children)] : [];
  for (const work of ['task-ab12', 'intake-cd34']) {
    api.showIntakeRefusal({error: 'Already running.', next: `metaform dispatch stop ${work}`});
    const button = buttons(box.children).find(one => one.children.includes('Open its chat'));
    assert.ok(button);
    button.attributes.onclick();
    assert.equal(opened.at(-1), work);
    assert.equal(box.hidden, false);
  }
});

test('a generic task event receives one restricted identity read and cannot navigate the page', async () => {
  const f = elsewhere([{work_id: 'task-worker', task_name: 'worker', state: 'starting'}]);
  await f.api.intakeElsewhere({project: 'other', tables: ['tasks.assignments'], kinds: ['task'],
    work_ids: ['task-worker']});
  assert.equal(f.navigation.length, 0);
  assert.equal(f.notices.length, 0);
  assert.equal(f.reads.length, 1);
  const query = new URL(f.reads[0], 'http://metaform.local').searchParams;
  assert.equal(query.get('project'), 'other');
  assert.equal(query.get('thread'), 'false');
  assert.deepEqual(JSON.parse(query.get('ids')), ['task-worker']);
});

test('a batched task launch follows only the confirmed intake once, even beside a newer worker', async () => {
  const f = elsewhere([{work_id: 'task-intake', task_name: 'intake', state: 'starting'},
    {work_id: 'task-worker', task_name: 'worker', state: 'running'}]);
  const event = {project: 'other', tables: ['dispatch.raised'], kinds: [],
    work_ids: ['task-worker', 'task-intake', 'task-worker']};
  await f.api.intakeElsewhere(event);
  assert.equal(f.navigation.length, 1);
  assert.equal(f.navigation[0].project, 'other');
  assert.equal(f.reads.length, 1);
  assert.deepEqual(JSON.parse(new URL(f.reads[0], 'http://metaform.local').searchParams.get('ids')),
    ['task-worker', 'task-intake']);
  f.S.project = null;
  await f.api.intakeElsewhere({...event, work_ids: ['task-intake']});
  assert.equal(f.reads.length, 1);
  assert.equal(f.navigation.length, 1);
});

test('unrelated ticket and task thread bursts make no cross-project reads', async () => {
  const f = elsewhere([]);
  for (let index = 0; index < 50; index++) {
    await f.api.intakeElsewhere({project: 'other', tables: ['work'], kinds: ['ticket'], work_ids: ['ticket-id']});
    await f.api.intakeElsewhere({project: 'other', tables: 'dispatch', kinds: ['line'], work_ids: ['task-worker']});
  }
  assert.equal(f.reads.length, 0);
  assert.equal(f.navigation.length, 0);
});

test('confirmed failed intake starts show their failure without navigating', async () => {
  const f = elsewhere([{work_id: 'task-failed', task_name: 'intake', state: 'ended', how: 'it did not start: missing adapter'}]);
  await f.api.intakeElsewhere({project: 'other', tables: ['tasks.assignments'], kinds: ['task'],
    work_ids: ['task-failed']});
  assert.equal(f.navigation.length, 0);
  assert.equal(f.notices.length, 1);
  assert.match(f.notices[0], /did not start: missing adapter/);
});
