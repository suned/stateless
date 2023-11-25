from datetime import timedelta
from typing import NoReturn as Never

from pytest import raises
from stateless import (
    Effect,
    Runtime,
    Success,
    Try,
    catch,
    depend,
    memoize,
    repeat,
    retry,
    success,
    throw,
    throws,
)
from stateless.functions import RetryError
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
    effect: Success[RuntimeError] = catch(lambda: throw(RuntimeError("oops")))()

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


def test_retry() -> None:
    @repeat(Recurs(2, Spaced(timedelta(seconds=1))))
    def effect() -> Try[RuntimeError, Never]:
        return throw(RuntimeError("oops"))

    time: Time = MockTime()
    with raises(RuntimeError, match="oops"):
        Runtime().use(time).run(effect())


def test_retry_on_eventual_success() -> None:
    counter = 0

    @retry(Recurs(2, Spaced(timedelta(seconds=1))))
    def effect() -> Effect[Never, RuntimeError, int]:
        nonlocal counter
        if counter == 1:
            return success(42)
        counter += 1
        return throw(RuntimeError("oops"))

    time: Time = MockTime()
    assert Runtime().use(time).run(effect()) == 42


def test_retry_on_failure() -> None:
    @retry(Recurs(2, Spaced(timedelta(seconds=1))))
    def effect() -> Effect[Never, RuntimeError, int]:
        return throw(RuntimeError("oops"))

    time: Time = MockTime()
    with raises(RetryError):
        Runtime().use(time).run(effect())


def test_memoize() -> None:
    counter = 0

    @memoize
    def f(_: int) -> Success[int]:
        nonlocal counter
        counter += 1
        return success(counter)

    def g() -> Success[tuple[int, int, int, int]]:
        i1 = yield from f(0)
        i2 = yield from f(1)
        e: Success[int] = f(0)
        i3 = yield from e
        i4 = yield from e
        return (i1, i2, i3, i4)

    assert Runtime().run(g()) == (1, 2, 1, 1)
    assert counter == 2


def test_memoize_with_args() -> None:
    @memoize(maxsize=1, typed=False)
    def f() -> Success[int]:
        return success(42)

    assert f.cache_parameters() == {"maxsize": 1, "typed": False}  # type: ignore


def test_memoize_on_unhandled_error() -> None:
    @memoize
    def f() -> Try[RuntimeError, Never]:
        return throw(RuntimeError("oops"))

    with raises(RuntimeError, match="oops"):
        Runtime().run(f())


def test_memoize_on_handled_error() -> None:
    @memoize
    def f() -> Try[RuntimeError, str]:
        try:
            return (yield from throw(RuntimeError("oops")))
        except RuntimeError:
            return "done"

    assert Runtime().run(f()) == "done"
