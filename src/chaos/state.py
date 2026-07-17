from __future__ import annotations

from dataclasses import dataclass

from src.chaos.model import Action, ScreenContext


@dataclass(slots=True)
class RuntimeState:
    unknown_streak: int = 0
    last_page_id: str | None = None
    last_action_signature: str | None = None
    last_context_fingerprint: str | None = None
    last_action_at: float = float("-inf")
    total_actions: int = 0

    def reset(self) -> None:
        self.unknown_streak = 0
        self.last_page_id = None
        self.last_action_signature = None
        self.last_context_fingerprint = None
        self.last_action_at = float("-inf")
        self.total_actions = 0

    def note_unknown(self) -> None:
        self.unknown_streak += 1
        self.last_page_id = None

    def note_page(self, page_id: str) -> None:
        self.unknown_streak = 0
        self.last_page_id = page_id

    def should_suppress(self, action: Action, context: ScreenContext, now: float, cooldown: float) -> bool:
        return (
            self.last_action_signature == action.signature
            and self.last_context_fingerprint == context.fingerprint
            and now - self.last_action_at < cooldown
        )

    def note_action(self, action: Action, context: ScreenContext, now: float) -> None:
        self.last_action_signature = action.signature
        self.last_context_fingerprint = context.fingerprint
        self.last_action_at = now
        self.total_actions += 1
