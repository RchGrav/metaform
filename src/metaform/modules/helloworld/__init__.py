"""helloworld: each chassis feature working once, BASE-019.

  settings  `greeting` and `loud`, declared in code; `loud` is also greet's switch,
            CLI-012; `favorite` is a select whose choices come from this module's data
  greet     a sync verb with a noun and a switch; it publishes helloworld.greeted
  wait      an async verb
  history   reads what the event subscriber recorded, a layer in the project store
  live      the chassis announces the subscriber's write as map.changed, so an open web GUI shows the greeting at once,
            VIEW-018; the module does nothing for it
  forget    a caution verb that acts only with --confirm
  todo      writes a work record, the condition of this module's own element kept apart from the map, MAP-046;
            done resolves it, and the status line counts what is still to do
  beep      a verb that runs on one system only, BASE-016
  task      hands a task out by nonce, BASE-050: the agent runs metaform <nonce> for what to do and
            metaform <nonce> finish when it is done, which closes the nonce
  status    a status hook that adds one line to `metaform` status

The greeting history is items in a layer this module declares, attached to an
element the layer creates for them, STORE-022 and D22.
"""
from __future__ import annotations

import asyncio
from typing import Any

from metaform import nonce, settings
from metaform.data import Node, Store
from metaform.module import Context, Module, Noun, Status, Subscription, Verb

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = True

LAYER = 'helloworld.greetings'
HOLDER = 'code.module.helloworld'
PROVENANCE = {'module': 'helloworld', 'workflow': 'greet', 'role': 'module'}


def _names(store: Store) -> list[str]:
    """The names greeted so far. No layer yet means no names yet; any other failure is real and raises."""
    if not any(layer.name == LAYER for layer in store.layers(limit=0).results):
        return []
    items = store.layer_items(LAYER, limit=0).results
    return [str(item.value) for item in items if getattr(item, 'item_id', None)]


def _favorite_choices(ctx: Context) -> list[str]:
    return sorted(set(_names(ctx.store))) if ctx.store is not None else []


settings.text('greeting', 'hello', help='The word helloworld greets with.')
settings.boolean('loud', False, help='Shout the greeting.')
settings.choice('favorite', choices=_favorite_choices,
                help="A name helloworld has greeted. Its choices come from the module's own data.")


def greet(ctx: Context) -> str:
    ctx.require_store()
    name = ctx.nouns['name']
    text = f"{ctx.setting('greeting')}, {name}"
    if ctx.setting('loud'):
        text = text.upper() + '!'
    ctx.publish('helloworld.greeted', {'name': name})
    return text + '\n'


async def wait(ctx: Context) -> str:
    seconds = ctx.nouns['seconds']
    await asyncio.sleep(seconds)
    return f'waited {seconds} s\n'


def history(ctx: Context) -> list[str] | str:
    names = _names(ctx.require_store())
    return '\n'.join(names) + '\n' if names else 'No greetings yet. Try: metaform helloworld greet <name>\n'


def forget(ctx: Context) -> str:
    store = ctx.require_store()
    if any(layer.name == LAYER for layer in store.layers(limit=0).results):
        store.discard(LAYER)
    return 'Greeting history deleted.\n'


def beep(ctx: Context) -> str:
    return '\a'


def task(ctx: Context) -> str:
    return 'Run: metaform ' + nonce.request('helloworld', 'brief', {'name': str(ctx.nouns['name'])})


def brief(ctx: Context) -> str:
    held = nonce.current()
    return f'Greet {held.value["name"]}, then run: metaform {held.nonce} finish'


def finish(ctx: Context) -> str:
    held = nonce.current()
    ctx.nouns['name'] = held.value['name']
    greet(ctx)
    nonce.close(held.nonce)
    return f'{held.value["name"]} is greeted; the task is complete.'


def _own_element(store: Store) -> None:
    """The element the greetings hang from, made when no greeting has made it yet."""
    with store.atomic():
        store.layer(LAYER, 'helloworld', 'Who helloworld has greeted.', mutable=True, hideable=True,
                    provenance=PROVENANCE)
        store.add_element(LAYER, HOLDER)


def todo(ctx: Context) -> str:
    """A work record on this module's own element: tbd, with the task given, MAP-046 and STORE-042."""
    store = ctx.require_store()
    _own_element(store)
    record = store.add_work(Node('element', HOLDER), 'tbd', note='helloworld has more to do', task=ctx.nouns['task'])
    return f'To do: {ctx.nouns["task"]} ({record.work_id})\n'


def done(ctx: Context) -> str:
    """Mark one of this module's work records done, its resolution kept beside it."""
    record = ctx.require_store().finish_work(ctx.nouns['id'], ctx.nouns['resolution'])
    return f'Done: {record.task} ({record.resolution})\n'


def _to_do(store: Store) -> int:
    return len(store.work(Node('element', HOLDER), open=True, limit=0).results)


def record(payload: dict[str, Any], ctx: Context) -> None:
    """helloworld.greeted: remember the name as one item of this module's layer."""
    store = ctx.require_store()
    with store.atomic():
        layer = store.layer(LAYER, 'helloworld', 'Who helloworld has greeted.', mutable=True, hideable=True,
                            provenance=PROVENANCE)
        store.add_element(LAYER, HOLDER)
        store.add_item(LAYER, Node('element', HOLDER), payload['name'])
    if layer.ready is None:  # finished, it is seen in context and stays editable, STORE-032
        store.finish(LAYER)


def status(ctx: Context) -> Status:
    if ctx.store is None:
        return Status()
    count, open_work = len(_names(ctx.store)), _to_do(ctx.store)
    if not count and not open_work:
        return Status()
    return Status(lines=(f'Helloworld: {count} greeted' + (f', {open_work} to do' if open_work else ''),))


MODULE = Module(
    id='helloworld',
    summary='A demonstration of every module feature.',
    purpose='Shows each Metaform module feature working once: it greets names, keeps them as a layer, '
            'publishes an event for each greeting, and keeps what it still has to do as work records. Use it to see '
            'how a module behaves. Details: metaform help helloworld.',
    details='Settings are declared in code and appear in set, unset and the settings screen. '
            'The favorite setting takes its choices from the names this module has greeted.',
    verbs=(
        Verb('greet', greet, 'Greet a name and publish helloworld.greeted.',
             nouns=(Noun('name', 'The name to greet.'),), switches=('loud',),
             examples=(('metaform helloworld greet world', 'Prints hello, world.'),
                       ('metaform helloworld greet world --loud', 'Prints HELLO, WORLD!'))),
        Verb('wait', wait, 'Wait a number of seconds. Shows an async verb.',
             nouns=(Noun('seconds', 'How long to wait.', kind='int'),)),
        Verb('history', history, 'List the names greeted so far.'),
        Verb('forget', forget, 'Delete the greeting history.', caution='This deletes the greeting history.'),
        Verb('beep', beep, 'Sound the terminal bell. Shows a verb that runs on one system.',
             supported_os=('windows',)),
        Verb('todo', todo, "Write a work record on this module's own element: something still to do.",
             nouns=(Noun('task', 'What it needs.'),),
             examples=(('metaform helloworld todo "greet in every language"', 'Records a tbd work record.'),)),
        Verb('done', done, 'Mark one of those work records done, keeping its resolution.',
             nouns=(Noun('id', 'The work record id todo returned.'), Noun('resolution', 'How it was resolved.'))),
        Verb('task', task, 'Hand out a greeting as a task, by nonce.', nouns=(Noun('name', 'The name to greet.'),)),
        Verb('brief', brief, 'What the task reached through a nonce asks for.'),
        Verb('finish', finish, 'Finish the task reached through a nonce, and close the nonce.'),
    ),
    subscriptions=(Subscription('helloworld.greeted', record),),
    status=status,
)
