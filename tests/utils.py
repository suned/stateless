from typing import TypeVar

from stateless import Abilities, Effect, run

R = TypeVar("R")
A = TypeVar("A")


def run_with_abilities(effect: Effect[A, Exception, R], abilities: Abilities[A]) -> R:
    @abilities.handle
    def main() -> Effect[A, Exception, R]:
        result = yield from effect
        return result

    return run(main())
