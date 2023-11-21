"""Contains the Schedule type and combinators."""

import itertools
from dataclasses import dataclass
from datetime import timedelta
from typing import Iterator, Protocol, TypeVar
from typing import NoReturn as Never

from stateless.effect import Depend, Success, success

A = TypeVar("A", covariant=True)


class Schedule(Protocol[A]):
    """An iterator of timedeltas depending on stateless abilities."""

    def __iter__(self) -> Depend[A, Iterator[timedelta]]:
        ...


@dataclass(frozen=True)
class Spaced(Schedule[Never]):
    """A schedule that yields a timedelta at a fixed interval forever."""

    interval: timedelta

    def __iter__(self) -> Success[Iterator[timedelta]]:
        return success(itertools.repeat(self.interval))


@dataclass(frozen=True)
class Recurs(Schedule[A]):
    """A schedule that yields timedeltas from the schedule given as arguments fixed number of times."""

    n: int
    schedule: Schedule[A]

    def __iter__(self) -> Depend[A, Iterator[timedelta]]:
        deltas = yield from self.schedule
        return itertools.islice(deltas, self.n)
