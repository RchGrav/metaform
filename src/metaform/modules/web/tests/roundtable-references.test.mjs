import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';

const code = readFileSync(new URL('../page/app/roundtable/references.js', import.meta.url), 'utf8');
const {referenceHref, referenceParts} = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
const context = {project: 'project & another', table: 'table/one'};
const queryOf = href => new URL(href, 'https://metaform.invalid').searchParams;

test('accepted message IDs, file lines and explicit search citations retain their exact targets', () => {
  const parts = referenceParts('See R1-1 and [evidence](src/engine.py:42), then `rg -n -F "gate" src/engine.py`.', context);
  const links = parts.filter(part => part.href);
  assert.deepEqual(links.map(part => part.text), ['R1-1', 'evidence', 'rg -n -F "gate" src/engine.py']);
  assert.deepEqual(links.map(part => queryOf(part.href).get('reference')),
    ['R1-1', 'src/engine.py:42', 'rg -n -F "gate" src/engine.py']);
  for (const link of links) {
    assert.equal(queryOf(link.href).get('project'), context.project);
    assert.equal(queryOf(link.href).get('table'), context.table);
  }
  const command = 'grep -n -F "retained decision" src/engine.py';
  assert.equal(queryOf(referenceParts(command, context)[0].href).get('reference'), command);
  assert.equal(queryOf(referenceHref('rg%20-n%20-F%20%22gate%22%20src%2Fengine.py', context)).get('reference'),
    'rg -n -F "gate" src/engine.py');
});

test('local Markdown references retain note or source file context and HTTP links remain ordinary links', () => {
  const note = referenceHref('../other.md', {...context, note: 'agents/ledger.md'}, true);
  assert.equal(queryOf(note).get('note'), 'agents/../other.md');
  assert.equal(queryOf(note).has('reference'), false);
  const source = referenceHref('../README.md', {...context, reference: 'docs/design.md:12'}, true);
  assert.equal(queryOf(source).get('reference'), 'docs/../README.md');
  assert.equal(referenceHref('https://example.com/proof?q=1', context), 'https://example.com/proof?q=1');
  assert.equal(queryOf(referenceHref('#R2-17', context)).get('reference'), 'R2-17');
});

test('untrusted markup and executable or unsupported destinations stay inert text', () => {
  for (const target of ['javascript:alert(1)', 'data:text/html,hello', 'file:///etc/passwd', '//example.com/a.md',
    'vscode://file/etc/passwd', 'python -c print(1)', 'rg']) assert.equal(referenceHref(target, context), null);
  const text = '<script>alert(1)</script> [run](javascript:alert(1))';
  const parts = referenceParts(text, context);
  assert.equal(parts.filter(part => part.href).length, 0);
  assert.equal(parts.map(part => part.text).join(''), text);
});
