from __future__ import annotations

from src.chaos.model import Action, Decision, ScreenContext
from src.chaos.settings import ChaosSettings
from src.chaos.state import RuntimeState


class ZeroSystemHomeHandler:
    page_id = "zero_system_home"
    priority = 100

    def match(self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState) -> float:
        if context.has_text("零式系统") and context.has_text("法典", exact=True):
            return 0.97
        return 0.0

    def plan(
        self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState, score: float
    ) -> Decision:
        return Decision(self.page_id, score, Action.click_text("法典", exact=True, after_delay=1.2), "进入法典")


class CodexSearchHandler:
    page_id = "codex_search"
    priority = 95

    def match(self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState) -> float:
        if context.has_text("法典", exact=True) and context.has_text("搜索新坐标"):
            return 0.96
        return 0.0

    def plan(
        self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState, score: float
    ) -> Decision:
        return Decision(
            self.page_id,
            score,
            Action.click_text("搜索新坐标", after_delay=1.2),
            "搜索新的卡厄思坐标",
        )


class MemoryEliminationHandler:
    page_id = "memory_elimination"
    priority = 90

    def match(self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState) -> float:
        matches = context.find_text(("记忆消除",))
        if len(matches) >= 2:
            return 0.95
        if matches:
            return 0.79
        return 0.0

    def plan(
        self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState, score: float
    ) -> Decision:
        # The title and action have the same text, so use the verified button location.
        return Decision(
            self.page_id,
            score,
            Action.click_relative(0.589, 0.703, after_delay=0.8),
            "执行记忆消除",
        )


class ChaosCraftHandler:
    page_id = "chaos_craft"
    priority = 90

    def match(self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState) -> float:
        if context.has_text("免费合成"):
            return 0.96
        if context.has_text("卡厄思合成"):
            return 0.91
        return 0.0

    def plan(
        self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState, score: float
    ) -> Decision:
        target = "免费合成" if context.has_text("免费合成") else "卡厄思合成"
        return Decision(self.page_id, score, Action.click_text(target, after_delay=1.2), f"执行{target}")


class NewDifficultyHandler:
    page_id = "new_difficulty"
    priority = 80

    def match(self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState) -> float:
        return 0.93 if context.has_text("征服新难度") else 0.0

    def plan(
        self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState, score: float
    ) -> Decision:
        return Decision(
            self.page_id,
            score,
            Action.click_relative(0.502, 0.943, after_delay=0.8),
            "关闭新难度提示",
        )


class ExpeditionUnlockedHandler:
    page_id = "expedition_unlocked"
    priority = 80

    def match(self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState) -> float:
        return 0.93 if context.has_text("解锁的探险记录") else 0.0

    def plan(
        self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState, score: float
    ) -> Decision:
        return Decision(
            self.page_id,
            score,
            Action.click_relative(0.5, 0.95, after_delay=0.8),
            "关闭探险记录解锁提示",
        )


class MentalBreakdownHandler:
    page_id = "mental_breakdown"
    priority = 100

    def match(self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState) -> float:
        return 0.96 if context.has_text("精神崩溃发生") else 0.0

    def plan(
        self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState, score: float
    ) -> Decision:
        if not settings.treat_breakdown:
            return Decision(self.page_id, score, None, "配置为不自动治疗，等待人工处理")
        return Decision(
            self.page_id,
            score,
            Action.click_relative(0.706, 0.915, after_delay=1.0),
            "前往创伤中心治疗",
        )


class TreatmentMethodHandler:
    page_id = "treatment_method"
    priority = 90

    def match(self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState) -> float:
        return 0.94 if context.has_text("选择哪种方法进行治疗") else 0.0

    def plan(
        self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState, score: float
    ) -> Decision:
        return Decision(
            self.page_id,
            score,
            Action.click_relative(0.765, 0.500, after_delay=0.8),
            "选择治疗方法",
        )


class TreatmentApproveHandler:
    page_id = "treatment_approve"
    priority = 90

    def match(self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState) -> float:
        return 0.94 if context.has_text("点击批准") else 0.0

    def plan(
        self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState, score: float
    ) -> Decision:
        return Decision(
            self.page_id,
            score,
            Action.click_text("点击批准", after_delay=0.8),
            "批准治疗结果",
        )


class GoToChaosCoreHandler:
    page_id = "go_to_chaos_core"
    priority = 85

    def match(self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState) -> float:
        return 0.94 if context.has_text("前往卡厄思核心") else 0.0

    def plan(
        self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState, score: float
    ) -> Decision:
        return Decision(
            self.page_id,
            score,
            Action.click_text("前往卡厄思核心", after_delay=1.0),
            "进入卡厄思核心",
        )


class DataCollectedHandler:
    page_id = "data_collected"
    priority = 110

    def match(self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState) -> float:
        return 0.98 if context.has_text("存储数据收集完成") else 0.0

    def plan(
        self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState, score: float
    ) -> Decision:
        if settings.keep_save:
            reason = "配置要求保留存档，等待后续非破坏性流程处理器"
        else:
            reason = "删除存档属于破坏性操作，模板和二次确认尚未实现，因此不执行"
        return Decision(self.page_id, score, None, reason)


class SafeConfirmDialogHandler:
    page_id = "safe_confirm_dialog"
    priority = 10
    _destructive_words = ("删除存档", "清除存档", "覆盖存档", "重置数据", "永久删除")

    def match(self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState) -> float:
        if not settings.auto_confirm or context.has_text(*self._destructive_words):
            return 0.0
        has_confirm = context.has_text("确认", "确定", exact=True)
        has_cancel = context.has_text("取消", exact=True)
        return 0.72 if has_confirm and has_cancel else 0.0

    def plan(
        self, context: ScreenContext, settings: ChaosSettings, state: RuntimeState, score: float
    ) -> Decision:
        target = "确认" if context.has_text("确认", exact=True) else "确定"
        return Decision(self.page_id, score, Action.click_text(target, exact=True), "点击普通确认对话框")
