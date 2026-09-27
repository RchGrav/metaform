"""The map's entry, roles indexed for it, and findings flags: STORE-009, STORE-025 `roots`, STORE-042."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from metaform.data import Store
from storekit import dump, plans, record_intake, small_map, store_file

pytestmark = pytest.mark.kind('fixture')

FIXTURE = json.loads((Path(__file__).parent / 'fixtures' / 'intake_timer.json').read_text(encoding='utf-8'))


@pytest.mark.req('STORE-009')
@pytest.mark.req('STORE-025')
def test_the_entry_is_the_ve_and_de_with_their_joins_and_every_root_element(home, store, traced):
    small_map(store)
    rows = dump(store_file(home, store))['element_roles']
    assert len(rows) == 3
    traced.clear()
    roots = store.roots()
    lines = [line for _, plan in plans(home, store, traced) for line in plan]
    assert any('element_roles_by_role' in line for line in lines)
    entry = {item.element.address: [join.provider_address for join in item.joins] for item in roots.entry}
    assert entry == {'stakeholder.cook.home': ['code.timer.kitchen'], 'code.timer.kitchen': ['code.alarm.audible']}
    assert sorted((element.address, element.role) for element in roots.elements) == [
        ('code.alarm.audible', 'SE'), ('code.timer.kitchen', 'DE'), ('stakeholder.cook.home', 'VE')]


@pytest.mark.req('STORE-025')
@pytest.mark.req('BASE-038')
@pytest.mark.req('MCP-008')
def test_map_roots_and_where_with_no_address_return_the_entry(run, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    small_map(Store('proj'))
    roots = json.loads(run('map', 'roots', '--json', cwd=folder).stdout)
    assert {item['element']['address'] for item in roots['entry']} == {'stakeholder.cook.home', 'code.timer.kitchen'}
    assert json.loads(run('map', 'where', '', '--json', cwd=folder).stdout) == roots
    purpose = run('help', 'agents', cwd=folder).stdout
    assert 'Start with map_roots: it returns the map\'s entry, the VE and the DE with their joins, and the root ' \
           'elements.' in purpose


@pytest.mark.req('STORE-042')
@pytest.mark.req('MAP-046')
def test_one_row_per_flagged_object_listed_by_flag_through_its_index(run, home, tmp_path, traced):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    given = copy.deepcopy(FIXTURE)
    given['elements'][2]['flag'] = 'missing'
    given['elements'][1]['joins'][0]['flag'] = 'broken'
    record_intake(run, folder, given['elements'])
    store = Store('proj')
    assert len(dump(store_file(home, store))['findings']) == 2
    broken = json.loads(run('map', 'findings', 'flag=broken', '--json', cwd=folder).stdout)['results']
    assert [(row['kind'], row['receiver_address'], row['provider_address'], row['flag']) for row in broken] == [
        ('join', 'code.timer.kitchen', 'code.alarm.audible', 'broken')]
    traced.clear()
    store.findings(flag='cruft')
    lines = [line for _, plan in plans(home, store, traced) for line in plan]
    assert any('findings_by_flag' in line for line in lines)
    view = json.loads(run('map', 'node', 'element:code.alarm.audible', '--json', cwd=folder).stdout)
    element = json.loads(run('map', 'element', 'code.alarm.audible', '--json', cwd=folder).stdout)
    assert element['flag'] == 'missing' and view['node']['kind'] == 'element'
