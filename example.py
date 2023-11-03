from stateless import catch, Effect, Runtime
from stateless.files import Files, read_file, LiveFiles
from stateless.console import Console, print_line, LiveConsole


def test() -> Effect[Files | Console, OSError, None]:
    content = yield from catch(read_file)("foo.py")
    match content:
        case OSError():
            yield from print_line("File not found")
        case _:
            yield from print_line(content)


files: Files = LiveFiles()
console: Console = LiveConsole()
runtime = Runtime().use(files).use(console)
runtime.run(test())
