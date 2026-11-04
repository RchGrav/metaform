import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import test from 'node:test';

const source = readFileSync(new URL('../page/app/roundtable/stage.js', import.meta.url), 'utf8');
const functions = source.slice(source.indexOf('function minutesIs('), source.indexOf("/* The bottom pane's grip"));

function fixture() {
  const writes = [];
  const node = (tag, attributes = {}, ...children) => ({tag, attributes, children: children.filter(Boolean), hidden: false,
    append(child) { this.children.push(child); child.parent = this; },
    remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); },
    setAttribute(key, value) { this.attributes[key] = value; }});
  const UI = {minutes: {textContent: '', hidden: true}, transcript: {hidden: false},
    showTranscript: node('button'), permissions: node('div')};
  const state = {chosen: false, topic: 0}, pending = new Map();
  const api = runInNewContext(`${functions}\n({minutesIs, permissionIs})`, {
    UI, MINUTES: state, PERMISSIONS: pending, S: {project: 'project'}, TABLE: {id: 'table'}, h: node,
    wrote: async (path, body) => { writes.push({path, body}); return {accepted: true}; },
    toast: message => { throw new Error(message); },
  });
  return {api, UI, state, pending, writes};
}

test('minutes retain earlier entries and speaker attribution across discussions', () => {
  const f = fixture();
  f.api.minutesIs({seat: 'Alpha', topic: 1, text: 'First proposal.'});
  f.api.minutesIs({seat: 'Beta', topic: 1, text: 'A disagreement.', vetoed: true});
  f.api.minutesIs({seat: 'Alpha', topic: 2, text: 'Next topic.'});
  assert.equal(f.UI.minutes.textContent,
    'Roundtable 1\nAlpha: First proposal.\n\nBeta (vetoed): A disagreement.\n\nRoundtable 2\nAlpha: Next topic.');
  assert.equal(f.UI.minutes.hidden, false);
  assert.equal(f.UI.transcript.hidden, true);
  f.state.chosen = true;
  f.UI.transcript.hidden = false;
  f.api.minutesIs({seat: 'Beta', topic: 2, text: 'Another point.'});
  assert.equal(f.UI.transcript.hidden, false);
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
