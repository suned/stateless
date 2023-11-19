from typing import (
    TypeVar,
    Callable,
    Type,
    ParamSpec,
    overload,
    Generic,
    Awaitable,
    TypeAlias,
    cast,
)
from collections.abc import Generator
from functools import wraps, lru_cache, partial
from dataclasses import dataclass, field
from types import TracebackType

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


def depend(ability: Type[A]) -> Generator[Type[A], object, A]:
    a = yield ability
    return cast(A, a)


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
class Memoize(Effect[A, E, R]):
    effect: Effect[A, E, R]
    _memoized_result: R | None = field(init=False, default=None)

    def send(self, value: A) -> Type[A] | E:
        if self._memoized_result is not None:
            raise StopIteration(self._memoized_result)
        try:
            return self.effect.send(value)
        except StopIteration as e:
            object.__setattr__(self, "_memoized_result", e.value)
            raise e

    def throw(
        self,
        exc_type: Type[BaseException] | BaseException,
        error: BaseException | object | None = None,
        exc_tb: TracebackType | None = None,
        /,
    ) -> Type[A] | E:
        try:
            return self.effect.throw(exc_type, error, exc_tb)  # type: ignore
        except StopIteration as e:
            object.__setattr__(self, "_memoized_result", e.value)
            raise e


@overload
def memoize(
    f: Callable[P, Effect[A, E, R]],
) -> Callable[P, Effect[A, E, R]]:
    ...


@overload
def memoize(
    *,
    maxsize: int | None = None,
    typed: bool = False,
) -> Callable[[Callable[P, Effect[A, E, R]]], Callable[P, Effect[A, E, R]]]:
    ...


def memoize(  # type: ignore
    f: Callable[P, Effect[A, E, R]] | None = None,
    *,
    maxsize: int | None = None,
    typed: bool = False,
) -> (
    Callable[P, Effect[A, E, R]]
    | Callable[[Callable[P, Effect[A, E, R]]], Callable[P, Effect[A, E, R]]]
):
    if f is None:
        return partial(memoize, maxsize=maxsize, typed=typed)  # type: ignore

    @lru_cache(maxsize=maxsize, typed=typed)
    @wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Effect[A, E, R]:
        return Memoize(f(*args, **kwargs))

    return wrapper  # type: ignore
