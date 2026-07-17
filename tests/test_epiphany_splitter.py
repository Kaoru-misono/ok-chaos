from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np

from src.chaos.cards.collector import CaptureLabel, CardSampleWriter, load_sample_manifest
from src.chaos.cards.enums import ReviewStatus, SampleScene
from src.chaos.cards.epiphany import EPIPHANY_VARIANT_SLOTS, split_epiphany_overview


@dataclass
class FakeBox:
    name: str
    x: int
    y: int
    width: int = 100
    height: int = 24
    confidence: float = 0.98


def test_reference_epiphany_layout_has_five_fixed_card_regions() -> None:
    assert [slot.branch for slot in EPIPHANY_VARIANT_SLOTS] == list("abcde")
    assert [slot.bounds_for(1280, 720) for slot in EPIPHANY_VARIANT_SLOTS] == [
        (42, 226, 263, 555),
        (286, 226, 507, 555),
        (530, 226, 751, 555),
        (774, 226, 995, 555),
        (1018, 226, 1239, 555),
    ]


def test_splitter_creates_idempotent_pending_variant_samples(tmp_path: Path) -> None:
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    boxes = [FakeBox("靈光一閃", x=590, y=50)]
    expected_colors: list[tuple[int, int, int]] = []
    for index, slot in enumerate(EPIPHANY_VARIANT_SLOTS, start=1):
        left, top, right, bottom = slot.bounds_for(1280, 720)
        color = (index * 20, index * 20 + 1, index * 20 + 2)
        expected_colors.append(color)
        frame[top:bottom, left:right] = color
        boxes.append(FakeBox(f"分支{slot.branch}", x=left + 20, y=top + 30))

    source_path = CardSampleWriter(tmp_path).capture(
        frame,
        boxes,
        CaptureLabel(
            SampleScene.EPIPHANY,
            owner_id="character_a",
            card_id="character_a/card_01",
        ),
        captured_at=datetime(2026, 7, 17, 9, 0, tzinfo=UTC),
        sample_id="soverview",
    )

    first = split_epiphany_overview(source_path, tmp_path)

    assert first.created == 5
    assert first.existing == 0
    assert len(first.manifests) == 5
    for index, (path, branch, expected_color) in enumerate(
        zip(first.manifests, "abcde", expected_colors, strict=True)
    ):
        manifest = load_sample_manifest(path)
        assert manifest.sample_id == f"dsoverview-epiphany-{branch}"
        assert manifest.review_status is ReviewStatus.PENDING
        assert manifest.label.variant_ids == (f"character_a/card_01/epiphany_{branch}",)
        assert manifest.width == 221
        assert manifest.height == 329
        assert [item.text for item in manifest.ocr] == [f"分支{branch}"]
        crop = cv2.imread(str(path.parent / "frame.png"), cv2.IMREAD_COLOR)
        assert tuple(int(value) for value in crop[100, 100]) == expected_color
        assert index == "abcde".index(branch)

    second = split_epiphany_overview(source_path, tmp_path)

    assert second.created == 0
    assert second.existing == 5
    assert second.manifests == first.manifests
