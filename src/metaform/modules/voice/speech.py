"""Speech out: the voice each mascot character speaks with.

The browser engine, speechSynthesis, runs in the page on every system and sends nothing anywhere; the page reads the
per-character defaults below for it. An engine another module brings, such as elevenlabs, has its own voices.
"""
from __future__ import annotations

from typing import Any

# Each character's own voice, so the mascot sounds like itself: a pitch and a rate on the system's voices, and which
# of them it leans to. voice_voices names a browser voice for any.
CHARACTERS: dict[str, dict[str, Any]] = {
    'beetle':   {'pitch': 0.80, 'rate': 1.00, 'lean': 'low'},
    'comet':    {'pitch': 1.15, 'rate': 1.12, 'lean': 'high'},
    'crystal':  {'pitch': 1.25, 'rate': 1.00, 'lean': 'high'},
    'cubebot':  {'pitch': 0.90, 'rate': 1.05, 'lean': 'low'},
    'drone':    {'pitch': 0.75, 'rate': 1.10, 'lean': 'low'},
    'gearling': {'pitch': 1.00, 'rate': 1.05, 'lean': 'low'},
    'jelly':    {'pitch': 1.30, 'rate': 0.95, 'lean': 'high'},
    'kite':     {'pitch': 1.20, 'rate': 1.10, 'lean': 'high'},
    'moth':     {'pitch': 1.10, 'rate': 0.95, 'lean': 'high'},
    'mushroom': {'pitch': 0.95, 'rate': 0.90, 'lean': 'low'},
    'owl':      {'pitch': 0.85, 'rate': 0.95, 'lean': 'low'},
    'plane':    {'pitch': 1.00, 'rate': 1.15, 'lean': 'low'},
    'puffer':   {'pitch': 1.35, 'rate': 1.05, 'lean': 'high'},
    'seahorse': {'pitch': 1.15, 'rate': 0.95, 'lean': 'high'},
    'slime':    {'pitch': 0.70, 'rate': 0.90, 'lean': 'low'},
    'snail':    {'pitch': 0.90, 'rate': 0.80, 'lean': 'low'},
    'wisp':     {'pitch': 1.40, 'rate': 1.00, 'lean': 'high'},
}
DEFAULT = {'pitch': 1.0, 'rate': 1.0, 'lean': 'any'}


def voices(chosen: list[str]) -> dict[str, dict[str, Any]]:
    """Each character's voice: its default, with the person's voice_voices entries, `character=voice name`, over it."""
    given = dict(entry.split('=', 1) for entry in chosen if '=' in entry)
    return {name: {**profile, **({'voice': given[name]} if given.get(name) else {})}
            for name, profile in CHARACTERS.items()}
