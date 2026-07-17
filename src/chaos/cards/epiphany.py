from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.chaos.cards.collector import (
    CaptureLabel,
    CardSampleWriter,
    OcrEvidence,
    load_sample_manifest,
)
from src.chaos.cards.enums import SampleScene

_REFERENCE_WIDTH = 1280
_REFERENCE_HEIGHT = 720


@dataclass(frozen=True, slots=True)
class EpiphanyVariantSlot:
    branch: str
    reference_bounds: tuple[int, int, int, int]

    def bounds_for(self, width: int, height: int) -> tuple[int, int, int, int]:
        if width <= 0 or height <= 0:
            raise ValueError("image dimensions must be positive")
        left, top, right, bottom = self.reference_bounds
        return (
            round(left * width / _REFERENCE_WIDTH),
            round(top * height / _REFERENCE_HEIGHT),
            round(right * width / _REFERENCE_WIDTH),
            round(bottom * height / _REFERENCE_HEIGHT),
        )

    @property
    def variant_suffix(self) -> str:
        return f"epiphany_{self.branch}"


EPIPHANY_VARIANT_SLOTS = tuple(
    EpiphanyVariantSlot(branch, (42 + index * 244, 226, 263 + index * 244, 555))
    for index, branch in enumerate("abcde")
)


@dataclass(frozen=True, slots=True)
class CroppedOcrBox:
    name: str
    x: int
    y: int
    width: int
    height: int
    confidence: float


@dataclass(frozen=True, slots=True)
class EpiphanySplitResult:
    manifests: tuple[Path, ...]
    created: int
    existing: int


def crop_epiphany_variant(
    frame: Any,
    evidence: Iterable[OcrEvidence],
    slot: EpiphanyVariantSlot,
) -> tuple[Any, tuple[CroppedOcrBox, ...]]:
    if frame is None or not hasattr(frame, "shape") or len(frame.shape) < 2:
        raise ValueError("epiphany frame must be an image array")
    height, width = int(frame.shape[0]), int(frame.shape[1])
    left, top, right, bottom = slot.bounds_for(width, height)
    crop = frame[top:bottom, left:right].copy()
    if crop.size == 0:
        raise ValueError("epiphany crop cannot be empty")

    cropped_boxes: list[CroppedOcrBox] = []
    for item in evidence:
        center_x = item.x + item.width / 2
        center_y = item.y + item.height / 2
        if not (left <= center_x < right and top <= center_y < bottom):
            continue
        item_left = max(item.x, left)
        item_top = max(item.y, top)
        item_right = min(item.x + item.width, right)
        item_bottom = min(item.y + item.height, bottom)
        if item_right <= item_left or item_bottom <= item_top:
            continue
        cropped_boxes.append(
            CroppedOcrBox(
                name=item.text,
                x=item_left - left,
                y=item_top - top,
                width=item_right - item_left,
                height=item_bottom - item_top,
                confidence=float(item.confidence),
            )
        )
    return crop, tuple(cropped_boxes)


def split_epiphany_overview(
    manifest_path: str | Path,
    output_root: str | Path,
) -> EpiphanySplitResult:
    import cv2

    source_path = Path(manifest_path)
    source = load_sample_manifest(source_path)
    if source.label.scene is not SampleScene.EPIPHANY:
        raise ValueError("source sample is not an epiphany overview")
    if source.label.variant_ids:
        raise ValueError("source sample is already an individual epiphany variant")
    if source.label.card_id is None or source.label.owner_id is None:
        raise ValueError("epiphany overview requires owner_id and card_id")

    frame = cv2.imread(str(source_path.parent / source.image_path), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError(f"failed to read epiphany image: {source_path.parent / source.image_path}")
    if int(frame.shape[1]) != source.width or int(frame.shape[0]) != source.height:
        raise ValueError("epiphany image dimensions do not match its manifest")

    timestamp = datetime.fromisoformat(source.captured_at.replace("Z", "+00:00"))
    date_folder = timestamp.strftime("%Y-%m-%d")
    writer = CardSampleWriter(output_root)
    manifests: list[Path] = []
    created = 0
    existing = 0

    for slot in EPIPHANY_VARIANT_SLOTS:
        variant_id = f"{source.label.card_id}/{slot.variant_suffix}"
        label = CaptureLabel(
            SampleScene.EPIPHANY,
            owner_id=source.label.owner_id,
            card_id=source.label.card_id,
            variant_ids=(variant_id,),
        )
        derived_sample_id = f"d{source.sample_id}-epiphany-{slot.branch}"
        expected_path = Path(output_root) / date_folder / derived_sample_id / "manifest.json"
        if expected_path.exists():
            existing_manifest = load_sample_manifest(expected_path)
            if existing_manifest.label != label:
                raise ValueError(f"derived sample label mismatch: {expected_path}")
            manifests.append(expected_path)
            existing += 1
            continue

        crop, boxes = crop_epiphany_variant(frame, source.ocr, slot)
        generated_path = writer.capture(
            crop,
            boxes,
            label,
            language=source.language,
            game_version=source.game_version,
            captured_at=timestamp,
            sample_id=derived_sample_id,
        )
        manifests.append(generated_path)
        created += 1

    return EpiphanySplitResult(tuple(manifests), created, existing)
