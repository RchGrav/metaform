"""The project tool's command engine over its LadybugDB store (src/metaform/project)."""
import pytest

from metaform import home as metaform_home
from metaform.project import commands, owner, service, store

pytestmark = pytest.mark.kind('fixture')


def run(command, caller=''):
    """The command engine in this process, on the test's own home: what the service runs for each command."""
    return commands.perform(command, owner.of(metaform_home.home()), caller)


@pytest.fixture(autouse=True)
def owners_closed():
    """Each test's home has its own owner; it is closed when the test ends, with its databases and writer threads."""
    yield
    owner.close_all()


@pytest.fixture
def served(home):
    """A home whose commands go through its single-writer service, a process of its own, stopped when the test ends."""
    yield home
    service.stop(home)

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
    assert run({WIDGET: {}}) == {WIDGET: {**WIDGET_FIELDS, 'wants': [], 'wanted_by': [], 'overlays': []}}
    assert run({'update': {WIDGET: {'role': None}}}) == {'status': 'ok'}
    assert 'role' not in run({WIDGET: {}})[WIDGET]
    assert run({'delete': {WIDGET: {}}}) == {'status': 'ok'}
    assert refusal(run({WIDGET: {}}))[0] == 'NOT_FOUND'
    assert f'{P}.code.masher' not in run({'map': P})['addresses']


def test_addressed_read_gives_wants_wanted_by_and_the_overlays_held_there(mapped):
    run({'add': {SPEC: SPEC_DEFINITION}})
    run({'add': {CS: {'project_specifications': [{'title': 'Purpose', 'level': 1}, {'title': 'Use', 'level': 2}]}}})
    assert run({WIDGET: {}})[WIDGET]['wanted_by'] == [CS]
    read = run({CS: {}})[CS]
    # one rule in the answer as in the stored form: a list is an overlay, a plain value is a field, nothing else
    assert read['wants'] == [WANT] and read['overlays'] == ['project_specifications']
    assert 'project_specifications' not in read
    assert not [value for value in read.values() if isinstance(value, dict)]


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
    assert definition['level'] == {'type': 'number', 'rule': 'The heading level, 1 to 4.', 'example': 1}
    # read back in the form and the order it was written in
    assert [name for name in definition if isinstance(definition[name], dict)] == ['title', 'level', 'draft']
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
    refused = run({'delete': {f'{SPEC}.draft': {}}})
    # no corrected command is offered: the only one would remove records the delete did not ask to remove
    assert refusal(refused) == ('DEPENDENCY_LOCK', None) and '1 record at 1 address' in refused['message']
    assert run({'update': {CS: {'project_specifications': None}}}) == {'status': 'ok'}
    assert run({'delete': {f'{SPEC}.draft': {}}}) == {'status': 'ok'}
    assert 'draft' not in run({SPEC: {}})[SPEC]


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
    ({'fetch': {}}, 'NOT_FOUND', {'map': {}}),  # one word: not a command, and not a project of this home
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


def holding(database, gate):
    """A write that keeps the writer busy until `gate` is set, returned once the writer has begun it."""
    import threading
    begun = threading.Event()
    held = database.write('first', lambda opened: (begun.set(), gate.wait()))
    assert begun.wait(10)
    return held


def test_writes_from_many_threads_are_all_stored(home):
    import threading
    answers = []

    def writing(caller):
        for index in range(15):
            answers.append(run({'add': {f'{P}.code.part_{caller}.unit_{index}': {'name': f'{caller} {index}'}}},
                               caller=caller))

    threads = [threading.Thread(target=writing, args=(f'c{number}',)) for number in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert answers == [{'status': 'ok'}] * 120
    assert len(run({'map': P})['addresses']) == 120


def test_the_writer_serves_callers_in_turn_and_each_callers_writes_in_order(home, tmp_path):
    import threading
    database = owner.Database(tmp_path / 'turns.lbug', create='turns')
    gate, order = threading.Event(), []
    try:
        held = holding(database, gate)  # the writer is busy while the rest queue
        many = [database.write('busy', lambda opened, n=n: order.append(('busy', n))) for n in range(4)]
        late = database.write('late', lambda opened: order.append(('late', 0)))
        gate.set()
        for future in [held, *many, late]:
            future.result(timeout=10)
    finally:
        database.close()
    assert order == [('busy', 0), ('late', 0), ('busy', 1), ('busy', 2), ('busy', 3)]


def test_a_read_does_not_wait_for_a_write_in_progress(mapped):
    import threading
    owned = owner.of(mapped)
    started, release = threading.Event(), threading.Event()

    def slow(opened):
        opened.put_element('code.pending', {'name': 'not yet'})
        started.set()
        release.wait()

    writing = threading.Thread(target=lambda: owned.write(P, 'slow', slow))
    writing.start()
    try:
        assert started.wait(10)
        found = run({'map': P})  # answered from the last committed state while the write is still open
        assert f'{P}.code.pending' not in found['addresses'] and WIDGET in found['addresses']
    finally:
        release.set()
        writing.join()
    assert f'{P}.code.pending' in run({'map': P})['addresses']


def test_processes_writing_at_once_are_all_stored_through_the_one_service(served, tmp_path):
    import subprocess
    import sys
    script = tmp_path / 'writer.py'
    script.write_text(
        'import sys\n'
        'from pathlib import Path\n'
        'from metaform.project.commands import run\n'
        'for n in range(30):\n'
        "    answer = run({'add': {f'mashtrac.code.from_{sys.argv[2]}.unit_{n}': {'name': str(n)}}}, "
        'home=Path(sys.argv[1]))\n'
        "    assert answer == {'status': 'ok'}, answer\n")
    writers = [subprocess.Popen([sys.executable, str(script), str(served), str(number)]) for number in range(4)]
    assert [writer.wait(timeout=120) for writer in writers] == [0, 0, 0, 0]
    assert len(commands.run({'map': P}, home=served)['addresses']) == 120


def test_only_the_service_holds_the_databases(served):
    assert commands.run({'add': {WIDGET: WIDGET_FIELDS}}, home=served) == {'status': 'ok'}
    with pytest.raises(owner.Owned):  # this process is a caller: the service is the owner
        owner.Owner(served)
    assert commands.run({WIDGET: {}}, home=served)[WIDGET]['name'] == 'mashbox'


def test_acknowledged_writes_survive_the_service_being_killed(served):
    import json
    import os
    import signal
    for number in range(20):
        assert commands.run({'add': {f'{P}.code.kept_{number}': {'name': str(number)}}}, home=served) == {
            'status': 'ok'}
    pid = json.loads((served / 'maps' / 'service.json').read_text())['pid']
    os.kill(pid, signal.SIGKILL if hasattr(signal, 'SIGKILL') else signal.SIGTERM)
    # a read after the service is gone starts a new one, which finds every write that was acknowledged
    assert len(commands.run({'map': P}, home=served)['addresses']) == 20


def test_waiting_writes_commit_together_and_a_refused_one_fails_alone(home, tmp_path):
    import threading
    told = []
    database = owner.Database(tmp_path / 'group.lbug', create='group', committed=told.append)
    gate, commits = threading.Event(), []
    real = database._writing.transaction

    def counted():
        commits.append(1)
        return real()

    database._writing.transaction = counted
    try:
        held = holding(database, gate)
        good = [database.write(f'c{n}', lambda opened, n=n: opened.put_element(f'code.unit_{n}', {'name': str(n)}))
                for n in range(10)]
        gate.set()
        for future in [held, *good]:
            future.result(timeout=10)
        assert len(commits) == 2  # the one that held the writer, then the ten that waited, in one transaction
        gate.clear()
        held = holding(database, gate)
        mixed = [database.write('a', lambda opened: opened.put_element('code.kept_a', {'name': 'a'})),
                 database.write('b', lambda opened: (_ for _ in ()).throw(ValueError('refused'))),
                 database.write('c', lambda opened: opened.put_element('code.kept_c', {'name': 'c'}))]
        gate.set()
        held.result(timeout=10)
        assert mixed[0].result(timeout=10) is None and mixed[2].result(timeout=10) is None
        # after the first two: the holder, the group of three that was rolled back, then each of the three alone
        assert len(commits) == 7
        with pytest.raises(ValueError):
            mixed[1].result(timeout=10)
        stored = database.read(lambda opened: [address for address, _ in opened.all_elements()])
        assert {'code.kept_a', 'code.kept_c'} <= set(stored) and len(stored) == 12
    finally:
        database.close()
    # each commit that stored writes is told once, however many writes it held: the holder and the group of ten,
    # then the holder and the three run alone, of which two were stored
    assert told == ['group'] * 4


def test_a_write_sent_again_with_the_same_request_id_is_done_once(mapped):
    run({'add': {SPEC: SPEC_DEFINITION}})
    owned = owner.of(metaform_home.home())
    record = {'add': {CS: {'project_specifications': [{'title': 'Purpose', 'level': 1}]}}}
    for _ in range(3):  # the caller never saw the answer, so it sends the same write again and again
        assert commands.perform(record, owned, 'c', 'request-1') == {'status': 'ok'}
    assert len(run({CS: {'project_specifications': {}}})[CS]['project_specifications']) == 1
    assert commands.perform(record, owned, 'c', 'request-2') == {'status': 'ok'}  # a new write appends
    assert len(run({CS: {'project_specifications': {}}})[CS]['project_specifications']) == 2
    refused = commands.perform({'add': {CS: {'role': 'DE'}}}, owned, 'c', 'request-3')
    assert refused['status'] == 'error'  # a refused write stores no id: it is refused the same way each time
    assert commands.perform({'add': {CS: {'role': 'Defining Element'}}}, owned, 'c', 'request-3') == {'status': 'ok'}


def test_many_callers_in_one_process_reach_the_service_at_once(served):
    import threading
    failures = []

    def writing(number):
        for index in range(40):
            answer = commands.run({'add': {f'{P}.code.thread_{number}.unit_{index}': {'name': str(index)}}},
                                  home=served, caller=f'thread {number}')
            if answer != {'status': 'ok'}:
                failures.append(answer)

    threads = [threading.Thread(target=writing, args=(number,)) for number in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(120)
    assert not [thread for thread in threads if thread.is_alive()] and not failures
    assert len(commands.run({'map': P}, home=served)['addresses']) == 640


def test_a_write_after_the_service_was_killed_is_sent_again_to_a_new_one(served):
    import json
    import os
    import signal
    assert commands.run({'add': {WIDGET: WIDGET_FIELDS}}, home=served) == {'status': 'ok'}
    pid = json.loads((served / 'maps' / 'service.json').read_text())['pid']
    os.kill(pid, signal.SIGKILL if hasattr(signal, 'SIGKILL') else signal.SIGTERM)
    # this caller still holds its connection to the service that is gone; the write goes to a new one
    assert commands.run({'add': {CS: {**CS_FIELDS, 'wants': [WANT]}}}, home=served) == {'status': 'ok'}
    assert commands.run({'map': P}, home=served)['wants'] == [[CS, WIDGET]]


def test_the_project_root_holds_the_projects_own_fields(home):
    root = {'id': 'carverj-mashtrac-2026-10-31', 'name': 'Mashtrac Protocol', 'project': 'carverj/mashtrac'}
    assert run({'add': {P: root}}) == {'status': 'ok'}  # the first write makes the project
    assert run({P: {}}) == {P: root} and run({'map': {}}) == {'projects': [P]}
    assert run({'update': {P: {'project': None, 'name': 'Mashtrac'}}}) == {'status': 'ok'}
    assert run({P: {}}) == {P: {'id': root['id'], 'name': 'Mashtrac'}}
    assert refusal(run({'add': {P: {'role': 'Defining Element'}}})) == ('FIELD_MISMATCH', None)
    assert refusal(run({'delete': {P: {}}})) == ('FIELD_MISMATCH', None)
    assert refusal(run({'nosuch': {}})) == ('NOT_FOUND', {'map': {}})


def test_one_record_of_an_overlay_is_changed_or_removed_without_rewriting_the_list(mapped):
    run({'add': {SPEC: SPEC_DEFINITION}})
    blocks = [{'title': 'Purpose', 'level': 1}, {'title': 'Use', 'level': 2, 'draft': True}, {'title': 'Limits', 'level': 2}]
    run({'add': {CS: {'project_specifications': blocks}}})

    def stored():
        return run({CS: {'project_specifications': {}}})[CS]['project_specifications']

    # a record that gives its position is changed in place: the fields given are laid over it, null removes one
    assert run({'update': {CS: {'project_specifications': [{'position': 1, 'title': 'Usage', 'draft': None}]}}}) == {
        'status': 'ok'}
    assert stored() == [blocks[0], {'title': 'Usage', 'level': 2}, blocks[2]]
    before = stored()
    wrong = [{'position': 1, 'level': 'two'}, {'position': 9, 'title': 'x'}, {'position': 0, 'title': None}]
    for record in wrong:
        refused = run({'update': {CS: {'project_specifications': [record]}}})
        assert refusal(refused) == ('FIELD_MISMATCH', None)  # no corrected command: one would replace the list
    assert refusal(run({'update': {CS: {'project_specifications': [{'position': 0, 'title': 'a'}, {'title': 'b'}]}}}))
    assert stored() == before
    # records are removed by position, and the ones after them close up
    assert run({'delete': {CS: {'project_specifications': [0]}}}) == {'status': 'ok'}
    assert stored() == [{'title': 'Usage', 'level': 2}, blocks[2]]
    assert run({'update': {CS: {'project_specifications': [{'position': 1, 'title': 'Bounds'}]}}}) == {'status': 'ok'}
    assert stored()[1] == {'title': 'Bounds', 'level': 2}
    assert refusal(run({'delete': {CS: {'project_specifications': [5]}}})) == ('FIELD_MISMATCH', None)
    assert refusal(run({'add': {f'{P}.overlay.notes': {'description': 'd', 'instruction': 'i', 'position': {
        'type': 'number', 'rule': 'r', 'example': 1}}}}))[0] == 'FIELD_MISMATCH'  # the word is the tool's own


def test_a_display_reads_a_whole_project_once_and_clearing_removes_it(served):
    mapped = served
    assert commands.run({'add': {WIDGET: WIDGET_FIELDS}}, served) == {'status': 'ok'}
    assert commands.run({'add': {CS: {**CS_FIELDS, 'wants': [WANT]}}}, served) == {'status': 'ok'}
    drawn = commands.drawn(P, mapped)
    assert [element['address'] for element in drawn['elements'] if element.get('role')] == [WIDGET, CS]
    assert drawn['wants'] == [{'holder': CS, **WANT}]
    assert commands.drawn('nosuch', mapped) is None
    assert commands.run({'drawn': P}, served)['status'] == 'error'  # not a command of the tool
    assert commands.clear(P, mapped) is True
    assert commands.drawn(P, mapped) is None and commands.clear(P, mapped) is False
