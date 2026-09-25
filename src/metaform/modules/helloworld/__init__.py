"""helloworld: each chassis feature working once, BASE-019.

  settings  `greeting` and `loud`, declared in code; `loud` is also greet's switch,
            CLI-012; `favorite` is a select whose choices come from this module's data
  greet     a sync verb with a noun and a switch; it publishes helloworld.greeted
  wait      an async verb
  history   reads what the event subscriber recorded, a layer in the project store
  forget    a caution verb that acts only with --confirm
  beep      a verb that runs on one system only, BASE-016
  status    a status hook that adds one line to `metaform` status

The greeting history is items in a layer this module declares, attached to an
element the layer creates for them, STORE-022 and D22.
"""
from __future__ import annotations

import asyncio
from typing import Any

from metaform import settings
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


def record(payload: dict[str, Any], ctx: Context) -> None:
    """helloworld.greeted: remember the name as one item of this module's layer."""
    store = ctx.require_store()
    with store.atomic():
        store.layer(LAYER, 'helloworld', 'Who helloworld has greeted.', mutable=True, hideable=True,
                    provenance=PROVENANCE)
        store.add_element(LAYER, HOLDER)
        store.add_item(LAYER, Node('element', HOLDER), payload['name'])


def status(ctx: Context) -> Status:
    if ctx.store is None:
        return Status()
    count = len(_names(ctx.store))
    return Status(lines=(f'Helloworld: {count} greeted',)) if count else Status()


MODULE = Module(
    id='helloworld',
    summary='A demonstration of every module feature.',
    purpose='Shows each Metaform module feature working once: it greets names, keeps them as a layer, and '
            'publishes an event for each greeting. Use it to see how a module behaves. '
            'Details: metaform help helloworld.',
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
    ),
    subscriptions=(Subscription('helloworld.greeted', record),),
    status=status,
)
