"""Address rules and the conversion between the agent's snake_case and the stored camelCase
(R-3.2, R-3.3, R-4.11). Agents see snake_case and full addresses; storage sees camelCase.
Ports `names.rs`.
"""
from typing import Any, Callable

from . import refusal
from .refusal import Refusal

# The address of a map's root (R-5.9).
ROOT = "."

# The valid root scopes (R-3.3).
ROOT_SCOPES = ("code", "document", "media", "data", "collection", "upstream", "downstream", "layer")

# The root prefixes (R-3.3): what follows them is not located in the project. `upstream` and
# `downstream` are outside the project being mapped (R-3.7), and `layer` holds layer
# definitions (R-6.24).
ROOT_PREFIXES = ("upstream", "downstream", "layer")


def in_project(address: str) -> bool:
    """Whether an address belongs to the project itself: the root, or an element not under a root
    prefix. The one-Definitive rule (R-3.13) counts only these elements."""
    return address == ROOT or address.split(".")[0] not in ROOT_PREFIXES


def to_camel(snake: str) -> str:
    out: list[str] = []
    upper = False
    for c in snake:
        if c == "_":
            upper = True
        elif upper:
            out.append(c.upper())
            upper = False
        else:
            out.append(c)
    return "".join(out)


def to_snake(camel: str) -> str:
    out: list[str] = []
    for c in camel:
        if c.isupper():
            out.append("_")
            out.append(c.lower())
        else:
            out.append(c)
    return "".join(out)


def map_address(address: str, convert: Callable[[str], str]) -> str:
    """Convert every segment of an address with `convert`."""
    if address == ROOT:
        return ROOT
    return ".".join(convert(segment) for segment in address.split("."))


def segment_problem(segment: str) -> str | None:
    """Why a name would not survive storage, or `None` if it converts back exactly."""
    if any(c.isupper() for c in segment):
        return "a name in uppercase is refused, not lowercased"
    if to_snake(to_camel(segment)) == segment:
        return None
    if "__" in segment:
        return "repeated underscores do not survive storage"
    if segment.endswith("_"):
        return "a trailing underscore does not survive storage"
    return "an underscore before a digit or symbol does not survive storage"


def suggest_segment(segment: str) -> str:
    """The nearest name that survives storage: lowercased, single underscores, digits joined to
    the word before them."""
    out = ""
    for word in segment.lower().split("_"):
        if not word:
            continue
        if out and word[0].isalpha():
            out += "_"
        out += word
    return out


def join(address: str, segment: str) -> str:
    return segment if address == ROOT else f"{address}.{segment}"


def last_segment(address: str) -> str:
    """The text after the last period: Rust's `address.rsplit('.').next()`."""
    return address.rsplit(".", 1)[-1]


def parent(address: str) -> str | None:
    """The parent of an address; `None` for the root."""
    if address == ROOT:
        return None
    return address.rsplit(".", 1)[0] if "." in address else ROOT


def prefixes(address: str) -> list[str]:
    """Every prefix of an address, the root first and the address itself last."""
    out = [ROOT]
    if address == ROOT:
        return out
    current = ""
    for segment in address.split("."):
        current = segment if not current else f"{current}.{segment}"
        out.append(current)
    return out


def is_beneath(child: str, address: str) -> bool:
    """Whether `child` lies beneath `address`."""
    return (address == ROOT and child != ROOT) or child.startswith(address + ".")


def check_scope(address: str) -> None:
    """Refuse a top-level element outside the root scopes (R-3.3)."""
    scope = address.split(".")[0]
    if address == ROOT or scope in ROOT_SCOPES:
        return
    raise Refusal(
        refusal.ROOT_SCOPE_NOT_ALLOWED,
        f"'{address}': the root scope '{scope}' is not one of: {', '.join(ROOT_SCOPES)}",
    )


class NameCheck:
    """Checks every name in a command, building the corrected command as it goes."""

    def __init__(self) -> None:
        self.problems: list[str] = []

    def segment(self, segment: str, address: str) -> str:
        why = segment_problem(segment)
        if why is None:
            return segment
        self.problems.append(f"'{address}': '{segment}': {why}")
        return suggest_segment(segment)

    def address(self, address: str) -> str:
        if address == ROOT:
            return ROOT
        return ".".join(self.segment(segment, address) for segment in address.split("."))

    def fields(self, fields: dict[str, Any], address: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in fields.items():
            fixed: Any
            if isinstance(value, list) and key == "wants":
                fixed = [self.want_group(group) for group in value]
            elif isinstance(value, dict):
                fixed = self.fields(value, join(address, key))
            else:
                fixed = value
            out[self.segment(key, address)] = fixed
        return out

    def want_group(self, group: Any) -> Any:
        if not isinstance(group, dict):
            return group
        out: dict[str, Any] = {}
        for provider, record in group.items():
            if isinstance(record, dict):
                record = {self.segment(key, provider): value for key, value in record.items()}
            out[self.address(provider)] = record
        return out


def check_command(command: Any) -> None:
    """Refuse a command holding a name that would not survive storage (R-4.11). The remediation
    is the command with each such name corrected. The command has already passed the shape check."""
    if not isinstance(command, dict) or not command:
        return
    verb, body = next(iter(command.items()))
    check = NameCheck()
    fixed_body: Any
    if verb in ("add", "update") and isinstance(body, dict):
        fixed_body = {}
        for address, fields in body.items():
            fixed = check.fields(fields, address) if isinstance(fields, dict) else fields
            fixed_body[check.address(address)] = fixed
    elif verb == "delete" and isinstance(body, dict):
        fixed_body = {}
        for address, supplied in body.items():
            if isinstance(supplied, dict) and isinstance(supplied.get("wants"), list):
                supplied = dict(supplied)
                supplied["wants"] = [
                    check.address(want) if isinstance(want, str) else want
                    for want in supplied["wants"]
                ]
            fixed_body[check.address(address)] = supplied
    elif verb == "goto" and isinstance(body, str):
        fixed_body = check.address(body)
    else:
        fixed_body = body
    if verb in ("add", "update", "delete", "orphaned", "goto", "map", "help"):
        fixed_verb = verb
    elif verb == ROOT:
        fixed_verb = ROOT
    elif verb.startswith("."):
        fixed_verb = "." + check.address(verb[1:])
    else:
        fixed_verb = check.address(verb)
    if not check.problems:
        return
    raise Refusal(
        refusal.NAME_ROUND_TRIP_FAILURE,
        "; ".join(check.problems),
        {fixed_verb: fixed_body},
    )


def stored_name(agent_form: str) -> str:
    """An address or key in the stored form: every segment in camelCase (R-4.11)."""
    return map_address(agent_form, to_camel)


def agent_name(stored_form: str) -> str:
    """An address or key in the agent's form: every segment in snake_case (R-4.11)."""
    return map_address(stored_form, to_snake)
