"""Write the release's current functional map from a STORE-027 export, BASE-048.

    metaform export metaform=main file=<export.json>
    python -m scripts.release_metaform <export.json> [<snapshot.json>]

This prepares a package resource. It never changes the source home or imports
anything. `metaform map collapse` collapses a working metaform in the home, LAYER-026.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from metaform.data.exchange import collapsed

DESTINATION = Path(__file__).resolve().parents[1] / 'src/metaform/resources/metaform.json'


def snapshot(document: dict[str, Any]) -> dict[str, Any]:
    """The release's current functional map, as a new metaform named `metaform-release`."""
    released = collapsed(document, 'metaform-release', workflow='release-snapshot', role='release builder')
    # The resource travels in every package, and the folder it was exported from belongs to that one machine;
    # import takes the project it is imported into, so the source's place is left empty.
    for entry in released['projects']:
        entry['project'].update(path='', target_value='')
    return released


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export', type=Path, help='STORE-027 export of one project and one metaform.')
    parser.add_argument('output', nargs='?', type=Path, default=DESTINATION,
                        help='Output snapshot, default: src/metaform/resources/metaform.json.')
    args = parser.parse_args()
    released = snapshot(json.loads(args.export.read_text(encoding='utf-8')))
    args.output.write_text(json.dumps(released, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Release snapshot: {args.output}')


if __name__ == '__main__':
    main()
