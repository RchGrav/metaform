"""The web GUI's restart, VIEW-002: the process `metaform web restart` hands the stop and the start to, so the page comes
back even when the process that asked ends between the two, as an agent's session can. What it does is the package's
`restarting`: the new server listens on the bind address and port the old one was started with.

Without the hold tool it is a detached process in a session of its own that forks once and lets its parent end, so it
is no longer among the descendants of the process that asked, and a kill of that process's tree or group does not
reach it. With hold, `restart` places it as the hold call metaform-web-restart-<port>, which hold keeps. Either way it
says how the restart went in one line of JSON, the start's answer or the error, to whoever still waits for it; no one
waiting changes nothing. What it does is written to run/web.log.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from metaform import home
from metaform.module import Stop, context

from . import PYTHON, restarting, run_dir


def log(text: str) -> None:
    """One line of run/web.log, beside the watchdog's and the server's, stamped with its UTC time and this process."""
    print(f'{datetime.now(UTC).isoformat(timespec="seconds")} Restart {os.getpid()}: {text}', file=sys.stderr,
          flush=True)


def tell(said: dict[str, Any], ready: Path | None) -> None:
    """Say how it went to `restart`: through its named pipe under hold, else on this process's standard output. A
    pipe no one reads any more, its asker gone, is left: the page is back all the same."""
    line = json.dumps(said).encode('utf-8') + b'\n'
    try:
        if ready is None:
            os.write(sys.stdout.fileno(), line)
            return
        descriptor = os.open(ready, os.O_WRONLY | os.O_NONBLOCK)  # refused at once when no one reads it
        try:
            os.write(descriptor, line)
        finally:
            os.close(descriptor)
    except OSError:
        log('no one waits for word of the restart any more')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='metaform-web-restart')
    parser.add_argument('--folder', type=Path, required=True)
    parser.add_argument('--ready', type=Path, help='the named pipe `restart` reads, under hold')
    given = parser.parse_args(argv)
    if sys.platform != 'win32' and given.ready is None and os.fork():
        os._exit(0)  # the parent ends at once, so this process is out of the asker's tree; hold holds its own call
    os.environ.pop(PYTHON, None)  # how a hold call ran this process; the watchdog it starts is given it again
    folder = run_dir()
    home.mkdir_private(folder)
    kept = os.open(folder / 'web.log', os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    os.dup2(kept, sys.stderr.fileno())
    os.close(kept)
    log('restarting the web GUI')
    try:
        said = restarting(context('web', given.folder))
    except Stop as stop:
        said = {'error': str(stop), 'next': stop.next_step or 'metaform web start'}
    except Exception:  # noqa: BLE001  whatever ends the restart is written to the log and said to the asker
        log(f'stopped by an unhandled error:\n{traceback.format_exc().rstrip()}')
        said = {'error': 'The restart failed; run/web.log in the Metaform home says why.', 'next': 'metaform web start'}
    log(f'the web GUI did not come back: {said["error"]}' if said.get('error') else
        f'the web GUI is {said.get("state")} at {said.get("address")}')
    tell(said, given.ready)
    return 1 if said.get('error') else 0


if __name__ == '__main__':
    sys.exit(main())
