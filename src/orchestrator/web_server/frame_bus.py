"""Thread-safe holder for the latest annotated camera frame.

The ROS node (background thread) writes JPEG bytes here; the FastAPI MJPEG
endpoint (main thread / event loop) reads them. Decoupling via this tiny bus
avoids passing ROS objects into the web layer.
"""
import threading
import time
from typing import Optional


class FrameBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jpeg: Optional[bytes] = None
        self._updated_at: float = 0.0
        self._event = threading.Event()

    def set_jpeg(self, data: bytes) -> None:
        with self._lock:
            self._jpeg = data
            self._updated_at = time.time()
        self._event.set()
        self._event.clear()

    def get_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._jpeg

    @property
    def age(self) -> Optional[float]:
        """Seconds since the last frame, or None if no frame has been published."""
        with self._lock:
            if self._updated_at == 0.0:
                return None
            return time.time() - self._updated_at

    def wait_for_new(self, timeout: float = 1.0) -> None:
        self._event.wait(timeout)


# Module-level singleton shared between the ROS node and the web server.
frame_bus = FrameBus()
