"""Custom errors for the stateless package."""

from typing import Type


class MissingAbilityError(Exception):
    """Raised when an effect requires an ability that is not available in the runtime thats executing it."""

    ability: Type[object]


class UnhandledAbilityError(Exception):
    """Raised when a handler is unable to handle an ability."""

    pass
