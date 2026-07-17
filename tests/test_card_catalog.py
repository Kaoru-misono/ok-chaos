from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.chaos.cards.catalog import CardCatalog, CatalogError
from src.chaos.cards.enums import CardType, EffectOp, TargetMode, Trigger


def card_document(*, owner: str = "character_a", slot: int = 1) -> dict:
    card_id = f"{owner}/card_01"
    return {
        "schema_version": 1,
        "owner": {
            "owner_id": owner,
            "name": {"zh_cn": "示例角色", "zh_tw": "示例角色"},
        },
        "cards": [
            {
                "card_id": card_id,
                "slot": slot,
                "name": {"zh_cn": "示例卡"},
                "card_type": "attack",
                "base_cost": 2,
                "target": "single_enemy",
                "effects": [
                    {
                        "trigger": "on_play",
                        "actions": [{"op": "damage", "params": {"base_value": 180}}],
                    }
                ],
            }
        ],
        "variants": [
            {
                "variant_id": f"{card_id}/epiphany_a",
                "base_card_id": card_id,
                "kind": "epiphany",
                "cost_override": 1,
                "additional_effects": [
                    {
                        "trigger": "on_play",
                        "actions": [{"op": "draw", "params": {"count": 1}}],
                    }
                ],
            }
        ],
    }


def write_document(root: Path, name: str, document: dict) -> Path:
    character_root = root / "characters"
    character_root.mkdir(parents=True, exist_ok=True)
    path = character_root / name
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


def test_catalog_loads_and_materializes_a_character_variant(tmp_path: Path) -> None:
    write_document(tmp_path, "character_a.json", card_document())

    catalog = CardCatalog.from_directory(tmp_path)
    materialized = catalog.materialize("character_a/card_01", "character_a/card_01/epiphany_a")

    assert catalog.summary.owners == 1
    assert catalog.summary.cards == 1
    assert catalog.summary.variants == 1
    assert catalog.get_owner("character_a").name.zh_cn == "示例角色"
    assert materialized.base_cost == 1
    assert materialized.effects[-1].actions[0].op is EffectOp.DRAW


def test_catalog_layers_epiphany_before_divine_flash_regardless_of_input_order(tmp_path: Path) -> None:
    document = card_document()
    document["variants"].append(
        {
            "variant_id": "character_a/card_01/divine_flash_a",
            "base_card_id": "character_a/card_01",
            "kind": "divine_flash",
            "additional_effects": [
                {
                    "trigger": "on_play",
                    "actions": [{"op": "shield", "params": {"base_value": 50}}],
                }
            ],
        }
    )
    write_document(tmp_path, "character_a.json", document)
    catalog = CardCatalog.from_directory(tmp_path)

    materialized = catalog.materialize(
        "character_a/card_01",
        ["character_a/card_01/divine_flash_a", "character_a/card_01/epiphany_a"],
    )

    assert materialized.variant_ids == (
        "character_a/card_01/epiphany_a",
        "character_a/card_01/divine_flash_a",
    )
    assert [effect.actions[0].op for effect in materialized.effects] == [
        EffectOp.DAMAGE,
        EffectOp.DRAW,
        EffectOp.SHIELD,
    ]


def test_catalog_layers_common_flash_before_divine_flash_regardless_of_input_order(tmp_path: Path) -> None:
    document = card_document()
    document["variants"] = [
        {
            "variant_id": "character_a/card_01/common_flash_draw",
            "base_card_id": "character_a/card_01",
            "kind": "common_flash",
            "additional_effects": [
                {
                    "trigger": "on_play",
                    "actions": [{"op": "draw", "params": {"count": 1}}],
                }
            ],
        },
        {
            "variant_id": "character_a/card_01/divine_flash_a",
            "base_card_id": "character_a/card_01",
            "kind": "divine_flash",
            "additional_effects": [
                {
                    "trigger": "on_play",
                    "actions": [{"op": "shield", "params": {"base_value": 50}}],
                }
            ],
        },
    ]
    write_document(tmp_path, "character_a.json", document)
    catalog = CardCatalog.from_directory(tmp_path)

    materialized = catalog.materialize(
        "character_a/card_01",
        ["character_a/card_01/divine_flash_a", "character_a/card_01/common_flash_draw"],
    )

    assert materialized.variant_ids == (
        "character_a/card_01/common_flash_draw",
        "character_a/card_01/divine_flash_a",
    )
    assert [effect.actions[0].op for effect in materialized.effects] == [
        EffectOp.DAMAGE,
        EffectOp.DRAW,
        EffectOp.SHIELD,
    ]


def test_catalog_rejects_two_active_variants_from_the_same_layer(tmp_path: Path) -> None:
    document = card_document()
    document["variants"].append(
        {
            "variant_id": "character_a/card_01/epiphany_b",
            "base_card_id": "character_a/card_01",
            "kind": "epiphany",
        }
    )
    write_document(tmp_path, "character_a.json", document)
    catalog = CardCatalog.from_directory(tmp_path)

    with pytest.raises(CatalogError, match="one variant from each"):
        catalog.materialize(
            "character_a/card_01",
            ["character_a/card_01/epiphany_a", "character_a/card_01/epiphany_b"],
        )


def test_catalog_rejects_common_flash_combined_with_epiphany(tmp_path: Path) -> None:
    document = card_document()
    document["variants"].append(
        {
            "variant_id": "character_a/card_01/common_flash_draw",
            "base_card_id": "character_a/card_01",
            "kind": "common_flash",
        }
    )
    write_document(tmp_path, "character_a.json", document)
    catalog = CardCatalog.from_directory(tmp_path)

    with pytest.raises(CatalogError, match="one variant from each"):
        catalog.materialize(
            "character_a/card_01",
            ["character_a/card_01/common_flash_draw", "character_a/card_01/epiphany_a"],
        )


def test_catalog_rejects_duplicate_character_slots(tmp_path: Path) -> None:
    document = card_document()
    second_card = json.loads(json.dumps(document["cards"][0]))
    second_card["card_id"] = "character_a/card_02"
    document["cards"].append(second_card)
    write_document(tmp_path, "character_a.json", document)

    with pytest.raises(CatalogError, match="slot 1"):
        CardCatalog.from_directory(tmp_path)


def test_catalog_rejects_variants_that_reference_missing_cards(tmp_path: Path) -> None:
    document = card_document()
    document["cards"] = []
    write_document(tmp_path, "orphan.json", document)

    with pytest.raises(CatalogError, match="references missing card"):
        CardCatalog.from_directory(tmp_path)


def test_catalog_rejects_out_of_scope_origin_fields(tmp_path: Path) -> None:
    document = card_document()
    document["origin"] = "neutral"
    write_document(tmp_path, "neutral.json", document)

    with pytest.raises(CatalogError, match="unknown catalog fields"):
        CardCatalog.from_directory(tmp_path)


def test_empty_character_catalog_is_valid(tmp_path: Path) -> None:
    (tmp_path / "characters").mkdir()

    catalog = CardCatalog.from_directory(tmp_path)

    assert catalog.summary.cards == 0
    assert catalog.summary.source_files == 0


def test_unplayable_base_cost_sentinel_is_accepted(tmp_path: Path) -> None:
    document = card_document()
    document["variants"] = []
    document["cards"][0]["base_cost"] = -1
    write_document(tmp_path, "character_a.json", document)

    catalog = CardCatalog.from_directory(tmp_path)

    assert catalog.get_card("character_a/card_01").base_cost == -1


def test_negative_base_cost_other_than_sentinel_is_rejected(tmp_path: Path) -> None:
    document = card_document()
    document["variants"] = []
    document["cards"][0]["base_cost"] = -2
    write_document(tmp_path, "character_a.json", document)

    with pytest.raises(CatalogError, match="base_cost"):
        CardCatalog.from_directory(tmp_path)


def test_shipped_haide_mali_catalog_matches_reviewed_baseline() -> None:
    catalog = CardCatalog.from_directory(Path(__file__).parents[1] / "data" / "cards")

    assert catalog.summary.owners == 1
    assert catalog.summary.cards == 7
    cards = catalog.cards_for_owner("haide_mali")
    assert [card.card_id for card in cards] == [f"haide_mali/card_0{index}" for index in range(1, 8)]

    sword_rain = catalog.get_card("haide_mali/card_03")
    assert sword_rain.name.zh_tw == "劍之雨"
    assert sword_rain.card_type is CardType.ATTACK
    assert sword_rain.base_cost == 1
    assert sword_rain.tags == ("link",)

    aurora = catalog.get_card("haide_mali/card_07")
    assert aurora.base_cost == -1
    assert aurora.target is TargetMode.NONE

    light = catalog.get_card("haide_mali/card_05")
    assert "縷光芒" in light.name.aliases


def test_shipped_haide_mali_effects_are_structured_where_unambiguous() -> None:
    catalog = CardCatalog.from_directory(Path(__file__).parents[1] / "data" / "cards")

    # 剑之雨: 101%×2 on play, plus a 感應 (on-draw) aurora-sword generation.
    sword_rain = catalog.get_card("haide_mali/card_03")
    on_play, on_draw = sword_rain.effects
    assert on_play.trigger is Trigger.ON_PLAY
    damage = on_play.actions[0]
    assert damage.op is EffectOp.DAMAGE
    assert damage.params["base_value"] == 101
    assert damage.params["hits"] == 2
    assert on_draw.trigger is Trigger.ON_DRAW
    assert on_draw.actions[0].op is EffectOp.CREATE_CARD

    # 凝结极光 fires on moving to grave and gains the aurora-light resource.
    aurora = catalog.get_card("haide_mali/card_07")
    assert aurora.effects[0].trigger is Trigger.ON_MOVE_TO_GRAVE
    assert aurora.effects[0].actions[0].op is EffectOp.GAIN_RESOURCE


def test_sword_rain_common_flash_layers_draw_onto_base_damage() -> None:
    catalog = CardCatalog.from_directory(Path(__file__).parents[1] / "data" / "cards")

    materialized = catalog.materialize(
        "haide_mali/card_03", "haide_mali/card_03/common_flash_draw_1"
    )

    ops = [action.op for effect in materialized.effects for action in effect.actions]
    assert EffectOp.DAMAGE in ops
    assert EffectOp.DRAW in ops


def test_ambiguous_effects_stay_unsupported_pending_review() -> None:
    catalog = CardCatalog.from_directory(Path(__file__).parents[1] / "data" / "cards")

    # 一缕光芒's dynamic "+120% per link card" is preserved verbatim, not guessed.
    light = catalog.get_card("haide_mali/card_05")
    actions = [action for effect in light.effects for action in effect.actions]
    unsupported = [action for action in actions if action.op is EffectOp.UNSUPPORTED]
    assert len(unsupported) == 1
    assert "連結卡牌數量" in unsupported[0].params["raw_text"]
