from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from src.chaos.cards.collector import CaptureLabel, CardSampleWriter, load_sample_manifest
from src.chaos.cards.enums import ReviewStatus, SampleScene


@dataclass
class FakeBox:
    name: str
    x: int = 10
    y: int = 20
    width: int = 100
    height: int = 24
    confidence: float = 0.95


def test_writer_saves_png_and_pending_manifest_from_the_same_sample(tmp_path: Path) -> None:
    frame = np.zeros((72, 128, 3), dtype=np.uint8)
    frame[10:20, 20:40] = (0, 255, 0)
    label = CaptureLabel(
        SampleScene.CARD_DETAIL,
        owner_id="character_a",
        card_id="character_a/card_01",
    )

    manifest_path = CardSampleWriter(tmp_path).capture(
        frame,
        [FakeBox("示例卡"), FakeBox("")],
        label,
        game_version="1.2.3",
        captured_at=datetime(2026, 7, 17, 6, 0, tzinfo=UTC),
    )
    manifest = load_sample_manifest(manifest_path)

    assert manifest.review_status is ReviewStatus.PENDING
    assert manifest.label == label
    assert manifest.width == 128
    assert manifest.height == 72
    assert manifest.game_version == "1.2.3"
    assert [box.text for box in manifest.ocr] == ["示例卡"]
    assert manifest_path.parent.name == manifest.sample_id
    assert (manifest_path.parent / "frame.png").is_file()


def test_manifest_loader_detects_modified_image(tmp_path: Path) -> None:
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    manifest_path = CardSampleWriter(tmp_path).capture(
        frame,
        [],
        CaptureLabel(SampleScene.UNKNOWN),
    )
    (manifest_path.parent / "frame.png").write_bytes(b"not the captured image")

    with pytest.raises(ValueError, match="hash mismatch"):
        load_sample_manifest(manifest_path)


def test_variant_capture_label_must_match_the_base_card() -> None:
    with pytest.raises(ValueError, match="does not belong"):
        CaptureLabel(
            SampleScene.EPIPHANY,
            owner_id="character_a",
            card_id="character_a/card_01",
            variant_ids=("character_a/card_02/epiphany_a",),
        )


def test_capture_label_preserves_multiple_enhancement_layers() -> None:
    label = CaptureLabel(
        SampleScene.DIVINE_FLASH,
        owner_id="character_a",
        card_id="character_a/card_01",
        variant_ids=(
            "character_a/card_01/epiphany_a",
            "character_a/card_01/divine_flash_a",
        ),
    )

    assert CaptureLabel.from_dict(label.to_dict()) == label


def test_manifest_parser_rejects_unreviewed_extra_fields(tmp_path: Path) -> None:
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    manifest_path = CardSampleWriter(tmp_path).capture(
        frame,
        [],
        CaptureLabel(SampleScene.UNKNOWN),
    )
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    value["auto_promote_to_catalog"] = True
    manifest_path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown sample fields"):
        load_sample_manifest(manifest_path, verify_image=False)


def _write_mutated_manifest(tmp_path: Path, mutate) -> Path:
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    manifest_path = CardSampleWriter(tmp_path).capture(
        frame,
        [FakeBox("示例卡")],
        CaptureLabel(SampleScene.UNKNOWN),
    )
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutate(value)
    manifest_path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return manifest_path


def test_manifest_with_numeric_captured_at_fails_with_clear_error(tmp_path: Path) -> None:
    def mutate(value: dict) -> None:
        value["captured_at"] = 20260717

    manifest_path = _write_mutated_manifest(tmp_path, mutate)

    with pytest.raises(ValueError, match="ISO-8601"):
        load_sample_manifest(manifest_path, verify_image=False)


def test_manifest_ocr_entry_missing_field_fails_with_clear_error(tmp_path: Path) -> None:
    def mutate(value: dict) -> None:
        del value["ocr"][0]["confidence"]

    manifest_path = _write_mutated_manifest(tmp_path, mutate)

    with pytest.raises(ValueError, match="missing OCR evidence fields"):
        load_sample_manifest(manifest_path, verify_image=False)


def test_manifest_with_string_variant_ids_fails_with_clear_error(tmp_path: Path) -> None:
    def mutate(value: dict) -> None:
        value["label"]["variant_ids"] = "character_a/card_01/epiphany_a"

    manifest_path = _write_mutated_manifest(tmp_path, mutate)

    with pytest.raises(ValueError, match="variant_ids must be an array"):
        load_sample_manifest(manifest_path, verify_image=False)


def test_manifest_with_non_string_sha256_fails_with_clear_error(tmp_path: Path) -> None:
    def mutate(value: dict) -> None:
        value["image"]["sha256"] = 123456

    manifest_path = _write_mutated_manifest(tmp_path, mutate)

    with pytest.raises(ValueError, match="SHA-256"):
        load_sample_manifest(manifest_path, verify_image=False)


def test_validate_samples_lists_bad_manifest_instead_of_crashing(tmp_path: Path, capsys) -> None:
    from src.chaos.cards.cli import _validate_samples

    def mutate(value: dict) -> None:
        del value["ocr"][0]["confidence"]

    _write_mutated_manifest(tmp_path, mutate)

    assert _validate_samples(str(tmp_path)) == 1
    output = capsys.readouterr().out
    assert "样本校验失败" in output
    assert "missing OCR evidence fields" in output
