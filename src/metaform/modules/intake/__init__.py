"""intake: serves the intake procedure and says whether a project has been mapped, BASE-039.

The intake is agent work. An agent reads the procedure with `intake prompt`, or is handed it as its first turn by
dispatch, and records the map as it reasons it with the `project` tool, into the project store. This module holds no
map and records nothing.

The procedure is the founder's, as Markdown sections beside the project tool (`metaform.project.intake`, from
`core/metaform/intake/procedure/`). An agent performing an intake is a clean-context agent with that one purpose, so it
is given the whole procedure inline, assembled from those same sections, with the selected mode and what the person
asked in the procedure's own place for a request (its `{prompt}`), followed by this module's own lines on how the
procedure's records are written with the tool. Other agents read the sections they need by address. There is no second
copy of the procedure (the founder, 2026-11-17).
"""
from __future__ import annotations

import hashlib
import os
from importlib import resources
from typing import Any

from metaform import home, project, prompt_files
from metaform.module import Context, Module, Noun, Provides, Status, Stop, ToolbarItem, Verb
from metaform.project import intake as procedure

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False
REMOTE_AGENT = False  # a project wheel carries a map already built

PROMPT_SLOT = '{prompt}'  # where the procedure's prompt section takes the request, as the founder's text writes it
HERE = resources.files(__name__)


def _registered(ctx: Context) -> home.Project:
    """The registered project of the command's folder."""
    found = home.project(ctx.project or '')
    if found is None:
        raise Stop('No project for this folder.',
                   'metaform add project <id> <path> for this folder, or metaform set --project <id> for a registered one')
    return found


def mapped(ctx: Context) -> bool:
    """Whether the project store holds a map of the command's project."""
    return bool(ctx.project) and project.holds(project.stored_name(str(ctx.project)))


def _procedure() -> tuple[str, str]:
    """The whole procedure, assembled from its sections, and the digest of that text."""
    text = procedure.whole()
    if not text.strip():
        raise Stop('The intake procedure has no sections.', 'reinstall Metaform: its intake procedure is missing')
    return text, hashlib.sha256(text.encode('utf-8')).hexdigest()


def _record_with_tool(ctx: Context) -> str:
    """How the procedure's records are written with the project tool, for this project by its name there."""
    return prompt_files.markdown(HERE, 'schema_pointer', project=project.stored_name(_registered(ctx).project_id))


def procedure_component(ctx: Context) -> dict[str, Any]:
    """The procedure an intake is given, without the request: the sections inline and this module's recording lines,
    with the identity of that text, so a runner knows which version each turn carried."""
    text, digest = _procedure()
    record = _registered(ctx)
    body = text.replace(PROMPT_SLOT, '', 1).rstrip('\n') + '\n\n' + _record_with_tool(ctx) + '\n'
    component = prompt_files.component('prompt.intake:procedure', body, version_id='intake-sections:' + digest,
                                       bindings={'project': record.project_id, 'target_type': record.target_type,
                                                 'target_value': record.target_value, 'prompt': ''})
    component['source'] = {'kind': 'shipped', 'path': 'metaform.project/procedure', 'sha256': digest}
    return component


def task_component(ctx: Context, **_bindings: str) -> dict[str, Any]:
    """Share the canonical procedure with assigned tasks, retaining its project bindings and source identity."""
    return procedure_component(ctx)


def served(ctx: Context, asked: str = '') -> str:
    """The whole procedure for an agent performing an intake: its sections inline, the selected mode and the request in
    the procedure's own place for a request, this module's recording lines, and what the intake must not read."""
    mode = str(ctx.nouns.get('mode') or '')
    if mode:
        if mode not in ('fresh', 'refine', 'resume'):
            raise Stop('Intake mode is fresh, refine or resume.', 'metaform help intake prompt')
        asked = prompt_files.markdown(HERE, 'selected_mode', mode=mode, request=asked,
                                      project=project.stored_name(_registered(ctx).project_id))
    text, _ = _procedure()
    # What the person asked for, a target or a task; nothing asked leaves it empty, which the intake reads as this
    # project, BASE-039.
    text = text.rstrip('\n') + '\n\n' + _record_with_tool(ctx) + '\n'
    if PROMPT_SLOT in text:
        text = text.replace(PROMPT_SLOT, asked, 1)
    elif asked:
        text = text.rstrip('\n') + '\n\n' + asked + '\n'
    ignored = home.ignore_patterns(_registered(ctx).path)
    if ignored:  # the one thing added after the intake: what it must not read, from .metaform/ignore.txt
        text = (text.rstrip('\n') + '\n\nDo not read these paths; they are not the project ('
                + home.IGNORE_FILE + '):\n' + '\n'.join(ignored) + '\n')
    return text


def prompt(ctx: Context) -> str:
    return served(ctx, ctx.nouns.get('text') or '')


def status_verb(ctx: Context) -> str:
    _registered(ctx)
    if mapped(ctx):
        name = project.stored_name(str(ctx.project))
        return f'This project has a map in the project store, as {name}. Read it with the project tool: {{"map": "{name}"}}.\n'
    return 'No intake yet. Read the instructions with metaform intake prompt.\n'


def status(ctx: Context) -> Status:
    here = resources.files(__name__)
    if os.environ.get('METAFORM_SESSION') or os.environ.get('METAFORM_ROLE') not in (None, '', 'none'):
        # An agent a dispatch runner started has its work, given as its first turn: the intake's onboarding, which
        # asks an agent to handle it first, is for the person's own agent, never for one dispatched, BASE-052.
        if ctx.store is None:
            return Status()
        return Status(lines=('Intake: complete' if mapped(ctx) else 'Intake: none yet',))
    if ctx.store is None:
        # A folder not registered yet gets the onboarding too, with registering as its first step: the instructions
        # are sent once at connect, so a notice that waited for registration would never arrive, MCP-009.
        step = '   ' + prompt_files.required(here, 'register_step') + '\n'
        return Status(instruction=prompt_files.required(here, 'no_intake', register=step))
    if mapped(ctx):
        return Status(lines=('Intake: complete',))
    return Status(lines=('Intake: none yet',), instruction=prompt_files.required(here, 'no_intake'))


def first_run(ctx: Context) -> str | None:
    """Intake's first-run text, `no_intake`, while the project has no map, with the register step while the folder is
    no registered project, as `status` gives it at connect; None otherwise, and to an agent a runner started. Offered
    as `intake.first_run`, so the MCP server serves it whole as metaform://firstrun."""
    got = status(ctx)
    return got.instruction if got.at_connect and got.instruction else None


MODULE = Module(
    id='intake',
    summary='Serve the intake procedure an agent follows to map a project.',
    purpose='Serves the intake procedure and says whether this project has been mapped. The intake is agent work: an '
            'agent reads the procedure with the command prompt and records the map with the project tool. Details: '
            'metaform help intake.',
    details="The procedure is the founder's Markdown sections, given whole to an agent performing an intake, with "
            "what the person asked in the procedure's own place for a request, followed by how its records are "
            'written with the project tool. The map is recorded into the project store as it is reasoned and is read '
            'there; this module holds none of it.',
    verbs=(
        Verb('prompt', prompt, "Read the intake instructions an agent follows to record this project's map.",
             nouns=(Noun('text', 'path to the target for the intake process; leaving this blank means this project',
                         required=False),
                    Noun('mode', 'Selected analysis: fresh maps the project from the beginning, refine corrects and '
                                 'completes the map recorded, resume continues an intake left unfinished.',
                         required=False, schema={'type': 'string', 'enum': ['fresh', 'refine', 'resume']})),
             effect='read'),
        Verb('status', status_verb, 'Say whether this project has been mapped.', effect='read'),
    ),
    status=status,
    provides=(Provides('intake.first_run', first_run), Provides('intake.task_component', task_component)),
    # A map starts with an intake and is checked against the project with another; the page's dialog starts it.
    toolbar=(
        ToolbarItem('intake', 'Run an intake', 'Start an agent recording the map as it reads the project, or checking '
                    'the map against it.', icon='spark', page='intake', order=90),
    ),
)
