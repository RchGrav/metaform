"""Settings declarations inherited from the local lifecycle template."""
from .template import PLUGIN as TEMPLATE

SETTINGS = tuple(item for item in TEMPLATE.settings if item.key in {'watch_enabled', 'lifecycle'})
