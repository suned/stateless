from typing import Callable, ParamSpec, TypeVar, Tuple, Generic
from functools import wraps

from stateless.schedule import Schedule
from stateless.effect import Effect, catch, throw
from stateless.time import Time, sleep

A = TypeVar("A")
A2 = TypeVar("A2")
E = TypeVar("E", bound=Exception)
R = TypeVar("R")
P = ParamSpec("P")


def repeat(
    schedule: Schedule[A],
) -> Callable[
    [Callable[P, Effect[A2, E, R]]],
    Callable[P, Effect[A | A2 | Time, E, Tuple[R, ...]]],
]:
    def decorator(
        f: Callable[P, Effect[A2, E, R]]
    ) -> Callable[P, Effect[A | A2 | Time, E, Tuple[R, ...]]]:
        @wraps(f)
        def wrapper(
            *args: P.args, **kwargs: P.kwargs
        ) -> Effect[A | A2 | Time, E, Tuple[R, ...]]:
            deltas = yield from schedule
            results = []
            for interval in deltas:
                result = yield from catch(f)(*args, **kwargs)
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
    errors: tuple[E, ...]


def retry(
    schedule: Schedule[A],
) -> Callable[
    [Callable[P, Effect[A2, E, R]]],
    Callable[P, Effect[A | A2 | Time, RetryError[E], R]],
]:
    def decorator(
        f: Callable[P, Effect[A2, E, R]]
    ) -> Callable[P, Effect[A | A2 | Time, RetryError[E], R]]:
        @wraps(f)
        def wrapper(
            *args: P.args, **kwargs: P.kwargs
        ) -> Effect[A | A2 | Time, RetryError[E], R]:
            deltas = yield from schedule
            errors = []
            for interval in deltas:
                result = yield from catch(f)(*args, **kwargs)
                match result:
                    case Exception() as error:
                        errors.append(error)
                    case _:
                        return result
                yield from sleep(interval.total_seconds())
            return (yield from throw(RetryError(tuple(errors))))

        return wrapper

    return decorator
