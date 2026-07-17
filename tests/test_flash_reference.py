from __future__ import annotations

import hashlib
import json
from pathlib import Path

REFERENCE_ROOT = Path(__file__).parents[1] / "datasets" / "cards" / "reference"
MANIFEST_PATH = REFERENCE_ROOT / "haide_mali" / "flash_layers.pending.json"


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_flash_reference_stays_pending_and_character_scoped() -> None:
    manifest = load_manifest()

    assert manifest["review_status"] == "pending"
    assert manifest["scope"]["owner_id"] == "haide_mali"
    assert manifest["scope"]["web_references_are_gameplay_samples"] is False
    assert manifest["scope"]["excludes"] == [
        "neutral_card_definitions",
        "monster_card_definitions",
    ]


def test_flash_layers_model_common_and_unique_as_exclusive_with_divine_overlay() -> None:
    rules = load_manifest()["composition_rules"]

    assert set(rules["base_flash_layer"]["variant_kinds"]) == {"common_flash", "epiphany"}
    assert rules["base_flash_layer"]["max_active"] == 1
    assert set(rules["divine_overlay_layer"]["can_stack_with"]) == {
        "base",
        "common_flash",
        "epiphany",
    }


def test_web_reference_images_match_recorded_size_and_hash() -> None:
    manifest = load_manifest()

    for reference in manifest["visual_references"]:
        path = REFERENCE_ROOT / reference["path"]
        content = path.read_bytes()
        assert len(content) == reference["bytes"]
        assert hashlib.sha256(content).hexdigest() == reference["sha256"]
        assert reference["review_status"] == "pending"
        assert reference["source_image_url"].startswith("https://")


def test_web_sources_are_attributed_and_use_https() -> None:
    manifest = load_manifest()
    source_ids = {source["source_id"] for source in manifest["sources"]}

    assert len(source_ids) == len(manifest["sources"])
    assert all(source["url"].startswith("https://") for source in manifest["sources"])
    assert all(reference["source_id"] in source_ids for reference in manifest["visual_references"])
