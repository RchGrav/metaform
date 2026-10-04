"""Workflow authoring, ingest and call transport for the Axiom agent interpreter."""
from __future__ import annotations

import json
from collections.abc import Mapping
from importlib import resources
from pathlib import Path
from typing import Any

from metaform import nonce, prompt_files, settings
from metaform.data import Store, prompts
from metaform.module import Context, Module, Noun, Verb

from . import catalog, executor
from .binding import Lookup, destination
from .element import Value, element_value

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = True
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


def _prompts() -> None:
    versions: dict[str, int] = {}
    for name in ('axiom-language', 'metaform-system', 'namespace-rules', 'workflow-logic',
                 'metaform-tools', 'delexicalization-rules'):
        versions[name] = prompts.shipped(name, 'text', prompt_files.required(PACKAGE, name)).number
    for name in ('workflow-authoring', 'workflow-ingest'):
        text = prompt_files.required(PACKAGE, name)
        for section, version in versions.items():
            text = text.replace(f'{section} 1', f'{section} {version}')
        prompts.shipped(name, 'text', text)
    prompts.shipped('prompt-lexicalization', 'text', prompt_files.required(PACKAGE, 'prompt-lexicalization'))


def author(ctx: Context) -> dict[str, Any]:
    _prompts()
    return {'prompt': prompts.prompt_version('workflow-authoring').text,
            'inputs': {'Goal': ctx.nouns['goal'], 'Target_Layer': ctx.nouns['layer'],
                       'Run_Args': ctx.nouns.get('arguments')}}


def ingest(ctx: Context) -> dict[str, Any]:
    _prompts()
    return {'prompt': prompts.prompt_version('workflow-ingest').text,
            'inputs': {'Workflow_Text': ctx.nouns['text'], 'Target_Layer': ctx.nouns['layer']}}


def lexicalize(ctx: Context) -> dict[str, Any]:
    _prompts()
    # PROMPT_STORE stays unfilled: no command saves a prompt yet, and the script halts and names it.
    return {'prompt': prompts.prompt_version('prompt-lexicalization').text,
            'inputs': {'Prompt_Text': ctx.nouns['text'],
                       'MAP_READ': 'metaform map where <address>; over MCP, map with command where',
                       'PROMPT_STORE': None,
                       'UNRESOLVED_POLICY': settings.value('lexicalize_unresolved', ctx.folder),
                       'ADDRESS_PLACEMENT': settings.value('lexicalize_addresses', ctx.folder)}}


def workflows(ctx: Context) -> Any:
    return catalog.workflows(ctx.require_store())


def submit(ctx: Context) -> Any:
    n = ctx.nouns
    return catalog.submit_workflow(ctx.require_store(), n['address'], n['layer'], n.get('name'),
                                   n.get('name_length', 2), n.get('selected', ()), n.get('provenance'))


def logic(ctx: Context) -> Any:
    n = ctx.nouns
    result = catalog.submit_logic(ctx.require_store(), n['address'], n['layer'], n['name'], n['content'],
                                  n.get('provenance'))
    return {'address': n['address'], 'layer': n['layer'], 'name': result.name, 'content': result.content}


def history(ctx: Context) -> Any:
    n = ctx.nouns
    return catalog.history(ctx.require_store(), n['address'], n['name'], n['layer'])


def export(ctx: Context) -> Any:
    n = ctx.nouns
    doc = catalog.document(ctx.require_store(), n['address'], n['layer'])
    if not n.get('file'):
        return doc
    path = Path(n['file'])
    if not path.is_absolute():
        path = ctx.folder / path
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'file': str(path)}


def import_(ctx: Context) -> Any:
    path = Path(ctx.nouns['file'])
    if not path.is_absolute():
        path = ctx.folder / path
    return catalog.ingest_document(ctx.require_store(), json.loads(path.read_text(encoding='utf-8')),
                                   ctx.nouns.get('layer'))


def _values(data: Mapping[str, Any]) -> dict[str, Any]:
    """JSON objects use the same field reads as element values in Axiom."""
    view = Value(data)
    return {key: view[key] for key in data}


def _lookup(store: Store) -> Lookup:
    return lambda address, name: catalog.lookup(store, address, name)


def _call_store(store: Store, text: str) -> Store:
    address, _ = destination(text)
    accompanying = catalog.selected_layers(store, address)
    if not store.toggled or not accompanying:
        return store
    active = store.bound_metaform()
    return Store(store.project_id, module='workflow',
                 metaform=None if active is None else active.metaform_id,
                 toggled=list(dict.fromkeys((*store.toggled, *accompanying))))


def _token(ctx: Context) -> str:
    word = ctx.nouns.get('nonce')
    return str(word) if word else nonce.current().nonce


def _store(ctx: Context, word: str) -> Store:
    source = executor.view(word)['context']
    return Store(source['project'], module='workflow', metaform=source['metaform'], toggled=source['layers'])


def _shown(word: str) -> dict[str, Any]:
    _prompts()
    result = executor.view(word)
    result['instructions'] = prompt_files.required(PACKAGE, 'execution', nonce=word)
    return result


def run(ctx: Context) -> Any:
    store = _call_store(ctx.require_store(), ctx.nouns['call'])
    element = ctx.nouns.get('element')
    this = None if element is None else element_value(store, element)
    variables = _values(ctx.nouns.get('variables', {}))
    active = store.bound_metaform()
    word = executor.start(ctx.nouns['call'], variables, this, _lookup(store), {
        'project': store.project_id, 'folder': str(ctx.folder),
        'metaform': None if active is None else active.metaform_id, 'layers': store.toggled},
        resolve=lambda address: element_value(store, address))
    return _shown(word)


def resume(ctx: Context) -> Any:
    return _shown(_token(ctx))


def _variables(ctx: Context, word: str) -> dict[str, Any]:
    stored = executor.view(word)['variables']
    # Only values explicitly supplied by the interpreter replace its saved scope.
    return {**stored, **_values(ctx.nouns.get('variables', {}))}


def _call_context(store: Store, word: str) -> dict[str, Any]:
    source = executor.view(word)['context']
    active = store.bound_metaform()
    return {**source, 'metaform': None if active is None else active.metaform_id, 'layers': store.toggled}


def call(ctx: Context) -> Any:
    word = _token(ctx)
    store = _call_store(_store(ctx, word), ctx.nouns['call'])
    child = executor.call(word, ctx.nouns['call'], _variables(ctx, word), _lookup(store),
                          resolve=lambda address: element_value(store, address), context=_call_context(store, word))
    return _shown(child)


def handoff(ctx: Context) -> Any:
    word = _token(ctx)
    store = _call_store(_store(ctx, word), ctx.nouns['call'])
    child = executor.call(word, ctx.nouns['call'], _variables(ctx, word), _lookup(store), fresh=True,
                          resolve=lambda address: element_value(store, address), context=_call_context(store, word))
    return {'nonce': child, 'handoff': prompt_files.required(PACKAGE, 'handoff', nonce=child)}


def parallel(ctx: Context) -> Any:
    word = _token(ctx)
    store = _store(ctx, word)
    for text in ctx.nouns['calls']:
        store = _call_store(store, text)
    words = executor.parallel(word, ctx.nouns['calls'], _variables(ctx, word), _lookup(store),
                              resolve=lambda address: element_value(store, address), context=_call_context(store, word))
    return {'handoffs': [{'nonce': child, 'handoff': prompt_files.required(PACKAGE, 'handoff', nonce=child)}
                         for child in words]}


def complete(ctx: Context) -> Any:
    word = _token(ctx)
    return executor.complete(word, ctx.nouns['return'], _variables(ctx, word))


def fail(ctx: Context) -> Any:
    return executor.fail(_token(ctx), ctx.nouns['name'], ctx.nouns.get('message', ''))


ADDRESS = Noun('address', 'The element address; workflow elements and project elements use the same logic.')
LAYER = Noun('layer', 'The ordinary knowledge layer to write into, created when absent.')
PROVENANCE = Noun('provenance', 'The producing prompt, model and role.', kind='json', required=False)
TOKEN = Noun('nonce', 'The call nonce; omit when running through that nonce.', required=False)
VARIABLES = Noun('variables', 'The interpreter\'s current variable values.', kind='json', required=False)
CALL = Noun('call', 'An Axiom call by address and name, with keyword arguments and optional return targets.')

MODULE = Module(
    id='workflow', summary='Author, ingest and run reusable Axiom subroutines.',
    purpose='Stores reusable Axiom logic in ordinary knowledge layers and transports calls, parameters and '
            'returns for the agent interpreter. Fresh-agent calls use nonce handoffs. Details: metaform help workflow.',
    details='The agent interprets Choice, Parallel, Map, Retry, Catch and verification from the stored Axiom. '
            'run gives its entry call; call composes on the same agent; handoff gives a nonce to a fresh agent. '
            'resume redeems it on CLI or MCP; complete returns to its caller and fail delivers a named error. '
            'Workflow logic can sit on any element, including a subtype. Selected and masked knowledge layers '
            'decide what callable logic is available. author, ingest and lexicalize serve the authored prompts and inputs.',
    tables=catalog.TABLES, node_read=catalog.node_read,
    verbs=(
        Verb('author', author, 'Read the workflow-authoring prompt with its inputs.',
             nouns=(Noun('goal', 'What the workflow must accomplish.'), LAYER,
                    Noun('arguments', 'Arguments for a run; absent means submit only.', kind='json', required=False))),
        Verb('ingest', ingest, 'Read the workflow-ingest prompt with an existing prompt as input.',
             nouns=(Noun('text', 'The existing prompt or workflow, verbatim.'), LAYER)),
        Verb('lexicalize', lexicalize, 'Read the prompt-lexicalization script with a prompt as input.',
             nouns=(Noun('text', 'The imported prompt or workflow, verbatim.'),)),
        Verb('list', workflows, 'List visible workflow elements and their subroutine names.'),
        Verb('submit', submit, 'Record a workflow element in an ordinary knowledge layer.',
             nouns=(ADDRESS, LAYER, Noun('name', 'The canonical workflow name.', required=False),
                    Noun('name_length', 'Trailing address segments that name its short type.', 'int', required=False),
                    Noun('selected', 'Knowledge layers selected to go with this workflow.', 'json', required=False),
                    PROVENANCE)),
        Verb('logic', logic, 'Record an Axiom subroutine on a workflow or project element.',
             nouns=(ADDRESS, LAYER, Noun('name', 'The subroutine name.'), Noun('content', 'Verbatim Axiom.'), PROVENANCE)),
        Verb('history', history, 'Read every saved version of a logic requirement.',
             nouns=(ADDRESS, Noun('name', 'The subroutine name.'), LAYER)),
        Verb('export', export, 'Read or write a portable workflow from its stored layer.',
             nouns=(ADDRESS, LAYER, Noun('file', 'The destination <workflow name>.metaform file.', required=False))),
        Verb('import', import_, 'Record a portable workflow in an ordinary knowledge layer.',
             nouns=(Noun('file', 'The exported .metaform file.'),
                    Noun('layer', 'Destination layer; absent keeps the carried name.', required=False))),
        Verb('run', run, 'Start an entry call for the Axiom interpreter.',
             nouns=(CALL, Noun('element', 'The element supplying this for the entry call.', required=False), VARIABLES)),
        Verb('resume', resume, 'Redeem a call nonce and read only its current subroutine and values.', nouns=(TOKEN,)),
        Verb('call', call, 'Call a subroutine on the same agent and keep the caller\'s scope.',
             nouns=(CALL, TOKEN, VARIABLES)),
        Verb('handoff', handoff, 'Issue a callee nonce to give directly or through the orchestrator to a fresh agent.',
             nouns=(CALL, TOKEN, VARIABLES)),
        Verb('parallel', parallel, 'Register independent calls and resume when every branch returns.',
             nouns=(Noun('calls', 'The independent Axiom calls.', 'json'), TOKEN, VARIABLES)),
        Verb('complete', complete, 'Deliver RETURN to the caller; the interpreter supplies its final variables.',
             nouns=(Noun('return', 'RETURN of a value or tuple.'), TOKEN, VARIABLES)),
        Verb('fail', fail, 'Deliver an error to the caller for its authored Retry or Catch.',
             nouns=(Noun('name', 'The authored error name.'), TOKEN,
                    Noun('message', 'The error detail.', required=False))),
    ),
)
