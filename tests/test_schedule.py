import itertools
from datetime import timedelta
from typing import Iterator

from stateless import Success, run
from stateless.schedule import Recurs, Spaced


def test_spaced() -> None:
    def effect() -> Success[Iterator[timedelta]]:
        schedule = yield from Spaced(timedelta(seconds=1))
        return itertools.islice(schedule, 3)

    deltas = run(effect())
    assert list(deltas) == [timedelta(seconds=1)] * 3


def test_recurs() -> None:
    schedule = Recurs(3, Spaced(timedelta(seconds=1)))
    deltas = run(iter(schedule))
    assert list(deltas) == [timedelta(seconds=1)] * 3
