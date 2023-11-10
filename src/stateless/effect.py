from typing import TypeVar, Callable, Type, ParamSpec, overload, Generic, Awaitable
from collections.abc import Generator
from functools import wraps
from dataclasses import dataclass

from typing_extensions import Never


R = TypeVar("R")
A = TypeVar("A", contravariant=True)
E = TypeVar("E", bound=Exception)
P = ParamSpec("P")
E2 = TypeVar("E2", bound=Exception)

# for some reason mypy yields "Expression type contains any" for these aliases
# it doesn't seem to affect the typechecking though
Effect = Generator[Type[A] | E, A, R]  # type: ignore
Depend = Effect[A, Never, R]  # type: ignore
Success = Depend[Never, R]  # type: ignore
Try = Generator[E, Never, R]  # type: ignore


class NoResult(Exception):
    pass


def success(result: R) -> Success[R]:
    yield None  # type: ignore
    return result


def throw(reason: E) -> Try[E, Never]:
    yield reason
    raise NoResult()


def catch(f: Callable[P, Effect[A, E, R]]) -> Callable[P, Depend[A, E | R]]:
    @wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Depend[A, E | R]:
        try:
            effect = f(*args, **kwargs)
            while True:
                ability_or_error = next(effect)
                if isinstance(ability_or_error, Exception):
                    return ability_or_error  # type: ignore
                else:
                    yield ability_or_error
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


@dataclass(frozen=True)
class Async(Generic[R]):
    awaitable: Awaitable[R]


def from_awaitable(awaitable: Awaitable[R]) -> Success[R]:
    return (yield Async(awaitable))  # type: ignore
