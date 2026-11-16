"""intake: serves the intake procedure and says whether a project has been mapped, BASE-039.

The intake is agent work. An agent reads the procedure with `intake prompt`, or is handed it as its first turn by
dispatch, and records the map as it reasons it with the `project` tool, into the project store. This module holds no
map and records nothing: it serves the founder's procedure exactly as written, with what the person asked in the
procedure's own place for a request, followed by this module's own lines on how the procedure's records are written
with the tool.
"""
from __future__ import annotations

import hashlib
import os
import re
from importlib import resources
from pathlib import Path
from typing import Any

from metaform import home, project, prompt_files, settings
from metaform.module import Context, Module, Noun, Provides, Resource, Status, Stop, ToolbarItem, Verb

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False
REMOTE_AGENT = False  # a project wheel carries a map already built

RESOURCE = resources.files(__name__) / 'resources' / 'digital_typology.xml'  # the founder's procedure, the served intake
PROCEDURE_URI = 'metaform://intake/procedure'
TARGET = re.compile(r'<target\b[^>]*>')

settings.text('intake_file', '',
              help='An intake file to serve instead of the shipped procedure. Empty means the shipped procedure.')


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


def _escape(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _fill(tag: str, name: str, value: str) -> str:
    attribute = re.compile(rf'(\s{name}=")[^"]*(")')
    if attribute.search(tag):
        return attribute.sub(lambda match: match.group(1) + _escape(value) + match.group(2), tag, count=1)
    return tag.replace('<target', f'<target {name}="{_escape(value)}"', 1)


def _procedure(ctx: Context) -> tuple[Any, str, str]:
    """The chosen source with only project target bindings, before request-specific data."""
    chosen = ctx.setting('intake_file')
    source: Any = Path(chosen) if chosen else RESOURCE
    try:
        raw = source.read_bytes()
        text = raw.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
    except OSError:
        raise Stop(f'No intake file at {source}.', 'metaform unset --intake-file') from None
    except UnicodeDecodeError:
        raise Stop(f'The intake file {source} is not UTF-8 text.',
                   'save it as UTF-8, or metaform unset --intake-file') from None
    record = _registered(ctx)
    match = TARGET.search(text)
    if match is not None:
        tag = _fill(_fill(match.group(0), 'type', record.target_type), 'value', record.target_value)
        text = text[:match.start()] + tag + text[match.end():]
    text = text.replace('{project_id}', record.project_id)
    return source, text, hashlib.sha256(raw).hexdigest()


def _record_with_tool(ctx: Context) -> str:
    """How the procedure's records are written with the project tool, for this project by its name there."""
    return prompt_files.required(resources.files(__name__), 'schema_pointer',
                                 project=project.stored_name(_registered(ctx).project_id))


def procedure_component(ctx: Context) -> dict[str, Any]:
    """Exact source-body instructions, independent of appended launch/focus data.

    A custom source's middle Prompt slot can prevent substring reuse. Only a
    matching delivered body receives this component's receipt, never a stripped
    approximation of a different rendered procedure.
    """
    source, text, digest = _procedure(ctx)
    record = _registered(ctx)
    body = text.replace('{prompt}', '', 1).rstrip('\n')
    if body.strip():
        body += '\n\n' + _record_with_tool(ctx) + '\n'
    component = prompt_files.component('prompt.intake:procedure', body,
        version_id='intake-source:' + digest,
        bindings={'project': record.project_id, 'target_type': record.target_type,
                  'target_value': record.target_value, 'prompt': ''})
    component['source'] = {'kind': 'configured_file' if ctx.setting('intake_file') else 'shipped',
                           'path': str(source), 'sha256': digest}
    # A selected mode can fill a custom middle Prompt slot even on an empty
    # resource read. The combined tool guide remains an exact, satisfiable read.
    if '{prompt}' not in text:
        component['read'] = {'uri': PROCEDURE_URI}
    return component


def task_component(ctx: Context, **_bindings: str) -> dict[str, Any]:
    """Share the canonical procedure with assigned tasks, retaining its project bindings and source identity."""
    return procedure_component(ctx)


def served(ctx: Context, asked: str = '') -> str:
    """The stored procedure, binding the selected analysis mode and request through its Prompt parameter, BASE-039."""
    mode = str(ctx.nouns.get('mode') or '')
    if mode:
        if mode not in ('fresh', 'refine', 'resume'):
            raise Stop('Intake mode is fresh, refine or resume.', 'metaform help intake prompt')
        asked = prompt_files.required(resources.files(__name__), 'selected_mode', mode=mode, request=asked,
                                      project=project.stored_name(_registered(ctx).project_id))
    source, text, _ = _procedure(ctx)
    # What the person asked for, a target or a task; nothing asked leaves it empty, which the intake reads as this
    # project, BASE-039. An intake with a `{prompt}` slot gets the words there, escaped only in an XML intake file.
    # The Axiom intake declares its prompt as a parameter and has no slot, so what was asked follows it as data,
    # the way a skill's input is bound, and the script itself is served as written.
    xml = source.name.lower().endswith('.xml')
    if text.strip():  # then this module's own lines: how the procedure's records are written with the tool
        text = text.rstrip('\n') + '\n\n' + _record_with_tool(ctx) + '\n'
    if '{prompt}' in text:
        text = text.replace('{prompt}', _escape(asked) if xml else asked, 1)
    elif asked:
        text = text.rstrip('\n') + '\n\n<<DATA: Prompt>>\n' + asked + '\n<<END DATA>>\n'
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
    details="The procedure is served as stored, with what the person asked in the procedure's own place for a "
            'request, followed by how its records are written with the project tool. The map is recorded into the '
            'project store as it is reasoned and is read there; this module holds none of it.',
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
    resources=(
        Resource(PROCEDURE_URI, 'Intake procedure',
                 'The intake instructions for this project, the procedure an intake follows.', 'prompt'),
    ),
    # A map starts with an intake and is checked against the project with another; the page's dialog starts it.
    toolbar=(
        ToolbarItem('intake', 'Run an intake', 'Start an agent recording the map as it reads the project, or checking '
                    'the map against it.', icon='spark', page='intake', order=90),
    ),
)
