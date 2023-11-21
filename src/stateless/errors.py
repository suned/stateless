from typing import Type


class MissingAbilityError(Exception):
    ability: Type[object]
