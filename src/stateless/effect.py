from typing import (
    TypeVar,
    Callable,
    Type,
    ParamSpec,
    overload,
    Generic,
    Awaitable,
    TypeAlias,
)
from collections.abc import Generator
from functools import wraps
from dataclasses import dataclass

from typing_extensions import Never


R = TypeVar("R")
A = TypeVar("A", contravariant=True)
E = TypeVar("E", bound=Exception)
P = ParamSpec("P")
E2 = TypeVar("E2", bound=Exception)

Effect: TypeAlias = Generator[Type[A] | E, A, R]
Depend: TypeAlias = Generator[Type[A], A, R]
Success: TypeAlias = Depend[Never, R]
Try: TypeAlias = Generator[E, Never, R]


class NoResult(Exception):
    pass


def success(result: R) -> Success[R]:
    yield None  # type: ignore
    return result


def throw(reason: E) -> Try[E, Never]:  # type: ignore
    yield reason


def catch(f: Callable[P, Effect[A, E, R]]) -> Callable[P, Depend[A, E | R]]:
    @wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Depend[A, E | R]:
        try:
            effect = f(*args, **kwargs)
            ability_or_error = next(effect)
            while True:
                if isinstance(ability_or_error, Exception):
                    return ability_or_error  # type: ignore
                else:
                    ability = yield ability_or_error
                    ability_or_error = effect.send(ability)
        except StopIteration as e:
            return e.value  # type: ignore

    return wrapper


def depend(ability: Type[A]) -> Depend[A, A]:
    return (yield ability)


def throws(
    *errors: Type[E2],
) -> Callable[[Callable[P, Effect[A, E, R]]], Callable[P, Effect[A, E | E2, R]]]:
    def decorator(f: Callable[P, Effect[A, E, R]]) -> Callable[P, Effect[A, E | E2, R]]:
        @wraps(f)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Effect[A, E | E2, R]:
            try:
                return (yield from f(*args, **kwargs))
            except errors as e:
                return (yield from throw(e))

        return wrapper

    return decorator
