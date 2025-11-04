"""Types and functions for handling abilities."""

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
A = TypeVar("A", covariant=True, bound=Ability[Any])
A2 = TypeVar("A2", bound=Ability[Any])
R = TypeVar("R")
P = ParamSpec("P")


@dataclass(frozen=True)
class Handler(Generic[A]):
    """Handles abilities."""

    # Sadly, complete type safety here requires higher-kinded types.
    handle: Callable[[A], Any]

    @overload
    def __call__(self, f: Callable[P, Depend[A, R]]) -> Callable[P, Success[R]]:
        ...  # pragma: no cover

    @overload
    def __call__(  # pyright: ignore[reportOverlappingOverload]
        self, f: Callable[P, Effect[A, E, R]]
    ) -> Callable[P, Try[E, R]]:
        ...  # pragma: no cover

    @overload
    def __call__(self, f: Callable[P, Depend[A | A2, R]]) -> Callable[P, Depend[A2, R]]:
        ...  # pragma: no cover

    @overload
    def __call__(
        self, f: Callable[P, Effect[A2 | A, E, R]]
    ) -> Callable[P, Effect[A2, E, R]]:
        ...  # pragma: no cover

    def __call__(
        self, f: Callable[P, Effect[A, E, R] | Effect[A | A2, E, R]]
    ) -> Callable[P, Try[E, R] | Effect[A2, E, R]]:
        """
        Decorate `f` as to handle abilities yielded by `f`, or yield them if they can't be handled.

        Args:
        ----
            f: Function to decorate.

        Returns:
        -------
            `f` decorated as to handle its abilities.

        """

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
                            yield error  # type: ignore
                        case ability:
                            try:
                                value = self.handle(ability)  # type: ignore
                            except UnhandledAbilityError:
                                # defer to handlers up the call stack
                                value = yield ability  # type: ignore
                            ability_or_error = effect.send(value)
            except StopIteration as e:
                return cast(R, e.value)

        return decorator


def handle(f: Callable[[A2], Any]) -> Handler[A2]:
    """
    Instantiate handler by inspecting type annotations.

    Args:
    ----
        f: Function that handles an ability. Must be a unary function \
        with its argument annotated as an ability type.

    Returns:
    -------
        `Handler` that handles abilities of the type `f` accepts.

    """
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
    t, *_ = d.values()

    def on(ability: A2) -> Any:
        if not isinstance(ability, t):
            raise UnhandledAbilityError()
        return f(ability)

    return Handler(on)
