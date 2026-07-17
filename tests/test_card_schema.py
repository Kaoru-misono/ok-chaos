from __future__ import annotations

import pytest

from src.chaos.cards.effects import EffectAction, EffectSpec
from src.chaos.cards.enums import (
    CardType,
    EffectOp,
    RecognitionStatus,
    RuntimeCardState,
    TargetMode,
    Trigger,
    VariantKind,
)
from src.chaos.cards.schema import (
    BoundingBox,
    CardDefinition,
    CardObservation,
    CardVariant,
    LocalizedText,
    MaterializedCard,
)


def damage_effect() -> EffectSpec:
    return EffectSpec(
        trigger=Trigger.ON_PLAY,
        actions=(EffectAction(EffectOp.DAMAGE, {"base_value": 180, "scaling": "attack"}),),
    )


def make_card() -> CardDefinition:
    return CardDefinition(
        card_id="character_a/card_01",
        owner_id="character_a",
        slot=1,
        name=LocalizedText("示例卡牌", zh_tw="示例卡牌", aliases=("示例卡",)),
        card_type=CardType.ATTACK,
        base_cost=2,
        target=TargetMode.SINGLE_ENEMY,
        effects=(damage_effect(),),
        tags=("single_target", "damage"),
        raw_effect_text="造成伤害。",
    )


def test_card_round_trip_preserves_structured_effects() -> None:
    card = make_card()

    restored = CardDefinition.from_dict(card.to_dict())

    assert restored == card
    assert restored.effects[0].actions[0].params["base_value"] == 180
    assert restored.name.aliases == ("示例卡",)
    assert restored.name.zh_tw == "示例卡牌"


def test_variant_materialization_layers_changes_without_mutating_base() -> None:
    card = make_card()
    variant = CardVariant(
        variant_id="character_a/card_01/epiphany_b",
        base_card_id=card.card_id,
        kind=VariantKind.EPIPHANY,
        branch="b",
        cost_override=1,
        additional_effects=(
            EffectSpec(
                trigger=Trigger.ON_PLAY,
                actions=(EffectAction(EffectOp.DRAW, {"count": 1}),),
            ),
        ),
        tags_add=("draw",),
        tags_remove=("single_target",),
    )

    materialized = MaterializedCard.apply_variant(card, variant)

    assert materialized.variant_ids == (variant.variant_id,)
    assert materialized.base_cost == 1
    assert [action.op for effect in materialized.effects for action in effect.actions] == [
        EffectOp.DAMAGE,
        EffectOp.DRAW,
    ]
    assert materialized.tags == ("damage", "draw")
    assert card.base_cost == 2
    assert len(card.effects) == 1


def test_variant_cannot_remove_an_effect_that_does_not_exist() -> None:
    variant = CardVariant(
        variant_id="character_a/card_01/epiphany_a",
        base_card_id="character_a/card_01",
        kind=VariantKind.EPIPHANY,
        remove_effect_indexes=(2,),
    )

    with pytest.raises(ValueError, match="missing effect index"):
        MaterializedCard.apply_variant(make_card(), variant)


def test_unsupported_effect_keeps_required_raw_text() -> None:
    effect = EffectAction.from_dict(
        {"op": "unsupported", "params": {"raw_text": "尚未结构化的效果"}}
    )
    assert effect.op is EffectOp.UNSUPPORTED

    with pytest.raises(ValueError, match="raw_text"):
        EffectAction(EffectOp.UNSUPPORTED, {})


def test_count_operations_reject_non_positive_counts() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        EffectAction(EffectOp.DRAW, {"count": 0})


def test_damage_requires_positive_base_value_and_validates_optional_fields() -> None:
    EffectAction(EffectOp.DAMAGE, {"base_value": 630, "hits": 1, "target": "all_enemies"})
    with pytest.raises(ValueError, match="base_value"):
        EffectAction(EffectOp.DAMAGE, {"hits": 2})
    with pytest.raises(ValueError, match="hits"):
        EffectAction(EffectOp.DAMAGE, {"base_value": 100, "hits": 0})
    with pytest.raises(ValueError, match="TargetMode"):
        EffectAction(EffectOp.DAMAGE, {"base_value": 100, "target": "everyone"})


def test_create_card_requires_card_and_count_with_optional_zone() -> None:
    EffectAction(EffectOp.CREATE_CARD, {"card": "aurora_sword", "count": 6, "zone": "discard_pile"})
    with pytest.raises(ValueError, match="card"):
        EffectAction(EffectOp.CREATE_CARD, {"count": 2})
    with pytest.raises(ValueError, match="CardZone"):
        EffectAction(EffectOp.CREATE_CARD, {"card": "aurora_sword", "count": 2, "zone": "sideboard"})


def test_apply_status_and_gain_resource_validate_required_fields() -> None:
    EffectAction(EffectOp.APPLY_STATUS, {"status": "damage_up", "subject": {"card": "aurora_sword"}, "base_value": 30})
    with pytest.raises(ValueError, match="status"):
        EffectAction(EffectOp.APPLY_STATUS, {"subject": {}})
    with pytest.raises(ValueError, match="value"):
        EffectAction(EffectOp.GAIN_RESOURCE, {"resource": "aurora_light", "value": 0})


def test_recognized_observation_requires_a_catalog_identity() -> None:
    bbox = BoundingBox(10, 20, 120, 200)
    with pytest.raises(ValueError, match="requires card_id"):
        CardObservation("hand-1", RecognitionStatus.RECOGNIZED, bbox)

    unknown = CardObservation(
        "hand-1",
        RecognitionStatus.UNKNOWN,
        bbox,
        runtime_states=(RuntimeCardState.UNPLAYABLE,),
        confidence=0.3,
    )
    assert unknown.card_id is None
    assert unknown.runtime_states == (RuntimeCardState.UNPLAYABLE,)


def test_owner_and_qualified_ids_must_be_consistent() -> None:
    with pytest.raises(ValueError, match="start with owner_id"):
        CardDefinition(
            card_id="character_b/card_01",
            owner_id="character_a",
            slot=1,
            name=LocalizedText("示例"),
            card_type=CardType.SKILL,
            base_cost=1,
            target=TargetMode.SELF,
            effects=(),
        )
