"""hello exercises each chassis feature once; each test fails if the chassis drops that feature, BASE-019."""
from __future__ import annotations

import asyncio
import json
import re
import sys

import pytest


def own(project_id):
    """A project's folder in the home, PROJ-026."""
    from metaform import home as metaform_home
    return metaform_home.project_folder(project_id)

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture
def hello(run, tmp_path):
    """hello enabled, in a registered project folder."""
    run('enable', 'hello')
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    return folder


@pytest.mark.req('BASE-019')
@pytest.mark.req('CLI-012')
@pytest.mark.req('CLI-011')
def test_greet_takes_a_noun_and_a_switch_that_is_a_setting(run, hello):
    assert run('hello', 'greet', 'world', cwd=hello).stdout.strip() == 'hello, world'
    assert run('hello', 'greet', 'world', '--loud', cwd=hello).stdout.strip() == 'HELLO, WORLD!'
    run('set', '--loud', cwd=hello)
    assert run('hello', 'greet', 'world', cwd=hello).stdout.strip() == 'HELLO, WORLD!'
    assert run('hello', 'greet', 'world', '--no-loud', cwd=hello).stdout.strip() == 'hello, world'
    run('set', '--greeting', 'hi', cwd=hello)
    run('unset', '--loud', cwd=hello)
    assert run('hello', 'greet', 'you', cwd=hello).stdout.strip() == 'hi, you'


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-009')
def test_wait_is_an_async_verb(run, hello):
    assert run('hello', 'wait', '0', cwd=hello).stdout.strip() == 'waited 0 s'


@pytest.mark.req('BASE-004')
@pytest.mark.req('BASE-027')
@pytest.mark.req('QUAL-016')
def test_shared_services_work_from_hello_and_preserve_project_cleanup(run, hello, home):
    run('hello', 'greet', 'ada', cwd=hello)
    got = json.loads(run('hello', 'basedemo', '--json', cwd=hello).stdout)
    assert got['home'] == str(home)
    assert got['project']['project_id'] == 'proj'
    assert got['registered'] == ['proj']
    assert got['layers'] == []
    assert 'roots' in got['reads'] and 'roots' in got
    assert got['backups'] == [] and got['held']
    assert got['caution'] and got['newer_store_error'] == 'NewerStore'
    from metaform.module import code_print
    assert got['code_print'] == code_print()

    refused = run('hello', 'base-remove', '--confirm', cwd=hello, ok=False)
    assert refused.returncode == 2 and got['held'] in refused.stderr
    run('clear', 'project', '--confirm', cwd=hello)
    got = json.loads(run('hello', 'basedemo', '--json', cwd=hello).stdout)
    assert got['held'] is None and len(got['backups']) == 1
    refused = run('hello', 'base-restore', cwd=hello, ok=False)
    assert refused.returncode == 2 and '--confirm' in refused.stderr
    restored = json.loads(run('hello', 'base-restore', '--confirm', '--json', cwd=hello).stdout)
    assert restored['project'] == 'proj'
    assert run('hello', 'history', cwd=hello).stdout.strip() == 'ada'
    run('clear', 'project', '--confirm', cwd=hello)
    refused = run('hello', 'base-remove', cwd=hello, ok=False)
    assert refused.returncode == 2 and '--confirm' in refused.stderr
    run('hello', 'base-remove', '--confirm', cwd=hello)
    assert hello.is_dir()
    assert (home / 'backups' / 'clear' / 'proj').is_dir()
    assert run('list', 'projects').stdout.startswith('No projects yet.')


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-010')
@pytest.mark.req('STORE-022')
def test_the_greeted_event_is_recorded_as_a_layer(run, hello, home, user_module):
    user_module('witness', '''
        from metaform.data import Node
        from metaform.module import Module, Subscription
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        def saw(payload, ctx):
            store = ctx.require_store()
            with store.atomic():
                store.layer('witnessed', 'witness', 'Greetings seen.', mutable=True, hideable=True,
                            provenance={'module': 'witness'})
                store.add_element('witnessed', 'code.witness')
                store.add_item('witnessed', Node('element', 'code.witness'), payload['name'])
        MODULE = Module(id='witness', summary='x', purpose='Witnesses. Details: metaform help witness.',
                        subscriptions=(Subscription('hello.greeted', saw),))
    ''')
    run('hello', 'greet', 'ada', cwd=hello)
    run('hello', 'greet', 'bob', cwd=hello)
    assert run('hello', 'history', cwd=hello).stdout.split() == ['ada', 'bob']
    from metaform.data import Store
    layers = {layer.name: layer for layer in Store('proj').layers(limit=0).results}
    assert layers['hello.greetings'].module == 'hello'
    assert [item.value for item in Store('proj').layer_items('witnessed').results] == ['ada', 'bob']


@pytest.mark.req('BASE-019')
@pytest.mark.req('CLI-019')
def test_the_favorite_setting_takes_its_choices_from_the_modules_data(run, hello, tmp_path):
    refused = run('set', '--favorite', 'zed', cwd=hello, ok=False)
    assert refused.returncode == 2
    run('hello', 'greet', 'zed', cwd=hello)
    run('set', '--favorite', 'zed', cwd=hello)
    elsewhere = tmp_path / 'nowhere'
    elsewhere.mkdir()
    outside = run('set', '--favorite', 'zed', cwd=elsewhere, ok=False)
    assert outside.stderr.splitlines() == [
        'Error: --favorite has no choices here: this folder is not in a registered project.',
        'Next: metaform add project <id> <path>']


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-013')
def test_forget_needs_confirm(run, hello):
    run('hello', 'greet', 'ada', cwd=hello)
    refused = run('hello', 'forget', cwd=hello, ok=False)
    assert refused.stderr.splitlines()[-1] == 'Next: If you are sure: metaform hello forget --confirm'
    assert run('hello', 'history', cwd=hello).stdout.split() == ['ada']
    run('hello', 'forget', '--confirm', cwd=hello)
    assert run('hello', 'history', cwd=hello).stdout.startswith('No greetings yet.')


@pytest.mark.req('STORE-023')
@pytest.mark.req('CLI-020')
def test_a_verb_that_needs_a_project_names_the_way_to_register_one(run, tmp_path):
    run('enable', 'hello')
    folder = tmp_path / 'nowhere'
    folder.mkdir()
    refused = run('hello', 'greet', 'ada', cwd=folder, ok=False)
    assert refused.returncode == 2
    assert refused.stderr.splitlines() == ['Error: No project for this folder.',
                                           'Next: metaform add project <id> <path>']


@pytest.mark.req('STORE-022')
@pytest.mark.req('BASE-002')
def test_every_verb_keeps_its_data_in_the_store(run, hello, home):
    run('hello', 'greet', 'ada', cwd=hello)
    run('hello', 'wait', '0', cwd=hello)
    run('hello', 'history', cwd=hello)
    run('hello', 'forget', '--confirm', cwd=hello)
    files = {path.relative_to(home).parts for path in home.rglob('*') if path.is_file()}
    allowed = [lambda parts: parts[0].startswith('metaform.sqlite3'),
               lambda parts: parts[0] == 'projects' and (parts[-1].startswith(('project.sqlite3', 'source.txt'))
                                                          or '.metaform.sqlite3' in parts[-1]
                                                          or parts[-2:] == ('.metaform', 'provenance.json'))]
    assert [parts for parts in files if not any(rule(parts) for rule in allowed)] == []


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-035')
def test_the_status_hook_adds_a_line(run, hello):
    run('hello', 'greet', 'ada', cwd=hello)
    assert 'Hello: 1 greeted' in run(cwd=hello).stdout.splitlines()


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-016')
def test_beep_runs_only_on_its_own_system(run, hello):
    import platform
    on_windows = platform.system() == 'Windows'
    assert ('hello beep' in run('help', 'commands', cwd=hello).stdout) == on_windows
    if not on_windows:
        refused = run('hello', 'beep', cwd=hello, ok=False)
        assert refused.stderr.splitlines() == ['Error: hello beep runs on windows.', 'Next: metaform help hello']


@pytest.mark.req('BASE-019')
@pytest.mark.req('QUAL-016')
@pytest.mark.req('MAP-046')
def test_todo_writes_a_work_record_on_the_modules_own_element_and_done_resolves_it(run, hello):
    """A capability added for a feature gets a demonstration in hello; here a module writes the
    condition of its own element as a work record, apart from the map, and resolves it, MAP-046."""
    from metaform.data import Node, Store
    run('hello', 'greet', 'ada', cwd=hello)
    said = run('hello', 'todo', 'greet in every language', cwd=hello).stdout.strip()
    store = Store('proj')
    records = store.work(node=Node('element', 'code.module.hello')).results
    assert [(row.condition, row.task, row.done) for row in records] == [('unbuilt', 'greet in every language', None)]
    assert said == f'To do: greet in every language ({records[0].id})'
    assert store.element('code.module.hello', raw=True).open_work == ('unbuilt',)
    assert 'Hello: 1 greeted, 1 to do' in run(cwd=hello).stdout.splitlines()
    run('hello', 'done', records[0].id, 'greets in Latin now', cwd=hello)
    finished = store.work(node=Node('element', 'code.module.hello')).results[0]
    assert (finished.resolution, finished.done is not None) == ('greets in Latin now', True)
    assert store.element('code.module.hello', raw=True).open_work == ()
    assert 'Hello: 1 greeted' in run(cwd=hello).stdout.splitlines()


# Each public import a module can use, shown once, BASE-019.

@pytest.fixture
def loaded(hello):
    """hello loaded in this process, as a long-running server loads it; unloaded afterwards."""
    from metaform import loader
    loader.reset()
    try:
        yield loader.get('hello')
    finally:
        loader.reset()


def _verb(found, name):
    return next(verb for verb in found.module.verbs if verb.name == name)


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-035')
@pytest.mark.req('BASE-036')
def test_count_says_a_message_for_a_person_and_returns_the_data(run, hello):
    """ctx.say: the sentence is for a person; the data an agent needs is the return value, so --json keeps them
    apart."""
    run('hello', 'greet', 'ada', cwd=hello)
    assert run('hello', 'count', cwd=hello).stdout.splitlines() == ['hello has greeted 1 name.', 'greeted: 1']
    as_json = run('hello', 'count', '--json', cwd=hello)
    assert json.loads(as_json.stdout) == {'greeted': 1}
    assert as_json.stderr.splitlines() == ['hello has greeted 1 name.']


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-009')
@pytest.mark.req('BASE-010')
def test_welcome_publishes_from_an_async_verb(run, hello):
    """ctx.publish_async: an async verb publishes without blocking its loop, and the subscriber still records."""
    assert run('hello', 'welcome', 'ada', cwd=hello).stdout == 'welcome, ada\n'
    assert run('hello', 'history', cwd=hello).stdout.split() == ['ada']


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-018')
def test_later_greets_from_a_task_hello_owns_and_the_chassis_cancels_it(run, hello, loaded):
    """ctx.spawn: the task outlives the verb while the process runs, as in the MCP server, and belongs to hello, so
    ending the process or unloading hello cancels it."""
    from metaform import loader
    from metaform.module import context
    later = _verb(loaded, 'later')

    async def served():
        said = await later.run(context('hello', hello, nouns={'name': 'bob', 'seconds': 0}))
        owned = loader.tasks_of('hello')
        assert len(owned) == 1
        await asyncio.gather(*owned)
        await later.run(context('hello', hello, nouns={'name': 'cy', 'seconds': 3600}))
        (waiting,) = loader.tasks_of('hello')
        await loader.unload_async('hello')
        return said, waiting
    said, waiting = asyncio.run(served())
    assert said == 'Greeting bob in 0 s from a task hello owns; the chassis cancels the task if the process ends first.\n'
    assert waiting.cancelled()
    assert run('hello', 'history', cwd=hello).stdout.split() == ['bob']
    ended = run('hello', 'later', 'dee', '3600', cwd=hello)
    assert 'destroyed' not in ended.stderr and 'Event loop is closed' not in ended.stderr, ended.stderr
    assert run('hello', 'history', cwd=hello).stdout.split() == ['bob']


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-035')
@pytest.mark.req('CLI-009')
def test_greet_favorite_stops_with_one_next_step_when_no_favorite_is_set(run, hello):
    """Stop from a verb: what happened and the one command to run next, exit 2."""
    refused = run('hello', 'greet-favorite', cwd=hello, ok=False)
    assert refused.returncode == 2
    assert refused.stderr.splitlines() == ['Error: No favorite is set.', 'Next: metaform set --favorite <name>']
    run('hello', 'greet', 'zed', cwd=hello)
    run('set', '--favorite', 'zed', cwd=hello)
    assert run('hello', 'greet-favorite', cwd=hello).stdout == 'hello, zed\n'


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-018')
def test_start_runs_when_hello_loads_and_stop_when_it_unloads(run, hello, loaded):
    """Module start and stop: start sets up what the process uses before the first verb; stop takes it down."""
    from metaform import loader
    shown = run('hello', 'uptime', cwd=hello).stdout
    assert re.fullmatch(r'hello started \d+\.\d s ago in this process\.\n', shown), shown
    namespace = sys.modules[loaded.import_name]
    assert set(namespace._loaded) == {'at'}
    loader.unload('hello')
    assert namespace._loaded == {}


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-035')
def test_hello_with_no_verb_runs_its_default_verb(run, hello):
    """Module.default: `metaform hello` runs history; --help still prints the syntax."""
    run('hello', 'greet', 'ada', cwd=hello)
    assert run('hello', cwd=hello).stdout == 'ada\n'
    assert run('hello', '--help', cwd=hello).stdout.startswith('Usage: metaform hello <verb>')


@pytest.mark.req('BASE-019')
@pytest.mark.req('CLI-010')
@pytest.mark.req('CLI-027')
def test_repeat_reads_a_number_setting(run, hello):
    """settings.number: a whole number with a least and a most, a switch on the call and a stored setting."""
    assert run('hello', 'repeat', 'ada', cwd=hello).stdout == 'hello, ada\n'
    assert run('hello', 'repeat', 'ada', '--times', '3', cwd=hello).stdout == 'hello, ada\n' * 3
    run('set', '--times', '2', cwd=hello)
    assert run('hello', 'repeat', 'ada', cwd=hello).stdout == 'hello, ada\n' * 2
    refused = run('set', '--times', '0', cwd=hello, ok=False)
    assert refused.returncode == 2 and refused.stderr.splitlines()[0] == 'Error: --times is at least 1.'


@pytest.mark.req('BASE-019')
@pytest.mark.req('CLI-010')
@pytest.mark.req('CLI-027')
def test_greet_friends_greets_each_name_of_an_items_setting(run, hello):
    """settings.items: a list of names, stored or passed on the call, each greeted and recorded."""
    assert run('hello', 'greet-friends', cwd=hello).stdout == 'No friends set. Try: metaform set --friends ada,bob\n'
    run('set', '--friends', 'ada,bob', cwd=hello)
    assert run('hello', 'greet-friends', cwd=hello).stdout.splitlines() == ['hello, ada', 'hello, bob']
    assert run('hello', 'greet-friends', '--friends', 'cy', cwd=hello).stdout.splitlines() == ['hello, cy']
    assert run('hello', 'history', cwd=hello).stdout.split() == ['ada', 'bob', 'cy']


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-045')
@pytest.mark.req('STORE-043')
def test_report_saves_a_report_that_hellos_layer_carries_in_its_provenance(run, hello, home):
    """save_report: one report file in the home, never in the project folder, recorded on hello's layer."""
    from metaform.data import Store
    name = run('hello', 'report', 'Greets in English only.', cwd=hello).stdout.strip()
    layer = Store('proj').layer_ref('hello.greetings')
    assert name == f'{layer.id}-report.md'
    assert (own('proj') / 'reports' / name).read_text(encoding='utf-8') == 'Greets in English only.'
    assert [(ref.key, ref.value) for ref in Store('proj').provenance('hello.greetings').refs
            if ref.key == 'report'] == [('report', name)]
    assert list(hello.iterdir()) == []


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-045')
def test_feedback_saves_feedback_on_the_metaform_process_from_a_module(run, hello, home):
    """feedback: saved whatever it says, in the home, and its file names returned."""
    said = json.loads(run('hello', 'feedback', 'The greet help was clear.', '--json', cwd=hello).stdout)
    assert said['project'] == 'proj' and said['notices'] == []
    (name,) = said['files']
    assert name == f'{said["run"]}-feedback.md'
    assert (own('proj') / 'reports' / name).read_text(encoding='utf-8') == 'The greet help was clear.'


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-045')
def test_reports_lists_the_projects_report_files(run, hello):
    """list_reports: every report, feedback and shape file of the folder's project, one name a line."""
    assert run('hello', 'reports', cwd=hello).stdout == 'No reports yet.\n'
    report = run('hello', 'report', 'Greets in English only.', cwd=hello).stdout.strip()
    feedback = json.loads(run('hello', 'feedback', 'Clear.', '--json', cwd=hello).stdout)['files'][0]
    assert sorted(run('hello', 'reports', cwd=hello).stdout.splitlines()) == sorted([report, feedback])


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-045')
def test_read_report_reads_one_listed_file_exactly(run, hello):
    """read_report: the file's text exactly; a name that is not listed stops with the chassis's next step."""
    name = run('hello', 'report', 'Line one.\nLine two.', cwd=hello).stdout.strip()
    assert run('hello', 'read-report', name, cwd=hello).stdout == 'Line one.\nLine two.'
    refused = run('hello', 'read-report', 'nothing-report.md', cwd=hello, ok=False)
    assert refused.stderr.splitlines() == ['Error: No report nothing-report.md.', 'Next: metaform list reports']


@pytest.mark.req('BASE-019')
@pytest.mark.req('QUAL-016')
@pytest.mark.req('STORE-045')
def test_visit_and_note_keep_hellos_own_tables_beside_the_map_and_in_the_project_and_a_clear_keeps_the_notes(
        run, hello, home):
    assert run('hello', 'visit', 'ada', cwd=hello).stdout.strip() == 'ada: 1 visit'
    assert run('hello', 'visit', 'ada', cwd=hello).stdout.strip() == 'ada: 2 visits'
    run('hello', 'note', 'tea at four', cwd=hello)
    run('hello', 'note', 'call bob', cwd=hello)
    assert run('hello', 'notes', cwd=hello).stdout.splitlines() == ['tea at four', 'call bob']
    assert (own('proj') / 'modules' / 'hello.sqlite3').is_file()
    run('clear', 'project', 'proj', '--confirm', cwd=hello)
    assert run('hello', 'notes', cwd=hello).stdout.splitlines() == ['tea at four', 'call bob']
    assert run('hello', 'visit', 'ada', cwd=hello).stdout.strip() == 'ada: 1 visit'
    files = {path.relative_to(home).parts for path in home.rglob('*') if path.is_file()}
    allowed = [lambda parts: parts[0].startswith('metaform.sqlite3'),
               lambda parts: parts[0] == 'backups',
               lambda parts: parts[0] == 'projects' and (parts[-1].startswith(('project.sqlite3', 'source.txt'))
                                                          or '.metaform.sqlite3' in parts[-1]
                                                          or parts[-2:] == ('.metaform', 'provenance.json')
                                                          or parts[-2:-1] == ('modules',)
                                                          and parts[-1].startswith('hello.sqlite3'))]
    assert [parts for parts in files if not any(rule(parts) for rule in allowed)] == []  # STORE-022, corrected


@pytest.mark.req('BASE-035')
@pytest.mark.req('QUAL-016')
def test_node_read_adds_hellos_count_to_the_read_of_its_own_element_and_nothing_elsewhere(run, hello):
    run('hello', 'greet', 'ada', cwd=hello)
    run('hello', 'greet', 'bob', cwd=hello)
    read = json.loads(run('map', 'where', 'code.module.hello', 'contents=true', '--json', cwd=hello).stdout)
    assert read['hello'] == {'greeted': 2} and read['element']['address'] == 'code.module.hello'
    node = json.loads(run('map', 'node', 'element:code.module.hello', '--json', cwd=hello).stdout)
    assert node['hello'] == {'greeted': 2}
    from metaform.data import Store
    with Store('proj').atomic():
        Store('proj').add_element('hello.greetings', 'code.module.other')
    assert 'hello' not in json.loads(run('map', 'where', 'code.module.other', 'contents=true', '--json', cwd=hello).stdout)


@pytest.mark.req('BASE-035')
@pytest.mark.req('STORE-045')
@pytest.mark.req('QUAL-016')
def test_work_read_shows_hellos_own_field_on_its_work_record_and_the_store_layout_is_unchanged(run, hello):
    """Work f6adbefd, 2026-10-03: a module keeps its own fields on a work record, such as a dispatched agent's
    session id, without changing the store layout. hello keeps how many names it had greeted when a task was written,
    in its own table keyed by the work id, and `map work id=<id>` shows it under `hello`."""
    from metaform.data import Node, Store
    run('hello', 'greet', 'ada', cwd=hello)
    run('hello', 'greet', 'bob', cwd=hello)
    said = run('hello', 'todo', 'greet in every language', cwd=hello).stdout.strip()
    work_id = said.rsplit('(', 1)[1].rstrip(')')
    run('hello', 'greet', 'cy', cwd=hello)
    ticket = json.loads(run('map', 'work', f'id={work_id}', '--json', cwd=hello).stdout)
    assert ticket['id'] == work_id and ticket['hello'] == {'greeted': 2}
    assert 'hello: {"greeted":2}' in run('map', 'work', f'id={work_id}', cwd=hello).stdout.splitlines()
    with Store('proj', module='hello').tables(write=False) as tx:
        assert tx.get('todos', {'work_id': work_id}) == {'work_id': work_id, 'greeted': 2}
    other = Store('proj').add_work(Node('element', 'code.module.hello'), None, task='not hello\'s own')
    assert 'hello' not in json.loads(run('map', 'work', f'id={other.id}', '--json', cwd=hello).stdout)
    from metaform.modules.map import TABLES
    work_table = TABLES.table('work').schema.split('CREATE TABLE IF NOT EXISTS work(')[1].split(');')[0]
    assert [line.split()[0] for line in work_table.strip().splitlines()] == [
        'row', 'work_id', 'target_kind', 'target_id', 'condition', 'note', 'task', 'held', 'reviewed', 'created',
        'done', 'resolution', 'steps', 'steps_done', 'taken', 'taken_by', 'position', 'kind'], \
        'the work record layout is the map\'s own, a ticket\'s kind included, MAP-046; hello adds no column'
