"""Workflow authoring, ingest and call transport for the Axiom agent interpreter."""
from __future__ import annotations

import json
import os
import time
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import Any, cast

from metaform import axiom, home, prompt_files, settings
from metaform import skills as skill_registry
from metaform.data import Store, StoreError, prompts
from metaform.module import Context, Module, Noun, Stop, Verb, held_role

from . import catalog, executor, runs
from . import preprocess as preprocessing
from .binding import Logic, Lookup, destination
from .element import ElementValue, Value, element_value

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = True
REMOTE_AGENT = True  # workflows run from the CLI over the carried map
PACKAGE = resources.files(__name__)

# The owner placeholders of prompt-lexicalization that choose how it works, LAYER-017; each choice is the script's
# own wording, the default the first it lists for unresolved spans and the footer for addresses.
UNRESOLVED = ['keep wording', 'mark missing', 'stop and ask']
PLACEMENT = ['inline after each name', 'one block of name -> address']
settings.choice('lexicalize_unresolved', UNRESOLVED, 'keep wording',
                help='How prompt lexicalization handles a span with no entry in the map.',
                details='The UNRESOLVED_POLICY of prompt-lexicalization: keep wording, mark missing or stop and ask.')
settings.choice('lexicalize_addresses', PLACEMENT, 'one block of name -> address',
                help='Where prompt lexicalization attaches namespace addresses.',
                details='The ADDRESS_PLACEMENT of prompt-lexicalization: inline after each name, or one block of '
                        'name -> address.')
settings.choice('preprocess_knowledge', ['context', 'whole'], 'context',
                help='How much selected knowledge accompanies a preprocessed prompt.',
                details='context includes knowledge visible at the supplied addresses; whole includes all visible '
                        'items of the layers selected there. Both preserve selection and masks, and context reads '
                        'retain the map\'s always_show items. Default context keeps the job\'s prepared context small.')


LIBS = skill_registry.LIBS
SKILLS = ('scan', 'write_workflow', 'import_workflow', 'workflow_efficiency', 'prompt_efficiency',
          'workflow_builder', 'workflow_evaluator', 'sentinel', 'code_links')


def _prompts() -> None:
    skill_registry.seed()
    prompts.shipped('prompt-lexicalization', 'text', prompt_files.required(PACKAGE, 'prompt-lexicalization'))


def lexicalize(ctx: Context) -> dict[str, Any]:
    _prompts()
    return {'prompt': prompts.prompt_version('prompt-lexicalization').text,
            'inputs': {'Prompt_Text': ctx.nouns['text'],
                       'MAP_READ': 'metaform map where <address>; over MCP, map_where',
                       'PROMPT_STORE': ('metaform prompt save <name> <text>; over MCP, metaform_save_prompt with name '
                                        'and text'),
                       'UNRESOLVED_POLICY': settings.value('lexicalize_unresolved', ctx.folder),
                       'ADDRESS_PLACEMENT': settings.value('lexicalize_addresses', ctx.folder)}}


def preprocess(ctx: Context) -> dict[str, Any]:
    return preprocessing.assemble(ctx.require_store(), ctx.nouns['text'], ctx.nouns['addresses'],
                                  scope=settings.value('preprocess_knowledge', ctx.folder))


@contextmanager
def _correctable(next_step: str) -> Generator[None, None, None]:
    """An address, subroutine, argument or RETURN the caller gave that does not bind is the caller's to correct: a
    user error with its next step, CLI-009, not an unexpected failure the host is told to report. The exception's
    type stays in the message, since it says which part did not bind."""
    try:
        yield
    except (KeyError, TypeError, ValueError, SyntaxError) as error:
        raise Stop(f'{type(error).__name__}: {error}', next_step) from error


def _path(ctx: Context, given: str) -> Path:
    path = Path(given)
    return path if path.is_absolute() else ctx.folder / path


def workflows(ctx: Context) -> Any:
    return catalog.workflows(ctx.require_store())


def _checked(ctx: Context, result: dict[str, Any], address: str, logic: list[dict[str, Any]]) -> dict[str, Any]:
    """The workflow as stored, with the structural check of each of its subroutines, BASE-057: a flagged one keeps
    its words, carries its notices and raises the incomplete-prompt signal."""
    found = [notice for one in logic for notice in axiom.notices(one['name'], one['content'])]
    if not found:
        return result
    ctx.publish('signal.raised', {'signal': axiom.SIGNAL, 'module': 'workflow', 'address': address, 'notices': found})
    return {**result, 'notices': found}


def submit(ctx: Context) -> Any:
    n = ctx.nouns
    doc = catalog.submit_workflow(ctx.require_store(), n['address'], n['layer'], n.get('name'),
                                  n.get('name_length', 2), n.get('selected', ()), n.get('provenance'))
    return _checked(ctx, doc, n['address'], doc['logic'])


def add_logic(ctx: Context) -> Any:
    n = ctx.nouns
    with _correctable(f'metaform map where {n["address"]}'):
        result = catalog.submit_logic(ctx.require_store(), n['address'], n['layer'], n['name'], n['content'],
                                      n.get('provenance'))
    return _checked(ctx, {'address': n['address'], 'layer': n['layer'], 'name': result.name,
                          'content': result.content}, n['address'], [result.to_dict()])


def history(ctx: Context) -> Any:
    n = ctx.nouns
    with _correctable('metaform workflow list'):
        return catalog.history(ctx.require_store(), n['address'], n['name'], n['layer'])


def export(ctx: Context) -> Any:
    n = ctx.nouns
    with _correctable('metaform workflow list'):
        doc = catalog.document(ctx.require_store(), n['address'], n['layer'])
    if not n.get('file'):
        return doc
    path = _path(ctx, n['file'])
    try:
        text = json.dumps(doc, ensure_ascii=False, indent=2) + '\n'
        if home.is_home_path(path):
            home.mkdir_private(path.parent)
            home.write_private(path, text)
        else:
            path.write_text(text, encoding='utf-8')
    except OSError as error:
        raise Stop(f'Cannot write {path}: {error.strerror or error}.',
                   f'metaform workflow export {n["address"]} {n["layer"]} file=<a writable path>') from error
    return {'file': str(path)}


def import_(ctx: Context) -> Any:
    path = _path(ctx, ctx.nouns['file'])
    try:
        given = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise Stop(f'Cannot read {path} as a portable workflow: {getattr(error, "strerror", None) or error}.',
                   'metaform help workflow import') from error
    with _correctable('metaform help workflow import'):
        doc = catalog.ingest_document(ctx.require_store(), given, ctx.nouns.get('layer'))
    return _checked(ctx, doc, doc['workflow']['address'], doc['logic'])


def _values(data: Mapping[str, Any]) -> dict[str, Any]:
    """JSON objects use the same field reads as element values in Axiom."""
    view = Value(data)
    return {key: view[key] for key in data}


def _lookup(store: Store) -> Lookup:
    def lookup(address: str, name: str) -> tuple[Logic, Any]:
        if address == 'logic.skill':
            one = skill_registry.get(name)
            return (Logic('skill', f'{one.address}@{one.version}', one.name, skill_registry.procedure(one.name)),
                    ElementValue(one.metadata()))
        return catalog.lookup(store, address, name)
    return lookup


def _call_store(store: Store, text: str) -> Store:
    address, _ = destination(text)
    accompanying = catalog.selected_layers(store, address)
    if not store.toggled or not accompanying:
        return store
    active = store.bound_base()
    return Store(store.project_id, module='workflow',
                 base=None if active is None else active.id,
                 toggled=list(dict.fromkeys((*store.toggled, *accompanying))))


def _token(ctx: Context) -> tuple[Store, str]:
    """The project's store, which holds the workflow run records, and the run id the call names."""
    word = ctx.nouns.get('run')
    if not word:
        raise Stop('This command needs the run id it works on, as run, handoff, parallel or assign returned it.',
                   'metaform workflow resume run=<run id>')
    return ctx.require_store(), str(word)


def _store(runs_store: Store, word: str) -> Store:
    source = executor.view(runs_store, word)['context']
    return Store(source['project'], module='workflow', base=source['metaform'], toggled=source['layers'])


def _shown(runs_store: Store, word: str) -> dict[str, Any]:
    _prompts()
    result = executor.view(runs_store, word)
    if result['logic']['type'] == 'skill':
        result['libs'] = skill_registry.libraries(skill_registry.get(result['address']))
    result['instructions'] = prompt_files.required(PACKAGE, 'execution', run=word)
    return result


def _handed(runs_store: Store, word: str) -> dict[str, Any]:
    return {'run': word, 'handoff': prompt_files.required(PACKAGE, 'handoff', run=word,
                                                          project=runs_store.project_id)}


def run(ctx: Context) -> Any:
    with _correctable('metaform workflow list'):
        store = _call_store(ctx.require_store(), ctx.nouns['call'])
        element = ctx.nouns.get('element')
        this = None if element is None else element_value(store, element)
        variables = _values(ctx.nouns.get('variables', {}))
        active = store.bound_base()
        word = executor.start(store, ctx.nouns['call'], variables, this, _lookup(store), {
            'project': store.project_id, 'folder': str(ctx.folder),
            'metaform': None if active is None else active.id, 'layers': store.toggled},
            resolve=lambda address: element_value(store, address))
    return _shown(store, word)


def resume(ctx: Context) -> Any:
    held, word = _token(ctx)
    if executor.held(held, word).kind == 'assign':
        return _assignment(held, word)
    return _shown(held, word)


def _variables(ctx: Context, held: Store, word: str) -> dict[str, Any]:
    stored = executor.view(held, word)['variables']
    # Only values explicitly supplied by the interpreter replace its saved scope.
    return {**stored, **_values(ctx.nouns.get('variables', {}))}


def _call_context(held: Store, store: Store, word: str) -> dict[str, Any]:
    source = executor.view(held, word)['context']
    active = store.bound_base()
    return {**source, 'metaform': None if active is None else active.id, 'layers': store.toggled}


def call(ctx: Context) -> Any:
    held, word = _token(ctx)
    with _correctable('metaform workflow list'):
        store = _call_store(_store(held, word), ctx.nouns['call'])
        child = executor.call(held, word, ctx.nouns['call'], _variables(ctx, held, word), _lookup(store),
                              resolve=lambda address: element_value(store, address),
                              context=_call_context(held, store, word))
    return _shown(held, child)


def handoff(ctx: Context) -> Any:
    held, word = _token(ctx)
    with _correctable('metaform workflow list'):
        store = _call_store(_store(held, word), ctx.nouns['call'])
        child = executor.call(held, word, ctx.nouns['call'], _variables(ctx, held, word), _lookup(store), fresh=True,
                              resolve=lambda address: element_value(store, address),
                              context=_call_context(held, store, word))
    return _handed(held, child)


def parallel(ctx: Context) -> Any:
    held, word = _token(ctx)
    with _correctable('metaform workflow list'):
        store = _store(held, word)
        for text in ctx.nouns['calls']:
            store = _call_store(store, text)
        words = executor.parallel(held, word, ctx.nouns['calls'], _variables(ctx, held, word), _lookup(store),
                                  resolve=lambda address: element_value(store, address),
                                  context=_call_context(held, store, word))
    return {'handoffs': [_handed(held, child) for child in words]}


def complete(ctx: Context) -> Any:
    held, word = _token(ctx)
    if executor.held(held, word).kind == 'assign':
        executor.working(held, word)
        runs.close(held, word)
        return {'run': word, 'closed': True}
    expression = _words(ctx.nouns.get('return'))
    if not expression:
        raise Stop("complete needs the call's RETURN.", f'metaform workflow complete "RETURN {{value}}" run={word}')
    with _correctable(f'metaform workflow resume run={word}'):  # its targets and scope, to correct the RETURN
        return executor.complete(held, word, expression, _variables(ctx, held, word))


def fail(ctx: Context) -> Any:
    held, word = _token(ctx)
    if executor.held(held, word).kind == 'assign':  # an assignment has no caller: its error is kept on its run
        executor.working(held, word)
        error = {'name': ctx.nouns['name'], 'message': ctx.nouns.get('message', '')}
        runs.close(held, word, result={'error': error}, failed=True)
        return {'run': word, 'error': error}
    return executor.fail(held, word, ctx.nouns['name'], ctx.nouns.get('message', ''))


AGENT = ('METAFORM_ROLE', 'METAFORM_SESSION', 'METAFORM_WORK')  # set by a runner on the agent it starts, BASE-052


def _identity(key: str) -> str | None:
    given = os.environ.get(key)
    return given if given and given != 'none' else None


def _noted(store: Store, work: str, line: str) -> None:
    """Add a line to a ticket's note, after what it says, where the person reads it, MAP-050."""
    with store.atomic():
        note = store.ticket(work, raw=True).work.note
        store.edit_work(work, {'note': f'{note}\n\n{line}' if note else line})


def pause(ctx: Context) -> Any:
    """Pause a run on the person, MAP-050 as amended 2026-10-08: what stopped it is kept on the run and, for an agent
    working a ticket, added to the ticket's note first, where the person reads it, so a run is never paused with
    nothing on its ticket; the agent then ends its turn, and nothing starts again by itself, VIEW-042. The ticket and
    session are kept on the run, so the answer names who goes on."""
    held, word = _token(ctx)
    found = _words(ctx.nouns.get('found'))
    executor.working(held, word)
    work, session = _identity('METAFORM_WORK'), _identity('METAFORM_SESSION')
    if work:
        try:
            _noted(held, work, prompt_files.required(PACKAGE, 'paused_note', run=word, found=found))
        except StoreError as error:
            raise Stop(f'Run {word} is not paused: what stopped it could not be added to ticket {work}: {error} '
                       'Write it in your ticket\'s note yourself and end your turn.',
                       f'metaform map work op=edit id={work} note="<what and where>"') from None
    result = executor.pause(held, word, found, ticket=work, session=session)
    return {**result, **({'ticket': work} if work else {}),
            'next': prompt_files.required(PACKAGE, 'paused', run=word)}


def answer(ctx: Context) -> Any:
    """The person's answer to a run paused on them. No agent answers, however it was started, as no agent answers a
    permission, BASE-052: refused whenever a runner's identity is set. A guard against an agent's mistakes, not a
    boundary, since an agent can change its own environment. The answer is added to the note of the ticket whose
    agent paused the run, after the run takes it, since the two are kept in different stores; nothing restarts by
    itself, VIEW-042, so the next step is the person's message to that agent."""
    held, word = _token(ctx)
    if any(_identity(key) for key in AGENT):
        raise Stop(f'Only the person answers a run paused on them. If they gave you their answer in a message, tell '
                   f'them to run metaform workflow answer run={word} <answer>, then end your turn.',
                   f'metaform workflow resume run={word}')
    given = _words(ctx.nouns.get('answer'))
    answered = executor.answer(held, word, given)
    result: dict[str, Any] = {'run': word, 'state': answered.state}
    if answered.ticket:
        when = time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())
        try:
            _noted(held, answered.ticket, prompt_files.required(PACKAGE, 'answered_note', time=when, answer=given))
            result['ticket'] = answered.ticket
        except StoreError as error:
            result['ticket'] = f'not noted on {answered.ticket}: {error}'
        session = f' session={answered.session}' if answered.session else ''
        result['next'] = prompt_files.required(PACKAGE, 'answered', run=word, ticket=answered.ticket,
                                               session=session)
    else:
        result['next'] = prompt_files.required(PACKAGE, 'answered_alone', run=word)
    return result


def cancel(ctx: Context) -> Any:
    """Cancel a run and the runs below it. An agent whose role the person holds back cancels none, as it stops no
    agent, BASE-052 and MAP-050: a running run it cannot finish it fails, so its caller's Catch decides; one waiting
    or paused it leaves to the person, with what stopped it in its ticket's note."""
    role = held_role(ctx)
    held, word = _token(ctx)
    if role is not None:
        refused = f'A {role} agent cancels no workflow run: that is for the person and the agents that serve them.'
        if executor.held(held, word).state == 'running':
            raise Stop(f'{refused} Fail your own run with what stopped it.', f'metaform workflow fail <name> run={word}')
        work = _identity('METAFORM_WORK') or '<your ticket>'
        raise Stop(f'{refused} End your turn; write what stopped you in your ticket\'s note. The person cancels it '
                   f'with metaform workflow cancel run={word}.',
                   f'metaform map work op=edit id={work} note="<what and where>"')
    return executor.cancel(held, word, str(ctx.nouns.get('reason') or ''))


def runs_(ctx: Context) -> Any:
    """A page of the project's open runs, oldest first, or of those in one state, the newest first for an ended
    state, with the command for the next page."""
    state = ctx.nouns.get('state')
    limit = int(ctx.nouns.get('limit', runs.LIMIT))
    listed, cursor = runs.listed(ctx.require_store(), state, limit=limit, after=ctx.nouns.get('after'))
    more = ' '.join(['metaform workflow runs', *([f'state={state}'] if state else []),
                     *([f'limit={limit}'] if limit != runs.LIMIT else []), f'after={cursor}'])
    return {'runs': listed, **({'more': more} if cursor else {})}


def _words(given: Any) -> str:
    """A noun of several words: the words on the command line, or one text over MCP."""
    return ' '.join(map(str, cast(list[Any], given))) if isinstance(given, list) else str(given or '')


def _known(name: str, held: tuple[str, ...], kind: str) -> str:
    if name not in held:
        raise Stop(f'workflow has no {kind} {name}.', f'metaform workflow {kind}s')
    return name


def _about(skill_name: str) -> str:
    return skill_registry.get(skill_name).description


def lib(ctx: Context) -> str:
    return skill_registry.library(_known(ctx.nouns['name'], LIBS, 'lib'))


def libs(ctx: Context) -> list[dict[str, str]]:
    return [{'name': name, 'marker': skill_registry.library(name).splitlines()[0]} for name in LIBS]


def skill(ctx: Context) -> str:
    return skill_registry.procedure(ctx.nouns['name'])


def skills(ctx: Context) -> list[dict[str, Any]]:
    return [{'name': one.name.replace('-', '_'), 'about': _about(one.name), 'requires': list(one.requires)}
            for one in skill_registry.catalog() if one.discover]


def scan(ctx: Context) -> str:
    bound = prompt_files.required(PACKAGE, 'scan_input', workflow=ctx.nouns['workflow'],
                                  task=ctx.nouns.get('task') or 'other')
    return skill_registry.procedure('scan') + '\n\n' + bound


def _assignment(held: Store, word: str) -> str:
    """A skill handed by run id: its libs, the skill, the input and the line that closes it, MCP-034."""
    value = executor.held(held, word).value['assignment']
    served = '\n\n'.join(skill_registry.libraries(skill_registry.get(value['skill'])).values())
    given, answered = value.get('input'), value.get('answer')
    bound = [prompt_files.required(PACKAGE, 'assignment_input', input=given) if given else '',
             prompt_files.required(PACKAGE, 'assignment_answer', found=answered['question'],
                                   answer=answered['answer']) if answered else '']
    return prompt_files.required(
        PACKAGE, 'assignment', libs=served, skill=skill_registry.procedure(value['skill']),
        input='\n\n'.join(one for one in bound if one), run=word, project=held.project_id)


def served(name: str, given: str | None = None) -> str:
    """A skill whole, for an agent already connected over ACP: its libs, the skill and the input bound as data, with
    no run record. Dispatch sends it as a purpose agent's first turn; nothing is resumed."""
    skill_name = skill_registry.get(name).name
    libs = '\n\n'.join(skill_registry.libraries(skill_registry.get(skill_name)).values())
    return prompt_files.required(
        PACKAGE, 'served', libs=libs, skill=skill_registry.procedure(skill_name),
        input=prompt_files.required(PACKAGE, 'assignment_input', input=given) if given else '')


def serve(ctx: Context) -> str:
    return served(str(ctx.nouns['name']), _words(ctx.nouns.get('input')) if ctx.nouns.get('input') else None)


def assign(ctx: Context) -> Any:
    """A run record of kind assign holding the skill and its input, for a fresh agent to read by its run id with
    resume and close with complete, BASE-051."""
    store = ctx.require_store()
    name = skill_registry.get(_words(ctx.nouns.get('skill'))).name.replace('-', '_')
    word = runs.start(store, 'assign', {'assignment': {'skill': name, 'input': ctx.nouns.get('input')}})
    return {'run': word, 'read': f'metaform workflow resume run={word} --project {store.project_id}'}


ADDRESS = Noun('address', 'The element address; workflow elements and project elements use the same logic.')
LAYER = Noun('layer', 'The ordinary knowledge layer to write into, created when absent.')
PROVENANCE = Noun('provenance', 'The producing prompt, model and role.', kind='json', required=False,
                  schema={'type': 'object', 'additionalProperties': False,
                          'properties': {'prompt': {'type': 'string', 'description': 'The prompt the work was done from.'},
                                         'model': {'type': 'string', 'description': 'The model that did the work.'},
                                         'role': {'type': 'string', 'description': 'The role of the agent.'}}})
# Named, run=<run id>, so it may follow a RETURN of several words; a call without it is stopped with its form.
TOKEN = Noun('run', 'The run id of the call or assignment, as run, handoff, parallel or assign returned it.',
             required=False)
VARIABLES = Noun('variables', 'The interpreter\'s current variable values, an object of variable name to value.',
                 kind='json', required=False,
                 schema={'type': 'object', 'additionalProperties': True,
                         'description': 'Each key is a variable name; its value is that variable\'s current JSON value.'})
# A noun of several words is positional, so the grammar collects its words as a list; over MCP it takes one text as
# well, read by _words.
TEXT = {'type': 'string'}
CALL = Noun('call','An Axiom call by address and name, with keyword arguments and optional return targets.')

MODULE = Module(
    id='workflow', summary='Write, import and run reusable Axiom subroutines.',
    purpose='Stores reusable Axiom logic in ordinary knowledge layers and transports calls, parameters and '
            'returns for the agent interpreter, keeping each run\'s state in a run record reached by its run id. '
            'Details: metaform help workflow.',
    details='The agent interprets Choice, Parallel, Map, Retry, Catch and verification from the stored Axiom. '
            'run gives its entry call and its run id; call composes on the same agent; handoff gives a fresh agent a run '
            'id of its own. resume reads a run by its id on CLI or MCP; complete returns to its caller and fail '
            'delivers a named error. pause holds a run on the person with what stopped it until they answer with '
            'answer, on the command line; cancel ends a run and the runs below it; runs lists the open runs. A run is '
            'running, waiting on its handoffs, input_required, completed, failed or cancelled, the status vocabulary '
            'of metaform.data.status, each mapped to an MCP Tasks and an A2A task state. '
            'Workflow logic can sit on any element, including an element held by a purpose. '
            'Selected and masked knowledge layers '
            'decide what callable logic is available. The skills write_workflow and import_workflow write and import '
            'workflows; lexicalize serves the prompt-lexicalization script with its inputs. lib, libs, skill, skills '
            'and scan serve the libs and skills; assign hands a skill to a fresh agent by run id, and complete closes '
            'it.',
    tables=catalog.TABLES, node_read=catalog.node_read,
    verbs=(
        Verb('lexicalize', lexicalize, 'Read the prompt-lexicalization script with a prompt as input, to tie its names '
                                       'to map addresses.',
             nouns=(Noun('text', 'The imported prompt or workflow, verbatim.'),), effect='read'),
        Verb('preprocess', preprocess, 'Prepare a lexicalized prompt by placing the knowledge visible at its addresses '
                                       'before its address footer.',
             nouns=(Noun('text', 'The lexicalized prompt body, verbatim, without its address footer.'),
                    Noun('addresses', 'The namespace addresses named by the prompt, as a JSON list.', 'json',
                         schema={'type': 'array', 'items': {'type': 'string'}})), effect='read'),
        Verb('list', workflows, 'List the visible workflow elements and the names of their Axiom subroutines.', effect='read'),
        Verb('submit', submit, 'Record a workflow element, which holds Axiom subroutines, in an ordinary knowledge '
                               'layer.',
             nouns=(ADDRESS, LAYER, Noun('name', 'The canonical workflow name.', required=False),
                    Noun('name_length', 'Trailing address segments that name its short type.', 'int', required=False),
                    Noun('selected', 'Knowledge layers selected to go with this workflow, by name or id.', 'json',
                         required=False, schema={'type': 'array', 'items': {'type': 'string'}}),
                    PROVENANCE)),
        Verb('add_logic', add_logic, 'Record a named Axiom subroutine on a workflow element or any other project '
                                     'element.',
             nouns=(ADDRESS, LAYER, Noun('name', 'The subroutine name.'), Noun('content', 'Verbatim Axiom.'), PROVENANCE)),
        Verb('history', history, 'Read every saved version of one named Axiom subroutine on an element.',
             nouns=(ADDRESS, Noun('name', 'The subroutine name.'), LAYER), effect='read'),
        Verb('export', export, 'Export a workflow from its stored layer as a portable document, printed or written to '
                               'a file.',
             nouns=(ADDRESS, LAYER, Noun('file', 'The destination <workflow name>.metaform file.', required=False))),
        Verb('import', import_, 'Import a portable workflow document into an ordinary knowledge layer.',
             nouns=(Noun('file', 'The exported .metaform file.'),
                    Noun('layer', 'Destination layer; absent keeps the carried name.', required=False))),
        Verb('run', run, 'Start a workflow run: an entry call to an Axiom subroutine, whose run id the interpreter '
                         'follows.',
             nouns=(CALL, Noun('element', 'The element supplying this for the entry call.', required=False), VARIABLES)),
        Verb('resume', resume, 'Read a workflow run by its id: its current subroutine and values, or its assignment.',
             nouns=(TOKEN,)),
        Verb('call', call, "Call an Axiom subroutine on the same agent, keeping the caller's scope.",
             nouns=(CALL, TOKEN, VARIABLES)),
        Verb('handoff', handoff, 'Start a callee run for a fresh agent; its run id reaches that agent directly or '
                                 'through the orchestrator.',
             nouns=(CALL, TOKEN, VARIABLES)),
        Verb('parallel', parallel, 'Run independent subroutine calls as branches; the run resumes when every branch '
                                   'returns.',
             nouns=(Noun('calls', 'The independent Axiom calls, each written as call is.', 'json',
                         schema={'type': 'array', 'items': {'type': 'string'}, 'minItems': 1}), TOKEN, VARIABLES)),
        Verb('complete', complete, 'Finish a run: deliver its RETURN to the caller, or close an assignment. The '
                                   'interpreter supplies its final variables.',
             nouns=(TOKEN, VARIABLES, Noun('return', 'RETURN of a value or tuple; an assignment needs none.',
                                           required=False, many=True, schema=TEXT))),
        Verb('fail', fail, "Fail a run: deliver an error to its caller, for the caller's authored Retry or Catch.",
             nouns=(Noun('name', 'The authored error name.'), TOKEN,
                    Noun('message', 'The error detail.', required=False))),
        Verb('pause', pause, 'Pause a run on the person when something its logic does not decide stops it, '
                             'saying what you found.',
             nouns=(TOKEN, Noun('found', 'What stopped the run that neither its ticket nor its logic decides, in plain '
                                         'words: what you found and what you need from the person. A choice you can '
                                         'undo is yours to make and record; it is not a pause.',
                                many=True, schema=TEXT))),
        Verb('answer', answer, "The person's answer to a run paused on them, read by its agent when it resumes the "
                               "run.",
             nouns=(TOKEN, Noun('answer', "The person's answer.", many=True, schema=TEXT)), surfaces=('cli',)),
        Verb('cancel', cancel, 'Cancel a run and every run below it; its caller receives the error cancelled.',
             nouns=(TOKEN, Noun('reason', 'Why it is cancelled.', required=False))),
        Verb('runs', runs_, 'List the open workflow runs, or those in one state, with what stopped a paused one.',
             nouns=(Noun('state', 'running, waiting, input_required, completed, failed or cancelled.',
                         required=False),
                    Noun('limit', f'How many runs, {runs.LIMIT} by default, 0 for all.', kind='int', required=False),
                    Noun('after', 'The cursor the previous page returned.', required=False)), effect='read'),
        Verb('lib', lib, 'Read one Axiom lib: its shared sections at their newest stored versions.',
             nouns=(Noun('name', 'lib_axiom, lib_metaform, lib_workflow or lib_quality.'),), effect='read'),
        Verb('libs', libs, 'List the Axiom libs, each with its first line, its marker.', effect='read'),
        Verb('skill', skill, "Read one workflow skill's Axiom, to follow it.", nouns=(Noun('name', 'The skill name.'),), effect='read'),
        Verb('skills', skills, 'List discoverable workflow skills with their descriptions and required libs.',
             effect='read'),
        Verb('serve', serve, 'Read one skill whole, its libs first and an input bound as data, as dispatch sends it to '
                             'an agent it started.',
             nouns=(Noun('name', 'The skill name.'), Noun('input', 'The input, bound as data.', required=False)),
             surfaces=('cli',)),
        Verb('scan', scan, 'Read the scan skill, which decides the libs a task needs, with a workflow and its task '
                           'bound as data.',
             nouns=(Noun('workflow', 'The workflow text or address.'),
                    Noun('task', 'write, import, workflow_efficiency or prompt_efficiency.', required=False)), effect='read'),
        Verb('assign', assign, 'Hand a workflow skill to a fresh agent: it gets a run id and reads its assignment with '
                               'resume.',
             nouns=(Noun('input', "The skill's input.", required=False),
                    Noun('skill', 'The skill name.', many=True, schema=TEXT))),
    ),
)
