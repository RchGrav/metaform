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


def fields_only(records):
    """Records as they were written: without the record id and revision the store gives each one (F02)."""
    return [{name: value for name, value in record.items() if name not in ('record', 'revision')} for record in records]


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
    assert not [one for one in found['addresses'] if '.overlay' in one] and found['overlays'] == ['memories', 'specification', 'tickets', 'wants']  # the overlays every project is given
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
    assert fields_only(run({CS: {'project_specifications': {}}})[CS]['project_specifications']) == [
        {'level': 1, 'title': 'Purpose', 'ref': 'a.md'}]


def test_update_replaces_an_overlays_records(mapped):
    run({'add': {SPEC: SPEC_DEFINITION}})
    run({'add': {CS: {'project_specifications': [{'title': 'A', 'level': 1}, {'title': 'B', 'level': 2}]}}})
    assert run({'update': {CS: {'project_specifications': [{'title': 'C', 'level': 1, 'draft': True}]}}}) == {
        'status': 'ok'}
    assert fields_only(run({CS: {'project_specifications': {}}})[CS]['project_specifications']) == [
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
    ({'add': {'Mashtrac.Code.x': {'name': 'x'}}}, 'NAME_ROUND_TRIP_FAILURE', {'add': {'mashtrac.code.x': {'name': 'x'}}}),
    ({'add': {WIDGET: {'refs': ['a.c']}}}, 'FIELD_MISMATCH', {'add': {WIDGET: {'ref': 'a.c'}}}),
    ({'add': {WIDGET: {'ref': ['a.c', 'b.c']}}}, 'FIELD_MISMATCH', None),
    ({'add': {WIDGET: {'uri': 'a.c'}}}, 'FIELD_MISMATCH', {'add': {WIDGET: {'ref': 'a.c'}}}),
    ({'add': {WIDGET: {'role': 'CE'}}}, 'ROLE_TAXONOMY_FAILURE', {'add': {WIDGET: {'role': 'Coupled Element'}}}),
    ({'add': {WIDGET: {'technical_name': 'mash widget'}}}, 'TECHNICAL_NAME_ALIGNMENT_FAILURE',
     {'add': {WIDGET: {'technical_name': 'widget masher'}}}),
    ({'add': {WIDGET: {'status': 'todo'}}}, 'FIELD_MISMATCH', {'add': {WIDGET: {'status': 'unbuilt'}}}),
    ({'add': {WIDGET: {'status': 'un_built'}}}, 'FIELD_MISMATCH', {'add': {WIDGET: {'status': 'unbuilt'}}}),
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
            answers.append(run({'add': {f'{P}.code.part_{caller}.unit{index}': {'name': f'{caller} {index}'}}},
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


def test_a_cypher_query_reads_the_graph_on_a_reader_and_never_writes(mapped, monkeypatch, tmp_path):
    """Decision t-legacy-keep: map cypher runs on a project store's graph, read only. A write is refused by the engine
    in the read-only transaction; what that lets through (a file written, a setting changed, the transaction ended, a
    file read) is refused before it; a query past its time limit is stopped, and the readers still answer."""
    owned = owner.of(mapped)
    found = commands.perform_cypher(P, 'MATCH (h:Element)-[w:Wants]->(e:Element) RETURN h.address, e.address, w.why',
                                    owned)
    assert found == {'columns': ['h.address', 'e.address', 'w.why'],
                     'rows': [['code.protocol.network.tracker.cs', 'code.masher.widget', WANT['why']]]}
    before = snapshot()
    written = tmp_path / 'out.csv'
    for query, code in (('MATCH (e:Element) SET e.name = "changed"', 'QUERY_REFUSED'),
                        ('MATCH (e:Element) DETACH DELETE e', 'QUERY_REFUSED'),
                        ('CREATE (e:Element {address: "code.new"})', 'QUERY_REFUSED'),
                        (f'COPY (MATCH (e:Element) RETURN e.address) TO "{written}"', 'QUERY_REFUSED'),
                        ('CALL threads=1', 'QUERY_REFUSED'),
                        ('COMMIT', 'QUERY_REFUSED'),
                        ('MATCH (e:Element) RETURN e.address; CREATE (e:Element {address: "code.new"})',
                         'QUERY_REFUSED'),
                        ('LOAD FROM "/etc/hostname" (file_format="csv") RETURN *', 'QUERY_REFUSED'),
                        ('MATCH (e:Element RETURN e', 'QUERY_INVALID')):
        assert refusal(commands.perform_cypher(P, query, owned)) == (code, None), query
    assert snapshot() == before and not written.exists()
    # a word inside a string or a name is no clause
    assert commands.perform_cypher(P, 'MATCH (load:Element) WHERE load.name = "x; COPY" RETURN load.address;',
                                   owned) == {'columns': ['load.address'], 'rows': []}
    counted = 'MATCH (e:Element) RETURN count(e)'
    count = commands.perform_cypher(P, counted, owned)['rows']
    monkeypatch.setattr(store, 'CYPHER_SECONDS', 0.001)
    slow = 'UNWIND range(1, 4000) AS a UNWIND range(1, 4000) AS b WITH a * b AS s WHERE s % 7 = 0 RETURN sum(s)'
    assert refusal(commands.perform_cypher(P, slow, owned)) == ('QUERY_TIMEOUT', None)
    monkeypatch.setattr(store, 'CYPHER_SECONDS', 30)
    for _ in range(owner.READERS + 1):  # every reader still answers, the one interrupted among them
        assert commands.perform_cypher(P, counted, owned)['rows'] == count


def test_processes_writing_at_once_are_all_stored_through_the_one_service(served, tmp_path):
    import subprocess
    import sys
    script = tmp_path / 'writer.py'
    script.write_text(
        'import sys\n'
        'from pathlib import Path\n'
        'from metaform.project.commands import run\n'
        'for n in range(30):\n'
        "    answer = run({'add': {f'mashtrac.code.from{sys.argv[2]}.unit{n}': {'name': str(n)}}}, "
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
        assert commands.run({'add': {f'{P}.code.kept{number}': {'name': str(number)}}}, home=served) == {
            'status': 'ok'}
    pid = json.loads((served / 'maps' / 'service.json').read_text())['pid']
    os.kill(pid, signal.SIGKILL if hasattr(signal, 'SIGKILL') else signal.SIGTERM)
    # a read after the service is gone starts a new one, which finds every write that was acknowledged
    assert len(commands.run({'map': P}, home=served)['addresses']) == 20


def test_waiting_writes_commit_together_and_a_refused_one_fails_alone(home, tmp_path):
    import threading
    told = []
    database = owner.Database(tmp_path / 'group.lbug', create='group',
                              committed=lambda name, kinds: told.append((name, kinds)))
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
        # twelve written, and their parent `code`, which the store makes so every element is reached from the root
        assert {'code', 'code.kept_a', 'code.kept_c'} <= set(stored) and len(stored) == 13
    finally:
        database.close()
    # each commit that stored writes is told once, however many writes it held: the holder and the group of ten,
    # then the holder and the three run alone, of which two were stored
    assert told == [('group', {'map'})] * 4  # each told with the kind of what it stored


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
            answer = commands.run({'add': {f'{P}.code.thread{number}.unit{index}': {'name': str(index)}}},
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
        return fields_only(run({CS: {'project_specifications': {}}})[CS]['project_specifications'])

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


def test_a_service_running_code_older_than_the_code_on_disk_is_replaced(served, monkeypatch):
    import json
    assert commands.run({'add': {WIDGET: WIDGET_FIELDS}}, served) == {'status': 'ok'}
    first = json.loads((served / 'maps' / 'service.json').read_text())['pid']
    service._LOCAL.__dict__.pop('held', None)  # a new caller, as another process is
    real, seen = service._code, []
    # the code on disk is no longer what the service runs, as the first caller after an update finds
    monkeypatch.setattr(service, '_code', lambda: real() if seen else seen.append(1) or 'changed')
    assert commands.run({WIDGET: {}}, served)[WIDGET]['name'] == 'mashbox'  # answered by a new service, data kept
    assert json.loads((served / 'maps' / 'service.json').read_text())['pid'] != first


def test_the_overlay_help_examples_are_commands_the_tool_accepts(mapped):
    define, write, read = commands.texts.HELP['overlay']['examples']
    assert run(define) == {'status': 'ok'} and run(write) == {'status': 'ok'}
    assert run(read)[f'{P}.overlay.concerns']['key'] == 'concerns'
    assert fields_only(run({WIDGET: {'concerns': {}}})[WIDGET]['concerns']) == write['add'][WIDGET]['concerns']
    refused = run({'add': {f'{P}.overlay.notes': {'fields': {'text': 'x'}}}})
    assert refusal(refused) == ('FIELD_MISMATCH', {'help': 'overlay'})


def test_reads_from_many_threads_share_a_few_connections_and_none_is_left_behind(mapped):
    from concurrent.futures import ThreadPoolExecutor
    database = owner.of(metaform_home.home())._open[P]

    def one(_):
        import threading
        answers = []
        thread = threading.Thread(target=lambda: answers.append(run({WIDGET: {}})))  # a caller's own thread, then gone
        thread.start()
        thread.join()
        return answers[0][WIDGET]['name']
    with ThreadPoolExecutor(16) as pool:
        assert set(pool.map(one, range(200))) == {'mashbox'}
    assert len(database._readers) <= owner.READERS and len(database._idle) == len(database._readers)


def test_every_project_is_given_tickets_and_memories_and_one_made_before_them_gains_them(mapped):
    assert run({f'{P}.overlay.tickets': {}})[f'{P}.overlay.tickets']['key'] == 'tickets'
    ticket = {'id': 't-1', 'title': 'Ring', 'task': 'Ring each timer as it ends.'}
    assert run({'add': {WIDGET: {'tickets': [ticket], 'memories': [
        {'entity': 'watch', 'entity_type': 'behaviour', 'observation': 'It loads the timers once.'}]}}}) == {'status': 'ok'}
    assert run({'update': {WIDGET: {'tickets': [{'position': 0, 'taken_by': 'claude'}]}}}) == {'status': 'ok'}
    assert fields_only(run({WIDGET: {'tickets': {}}})[WIDGET]['tickets']) == [{**ticket, 'taken_by': 'claude'}]
    assert refusal(run({'add': {WIDGET: {'tickets': [{**ticket, 'outcome': 'lost'}]}}}))[0] == 'FIELD_MISMATCH'
    # a project whose database was made before these overlays existed is given them when it is next opened
    owned = owner.of(metaform_home.home())
    owned.write(P, 't', lambda opened: [opened.delete_part(address) for address in list(opened.parts())
                                        if address.startswith('overlay.memories')] and opened.drop_overlay('memories'))
    owner.close_all()
    assert run({f'{P}.overlay.memories': {}})[f'{P}.overlay.memories']['key'] == 'memories'


def test_a_display_lists_every_record_of_one_overlay_across_the_project(served):
    for path, title in ((WIDGET, 'Ring'), (CS, 'Relay')):
        assert commands.run({'add': {path: {**(WIDGET_FIELDS if path == WIDGET else CS_FIELDS), 'tickets': [
            {'id': f't-{title}', 'title': title, 'task': 'Do it.'}]}}}, served) == {'status': 'ok'}
    assert fields_only(commands.overlay_records(P, 'tickets', served)) == [
        {'element': WIDGET, 'position': 0, 'id': 't-Ring', 'title': 'Ring', 'task': 'Do it.'},
        {'element': CS, 'position': 0, 'id': 't-Relay', 'title': 'Relay', 'task': 'Do it.'}]
    assert commands.overlay_records(P, 'memories', served) == [] and commands.overlay_records('nosuch', 'tickets', served) is None


def test_help_serves_the_intake_procedure_one_section_at_a_time(home):
    """`{"help": "intake"}` lists the sections of the intake procedure in reading order, and `{"help":
    "intake/<section>"}` returns one section's text; a name the procedure does not hold is refused with the command
    that lists them. Ported from the Rust form's `metaform-core/tests/help.rs`: it reads the list from the procedure
    itself and asserts nothing about which sections exist, what they are named, which are required or what they say,
    so the founder can edit the procedure without a test failing."""
    from metaform.project import intake
    sections = intake.sections()
    listing = run({'help': 'intake'})['help']['intake']
    assert listing['sections'] == [one.name for one in sections]
    assert listing['required'] == [one.name for one in sections if one.required]
    assert listing['when'] == {one.name: one.when for one in sections if one.when}
    for one in sections:
        assert run({'help': f'intake/{one.name}'}) == {'help': {f'intake/{one.name}': one.text}}
    unknown = run({'help': 'intake/no such section'})
    assert unknown['code'] == 'FIELD_MISMATCH' and unknown['remediation'] == {'help': 'intake'}


def opened_store(home):
    """The project's database, opened as the owner's writer opens it, after the owner has let it go."""
    owner.close_all()
    return store.Store(store.location(home, P))


def test_the_map_is_one_tree_from_its_root(mapped):
    """The Rust form's shape (R-4.16, `metaform-store/src/graph.rs`): the map reaches the project's root by `ROOT`, and
    every element is reached by exactly one `CONTAINS` from its parent address, a top-level element from the root."""
    opened = opened_store(mapped)
    try:
        assert opened._rows("MATCH (:Map {id: $id})-[:ROOT]->(r:Project) RETURN count(r)", id=P) == [[1]]
        edges = opened.tree()
        addresses = [address for address, _ in opened.all_elements()]
        parents: dict[str, list[str]] = {}
        for parent, child in edges:
            parents.setdefault(child, []).append(parent)
        for address in addresses:
            assert parents.get(address) == [address.rpartition('.')[0] or '.'], address
        assert opened.beneath('code.masher') == ['code.masher.widget']
    finally:
        opened.close()


def test_overlay_records_are_reached_from_their_element_and_go_with_it(mapped):
    """Each overlay record is reached from its element by `HOLDS`, and deleting the element removes them."""
    note = {f'{P}.overlay.notes': {'description': 'Notes.', 'instruction': 'Write a note.'},
            f'{P}.overlay.notes.text': {'type': 'text', 'rule': 'One sentence.', 'example': 'It works.'}}
    for path, fields in note.items():
        assert run({'add': {path: fields}}) == {'status': 'ok'}, path
    assert run({'add': {WIDGET: {'notes': [{'text': 'Kept.'}]}}}) == {'status': 'ok'}
    opened = opened_store(mapped)
    try:
        held = opened._rows('MATCH (e:Element)-[:HOLDS]->(r:ov_notes) RETURN e.address, r.f_text')
        assert held == [['code.masher.widget', 'Kept.']]
    finally:
        opened.close()
    assert run({'delete': {CS: {'wants': [WIDGET]}}}) == {'status': 'ok'}
    assert run({'delete': {WIDGET: {}}}) == {'status': 'ok'}
    opened = opened_store(mapped)
    try:
        assert opened._rows('MATCH (r:ov_notes) RETURN count(r)') == [[0]]
    finally:
        opened.close()


def test_a_database_made_before_the_tree_is_given_it_on_open(home):
    """A project database from before the tree and `HOLDS` were stored, with its root named `Root` and its records
    tied to elements by an address column, is brought to the graph's structure once, when the writer opens it."""
    path = store.location(home, P)
    path.parent.mkdir(parents=True, exist_ok=True)
    old = store._Engine(path)
    for statement in (('CREATE NODE TABLE Element(address STRING PRIMARY KEY, `technical_name` STRING, `name` STRING, '
                       '`role` STRING, `ref` STRING, `status` STRING)'),
                      'CREATE NODE TABLE Root(k STRING PRIMARY KEY, `id` STRING, `name` STRING, `project` STRING)',
                      ('CREATE NODE TABLE ov_notes(id SERIAL PRIMARY KEY, address STRING, position INT64, ref STRING, '
                       'f_text STRING)'),
                      "CREATE (:Root {k: 'root', name: 'Mashtrac'})",
                      "CREATE (:Element {address: 'code'})", "CREATE (:Element {address: 'code.loop.main'})",
                      "CREATE (:ov_notes {address: 'code.loop.main', position: 0, f_text: 'Kept.'})"):
        old.rows(statement, {})
    old.close()
    opened = store.Store(path)
    try:
        assert opened.root()['name'] == 'Mashtrac'
        assert opened.tree() == [('.', 'code'), ('code', 'code.loop'), ('code.loop', 'code.loop.main')]
        (kept,) = opened.records('notes', 'code.loop.main', ['text'])
        assert {name: kept[name] for name in ('ref', 'text', 'revision')} == {'ref': None, 'text': 'Kept.', 'revision': 1}
        assert str(kept['record']).startswith('r-')  # a record made before ids is given one, its content untouched
    finally:
        opened.close()
    again = store.Store(path)  # a second open finds the structure in place and changes nothing
    try:
        assert len(again.tree()) == 3
    finally:
        again.close()


def test_the_root_has_no_technical_name_and_overlay_records_are_a_list(mapped):
    """Two refusals as the Rust form gives them (`metaform-core/tests/rules.rs`), in this tool's paths: a technical
    name at the project's root, which is the project, and an overlay's records given as an object, alone or nested
    as steps, each with the corrected command; a name that is no overlay keeps the shape check's answer."""
    root = run({'update': {P: {'technical_name': 'project'}}})
    assert (root['code'], root['remediation']) == ('TECHNICAL_NAME_ALIGNMENT_FAILURE',
                                                   {'update': {P: {'technical_name': None}}})
    for path, fields in {f'{P}.overlay.notes': {'description': 'Notes.', 'instruction': 'Write a note.'},
                         f'{P}.overlay.notes.text': {'type': 'text', 'rule': 'One sentence.',
                                                     'example': 'It works.'}}.items():
        assert run({'add': {path: fields}}) == {'status': 'ok'}, path
    corrected = {'update': {WIDGET: {'notes': [{'text': 'an object'}]}}}
    for command in ({'update': {WIDGET: {'notes': {'text': 'an object'}}}},
                    {'update': {f'{P}.code.masher': {'widget': {'notes': {'text': 'an object'}}}}}):
        answer = run(command)
        assert (answer['code'], answer['remediation']) == ('FIELD_MISMATCH', corrected), command
    assert run(corrected) == {'status': 'ok'}
    other = run({'update': {WIDGET: {'cpp': {'note': 'not an overlay'}}}})
    assert other['code'] == 'FIELD_MISMATCH' and other['remediation'] is None


def test_the_rust_forms_refusal_table(mapped):
    """The table of `refusals_name_the_rule_and_change_nothing` in the Rust form's `metaform-core/tests/contract.rs`,
    each command in this tool's paths, led by the project's name. A row answers as the Rust form does, unless a later
    decision of the founder's changed it; each such row says which, and asserts this tool's answer."""
    def at(text):
        return f'{P}.{text}'
    def want(direction):
        return {'why': 'Relay it.', 'how': 'Supplies data.', 'direction': direction}
    roles = ('<Artifact Type, Defining Element, Supporting Element, Coupled Element, Notable Element, Vested '
             'Beneficiary, Upstream Dependency or Downstream Dependant>')
    table = [
        ({'add': {at('Code.relay'): {'role': 'Supporting Element'}}}, 'NAME_ROUND_TRIP_FAILURE',
         {'add': {at('code.relay'): {'role': 'Supporting Element'}}}),
        ({'update': {at('code.queue_2'): {'name': 'q'}}}, 'NAME_ROUND_TRIP_FAILURE',
         {'update': {at('code.queue2'): {'name': 'q'}}}),
        ({'add': {at('widgets.relay'): {'name': 'r'}}}, 'ROOT_SCOPE_NOT_ALLOWED', None),
        # a want's direction outside send, receive or both: the corrected command holds the field to fill, `<direction>`,
        # never an example value (the founder, 2026-11-16 03:09); the Rust form gave none
        ({'add': {at('code.relay'): {'wants': [{'element': WIDGET, **want('push')}]}}}, 'FIELD_MISMATCH',
         {'add': {at('code.relay'): {'wants': [{'element': WIDGET, **want('<direction>')}]}}}),
        # the procedure's "missing" is written unbuilt (the founder, 2026-11-17), as the intake's recording lines tell the agent
        ({'update': {WIDGET: {'status': 'missing'}}}, 'FIELD_MISMATCH', {'update': {WIDGET: {'status': 'unbuilt'}}}),
        ({'add': {}}, 'FIELD_MISMATCH', None),
        # no corrected command: the Rust form's removed the element's own field, which Fable's decision 18 found a fault
        ({'add': {f'{WIDGET}.name': {'name': 'n'}}}, 'FIELD_ELEMENT_COLLISION', None),
        ({'update': {at('code.relay'): {'wants': [{'element': at('code.other'), 'direction': 'send'}]}}},
         'WANT_INCOMPLETE',
         {'update': {at('code.relay'): {'wants': [{'element': at('code.other'), 'direction': 'send', 'why': '<why>',
                                                   'how': '<how>'}]}}}),
        ({'add': {at('code.relay'): {'name': 'r', 'technical_name': 'relay code extra'}}},
         'TECHNICAL_NAME_ALIGNMENT_FAILURE', {'add': {at('code.relay'): {'name': 'r', 'technical_name': 'relay'}}}),
        ({'add': {at('code.cache.response'): {'name': 'c', 'technical_name': 'cache response'}}},
         'TECHNICAL_NAME_ALIGNMENT_FAILURE',
         {'add': {at('code.cache.response'): {'name': 'c', 'technical_name': 'response cache'}}}),
        ({'update': {WIDGET: {'technical_name': 'masher widget'}}}, 'TECHNICAL_NAME_ALIGNMENT_FAILURE',
         {'update': {WIDGET: {'technical_name': 'widget masher'}}}),
        # layers are overlays (the founder, 2026-11-15 22:18), and a map is read by the project's name
        ({'update': {WIDGET: {'references': [{'path': './src/widgets/mashbox.c'}]}}}, 'OVERLAY_NOT_DEFINED',
         {'map': P}),
        ({'add': {at('code.relay'): {'role': 'Definitive'}}}, 'ROLE_TAXONOMY_FAILURE',
         {'add': {at('code.relay'): {'role': roles}}}),
        ({'delete': {at('code.protocol'): {}}}, 'ELEMENTS_BENEATH', {'delete': {CS: {}}}),
        ({at('code.nowhere'): {}}, 'NOT_FOUND', {'map': P}),
    ]
    before = snapshot()
    for command, code, remediation in table:
        answer = run(command)
        assert (answer.get('code'), answer.get('remediation')) == (code, remediation), command
    assert snapshot() == before  # a refused command changes nothing


def remember(tool, arguments, caller=''):
    """A memory tool called in this process, as the service answers it: its texts, and its result or error."""
    from metaform.project import memory_layer
    try:
        given = memory_layer.checked(tool, arguments)
    except memory_layer.MemoryError as error:
        return str(error), None
    answer = memory_layer.perform({'project': P, 'tool': tool, 'arguments': given}, owner.of(metaform_home.home()),
                                  caller)
    if answer['status'] != 'ok':
        return answer['message'], None
    return memory_layer.answer(tool, given, answer['result'])


def test_the_memory_layer_is_the_reference_with_the_maps_objects_as_entities(mapped):
    watch = {'name': 'watch command', 'entityType': 'behaviour', 'observations': ['rings each timer']}
    texts, made = remember('create_entities', {'entities': [watch, watch, {**watch, 'name': WIDGET}]})
    # the repeat and the element, which is an entity already, are skipped and said to be, as the reference says it
    assert made == {'entities': [watch], 'skipped': ['watch command', WIDGET]}
    assert texts[1] == ('Skipped 2 entities that already exist: watch command, mashtrac.code.masher.widget. Their '
                        'observations were not added; use add_observations for existing entities.')
    _, added = remember('add_observations', {'observations': [{'entityName': WIDGET, 'contents': ['mashes', 'mashes']}]})
    assert added == {'results': [{'entityName': WIDGET, 'addedObservations': ['mashes']}]}
    relation = {'from': 'watch command', 'to': WIDGET, 'relationType': 'reads'}
    assert remember('create_relations', {'relations': [relation, relation]})[1] == {'relations': [relation]}
    assert remember('create_relations', {'relations': [relation]})[1] == {'relations': []}
    assert remember('create_relations', {'relations': [{**relation, 'to': 'nothing'}]}) == (
        'Entity with name nothing not found', None)
    message, _ = remember('create_entities', {'entities': [{**watch, 'name': f'{P}.code.not.there'}]})
    assert message.startswith('Entity with name mashtrac.code.not.there not found')
    # the element reports its technical name as its type, so a search finds it by that too
    _, found = remember('search_nodes', {'query': 'MASHER'})
    assert found == {'entities': [{'name': WIDGET, 'entityType': 'widget masher', 'observations': ['mashes']}],
                     'relations': [relation]}
    _, opened = remember('open_nodes', {'names': [CS], 'observationLimit': 0})
    assert opened['entities'] == [{'name': CS, 'entityType': 'cs tracker network protocol', 'observations': [],
                                   'observationCount': 0}]
    assert remember('delete_relations', {'relations': [relation, {**relation, 'relationType': 'x'}]})[0] == [
        'Deleted 1 of 2 relations. The rest matched nothing.']
    assert remember('read_graph', {})[1] == {
        'entities': [watch, {'name': WIDGET, 'entityType': 'widget masher', 'observations': ['mashes']}],
        'relations': []}
    assert remember('search_nodes', {'query': 'x' * 2049})[0].startswith('Input validation error')


def test_memory_tied_to_an_object_the_map_no_longer_holds_is_hidden_and_shows_again(mapped):
    remember('create_entities', {'entities': [{'name': 'relay', 'entityType': 'part', 'observations': []}]})
    remember('add_observations', {'observations': [{'entityName': CS, 'contents': ['tracks the mash']}]})
    remember('create_relations', {'relations': [{'from': 'relay', 'to': CS, 'relationType': 'feeds'}]})
    assert run({'delete': {CS: {}}}) == {'status': 'ok'}
    assert remember('read_graph', {})[1] == {
        'entities': [{'name': 'relay', 'entityType': 'part', 'observations': []}], 'relations': []}
    assert remember('add_observations', {'observations': [{'entityName': CS, 'contents': ['x']}]})[0] == (
        'Entity with name mashtrac.code.protocol.network.tracker.cs not found')
    assert run({'add': {CS: CS_FIELDS}}) == {'status': 'ok'}
    assert remember('open_nodes', {'names': [CS]})[1] == {
        'entities': [{'name': CS, 'entityType': 'cs tracker network protocol', 'observations': ['tracks the mash']}],
        'relations': [{'from': 'relay', 'to': CS, 'relationType': 'feeds'}]}


def test_a_memory_write_is_announced_as_memory(tmp_path):
    told = []
    database = owner.Database(tmp_path / 'told.lbug', create='told',
                              committed=lambda name, kinds: told.append((name, kinds)))
    try:
        database.write('a', lambda opened: opened.put_memory_entity('relay', 'part', []), 'memory').result(timeout=10)
    finally:
        database.close()
    assert told == [('told', {'memory'})]


def test_clearing_a_map_keeps_its_memory_for_the_next_map(mapped):
    remember('create_entities', {'entities': [{'name': 'relay', 'entityType': 'part', 'observations': ['kept']}]})
    remember('add_observations', {'observations': [{'entityName': WIDGET, 'contents': ['mashes']}]})
    remember('create_relations', {'relations': [{'from': 'relay', 'to': WIDGET, 'relationType': 'feeds'}]})
    assert owner.of(metaform_home.home()).remove(P)
    assert P not in store.projects(metaform_home.home())  # no map: the project reads as cleared everywhere
    assert run({'add': {WIDGET: WIDGET_FIELDS}}) == {'status': 'ok'}  # the next map, with the element again
    assert remember('read_graph', {})[1] == {
        'entities': [{'name': 'relay', 'entityType': 'part', 'observations': ['kept']},
                     {'name': WIDGET, 'entityType': 'widget masher', 'observations': ['mashes']}],
        'relations': [{'from': 'relay', 'to': WIDGET, 'relationType': 'feeds'}]}
    assert not owner.kept_memory(store.location(metaform_home.home(), P)).exists()


def test_the_pages_layers_find_each_definition_by_its_key_with_underscores_inside_a_step(served):
    """F04: a definition whose step holds an underscore keeps its description on the page. Its key reversed back
    into steps names another address, demo.overlay.findings.review, so the page must look it up, not rebuild it."""
    from metaform.modules.web import project_map
    defined = {f'{P}.overlay.review_findings': 'Findings of a review.',
               f'{P}.overlay.design_notes.team': 'Notes the team keeps on a design.',
               SPEC: SPEC_DEFINITION['description']}
    assert commands.run({'add': {WIDGET: WIDGET_FIELDS}}, home=served) == {'status': 'ok'}
    for address, description in defined.items():
        fields = SPEC_DEFINITION if address == SPEC else {
            'description': description, 'instruction': 'One record a finding.',
            'title': {'type': 'text', 'rule': 'The finding in a line.', 'example': 'A leak'}}
        assert commands.run({'add': {address: fields}}, home=served) == {'status': 'ok'}
    record = {'title': 'A leak'}
    assert commands.run({'add': {WIDGET: {'review_findings': [record]}}}, home=served) == {'status': 'ok'}
    before = commands.run({WIDGET: {'review_findings': {}}}, home=served)

    found = {layer.name: layer.variable for layer in project_map.layers(P, 'base')}

    expected = {'base': "The project's map: its elements and what each wants of another.",
                'review_findings': 'Findings of a review.',
                'team_design_notes': 'Notes the team keeps on a design.',
                'project_specifications': SPEC_DEFINITION['description']}
    assert {name: found.get(name) for name in expected} == expected  # the store's own overlays are listed beside them
    for address, description in defined.items():  # each definition is still read at the address it was written at
        assert commands.run({address: {}}, home=served)[address]['description'] == description
    assert commands.run({WIDGET: {'review_findings': {}}}, home=served) == before


def test_a_definition_change_that_would_leave_records_outside_it_is_refused(mapped):
    """F03: narrowing choices, making a field required, adding a required field or changing text to address while
    stored records break the change is refused with the records named, and nothing changes. Compatible changes, and
    the same change once the records are fixed, go through."""
    notes = f'{P}.overlay.notes'
    assert run({'add': {notes: {'description': 'd', 'instruction': 'i',
                                'title': {'type': 'text', 'rule': 'r', 'example': 'x'},
                                'kind': {'type': 'alpha | beta', 'rule': 'r', 'example': 'alpha'},
                                'extra': {'type': 'text', 'rule': 'r', 'example': 'x', 'optional': True}}}}) == {
        'status': 'ok'}
    assert run({'add': {CS: {'notes': [{'title': 'B', 'kind': 'beta'}, {'title': 'C', 'kind': 'beta', 'extra': 'e'}]}}}
               ) == {'status': 'ok'}
    before = snapshot(), run({notes: {}})
    for change, wrong in (({'kind': {'type': 'alpha | gamma', 'rule': 'r', 'example': 'alpha'}}, 'kind'),
                          ({'extra': {'type': 'text', 'rule': 'r', 'example': 'x', 'optional': False}}, 'extra'),
                          ({'owner': {'type': 'text', 'rule': 'r', 'example': 'x'}}, 'owner'),
                          ({'title': {'type': 'address', 'rule': 'r', 'example': WIDGET}}, 'title')):
        answer = run({'update': {notes: change}})
        assert answer['code'] == 'DEFINITION_INCOMPATIBLE', (change, answer)
        assert f"'{CS}' position 0 ({wrong})" in answer['message']
        if wrong == 'owner':  # a new required field: defined optional first, since records cannot take it before
            assert answer['remediation'] == {'update': {notes: {'owner': {
                'type': 'text', 'rule': 'r', 'example': 'x', 'optional': True}}}}
            optional_first = answer['remediation']
        else:
            assert answer['remediation'] == {'update': {CS: {'notes': [{'position': 0, wrong: f'<{wrong}>'}]}}}
        assert (snapshot(), run({notes: {}})) == before
    assert run(optional_first) == {'status': 'ok'}  # the remedy offered for a new required field is taken
    # compatible changes leave every record valid
    assert run({'update': {notes: {'instruction': 'One note a line.'}}}) == {'status': 'ok'}
    assert run({'update': {notes: {'seen': {'type': 'boolean', 'rule': 'r', 'example': True, 'optional': True}}}}) == {
        'status': 'ok'}
    # once the records meet it, the same change is taken
    assert run({'update': {CS: {'notes': [{'position': 0, 'extra': 'given'}]}}}) == {'status': 'ok'}
    assert run({'update': {notes: {'extra': {'type': 'text', 'rule': 'r', 'example': 'x', 'optional': False}}}}) == {
        'status': 'ok'}


def test_an_edit_from_a_stale_read_is_refused_instead_of_landing_on_another_record(mapped):
    """F02: each record keeps an id for its life and a revision counted up on each change. An edit that names the
    record and revision it read is refused when the record moved, went or changed, and nothing changes; an edit by
    position alone is taken as before. A delete may name records by id."""
    run({'add': {SPEC: SPEC_DEFINITION}})
    run({'add': {CS: {'project_specifications': [{'title': t, 'level': 1} for t in 'ABC']}}})

    def stored():
        return run({CS: {'project_specifications': {}}})[CS]['project_specifications']

    a, b, c = stored()
    assert len({a['record'], b['record'], c['record']}) == 3 and a['revision'] == b['revision'] == c['revision'] == 1
    assert run({'delete': {CS: {'project_specifications': [0]}}}) == {'status': 'ok'}  # another client removes A
    stale = {'update': {CS: {'project_specifications': [
        {'position': 1, 'record': b['record'], 'revision': 1, 'title': 'B2'}]}}}
    before = stored()
    moved = run(stale)
    assert moved['code'] == 'RECORD_MOVED' and stored() == before  # C was not touched
    assert moved['remediation'] == {'update': {CS: {'project_specifications': [
        {'position': 0, 'record': b['record'], 'revision': 1, 'title': 'B2'}]}}}
    assert run(moved['remediation']) == {'status': 'ok'}
    b2, c_now = stored()
    assert (b2['title'], b2['record'], b2['revision']) == ('B2', b['record'], 2) and c_now == c
    changed = run({'update': {CS: {'project_specifications': [
        {'position': 0, 'record': b['record'], 'revision': 1, 'title': 'B3'}]}}})
    assert changed['code'] == 'RECORD_CHANGED' and stored() == [b2, c_now]
    gone = run({'update': {CS: {'project_specifications': [{'position': 0, 'record': a['record'], 'title': 'A2'}]}}})
    assert gone['code'] == 'RECORD_GONE' and stored() == [b2, c_now]
    assert run({'delete': {CS: {'project_specifications': [a['record']]}}})['code'] == 'RECORD_GONE'
    # by position alone, as before
    assert run({'update': {CS: {'project_specifications': [{'position': 1, 'title': 'C2'}]}}}) == {'status': 'ok'}
    assert run({'delete': {CS: {'project_specifications': [c['record']]}}}) == {'status': 'ok'}
    assert fields_only(stored()) == [{'title': 'B2', 'level': 1}]


def test_the_page_moves_and_removes_a_ticket_by_its_record_id(served):
    """Phase 3: the board's changes name the record they found, so a card moved by another writer meanwhile is
    refused rather than another card changed (F02)."""
    from metaform.modules.web import project_map
    assert commands.run({'add': {WIDGET: {**WIDGET_FIELDS, 'tickets': [
        {'id': 't-a', 'title': 'A', 'task': 'Do A.'}, {'id': 't-b', 'title': 'B', 'task': 'Do B.'}]}}}, served) == {
        'status': 'ok'}
    assert project_map.move_ticket(P, 't-b', 'doing', 'claude')['taken_by'] == 'claude'
    assert project_map.remove_ticket(P, 't-a')['id'] == 't-a'
    (left,) = commands.overlay_records(P, 'tickets', served)
    assert (left['id'], left['taken_by'], left['position'], left['revision']) == ('t-b', 'claude', 0, 2)
    stale = {**left, 'position': 0, 'record': 'r-0000000000000000'}  # a record that is no longer there
    with pytest.raises(Exception, match='no longer there'):
        project_map._changed(P, stale, {'note': 'lands nowhere'})
    assert commands.overlay_records(P, 'tickets', served) == [left]


def test_map_work_reads_and_writes_the_tickets_of_a_project_in_the_project_store(served):
    """Phase 3: `map work` for a project held in the project store works on its tickets overlay, where the page's
    board reads them; what has no field there yet is refused by name, never dropped."""
    from metaform.module import Stop
    from metaform.modules.map.project_work import project_work
    assert commands.run({'add': {WIDGET: WIDGET_FIELDS}}, served) == {'status': 'ok'}
    node = 'element:code.masher.widget'
    made = project_work(P, 'add', {'node': node, 'title': 'Ring', 'task': 'Ring each timer as it ends.'})
    other = project_work(P, 'add', {'node': node, 'title': 'Snooze', 'task': 'Let a ring be snoozed.'})
    assert (made['title'], made['address'], made['status'], made['revision']) == ('Ring', 'code.masher.widget', 'open', 1)
    project_work(P, 'remove', {'id': made['id']})  # the second ticket moves to position 0
    taken = project_work(P, 'take', {'id': other['id'], 'by': 'claude'})  # by=, as the command line names it
    assert (taken['id'], taken['taken_by'], taken['position']) == (other['id'], 'claude', 0)
    project_work(P, 'edit', {'id': other['id'], 'note': 'Snooze added.'})
    done = project_work(P, 'done', {'id': other['id'], 'resolution': 'Snooze works.', 'why': 'Tested.'})
    assert (done['status'], done['outcome'], done['note']) == (
        'done', 'completed', 'Snooze added.\n\nResolution: Snooze works. Why: Tested.')  # the note is kept
    assert project_work(P, 'list', {})['results'] == []
    assert [row['id'] for row in project_work(P, 'list', {'open': False})['results']] == [other['id']]
    for op, nouns, said in (('plan', {'id': other['id']}, 'op=plan has no place'),
                            ('take', {'id': other['id']}, 'names who takes'),
                            ('add', {'node': node, 'title': 't', 'task': 't', 'condition': 'broken'}, 'condition'),
                            ('add', {'receiver': 'code.masher.widget', 'title': 't', 'task': 't'}, 'receiver'),
                            ('read', {'id': 't-none'}, 'No ticket')):
        with pytest.raises(Stop, match=said):
            project_work(P, op, nouns)


def test_the_page_reads_memory_from_the_memory_layer_the_memory_tools_write(served):
    """F05: the page's memories are the memory layer's graph, not the memories overlay: an observation an agent adds
    to an element with the memory tools shows at that element, with the relations among entities."""
    from metaform import project as project_store
    from metaform.modules.web import project_map
    assert commands.run({'add': {WIDGET: WIDGET_FIELDS}}, served) == {'status': 'ok'}
    assert project_store.memory(P, 'add_observations', {'observations': [
        {'entityName': WIDGET, 'contents': ['It loads the timers once.']}]}, served)['status'] == 'ok'
    assert project_store.memory(P, 'create_entities', {'entities': [
        {'name': 'watch', 'entityType': 'behaviour', 'observations': ['It polls.']}]}, served)['status'] == 'ok'
    assert project_store.memory(P, 'create_relations', {'relations': [
        {'from': 'watch', 'to': WIDGET, 'relationType': 'reads'}]}, served)['status'] == 'ok'
    shown = project_map.memories(P)
    by_name = {entity['name']: entity for entity in shown['entities']}
    assert by_name[WIDGET]['observations'] == [{'content': 'It loads the timers once.', 'by': ''}]
    assert by_name['watch']['entityType'] == 'behaviour'
    assert shown['relations'] == [{'from': 'watch', 'to': WIDGET, 'relationType': 'reads'}]
    assert [join['address'] for join in shown['joins']] == ['code.masher.widget']
    assert shown['overlay_records'] == []


def test_the_walk_beneath_an_element_reaches_every_level_however_deep(mapped):
    """F14: a branch more than 30 levels deep is walked whole; the walk once stopped at 30 and returned what it had."""
    deep = f'{P}.code.' + '.'.join(f's{n}' for n in range(40))
    assert run({'add': {deep: {'technical_name': 's39 s38', 'name': 'deep', 'role': 'Notable Element'}}}) == {
        'status': 'ok'}
    owned = owner.of(metaform_home.home())
    below = owned.read(P, lambda opened: opened.beneath('code.s0'))
    assert len(below) == 39 and below[-1] == deep[len(P) + 1:]
    # deleting the top of it is refused while elements are beneath, naming the deepest
    answer = run({'delete': {f'{P}.code.s0': {}}})
    assert answer['code'] == 'ELEMENTS_BENEATH' and answer['remediation'] == {'delete': {deep: {}}}


def test_an_upgrade_that_would_leave_the_graph_incomplete_changes_nothing_and_says_why(home, mapped):
    """F15: an upgrade is finished only when the graph it leaves is whole, checked inside its transaction. A record
    an old database ties to no element would be left unheld, so the upgrade is refused by name and the old database
    is left as it was; a whole graph reports nothing."""
    assert owner.of(metaform_home.home()).read(P, lambda opened: opened.integrity()) == []
    owner.close_all()
    path = store.location(home, 'oldproject')
    path.parent.mkdir(parents=True, exist_ok=True)
    old = store._Engine(path)
    for statement in (('CREATE NODE TABLE Element(address STRING PRIMARY KEY, `technical_name` STRING, `name` STRING, '
                       '`role` STRING, `ref` STRING, `status` STRING)'),
                      'CREATE NODE TABLE Root(k STRING PRIMARY KEY, `id` STRING, `name` STRING, `project` STRING)',
                      ('CREATE NODE TABLE ov_notes(id SERIAL PRIMARY KEY, address STRING, position INT64, ref STRING, '
                       'f_text STRING)'),
                      "CREATE (:Root {k: 'root', name: 'Old'})", "CREATE (:Element {address: 'code'})",
                      "CREATE (:ov_notes {address: 'code.gone', position: 0, f_text: 'Held by nothing.'})"):
        old.rows(statement, {})
    old.close()
    with pytest.raises(store.StoreError, match='notes records are not held by exactly one element'):
        store.Store(path)
    again = store._Engine(path)
    try:  # left as it was: still the old root, no map, the record's text untouched
        tables = {str(row[0]) for row in again.rows('CALL show_tables() RETURN name', {})}
        assert 'Root' in tables and 'Map' not in tables and 'MemoryEntity' not in tables
        assert 'record' not in {str(row[0]) for row in again.rows("CALL table_info('ov_notes') RETURN name", {})}
        assert again.rows('MATCH (r:ov_notes) RETURN r.f_text', {}) == [['Held by nothing.']]
    finally:
        again.close()


def test_a_ticket_id_names_one_ticket_and_a_claim_is_exclusive(served):
    """F09: a command that would leave one ticket id on two tickets is refused whole; a ticket another agent holds is
    not taken again, and of two claims made from the same read only the first is taken."""
    from metaform.module import Stop
    from metaform.modules.map.project_work import project_work
    ticket = {'id': 't-1', 'title': 'Ring', 'task': 'Ring.'}
    assert commands.run({'add': {WIDGET: {**WIDGET_FIELDS, 'tickets': [ticket]}}}, served) == {'status': 'ok'}
    assert commands.run({'add': {CS: CS_FIELDS}}, served) == {'status': 'ok'}
    before = commands.overlay_records(P, 'tickets', served)
    for command in ({'add': {CS: {'tickets': [ticket]}}},
                    {'add': {WIDGET: {'tickets': [{**ticket, 'title': 'Again'}]}}},
                    {'update': {CS: {'tickets': [ticket, {**ticket, 'title': 'Twice'}]}}}):
        answer = commands.run(command, served)
        assert answer['code'] == 'TICKET_ID_TAKEN', command
        assert commands.overlay_records(P, 'tickets', served) == before
    assert project_work(P, 'take', {'id': 't-1', 'agent': 'claude'})['taken_by'] == 'claude'
    with pytest.raises(Stop, match='taken by claude'):
        project_work(P, 'take', {'id': 't-1', 'by': 'codex'})  # as the command line sends it
    assert project_work(P, 'take', {'id': 't-1', 'agent': 'claude'})['taken_by'] == 'claude'  # its holder again
    (read,) = commands.overlay_records(P, 'tickets', served)  # two claims made from this one read
    claim = {'position': 0, 'record': read['record'], 'revision': read['revision']}
    assert commands.run({'update': {WIDGET: {'tickets': [{**claim, 'taken_by': 'a'}]}}}, served) == {'status': 'ok'}
    assert commands.run({'update': {WIDGET: {'tickets': [{**claim, 'taken_by': 'b'}]}}}, served)['code'] == (
        'RECORD_CHANGED')


def test_a_list_written_back_keeps_its_records_ids_and_record_and_revision_are_no_field_names(mapped):
    """F02, after verification: a whole list written back from a read keeps each record's id at its next revision,
    and a new record in it gets a new id; a definition cannot name a field record or revision."""
    run({'add': {SPEC: SPEC_DEFINITION}})
    run({'add': {CS: {'project_specifications': [{'title': 'A', 'level': 1}, {'title': 'B', 'level': 1}]}}})
    a, b = run({CS: {'project_specifications': {}}})[CS]['project_specifications']
    assert run({'update': {CS: {'project_specifications': [b, {**a, 'title': 'A2'}, {'title': 'C', 'level': 2}]}}}) == {
        'status': 'ok'}
    b2, a2, c = run({CS: {'project_specifications': {}}})[CS]['project_specifications']
    assert (b2['record'], b2['revision'], a2['record'], a2['revision'], a2['title']) == (
        b['record'], 2, a['record'], 2, 'A2')
    assert c['record'] not in (a['record'], b['record']) and c['revision'] == 1
    for name in ('record', 'revision'):
        answer = run({'add': {f'{P}.overlay.notes': {'description': 'd', 'instruction': 'i',
                                                     name: {'type': 'text', 'rule': 'r', 'example': 'x'}}}})
        assert answer['status'] == 'error' and "tool's word" in answer['message'], name


def test_a_map_verb_refuses_on_a_project_whose_map_is_in_the_project_store(served):
    """Phase 3, F01: the old store's map is not a store project's map, so its verbs refuse there naming the project
    tool, instead of answering from an empty map; work, boards and guide are answered, and other projects as before."""
    from types import SimpleNamespace

    from metaform.module import Stop
    from metaform.modules.map import MODULE
    assert commands.run({'add': {WIDGET: WIDGET_FIELDS}}, served) == {'status': 'ok'}
    verbs = {verb.name: verb for verb in MODULE.verbs}
    in_store, elsewhere = SimpleNamespace(store=SimpleNamespace(project_id=P)), SimpleNamespace(store=None)
    with pytest.raises(Stop, match=f"{P}'s map is in the project store, so `map where`"):
        verbs['where'].run(in_store)
    for name in ('work', 'boards', 'guide', 'ask', 'reply', 'reopen', 'messages', 'cypher'):
        assert verbs[name].run.__name__ != 'refused_in_the_store', name
    assert verbs['where'].run.__name__ == 'refused_in_the_store'
    with pytest.raises(Exception) as raised:  # no store: the verb's own code runs, as before
        verbs['where'].run(elsewhere)
    assert "map is in the project store" not in str(raised.value)


def test_the_specification_round_trips_through_its_document_and_refuses_what_would_break_it(served):
    """Phase 4, F06: every project is given the specification overlay; blocks that would break the round trip are
    refused whole; export, edit, import and export again give the edited document byte for byte; a stale or broken
    document changes nothing."""
    from metaform import project as project_store
    for path, fields in ((WIDGET, WIDGET_FIELDS), (CS, {**CS_FIELDS, 'wants': [WANT]})):
        assert commands.run({'add': {path: fields}}, served) == {'status': 'ok'}
    assert commands.run({f'{P}.overlay.specification': {}}, served)[f'{P}.overlay.specification']['key'] == (
        'specification')
    blocks = [{'text': 'The mash box relays packets.'},
              {'level': 1, 'title': 'Purpose', 'code': 'R-1', 'text': 'Relay each packet as it arrives.'},
              {'level': 2, 'title': 'Limits', 'text': 'One packet at a time.'}]
    assert commands.run({'add': {WIDGET: {'specification': blocks}}}, served) == {'status': 'ok'}

    def stored():
        return fields_only(commands.run({WIDGET: {'specification': {}}}, served)[WIDGET]['specification'])
    for wrong, code in (([{'level': 2, 'title': 'Skips'}], 'HEADING_LEVEL_INVALID'),
                        ([{'level': 1, 'title': 'T', 'text': 'line\n## a heading'}], 'HEADING_IN_TEXT'),
                        ([{'level': 1, 'title': 'T'}, {'text': 'late intro'}], 'FIELD_MISMATCH'),
                        ([{'level': 1, 'title': 'T', 'code': 'r-1'}], 'CODE_TAKEN')):
        answer = commands.run({'add': {CS: {'specification': wrong}}}, served)
        assert answer.get('code') == code, (wrong, answer)
    assert stored() == blocks

    exported = project_store.specification_document(P, home=served)['document']
    assert exported.startswith(f'# {P}\n\n## mashbox (`{WIDGET}`)\n\nRole: Coupled Element.')
    assert '### `R-1` Purpose\n\nRelay each packet as it arrives.\n\n#### Limits' in exported
    assert f'- `{CS}` (mashtrac) requires `{WIDGET}` (mashbox) in order to receive the mash data to relay it, ' in (
        exported)
    assert project_store.specification_document(P, exported, served) == {'status': 'ok', 'changed': []}

    edited = exported.replace('One packet at a time.', 'One packet at a time, oldest first.\n\n### Errors\n\n'
                                                        'A packet that fails is dropped.')
    assert project_store.specification_document(P, edited, served) == {'status': 'ok', 'changed': [WIDGET]}
    assert project_store.specification_document(P, home=served)['document'] == edited
    assert stored()[-1] == {'level': 1, 'title': 'Errors', 'text': 'A packet that fails is dropped.'}

    before = project_store.specification_document(P, home=served)['document']
    stale = before.replace('Role: Coupled Element.', 'Role: Defining Element.')
    for broken in (stale, before + '\n```\nunclosed\n', before.replace(f'# {P}', '# other', 1)):
        answer = project_store.specification_document(P, broken.replace('dropped.', 'kept.'), served)
        assert answer['code'] == 'DOCUMENT_REFUSED', answer
    assert project_store.specification_document(P, home=served)['document'] == before


def test_an_elements_read_carries_its_specification_so_an_agent_reads_its_purpose_first(mapped):
    """Phase 4 step 4: the project tool's read of an element brings its specification blocks unasked, as it brings
    its wants; an element with none is read as before."""
    blocks = [{'level': 1, 'title': 'Purpose', 'text': 'Relay each packet as it arrives.'}]
    assert run({'add': {WIDGET: {'specification': blocks}}}) == {'status': 'ok'}
    read = run({WIDGET: {}})[WIDGET]
    assert fields_only(read['specification']) == blocks and 'specification' in read['overlays']
    assert 'specification' not in run({CS: {}})[CS]


def test_the_projects_root_holds_its_own_description_and_no_other_overlay(home, mapped):
    """F07: the root, the project's name alone, holds specification blocks, the project's own description: written
    with update, read back with the root's read, checked by the block rules and the project's one set of codes, and
    held in a graph that stays whole. Any other overlay at the root is refused by name, and nothing changes."""
    blocks = [{'text': 'Mashtrac tracks mash packets.'},
              {'level': 1, 'title': 'Purpose', 'code': 'P-1', 'text': 'Relay each packet once.'},
              {'level': 2, 'title': 'Scope', 'text': 'Packets only.'}]
    assert run({'update': {P: {'name': 'Mashtrac', 'specification': blocks}}}) == {'status': 'ok'}
    read = run({P: {}})[P]
    assert read['name'] == 'Mashtrac' and fields_only(read['specification']) == blocks
    assert owner.of(metaform_home.home()).read(P, lambda opened: opened.integrity()) == []
    for command, code in (({'update': {P: {'tickets': [{'id': 't-1', 'title': 'T', 'task': 'T.'}]}}},
                           'OVERLAY_NOT_AT_ROOT'),
                          ({'update': {P: {'specification': [{'level': 2, 'title': 'Skips'}]}}},
                           'HEADING_LEVEL_INVALID'),
                          ({'add': {WIDGET: {'specification': [{'level': 1, 'title': 'T', 'code': 'p-1'}]}}},
                           'CODE_TAKEN')):
        answer = run(command)
        assert answer.get('code') == code, (command, answer)
        assert 'tickets' in answer['message'] if code == 'OVERLAY_NOT_AT_ROOT' else True
    assert fields_only(run({P: {}})[P]['specification']) == blocks
    kept = run({P: {}})[P]['specification'][1]
    assert run({'update': {P: {'specification': [{'position': 1, 'record': kept['record'], 'title': 'Aim'}]}}}) == {
        'status': 'ok'}
    assert run({P: {}})[P]['specification'][1] == {**kept, 'title': 'Aim', 'revision': kept['revision'] + 1}
    assert run({'update': {P: {'specification': []}}}) == {'status': 'ok'}
    assert 'specification' not in run({P: {}})[P]


def test_the_root_blocks_round_trip_through_the_document_between_its_heading_and_the_first_element(home, mapped):
    """F07: the root's blocks are rendered after the project's heading and before the first element, one Markdown
    level deeper than their level, and read back from there; export, edit, import and export again give the edited
    document byte for byte."""
    owned = owner.of(metaform_home.home())
    assert run({'update': {P: {'specification': [{'text': 'Mashtrac tracks mash packets.'},
                                                  {'level': 1, 'title': 'Purpose', 'code': 'P-1', 'text': 'Relay.'}]}}})[
        'status'] == 'ok'
    exported = commands.perform_specification(P, None, owned)['document']
    assert exported.startswith(f'# {P}\n\nMashtrac tracks mash packets.\n\n## `P-1` Purpose\n\nRelay.\n\n'
                               f'## mashbox (`{WIDGET}`)\n\n')
    assert commands.perform_specification(P, exported, owned) == {'status': 'ok', 'changed': []}
    edited = exported.replace('Relay.', 'Relay each packet once.\n\n### Scope\n\nPackets only.')
    assert commands.perform_specification(P, edited, owned) == {'status': 'ok', 'changed': [P]}
    assert commands.perform_specification(P, None, owned)['document'] == edited
    assert fields_only(run({P: {}})[P]['specification'])[-1] == {'level': 2, 'title': 'Scope', 'text': 'Packets only.'}
    for broken in (edited.replace('### Scope', '#### Scope'), edited.replace('Relay each', '# Relay each')):
        assert commands.perform_specification(P, broken, owned)['code'] == 'DOCUMENT_REFUSED', broken
    assert commands.perform_specification(P, None, owned)['document'] == edited



def test_a_root_record_completes_and_reopens_as_an_elements_does(home, mapped):
    """Review of 2026-11-18, F2: a root update with completed: true answered ok and changed nothing. The root's records
    now complete as an element's do, leave the default read, are read back by their id, and reopen by their id."""
    assert run({'update': {P: {'specification': [{'text': 'Mashtrac tracks mash packets.'},
                                                  {'level': 1, 'title': 'Purpose', 'text': 'Obsolete.'}]}}})[
        'status'] == 'ok'
    intro, purpose = run({P: {}})[P]['specification']
    assert run({'update': {P: {'specification': [{'position': 1, 'record': purpose['record'],
                                                  'completed': True}]}}}) == {'status': 'ok'}
    assert [one['record'] for one in run({P: {}})[P]['specification']] == [intro['record']]
    (back,) = run({P: {'specification': {'record': purpose['record']}}})[P]['specification']
    assert back['title'] == 'Purpose' and back['completed'].startswith('20')
    assert run({'update': {P: {'specification': [{'record': purpose['record'], 'completed': False}]}}}) == {
        'status': 'ok'}
    assert [one['record'] for one in run({P: {}})[P]['specification']] == [intro['record'], purpose['record']]


def test_a_reopened_specification_block_is_checked_and_can_come_back_where_it_was(home, mapped):
    """Review of 2026-11-18, F12: an introduction completed and reopened came back after a heading, which the export
    then refused. A reopen at the end that would break the block rules is refused whole; one given a position comes
    back there, and the specification exports."""
    owned = owner.of(metaform_home.home())
    assert run({'update': {P: {'specification': [{'text': 'Intro.'}, {'level': 1, 'title': 'Purpose', 'text': 'R.'}]}}})[
        'status'] == 'ok'
    intro = run({P: {}})[P]['specification'][0]
    assert run({'update': {P: {'specification': [{'position': 0, 'record': intro['record'],
                                                  'completed': True}]}}}) == {'status': 'ok'}
    refused = run({'update': {P: {'specification': [{'record': intro['record'], 'completed': False}]}}})
    assert refused['status'] == 'error', refused
    assert [one['title'] for one in run({P: {}})[P]['specification']] == ['Purpose'], 'the refusal changed nothing'
    assert run({'update': {P: {'specification': [{'record': intro['record'], 'completed': False, 'position': 0}]}}}) == {
        'status': 'ok'}
    assert [one.get('text') for one in run({P: {}})[P]['specification']] == ['Intro.', 'R.']
    assert commands.perform_specification(P, None, owned)['document'].startswith(f'# {P}\n\nIntro.\n\n## Purpose')

def test_dispatch_waits_on_a_ticket_of_the_project_store(served):
    """Phase 3, F01: `dispatch wait` found no store ticket, since it read only the old store. A done store ticket now
    answers done at once, an open one waits out the limit as pending, and a condition a store ticket cannot meet is
    refused by name."""
    import asyncio
    import contextlib
    from types import SimpleNamespace

    from metaform.module import Stop
    from metaform.modules.dispatch import wait_in_store
    assert commands.run({'add': {WIDGET: {**WIDGET_FIELDS, 'tickets': [
        {'id': 't-done', 'title': 'Done', 'task': 'Done.', 'done': '2026-11-17T00:00:00Z', 'outcome': 'completed'},
        {'id': 't-open', 'title': 'Open', 'task': 'Open.'}]}}}, served) == {'status': 'ok'}
    ctx = SimpleNamespace(listen=lambda _: contextlib.nullcontext(), setting=lambda _: 0.3)
    assert asyncio.run(wait_in_store(ctx, P, P, 'done', 't-done'))['state'] == 'done'
    assert asyncio.run(wait_in_store(ctx, P, P, 'done', 't-open'))['state'] == 'pending'
    with pytest.raises(Stop, match='until=stopped has no meaning yet'):
        asyncio.run(wait_in_store(ctx, P, P, 'stopped', 't-open'))


def test_the_specification_command_never_overwrites_a_document_and_a_refusal_keeps_the_edits(served, tmp_path):
    """Phase 4, after verification: an export never writes over an existing file, which may hold edits not yet
    imported, and a refused import names the import again as its next step, never an export over the edited file."""
    from types import SimpleNamespace

    from metaform.module import Stop
    from metaform.modules.map import specification as verb
    assert commands.run({'add': {WIDGET: WIDGET_FIELDS}}, served) == {'status': 'ok'}

    def ctx(**nouns):
        return SimpleNamespace(require_store=lambda: SimpleNamespace(project_id=P), nouns=nouns)
    path = tmp_path / 'spec.md'
    assert verb(ctx(file=str(path)))['bytes'] > 0
    edited = path.read_text().replace('Role: Coupled Element.', 'Role: Defining Element.')  # stale: refused
    path.write_text(edited)
    with pytest.raises(Stop, match='already exists') as refused:
        verb(ctx(file=str(path)))
    assert 'spec-fresh.md' in str(refused.value.next_step) and path.read_text() == edited
    with pytest.raises(Stop, match='Nothing was written') as stale:
        verb(ctx(op='import', file=str(path)))
    assert f'op=import file={path}' in str(stale.value.next_step) and path.read_text() == edited


def test_a_base_switch_whose_record_cannot_be_written_puts_every_file_back(mapped, monkeypatch):
    """Bases, after verification (helper-2cdabcb8): writing the record of the bases is the switch's last step, inside
    its guard, so when it fails the files and the record are left as they were and the project still reads its map;
    a removal whose record cannot be written puts the base back."""
    from metaform.project import base_maps
    owned = owner.of(metaform_home.home())
    whole = run({'map': P})
    assert base_maps.perform({'project': P, 'op': 'add', 'name': 'fresh'}, owned)['status'] == 'ok'
    assert base_maps.perform({'project': P, 'op': 'activate', 'name': 'main'}, owned)['status'] == 'ok'
    before = (base_maps.folder(metaform_home.home(), P) / 'bases.json').read_text()
    real = base_maps._save

    def failing(*_args: object) -> None:
        raise OSError('disk full')
    monkeypatch.setattr(base_maps, '_save', failing)
    for asked in ({'op': 'add', 'name': 'other'}, {'op': 'activate', 'name': 'fresh'},
                  {'op': 'remove', 'name': 'fresh'}):
        with pytest.raises(OSError):
            base_maps.perform({'project': P, **asked}, owned)
        assert run({'map': P}) == whole, asked  # the project still reads its own map
        assert (base_maps.folder(metaform_home.home(), P) / 'bases.json').read_text() == before, asked
    monkeypatch.setattr(base_maps, '_save', real)
    listed = base_maps.perform({'project': P, 'op': 'list'}, owned)
    assert (listed['active'], [one['name'] for one in listed['bases']]) == ('main', ['main', 'fresh'])
    assert base_maps.perform({'project': P, 'op': 'activate', 'name': 'fresh'}, owned)['status'] == 'ok'


def test_each_elements_array_is_one_node_and_the_panel_completes_its_records(served):
    """The person, 2026-11-17: "those arrays should read as a node, and you should be able to mark them complete so they
    don't pollute other agents' contexts". The page's layer-items read gives one item per element's array of open
    records with its count; opened, it lists them with their ids; one completed from the panel leaves the count."""
    from metaform.modules.web import project_map
    tickets = [{'id': f't-{n}', 'title': n, 'task': n} for n in 'ab']
    assert commands.run({'add': {WIDGET: {**WIDGET_FIELDS, 'tickets': tickets}}}, served) == {'status': 'ok'}
    (array,) = project_map.layer_items(P, 'tickets')
    assert array['array'] == {'element': 'code.masher.widget', 'overlay': 'tickets', 'open': 2}
    assert array['target'] == {'kind': 'element', 'id': 'code.masher.widget'} and array['value'] == {'tickets': '2 open'}
    a, b = project_map.array_records(P, 'code.masher.widget', 'tickets')
    assert (a['id'], a['position'], b['position']) == ('t-a', 0, 1) and a['record'].startswith('r-')
    project_map.complete_record(P, 'code.masher.widget', 'tickets', a['position'], a['record'], a['revision'])
    assert project_map.layer_items(P, 'tickets')[0]['array']['open'] == 1
    (left,) = project_map.array_records(P, 'code.masher.widget', 'tickets')
    assert (left['id'], left['position']) == ('t-b', 0)
    with pytest.raises(Exception, match='no longer there|now at position|changed since'):  # a stale completion
        project_map.complete_record(P, 'code.masher.widget', 'tickets', 0, a['record'], a['revision'])
    assert project_map.layer_items(P, 'wants') == [] and project_map.layer_items('nosuch', 'tickets') is None


def test_a_completed_record_leaves_every_default_read_and_comes_back_only_when_reopened(served):
    """The person's rule, 2026-11-17: agents are never shown what is no longer relevant. A record completed by an update
    naming it leaves the element read, the named read, the overlay list, the board's read and the specification
    blocks; it leaves the list too, so the next record takes its position and a position always names what a read
    shows. A list written whole keeps it, its ticket id stays taken, and completed: false by its id reopens it."""
    from metaform import project as project_store
    tickets = [{'id': f't-{n}', 'title': n, 'task': n} for n in ('a', 'b', 'c')]
    assert commands.run({'add': {WIDGET: {**WIDGET_FIELDS, 'tickets': tickets,
                                          'specification': [{'level': 1, 'title': 'Old', 'text': 'Superseded.'}]}}},
                        served) == {'status': 'ok'}

    def read(named=None):
        return commands.run({WIDGET: named or {}}, served)[WIDGET]
    a, b, c = read({'tickets': {}})['tickets']
    assert commands.run({'update': {WIDGET: {'tickets': [
        {'position': 0, 'record': a['record'], 'revision': a['revision'], 'completed': True}]}}}, served) == {
        'status': 'ok'}
    open_now = read({'tickets': {}})['tickets']
    assert [one['record'] for one in open_now] == [b['record'], c['record']]
    assert [one['id'] for one in project_store.overlay_records(P, 'tickets', served)] == ['t-b', 't-c']
    # positions close up: position 0 now names b, as the read shows
    assert commands.run({'update': {WIDGET: {'tickets': [{'position': 0, 'record': b['record'], 'note': 'b'}]}}},
                        served) == {'status': 'ok'}
    # a stale completion of a, already gone from the list, is refused
    assert commands.run({'update': {WIDGET: {'tickets': [
        {'position': 0, 'record': a['record'], 'completed': True}]}}}, served)['code'] == 'RECORD_GONE'
    # the specification block, completed, leaves the read an agent gets unasked, and the overlay list empties
    (old,) = read()['specification']
    assert commands.run({'update': {WIDGET: {'specification': [
        {'position': 0, 'record': old['record'], 'completed': True}]}}}, served) == {'status': 'ok'}
    assert 'specification' not in read() and 'specification' not in read()['overlays']
    # a list written whole replaces the open records and keeps the completed one; its id stays taken
    assert commands.run({'update': {WIDGET: {'tickets': [{'id': 't-d', 'title': 'd', 'task': 'd'}]}}}, served) == {
        'status': 'ok'}
    assert commands.run({'add': {WIDGET: {'tickets': [{'id': 't-a', 'title': 'again', 'task': 'x'}]}}},
                        served)['code'] == 'TICKET_ID_TAKEN'
    # reopened by its id, it comes back at the end of the list
    assert commands.run({'update': {WIDGET: {'tickets': [{'record': a['record'], 'completed': False}]}}}, served) == {
        'status': 'ok'}
    assert [one['id'] for one in read({'tickets': {}})['tickets']] == ['t-d', 't-a']
    assert commands.run({'update': {WIDGET: {'tickets': [{'record': 'r-0000000000000000', 'completed': False}]}}},
                        served)['code'] == 'RECORD_GONE'


def test_a_completed_record_is_reached_by_its_id_or_by_find_and_find_never_gives_everything(mapped):
    """The person's rule, 2026-11-17: what is no longer relevant is reached by search or by reference, never in bulk.
    A completed record is read back by its record id and found by find with completed: true; find without it looks
    in open records only; find gives at most 20 and says how many more."""
    run({'add': {SPEC: SPEC_DEFINITION}})
    run({'add': {CS: {'project_specifications': [{'title': f'Relay rule n{n}x', 'level': 1} for n in range(25)]}}})
    first = run({CS: {'project_specifications': {}}})[CS]['project_specifications'][0]
    assert run({'update': {CS: {'project_specifications': [
        {'position': 0, 'record': first['record'], 'completed': True}]}}}) == {'status': 'ok'}
    (back,) = run({CS: {'project_specifications': {'record': first['record']}}})[CS]['project_specifications']
    assert (back['title'], back['record']) == ('Relay rule n0x', first['record']) and back['completed'].startswith('20')
    open_only = run({'find': {P: 'relay rule'}})
    assert len(open_only['find']) == 20 and open_only['more'] == 4  # 24 open: never the whole list
    assert first['record'] not in [one['record'] for one in open_only['find']]
    hit = run({'find': {P: 'rule n0x', 'overlay': 'project_specifications', 'completed': True}})['find']
    assert [(one['record'], one['element'], one['field']) for one in hit] == [(first['record'], CS, 'title')]
    assert run({'find': {P: 'relay', 'overlay': 'nosuch'}})['code'] == 'OVERLAY_NOT_DEFINED'
    assert run({'find': {P: ''}})['status'] == 'error' and run({'help': 'find'})['help']['find']['does']


def test_archiving_done_tickets_completes_them(served):
    """The board's Archive done tickets, for a store project, completes every ticket done by the cutoff: it leaves the
    board's read and every other, and is found again by find."""
    from metaform.modules.web import project_map
    assert commands.run({'add': {WIDGET: {**WIDGET_FIELDS, 'tickets': [
        {'id': 't-old', 'title': 'old', 'task': 'x', 'done': '2026-11-01T00:00:00Z', 'outcome': 'completed'},
        {'id': 't-open', 'title': 'open', 'task': 'x'},
        {'id': 't-new', 'title': 'new', 'task': 'x', 'done': '2026-11-20T00:00:00Z', 'outcome': 'completed'}]}}},
        served) == {'status': 'ok'}
    assert project_map.archive_done(P, '2026-11-17T00:00:00Z') == 1
    assert [one['id'] for one in commands.overlay_records(P, 'tickets', served)] == ['t-open', 't-new']
    assert [one['overlay'] for one in commands.run({'find': {P: 'old', 'completed': True}}, served)['find']] == ['tickets']
