from typing import Type


class MissingAbility(Exception):
    ability: Type[object]
