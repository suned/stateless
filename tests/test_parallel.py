import pickle
from multiprocessing import Manager
from multiprocessing.pool import ThreadPool
from typing import Iterator

from pytest import fixture, raises

from stateless import Depend, Effect, Runtime, Success, catch, success, throws
from stateless.parallel import Parallel, parallel, process, thread


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

    result = runtime.run(catch(g)())
    assert isinstance(result, ValueError)
    assert result.args == ("error",)


def test_unhandled_errors(runtime: Runtime[Parallel]) -> None:
    def f() -> Success[str]:
        raise ValueError("error")

    with raises(ValueError, match="error"):
        # todo: why does this need a type annotation?
        effect: Depend[Parallel, tuple[str]] = parallel(thread(f)())  # type: ignore
        # todo: there is a bug in mypy's type inference here
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


def test_cpu_effect(runtime: Runtime[Parallel]) -> None:
    @process
    def f() -> Success[str]:
        return success("done")

    result = runtime.run(parallel(f()))  # type: ignore
    # todo: there is a bug in mypy's type inference here
    assert result == ("done",)


def test_io_effect(runtime: Runtime[Parallel]) -> None:
    @thread
    def f() -> Success[str]:
        return success("done")

    result = runtime.run(parallel(f()))  # type: ignore
    # todo: there is a bug in mypy's type inference here
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
    with Manager() as manager, manager.Pool() as pool, ThreadPool() as thread_pool:  # type: ignore
        with Parallel(thread_pool, pool) as p:
            assert p._manager is None

        # check that Parallel did not close the thread pool or pool
        assert thread_pool.apply(ping) == "pong"
        assert pool.apply(ping) == "pong"
