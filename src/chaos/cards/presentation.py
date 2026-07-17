from __future__ import annotations

from collections.abc import Iterable

from src.chaos.cards.enums import RecognitionStatus, VariantKind
from src.chaos.cards.flash_recognizer import FlashEffectMatch, FlashRecognition
from src.chaos.cards.runtime_index import (
    ResolutionStatus,
    RuntimeCardResolution,
    RuntimeIndexSummary,
)
from src.chaos.cards.schema import CardObservation

_STATUS_LABELS = {
    RecognitionStatus.RECOGNIZED: "已识别",
    RecognitionStatus.UNKNOWN: "未知",
    RecognitionStatus.UNSUPPORTED: "不支持",
}

_LAYER_LABELS = {
    VariantKind.BASE: "未识别到普通闪或专属闪",
    VariantKind.COMMON_FLASH: "普通闪",
    VariantKind.EPIPHANY: "专属灵光一闪",
    VariantKind.DIVINE_FLASH: "神闪",
    VariantKind.CHARACTER_ENHANCEMENT: "角色强化",
}

_REASON_LABELS = {
    "card identity was not recognized": "未识别到支持的角色牌卡名",
    "common flash and epiphany matched the mutually exclusive base layer": (
        "普通闪与专属灵光一闪同时命中，基础层存在冲突"
    ),
    "flash layers recognized": "闪光层识别完成",
    "no supported flash effect was recognized": "已识别卡牌，但未识别到支持的闪光效果",
    "effect text belongs to both common and divine pools without visual layer evidence": (
        "效果文字同时属于普通闪和神闪，但缺少图层视觉证据"
    ),
}


def _format_effects(matches: Iterable[FlashEffectMatch]) -> str:
    values = [
        f"{match.evidence_text}（{match.effect_id}，{match.confidence:.0%}）"
        for match in matches
    ]
    return "、".join(values) or "无"


def flash_recognition_info(result: FlashRecognition, *, ocr_count: int) -> dict[str, object]:
    """Create stable, user-facing fields for the ok-script task information panel."""

    return {
        "识别状态": _STATUS_LABELS[result.status],
        "卡牌": result.observed_card_name or "未知",
        "卡牌ID": result.card_id or "未知",
        "卡牌置信度": f"{result.card_confidence:.1%}",
        "基础闪光层": _LAYER_LABELS[result.base_layer_kind],
        "普通闪": _format_effects(result.common_effects),
        "专属灵光一闪": result.epiphany_variant_id or "无",
        "神闪": _format_effects(result.divine_effects),
        "组合变体": "、".join(result.variant_ids) or "无",
        "歧义候选": "、".join(result.ambiguous_effect_ids) or "无",
        "识别说明": _REASON_LABELS.get(result.reason, result.reason),
        "OCR文本数量": ocr_count,
        "保存截图": "否（仅在内存中识别）",
    }


def card_observation_info(
    observation: CardObservation,
    resolution: RuntimeCardResolution,
    index_summary: RuntimeIndexSummary,
) -> dict[str, object]:
    """Format the normalized observation and its reviewed-catalog admission result."""

    bbox = observation.bbox
    resolution_labels = {
        ResolutionStatus.READY: "已从审核目录实体化，可供策略读取",
        ResolutionStatus.OBSERVATION_UNKNOWN: "当前观察不够可靠，不进入策略层",
        ResolutionStatus.CARD_NOT_APPROVED: "卡牌仅在候选索引中，尚未进入审核目录",
        ResolutionStatus.VARIANT_NOT_APPROVED: "闪光变体尚未进入审核目录",
        ResolutionStatus.INVALID_VARIANT_COMBINATION: "变体组合不在运行时索引或不满足叠加规则",
    }
    unresolved = "、".join(resolution.unresolved_variant_ids)
    admission = resolution_labels[resolution.status]
    if unresolved:
        admission = f"{admission}：{unresolved}"
    return {
        "观察实例": observation.instance_id,
        "观察区域": f"{bbox.x},{bbox.y} {bbox.width}×{bbox.height}",
        "观察置信度": f"{observation.confidence:.1%}",
        "运行时状态": "、".join(state.value for state in observation.runtime_states) or "无",
        "运行时索引": (
            f"{index_summary.cards}张候选/{index_summary.approved_cards}张已审核，"
            f"{index_summary.variants}个候选变体/{index_summary.approved_variants}个已审核"
        ),
        "策略可用": "是" if resolution.decision_ready else "否",
        "策略准入": admission,
    }
