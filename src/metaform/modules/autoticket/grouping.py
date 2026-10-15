"""Grouping: the similarity method of onhold's log viewer, src/viewer/filter.c in github.com/rchgrav/onhold, used as
it is.

An entry's fingerprint is the set of its alphanumeric words of two or more characters, lowercased and hashed with
FNV-1a, at most 64, in the order they first appear. Two fingerprints are the same kind when their Dice coefficient,
twice the shared words over both counts, reaches the threshold. An entry joins the first group it matches, in the
order the groups were made; otherwise it starts a new group.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

FNV_OFFSET = 2166136261
FNV_PRIME = 16777619
MAX_TERMS = 64  # onhold's VIEWER_MAX_TERMS
THRESHOLD = 0.45  # onhold's similar_threshold
# C's isalnum in the C locale: ASCII letters and digits; every other byte separates words.
WORD = re.compile(rb'[A-Za-z0-9]+')


def fnv1a_lower(word: bytes) -> int:
    """onhold's fnv1a_lower_token: 32-bit FNV-1a over the word's bytes, each lowercased."""
    hashed = FNV_OFFSET
    for byte in word.lower():
        hashed = ((hashed ^ byte) * FNV_PRIME) & 0xFFFFFFFF
    return hashed


def fingerprint(text: str) -> tuple[int, ...]:
    """onhold's build_profile: each distinct word of 2 or more characters, hashed, at most 64, first seen first."""
    terms: list[int] = []
    seen: set[int] = set()
    for found in WORD.finditer(text.encode('utf-8', 'surrogateescape')):
        if len(terms) >= MAX_TERMS:
            break
        word = found.group(0)
        if len(word) < 2:
            continue
        hashed = fnv1a_lower(word)
        if hashed not in seen:
            seen.add(hashed)
            terms.append(hashed)
    return tuple(terms)


def dice(a: Sequence[int], b: Sequence[int]) -> float:
    """onhold's dice_similarity: 0 when either is empty."""
    if not a or not b:
        return 0.0
    common = len(set(a) & set(b))
    return 2.0 * common / (len(a) + len(b))


def first_match(entry: Sequence[int], groups: Iterable[tuple[int, Sequence[int]]], threshold: float) -> int | None:
    """The id of the first group, in the order given, whose fingerprint the entry matches; None when none does."""
    for group_id, terms in groups:
        if dice(entry, terms) >= threshold:
            return group_id
    return None


def encode(terms: Sequence[int]) -> str:
    """A fingerprint as it is stored: its hashes in hex, space separated."""
    return ' '.join(f'{term:08x}' for term in terms)


def decode(text: str) -> tuple[int, ...]:
    return tuple(int(term, 16) for term in text.split())
