from typing import TypeVar, Iterator, NoReturn as Never, Callable, Protocol
from datetime import timedelta
from dataclasses import dataclass

import itertools

from stateless.effect import Depend, success, Success


A = TypeVar("A")


class Schedule(Protocol[A]):
    def __iter__(self) -> Depend[A, Iterator[timedelta]]:
        pass


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
