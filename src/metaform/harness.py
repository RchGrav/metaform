"""The harnesses Metaform knows, MCP-028.

A harness is known by the parent folder of its binary, since its path may carry its version and some harnesses run
from an install folder of their own; a binary under the system's temporary folder is ignored. Once the agent says
it is done provisioning a harness, the home records it, and it is never asked again. Under a harness not
recorded, every command gives the notice on stderr, D96.
"""
from __future__ import annotations

import ctypes
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import cast

from . import home

# A home made before this table existed is given it on the first harness recorded, as with the nonces, BASE-050.
HARNESSES = """CREATE TABLE IF NOT EXISTS harnesses(
  path_key TEXT PRIMARY KEY,
  binary   TEXT NOT NULL,
  done     TEXT NOT NULL
);
"""

FIRST_RUN = "This is Metaform's first run here. "
NOTICE = (FIRST_RUN + 'Read metaform help provision for each feature, MCP registration, skill and hooks, then run '
          'metaform provision done.')


def running() -> Path | None:
    """Walk past shells, launchers and command wrappers to the first other parent program."""
    pid = os.getppid()
    seen: set[int] = set()
    shells = {'sh', 'bash', 'dash', 'zsh', 'fish', 'ksh', 'csh', 'tcsh', 'ash', 'cmd', 'powershell', 'pwsh', 'nu'}
    wrappers = shells | {'uv', 'uvx', 'timeout', 'nice', 'env', 'xargs', 'nohup'}
    while pid > 0 and pid not in seen:
        seen.add(pid)
        process = _process(pid)
        if process is None:
            return None
        parent, binary = process
        name = binary.name.lower().removesuffix('.exe')
        if name == 'busybox' and sys.platform == 'linux':
            try:
                arguments = (Path('/proc') / str(pid) / 'cmdline').read_bytes().split(b'\0')
            except OSError:
                return None
            applet = Path(os.fsdecode(arguments[0])).name
            if applet == 'busybox' and len(arguments) > 1:
                applet = os.fsdecode(arguments[1])
            if applet.removeprefix('-') in wrappers:
                name = applet.removeprefix('-')
        if name not in wrappers and not re.fullmatch(r'(pythonw?|pypy)(\d+(\.\d+)*)?', name):
            return binary
        pid = parent
    return None


def _process(pid: int) -> tuple[int, Path] | None:
    """A process's parent and full executable path; an exited or inaccessible process cannot be identified."""
    try:
        if sys.platform == 'win32':
            return _windows_process(pid)
        if sys.platform == 'darwin':
            library = ctypes.CDLL('/usr/lib/libproc.dylib')
            library.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p,
                                            ctypes.c_int]
            library.proc_pidinfo.restype = ctypes.c_int
            library.proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
            library.proc_pidpath.restype = ctypes.c_int
            # proc_bsdshortinfo is 64 bytes, with its parent PID in the second uint32 field, Apple's proc_info.h.
            info = (ctypes.c_uint32 * 16)()
            if library.proc_pidinfo(pid, 13, 0, info, ctypes.sizeof(info)) != ctypes.sizeof(info):
                return None
            path = ctypes.create_string_buffer(4096)  # PROC_PIDPATHINFO_MAXSIZE
            if library.proc_pidpath(pid, path, len(path)) <= 0:
                return None
            return info[1], Path(os.fsdecode(path.value))
        process = Path('/proc') / str(pid)
        # The comm field is parenthesized and may contain spaces or parentheses; ppid follows state.
        parent = int((process / 'stat').read_text().rsplit(')', 1)[1].split()[1])
        return parent, (process / 'exe').readlink()
    except (OSError, ValueError, IndexError):
        return None


def _windows_process(pid: int) -> tuple[int, Path] | None:
    """Read the parent from a Tool Help snapshot and the binary through its process handle."""
    from ctypes import wintypes

    class Entry(ctypes.Structure):
        _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD), ('th32ProcessID', wintypes.DWORD),
                    ('th32DefaultHeapID', ctypes.c_size_t), ('th32ModuleID', wintypes.DWORD),
                    ('cntThreads', wintypes.DWORD), ('th32ParentProcessID', wintypes.DWORD),
                    ('pcPriClassBase', wintypes.LONG), ('dwFlags', wintypes.DWORD), ('szExeFile', wintypes.WCHAR * 260)]

    # WinDLL is present only on Windows; its CDLL base carries the shared ctypes interface for type checking.
    library = cast(ctypes.CDLL, getattr(ctypes, 'WinDLL')('kernel32', use_last_error=True))  # noqa: B009 -- WinDLL exists only on Windows.
    library.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    library.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    for function in (library.Process32FirstW, library.Process32NextW):
        function.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
        function.restype = wintypes.BOOL
    library.CloseHandle.argtypes = [wintypes.HANDLE]
    library.CloseHandle.restype = wintypes.BOOL
    library.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    library.OpenProcess.restype = wintypes.HANDLE
    library.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                 ctypes.POINTER(wintypes.DWORD)]
    library.QueryFullProcessImageNameW.restype = wintypes.BOOL
    snapshot = library.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS
    if snapshot == ctypes.c_void_p(-1).value:
        return None
    parent: int | None = None
    try:
        entry = Entry()
        entry.dwSize = ctypes.sizeof(entry)
        more = library.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            if entry.th32ProcessID == pid:
                parent = int(entry.th32ParentProcessID)
                break
            more = library.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        library.CloseHandle(snapshot)
    if parent is None:
        return None
    handle = library.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        path = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(path))
        if not library.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
            return None
        return parent, Path(path.value)
    finally:
        library.CloseHandle(handle)


def notice() -> str | None:
    """The first-run notice, when the running harness is one the home has not recorded. It never says this is
    Metaform's first run when an intake exists."""
    binary = running()
    if binary is None or key(binary) is None or known(binary):
        return None
    return NOTICE.removeprefix(FIRST_RUN) if home.intake_exists() else NOTICE


def key(binary: Path | str) -> str | None:
    """The harness a binary belongs to: the parent folder of the binary a link points to, or None under the
    temporary folder."""
    folder = Path(home.path_key(Path(binary).expanduser().resolve().parent))
    temporary = Path(home.path_key(tempfile.gettempdir()))
    if folder == temporary or temporary in folder.parents:
        return None
    return str(folder)


def known(binary: Path | str) -> bool:
    """Whether the agent has said it is done provisioning this binary's harness."""
    found = key(binary)
    if found is None or not home.chassis_path().exists():
        return False
    with home.chassis() as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='harnesses'").fetchone():
            return False
        return db.execute('SELECT 1 FROM harnesses WHERE path_key=?', (found,)).fetchone() is not None


def done(binary: Path | str) -> None:
    """Record that provisioning this binary's harness is done. An ignored binary records nothing."""
    found = key(binary)
    if found is None:
        return
    with home.chassis(write=True) as db:
        db.execute(HARNESSES)
        db.execute('INSERT INTO harnesses(path_key, binary, done) VALUES (?, ?, ?) '
                   'ON CONFLICT(path_key) DO UPDATE SET binary=excluded.binary, done=excluded.done',
                   (found, str(binary), home.now()))
