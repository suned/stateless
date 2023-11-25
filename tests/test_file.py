from unittest.mock import mock_open, patch

from stateless import Runtime
from stateless.files import Files, read_file


def test_read_file() -> None:
    with patch("builtins.open", mock_open(read_data="hello")) as open_mock:
        assert Runtime().use(Files()).run(read_file("hello.txt")) == "hello"
        open_mock.assert_called_once_with("hello.txt")
