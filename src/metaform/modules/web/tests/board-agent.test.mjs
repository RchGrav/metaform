import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import test from 'node:test';

const source = readFileSync(new URL('../page/app/board/board.js', import.meta.url), 'utf8');
const area = source.slice(source.indexOf('const FRONTEND'), source.indexOf('export const eligibleAgents'))
  .replaceAll('export ', '');
const controls = source.slice(source.indexOf('function ticketControls('), source.indexOf('/* Which agent works'));
function fixture(defaultAgent = 'other') {
  let selected;
  const api = runInNewContext(`${area}\n${controls}\n({defaultAgent, ticketControls})`, {
    HARNESS: {default: defaultAgent},
    h: () => ({}),
    agentSelect: chosen => { selected = chosen; },
    eligibilityPicker: () => null, eligibleAgents: () => [], glyphPick: () => null,
  });
  return {api, selected: () => selected};
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
