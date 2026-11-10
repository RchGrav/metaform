"""Reads: an addressed read (R-5.10, R-5.21), the raw dump (R-5.34), `map` (R-5.11), `orphaned`
(R-5.23) and the `goto` summary sheet (R-5.30). Ports `reads.rs`.

Reads never change the map, and every element is named by its full address (R-4.12).
"""
from typing import Any

from . import names, refusal, specification
from .model import Map
from .names import ROOT
from .refusal import Refusal
from .values import ascii_lower, copy


def is_definitive(role: Any) -> bool:
    """Role values that mark the Definitive element: `definitive`, R-3.13's name, which the
    intake writes; `DE`, its abbreviation; `defining`, an earlier name of DE in the canonical map."""
    return isinstance(role, str) and ascii_lower(role) in ("de", "defining", "definitive")


def is_project_definitive(address: str, role: Any) -> bool:
    """The project's own Definitive element at an address: a Definitive role on an element inside
    the project (`names.in_project`). An element under `upstream`, `downstream` or `layer` is
    outside the project (R-3.3, R-3.7), so a Definitive role there does not count (R-3.13)."""
    return names.in_project(address) and is_definitive(role)


def read(map: Map, address: str, body: Any) -> dict[str, Any]:
    """`{"<address>": {}}` returns that element's own fields, keyed by its address: the form in
    which data is entered (R-5.10). `{"<address>": {"<layer>": {}, ...}}` adds each named layer
    held there (R-5.21). A named layer the element does not hold comes back empty when it is a
    layer that applies there, and is left out otherwise."""
    named = list(body) if isinstance(body, dict) else []
    element = map.element(address)
    if element is None:
        raise not_found(address)
    fields = element.base_fields()
    for name in named:
        if name == "wants":
            fields["wants"] = element.wants_json()
        elif isinstance(element.fields.get(name), list):
            fields[name] = element.fields[name]
        elif specification.definition_of(map, name) is not None and specification.records_allowed(map, address):
            fields[name] = []
    return {address: copy(fields)}


def not_found(address: str) -> Refusal:
    """A refusal for an address that holds no element. `map` lists the addresses that exist."""
    return Refusal(refusal.NOT_FOUND, f"'{address}' does not exist", {"map": {}})


def raw(map: Map, path: str) -> dict[str, Any]:
    """`{".<path>": {}}` is a raw dump (R-5.34): the stored nested JSON at that path. `{".": {}}`
    dumps the whole project; `{".code.server": {}}` dumps that element and everything beneath
    it. Names are in the agent's form (R-4.11). The result is keyed by the path that was asked
    for. Every layer is included, memory too."""
    value: Any = map.to_tree()
    if path != ROOT:
        for segment in path[1:].split("."):
            if not isinstance(value, dict) or segment not in value:
                raise not_found(path[1:])
            value = value[segment]
    return {path: value}


def shallow(map: Map) -> dict[str, Any]:
    """`{"map": {}}` returns the shallow graph (R-5.11): every address beneath the root, each
    want as an edge from the element that holds it to the element it names, and the one
    Definitive element. No fields and no layers."""
    addresses = [address for address in map.addresses() if address != ROOT]
    edges = [[holder, other] for holder, element in map.elements() for other in sorted(element.wants)]
    definitive = next(
        (address for address, element in map.elements() if is_project_definitive(address, element.fields.get("role"))),
        None,
    )
    return {"addresses": addresses, "edges": edges, "definitive": definitive}


def orphaned(map: Map) -> dict[str, Any]:
    """`{"orphaned": {}}` returns a bare dictionary keyed by address: each named element that
    nothing wants maps to its own fields (R-5.23). Being orphaned does not mean an element should
    go. Layer definitions are left out: nothing wants them, and the server keeps them (R-6.24), so
    listing them would invite a delete that is refused."""
    wanted = map.wanted()
    return {
        address: copy(element.base_fields())
        for address, element in map.elements()
        if address != ROOT
        and not specification.in_layer_scope(address)
        and element.fields
        and address not in wanted
    }


# Fields that are not layers in the summary sheet: `memory` has its own count, and `skills`
# deliver their frontmatter.
NON_LAYER_FIELDS = ("memory", "skills")


def _has(value: Any, key: str) -> bool:
    """Whether serde_json's `Value::get` finds an entry: the value is an object that has the key.
    An entry that holds `null` is found."""
    return isinstance(value, dict) and key in value


def goto(map: Map, address: str) -> dict[str, Any]:
    """`{"goto": "<address>"}` returns the summary sheet for the address (R-5.30): the element's
    own fields and wants, every element that wants it (`wanted_by`) with that element's want,
    each layer held there with its record count, the frontmatter of the skills at the address
    (only when it has some), and its memory count. Counts, not records. Delivering the sheet once
    for each context is the server's job (`tool.Presence`), because it knows the connection."""
    element = map.element(address)
    if element is None:
        raise not_found(address)
    wanted_by = {
        holder: dict(holder_element.wants[address])
        for holder, holder_element in map.elements()
        if holder != address and address in holder_element.wants
    }
    layers: dict[str, Any] = {
        key: {"records": len(value)}
        for key, value in element.fields.items()
        if isinstance(value, list) and key not in NON_LAYER_FIELDS
    }
    # Every defined layer is listed wherever its records are allowed, even with none yet, so the
    # agent sees where records are due once intake has placed the element (R-6.27).
    defined = specification.definitions(map) if specification.records_allowed(map, address) else []
    for definition in defined:
        layers.setdefault(definition.layer, {"records": 0})
    skills: dict[str, Any] = {}
    stored_skills = element.fields.get("skills")
    for skill in stored_skills if isinstance(stored_skills, list) else []:
        front = skill["frontmatter"] if _has(skill, "frontmatter") else skill
        name = front["name"] if _has(front, "name") else None
        if isinstance(name, str):
            entry: dict[str, Any] = {}
            for key in ("name", "description"):
                if key in front:
                    entry[key] = front[key]
            if "uri" in skill:
                entry["uri"] = skill["uri"]
            skills[name] = entry
    memory = element.fields.get("memory")
    sheet: dict[str, Any] = {
        "at": address,
        "element": element.base_fields(),
        "wants": element.wants_json(),
        "wanted_by": wanted_by,
        "layers": layers,
        "memory": {"records": len(memory) if isinstance(memory, list) else 0},
    }
    if skills:
        sheet["skills"] = skills
    # How to write the layers listed here. The server delivers this part once for each context,
    # not once for each address (R-6.27), so each entry says where to read it again (R-5.30).
    if defined:
        sheet["instructions"] = {
            d.layer: f"{d.guidance()}\ngoto {d.address} to see this again." for d in defined
        }
    # At a layer's definition element, the sheet always carries that layer's guidance, so an
    # agent whose context was reset can read it again (R-5.30).
    definition = next((d for d in specification.definitions(map) if d.address == address), None)
    if definition is not None:
        sheet["guidance"] = definition.guidance()
    return copy(sheet)
