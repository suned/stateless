import time

from stateless.effect import Depend


class Time:
    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def sleep(seconds: float) -> Depend[Time, None]:
    time_ = yield Time
    time_.sleep(seconds)
