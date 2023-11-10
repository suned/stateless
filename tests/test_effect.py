from typing import NoReturn as Never
from datetime import timedelta

from pytest import raises

from stateless import (
    catch,
    Runtime,
    depend,
    throw,
    throws,
    repeat,
    success,
    Success,
    Try,
)
from stateless.schedule import Recurs, Spaced
from stateless.time import Time


class MockTime(Time):
    def sleep(self, seconds: float) -> None:
        pass


def test_throw() -> None:
    effect = throw(RuntimeError("oops"))
    with raises(RuntimeError, match="oops"):
        Runtime().run(effect)


def test_catch() -> None:
    effect = catch(lambda: throw(RuntimeError("oops")))()
    error = Runtime().run(effect)

    assert isinstance(error, RuntimeError)
    assert str(error) == "oops"


def test_catch_success() -> None:
    effect = catch(lambda: success(42))()
    value = Runtime().run(effect)

    assert value == 42


def test_catch_unhandled() -> None:
    def effect() -> Success[None]:
        raise ValueError("oops")

    with raises(ValueError, match="oops"):
        Runtime().run(catch(effect)())


def test_throws() -> None:
    @throws(ValueError)
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


def test_repeat_on_error() -> None:
    @repeat(Recurs(2, Spaced(timedelta(seconds=1))))
    def effect() -> Try[RuntimeError, Never]:
        return throw(RuntimeError("oops"))

    time: Time = MockTime()
    with raises(RuntimeError, match="oops"):
        Runtime().use(time).run(effect())
