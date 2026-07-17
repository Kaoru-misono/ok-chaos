from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class ConfigLike(Protocol):
    def get(self, key: str, default: Any = None) -> Any: ...


KEEP_SAVE = "保留存档"
TREAT_BREAKDOWN = "治疗精神崩溃"
AUTO_CONFIRM = "自动点击普通确认"
ACTION_COOLDOWN = "动作冷却秒"
SAVE_UNKNOWN = "保存未知页面截图"
UNKNOWN_THRESHOLD = "未知页面截图阈值"
MIN_OCR_CONFIDENCE = "OCR最小置信度"


@dataclass(frozen=True, slots=True)
class ChaosSettings:
    keep_save: bool = True
    treat_breakdown: bool = True
    auto_confirm: bool = True
    action_cooldown: float = 1.0
    save_unknown_screenshot: bool = False
    unknown_screenshot_threshold: int = 8
    min_ocr_confidence: float = 0.20

    @classmethod
    def defaults(cls) -> dict[str, Any]:
        defaults = cls()
        return {
            KEEP_SAVE: defaults.keep_save,
            TREAT_BREAKDOWN: defaults.treat_breakdown,
            AUTO_CONFIRM: defaults.auto_confirm,
            ACTION_COOLDOWN: defaults.action_cooldown,
            SAVE_UNKNOWN: defaults.save_unknown_screenshot,
            UNKNOWN_THRESHOLD: defaults.unknown_screenshot_threshold,
            MIN_OCR_CONFIDENCE: defaults.min_ocr_confidence,
        }

    @classmethod
    def from_mapping(cls, values: ConfigLike) -> ChaosSettings:
        settings = cls(
            keep_save=values.get(KEEP_SAVE, True),
            treat_breakdown=values.get(TREAT_BREAKDOWN, True),
            auto_confirm=values.get(AUTO_CONFIRM, True),
            action_cooldown=values.get(ACTION_COOLDOWN, 1.0),
            save_unknown_screenshot=values.get(SAVE_UNKNOWN, False),
            unknown_screenshot_threshold=values.get(UNKNOWN_THRESHOLD, 8),
            min_ocr_confidence=values.get(MIN_OCR_CONFIDENCE, 0.20),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        boolean_fields = {
            KEEP_SAVE: self.keep_save,
            TREAT_BREAKDOWN: self.treat_breakdown,
            AUTO_CONFIRM: self.auto_confirm,
            SAVE_UNKNOWN: self.save_unknown_screenshot,
        }
        for name, value in boolean_fields.items():
            if not isinstance(value, bool):
                raise ValueError(f"{name}必须是布尔值")
        if isinstance(self.action_cooldown, bool) or not isinstance(self.action_cooldown, (int, float)):
            raise ValueError(f"{ACTION_COOLDOWN}必须是数字")
        if not 0.2 <= float(self.action_cooldown) <= 10:
            raise ValueError(f"{ACTION_COOLDOWN}必须在0.2到10之间")
        if isinstance(self.unknown_screenshot_threshold, bool) or not isinstance(
            self.unknown_screenshot_threshold, int
        ):
            raise ValueError(f"{UNKNOWN_THRESHOLD}必须是整数")
        if not 1 <= self.unknown_screenshot_threshold <= 300:
            raise ValueError(f"{UNKNOWN_THRESHOLD}必须在1到300之间")
        if isinstance(self.min_ocr_confidence, bool) or not isinstance(self.min_ocr_confidence, (int, float)):
            raise ValueError(f"{MIN_OCR_CONFIDENCE}必须是数字")
        if not 0 <= float(self.min_ocr_confidence) <= 1:
            raise ValueError(f"{MIN_OCR_CONFIDENCE}必须在0到1之间")

    @classmethod
    def validate_pair(cls, key: str, value: Any) -> str | None:
        values = cls.defaults()
        if key not in values:
            return None
        values[key] = value
        try:
            cls.from_mapping(values)
        except ValueError as exception:
            return str(exception)
        return None
