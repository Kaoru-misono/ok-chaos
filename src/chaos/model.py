from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from src.chaos.text import normalize_text, text_matches


@dataclass(frozen=True, slots=True)
class TextBox:
    text: str
    x: int
    y: int
    width: int
    height: int
    confidence: float = 1.0
    native: Any = field(default=None, compare=False, repr=False)

    @property
    def normalized_text(self) -> str:
        return normalize_text(self.text)

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.width // 2, self.y + self.height // 2


@dataclass(frozen=True, slots=True)
class ScreenContext:
    frame_id: int
    captured_at: float
    width: int
    height: int
    texts: tuple[TextBox, ...]

    @classmethod
    def from_ocr(
        cls,
        boxes: Iterable[Any],
        *,
        frame_id: int,
        captured_at: float,
        width: int,
        height: int,
        min_confidence: float = 0.0,
    ) -> ScreenContext:
        converted: list[TextBox] = []
        for box in boxes:
            text = str(getattr(box, "name", "") or "").strip()
            confidence = float(getattr(box, "confidence", 1.0) or 0.0)
            if not text or confidence < min_confidence:
                continue
            converted.append(
                TextBox(
                    text=text,
                    x=int(getattr(box, "x", 0)),
                    y=int(getattr(box, "y", 0)),
                    width=int(getattr(box, "width", 0)),
                    height=int(getattr(box, "height", 0)),
                    confidence=confidence,
                    native=box,
                )
            )
        return cls(frame_id, captured_at, width, height, tuple(converted))

    def find_text(self, candidates: Iterable[str], *, exact: bool = False) -> tuple[TextBox, ...]:
        ranked: list[tuple[int, float, int, int, TextBox]] = []
        for candidate_rank, candidate in enumerate(candidates):
            for box in self.texts:
                if text_matches(box.text, candidate, exact=exact):
                    ranked.append((candidate_rank, -box.confidence, box.y, box.x, box))
        ranked.sort(key=lambda item: item[:4])
        return tuple(item[-1] for item in ranked)

    def first_text(self, candidates: Iterable[str], *, exact: bool = False) -> TextBox | None:
        matches = self.find_text(candidates, exact=exact)
        return matches[0] if matches else None

    def has_text(self, *candidates: str, exact: bool = False) -> bool:
        return self.first_text(candidates, exact=exact) is not None

    @property
    def fingerprint(self) -> str:
        stable_parts = [
            f"{box.normalized_text}:{round(box.x / 20)}:{round(box.y / 20)}"
            for box in sorted(self.texts, key=lambda item: (item.y, item.x, item.normalized_text))
        ]
        digest = hashlib.sha1("|".join(stable_parts).encode("utf-8"), usedforsecurity=False)
        return digest.hexdigest()[:16]


class ActionKind(StrEnum):
    CLICK_TEXT = "click_text"
    CLICK_RELATIVE = "click_relative"
    PRESS_KEY = "press_key"


@dataclass(frozen=True, slots=True)
class Action:
    kind: ActionKind
    target: str | None = None
    exact: bool = False
    x: float | None = None
    y: float | None = None
    key: str | None = None
    after_delay: float = 0.6
    destructive: bool = False

    def __post_init__(self) -> None:
        if self.after_delay < 0:
            raise ValueError("after_delay cannot be negative")
        if self.kind is ActionKind.CLICK_TEXT and not self.target:
            raise ValueError("click_text requires target")
        if (
            self.kind is ActionKind.CLICK_RELATIVE
            and (self.x is None or self.y is None or not (0 <= self.x <= 1 and 0 <= self.y <= 1))
        ):
            raise ValueError("click_relative requires normalized x and y")
        if self.kind is ActionKind.PRESS_KEY and not self.key:
            raise ValueError("press_key requires key")

    @classmethod
    def click_text(
        cls,
        target: str,
        *,
        exact: bool = False,
        after_delay: float = 0.6,
        destructive: bool = False,
    ) -> Action:
        return cls(
            ActionKind.CLICK_TEXT,
            target=target,
            exact=exact,
            after_delay=after_delay,
            destructive=destructive,
        )

    @classmethod
    def click_relative(
        cls,
        x: float,
        y: float,
        *,
        after_delay: float = 0.6,
        destructive: bool = False,
    ) -> Action:
        return cls(
            ActionKind.CLICK_RELATIVE,
            x=x,
            y=y,
            after_delay=after_delay,
            destructive=destructive,
        )

    @classmethod
    def press_key(cls, key: str, *, after_delay: float = 0.3) -> Action:
        return cls(ActionKind.PRESS_KEY, key=key, after_delay=after_delay)

    @property
    def signature(self) -> str:
        return ":".join(
            (
                self.kind.value,
                self.target or "",
                str(self.exact),
                "" if self.x is None else f"{self.x:.4f}",
                "" if self.y is None else f"{self.y:.4f}",
                self.key or "",
            )
        )


@dataclass(frozen=True, slots=True)
class Decision:
    page_id: str
    score: float
    action: Action | None
    reason: str


class TickStatus(StrEnum):
    UNKNOWN = "unknown"
    AMBIGUOUS = "ambiguous"
    OBSERVED = "observed"
    SUPPRESSED = "suppressed"
    EXECUTED = "executed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TickReport:
    status: TickStatus
    frame_id: int
    page_id: str | None = None
    score: float = 0.0
    action: Action | None = None
    reason: str = ""
