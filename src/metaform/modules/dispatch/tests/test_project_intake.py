"""Architect designs get their own project before the authored intake runs."""
import importlib
import json
from pathlib import Path

import pytest

from metaform import home as registry
from metaform.data import Store
from metaform.module import Context, Stop

pytestmark = pytest.mark.kind('simulation')


def active_dispatch(folder):
    """Patch the module that supplies the enabled native transport, including loader-owned package aliases."""
    from metaform.module import provided
    transport = provided(folder, 'task.transport')[0][1]
    return importlib.import_module(type(transport).__module__.rpartition('.')[0])


@pytest.fixture(autouse=True)
def enabled(run, tmp_path, monkeypatch):
    run('enable', 'dispatch', cwd=tmp_path)
    dispatch = active_dispatch(tmp_path)
    monkeypatch.setattr(dispatch, 'runnable', lambda *args: None)

    def no_live_start(*args, **kwargs):
        pytest.fail('A launch test must replace the enabled transport spawn before assigning an intake.')
    monkeypatch.setattr(dispatch, 'spawn', no_live_start)


def test_design_gets_free_folder_registration_and_authored_intake(home, tmp_path, monkeypatch):
    from metaform.modules import intake
    dispatch = active_dispatch(tmp_path)

    user_home = tmp_path / 'user'
    user_home.mkdir()
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: user_home))
    existing = user_home / 'dish-clock'
    existing.mkdir()
    (existing / 'keep.txt').write_text('untouched')
    other = tmp_path / 'other'
    other.mkdir()
    registry.add_project('dish-clock-2', other)
    design = '# Dish Clock\nNotify cooks when dishes finish.\n'
    monkeypatch.setattr(dispatch, 'runnable', lambda *args: None)
    launched = []

    def launch(store, work_id, agent, flags, mode, *, kept, ctx):
        assert mode == 'task' and any(flag.startswith('task=') for flag in flags)
        assert 'intake=true' not in flags and 'system=true' not in flags
        assert ctx.folder == user_home / 'dish-clock-3'
        assert ctx.project == store.project_id == 'dish-clock-3'
        with Store(store.project_id, module='dispatch').tables(write=False) as tx:
            asked = json.loads(tx.get('raised', {'work_id': work_id})['asked'])
        assert asked['name'] == 'intake' and design in asked['input']
        assert asked['instructions'] == asked['component']['text']
        launched.append(ctx)
        return {'pid': 12345}

    monkeypatch.setattr(dispatch, 'spawn', launch)
    result = dispatch.intake(Context('dispatch', tmp_path, nouns={
        'project_name': 'Dish Clock!', 'text': design, 'agent': 'codex'}))
    assert result['project'] == 'dish-clock-3'
    assert result['folder'] == str(user_home / 'dish-clock-3')
    assert result['state'] == 'starting', result
    assert registry.project(result['project']).path == result['folder']
    # The agent records after launch releases the existing intake lock.
    [ctx] = launched
    target = Context('intake', ctx.folder, project=ctx.project, store=Store(ctx.project))
    intake.start(target)
    target.nouns = {'namespace_address': 'code.timer.kitchen', 'role': 'DE'}
    intake.element(target)
    target.nouns = {}
    intake.finish(target)
    assert Store(result['project']).has_intake()
    assert Store(result['project']).element('code.timer.kitchen') is not None
    assert (existing / 'keep.txt').read_text() == 'untouched'
    assert list(existing.iterdir()) == [existing / 'keep.txt']
    assert registry.project('dish-clock-2').path == str(other)


@pytest.mark.parametrize('name,design', [('!!!', 'design'), ('clock', ''), ('clock', '   ')])
def test_invalid_design_input_creates_nothing(home, tmp_path, monkeypatch, name, design):
    dispatch = active_dispatch(tmp_path)

    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    before = set(tmp_path.iterdir())
    with pytest.raises(Stop):
        dispatch.intake(Context('dispatch', tmp_path, nouns={'project_name': name, 'text': design}))
    assert set(tmp_path.iterdir()) == before


def test_failed_launch_keeps_project_for_explicit_retry(home, tmp_path, monkeypatch):
    dispatch = active_dispatch(tmp_path)

    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(dispatch, 'runnable', lambda *args: None)

    def fail(*args, **kwargs):
        raise Stop('No free agent slots.', 'metaform dispatch agents')

    monkeypatch.setattr(dispatch, 'spawn', fail)
    result = dispatch.intake(Context('dispatch', tmp_path, nouns={
        'project_name': 'Clock', 'text': 'Clock design', 'agent': 'codex'}))
    assert result['state'] == 'failed'
    assert result['project'] == 'clock'
    assert result['folder'] == str(tmp_path / 'clock')
    assert 'No free agent slots.' in result['error']
    assert registry.project('clock') is not None
    with Store('clock', module='dispatch').tables(write=False) as tx:
        assert not tx.rows('raised', limit=0).results


@pytest.mark.parametrize('kind', ['file', 'symlink'])
def test_existing_file_or_dangling_symlink_reserves_name(home, tmp_path, monkeypatch, kind):
    dispatch = active_dispatch(tmp_path)

    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    existing = tmp_path / 'clock'
    if kind == 'file':
        existing.write_text('keep')
    else:
        try:
            existing.symlink_to(tmp_path / 'absent', target_is_directory=True)
        except OSError:
            pytest.skip('Symlinks unavailable.')
    monkeypatch.setattr(dispatch, 'runnable', lambda *args: None)
    monkeypatch.setattr(dispatch, 'spawn', lambda *args, **kwargs: {'pid': 12345})
    result = dispatch.intake(Context('dispatch', tmp_path, nouns={
        'project_name': '../CLOCK', 'text': 'Clock design', 'agent': 'codex'}))
    assert result['project'] == 'clock-2'
    assert Path(result['folder']).parent == tmp_path
    if kind == 'file':
        assert existing.read_text() == 'keep'
    else:
        assert existing.is_symlink() and existing.readlink() == tmp_path / 'absent'


def test_registration_failure_removes_only_created_empty_folder(home, tmp_path, monkeypatch):
    dispatch = active_dispatch(tmp_path)

    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))

    def fail(*args, **kwargs):
        raise OSError('Registry unavailable')

    monkeypatch.setattr(registry, 'add_project', fail)
    with pytest.raises(OSError, match='Registry unavailable'):
        dispatch.intake(Context('dispatch', tmp_path, nouns={'project_name': 'clock', 'text': 'Clock design'}))
    assert not (tmp_path / 'clock').exists()


def test_cli_accepts_design_intake_without_current_project(run, tmp_path):
    result = run('dispatch', 'intake', 'project_name=clock', cwd=tmp_path, ok=False)
    assert result.returncode != 0
    assert 'Provide the design and its project name.' in result.stdout + result.stderr
    assert 'No project for this folder.' not in result.stdout + result.stderr


@pytest.mark.req('PROJ-030')
@pytest.mark.parametrize('inherited', [False, True])
@pytest.mark.parametrize('override', [None, 'claude'])
def test_new_project_keeps_saved_default_after_intake(home, tmp_path, monkeypatch, inherited, override):
    from metaform import settings
    from metaform.modules import intake
    dispatch = active_dispatch(tmp_path)
    from metaform.modules.web.server import module_verb

    source = tmp_path / 'source'
    source.mkdir()
    work = source / 'work'
    work.mkdir()
    registry.add_project('source', source)
    settings.put('dispatch_agent', 'codex', source if inherited else work)
    user_home = tmp_path / 'user'
    user_home.mkdir()
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: user_home))
    monkeypatch.setattr(dispatch, 'runnable', lambda *args: None)
    launched = []
    monkeypatch.setattr(dispatch, 'spawn', lambda store, work_id, agent, *args, **kwargs:
                        launched.append(agent) or {'pid': 12345})
    nouns = {'project_name': 'Clock', 'text': 'Clock design'}
    if override:
        nouns['agent'] = override
    result = dispatch.intake(Context('dispatch', work, project='source', nouns=nouns))
    assert result['state'] == 'starting', result
    assert result['agent'] == (override or 'codex')
    folder = Path(result['folder'])
    assert settings.value('dispatch_agent', work) == 'codex'
    assert settings.value('dispatch_agent', folder) == 'codex'
    # The page reads the new project's default, separately from its intake session's agent.
    assert module_verb({'project': result['project']}, 'dispatch', 'agents', {})['default'] == 'codex'
    target = Context('intake', folder, project=result['project'], store=Store(result['project']))
    intake.start(target)
    target.nouns = {'namespace_address': 'code.timer.kitchen', 'role': 'DE'}
    intake.element(target)
    target.nouns = {}
    intake.finish(target)
    # A later unqualified intake, including a fresh base, still starts Codex.
    dispatch.intake(Context('dispatch', folder, project=result['project'], store=Store(result['project']),
                            nouns={'map': 'new', 'name': 'fresh'}))
    assert launched == [override or 'codex', 'codex']
    assert settings.value('dispatch_agent', folder) == 'codex'


@pytest.mark.parametrize('override', ['agent', 'switch'])
def test_intake_override_without_saved_default_stays_temporary(home, tmp_path, monkeypatch, override):
    from metaform import settings
    dispatch = active_dispatch(tmp_path)

    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(dispatch, 'runnable', lambda *args: None)
    monkeypatch.setattr(dispatch, 'spawn', lambda *args, **kwargs: {'pid': 12345})
    nouns = {'project_name': 'Clock', 'text': 'Clock design'}
    switches = {}
    if override == 'agent':
        nouns['agent'] = 'codex'
    else:
        switches['dispatch_agent'] = 'codex'
    result = dispatch.intake(Context('dispatch', tmp_path, nouns=nouns, switches=switches))
    assert result['agent'] == 'codex'
    assert settings.value('dispatch_agent', Path(result['folder'])) == 'claude'
    assert settings.state('dispatch_agent', Path(result['folder'])) == 'default'
    assert settings.state('dispatch_agent', tmp_path) == 'default'


def test_failed_codex_intake_keeps_default_and_error_for_retry(home, tmp_path, monkeypatch):
    from metaform import settings
    dispatch = active_dispatch(tmp_path)

    source = tmp_path / 'source'
    source.mkdir()
    settings.put('dispatch_agent', 'codex', source)
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(dispatch, 'runnable', lambda *args: None)
    launched = []

    def fail(store, work_id, agent, *args, **kwargs):
        launched.append(agent)
        raise Stop('Codex usage limit reached.', 'Check your Codex quota.')

    monkeypatch.setattr(dispatch, 'spawn', fail)
    result = dispatch.intake(Context('dispatch', source, nouns={'project_name': 'Clock', 'text': 'Clock design'}))
    assert result['state'] == 'failed'
    assert result['error'] == 'Codex usage limit reached.'
    assert launched == ['codex']
    folder = Path(result['folder'])
    assert settings.value('dispatch_agent', source) == settings.value('dispatch_agent', folder) == 'codex'
    monkeypatch.setattr(dispatch, 'spawn', lambda store, work_id, agent, *args, **kwargs:
                        launched.append(agent) or {'pid': 12345})
    retried = dispatch.intake(Context('dispatch', folder, project=result['project'], store=Store(result['project'])))
    assert retried['agent'] == 'codex'
    assert launched == ['codex', 'codex']
