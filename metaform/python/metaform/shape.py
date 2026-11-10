"""The shape of a command, checked by hand (R-5.24). Ports `shape.rs` line for line.

`check` refuses a command that does not have the form the `project-map` tool takes. It reads
only the command, never the map. Each message names a place the way an agent writes it:
`'code.engine.game'`, `status at 'code.engine.game'`, `the want 'code.bus.data.event' at
'code.engine.game'`. Nothing here depends on a schema validator.

# Order of checks

A command can have several problems. `check` reports the first one it finds, in this order:

1. The number of entries: a command is an object with one entry.
2. The command name: `add`, `update`, `delete`, `orphaned`, `goto` and `map` are commands. A
   key that starts with a period is a raw dump. Any other key is an address to read.
3. The address. For `add`, `update` and `delete` the body must first be an object with one
   entry, because that entry's key is the address.
4. The shape of the value at the address.
5. Each field, in the order the command gives them. An object value is an element beneath;
   its fields are checked, in order, before the next field of the element above.

In a want record the order is: the record is an object, the names it does not take, each field
in the command's order, then the fields that are missing. In `delete`, the items of `wants` are
checked in the command's order; for each item: it is text, it is not the root, it is an
address, it is not a repeat.

The inventory of rules (C1 to W8) is in the module text of `shape.rs`.
"""
from typing import Any

from . import names, refusal
from .names import ROOT
from .refusal import Refusal
from .values import copy, is_blank, is_space

ONE_ENTRY = "a command has one entry: add, update, delete, orphaned, goto, map, an address to read, or a path that starts with a period for a raw dump"
DELETE_FORM = 'delete takes {} to delete the element, or {"wants": ["<address>"]} to remove wants'
# The fields that hold text (N2 to N5).
TEXT_FIELDS = ("technical_name", "name", "role", "status", "project", "uri")
# The words that belong to a want, not to an element (N6). `op`, `ef` and `ifd` are older names.
WANT_WORDS = ("why", "how", "direction", "op", "ef", "ifd")
WANT_FIELDS = ("why", "how", "direction")
DIRECTIONS = ("inbound", "outbound", "two-way")
LEGACY_STATUS = ("missing", "MISSING", "BKN", "broken", "todo", "TODO")

# Where a set of fields sits in the command: the fields of the element that `add` names, the
# fields of the element that `update` names, or the fields of an element beneath, written as an
# object value.
ADD, UPDATE, BENEATH = "add", "update", "beneath"


def check(command: Any) -> None:
    """Refuse a command that does not have the form the tool takes. See the module text for the
    order."""
    entry = one_entry(command)
    if entry is None:
        raise refuse(ONE_ENTRY)
    key, body = entry
    if key in ("map", "orphaned"):
        if is_empty_object(body):
            return
        raise refuse(f"{key} takes {{}}", {key: {}})
    if key == "goto":
        if isinstance(body, str) and (body == ROOT or is_address(body)):
            return
        if isinstance(body, str) and body != "":
            raise not_an_address(body)
        raise refuse('goto takes one address, such as {"goto": "code.engine.game"}', {"goto": "<address>"})
    if key in ("add", "update", "delete"):
        inner = one_entry(body)
        if inner is None:
            first = next(iter(body.items()), None) if isinstance(body, dict) else None
            raise refuse(
                f"{key} takes one address; send one command for each element",
                None if first is None else accepted({key: {first[0]: first[1]}}),
            )
        address, value = inner
        if key == "delete":
            delete(address, value)
            return
        if address != ROOT and not is_address(address):
            raise not_an_address(address)
        if not isinstance(value, dict):
            raise refuse(f"{key} takes an object of fields at '{address}'")
        if not value:
            raise refuse(f"{key} needs at least one field at '{address}'")
        Check(command).fields(value, address, [key, address], ADD if key == "add" else UPDATE)
        return
    if key.startswith("."):
        if key != ROOT and not is_address(key[1:]):
            raise not_an_address(key)
        if not is_empty_object(body):
            raise refuse("a raw dump takes {}", {key: {}})
        return
    read(key, body)


class Check:
    """The command being checked. A remediation is this command with one value corrected."""

    def __init__(self, command: Any) -> None:
        self.command = command

    def fields(self, fields: dict[str, Any], address: str, path: list[str], level: str) -> None:
        """The fields of one element (N1 to N10). `path` is the keys from the command to these
        fields."""
        for key, value in fields.items():
            if not is_segment(key):
                raise refuse(
                    f"'{key}' at '{address}' is not a field name: a name is one segment, with no periods, spaces, '$', '[' or ']'"
                )
            here = path + [key]
            if key == "wants":
                self.wants(value, address, here, level)
                continue
            if isinstance(value, dict):
                self.fields(value, names.join(address, key), here, BENEATH)
            elif value is None and level == UPDATE:
                pass
            elif isinstance(value, list) and key != "uri" and key != "providers":
                pass
            elif key in TEXT_FIELDS:
                self.text(key, value, address, here)
            elif key in WANT_WORDS:
                record = want_placeholder()
                if key in WANT_FIELDS and isinstance(value, str):
                    record[key] = value
                raise refuse(
                    f"{key} at '{address}' is not a field of an element; why, how and direction belong in a want",
                    {"update": {address: {"wants": {"<address>": record}}}},
                )
            elif key == "providers":
                raise refuse(
                    f"providers at '{address}' can hold only elements beneath it; wants holds what an element wants"
                )

    def text(self, key: str, value: Any, address: str, path: list[str]) -> None:
        """A value that is not an object, a list or an accepted `null`, at a field that holds
        text."""
        if isinstance(value, str) and not is_blank(value):
            if key == "status" and value in LEGACY_STATUS:
                raise refuse(
                    f"status at '{address}' cannot be \"{value}\"; use un_built for functionality that is not built",
                    accepted(replaced(self.command, path, "un_built")),
                )
            return
        placeholder = "<Definitive, Supportive, Notable or Divergent>" if key == "role" else f"<{key}>"
        raise refuse(
            f"{key} at '{address}' must be text that is not blank",
            replaced(self.command, path, placeholder),
        )

    def wants(self, value: Any, holder: str, path: list[str], level: str) -> None:
        """The value of `wants` at an element (W1, N10)."""
        if not isinstance(value, dict):
            raise refuse(
                f"wants at '{holder}' must be an object of want records keyed by address",
                replaced(self.command, path, {"<address>": want_placeholder()}),
            )
        # Beneath the command's own element, `wants` may also be a branch of elements. It holds
        # want records when a value in it gives why, how or direction as a plain value.
        holds_records = any(
            isinstance(record, dict) and field in record and not isinstance(record[field], (dict, list))
            for record in value.values()
            for field in WANT_FIELDS
        )
        if level == BENEATH and not holds_records:
            self.fields(value, names.join(holder, "wants"), path, BENEATH)
            return
        if not value:
            # W8: an empty `wants` would be read as an element named "wants" beneath the holder.
            raise refuse(
                f"wants at '{holder}' holds no want record",
                replaced(self.command, path, {"<address>": want_placeholder()}),
            )
        for other, record in value.items():
            if other == ROOT:
                raise refuse("the root cannot be wanted")
            if not is_address(other):
                raise not_an_address(other)
            self.want(record, other, holder, path + [other], level == UPDATE)

    def want(self, record: Any, other: str, holder: str, path: list[str], partial: bool) -> None:
        """One want record (W2 to W7). `partial` is true at `update`'s own element, where a
        record holds only the fields to adjust."""
        place = f"the want '{other}' at '{holder}'"
        if not isinstance(record, dict):
            raise refuse(
                f"{place} must be a record with why, how and direction",
                replaced(self.command, path, want_placeholder()),
            )
        extra = [name for name in record if name not in WANT_FIELDS]
        if extra:
            fixed = self.command
            for name in extra:
                fixed = replaced(fixed, path + [name], REMOVE)
            raise refuse(f"{place} does not take: {', '.join(extra)}", accepted(fixed))
        for field, value in record.items():
            here = path + [field]
            if field == "direction":
                if not (isinstance(value, str) and value in DIRECTIONS):
                    raise refuse(
                        f"direction at {place} must be inbound, outbound or two-way",
                        replaced(self.command, here, "<inbound, outbound or two-way>"),
                    )
            elif not (isinstance(value, str) and not is_blank(value)):
                raise refuse(
                    f"{field} at {place} must be text that is not blank",
                    replaced(self.command, here, f"<{field}>"),
                )
        missing = [field for field in WANT_FIELDS if field not in record]
        if partial and not record:
            raise refuse(
                f"{place} has no fields; give why, how or direction",
                replaced(self.command, path, want_placeholder()),
            )
        if not partial and missing:
            # The same code and message as a want that an update leaves incomplete (R-5.6).
            fixed = self.command
            for field in missing:
                fixed = replaced(fixed, path + [field], f"<{field}>")
            raise Refusal(
                refusal.WANT_INCOMPLETE,
                f"'{holder}' wants '{other}': the want has no {', '.join(missing)}",
                fixed,
            )


def delete(address: str, value: Any) -> None:
    """`delete` (D2 to D5)."""
    if address == ROOT:
        raise refuse("the root cannot be deleted")
    if not is_address(address):
        raise not_an_address(address)
    if not isinstance(value, dict):
        raise refuse(DELETE_FORM)
    if not value:
        return
    if "wants" not in value or len(value) != 1:
        raise refuse(DELETE_FORM)
    wants = value["wants"]

    def remove(wants: list[str]) -> dict[str, Any]:
        return {"delete": {address: {"wants": wants}}}

    if isinstance(wants, str) and is_address(wants):
        raise refuse(DELETE_FORM, remove([wants]))
    if not isinstance(wants, list) or not wants:
        raise refuse(DELETE_FORM, remove(["<address>"]))
    seen: list[str] = []
    for item in wants:
        if not isinstance(item, str):
            raise refuse(DELETE_FORM, remove(["<address>"]))
        if item == ROOT:
            raise refuse("the root cannot be wanted")
        if not is_address(item):
            raise not_an_address(item)
        if item in seen:
            once: list[str] = []
            for other in wants:
                if isinstance(other, str) and other not in once:
                    once.append(other)
            raise refuse(f"delete names the want '{item}' more than once", accepted(remove(once)))
        seen.append(item)


def read(address: str, body: Any) -> None:
    """An addressed read (L1 to L4)."""
    if not is_address(address):
        raise not_an_address(address)
    form = f'a read names each layer with {{}} as its value, such as {{"{address}": {{"wants": {{}}}}}}'
    if not isinstance(body, dict):
        raise refuse(form, {address: {}})
    for name, value in body.items():
        if not is_segment(name):
            raise refuse(
                f"'{name}' is not a layer name: a layer name is one segment, with no periods, spaces, '$', '[' or ']'"
            )
        if not is_empty_object(value):
            raise refuse(form, accepted({address: {name: {} for name in body}}))


def refuse(message: str, remediation: Any = None) -> Refusal:
    return Refusal(refusal.FIELD_MISMATCH, message, remediation)


def not_an_address(text: str) -> Refusal:
    return refuse(f"'{text}' is not an address: segments are joined by periods, with no spaces, '$', '[' or ']'")


def accepted(command: Any) -> Any:
    """A corrected command, if this check accepts it. A remediation must not be refused in turn."""
    try:
        check(command)
    except Refusal:
        return None
    return command


def want_placeholder() -> dict[str, Any]:
    """A want record with a placeholder for each value only the agent can supply."""
    return {"why": "<why>", "how": "<how>", "direction": "<direction>"}


def one_entry(value: Any) -> tuple[str, Any] | None:
    """The single entry of an object, or `None` if the value is not an object with one entry."""
    if not isinstance(value, dict) or len(value) != 1:
        return None
    return next(iter(value.items()))


def is_empty_object(value: Any) -> bool:
    return isinstance(value, dict) and not value


# Given to `replaced` in place of a value, to remove the entry at the path.
REMOVE = object()


def replaced(command: Any, path: list[str], value: Any) -> Any:
    """The command with the value at `path` replaced, or removed when `value` is `REMOVE`. Every
    key of `path` but the last names an object in the command."""
    out = copy(command)
    if not path:
        return out
    at = out
    for key in path[:-1]:
        at = at[key]
    if isinstance(at, dict):
        if value is REMOVE:
            at.pop(path[-1], None)
        else:
            at[path[-1]] = value
    return out


def is_segment(text: str) -> bool:
    """One address segment: at least one character, and no period, `$`, `[`, `]` or space."""
    return text != "" and not any(c in ".$[]" or is_space(c) for c in text)


def is_address(text: str) -> bool:
    """An address beneath the root: segments joined by periods. The root `.` is not one."""
    return all(is_segment(segment) for segment in text.split("."))
