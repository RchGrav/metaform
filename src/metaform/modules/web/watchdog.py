"""The web GUI's watchdog, VIEW-002: the process `metaform web start` runs, which starts the page server and starts it
again when it ends or hangs.

Every CHECK seconds it asks the server's /api/health. It starts the server again when the server's process ends, when
nothing listens on its port any more, when /api/health answers that a page read is stuck (server.py's STUCK), or when
/api/health has given no healthy answer for SILENT seconds. Each restart is written to run/web.log with its cause,
and the new server is told it, so the page can say what happened. A server that ends again soon after it started
waits a little longer before each new start, so one that cannot start does not spin. A server that hands over to newer
code, STORE-029, is followed to its successor, which is no restart.

Agents go on through a restart: a runner is started in a session of its own, never as the server's child, and a
restarted server takes up the runners still alive. With the hold tool installed, `start` places the watchdog as a hold
call named metaform-web-<port>, so `hold list` shows it and `hold end` stops it and its server; hold has no restart or
health check of its own, so the watchdog does both either way. `metaform web stop` stops the watchdog first, which ends
its server.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import secrets
import signal
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from types import FrameType
from typing import Any, cast

from metaform import home

from . import (
    PYTHON,
    WAIT,
    answering,
    host_port,
    reach,
    ready_line,
    recorded,
    run_dir,
    spawn,
    token,
    watchdog_file,
    write_run,
)

CHECK = 5.0  # seconds between two asks of /api/health
SILENT = 20.0  # seconds with no healthy answer before the server is started again
ASK = 4.0  # the limit on one answer of /api/health
QUICK = 30.0  # a server that ends sooner than this after its start waits before the next one
PAUSE_MOST = 30.0  # the longest wait before a start, for a server that keeps ending at once


class Stopped(BaseException):
    """The stop signal, raised out of whatever the watchdog was waiting on, so it ends its server in order."""


def log(text: str) -> None:
    """One line of run/web.log, beside the server's own, stamped with its UTC time and this process."""
    print(f'{datetime.now(UTC).isoformat(timespec="seconds")} Watchdog {os.getpid()}: {text}', file=sys.stderr,
          flush=True)


def now_said() -> str:
    return datetime.now(UTC).isoformat(timespec='seconds')


class Watchdog:
    def __init__(self, bind: str, port: int) -> None:
        self.bind, self.port = bind, port
        self.process: subprocess.Popen[bytes] | None = None  # the server, when it is this watchdog's own child
        self.pid: int | None = None  # the server's process, its own or a successor it handed over to
        self.began = 0.0  # when the server last started
        self.restarts = 0
        self.quick = 0  # restarts in a row of a server that ended soon after it started
        self.started = now_said()

    def record(self) -> None:
        """run/web-watchdog.json: this process, its port, and the server it keeps, for `start` and `stop`."""
        path = watchdog_file()
        written = path.with_suffix('.tmp')
        write_run(written, json.dumps({'pid': os.getpid(), 'bind': self.bind, 'port': self.port, 'server': self.pid,
                                       'started': self.started, 'restarts': self.restarts}))
        os.replace(written, path)

    def start(self, nonce: str, restarted: dict[str, Any] | None) -> bytes | None:
        """Start the server and return its line saying it listens, as `start` reads it: empty when it ended first,
        None when it said nothing within `WAIT`, and was then ended."""
        process = spawn(self.bind, self.port, nonce, supervisor=str(os.getpid()),
                        restarted=json.dumps(restarted) if restarted else None)
        self.process, self.pid = process, process.pid  # a stop signal from here on ends it too
        line = ready_line(process)
        if process.stdout is not None:
            process.stdout.close()
        if line:
            self.began = time.monotonic()
            self.record()
            return line
        if line is None:
            process.kill()
        process.wait()
        self.process = self.pid = None
        return line

    def health(self) -> tuple[str, dict[str, Any] | None]:
        """One ask of /api/health: `ok`, `stuck` (a page read is wedged), `refused` (nothing listens) or `silent`
        (no answer, or not a healthy one), with what it answered."""
        address = reach(self.bind)
        connection = http.client.HTTPConnection(address, self.port, timeout=ASK)
        try:
            connection.request('GET', '/api/health', headers={'Host': host_port(address, self.port),
                                                              'X-Metaform-Token': token() or ''})
            response = connection.getresponse()
            found: Any = json.loads(response.read())
        except ConnectionRefusedError:
            return 'refused', None
        except (OSError, ValueError):
            return 'silent', None
        finally:
            connection.close()
        said = cast(dict[str, Any], found) if isinstance(found, dict) else None
        if response.status == 200 and said is not None:
            return 'ok', said
        if response.status == 503 and said is not None and said.get('stuck'):
            return 'stuck', said
        return 'silent', said

    def successor(self) -> int | None:
        """The server this one handed over to, when the run record names another that answers."""
        record = recorded()
        if record is None or record.get('pid') == self.pid or not answering(record):
            return None
        return int(record['pid'])

    def watch(self) -> str:
        """Wait until the server must be started again, and say why."""
        healthy, last = time.monotonic(), ''
        while True:
            if self.process is not None:
                try:
                    code = self.process.wait(CHECK)
                except subprocess.TimeoutExpired:
                    pass
                else:
                    successor = self.successor()
                    if successor is None:
                        return f'its process {self.pid} ended with code {code}'
                    log(f'the server handed over from process {self.pid} to process {successor}')
                    self.process, self.pid, healthy = None, successor, time.monotonic()
                    self.record()
                    continue
            else:
                time.sleep(CHECK)
            state, found = self.health()
            slowest = cast(dict[str, Any], (found or {}).get('slowest') or {})
            last = str(slowest.get('said') or last)
            if state == 'ok':
                healthy = time.monotonic()
                continue
            if state == 'stuck' and found is not None:
                slow = cast(dict[str, Any], found.get('slow') or slowest)
                return f'{slow.get("route")} was stuck, {slow.get("said")}'
            if state == 'refused' and self.process is None:
                return f'nothing listens on port {self.port} where process {self.pid} served'
            silent = time.monotonic() - healthy
            if silent >= SILENT:
                return f'/api/health gave no healthy answer for {silent:.0f} s' + (
                    f'; it last said it was {last}' if last else '')

    def end(self) -> None:
        """End the server: the stop signal, then, if it is still there after a while, killed."""
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(WAIT / 3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        elif self.pid is not None:
            try:
                os.kill(self.pid, signal.SIGTERM)
            except OSError:
                pass
            else:
                deadline = time.monotonic() + WAIT / 3
                while self.health()[0] != 'refused' and time.monotonic() < deadline:
                    time.sleep(0.2)
                if self.health()[0] != 'refused' and hasattr(signal, 'SIGKILL'):
                    try:
                        os.kill(self.pid, getattr(signal, 'SIGKILL'))  # noqa: B009  POSIX systems only
                    except OSError:
                        pass
        self.process, self.pid = None, None

    def run(self, nonce: str, ready: Path | None) -> int:
        """Start the server, tell `start` it listens, then keep it: started again on every cause `watch` finds."""
        line = self.start(nonce, None)
        tell(line or b'', ready)
        if not line:
            return 1  # the server wrote why to the log, and `start` reports it
        log(f'keeps the server, process {self.pid}, on port {self.port}')
        while True:
            cause = self.watch()
            self.restarts += 1
            log(f'starting the server again ({self.restarts}): {cause}')
            self.quick = self.quick + 1 if time.monotonic() - self.began < QUICK else 0
            self.end()
            restarted = {'at': now_said(), 'cause': cause, 'count': self.restarts}
            while True:
                pause = min(PAUSE_MOST, 2.0 ** self.quick) if self.quick else 0.0
                time.sleep(pause)
                if self.start(secrets.token_hex(8), restarted):
                    break
                self.quick += 1
                log(f'the server did not start again; trying in {min(PAUSE_MOST, 2.0 ** self.quick):.0f} s')
            log(f'started the server again, process {self.pid}')


def tell(line: bytes, ready: Path | None) -> None:
    """Pass the server's line saying it listens to `start`: through the named pipe it made, under hold, or on the
    pipe this process inherited as its standard output, which is then pointed at the log."""
    if ready is not None:
        with ready.open('wb') as stream:
            stream.write(line)
        return
    sys.stdout.buffer.write(line)
    sys.stdout.flush()
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='metaform-web-watchdog')
    parser.add_argument('--bind', required=True)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--nonce', required=True)
    parser.add_argument('--ready', type=Path, help='the named pipe `start` reads, under hold')
    given = parser.parse_args(argv)
    os.environ.pop(PYTHON, None)  # how a hold call ran this process; nothing it starts needs it
    folder = run_dir()
    home.mkdir_private(folder)
    # The log is run/web.log under hold too, which would keep it in its own.
    kept = os.open(folder / 'web.log', os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    os.dup2(kept, sys.stderr.fileno())
    os.close(kept)
    watchdog = Watchdog(given.bind, given.port)

    def stopped(number: int, frame: FrameType | None) -> None:
        raise Stopped(signal.Signals(number).name)

    signal.signal(signal.SIGTERM, stopped)
    watchdog.record()
    try:
        return watchdog.run(given.nonce, given.ready)
    except Stopped as signalled:
        log(f'stopped by {signalled}; ending the server, process {watchdog.pid}')
        watchdog.end()
        return 0
    except Exception:  # noqa: BLE001  whatever ends the watchdog is written to the log with its time
        log(f'stopped by an unhandled error:\n{traceback.format_exc().rstrip()}')
        return 1
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        try:
            found: Any = json.loads(watchdog_file().read_text(encoding='utf-8'))
            if isinstance(found, dict) and cast(dict[str, Any], found).get('pid') == os.getpid():
                watchdog_file().unlink(missing_ok=True)
        except (OSError, ValueError):
            pass


if __name__ == '__main__':
    sys.exit(main())
