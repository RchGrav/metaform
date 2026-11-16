"""The connection to a harness: start its process, agree on a protocol version, hand the stream to that version's
adapter.

The client asks for version 2 on every connection, as ACP's version negotiation says a client asks for the latest it
supports. A harness that knows v2 selects it; one that knows only v1 selects 1 and reads the v2 request without the
client capabilities v1 has (client files, client terminals, terminal login and the rest). So a harness that selects
1 is started again and initialized afresh in v1, with them: a v1-only harness may refuse a second `initialize` on one
connection, and the stream is the process's. The evidence for v1 is the protocol's: the answer says 1, or it is in
v1's shape, or the refusal lists 1 (`v2.evidence`). Anything else is an error, never a guess.

Client files and terminals exist only in v1. A connection that needs them asks for v1 at once, rather than starting
the harness in v2 and again in v1: for that connection v1 is the latest version the client can use. A harness that
knows only v2 refuses it, and is then spoken to in v2 with what it cannot give listed in `Harness.unsupported`.
A terminal login is in both versions and needs no v1.

The setting `dispatch_acp_v2`, on by default, turns v2 off, for the day a change to the draft breaks a harness; the
caller reads it and passes `v2`.
"""
from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Any

from .model import Client, ClientTools, Harness, Offer, SelectedVersion
from .v1 import V1
from .v2 import V2

START_LIMIT = 300.0  # seconds a harness has to start and answer initialize; npx may download it first
LINE_LIMIT = 64 * 1024 * 1024  # the longest line read from a harness

Starter = Callable[[], Awaitable[asyncio.subprocess.Process]]


def starter(command: list[str], *, cwd: str, env: dict[str, str] | None = None,
            stderr: Any = asyncio.subprocess.DEVNULL, **options: Any) -> Starter:
    """How to start a harness: its command in `cwd`, in a process group of its own (so ending it ends what it started,
    such as the harness npx runs), its standard input and output piped for ACP. `stderr` is where its own output goes;
    a pipe must be read by the caller."""
    from .. import group_options

    async def start() -> asyncio.subprocess.Process:
        return await asyncio.create_subprocess_exec(
            *command, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=stderr, cwd=cwd, env=env,
            limit=LINE_LIMIT, **{**group_options(), **options})
    return start


async def connect(start: Starter, client: Client, *, info: dict[str, str], offer: Offer | None = None,
                  v2: bool = True, tools: ClientTools | None = None, timeout: float = START_LIMIT) -> Harness:
    """A started, initialized harness on the version it selected. `info` is the client's name, title and version;
    `offer` what the client offers; `tools` answer client files and terminals, which `offer` may ask for only with
    them."""
    offer = offer or Offer()
    if (offer.files or offer.terminals) and tools is None:
        raise ValueError('Client files and terminals are offered only with the tools that answer them.')
    if v2 and not (offer.files or offer.terminals):
        harness = await opened(V2(await start(), client), info, offer, timeout)
        if harness is not None:
            return harness
    made = await opened(V1(await start(), client, tools), info, offer, timeout, fallback=v2)
    if made is not None:
        return made
    # a harness that knows only v2, asked for v1 for what only v1 has: spoken to in v2 without it
    harness = await opened(V2(await start(), client), info, offer, timeout, fallback=False)
    assert harness is not None
    harness.unsupported += [name for name, wanted in (('client files', offer.files),
                                                      ('client terminals', offer.terminals)) if wanted]
    return harness


async def opened(harness: Harness, info: dict[str, str], offer: Offer, timeout: float, *,
                 fallback: bool = True) -> Harness | None:
    """The harness initialized; None when it selected the other version and `fallback` allows trying that one, the
    first process then ended. Any failure ends the process before it is raised."""
    try:
        await harness.initialize(info, offer, timeout)
        return harness
    except SelectedVersion as selected:
        await closed(harness)
        other = 1 if harness.protocol == 2 else 2
        if fallback and selected.version == other:
            return None
        raise
    except BaseException:
        await closed(harness)
        raise


async def closed(harness: Harness) -> None:
    with contextlib.suppress(Exception):
        await harness.close()
