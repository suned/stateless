from dataclasses import dataclass
from functools import wraps
from typing import Callable, Generic, Never, ParamSpec, Type, TypeVar, cast, overload

from stateless.effect import Depend, Effect, Success, Try, depend
from stateless.errors import MissingAbilityError
from stateless.parallel import Parallel

A = TypeVar("A")
A2 = TypeVar("A2")
R = TypeVar("R")
E = TypeVar("E", bound=Exception)
P = ParamSpec("P")


def _cache_key(ability_type: Type[A]) -> str:
    return f"{ability_type.__module__}.{ability_type.__name__}"


def _get_ability(
    ability_type: Type[A], abilities: tuple[A, ...], ability_cache: dict[str, A]
) -> A:
    cache_key = _cache_key(ability_type)
    if cache_key in ability_cache:
        return ability_cache[cache_key]
    for ability in abilities:
        if isinstance(ability, ability_type):
            ability_cache[cache_key] = ability
            return ability
    raise MissingAbilityError(ability_type)


@dataclass
class EffectAbility(Generic[A, R]):
    ability: Effect[A, Exception, R]


@dataclass(frozen=True, init=False)
class Abilities(Generic[A]):
    abilities: tuple[A, ...] = ()

    def __init__(self: "Abilities[Never]"):
        pass

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
        effect_ability = EffectAbility(ability(*args, **kwargs))
        ability_union = (effect_ability, *self.abilities)
        object.__setattr__(a, "abilities", ability_union)
        return cast(Abilities[A | R], a)

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
    def handle(  # pyright: ignore[reportOverlappingOverload]
        self,
        f: Callable[P, Effect[A, E, R]],
    ) -> Callable[P, Try[E, R]]: ...

    @overload
    def handle(self, f: Callable[P, Depend[A, R]]) -> Callable[P, Success[R]]:  # pyright: ignore[reportOverlappingOverload]
        ...

    @overload
    def handle(
        self, f: Callable[P, Depend[A | A2, R]]
    ) -> Callable[P, Depend[A2, R]]: ...

    @overload
    def handle(
        self, f: Callable[P, Effect[A | A2, E, R]]
    ) -> Callable[P, Effect[A2, E, R]]: ...

    def handle(
        self, f: Callable[P, Effect[A | A2, E, R] | Depend[A | A2, R]]
    ) -> Callable[P, Effect[A2, E, R] | Depend[A2, R]]:
        @wraps(f)
        def decorator(
            *args: P.args, **kwargs: P.kwargs
        ) -> Effect[A2, E, R] | Depend[A2, R]:
            ability_cache = {}
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
                            try:
                                ability = _get_ability(
                                    ability_type, self.abilities, ability_cache
                                )
                            except MissingAbilityError:
                                # Pass up the dependency request to
                                # Abilitity.handle calls higher up the stack
                                try:
                                    ability = yield from depend(ability_type)  # type: ignore
                                except MissingAbilityError as e:
                                    effect.throw(e)
                            ability_or_error = effect.send(ability)
                except StopIteration as e:
                    return cast(R, e.value)

        return decorator
