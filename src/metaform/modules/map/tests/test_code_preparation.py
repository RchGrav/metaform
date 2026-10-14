"""Inventory boundaries keep source and graph evidence safe and attributable."""
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.kind("simulation")

from metaform.module import Context
from metaform.modules.map import code_preparation as preparation
from metaform.modules.map.code_index import Symbol


def inventory(tmp_path, monkeypatch, symbols, paths=None, settings=None, coverage=None, parser=True):
    calls = []

    class Server:
        project, tool, version = 'example', 'codebase-memory-mcp', 'test'

        def query(self, tool, arguments):
            calls.append((tool, arguments))
            if tool == 'check_index_coverage':
                if isinstance(coverage, Exception):
                    raise coverage
                return coverage if coverage is not None else {
                    'metadata': {'generation_matches': True, 'recording_status': 'complete'},
                    'paths': [{'requested_path': path, 'status': 'no_recorded_issue',
                               'freshness': 'metadata_match', 'coverage': []} for path in arguments['paths']]}
            return {'indexed_at': 'today'}

        def listing(self):
            return dict.fromkeys([s.path for s in symbols], 'stamp')

        def read(self, paths):
            return [s for s in symbols if s.path in paths], []

    @contextmanager
    def server(*args, **kwargs):
        assert kwargs['index_missing']
        yield Server()

    from metaform.modules.source_placement.parser import SUFFIXES, parse
    capabilities = [('source_placement', {'suffixes': SUFFIXES, 'parse': parse})] if parser else []
    monkeypatch.setattr(preparation, 'provided', lambda *_: capabilities)
    monkeypatch.setattr(preparation, 'code_graph_server', server)
    monkeypatch.setattr(preparation.home, 'ignore_patterns', lambda _: ['private/'])
    ctx = Context('map', tmp_path, switches={'code_ignore': [], **(settings or {})})
    ctx.store = SimpleNamespace(project=lambda: SimpleNamespace(path=str(tmp_path)))
    return preparation.inventory(ctx, paths), calls


def test_inventory_rejects_outside_and_ignored_sources(tmp_path, monkeypatch):
    (tmp_path / 'ok.py').write_text('def ok():\n    return 1\n')
    (tmp_path / 'escape.py').symlink_to(tmp_path.parent / 'outside.py')
    symbols = [Symbol('ok', 'ok', 'Function', 'ok.py', 1, 2)]
    result, calls = inventory(tmp_path, monkeypatch, symbols,
                              ['ok.py', '../outside.py', 'escape.py', 'private/key.py'])
    assert [i['symbol'] for i in result['items']] == ['ok']
    assert len(result['gaps']) == 3
    assert [call[0] for call in calls] == ['index_status', 'check_index_coverage']
    assert result['scope'] == ['ok.py']


def test_inventory_preserves_duplicate_locators_and_reports_bad_ranges(tmp_path, monkeypatch):
    (tmp_path / 'ok.py').write_text('def same(): return 1\ndef same(): return 2\n')
    symbols = [Symbol('same', 'same', 'Function', 'ok.py', 1, 1),
               Symbol('same', 'same', 'Function', 'ok.py', 2, 2),
               Symbol('missing', 'missing', 'Function', 'ok.py', 99, 100)]
    result, _ = inventory(tmp_path, monkeypatch, symbols)
    assert len(result['items']) == 2
    assert all(not item['unique_identity'] for item in result['items'])
    assert {item['start_line'] for item in result['items']} == {1, 2}
    assert {gap['reason'] for gap in result['gaps']} == {'duplicate_symbol_identity', 'invalid_source_range'}


def test_inventory_oversize_and_missing_files_are_gaps(tmp_path, monkeypatch):
    (tmp_path / 'big.py').write_text('def big(): return 123456789\n')
    monkeypatch.setattr(preparation, 'MAX_SOURCE_BYTES', 10)
    result, _ = inventory(tmp_path, monkeypatch, [Symbol('big', 'big', 'Function', 'big.py', 1, 1)],
                          ['big.py', 'missing.py'])
    assert not result['items']
    assert {gap['reason'] for gap in result['gaps']} == {'source_too_large', 'source_unreadable'}


def test_javascript_inventory_includes_nested_anonymous_callbacks(tmp_path, monkeypatch):
    pytest.importorskip('tree_sitter')
    pytest.importorskip('tree_sitter_javascript')
    (tmp_path / 'app.js').write_text('function start() { setTimeout(() => { finish(); }, 10); }\n')
    result, _ = inventory(tmp_path, monkeypatch, [Symbol('start', 'start', 'Function', 'app.js', 1, 1)])
    assert len(result['items']) == 2
    assert result['items'][1]['source'] == '() => { finish(); }'
    assert all(item['unique_identity'] for item in result['items'])
    assert result['items'][0]['start_byte'] != result['items'][1]['start_byte']


def test_map_inventory_works_without_a_parser_module(tmp_path, monkeypatch):
    (tmp_path / 'app.js').write_text('function start() { later(() => finish()); }\n')
    result, _ = inventory(tmp_path, monkeypatch, [Symbol('start', 'start', 'Function', 'app.js', 1, 1)],
                          parser=False)
    assert len(result['items']) == 1
    assert result['items'][0]['symbol'] == 'start'
    assert not result['gaps']


def test_missing_index_is_created_only_when_requested(tmp_path):
    from metaform.modules.map.code_index import CodeGraphServer, Unavailable
    calls = []

    def call(tool, arguments):
        calls.append(tool)
        if tool == 'list_projects':
            projects = ([{'name': 'example', 'root_path': str(tmp_path)}]
                        if 'index_repository' in calls else [])
            payload = {'projects': projects}
        else:
            assert tool == 'index_repository'
            assert arguments['repo_path'] == str(tmp_path)
            payload = {'status': 'ready'}
        return SimpleNamespace(structured_content=payload)

    tools = ['query_graph', 'list_projects', 'index_repository']
    with pytest.raises(Unavailable, match='holds no index'):
        CodeGraphServer(call, 'test', '1', tools, tmp_path, '', ['Function'])
    assert 'index_repository' not in calls
    calls.clear()
    provider = CodeGraphServer(call, 'test', '1', tools, tmp_path, '', ['Function'], index_missing=True)
    assert provider.project == 'example'
    assert calls == ['list_projects', 'index_repository', 'list_projects']


@pytest.mark.parametrize('freshness', ['changed', 'missing', 'unknown'])
def test_stale_graph_ranges_do_not_bless_unrelated_current_source(tmp_path, monkeypatch, freshness):
    (tmp_path / 'ok.py').write_text('def entirely_different(): return 2\n')
    stale = Symbol('old_name', 'old_name', 'Function', 'ok.py', 1, 1)
    coverage = {'metadata': {'generation_matches': True, 'recording_status': 'complete'},
                'paths': [{'requested_path': 'ok.py', 'status': 'no_recorded_issue',
                           'freshness': freshness, 'coverage': []}]}
    result, _ = inventory(tmp_path, monkeypatch, [stale], coverage=coverage)
    assert not result['items']
    assert any(gap['reason'] == 'structural_coverage_unverified' for gap in result['gaps'])


def test_absent_coverage_is_gap_instead_of_intake_failure(tmp_path, monkeypatch):
    (tmp_path / 'ok.py').write_text('def ok(): return 1\n')
    result, _ = inventory(tmp_path, monkeypatch, [Symbol('ok', 'ok', 'Function', 'ok.py', 1, 1)],
                          coverage=preparation.Unavailable('path absent from graph', 'read source'))
    assert not result['items']
    assert result['coverage'][0]['error'] == 'path absent from graph'
    assert any(gap['reason'] == 'structural_coverage_unverified' for gap in result['gaps'])


def test_fresh_javascript_ast_does_not_reuse_stale_graph_identity(tmp_path, monkeypatch):
    pytest.importorskip('tree_sitter')
    pytest.importorskip('tree_sitter_javascript')
    (tmp_path / 'app.js').write_text('function current() { return 1; }\n')
    result, _ = inventory(tmp_path, monkeypatch,
                          [Symbol('old_scope.current', 'current', 'Function', 'app.js', 1, 1)], coverage={})
    assert len(result['items']) == 1
    assert result['items'][0]['qualified_name'].startswith('app.js::current@')
    assert result['items'][0]['source'] == 'function current() { return 1; }'
    assert any(gap['reason'] == 'structural_coverage_unverified' for gap in result['gaps'])
