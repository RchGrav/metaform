"""Native element metadata survives refinement and map read surfaces."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import pytest

from metaform.data import Store
from metaform.modules.map import MODULE
from metaform.modules.map.tests.test_map import mapped as mapped  # noqa: PLC0414 fixture re-export

pytestmark = pytest.mark.kind('fixture')


@pytest.mark.req('LAYER-025')
@pytest.mark.req('MAP-059')
def test_refine_creates_updates_preserves_and_clears_native_element_metadata(run, mapped):
    store = Store('proj')
    layers = {layer.name for layer in store.layers(limit=0).results}
    nouns = {noun.name: noun for verb in MODULE.verbs if verb.name == 'refine' for noun in verb.nouns}
    for field in ('block', 'within'):
        assert nouns[field].kind == 'json' and nouns[field].schema == {'type': ['string', 'null']}

    def refine(*args):
        return json.loads(run('map', 'refine', 'address=code.alarm.snooze', 'reason=Capture the alarm structure.',
                              *args, '--json', cwd=mapped).stdout)

    def native(block, within):
        found = store.element('code.alarm.snooze')
        assert (found.block, found.within) == (block, within)

    def surfaces(block, within):
        native(block, within)
        element = json.loads(run('map', 'element', 'code.alarm.snooze', '--json', cwd=mapped).stdout)
        where = json.loads(run('map', 'where', 'code.alarm.snooze', '--json', cwd=mapped).stdout)
        for found in (element, where['element']):
            assert (found.get('block'), found.get('within')) == (block, within)
        xml = ET.fromstring(run('map', 'xml', 'address=code.alarm.snooze', cwd=mapped).stdout)
        [written] = xml.findall(".//element[@namespace_address='code.alarm.snooze']")
        for field, expected in (('block', block), ('within', within)):
            if expected is None:
                assert field not in written.attrib
            else:
                assert written.get(field) == expected

    created = refine('role=SE', 'name_length=2', 'name=snooze alarm',
                     'block="BLOCK_001"', 'within="code.timer.kitchen"')
    assert created['op'] == 'add' and created['notices'] == []
    element_id = store.element('code.alarm.snooze').id
    surfaces('BLOCK_001', 'code.timer.kitchen')
    refine('name=alarm snooze')
    native('BLOCK_001', 'code.timer.kitchen')
    refine('block="BLOCK_002"')
    native('BLOCK_002', 'code.timer.kitchen')
    refine('within="code.alarm.audible"')
    surfaces('BLOCK_002', 'code.alarm.audible')
    refine('block=null')
    native(None, 'code.alarm.audible')
    refine('within=null')
    surfaces(None, None)
    assert store.element('code.alarm.snooze').id == element_id
    assert {layer.name for layer in store.layers(limit=0).results} == layers
    assert not {'critic', 'checked'} & layers
    assert store.work(open=True, limit=0).results == ()
