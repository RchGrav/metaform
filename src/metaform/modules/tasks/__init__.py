"""Assigned tasks and dynamically selected skills, independent of organizational roles."""
from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

from metaform import prompt_files, skills
from metaform.module import Context, Module, Noun, Provides, Resource, Stop, Subscription, Verb, context, project_for

from . import expertise, protocol
from .runtime import SERVICE, TABLES

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False
REMOTE_AGENT = True
PACKAGE = resources.files(__name__)


DEFINITIONS = {
    'user_agent': 'Interact with the user for the active project.',
    'worker': 'Persistent paired project work with node-scoped expertise.',
    'ticket_creation': 'Write a project ticket for a pair of agents.',
    'facilitator': 'Author portable reusable or receiver-bound expertise skills.',
}


def catalog(ctx: Context) -> dict[str, Any]:
    return {'tasks': [{'name': name, 'description': description,
                       'uri': f'metaform://tasks/definitions/{name}'} for name, description in DEFINITIONS.items()],
            'skills': expertise.catalog(ctx) if ctx.store is not None else []}


def definition(ctx: Context) -> dict[str, Any]:
    name = str(ctx.nouns.get('name') or 'user_agent')
    if name not in DEFINITIONS:
        raise Stop(f'No task definition {name}.', 'metaform tasks list')
    project = str(ctx.nouns.get('project_name') or ctx.project or ctx.folder.name)
    bindings = {'{project}': project}
    if ctx.nouns.get('agent_name'):
        bindings['{name variable}'] = str(ctx.nouns['agent_name'])
    component = prompt_files.resolve(f'prompt.tasks:{name}.txt', **bindings)
    return {'name': name, 'project': project, 'instructions': component['text'], 'component': component}


def project_expertise(ctx: Context) -> dict[str, Any]:
    node = ctx.nouns.get('node')
    op = str(ctx.nouns.get('op') or 'list')
    if op == 'list':
        return {'skills': expertise.catalog(ctx, node)}
    if op == 'read':
        return {key: value for key, value in expertise.read(ctx, str(ctx.nouns['skill']), node).items()
                if key != 'files'}
    if op == 'write':
        return expertise.put(ctx, str(ctx.nouns['node']), str(ctx.nouns['name']), str(ctx.nouns['text']),
                             str(ctx.nouns.get('description') or ''), ctx.nouns.get('skill'),
                             files=ctx.nouns.get('files'))
    raise Stop(f'Unknown expertise operation {op}.', 'metaform tasks expertise op=list')


def reusable(ctx: Context) -> dict[str, Any]:
    result = skills.publish(str(ctx.nouns['name']), str(ctx.nouns['text']),
                            str(ctx.nouns.get('description') or ''), ctx.nouns.get('files'))
    return {key: result[key] for key in ('uri', 'frontmatter', 'resources')}


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
    if 'tasks.board' in payload.get('tables', []):
        protocol.event(ctx, payload)
    else:
        SERVICE.changed(ctx, payload)


MODULE = Module(
    id='tasks', summary='Discover task instructions, assign dedicated agents and follow their execution.',
    purpose='Runs explicit assignments with selected skills, without roles, commissions or required tickets.',
    tables=TABLES, provides=(Provides('task.lifecycle', SERVICE), Provides('skill.document', expertise.resource)),
    subscriptions=(Subscription('map.changed', changed),),
    resources=(Resource('metaform://tasks/definitions/{name}', 'Task definition',
                        'The complete instruction text of a named task.', 'read'),),
    verbs=(
        Verb('list', catalog, 'Discover task definitions and skills without loading their instruction bodies.',
             effect='read', needs_project=False, nouns=(Noun('node', 'Current functional node for expertise discovery.', required=False),)),
        Verb('read', definition, 'Load a task’s full instructions before carrying out its assignment.',
             nouns=(Noun('name', 'Task definition name, such as user_agent.'),
                    Noun('project_name', 'Project name substituted for {project}.', required=False),
                    Noun('agent_name', 'Worker name substituted for {name variable}.', required=False)),
             effect='read', needs_project=False),
        Verb('assign', assign, 'Assign a named or explicit task to a dedicated agent with selected skills; no ticket required.',
             nouns=(Noun('name', 'Named task definition; omit for an explicit task objective.', required=False),
                    Noun('text', 'Exact assignment, objectives, context and expected result.', required=False),
                    Noun('skills', 'Skills to load for this assignment only.', 'json', required=False,
                         schema={'type': 'array', 'items': {'type': 'string'}}),
                    Noun('agent', 'ACP agent adapter; omitted uses the project choice.', required=False),
                    Noun('folder', 'Working directory; defaults to the current project folder.', required=False),
                    Noun('project_name', 'Project name substituted for {project}.', required=False),
                    Noun('node', 'Functional arrival node for selecting expertise.', required=False),
                    Noun('agent_name', 'Requested worker name.', required=False),
                    Noun('options', 'Native adapter configuration by advertised option ID.', 'json', required=False,
                         schema={'type': 'object', 'additionalProperties': True})),
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
        Verb('board', protocol.view, 'Read the live worker board, excluding the calling worker and its ratings.', effect='read'),
        Verb('message', protocol.message, 'Send an attributed message or invitation to any assigned agent.',
             nouns=(Noun('agent_id', 'Recipient task ID.'), Noun('text', 'Exact message text.'))),
        Verb('status', protocol.status, 'Update worker availability and canonical node assignments.',
             nouns=(Noun('agent_id', 'Worker task ID; defaults to the caller.', required=False),
                    Noun('state', 'Current availability description.', required=False),
                    Noun('nodes', 'Canonical node names, without expansion.', 'json', required=False,
                         schema={'type': 'array', 'items': {'type': 'string'}}),
                    Noun('current', 'Current ticket ID.', required=False), Noun('next', 'Accepted next ticket ID.', required=False),
                    Noun('waiting_for', 'Partner task ID whose completion should wake this worker.', required=False))),
        Verb('ticket', protocol.ticket, 'Write a ticket with a summary phrase and detailed work for a pair.',
             nouns=(Noun('summary', 'Concise task phrase.'), Noun('text', 'Requested outcome and pair allocation.'),
                    Noun('node', 'Functional element address or join:id.'))),
        Verb('worksheet', protocol.worksheet, 'Read or register the ticket checklist and planned element allocation.',
             nouns=(Noun('ticket', 'Ticket ID.'),
                    Noun('items', 'Checklist strings or objects with id, text, agent, nodes and done.', 'json', required=False,
                         schema={'type': 'array', 'items': {'anyOf': [{'type': 'string'}, {'type': 'object'}]}}),
                    Noun('holder', 'Ticket holder worker task ID; defaults to caller.', required=False),
                    Noun('partner', 'Accepted partner task ID.', required=False),
                    Noun('nodes', 'Canonical node names, preserved verbatim.', 'json', required=False,
                         schema={'type': 'array', 'items': {'type': 'string'}}))),
        Verb('pair', protocol.pair, 'Register a partnership accepted through messages, and its next/current work.',
             nouns=(Noun('ticket', 'Ticket ID.'), Noun('partner', 'Accepted partner worker task ID.'))),
        Verb('check', protocol.check, 'Mark a worksheet item and calculate the exact completion percentage.',
             nouns=(Noun('ticket', 'Ticket ID.'), Noun('item', 'Checklist item ID.'),
                    Noun('done', 'Whether this item is complete; defaults to true.', 'bool', required=False))),
        Verb('rate', protocol.rate, 'Record category points for a completed peer contribution; total possible points are 100.',
             nouns=(Noun('ticket', 'Ticket ID.'), Noun('scores', 'Category names and earned points; summed score is at most 100.',
                    'json', schema={'type': 'object', 'additionalProperties': {'type': 'number', 'minimum': 0}}),
                    Noun('target', 'Partner task ID; inferred from the registered pair when omitted.', required=False),
                    Noun('reviewer', 'Reviewer task ID for a caller outside a native task session.', required=False))),
        Verb('expertise', project_expertise, 'Discover, read or write project agent skills in the expertise knowledge layer.',
             nouns=(Noun('op', 'list, read or write.', required=False),
                    Noun('node', 'Functional element address or join:id.', required=False),
                    Noun('skill', 'Exact skill item ID, or scoped canonical name for read.', required=False),
                    Noun('name', 'Project skill name for write.', required=False),
                    Noun('text', 'Exact skill instruction text for write.', required=False),
                    Noun('description', 'Short skill description for discovery.', required=False),
                    Noun('files', 'Supporting resource paths and text.', 'json', required=False,
                         schema={'type': 'object', 'additionalProperties': {'type': 'string'}}))),
        Verb('reusable', reusable, 'Store a reusable SKILL.md and supporting resources served through the MCP Skills Extension.',
             nouns=(Noun('name', 'Canonical skill name.'), Noun('text', 'Full SKILL.md with YAML frontmatter, or body with description.'),
                    Noun('description', 'Description when authoring a plain instruction body.', required=False),
                    Noun('files', 'Supporting resource paths and their text contents.', 'json', required=False,
                         schema={'type': 'object', 'additionalProperties': {'type': 'string'}})), needs_project=False),
    ),
)
