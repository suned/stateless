from concurrent.futures import Executor, ProcessPoolExecutor
from concurrent.futures.thread import ThreadPoolExecutor
from threading import Event

from stateless import (
    Async,
    Depend,
    Need,
    Success,
    as_type,
    fork,
    run,
    success,
    supply,
    wait,
)


def say_hi() -> Success[str]:
    return success("hi")


def fork_say_hi() -> Depend[Need[Executor] | Async, str]:
    task = yield from fork(say_hi)()
    value = yield from wait(task)
    return value


def test_fork_and_wait() -> None:
    with as_type(Executor)(ThreadPoolExecutor()) as executor:
        assert run(supply(executor)(fork_say_hi)()) == "hi"


def test_fork_still_runs_when_not_waited() -> None:
    event = Event()

    def f() -> Success[None]:
        event.set()
        yield from success(None)

    def g() -> Depend[Need[Executor], None]:
        yield from fork(f)()

    with as_type(Executor)(ThreadPoolExecutor()) as executor:
        effect = supply(executor)(g)()
        run(effect)

    assert event.wait(timeout=1)


def test_wait_coroutine() -> None:
    async def say_hi() -> str:
        return "hi"

    def f() -> Depend[Async, str]:
        value = yield from wait(say_hi())
        return value

    assert run(f()) == "hi"


def test_fork_with_process_executor() -> None:
    with as_type(Executor)(ProcessPoolExecutor()) as executor:
        effect = supply(executor)(fork_say_hi)()
        assert run(effect) == "hi"
