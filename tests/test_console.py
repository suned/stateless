from unittest.mock import MagicMock, patch

from pytest import CaptureFixture
from stateless import Runtime
from stateless.console import Console, print_line, read_line


def test_print_line(capsys: CaptureFixture[str]) -> None:
    console = Console()
    Runtime().use(console).run(print_line("hello"))
    captured = capsys.readouterr()
    assert captured.out == "hello\n"


@patch("stateless.console.input", return_value="hello")
def test_read_line(input_mock: MagicMock) -> None:
    console = Console()
    assert Runtime().use(console).run(read_line("hi!")) == "hello"
    input_mock.assert_called_once_with("hi!")
