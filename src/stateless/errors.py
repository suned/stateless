"""Custom errors for the stateless package."""

from typing import Type


class MissingAbilityError(Exception):
    ability: Type[object]
