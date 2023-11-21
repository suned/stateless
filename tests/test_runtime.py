from dataclasses import dataclass

from pytest import raises
from stateless import Depend, Effect, Runtime, Try, depend
from stateless.errors import MissingAbilityError
from typing_extensions import Never


@dataclass(frozen=True)
class Super:
    pass


@dataclass(frozen=True)
class Sub(Super):
    pass


@dataclass(frozen=True)
class SubSub(Sub):
    pass


def test_run_with_unhandled_exception() -> None:
    def fails() -> Depend[str, None]:
        yield str
        raise RuntimeError("oops")

    e = fails()
    with raises(RuntimeError, match="oops"):
        Runtime().use("").run(e)


def test_provide_multiple_sub_types() -> None:
    sub: Super = Sub()
    subsub: Super = SubSub()
    assert Runtime().use(subsub).use(sub).run(depend(Super)) == Sub()
    assert Runtime().use(sub).use(subsub).run(depend(Super)) == SubSub()


def test_missing_dependency() -> None:
    def effect() -> Depend[Super, Super]:
        ability: Super = yield Super
        return ability

    with raises(MissingAbilityError, match="Super") as info:
        Runtime().run(effect())  # type: ignore

    print(info.getrepr())

    # test that the third frame is the yield
    # expression in `effect` function above
    # (first is Runtime().run(..)
    # second is effect.throw in Runtime.run)
    frame = info.traceback[2]
    assert str(frame.path) == __file__
    assert frame.lineno == effect.__code__.co_firstlineno


def test_simple_dependency() -> None:
    def effect() -> Depend[str, str]:
        ability: str = yield str
        return ability

    assert Runtime().use("hi!").run(effect()) == "hi!"


def test_simple_failure() -> None:
    def effect() -> Effect[Never, ValueError, None]:
        yield ValueError("oops")
        return

    with raises(ValueError, match="oops"):
        Runtime().run(effect())


def test_return_errors() -> None:
    def fails() -> Try[ValueError, None]:
        yield ValueError("oops")
        return

    result = Runtime().run(fails(), return_errors=True)
    assert isinstance(result, ValueError)
    assert result.args == ("oops",)


def test_return_errors_on_duplicate_error_type() -> None:
    def fails() -> Try[ValueError, None]:
        yield ValueError("oops")
        return

    def catches() -> Try[ValueError, None]:
        try:
            yield from fails()
        except ValueError:
            pass
        raise ValueError("oops again")

    with raises(ValueError, match="oops again"):
        Runtime().run(catches(), return_errors=True)
