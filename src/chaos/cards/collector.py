from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.chaos.cards.enums import ReviewStatus, SampleScene
from src.chaos.cards.schema import SCHEMA_VERSION, validate_id_part, validate_qualified_id


@dataclass(frozen=True, slots=True)
class CaptureLabel:
    scene: SampleScene
    owner_id: str | None = None
    card_id: str | None = None
    variant_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.scene, SampleScene):
            object.__setattr__(self, "scene", SampleScene(self.scene))
        if self.owner_id is not None:
            object.__setattr__(self, "owner_id", validate_id_part(self.owner_id, "owner_id"))
        if self.card_id is not None:
            card_id = validate_qualified_id(self.card_id, "card_id")
            object.__setattr__(self, "card_id", card_id)
            if self.owner_id is not None and card_id.split("/", 1)[0] != self.owner_id:
                raise ValueError("card_id does not belong to owner_id")
        variants = tuple(self.variant_ids)
        if variants:
            if self.card_id is None:
                raise ValueError("variant_ids require card_id")
            normalized: list[str] = []
            for variant_id in variants:
                checked = validate_qualified_id(variant_id, "variant_id", parts=3)
                if "/".join(checked.split("/")[:2]) != self.card_id:
                    raise ValueError("variant_id does not belong to card_id")
                normalized.append(checked)
            if len(normalized) != len(set(normalized)):
                raise ValueError("variant_ids cannot contain duplicates")
            object.__setattr__(self, "variant_ids", tuple(normalized))
        else:
            object.__setattr__(self, "variant_ids", ())

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"scene": self.scene.value}
        for key in ("owner_id", "card_id"):
            value = getattr(self, key)
            if value is not None:
                result[key] = value
        if self.variant_ids:
            result["variant_ids"] = list(self.variant_ids)
        return result

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CaptureLabel:
        if not isinstance(value, dict):
            raise ValueError("label must be an object")
        unknown = set(value) - {"scene", "owner_id", "card_id", "variant_ids"}
        if unknown:
            raise ValueError(f"unknown label fields: {sorted(unknown)}")
        variant_ids = value.get("variant_ids", [])
        if not isinstance(variant_ids, (list, tuple)):
            raise ValueError("variant_ids must be an array of variant ids")
        return cls(
            scene=SampleScene(value.get("scene", SampleScene.UNKNOWN)),
            owner_id=value.get("owner_id"),
            card_id=value.get("card_id"),
            variant_ids=tuple(variant_ids),
        )


@dataclass(frozen=True, slots=True)
class OcrEvidence:
    text: str
    x: int
    y: int
    width: int
    height: int
    confidence: float

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("OCR evidence text cannot be blank")
        coordinates = (self.x, self.y, self.width, self.height)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in coordinates):
            raise ValueError("OCR evidence coordinates must be integers")
        if self.x < 0 or self.y < 0 or self.width < 0 or self.height < 0:
            raise ValueError("OCR evidence coordinates cannot be negative")
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)):
            raise ValueError("OCR confidence must be numeric")
        if not 0 <= float(self.confidence) <= 1:
            raise ValueError("OCR confidence must be between 0 and 1")

    @classmethod
    def from_box(cls, box: Any) -> OcrEvidence | None:
        text = str(getattr(box, "name", "") or "").strip()
        if not text:
            return None
        return cls(
            text=text,
            x=int(getattr(box, "x", 0)),
            y=int(getattr(box, "y", 0)),
            width=int(getattr(box, "width", 0)),
            height=int(getattr(box, "height", 0)),
            confidence=float(getattr(box, "confidence", 0.0) or 0.0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "confidence": round(float(self.confidence), 6),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> OcrEvidence:
        if not isinstance(value, dict):
            raise ValueError("OCR evidence must be an object")
        fields = {"text", "x", "y", "width", "height", "confidence"}
        unknown = set(value) - fields
        if unknown:
            raise ValueError(f"unknown OCR evidence fields: {sorted(unknown)}")
        missing = fields - set(value)
        if missing:
            raise ValueError(f"missing OCR evidence fields: {sorted(missing)}")
        return cls(**value)


@dataclass(frozen=True, slots=True)
class CardSampleManifest:
    sample_id: str
    captured_at: str
    review_status: ReviewStatus
    label: CaptureLabel
    image_path: str
    image_sha256: str
    width: int
    height: int
    ocr: tuple[OcrEvidence, ...]
    language: str = "zh-CN"
    game_version: str = "unknown"
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        validate_id_part(self.sample_id, "sample_id")
        if not isinstance(self.captured_at, str):
            raise ValueError("captured_at must be an ISO-8601 timestamp string")
        try:
            datetime.fromisoformat(self.captured_at.replace("Z", "+00:00"))
        except ValueError as exception:
            raise ValueError("captured_at must be an ISO-8601 timestamp") from exception
        if not isinstance(self.review_status, ReviewStatus):
            object.__setattr__(self, "review_status", ReviewStatus(self.review_status))
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"sample schema_version must be {SCHEMA_VERSION}")
        if self.image_path != "frame.png":
            raise ValueError("sample image_path must be frame.png")
        if (
            not isinstance(self.image_sha256, str)
            or len(self.image_sha256) != 64
            or any(char not in "0123456789abcdef" for char in self.image_sha256)
        ):
            raise ValueError("image_sha256 must be a lowercase SHA-256 digest")
        if isinstance(self.width, bool) or not isinstance(self.width, int) or self.width <= 0:
            raise ValueError("sample width must be a positive integer")
        if isinstance(self.height, bool) or not isinstance(self.height, int) or self.height <= 0:
            raise ValueError("sample height must be a positive integer")
        if not isinstance(self.ocr, tuple):
            object.__setattr__(self, "ocr", tuple(self.ocr))
        if not isinstance(self.language, str) or not self.language.strip():
            raise ValueError("sample language cannot be blank")
        if not isinstance(self.game_version, str) or not self.game_version.strip():
            raise ValueError("sample game_version cannot be blank")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "sample_id": self.sample_id,
            "captured_at": self.captured_at,
            "review_status": self.review_status.value,
            "label": self.label.to_dict(),
            "image": {
                "path": self.image_path,
                "sha256": self.image_sha256,
                "width": self.width,
                "height": self.height,
            },
            "ocr": [item.to_dict() for item in self.ocr],
            "environment": {"language": self.language, "game_version": self.game_version},
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CardSampleManifest:
        if not isinstance(value, dict):
            raise ValueError("sample manifest must be an object")
        unknown = set(value) - {
            "schema_version",
            "sample_id",
            "captured_at",
            "review_status",
            "label",
            "image",
            "ocr",
            "environment",
        }
        if unknown:
            raise ValueError(f"unknown sample fields: {sorted(unknown)}")
        image = value.get("image")
        environment = value.get("environment", {})
        ocr = value.get("ocr", [])
        if not isinstance(image, dict):
            raise ValueError("sample image must be an object")
        if set(image) - {"path", "sha256", "width", "height"}:
            raise ValueError("sample image has unknown fields")
        if not isinstance(environment, dict):
            raise ValueError("sample environment must be an object")
        if set(environment) - {"language", "game_version"}:
            raise ValueError("sample environment has unknown fields")
        if not isinstance(ocr, list):
            raise ValueError("sample OCR evidence must be an array")
        return cls(
            schema_version=value.get("schema_version"),
            sample_id=value.get("sample_id"),
            captured_at=value.get("captured_at"),
            review_status=ReviewStatus(value.get("review_status")),
            label=CaptureLabel.from_dict(value.get("label")),
            image_path=image.get("path"),
            image_sha256=image.get("sha256"),
            width=image.get("width"),
            height=image.get("height"),
            ocr=tuple(OcrEvidence.from_dict(item) for item in ocr),
            language=environment.get("language", "zh-CN"),
            game_version=environment.get("game_version", "unknown"),
        )


class CardSampleWriter:
    def __init__(self, output_root: str | Path) -> None:
        self.output_root = Path(output_root).expanduser()

    def capture(
        self,
        frame: Any,
        ocr_boxes: Iterable[Any],
        label: CaptureLabel,
        *,
        language: str = "zh-CN",
        game_version: str = "unknown",
        captured_at: datetime | None = None,
        sample_id: str | None = None,
    ) -> Path:
        import cv2

        if frame is None or not hasattr(frame, "shape") or len(frame.shape) < 2:
            raise ValueError("capture frame must be an image array")
        height, width = (int(frame.shape[0]), int(frame.shape[1]))
        if width <= 0 or height <= 0:
            raise ValueError("capture frame cannot be empty")
        ok, encoded = cv2.imencode(".png", frame)
        if not ok:
            raise ValueError("failed to encode capture frame as PNG")
        image_bytes = encoded.tobytes()

        timestamp = (captured_at or datetime.now(UTC)).astimezone(UTC)
        if sample_id is None:
            sample_id = f"s{timestamp.strftime('%Y%m%d-%H%M%S-%f')}-{uuid4().hex[:8]}"
        else:
            sample_id = validate_id_part(sample_id, "sample_id")
        sample_dir = self.output_root / timestamp.strftime("%Y-%m-%d") / sample_id
        sample_dir.mkdir(parents=True, exist_ok=False)
        image_path = sample_dir / "frame.png"
        image_temp = sample_dir / "frame.png.tmp"
        image_temp.write_bytes(image_bytes)
        image_temp.replace(image_path)

        evidence = tuple(item for box in ocr_boxes if (item := OcrEvidence.from_box(box)) is not None)
        manifest = CardSampleManifest(
            sample_id=sample_id,
            captured_at=timestamp.isoformat().replace("+00:00", "Z"),
            review_status=ReviewStatus.PENDING,
            label=label,
            image_path=image_path.name,
            image_sha256=hashlib.sha256(image_bytes).hexdigest(),
            width=width,
            height=height,
            ocr=evidence,
            language=language,
            game_version=game_version,
        )
        manifest_path = sample_dir / "manifest.json"
        manifest_temp = sample_dir / "manifest.json.tmp"
        manifest_temp.write_text(
            json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest_temp.replace(manifest_path)
        return manifest_path


def load_sample_manifest(path: str | Path, *, verify_image: bool = True) -> CardSampleManifest:
    manifest_path = Path(path)
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = CardSampleManifest.from_dict(value)
    if verify_image:
        image_path = manifest_path.parent / manifest.image_path
        image_bytes = image_path.read_bytes()
        digest = hashlib.sha256(image_bytes).hexdigest()
        if digest != manifest.image_sha256:
            raise ValueError(f"image hash mismatch: {image_path}")
    return manifest
