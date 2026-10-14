"""Source extraction includes callbacks omitted by declaration indexes."""
import pytest

from metaform.modules.refactor.parser import parse

pytestmark = pytest.mark.kind('fixture')


def test_nested_anonymous_callbacks_have_distinct_exact_source_ranges():
    source = b'function outer() { values.map(value => run(() => value)); }'
    result = parse('app.js', source)
    assert result['gaps'] == []
    items = result['items']
    assert [item['symbol'] for item in items] == ['outer', '<anonymous>', '<anonymous>']
    assert len({item['qualified_name'] for item in items}) == 3
    for item in items:
        assert source[item['start_byte']:item['end_byte']].decode() == item['source']


def test_unicode_offsets_and_multiline_positions_are_derived_from_bytes():
    source = '// café 🌲\nconst début = () => {\n  return "你好";\n};\n'.encode()
    item = parse('unicode.js', source)['items'][0]
    assert item['symbol'] == 'début'
    assert item['start_line'] == 2
    assert item['end_line'] == 4
    assert item['start_byte'] == source.index(b'()')
    assert item['source'] == '() => {\n  return "你好";\n}'
    assert item['qualified_name'] == f"unicode.js::début@{item['start_byte']}:{item['end_byte']}"


def test_partial_parse_reports_gap_and_preserves_readable_function():
    source = b'function complete() { return 1; }\nconst broken = ('
    result = parse('broken.js', source)
    assert result['gaps'] == [{'file': 'broken.js', 'reason': 'javascript_parse_partial'}]
    assert any(item['symbol'] == 'complete' for item in result['items'])


def test_binding_names_methods_and_generators():
    source = b'const held = function() {}; target = () => 1; const obj = { run() {} }; function* stream() {}'
    items = parse('bindings.js', source)['items']
    assert [item['symbol'] for item in items] == ['held', 'target', 'run', 'stream']
    assert [item['label'] for item in items] == ['Function', 'Function', 'Method', 'Function']


def test_missing_parser_dependencies_do_not_withdraw_map_or_intake(home, tmp_path, monkeypatch):
    from metaform import loader
    from metaform.module import provided, surface

    original = loader.missing_dependencies

    def missing(requirements):
        parser_requirements = [one for one in requirements if one.startswith('tree-sitter')]
        return parser_requirements or original(requirements)

    monkeypatch.setattr(loader, 'missing_dependencies', missing)
    loader.set_enabled('dispatch', True)
    modules = {module.id for module in surface(tmp_path)}
    assert {'map', 'intake', 'dispatch'} <= modules
    assert 'refactor' not in modules
    assert provided(tmp_path, 'code.inventory')
    assert not provided(tmp_path, 'code.functions')
