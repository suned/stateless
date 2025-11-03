"""Ability for dependency injection."""

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
    """The Need ability."""

    t: Type[T]


def need(t: Type[T]) -> Depend[Need[T], T]:
    """
    Create an effect that uses the `Need` ability to return an instance of type `T`.

    Args:
    ----
        t: The type to need.

    Returns:
    -------
        An instance of `t`.

    """
    v = yield from Need(t)
    return v


T1 = TypeVar("T1")
T2 = TypeVar("T2")
T3 = TypeVar("T3")
T4 = TypeVar("T4")
T5 = TypeVar("T5")
T6 = TypeVar("T6")
T7 = TypeVar("T7")
T8 = TypeVar("T8")
T9 = TypeVar("T9")


# Using overloads here since using just variadics would result
# in an inferred return type `Handler[Need[T1 | T2 | ...]]
# which would not eliminate the abilities correctly when using
# Handler.__call__
@overload
def supply(v1: T1, /) -> Handler[Need[T1]]:
    ...  # pragma: no cover


@overload
def supply(v1: T1, v2: T2, /) -> Handler[Need[T1] | Need[T2]]:
    ...  # pragma: no cover


@overload
def supply(v1: T1, v2: T2, v3: T3, /) -> Handler[Need[T1] | Need[T2] | Need[T3]]:
    ...  # pragma: no cover


@overload
def supply(
    v1: T1, v2: T2, v3: T3, v4: T4, /
) -> Handler[Need[T1] | Need[T2] | Need[T3] | Need[T4]]:
    ...  # pragma: no cover


@overload
def supply(
    v1: T1, v2: T2, v3: T3, v4: T4, v5: T5, /
) -> Handler[Need[T1] | Need[T2] | Need[T3] | Need[T4] | Need[T5]]:
    ...  # pragma: no cover


@overload
def supply(
    v1: T1, v2: T2, v3: T3, v4: T4, v5: T5, v6: T6, /
) -> Handler[Need[T1] | Need[T2] | Need[T3] | Need[T4] | Need[T5] | Need[T6]]:
    ...  # pragma: no cover


@overload
def supply(
    v1: T1, v2: T2, v3: T3, v4: T4, v5: T5, v6: T6, v7: T7, /
) -> Handler[
    Need[T1] | Need[T2] | Need[T3] | Need[T4] | Need[T5] | Need[T6] | Need[T7]
]:
    ...  # pragma: no cover


@overload
def supply(
    v1: T1, v2: T2, v3: T3, v4: T4, v5: T5, v6: T6, v7: T7, v8: T8, /
) -> Handler[
    Need[T1]
    | Need[T2]
    | Need[T3]
    | Need[T4]
    | Need[T5]
    | Need[T6]
    | Need[T7]
    | Need[T8]
]:
    ...  # pragma: no cover


@overload
def supply(
    v1: T1, v2: T2, v3: T3, v4: T4, v5: T5, v6: T6, v7: T7, v8: T8, v9: T9, /
) -> Handler[
    Need[T1]
    | Need[T2]
    | Need[T3]
    | Need[T4]
    | Need[T5]
    | Need[T6]
    | Need[T7]
    | Need[T8]
    | Need[T9]
]:
    ...  # pragma: no cover


def supply(  # type: ignore
    first: T1, /, *rest: T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9
) -> Handler[
    Need[T1]
    | Need[T2]
    | Need[T3]
    | Need[T4]
    | Need[T5]
    | Need[T6]
    | Need[T7]
    | Need[T8]
    | Need[T9]
]:
    """
    Handle a `Need` ability by supplying instances of type `T`.

    Args:
    ----
        first: The first instance to supply.
        rest: The remaining instances to supply, variadically.

    Returns:
    -------
        `Handler` that handles `Need[T1] | Need[T2] | ... `.

    """
    instances = (first, *rest)

    def on(ability: Need[T1]) -> T1:
        if not isinstance(ability, Need):
            raise UnhandledAbilityError()
        for instance in instances:
            if isinstance(instance, ability.t):
                return instance
        raise UnhandledAbilityError()

    return Handler(handle=on)
