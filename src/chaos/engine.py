from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from src.chaos.model import Action, Decision, ScreenContext, TickReport, TickStatus
from src.chaos.settings import ChaosSettings
from src.chaos.state import RuntimeState


class PageHandler(Protocol):
    page_id: str
    priority: int

    def match(self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState) -> float: ...

    def plan(self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState, score: float) -> Decision: ...


class ActionExecutor(Protocol):
    def perform(self, action: Action, context: ScreenContext) -> bool: ...


@dataclass(frozen=True, slots=True)
class _Candidate:
    handler: PageHandler
    score: float


class ChaosEngine:
    """Select one page and execute at most one action for each OCR snapshot."""

    def __init__(
        self,
        handlers: Sequence[PageHandler],
        *,
        minimum_score: float = 0.62,
        ambiguity_margin: float = 0.04,
    ) -> None:
        page_ids = [handler.page_id for handler in handlers]
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("handler page_id values must be unique")
        self._handlers = tuple(handlers)
        self._minimum_score = minimum_score
        self._ambiguity_margin = ambiguity_margin

    def tick(
        self,
        context: ScreenContext,
        settings: ChaosSettings,
        state: RuntimeState,
        executor: ActionExecutor,
        *,
        now: float | None = None,
    ) -> TickReport:
        current_time = time.monotonic() if now is None else now
        candidates = [
            _Candidate(handler, score)
            for handler in self._handlers
            if (score := handler.match(context, settings, state)) >= self._minimum_score
        ]
        candidates.sort(key=lambda item: (-item.score, -item.handler.priority, item.handler.page_id))

        if not candidates:
            state.note_unknown()
            return TickReport(TickStatus.UNKNOWN, context.frame_id, reason="没有页面达到最低置信度")

        top = candidates[0]
        if len(candidates) > 1:
            second = candidates[1]
            if (
                top.handler.priority == second.handler.priority
                and top.score - second.score < self._ambiguity_margin
            ):
                state.note_unknown()
                return TickReport(
                    TickStatus.AMBIGUOUS,
                    context.frame_id,
                    score=top.score,
                    reason=f"页面歧义: {top.handler.page_id} / {second.handler.page_id}",
                )

        decision = top.handler.plan(context, settings, state, top.score)
        state.note_page(decision.page_id)
        if decision.action is None:
            return TickReport(
                TickStatus.OBSERVED,
                context.frame_id,
                page_id=decision.page_id,
                score=decision.score,
                reason=decision.reason,
            )

        if state.should_suppress(decision.action, context, current_time, settings.action_cooldown):
            return TickReport(
                TickStatus.SUPPRESSED,
                context.frame_id,
                page_id=decision.page_id,
                score=decision.score,
                action=decision.action,
                reason="相同画面和动作仍在冷却期",
            )

        if not executor.perform(decision.action, context):
            return TickReport(
                TickStatus.FAILED,
                context.frame_id,
                page_id=decision.page_id,
                score=decision.score,
                action=decision.action,
                reason="动作执行器没有完成计划动作",
            )

        state.note_action(decision.action, context, current_time)
        return TickReport(
            TickStatus.EXECUTED,
            context.frame_id,
            page_id=decision.page_id,
            score=decision.score,
            action=decision.action,
            reason=decision.reason,
        )
