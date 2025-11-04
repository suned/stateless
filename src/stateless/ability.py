"""Module containing the base ability type."""

from typing import Generator, Generic, TypeVar

from typing_extensions import Self

from stateless.errors import MissingAbilityError

T = TypeVar("T", covariant=True)


class Ability(Generic[T]):
    """The base ability type."""

    def __iter__(self: Self) -> Generator[Self, T, T]:
        """Depend on `self` and return the value of handling `self`."""
        try:
            v = yield self
        except MissingAbilityError:
            raise MissingAbilityError(self) from None
        return v
