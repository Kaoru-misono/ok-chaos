from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.chaos.cards.collector import load_sample_manifest
from src.chaos.cards.enums import RecognitionStatus, VariantKind
from src.chaos.cards.flash_recognizer import (
    EpiphanySignature,
    FlashKnowledgeBase,
    FlashRecognitionLayout,
    FlashRecognizer,
)
from src.chaos.model import ScreenContext, TextBox

REPO_ROOT = Path(__file__).parents[1]
REFERENCE_PATH = REPO_ROOT / "datasets" / "cards" / "reference" / "haide_mali" / "flash_layers.pending.json"
EPIPHANY_PATH = REPO_ROOT / "datasets" / "cards" / "review" / "haide_mali" / "epiphany.pending.json"
SAMPLE_MANIFEST = (
    REPO_ROOT
    / "datasets"
    / "cards"
    / "inbox"
    / "2026-07-17"
    / "s20260717-114847-312497-2076b1a9"
    / "manifest.json"
)
BASE_HERO_MANIFEST = (
    REPO_ROOT
    / "datasets"
    / "cards"
    / "inbox"
    / "2026-07-17"
    / "s20260717-165108-416089-0041bee0"
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


def _load_base_hero_case() -> tuple[ScreenContext, object, FlashKnowledgeBase]:
    manifest = load_sample_manifest(BASE_HERO_MANIFEST)
    frame = cv2.imread(str(BASE_HERO_MANIFEST.parent / manifest.image_path), cv2.IMREAD_COLOR)
    boxes = tuple(
        TextBox(item.text, item.x, item.y, item.width, item.height, float(item.confidence))
        for item in manifest.ocr
    )
    context = make_context(*boxes, width=manifest.width, height=manifest.height)
    knowledge = FlashKnowledgeBase.from_reference_files(REFERENCE_PATH, EPIPHANY_PATH)
    return context, frame, knowledge


def test_real_base_hero_detail_does_not_claim_trait_gated_epiphany() -> None:
    # card_04 branch a keeps the base effect text and only adds a [連結] trait
    # tag, so the base detail page must stay base instead of matching epiphany_a.
    context, frame, knowledge = _load_base_hero_case()

    result = FlashRecognizer(knowledge).recognize(context, frame)

    assert result.card_id == "haide_mali/card_04"
    assert result.epiphany_variant_id is None
    assert result.variant_ids == ()


def test_link_trait_tag_unlocks_the_text_identical_epiphany_branch() -> None:
    context, frame, knowledge = _load_base_hero_case()
    tag_box = TextBox("[連結]", 1060, 862, 130, 70, 0.99)
    context = make_context(*context.texts, tag_box, width=context.width, height=context.height)

    result = FlashRecognizer(knowledge).recognize(context, frame)

    assert result.card_id == "haide_mali/card_04"
    assert result.epiphany_variant_id == "haide_mali/card_04/epiphany_a"
    assert result.base_layer_kind is VariantKind.EPIPHANY


def test_epiphany_signature_loads_required_trait_tags_from_pending_data() -> None:
    knowledge = FlashKnowledgeBase.from_reference_files(REFERENCE_PATH, EPIPHANY_PATH)
    signature = next(
        item for item in knowledge.epiphanies if item.variant_id == "haide_mali/card_04/epiphany_a"
    )

    assert signature.required_trait_tags == ("連結",)


def test_unknown_card_hint_is_not_forced_onto_first_catalog_card() -> None:
    # card_01 is intentionally absent from card_aliases: a hint outside the
    # knowledge base must yield "unknown", never the alphabetically-first card.
    context = make_context(TextBox("完全不像卡名的文字", 555, 132, 102, 43, 0.99))

    result = FlashRecognizer(load_knowledge()).recognize(
        context,
        card_id_hint="haide_mali/card_01",
    )

    assert result.status is RecognitionStatus.UNKNOWN
    assert result.card_id is None
    assert result.variant_ids == ()


def test_known_card_hint_still_backstops_weak_name_ocr() -> None:
    context = make_context(TextBox("鍺之丙", 555, 132, 102, 43, 0.4))

    result = FlashRecognizer(load_knowledge()).recognize(
        context,
        card_id_hint="haide_mali/card_03",
    )

    assert result.card_id == "haide_mali/card_03"
    assert result.card_confidence == pytest.approx(0.6)


def test_bgra_frame_still_detects_gold_marker() -> None:
    frame = np.zeros((720, 1280, 4), dtype=np.uint8)
    frame[512:560, 565:607] = (0, 190, 255, 255)
    context = make_context(
        TextBox("劍之雨", 555, 132, 102, 43, 0.99),
        TextBox("抽取1", 616, 524, 65, 29, 0.99),
    )

    result = FlashRecognizer(load_knowledge()).recognize(context, frame)

    assert result.status is RecognitionStatus.RECOGNIZED
    assert [match.effect_id for match in result.divine_effects] == ["draw_1"]


def test_partial_recognition_layout_falls_back_to_default_card_name_search() -> None:
    layout = FlashRecognitionLayout.from_dict(
        {"ocr_search": {"left": 0.2, "top": 0.1, "right": 0.8, "bottom": 0.9}}
    )

    assert layout.ocr_search.left == 0.2
    assert layout.card_name_search == FlashRecognitionLayout().card_name_search


def test_reference_candidate_missing_effect_id_raises_value_error(tmp_path: Path) -> None:
    reference = {
        "card_aliases": {"haide_mali/card_03": ["劍之雨"]},
        "effect_text_aliases": {},
        "haide_mali_common_flash_candidates": [
            {"card_id": "haide_mali/card_03", "candidates": [{"text_zh_cn": "抽取1"}]}
        ],
    }
    path = tmp_path / "reference.json"
    path.write_text(json.dumps(reference, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="effect_id"):
        FlashKnowledgeBase.from_reference_files(path)


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
