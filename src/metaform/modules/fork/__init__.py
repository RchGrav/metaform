"""Maintain a user's own repository of modules over the released Metaform chassis, BASE-027."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from metaform import settings
from metaform.module import Context, Module, Noun, Verb

from . import repository
from .checks import check
from .review import upkeep, wheel

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False
REMOTE_AGENT = False  # it sets up a repository of the person's own modules, which is work done at home

settings.choice('fork_agent', ['codex', 'claude', 'gemini'], 'codex',
                help='The dispatched agent for CI muster and template upkeep.')
settings.text('fork_secret', 'OPENAI_API_KEY',
              help='The CI environment variable holding the selected agent\'s API key.',
              details='The workflow passes the repository secret to the agent. Its value is never put in a ticket.')


def init(ctx: Context) -> dict[str, Any]:
    return repository.init(Path(ctx.nouns['folder']).expanduser().resolve(), str(ctx.nouns['module']),
                           str(ctx.setting('fork_agent')), str(ctx.setting('fork_secret')))


MODULE = Module(
    id='fork',
    summary='Build and maintain your own repository of Metaform modules.',
    purpose='Sets up a repository of user modules over the released chassis, checks it on three systems, '
            'dispatches CI quality reviews before building its wheel, and dispatches template updates as pull requests. '
            'Use it when a user needs a feature built as a module. Details: metaform help fork.',
    details='Enable fork, map, dispatch and mcp. init writes only local files in a new or empty folder. '
            'Register the repository as a project before wheel or upkeep. check runs the current matrix job. '
            'wheel needs all six check reports and the configured agent secret. upkeep opens tickets for released '
            'template entries newer than each README Template version and runs their agents in turn. '
            'The agent owns its credentials. A dispatched upkeep agent opens a pull request through the repository\'s '
            'own authenticated GitHub CLI. The install-stage trigger is not connected yet.',
    verbs=(
        Verb('init', init, 'Create a module repository in a new or empty folder.',
             nouns=(Noun('folder', 'The local repository folder.'), Noun('module', 'The first module identifier.')),
             switches=('fork_agent', 'fork_secret')),
        Verb('check', check, 'Run type checking, lint and tests for each module, and save this matrix job\'s report.',
             surfaces=('cli',)),
        Verb('wheel', wheel, 'Dispatch a quality review per module, then build a wheel with those that passed.',
             switches=('fork_agent', 'fork_secret'), surfaces=('cli',)),
        Verb('upkeep', upkeep, 'Dispatch template updates for older modules, each as a pull request.',
             switches=('fork_agent',)),
    ),
)
