import sys
from dataclasses import dataclass

from pytest import raises
from stateless import Depend, Effect, Need, need, run, supply
from stateless.ability import Ability
from stateless.effect import catch, throws
from stateless.errors import MissingAbilityError
from stateless.handler import handle
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
    def fails() -> Depend[Need[str], None]:
        yield from need(str)
        raise RuntimeError("oops")

    e = fails()
    with raises(RuntimeError, match="oops"):
        run_with_abilities(e, supply(""))


def test_provide_multiple_sub_types() -> None:
    sub: Super = Sub()
    subsub: Super = SubSub()
    abilities = supply(subsub, sub)
    assert run_with_abilities(need(Super), abilities) == SubSub()
    abilities = supply(sub, subsub)
    assert run_with_abilities(need(Super), abilities) == Sub()


def test_missing_dependency() -> None:
    def effect() -> Depend[Need[Super], Super]:
        ability: Super = yield from need(Super)
        return ability

    with raises(MissingAbilityError, match="Super") as info:
        run(effect())  # type: ignore

    # test that the sixth frame is the yield
    # expression in `effect` function above
    # (first is stateless.run(..)
    # second is effect.throw in Runtime.run)
    index = 6 if sys.version_info > (3, 11) else 5
    frame = info.traceback[index]
    assert str(frame.path) == __file__
    assert frame.lineno == effect.__code__.co_firstlineno


def test_simple_dependency() -> None:
    def effect() -> Depend[Need[str], str]:
        ability: str = yield from need(str)
        return ability

    assert run_with_abilities(effect(), supply("hi!")) == "hi!"


def test_simple_failure() -> None:
    def effect() -> Effect[Never, ValueError, None]:
        yield ValueError("oops")
        return

    with raises(ValueError, match="oops"):
        run(effect())


def test_ability_order_with_multiple_abilities() -> None:
    def f() -> Depend[Need[str], str]:
        result = yield from need(str)
        return result

    outer = supply("outer")
    inner = supply("inner")

    effect = outer(inner(f))()
    assert run(effect) == "inner"


def test_compose_handler_with_catch() -> None:
    error = ValueError()

    @throws(ValueError)
    def fail() -> Never:
        raise error

    effect = catch(ValueError)(supply("value")(fail))()
    assert run(effect) == error


def test_handle() -> None:
    class TestAbility(Ability[None]):
        pass

    def no_annotations(_):  # type: ignore
        pass

    def only_return_annotation(_) -> None:  # type: ignore
        pass

    def two_annotations(_: TestAbility, __: str) -> None:
        pass

    with raises(ValueError):
        handle(no_annotations)

    with raises(ValueError):
        handle(only_return_annotation)

    with raises(ValueError):
        handle(two_annotations)  # type: ignore

    target_ability = TestAbility()

    def f() -> Depend[TestAbility, None]:
        yield target_ability

    def handle_test_ability(ability: TestAbility) -> None:
        assert ability == target_ability

    effect = handle(handle_test_ability)(f)()
    run(effect)

    class OtherAbility(Ability[None]):
        pass

    def g() -> Depend[OtherAbility, None]:
        yield OtherAbility()

    with raises(MissingAbilityError):
        effect_that_fails = handle(handle_test_ability)(g)()
        run(effect_that_fails)  # type: ignore
