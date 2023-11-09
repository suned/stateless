from typing import NoReturn as Never
from datetime import timedelta

from pytest import raises

from stateless import fail, catch, Runtime, depend, absorb, repeat, success, Success
from stateless.schedule import Recurs, Spaced
from stateless.time import Time


class MockTime(Time):
    def sleep(self, seconds: float) -> None:
        pass


def test_fail() -> None:
    effect = fail(RuntimeError("oops"))
    with raises(RuntimeError, match="oops"):
        Runtime().run(effect)


def test_catch() -> None:
    effect = catch(lambda: fail(RuntimeError("oops")))()
    error = Runtime().run(effect)

    assert isinstance(error, RuntimeError)
    assert str(error) == "oops"


def test_absorb() -> None:
    @absorb(ValueError)
    def effect() -> Never:
        raise ValueError("oops")

    with raises(ValueError, match="oops"):
        Runtime().run(effect())


def test_depend() -> None:
    effect = depend(int)
    assert Runtime().use(0).run(effect) == 0


def test_repeat() -> None:
    @repeat(Recurs(2, Spaced(timedelta(seconds=1))))
    def effect() -> Success[int]:
        return success(42)

    time: Time = MockTime()
    assert Runtime().use(time).run(effect()) == (42, 42)
