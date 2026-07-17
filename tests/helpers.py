from __future__ import annotations

from dataclasses import dataclass

from src.chaos.model import ScreenContext


@dataclass
class FakeOCRBox:
    name: str
    x: int = 100
    y: int = 100
    width: int = 120
    height: int = 30
    confidence: float = 0.95


def make_context(*texts: str, frame_id: int = 1) -> ScreenContext:
    boxes = [FakeOCRBox(text, x=100, y=50 + index * 60) for index, text in enumerate(texts)]
    return ScreenContext.from_ocr(
        boxes,
        frame_id=frame_id,
        captured_at=float(frame_id),
        width=1920,
        height=1080,
    )


class RecordingExecutor:
    def __init__(self, succeeds: bool = True) -> None:
        self.succeeds = succeeds
        self.actions = []

    def perform(self, action, context) -> bool:
        self.actions.append((action, context.frame_id))
        return self.succeeds
