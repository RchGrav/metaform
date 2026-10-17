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
    """Stop only the recorded adapter's group, and the group of each terminal the runner recorded for the session.
    Unknown or reused roots do not authorize killing another process."""
    pid, expected = held.get('adapter_pid'), held.get('adapter_identity')
    if not isinstance(pid, int) or not isinstance(expected, str) or not expected:
        raise ValueError('the adapter identity was not recorded')
    current = identity(pid)
    if current is None or current not in ('', expected):
        raise ValueError('the adapter identity cannot be verified')
    stop_group(pid, expected)
    stop_terminals(held)


def stop_terminals(held: dict[str, Any]) -> None:
    """Stop the group of each terminal the runner recorded for the session; one whose pid holds another birth is
    gone already."""
    raw: Any = held.get('terminals') or []
    for terminal in cast(list[Any], raw) if isinstance(raw, list) else []:
        one = cast(dict[str, Any], terminal) if isinstance(terminal, dict) else {}
        if isinstance(one.get('pid'), int) and isinstance(one.get('identity'), str) and one['identity']:
            stop_group(int(one['pid']), str(one['identity']))


def swept(held: dict[str, Any]) -> None:
    """What a runner verifiably dead left running is stopped: its agent's group, its leader alive or ended, and its
    terminals'. An agent pid that holds another birth, as every pid does after the machine restarts, means its group
    is gone, since a group's id is not reused while it has members; one that cannot be inspected raises."""
    pid, expected = held.get('adapter_pid'), held.get('adapter_identity')
    if not isinstance(pid, int) or not isinstance(expected, str) or not expected:
        raise ValueError('the adapter identity was not recorded')
    stop_group(pid, expected)
    stop_terminals(held)


def stop_group(pid: int, expected: str) -> None:
    """Stop the process group whose leader was born `expected`. A leader that has ended leaves its group to be ended by
    its id: the kernel gives no new process that id while the group has members, so the group is still the recorded
    one. A pid that holds another birth means the recorded group is gone, since its id was free to be reused. UX
    review round 1, 2026-10-17 (interrupt-failure-recovery F3, dispatch-concurrency F6): an agent whose leader exited
    when its runner died left its children, builds, servers and test runs, running for good."""
    current = identity(pid)
    if current is None:
        raise ValueError('the agent identity cannot be verified')
    if current not in ('', expected):
        return
    if os.name == 'nt':
        if current == '':  # Windows keeps no group by the leader's id once it has ended
            return
        # Numeric taskkill cannot bind descendant cleanup to the birth we inspected.
        raise ValueError('safe process-group signalling is unavailable; Windows descendants need manual cleanup')
    members = group_members(pid)
    if not members:
        return
    if current == '':  # the leader is gone and its group lives on
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        if group_members(pid):  # a single confirmation, not a poll
            raise ValueError('the agent group has not finished terminating; run dispatch recover again')
        return
    if os.getpgid(pid) != pid or identity(pid) != expected:
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
    from . import base_store, foreign, held_ticket, sessions, ticket

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
    for row in sessions(own_store(store), verify=False):
        if row['state'] != 'running':
            continue
        # its ticket is in the metaform its runner was pinned to, whichever is active now (UX review round 2,
        # 2026-10-17, project-scope F7)
        own = base_store(own_store(store), row)
        work_id = str(row['work_id'])
        # an intake agent or a conversation on no map holds no ticket, and one a cleared map took has none to return
        record = held_ticket(own, work_id)
        if record is None:
            continue
        owner = f'{row["agent"]} {row["session_id"]}'
        if record.done or not record.taken or record.taken_by != owner:
            continue
        try:
            if foreign(row):  # its processes are another home's, in a store copied here: never stopped or released
                raise ValueError('another Metaform home started this session')
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
                    latest = tx.rows('agent_sessions', {'session_id': row['session_id']}, limit=1).results
                if (fresh.done or not fresh.taken or fresh.taken_by != owner or not latest
                        or dict(latest[0]) != row):
                    continue
                from .progress import finish
                finish(own, work_id, str(row.get('runner') or ''), 'its verified dead runner was recovered automatically')
                own.move_work(work_id, 'todo', fresh.position, 'dispatch recovery')
                with own.tables() as tx:
                    tx.update('agent_sessions', {'session_id': row['session_id']},
                              {'state': 'ended', 'how': 'its verified dead runner was recovered automatically'})
            result['released'].append(work_id)
            from .progress import refresh
            refresh(ctx, own, ticket(own, work_id))
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


def gone(held: dict[str, Any]) -> bool:
    """Whether a session's runner and its agent are verifiably no longer running, from the births recorded when its
    ticket was taken: the runner's PID is absent or holds another process's birth, as after a crash or a restart of
    the machine, and the agent's group, whatever of it survived with its leader alive or gone, and each terminal's the
    runner recorded, are stopped here, `swept`. False when any of it cannot be established: a missing record or
    an uninspectable process is never taken for death."""
    runner, born = held.get('runner_pid'), held.get('runner_identity')
    if not isinstance(runner, int) or not isinstance(born, str) or not born:
        return False
    now = identity(runner)
    if now is None or now == born:
        return False
    adapter, adapter_born = held.get('adapter_pid'), held.get('adapter_identity')
    if not isinstance(adapter, int) or not isinstance(adapter_born, str) or not adapter_born:
        return False
    try:  # the runner died: what it left of its agent and terminals is stopped first, or the session waits
        swept(held)
    except (OSError, ValueError, subprocess.SubprocessError):
        return False
    return True


DEAD = 'the runner is no longer running'  # one of dispatch's DIED: an end the supervisor resumes, never the person's


def settle(ctx: Context) -> list[str]:
    """The store's sessions checked against the truth, before the supervisor looks, whatever dispatch_recovery says: a
    session the store holds as running whose runner and agent are verifiably gone, `gone`, is written as ended, its
    runner died, so the supervisor, `retry`, resumes it in place with its memory, up to dispatch_retries, and then
    hands it to the person. The store's row was the only word the supervisor read, and a runner killed with the
    machine, as by a crash of WSL, never wrote its end, so its ticket stayed taken by a session no one would resume
    and held an agent slot for good (2026-10-15, not the first time). Returns the sessions settled."""
    from . import foreign, sessions

    own = own_store(ctx.require_store())
    settled: list[str] = []
    for row in sessions(own, verify=False):
        if row['state'] != 'running' or row.get('origin') and foreign(row):
            continue
        raw: Any = row.get('recovery')
        held = cast(dict[str, Any], raw) if isinstance(raw, dict) else {}
        if held.get('session_id') != row['session_id'] or held.get('runner_pid') != row.get('pid') or not gone(held):
            continue
        with own.atomic():  # written only if the row is as it was read: a runner that took it up meanwhile keeps it
            with own.tables(write=False) as tx:
                latest = tx.rows('agent_sessions', {'session_id': row['session_id']}, limit=1).results
            if not latest or dict(latest[0]) != row:
                continue
            with own.tables() as tx:
                tx.update('agent_sessions', {'session_id': row['session_id']}, {'state': 'ended', 'how': DEAD})
        settled.append(str(row['session_id']))
        # the board shows the crash and what comes of it, UX review round 1, 2026-10-17 (interrupt-failure-recovery
        # F5): settle published nothing, so a dead runner's resume came unannounced
        from .signals import publish
        publish(ctx, 'not-smooth', work_id=str(row['work_id']), session_id=str(row['session_id']),
                key=str(row['session_id']),
                reason='its runner died; while Autostart agents is checked it resumes in place once its wait is over '
                       'and an agent slot is free')
    return settled
