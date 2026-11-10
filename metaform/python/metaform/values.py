"""JSON values and text, handled the way the Rust form handles them.

Python and Rust differ in small ways that an agent could see: `1 == 1.0` is true in Python, and
`str.strip` and `str.splitlines` use a wider set of characters than Rust's `trim` and `lines`.
Every form of Metaform uses the functions here, so the answers stay equal. This module has no
Rust counterpart; it holds what `serde_json` and the Rust standard library give the Rust form.
"""
import json
import json.encoder
import re
from typing import Any

# The characters with the Unicode property White_Space (`shape.rs`, `is_space`).
SPACE = "\u0009-\u000d \u0085   -     　"
_SPACE = re.compile(f"[{SPACE}]")
_NOT_SPACE = re.compile(f"[^{SPACE}]+")
_TRIM = re.compile(f"\\A[{SPACE}]+|[{SPACE}]+\\Z")
_TRIM_END = re.compile(f"[{SPACE}]+\\Z")

# serde_json keeps a whole number as an integer only within these limits.
_LOWEST, _HIGHEST = -(2**63), 2**64 - 1


def is_space(character: str) -> bool:
    return _SPACE.fullmatch(character) is not None


def is_blank(text: str) -> bool:
    """Whether the text is empty or holds only White_Space characters."""
    return _NOT_SPACE.search(text) is None


def trim(text: str) -> str:
    """Rust's `str::trim`."""
    return _TRIM.sub("", text)


def trim_end(text: str) -> str:
    """Rust's `str::trim_end`."""
    return _TRIM_END.sub("", text)


def split_whitespace(text: str) -> list[str]:
    """Rust's `str::split_whitespace`."""
    return _NOT_SPACE.findall(text)


def lines(text: str) -> list[str]:
    """Rust's `str::lines`: split at LF, drop one CR before it, and no last empty line."""
    parts = text.split("\n")
    if parts[-1] == "":
        parts.pop()
    return [part[:-1] if part.endswith("\r") else part for part in parts]


def ascii_lower(text: str) -> str:
    """Rust's `to_ascii_lowercase`: only A to Z change."""
    return "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in text)


def same(left: Any, right: Any) -> bool:
    """Whether two JSON values are equal as `serde_json` compares them.

    The order of an object's keys does not matter. `1`, `1.0` and `true` are three values.
    """
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return len(left) == len(right) and all(
            key in right and same(value, right[key]) for key, value in left.items()
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
    return bool(left == right)


def copy(value: Any) -> Any:
    """A copy of a JSON value that shares nothing with it."""
    if isinstance(value, dict):
        return {key: copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [copy(item) for item in value]
    return value


def is_text(value: Any) -> bool:
    return isinstance(value, str)


def as_whole_number(value: Any) -> int | None:
    """serde_json's `as_u64`: a whole number that is not negative and was not written as a float."""
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _fraction(text: str) -> float:
    number = float(text)
    if number in (float("inf"), float("-inf")):
        raise ValueError(f"{text} is out of range")
    return number


def _whole(text: str) -> int | float:
    number = int(text)
    return number if _LOWEST <= number <= _HIGHEST else _fraction(text)


def _constant(name: str) -> Any:
    raise ValueError(f"{name} is not JSON")


def _has_lone_surrogate(value: Any) -> bool:
    if isinstance(value, str):
        return any("\ud800" <= c <= "\udfff" for c in value)
    if isinstance(value, dict):
        return any(_has_lone_surrogate(key) or _has_lone_surrogate(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_has_lone_surrogate(item) for item in value)
    return False


def loads(text: str) -> Any:
    """Parse JSON as serde_json does: a whole number outside 64 bits becomes a float. `NaN`,
    `Infinity`, a number too large for a float and half of a surrogate pair are refused. Raises
    `ValueError` for text that is not JSON."""
    value = json.loads(text, parse_int=_whole, parse_float=_fraction, parse_constant=_constant)
    if "\\u" in text and _has_lone_surrogate(value):
        raise ValueError("half of a surrogate pair is not text")
    return value


def _float_text(number: float) -> str:
    """A float as the Rust form writes it. Python differs for small numbers only: it writes
    `1e-05` and `1e-07` where the Rust form writes `0.00001` and `1e-7`."""
    text = repr(number)
    if "e-" not in text:
        return text
    digits, exponent = text.split("e-")
    if int(exponent) != 5:
        return f"{digits}e-{int(exponent)}"
    sign = "-" if digits.startswith("-") else ""
    return f"{sign}0.0000{digits.lstrip('-').replace('.', '')}"


def _write(value: Any, out: list[str]) -> None:
    if isinstance(value, str):
        out.append(_TEXT(value))
    elif value is None:
        out.append("null")
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif isinstance(value, int):
        out.append(str(value))
    elif isinstance(value, float):
        out.append(_float_text(value))
    elif isinstance(value, dict):
        out.append("{")
        for index, (key, item) in enumerate(value.items()):
            out.append(("," if index else "") + _TEXT(key) + ":")
            _write(item, out)
        out.append("}")
    else:
        out.append("[")
        for index, item in enumerate(value):
            if index:
                out.append(",")
            _write(item, out)
        out.append("]")


# JSON text of a string, with characters outside ASCII written as they are.
_TEXT = json.encoder.encode_basestring


def dumps(value: Any) -> str:
    """Compact JSON text as serde_json writes it: no spaces, characters outside ASCII written as
    they are, and floats in the Rust form's notation."""
    out: list[str] = []
    _write(value, out)
    return "".join(out)
