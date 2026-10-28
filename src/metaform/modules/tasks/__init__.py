"""Assigned tasks and dynamically selected skills, independent of organizational roles."""
from __future__ import annotations

from collections.abc import Callable
from importlib import resources
from pathlib import Path
from typing import Any

from metaform import prompt_files, settings, skills
from metaform.module import (
    Context,
    Module,
    Noun,
    Provides,
    Resource,
    Stop,
    Subscription,
    Verb,
    context,
    project_for,
    provided,
)

from . import protocol, skill_layer
from .runtime import SERVICE, TABLES

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False
REMOTE_AGENT = True
PACKAGE = resources.files(__name__)


DEFINITIONS = {
    'user_agent': 'Interact with the user for the active project.',
    'project_agent': 'Persistent paired work on assignments spanning tickets, with the skills of the skill layer.',
    'composer': 'Write the project tickets for pairs of agents; tickets that land together share a worktree.',
    'facilitator': 'Write reusable skills, or skills for the skill layer at the join on the receiving element.',
    'architect': 'Expand refined plans into codebase-grounded technical specifications.',
    'intake': 'Map project functionality and record its elements and purpose relationships through MCP.',
}


def _agents(ctx: Any = None) -> list[str]:
    """The agents dispatch starts, when it is enabled; Claude and Codex otherwise, so the choice is always offered."""
    folder = getattr(ctx, 'folder', None)
    found = provided(Path(folder), 'dispatch.agents') if folder else []
    return list(found[0][1]()) if found else ['claude', 'codex']


def _slot_choices(slot: str, option: str) -> Callable[[Any], list[str]]:
    """The values the slot's agent offers for a model or thinking level, as dispatch learned them at its last session
    here; default alone until then. Default leaves the agent on its own dispatch_<agent>_<option> setting."""
    def choices(ctx: Any = None) -> list[str]:
        folder = getattr(ctx, 'folder', None)
        agent = str(ctx.setting(slot) or '') if ctx is not None else ''
        found = provided(Path(folder), 'dispatch.option_choices') if folder and agent else []
        return list(found[0][1](agent, option)(ctx)) if found else ['default']
    return choices


# Agents start in pairs, even for one ticket: the person chooses each agent of the pair here, and each slot's model
# and thinking level, so one pair can be Opus with Sonnet. A slot left at default runs on its agent's own
# dispatch_<agent>_model and dispatch_<agent>_effort settings. Nothing chooses for the person (the owner's decision,
# 2026-10-25).
SLOTS = ('tasks_agent_1', 'tasks_agent_2')
for _slot, _label, _agent in ((SLOTS[0], 'Agent 1', 'claude'), (SLOTS[1], 'Agent 2', 'codex')):
    settings.choice(_slot, _agents, _agent, label=_label, category='agents', heading='Pairs',
                    help=f'{_label} of each pair tasks start begins.')
    settings.choice(f'{_slot}_model', _slot_choices(_slot, 'model'), 'default', label=f'{_label} model',
                    category='agents', heading='Pairs',
                    help=f'The model {_label.lower()} runs; default is its own dispatch model setting.')
    settings.choice(f'{_slot}_effort', _slot_choices(_slot, 'thought_level'), 'default',
                    label=f'{_label} thinking level', category='agents', heading='Pairs',
                    help=f'The thinking level {_label.lower()} runs at; default is its own dispatch effort setting.')
settings.boolean('tasks_full_auto', False, label='Full Auto', category='automation', heading='Worktrees',
                 help='When a worktree closes, merge its branch into the branch checked out in the project folder '
                      'and remove the worktree.',
                 details='Off: a closed worktree and its branch metaform/<name> stay for you to merge. On: what the '
                         'worktree holds is committed, merged into your checked-out branch and the worktree and '
                         'branch removed; a merge git refuses is undone, left in place and noted on its tickets.')


def catalog(ctx: Context) -> dict[str, Any]:
    """The task definitions, and the skill layer's skills followed by the reusable skills of the Metaform home, which
    need no project, so an agent finds them without the MCP Skills Extension."""
    shared = [{'name': entry['frontmatter']['name'], 'description': entry['frontmatter']['description'],
               'uri': entry['uri']} for entry in skills.reusable_catalog()]
    return {'tasks': [{'name': name, 'description': description,
                       'uri': f'metaform://tasks/definitions/{name}'} for name, description in DEFINITIONS.items()],
            'skills': (skill_layer.catalog(ctx) if ctx.store is not None else []) + shared}


def definition(ctx: Context) -> dict[str, Any]:
    name = str(ctx.nouns.get('name') or 'user_agent')
    if name not in DEFINITIONS:
        raise Stop(f'No task definition {name}.', 'metaform tasks list')
    project = str(ctx.nouns.get('project_name') or ctx.project or ctx.folder.name)
    bindings = {'{project}': project}
    if ctx.nouns.get('agent_name'):
        bindings['{name variable}'] = str(ctx.nouns['agent_name'])
    if name == 'intake':
        from metaform.modules.intake import task_component
        own = context('intake', ctx.folder, project=ctx.project, surface=ctx.surface,
                      session=ctx.session, identity=ctx.identity)
        component = task_component(own, **bindings)
    else:
        source = PACKAGE / 'resources' / f'{name}.txt'
        component = prompt_files.resolve_text(f'prompt.tasks:{name}.txt', source.read_bytes().decode('utf-8'),
                                              **bindings)
        component['source'] = {**component['source'], 'path': str(source)}
    return {'name': name, 'project': project, 'instructions': component['text'], 'component': component}


def project_skills(ctx: Context) -> dict[str, Any]:
    """The skill layer at a node: list its skills with their front matter, read one, or write one."""
    node = ctx.nouns.get('node')
    op = str(ctx.nouns.get('op') or 'list')
    if op == 'list':
        return {'skills': skill_layer.catalog(ctx, node)}
    if op == 'read':
        return {key: value for key, value in skill_layer.read(ctx, str(ctx.nouns['skill']), node).items()
                if key != 'files'}
    if op == 'write':
        return skill_layer.put(ctx, str(ctx.nouns['node']), str(ctx.nouns['name']), str(ctx.nouns['text']),
                               str(ctx.nouns.get('description') or ''), ctx.nouns.get('skill'),
                               files=ctx.nouns.get('files'))
    raise Stop(f'Unknown skill layer operation {op}.', 'metaform tasks skills op=list')


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


def start(ctx: Context) -> dict[str, Any]:
    """Start a pair of project agents, even for one ticket: agent 1 and agent 2 as the person's settings choose them,
    each on its own agent's model and thinking level settings."""
    started: list[dict[str, Any]] = []
    for slot in SLOTS:
        nouns: dict[str, Any] = {'name': 'project_agent', 'agent': str(ctx.setting(slot) or '') or None}
        options = {option: value for option, key in (('model', f'{slot}_model'), ('thought_level', f'{slot}_effort'))
                   if (value := str(ctx.setting(key) or '')) and value != 'default'}
        if options:
            nouns['options'] = options
        if ctx.nouns.get('node'):
            nouns['node'] = ctx.nouns['node']
        own = context('tasks', ctx.folder, project=ctx.project, nouns=nouns, surface=ctx.surface,
                      session=ctx.session, identity=ctx.identity)
        started.append(SERVICE.assign(own, 'project_agent', definition(own)['component']))
    return {'agents': started}


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
    tables=TABLES, provides=(Provides('task.lifecycle', SERVICE), Provides('skill.document', skill_layer.resource)),
    subscriptions=(Subscription('map.changed', changed),),
    resources=(Resource('metaform://tasks/definitions/{name}', 'Task definition',
                        'The complete instruction text of a named task.', 'read'),),
    verbs=(
        Verb('list', catalog, 'Discover task definitions and skills without loading their instruction bodies.',
             effect='read', needs_project=False, nouns=(Noun('node', 'Current functional node for skill discovery.', required=False),)),
        Verb('read', definition, 'Load a task’s full instructions before carrying out its assignment.',
             nouns=(Noun('name', 'Task definition name, such as user_agent.'),
                    Noun('project_name', 'Project name substituted for {project}.', required=False),
                    Noun('agent_name', 'Agent name substituted for {name variable}.', required=False)),
             effect='read', needs_project=False),
        Verb('assign', assign, 'Assign a named or explicit task to a dedicated agent with selected skills; no ticket required.',
             nouns=(Noun('name', 'Named task definition; omit for an explicit task objective.', required=False),
                    Noun('text', 'Exact assignment, objectives, context and expected result.', required=False),
                    Noun('skills', 'Skills to load for this assignment only.', 'json', required=False,
                         schema={'type': 'array', 'items': {'type': 'string'}}),
                    Noun('agent', 'ACP agent adapter; omitted uses the project choice.', required=False),
                    Noun('folder', 'Working directory; defaults to the current project folder.', required=False),
                    Noun('project_name', 'Project name substituted for {project}.', required=False),
                    Noun('node', 'Functional arrival node for selecting skills.', required=False),
                    Noun('options', 'Native adapter configuration by advertised option ID.', 'json', required=False,
                         schema={'type': 'object', 'additionalProperties': True})),
             task='session', open_world=True),
        Verb('start', start, 'Start a pair of project agents, agent 1 and agent 2 as the settings choose them, even for '
                             'one ticket.',
             nouns=(Noun('node', 'Functional arrival node for selecting skills.', required=False),),
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
        Verb('board', protocol.with_inbox(protocol.view), 'Read the live board: the other agents online with their scores and work, and the '
                                     'worktrees open on the project, claimed or free.', effect='read'),
        Verb('message', protocol.with_inbox(protocol.message), 'Send an attributed message or invitation to any assigned agent.',
             nouns=(Noun('agent_id', 'Recipient task ID.'), Noun('text', 'Exact message text.'))),
        Verb('status', protocol.with_inbox(protocol.status), 'Update an agent’s availability, canonical nodes and current or next worktree.',
             nouns=(Noun('agent_id', 'Agent task ID; defaults to the caller.', required=False),
                    Noun('state', 'starting, working, idle or waiting.', required=False),
                    Noun('nodes', 'Canonical node names, without expansion.', 'json', required=False,
                         schema={'type': 'array', 'items': {'type': 'string'}}),
                    Noun('current', 'Current worktree.', required=False), Noun('next', 'Accepted next worktree.', required=False),
                    Noun('waiting_for', 'Partner task ID whose completion should wake this agent.', required=False))),
        Verb('ticket', protocol.with_inbox(protocol.ticket), 'Write a ticket with a summary phrase and detailed work for a pair, in its worktree.',
             nouns=(Noun('summary', 'Concise task phrase.'), Noun('text', 'Requested outcome and pair allocation.'),
                    Noun('node', 'Functional element address or join:id.'),
                    Noun('worktree', 'The worktree the ticket shares with the tickets that land with it; omitted, the '
                                     'ticket is a worktree of its own.', required=False),
                    Noun('agents', 'The names of the agents who work it, the first claiming it and the next its '
                                   'partner; each one online is told.', 'json', required=False,
                         schema={'type': 'array', 'items': {'type': 'string'}}))),
        Verb('worksheet', protocol.with_inbox(protocol.worksheet), 'Read a worktree’s worksheet, or claim the worktree and register its '
                                              'unified checklist and planned element allocation.',
             nouns=(Noun('worktree', 'Worktree name.'),
                    Noun('items', 'Checklist strings or objects with id, text, ticket, agent, nodes and done.', 'json',
                         required=False, schema={'type': 'array', 'items': {'anyOf': [{'type': 'string'}, {'type': 'object'}]}}),
                    Noun('holder', 'The claiming agent’s task ID; defaults to caller.', required=False),
                    Noun('partner', 'Accepted partner task ID.', required=False),
                    Noun('nodes', 'Canonical node names, preserved verbatim.', 'json', required=False,
                         schema={'type': 'array', 'items': {'type': 'string'}}))),
        Verb('pair', protocol.with_inbox(protocol.pair), 'Register a partnership accepted through messages, and its next/current worktree.',
             nouns=(Noun('worktree', 'Worktree name.'), Noun('partner', 'Accepted partner task ID.'))),
        Verb('check', protocol.with_inbox(protocol.check), 'Mark a worksheet item and calculate the exact completion percentage.',
             nouns=(Noun('worktree', 'Worktree name.'), Noun('item', 'Checklist item ID.'),
                    Noun('done', 'Whether this item is complete; defaults to true.', 'bool', required=False))),
        Verb('rate', protocol.with_inbox(protocol.rate), 'Rate an agent at the close of a worktree, stars of five in each category and the '
                                    'bonus, or say you worked alone; the worktree closes once every participant has.',
             nouns=(Noun('worktree', 'Worktree name.'),
                    Noun('scores', 'Stars 0 to 5 by category: Efficient, Alert & Aware, Thorough, Coordination.', 'json',
                         required=False,
                         schema={'type': 'object', 'additionalProperties': {'type': 'number', 'minimum': 0, 'maximum': 5}}),
                    Noun('bonus', 'true when the agent improved the final work beyond critiquing it: +5.', 'bool',
                         required=False),
                    Noun('target', 'The agent rated; the registered counterpart when omitted.', required=False),
                    Noun('alone', 'true when there was no one to rate.', 'bool', required=False),
                    Noun('reviewer', 'Reviewer task ID for a caller outside a native task session.', required=False))),
        Verb('handoff', protocol.handoff, 'Hand your place to a new project agent on the same agent: it starts with '
                                          'your handoff as its input, takes your worktrees and partners, and your own '
                                          'task ends. At 50% of your context, once the task in hand is finished.',
             nouns=(Noun('text', 'The handoff: what is done, what is in hand, what comes next, and where.'),
                    Noun('agent_id', 'The task ID of the agent handing off; defaults to the caller.', required=False)),
             task='session', open_world=True),
        Verb('skills', project_skills, 'Discover, read or write the skill layer: project skills at a node, each with its '
                                       'front matter.',
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
