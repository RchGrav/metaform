"""The ledger file: every entry, kept between runs as JSON."""
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast


@dataclass(frozen=True)
class Entry:
    day: str  # yyyy-mm-dd
    category: str
    cents: int


class Ledger:
    def __init__(self, path: Path) -> None:
        self.path = path

    def entries(self) -> list[Entry]:
        if not self.path.exists():
            return []
        rows = cast(list[dict[str, Any]], json.loads(self.path.read_text(encoding='utf-8')))
        return [Entry(day=str(row['day']), category=str(row['category']), cents=int(row['cents'])) for row in rows]

    def append(self, entry: Entry) -> None:
        rows = [asdict(one) for one in [*self.entries(), entry]]
        self.path.write_text(json.dumps(rows, indent=1), encoding='utf-8')
