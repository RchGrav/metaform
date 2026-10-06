"""Setting declarations and visibility use the chassis settings service."""
from metaform import settings
from metaform.plugin_contract import Setting

SETTINGS = (Setting('label', 'Showcase', 'Label on newly created sample note joins.'),
              Setting('write_enabled', True, 'Expose note, annotation, prompt and authoring commands and operations.', bool),
              Setting('async_enabled', True, 'Expose the async command and its operations.', bool),
              Setting('watch_enabled', True, 'Restore the dynamic observer on activation.', bool),
              Setting('lifecycle', 'new', 'Latest activation or teardown state.'))


def write_enabled():
    return settings.get('write_enabled')


def async_enabled():
    return settings.get('async_enabled')
