"""Entries: one logical event made of the physical lines that belong to it, whether it is captured, its example with
secrets masked, and the file and function its trace names."""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

QUIET_SECONDS = 2.0  # an open entry is closed after this long with no new line, so the last one is never held back
MAX_LINES = 400  # lines joined into one entry; past it the entry is closed, so a runaway trace cannot grow without end
EXAMPLE_CHARS = 4000  # the most of an example kept: enough for a long traceback's head and its last line

# A new record starts at column zero with a timestamp or a level prefix.
RECORD_START = re.compile(
    r'\[?\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}'  # 2026-10-15 10:00, 2026-10-15T10:00, [2026-10-15 10:00
    r'|\[?\d{4}/\d{2}/\d{2} \d{2}:\d{2}'  # 2026/10/15 10:00
    r'|[A-Z][a-z]{2} [ \d]\d \d{2}:\d{2}:\d{2}'  # syslog, Oct 15 10:00:00
    r'|\[?\d{2}:\d{2}:\d{2}'  # 10:00:00
    r'|\d{10}(?:\.\d+)?\s'  # epoch seconds
    r'|\[?(?:TRACE|DEBUG|INFO|NOTICE|WARN|WARNING|ERROR|ERR|FATAL|CRITICAL|SEVERE|PANIC)\b'
    r'|[IWEF]\d{4} \d{2}:\d{2}'  # glog, E1015 10:00
    r'|(?:time|ts|level)=')  # logfmt
TRACEBACK = 'Traceback (most recent call last):'
# Lines at column zero that still belong to a stack trace: Java's causes, Python's chained exceptions.
TRACE_CONTINUES = re.compile(r'Caused by:|Suppressed:|\.\.\. \d+ more|During handling of the above exception|'
                             r'The above exception was the direct cause|' + re.escape(TRACEBACK))
# What counts as an error with autoticket_capture at errors: level words and the start of a trace.
ERRORS = re.compile(r'\b(?:ERROR|FATAL|CRITICAL|SEVERE|PANIC)\b|Traceback \(most recent call last\)|Exception\b|'
                          r'\blevel=(?:error|fatal|critical)\b')


@dataclass
class Entry:
    """One logical event: its lines, and the byte offset its first line starts at in the log, so a reader that takes
    the log over resumes at the start of an entry not yet counted."""
    lines: list[str] = field(default_factory=list[str])
    start: int = 0
    last: float = 0.0

    @property
    def text(self) -> str:
        return '\n'.join(self.lines)


class Assembler:
    """Joins lines into entries, up to the next line that starts a new record. A line at column zero starts a new
    entry unless it carries on a stack trace; an indented or empty line carries on the entry open."""

    def __init__(self) -> None:
        self.open: Entry | None = None
        self.in_trace = False

    def feed(self, line: str, start: int, now: float) -> list[Entry]:
        """Take one line, which began at byte `start`; returns the entries this line closed."""
        closed: list[Entry] = []
        if self.open is not None and not self._continues(line):
            closed.append(self._close())
        if self.open is None:
            self.open = Entry(start=start)
            self.in_trace = False
        self.open.lines.append(line)
        self.open.last = now
        if line.lstrip().startswith(TRACEBACK):
            self.in_trace = True
        elif self.in_trace and line and not line[:1].isspace() and not TRACE_CONTINUES.match(line):
            self.in_trace = False  # the exception's own line, such as `ValueError: bad`, ends a Python traceback
        if len(self.open.lines) >= MAX_LINES:
            closed.append(self._close())
        return closed

    def _continues(self, line: str) -> bool:
        """Whether a line belongs to the entry open: an indented or empty line, a line carrying on a stack trace, and
        inside a Python traceback the exception's own line; never a line that starts a new record."""
        if not line or line[:1].isspace():
            return True
        if RECORD_START.match(line):
            return False
        return self.in_trace or bool(TRACE_CONTINUES.match(line))

    def _close(self) -> Entry:
        entry = self.open
        assert entry is not None
        self.open = None
        self.in_trace = False
        return entry

    def idle(self, now: float) -> list[Entry]:
        """The open entry, closed once it has been quiet for QUIET_SECONDS."""
        if self.open is not None and now - self.open.last >= QUIET_SECONDS:
            return [self._close()]
        return []

    def flush(self) -> list[Entry]:
        return [self._close()] if self.open is not None else []

    @property
    def pending_start(self) -> int | None:
        """Where the open entry starts in the log, or None when none is open."""
        return None if self.open is None else self.open.start


def captured(entry: str, mode: str, rules: Sequence[re.Pattern[str]]) -> bool:
    """Whether an entry counts: any of its lines matches a capture rule, and with mode errors the level words."""
    if mode == 'errors' and ERRORS.search(entry):
        return True
    return any(rule.search(entry) for rule in rules)


# ------------------------------------------------------------------------------------------------ secrets

MASK = '****'
SECRET_SHAPES = (
    re.compile(r'\b(?:sk|pk|rk)-[A-Za-z0-9_-]{12,}'),  # OpenAI, Anthropic, OpenRouter and Stripe keys
    re.compile(r'\bgh[pousr]_[A-Za-z0-9]{20,}'),  # GitHub tokens
    re.compile(r'\bgithub_pat_[A-Za-z0-9_]{20,}'),
    re.compile(r'\bglpat-[A-Za-z0-9_-]{20,}'),  # GitLab tokens
    re.compile(r'\bxox[abprs]-[A-Za-z0-9-]{10,}'),  # Slack tokens
    re.compile(r'\bAKIA[0-9A-Z]{16}\b'),  # AWS access keys
    re.compile(r'\bAIza[0-9A-Za-z_-]{30,}'),  # Google API keys
    re.compile(r'\beyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{8,}'),  # JSON web tokens
)
SECRET_NAME = re.compile(r'api[_-]?key|access[_-]?key|private[_-]?key|secret|token|passw|pwd|credential|cookie|'
                         r'authorization|auth[_-]|nonce|_sid\b|^key$', re.IGNORECASE)
NAMED_SECRET = re.compile(r'(?P<name>[\w.-]*(?:api[_-]?key|access[_-]?key|private[_-]?key|secret|token|passw|pwd|'
                          r'credential|cookie|authorization|auth[_-]|nonce|_sid)[\w.-]*)'
                          r'(?P<between>["\']?\s*[:=]\s*["\']?(?:Bearer\s+|Basic\s+)?)'
                          r'(?P<value>[^\s"\'&,;<>]{4,})', re.IGNORECASE)
BEARER = re.compile(r'(?P<between>\b(?:Bearer|Basic)\s+)(?P<value>[A-Za-z0-9._~+/=-]{8,})')
URL_PASSWORD = re.compile(r'(?P<before>[a-z][a-z0-9+.-]*://[^\s:/@]+:)(?P<value>[^\s@/]+)(?=@)', re.IGNORECASE)


def mask(text: str, secrets: Iterable[str] = ()) -> str:
    """The text with every secret it holds replaced by ****: the values named, those of a known shape, those written
    beside a name that says secret, bearer values and the password in a URL."""
    for secret in sorted(set(secrets), key=len, reverse=True):
        text = text.replace(secret, MASK)
    for pattern in SECRET_SHAPES:
        text = pattern.sub(MASK, text)
    text = NAMED_SECRET.sub(lambda found: found['name'] + found['between'] + MASK, text)
    text = BEARER.sub(lambda found: found['between'] + MASK, text)
    return URL_PASSWORD.sub(lambda found: found['before'] + MASK, text)


def example(entry: str, secrets: Iterable[str] = ()) -> str:
    """The example kept for a group: the entry masked, cut to EXAMPLE_CHARS keeping its head and its last line."""
    text = mask(entry, secrets)
    if len(text) <= EXAMPLE_CHARS:
        return text
    last = text.rsplit('\n', 1)[-1][-500:]
    return text[:EXAMPLE_CHARS - len(last) - 5] + '\n...\n' + last


# ------------------------------------------------------------------------------------------------ where it happened

PYTHON_FRAME = re.compile(r'File "(?P<file>[^"]+)", line \d+, in (?P<function>[\w<>.]+)')
JAVA_FRAME = re.compile(r'\bat (?P<qn>[\w$.]+)\.(?P<function>[\w$<>]+)\((?P<file>[\w$.-]+\.\w+):\d+\)')
JS_FRAME = re.compile(r'\bat (?:(?P<function>[\w$.<>]+) \()?(?:file://)?(?P<file>[^\s()]+?\.[cm]?[jt]sx?):\d+:\d+\)?')
GENERIC = re.compile(r'(?P<file>[\w./\\-]+\.(?:py|js|mjs|cjs|ts|tsx|jsx|go|rs|rb|java|kt|cs|cpp|cc|c|h|php|swift))'
                     r'(?::\d+)?(?:[: ]+in )?(?P<function>\w+)?')


def location(entry: str) -> tuple[str, str | None] | None:
    """The file and function an entry names: the innermost frame of its trace, the last one written, else the first
    source file it mentions; None when it names none."""
    frames = [(found['file'], found['function']) for found in PYTHON_FRAME.finditer(entry)]
    if frames:
        return frames[-1]
    found = JAVA_FRAME.search(entry)  # Java writes the innermost frame first
    if found is not None:  # com.example.Shop.pay(Shop.java:9): the package's folders, then the file
        return '/'.join([*found['qn'].split('.')[:-1], found['file']]), found['function']
    found = JS_FRAME.search(entry)
    if found is not None:
        return found['file'], found['function']
    found = GENERIC.search(entry)
    if found is not None:
        return found['file'], found['function']
    return None
