"""Remove the `:Zone.Identifier` files Windows leaves beside a file copied into WSL.

Windows marks a downloaded file with a `Zone.Identifier` stream; a copy into WSL turns that stream into a file named
`<name>:Zone.Identifier`. A `:` is not allowed in a Windows file name, so git cannot check such a file out on Windows.
`.gitignore` keeps new ones out; this removes the ones already tracked from git and every one on disk.

    uv run python scripts/remove_zone_identifiers.py [FOLDER]   # FOLDER defaults to this repository
"""

import subprocess
import sys
from pathlib import Path

SUFFIX = ':Zone.Identifier'


def main(folder: Path) -> int:
    inside = subprocess.run(['git', '-C', str(folder), 'rev-parse', '--is-inside-work-tree'], capture_output=True,
                            check=False).returncode == 0
    tracked: list[str] = []
    if inside:
        listed = subprocess.run(['git', '-C', str(folder), 'ls-files', '-z'], capture_output=True, check=False)
        if listed.returncode:  # files git still tracks are never deleted under it
            print(f'git could not list the tracked files, so nothing was removed: {listed.stderr.decode().strip()}',
                  file=sys.stderr)
            return 1
        tracked = [name for name in listed.stdout.decode().split('\0') if name.endswith(SUFFIX)]
    if tracked:
        subprocess.run(['git', '-C', str(folder), 'rm', '-q', '--cached', '--', *tracked], check=True)
    removed = 0
    for path in folder.rglob(f'*{SUFFIX}'):
        if '.git' not in path.relative_to(folder).parts and path.is_file():
            path.unlink()
            removed += 1
    print(f'{len(tracked)} untracked from git, {removed} removed from disk')
    return 0


if __name__ == '__main__':
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent)))
