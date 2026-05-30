# orchestrator/execution/scheduler.py
import asyncio
import threading
from typing import Awaitable, Optional

class AsyncScheduler:
    """
    Runs an asyncio event loop in a dedicated thread.
    Allows submitting coroutines from any thread.
    """
    def __init__(self):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread is not None:
            return

        def _run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

        # wait until loop is ready
        while self._loop is None:
            pass

    def submit(self, coro: Awaitable) -> "asyncio.Future":
        if self._loop is None:
            raise RuntimeError("AsyncScheduler not started")
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def stop(self) -> None:
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
