from typing import Generic, TypeVar, Any, Type, Tuple, Dict, Callable, Protocol, cast
from dataclasses import dataclass
from functools import cache
import asyncio

from stateless.effect import Effect, Async


A = TypeVar("A", covariant=True)
A2 = TypeVar("A2")
A3 = TypeVar("A3")
R = TypeVar("R")
E = TypeVar("E", bound=Exception)


class MissingAbility(Exception):
    ability: Type[Any]


class Exhausted(Exception):
    pass


@cache  # type: ignore
def _get_ability(ability_type: Type[A], abilities: Tuple[A, ...]) -> A:
    for ability in abilities:
        if isinstance(ability, ability_type):
            return ability
    raise MissingAbility(ability_type)


@dataclass(frozen=True)
class Runtime(Generic[A]):
    abilities: tuple[A, ...] = ()

    def use(self, ability: A2) -> "Runtime[A | A2]":
        return Runtime((ability,) + self.abilities)

    def get_ability(self, ability_type: Type[A]) -> A:
        return _get_ability(ability_type, self.abilities)  # type: ignore

    def run(self, effect: Effect[A, E, R]) -> R:
        try:
            ability_or_error = next(effect)

            while True:
                try:
                    match ability_or_error:
                        case None:
                            ability_or_error = effect.send(None)
                        case Exception() as error:
                            ability_or_error = effect.throw(error)
                        case Async(awaitable):
                            try:
                                result = asyncio.run(awaitable)
                            except Exception as e:
                                ability_or_error = effect.throw(e)
                            else:
                                ability_or_error = effect.send(result)
                        case _ as ability_type:
                            ability = self.get_ability(ability_type)
                            ability_or_error = effect.send(ability)
                except MissingAbility as error:
                    ability_or_error = effect.throw(error)
        except StopIteration as e:
            return cast(R, e.value)
