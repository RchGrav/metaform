"""Stage 2: import a functional map, then read it with where and element."""
import json
from pathlib import Path

FIXTURE = Path(__file__).parent / 'fixtures' / 'kitchen_timer.xml'


def project(run, tmp_path):
    work = tmp_path / 'kitchen'
    work.mkdir(exist_ok=True)
    run('add', 'project', 'kitchen', str(work))
    return work


def test_import_counts_roots_joins_and_subtypes(run, tmp_path):
    work = project(run, tmp_path)
    out = run('map', 'import', str(FIXTURE), cwd=work).stdout
    assert 'Imported into kitchen: 3 elements, 2 joins, 1 internal subtypes' in out


def test_import_needs_a_project(run, tmp_path):
    result = run('map', 'import', str(FIXTURE), cwd=tmp_path, ok=False)
    assert result.stderr.splitlines() == ['Error: This folder has no project.',
                                          'Next: metaform add project <id> <path>']


def test_where_finds_the_join_and_the_subtype_citing_a_file(run, tmp_path):
    work = project(run, tmp_path)
    run('map', 'import', str(FIXTURE), cwd=work)
    hits = json.loads(run('map', 'where', 'src/tick.c', '--json', cwd=work).stdout)['hits']
    assert [(hit['kind'], hit['address']) for hit in hits] == [('subtype', 'code.loop.tick')]
    assert hits[0]['receiver'] == 'exterior.cook.home' and hits[0]['provider'] == 'code.timer.kitchen'
    within = json.loads(run('map', 'where', 'src/tick.c', '--json', cwd=work).stdout)['within']
    assert [item['address'] for item in within] == ['code.timer.kitchen']
    alarm = json.loads(run('map', 'where', 'alarm.c', '--json', cwd=work).stdout)['hits']
    assert [(hit['kind'], hit['address']) for hit in alarm] == [('join', 'code.alarm.audible')]


def test_where_on_an_uncited_file_says_so(run, tmp_path):
    work = project(run, tmp_path)
    run('map', 'import', str(FIXTURE), cwd=work)
    assert 'No element or join cites src/nothing.c.' in run('map', 'where', 'src/nothing.c', cwd=work).stdout


def test_element_shows_role_joins_both_ways_and_subtypes(run, tmp_path):
    work = project(run, tmp_path)
    run('map', 'import', str(FIXTURE), cwd=work)
    de = json.loads(run('map', 'element', 'code.timer.kitchen', '--json', cwd=work).stdout)
    assert de['role'] == 'DE' and de['reading'] == 'kitchen timer code'
    assert [join['provider'] for join in de['owns']] == ['code.alarm.audible']
    assert [join['receiver'] for join in de['provides']] == ['exterior.cook.home']
    assert [sub['namespace_address'] for sub in de['subtypes']] == ['code.loop.tick']


def test_subtype_is_read_from_its_parent_join_and_is_not_a_root(run, tmp_path):
    work = project(run, tmp_path)
    run('map', 'import', str(FIXTURE), cwd=work)
    sub = json.loads(run('map', 'element', 'code.loop.tick', '--json', cwd=work).stdout)
    assert sub['kind'] == 'subtype'
    assert sub['parent'] == {'receiver': 'exterior.cook.home', 'provider': 'code.timer.kitchen'}
    roots = run('map', 'list', cwd=work).stdout.split()
    assert 'code.loop.tick' not in roots and 'code.timer.kitchen' in roots


def test_unknown_address_names_the_next_step(run, tmp_path):
    work = project(run, tmp_path)
    run('map', 'import', str(FIXTURE), cwd=work)
    result = run('map', 'element', 'code.nothing', cwd=work, ok=False)
    assert result.stderr.splitlines() == ['Error: No element or internal subtype at code.nothing.',
                                          'Next: metaform map list']


def test_reimporting_the_same_map_changes_nothing(run, tmp_path):
    work = project(run, tmp_path)
    run('map', 'import', str(FIXTURE), cwd=work)
    assert 'unchanged' in run('map', 'import', str(FIXTURE), cwd=work).stdout


def test_changed_join_gets_a_new_revision_and_the_old_one_stays(run, tmp_path, home):
    work = project(run, tmp_path)
    run('map', 'import', str(FIXTURE), cwd=work)
    changed = tmp_path / 'changed.xml'
    changed.write_text(FIXTURE.read_text().replace('plays a tone', 'flashes a light'))
    run('map', 'import', str(changed), cwd=work)
    de = json.loads(run('map', 'element', 'code.timer.kitchen', '--json', cwd=work).stdout)
    assert 'flashes a light' in de['owns'][0]['function']
    assert de['owns'][0]['revision'] == 2
    from metaform import store
    old = store.Store('kitchen').read(de['owns'][0]['ref'] | {'revision': 1})
    assert 'plays a tone' in old['function']


def test_data_is_global_not_in_the_project_folder(run, tmp_path, home):
    work = project(run, tmp_path)
    run('map', 'import', str(FIXTURE), cwd=work)
    assert not any(path.name == '.metaform' for path in work.rglob('*'))
    assert (home / 'projects' / 'kitchen' / 'store.sqlite3').is_file()
