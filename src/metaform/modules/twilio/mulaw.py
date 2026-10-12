"""G.711 mu-law, the telephone's 8 kHz encoding Twilio Media Streams carries, in the standard library only.

The bridge needs only how loud a frame is, to hear the caller start speaking over the agent (barge-in); the voice
module decodes the audio it transcribes. `encode` is here for the simulated call, which makes a caller's speech.
"""
from __future__ import annotations

import math
from array import array

RATE = 8000
FRAME = 160  # bytes in 20 ms, the frame Twilio sends and the size the bridge sends back
SILENCE = 0xFF  # mu-law's zero


def _decoded() -> tuple[int, ...]:
    table: list[int] = []
    for byte in range(256):
        value = ~byte & 0xFF
        sign, exponent, mantissa = value & 0x80, (value >> 4) & 0x07, value & 0x0F
        sample = (((mantissa << 3) + 0x84) << exponent) - 0x84
        table.append(-sample if sign else sample)
    return tuple(table)


DECODED = _decoded()


def decode(chunk: bytes) -> array[int]:
    """16-bit linear samples of mu-law bytes."""
    return array('h', (DECODED[byte] for byte in chunk))


def encode_sample(sample: int) -> int:
    """One 16-bit linear sample as a mu-law byte, G.711's bias-and-segment form."""
    sign = 0x80 if sample < 0 else 0
    magnitude = min(abs(sample), 32635) + 0x84
    exponent = max(0, magnitude.bit_length() - 8)
    exponent = min(exponent, 7)
    mantissa = (magnitude >> (exponent + 3)) & 0x0F
    return ~(sign | (exponent << 4) | mantissa) & 0xFF


def encode(samples: array[int] | list[int]) -> bytes:
    return bytes(encode_sample(sample) for sample in samples)


def loudness(chunk: bytes) -> float:
    """The root-mean-square level of a mu-law chunk, 0 for silence, up to about 32000."""
    if not chunk:
        return 0.0
    return math.sqrt(sum(DECODED[byte] ** 2 for byte in chunk) / len(chunk))


def tone(seconds: float, frequency: float = 220.0, level: int = 8000) -> bytes:
    """A tone as mu-law, a stand-in for speech in the simulated call."""
    count = int(seconds * RATE)
    return encode([int(level * math.sin(2 * math.pi * frequency * n / RATE)) for n in range(count)])


def silence(seconds: float) -> bytes:
    return bytes([SILENCE]) * int(seconds * RATE)


def frames(audio: bytes, size: int = FRAME) -> list[bytes]:
    return [audio[at:at + size] for at in range(0, len(audio), size)]
