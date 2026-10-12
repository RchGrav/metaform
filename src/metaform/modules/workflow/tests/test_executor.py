"""Call scopes and run-id handoffs survive process boundaries, BASE-051."""
import json
import subprocess
import sys

import pytest

from metaform.data import Store
from metaform.data.records import plain
from metaform.modules.workflow import executor, runs
from metaform.modules.workflow.binding import Logic
from metaform.modules.workflow.element import ElementValue

pytestmark = [pytest.mark.req('BASE-051'), pytest.mark.req('MAP-056'), pytest.mark.kind('fixture')]

SCRIPT = '@STATE_INIT:\n {target} := PARAM\n@CONSTRAINT:\n'


@pytest.fixture
def store(run, project_folder):
    """The project's store, which holds the workflow run records once the module is enabled."""
    run('enable', 'workflow')
    return Store('proj', module='workflow')


def lookup(address, name):
    return Logic('logic', name, name, SCRIPT), ElementValue({'address': address})


def begin(store):
    return executor.start(store, '({ok}, {issues}) := workflow.quality.code.improve(target=this)',
                          {'secret': 'caller history'}, ElementValue({'address': 'code.timer'}), lookup,
                          {'project': 'proj', 'folder': '/tmp', 'metaform': None, 'layers': []})


def test_same_agent_nested_calls_restore_values_and_callee_this(store):
    word = begin(store)
    first = executor.view(store, word)
    assert first['this'].address == 'workflow.quality.code'
    assert first['arguments']['target'].address == 'code.timer'
    variables = {**first['variables'], 'attempt': 2}
    executor.call(store, word, '({ok}, {issues}) := workflow.review.code.review(target={target})', variables, lookup)
    child = executor.view(store, word)
    assert child['this'].address == 'workflow.review.code'
    assert 'attempt' not in child['variables']
    resumed = executor.complete(store, word, 'RETURN (TRUE, [])', {})
    assert resumed['variables']['attempt'] == 2 and resumed['variables']['ok'] is True
    result = executor.complete(store, word, 'RETURN ({ok}, {issues})', resumed['variables'])
    assert result == {'value': (True, []), 'variables': {'secret': 'caller history', 'ok': True, 'issues': []}}
    assert runs.read(store, word).state == 'completed'


def test_fresh_handoff_redeems_in_another_process_with_only_callee_context(store):
    parent = begin(store)
    child = executor.call(store, parent, '({ok}, {issues}) := workflow.review.code.review(target={target})',
                          {**executor.view(store, parent)['variables'], 'private': 'caller only'}, lookup, fresh=True)
    script = 'import json, sys; from metaform.data import Store; from metaform.data.records import plain; ' \
             'from metaform.modules.workflow.executor import view; ' \
             'print(json.dumps(plain(view(Store("proj", module="workflow"), sys.argv[1]))))'
    result = subprocess.run([sys.executable, '-c', script, child], capture_output=True, text=True, check=True)
    visible = json.loads(result.stdout)
    assert 'private' not in visible['variables'] and 'secret' not in result.stdout
    assert visible['arguments']['target']['address'] == 'code.timer'
    assert visible['logic']['content'] == SCRIPT
    assert executor.view(store, parent)['state'] == 'waiting'
    with pytest.raises(Exception, match='waiting'):
        executor.complete(store, parent, 'RETURN TRUE', {})
    resumed = executor.complete(store, child, 'RETURN (TRUE, [])', {})
    assert resumed == {'resume': parent}
    assert executor.view(store, parent)['variables']['private'] == 'caller only'
    assert runs.read(store, child).state == 'completed'
    assert executor.view(store, parent)['state'] == 'running'


def test_error_propagates_unchanged_to_caller_and_then_orchestrator(store):
    parent = begin(store)
    executor.call(store, parent, '{fixed} := workflow.quality.code.fix(target={target})',
                  executor.view(store, parent)['variables'], lookup)
    resumed = executor.fail(store, parent, 'SourceUnreadable', 'src/timer.py')
    assert resumed['error'] == {'name': 'SourceUnreadable', 'message': 'src/timer.py'}
    assert 'fixed' not in resumed['variables']
    assert executor.fail(store, parent, name='SourceUnreadable', message='src/timer.py') == {
        'error': {'name': 'SourceUnreadable', 'message': 'src/timer.py'}}


def test_parallel_waits_for_every_branch_and_preserves_every_error(store):
    parent = begin(store)
    words = executor.parallel(store, parent, ['{a} := workflow.review.code.review(target={target})',
                                      '{b} := workflow.review.code.review(target={target})'],
                              executor.view(store, parent)['variables'], lookup)
    assert executor.fail(store, words[0], 'FirstFailed', 'first') == {'caller': parent, 'state': 'waiting'}
    resumed = executor.complete(store, words[1], 'RETURN TRUE', {})
    assert resumed == {'resume': parent}
    resumed = executor.view(store, parent)
    assert resumed['variables']['b'] is True
    assert resumed['branches'] == [{'run': words[0], 'error': {'name': 'FirstFailed', 'message': 'first'}},
                                  {'run': words[1], 'value': True}]
    assert [runs.read(store, one).state for one in words] == ['failed', 'completed']


def test_failed_return_binding_keeps_child_available_to_correct(store):
    parent = begin(store)
    executor.call(store, parent, '({ok}, {issues}) := workflow.review.code.review(target={target})',
                  executor.view(store, parent)['variables'], lookup)
    with pytest.raises(ValueError):
        executor.complete(store, parent, 'RETURN (TRUE,)', {})
    assert executor.view(store, parent)['logic']['name'] == 'review'
    assert executor.complete(store, parent, 'RETURN (TRUE, [])', {})['variables']['ok'] is True


def test_tuple_values_and_read_only_element_views_roundtrip(home):
    original = {'element': ElementValue({'address': 'code.timer', 'refs': {'path': ['timer.py']}}),
                'tuple': ('one', ['two'])}
    restored = executor.unpack(json.loads(json.dumps(executor.pack(original))))
    assert restored['element'].refs['path'] == ['timer.py']
    assert isinstance(restored['tuple'], tuple)
    assert plain(restored) == plain(original)


def test_parallel_bad_return_keeps_branch_open_for_correction(store):
    parent = begin(store)
    words = executor.parallel(store, parent, ['({a}, {b}) := workflow.review.code.review(target={target})',
                                      '{c} := workflow.review.code.review(target={target})'],
                              executor.view(store, parent)['variables'], lookup)
    with pytest.raises(ValueError):
        executor.complete(store, words[0], 'RETURN (TRUE,)', {})
    assert runs.read(store, words[0]).open
    executor.complete(store, words[0], 'RETURN (TRUE, FALSE)', {})
    assert executor.complete(store, words[1], 'RETURN TRUE', {}) == {'resume': parent}
    assert executor.view(store, parent)['variables']['b'] is False


def test_caller_can_run_its_catch_handler_and_use_its_return(store):
    parent = begin(store)
    executor.call(store, parent, '{fixed} := workflow.quality.code.fix(target={target})',
                  executor.view(store, parent)['variables'], lookup)
    failed = executor.fail(store, parent, 'FixFailed', 'The issue remains.')
    assert failed['error']['name'] == 'FixFailed'
    executor.call(store, parent, '{fixed} := workflow.quality.code.diagnose(target={target})',
                  failed['variables'], lookup)
    recovered = executor.complete(store, parent, 'RETURN "diagnosed cause"', {})
    assert recovered['variables']['fixed'] == 'diagnosed cause'
    assert 'error' not in recovered


def test_a_run_record_keeps_its_lifecycle_its_parent_and_its_result(store):
    parent = begin(store)
    child = executor.call(store, parent, '({ok}, {issues}) := workflow.review.code.review(target={target})',
                          executor.view(store, parent)['variables'], lookup, fresh=True)
    assert (runs.read(store, parent).state, runs.read(store, child).state) == ('waiting', 'running')
    assert runs.read(store, child).value['parent'] == parent and runs.read(store, child).kind == 'call'
    executor.fail(store, child, 'ReviewFailed', 'no reviewer')
    failed = runs.read(store, child)
    assert (failed.state, failed.result, failed.closed is not None) == (
        'failed', {'error': {'name': 'ReviewFailed', 'message': 'no reviewer'}}, True)
    assert runs.read(store, parent).state == 'running'
    with pytest.raises(Exception, match=f'No open workflow run {child}'):
        executor.complete(store, child, 'RETURN TRUE', {})


def test_a_run_paused_on_the_person_takes_no_step_until_they_answer(store):
    """input_required is apart from waiting: only the person's answer resumes it, and the answer is read beside its
    question in the run's current frame."""
    word = begin(store)
    with pytest.raises(Exception, match='only a run paused on the person takes an answer'):
        executor.answer(store, word, 'too early')
    assert executor.pause(store, word, 'Which fix lands?')['state'] == 'input_required'
    paused = executor.view(store, word)
    assert (paused['state'], paused['message']) == ('input_required', 'Which fix lands?')
    for step in (lambda: executor.complete(store, word, 'RETURN TRUE', {}),
                 lambda: executor.call(store, word, '{fixed} := workflow.quality.code.fix(target={target})', {},
                                       lookup),
                 lambda: executor.pause(store, word, 'again?')):
        with pytest.raises(Exception, match='paused on the person'):
            step()
    assert executor.answer(store, word, 'the second').state == 'running'
    resumed = executor.view(store, word)
    assert resumed['answer'] == {'question': 'Which fix lands?', 'answer': 'the second'}
    assert resumed['state'] == 'running' and 'message' not in resumed
    executor.complete(store, word, 'RETURN (TRUE, [])', {})
    assert runs.read(store, word).state == 'completed'


def test_cancel_ends_a_run_and_every_run_below_it_and_its_caller_catches_it(store):
    parent = begin(store)
    child = executor.call(store, parent, '({ok}, {issues}) := workflow.review.code.review(target={target})',
                          executor.view(store, parent)['variables'], lookup, fresh=True)
    grandchild = executor.call(store, child, '{fixed} := workflow.quality.code.fix(target={target})',
                               executor.view(store, child)['variables'], lookup, fresh=True)
    cancelled = executor.cancel(store, child, 'superseded')
    assert cancelled == {'run': child, 'state': 'cancelled', 'cancelled': [child, grandchild], 'resume': parent}
    for word in (child, grandchild):
        ended = runs.read(store, word)
        assert (ended.state, ended.message, ended.closed is not None) == ('cancelled', 'superseded', True)
    assert executor.view(store, parent)['error'] == {'name': 'cancelled', 'message': 'superseded'}
    with pytest.raises(Exception, match=f'No open workflow run {grandchild} in project proj: it is cancelled'):
        executor.complete(store, grandchild, 'RETURN TRUE', {})
    assert executor.cancel(store, parent, '')['cancelled'] == [parent]
    with pytest.raises(Exception, match='it is cancelled'):
        executor.cancel(store, parent, '')


def test_status_vocabulary_maps_every_state_and_refuses_moves_out_of_an_end():
    from metaform.data import status
    assert set(status.MCP_TASKS) == set(status.A2A) == set(status.TRANSITIONS) == set(status.STATES)
    assert set(status.MCP_TASKS.values()) == {'working', 'input_required', 'completed', 'failed', 'cancelled'}
    assert (status.MCP_TASKS['waiting'], status.A2A['cancelled']) == ('working', 'TASK_STATE_CANCELED')
    assert status.moved('input_required', 'running', 'next') == 'running'
    for end in status.TERMINAL:
        with pytest.raises(Exception, match=f'Work that is {end} cannot become running'):
            status.moved(end, 'running', 'next')
    with pytest.raises(Exception, match='cannot become completed'):
        status.moved('waiting', 'completed', 'next')
    with pytest.raises(Exception, match="'done' is not a status of work"):
        status.known('done', 'next')


def test_runs_kept_at_version_2_are_upgraded_keeping_their_states_and_dated(run, project_folder):
    """Version 3 adds message and updated, and version 4 ticket and session: every version 2 row keeps its state,
    and each is dated by its close or else its creation; the new columns may be empty, so version 1's code still reads
    the tables."""
    from dataclasses import replace

    from metaform.data import Tables
    from metaform.data.tables import TableTx, ensure, project_store, project_transaction
    from metaform.modules.workflow.catalog import TABLES
    declared = Tables(version=2, compatible_from=1, tables=tuple(
        replace(table, columns=tuple(column for column in table.columns if column.name not in ('message', 'updated', 'ticket', 'session')))
        if table.name == 'runs' else table for table in TABLES.tables))
    path = project_store('proj', 'workflow')
    path.parent.mkdir(parents=True, exist_ok=True)
    with project_transaction(path, write=True) as db:
        ensure(db, path, 'workflow', declared, 'project')
        tx = TableTx('workflow', declared, write=True, opener=lambda _: (db, path, True), bound='project')
        tx.insert('runs', {'run_id': 'a', 'kind': 'call', 'state': 'waiting', 'created': '2026-10-01T00:00:00Z',
                           'seq': 1})
        tx.insert('runs', {'run_id': 'b', 'kind': 'assign', 'state': 'completed', 'created': '2026-10-01T00:00:00Z',
                           'closed': '2026-10-02T00:00:00Z', 'seq': 2})
    run('enable', 'workflow')
    store = Store('proj', module='workflow')
    assert (runs.read(store, 'a').state, runs.read(store, 'b').state) == ('waiting', 'completed')
    with store.tables(write=False) as tx:
        dated = {row['run_id']: row['updated'] for row in tx.rows('runs', limit=0).results}
    assert dated == {'a': '2026-10-01T00:00:00Z', 'b': '2026-10-02T00:00:00Z'}
    with project_transaction(path, write=False) as db:
        recorded = json.loads(db.execute("SELECT value FROM meta WHERE key='module:workflow'").fetchone()[0])
    assert (recorded['version'], recorded['compatible_from']) == (4, 1)


def test_a_child_that_returned_cannot_then_be_cancelled_and_its_caller_keeps_the_value(store):
    """A child's return reaches its caller in the transaction that closes it, so a cancel after it is refused and the
    caller never holds both its value and the error cancelled."""
    parent = begin(store)
    child = executor.call(store, parent, '({ok}, {issues}) := workflow.review.code.review(target={target})',
                          executor.view(store, parent)['variables'], lookup, fresh=True)
    assert executor.complete(store, child, 'RETURN (TRUE, [])', {}) == {'resume': parent}
    with pytest.raises(Exception, match=f'No open workflow run {child} in project proj: it is completed'):
        executor.cancel(store, child, 'too late')
    resumed = executor.view(store, parent)
    assert resumed['returned'] == (True, []) and 'error' not in resumed


def test_login_and_refusal_are_a2a_states_with_a_reason():
    from metaform.data import status
    assert status.a2a('input_required', 'login') == 'TASK_STATE_AUTH_REQUIRED'
    assert status.a2a('failed', 'rejected') == 'TASK_STATE_REJECTED'
    assert (status.a2a('input_required'), status.MCP_TASKS['input_required']) == ('TASK_STATE_INPUT_REQUIRED',
                                                                                   'input_required')


def test_only_the_person_answers_a_paused_run_and_a_held_role_cancels_none(run, store, project_folder):
    """MAP-050 as amended 2026-10-08 and BASE-052: an agent pauses a run, and the person answers it; a worker neither
    answers it nor cancels it, and a refusal names the person's answer command for the agent to hand on."""
    word = begin(store)
    executor.pause(store, word, 'The target code.timer.kitchen is gone from the map and the logic names no other.')
    refused = run('workflow', 'complete', 'RETURN TRUE', f'run={word}', cwd=project_folder, ok=False)
    assert 'paused on the person' in refused.stderr and f'workflow answer run={word}' in refused.stderr
    for key in ('METAFORM_ROLE', 'METAFORM_SESSION', 'METAFORM_WORK'):
        refused = run('workflow', 'answer', f'run={word}', 'yes', cwd=project_folder, ok=False, env={key: 'x'})
        assert 'Only the person answers' in refused.stderr
    assert runs.read(store, word).state == 'input_required'
    listed = run('workflow', 'runs', 'state=input_required', '--json', cwd=project_folder).stdout
    assert [one['run'] for one in json.loads(listed)['runs']] == [word]
    run('workflow', 'answer', f'run={word}', 'the', 'second', cwd=project_folder)
    assert executor.view(store, word)['answer']['answer'] == 'the second'
    refused = run('workflow', 'cancel', f'run={word}', cwd=project_folder, ok=False, env={'METAFORM_ROLE': 'worker'})
    assert 'cancels no workflow run' in refused.stderr and runs.read(store, word).state == 'running'
    run('workflow', 'cancel', f'run={word}', cwd=project_folder)
    assert runs.read(store, word).state == 'cancelled'


def test_a_pause_by_an_agent_on_a_ticket_is_added_to_the_ticket_note(run, store, project_folder):
    from metaform.data import Node
    from tests.storekit import small_map
    mapped = Store('proj')
    small_map(mapped)
    ticket = mapped.add_work(Node('element', 'code.timer.kitchen'), 'unbuilt', task='Fix the timer', note='Started.')
    word = begin(store)
    paused = json.loads(run('workflow', 'pause', f'run={word}', 'The', 'tick', 'is', 'gone.', '--json',
                            cwd=project_folder, env={'METAFORM_WORK': ticket.id}).stdout)
    assert (paused['state'], paused['ticket']) == ('input_required', ticket.id)
    assert 'End your turn' in paused['next']
    note = mapped.ticket(ticket.id, raw=True).work.note
    assert note.startswith('Started.\n\nWorkflow run ') and 'The tick is gone.' in note


def test_the_answer_reaches_the_ticket_and_names_the_message_to_its_agent(run, store, project_folder):
    """The run keeps the ticket and session that paused it; the person's answer is added to that ticket's note, and
    its next step is the message that tells that agent, since nothing restarts by itself, VIEW-042."""
    from metaform.data import Node
    from tests.storekit import small_map
    mapped = Store('proj')
    small_map(mapped)
    ticket = mapped.add_work(Node('element', 'code.timer.kitchen'), 'unbuilt', task='Fix the timer')
    word = begin(store)
    run('workflow', 'pause', f'run={word}', 'The', 'target', 'is', 'gone.', cwd=project_folder,
        env={'METAFORM_WORK': ticket.id, 'METAFORM_SESSION': 's1'})
    listed = json.loads(run('workflow', 'runs', '--json', cwd=project_folder).stdout)['runs']
    assert [(one['run'], one['ticket']) for one in listed] == [(word, ticket.id)]
    answered = json.loads(run('workflow', 'answer', f'run={word}', 'Use', 'code.timer.oven', '--json',
                              cwd=project_folder).stdout)
    assert (answered['state'], answered['ticket']) == ('running', ticket.id)
    assert f'dispatch message {ticket.id} session=s1 -- "Run {word} is answered' in answered['next']
    assert 'Answered ' in mapped.ticket(ticket.id, raw=True).work.note.splitlines()[-1]
    assert 'Use code.timer.oven' in mapped.ticket(ticket.id, raw=True).work.note


def test_a_pause_whose_ticket_note_cannot_be_written_leaves_the_run_running(run, store, project_folder):
    word = begin(store)
    refused = run('workflow', 'pause', f'run={word}', 'stuck', cwd=project_folder, ok=False,
                  env={'METAFORM_WORK': 'deadbeef'})
    assert 'is not paused' in refused.stderr and 'map work op=edit id=deadbeef' in refused.stderr
    assert runs.read(store, word).state == 'running'


def test_an_assignment_pauses_and_reads_the_answer_like_a_call(run, store, project_folder):
    word = json.loads(run('workflow', 'assign', 'write_workflow', '--json', cwd=project_folder).stdout)['run']
    run('workflow', 'pause', f'run={word}', 'The', 'target', 'is', 'gone.', cwd=project_folder)
    refused = run('workflow', 'complete', f'run={word}', cwd=project_folder, ok=False)
    assert 'paused on the person' in refused.stderr and runs.read(store, word).state == 'input_required'
    run('workflow', 'answer', f'run={word}', 'Use', 'code.timer.oven', cwd=project_folder)
    resumed = run('workflow', 'resume', f'run={word}', cwd=project_folder).stdout
    assert 'What stopped this run: The target is gone.' in resumed and 'Their answer: Use code.timer.oven' in resumed
    run('workflow', 'fail', 'Gone', f'run={word}', cwd=project_folder)
    assert (runs.read(store, word).state, runs.read(store, word).result['error']['name']) == ('failed', 'Gone')


def test_a_worker_cancel_refusal_names_a_step_that_works_in_the_state_it_is_in(run, store, project_folder):
    word = begin(store)
    worker = {'METAFORM_ROLE': 'worker', 'METAFORM_WORK': 'abc'}
    refused = run('workflow', 'cancel', f'run={word}', cwd=project_folder, ok=False, env=worker)
    assert f'workflow fail <name> run={word}' in refused.stderr
    executor.pause(store, word, 'stuck')
    refused = run('workflow', 'cancel', f'run={word}', cwd=project_folder, ok=False, env=worker)
    assert 'workflow fail' not in refused.stderr and 'map work op=edit id=abc' in refused.stderr


def test_runs_are_listed_a_page_at_a_time_and_ended_ones_newest_first(store):
    words = [runs.start(store, 'assign', {'assignment': {'skill': 'scan'}}) for _ in range(5)]
    for word in words:
        runs.close(store, word)
    page, cursor = runs.listed(store, 'completed', limit=2)
    assert [one['run'] for one in page] == words[:-3:-1] and cursor is not None
    rest, last = runs.listed(store, 'completed', limit=2, after=cursor)
    assert [one['run'] for one in rest] == [words[2], words[1]] and last is not None
    assert runs.listed(store)[0] == []
