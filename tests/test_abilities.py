from dataclasses import dataclass

from pytest import raises
from stateless import Abilities, Depend, Effect, depend, parallel, process, run
from stateless.errors import MissingAbilityError
from stateless.parallel import Parallel
from typing_extensions import Never

from tests.utils import run_with_abilities


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
        run_with_abilities(e, Abilities(""))


def test_provide_multiple_sub_types() -> None:
    sub: Super = Sub()
    subsub: Super = SubSub()
    abilities = Abilities().add(subsub).add(sub)
    assert run_with_abilities(depend(Super), abilities) == Sub()
    abilities = Abilities().add(sub).add(subsub)
    assert run_with_abilities(depend(Super), abilities) == SubSub()


def test_missing_dependency() -> None:
    def effect() -> Depend[Super, Super]:
        ability: Super = yield Super
        return ability

    with raises(MissingAbilityError, match="Super") as info:
        run(effect())  # type: ignore

    # test that the fourth frame is the yield
    # expression in `effect` function above
    # (first is Runtime().run(..)
    # second is effect.throw in Runtime.run)
    frame = info.traceback[2]
    assert str(frame.path) == __file__
    assert frame.lineno == effect.__code__.co_firstlineno


def test_missing_dependency_with_abilities() -> None:
    def effect() -> Depend[Super, Super]:
        ability: Super = yield Super
        return ability

    with raises(MissingAbilityError, match="Super") as info:
        run_with_abilities(effect(), Abilities())

    frame = info.traceback[5]
    assert str(frame.path) == __file__
    assert frame.lineno == effect.__code__.co_firstlineno


def test_simple_dependency() -> None:
    def effect() -> Depend[str, str]:
        ability: str = yield str
        return ability

    assert run_with_abilities(effect(), Abilities("hi!")) == "hi!"


def test_simple_failure() -> None:
    def effect() -> Effect[Never, ValueError, None]:
        yield ValueError("oops")
        return

    with raises(ValueError, match="oops"):
        run(effect())


def test_use_effect() -> None:
    def effect() -> Depend[str, bytes]:
        ability: str = yield str
        return ability.encode()

    abilities = Abilities().add("ability").add_effect(effect)
    assert run_with_abilities(depend(bytes), abilities) == b"ability"


def test_multiple_abilities_with_parallel() -> None:
    def f() -> Depend[str | int, tuple[str, int]]:
        s = yield from depend(str)
        i = yield from depend(int)
        return (s, i)

    def g() -> Depend[str | int | Parallel, tuple[str, int]]:
        result, *_ = yield from parallel(process(f)())
        return result

    with Parallel() as p:
        outer = Abilities().add(0)
        inner = Abilities().add("s").add(p)
        effect = outer.handle(inner.handle(g))()
        assert run(effect) == ("s", 0)


def test_ability_order_with_multiple_abilities() -> None:
    def f() -> Depend[str, str]:
        result = yield from depend(str)
        return result

    outer = Abilities().add("outer")
    inner = Abilities().add("inner")

    effect = outer.handle(inner.handle(f))()
    assert run(effect) == "inner"


def test_multiple_abilities_without_direct_composition() -> None:
    def f() -> Depend[str | int, tuple[str, int]]:
        s = yield from depend(str)
        i = yield from depend(int)
        return (s, i)

    def h() -> Depend[Parallel | str | int, tuple[str, int]]:
        result, *_ = yield from parallel(process(f)())
        return result

    def g() -> Depend[Parallel | str, tuple[str, int]]:
        abilities = Abilities(0)
        s, i = yield from abilities.handle(h)()  # type: ignore
        return (s, i)

    with Parallel() as p:
        assert run(Abilities("s", p).handle(g)()) == ("s", 0)
