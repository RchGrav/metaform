"""Lifecycle scaffold copied from ../showcase; this package owns its hooks."""
from metaform import cli, data, event, settings
from metaform.plugin_contract import Plugin, Setting

_watches = {}


def start():
    settings.set('lifecycle', 'started')
    if settings.get('watch_enabled'):
        module = cli.context().module
        _watches[module] = event.subscribe(module + '.saved', observed)


async def stop():
    handle = _watches.pop(cli.context().module, None)
    if handle is not None:
        event.unsubscribe(handle)
    await settings.aset('lifecycle', 'stopped')


def observed(notification):
    return data.namespace_store().put_join('data.' + cli.context().module + '.observation', {
        'id': 'latest', 'type': 'example.receipt',
        'event': notification['id'], 'refs': notification['refs'],
    })


PLUGIN = Plugin(
    id='template',
    settings=(Setting('watch_enabled', True, 'Restore the dynamic observer on activation.', bool),
              Setting('lifecycle', 'new', 'Latest activation or teardown state.')),
    start=start,
    stop=stop,
)
