from dataclasses import dataclass
from functools import wraps
from typing import (
    Any,
    Callable,
    Generic,
    ParamSpec,
    TypeVar,
    cast,
    get_type_hints,
    overload,
)

from stateless.ability import Ability
from stateless.effect import Depend, Effect, Success, Try
from stateless.errors import UnhandledAbilityError

E = TypeVar("E", bound=Exception)
A = TypeVar("A", covariant=True, bound=Ability)
A2 = TypeVar("A2", bound=Ability)
R = TypeVar("R")
P = ParamSpec("P")


@dataclass(frozen=True)
class Handler(Generic[A]):
    # Sadly, complete type safety here requires higher-kinded types.
    on: Callable[[A], Any]

    @overload
    def __call__(self, f: Callable[P, Depend[A, R]]) -> Callable[P, Success[R]]:
        ...  # pragma: no cover

    @overload
    def __call__(self, f: Callable[P, Depend[A | A2, R]]) -> Callable[P, Depend[A2, R]]:  # pyright: ignore[reportOverlappingOverload]
        ...  # pragma: no cover

    @overload
    def __call__(self, f: Callable[P, Effect[A, E, R]]) -> Callable[P, Try[E, R]]:
        ...  # pragma: no cover

    @overload
    def __call__(
        self, f: Callable[P, Effect[A2 | A, E, R]]
    ) -> Callable[P, Effect[A2, E, R]]:
        ...  # pragma: no cover

    def __call__(
        self, f: Callable[P, Effect[A, E, R] | Effect[A | A2, E, R]]
    ) -> Callable[P, Try[E, R] | Effect[A2, E, R]]:
        @wraps(f)
        def decorator(
            *args: P.args, **kwargs: P.kwargs
        ) -> Effect[A2, E, R] | Depend[A2, R]:
            effect = f(*args, **kwargs)
            try:
                ability_or_error = next(effect)

                while True:
                    match ability_or_error:
                        case Exception() as error:
                            value = yield error
                            ability_or_error = effect.send(value)
                        case ability:
                            try:
                                value = self.on(ability)
                            except UnhandledAbilityError:
                                # defer to handlers up the call stack
                                value = yield ability  # type: ignore
                            ability_or_error = effect.send(value)
            except StopIteration as e:
                return cast(R, e.value)

        return decorator


def handle(f: Callable[[A], Any]) -> Handler[A]:
    d = get_type_hints(f)
    if len(d) == 0:
        raise ValueError(f"Handler function {f} was not annotated.")
    if "return" in d:
        d.pop("return")

    if len(d) == 0:
        raise ValueError(
            f"Not enough annotated arguments to handler function '{f}'. Expected 1, got 0. "
            f"'handle' uses type annotations to match handlers with abilities, so the argument to '{f}' must "
            "be annotated."
        )
    if len(d) > 1:
        raise ValueError(
            f"Too many annotated arguments to handler function '{f}'. Expected 1, got {len(d)}. "
            f"'handle' uses type annotations to match handlers with abilities, so '{f}' must have exactly "
            "1 annotated argument."
        )
    t = list(d.values())[0]

    def on(ability: A) -> Any:
        if not isinstance(ability, t):
            raise UnhandledAbilityError()
        return f(ability)

    return Handler(on)
