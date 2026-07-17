from __future__ import annotations

from src.chaos.cards.collection_plan import (
    HAIDE_MALI_CARD_SLOTS,
    detail_contains_expected_name,
    find_epiphany_button,
    is_character_card_list,
    is_epiphany_overview,
)
from src.chaos.model import ScreenContext
from tests.helpers import FakeOCRBox, make_context


def test_haide_mali_plan_tracks_two_copies_without_duplicate_card_identity() -> None:
    assert len(HAIDE_MALI_CARD_SLOTS) == 8
    assert HAIDE_MALI_CARD_SLOTS[0].card_id == "haide_mali/card_01"
    assert HAIDE_MALI_CARD_SLOTS[1].card_id == "haide_mali/card_01"
    assert HAIDE_MALI_CARD_SLOTS[0].copy_index == 1
    assert HAIDE_MALI_CARD_SLOTS[1].copy_index == 2
    assert len({slot.card_id for slot in HAIDE_MALI_CARD_SLOTS}) == 7


def test_card_list_requires_both_headers_in_simplified_or_traditional_chinese() -> None:
    assert is_character_card_list(make_context("起始卡牌", "靈光一閃卡牌"))
    assert is_character_card_list(make_context("起始卡牌", "灵光一闪卡牌"))
    assert not is_character_card_list(make_context("起始卡牌", "能力值"))


def test_detail_name_accepts_traditional_or_split_ocr_text() -> None:
    slot = HAIDE_MALI_CARD_SLOTS[5]
    assert detail_contains_expected_name(make_context("一縷光芒"), slot)
    assert detail_contains_expected_name(make_context("一", "缕光芒"), slot)
    assert detail_contains_expected_name(make_context("縷光芒"), slot)
    assert not detail_contains_expected_name(make_context("光芒"), slot)
    assert not detail_contains_expected_name(make_context("展开极光"), slot)


def test_epiphany_button_requires_exact_text_in_bottom_right_region() -> None:
    context = ScreenContext.from_ocr(
        [
            FakeOCRBox("靈光一閃", x=873, y=250, width=96, height=32),
            FakeOCRBox("當觸發靈光一閃，可賦予卡牌新的效果", x=839, y=289, width=329, height=21),
            FakeOCRBox("靈光一閃", x=1064, y=654, width=99, height=32),
        ],
        frame_id=1,
        captured_at=1.0,
        width=1280,
        height=720,
    )

    button = find_epiphany_button(context)

    assert button is not None
    assert button.x == 1064
    assert button.y == 654


def test_epiphany_help_text_or_card_list_header_is_not_a_button() -> None:
    context = ScreenContext.from_ocr(
        [
            FakeOCRBox("靈光一閃", x=873, y=250, width=96, height=32),
            FakeOCRBox("靈光一閃卡牌", x=112, y=480, width=160, height=30),
        ],
        frame_id=1,
        captured_at=1.0,
        width=1280,
        height=720,
    )

    assert find_epiphany_button(context) is None


def test_epiphany_overview_requires_title_and_outcome_explanation() -> None:
    assert is_epiphany_overview(
        make_context("靈光一閃", "卡牌可能會觸發以下的靈光一閃。", "展開極光")
    )
    assert is_epiphany_overview(
        make_context("灵光一闪", "卡牌可能会触发以下的灵光一闪。", "展开极光")
    )
    assert not is_epiphany_overview(
        make_context("靈光一閃", "當觸發靈光一閃，可賦予卡牌新的效果")
    )
