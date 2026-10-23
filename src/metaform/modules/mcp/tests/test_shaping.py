"""Result selection preserves evidence before formatting, audit F08."""
from __future__ import annotations

import json

import pytest

from metaform.modules.mcp import shaping

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('MCP-039')]


@pytest.mark.parametrize('view', ['triage', 'full'])
@pytest.mark.parametrize('field', ['candidate.artifact.hash', 'hash', 'candidate.artifact'])
def test_deep_projection_uses_the_validated_paths(view, field):
    raw = {'candidate': {'artifact': {'hash': 'abc123', 'path': 'result.txt'}, 'review': 'omit'}}
    text, data = shaping.shaped(raw, shaping.Shape(view=view, fields=(field,)), '', record=True)
    artifact = raw['candidate']['artifact'] if field == 'candidate.artifact' else {'hash': 'abc123'}
    assert data == {'candidate': {'artifact': artifact}}
    assert 'abc123' in text and 'review' not in text
    if view == 'full':
        assert json.loads(text) == data


@pytest.mark.parametrize('view', ['triage', 'full'])
def test_filters_see_raw_fields_before_projection_and_default_omissions(view):
    raw = {'results': [{'id': 'A', 'state': 'open', 'existing': False, 'passed': False, 'evidence': 'KEEP'},
                       {'id': 'B', 'state': 'done', 'existing': False, 'passed': True, 'evidence': 'OMIT'},
                       {'id': 'C', 'state': 'open', 'existing': True, 'passed': True, 'evidence': 'OMIT'}]}
    shape = shaping.Shape(view=view, fields=('id', 'passed'), status_equals='open', must_contain='false')
    text, data = shaping.shaped(raw, shape, '')
    assert data == {'results': [{'id': 'A', 'passed': False}]}
    assert 'false' in text and 'KEEP' not in text and 'OMIT' not in text
    if view == 'full':
        assert json.loads(text) == data
    assert raw['results'][0]['evidence'] == 'KEEP'


@pytest.mark.parametrize('view', ['triage', 'full'])
def test_projection_keeps_nested_lists_and_empty_containers(view):
    raw = {'results': [{'id': 'A', 'candidate': {'artifacts': [{'hash': 'abc', 'path': 'omit'},
                                                            {'hash': '', 'path': 'omit'}, {}]}},
                       {'id': 'B', 'candidate': {'artifacts': []}}, {'id': 'C', 'candidate': {}}]}
    shape = shaping.Shape(view=view, fields=('id', 'candidate.artifacts.hash'))
    text, data = shaping.shaped(raw, shape, '')
    assert data == {'results': [{'id': 'A', 'candidate': {'artifacts': [{'hash': 'abc'}, {'hash': ''}, {}]}},
                                {'id': 'B', 'candidate': {'artifacts': []}}, {'id': 'C', 'candidate': {}}]}
    assert 'abc' in text and '[]' in text and '""' in text
    assert 'omit' not in text
    if view == 'full':
        assert json.loads(text) == data


def test_a_nested_list_only_projection_renders_without_recursing_into_its_parent_label():
    raw = {'results': [{'candidate': {'artifacts': [{'hash': 'abc'}, {'hash': ''}]}},
                       {'candidate': {'artifacts': []}}]}
    text, data = shaping.shaped(raw, shaping.Shape(fields=('candidate.artifacts.hash',)), '')
    assert data == raw
    assert 'row|hash\n1|abc\n1|""' in text and '[]' in text


@pytest.mark.parametrize('view', ['triage', 'full'])
def test_explicit_false_zero_empty_null_and_metadata_are_preserved(view):
    raw = {'id': 'check', 'passed': False, 'total': 0, 'note': '', 'links': [], 'details': {},
           'unknown': None, 'node_id': 'internal'}
    text, data = shaping.shaped(raw, shaping.Shape(view=view, fields=tuple(raw)), '', record=True)
    assert data == raw
    if view == 'full':
        assert json.loads(text) == raw
    else:
        assert 'passed: false' in text and 'total: 0' in text and 'note: ""' in text
        assert 'links:' in text and 'details: {}' in text and 'unknown: null' in text


def test_default_triage_preserves_negative_and_empty_evidence():
    raw = {'results': [{'id': 'check', 'passed': False, 'existing': False, 'differs': False,
                        'orphaned': False, 'total': 0, 'note': '', 'links': [], 'details': {},
                        'unknown': None, 'node_id': 'internal'}]}
    text, data = shaping.shaped(raw, shaping.Shape(), '', record=True)
    assert data == {'results': [{key: value for key, value in raw['results'][0].items()
                                if key not in ('unknown', 'node_id')}]}
    assert 'false' in text and '0' in text and '[]' in text and '{}' in text and '""' in text


@pytest.mark.parametrize('view', ['triage', 'full', 'count'])
def test_a_record_with_an_empty_detail_list_is_still_projected_as_a_record(view):
    raw = {'id': 'check', 'passed': False, 'links': []}
    text, data = shaping.shaped(raw, shaping.Shape(view=view, fields=('passed',)), '', record=True)
    assert data == ({'total': 1, 'by': {'passed': {'false': 1}}} if view == 'count' else {'passed': False})
    assert 'false' in text and 'links' not in text


@pytest.mark.parametrize('view', ['triage', 'full', 'count'])
def test_validation_uses_unfiltered_rows_and_refuses_unknown_fields_even_in_full(view):
    raw = {'results': [{'id': 'A', 'state': 'open', 'passed': False}]}
    shape = shaping.Shape(view=view, fields=('passed',), status_equals='done')
    text, data = shaping.shaped(raw, shape, '')
    expected = {'total': 0, 'by': {'passed': {}}} if view == 'count' else {'results': []}
    assert data == expected
    if view != 'triage':
        assert json.loads(text) == expected
    with pytest.raises(shaping.Unheld, match='No record here holds missing'):
        shaping.shaped(raw, shaping.Shape(view=view, fields=('missing',), status_equals='done'), '')
    with pytest.raises(shaping.Unheld, match='status_equals compares'):
        shaping.shaped({'results': [{'id': 'A'}]}, shaping.Shape(view=view, status_equals='open'), '')


@pytest.mark.parametrize('view', ['triage', 'full', 'count'])
@pytest.mark.parametrize('raw', [[], {'results': []}, {'matches': []}])
def test_empty_results_are_valid_without_fabricating_records(view, raw):
    text, data = shaping.shaped(raw, shaping.Shape(view=view, fields=('passed',), status_equals='open'), '')
    if view == 'count':
        assert data == {'total': 0, 'by': {'passed': {}}}
    elif isinstance(raw, dict):
        assert data == raw
    else:
        assert data is None
    if view == 'full':
        assert json.loads(text) == raw
    elif view == 'triage':
        assert '(none)' in text


def test_counts_preserve_false_null_missing_empty_and_nested_list_values():
    raw = {'results': [{'passed': False, 'artifacts': [{'hash': 'abc'}, {'hash': 'abc'}, {'hash': ''}]},
                       {'passed': None, 'artifacts': [{'hash': 'def'}]},
                       {'passed': '', 'artifacts': []}, {}]}
    text, data = shaping.shaped(raw, shaping.Shape(view='count', fields=('passed', 'artifacts.hash')), '')
    assert json.loads(text) == data == {
        'total': 4, 'by': {'passed': {'': 1, '(missing)': 1, '(none)': 1, 'false': 1},
                          'artifacts.hash': {'(missing)': 2, '': 1, 'abc': 1, 'def': 1}}}


def test_count_alias_includes_each_matching_path_instead_of_only_the_first():
    raw = {'results': [{'passed': None, 'candidate': {'passed': False}, 'review': {'passed': True}}]}
    text, data = shaping.shaped(raw, shaping.Shape(view='count', fields=('passed',)), '')
    assert json.loads(text) == data == {
        'total': 1, 'by': {'passed': {'(none)': 1}, 'candidate.passed': {'false': 1}, 'review.passed': {'true': 1}}}


def test_full_and_count_are_complete_while_triage_is_bounded():
    raw = {'results': [{'id': number, 'passed': False} for number in range(30)]}
    full, data = shaping.shaped(raw, shaping.Shape(view='full', fields=('id',)), '')
    assert json.loads(full) == data == {'results': [{'id': number} for number in range(30)]}
    counted, data = shaping.shaped(raw, shaping.Shape(view='count', fields=('passed',)), '')
    assert json.loads(counted) == data == {'total': 30, 'by': {'passed': {'false': 30}}}
    text, data = shaping.shaped(raw, shaping.Shape(fields=('id',)), '<n/> more')
    assert text.endswith('5 more') and len(data['results']) == 25
