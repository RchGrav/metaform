"""When something needs the person: the signals that place a call or send a text, in words they hear.

twilio_call_when and twilio_text_when each list group names, or dispatch's own signal names for one signal alone:

  waiting-for-you   an agent waits on the person: a permission, a question, a login, or it stopped with its
                    ticket open
  stuck             an agent looks stuck: spinning, silent, failing the same way, or reworked too often
  budget            an agent reached its budget
  intake-finished   the project's intake finished, so the map is ready

The serving bridge hears each signal as dispatch publishes it, in `map.changed` from the runner's process, BASE-053;
only the bridge calls, so a call is placed where its answer can be bridged, once, with the gap between calls the
person set.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, cast

GROUPS: dict[str, tuple[str, ...]] = {
    'waiting-for-you': ('permission-waiting', 'question-waiting', 'login-needed', 'stopped-open'),
    'stuck': ('spinning-calls', 'spinning-time', 'repeated-failure', 'silent', 'not-smooth', 'rework-limit'),
    'budget': ('budget',),
    'intake-finished': ('intake-finished',),
}
# What the call and text lists offer: each group, then each signal the groups hold, for one signal alone.
CHOICES = [*GROUPS, *dict.fromkeys(signal for signals in GROUPS.values() for signal in signals if signal not in GROUPS)]
SIGNAL = re.compile(r'^[a-z][a-z0-9-]{1,40}$')
TEXT_GAP = 60.0      # seconds between texts the bridge sends on its own
SAME_GAP = 3600.0    # seconds before the same signal on the same ticket is told again

WORDS = {
    'permission-waiting': 'an agent is waiting for your permission{what}',
    'question-waiting': 'an agent has a question for you{what}',
    'login-needed': '{agent} needs you to log in',
    'stopped-open': 'an agent stopped with its ticket still open{what}',
    'budget': 'an agent reached its budget{what}',
    'intake-finished': "the project's intake is finished and the map is ready",
}
STUCK = 'an agent looks stuck{what}'


def check(value: list[str], name: str) -> list[str] | None:
    wrong = [one for one in value if one not in GROUPS and not SIGNAL.match(one)]
    return [f'{name} takes {", ".join(GROUPS)} or a dispatch signal name; not {", ".join(wrong)}.'] if wrong else None


def signals_of(chosen: list[str]) -> set[str]:
    """The signal names a list of groups and names stands for."""
    found: set[str] = set()
    for one in chosen:
        found.update(GROUPS.get(one, (one,)))
    return found


def why(signal: dict[str, Any], task: str | None = None) -> str:
    """What needs the person, as a clause after "because", in words that say it on the phone."""
    name = str(signal.get('signal') or '')
    what = f' on "{task[:80]}"' if task else ''
    template = WORDS.get(name, STUCK if name in GROUPS['stuck'] else 'an agent raised ' + name.replace('-', ' ') + '{what}')
    return template.format(what=what, agent=str(signal.get('agent') or 'an agent'))


class Notifier:
    """Decides, for each signal heard, whether to call, to text, both or neither, and does it through `place` and
    `send`, which the bridge supplies. Calls and texts the same signal on the same ticket once per SAME_GAP.

    `place(reason)` answers whether the call is being placed: False when twilio_call_gap_minutes or a call in progress
    holds it back. A call or text held back is not counted as told; it waits, and `retry` places or sends it once
    nothing holds it back, unless its signal is cleared first. The bridge runs `retry` when the call in progress ends,
    and at `due`, when the gap that holds the first of them back ends; never on a timer of its own, QUAL-015.
    `call_free` is when the gap between calls lets the next one go, None while a call is in progress."""

    def __init__(self, *, calls: list[str], texts: list[str], place: Callable[[str], bool],
                 send: Callable[[str], Any], clock: Callable[[], float],
                 task_of: Callable[[str], str | None] = lambda work_id: None,
                 call_free: Callable[[], float | None] = lambda: None) -> None:
        self.calls, self.texts = signals_of(calls), signals_of(texts)
        self.place, self.send, self.clock, self.task_of, self.call_free = place, send, clock, task_of, call_free
        self.told: dict[tuple[str, str, str, str], float] = {}   # (act, signal, ticket, session) -> when told
        self.waiting: dict[tuple[str, str, str, str], str] = {}  # the same, held back -> what to say
        self.last_text = float('-inf')

    def heard(self, signal: dict[str, Any]) -> list[str]:
        """Act on one raised signal; the acts done, `call` and `text`, for the log."""
        name = str(signal.get('signal') or '')
        key = (name, str(signal.get('work_id') or ''), str(signal.get('session_id') or ''))
        if not signal.get('active', True):  # cleared: what waited on it no longer needs the person
            for act in ('call', 'text'):
                self.waiting.pop((act, *key), None)
            return []
        acts = [act for act, chosen in (('call', self.calls), ('text', self.texts)) if name in chosen]
        if not acts:
            return []
        now = self.clock()
        reason = why(signal, self.task_of(key[1]) if key[1] else None)
        done: list[str] = []
        for act in acts:
            told = (act, *key)
            if now - self.told.get(told, float('-inf')) < SAME_GAP:
                continue
            if self._act(act, reason, now):
                self.told[told] = now
                self.waiting.pop(told, None)
                done.append(act)
            else:
                self.waiting[told] = reason
        return done

    def retry(self) -> list[str]:
        """Place or send what was held back, if nothing holds it back now; what was done, as `call for <signal>`."""
        done: list[str] = []
        for told, reason in list(self.waiting.items()):
            now = self.clock()
            if self._act(told[0], reason, now):
                self.told[told] = now
                del self.waiting[told]
                done.append(f'{told[0]} for {told[1]}')
        return done

    def due(self) -> float | None:
        """When, by the clock, the first act held back may go: a text once TEXT_GAP has passed since the last, a call
        once the gap between calls has; None when nothing waits, or only calls held back by a call in progress, which
        go when it ends."""
        acts = {told[0] for told in self.waiting}
        times = [self.last_text + TEXT_GAP] if 'text' in acts else []
        free = self.call_free() if 'call' in acts else None
        return min([*times, *([free] if free is not None else [])], default=None)

    def _act(self, act: str, reason: str, now: float) -> bool:
        if act == 'call':
            return bool(self.place(reason))
        if now - self.last_text < TEXT_GAP:
            return False
        self.last_text = now
        self.send(reason)
        return True


def signal_in(payload: dict[str, Any]) -> dict[str, Any] | None:
    found = payload.get('signal')
    return cast(dict[str, Any], found) if isinstance(found, dict) else None
