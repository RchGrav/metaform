"""Public entry for the event requester module."""

SUPPORTED_OS = ('linux', 'macos', 'windows')

from .plugin import PLUGIN

__all__ = ["PLUGIN"]
