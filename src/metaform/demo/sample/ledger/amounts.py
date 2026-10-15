"""Amounts as the person types them, and as whole cents, so a total never drifts."""


def parse_amount(text: str) -> int:
    """The amount typed, such as 41.15, in whole cents."""
    return int(float(text) * 100)


def format_cents(cents: int) -> str:
    """Whole cents as the person reads them, such as 41.15."""
    sign = '-' if cents < 0 else ''
    whole, part = divmod(abs(cents), 100)
    return f'{sign}{whole}.{part:02d}'
