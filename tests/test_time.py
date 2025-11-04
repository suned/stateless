from unittest.mock import MagicMock, patch

from stateless import run, supply
from stateless.time import Time, sleep


@patch("stateless.time.asyncio.sleep")
def test_sleep(sleep_mock: MagicMock) -> None:
    effect = supply(Time())(sleep)(1)
    run(effect)
    sleep_mock.assert_called_once_with(1)
