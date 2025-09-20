from unittest.mock import MagicMock, patch

from pytest import CaptureFixture
from stateless import Abilities, run
from stateless.console import Console, print_line, read_line


def test_print_line(capsys: CaptureFixture[str]) -> None:
    abilities = Abilities().add(Console())
    effect = abilities.handle(print_line)("hello")
    run(effect)
    captured = capsys.readouterr()
    assert captured.out == "hello\n"


@patch("stateless.console.input", return_value="hello")
def test_read_line(input_mock: MagicMock) -> None:
    abilities = Abilities().add(Console())
    effect = abilities.handle(read_line)("hi!")
    assert run(effect) == "hello"
    input_mock.assert_called_once_with("hi!")
