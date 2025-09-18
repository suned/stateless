"""Contains the Effect type and core functions for working with effects."""

from collections.abc import Generator
from dataclasses import dataclass, field
from functools import lru_cache, partial, wraps
from types import TracebackType
from typing import Any, Callable, Generic, Type, TypeVar, cast, overload

from typing_extensions import Never, ParamSpec, TypeAlias

R = TypeVar("R")
A = TypeVar("A")
E = TypeVar("E", bound=Exception)
P = ParamSpec("P")
E2 = TypeVar("E2", bound=Exception)

Effect: TypeAlias = Generator[Type[A] | E, Any, R]
Depend: TypeAlias = Generator[Type[A], Any, R]
Success: TypeAlias = Generator[Type[Never], Any, R]
Try: TypeAlias = Generator[E, Any, R]


class NoResultError(Exception):
    """Raised when an effect has no result.

    If this error is raised to user code
    it should be considered a bug in stateless.
    """


def run(effect: Try[Exception, R]) -> R:
    raise NotImplementedError()


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
    yield None  # type: ignore
    return result


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
    def __call__(self, f: Callable[P, Try[E | E2, R]]) -> Callable[P, Try[E2, R]]:
        ...  # pragma: no cover

    @overload
    def __call__(
        self, f: Callable[P, Effect[A, E2 | E, R]]
    ) -> Callable[P, Effect[A, E2, R | E]]:
        ...  # pragma: no cover

    def __call__(
        self, f: Callable[P, Effect[A, E2 | E, R]]
    ) -> Callable[P, Effect[A, E2, R | E]]:
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
    return Catch(*errors)


def catch_all(f: Callable[P, Effect[A, E, R]]) -> Callable[P, Depend[A, E | R]]:
    return Catch(Exception)(f)  # type: ignore


def depend(ability: Type[A]) -> Depend[A, A]:
    """
    Create an effect that yields an ability and returns the ability sent from the runtime.

    Args:
    ----
        ability: The ability to yield.

    Returns:
    -------
        An effect that yields the ability and returns the ability sent from the runtime.

    """
    a = yield ability
    return cast(A, a)


def throws(
    *errors: Type[E2],
) -> Callable[[Callable[P, Effect[A, E, R]]], Callable[P, Effect[A, E | E2, R]]]:
    """
    Decorate functions returning effects by catching exceptions of a certain type and yields them as an effect.

    Args:
    ----
        *errors: The types of exceptions to catch.

    Returns:
    -------
        A decorator that catches exceptions of a certain type from functions returning effects and yields them as an effect.

    """

    def decorator(f: Callable[P, Effect[A, E, R]]) -> Callable[P, Effect[A, E | E2, R]]:
        @wraps(f)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Effect[A, E | E2, R]:
            try:
                return (yield from f(*args, **kwargs))
            except errors as e:  # pyright: ignore
                return (yield from throw(e))

        return wrapper

    return decorator


@dataclass(frozen=True)
class Memoize(Effect[A, E, R]):
    """Effect that memoizes the result of an effect."""

    effect: Effect[A, E, R]
    _memoized_result: R | None = field(init=False, default=None)

    def send(self, value: A) -> Type[A] | E:
        """Send a value to the effect."""

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
        """Throw an exception into the effect."""

        try:
            return self.effect.throw(exc_type, error, exc_tb)  # type: ignore
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


def memoize(  # type: ignore
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
        return partial(memoize, maxsize=maxsize, typed=typed)  # type: ignore

    @lru_cache(maxsize=maxsize, typed=typed)
    @wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Effect[A, E, R]:
        return Memoize(f(*args, **kwargs))

    return wrapper  # type: ignore
