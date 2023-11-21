"""Contains the Time ability and ability helpers."""

import time
from dataclasses import dataclass

from stateless.effect import Depend


@dataclass(frozen=True)
class Time:
    """The Time ability."""

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def sleep(seconds: float) -> Depend[Time, None]:
    time_ = yield Time
    time_.sleep(seconds)
