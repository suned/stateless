from typing import Iterator, NoReturn as Never
from datetime import timedelta
import itertools

from stateless import Runtime, Success, Schedule, success
from stateless.schedule import Spaced, Recurs


def test_spaced() -> None:
    def effect() -> Success[Iterator[timedelta]]:
        schedule = yield from Spaced(timedelta(seconds=1))
        return itertools.islice(schedule, 3)

    deltas = Runtime().run(effect())
    assert list(deltas) == [timedelta(seconds=1)] * 3


def test_recurs() -> None:
    schedule = Recurs(3, Spaced(timedelta(seconds=1)))
    deltas = Runtime().run(iter(schedule))
    assert list(deltas) == [timedelta(seconds=1)] * 3
