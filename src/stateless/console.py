from stateless.effect import Depend


class Console:
    def print(self, content: str) -> None:
        print(content)

    def input(self, prompt: str = "") -> str:
        return input(prompt)


def print_line(content: str) -> Depend[Console, None]:
    console = yield Console
    console.print(content)


def read_line(prompt: str = "") -> Depend[Console, str]:
    console: Console = yield Console
    return console.input(prompt)
