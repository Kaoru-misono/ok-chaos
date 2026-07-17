from __future__ import annotations

from src.chaos.cards.enums import RecognitionStatus, VariantKind
from src.chaos.cards.flash_recognizer import FlashEffectMatch, FlashRecognition, TextBounds
from src.chaos.cards.presentation import card_observation_info, flash_recognition_info
from src.chaos.cards.runtime_index import (
    ResolutionStatus,
    RuntimeCardResolution,
    RuntimeIndexSummary,
)
from src.chaos.cards.schema import BoundingBox, CardObservation


def test_common_flash_result_is_formatted_for_task_information() -> None:
    effect = FlashEffectMatch(
        effect_id="draw_1",
        kind=VariantKind.COMMON_FLASH,
        confidence=0.996,
        evidence_text="抽取1",
        bounds=TextBounds(616, 524, 65, 29),
        divine_marker_score=0.0,
        evidence_status="pending_human_review",
    )
    result = FlashRecognition(
        status=RecognitionStatus.RECOGNIZED,
        card_id="haide_mali/card_03",
        observed_card_name="劍之雨",
        card_confidence=0.998,
        base_layer_kind=VariantKind.COMMON_FLASH,
        variant_ids=("haide_mali/card_03/common_flash_draw_1",),
        common_effects=(effect,),
        reason="flash layers recognized",
    )

    info = flash_recognition_info(result, ocr_count=26)

    assert info["识别状态"] == "已识别"
    assert info["卡牌"] == "劍之雨"
    assert info["基础闪光层"] == "普通闪"
    assert info["普通闪"] == "抽取1（draw_1，100%）"
    assert info["神闪"] == "无"
    assert info["识别说明"] == "闪光层识别完成"
    assert info["OCR文本数量"] == 26
    assert info["保存截图"] == "否（仅在内存中识别）"


def test_pending_observation_is_explicitly_blocked_from_strategy() -> None:
    observation = CardObservation(
        instance_id="detail-1",
        status=RecognitionStatus.RECOGNIZED,
        bbox=BoundingBox(450, 58, 384, 590),
        card_id="haide_mali/card_03",
        variant_ids=("haide_mali/card_03/common_flash_draw_1",),
        observed_name="劍之雨",
        confidence=0.98,
    )
    resolution = RuntimeCardResolution(
        observation,
        ResolutionStatus.CARD_NOT_APPROVED,
    )
    summary = RuntimeIndexSummary(4, 0, 16, 30, 80, 44, 0)

    info = card_observation_info(observation, resolution, summary)

    assert info["观察实例"] == "detail-1"
    assert info["观察区域"] == "450,58 384×590"
    assert info["策略可用"] == "否"
    assert info["策略准入"] == "卡牌仅在候选索引中，尚未进入审核目录"
