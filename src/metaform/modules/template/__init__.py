"""The template module: one small example of every chassis feature.

Copy this folder to start a module. Each part below shows one feature:
  settings  declared in code with metaform.settings, including a select whose
            choices come from this module's own data
  greet     a sync verb with a noun and an adverb; it publishes an event
  wait      an async verb
  history   reads what the event subscriber recorded
  forget    a verb that asks for --confirm before it acts
"""
import asyncio
import json

from metaform import home, settings
from metaform.module import Adverb, Module, Stop, Subscription, Verb

SUPPORTED_OS = ('linux', 'macos', 'windows')


def _history_file():
    return home.home() / 'data' / 'template' / 'history.json'


def _greeted():
    path = _history_file()
    return json.loads(path.read_text()) if path.exists() else []


settings.text('greeting', 'hello', help='The word the template module greets with.')
settings.choice('favorite', choices=lambda: sorted(set(_greeted())),
                help="A name the template module has greeted. Its choices come from the module's own data.")


def greet(ctx):
    if len(ctx.nouns) != 1:
        raise Stop('greet needs one name.', 'metaform template greet <name>')
    name = ctx.nouns[0]
    text = f"{ctx.setting('greeting')}, {name}"
    ctx.say(text.upper() + '!' if ctx.adverbs.get('--loud') else text)
    ctx.publish('template.greeted', {'name': name})


async def wait(ctx):
    if len(ctx.nouns) != 1 or not ctx.nouns[0].isdigit():
        raise Stop('wait needs a number of seconds.', 'metaform template wait <seconds>')
    seconds = int(ctx.nouns[0])
    await asyncio.sleep(seconds)
    ctx.say(f'waited {seconds} s')


def history(ctx):
    names = _greeted()
    ctx.say('\n'.join(names) if names else 'No greetings yet. Try: metaform template greet <name>')


def forget(ctx):
    _history_file().unlink(missing_ok=True)
    ctx.say('Greeting history deleted.')


def record(payload, ctx):
    path = ctx.data / 'history.json'
    names = json.loads(path.read_text()) if path.exists() else []
    names.append(payload['name'])
    path.write_text(json.dumps(names))


MODULE = Module(
    id='template',
    summary='An example of every module feature. Copy it to start a module.',
    purpose='Shows how a module declares verbs, settings and events. It greets names and remembers them.',
    details='Settings are declared in code and appear in set, unset and the settings screen. '
            'The favorite setting takes its choices from the names this module has greeted.',
    verbs=(
        Verb('greet', greet, 'Greet a name and publish template.greeted.', nouns='<name>',
             adverbs=(Adverb('--loud', 'Shout the greeting.'),),
             examples=(('metaform template greet world', 'Prints hello, world.'),
                       ('metaform template greet world --loud', 'Prints HELLO, WORLD!'))),
        Verb('wait', wait, 'Wait a number of seconds. Shows an async verb.', nouns='<seconds>'),
        Verb('history', history, 'List the names greeted so far.'),
        Verb('forget', forget, 'Delete the greeting history.',
             caution='This deletes the greeting history.'),
    ),
    subscriptions=(Subscription('template.greeted', record),),
)
