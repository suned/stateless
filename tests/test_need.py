import sys

from pytest import raises
from stateless import Depend, Need, need, run, supply
from stateless.errors import MissingAbilityError

from tests.utils import run_with_abilities


def test_need() -> None:
    effect = need(int)
    assert run_with_abilities(effect, supply(0)) == 0


def test_need_missing_ability() -> None:
    def effect() -> Depend[Need[int], int]:
        return (yield from need(int))

    with raises(MissingAbilityError) as info:
        run(effect())  # type: ignore

    frame = info.traceback[0]
    assert str(frame.path) == __file__
    assert frame.lineno == test_need_missing_ability.__code__.co_firstlineno + 4

    index = 6 if sys.version_info > (3, 11) else 5
    frame = info.traceback[index]
    assert str(frame.path) == __file__
    assert frame.lineno == test_need_missing_ability.__code__.co_firstlineno + 1


def test_missing_ability_with_supply() -> None:
    with raises(MissingAbilityError):
        effect = supply("")(lambda: need(int))()
        run(effect)  # type: ignore
