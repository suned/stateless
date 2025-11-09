from datetime import timedelta
from typing import NoReturn as Never

from pytest import raises
from stateless import (
    Effect,
    Success,
    Try,
    catch,
    memoize,
    repeat,
    retry,
    run,
    success,
    supply,
    throw,
    throws,
)
from stateless.effect import SuccessEffect
from stateless.functions import RetryError
from stateless.need import need
from stateless.schedule import recurs, spaced
from stateless.time import Time

from tests.utils import run_with_abilities


class MockTime(Time):
    async def sleep(self, seconds: float) -> None:
        pass


def test_throw() -> None:
    effect = throw(RuntimeError("oops"))
    with raises(RuntimeError, match="oops"):
        run(effect)


def test_catch() -> None:
    effect: Success[RuntimeError] = catch(RuntimeError)(
        lambda: throw(RuntimeError("oops"))
    )()

    error = run(effect)

    assert isinstance(error, RuntimeError)
    assert str(error) == "oops"


def test_catch_with_errors() -> None:
    effect: Success[RuntimeError | ZeroDivisionError] = catch(  # type: ignore
        RuntimeError, ZeroDivisionError
    )(lambda: throw(RuntimeError("oops")))()

    error = run(effect)

    assert isinstance(error, RuntimeError)
    assert str(error) == "oops"


def test_catch_with_nothing() -> None:
    effect: Try[RuntimeError, None] = catch()(lambda: throw(RuntimeError("oops")))()
    with raises(RuntimeError, match="oops"):
        run(effect)


def test_catch_with_wrong_error() -> None:
    effect: Try[ZeroDivisionError, ValueError] = catch(ValueError)(
        lambda: throw(ZeroDivisionError())
    )()

    with raises(ZeroDivisionError):
        run(effect)


def test_catch_success() -> None:
    effect = catch(Exception)(lambda: success(42))()
    value = run(effect)

    assert value == 42


def test_catch_unhandled() -> None:
    def effect() -> Success[None]:
        raise ValueError("oops")

    with raises(ValueError, match="oops"):
        run(catch(ValueError)(effect)())


def test_throws() -> None:
    @throws(ValueError)
    def effect() -> Never:
        raise ValueError("oops")

    with raises(ValueError, match="oops"):
        run(effect())


def test_repeat() -> None:
    @repeat(recurs(2, spaced(timedelta(seconds=1))))
    def effect() -> Success[int]:
        return success(42)

    assert run_with_abilities(effect(), supply(MockTime())) == (42, 42)


def test_repeat_on_error() -> None:
    @repeat(recurs(2, spaced(timedelta(seconds=1))))
    def effect() -> Try[RuntimeError, Never]:
        return throw(RuntimeError("oops"))

    with raises(RuntimeError, match="oops"):
        run_with_abilities(effect(), supply(MockTime()))


def test_retry() -> None:
    @repeat(recurs(2, spaced(timedelta(seconds=1))))
    def effect() -> Try[RuntimeError, Never]:
        return throw(RuntimeError("oops"))

    with raises(RuntimeError, match="oops"):
        run_with_abilities(effect(), supply(MockTime()))


def test_retry_on_eventual_success() -> None:
    counter = 0

    @retry(recurs(2, spaced(timedelta(seconds=1))))
    def effect() -> Effect[Never, RuntimeError, int]:
        nonlocal counter
        if counter == 1:
            return success(42)
        counter += 1
        return throw(RuntimeError("oops"))

    assert run_with_abilities(effect(), supply(MockTime())) == 42


def test_retry_on_failure() -> None:
    @retry(recurs(2, spaced(timedelta(seconds=1))))
    def effect() -> Effect[Never, RuntimeError, int]:
        return throw(RuntimeError("oops"))

    with raises(RetryError):
        run_with_abilities(effect(), supply(MockTime()))


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

    assert run(g()) == (1, 2, 1, 1)
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
        run(f())


def test_memoize_on_handled_error() -> None:
    @memoize
    def f() -> Try[RuntimeError, str]:
        try:
            return (yield from throw(RuntimeError("oops")))
        except RuntimeError:
            return "done"

    assert run(f()) == "done"


def test_success_throw() -> None:
    effect = SuccessEffect("hi")
    with raises(ValueError, match="oops"):
        effect.throw(ValueError("oops"))


def test_compose_catch_and_handle() -> None:
    effect = supply("value")(catch(Exception)(lambda: need(str)))()
    assert run(effect) == "value"
