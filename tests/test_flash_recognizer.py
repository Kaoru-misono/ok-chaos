from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

from src.chaos.cards.collector import load_sample_manifest
from src.chaos.cards.enums import RecognitionStatus, VariantKind
from src.chaos.cards.flash_recognizer import (
    EpiphanySignature,
    FlashKnowledgeBase,
    FlashRecognizer,
)
from src.chaos.model import ScreenContext, TextBox

REPO_ROOT = Path(__file__).parents[1]
REFERENCE_PATH = REPO_ROOT / "datasets" / "cards" / "reference" / "haide_mali" / "flash_layers.pending.json"
SAMPLE_MANIFEST = (
    REPO_ROOT
    / "datasets"
    / "cards"
    / "inbox"
    / "2026-07-17"
    / "s20260717-114847-312497-2076b1a9"
    / "manifest.json"
)


def make_context(*boxes: TextBox, width: int = 1280, height: int = 720) -> ScreenContext:
    return ScreenContext(1, 0.0, width, height, boxes)


def load_knowledge() -> FlashKnowledgeBase:
    return FlashKnowledgeBase.from_reference_files(REFERENCE_PATH)


def test_real_sword_rain_sample_recognizes_common_draw_without_label_hint() -> None:
    manifest = load_sample_manifest(SAMPLE_MANIFEST)
    frame = cv2.imread(str(SAMPLE_MANIFEST.parent / manifest.image_path), cv2.IMREAD_COLOR)
    context = make_context(
        *(
            TextBox(item.text, item.x, item.y, item.width, item.height, float(item.confidence))
            for item in manifest.ocr
        )
    )

    result = FlashRecognizer(load_knowledge()).recognize(context, frame)

    assert result.status is RecognitionStatus.RECOGNIZED
    assert result.card_id == "haide_mali/card_03"
    assert result.observed_card_name == "劍之雨"
    assert result.base_layer_kind is VariantKind.COMMON_FLASH
    assert [match.effect_id for match in result.common_effects] == ["draw_1"]
    assert result.divine_effects == ()
    assert result.variant_ids == ("haide_mali/card_03/common_flash_draw_1",)


def test_fast_ocr_region_keeps_required_real_sample_evidence() -> None:
    manifest = load_sample_manifest(SAMPLE_MANIFEST)
    knowledge = load_knowledge()
    frame = cv2.imread(str(SAMPLE_MANIFEST.parent / manifest.image_path), cv2.IMREAD_COLOR)
    all_boxes = tuple(
        TextBox(item.text, item.x, item.y, item.width, item.height, float(item.confidence))
        for item in manifest.ocr
    )
    region_boxes = tuple(
        box
        for box in all_boxes
        if knowledge.layout.ocr_search.contains(box, manifest.width, manifest.height)
    )
    context = make_context(*region_boxes)

    result = FlashRecognizer(knowledge).recognize(context, frame)

    assert len(region_boxes) < len(all_boxes)
    assert result.status is RecognitionStatus.RECOGNIZED
    assert result.card_id == "haide_mali/card_03"
    assert result.variant_ids == ("haide_mali/card_03/common_flash_draw_1",)


def test_gold_marker_disambiguates_shared_draw_text_as_divine_flash() -> None:
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    frame[512:560, 565:607] = (0, 190, 255)
    context = make_context(
        TextBox("劍之雨", 555, 132, 102, 43, 0.99),
        TextBox("抽取1", 616, 524, 65, 29, 0.99),
    )

    result = FlashRecognizer(load_knowledge()).recognize(context, frame)

    assert result.status is RecognitionStatus.RECOGNIZED
    assert result.base_layer_kind is VariantKind.BASE
    assert result.common_effects == ()
    assert [match.effect_id for match in result.divine_effects] == ["draw_1"]
    assert result.variant_ids == ("haide_mali/card_03/divine_flash_draw_1",)
    assert result.divine_effects[0].divine_marker_score >= 0.3


def test_saved_web_reference_confirms_real_gold_marker_geometry() -> None:
    # Web images are weak structural references only, never approved gameplay samples.
    path = REPO_ROOT / "datasets" / "cards" / "reference" / "haide_mali" / "visual"
    frame = cv2.imread(str(path / "hero_to_all_unique_plus_divine.png"), cv2.IMREAD_COLOR)
    height, width = frame.shape[:2]
    context = make_context(
        TextBox("萬人的英雄", 43, 15, 118, 29, 0.99),
        TextBox("獲得1點AP", 116, 377, 90, 24, 0.99),
        width=width,
        height=height,
    )

    result = FlashRecognizer(load_knowledge()).recognize(context, frame)

    assert result.status is RecognitionStatus.RECOGNIZED
    assert result.base_layer_kind is VariantKind.BASE
    assert [match.effect_id for match in result.divine_effects] == ["gain_ap_1"]
    assert result.divine_effects[0].divine_marker_score >= 0.3


def test_specific_divine_text_does_not_also_create_generic_common_layer() -> None:
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    frame[512:560, 535:607] = (0, 190, 255)
    context = make_context(
        TextBox("劍之雨", 555, 132, 102, 43, 0.99),
        TextBox("抽取1張自身卡牌", 616, 524, 180, 29, 0.99),
    )

    result = FlashRecognizer(load_knowledge()).recognize(context, frame)

    assert result.status is RecognitionStatus.RECOGNIZED
    assert result.base_layer_kind is VariantKind.BASE
    assert result.common_effects == ()
    assert [match.effect_id for match in result.divine_effects] == ["draw_1_card_of_this_unit"]


def test_same_effect_can_exist_once_in_common_and_once_in_divine_layer() -> None:
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    frame[550:605, 565:607] = (0, 190, 255)
    context = make_context(
        TextBox("劍之雨", 555, 132, 102, 43, 0.99),
        TextBox("抽取1", 616, 500, 65, 29, 0.99),
        TextBox("抽取1", 616, 560, 65, 29, 0.99),
    )

    result = FlashRecognizer(load_knowledge()).recognize(context, frame)

    assert result.status is RecognitionStatus.RECOGNIZED
    assert [match.effect_id for match in result.common_effects] == ["draw_1"]
    assert [match.effect_id for match in result.divine_effects] == ["draw_1"]
    assert result.variant_ids == (
        "haide_mali/card_03/common_flash_draw_1",
        "haide_mali/card_03/divine_flash_draw_1",
    )


def test_shared_effect_without_pixels_is_reported_as_ambiguous() -> None:
    context = make_context(
        TextBox("劍之雨", 555, 132, 102, 43, 0.99),
        TextBox("抽取1", 616, 524, 65, 29, 0.99),
    )

    result = FlashRecognizer(load_knowledge()).recognize(context)

    assert result.status is RecognitionStatus.UNKNOWN
    assert result.variant_ids == ()
    assert result.ambiguous_effect_ids == ("draw_1",)


def test_explicit_sections_compose_common_and_divine_layers() -> None:
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    context = make_context(
        TextBox("劍之雨", 555, 132, 102, 43, 0.99),
        TextBox("通用閃光", 890, 100, 120, 30, 0.99),
        TextBox("抽取1", 900, 145, 65, 29, 0.99),
        TextBox("物主之閃光", 890, 210, 145, 30, 0.99),
        TextBox("此卡牌費用減少1", 900, 255, 190, 29, 0.99),
    )

    result = FlashRecognizer(load_knowledge()).recognize(context, frame)

    assert result.status is RecognitionStatus.RECOGNIZED
    assert [match.effect_id for match in result.common_effects] == ["draw_1"]
    assert [match.effect_id for match in result.divine_effects] == ["cost_minus_1"]
    assert result.variant_ids == (
        "haide_mali/card_03/common_flash_draw_1",
        "haide_mali/card_03/divine_flash_cost_minus_1",
    )


def test_epiphany_and_divine_can_be_composed() -> None:
    knowledge = replace(
        load_knowledge(),
        epiphanies=(
            EpiphanySignature(
                "haide_mali/card_04/epiphany_a",
                "haide_mali/card_04",
                ("抽取3。本回合內將這些卡牌連結。",),
            ),
        ),
    )
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    frame[550:590, 560:602] = (0, 190, 255)
    context = make_context(
        TextBox("萬人的英雄", 540, 132, 150, 43, 0.99),
        TextBox("抽取3", 560, 430, 70, 29, 0.99),
        TextBox("本回合內將這些卡牌連結", 530, 470, 260, 29, 0.99),
        TextBox("獲得1點AP", 610, 555, 110, 29, 0.99),
    )

    result = FlashRecognizer(knowledge).recognize(context, frame)

    assert result.status is RecognitionStatus.RECOGNIZED
    assert result.base_layer_kind is VariantKind.EPIPHANY
    assert result.epiphany_variant_id == "haide_mali/card_04/epiphany_a"
    assert [match.effect_id for match in result.divine_effects] == ["gain_ap_1"]
    assert result.variant_ids == (
        "haide_mali/card_04/epiphany_a",
        "haide_mali/card_04/divine_flash_gain_ap_1",
    )
