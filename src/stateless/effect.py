"""Contains the Effect type and core functions for working with effects."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Generator
from dataclasses import dataclass, field
from functools import lru_cache, partial, wraps
from types import TracebackType
from typing import TYPE_CHECKING, Any, Callable, Generic, Type, TypeVar, cast, overload

from typing_extensions import Never, ParamSpec, TypeAlias

from stateless.ability import Ability
from stateless.errors import MissingAbilityError

if TYPE_CHECKING:
    from stateless.async_ import Async  # pragma: no cover

R = TypeVar("R")
# A is bound to Ability since if A is completely unbound
# type inference is not possible. Specifically
# type checkers can't distinguish between abilities
# and errors in Effect types.
A = TypeVar("A", bound=Ability[Any])
E = TypeVar("E", bound=Exception)
P = ParamSpec("P")
E2 = TypeVar("E2", bound=Exception)

Effect: TypeAlias = Generator[A | E, Any, R]
Depend: TypeAlias = Generator[A, Any, R]
Success: TypeAlias = Generator[Never, Any, R]
Try: TypeAlias = Generator[E, Any, R]


async def run_async(effect: Effect[Async, Exception, R]) -> R:
    """
    Run an effect asynchronously.

    Args:
    ----
        effect: The effect to run
    Returns:
        The result of running `effect`.

    """
    from stateless.async_ import Async

    try:
        ability_or_error = next(effect)
        while True:
            match ability_or_error:
                case Async(awaitable):
                    v = await awaitable
                    ability_or_error = effect.send(v)
                case Exception() as error:
                    # at this point this is an exception
                    # not handled with stateless.catch anywhere
                    ability_or_error = effect.throw(error)
                case ability:
                    # At this point all abilities should be handled,
                    # so any ability request indicates a missing ability
                    ability_or_error = effect.throw(MissingAbilityError(ability))
    except StopIteration as e:
        return cast(R, e.value)


def run(effect: Effect[Async, Exception, R]) -> R:
    """
    Run an effect.

    Args:
    ----
        effect: The effect to run.

    Returns:
    -------
        The result of running `effect`.

    """
    return asyncio.run(run_async(effect))


@dataclass(frozen=True)
class SuccessEffect(Success[R]):
    """Success effect that just returns a constant."""

    value: R

    def send(self, _: object) -> Never:
        """Send an ability to this effect that is ignored."""
        raise StopIteration(self.value)

    if sys.version_info < (3, 12):  # pragma: no cover

        def throw(
            self,
            exc_type: Type[BaseException] | BaseException,
            error: BaseException | object | None = None,
            exc_tb: TracebackType | None = None,
            /,
        ) -> Never:
            """Throw an exception in this effect."""
            raise exc_type
    else:  # pragma: no cover

        def throw(self, value: Exception, /) -> Never:  # type: ignore
            """Throw an exception in this effect."""
            raise value


def success(result: R) -> Success[R]:
    """
    Create an effect that returns a value.

    Args:
    ----
        result: The value to return.

    Returns:
    -------
        An effect that returns the value.

    """
    return SuccessEffect(result)


def throw(reason: E) -> Try[E, Never]:  # type: ignore
    """
    Create an effect that yields an exception.

    Args:
    ----
        reason: The exception to yield.

    Returns:
    -------
        An effect that yields the exception.

    """
    yield reason


# this class exists solely for type inference purposes
# the original design was a number of overloads
# of a function catch: (*E) -> ((**P) -> Effect[A, E | E2, R]) -> (**P) -> Effect[A, E2, R | E]
# but this made it impossible to overload the returned function to correctly handle "Never"
# arguments when ability or error types should be missing
# leading to mypy complaining that return values must be annotated.
# With this design, that does not happen.
@dataclass(frozen=True, init=False)
class Catch(Generic[E]):
    """Provides improved type-checker inference for calls to `catch`."""

    errors: tuple[Type[E], ...]

    @overload
    def __init__(self: "Catch[Never]"):
        ...  # pragma: no cover

    @overload
    def __init__(self, *errors: Type[E]):
        ...  # pragma: no cover

    def __init__(self, *errors: Type[E]):
        object.__setattr__(self, "errors", errors)

    @overload
    def __call__(self, f: Callable[P, Try[E, R]]) -> Callable[P, Success[R | E]]:
        ...  # pragma: no cover

    @overload
    def __call__(  # pyright: ignore[reportOverlappingOverload]
        self, f: Callable[P, Effect[A, E, R]]
    ) -> Callable[P, Depend[A, R | E]]:
        ...  # pragma: no cover

    @overload
    def __call__(self, f: Callable[P, Try[E | E2, R]]) -> Callable[P, Try[E2, E | R]]:
        ...  # pragma: no cover

    @overload
    def __call__(
        self, f: Callable[P, Effect[A, E2 | E, R]]
    ) -> Callable[P, Effect[A, E2, R | E]]:
        ...  # pragma: no cover

    def __call__(
        self, f: Callable[P, Effect[A, E2 | E, R]]
    ) -> Callable[P, Effect[A, E2, R | E]]:
        """
        Catch and yield errors produced by the effect returned by `f`.

        Args:
        ----
            f: The function to catch effects for
        Return:
            `f`, but returning an effect where errors are included in the result type.

        """

        @wraps(f)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Depend[A, E | R]:
            try:
                effect = f(*args, **kwargs)
                ability_or_error = next(effect)
                while True:
                    if isinstance(ability_or_error, self.errors):
                        return ability_or_error
                    else:
                        ability = yield ability_or_error  # type: ignore
                        ability_or_error = effect.send(ability)
            except StopIteration as e:
                return e.value  # type: ignore

        return wrapper


@overload
def catch() -> Catch[Never]:
    ...  # pragma: no cover


@overload
def catch(*errors: Type[E]) -> Catch[E]:
    ...  # pragma: no cover


def catch(*errors: Type[E]) -> Catch[E]:
    """
    Catch `errors` in functions returning effects.

    Args:
    ----
        errors: The error types to catch.

    Returns:
    -------
        Decorator function where `errors` are returned as the result type of effects.

    """
    return Catch(*errors)


def catch_all(f: Callable[P, Effect[A, E, R]]) -> Callable[P, Depend[A, E | R]]:
    """
    Like `catch` but catch all errors yielded by `f`.

    Args:
    ----
        f: The function to catch effects for
    Returns:
        `f`, but returning an effect where errors are included in the result type.

    """
    return Catch(Exception)(f)  # type: ignore


@dataclass(frozen=True)
class Throws(Generic[E2]):
    """Provides improved type inference for `throws`."""

    errors: tuple[Type[E2], ...]

    @overload
    def __call__(self, f: Callable[P, Success[R]]) -> Callable[P, Try[E2, R]]:
        ...

    @overload
    def __call__(  # type: ignore
        self, f: Callable[P, Depend[A, R]]
    ) -> Callable[P, Effect[A, E2, R]]:
        ...

    @overload
    def __call__(self, f: Callable[P, Try[E, R]]) -> Callable[P, Try[E | E2, R]]:
        ...

    @overload
    def __call__(  # type: ignore
        self, f: Callable[P, Effect[A, E, R]]
    ) -> Callable[P, Effect[A, E | E2, R]]:
        ...

    @overload
    def __call__(self, f: Callable[P, R]) -> Callable[P, Try[E2, R]]:
        ...

    def __call__(  # type: ignore
        self, f: Callable[P, Effect[Ability[Any], Exception, R] | R]
    ) -> Effect[Ability[Any], Exception, R]:
        """
        Decorate `f` as to except any instance of `errors` and yield.

        Args:
        ----
            f: The function to decorate.

        Returns:
        -------
            `f` decorated as to except exceptions and yield them.

        """

        @wraps(f)
        def decorator(
            *args: P.args, **kwargs: P.kwargs
        ) -> Effect[Ability[Any], Exception, R]:
            try:
                result = f(*args, **kwargs)
                if isinstance(result, Generator):
                    result = yield from result

                return result  # pyright: ignore
            except self.errors as e:  # pyright: ignore
                return (yield from throw(e))

        return decorator  # type: ignore


def throws(
    *errors: Type[E2],
) -> Throws[E2]:
    """
    Decorate functions returning effects by catching exceptions of a certain type and yields them as an effect.

    Args:
    ----
        *errors: The types of exceptions to catch.

    Returns:
    -------
        A decorator that catches exceptions of a certain type from functions returning effects and yields them as an effect.

    """
    return Throws(errors)


@dataclass(frozen=True)
class Memoize(Effect[A, E, R]):
    """Effect that memoizes the result of an effect."""

    effect: Effect[A, E, R]
    _memoized_result: R | None = field(init=False, default=None)

    def send(self, value: A) -> A | E:
        """Send a value to the effect."""

        if self._memoized_result is not None:
            raise StopIteration(self._memoized_result)
        try:
            return self.effect.send(value)
        except StopIteration as e:
            object.__setattr__(self, "_memoized_result", e.value)
            raise e

    if sys.version_info < (3, 12):  # pragma: no cover

        def throw(
            self,
            exc_type: Type[BaseException] | BaseException,
            error: BaseException | object | None = None,
            exc_tb: TracebackType | None = None,
            /,
        ) -> A | E:
            """Throw an exception into the effect."""

            try:
                return self.effect.throw(exc_type, error, exc_tb)  # type: ignore
            except StopIteration as e:
                object.__setattr__(self, "_memoized_result", e.value)
                raise e
    else:  # pragma: no cover

        def throw(self, value: Exception, /) -> A | E:  # type: ignore
            """Throw an exception into the effect."""

            try:
                return self.effect.throw(value)
            except StopIteration as e:
                object.__setattr__(self, "_memoized_result", e.value)
                raise e


@overload
def memoize(
    f: Callable[P, Effect[A, E, R]],
) -> Callable[P, Effect[A, E, R]]:
    ...  # pragma: no cover


@overload
def memoize(
    *,
    maxsize: int | None = None,
    typed: bool = False,
) -> Callable[[Callable[P, Effect[A, E, R]]], Callable[P, Effect[A, E, R]]]:
    ...  # pragma: no cover


def memoize(
    f: Callable[P, Effect[A, E, R]] | None = None,
    *,
    maxsize: int | None = None,
    typed: bool = False,
) -> (
    Callable[P, Effect[A, E, R]]
    | Callable[[Callable[P, Effect[A, E, R]]], Callable[P, Effect[A, E, R]]]
):
    """Memoize a function that returns an effect.

    Args:
    ----
        f: The function to memoize.
        maxsize: The maximum size of the cache.
        typed: Whether to use typed caching.

    Returns:
    -------
        The memoized function.

    """
    if f is None:
        return partial(memoize, maxsize=maxsize, typed=typed)  # pyright: ignore

    @lru_cache(maxsize=maxsize, typed=typed)
    @wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Effect[A, E, R]:
        return Memoize(f(*args, **kwargs))

    return wrapper  # type: ignore
