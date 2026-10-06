"""Compose the requester from its contained template and contributions."""
from dataclasses import replace
from .template import PLUGIN as TEMPLATE
from .commands import COMMANDS
from .events import SUBSCRIPTIONS
from .help import MODULE_HELP
from .operations import OPERATIONS
from .settings import SETTINGS

PLUGIN = replace(
    TEMPLATE, id='event_requester',
    description='Send work through the chassis event bus and retain the later response.',
    help=MODULE_HELP, operations=OPERATIONS, commands=COMMANDS, settings=SETTINGS,
    subscriptions=SUBSCRIPTIONS, command_visibility={}, operation_visibility={},
)
