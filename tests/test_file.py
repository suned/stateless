from unittest.mock import mock_open, patch

from stateless import run, supply
from stateless.files import Files, read_file


def test_read_file() -> None:
    effect = supply(Files())(read_file)("hello.txt")
    with patch("builtins.open", mock_open(read_data="hello")) as open_mock:
        assert run(effect) == "hello"
        open_mock.assert_called_once_with("hello.txt")
