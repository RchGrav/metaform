"""A variation: the work kept as what differs from its origin, PROJ-026.

A variation's folder holds `changes.diff`, a unified diff of the text files that differ; `files/`, a whole copy of
each binary file that differs, since a binary file is never written as a diff; and `removed.txt`, the files the work
no longer has. `expanded` gives the work back, and the scripts beside this file do the same where there is no
Metaform, PROJ-027. A diff applies at the lines it names or not at all.
"""
from __future__ import annotations

import difflib
from collections.abc import Mapping

DIFF, FILES, REMOVED = 'changes.diff', 'files/', 'removed.txt'
MARK = '\\ No newline at end of file'
END = '\0'  # on a last line with no newline after it; text never holds it


class Mismatch(Exception):
    """The origin is not the one the diff was taken from; `path` names the file."""

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self.path = path


def is_text(body: bytes) -> bool:
    if b'\0' in body:
        return False
    try:
        body.decode('utf-8')
    except UnicodeDecodeError:
        return False
    return True


def lines_of(body: bytes) -> list[str]:
    text = body.decode('utf-8')
    if not text:
        return []
    lines = text.split('\n')
    if lines[-1] == '':
        lines.pop()
    else:
        lines[-1] += END
    return lines


def body_of(lines: list[str]) -> bytes:
    return ''.join(line[:-1] if line.endswith(END) else line + '\n' for line in lines).encode('utf-8')


def _shown(prefix: str, line: str) -> list[str]:
    return [prefix + line[:-1], MARK] if line.endswith(END) else [prefix + line]


def _hunks(old: list[str], new: list[str]) -> list[str]:
    out: list[str] = []
    for group in difflib.SequenceMatcher(None, old, new, autojunk=False).get_grouped_opcodes(3):
        (a1, a2), (b1, b2) = (group[0][1], group[-1][2]), (group[0][3], group[-1][4])
        out.append(f'@@ -{a1 + 1 if a2 > a1 else a1},{a2 - a1} +{b1 + 1 if b2 > b1 else b1},{b2 - b1} @@')
        for tag, i1, i2, j1, j2 in group:
            if tag == 'equal':
                out += [shown for line in old[i1:i2] for shown in _shown(' ', line)]
                continue
            out += [shown for line in old[i1:i2] for shown in _shown('-', line)]
            out += [shown for line in new[j1:j2] for shown in _shown('+', line)]
    return out


def variation(origin: Mapping[str, bytes], work: Mapping[str, bytes]) -> dict[str, bytes]:
    """The files of the variation's folder."""
    held: dict[str, bytes] = {}
    diff: list[str] = []
    for path in sorted(work):
        body, before = work[path], origin.get(path)
        if body == before:
            continue
        if not is_text(body):
            held[FILES + path] = body
            continue
        based = before is not None and is_text(before)
        diff += ['--- ' + ('a/' + path if based else '/dev/null'), '+++ b/' + path]
        diff += _hunks(lines_of(before) if based and before is not None else [], lines_of(body))
    held[DIFF] = ''.join(line + '\n' for line in diff).encode('utf-8')
    held[REMOVED] = ''.join(path + '\n' for path in sorted(origin) if path not in work).encode('utf-8')
    return held


def _applied(path: str, old: list[str], hunks: list[tuple[int, int, list[str]]]) -> list[str]:
    out: list[str] = []
    at = 0
    for start, length, lines in hunks:
        to = start - 1 if length else start
        if to < at or to > len(old):
            raise Mismatch(path)
        out += old[at:to]
        at = to
        for line in lines:
            if line[0] == '+':
                out.append(line[1:])
                continue
            if at >= len(old) or old[at] != line[1:]:
                raise Mismatch(path)
            if line[0] == ' ':
                out.append(old[at])
            at += 1
    return out + old[at:]


def expanded(origin: Mapping[str, bytes], held: Mapping[str, bytes]) -> dict[str, bytes]:
    """The work the variation stands for."""
    work = dict(origin)
    lines = held.get(DIFF, b'').decode('utf-8').split('\n')
    at = 0
    while at < len(lines):
        if not lines[at].startswith('--- ') or at + 1 >= len(lines) or not lines[at + 1].startswith('+++ b/'):
            at += 1
            continue
        based, path = lines[at][4:] != '/dev/null', lines[at + 1][6:]
        at += 2
        hunks: list[tuple[int, int, list[str]]] = []
        while at < len(lines) and lines[at].startswith('@@ -'):
            old_part, new_part = lines[at].split(' ')[1:3]
            start, comma, length = old_part[1:].partition(',')
            need_old = int(length) if comma else 1
            counted = new_part[1:].partition(',')
            need_new = int(counted[2]) if counted[1] else 1
            size = need_old
            at += 1
            part: list[str] = []
            while need_old or need_new or (at < len(lines) and lines[at] == MARK):
                line = lines[at]
                at += 1
                if line == MARK:
                    part[-1] += END
                    continue
                need_old -= line[0] in ' -'
                need_new -= line[0] in ' +'
                part.append(line)
            hunks.append((int(start), size, part))
        if based and path not in origin:
            raise Mismatch(path)
        work[path] = body_of(_applied(path, lines_of(origin[path]) if based else [], hunks))
    for name, whole in held.items():
        if name.startswith(FILES):
            work[name[len(FILES):]] = whole
    for path in held.get(REMOVED, b'').decode('utf-8').split('\n'):
        work.pop(path, None)
    return work
