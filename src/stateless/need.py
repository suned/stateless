from dataclasses import dataclass
from typing import TypeVar, Type, Callable, Generic, overload, Never
from typing_extensions import ParamSpec

from stateless.ability import Ability
from stateless.handler import Handler
from stateless.effect import Depend, Effect, Try, Success
from stateless.errors import UnhandledAbilityError


T = TypeVar('T', covariant=True)
T2 = TypeVar('T2')
T3 = TypeVar('T3')
R = TypeVar('R')
P = ParamSpec('P')
E = TypeVar('E', bound=Exception)
A = TypeVar('A', bound=Ability)


@dataclass(frozen=True)
class Need(Ability[T]):
    t: Type[T]



def need(t: Type[T]) -> Depend[Need[T], T]:
    v = yield from Need(t)
    return v

@overload
def supply(v1: T, /) -> Handler[Need[T]]:
    ...  # pragma: no cover

@overload
def supply(v1: T, v2: T2, /) -> Handler[Need[T] | Need[T2]]:
    ...  # pragma: no cover

@overload
def supply(v1: T, v2: T2, v3: T3, /) -> Handler[Need[T] | Need[T2] | Need[T3]]:
    ...  # pragma: no cover


def supply(first: T, /, *rest: T2) -> Handler[Need[T] | Need[T2]]:
    # TODO: combine instances with &, or come up with a better way of handling abilities
    instances = (first, *rest)

    def on(ability: Need[T]) -> T:
        if not isinstance(ability, Need) or not isinstance(first, ability.t):
            raise UnhandledAbilityError()
        for instance in instances:
            if isinstance(instance, ability.t):
                return instance

    return Handler(on=on)
