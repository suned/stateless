"""Contains the Schedule type and combinators."""

import itertools
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable, Generic, Iterator, TypeVar

from typing_extensions import Never

from stateless.ability import Ability
from stateless.effect import Depend, Success, success

A = TypeVar("A", covariant=True, bound=Ability[Any])


@dataclass(frozen=True)
class Schedule(Generic[A]):
    """An iterator of timedeltas depending on stateless abilities."""

    schedule: Callable[[], Depend[A, Iterator[timedelta]]]

    def __iter__(self) -> Depend[A, Iterator[timedelta]]:
        """Iterate over the schedule."""
        return self.schedule()


def spaced(interval: timedelta) -> Schedule[Never]:
    """
    Create a schedule that yields a fixed timedelta forever.

    Args:
    ----
        interval: the fixed interval to yield.

    """

    def schedule() -> Success[Iterator[timedelta]]:
        return success(itertools.repeat(interval))

    return Schedule(schedule)


def recurs(n: int, schedule: Schedule[A]) -> Schedule[A]:
    """
    Create  schedule that yields timedeltas from the schedule given as arguments fixed number of times.

    Args:
    ----
        n: the number of times to yield from `schedule`.
        schedule: The schedule to yield from.

    """

    def _() -> Depend[A, Iterator[timedelta]]:
        deltas = yield from schedule
        return itertools.islice(deltas, n)

    return Schedule(_)
