"""Module with classes and functions for providing abililties to effects."""

from dataclasses import dataclass
from functools import wraps
from typing import Callable, Generic, ParamSpec, Type, TypeVar, cast, overload

from typing_extensions import Never

from stateless.constants import PARALLEL_SENTINEL
from stateless.effect import Depend, Effect, Success, Try, run
from stateless.errors import MissingAbilityError

A = TypeVar("A", covariant=True)
A2 = TypeVar("A2")
R = TypeVar("R")
E = TypeVar("E", bound=Exception)
P = ParamSpec("P")


def _cache_key(ability_type: Type[A]) -> str:
    return f"{ability_type.__module__}.{ability_type.__name__}"


@dataclass
class EffectAbility(Generic[A, R]):
    """
    Wrapper for effects passed to Abilities.add_effect.

    Used mainly to distinguish these abilities
    from other abilities at runtime using isinstance
    to tell if an ability requires interpretation
    to get its value.
    """

    effect: Effect[A, Exception, R]


@dataclass(frozen=True, init=False)
class Abilities(Generic[A]):
    """Wraps ability instances and provides them to effects during effect interpretation."""

    _ability_cache: dict[str, A]
    abilities: tuple[A, ...]

    @overload
    def __init__(self: "Abilities[Never]"):
        ...  # pragma: no cover

    @overload
    def __init__(self, *abilities: A):
        ...  # pragma: no cover

    def __init__(self, *abilities: A):
        object.__setattr__(self, "_ability_cache", {})
        object.__setattr__(self, "abilities", abilities)

    def add(self, ability: A2) -> "Abilities[A | A2]":
        """
        Add an ability that can be provided during effect interpration.

        Args:
        ----
            ability: The ability instance to provide
        Returns:
            New instance of Abilities wrapping the ability.

        """
        a = Abilities()
        ability_union = (ability, *self.abilities)
        object.__setattr__(a, "abilities", ability_union)
        return cast(Abilities[A | A2], a)

    def add_effect(
        self,
        ability: Callable[P, Effect[A, Exception, R]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> "Abilities[A | R]":
        """
        Like `Ability.add`, but for abilities that themselves require effects to provide.

        Args:
        ----
            ability: Factory function for getting the effect
            args: args for `ability`
            kwargs: kwargs for `ability`

        """
        a = Abilities()
        effect_ability = EffectAbility(self.handle(ability)(*args, **kwargs))
        ability_union = (effect_ability, *self.abilities)
        object.__setattr__(a, "abilities", ability_union)
        return cast(Abilities[A | R], a)

    def get_ability(self, ability_type: Type[A2]) -> A2 | None:
        """
        Get a wrapped ability instance by type.

        Finds the most recently added ability that is a subtype of `ability_type`
        using `isinstance`, or `None` if no such instance exists.

        Args:
        ----
            ability_type: The ability type to find.

        Returns:
        -------
            Most recently added instance of type `ability_type` or
            `None` if no subclasses of `ability_type` are wrapped.

        """
        cache_key = _cache_key(ability_type)
        if cache_key in self._ability_cache:
            return self._ability_cache[cache_key]  # type: ignore
        for ability in self.abilities:
            # run effects passed as arguments to add_effect
            if isinstance(ability, EffectAbility):
                ability = run(ability.effect)  # pyright: ignore
            if isinstance(ability, ability_type):
                self._ability_cache[cache_key] = ability  # type: ignore
                return ability
        return None

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
    @overload
    def handle(self, f: Callable[P, Depend[A, R]]) -> Callable[P, Success[R]]:
        ...  # pragma: no cover

    @overload
    def handle(  # pyright: ignore
        self,
        f: Callable[P, Effect[A, E, R]],
    ) -> Callable[P, Try[E, R]]:
        ...  # pragma: no cover

    @overload
    def handle(self, f: Callable[P, Depend[A | A2, R]]) -> Callable[P, Depend[A2, R]]:
        ...  # pragma: no cover

    @overload
    def handle(
        self, f: Callable[P, Effect[A | A2, E, R]]
    ) -> Callable[P, Effect[A2, E, R]]:
        ...  # pragma: no cover

    def handle(
        self, f: Callable[P, Effect[A | A2, E, R] | Depend[A | A2, R]]
    ) -> Callable[P, Effect[A2, E, R] | Depend[A2, R]]:
        """
        Handle abilities yielded by the effect returned by `f`.

        Args:
        ----
            f: The function to handle abilities for.

        Returns:
        -------
            f: With its abilities handled.

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
                            ability_or_error = effect.throw(error)
                        case ability_type if ability_type is PARALLEL_SENTINEL:
                            other_abilities = yield ability_type  # type: ignore
                            effect.send((*self.abilities, *other_abilities))
                        case ability_type:
                            ability = self.get_ability(ability_type)
                            if ability is None:
                                # yield the ability to `run` to trigger
                                # missing ability error
                                try:
                                    ability = yield ability_type  # type: ignore
                                except MissingAbilityError as e:
                                    effect.throw(e)
                            ability_or_error = effect.send(ability)
            except StopIteration as e:
                return cast(R, e.value)

        return decorator
