"""Root pytest configuration. Shared fixtures land here as they emerge."""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture(scope="session", autouse=True)
def _disable_asyncio_auto_create_loop() -> None:
    """Disable the default asyncio policy's auto-create branch in get_event_loop.

    Sprint 8 root cause (PYTHONTRACEMALLOC=10):
    pytest-asyncio's ``_get_event_loop_no_warn`` calls
    ``asyncio.get_event_loop()`` which on Python 3.12 still auto-creates a
    fresh ``_UnixSelectorEventLoop`` when the default policy's
    ``_local._set_called == False``. Each orphan loop carries two unclosed
    self-pipe sockets (``socket.socketpair()``) and surfaces as
    ``PytestUnraisableExceptionWarning`` at GC time, failing a random later
    test under ``filterwarnings=error``.

    Forcing ``_set_called=True`` once at session start drops the auto-create
    branch — future ``get_event_loop()`` calls without an explicit
    ``set_event_loop`` raise ``RuntimeError`` instead of silently creating
    an orphan. pytest-asyncio's ``_temporary_event_loop_policy`` already
    handles ``RuntimeError`` (``old_loop = None``), so the contract is
    preserved. Async tests still get a fresh loop via the Runner's explicit
    ``events.set_event_loop`` path; sync tests calling ``asyncio.run`` are
    unaffected (their internal Runner does the same).
    """
    policy = asyncio.get_event_loop_policy()
    policy._local._set_called = True  # type: ignore[attr-defined]
