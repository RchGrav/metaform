import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import test from 'node:test';

const source = readFileSync(new URL('../page/app/roundtable/stage.js', import.meta.url), 'utf8');
const references = readFileSync(new URL('../page/app/roundtable/references.js', import.meta.url), 'utf8');
const {referenceParts} = await import(`data:text/javascript;base64,${Buffer.from(references).toString('base64')}`);
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

test('the stage opens directly on the transcript without requesting a generated Breakdown', () => {
  const elements = source.slice(source.indexOf('UI.transcript ='), source.indexOf('/* The harness supplies'));
  const UI = {};
  const node = (tag, attributes = {}, ...children) => ({tag, attributes, children, hidden: attributes.hidden ?? false});
  runInNewContext(elements, {UI, h: node});
  assert.equal(UI.transcript.hidden, false);
  assert.equal(UI.transcript.attributes['aria-label'], 'The transcript');
  assert.equal(UI.breakdown, undefined);
  assert.equal(UI.liveSummary, undefined);
  assert.doesNotMatch(source, /watchMinutes|minutesIs|minutesPending|Preparing Haiku/);
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

test('budget operational messages show their readable text with safe raw-text fallbacks', () => {
  const heard = source.slice(source.indexOf('function heard('), source.indexOf('const seatOf ='));
  const rows = [], TABLE = {seq: 41};
  const show = runInNewContext(`${heard}\nheard`, {TABLE, said: (...args) => rows.push(args), nextUp: () => {}});
  const old = JSON.stringify({phase: 'panel', text: 'Token budget warning: Alpha has reached 80%.'});
  show({kind: 'operational', what: 'budget', text: old});
  show({kind: 'operational', what: 'budget', text: old, budget: {text: 'The structured warning takes precedence.'}});
  show({kind: 'operational', what: 'budget', text: '{malformed budget'});
  show({kind: 'operational', what: 'budget', text: '{"phase":"panel"}'});
  show({kind: 'operational', what: 'another-kind', text: old});
  assert.deepEqual(rows, [
    ['rt-note', 'budget', 'Token budget warning: Alpha has reached 80%.'],
    ['rt-note', 'budget', 'The structured warning takes precedence.'],
    ['rt-note', 'budget', '{malformed budget'],
    ['rt-note', 'budget', '{"phase":"panel"}'],
    ['rt-note', 'another-kind', old],
  ]);
  assert.equal(TABLE.seq, 41, 'Rendering does not rewind or redeliver events.');
});

function vetoFixture() {
  const code = source.slice(source.indexOf('const VETO_REASONS ='), source.indexOf('/* Who speaks next'));
  const said = source.slice(source.indexOf('function said('), source.indexOf('/* ---------- the figures'));
  const rows = [];
  const UI = {transcript: {scrollHeight: 100, scrollTop: 0, clientHeight: 100, append: row => rows.push(row)}};
  const turn = runInNewContext(`${code}\n${said}\nturn`, {UI, TABLE: {ended: false, id: 'table'},
    S: {project: 'project'}, referenceParts, seatOf: () => -1,
    h: (tag, attributes, ...children) => ({tag, attributes, children})});
  return {turn, rows};
}

test('accepted public IDs and citations open readable references while vetoed or legacy turns keep their labels', () => {
  const f = vetoFixture();
  f.turn({kind: 'turn', message_id: 'R2-17', seat: 'Alpha', text: 'See R1-1 and [the source](src/engine.py:42).'});
  const links = [];
  function visit(node) {
    if (!node || typeof node !== 'object') return;
    if (node.tag === 'a') links.push(node);
    for (const child of node.children || []) visit(child);
  }
  visit(f.rows[0]);
  assert.deepEqual(links.map(link => link.children[0]), ['R2-17', 'R1-1', 'the source']);
  assert.deepEqual(links.map(link => new URL(link.attributes.href, 'https://metaform.invalid').searchParams.get('reference')),
    ['R2-17', 'R1-1', 'src/engine.py:42']);
  assert.ok(links.every(link => link.attributes.target === '_blank' && link.attributes.rel === 'noopener noreferrer'));
  f.turn({kind: 'veto', message_id: 'R9-9', seat: 'Beta', text: 'An owner-visible rejected contribution.'});
  f.turn({kind: 'turn', n: 47, seat: 'Gamma', text: 'An older contribution.'});
  assert.equal(f.rows[1].children[0].children[0], 'Beta');
  assert.equal(f.rows[2].children[0].children[0], 'Gamma');
});

test('vetoes state the recorded failed condition while keeping the original contribution', () => {
  for (const [failed, expected] of [
    [['on_topic'], 'The topic relevance criterion was not met.'],
    [['new_context'], 'The new-information criterion was not met.'],
    [['repeat'], 'The contribution was marked as repeated material.'],
    [['on_topic', 'new_context'], 'The topic relevance criterion was not met. The new-information criterion was not met.'],
    [[], 'No veto reason was recorded'],
  ]) {
    const f = vetoFixture();
    f.turn({kind: 'veto', seat: 'Alpha', text: 'The original contribution.', failed,
      scores: {on_topic: 0.42, new_context: 0.30, valuable: 0.99}});
    assert.equal(f.rows[0].attributes.class, 'rt-turn vetoed');
    assert.equal(f.rows[0].children[2], 'The original contribution.');
    assert.equal(f.rows[0].children[3].children[0], ` (vetoed: ${expected})`);
    assert.doesNotMatch(f.rows[0].children[3].children[0], /0\.99|usefulness/);
  }
});

test('a recorded score-and-cutoff reason takes precedence and remains plain text', () => {
  const f = vetoFixture(), recorded = 'Topic relevance was 0.42; required 0.60. <b>Recorded evidence</b>';
  f.turn({kind: 'veto', seat: 'Alpha', text: 'Keep the contribution.', veto_reason: recorded,
    reason: 'Another recorded reason.', failed: ['new_context']});
  const suffix = f.rows[0].children[3];
  assert.equal(suffix.tag, 'span');
  assert.equal(suffix.children[0], ` (vetoed: ${recorded})`);
  assert.equal(typeof suffix.children[0], 'string', 'The reason goes through the existing plain-text DOM path.');
  f.turn({kind: 'veto', seat: 'Beta', text: 'Keep this too.', reason: ' A recorded condition failed. ', failed: ['on_topic']});
  assert.equal(f.rows[1].children[3].children[0], ' (vetoed: A recorded condition failed.)');
});
