"""Functions for working with effects."""

from functools import wraps
from typing import Any, Callable, Generic, ParamSpec, Tuple, Type, TypeVar

from stateless.ability import Ability
from stateless.async_ import Async
from stateless.effect import Effect, catch_all, throw
from stateless.need import Need
from stateless.schedule import Schedule
from stateless.time import Time, sleep

A = TypeVar("A", bound=Ability[Any])
A2 = TypeVar("A2", bound=Ability[Any])
E = TypeVar("E", bound=Exception)
R = TypeVar("R")
P = ParamSpec("P")


def repeat(
    schedule: Schedule[A],
) -> Callable[
    [Callable[P, Effect[A2, E, R]]],
    Callable[P, Effect[A | A2 | Need[Time] | Async, E, Tuple[R, ...]]],
]:
    """
    Repeat an effect according to a schedule.

    Decorates a function that returns an effect to repeat the effect according to a schedule.
    Repeats the effect until the schedule is exhausted, or an exception is yielded.

    Args:
    ----
        schedule: The schedule to repeat the effect according to.

    Returns:
    -------
        A decorator that repeats the effect according to the schedule.

    """

    def decorator(
        f: Callable[P, Effect[A2, E, R]],
    ) -> Callable[P, Effect[A | A2 | Need[Time] | Async, E, Tuple[R, ...]]]:
        @wraps(f)
        def wrapper(
            *args: P.args, **kwargs: P.kwargs
        ) -> Effect[A | A2 | Need[Time] | Async, E, Tuple[R, ...]]:
            deltas = yield from schedule
            results = []
            for interval in deltas:
                result = yield from catch_all(f)(*args, **kwargs)
                match result:
                    case Exception() as error:
                        return (yield from throw(error))  # type: ignore
                    case _:
                        results.append(result)
                yield from sleep(interval.total_seconds())
            return tuple(results)

        return wrapper

    return decorator


class RetryError(Exception, Generic[E]):
    """An error that contains all the errors from a retry."""

    errors: tuple[E, ...]


def retry(
    schedule: Schedule[A],
) -> Callable[
    [Callable[P, Effect[A2, E, R]]],
    Callable[P, Effect[A | A2 | Need[Time] | Async, RetryError[E], R]],
]:
    """
    Retry an effect according to a schedule.

    Decorates a function that returns an effect to retry the effect according to a schedule.
    Retries the effect until the schedule is exhausted, or the effect returns a value.
    If the effect never returns a value before the schedule is exhausted, a `RetryError` is yielded containing all the errors.

    Args:
    ----
        schedule: The schedule to retry the effect according to.

    Returns:
    -------
        A decorator that retries the effect according to the schedule.

    """

    def decorator(
        f: Callable[P, Effect[A2, E, R]],
    ) -> Callable[P, Effect[A | A2 | Need[Time] | Async, RetryError[E], R]]:
        @wraps(f)
        def wrapper(
            *args: P.args, **kwargs: P.kwargs
        ) -> Effect[A | A2 | Need[Time] | Async, RetryError[E], R]:
            deltas = yield from schedule
            errors = []
            for interval in deltas:
                result = yield from catch_all(f)(*args, **kwargs)
                match result:
                    case Exception() as error:
                        errors.append(error)
                    case _:
                        return result
                yield from sleep(interval.total_seconds())
            return (yield from throw(RetryError(tuple(errors))))

        return wrapper

    return decorator


def as_type(t: Type[R]) -> Callable[[R], R]:
    """
    Create an identity function with additional type information.

    Args:
    ----
        t: The (super)type to consider the result of the identity function
    Returns:
        The identity function.

    """

    def _(v: R) -> R:
        return v

    return _
