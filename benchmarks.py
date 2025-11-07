# ruff: noqa: D100, D103

from functools import reduce
from typing import Any, Callable

from pytest_benchmark.fixture import BenchmarkFixture
from stateless import (
    Ability,
    Depend,
    Handler,
    Need,
    Success,
    handle,
    need,
    run,
    supply,
)
from stateless.errors import UnhandledAbilityError
from typing_extensions import Never


def never_handler(_: Ability[Any]) -> Never:
    raise UnhandledAbilityError()


dummy_handler: Handler[Never] = handle(never_handler)  # type: ignore


def create_effect_chain(chain_length: int, n_yields: int) -> Callable[[], Success[str]]:
    def base() -> Depend[Need[str], str]:
        for i in range(n_yields):
            yield from need(str)
        return "done"

    def wrap_test_handler(
        f: Callable[[], Depend[Need[str], str]],
    ) -> Callable[[], Depend[Need[str], str]]:
        return dummy_handler(f)

    g = reduce(lambda acc, _: wrap_test_handler(acc), range(chain_length - 1), base)

    return supply("")(g)


def test_effect_chain(benchmark: BenchmarkFixture) -> None:
    """Benchmark a long chain of functions using functools.reduce."""

    effect = create_effect_chain(500, 0)()
    benchmark(run, effect)


def test_handler_chain(benchmark: BenchmarkFixture) -> None:
    effect = create_effect_chain(chain_length=500, n_yields=500)()

    benchmark(run, effect)
