from unittest.mock import MagicMock, patch

from stateless import Abilities, run
from stateless.time import Time, sleep


@patch("stateless.time.time.sleep")
def test_sleep(sleep_mock: MagicMock) -> None:
    effect = Abilities().add(Time()).handle(sleep)(1)
    run(effect)
    sleep_mock.assert_called_once_with(1)
