from __future__ import annotations

import time
from pathlib import Path

import cv2
from ok import BaseTask, TriggerTask

from src.chaos.cards.catalog import CardCatalog
from src.chaos.cards.collection_plan import (
    HAIDE_MALI_CARD_SLOTS,
    detail_contains_expected_name,
    find_epiphany_button,
    is_character_card_list,
    is_epiphany_overview,
)
from src.chaos.cards.collector import CaptureLabel, CardSampleWriter
from src.chaos.cards.enums import SampleScene
from src.chaos.cards.flash_recognizer import FlashKnowledgeBase
from src.chaos.cards.presentation import card_observation_info, flash_recognition_info
from src.chaos.cards.runtime_index import RuntimeCardIndex
from src.chaos.cards.schema import validate_id_part, validate_qualified_id
from src.chaos.engine import ChaosEngine
from src.chaos.handlers import create_default_handlers
from src.chaos.model import Action, ActionKind, ScreenContext, TickReport, TickStatus
from src.chaos.resources import resolve_project_resource
from src.chaos.settings import (
    ACTION_COOLDOWN,
    AUTO_CONFIRM,
    KEEP_SAVE,
    MIN_OCR_CONFIDENCE,
    SAVE_UNKNOWN,
    TREAT_BREAKDOWN,
    UNKNOWN_THRESHOLD,
    ChaosSettings,
)
from src.chaos.state import RuntimeState
from src.privacy import redact_bottom_right

COLLECT_SCENE = "采集场景"
COLLECT_OWNER_ID = "角色ID"
COLLECT_CARD_ID = "卡牌ID"
COLLECT_VARIANT_ID = "变体ID"
COLLECT_GAME_VERSION = "游戏版本"
COLLECT_LANGUAGE = "游戏语言"
COLLECT_OUTPUT_FOLDER = "采集输出目录"

FLASH_REFERENCE_PATH = "datasets/cards/reference/haide_mali/flash_layers.pending.json"
EPIPHANY_REFERENCE_PATH = "datasets/cards/review/haide_mali/epiphany.pending.json"
CARD_CATALOG_PATH = "data/cards"


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _variant_ids(value: object) -> tuple[str, ...]:
    text = _optional_text(value)
    if text is None:
        return ()
    normalized = text.replace("；", ";").replace("，", ",").replace(";", ",")
    return tuple(part.strip() for part in normalized.split(",") if part.strip())


class CardCollectorTask(BaseTask):
    """Capture exactly one passive card sample for later human review."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.name = "采集一份角色牌样本"
        self.description = (
            "保存当前游戏画面、同一帧OCR证据和待审核标签；不会点击、滚动或自动修改卡牌数据库。"
        )
        self.instructions = "https://github.com/ok-oldking/ok-script"
        self.show_create_shortcut = True
        self.default_config.update(
            {
                COLLECT_SCENE: SampleScene.CARD_DETAIL.value,
                COLLECT_OWNER_ID: "",
                COLLECT_CARD_ID: "",
                COLLECT_VARIANT_ID: "",
                COLLECT_GAME_VERSION: "unknown",
                COLLECT_LANGUAGE: "zh-TW",
                COLLECT_OUTPUT_FOLDER: "datasets/cards/inbox",
            }
        )
        self.config_description.update(
            {
                COLLECT_SCENE: "当前画面类型。首轮优先采集卡牌详情，再补战斗手牌和强化页面。",
                COLLECT_OWNER_ID: "稳定的小写英文角色ID，例如 character_id；未知时可以留空等待审核。",
                COLLECT_CARD_ID: "格式为 owner_id/card_id；未知时可以留空等待审核。",
                COLLECT_VARIANT_ID: "一个或多个变体ID，多个使用逗号分隔；基础牌或未知时留空。",
                COLLECT_GAME_VERSION: "记录采样时的游戏版本，便于版本变更后隔离旧样本。",
                COLLECT_LANGUAGE: "当前游戏界面的语言；OCR仍会按全局配置统一转为简体文本。",
                COLLECT_OUTPUT_FOLDER: "本地样本 inbox。图片默认被 Git 忽略，不会上传。",
            }
        )
        self.config_type.update(
            {
                COLLECT_SCENE: {
                    "type": "drop_down",
                    "options": [scene.value for scene in SampleScene],
                },
                COLLECT_LANGUAGE: {
                    "type": "drop_down",
                    "options": ["zh-TW", "zh-CN"],
                },
                COLLECT_OUTPUT_FOLDER: {
                    "type": "file_selector",
                    "selector_type": "folder",
                    "dialog_title": "选择卡牌样本目录",
                },
            }
        )

    def validate_config(self, key, value):
        try:
            if key == COLLECT_SCENE:
                SampleScene(value)
            elif key == COLLECT_OWNER_ID and _optional_text(value) is not None:
                validate_id_part(_optional_text(value), "owner_id")
            elif key == COLLECT_CARD_ID and _optional_text(value) is not None:
                validate_qualified_id(_optional_text(value), "card_id")
            elif key == COLLECT_VARIANT_ID:
                for variant_id in _variant_ids(value):
                    validate_qualified_id(variant_id, "variant_id", parts=3)
            elif key == COLLECT_GAME_VERSION and _optional_text(value) is None:
                return "游戏版本不能为空"
            elif key == COLLECT_LANGUAGE and value not in {"zh-TW", "zh-CN"}:
                return "游戏语言必须是 zh-TW 或 zh-CN"
        except ValueError as exception:
            return str(exception)
        return None

    def run(self) -> None:
        # The privacy mask is applied before OCR so the PNG and evidence describe
        # exactly the same captured frame.
        frame = redact_bottom_right(self.frame.copy())
        boxes = self.ocr(frame=frame)
        label = CaptureLabel(
            scene=SampleScene(self.config.get(COLLECT_SCENE, SampleScene.UNKNOWN.value)),
            owner_id=_optional_text(self.config.get(COLLECT_OWNER_ID)),
            card_id=_optional_text(self.config.get(COLLECT_CARD_ID)),
            variant_ids=_variant_ids(self.config.get(COLLECT_VARIANT_ID)),
        )
        output = _optional_text(self.config.get(COLLECT_OUTPUT_FOLDER)) or "datasets/cards/inbox"
        manifest_path = CardSampleWriter(Path(output)).capture(
            frame,
            boxes,
            label,
            language=str(self.config.get(COLLECT_LANGUAGE, "zh-TW")),
            game_version=_optional_text(self.config.get(COLLECT_GAME_VERSION)) or "unknown",
        )
        resolved = manifest_path.resolve()
        self.info_set("样本清单", str(resolved))
        self.info_set("OCR文本数量", len(boxes))
        self.log_info(f"角色牌样本已保存，等待人工审核: {resolved}", notify=True)


class CurrentCardRecognitionTask(BaseTask):
    """Recognize one live card-detail frame without saving or interacting."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.name = "识别当前卡牌闪光（只读）"
        self.description = (
            "读取当前游戏画面一次、执行一次OCR，并识别海德玛丽卡牌的普通闪、"
            "专属灵光一闪和神闪；不点击，也不保存截图。"
        )
        self.instructions = "https://github.com/ok-oldking/ok-script"
        self.show_create_shortcut = True
        self._runtime_index: RuntimeCardIndex | None = None

    def _get_runtime_index(self) -> RuntimeCardIndex:
        if self._runtime_index is None:
            knowledge = FlashKnowledgeBase.from_reference_files(
                resolve_project_resource(FLASH_REFERENCE_PATH),
                resolve_project_resource(EPIPHANY_REFERENCE_PATH),
            )
            catalog = CardCatalog.from_directory(resolve_project_resource(CARD_CATALOG_PATH))
            self._runtime_index = RuntimeCardIndex(catalog, knowledge)
        return self._runtime_index

    def run(self) -> None:
        started_at = time.perf_counter()
        try:
            source_frame = self.frame
            if source_frame is None or not hasattr(source_frame, "shape") or len(source_frame.shape) < 2:
                raise ValueError("当前没有可识别的游戏画面")
            frame = source_frame
            runtime_index = self._get_runtime_index()
            region = runtime_index.knowledge.layout.ocr_search
            ocr_started_at = time.perf_counter()
            boxes = tuple(
                self.ocr(
                    x=region.left,
                    y=region.top,
                    to_x=region.right,
                    to_y=region.bottom,
                    threshold=0.15,
                    frame=frame,
                )
            )
            ocr_elapsed = time.perf_counter() - ocr_started_at
            height, width = (int(frame.shape[0]), int(frame.shape[1]))
            context = ScreenContext.from_ocr(
                boxes,
                frame_id=1,
                captured_at=time.monotonic(),
                width=width,
                height=height,
                min_confidence=0.15,
            )
            match_started_at = time.perf_counter()
            result = runtime_index.recognize_flash(context, frame)
            observation = runtime_index.to_observation(result, context)
            resolution = runtime_index.resolve(observation)
            match_elapsed = time.perf_counter() - match_started_at
        except (OSError, ValueError) as exception:
            self.info_set("识别状态", "失败")
            self.info_set("识别说明", str(exception))
            self.info_set("识别耗时", f"{time.perf_counter() - started_at:.2f}秒")
            self.info_set("保存截图", "否")
            self.log_warning(f"当前卡牌识别失败: {exception}")
            return

        for key, value in flash_recognition_info(result, ocr_count=len(boxes)).items():
            self.info_set(key, value)
        for key, value in card_observation_info(
            observation,
            resolution,
            runtime_index.summary,
        ).items():
            self.info_set(key, value)
        total_elapsed = time.perf_counter() - started_at
        self.info_set(
            "识别耗时",
            f"OCR {ocr_elapsed:.2f}秒｜匹配 {match_elapsed:.3f}秒｜总计 {total_elapsed:.2f}秒",
        )
        summary = (
            f"{result.observed_card_name or '未知卡牌'} | "
            f"{result.base_layer_kind.value} | "
            f"{', '.join(result.variant_ids) or '未识别到闪光变体'} | "
            f"decision_ready={resolution.decision_ready}"
        )
        self.log_info(f"当前卡牌识别完成: {summary}", notify=True)


class AutoCardCollectionError(RuntimeError):
    pass


class AutoCardCollectorTask(BaseTask):
    """Safely traverse the verified Haide Mali card grid and collect details."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.name = "自动采集海德玛丽卡牌详情"
        self.description = (
            "仅在同时识别到起始卡牌和灵光一闪卡牌标题时遍历八个已验证卡位；"
            "每次点击后验证详情、保存待审核样本并返回，任何异常立即停止。"
        )
        self.default_config.update(
            {
                COLLECT_GAME_VERSION: "unknown",
                COLLECT_LANGUAGE: "zh-TW",
                COLLECT_OUTPUT_FOLDER: "datasets/cards/inbox",
            }
        )

    def run(self) -> None:
        writer = CardSampleWriter(
            Path(_optional_text(self.config.get(COLLECT_OUTPUT_FOLDER)) or "datasets/cards/inbox")
        )
        language = str(self.config.get(COLLECT_LANGUAGE, "zh-TW"))
        game_version = _optional_text(self.config.get(COLLECT_GAME_VERSION)) or "unknown"
        collected: list[Path] = []

        for position, slot in enumerate(HAIDE_MALI_CARD_SLOTS, start=1):
            list_frame, _, list_context = self._snapshot(position * 2 - 1)
            if not is_character_card_list(list_context):
                raise AutoCardCollectionError(
                    f"采集第{position}个卡位前未确认卡牌列表，已停止且未点击"
                )

            self.info_set("采集进度", f"{position}/8 {slot.expected_name} 第{slot.copy_index}份")
            self.log_info(f"采集卡位{position}: {slot.expected_name} copy={slot.copy_index}")
            self.click_relative(slot.relative_x, slot.relative_y, after_sleep=1.2)

            detail_frame, detail_boxes, detail_context = self._snapshot(position * 2)
            difference = self._frame_difference(list_frame, detail_frame)
            if (
                difference < 3.0
                or is_character_card_list(detail_context)
                or not detail_contains_expected_name(detail_context, slot)
            ):
                diagnostic = writer.capture(
                    detail_frame,
                    detail_boxes,
                    CaptureLabel(SampleScene.UNKNOWN, owner_id="haide_mali"),
                    language=language,
                    game_version=game_version,
                )
                raise AutoCardCollectionError(
                    f"卡位{position}点击后详情验证失败(diff={difference:.2f})，"
                    f"诊断样本: {diagnostic.resolve()}"
                )

            manifest = writer.capture(
                detail_frame,
                detail_boxes,
                CaptureLabel(
                    SampleScene.CARD_DETAIL,
                    owner_id="haide_mali",
                    card_id=slot.card_id,
                ),
                language=language,
                game_version=game_version,
            )
            collected.append(manifest)
            self.info_set("最近样本", str(manifest.resolve()))

            self.send_key("esc", after_sleep=1.0)

        _, _, final_context = self._snapshot(99)
        if not is_character_card_list(final_context):
            raise AutoCardCollectionError("全部详情已采集，但最终未返回卡牌列表")
        self.info_set("采集完成", f"{len(collected)}份详情样本")
        self.log_info(f"海德玛丽卡牌详情自动采集完成: {len(collected)}份", notify=True)

    def _snapshot(self, frame_id: int) -> tuple[object, tuple[object, ...], ScreenContext]:
        frame = redact_bottom_right(self.frame.copy())
        boxes = tuple(self.ocr(frame=frame))
        context = ScreenContext.from_ocr(
            boxes,
            frame_id=frame_id,
            captured_at=time.monotonic(),
            width=int(frame.shape[1]),
            height=int(frame.shape[0]),
            min_confidence=0.15,
        )
        return frame, boxes, context

    @staticmethod
    def _frame_difference(before, after) -> float:
        if before.shape != after.shape:
            return float("inf")
        return float(cv2.absdiff(before, after).mean())


class AutoEpiphanyCollectorTask(AutoCardCollectorTask):
    """Capture the epiphany preview of every eligible Haide Mali card."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.name = "自动采集海德玛丽灵光一闪"
        self.description = (
            "从已验证的卡牌列表逐张打开详情；仅点击右下角的灵光一闪按钮，"
            "保存点击后的待审核画面，没有该按钮的卡牌会直接跳过。"
        )

    def run(self) -> None:
        writer = CardSampleWriter(
            Path(_optional_text(self.config.get(COLLECT_OUTPUT_FOLDER)) or "datasets/cards/inbox")
        )
        language = str(self.config.get(COLLECT_LANGUAGE, "zh-TW"))
        game_version = _optional_text(self.config.get(COLLECT_GAME_VERSION)) or "unknown"
        collected: list[Path] = []
        collected_card_ids: set[str] = set()
        skipped: list[str] = []

        initial_frame, initial_boxes, initial_context = self._snapshot(1)
        if is_epiphany_overview(initial_context):
            matching_card_ids = {
                slot.card_id
                for slot in HAIDE_MALI_CARD_SLOTS
                if detail_contains_expected_name(initial_context, slot)
            }
            if len(matching_card_ids) != 1:
                diagnostic = writer.capture(
                    initial_frame,
                    initial_boxes,
                    CaptureLabel(SampleScene.UNKNOWN, owner_id="haide_mali"),
                    language=language,
                    game_version=game_version,
                )
                raise AutoCardCollectionError(
                    "当前是灵光一闪总览，但无法唯一确认卡牌，"
                    f"诊断样本: {diagnostic.resolve()}"
                )
            initial_card_id = matching_card_ids.pop()
            initial_slot = next(
                slot for slot in HAIDE_MALI_CARD_SLOTS if slot.card_id == initial_card_id
            )
            manifest = writer.capture(
                initial_frame,
                initial_boxes,
                CaptureLabel(
                    SampleScene.EPIPHANY,
                    owner_id="haide_mali",
                    card_id=initial_card_id,
                ),
                language=language,
                game_version=game_version,
            )
            collected.append(manifest)
            collected_card_ids.add(initial_card_id)
            self.info_set("最近样本", str(manifest.resolve()))
            self.log_info(f"已接续保存当前{initial_slot.expected_name}灵光一闪总览")
            self._return_to_card_list(initial_slot, 2)
        elif not is_character_card_list(initial_context):
            raise AutoCardCollectionError("启动时既不是卡牌列表也不是可识别的灵光一闪总览，未点击")

        for position, slot in enumerate(HAIDE_MALI_CARD_SLOTS, start=1):
            if slot.card_id in collected_card_ids:
                continue
            list_frame, _, list_context = self._snapshot(position * 10)
            if not is_character_card_list(list_context):
                raise AutoCardCollectionError(
                    f"检查第{position}个卡位前未确认卡牌列表，已停止且未点击"
                )

            self.info_set("采集进度", f"{position}/8 检查 {slot.expected_name}")
            self.log_info(f"检查灵光一闪卡位{position}: {slot.expected_name}")
            self.click_relative(slot.relative_x, slot.relative_y, after_sleep=1.2)

            detail_frame, detail_boxes, detail_context = self._snapshot(position * 10 + 1)
            difference = self._frame_difference(list_frame, detail_frame)
            if (
                difference < 3.0
                or is_character_card_list(detail_context)
                or not detail_contains_expected_name(detail_context, slot)
            ):
                diagnostic = writer.capture(
                    detail_frame,
                    detail_boxes,
                    CaptureLabel(SampleScene.UNKNOWN, owner_id="haide_mali"),
                    language=language,
                    game_version=game_version,
                )
                raise AutoCardCollectionError(
                    f"卡位{position}详情验证失败(diff={difference:.2f})，"
                    f"诊断样本: {diagnostic.resolve()}"
                )

            button = find_epiphany_button(detail_context)
            if button is None:
                skipped.append(slot.expected_name)
                self.log_info(f"{slot.expected_name}没有灵光一闪按钮，跳过")
                self.send_key("esc", after_sleep=1.0)
                continue

            button_x, button_y = button.center
            self.click_relative(
                button_x / detail_context.width,
                button_y / detail_context.height,
                after_sleep=1.2,
            )
            preview_frame, preview_boxes, preview_context = self._snapshot(position * 10 + 2)
            preview_difference = self._frame_difference(detail_frame, preview_frame)
            if (
                preview_difference < 3.0
                or is_character_card_list(preview_context)
                or not is_epiphany_overview(preview_context)
                or not detail_contains_expected_name(preview_context, slot)
            ):
                diagnostic = writer.capture(
                    preview_frame,
                    preview_boxes,
                    CaptureLabel(SampleScene.UNKNOWN, owner_id="haide_mali", card_id=slot.card_id),
                    language=language,
                    game_version=game_version,
                )
                raise AutoCardCollectionError(
                    f"{slot.expected_name}点击灵光一闪后验证失败(diff={preview_difference:.2f})，"
                    f"诊断样本: {diagnostic.resolve()}"
                )

            manifest = writer.capture(
                preview_frame,
                preview_boxes,
                CaptureLabel(
                    SampleScene.EPIPHANY,
                    owner_id="haide_mali",
                    card_id=slot.card_id,
                ),
                language=language,
                game_version=game_version,
            )
            collected.append(manifest)
            collected_card_ids.add(slot.card_id)
            self.info_set("最近样本", str(manifest.resolve()))

            self._return_to_card_list(slot, position * 10 + 3)

        _, _, final_context = self._snapshot(999)
        if not is_character_card_list(final_context):
            raise AutoCardCollectionError("灵光一闪采集结束，但最终未返回卡牌列表")
        self.info_set("采集完成", f"{len(collected)}份灵光一闪，跳过{len(skipped)}个卡位")
        self.log_info(
            f"海德玛丽灵光一闪采集完成: {len(collected)}份，"
            f"无按钮卡位: {', '.join(skipped) or '无'}",
            notify=True,
        )

    def _return_to_card_list(self, slot, frame_id: int) -> None:
        self.send_key("esc", after_sleep=1.0)
        _, _, return_context = self._snapshot(frame_id)
        if is_character_card_list(return_context):
            return
        if not detail_contains_expected_name(return_context, slot):
            raise AutoCardCollectionError(
                f"{slot.expected_name}灵光一闪总览关闭后页面未知，已停止"
            )
        self.send_key("esc", after_sleep=1.0)
        _, _, list_context = self._snapshot(frame_id + 1)
        if not is_character_card_list(list_context):
            raise AutoCardCollectionError(
                f"{slot.expected_name}详情关闭后未返回卡牌列表，已停止"
            )


class _TaskActionExecutor:
    def __init__(self, task: ChaosTask) -> None:
        self._task = task

    def perform(self, action: Action, context: ScreenContext) -> bool:
        self._task.log_info(f"执行动作: {action.signature}")
        if action.kind is ActionKind.CLICK_TEXT:
            box = context.first_text((action.target or "",), exact=action.exact)
            if box is None or box.native is None:
                self._task.log_warning(f"计划点击的文字已不存在: {action.target}")
                return False
            return bool(self._task.click_box(box.native, after_sleep=action.after_delay))
        if action.kind is ActionKind.CLICK_RELATIVE:
            return bool(self._task.click(action.x, action.y, after_sleep=action.after_delay))
        if action.kind is ActionKind.PRESS_KEY:
            return bool(self._task.send_key(action.key, after_sleep=action.after_delay))
        raise ValueError(f"不支持的动作类型: {action.kind}")


class ChaosTask(TriggerTask):
    """Thin ok-script adapter around the pure Chaos decision engine."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.name = "卡厄思自动运行（重写版）"
        self.description = (
            "全新状态机实现。当前为基础开发版本，仅覆盖少量低风险页面；"
            "任务默认关闭，运行前请确认窗口和配置。"
        )
        self.instructions = "https://github.com/ok-oldking/ok-script"
        self.trigger_interval = 0.8
        self.default_config.update(ChaosSettings.defaults())
        self.default_config["_enabled"] = False
        self.config_description.update(
            {
                KEEP_SAVE: "默认保留存档。删除流程只有在模板和二次确认齐备后才会实现。",
                TREAT_BREAKDOWN: "检测到精神崩溃时，是否自动前往创伤中心。",
                AUTO_CONFIRM: "只处理同时存在确认和取消、且不含删除等危险词的普通对话框。",
                ACTION_COOLDOWN: "相同画面上重复执行同一动作的最短间隔。",
                SAVE_UNKNOWN: "连续无法识别时保存脱敏截图，供开发页面规则使用。",
                UNKNOWN_THRESHOLD: "连续多少轮无法识别后保存一张截图。",
                MIN_OCR_CONFIDENCE: "低于此置信度的OCR结果不会进入页面决策。",
            }
        )
        self._engine = ChaosEngine(create_default_handlers())
        self._state = RuntimeState()
        self._action_executor = _TaskActionExecutor(self)
        self._frame_sequence = 0
        self._last_report_signature: tuple[object, ...] | None = None
        self._last_unknown_screenshot_at = float("-inf")

    def on_create(self) -> None:
        super().on_create()
        self._reset_runtime()

    def enable(self) -> None:
        self._reset_runtime()
        super().enable()

    def disable(self) -> None:
        super().disable()
        self._reset_runtime()

    def validate_config(self, key, value):
        return ChaosSettings.validate_pair(key, value)

    def run(self) -> None:
        settings = ChaosSettings.from_mapping(self.config)
        boxes = self.ocr()
        self._frame_sequence += 1
        captured_at = time.monotonic()
        context = ScreenContext.from_ocr(
            boxes,
            frame_id=self._frame_sequence,
            captured_at=captured_at,
            width=self.width,
            height=self.height,
            min_confidence=settings.min_ocr_confidence,
        )
        report = self._engine.tick(
            context,
            settings,
            self._state,
            self._action_executor,
            now=captured_at,
        )
        self._publish_report(report)
        self._capture_unknown_if_needed(report, settings, captured_at)

    def _reset_runtime(self) -> None:
        self._state.reset()
        self._frame_sequence = 0
        self._last_report_signature = None
        self._last_unknown_screenshot_at = float("-inf")

    def _publish_report(self, report: TickReport) -> None:
        signature = (report.status, report.page_id, report.reason)
        if signature == self._last_report_signature:
            return
        self._last_report_signature = signature
        self.info_set("识别页面", report.page_id or "未知")
        self.info_set("运行状态", report.status.value)
        self.info_set("决策原因", report.reason)
        if report.status is TickStatus.FAILED:
            self.log_warning(report.reason)

    def _capture_unknown_if_needed(
        self,
        report: TickReport,
        settings: ChaosSettings,
        captured_at: float,
    ) -> None:
        if not settings.save_unknown_screenshot:
            return
        if report.status not in (TickStatus.UNKNOWN, TickStatus.AMBIGUOUS):
            return
        if self._state.unknown_streak < settings.unknown_screenshot_threshold:
            return
        if captured_at - self._last_unknown_screenshot_at < 30:
            return
        self._last_unknown_screenshot_at = captured_at
        self.screenshot(name=f"chaos_unknown_{self._frame_sequence}")
