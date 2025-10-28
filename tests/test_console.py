from unittest.mock import MagicMock, patch

from pytest import CaptureFixture
from stateless import run, supply
from stateless.console import Console, print_line, read_line


def test_print_line(capsys: CaptureFixture[str]) -> None:
    handle = supply(Console())
    effect = handle(print_line)("hello")
    run(effect)
    captured = capsys.readouterr()
    assert captured.out == "hello\n"


@patch("stateless.console.input", return_value="hello")
def test_read_line(input_mock: MagicMock) -> None:
    handle = supply(Console())
    effect = handle(read_line)("hi!")
    assert run(effect) == "hello"
    input_mock.assert_called_once_with("hi!")
