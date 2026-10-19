"""Server-owned, event-driven log watch; project navigation never owns its lifetime."""
from __future__ import annotations

import threading
from typing import Any

from metaform.module import Context

from .watch import Watch


class Background:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.closed = threading.Event()
        self.lock = threading.RLock()
        self.watching: Watch | None = None
        self.listener: Any = None
        self.thread: threading.Thread | None = None
        self.retry: threading.Timer | None = None
        self.failures = 0
        self.start()

    def start(self) -> None:
        with self.lock:
            if self.closed.is_set():
                return
            self.thread = threading.Thread(target=self.run, name=f'logs {self.ctx.project}', daemon=True)
            self.thread.start()

    def run(self) -> None:
        watching: Watch | None = None
        failed = False
        try:
            with self.lock:
                if self.closed.is_set():
                    return
                watching = self.watching = Watch(self.ctx, self.ctx.require_store())
                self.listener = self.ctx.listen(watching.heard)
            watching.run()
        except Exception as error:  # noqa: BLE001  retry a failed service, never lose the server
            failed = True
            self.failures += 1
            self.ctx.publish('fault.raised', {'source': 'log watcher', 'message': str(error),
                'reproduce': 'Inspect autoticket logs and restart the watcher; verify a new log entry is captured.'})
        finally:
            if watching is not None:
                watching.release()
            with self.lock:
                if self.listener is not None:
                    self.listener.close()
                    self.listener = None
                if failed and not self.closed.is_set() and self.failures <= 5:
                    # A bounded failure retry is a deadline, not an idle polling loop.
                    self.retry = threading.Timer(min(30, 2 ** self.failures), self.start)
                    self.retry.daemon = True
                    self.retry.start()

    def close(self) -> None:
        with self.lock:
            self.closed.set()
            if self.retry is not None:
                self.retry.cancel()
            if self.watching is not None:
                self.watching.stop()
            thread = self.thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(10)


def start(ctx: Context) -> Background | None:
    return Background(ctx) if ctx.setting('autoticket_watch') else None
