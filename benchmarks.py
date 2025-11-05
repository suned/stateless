from functools import reduce
from typing import Callable

from pytest_benchmark.fixture import BenchmarkFixture
from typing_extensions import Never

from stateless import (
    Ability,
    Depend,
    Handler,
    Need,
    Success,
    handle,
    need,
    run,
    success,
    supply,
)
from stateless.errors import UnhandledAbilityError


def create_effect_chain(chain_length: int) -> Callable[[], Success[None]]:
    """Creates a chain using functools.reduce."""

    def yield_from(
        f: Callable[[], Success[None]],
    ) -> Callable[[], Success[None]]:
        def _() -> Success[None]:
            result = yield from f()
            return result

        return _

    # Base function
    def base_function() -> Success[None]:
        result = yield from success(None)
        return result

    # Create chain using reduce
    return reduce(
        lambda acc, _: yield_from(acc), range(chain_length - 1), base_function
    )


def test_effect_chain(benchmark: BenchmarkFixture) -> None:
    """Benchmark a long chain of functions using functools.reduce."""

    effect = create_effect_chain(500)()
    benchmark(run, effect)


def never_handler(_: Ability) -> Never:
    raise UnhandledAbilityError()


dummy_handler: Handler[Never] = handle(never_handler)


def create_handler_chain(chain_length: int) -> Callable[[], Success[str]]:
    def base() -> Depend[Need[str], str]:
        s = yield from need(str)
        return s

    def wrap_test_handler(
        f: Callable[[], Depend[Need[str], str]],
    ) -> Callable[[], Depend[Need[str], str]]:
        return dummy_handler(f)

    g = reduce(lambda acc, _: wrap_test_handler(acc), range(chain_length - 1), base)

    return supply("")(g)


def test_handler_chain(benchmark: BenchmarkFixture) -> None:
    effect = create_handler_chain(500)()

    benchmark(run, effect)
