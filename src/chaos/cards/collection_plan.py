from __future__ import annotations

from dataclasses import dataclass

from src.chaos.model import ScreenContext, TextBox


@dataclass(frozen=True, slots=True)
class CardCollectionSlot:
    slot_index: int
    card_id: str
    expected_name: str
    relative_x: float
    relative_y: float
    copy_index: int = 1
    traditional_name: str | None = None

    def __post_init__(self) -> None:
        if self.slot_index < 0:
            raise ValueError("slot_index cannot be negative")
        if not self.card_id or not self.expected_name:
            raise ValueError("card slot requires identity and expected name")
        if not 0 < self.relative_x < 1 or not 0 < self.relative_y < 1:
            raise ValueError("card slot coordinates must be normalized")
        if self.copy_index <= 0:
            raise ValueError("copy_index must be positive")

    @property
    def name_candidates(self) -> tuple[str, ...]:
        if self.traditional_name and self.traditional_name != self.expected_name:
            return self.expected_name, self.traditional_name
        return (self.expected_name,)


HAIDE_MALI_CARD_SLOTS = (
    CardCollectionSlot(0, "haide_mali/card_01", "剑光", 0.339, 0.332, 1, "劍光"),
    CardCollectionSlot(1, "haide_mali/card_01", "剑光", 0.484, 0.332, 2, "劍光"),
    CardCollectionSlot(2, "haide_mali/card_02", "剑幕", 0.628, 0.332, 1, "劍幕"),
    CardCollectionSlot(3, "haide_mali/card_03", "剑之雨", 0.773, 0.332, 1, "劍之雨"),
    CardCollectionSlot(4, "haide_mali/card_04", "万人的英雄", 0.339, 0.771, 1, "萬人的英雄"),
    CardCollectionSlot(5, "haide_mali/card_05", "一缕光芒", 0.484, 0.771, 1, "一縷光芒"),
    CardCollectionSlot(6, "haide_mali/card_06", "展开极光", 0.628, 0.771, 1, "展開極光"),
    CardCollectionSlot(7, "haide_mali/card_07", "凝结极光", 0.773, 0.771, 1, "凝結極光"),
)


def is_character_card_list(context: ScreenContext) -> bool:
    return context.has_text("起始卡牌") and context.has_text("灵光一闪卡牌", "靈光一閃卡牌")


def detail_contains_expected_name(context: ScreenContext, slot: CardCollectionSlot) -> bool:
    if context.has_text(*slot.name_candidates):
        return True
    compact = "".join(box.normalized_text for box in context.texts)
    for candidate in slot.name_candidates:
        if candidate in compact:
            return True
        # The large energy-cost glyph overlaps the first title character on
        # four-character cards. PaddleOCR can therefore return e.g. “縷光芒”
        # for “一縷光芒”; the remaining three characters are still distinctive.
        if len(candidate) >= 4 and candidate[1:] in compact:
            return True
    return False


def find_epiphany_button(context: ScreenContext) -> TextBox | None:
    """Return only the bottom-right epiphany preview button.

    Card detail pages also explain the epiphany keyword in the right-hand help
    panel.  Position is therefore part of the identity, matching ok-kes' habit
    of constraining generic action text to the expected button region.
    """

    for box in context.find_text(("灵光一闪", "靈光一閃"), exact=True):
        center_x, center_y = box.center
        relative_x = center_x / context.width
        relative_y = center_y / context.height
        if 0.75 <= relative_x <= 0.95 and 0.85 <= relative_y <= 0.99:
            return box
    return None


def is_epiphany_overview(context: ScreenContext) -> bool:
    """Identify the screen listing all possible epiphany outcomes for a card."""

    has_title = context.has_text("灵光一闪", "靈光一閃", exact=True)
    has_explanation = context.has_text(
        "卡牌可能会触发以下的灵光一闪",
        "卡牌可能會觸發以下的靈光一閃",
    )
    return has_title and has_explanation
