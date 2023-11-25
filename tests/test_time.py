from unittest.mock import MagicMock, patch

from stateless import Runtime
from stateless.time import Time, sleep


@patch("stateless.time.time.sleep")
def test_sleep(sleep_mock: MagicMock) -> None:
    Runtime().use(Time()).run(sleep(1))
    sleep_mock.assert_called_once_with(1)
