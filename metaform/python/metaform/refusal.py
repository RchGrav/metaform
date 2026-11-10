"""Refusals (R-5.24): a fixed error code, a message in plain words, the tested sentence where one
applies, and the remediation command that fixes it. Ports `refusal.rs`.

The rule a code stands for is documentation, kept here in `RULES`. It is not a field of the
response.
"""
from typing import Any

TECHNICAL_NAME_ALIGNMENT_FAILURE = "TECHNICAL_NAME_ALIGNMENT_FAILURE"
CANONICAL_NAME_COLLISION_FAILURE = "CANONICAL_NAME_COLLISION_FAILURE"
ROLE_TAXONOMY_FAILURE = "ROLE_TAXONOMY_FAILURE"
GRAMMAR_CONSTRAINT_VIOLATION = "GRAMMAR_CONSTRAINT_VIOLATION"
FIELD_MISMATCH = "FIELD_MISMATCH"
ROOT_SCOPE_NOT_ALLOWED = "ROOT_SCOPE_NOT_ALLOWED"
FIELD_ELEMENT_COLLISION = "FIELD_ELEMENT_COLLISION"
LAYER_NOT_REGISTERED = "LAYER_NOT_REGISTERED"
DEPENDENCY_LOCK = "DEPENDENCY_LOCK"
NAME_ROUND_TRIP_FAILURE = "NAME_ROUND_TRIP_FAILURE"
NOT_FOUND = "NOT_FOUND"
ELEMENTS_BENEATH = "ELEMENTS_BENEATH"
WANT_INCOMPLETE = "WANT_INCOMPLETE"
ELEMENT_NOT_IN_SKELETON = "ELEMENT_NOT_IN_SKELETON"
HEADING_LEVEL_INVALID = "HEADING_LEVEL_INVALID"
HEADING_IN_TEXT = "HEADING_IN_TEXT"
LAYER_DEFINITION_LOCKED = "LAYER_DEFINITION_LOCKED"
CODE_NOT_UNIQUE = "CODE_NOT_UNIQUE"
LAYER_NAME_COLLISION = "LAYER_NAME_COLLISION"
INTERNAL_ERROR = "INTERNAL_ERROR"

# The rule each code stands for, with the requirement it comes from.
RULES: dict[str, str] = {
    TECHNICAL_NAME_ALIGNMENT_FAILURE: "R-3.11: technical_name is the same number of leading words of the reversed, space-separated address.",
    CANONICAL_NAME_COLLISION_FAILURE: "R-3.12: name must not equal technical_name.",
    ROLE_TAXONOMY_FAILURE: "R-3.13: a role is Definitive, Supportive, Notable or Divergent, and a map has exactly one Definitive element.",
    GRAMMAR_CONSTRAINT_VIOLATION: "R-3.17, R-6.17, module 6.4: why is one fragment that starts with a base verb, and how is one fragment that starts with a verb ending in -s. Neither starts with to, a subject or an -ing verb, holds a second fragment, or holds a number that stands alone. Checked for the parts of a want that an add or update writes. Words ending in -ing after the first word are not checked (D-14).",
    FIELD_MISMATCH: "The command must match the project-map input schema, and every element must match the stored-document schema.",
    ROOT_SCOPE_NOT_ALLOWED: "R-3.3: a top-level element is in one of the root scopes.",
    FIELD_ELEMENT_COLLISION: "A word on an element is either a field or the name of an element beneath it, not both.",
    LAYER_NOT_REGISTERED: "R-6.24, R-6.15: a list is written only to a layer defined beneath layer, or to a system layer (skills, memory, sources).",
    DEPENDENCY_LOCK: "R-5.7: delete refuses an element that something still wants.",
    NAME_ROUND_TRIP_FAILURE: "R-4.11: a name must convert to camelCase and back exactly, and a name in uppercase is refused, not lowercased.",
    NOT_FOUND: "R-5.10: a read names an element that exists.",
    ELEMENTS_BENEATH: "R-3.1: an element with elements beneath it cannot be deleted before them.",
    WANT_INCOMPLETE: "R-5.6: a want needs all of its fields: why, how and direction.",
    ELEMENT_NOT_IN_SKELETON: "R-6.26: layer records are written only at an element with technical_name, name and role, or at the root once the map has a Definitive element.",
    HEADING_LEVEL_INVALID: "R-6.25: the first titled block is level 1, each level is at most one more than the level before it, and no level is above 4.",
    LAYER_NAME_COLLISION: "R-6.24: a layer definition's last segment is the layer's field name, so no two definitions share it.",
    CODE_NOT_UNIQUE: "R-6.25: a block's code is unique within its layer across the map, ignoring case, so other text can cite it.",
    LAYER_DEFINITION_LOCKED: "R-6.24, R-6.11: a layer defined by the server's code keeps the definition the code gives it; agents write only its records.",
    HEADING_IN_TEXT: "R-6.25: block text holds no Markdown heading line outside fenced code; the block's level and title set its heading.",
    INTERNAL_ERROR: "Server design, Isolation: an unexpected error fails only the request that caused it.",
}


class Refusal(Exception):
    """A refused command. A refused command changes nothing (R-5.8)."""

    def __init__(self, code: str, reason: str, remediation: Any = None) -> None:
        super().__init__(f"{code}: {reason}")
        self.code = code
        self.reason = reason
        # The tested sentence, where the rule tests one.
        self.sentence: str | None = None
        # The command that fixes the problem. `None` where no command can be derived.
        self.remediation = remediation

    def rule(self) -> str:
        """The rule the command broke, as its code determines."""
        return RULES[self.code]

    def to_json(self) -> dict[str, Any]:
        """The refusal's own fields, in the founder's order (module 6): `code`, `message`, the
        `tested_sentence` where one applies, and `remediation`. The store puts the echoed command
        and `"status": "error"` in front (`store.refusal_json`)."""
        out: dict[str, Any] = {"code": self.code, "message": self.reason}
        if self.sentence is not None:
            out["tested_sentence"] = self.sentence
        out["remediation"] = self.remediation
        return out
