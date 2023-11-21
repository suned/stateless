"""Contains the Schedule type and combinators."""

import itertools
from dataclasses import dataclass
from datetime import timedelta
from typing import Iterator, Protocol, TypeVar
from typing import NoReturn as Never

from stateless.effect import Depend, Success, success

A = TypeVar("A", covariant=True)


class Schedule(Protocol[A]):
    def __iter__(self) -> Depend[A, Iterator[timedelta]]:
        ...


@dataclass(frozen=True)
class Spaced(Schedule[Never]):
    interval: timedelta

    def __iter__(self) -> Success[Iterator[timedelta]]:
        return success(itertools.repeat(self.interval))


@dataclass(frozen=True)
class Recurs(Schedule[A]):
    n: int
    schedule: Schedule[A]

    def __iter__(self) -> Depend[A, Iterator[timedelta]]:
        deltas = yield from self.schedule
        return itertools.islice(deltas, self.n)
