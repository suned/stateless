"""Module for asyncio integration and running effects in parallel."""

import asyncio
from concurrent.futures import Executor, ProcessPoolExecutor
from dataclasses import dataclass
from functools import wraps
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Generic,
    ParamSpec,
    TypeVar,
    cast,
    overload,
)

import cloudpickle

from stateless.ability import Ability
from stateless.effect import Depend, Effect, Success, Try, run
from stateless.need import Need, need

P = ParamSpec("P")
R = TypeVar("R")
A = TypeVar("A", bound=Ability[Any])
E = TypeVar("E", bound=Exception)
B = TypeVar("B")


@dataclass(frozen=True)
class Task(Generic[R]):
    """
    Represents a running task, created by `fork`.

    Wraps an asyncio future for the eventual result.
    """

    future: asyncio.Future[bytes] | asyncio.Future[R]

    async def get_result(self) -> R:
        """Get the result of this task."""
        result = await self.future
        if isinstance(result, bytes):
            return cloudpickle.loads(result)  # type: ignore
        return result


@dataclass(frozen=True)
class Async(Ability[Any]):
    """
    The Async ability.

    Used for integration with asyncio.
    """

    awaitable: Awaitable[Any]


@overload
def fork(
    f: Callable[P, Success[R]],
) -> Callable[P, Depend[Need[Executor], Task[R]]]:
    ...


@overload
def fork(f: Callable[P, Try[E, R]]) -> Callable[P, Depend[Need[Executor], Task[R]]]:
    ...


@overload
def fork(
    f: Callable[P, Depend[Async, R]],
) -> Callable[P, Depend[Need[Executor], Task[R]]]:
    ...


@overload
def fork(
    f: Callable[P, Effect[Async, E, R]],
) -> Callable[P, Depend[Need[Executor], Task[R]]]:
    ...


def fork(
    f: Callable[P, Success[R] | Effect[Async, E, R]],
) -> Callable[P, Depend[Need[Executor], Task[R]]]:
    """
    Run the effect produced by `f` in another thread or process using `Executor`.

    Args:
    ----
        f: Function that produces an effect
    Returns:
        `f` decorated so it runs in a thread or process managed
        by `Executor`

    """

    @wraps(f)
    def decorator(*args: P.args, **kwargs: P.kwargs) -> Depend[Need[Executor], Task[R]]:
        def thread_target() -> R:
            result = run(f(*args, **kwargs))
            return result

        executor = yield from need(Executor)
        loop = asyncio.get_running_loop()
        if isinstance(executor, ProcessPoolExecutor):
            payload = cloudpickle.dumps((f, args, kwargs))
            future = loop.run_in_executor(executor, _process_target, payload)
        else:
            future = loop.run_in_executor(executor, thread_target)  # type: ignore
        return Task(future)

    return decorator


def _process_target(payload: bytes) -> bytes:
    f, args, kwargs = cloudpickle.loads(payload)
    result = run(f(*args, **kwargs))
    return cast(bytes, cloudpickle.dumps(result))


@overload
def wait(target: Coroutine[Any, Any, R]) -> Depend[Async, R]:
    ...


@overload
def wait(target: Task[R]) -> Effect[Async, E, R]:
    ...


def wait(target: Coroutine[Any, Any, R] | Task[R]) -> Effect[Async, E, R]:
    """
    Wait for the result of `target` using the `Async` ability.

    Args:
    ----
        target: The coroutine or task to wait for
    Returns:
        The value produced by `target`.

    """
    # We dont want `Async` to be generic since we don't
    # want to specify handlers for e.g `Async[int]` and `Async[str]`
    # separately. They should be handled by the same handler.
    # Unfortunately that breaks the pattern with `Ability`
    # so `v` here is `Any`
    # idea: don't handle errors in target function, but require that user handles them
    # in their code before forking
    if isinstance(target, Task):
        v = yield from Async(target.get_result())
    else:
        v = yield from Async(target)
    return cast(R, v)
