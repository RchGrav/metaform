"""The kitchen timer."""
from kitchen.alarm import ring


class Timer:
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds

    def tick(self) -> str:
        self.seconds -= 1
        if self.seconds <= 0:
            return ring(3)
        return ''


def unused_helper() -> None:
    pass
