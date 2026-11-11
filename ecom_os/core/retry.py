"""Reprise après erreur : exécute une fonction avec nouvelles tentatives et backoff."""
import functools
import time

from .logs import get_logger


class NonRetryableError(Exception):
    """Erreur à ne pas retenter (ex. intégration non connectée, permission refusée)."""


def with_retry(fn=None, *, attempts: int = 3, base_delay: float = 1.0, max_delay: float = 30.0,
               retry_on: tuple = (Exception,), sleep=time.sleep):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last = None
            for i in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except NonRetryableError:
                    raise
                except retry_on as exc:  # noqa: PERF203
                    last = exc
                    get_logger().warning("Tentative %s/%s échouée pour %s : %s", i, attempts, func.__name__, exc)
                    if i < attempts:
                        sleep(min(max_delay, base_delay * (2 ** (i - 1))))
            raise last
        return wrapper
    if fn is not None:
        return decorator(fn)
    return decorator
