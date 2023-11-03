from typing import (
    TypeVar,
    Callable,
    Type,
    ParamSpec,
)
from collections.abc import Generator
from functools import wraps

from typing_extensions import Never


R = TypeVar("R")
A = TypeVar("A", contravariant=True)
E = TypeVar("E", bound=Exception)
P = ParamSpec("P")
E2 = TypeVar("E2", bound=Exception)

Effect = Generator[Type[A] | E, A, R]
Depend = Effect[A, Never, R]
Success = Depend[Never, R]
Try = Generator[E, Never, R]


class NoResult(Exception):
    pass


def success(result: R) -> Success[R]:
    yield None  # type: ignore
    return result


def fail(reason: E) -> Try[E, Never]:
    yield reason
    raise NoResult()


def catch(f: Callable[P, Effect[A, E, R]]) -> Callable[P, Depend[A, E | R]]:
    @wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Depend[A, E | R]:
        try:
            return (yield from f(*args, **kwargs))  # type: ignore
        except Exception as e:
            return e  # type: ignore

    return wrapper


def depend(ability: Type[A]) -> Depend[A, A]:
    return (yield ability)


def absorb(
    *errors: Type[E2],
) -> Callable[[Callable[P, Effect[A, E, R]]], Callable[P, Effect[A, E | E2, R]]]:
    def decorator(f: Callable[P, Effect[A, E, R]]) -> Callable[P, Effect[A, E | E2, R]]:
        @wraps(f)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Effect[A, E | E2, R]:
            try:
                return (yield from f(*args, **kwargs))
            except errors as e:
                return (yield from fail(e))

        return wrapper

    return decorator
