"""Copyable external module using only Metaform's public extension contract."""

SUPPORTED_OS = ('linux', 'macos', 'windows')

import hashlib
import json
from pathlib import Path

import click

from metaform import cli, data, event, settings
from metaform.event import EventMessage
from metaform.objects import Record
from metaform.plugin_contract import Plugin, Setting, Subscription


def record(address: str, text: str) -> Record:
    result = data.put(address, {'text': text, 'label': settings.get('label'), 'joins': {}})
    event.publish('record_demo.saved', refs=(address,))
    return result


async def fingerprint(address: str, path: str) -> Record:
    # File reading and hashing are blocking work, even when an operation is async.
    import asyncio
    digest = await asyncio.to_thread(lambda: hashlib.sha256(Path(path).read_bytes()).hexdigest())
    result = await data.aput(address, {'source': str(Path(path).resolve()), 'sha256': digest, 'joins': {}})
    await event.apublish('record_demo.saved', refs=(address,))
    return result


def saved(notification: EventMessage) -> None:
    # A handler's output belongs to this module and retains the publishing context.
    data.put('data.observation.latest', {'event': notification, 'joins': {}})


@click.command('record-demo', help='Store a project record and inspect its production history.')
@click.argument('address')
@click.option('--text', required=True, help='Record text, preserved as supplied.')
def record_command(address, text):
    cli.output(cli.invoke('record', address=address, text=text))


@click.command('fingerprint', help='Hash a source file asynchronously without changing it.')
@click.argument('address')
@click.argument('path', type=click.Path(exists=True, dir_okay=False))
def fingerprint_command(address, path):
    cli.output(cli.invoke('fingerprint', address=address, path=path))


PLUGIN = Plugin(
    id='record_demo',
    operations={'record': record, 'fingerprint': fingerprint},
    commands=(record_command, fingerprint_command),
    settings=(Setting('label', 'Example record', help='Label attached to new records.'),),
    subscriptions=(Subscription('record_demo.saved', saved),),
)
