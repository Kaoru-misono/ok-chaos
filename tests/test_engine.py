from dataclasses import dataclass

from src.chaos.engine import ChaosEngine
from src.chaos.model import Action, Decision, TickStatus
from src.chaos.settings import ChaosSettings
from src.chaos.state import RuntimeState
from tests.helpers import RecordingExecutor, make_context


@dataclass
class StubHandler:
    page_id: str
    priority: int
    score: float
    action: Action | None

    def match(self, context, settings, state) -> float:
        return self.score

    def plan(self, context, settings, state, score) -> Decision:
        return Decision(self.page_id, score, self.action, self.page_id)


def test_engine_uses_highest_score_instead_of_handler_order() -> None:
    low = StubHandler("low", 100, 0.70, Action.press_key("a"))
    high = StubHandler("high", 1, 0.95, Action.press_key("b"))
    executor = RecordingExecutor()

    report = ChaosEngine([low, high]).tick(
        make_context("页面"), ChaosSettings(), RuntimeState(), executor, now=1.0
    )

    assert report.status is TickStatus.EXECUTED
    assert report.page_id == "high"
    assert [item[0].key for item in executor.actions] == ["b"]


def test_engine_refuses_ambiguous_pages_with_equal_priority() -> None:
    first = StubHandler("first", 10, 0.91, Action.press_key("a"))
    second = StubHandler("second", 10, 0.89, Action.press_key("b"))
    executor = RecordingExecutor()

    report = ChaosEngine([first, second]).tick(
        make_context("页面"), ChaosSettings(), RuntimeState(), executor, now=1.0
    )

    assert report.status is TickStatus.AMBIGUOUS
    assert executor.actions == []


def test_engine_executes_at_most_one_action_per_tick() -> None:
    handlers = [
        StubHandler("one", 20, 0.98, Action.press_key("a")),
        StubHandler("two", 10, 0.90, Action.press_key("b")),
        StubHandler("three", 5, 0.80, Action.press_key("c")),
    ]
    executor = RecordingExecutor()

    ChaosEngine(handlers).tick(make_context("页面"), ChaosSettings(), RuntimeState(), executor, now=1.0)

    assert len(executor.actions) == 1


def test_same_action_on_same_screen_is_suppressed_during_cooldown() -> None:
    handler = StubHandler("page", 10, 0.95, Action.press_key("enter"))
    executor = RecordingExecutor()
    state = RuntimeState()
    engine = ChaosEngine([handler])
    settings = ChaosSettings(action_cooldown=1.0)

    first = engine.tick(make_context("页面", frame_id=1), settings, state, executor, now=1.0)
    second = engine.tick(make_context("页面", frame_id=2), settings, state, executor, now=1.5)

    assert first.status is TickStatus.EXECUTED
    assert second.status is TickStatus.SUPPRESSED
    assert len(executor.actions) == 1


def test_unknown_page_does_not_execute() -> None:
    executor = RecordingExecutor()
    state = RuntimeState()

    report = ChaosEngine([]).tick(make_context("陌生页面"), ChaosSettings(), state, executor, now=1.0)

    assert report.status is TickStatus.UNKNOWN
    assert state.unknown_streak == 1
    assert executor.actions == []
