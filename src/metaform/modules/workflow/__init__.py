"""Workflow authoring, ingest and call transport for the Axiom agent interpreter."""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from importlib import resources
from itertools import takewhile
from pathlib import Path
from typing import Any, cast

from metaform import axiom, nonce, prompt_files, settings
from metaform.data import Store, prompts
from metaform.module import Context, Module, Noun, Stop, Verb

from . import catalog, executor
from . import preprocess as preprocessing
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
settings.choice('preprocess_knowledge', ['context', 'whole'], 'context',
                help='How much selected knowledge accompanies a preprocessed prompt.',
                details='context includes knowledge visible at the supplied addresses; whole includes all visible '
                        'items of the layers selected there. Both preserve selection and masks, and context reads '
                        'retain the map\'s always_show items. Default context keeps the job\'s prepared context small.')


SECTIONS = ('axiom-language', 'metaform-system', 'namespace-rules', 'workflow-logic', 'metaform-tools',
            'delexicalization-rules')
LIBS = ('lib_axiom', 'lib_metaform', 'lib_workflow', 'lib_quality')
SKILLS = ('scan', 'write_workflow', 'import_workflow', 'workflow_efficiency', 'prompt_efficiency',
          'workflow_builder', 'workflow_evaluator', 'sentinel')


def _prompts() -> None:
    for name in (*SECTIONS, 'prompt-lexicalization'):
        prompts.shipped(name, 'text', prompt_files.required(PACKAGE, name))


def lexicalize(ctx: Context) -> dict[str, Any]:
    _prompts()
    return {'prompt': prompts.prompt_version('prompt-lexicalization').text,
            'inputs': {'Prompt_Text': ctx.nouns['text'],
                       'MAP_READ': 'metaform map where <address>; over MCP, map with command where',
                       'PROMPT_STORE': 'metaform prompt save <name> <text>; over MCP, save_prompt with name and text',
                       'UNRESOLVED_POLICY': settings.value('lexicalize_unresolved', ctx.folder),
                       'ADDRESS_PLACEMENT': settings.value('lexicalize_addresses', ctx.folder)}}


def preprocess(ctx: Context) -> dict[str, Any]:
    return preprocessing.assemble(ctx.require_store(), ctx.nouns['text'], ctx.nouns['addresses'],
                                  scope=settings.value('preprocess_knowledge', ctx.folder))


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
    result = catalog.submit_logic(ctx.require_store(), n['address'], n['layer'], n['name'], n['content'],
                                  n.get('provenance'))
    return _checked(ctx, {'address': n['address'], 'layer': n['layer'], 'name': result.name,
                          'content': result.content}, n['address'], [result.to_dict()])


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
    doc = catalog.ingest_document(ctx.require_store(), json.loads(path.read_text(encoding='utf-8')),
                                  ctx.nouns.get('layer'))
    return _checked(ctx, doc, doc['workflow']['address'], doc['logic'])


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
    active = store.bound_base()
    return Store(store.project_id, module='workflow',
                 base=None if active is None else active.id,
                 toggled=list(dict.fromkeys((*store.toggled, *accompanying))))


def _token(ctx: Context) -> str:
    word = ctx.nouns.get('nonce')
    return str(word) if word else nonce.current().nonce


def _store(ctx: Context, word: str) -> Store:
    source = executor.view(word)['context']
    return Store(source['project'], module='workflow', base=source['metaform'], toggled=source['layers'])


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
    active = store.bound_base()
    word = executor.start(ctx.nouns['call'], variables, this, _lookup(store), {
        'project': store.project_id, 'folder': str(ctx.folder),
        'metaform': None if active is None else active.id, 'layers': store.toggled},
        resolve=lambda address: element_value(store, address))
    return _shown(word)


def resume(ctx: Context) -> Any:
    word = _token(ctx)
    if executor.held(word).function == 'assign':
        return _assignment(word)
    return _shown(word)


def _variables(ctx: Context, word: str) -> dict[str, Any]:
    stored = executor.view(word)['variables']
    # Only values explicitly supplied by the interpreter replace its saved scope.
    return {**stored, **_values(ctx.nouns.get('variables', {}))}


def _call_context(store: Store, word: str) -> dict[str, Any]:
    source = executor.view(word)['context']
    active = store.bound_base()
    return {**source, 'metaform': None if active is None else active.id, 'layers': store.toggled}


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
    if executor.held(word).function == 'assign':
        nonce.close(word)
        return {'nonce': word, 'closed': True}
    expression = _words(ctx.nouns.get('return'))
    if not expression:
        raise Stop("complete needs the call's RETURN.", f'metaform workflow complete "RETURN {{value}}" nonce={word}')
    return executor.complete(word, expression, _variables(ctx, word))


def fail(ctx: Context) -> Any:
    return executor.fail(_token(ctx), ctx.nouns['name'], ctx.nouns.get('message', ''))


def _words(given: Any) -> str:
    """A noun that may follow a nonce: the words after it on the command line, or one text over MCP."""
    return ' '.join(map(str, cast(list[Any], given))) if isinstance(given, list) else str(given or '')


def _fills() -> dict[str, str]:
    """Each shared section's newest stored version and its number, for the libs that carry them, MCP-034."""
    _prompts()
    fills: dict[str, str] = {}
    for section in SECTIONS:
        version = prompts.prompt_version(section)
        fills[section] = version.text
        fills[f'{section}-version'] = str(version.number)
    return fills


def _known(name: str, held: tuple[str, ...], kind: str) -> str:
    if name not in held:
        raise Stop(f'workflow has no {kind} {name}.', f'metaform workflow {kind}s')
    return name


def _requires(skill_name: str) -> list[str]:
    """The libs a skill names on its own `# requires:` line, in LIBS order, so the list is written once."""
    text = prompt_files.required(PACKAGE, skill_name)
    line = next((one for one in text.splitlines() if one.strip().startswith('# requires:')), '')
    named = set(re.findall(r'lib_\w+', line))
    return [name for name in LIBS if name in named]


def _about(skill_name: str) -> str:
    """What a skill does, from its own `# skill:` line and the indented lines that continue it, the text after the
    name and `·`, so the skill's own header is the one place it is written, MCP-032 and MCP-034."""
    lines = prompt_files.required(PACKAGE, skill_name).splitlines()
    start = next(index for index, one in enumerate(lines) if one.startswith('# skill:'))
    header = [lines[start], *takewhile(lambda one: one.startswith('#  '), lines[start + 1:])]
    return ' '.join(one.lstrip('#').strip() for one in header).split('·', 1)[1].strip()


def lib(ctx: Context) -> str:
    return prompt_files.required(PACKAGE, _known(ctx.nouns['name'], LIBS, 'lib'), **_fills())


def libs(ctx: Context) -> list[dict[str, str]]:
    fills = _fills()
    return [{'name': name, 'marker': prompt_files.required(PACKAGE, name, **fills).splitlines()[0]} for name in LIBS]


def skill(ctx: Context) -> str:
    return prompt_files.required(PACKAGE, _known(ctx.nouns['name'], SKILLS, 'skill'))


def skills(ctx: Context) -> list[dict[str, Any]]:
    return [{'name': name, 'about': _about(name), 'requires': _requires(name)} for name in SKILLS]


def scan(ctx: Context) -> str:
    bound = prompt_files.required(PACKAGE, 'scan_input', workflow=ctx.nouns['workflow'],
                                  task=ctx.nouns.get('task') or 'other')
    return prompt_files.required(PACKAGE, 'scan') + '\n\n' + bound


def _assignment(word: str) -> str:
    """A skill handed by nonce: its libs, the skill, the input and the line that closes it, MCP-034."""
    value = executor.held(word).value
    fills = _fills()
    served = '\n\n'.join(prompt_files.required(PACKAGE, name, **fills) for name in _requires(value['skill']))
    given = value.get('input')
    return prompt_files.required(
        PACKAGE, 'assignment', libs=served, skill=prompt_files.required(PACKAGE, value['skill']),
        input=prompt_files.required(PACKAGE, 'assignment_input', input=given) if given else '', nonce=word)


def served(name: str, given: str | None = None) -> str:
    """A skill whole, for an agent already connected over ACP: its libs, the skill and the input bound as data, with
    no nonce, Rich 2026-10-08. Dispatch sends it as a purpose agent's first turn; nothing is redeemed."""
    skill_name = _known(name, SKILLS, 'skill')
    fills = _fills()
    libs = '\n\n'.join(prompt_files.required(PACKAGE, lib_name, **fills) for lib_name in _requires(skill_name))
    return prompt_files.required(
        PACKAGE, 'served', libs=libs, skill=prompt_files.required(PACKAGE, skill_name),
        input=prompt_files.required(PACKAGE, 'assignment_input', input=given) if given else '')


def serve(ctx: Context) -> str:
    return served(str(ctx.nouns['name']), _words(ctx.nouns.get('input')) if ctx.nouns.get('input') else None)


def assign(ctx: Context) -> Any:
    """Run directly, a nonce whose function is this verb; reached through that nonce, the assignment, BASE-050."""
    held = nonce.reached()
    if held is not None:
        return _assignment(held.nonce)
    name = _known(_words(ctx.nouns.get('skill')), SKILLS, 'skill')
    word = nonce.request('workflow', 'assign', value={'skill': name, 'input': ctx.nouns.get('input')})
    return {'nonce': word, 'run': f'metaform {word}'}


ADDRESS = Noun('address', 'The element address; workflow elements and project elements use the same logic.')
LAYER = Noun('layer', 'The ordinary knowledge layer to write into, created when absent.')
PROVENANCE = Noun('provenance', 'The producing prompt, model and role.', kind='json', required=False,
                  schema={'type': 'object', 'additionalProperties': False,
                          'properties': {'prompt': {'type': 'string', 'description': 'The prompt the work was done from.'},
                                         'model': {'type': 'string', 'description': 'The model that did the work.'},
                                         'role': {'type': 'string', 'description': 'The role of the agent.'}}})
TOKEN = Noun('nonce', 'The call nonce; omit when running through that nonce.', required=False)
VARIABLES = Noun('variables', 'The interpreter\'s current variable values, an object of variable name to value.',
                 kind='json', required=False,
                 schema={'type': 'object', 'additionalProperties': True,
                         'description': 'Each key is a variable name; its value is that variable\'s current JSON value.'})
# A noun that may follow a nonce is positional and optional, so the grammar collects its words as a list; over MCP it
# takes one text as well, read by _words.
TEXT = {'type': 'string'}
CALL = Noun('call','An Axiom call by address and name, with keyword arguments and optional return targets.')

MODULE = Module(
    id='workflow', summary='Write, import and run reusable Axiom subroutines.',
    purpose='Stores reusable Axiom logic in ordinary knowledge layers and transports calls, parameters and '
            'returns for the agent interpreter. Fresh-agent calls use nonce handoffs. Details: metaform help workflow.',
    details='The agent interprets Choice, Parallel, Map, Retry, Catch and verification from the stored Axiom. '
            'run gives its entry call; call composes on the same agent; handoff gives a nonce to a fresh agent. '
            'resume redeems it on CLI or MCP; complete returns to its caller and fail delivers a named error. '
            'Workflow logic can sit on any element, including a subtype. Selected and masked knowledge layers '
            'decide what callable logic is available. The skills write_workflow and import_workflow write and import '
            'workflows; lexicalize serves the prompt-lexicalization script with its inputs. lib, libs, skill, skills '
            'and scan serve the libs and skills; assign hands a skill to a fresh agent by nonce, and complete closes '
            'it.',
    tables=catalog.TABLES, node_read=catalog.node_read,
    verbs=(
        Verb('lexicalize', lexicalize, 'Read the prompt-lexicalization script with a prompt as input.',
             nouns=(Noun('text', 'The imported prompt or workflow, verbatim.'),)),
        Verb('preprocess', preprocess, 'Place visible knowledge between a lexicalized prompt body and its address footer.',
             nouns=(Noun('text', 'The lexicalized prompt body, verbatim, without its address footer.'),
                    Noun('addresses', 'The namespace addresses named by the prompt, as a JSON list.', 'json',
                         schema={'type': 'array', 'items': {'type': 'string'}}))),
        Verb('list', workflows, 'List visible workflow elements and their subroutine names.'),
        Verb('submit', submit, 'Record a workflow element in an ordinary knowledge layer.',
             nouns=(ADDRESS, LAYER, Noun('name', 'The canonical workflow name.', required=False),
                    Noun('name_length', 'Trailing address segments that name its short type.', 'int', required=False),
                    Noun('selected', 'Knowledge layers selected to go with this workflow, by name or id.', 'json',
                         required=False, schema={'type': 'array', 'items': {'type': 'string'}}),
                    PROVENANCE)),
        Verb('add_logic', add_logic, 'Record an Axiom subroutine on a workflow or project element.',
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
             nouns=(Noun('calls', 'The independent Axiom calls, each written as call is.', 'json',
                         schema={'type': 'array', 'items': {'type': 'string'}, 'minItems': 1}), TOKEN, VARIABLES)),
        Verb('complete', complete, 'Deliver RETURN to the caller, or close an assignment; the interpreter supplies '
                                   'its final variables.',
             nouns=(TOKEN, VARIABLES, Noun('return', 'RETURN of a value or tuple; an assignment needs none.',
                                           required=False, many=True, schema=TEXT))),
        Verb('fail', fail, 'Deliver an error to the caller for its authored Retry or Catch.',
             nouns=(Noun('name', 'The authored error name.'), TOKEN,
                    Noun('message', 'The error detail.', required=False))),
        Verb('lib', lib, 'Read one lib, its shared sections at their newest stored versions.',
             nouns=(Noun('name', 'lib_axiom, lib_metaform, lib_workflow or lib_quality.'),)),
        Verb('libs', libs, 'List the libs, each with its first line, its marker.'),
        Verb('skill', skill, "Read one skill's Axiom.", nouns=(Noun('name', 'The skill name.'),)),
        Verb('skills', skills, 'List the skills, each with what its # skill: line says and the libs its # requires: '
                               'line names.'),
        Verb('serve', serve, 'Read one skill whole, its libs first and an input bound as data, as dispatch sends it to '
                             'an agent it started.',
             nouns=(Noun('name', 'The skill name.'), Noun('input', 'The input, bound as data.', required=False)),
             surfaces=('cli',)),
        Verb('scan', scan, 'Read the scan skill with a workflow and its task bound as data.',
             nouns=(Noun('workflow', 'The workflow text or address.'),
                    Noun('task', 'write, import, workflow_efficiency or prompt_efficiency.', required=False))),
        Verb('assign', assign, 'Hand a skill to a fresh agent by nonce; run through it, read the assignment.',
             nouns=(Noun('input', "The skill's input.", required=False),
                    Noun('skill', 'The skill name; none when run through its nonce.', required=False, many=True,
                         schema=TEXT))),
    ),
)
