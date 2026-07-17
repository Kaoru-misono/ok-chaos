from src.chaos.engine import ChaosEngine
from src.chaos.handlers import create_default_handlers
from src.chaos.model import ActionKind, TickStatus
from src.chaos.settings import ChaosSettings
from src.chaos.state import RuntimeState
from tests.helpers import RecordingExecutor, make_context


def run_page(*texts: str, settings: ChaosSettings | None = None):
    executor = RecordingExecutor()
    report = ChaosEngine(create_default_handlers()).tick(
        make_context(*texts), settings or ChaosSettings(), RuntimeState(), executor, now=1.0
    )
    return report, executor


def test_zero_system_home_clicks_codex() -> None:
    report, executor = run_page("零式系统", "法典")

    assert report.page_id == "zero_system_home"
    assert report.status is TickStatus.EXECUTED
    assert executor.actions[0][0].kind is ActionKind.CLICK_TEXT
    assert executor.actions[0][0].target == "法典"


def test_free_craft_is_preferred() -> None:
    report, executor = run_page("卡厄思合成", "免费合成")

    assert report.page_id == "chaos_craft"
    assert executor.actions[0][0].target == "免费合成"


def test_data_collection_page_never_deletes_without_verified_template() -> None:
    settings = ChaosSettings(keep_save=False)
    report, executor = run_page("存储数据收集完成", settings=settings)

    assert report.page_id == "data_collected"
    assert report.status is TickStatus.OBSERVED
    assert "破坏性操作" in report.reason
    assert executor.actions == []


def test_destructive_confirmation_is_not_handled_by_generic_confirm() -> None:
    report, executor = run_page("删除存档", "取消", "确认")

    assert report.status is TickStatus.UNKNOWN
    assert executor.actions == []


def test_mental_breakdown_can_be_left_for_manual_handling() -> None:
    report, executor = run_page("精神崩溃发生", settings=ChaosSettings(treat_breakdown=False))

    assert report.page_id == "mental_breakdown"
    assert report.status is TickStatus.OBSERVED
    assert executor.actions == []
