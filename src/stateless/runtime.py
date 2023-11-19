from typing import (
    Generic,
    TypeVar,
    Type,
    Tuple,
    cast,
    overload,
    Literal,
)
from dataclasses import dataclass
from functools import cache
from stateless.parallel import Parallel

from stateless.effect import Effect
from stateless.errors import MissingAbility


A = TypeVar("A", covariant=True)
A2 = TypeVar("A2")
A3 = TypeVar("A3")
R = TypeVar("R")
E = TypeVar("E", bound=Exception)


@cache
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

    @overload
    def run(self, effect: Effect[A, E, R], return_errors: Literal[False] = False) -> R:
        ...

    @overload
    def run(
        self, effect: Effect[A, E, R], return_errors: Literal[True] = True
    ) -> R | E:
        ...

    def run(self, effect: Effect[A, E, R], return_errors: bool = False) -> R | E:
        try:
            ability_or_error = next(effect)

            while True:
                try:
                    match ability_or_error:
                        case None:
                            ability_or_error = effect.send(None)
                        case Exception() as error:
                            try:
                                ability_or_error = effect.throw(error)
                            except type(error) as e:
                                if return_errors and e is error:
                                    return cast(E, e)
                                else:
                                    raise e
                        case ability_type if ability_type is Parallel:
                            ability_or_error = effect.send(self)  # type: ignore
                        case ability_type:
                            ability = self.get_ability(ability_type)
                            ability_or_error = effect.send(ability)
                except MissingAbility as error:
                    ability_or_error = effect.throw(error)
        except StopIteration as e:
            return cast(R, e.value)
