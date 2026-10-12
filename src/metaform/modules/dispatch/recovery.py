"""Opt-in crash recovery, MAP-049 and BASE-052. Display liveness never authorizes a release.

Process births and resource ownership live in the session's own row, its private `recovery`, written with the row
when the ticket is taken. Missing evidence, including a session recorded before the column existed, requires manual
recovery.
"""
from __future__ import annotations

import ctypes
import errno
import os
import platform
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from metaform.module import Context

from .signals import own_store


def identity(pid: int) -> str | None:
    """A process birth, '' for a verified absent PID, None when inspection cannot establish either.

    Linux includes the boot ID and start ticks. macOS uses libproc's unique process identifier and boot UUID.
    Windows uses GetProcessTimes' creation FILETIME. A command line alone cannot distinguish reused PIDs.
    """
    if pid <= 0:
        return None
    try:
        if sys.platform.startswith('linux'):
            fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
            boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
            return f'{boot}:{fields[19]}'  # starttime is field 22, after pid and comm
        if sys.platform == 'darwin':
            return _mac_identity(pid)
        if sys.platform == 'win32':
            return _windows_identity(pid)
    except FileNotFoundError:
        # Only the PID's stat file establishes absence, not a missing kernel interface.
        return '' if sys.platform.startswith('linux') and not Path(f'/proc/{pid}').exists() else None
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        pass
    return None


def _mac_identity(pid: int) -> str | None:
    # Apple's proc_uniqidentifierinfo is a 56-byte API structure, with uniqueid at offset 16:
    # https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/proc_info_private.h
    lib = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
    lib.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
    lib.proc_pidinfo.restype = ctypes.c_int
    held = ctypes.create_string_buffer(56)
    if lib.proc_pidinfo(pid, 17, 0, held, len(held)) != len(held):
        return '' if ctypes.get_errno() == errno.ESRCH else None
    boot = subprocess.run(['sysctl', '-n', 'kern.bootsessionuuid'], capture_output=True, text=True,
                          check=True, timeout=2).stdout.strip()
    unique = ctypes.c_uint64.from_buffer(held, 16).value
    return f'{boot}:{unique}' if boot and unique else None


def _windows_identity(pid: int) -> str | None:
    from ctypes import wintypes

    kernel = cast(ctypes.CDLL, getattr(ctypes, 'WinDLL')('kernel32', use_last_error=True))  # noqa: B009
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return '' if getattr(ctypes, 'get_last_error')() == 87 else None  # noqa: B009 -- Windows-only ctypes API
    try:
        code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
            return None
        if code.value != 259:  # STILL_ACTIVE
            return ''
        times = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(item) for item in times)):
            return None
        return str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)
    finally:
        kernel.CloseHandle(handle)


def resources(project: str, work_id: str, session_id: str, adapter_pid: int) -> dict[str, Any]:
    """Evidence acquired before taking the ticket, kept privately in its session row, never in public session reads."""
    return {'project': project, 'work_id': work_id, 'session_id': session_id, 'runner_pid': os.getpid(),
            'runner_identity': identity(os.getpid()), 'adapter_pid': adapter_pid,
            'adapter_identity': identity(adapter_pid)}


def group_members(pid: int) -> list[int]:
    """One snapshot of executable members of a POSIX group. Zombies cannot perform further work."""
    result = subprocess.run(['ps', '-axo', 'pid=,pgid=,stat='], capture_output=True, text=True, check=True, timeout=2)
    found: list[int] = []
    for line in result.stdout.splitlines():
        member, group, state = line.split()
        if int(group) == pid and not state.startswith('Z'):
            found.append(int(member))
    return found


def _pidfd_call(number: int, *args: Any) -> int:
    """Linux syscall fallback for Python builds that omit pidfd APIs, including the installed standalone build.

    These syscall numbers are shared by the x86-64 and arm64 64-bit Linux ABIs. Other ABIs require the Python APIs.
    """
    if platform.machine().lower() not in ('x86_64', 'aarch64') or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise ValueError('safe process-group signalling is unavailable on this Linux ABI')
    try:
        lib = ctypes.CDLL('libc.so.6', use_errno=True)
        call = lib.syscall
    except (OSError, AttributeError) as error:
        raise ValueError('safe process-group signalling is unavailable in this Python build') from error
    call.restype = ctypes.c_long
    call.argtypes = [ctypes.c_long]
    result = int(call(number, *args))
    if result < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return result


def stop_adapter(held: dict[str, Any]) -> None:
    """Stop only the recorded adapter's group. Unknown or reused roots do not authorize killing another process."""
    pid, expected = held.get('adapter_pid'), held.get('adapter_identity')
    if not isinstance(pid, int) or not isinstance(expected, str) or not expected:
        raise ValueError('the adapter identity was not recorded')
    current = identity(pid)
    if current is None or current not in ('', expected):
        raise ValueError('the adapter identity cannot be verified')
    if os.name == 'nt':
        # Numeric taskkill cannot bind descendant cleanup to the birth we inspected.
        raise ValueError('safe process-group signalling is unavailable; Windows descendants need manual cleanup')
    members = group_members(pid)
    if not members:
        return
    if current != expected or os.getpgid(pid) != pid or identity(pid) != expected:
        raise ValueError('the surviving agent group cannot be verified')
    if not sys.platform.startswith('linux'):
        raise ValueError('safe process-group signalling is unavailable; the agent needs manual cleanup')
    # A second birth read alone leaves a race before killpg. A pidfd binds the signal to the inspected process,
    # even if it exits and its numeric PID is recycled before signalling. Group scope requires Linux 6.9.
    fd = os.pidfd_open(pid) if hasattr(os, 'pidfd_open') else _pidfd_call(434, ctypes.c_int(pid), ctypes.c_uint(0))
    try:
        if identity(pid) != expected or os.getpgid(pid) != pid:
            raise ValueError('the surviving agent group cannot be verified')
        if hasattr(signal, 'pidfd_send_signal'):
            signal.pidfd_send_signal(fd, signal.SIGKILL, None, 4)  # PIDFD_SIGNAL_PROCESS_GROUP
        else:
            _pidfd_call(424, ctypes.c_int(fd), ctypes.c_int(signal.SIGKILL), ctypes.c_void_p(), ctypes.c_uint(4))
    except OSError as error:
        if error.errno in (errno.EINVAL, errno.ENOSYS):
            raise ValueError('safe process-group signalling is unavailable; the agent needs manual cleanup') from error
        raise
    finally:
        os.close(fd)
    # A single confirmation, not a poll. If termination has not finished, retain ownership for a later recovery.
    if group_members(pid):
        raise ValueError('the agent group has not finished terminating; run dispatch recover again')


def recover(ctx: Context) -> dict[str, Any]:
    """Apply the configured recovery policy on demand or before Autostart selection, without rewriting reads."""
    from . import intake_id, sessions, ticket

    policy = str(ctx.setting('dispatch_recovery'))
    result: dict[str, Any] = {'policy': policy, 'released': [], 'deferred': []}
    if ctx.store is not None and ctx.setting('dispatch_worktrees'):  # worktrees gone and abandoned branches, P192, P017
        store = ctx.store
        from .merge import abandoned
        try:
            removed = abandoned(store, store.project().path, int(ctx.setting('dispatch_abandoned_branch_days')))
        except (OSError, subprocess.SubprocessError) as error:
            result['deferred'].append({'reason': f'abandoned branches were not cleaned up: {error}'})
        else:
            if removed:
                result['branches_removed'] = removed
    if policy != 'automatic':
        return result
    store = ctx.require_store()
    own = own_store(store)
    for row in sessions(own, verify=False):
        if row['state'] != 'running':
            continue
        work_id = str(row['work_id'])
        if intake_id(work_id):  # an intake agent holds no ticket, so it has none to return
            continue
        owner = f'{row["agent"]} {row["session_id"]}'
        record = ticket(own, work_id)
        if record.done or not record.taken or record.taken_by != owner:
            continue
        try:
            raw: Any = row.get('recovery')  # none on a session recorded before the evidence was kept
            held = cast(dict[str, Any], raw) if isinstance(raw, dict) else {}
            if (held.get('project') != store.project_id or held.get('work_id') != work_id
                    or held.get('session_id') != row['session_id'] or held.get('runner_pid') != row.get('pid')):
                raise ValueError('this session has no verified recovery metadata')
            expected = held.get('runner_identity')
            pid = held.get('runner_pid')
            if not isinstance(expected, str) or not expected or not isinstance(pid, int):
                raise ValueError('the runner identity was not recorded')
            current = identity(pid)
            if current == expected:
                continue
            if current is None:
                raise ValueError('runner death cannot be verified')
            if ticket(own, work_id).taken_by != owner:
                continue
            # Process cleanup never holds the project's write lock. It owns only this session's verified resources.
            # A short final transaction preserves any ownership or session changes made while cleanup ran.
            stop_adapter(held)
            with own.atomic():
                fresh = ticket(own, work_id)
                with own.tables(write=False) as tx:
                    latest = tx.rows('sessions', {'session_id': row['session_id']}, limit=1).results
                if (fresh.done or not fresh.taken or fresh.taken_by != owner or not latest
                        or dict(latest[0]) != row):
                    continue
                own.move_work(work_id, 'todo', fresh.position, 'dispatch recovery')
                with own.tables() as tx:
                    tx.update('sessions', {'session_id': row['session_id']},
                              {'state': 'ended', 'how': 'its verified dead runner was recovered automatically'})
            result['released'].append(work_id)
            from .signals import clear_permissions, publish
            clear_permissions(ctx, row['session_id'])
            publish(ctx, 'not-smooth', work_id=work_id, session_id=row['session_id'],
                    reason='its verified dead runner was recovered automatically')
            publish(ctx, 'requeue', work_id=work_id, session_id=row['session_id'],
                    reason='automatic dead runner recovery')
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            result['deferred'].append({'work_id': work_id, 'reason': str(error),
                                       'next': f'metaform map work op=move id={work_id} column=todo'})
    return result
