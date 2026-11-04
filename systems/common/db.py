"""Tiny database helper shared by the Contoso systems.

Each request opens its own connection, as many older systems do.
(That is deliberate: connection overhead is one of the performance problems
you will diagnose later.)
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row


def dsn() -> str:
    return os.environ["DATABASE_URL"]


@contextmanager
def connect():
    with psycopg.connect(dsn(), row_factory=dict_row, autocommit=False) as conn:
        yield conn


def wait_for_db(timeout_seconds: int = 60) -> None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            with psycopg.connect(dsn(), connect_timeout=3):
                return
        except psycopg.OperationalError:
            if time.monotonic() > deadline:
                raise
            time.sleep(2)
