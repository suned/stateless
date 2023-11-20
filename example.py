from stateless import Depend, Runtime, catch
from stateless.console import Console, print_line
from stateless.files import Files, read_file


def example() -> Depend[Files | Console, None]:
    content = yield from catch(read_file)("foo.py")
    match content:
        # if you use pyright, this should be:
        # case FileNotFoundError() | PermissionError():
        # since pyright unifies types as their union, and not their supertype
        # (which is what mypy does)
        case OSError():
            yield from print_line("An error occurred")
        case _:
            yield from print_line(content)  # pyright: ignore


files = Files()
console = Console()

runtime = Runtime().use(files).use(console)
runtime.run(example())
