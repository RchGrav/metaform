"""Normalize configuration labels for matching."""


def normalize_label(text: str) -> str:
    """Lowercase a label and join whitespace-separated parts with underscores.

    Preserve punctuation and reject empty or whitespace-only labels.
    """
    parts = text.split()
    if not parts:
        raise ValueError("Label must contain non-whitespace characters")
    return "_".join(parts).lower()
