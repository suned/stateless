from stateless import catch, Depend, Runtime
from stateless.files import Files, read_file
from stateless.console import Console, print_line


def example() -> Depend[Files | Console, None]:
    content = yield from catch(read_file)("foo.py")
    match content:
        case OSError():
            yield from print_line("An error occurred")
        case _:
            yield from print_line(content)


files = Files()
console = Console()
runtime = Runtime().use(files).use(console)
runtime.run(example())
