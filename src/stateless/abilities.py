from dataclasses import dataclass
from functools import wraps
from typing import Callable, Generic, Never, ParamSpec, Type, TypeVar, cast, overload

from stateless.effect import Depend, Effect, Success, Try, run
from stateless.errors import MissingAbilityError
from stateless.parallel import Parallel

A = TypeVar("A", covariant=True)
A2 = TypeVar("A2")
R = TypeVar("R")
E = TypeVar("E", bound=Exception)
P = ParamSpec("P")


def _cache_key(ability_type: Type[A]) -> str:
    return f"{ability_type.__module__}.{ability_type.__name__}"


@dataclass
class EffectAbility(Generic[A, R]):
    effect: Effect[A, Exception, R]


@dataclass(frozen=True, init=False)
class Abilities(Generic[A]):
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
        a = Abilities()
        effect_ability = EffectAbility(self.handle(ability)(*args, **kwargs))
        ability_union = (effect_ability, *self.abilities)
        object.__setattr__(a, "abilities", ability_union)
        return cast(Abilities[A | R], a)

    def get_ability(self, ability_type: Type[A2]) -> A2 | None:
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
        ...   # pragma: no cover

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
        @wraps(f)
        def decorator(
            *args: P.args, **kwargs: P.kwargs
        ) -> Effect[A2, E, R] | Depend[A2, R]:
            effect = f(*args, **kwargs)
            ability_or_error = next(effect)

            while True:
                try:
                    match ability_or_error:
                        case None:
                            # special case for implementation
                            # of `stateless.success`
                            ability_or_error = effect.send(None)
                        case Exception() as error:
                            ability_or_error = effect.throw(error)
                        case ability_type if ability_type is Parallel:
                            ability_or_error = effect.send(self)
                        case ability_type:
                            ability = self.get_ability(ability_type)
                            if ability is None:
                                # Pass up the dependency request to
                                # Abilitities.handle calls higher up the stack
                                try:
                                    ability = yield ability_type  # type: ignore
                                except MissingAbilityError as e:
                                    effect.throw(e)
                            ability_or_error = effect.send(ability)
                except StopIteration as e:
                    return cast(R, e.value)

        return decorator
