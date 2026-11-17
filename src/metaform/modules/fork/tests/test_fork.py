"""A user's repository supplies modules over the released chassis, BASE-027."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

pytestmark = [pytest.mark.req('BASE-027'), pytest.mark.kind('simulation')]


def candidate(root, name, version='0.2.0'):
    folder = root / name
    folder.mkdir()
    (folder / '__init__.py').write_text(
        "from metaform.module import Module\n"
        "SUPPORTED_OS = ('linux', 'macos', 'windows')\n"
        "DEPENDENCIES = ()\nSHIPS_DISABLED = True\n"
        f"MODULE = Module(id='{name}', summary='A feature.', purpose='A feature for this user.')\n",
        encoding='utf-8')
    (folder / 'README.md').write_text(f'# {name}\n\n## Template version\n\n{version}\n', encoding='utf-8')
    return folder


@pytest.fixture
def fork_context(run, store, project_folder):
    for name in ('fork', 'dispatch', 'map', 'mcp'):
        run('enable', name)
    from metaform.module import context
    return context('fork', project_folder, project=store.project_id)


def reports(ctx, modules, failed=()):
    from metaform.modules.fork.repository import digest
    folder = ctx.folder / '.metaform' / 'checks'
    folder.mkdir(parents=True)
    for system in ('linux', 'macos', 'windows'):
        for python in ('3.11', '3.14'):
            (folder / f'{system}-{python}.json').write_text(json.dumps({
                'system': system, 'python': python,
                'modules': {item.name: {'digest': digest(item), 'passed': item.name not in failed,
                                      'reason': 'tests failed' if item.name in failed else ''}
                            for item in modules},
            }), encoding='utf-8')


def test_setup_makes_a_module_repository_without_a_chassis(run, tmp_path):
    folder = tmp_path / 'my-features'
    run('enable', 'fork')
    run('fork', 'init', str(folder), 'alarm')
    assert (folder / 'alarm' / '__init__.py').exists()
    assert not (folder / 'src' / 'metaform').exists()
    workflow = (folder / '.github' / 'workflows' / 'metaform.yml').read_text()
    assert all(system in workflow for system in ('ubuntu-latest', 'macos-latest', 'windows-latest'))
    assert 'pull_request_target' not in workflow
    assert 'dispatch' in (folder / 'README.md').read_text()
    before = (folder / 'alarm' / '__init__.py').read_bytes()
    refused = run('fork', 'init', str(folder), 'alarm', ok=False)
    assert refused.returncode == 2
    assert (folder / 'alarm' / '__init__.py').read_bytes() == before


def test_wheel_carries_only_the_module_that_passed_and_runs_directly(fork_context, monkeypatch, capsys):
    from metaform.module import call
    from metaform.modules.fork import review, wheel

    good = candidate(fork_context.folder, 'good')
    bad = candidate(fork_context.folder, 'bad')
    reports(fork_context, [good, bad])
    monkeypatch.setenv('OPENAI_API_KEY', 'simulation-key')

    async def dispatch(ctx, work_id, agent):
        record = ctx.require_store().ticket(work_id).work
        passed = 'code.module.good' == record.address
        ctx.require_store().finish_work(work_id, json.dumps({
            'passed': passed, 'reason': 'meets QUAL-001' if passed else 'No behavior tests.'}))

    monkeypatch.setattr(review, 'dispatch', dispatch)
    # Run the real builder in its isolated interpreter. Simulate dependency resolution only.
    def pack(folder, environment):
        script = """
from pathlib import Path
from metaform import build, home, loader
for item in loader.discover():
    home.set_module_state(item.id, False)
home.set_module_state('good', True)
loader.reset()
build._carry = lambda *args: ({}, [])
print(build.build(Path.cwd())[0])
"""
        result = subprocess.run([sys.executable, '-c', script], cwd=folder, env=environment,
                                text=True, capture_output=True, timeout=30, check=True)
        return Path(result.stdout.strip()), []

    monkeypatch.setattr(review, 'pack', pack)
    result = call(wheel, fork_context)
    with zipfile.ZipFile(result['wheel']) as archive:
        names = archive.namelist()
        assert 'metaform/modules/good/__init__.py' in names
        assert 'metaform/modules/bad/__init__.py' not in names
        assert '__main__.py' in names and 'metaform/cli.py' in names
    assert result['excluded'] == {'bad': 'No behavior tests.'}
    assert 'bad: left out: No behavior tests.' in capsys.readouterr().err
    probe = subprocess.run([sys.executable, result['wheel'], '--version'], cwd=fork_context.folder,
                           env={**os.environ, 'PYTHONPATH': ''}, text=True, capture_output=True,
                           timeout=30, check=True)
    assert probe.stdout.startswith('metaform ')


def test_upkeep_worktrees_keep_updates_separate_and_leave_the_checkout_unchanged(tmp_path):
    from metaform.modules.fork.repository import update_worktree
    root = tmp_path / 'repo'
    root.mkdir()
    candidate(root, 'first')
    candidate(root, 'second')
    (root / '.gitignore').write_text('.metaform/\n', encoding='utf-8')
    def git(*args):
        return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True,
                              text=True, timeout=30).stdout.strip()
    git('init')
    git('config', 'user.name', 'Fork simulation')
    git('config', 'user.email', 'fork@example.invalid')
    git('add', '.')
    git('commit', '-m', 'Module requirements')
    original = git('branch', '--show-current')
    first = update_worktree(root, 'first-update')
    (first / 'first' / 'README.md').write_text('# updated first module\n', encoding='utf-8')
    second = update_worktree(root, 'second-update')
    assert '0.2.0' in (second / 'first' / 'README.md').read_text()
    assert '0.2.0' in (root / 'first' / 'README.md').read_text()
    assert git('branch', '--show-current') == original
    assert update_worktree(root, 'first-update') == first


def test_matrix_checks_enable_candidate_runtime_and_report_a_failure(fork_context, monkeypatch):
    from metaform.module import Stop
    from metaform.modules.fork import checks
    from metaform.modules.fork.checks import check
    candidate(fork_context.folder, 'runtime')
    seen = []
    def command(argv, **kwargs):
        environment = kwargs['env']
        assert (Path(environment['METAFORM_HOME']) / 'modules' / 'runtime' / '__init__.py').exists()
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 5 if 'pytest' in argv else 0, '', '')
    monkeypatch.setattr(checks.subprocess, 'run', command)
    with pytest.raises(Stop, match='checks failed'):
        check(fork_context)
    assert any(command[-2:] == ['enable', 'runtime'] for command in seen)
    report = next((fork_context.folder / '.metaform' / 'checks').glob('*.json'))
    assert json.loads(report.read_text())['modules']['runtime']['passed'] is False


def test_matrix_tests_can_call_the_candidate_through_metaform(fork_context):
    from metaform.modules.fork.checks import check
    module = candidate(fork_context.folder, 'runtime')
    # Development installs use an editable import hook that Pyright cannot follow.
    source = Path(__file__).resolve().parents[4]
    (fork_context.folder / 'pyproject.toml').write_text(
        '[tool.pyright]\nextraPaths = ' + json.dumps([str(source)]) + '\n', encoding='utf-8')
    (module / '__init__.py').write_text(
        "from metaform.module import Context, Module, Verb\n\n"
        "SUPPORTED_OS = ('linux', 'macos', 'windows')\n"
        "DEPENDENCIES = ()\nSHIPS_DISABLED = True\n"
        "def greeting(ctx: Context) -> str:\n    return 'running'\n"
        "MODULE = Module(id='runtime', summary='Greeting.', purpose='Serve a greeting.', "
        "verbs=(Verb('greet', greeting, 'Say hello.'),))\n", encoding='utf-8')
    tests = module / 'tests'
    tests.mkdir()
    (tests / 'test_runtime.py').write_text(
        "import subprocess\nimport sys\n\n\n"
        "def test_command():\n"
        "    result = subprocess.run([sys.executable, '-m', 'metaform', 'runtime', 'greet'], "
        "text=True, capture_output=True, check=True)\n"
        "    assert result.stdout.strip() == 'running'\n", encoding='utf-8')
    assert check(fork_context)['modules']['runtime']['passed'] is True


@pytest.mark.parametrize('declaration', [
    "DEPENDENCIES = ('needed>=1',)\n",
    "DEPENDENCIES: tuple[str, ...] = ('needed>=1',)\n",
    'from .manifest import DEPENDENCIES\n',
])
def test_dependency_preparation_accepts_the_chassis_declarations(tmp_path, declaration):
    from metaform.modules.fork.repository import dependencies
    module = candidate(tmp_path, 'feature')
    (module / '__init__.py').write_text(declaration, encoding='utf-8')
    if declaration.startswith('from'):
        (module / 'manifest.py').write_text("DEPENDENCIES = ('needed>=1',)\n", encoding='utf-8')
    assert dependencies(module) == ['needed>=1']
    (module / 'manifest.py').write_text("DEPENDENCIES = ('different',)\n", encoding='utf-8')
    if not declaration.startswith('from'):
        with pytest.raises(ValueError, match='differs'):
            dependencies(module)


def test_pack_prepares_approved_requirements_before_loading_modules(tmp_path, monkeypatch):
    from metaform.modules.fork import review
    home = tmp_path / 'home'
    (home / 'modules').mkdir(parents=True)
    module = candidate(home / 'modules', 'feature')
    (module / 'manifest.py').write_text("DEPENDENCIES = ('needed>=1',)\n", encoding='utf-8')
    (module / '__init__.py').write_text('from .manifest import DEPENDENCIES\n', encoding='utf-8')
    artifact = tmp_path / 'built.whl'
    artifact.touch()
    commands = []
    def run(argv, **kwargs):
        commands.append(argv)
        output = f'Wheel: {artifact}\n' if argv[-1] == 'build' else 'template shipped\n'
        return subprocess.CompletedProcess(argv, 0, output, '')
    monkeypatch.setattr(review.subprocess, 'run', run)
    assert review.pack(tmp_path, {'METAFORM_HOME': str(home)})[0] == artifact
    assert commands[0] == ['uv', 'pip', 'install', '--python', sys.executable, 'needed>=1']
    assert ['enable', 'feature'] in [command[-2:] for command in commands]


def test_public_dispatch_call_disables_automatic_merge(fork_context, monkeypatch):
    from metaform.module import Module, Verb, call
    from metaform.modules.fork import review
    seen = []
    async def run(ctx):
        seen.append(ctx)
        return {'ended': 'done'}
    fake = Module(id='dispatch', summary='Simulation.', purpose='Verify public dispatch calls.',
                  verbs=(Verb('run', run, 'Simulation.'),))
    monkeypatch.setattr(review, 'surface', lambda folder: [fake])
    assert call(review.dispatch, fork_context, 'ticket', 'codex')['ended'] == 'done'
    assert seen[0].switches['dispatch_worktrees'] is False
    assert seen[0].nouns == {'id': 'ticket', 'agent': 'codex'}


def test_completed_upkeep_pr_does_not_start_another_update(fork_context, monkeypatch):
    from metaform.module import call
    from metaform.modules.fork import repository, review, upkeep
    candidate(fork_context.folder, 'old')
    monkeypatch.setattr(repository, 'template_changelog', lambda: '## 0.3.0\n- Updated contract.\n')
    monkeypatch.setattr(repository, 'update_worktree', lambda root, work_id: root)
    started = []
    async def dispatch(ctx, work_id, agent):
        started.append(work_id)
        ctx.require_store().finish_work(work_id, 'https://github.example.invalid/module/pull/1')
    monkeypatch.setattr(review, 'dispatch', dispatch)
    first = call(upkeep, fork_context)
    second = call(upkeep, fork_context)
    assert first['tickets'] == second['tickets']
    assert len(started) == 1


def test_missing_secret_stops_before_dispatch_or_build(fork_context, monkeypatch):
    from metaform.module import Stop, call
    from metaform.modules.fork import review, wheel

    candidate(fork_context.folder, 'good')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setattr(review, 'pack', lambda *args: pytest.fail('unchecked wheel built'))
    with pytest.raises(Stop, match='OPENAI_API_KEY'):
        call(wheel, fork_context)
    assert not (fork_context.folder / 'dist').exists()


@pytest.mark.parametrize('fault', ['missing', 'changed', 'failed', 'incomplete-verdict'])
def test_unproven_modules_cannot_enter_the_wheel(fork_context, monkeypatch, fault):
    from metaform.module import Stop, call
    from metaform.modules.fork import review, wheel

    good = candidate(fork_context.folder, 'good')
    reports(fork_context, [good], failed=['good'] if fault == 'failed' else [])
    monkeypatch.setenv('OPENAI_API_KEY', 'simulation-key')
    if fault == 'missing':
        (fork_context.folder / '.metaform' / 'checks' / 'windows-3.14.json').unlink()
    if fault == 'changed':
        (good / '__init__.py').write_text('# different module\n', encoding='utf-8')
    async def dispatch(ctx, work_id, agent):
        if fault != 'incomplete-verdict':
            ctx.require_store().finish_work(work_id, '{"passed": true, "reason": "looks fine"}')
    monkeypatch.setattr(review, 'dispatch', dispatch)
    monkeypatch.setattr(review, 'pack', lambda *args: pytest.fail('unproven module built'))
    with pytest.raises(Stop):
        call(wheel, fork_context)


def test_upkeep_records_newer_entries_once_and_dispatches_a_pr_task(fork_context, monkeypatch):
    from metaform.module import call
    from metaform.modules.fork import repository, review, upkeep

    candidate(fork_context.folder, 'old', '0.2.0')
    candidate(fork_context.folder, 'current', '0.3.0')
    monkeypatch.setattr(repository, 'template_changelog', lambda:
                        '## 0.3.0\n\n- New public service.\n\n## 0.2.0\n\n- Earlier service.\n')
    monkeypatch.setattr(repository, 'update_worktree', lambda root, work_id: root)
    started = []
    async def dispatch(ctx, work_id, agent):
        started.append(work_id)
        record = ctx.require_store().ticket(work_id).work
        assert 'New public service.' in record.task and 'Earlier service.' not in record.task
        assert 'pull request' in record.task.lower()
        assert '0.3.0' in record.task
        # Leave it open as an interrupted ACP session would.
    monkeypatch.setattr(review, 'dispatch', dispatch)
    first = call(upkeep, fork_context)
    second = call(upkeep, fork_context)
    assert len(first['tickets']) == len(second['tickets']) == 1
    assert first['tickets'] == second['tickets']
    assert len(fork_context.require_store().work(open=True, limit=0).results) == 1


@pytest.fixture
def in_project_store(fork_context, home):
    """proj with its map in the project store: code and code.module.good are elements there, code.module a bare step.
    Its tickets are the tickets overlay's records (kickoff 2026-11-17, t-legacy-keep); the service stops at the end."""
    from metaform import project
    from metaform.project import owner, service
    for path, role in (('proj.code', 'Defining Element'), ('proj.code.module.good', 'Supporting Element')):
        assert project.run({'add': {path: {'technical_name': path.rsplit('.', 1)[1], 'name': path.rsplit('.', 1)[1],
                                           'role': role}}}) == {'status': 'ok'}
    yield fork_context
    service.stop(home)
    owner.close_all()


def stored_tickets():
    from metaform import project
    return {one['id']: one for one in project.overlay_records('proj', 'tickets') or []}


def test_muster_on_a_project_in_the_project_store_is_a_ticket_there_and_its_verdict_is_read_from_it(
        in_project_store, run):
    from metaform.modules.fork import review
    ctx = in_project_store
    record = review.ticket(ctx, ctx.folder / 'good', 'Review the module.', 'CI muster of good, source abc.')
    one = stored_tickets()[record['id']]
    assert one['element'] == 'proj.code.module.good' and one['task'] == 'Review the module.'
    assert not ctx.require_store().work(limit=0).results  # the old store gets no ticket, and no fork layer
    run('map', 'work', 'op=done', f'id={one["id"]}', 'resolution={"passed": true, "reason": "Tests cover it."}',
        'why=Reviewed against the standard', cwd=ctx.folder)
    assert review.verdict(ctx, str(one['id'])) == (True, 'Tests cover it.')


def test_upkeep_on_a_project_in_the_project_store_files_once_at_the_nearest_element_held(
        in_project_store, run, monkeypatch):
    from metaform.module import call
    from metaform.modules.fork import repository, review, upkeep
    ctx = in_project_store
    candidate(ctx.folder, 'old', '0.2.0')
    monkeypatch.setattr(repository, 'template_changelog', lambda: '## 0.3.0\n\n- New public service.\n')
    monkeypatch.setattr(repository, 'update_worktree', lambda root, work_id: root)
    started = []

    async def dispatch(ctx, work_id, agent):
        started.append(work_id)
        assert 'New public service.' in str(stored_tickets()[work_id]['task'])
        run('map', 'work', 'op=done', f'id={work_id}', 'resolution=https://github.example.invalid/module/pull/1',
            'why=The pull request is open', cwd=ctx.folder)
    monkeypatch.setattr(review, 'dispatch', dispatch)
    first = call(upkeep, ctx)
    second = call(upkeep, ctx)
    assert first['tickets'] == second['tickets'] and len(started) == 1  # a completed upkeep starts no other
    assert stored_tickets()[first['tickets'][0]]['element'] == 'proj.code'  # the nearest element, not the bare step


def test_a_module_ticket_with_no_element_on_its_path_in_the_project_store_is_refused_by_name(fork_context, home):
    from metaform import project
    from metaform.module import Stop
    from metaform.modules.fork import review
    from metaform.project import owner, service
    assert project.run({'add': {'proj.upstream.harness': {'technical_name': 'harness', 'name': 'harness',
                                                          'role': 'Defining Element'}}}) == {'status': 'ok'}
    try:
        with pytest.raises(Stop, match='keeps no layer'):
            review.ticket(fork_context, fork_context.folder / 'old', 'Update it.', 'Template upkeep of old.')
        assert not stored_tickets()
    finally:
        service.stop(home)
        owner.close_all()


@pytest.mark.req('BASE-047')
@pytest.mark.parametrize('transition', ['newer', 'handed', 'first', 'same', 'downgrade', 'blocked', 'failed'])
def test_install_transition_runs_existing_upkeep_only_after_a_newer_success(
        fork_context, monkeypatch, tmp_path, transition):
    from metaform import home, install, loader
    from metaform.module import Stop, call

    (fork_context.folder / 'pyproject.toml').write_text(
        '[tool.metaform.fork]\nrepository = true\n', encoding='utf-8')
    candidate(fork_context.folder, 'old', '0.2.0')
    candidate(fork_context.folder, 'current', '0.3.0')
    # Installation is global, so the caller need not be inside the module repository.
    monkeypatch.chdir(tmp_path)
    loader.follow_enabled()
    module = next(item for item in loader.enabled() if item.id == 'fork')
    upkeep = next(verb.run for verb in module.verbs if verb.name == 'upkeep')
    review = sys.modules[upkeep.__module__]
    repository = review.repository
    monkeypatch.setattr(install, '__version__', '2026.10.1.10')
    previous = {'same': '2026.10.1.10', 'downgrade': '2026.10.1.11',
                'blocked': '2026.10.1.11'}.get(transition, '2026.9.30.9')
    if transition != 'first':
        home.set_meta('installed_version', previous)
    monkeypatch.setattr(install.shutil, 'which', lambda name: None)
    commands = []
    def run(tool, argv, **kwargs):
        commands.append(argv)
        return subprocess.CompletedProcess(argv, 1 if transition == 'failed' else 0, '', 'install failed')
    monkeypatch.setattr(install, '_run', run)
    if transition == 'handed':
        monkeypatch.setenv('METAFORM_WHEEL', str(tmp_path / 'metaform.whl'))
        monkeypatch.setattr(loader, 'withdrawn', lambda: frozenset())
    monkeypatch.setattr(repository, 'template_changelog', lambda: '## 0.3.0\n- New contract.\n')
    monkeypatch.setattr(repository, 'update_worktree', lambda root, work_id: root)
    started = []
    async def dispatch(ctx, work_id, agent):
        # The stage's write transaction must already be committed before upkeep writes or launches an agent.
        assert home.meta('installed_version') == '2026.10.1.10'
        assert ctx.project == fork_context.project and ctx.folder == fork_context.folder
        record = ctx.require_store().ticket(work_id).work
        assert record.address == 'code.module.old'
        assert 'New contract.' in record.task and 'pull request' in record.task
        started.append(work_id)
        ctx.require_store().finish_work(work_id, 'https://github.example.invalid/module/pull/1')
    monkeypatch.setattr(review, 'dispatch', dispatch)
    output = []
    wheel = tmp_path / 'metaform.whl'
    if transition in ('failed', 'blocked'):
        with pytest.raises(install.Failed if transition == 'failed' else Stop):
            install.stage(wheel, 'uv', False, output.append, 'retry')
        assert home.meta('installed_version') == previous
    else:
        install.stage(wheel, 'uv', transition == 'downgrade', output.append, 'retry')
    if transition == 'handed':
        assert not started and not fork_context.require_store().work(limit=0).results
        # The installed process consumes the stage's handover before AI-tool setup.
        monkeypatch.delenv('METAFORM_WHEEL', raising=False)
        monkeypatch.setenv(install.HANDED, str(wheel))
        monkeypatch.setenv(install.UPKEEP, install.__version__)
        monkeypatch.setattr(install, '_python_ok', lambda: False)
        with pytest.raises(Stop, match='older than Metaform needs'):
            install.install([], output.append)
        assert install.UPKEEP not in os.environ
    work = fork_context.require_store().work(limit=0).results
    if transition in ('newer', 'handed', 'first'):
        assert len(started) == len(work) == 1, output
        # Reinstalling and manual upkeep retain the completed PR and its original work record.
        install.stage(wheel, 'uv', False, output.append, 'retry')
        assert call(upkeep, fork_context)['tickets'] == started
        assert len(started) == 1
    else:
        assert started == [] and not work
    assert bool(commands) == (transition != 'blocked')


def test_install_upkeep_failure_retains_manual_retry_and_continues_other_repositories(
        fork_context, monkeypatch, tmp_path):
    from metaform import home, loader
    from metaform.data import Store
    from metaform.module import Stop, call
    monkeypatch.chdir(tmp_path)
    loader.follow_enabled()
    module = next(item for item in loader.enabled() if item.id == 'fork')
    upkeep = next(verb.run for verb in module.verbs if verb.name == 'upkeep')
    review = sys.modules[upkeep.__module__]
    repository = review.repository

    other = tmp_path / 'other-fork'
    ordinary = tmp_path / 'ordinary-project'
    other.mkdir()
    ordinary.mkdir()
    home.add_project('other', other)
    home.add_project('ordinary', ordinary)
    for folder in (fork_context.folder, other):
        (folder / 'pyproject.toml').write_text('[tool.metaform.fork]\nrepository = true\n', encoding='utf-8')
        candidate(folder, 'old')
    # An ordinary project can hold Python packages without being a module repository.
    candidate(ordinary, 'unrelated')
    monkeypatch.setattr(repository, 'template_changelog', lambda: '## 0.3.0\n- New contract.\n')
    def worktree(root, work_id):
        if root == fork_context.folder:
            raise Stop('Commit your module repository changes.', 'metaform help fork upkeep')
        return root
    monkeypatch.setattr(repository, 'update_worktree', worktree)
    started = []
    async def dispatch(ctx, work_id, agent):
        started.append(ctx.project)
        ctx.require_store().finish_work(work_id, 'https://github.example.invalid/module/pull/1')
    monkeypatch.setattr(review, 'dispatch', dispatch)
    output = []
    fork_context.sink = output.append
    delivered = fork_context.publish('install.completed', {'version': '2026.10.1.10'})
    assert next(item for item in delivered if item['module'] == 'fork')['status'] == 'completed'
    assert started == ['other']
    assert len(Store('other').work(limit=0).results) == 1
    assert not Store('ordinary').work(limit=0).results
    waiting = fork_context.require_store().work(open=True, limit=0).results
    assert len(waiting) == 1
    assert any('metaform fork upkeep' in line and str(fork_context.folder) in line for line in output)
    monkeypatch.setattr(repository, 'update_worktree', lambda root, work_id: root)
    assert call(upkeep, fork_context)['tickets'] == [waiting[0].id]
    assert started == ['other', fork_context.project]
