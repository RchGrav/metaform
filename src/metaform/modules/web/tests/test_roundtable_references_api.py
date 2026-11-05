"""Roundtable citations use the real HTTP read, module verb and project-confined evidence reader."""
from __future__ import annotations

import shlex
from urllib.parse import urlencode

import pytest

from metaform.module import context
from metaform.modules.web.tests.test_web import api, started, web  # noqa: F401

pytestmark = pytest.mark.kind('fixture')

ACCEPTED = '**Keep the original proposal.**\n\n' + 'The complete accepted context remains available. ' * 100


@pytest.fixture
def reference_web(run, web, project_folder):  # noqa: F811 -- shared HTTP server fixture
    run('enable', 'roundtables', cwd=project_folder)
    ctx = context('roundtables', project_folder)
    with ctx.require_store().tables() as tx:
        for name in ('current', 'other'):
            tx.insert('tables', {'table_id': name, 'topic': 'Read the cited evidence', 'opening': '',
                                 'seats': [], 'spend': 0, 'state': 'ended', 'discussion': 7,
                                 'created': '2026-11-05T00:00:00Z'})
        for table, seq, message, outcome, text in (
                ('current', 1, 'R1-1', 'kept', ACCEPTED),
                ('current', 2, 'R1-2', 'vetoed', 'Private rejected contribution.'),
                ('other', 1, 'R1-3', 'kept', 'Another table’s accepted contribution.')):
            tx.insert('events', {'table_id': table, 'seq': seq, 'kind': 'turn', 'audience': 'table',
                                 'payload': {'message_id': message, 'seat': 'StableComet', 'outcome': outcome,
                                             'text': text, 'model': 'private-model', 'profile_key': 'private-profile',
                                             'provider': 'private-provider', 'judging': 'private-judging-detail'},
                                 'at': '2026-11-05T00:00:00Z'})
    started(run)
    return web, project_folder, ctx


def read(port, reference=None, **query):
    values = {'project': 'proj', 'table': 'current', **query}
    if reference is not None:
        values['reference'] = reference
    return api(port, '/api/roundtable?' + urlencode(values))


def test_http_reference_uses_public_accepted_message_and_full_text_without_private_metadata(reference_web):
    port, _, ctx = reference_web
    status, body = read(port, 'R1-1')
    assert status == 200, body
    assert body == {'path': 'R1-1', 'text': '# R1-1 · StableComet\n\n' + ACCEPTED, 'cut': False}
    assert 'private' not in str(body)
    for reference in ('R1-2', 'R1-3'):
        status, refused = read(port, reference)
        assert status == 400, refused
        assert f'No accepted message {reference}' in refused['error']
        assert 'Private rejected' not in str(refused) and 'Another table' not in str(refused)
    status, refused = read(port, 'R1-1', table='unknown')
    assert status == 400 and 'No roundtable unknown in this project' in refused['error']
    with ctx.require_store().tables(write=False) as tx:
        assert len(tx.rows('events', {'table_id': 'current'}, limit=0).results) == 2


def test_http_file_reference_preserves_bounded_line_context_and_reports_byte_cut(reference_web):
    port, folder, _ = reference_web
    (folder / 'source.py').write_text(''.join(f'content {line}\n' for line in range(1, 301)), encoding='utf-8')
    status, body = read(port, 'source.py:100')
    assert status == 200, body
    assert set(body) == {'path', 'text', 'cut', 'line'}
    assert body['path'] == 'source.py' and body['line'] == 100 and body['cut'] is False
    assert body['text'].startswith('source.py:100\n\n20: content 20\n')
    assert '\n100: content 100\n' in body['text'] and body['text'].endswith('180: content 180')
    assert '\n19:' not in body['text'] and '\n181:' not in body['text']
    (folder / 'large.txt').write_text('é' * (1024 * 1024), encoding='utf-8')
    status, body = read(port, 'large.txt')
    assert status == 200, body
    assert body['path'] == 'large.txt' and body['cut'] is True
    assert body['text'] == 'é' * (512 * 1024)
    assert len(body['text'].encode('utf-8')) == 1024 * 1024


def test_http_rg_and_grep_references_search_literal_patterns_without_executing_commands(reference_web):
    port, folder, _ = reference_web
    docs = folder / 'docs'
    docs.mkdir()
    literal = 'a.*b; c|d && $(literal)'
    (docs / 'proof.txt').write_text('a regular expression would match aZZb here\n' + literal + '\nNEEDLE\n',
                                    encoding='utf-8')
    for command, expected in (
            (f'rg -n -F {shlex.quote(literal)} docs', f'docs/proof.txt:2:{literal}'),
            ('grep -nriF needle docs', 'docs/proof.txt:3:NEEDLE')):
        status, body = read(port, command)
        assert status == 200, body
        assert body == {'path': 'Search results', 'text': expected, 'cut': False}
    status, body = read(port, 'rg NEEDLE docs; touch marker')
    assert status == 400 and 'Compound commands' in body['error']
    assert not (folder / 'marker').exists()


def test_http_file_and_search_references_confine_traversal_and_outside_symlinks(reference_web):
    port, folder, _ = reference_web
    outside = folder.parent / 'outside'
    outside.mkdir()
    secret = outside / 'private.txt'
    secret.write_text('needle private outside text', encoding='utf-8')
    (folder / 'outside-file').symlink_to(secret)
    (folder / 'outside-dir').symlink_to(outside, target_is_directory=True)
    (folder / 'visible.txt').write_text('needle visible\n', encoding='utf-8')
    for reference in ('../outside/private.txt', '%2e%2e/outside/private.txt', str(secret),
                      'outside-file', 'outside-dir/private.txt', 'rg needle ../outside',
                      'grep needle outside-file'):
        status, body = read(port, reference)
        assert status == 400, (reference, body)
        assert 'inside this project' in body['error']
        assert 'private outside text' not in str(body)
    status, body = read(port, 'rg needle .')
    assert status == 200, body
    assert body == {'path': 'Search results', 'text': 'visible.txt:1:needle visible', 'cut': False}


def test_http_legacy_note_list_and_read_keep_the_reader_shape_and_confinement(reference_web):
    port, folder, _ = reference_web
    notes = folder / 'docs' / 'roundtables' / '7-notes'
    (notes / 'agents').mkdir(parents=True)
    text = '# Shared decisions\n\nKeep the original note API.\n'
    (notes / 'agents' / 'meeting.md').write_text(text, encoding='utf-8')
    outside = folder.parent / 'private.md'
    outside.write_text('Private outside note.', encoding='utf-8')
    (notes / 'outside.md').symlink_to(outside)
    status, body = read(port, notes='1')
    assert status == 200, body
    assert body == {'notes': [{'path': 'agents/meeting.md', 'bytes': len(text.encode('utf-8'))}]}
    status, body = read(port, note='agents/meeting.md')
    assert status == 200, body
    assert body == {'path': 'agents/meeting.md', 'text': text, 'cut': False}
    for note in ('../../../../private.md', 'outside.md'):
        status, body = read(port, note=note)
        assert status == 404 and 'No such note' in body['error']
        assert 'Private outside note' not in str(body)
