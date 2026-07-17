from __future__ import annotations

from pathlib import Path

import cv2
import pytest

from src.chaos.cards.catalog import CardCatalog
from src.chaos.cards.collector import load_sample_manifest
from src.chaos.cards.enums import (
    CardType,
    RecognitionStatus,
    TargetMode,
    VariantKind,
)
from src.chaos.cards.flash_recognizer import FlashKnowledgeBase
from src.chaos.cards.runtime_index import ResolutionStatus, RuntimeCardIndex
from src.chaos.cards.schema import (
    BoundingBox,
    CardDefinition,
    CardObservation,
    CardVariant,
    CharacterDefinition,
    LocalizedText,
)
from src.chaos.model import ScreenContext, TextBox

REPO_ROOT = Path(__file__).parents[1]
CATALOG_PATH = REPO_ROOT / "data" / "cards"
REFERENCE_PATH = (
    REPO_ROOT
    / "datasets"
    / "cards"
    / "reference"
    / "haide_mali"
    / "flash_layers.pending.json"
)
EPIPHANY_PATH = (
    REPO_ROOT
    / "datasets"
    / "cards"
    / "review"
    / "haide_mali"
    / "epiphany.pending.json"
)
SAMPLE_MANIFEST = (
    REPO_ROOT
    / "datasets"
    / "cards"
    / "inbox"
    / "2026-07-17"
    / "s20260717-114847-312497-2076b1a9"
    / "manifest.json"
)


def load_index(catalog: CardCatalog | None = None) -> RuntimeCardIndex:
    knowledge = FlashKnowledgeBase.from_reference_files(REFERENCE_PATH, EPIPHANY_PATH)
    return RuntimeCardIndex(catalog or CardCatalog.from_directory(CATALOG_PATH), knowledge)


def test_index_precompiles_read_only_name_effect_and_variant_tables() -> None:
    index = load_index()

    assert index.summary.cards == 4
    assert index.summary.approved_cards == 0
    assert index.summary.variants > 20
    assert index.summary.approved_variants == 0
    assert [record.card_id for record in index.lookup_card_name("劍之雨")] == [
        "haide_mali/card_03"
    ]
    draw_candidates = index.lookup_effect_text("抽取1")
    assert {candidate.kind for candidate in draw_candidates} == {
        VariantKind.COMMON_FLASH,
        VariantKind.DIVINE_FLASH,
    }
    with pytest.raises(TypeError):
        index.card_table["haide_mali/card_99"] = index.card_table["haide_mali/card_03"]  # type: ignore[index]


def test_real_sample_becomes_observation_but_is_not_strategy_approved() -> None:
    index = load_index()
    manifest = load_sample_manifest(SAMPLE_MANIFEST)
    frame = cv2.imread(str(SAMPLE_MANIFEST.parent / manifest.image_path), cv2.IMREAD_COLOR)
    context = ScreenContext(
        frame_id=7,
        captured_at=0.0,
        width=manifest.width,
        height=manifest.height,
        texts=tuple(
            TextBox(item.text, item.x, item.y, item.width, item.height, float(item.confidence))
            for item in manifest.ocr
        ),
    )

    result = index.recognize_flash(context, frame)
    observation = index.to_observation(result, context)
    resolution = index.resolve(observation)

    assert result.card_bounds is not None
    assert observation.instance_id == "detail-7"
    assert observation.status is RecognitionStatus.RECOGNIZED
    assert observation.card_id == "haide_mali/card_03"
    assert observation.variant_ids == ("haide_mali/card_03/common_flash_draw_1",)
    assert 0 <= observation.bbox.x < manifest.width
    assert 0 <= observation.bbox.y < manifest.height
    assert observation.bbox.x + observation.bbox.width <= manifest.width
    assert observation.bbox.y + observation.bbox.height <= manifest.height
    assert observation.confidence > 0.9
    assert observation.to_dict()["card_id"] == "haide_mali/card_03"
    assert resolution.status is ResolutionStatus.CARD_NOT_APPROVED
    assert not resolution.decision_ready


def test_reviewed_card_and_variant_can_be_materialized_for_strategy() -> None:
    owner = CharacterDefinition("haide_mali", LocalizedText("海德玛丽", "海德瑪麗"))
    card = CardDefinition(
        card_id="haide_mali/card_03",
        owner_id="haide_mali",
        slot=3,
        name=LocalizedText("剑之雨", "劍之雨"),
        card_type=CardType.ATTACK,
        base_cost=1,
        target=TargetMode.SINGLE_ENEMY,
        effects=(),
    )
    variant = CardVariant(
        variant_id="haide_mali/card_03/common_flash_draw_1",
        base_card_id=card.card_id,
        kind=VariantKind.COMMON_FLASH,
    )
    catalog = CardCatalog(
        owners={owner.owner_id: owner},
        cards={card.card_id: card},
        variants={variant.variant_id: variant},
    )
    index = load_index(catalog)
    observation = CardObservation(
        instance_id="detail-9",
        status=RecognitionStatus.RECOGNIZED,
        bbox=BoundingBox(400, 50, 380, 600),
        card_id=card.card_id,
        variant_ids=(variant.variant_id,),
        observed_name="劍之雨",
        confidence=0.99,
    )

    resolution = index.resolve(observation)

    assert index.summary.approved_cards == 1
    assert index.summary.approved_variants == 1
    assert resolution.status is ResolutionStatus.READY
    assert resolution.decision_ready
    assert resolution.materialized_card is not None
    assert resolution.materialized_card.variant_ids == (variant.variant_id,)
