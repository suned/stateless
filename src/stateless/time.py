"""Contains the Time ability and ability helpers."""

import time
from dataclasses import dataclass

from stateless.effect import Depend


@dataclass(frozen=True)
class Time:
    """The Time ability."""

    def sleep(self, seconds: float) -> None:
        """
        Sleep for a number of seconds.

        Args:
        ----
            seconds: The number of seconds to sleep for.
        """
        time.sleep(seconds)


def sleep(seconds: float) -> Depend[Time, None]:
    """
    Sleep for a number of seconds.

    Args:
    ----
        seconds: The number of seconds to sleep for.

    Returns:
    -------
        An effect that sleeps for a number of seconds.
    """
    time_ = yield Time
    time_.sleep(seconds)
