"""The audible alarm."""


def ring(times: int) -> str:
    return tone() * times


def tone() -> str:
    return 'beep'
