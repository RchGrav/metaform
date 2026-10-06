"""Run the fork's checks and bind all six CI reports to the sources reviewed and built."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from metaform.module import Context, Stop

from .repository import PYTHONS, SYSTEMS, copy_module, dependencies, digest, modules, save_report

CHECK_TIMEOUT = 600


def check(ctx: Context) -> dict[str, Any]:
    system = {'darwin': 'macos', 'win32': 'windows'}.get(sys.platform, 'linux')
    python = f'{sys.version_info.major}.{sys.version_info.minor}'
    results: dict[str, dict[str, Any]] = {}
    for item in modules(ctx.folder):
        before = digest(item)
        errors: list[str] = []
        try:
            needed = dependencies(item)
        except (ValueError, TypeError, SyntaxError) as error:
            needed = []
            errors.append(f'dependency declaration: {error}')
        commands = ([('dependencies', ['uv', 'pip', 'install', '--python', sys.executable, *needed])]
                    if needed else [])
        commands.extend([
            ('type check', [sys.executable, '-m', 'pyright', '--pythonpath', sys.executable, str(item)]),
            ('lint', [sys.executable, '-m', 'ruff', 'check', str(item)]),
            ('tests', [sys.executable, '-m', 'pytest', '-q', str(item / 'tests')]),
        ])
        with tempfile.TemporaryDirectory(prefix='metaform-check-') as temporary:
            candidate_home = Path(temporary) / 'home'
            copy_module(item, candidate_home / 'modules' / item.name)
            environment = {**os.environ, 'METAFORM_HOME': str(candidate_home)}
            environment.pop('METAFORM_WHEEL', None)
            environment.pop(str(ctx.setting('fork_secret')), None)
            commands.insert(0, ('enable', [sys.executable, '-m', 'metaform', 'enable', item.name]))
            for name, command in commands:
                try:
                    result = subprocess.run(command, cwd=ctx.folder, env=environment, capture_output=True, text=True,
                                            encoding='utf-8', timeout=CHECK_TIMEOUT, check=False)
                    ctx.say(f'{item.name}, {name}:\n{result.stdout}{result.stderr}')
                    if result.returncode:
                        errors.append(f'{name} exited {result.returncode}')
                except (subprocess.TimeoutExpired, OSError) as error:
                    errors.append(f'{name}: {error}')
        if digest(item) != before:
            errors.append('checks changed the module sources')
        results[item.name] = {'digest': before, 'passed': not errors, 'reason': ', '.join(errors)}
    path = ctx.folder / '.metaform' / 'checks' / f'{system}-{python}.json'
    report: dict[str, Any] = {'system': system, 'python': python, 'modules': results}
    save_report(path, report)
    if any(not item['passed'] for item in results.values()):
        raise Stop(f'Module checks failed; results saved in {path}.', 'metaform help fork check')
    return {'report': str(path), 'modules': results}


def evidence(root: Path, candidates: list[Path]) -> dict[str, str]:
    """A failure excludes a module; missing, malformed or stale evidence aborts the build."""
    failures: dict[str, str] = {}
    for system in SYSTEMS:
        for python in PYTHONS:
            path = root / '.metaform' / 'checks' / f'{system}-{python}.json'
            try:
                report = json.loads(path.read_text(encoding='utf-8'))
                if report['system'] != system or report['python'] != python:
                    raise ValueError('the report names another matrix job')
                for item in candidates:
                    own = report['modules'][item.name]
                    if own['digest'] != digest(item):
                        raise ValueError(f'{item.name} changed after its checks')
                    if type(own['passed']) is not bool:
                        raise ValueError('passed must be a boolean')
                    if not own['passed']:
                        failures[item.name] = f'{system}, Python {python}: {own.get("reason") or "checks failed"}'
            except (OSError, KeyError, TypeError, ValueError) as error:
                raise Stop(f'Cannot build from {path.name}: {error}.', 'metaform help fork check') from None
    return failures
