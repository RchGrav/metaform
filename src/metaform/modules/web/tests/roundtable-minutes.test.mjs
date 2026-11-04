import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import test from 'node:test';

const source = readFileSync(new URL('../page/app/roundtable/stage.js', import.meta.url), 'utf8');
const functions = source.slice(source.indexOf('function permissionIs('), source.indexOf("/* The bottom pane's grip"));

function fixture() {
  const writes = [];
  const node = (tag, attributes = {}, ...children) => ({tag, attributes, children: children.filter(Boolean), hidden: false,
    append(child) { this.children.push(child); child.parent = this; },
    remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); },
    setAttribute(key, value) { this.attributes[key] = value; }});
  const UI = {permissions: node('div')};
  const pending = new Map();
  const api = runInNewContext(`${functions}\n({permissionIs})`, {
    UI, PERMISSIONS: pending, S: {project: 'project'}, TABLE: {id: 'table'}, h: node,
    wrote: async (path, body) => { writes.push({path, body}); return {accepted: true}; },
    toast: message => { throw new Error(message); },
  });
  return {api, UI, pending, writes};
}

test('the stage defaults to Haiku explanations while retaining the raw transcript toggle', () => {
  const elements = source.slice(source.indexOf('UI.summaryStatus ='), source.indexOf('/* The harness supplies'));
  const UI = {};
  const node = (tag, attributes = {}, ...children) => ({tag, attributes, children,
    hidden: attributes.hidden ?? false,
    setAttribute(key, value) { this.attributes[key] = value; }});
  runInNewContext(elements, {UI, h: node});
  assert.equal(UI.liveSummary.hidden, false);
  assert.equal(UI.liveSummary.attributes['aria-label'], 'Haiku summary');
  assert.equal(UI.transcript.hidden, true);
  assert.equal(UI.showTranscript.attributes['aria-pressed'], 'false');
  assert.equal(UI.breakdown.children[0], 'Breakdown');
  assert.equal(UI.breakdown.attributes['aria-pressed'], 'true');
  assert.match(UI.summaryStatus.children[0], /Preparing Haiku/);
  UI.showTranscript.attributes.onclick();
  assert.equal(UI.transcript.hidden, false);
  assert.equal(UI.liveSummary.hidden, true);
  assert.equal(UI.breakdown.attributes['aria-pressed'], 'false');
  assert.equal(UI.showTranscript.attributes['aria-pressed'], 'true');
  UI.showTranscript.attributes.onclick();
  assert.equal(UI.transcript.hidden, false, 'Selecting Transcript again keeps only the raw pane visible.');
  assert.equal(UI.liveSummary.hidden, true);
  UI.breakdown.attributes.onclick();
  assert.equal(UI.transcript.hidden, true);
  assert.equal(UI.liveSummary.hidden, false);
  assert.equal(UI.breakdown.attributes['aria-pressed'], 'true');
  assert.equal(UI.showTranscript.attributes['aria-pressed'], 'false');
  assert.match(source, /async function readNotes\(/);
  assert.match(source, /function viewNote\(/);
});

test('permission choices relay the exact ACP option and disappear after resolution', async () => {
  const f = fixture();
  f.api.permissionIs({request: 'request-id', state: 'waiting', name: 'Codex', title: 'Write the materials',
    options: [{optionId: 'native-allow-once', name: 'Allow once', kind: 'allow_once'},
      {optionId: 'native-reject', name: 'Reject', kind: 'reject_once'}]});
  assert.equal(f.UI.permissions.hidden, false);
  const panel = f.pending.get('request-id'), controls = panel.children.at(-1);
  assert.equal(controls.children[0].children[0], 'Allow once');
  await controls.children[0].attributes.onclick();
  assert.equal(f.writes[0].path, '/api/roundtable-control');
  assert.deepEqual(JSON.parse(JSON.stringify(f.writes[0].body)), {project: 'project', table: 'table', action: 'permit',
    request: 'request-id', option: 'native-allow-once'});
  f.api.permissionIs({request: 'request-id', state: 'answered'});
  assert.equal(f.pending.size, 0);
  assert.equal(f.UI.permissions.hidden, true);
});

const elements = source.slice(source.indexOf('UI.summaryStatus ='), source.indexOf("/* The owner's live account"));
const summaryFunctions = source.slice(source.indexOf('function resetMinutes('), source.indexOf('/* The harness supplies'));
const readTable = source.slice(source.indexOf('async function readTable('), source.indexOf('function tell('));
function summaryFixture(get = async () => ({events: [], latest: 0})) {
  const UI = {}, S = {project: 'project'}, TABLE = {id: 'table', seq: 0, busy: false, again: false};
  const reads = [], warnings = [];
  const node = (tag, attributes = {}, ...children) => ({tag, attributes,
    children: children.flat(Infinity).filter(Boolean), textContent: children.flat(Infinity).filter(Boolean).join(''),
    hidden: attributes.hidden ?? false, scrollHeight: 100, scrollTop: 0, clientHeight: 100,
    append(child) { this.children.push(child); child.parent = this; },
    remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); },
    setAttribute(key, value) { this.attributes[key] = value; }});
  const api = runInNewContext(`${source.match(/^const MINUTES = .+;$/m)[0]}
    ${elements}\n${summaryFunctions}\n${functions}\n${readTable}
    ({minutesIs, historicMinutesIs, minutesPending, watchMinutes, resetMinutes, readTable, MINUTES, PERMISSIONS})`, {
    UI, S, TABLE, h: node, SEAT: {n: 1}, TOLD: {list: []},
    getJson: async path => { reads.push(path); return get(path); },
    seated: () => {}, stateIs: () => {}, ended: () => {}, pipelineIs: () => {}, tell: () => {},
    watchPhaseBudget: () => {}, phaseBudgetIs: () => {},
    readNotes: () => {}, toast: message => { warnings.push(message); }, wrote: async () => ({}),
  });
  return {api, UI, S, TABLE, reads, warnings};
}

test('the rolling account updates immediately even when the event cursor does not change', async () => {
  let text = 'Alpha proposes reusing the existing store. Beta wants to check its limits.';
  const f = summaryFixture(async () => ({events: [], latest: 12,
    live_summary: {state: 'ready', text, through_seq: 4, permissions: []}}));
  await f.api.readTable();
  assert.equal(f.TABLE.seq, 12);
  assert.equal(f.UI.summaryText.textContent, text);
  text = 'They agree to measure the existing store. The acceptable delay remains undecided.';
  await f.api.readTable();
  assert.equal(f.TABLE.seq, 12);
  assert.equal(f.UI.summaryText.textContent, text, 'The rolling account replaces its previous version.');
  assert.equal(f.UI.transcript.hidden, true);
  assert.equal(f.UI.liveSummary.hidden, false);
});

test('working, empty, failed and paused snapshots keep truthful readable states', () => {
  const f = summaryFixture();
  f.api.minutesIs({state: 'working', text: '', through_seq: 0});
  assert.equal(f.UI.summaryText.textContent, '');
  assert.match(f.UI.summaryStatus.textContent, /Haiku is preparing/);
  const text = 'Alpha wants faster reads. Beta asks how much stale data the owner can accept.';
  f.api.minutesIs({state: 'ready', text, through_seq: 3});
  f.api.minutesIs({state: 'error', text: '', through_seq: 3, error: 'Native transport failed.'});
  assert.equal(f.UI.summaryText.textContent, text);
  assert.match(f.UI.summaryStatus.textContent, /Haiku could not update.*discussion can continue/);
  assert.doesNotMatch(f.UI.summaryStatus.textContent, /Native transport/);
  f.api.minutesIs({state: 'paused', text: '', through_seq: 3});
  assert.match(f.UI.summaryStatus.textContent, /paused/);
  assert.equal(f.UI.summaryText.textContent, text);
  f.api.minutesIs({state: 'ready', text: '   ', through_seq: 3});
  assert.equal(f.UI.summaryText.textContent, text);
});

test('summary updates preserve an explicit transcript selection and reject an older snapshot', () => {
  const f = summaryFixture();
  f.UI.showTranscript.attributes.onclick();
  f.api.minutesIs({state: 'ready', text: 'The current decision is still open.', through_seq: 8});
  f.api.minutesIs({state: 'ready', text: 'An older account.', through_seq: 7});
  assert.equal(f.UI.summaryText.textContent, 'The current decision is still open.');
  assert.equal(f.UI.transcript.hidden, false);
  assert.equal(f.UI.liveSummary.hidden, true);
});

test('a delayed read cannot put another project or table account on the selected stage', async () => {
  let resolve;
  const f = summaryFixture(path => path.includes('project=project&table=table&')
    ? new Promise(done => { resolve = done; })
    : {events: [], latest: 0, live_summary: {state: 'ready', text: 'The selected discussion.', through_seq: 1}});
  const first = f.api.readTable();
  f.S.project = 'selected-project'; f.TABLE.id = 'selected-table'; f.TABLE.seq = 0;
  await f.api.readTable();
  resolve({events: [], latest: 20,
    live_summary: {state: 'ready', text: 'The previous discussion.', through_seq: 20}});
  await first;
  assert.equal(f.UI.summaryText.textContent, 'The selected discussion.');
  assert.equal(f.reads.length, 2);
  assert.equal(f.TABLE.seq, 0);
});

test('a failed read retains the last explanation and shows a plain loading failure', async () => {
  const f = summaryFixture(async () => { throw new Error('Network failure.'); });
  f.api.watchMinutes(f.S.project, f.TABLE.id);
  f.api.minutesIs({state: 'ready', text: 'They are checking the implementation before deciding.', through_seq: 3});
  await f.api.readTable();
  assert.equal(f.UI.summaryText.textContent, 'They are checking the implementation before deciding.');
  assert.match(f.UI.summaryStatus.textContent, /could not be loaded.*Transcript/);
  assert.deepEqual(f.warnings, ['Network failure.']);
});

test('historical minutes preserve speaker and topic while a new live account takes precedence', () => {
  const f = summaryFixture();
  f.api.historicMinutesIs({kind: 'minutes', seq: 1, topic: 1, seat: 'Alpha', text: 'Use the existing store.'});
  f.api.historicMinutesIs({kind: 'minutes', seq: 2, topic: 2, seat: 'Beta', text: 'Test the failure case.', vetoed: true});
  assert.match(f.UI.summaryText.textContent, /Roundtable 1 · Alpha\nUse the existing store/);
  assert.match(f.UI.summaryText.textContent, /Roundtable 2 · Beta \(vetoed\)\nTest the failure case/);
  f.api.minutesIs({state: 'ready', text: 'They are comparing storage options.', through_seq: 3});
  f.api.historicMinutesIs({kind: 'minutes', seq: 4, topic: 2, seat: 'Alpha', text: 'Earlier material.'});
  assert.equal(f.UI.summaryText.textContent, 'They are comparing storage options.');
});

test('Haiku permission requests share the existing controls and disappear after resolution', () => {
  const f = summaryFixture();
  f.api.minutesIs({state: 'working', text: '', through_seq: 0,
    permissions: [{request: 'haiku-read', title: 'Read the referenced file',
      options: [{optionId: 'allow-once', name: 'Allow once'}]}]});
  assert.equal(f.UI.permissions.hidden, false);
  assert.match(f.UI.summaryStatus.textContent, /waiting for permission/);
  f.api.minutesIs({state: 'ready', text: 'The file supports the proposal.', through_seq: 1,
    permissions: [{request: 'haiku-read', state: 'answered'}]});
  assert.equal(f.UI.permissions.hidden, true);
});

test('note clicks synchronously open a separate reading window with a blocked-popup fallback', () => {
  const note = source.slice(source.indexOf('function viewNote('), source.indexOf('UI.canvas ='));
  const calls = [], opened = {opener: {}, focus() { this.focused = true; }}, UI = {noteFallback: {}};
  let blocked = false;
  const view = runInNewContext(`${note}\nviewNote`, {UI, S: {project: 'project'}, TABLE: {id: 'table'},
    URLSearchParams, screen: {availWidth: 1400, availHeight: 900},
    window: {open: (...args) => { calls.push(args); return blocked ? null : opened; }},
    fill: (box, ...children) => { box.children = children; },
    h: (tag, attributes, ...children) => ({tag, attributes, children}),
  });
  view('joint notes.md');
  assert.equal(new URL(calls[0][0], 'https://example.test').pathname, '/page/roundtable-note.html');
  assert.equal(new URL(calls[0][0], 'https://example.test').searchParams.get('note'), 'joint notes.md');
  assert.match(calls[0][2], /popup,width=1400,height=900/);
  assert.equal(opened.opener, null);
  assert.equal(opened.focused, true);
  view('joint notes.md');
  assert.equal(calls[0][1], calls[1][1], 'The same note reuses its reading window.');
  blocked = true;
  view('different.md');
  assert.notEqual(calls[0][1], calls[2][1]);
  assert.equal(UI.noteFallback.hidden, false);
  assert.equal(UI.noteFallback.children[1].tag, 'a');
  assert.equal(UI.noteFallback.children[1].attributes.target, '_blank');
});
