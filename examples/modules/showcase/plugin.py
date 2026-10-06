"""Compose the teaching module and its lifecycle contributions."""
from metaform import settings
from metaform.plugin_contract import Plugin
from .commands import COMMANDS
from .events import SUBSCRIPTIONS, watch, close_watch
from .help import MODULE_HELP
from .operations import OPERATIONS
from .settings import SETTINGS, write_enabled, async_enabled


def start():
    settings.set('lifecycle', 'started')
    if settings.get('watch_enabled'):
        watch(True)


async def stop():
    close_watch()
    await settings.aset('lifecycle', 'stopped')


PLUGIN = Plugin(
    id='showcase', description='Explore every chassis service through inspectable project work.',
    help=MODULE_HELP, settings=SETTINGS, operations=OPERATIONS, commands=COMMANDS,
    command_visibility={'sample-write': write_enabled, 'sample-join': write_enabled,
                        'sample-prompt': write_enabled, 'sample-author': write_enabled,
                        'sample-async': async_enabled},
    operation_visibility={'write': write_enabled, 'annotate': write_enabled,
                          'prompt': write_enabled, 'author': write_enabled,
                          'delayed': async_enabled, 'queue': async_enabled},
    subscriptions=SUBSCRIPTIONS, start=start, stop=stop,
)
