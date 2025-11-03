import asyncio
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from concurrent.futures.thread import ThreadPoolExecutor
from dataclasses import dataclass
from functools import wraps
from types import TracebackType
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
    future: asyncio.Future[bytes] | asyncio.Future[R]

    async def get_result(self) -> R:
        result = await self.future
        if isinstance(result, bytes):
            return cloudpickle.loads(result)  # type: ignore
        return result


@dataclass(frozen=True)
class Async(Ability[Any]):
    awaitable: Awaitable[Any]


# this exists only for type inference purposes,
# specifally that `Need[Executor]` can be
# eliminated by handling the need ability
# with either a Process- or ThreadPoolExecutor
@dataclass(frozen=True, init=False)
class Executor:
    executor: ThreadPoolExecutor | ProcessPoolExecutor

    def __init__(
        self, executor: ThreadPoolExecutor | ProcessPoolExecutor | None = None
    ):
        if not executor:
            executor = ThreadPoolExecutor()

        object.__setattr__(self, "executor", executor)

    def __enter__(self) -> "Executor":
        self.executor.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.executor.__exit__(exc_type, exc_val, exc_tb)


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
    @wraps(f)
    def decorator(*args: P.args, **kwargs: P.kwargs) -> Depend[Need[Executor], Task[R]]:
        def thread_target() -> R:
            result = run(f(*args, **kwargs))
            return result

        executor = yield from need(Executor)
        loop = asyncio.get_running_loop()
        if isinstance(executor.executor, ProcessPoolExecutor):
            payload = cloudpickle.dumps((f, args, kwargs))
            future = loop.run_in_executor(executor.executor, process_target, payload)
        else:
            future = loop.run_in_executor(executor.executor, thread_target)  # type: ignore
        return Task(future)

    return decorator


def process_target(payload: bytes) -> bytes:
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
