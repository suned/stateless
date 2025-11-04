"""Contains the Time ability and ability helpers."""

import asyncio
from dataclasses import dataclass

from stateless.async_ import Async, wait
from stateless.effect import Depend
from stateless.need import Need, need


@dataclass(frozen=True)
class Time:
    """The Time ability."""

    async def sleep(self, seconds: float) -> None:
        """
        Sleep for a number of seconds.

        Args:
        ----
            seconds: The number of seconds to sleep for.

        """
        await asyncio.sleep(seconds)


def sleep(seconds: float) -> Depend[Need[Time] | Async, None]:
    """
    Sleep for a number of seconds.

    Args:
    ----
        seconds: The number of seconds to sleep for.

    Returns:
    -------
        An effect that sleeps for a number of seconds.

    """
    time = yield from need(Time)
    yield from wait(time.sleep(seconds))
