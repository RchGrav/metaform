"""Create a design's project, then reuse dispatch's authored intake launch."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

from metaform import home, prompt_files
from metaform.data import Store
from metaform.module import Context, Stop


def start(ctx: Context) -> dict[str, Any]:
    from importlib import resources

    from . import intake

    name = re.sub(r'[^a-z0-9]+', '-', str(ctx.nouns['project_name']).lower()).strip('-')[:48].rstrip('-')
    given = ctx.nouns.get('text') or ''
    design = (' '.join(str(word) for word in cast(list[Any], given))
              if isinstance(given, (list, tuple)) else str(given))
    if not name or not design.strip():
        raise Stop('Provide the design and its project name.',
                   'metaform dispatch intake project_name=<name> -- "<complete design>"')
    # mkdir is exclusive: files, folders and dangling symlinks all reserve their names.
    # Registry ids also reserve names, even when registered outside the user's home.
    home.mkdir_private(home.projects_dir())
    with home.file_lock(home.projects_dir() / 'design-intake.lock'):
        number = 1
        while True:
            project = name if number == 1 else f'{name}-{number}'
            folder = Path.home() / project
            if home.project(project) is not None:
                number += 1
                continue
            try:
                folder.mkdir()
            except FileExistsError:
                number += 1
                continue
            try:
                home.add_project(project, folder)
            except Exception:
                # Remove only our empty directory when registration did not persist.
                if home.project(project) is None:
                    folder.rmdir()
                raise
            break
    asked = prompt_files.required(resources.files('metaform.modules.dispatch'), 'design_intake', design=design)
    target = Context('dispatch', folder, project=project, store=Store(project, module='dispatch'),
                     nouns={key: value for key, value in ctx.nouns.items()
                            if key in ('agent', 'wait')},
                     switches={key: value for key, value in ctx.switches.items() if key.startswith('dispatch_')},
                     sink=ctx.sink, surface=ctx.surface, client=ctx.client)
    target.nouns['text'] = asked
    try:
        result = intake(target)
    except (Stop, OSError) as error:
        # Registration is useful even when admission fails. Return its identity so
        # callers retry dispatch intake in this folder instead of creating another.
        result = {'state': 'failed', 'error': str(error),
                  'next': f'Run metaform dispatch intake in {folder} with the same design.'}
    return {**result, 'project': project, 'folder': str(folder)}
