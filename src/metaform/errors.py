"""The two user-facing error types every surface prints the same way.

`Stop` is a user error: what happened and the one command to run next,
CLI-009. `StoreError` is the data access object's error, STORE-026; it is a
`Stop`, so the CLI and MCP print it without knowing where it came from.
"""
from __future__ import annotations


class Stop(Exception):
    """A user error. It says what happened and the one command to run next."""

    def __init__(self, message: str, next_step: str) -> None:
        super().__init__(message)
        self.message = message
        self.next_step = next_step


class StoreError(Stop):
    """A shape error from the data access object. It never judges content."""
