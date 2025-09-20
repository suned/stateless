"""Contains the Parallel ability and ability helpers."""

from dataclasses import dataclass
from functools import wraps
from multiprocessing import Manager
from multiprocessing.managers import BaseManager, PoolProxy  # type: ignore
from multiprocessing.pool import ThreadPool
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Callable,
    Generic,
    Literal,
    ParamSpec,
    Sequence,
    Type,
    TypeVar,
    cast,
    overload,
)

import cloudpickle  # type: ignore
from typing_extensions import Never

from stateless.effect import Depend, Effect, Success, run, throw
from stateless.errors import MissingAbilityError

if TYPE_CHECKING:
    from stateless.abilities import Abilities  # pragma: no cover


A = TypeVar("A")
E = TypeVar("E", bound=Exception)
R = TypeVar("R")


@dataclass(frozen=True)
class Task(Generic[A, E, R]):
    """A task that can be run in parallel.

    Captures arguments to functions that return effects
    in order that they can be run in parallel, without concerns
    about serialization and thread-safety of effects.
    """

    f: Callable[..., Effect[A, E, R]]
    args: tuple[object, ...]
    kwargs: dict[str, object]
    use_threads: bool


def _run_task(payload: bytes) -> bytes:
    abilities, task = cast(
        tuple["Abilities[Parallel]", Task[object, Exception, object]],
        cloudpickle.loads(payload),
    )
    ability = abilities.get_ability(Parallel)
    if ability is None:
        return cloudpickle.dumps(MissingAbilityError(Parallel))  # type: ignore
    effect = abilities.handle(task.f)(*task.args, **task.kwargs)
    with ability:
        try:
            result = run(effect)  # type: ignore
        except Exception as e:
            result = e
        return cloudpickle.dumps(result)  # type: ignore


class SuccessTask(Task["Parallel", Never, R]):
    """A task that can be run in parallel.

    Captures arguments to functions that return effects
    in order that they can be run in parallel, remove concerns
    about serialization and thread-safety of effects.
    """


class DependTask(Task[A, Never, R]):
    """A task that can be run in parallel.

    Captures arguments to functions that return effects
    in order that they can be run in parallel, without concerns
    about serialization and thread-safety of effects.
    """


@dataclass(frozen=True, init=False)
class Parallel:
    """The Parallel ability.

    Enables running tasks in parallel using threads and processes.

    Args:
    ----
            thread_pool: The thread pool to use to run tasks in parallel.
            pool: The multiprocessing pool to use to run tasks in parallel. Must be a proxy pool.

    """

    _thread_pool: ThreadPool | None
    _manager: BaseManager | None
    _pool: PoolProxy | None
    state: Literal["init", "entered", "exited"] = "init"
    _owns_thread_pool: bool = True
    _owns_process_pool: bool = True

    @property
    def thread_pool(self) -> ThreadPool:
        """The thread pool used to run tasks in parallel."""

        if self._thread_pool is None:
            object.__setattr__(self, "_thread_pool", ThreadPool())
            self._thread_pool.__enter__()  # type: ignore
        return self._thread_pool  # type: ignore

    @property
    def manager(self) -> BaseManager:
        """The multiprocessing manager used to run tasks in parallel."""

        if self._manager is None:
            object.__setattr__(self, "_manager", Manager())
            self._manager.__enter__()  # type: ignore
        return self._manager  # type: ignore

    @property
    def pool(self) -> PoolProxy:
        """The multiprocessing pool used to run tasks in parallel."""

        if self._pool is None:
            object.__setattr__(self, "_pool", self.manager.Pool())  # type: ignore
            self._pool.__enter__()  # type: ignore
        return self._pool

    def __init__(
        self, thread_pool: ThreadPool | None = None, pool: PoolProxy | None = None
    ):
        object.__setattr__(self, "_thread_pool", thread_pool)
        object.__setattr__(self, "_manager", None)
        object.__setattr__(self, "_pool", pool)

        if thread_pool is not None:
            object.__setattr__(self, "_owns_thread_pool", False)
        if pool is not None:
            object.__setattr__(self, "_owns_process_pool", False)

    def __getstate__(
        self,
    ) -> tuple[
        tuple[int, Callable[..., tuple[object, ...]], tuple[object, ...]] | None,
        PoolProxy,
    ]:
        """
        Get the state of the Parallel ability for pickling.

        Returns
        -------
        tuple[tuple[int, Callable[..., tuple[object, ...]], tuple[object, ...]] | None, PoolProxy]
            A tuple containing the thread pool state (or None) and the process pool proxy.


        """
        if self._thread_pool is None:
            return None, self.pool
        else:
            return (
                (
                    self.thread_pool._processes,  # type: ignore
                    self.thread_pool._initializer,  # type: ignore
                    self.thread_pool._initargs,  # type: ignore
                ),
                self.pool,
            )

    def __setstate__(
        self,
        state: tuple[
            tuple[int, Callable[..., tuple[object, ...]], tuple[object, ...]], PoolProxy
        ],
    ) -> None:
        """
        Set the state of the Parallel ability from pickling.

        Args:
        ----
            state: The state of the Parallel ability obtained using __getstate__.

        """
        thread_pool_args, pool = state
        if thread_pool_args is None:
            object.__setattr__(self, "_thread_pool", None)
        else:
            object.__setattr__(self, "_thread_pool", ThreadPool(*thread_pool_args))

        object.__setattr__(self, "_pool", pool)
        object.__setattr__(self, "_manager", None)
        object.__setattr__(self, "state", "entered")

    def __enter__(self) -> "Parallel":
        """Enter the Parallel ability context."""
        object.__setattr__(self, "state", "entered")
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_value: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None | bool:
        """Exit the Parallel ability context."""

        if self._manager is not None:
            if self._owns_process_pool:
                self._pool.__exit__(exc_type, exc_value, exc_tb)  # type: ignore
            self._manager.__exit__(exc_type, exc_value, exc_tb)
        if self._thread_pool is not None and self._owns_thread_pool:
            self._thread_pool.__exit__(exc_type, exc_value, exc_tb)
        object.__setattr__(self, "_thread_pool", None)
        object.__setattr__(self, "state", "exited")

        return None

    def run_thread_tasks(
        self,
        abilities: "Abilities[object]",
        tasks: Sequence[Task[object, Exception, object]],
    ) -> Sequence[object]:
        """
        Run tasks in parallel using threads.

        Args:
        ----
            abilities: The abilities to run the tasks with.
            tasks: The tasks to run.

        Returns:
        -------
            The results of the tasks.

        """
        self.thread_pool.__enter__()

        def _run_task(task: Task[object, Exception, R]) -> R | Exception:
            effect = abilities.handle(task.f)(*task.args, **task.kwargs)
            try:
                return run(effect)
            except Exception as e:
                return e

        return self.thread_pool.map(_run_task, tasks)

    def run_process_tasks(
        self,
        abilities: "Abilities[object]",
        tasks: Sequence[Task[object, Exception, object]],
    ) -> Sequence[object]:
        """
        Run tasks in parallel using processes.

        Args:
        ----
            abilities: The abilities to run the tasks with.
            tasks: The tasks to run.

        Returns:
        -------
            The results of the tasks.

        """
        payloads: list[bytes] = [cloudpickle.dumps((abilities, task)) for task in tasks]
        return [
            cloudpickle.loads(result) for result in self.pool.map(_run_task, payloads)
        ]

    def run(
        self,
        abilities: "Abilities[object]",
        tasks: tuple[Task[object, Exception, object], ...],
    ) -> tuple[object, ...] | Exception:
        """
        Run tasks in parallel.

        Args:
        ----
            abilities: The abilities to run the tasks with.
            tasks: The tasks to run.

        Returns:
        -------
            The results of the tasks.

        """
        if self.state == "init":
            raise RuntimeError("Parallel must be used as a context manager")
        if self.state == "exited":
            raise RuntimeError("Parallel context manager has already exited")
        thread_tasks_and_indices = [
            (i, task) for i, task in enumerate(tasks) if task.use_threads
        ]

        if thread_tasks_and_indices:
            thread_indices, thread_tasks = zip(*thread_tasks_and_indices)
            thread_results = self.run_thread_tasks(abilities, thread_tasks)
            for result in thread_results:
                if isinstance(result, Exception):
                    return result
        else:
            thread_results = ()
            thread_indices = ()

        cpu_tasks_and_indices = [
            (i, task) for i, task in enumerate(tasks) if not task.use_threads
        ]

        if cpu_tasks_and_indices:
            cpu_indices, cpu_tasks = zip(*cpu_tasks_and_indices)
            cpu_results = self.run_process_tasks(abilities, cpu_tasks)
            for result in cpu_results:
                if isinstance(result, Exception):
                    return result
        else:
            cpu_results = ()
            cpu_indices = ()
        results: list[object] = [None] * len(tasks)
        for i, result in zip(thread_indices, thread_results):
            results[i] = result
        for i, result in zip(cpu_indices, cpu_results):
            results[i] = result
        return tuple(results)


A1 = TypeVar("A1")
A2 = TypeVar("A2")
A3 = TypeVar("A3")
A4 = TypeVar("A4")
A5 = TypeVar("A5")
A6 = TypeVar("A6")
A7 = TypeVar("A7")
E1 = TypeVar("E1", bound=Exception)
E2 = TypeVar("E2", bound=Exception)
E3 = TypeVar("E3", bound=Exception)
E4 = TypeVar("E4", bound=Exception)
E5 = TypeVar("E5", bound=Exception)
E6 = TypeVar("E6", bound=Exception)
E7 = TypeVar("E7", bound=Exception)
R1 = TypeVar("R1")
R2 = TypeVar("R2")
R3 = TypeVar("R3")
R4 = TypeVar("R4")
R5 = TypeVar("R5")
R6 = TypeVar("R6")
R7 = TypeVar("R7")


P = ParamSpec("P")


# I'm not sure why this is overload is necessary, but mypy complains without it
@overload
def process(  # type: ignore
    f: Callable[P, Success[R]],
) -> Callable[P, SuccessTask[R]]:
    ...  # pragma: no cover


@overload
def process(
    f: Callable[P, Depend[A, R]],
) -> Callable[P, DependTask[A, R]]:
    ...  # pragma: no cover


@overload
def process(
    f: Callable[P, Effect[A, E, R]],
) -> Callable[P, Task[A, E, R]]:
    ...  # pragma: no cover


def process(  # type: ignore
    f: Callable[P, Effect[object, Exception, object]],
) -> Callable[P, Task[object, Exception, object]]:
    """
    Create a task that can be run in parallel using processes.

    Args:
    ----
        f: The function to capture as a task.

    Returns:
    -------
        `f` decorated to return a task.

    """

    @wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Task[object, Exception, object]:
        return Task(
            f,
            args,
            kwargs,
            use_threads=False,
        )

    return wrapper


@overload
def thread(  # type: ignore
    f: Callable[P, Success[R]],
) -> Callable[P, SuccessTask[R]]:
    ...  # pragma: no cover


@overload
def thread(
    f: Callable[P, Depend[A, R]],
) -> Callable[P, DependTask[A, R]]:
    ...  # pragma: no cover


@overload
def thread(
    f: Callable[P, Effect[A, E, R]],
) -> Callable[P, Task[A, E, R]]:
    ...  # pragma: no cover


def thread(  # type: ignore
    f: Callable[P, Effect[object, Exception, object]],
) -> Callable[P, Task[object, Exception, object]]:
    """
    Create a task that can be run in parallel using threads.

    Args:
    ----
        f: The function to capture as a task.

    Returns:
    -------
        `f` decorated to return a task.

    """

    @wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Task[object, Exception, object]:
        return Task(
            f,
            args,
            kwargs,
            use_threads=True,
        )

    return wrapper


@overload
def parallel() -> Effect[Parallel, Never, tuple[()]]:
    ...  # pragma: no cover


@overload
def parallel(t1: Task[A1, E1, R1], /) -> Effect[A1 | Parallel, E1, tuple[R1]]:
    ...  # pragma: no cover


@overload
def parallel(
    t1: Task[A1, E1, R1], t2: Task[A2, E2, R2], /
) -> Effect[A1 | A2 | Parallel, E1 | E2, tuple[R1, R2]]:
    ...  # pragma: no cover


@overload
def parallel(
    t1: Task[A1, E1, R1],
    t2: Task[A2, E2, R2],
    t3: Task[A3, E3, R3],
    /,
) -> Effect[A1 | A2 | A3 | Parallel, E1 | E2 | E3, tuple[R1, R2, R3]]:
    ...  # pragma: no cover


@overload
def parallel(
    *tasks: Task[A1, E1, R1],
) -> Effect[A1 | Parallel, E1, tuple[R1, ...]]:
    ...  # pragma: no cover


def parallel(  # type: ignore
    *tasks: Task[object, Exception, object],
) -> Effect[Parallel, Exception, tuple[object, ...]]:
    """
    Run tasks in parallel.

    If any of the tasks yield an exception, the exception is yielded.

    Args:
    ----
        tasks: The tasks to run.

    Returns:
    -------
        The results of the tasks.

    """
    runtime: "Abilities[Parallel]" = cast("Abilities[Parallel]", (yield Parallel))
    ability = runtime.get_ability(Parallel)
    result = ability.run(runtime, tasks)  # type: ignore
    if isinstance(result, Exception):
        return (yield from throw(result))
    else:
        return result
