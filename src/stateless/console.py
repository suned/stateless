"""Contains the Console ability and ability helpers."""

from typing import Any

from stateless.effect import Depend
from stateless.need import Need, need


class Console:
    """The Console ability."""

    def print(self, content: Any) -> None:
        """Print the given content to stdout.

        Args:
        ----
            content: The content to print.

        """
        print(content)

    def input(self, prompt: str = "") -> str:
        """Read a line from stdin.

        Args:
        ----
            prompt: The prompt to display.

        Returns:
        -------
            The line read from stdin.

        """
        return input(prompt)


def print_line(content: Any) -> Depend[Need[Console], None]:
    """Print the given content to stdout.

    Args:
    ----
        content: The content to print.

    Returns:
    -------
        A Depend that prints the given content.

    """
    console = yield from need(Console)
    console.print(content)


def read_line(prompt: str = "") -> Depend[Need[Console], str]:
    """Read a line from stdin.

    Args:
    ----
        prompt: The prompt to display.

    Returns:
    -------
        A Depend that reads a line from stdin.

    """
    console: Console = yield from need(Console)
    return console.input(prompt)
