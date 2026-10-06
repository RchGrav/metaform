"""Public entrypoint for the standalone teaching module."""

SUPPORTED_OS = ('linux', 'macos', 'windows')

from .plugin import PLUGIN

__all__ = ['PLUGIN']
