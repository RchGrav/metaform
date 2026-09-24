# template

The template module shows every feature a module can use, once each. Copy this
folder to start your own module, rename it, and replace the verbs.

## Layout

A module is a folder with an `__init__.py` that sets two names:

- `SUPPORTED_OS`: a literal tuple such as `('linux', 'macos', 'windows')`.
  Metaform reads it without running the module.
- `MODULE`: a `metaform.module.Module`. Its `id` must match the folder name.

Put the folder in `~/.metaform/modules/`, or publish it as a package with an
entry point in the `metaform.modules` group.

## Verbs

A verb runs as `metaform <module> <verb> <nouns> [--adverbs]`. Commands are
verbs, the words after them are the nouns they act on, and adverbs change how
they run.

| Verb | Shows |
|---|---|
| `greet <name> [--loud]` | A sync verb, a noun, an adverb, and publishing an event |
| `wait <seconds>` | An async verb |
| `history` | Reading data a subscriber wrote |
| `forget` | A verb that asks for `--confirm` before it acts |

A verb function takes one `ctx` argument:

- `ctx.nouns` and `ctx.adverbs` hold what the user typed.
- `ctx.setting(key)` returns a setting's value for the current folder.
- `ctx.data` is this module's data folder in the Metaform home.
- `ctx.publish(topic, payload)` sends an event to every subscriber.
- `ctx.say(text)` prints a line.

Raise `Stop(message, next_step)` for a user error. Metaform prints the message
and the one command to run next.

## Settings

Declare settings in the module's code:

```python
from metaform import settings

settings.text('greeting', 'hello', help='The word the template module greets with.')
settings.choice('favorite', choices=lambda: names_from_my_data(), help='...')
```

They appear in `metaform set`, `metaform unset`, `metaform help switches` and
the `metaform config` screen with no other code. The defaults are the working
settings: a module works as installed.

## Events

`Subscription(topic, handler)` receives every `ctx.publish` of that topic. The
template records each greeted name in `history.json` in its data folder, and the
`favorite` setting reads its choices from there.

## Tests

`tests/test_modules.py` in the Metaform repository runs every verb, setting and
event of this module through the real `metaform` command.
