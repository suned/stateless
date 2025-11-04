from typing import Any, TypeVar

from stateless import Effect, Handler, run
from stateless.ability import Ability

R = TypeVar("R")
A = TypeVar("A", bound=Ability[Any])


def run_with_abilities(effect: Effect[A, Exception, R], abilities: Handler[A]) -> R:
    @abilities
    def main() -> Effect[A, Exception, R]:
        result = yield from effect
        return result

    return run(main())
