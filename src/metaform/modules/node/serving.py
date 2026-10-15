"""uvicorn's server, waiting on events rather than looking ten times a second, QUAL-015.

uvicorn's own main loop wakes every 0.1 s to see whether it should exit. This one waits for the exit it is told of,
by a signal or by `stop`, and sets `ready` once it listens, so nothing waits on its `started` flag in a loop either.
"""
from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import uvicorn


class Serving(uvicorn.Server):
    def __init__(self, config: uvicorn.Config) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self.ready = asyncio.Event()
        self.exiting = asyncio.Event()
        self.exit = False
        super().__init__(config)

    @property
    def should_exit(self) -> bool:  # pyright: ignore[reportIncompatibleVariableOverride]
        """uvicorn's flag, which anything may set, as uvicorn's own signal handler does: setting it wakes the loop."""
        return self.exit

    @should_exit.setter
    def should_exit(self, value: bool) -> None:
        self.exit = value
        if value:
            self._wake()

    async def startup(self, sockets: list[Any] | None = None) -> None:
        self.loop = asyncio.get_running_loop()
        await super().startup(sockets=sockets)
        if self.started:
            self.ready.set()

    async def main_loop(self) -> None:
        await self.on_tick(0)  # the default headers, as uvicorn's own first tick sets them
        if not self.should_exit:
            await self.exiting.wait()

    def stop(self) -> None:
        """End serving, from the server's own loop or any other thread."""
        self.should_exit = True

    def _wake(self) -> None:
        if self.loop is not None:
            with contextlib.suppress(RuntimeError):  # its loop has closed: it is not serving
                self.loop.call_soon_threadsafe(self.exiting.set)
