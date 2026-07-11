from collections import deque
from typing import Deque, List

from .types import RgbSample


class RgbRingBuffer:
    """Time-ordered buffer of RGB samples, evicting anything older than
    `max_seconds` behind the newest sample."""

    def __init__(self, max_seconds: float) -> None:
        self._max_seconds = float(max_seconds)
        self._samples: Deque[RgbSample] = deque()

    def append(self, sample: RgbSample) -> None:
        self._samples.append(sample)
        newest = sample.t
        cutoff = newest - self._max_seconds
        while self._samples and self._samples[0].t < cutoff:
            self._samples.popleft()

    def window(self, now: float, seconds: float) -> List[RgbSample]:
        cutoff = now - seconds
        return [s for s in self._samples if s.t > cutoff]

    def effective_fps(self, now: float, seconds: float) -> float:
        win = self.window(now, seconds)
        if len(win) < 2:
            return 0.0
        span = win[-1].t - win[0].t
        if span <= 0:
            return 0.0
        return (len(win) - 1) / span

    def __len__(self) -> int:
        return len(self._samples)
