"""Assigned tasks and dynamically selected skills, independent of organizational roles."""
from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

from metaform import prompt_files, skills
from metaform.module import Context, Module, Noun, Provides, Resource, Stop, Subscription, Verb, context, project_for

from .runtime import SERVICE, TABLES

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False
REMOTE_AGENT = True
PACKAGE = resources.files(__name__)


def catalog(ctx: Context) -> dict[str, Any]:
    return {'tasks': [{'name': 'user_agent', 'description': 'Interact with the user for the active project.',
                       'uri': 'metaform://tasks/definitions/user_agent'}],
            'skills': skills.listing(discoverable=True)}


def definition(ctx: Context) -> dict[str, Any]:
    name = str(ctx.nouns.get('name') or 'user_agent')
    if name != 'user_agent':
        raise Stop(f'No task definition {name}.', 'metaform tasks list')
    project = str(ctx.nouns.get('project_name') or ctx.project or ctx.folder.name)
    component = prompt_files.resolve('prompt.tasks:user_agent.txt', **{'{project}': project})
    return {'name': name, 'project': project, 'instructions': component['text'], 'component': component}


def assign(ctx: Context) -> dict[str, Any]:
    if ctx.nouns.get('folder'):
        folder = Path(str(ctx.nouns['folder'])).expanduser().resolve()
        project = project_for(folder)
        if project and project != ctx.project:
            ctx = context('tasks', folder, project=project, nouns=ctx.nouns, surface=ctx.surface,
                          session=ctx.session, identity=ctx.identity)
    name = str(ctx.nouns.get('name') or '')
    component = definition(ctx)['component'] if name else None
    return SERVICE.assign(ctx, name, component)


def inspect(ctx: Context) -> Any:
    return SERVICE.get(ctx, str(ctx.nouns['id']))


def update(ctx: Context) -> Any:
    return SERVICE.update(ctx, str(ctx.nouns['id']), dict(ctx.nouns['responses']))


def cancel(ctx: Context) -> Any:
    return SERVICE.cancel(ctx, str(ctx.nouns['id']))


def configure(ctx: Context) -> Any:
    return SERVICE.configure(ctx, str(ctx.nouns['id']), str(ctx.nouns.get('setting') or ''), str(ctx.nouns.get('value') or ''))


def changed(payload: dict[str, Any], ctx: Context) -> None:
    SERVICE.changed(ctx, payload)


MODULE = Module(
    id='tasks', summary='Discover task instructions, assign dedicated agents and follow their execution.',
    purpose='Runs explicit assignments with selected skills, without roles, commissions or required tickets.',
    tables=TABLES, provides=(Provides('task.lifecycle', SERVICE),),
    subscriptions=(Subscription('map.changed', changed),),
    resources=(Resource('metaform://tasks/definitions/{name}', 'Task definition',
                        'The complete instruction text of a named task.', 'read'),),
    verbs=(
        Verb('list', catalog, 'Discover task definitions and skills without loading their instruction bodies.',
             effect='read', needs_project=False),
        Verb('read', definition, 'Load a task’s full instructions before carrying out its assignment.',
             nouns=(Noun('name', 'Task definition name, such as user_agent.'),
                    Noun('project_name', 'Project name substituted for {project}.', required=False)),
             effect='read', needs_project=False),
        Verb('assign', assign, 'Assign a named or explicit task to a dedicated agent with selected skills; no ticket required.',
             nouns=(Noun('name', 'Named task definition; omit for an explicit task objective.', required=False),
                    Noun('text', 'Exact assignment, objectives, context and expected result.', required=False),
                    Noun('skills', 'Skills to load for this assignment only.', 'json', required=False,
                         schema={'type': 'array', 'items': {'type': 'string'}}),
                    Noun('agent', 'ACP agent adapter; omitted uses the project choice.', required=False),
                    Noun('folder', 'Working directory; defaults to the current project folder.', required=False),
                    Noun('project_name', 'Project name substituted for {project}.', required=False)),
             task='session', open_world=True),
        Verb('get', inspect, 'Read an assigned task’s progress, input requests or terminal result.',
             nouns=(Noun('id', 'Assigned task ID.'),), effect='read', needs_project=False),
        Verb('update', update, 'Supply responses for currently outstanding task input requests.',
             nouns=(Noun('id', 'Assigned task ID.'),
                    Noun('responses', 'Input responses keyed by the task’s outstanding request IDs.', 'json',
                         schema={'type': 'object', 'additionalProperties': True})), needs_project=False),
        Verb('cancel', cancel, 'Request cancellation of an assigned task.', nouns=(Noun('id', 'Assigned task ID.'),), needs_project=False),
        Verb('configure', configure, 'Set an option advertised by the assigned agent, including its planning mode.',
             nouns=(Noun('id', 'Assigned task ID.'), Noun('setting', 'Advertised configuration option ID; omit to list options.', required=False),
                    Noun('value', 'Advertised value.', required=False)), needs_project=False),
    ),
)
