from dataclasses import dataclass
from typing import Generator, Generic, Self, TypeVar

from stateless.errors import MissingAbilityError

T = TypeVar('T', covariant=True)

@dataclass(frozen=True)
class Ability(Generic[T]):
    def __iter__(self: Self) -> Generator[Self, T, T]:
        try:
            v = yield self
        except MissingAbilityError:
            raise MissingAbilityError(self) from None
        return v
