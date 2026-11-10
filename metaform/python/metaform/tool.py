"""The one Metaform tool, as one connection uses it. Ports the tool part of
`metaform-server/src/tool.rs`.

The tool's name, description and input schema come from the contract,
`metaform/mcp-tools.proposed.json`, read at start. This file adds no tool and changes no schema.
"""
import json
from pathlib import Path
from typing import Any

from .refusal import Refusal
from .store import MapStore, StoreError, refusal_json, store_failure_json
from .values import copy, dumps, same

# The contract, two folders above this package: `metaform/mcp-tools.proposed.json`.
CONTRACT = Path(__file__).resolve().parents[2] / "mcp-tools.proposed.json"

# Sheet parts whose entries are the same wherever they appear, so each entry is delivered once
# for each context: the layer `instructions` (R-6.27).
ONCE_PER_CONTEXT = ("instructions",)

# Sheet parts delivered on every arrival, never held back: a layer's `guidance` at its
# definition element, which is where an agent reads the guidance again after a reset (R-5.30).
ALWAYS = ("guidance",)


def tool_definition() -> dict[str, Any]:
    """The MCP tool from the contract's definition: its name, description and input schema."""
    definition = json.loads(CONTRACT.read_text(encoding="utf-8"))["tools"][0]
    schema = definition.get("inputSchema")
    return {
        "name": definition.get("name") if isinstance(definition.get("name"), str) else "",
        "description": definition.get("description") if isinstance(definition.get("description"), str) else "",
        "inputSchema": schema if isinstance(schema, dict) else {},
    }


class Presence:
    """Where the agent is, and what `goto` already delivered in this context."""

    def __init__(self) -> None:
        self.at: str | None = None
        self.delivered: dict[str, dict[str, Any]] = {}
        self.once: dict[str, Any] = {}

    def arrive(self, sheet: Any) -> Any:
        """Record an arrival and return only the parts of the sheet not yet delivered unchanged
        in this context (R-5.30). The parts held back are named in `unchanged`, so an agent whose
        context was reset can tell "nothing here" from "already delivered" and read them again."""
        if not isinstance(sheet, dict):
            return sheet
        found = sheet.get("at")
        at: str = found if isinstance(found, str) else ""
        seen = self.delivered.setdefault(at, {})
        out: dict[str, Any] = {"at": at}
        unchanged: list[str] = []
        for part, value in sheet.items():
            if part == "at":
                continue
            if part in ALWAYS:
                out[part] = value
                continue
            if part in ONCE_PER_CONTEXT:
                if not isinstance(value, dict):
                    continue
                fresh = {
                    name: text
                    for name, text in value.items()
                    if not (name in self.once and same(self.once[name], text))
                }
                if not fresh:
                    unchanged.append(part)
                else:
                    self.once.update(fresh)
                    out[part] = fresh
                continue
            if part in seen and same(seen[part], value):
                unchanged.append(part)
            else:
                seen[part] = copy(value)
                out[part] = value
        if unchanged:
            out["unchanged"] = unchanged
        self.at = at
        return out


class MapTool:
    """One agent's connection: the map it works on and what `goto` delivered to it. The
    connection stands for the agent and its context (R-5.30, R-8.2)."""

    def __init__(self, store: MapStore) -> None:
        self.store = store
        self.presence = Presence()

    def call(self, command: Any) -> tuple[str, bool]:
        """Perform one command. Returns the answer as compact JSON text, and whether the command
        was refused or failed."""
        try:
            result = self.store.execute(command)
        except Refusal as refused:
            return dumps(refusal_json(command, refused)), True
        except StoreError as error:
            return dumps(store_failure_json(command, error)), True
        if isinstance(command, dict) and "goto" in command:
            result = self.presence.arrive(result)
        return dumps(result), False
