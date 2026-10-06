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
