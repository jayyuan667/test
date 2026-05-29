# -*- coding: utf-8 -*-
"""Lightweight pipeline observability -- timing and step tracking."""

import time
import functools
from contextlib import contextmanager
from typing import Callable


def track_step(step_name: str):
    """Decorator that logs step timing and outcome."""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            started = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = round(time.time() - started, 2)
                print(f"[OBSERVE] {step_name} completed in {elapsed}s")
                return result
            except Exception as e:
                elapsed = round(time.time() - started, 2)
                print(f"[OBSERVE] {step_name} FAILED after {elapsed}s: {e}")
                raise
        return wrapper
    return decorator


@contextmanager
def time_block(name: str):
    """Context manager for timing a block of code."""
    start = time.time()
    try:
        yield
    finally:
        elapsed = round(time.time() - start, 2)
        print(f"[OBSERVE] {name} took {elapsed}s")
