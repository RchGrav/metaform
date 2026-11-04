"""The end of a session of roundtables: its folder zipped beside it and both pushed, as one commit on a branch of
their own, `roundtables/<session>`, so no branch anyone works on moves."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from metaform.module import Stop


def pushed(root: Path, session: Path) -> str:
    """The session's folder zipped beside it, both committed on a branch of their own and pushed; the branch. The
    commit is made with a temporary index, so the project's checkout and branch are left as they are."""
    archive = shutil.make_archive(str(session), 'zip', root_dir=session.parent, base_dir=session.name)
    branch = f'roundtables/{session.name}'
    paths = [str(session.relative_to(root)), str(Path(archive).relative_to(root))]
    with tempfile.TemporaryDirectory() as scratch:
        env = {**os.environ, 'GIT_INDEX_FILE': str(Path(scratch) / 'index')}

        def git(*args: str) -> str:
            done = subprocess.run(['git', *args], cwd=root, env=env, capture_output=True, text=True, timeout=300,
                                  check=False)
            if done.returncode != 0:
                raise Stop(f'git {args[0]} failed for the planning session: {done.stderr.strip() or done.stdout}',
                           f'git -C {root} status')
            return done.stdout.strip()
        git('read-tree', 'HEAD')
        git('add', '-f', '--', *paths)
        tree = git('write-tree')
        commit = git('commit-tree', tree, '-p', 'HEAD', '-m', f'Planning session {session.name}: every table\'s '
                     'summary, notes and record, and the session zipped')
        git('push', 'origin', f'{commit}:refs/heads/{branch}')
    return branch
