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

test('the stage keeps the transcript and shared document browser without automatic minutes', () => {
  assert.doesNotMatch(source, /UI\.minutes|minutesIs|MINUTES|rt-running/);
  assert.match(source, /UI\.transcript = h\('ol'/);
  assert.match(source, /async function readNotes\(/);
  assert.match(source, /async function viewNote\(/);
  assert.match(source, /UI\.records = h\('section'/);
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
