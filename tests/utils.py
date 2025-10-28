from typing import TypeVar

from stateless import Effect, Handler, run

R = TypeVar("R")
A = TypeVar("A")


def run_with_abilities(effect: Effect[A, Exception, R], abilities: Handler[A]) -> R:
    @abilities
    def main() -> Effect[A, Exception, R]:
        result = yield from effect
        return result

    return run(main())
