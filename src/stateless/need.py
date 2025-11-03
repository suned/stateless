from dataclasses import dataclass
from typing import Any, Type, TypeVar, overload

from typing_extensions import ParamSpec

from stateless.ability import Ability
from stateless.effect import Depend
from stateless.errors import UnhandledAbilityError
from stateless.handler import Handler

T = TypeVar("T", covariant=True)

R = TypeVar("R")
P = ParamSpec("P")
E = TypeVar("E", bound=Exception)
A = TypeVar("A", bound=Ability[Any])


@dataclass(frozen=True)
class Need(Ability[T]):
    t: Type[T]


def need(t: Type[T]) -> Depend[Need[T], T]:
    v = yield from Need(t)
    return v


T1 = TypeVar("T1")
T2 = TypeVar("T2")
T3 = TypeVar("T3")


@overload
def supply(v1: T1, /) -> Handler[Need[T1]]:
    ...  # pragma: no cover


@overload
def supply(v1: T1, v2: T2, /) -> Handler[Need[T1] | Need[T2]]:
    ...  # pragma: no cover


@overload
def supply(v1: T1, v2: T2, v3: T3, /) -> Handler[Need[T1] | Need[T2] | Need[T3]]:
    ...  # pragma: no cover


def supply(first: T1, /, *rest: T2) -> Handler[Need[T1] | Need[T2]]:  # pyright: ignore
    # TODO: combine instances with &, or come up with a better way of handling abilities
    instances = (first, *rest)

    def on(ability: Need[T1]) -> T1:
        if not isinstance(ability, Need) or not isinstance(first, ability.t):
            raise UnhandledAbilityError()
        for instance in instances:
            if isinstance(instance, ability.t):
                return instance
        raise UnhandledAbilityError()

    return Handler(handle=on)
