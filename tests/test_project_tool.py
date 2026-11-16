"""The project tool's command engine over its LadybugDB store (src/metaform/project)."""
import pytest

from metaform.project import commands, store
from metaform.project.commands import run

pytestmark = pytest.mark.kind('fixture')

P = 'mashtrac'
WIDGET = f'{P}.code.masher.widget'
CS = f'{P}.code.protocol.network.tracker.cs'
WANT = {'element': WIDGET, 'why': 'Receive the mash data to relay it.', 'how': 'Prepared mash data packets.',
        'direction': 'receive'}
WIDGET_FIELDS = {'technical_name': 'widget masher', 'name': 'mashbox', 'role': 'Coupled Element',
                 'ref': './src/widgets/mashbox.c'}
CS_FIELDS = {'technical_name': 'cs tracker network protocol', 'name': 'mashtrac', 'role': 'Defining Element',
             'ref': './src/network/mashtrac.c'}
SPEC = f'{P}.overlay.specifications.project'
SPEC_DEFINITION = {'description': 'Prose the skeleton leaves out.', 'instruction': 'Write one block per heading.',
                   'title': {'type': 'text', 'rule': 'The heading of the block.', 'example': 'Purpose'},
                   'level': {'type': 'number', 'rule': 'The heading level, 1 to 4.', 'example': 1},
                   'draft': {'type': 'boolean', 'rule': 'True while unreviewed.', 'example': False, 'optional': True}}


@pytest.fixture
def mapped(home):
    """The founder's two mashtrac elements, the Defining Element wanting the Coupled Element."""
    assert run({'add': {WIDGET: WIDGET_FIELDS}}) == {'status': 'ok'}
    assert run({'add': {CS: {**CS_FIELDS, 'wants': [WANT]}}}) == {'status': 'ok'}
    return home


def refusal(answer):
    assert answer['status'] == 'error', answer
    return answer['code'], answer['remediation']


def snapshot():
    """Everything a read can see of the project."""
    found = run({'map': P})
    return found, {path: run({path: {}}) for path in found['addresses']}


def test_founders_worked_sequence(mapped):
    refused = run({'delete': {WIDGET: {}}})
    assert refused == {'delete': {WIDGET: {}}, 'status': 'error', 'code': 'DEPENDENCY_LOCK',
                       'message': f"cannot delete '{WIDGET}': '{CS}' still wants it. Remove that want first.",
                       'remediation': {'delete': {CS: {'wants': [WIDGET]}}}}
    assert run(refused['remediation']) == {'status': 'ok'}
    assert run({'orphaned': P}) == {WIDGET: WIDGET_FIELDS, CS: CS_FIELDS}
    assert run({WIDGET: {}}) == {WIDGET: {**WIDGET_FIELDS, 'wanted_by': [], 'overlays': {}}}
    assert run({'update': {WIDGET: {'role': None}}}) == {'status': 'ok'}
    assert 'role' not in run({WIDGET: {}})[WIDGET]
    assert run({'delete': {WIDGET: {}}}) == {'status': 'ok'}
    assert refusal(run({WIDGET: {}}))[0] == 'NOT_FOUND'
    assert f'{P}.code.masher' not in run({'map': P})['addresses']


def test_addressed_read_gives_wanted_by_and_overlay_counts(mapped):
    run({'add': {SPEC: SPEC_DEFINITION}})
    run({'add': {CS: {'project_specifications': [{'title': 'Purpose', 'level': 1}, {'title': 'Use', 'level': 2}]}}})
    assert run({WIDGET: {}})[WIDGET]['wanted_by'] == [CS]
    read = run({CS: {'wants': {}}})[CS]
    assert read['overlays'] == {'wants': 1, 'project_specifications': 2}
    assert read['wants'] == [WANT]
    assert 'project_specifications' not in read


def test_map_of_a_project_and_of_the_home(mapped):
    found = run({'map': P})
    assert found['wants'] == [[CS, WIDGET]]
    assert found['defining'] == [CS]
    assert found['addresses'] == sorted([WIDGET, CS])  # the bare branches above them are left out
    assert not [one for one in found['addresses'] if '.overlay' in one] and found['overlays'] == ['wants']
    assert run({'map': {}}) == {'projects': [P]}


def test_a_refused_first_add_leaves_no_project(home):
    code, _ = refusal(run({'add': {CS: {**CS_FIELDS, 'wants': [{**WANT, 'how': None}]}}}))
    assert code == 'FIELD_MISMATCH'
    assert run({'map': {}}) == {'projects': []}
    assert not store.location(home, P).exists()


def test_a_refused_write_changes_nothing(mapped):
    before = snapshot()
    command = {'add': {f'{P}.code.extra.part': {'technical_name': 'part extra', 'name': 'part', 'role':
                                                'Supporting Element', 'wants': [{'element': f'{P}.code.new.thing',
                                                                                 'why': 'w', 'direction': 'send'}]}}}
    assert refusal(run(command))[0] == 'WANT_INCOMPLETE'
    assert snapshot() == before


def test_a_store_failure_is_an_internal_error_and_rolls_back(mapped, monkeypatch):
    before = snapshot()

    def fail(*_):
        raise store.StoreError('disk full')
    with monkeypatch.context() as patch:
        patch.setattr(store.Store, 'add_want', fail)
        answer = run({'add': {f'{P}.code.extra.part': {'technical_name': 'part', 'name': 'part',
                                                       'role': 'Notable Element', 'wants': [WANT]}}})
    assert answer['code'] == 'INTERNAL_ERROR' and 'changed nothing' in answer['message']
    assert snapshot() == before


def test_strings_are_stored_as_data(mapped):
    hostile = "it's \"q\" '}); MATCH (n) DETACH DELETE n; //"
    assert run({'update': {WIDGET: {'name': hostile, 'ref': "$address` RETURN 1"}}}) == {'status': 'ok'}
    read = run({WIDGET: {}})[WIDGET]
    assert read['name'] == hostile and read['ref'] == "$address` RETURN 1"
    assert run({CS: {}})[CS]['name'] == 'mashtrac'


def test_defined_overlay_takes_valid_records_and_refuses_wrong_ones(mapped):
    assert run({'add': {SPEC: SPEC_DEFINITION}}) == {'status': 'ok'}
    definition = run({SPEC: {}})[SPEC]
    assert definition['key'] == 'project_specifications'
    assert definition['fields']['level'] == {'type': 'number', 'rule': 'The heading level, 1 to 4.', 'example': 1}
    assert run({'add': {CS: {'project_specifications': [{'title': 'Purpose', 'level': 1, 'ref': 'a.md'}]}}}) == {
        'status': 'ok'}
    wrong = {'add': {CS: {'project_specifications': [{'title': 'Use', 'level': 'two'}]}}}
    answer = run(wrong)
    assert answer['code'] == 'FIELD_MISMATCH'
    assert 'level' in answer['message'] and 'The heading level, 1 to 4.' in answer['message']
    # a wrong or missing value comes back as a placeholder; the example is shown in the message and never stored
    assert answer['remediation'] == {'add': {CS: {'project_specifications': [{'title': 'Use', 'level': '<level>'}]}}}
    assert 'Example: 1.' in answer['message']
    assert refusal(run({'add': {CS: {'project_specifications': [{'level': 2}]}}})) == (
        'FIELD_MISMATCH', {'add': {CS: {'project_specifications': [{'level': 2, 'title': '<title>'}]}}})
    before = snapshot()
    assert run(answer['remediation'])['code'] == 'FIELD_MISMATCH'  # run as it is, the placeholder is refused
    assert snapshot() == before
    assert run({CS: {'project_specifications': {}}})[CS]['project_specifications'] == [
        {'level': 1, 'title': 'Purpose', 'ref': 'a.md'}]


def test_update_replaces_an_overlays_records(mapped):
    run({'add': {SPEC: SPEC_DEFINITION}})
    run({'add': {CS: {'project_specifications': [{'title': 'A', 'level': 1}, {'title': 'B', 'level': 2}]}}})
    assert run({'update': {CS: {'project_specifications': [{'title': 'C', 'level': 1, 'draft': True}]}}}) == {
        'status': 'ok'}
    assert run({CS: {'project_specifications': {}}})[CS]['project_specifications'] == [
        {'draft': True, 'level': 1, 'title': 'C'}]


def test_a_field_of_an_overlay_with_records_cannot_be_deleted(mapped):
    run({'add': {SPEC: SPEC_DEFINITION}})
    run({'add': {CS: {'project_specifications': [{'title': 'A', 'level': 1}]}}})
    assert refusal(run({'delete': {f'{SPEC}.draft': {}}})) == (
        'DEPENDENCY_LOCK', {'update': {CS: {'project_specifications': None}}})
    assert run({'update': {CS: {'project_specifications': None}}}) == {'status': 'ok'}
    assert run({'delete': {f'{SPEC}.draft': {}}}) == {'status': 'ok'}
    assert 'draft' not in run({SPEC: {}})[SPEC]['fields']


def test_wants_definition_is_locked(mapped):
    assert refusal(run({'update': {f'{P}.overlay.wants.why': {'rule': 'Anything.'}}})) == (
        'OVERLAY_DEFINITION_LOCKED', None)
    assert refusal(run({'delete': {f'{P}.overlay.wants.ref': {}}}))[0] == 'OVERLAY_DEFINITION_LOCKED'


def test_two_definitions_cannot_share_a_key(mapped):
    run({'add': {f'{P}.overlay.notes_team': {'description': 'd', 'instruction': 'i'}}})
    assert refusal(run({'add': {f'{P}.overlay.team.notes': {'description': 'd', 'instruction': 'i'}}}))[0] == (
        'OVERLAY_NAME_COLLISION')
    assert refusal(run({'add': {f'{P}.overlay.name': {'description': 'd', 'instruction': 'i'}}}))[0] == (
        'OVERLAY_NAME_COLLISION')


def test_records_of_an_undefined_overlay_are_refused(mapped):
    assert refusal(run({'add': {CS: {'memory': [{'fact': 'x'}]}}})) == ('OVERLAY_NOT_DEFINED', {'map': P})


def test_records_need_an_element(mapped):
    code, remedy = refusal(run({'add': {f'{P}.code.masher': {'wants': [WANT]}}}))
    assert code == 'ELEMENT_NOT_IN_SKELETON'
    assert remedy['add'][f'{P}.code.masher']['technical_name'] == 'masher'


def test_one_of_several_wants_is_deleted_by_its_ref(mapped):
    run({'add': {CS: {'wants': [{**WANT, 'ref': 'a.c'}, {**WANT, 'ref': 'b.c'}]}}})
    assert run({'delete': {CS: {'wants': [{'element': WIDGET, 'ref': 'a.c'}]}}}) == {'status': 'ok'}
    assert [want.get('ref') for want in run({CS: {'wants': {}}})[CS]['wants']] == [None, 'b.c']


def test_removing_the_last_want_prunes_an_empty_wanted_element(mapped):
    run({'add': {CS: {'wants': [{**WANT, 'element': f'{P}.code.bus.event'}]}}})
    assert f'{P}.code.bus.event' in run({'map': P})['addresses']
    run({'delete': {CS: {'wants': [f'{P}.code.bus.event']}}})
    assert not {f'{P}.code.bus', f'{P}.code.bus.event'} & set(run({'map': P})['addresses'])


def test_update_merges_into_a_want(mapped):
    assert run({'update': {CS: {'wants': [{'element': WIDGET, 'direction': 'both'}]}}}) == {'status': 'ok'}
    assert run({CS: {'wants': {}}})[CS]['wants'] == [{**WANT, 'direction': 'both'}]
    code, remedy = refusal(run({'update': {CS: {'wants': [{'element': WIDGET, 'ref': 'x.c', 'direction': 'send'}]}}}))
    assert code == 'WANT_INCOMPLETE'
    assert remedy['update'][CS]['wants'][0]['why'] == '<why>'


@pytest.mark.parametrize(('command', 'code', 'remediation'), [
    ({'add': {}, 'map': {}}, 'FIELD_MISMATCH', None),
    ({'goto': WIDGET}, 'FIELD_MISMATCH', {WIDGET: {}}),
    ({'fetch': {}}, 'FIELD_MISMATCH', {'help': {}}),
    ({'add': {'mashtrac.lib.x': {'name': 'x'}}}, 'ROOT_SCOPE_NOT_ALLOWED', None),
    ({'add': {'Mashtrac.Code.x': {'name': 'x'}}}, 'FIELD_MISMATCH', {'add': {'mashtrac.code.x': {'name': 'x'}}}),
    ({'add': {WIDGET: {'refs': ['a.c']}}}, 'FIELD_MISMATCH', {'add': {WIDGET: {'ref': 'a.c'}}}),
    ({'add': {WIDGET: {'ref': ['a.c', 'b.c']}}}, 'FIELD_MISMATCH', None),
    ({'add': {WIDGET: {'uri': 'a.c'}}}, 'FIELD_MISMATCH', {'add': {WIDGET: {'ref': 'a.c'}}}),
    ({'add': {WIDGET: {'role': 'CE'}}}, 'ROLE_TAXONOMY_FAILURE', {'add': {WIDGET: {'role': 'Coupled Element'}}}),
    ({'add': {WIDGET: {'technical_name': 'mash widget'}}}, 'TECHNICAL_NAME_ALIGNMENT_FAILURE',
     {'add': {WIDGET: {'technical_name': 'widget masher'}}}),
    ({'add': {WIDGET: {'status': 'todo'}}}, 'FIELD_MISMATCH', {'add': {WIDGET: {'status': 'un_built'}}}),
    ({'add': {WIDGET: {'name': None}}}, 'FIELD_MISMATCH', {'add': {WIDGET: {'name': '<name>'}}}),
    ({'add': {CS: {'wants': [{'pe': WIDGET, 'op': 'w', 'ef': 'h', 'ifd': 'sends'}]}}}, 'FIELD_MISMATCH',
     {'add': {CS: {'wants': [{'element': WIDGET, 'why': 'w', 'how': 'h', 'direction': 'send'}]}}}),
    ({'add': {CS: {'dependencies': [WANT]}}}, 'FIELD_MISMATCH', {'add': {CS: {'wants': [WANT]}}}),
    ({'add': {CS: {'wants': [{**WANT, 'element': 'other.code.x'}]}}}, 'FIELD_MISMATCH', None),
    ({'add': {CS: {'wants': [{**WANT, 'direction': 'sideways'}]}}}, 'FIELD_MISMATCH',
     {'add': {CS: {'wants': [{**WANT, 'direction': '<direction>'}]}}}),
    ({'add': {CS: {'wants': [{**WANT, 'refs': ['a.c', 'b.c']}]}}}, 'FIELD_MISMATCH',
     {'add': {CS: {'wants': [{**WANT, 'ref': 'a.c'}, {**WANT, 'ref': 'b.c'}]}}}),
    ({'delete': {f'{P}.code': {}}}, 'ELEMENTS_BENEATH', {'delete': {CS: {}}}),
    ({'update': {'nothing.code.x': {'name': 'x'}}}, 'NOT_FOUND', {'map': {}}),
    ({f'{P}.code.absent': {}}, 'NOT_FOUND', {'map': P}),
    ({WIDGET: {'memory': {}}}, 'OVERLAY_NOT_DEFINED', {'map': P}),
    ({'help': 'goto'}, 'FIELD_MISMATCH', {'help': {}}),
])
def test_refusal_code_and_remediation(mapped, command, code, remediation):
    before = snapshot()
    answer = run(command)
    assert (answer['code'], answer['remediation']) == (code, remediation), answer
    assert answer['message']
    assert snapshot() == before


def test_a_name_both_field_and_step_is_refused_without_remediation(mapped):
    assert refusal(run({'add': {f'{WIDGET}.name': {'name': 'n'}}})) == ('FIELD_ELEMENT_COLLISION', None)


def test_help_lists_names_and_explains_one(home):
    assert run({'help': {}})['help']['properties']['help']['enum'] == list(commands.texts.HELP_NAMES)
    assert run({'help': 'add'})['help']['add']['examples'][0] == {'add': {WIDGET: WIDGET_FIELDS}}


def test_a_path_without_the_project_name_is_refused_naming_what_is_missing():
    refused = run({'code.masher.widget': {}})
    assert refused['code'] == 'ROOT_SCOPE_NOT_ALLOWED' and 'no project named' in refused['message']
    assert refused['remediation'] is None
