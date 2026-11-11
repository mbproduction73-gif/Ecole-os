import pytest

from ecom_os.connectors.base import NotConnectedError
from ecom_os.core.retry import with_retry


def test_retry_then_success():
    calls = []

    @with_retry(attempts=3, sleep=lambda s: None)
    def f():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("boom")
        return "ok"
    assert f() == "ok" and len(calls) == 3


def test_retry_gives_up():
    @with_retry(attempts=2, sleep=lambda s: None)
    def f():
        raise RuntimeError("x")
    with pytest.raises(RuntimeError):
        f()


def test_not_connected_is_not_retried():
    calls = []

    @with_retry(attempts=5, sleep=lambda s: None)
    def f():
        calls.append(1)
        raise NotConnectedError("k")
    with pytest.raises(NotConnectedError):
        f()
    assert len(calls) == 1
