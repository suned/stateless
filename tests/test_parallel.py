import pickle
from multiprocessing import Manager
from multiprocessing.pool import ThreadPool
from typing import Iterator

import cloudpickle  # type: ignore
from pytest import fixture, raises
from stateless import Depend, Effect, Runtime, Success, catch, success, throws
from stateless.parallel import Parallel, _run_task, parallel, process, thread


@fixture(scope="module", name="runtime")
def runtime_fixture() -> Iterator[Runtime[Parallel]]:
    with Parallel() as p:
        yield Runtime().use(p)


def test_error_handling(runtime: Runtime[Parallel]) -> None:
    @throws(ValueError)
    def f() -> Success[str]:
        raise ValueError("error")

    def g() -> Effect[Parallel, ValueError, tuple[str]]:
        result = yield from parallel(thread(f)())
        return result

    result = runtime.run(catch(ValueError)(g)())
    assert isinstance(result, ValueError)
    assert result.args == ("error",)


def test_process_error_handling(runtime: Runtime[Parallel]) -> None:
    @throws(ValueError)
    def f() -> Success[str]:
        raise ValueError("error")

    def g() -> Effect[Parallel, ValueError, tuple[str]]:
        result = yield from parallel(process(f)())
        return result

    result = runtime.run(catch(ValueError)(g)())
    assert isinstance(result, ValueError)
    assert result.args == ("error",)


def test_unhandled_errors(runtime: Runtime[Parallel]) -> None:
    def f() -> Success[str]:
        raise ValueError("error")

    with raises(ValueError, match="error"):
        effect = parallel(thread(f)())
        runtime.run(effect)


def test_pickling() -> None:
    with Parallel() as p:
        assert p._thread_pool is None
        assert p._manager is None
        assert p._pool is None

        p2 = pickle.loads(pickle.dumps(p))

        assert p._pool is not None
        assert p._manager is not None

        assert p2._thread_pool is None
        assert p2._manager is None
        assert p2._pool is not None

        assert p2._pool._id == p._pool._id

        p.thread_pool  # initialize thread pool
        p3 = pickle.loads(pickle.dumps(p))
        assert p3._thread_pool is not None


def test_cpu_effect(runtime: Runtime[Parallel]) -> None:
    @process
    def f() -> Success[str]:
        return success("done")

    effect = parallel(f())
    result = runtime.run(effect)
    assert result == ("done",)


def test_io_effect(runtime: Runtime[Parallel]) -> None:
    @thread
    def f() -> Success[str]:
        return success("done")

    effect = parallel(f())
    result = runtime.run(effect)
    assert result == ("done",)


def ping() -> str:
    return "pong"


def test_yield_from_parallel(runtime: Runtime[Parallel]) -> None:
    def f() -> Success[str]:
        return success("done")

    def g() -> Depend[Parallel, tuple[str, str]]:
        result = yield from parallel(thread(f)(), process(f)())
        return result

    result = runtime.run(g())
    assert result == ("done", "done")


def test_passed_in_resources() -> None:
    with Manager() as manager, manager.Pool() as pool, ThreadPool() as thread_pool:
        with Parallel(thread_pool, pool) as p:
            assert p._manager is None

        # check that Parallel did not close the thread pool or pool
        assert thread_pool.apply(ping) == "pong"
        assert pool.apply(ping) == "pong"


def test_use_before_with() -> None:
    task = thread(success)("done")
    with raises(RuntimeError, match="Parallel must be used as a context manager"):
        Runtime().use(Parallel()).run(parallel(task))  # type: ignore


def test_use_after_with() -> None:
    with Parallel() as p:
        pass

    with raises(RuntimeError, match="Parallel context manager has already exited"):
        Runtime().use(p).run(parallel(thread(success)("done")))  # type: ignore


def test_run_task(runtime: Runtime[Parallel]) -> None:
    def f() -> Success[str]:
        return success("done")

    payload = cloudpickle.dumps((runtime, thread(f)()))
    result = _run_task(payload)
    assert cloudpickle.loads(result) == "done"
