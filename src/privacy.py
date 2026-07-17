from __future__ import annotations

from typing import Any


def redact_bottom_right(frame: Any) -> Any:
    """Mask the likely account/UID area in screenshots saved by the framework."""
    if frame is None or not hasattr(frame, "shape") or len(frame.shape) < 2:
        return frame

    height, width = frame.shape[:2]
    x = int(width * 0.86)
    y = int(height * 0.965)
    frame[y:height, x:width] = 0
    return frame
