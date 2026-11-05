"""References read accepted messages and bounded project text without executing commands."""
import shlex

import pytest

from metaform.module import Stop, context
from metaform.modules.roundtables import references

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture
def table(project_folder):
    ctx = context('roundtables', project_folder, nouns={'table': 'current', 'reference': ''})
    with ctx.require_store().tables() as tx:
        for name in ('current', 'other'):
            tx.insert('tables', {'table_id': name, 'topic': 'Read the evidence', 'opening': '',
                                'seats': [], 'spend': 0, 'state': 'held', 'created': '2026-11-05T00:00:00Z'})
    return ctx, project_folder


def recorded(ctx, seq, reference, *, table='current', kind='turn', outcome='kept', **fields):
    payload = {'message_id': reference, 'seat': 'StableComet', 'outcome': outcome,
               'text': '**Keep this proposal.**\n\nThe full supporting discussion.', **fields}
    with ctx.require_store().tables() as tx:
        tx.insert('events', {'table_id': table, 'seq': seq, 'kind': kind, 'audience': 'table',
                             'payload': payload, 'at': '2026-11-05T00:00:00Z'})


def read(table, reference):
    ctx, _ = table
    ctx.nouns['reference'] = reference
    return references.read(ctx)


def test_public_message_has_generated_name_id_and_full_content_without_private_metadata(table):
    ctx, _ = table
    recorded(ctx, 1, 'R3-4', model='private-model', provider='private-provider', profile_key='private-key')
    recorded(ctx, 1, 'R3-4', table='other', text='Other table private material.')
    answer = read(table, 'R3-4')
    assert answer == {'path': 'R3-4', 'text': '# R3-4 · StableComet\n\n**Keep this proposal.**\n\n'
                      'The full supporting discussion.', 'cut': False}
    assert 'private' not in answer['text']
    with ctx.require_store().tables(write=False) as tx:
        assert len(tx.rows('events', {'table_id': 'current'}, limit=0).results) == 1


@pytest.mark.parametrize('kind,outcome,extra', [
    ('veto', 'vetoed', {}), ('turn', 'vetoed', {}), ('turn', 'none', {}),
    ('turn', 'pass', {}), ('turn', 'unjudged', {}), ('turn', 'handoff', {}),
    ('turn', 'carry', {}), ('turn', 'over512', {}), ('turn', 'kept', {'accepted': False}),
    ('turn', None, {}), ('operational', 'kept', {}),
])
def test_unaccepted_or_nonmessage_events_cannot_be_read(table, kind, outcome, extra):
    ctx, _ = table
    recorded(ctx, 1, 'R1-1', kind=kind, outcome=outcome, **extra)
    with pytest.raises(Stop, match='No accepted message'):
        read(table, 'R1-1')


@pytest.mark.parametrize('kind,outcome', [('turn', 'comment'), ('comment', None)])
def test_accepted_chair_comments_are_references(table, kind, outcome):
    ctx, _ = table
    recorded(ctx, 1, 'R1-2', kind=kind, outcome=outcome, seat='Chair', text='Please compare both choices.')
    assert read(table, '`R1-2`')['text'] == '# R1-2 · Chair\n\nPlease compare both choices.'


def test_reference_never_falls_back_to_another_table_or_an_unknown_project_table(table):
    ctx, _ = table
    recorded(ctx, 1, 'R1-1', table='other')
    with pytest.raises(Stop, match='No accepted message'):
        read(table, 'R1-1')
    ctx.nouns['table'] = 'not-in-this-project'
    with pytest.raises(Stop, match='No roundtable .* in this project'):
        read(table, 'R1-1')


@pytest.mark.parametrize('style', ['relative', 'absolute', 'quoted', 'backtick', 'encoded', 'normalized'])
def test_project_file_paths_are_canonical_and_keep_markdown(table, style):
    _, folder = table
    docs = folder / 'docs'
    docs.mkdir()
    document = docs / 'a report.md'
    document.write_text('# Evidence\n\nA useful report.\n', encoding='utf-8')
    reference = {'relative': 'docs/a report.md', 'absolute': str(document),
                 'quoted': '"docs/a report.md"', 'backtick': '`docs/a report.md`',
                 'encoded': 'docs/a%20report.md', 'normalized': 'docs/../docs/a report.md'}[style]
    assert read(table, reference) == {'path': 'docs/a report.md', 'text': '# Evidence\n\nA useful report.\n',
                                      'cut': False}


@pytest.mark.parametrize('suffix', [':100', '#L100', '#L100-L105', ':100:5'])
def test_file_line_context_names_the_requested_line_and_bounds_context(table, suffix):
    _, folder = table
    (folder / 'source.py').write_text(''.join(f'content {line}\n' for line in range(1, 301)), encoding='utf-8')
    answer = read(table, 'source.py' + suffix)
    assert answer['path'] == 'source.py' and answer['line'] == 100 and answer['cut'] is False
    assert answer['text'].startswith('source.py:100\n\n20: content 20\n')
    assert '100: content 100\n' in answer['text']
    assert answer['text'].endswith('180: content 180')
    assert '\n19:' not in answer['text'] and '\n181:' not in answer['text']


@pytest.mark.parametrize('reference', ['small.txt:0', 'small.txt:9', 'missing.txt', '.'])
def test_invalid_file_targets_have_plain_errors(table, reference):
    _, folder = table
    (folder / 'small.txt').write_text('one line\n', encoding='utf-8')
    with pytest.raises(Stop):
        read(table, reference)


@pytest.mark.parametrize('style', ['parent', 'absolute', 'symlink', 'search-parent', 'search-absolute'])
def test_file_and_search_paths_cannot_escape_the_project(table, style):
    _, folder = table
    outside = folder.parent / 'outside.txt'
    outside.write_text('private outside text', encoding='utf-8')
    (folder / 'linked.txt').symlink_to(outside)
    reference = {'parent': '../outside.txt', 'absolute': str(outside), 'symlink': 'linked.txt',
                 'search-parent': "rg private ../outside.txt", 'search-absolute': f'grep private {outside}'}[style]
    with pytest.raises(Stop, match='inside this project'):
        read(table, reference)


@pytest.mark.parametrize('data', [b'ordinary\0binary', b'bad utf8\xff'])
def test_binary_or_invalid_utf8_file_is_refused(table, data):
    _, folder = table
    (folder / 'binary').write_bytes(data)
    with pytest.raises(Stop, match='not readable UTF-8'):
        read(table, 'binary')


def test_file_byte_limit_preserves_valid_utf8_and_reports_unreached_target_line(table, monkeypatch):
    _, folder = table
    monkeypatch.setattr(references, 'MAX_BYTES', 71)
    (folder / 'large.txt').write_text('é' * 100 + '\nsecond\n', encoding='utf-8')
    answer = read(table, 'large.txt')
    assert answer['cut'] and answer['text'] == 'é' * 35
    assert len(answer['text'].encode('utf-8')) <= 71
    answer = read(table, 'large.txt:2')
    assert answer['cut'] and answer['line'] == 2 and 'before line 2' in answer['text']


@pytest.mark.parametrize('wrapper', ['raw', 'backtick', 'quoted'])
def test_search_is_literal_and_allows_shell_symbols_inside_the_quoted_pattern(table, wrapper):
    _, folder = table
    docs = folder / 'docs'
    docs.mkdir()
    literal = 'a.*b; c|d && $(literal)'
    (docs / 'proof.txt').write_text('not a regex match\n' + literal + '\n', encoding='utf-8')
    command = f'rg -n -F {shlex.quote(literal)} docs'
    reference = {'raw': command, 'backtick': f'`{command}`', 'quoted': shlex.quote(command)}[wrapper]
    answer = read(table, reference)
    assert answer == {'path': 'Search results', 'text': f'docs/proof.txt:2:{literal}', 'cut': False}


@pytest.mark.parametrize('command', ['grep -nriF needle docs', ('rg --line-number --ignore-case --fixed-strings '
                                   '--recursive --with-filename --no-messages needle docs')])
def test_safe_search_flags_and_absolute_inside_paths_work(table, command):
    _, folder = table
    docs = folder / 'docs'
    docs.mkdir()
    (docs / 'readme.txt').write_text('first\nNEEDLE evidence\nneedle again\n', encoding='utf-8')
    assert read(table, command)['text'] == 'docs/readme.txt:2:NEEDLE evidence\ndocs/readme.txt:3:needle again'
    assert read(table, f'rg -il needle {shlex.quote(str(docs))}')['text'] == 'docs/readme.txt:2'


def test_search_skips_git_binary_and_outside_symlinks_without_losing_valid_hits(table):
    _, folder = table
    outside = folder.parent / 'outside'
    outside.mkdir()
    (outside / 'private.txt').write_text('needle outside', encoding='utf-8')
    (folder / 'outside-dir').symlink_to(outside, target_is_directory=True)
    (folder / 'outside-file').symlink_to(outside / 'private.txt')
    (folder / '.git').mkdir()
    (folder / '.git' / 'config').write_text('needle git', encoding='utf-8')
    (folder / 'binary').write_bytes(b'needle\0binary')
    (folder / 'visible.txt').write_text('needle visible\n', encoding='utf-8')
    assert read(table, 'rg needle .') == {'path': 'Search results', 'text': 'visible.txt:1:needle visible',
                                          'cut': False}


@pytest.mark.parametrize('command', [
    'rg needle .; touch marker', 'rg needle . | cat', 'rg needle . && cat secret',
    'rg needle > copied', 'rg $(cat secret) .', 'rg `cat secret` .', 'rg needle\ncat secret',
    'rg --pre=cat needle .', 'grep --include=*.py needle .', 'rg -e needle .',
    'rg -f patterns .', 'rg --hidden needle .', 'rg -n "unmatched', 'rg',
])
def test_unsupported_flags_and_compound_searches_are_refused_without_side_effects(table, command):
    _, folder = table
    with pytest.raises(Stop):
        read(table, command)
    assert not (folder / 'marker').exists() and not (folder / 'copied').exists()


def test_search_dash_pattern_and_no_match_status(table):
    _, folder = table
    (folder / 'flags.txt').write_text('literal -n option\n', encoding='utf-8')
    assert read(table, 'rg -F -- -n flags.txt')['text'] == 'flags.txt:1:literal -n option'
    assert read(table, 'grep absent flags.txt')['text'] == "No matches for 'absent'."


def test_search_output_is_bounded_even_for_one_oversized_matching_line(table, monkeypatch):
    _, folder = table
    monkeypatch.setattr(references, 'MAX_BYTES', 100)
    (folder / 'large.txt').write_text('needle ' + 'x' * 300, encoding='utf-8')
    answer = read(table, 'rg needle large.txt')
    assert answer['cut'] and len(answer['text'].encode('utf-8')) <= 100
    assert answer['text'].startswith('large.txt:1:needle ')


def test_search_file_count_and_elapsed_time_limits_report_incomplete_results(table, monkeypatch):
    _, folder = table
    for number in range(2):
        (folder / f'{number}.txt').write_text('needle\n', encoding='utf-8')
    monkeypatch.setattr(references, 'MAX_FILES', 1)
    assert read(table, 'rg needle .')['cut'] is True
    monkeypatch.setattr(references, 'SEARCH_SECONDS', 0)
    assert read(table, 'rg needle .')['cut'] is True


@pytest.mark.parametrize('reference', ['', 'x' * 8193, 'rg "" .', 'rg x ' + ' '.join(['.'] * 9)])
def test_empty_and_oversized_reference_inputs_are_refused(table, reference):
    with pytest.raises(Stop):
        read(table, reference)
