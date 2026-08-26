import pytest

from services.rate_limit import RateLimiter
from utils.time import parse_timestamp, progress_bar


def test_parse_timestamp():
    assert parse_timestamp("90") == 90
    assert parse_timestamp("1:32") == 92
    assert parse_timestamp("1:02:03") == 3723


@pytest.mark.parametrize("value", ["1:60", "x", "1:2:3", "-1"])
def test_parse_timestamp_rejects_invalid(value):
    with pytest.raises(ValueError):
        parse_timestamp(value)


def test_progress_bar_is_bounded():
    assert progress_bar(50, 100).count("●") == 1
    assert len(progress_bar(1000, 100)) == 18


def test_rate_limiter_is_per_user_and_bucket():
    limiter = RateLimiter()
    assert limiter.allow(1, "search", 1)
    assert not limiter.allow(1, "search", 1)
    assert limiter.allow(2, "search", 1)
    assert limiter.allow(1, "play", 1)
