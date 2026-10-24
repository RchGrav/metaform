"""Persistent worker sessions use the real runner and a local fake ACP adapter."""
import json
import time

import pytest

pytestmark = pytest.mark.kind('fixture')


@pytest.mark.timeout(20)
def test_worker_stays_idle_and_one_message_wakes_same_session(run, project_folder, tmp_path, monkeypatch):
    from metaform.data import Store
    from metaform.modules.dispatch import end_group
    from metaform.modules.tasks.board import Board

    monkeypatch.setenv('TMPDIR', str(tmp_path))
    log = tmp_path / 'worker-acp.jsonl'
    monkeypatch.setenv('FAKE_ACP_LOG', str(log))
    monkeypatch.setenv('FAKE_ACP_MODE', 'finite')
    monkeypatch.setenv('FAKE_ACP_USED', '3200')
    run('enable', 'dispatch', cwd=project_folder)
    task_id = None
    runner_pid = None

    def entries():
        if not log.exists():
            return []
        data = log.read_bytes()
        return [json.loads(line) for line in data[:data.rfind(b'\n') + 1].decode().splitlines()]

    def until(predicate):
        deadline = time.monotonic() + 8
        last = None
        while time.monotonic() < deadline:
            last = json.loads(run('tasks', 'get', task_id, '--json', cwd=project_folder).stdout)
            worker = Board('proj').worker(task_id)
            if predicate(last, worker):
                return last, worker
            time.sleep(0.05)
        raise AssertionError(f'Expected worker state not reached: {last}')

    try:
        launched = json.loads(run('tasks', 'assign', 'name=worker', 'agent=claude', 'agent_name=Exact Worker',
                                 '--json', cwd=project_folder).stdout)
        task_id = launched['task_id']
        with Store('proj', module='tasks').tables(write=False) as tx:
            assignment = dict(tx.get('assignments', {'task_id': task_id}))
        runner_pid = assignment['locator']['pid']
        assert assignment['payload']['persistent'] is True
        assert assignment['payload']['interactive'] is False
        first, worker = until(lambda task, worker: worker is not None and worker['state'] == 'idle')
        assert first['status'] == 'working' and 'inputRequests' not in first
        assert worker['context']['used'] == 3200 and worker['context']['size'] == 200000
        assert worker['session_id']
        assert Board('proj').view()[0]['context'] == 1.6
        canonical = assignment['payload']['instructions']
        assert 'Exact Worker' in canonical and '{name variable}' not in canonical
        queued = json.loads(run('tasks', 'message', task_id, 'Continue with exact  spacing.',
                               '--json', cwd=project_folder).stdout)
        assert queued['queued'] is True

        def second_turn(task, current):
            with Store('proj', module='dispatch').tables(write=False) as tx:
                states = [json.loads(row['text']) for row in tx.rows('session_lines', {'kind': 'state'}, limit=0).results]
            return current is not None and current['state'] == 'idle' and states and states[0]['task_turns'] == 2

        second, same = until(second_turn)
        assert second['status'] == 'working' and 'inputRequests' not in second
        assert same['session_id'] == worker['session_id']
        messages = [entry['message'] for entry in entries() if 'message' in entry]
        created = [message for message in messages if message.get('method') == 'session/new']
        prompts = [message for message in messages if message.get('method') == 'session/prompt']
        assert len(created) == 1 and created[0]['params']['cwd'] == str(project_folder)
        assert len(prompts) == 2
        first_prompt = '\n'.join(block['text'] for block in prompts[0]['params']['prompt'] if block['type'] == 'text')
        assert canonical in first_prompt
        assert 'From cli: Continue with exact  spacing.' in str(prompts[1]['params']['prompt'])
        assert all(not entry.get('role') for entry in entries())
        assert Board('proj').pending(task_id) == []
        run('tasks', 'cancel', task_id, '--json', cwd=project_folder)
        final, removed = until(lambda task, worker: task['status'] == 'cancelled')
        assert final['status'] == 'cancelled' and removed is None
    finally:
        if runner_pid is not None:
            end_group(runner_pid)
        for entry in entries():
            if 'pid' in entry:
                end_group(entry['pid'])


@pytest.mark.timeout(20)
def test_completed_pair_ratings_drain_two_native_workers(run, project_folder, tmp_path, monkeypatch):
    from metaform.data import Node, Store
    from metaform.modules.dispatch import end_group
    from metaform.modules.tasks.board import Board

    monkeypatch.setenv('TMPDIR', str(tmp_path))
    log = tmp_path / 'pair-acp.jsonl'
    monkeypatch.setenv('FAKE_ACP_LOG', str(log))
    monkeypatch.setenv('FAKE_ACP_MODE', 'finite')
    run('enable', 'dispatch', cwd=project_folder)
    store = Store('proj')
    store.layer('parts', 'test', 'Example parts.', mutable=True, hideable=True, ready=True)
    store.add_element('parts', 'code.Example')
    ticket = store.add_work(Node('element', 'code.Example'), None, task='Complete the pair example.', title='Pair example').id
    launched = []
    runner_pids = []

    def until(predicate):
        deadline = time.monotonic() + 8
        states = []
        while time.monotonic() < deadline:
            states = [json.loads(run('tasks', 'get', item['task_id'], '--json', cwd=project_folder).stdout)
                      for item in launched]
            if predicate(states):
                return states
            time.sleep(0.05)
        raise AssertionError(f'Pair did not reach expected state: {states}')

    try:
        for name in ('Worker A', 'Worker B'):
            launch = json.loads(run('tasks', 'assign', 'name=worker', 'agent=claude', f'agent_name={name}',
                                   '--json', cwd=project_folder).stdout)
            launched.append(launch)
            with Store('proj', module='tasks').tables(write=False) as tx:
                assignment = dict(tx.get('assignments', {'task_id': launch['task_id']}))
            runner_pids.append(assignment['locator']['pid'])
        until(lambda states: len(Board('proj').workers()) == 2 and
              all(worker['state'] == 'idle' for worker in Board('proj').workers()))
        holder, partner = [item['task_id'] for item in launched]
        items = [{'id': 'a', 'text': 'First contribution', 'agent': holder, 'nodes': ['code.Example']},
                 {'id': 'b', 'text': 'Second contribution', 'agent': partner, 'nodes': ['code.Example']}]
        run('tasks', 'worksheet', ticket, f'holder={holder}', f'items={json.dumps(items)}',
            'nodes=["code.Example"]', '--json', cwd=project_folder)
        run('tasks', 'pair', ticket, partner, '--json', cwd=project_folder)
        for item in ('a', 'b'):
            run('tasks', 'check', ticket, item, '--json', cwd=project_folder)
        assert not store.ticket(ticket).work.done
        first = json.loads(run('tasks', 'rate', ticket, 'scores={"care":80}', f'reviewer={holder}',
                               f'target={partner}', '--json', cwd=project_folder).stdout)
        assert first['recorded'] is True and first['completed'] is False
        assert not store.ticket(ticket).work.done
        second = json.loads(run('tasks', 'rate', ticket, 'scores={"accuracy":90}', f'reviewer={partner}',
                                f'target={holder}', '--json', cwd=project_folder).stdout)
        assert second['completed'] is True and store.ticket(ticket).work.done
        states = until(lambda states: all(state['status'] == 'completed' for state in states))
        assert all(not state['result'].get('isError') for state in states)
        assert Board('proj').workers() == []
        assert 'First contribution' in store.ticket(ticket).work.note
        assert 'Second contribution' in store.ticket(ticket).work.note
        assert not store.work(open=True, limit=0).results
    finally:
        for pid in runner_pids:
            end_group(pid)
        if log.exists():
            data = log.read_bytes()
            for line in data[:data.rfind(b'\n') + 1].decode().splitlines():
                entry = json.loads(line)
                if 'pid' in entry:
                    end_group(entry['pid'])
