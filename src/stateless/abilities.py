from typing import Callable, Generic, Never, ParamSpec, TypeVar, overload

from stateless.effect import Depend, Effect, Success, Try

A = TypeVar("A")
A2 = TypeVar("A2")
R = TypeVar("R")
E = TypeVar("E", bound=Exception)
P = ParamSpec("P")


class Abilities(Generic[A]):
    def __init__(self: "Abilities[Never]"):
        pass

    def add(self, ability: A2) -> "Abilities[A | A2]":
        raise NotImplementedError()

        # These overloads are to help type inference figure
        # out when the error or ability types are "Never".
        # Without them both mypy and pyright seem to have a hard time
        # figuring this out, and often replaces them with "Unknown"
        # in pyright, or "Any" in mypy, and also complaining
        # that assigning the return value must be annotated.
        # With these overloads things seem to work as expected.
        #
        # pyright complains about the order of these overloads, but
        # type inference still succeeds.

        ...

    @overload
    def handle(  # pyright: ignore[reportOverlappingOverload]
        self,
        f: Callable[P, Effect[A, E, R]],
    ) -> Callable[P, Try[E, R]]:
        ...

    @overload
    def handle(self, f: Callable[P, Depend[A, R]]) -> Callable[P, Success[R]]:  # pyright: ignore[reportOverlappingOverload]
        ...

    @overload
    def handle(self, f: Callable[P, Depend[A | A2, R]]) -> Callable[P, Depend[A2, R]]:
        ...

    @overload
    def handle(
        self, f: Callable[P, Effect[A | A2, E, R]]
    ) -> Callable[P, Effect[A2, E, R]]:
        ...

    def handle(
        self, f: Callable[P, Effect[A | A2, E, R] | Depend[A | A2, R]]
    ) -> Callable[P, Effect[A2, E, R] | Depend[A2, R]]:
        raise NotImplementedError()
