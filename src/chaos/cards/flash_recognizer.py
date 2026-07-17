from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from opencc import OpenCC

from src.chaos.cards.enums import RecognitionStatus, VariantKind
from src.chaos.cards.schema import validate_id_part, validate_qualified_id
from src.chaos.model import ScreenContext, TextBox
from src.chaos.text import normalize_text

_TO_SIMPLIFIED = OpenCC("t2s")
_IGNORABLE_PUNCTUATION = re.compile(r"[\s，。,:：；;、·【】\[\]（）()「」『』《》<>]")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def normalize_flash_text(value: object) -> str:
    """Normalize OCR wording for matching without discarding effect numbers."""

    simplified = _TO_SIMPLIFIED.convert(str(value or ""))
    return _IGNORABLE_PUNCTUATION.sub("", normalize_text(simplified)).lower()


@dataclass(frozen=True, slots=True)
class RelativeRegion:
    left: float
    top: float
    right: float
    bottom: float

    def __post_init__(self) -> None:
        if not (0 <= self.left < self.right <= 1 and 0 <= self.top < self.bottom <= 1):
            raise ValueError("relative region coordinates must be ordered between 0 and 1")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> RelativeRegion:
        if not isinstance(value, dict):
            raise ValueError("relative region must be an object")
        missing = {"left", "top", "right", "bottom"} - set(value)
        if missing:
            raise ValueError(f"relative region is missing fields: {sorted(missing)}")
        try:
            return cls(
                left=float(value["left"]),
                top=float(value["top"]),
                right=float(value["right"]),
                bottom=float(value["bottom"]),
            )
        except TypeError as exception:
            raise ValueError("relative region coordinates must be numeric") from exception

    def contains(self, box: TextBox, width: int, height: int) -> bool:
        center_x, center_y = box.center
        return (
            self.left * width <= center_x <= self.right * width
            and self.top * height <= center_y <= self.bottom * height
        )


@dataclass(frozen=True, slots=True)
class DivineMarkerLayout:
    left_width_in_text_heights: float = 2.0
    vertical_padding_in_text_heights: float = 0.33
    hue_min: int = 8
    hue_max: int = 35
    saturation_min: int = 80
    value_min: int = 120
    score_threshold: float = 0.3

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> DivineMarkerLayout:
        return cls(**(value or {}))


@dataclass(frozen=True, slots=True)
class FlashRecognitionLayout:
    ocr_search: RelativeRegion = RelativeRegion(0.3, 0.08, 0.72, 0.9)
    card_name_search: RelativeRegion = RelativeRegion(0.34, 0.1, 0.68, 0.31)
    card_half_width: float = 0.15
    effect_top_offset_from_name_bottom: float = 0.27
    effect_bottom: float = 0.88
    section_height: float = 0.42
    section_horizontal_tolerance: float = 0.28
    common_header_aliases: tuple[str, ...] = ("通用闪光", "中立闪", "普通闪")
    divine_header_aliases: tuple[str, ...] = ("物主之闪光", "神之灵光一闪", "神光一闪", "神闪")
    divine_marker: DivineMarkerLayout = DivineMarkerLayout()

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> FlashRecognitionLayout:
        if not value:
            return cls()
        defaults = cls()
        return cls(
            ocr_search=RelativeRegion.from_dict(
                value.get(
                    "ocr_search",
                    {
                        "left": defaults.ocr_search.left,
                        "top": defaults.ocr_search.top,
                        "right": defaults.ocr_search.right,
                        "bottom": defaults.ocr_search.bottom,
                    },
                )
            ),
            card_name_search=RelativeRegion.from_dict(
                value.get(
                    "card_name_search",
                    {
                        "left": defaults.card_name_search.left,
                        "top": defaults.card_name_search.top,
                        "right": defaults.card_name_search.right,
                        "bottom": defaults.card_name_search.bottom,
                    },
                )
            ),
            card_half_width=float(value.get("card_half_width", defaults.card_half_width)),
            effect_top_offset_from_name_bottom=float(
                value.get("effect_top_offset_from_name_bottom", defaults.effect_top_offset_from_name_bottom)
            ),
            effect_bottom=float(value.get("effect_bottom", defaults.effect_bottom)),
            section_height=float(value.get("section_height", defaults.section_height)),
            section_horizontal_tolerance=float(
                value.get("section_horizontal_tolerance", defaults.section_horizontal_tolerance)
            ),
            common_header_aliases=tuple(value.get("common_header_aliases", defaults.common_header_aliases)),
            divine_header_aliases=tuple(value.get("divine_header_aliases", defaults.divine_header_aliases)),
            divine_marker=DivineMarkerLayout.from_dict(value.get("divine_marker")),
        )


@dataclass(frozen=True, slots=True)
class CardNameDefinition:
    card_id: str
    aliases: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "card_id", validate_qualified_id(self.card_id, "card_id"))
        if not self.aliases:
            raise ValueError("card aliases cannot be empty")


@dataclass(frozen=True, slots=True)
class FlashEffectDefinition:
    effect_id: str
    kind: VariantKind
    aliases: tuple[str, ...]
    card_ids: tuple[str, ...] = ()
    evidence_status: str = "pending"

    def __post_init__(self) -> None:
        object.__setattr__(self, "effect_id", validate_id_part(self.effect_id, "effect_id"))
        if not isinstance(self.kind, VariantKind):
            object.__setattr__(self, "kind", VariantKind(self.kind))
        if self.kind not in {VariantKind.COMMON_FLASH, VariantKind.DIVINE_FLASH}:
            raise ValueError("flash effect definitions must be common_flash or divine_flash")
        if not self.aliases:
            raise ValueError("flash effect aliases cannot be empty")
        object.__setattr__(
            self,
            "card_ids",
            tuple(validate_qualified_id(card_id, "card_id") for card_id in self.card_ids),
        )

    def applies_to(self, card_id: str) -> bool:
        return not self.card_ids or card_id in self.card_ids


@dataclass(frozen=True, slots=True)
class EpiphanySignature:
    variant_id: str
    base_card_id: str
    aliases: tuple[str, ...]
    evidence_status: str = "pending"
    # Trait tags (e.g. "連結") that must appear as standalone card-face tags before
    # this variant may match. Required when the branch effect text equals the base
    # card text and only the added trait distinguishes them.
    required_trait_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        variant_id = validate_qualified_id(self.variant_id, "variant_id", parts=3)
        base_card_id = validate_qualified_id(self.base_card_id, "base_card_id")
        if "/".join(variant_id.split("/")[:2]) != base_card_id:
            raise ValueError("epiphany variant_id must belong to base_card_id")
        if not self.aliases:
            raise ValueError("epiphany aliases cannot be empty")
        if not isinstance(self.evidence_status, str) or not self.evidence_status.strip():
            raise ValueError("epiphany evidence_status cannot be blank")
        object.__setattr__(self, "variant_id", variant_id)
        object.__setattr__(self, "base_card_id", base_card_id)
        object.__setattr__(self, "required_trait_tags", _unique_strings(self.required_trait_tags))


@dataclass(frozen=True, slots=True)
class FlashKnowledgeBase:
    cards: tuple[CardNameDefinition, ...]
    effects: tuple[FlashEffectDefinition, ...]
    epiphanies: tuple[EpiphanySignature, ...] = ()
    layout: FlashRecognitionLayout = FlashRecognitionLayout()

    @classmethod
    def from_reference_files(
        cls,
        reference_path: str | Path,
        epiphany_path: str | Path | None = None,
    ) -> FlashKnowledgeBase:
        reference = json.loads(Path(reference_path).read_text(encoding="utf-8"))
        card_aliases = reference.get("card_aliases", {})
        alias_map = reference.get("effect_text_aliases", {})
        cards = tuple(
            CardNameDefinition(card_id=card_id, aliases=tuple(aliases))
            for card_id, aliases in sorted(card_aliases.items())
        )

        effects: dict[tuple[VariantKind, str, tuple[str, ...]], FlashEffectDefinition] = {}
        for card in reference.get("haide_mali_common_flash_candidates", []):
            records = list(card.get("candidates", []))
            if recommended := card.get("recommended_candidate"):
                records.append(recommended)
            records.extend(card.get("conflicts", []))
            card_id = _require_field(card, "card_id", "common flash candidate group")
            for record in records:
                effect_id = _require_field(record, "effect_id", "common flash candidate")
                aliases = _unique_strings((record.get("text_zh_cn"), *alias_map.get(effect_id, [])))
                definition = FlashEffectDefinition(
                    effect_id=effect_id,
                    kind=VariantKind.COMMON_FLASH,
                    aliases=aliases,
                    card_ids=(card_id,),
                    evidence_status=str(record.get("evidence_level", card.get("pool_status", "pending"))),
                )
                effects[(definition.kind, definition.effect_id, definition.card_ids)] = definition

        divine_effect_ids: set[str] = set()
        legacy = reference.get("legacy_divine_flash_pool", {})
        for card_type, values in legacy.items():
            if card_type not in {"status", "source_ids"} and isinstance(values, list):
                divine_effect_ids.update(str(value) for value in values)
        for group in reference.get("new_divinity_specific_divine_flash_candidates", []):
            divine_effect_ids.update(str(value) for value in group.get("effect_ids", []))
        for effect_id in sorted(divine_effect_ids):
            aliases = _unique_strings(alias_map.get(effect_id, []))
            if not aliases:
                raise ValueError(f"missing text aliases for divine effect {effect_id}")
            definition = FlashEffectDefinition(
                effect_id=effect_id,
                kind=VariantKind.DIVINE_FLASH,
                aliases=aliases,
                evidence_status="pending_web_reference",
            )
            effects[(definition.kind, definition.effect_id, definition.card_ids)] = definition

        epiphanies: list[EpiphanySignature] = []
        if epiphany_path is not None and Path(epiphany_path).exists():
            document = json.loads(Path(epiphany_path).read_text(encoding="utf-8"))
            evidence_status = str(document.get("review_status", "pending"))
            for variant in document.get("variants", []):
                raw_text = variant.get("raw_effect_text_zh_tw") or variant.get("raw_effect_text_zh_cn")
                if raw_text:
                    epiphanies.append(
                        EpiphanySignature(
                            variant_id=_require_field(variant, "variant_id", "epiphany variant"),
                            base_card_id=_require_field(variant, "base_card_id", "epiphany variant"),
                            aliases=(raw_text,),
                            evidence_status=evidence_status,
                            required_trait_tags=_unique_strings(
                                (
                                    *variant.get("required_trait_tags_zh_tw", []),
                                    *variant.get("required_trait_tags_zh_cn", []),
                                )
                            ),
                        )
                    )

        return cls(
            cards=cards,
            effects=tuple(effects.values()),
            epiphanies=tuple(epiphanies),
            layout=FlashRecognitionLayout.from_dict(reference.get("recognition_layout")),
        )


@dataclass(frozen=True, slots=True)
class TextBounds:
    x: int
    y: int
    width: int
    height: int

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass(frozen=True, slots=True)
class FlashEffectMatch:
    effect_id: str
    kind: VariantKind
    confidence: float
    evidence_text: str
    bounds: TextBounds
    divine_marker_score: float
    evidence_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "effect_id": self.effect_id,
            "kind": self.kind.value,
            "confidence": round(self.confidence, 4),
            "evidence_text": self.evidence_text,
            "bounds": self.bounds.to_dict(),
            "divine_marker_score": round(self.divine_marker_score, 4),
            "evidence_status": self.evidence_status,
        }


@dataclass(frozen=True, slots=True)
class FlashRecognition:
    status: RecognitionStatus
    card_id: str | None
    observed_card_name: str | None
    card_confidence: float
    base_layer_kind: VariantKind
    variant_ids: tuple[str, ...]
    card_bounds: TextBounds | None = None
    common_effects: tuple[FlashEffectMatch, ...] = ()
    epiphany_variant_id: str | None = None
    epiphany_confidence: float = 0.0
    divine_effects: tuple[FlashEffectMatch, ...] = ()
    ambiguous_effect_ids: tuple[str, ...] = ()
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "card_id": self.card_id,
            "observed_card_name": self.observed_card_name,
            "card_bounds": None if self.card_bounds is None else self.card_bounds.to_dict(),
            "card_confidence": round(self.card_confidence, 4),
            "base_layer_kind": self.base_layer_kind.value,
            "variant_ids": list(self.variant_ids),
            "common_flash": [match.to_dict() for match in self.common_effects],
            "epiphany": (
                None
                if self.epiphany_variant_id is None
                else {
                    "variant_id": self.epiphany_variant_id,
                    "confidence": round(self.epiphany_confidence, 4),
                }
            ),
            "divine_flash": [match.to_dict() for match in self.divine_effects],
            "ambiguous_effect_ids": list(self.ambiguous_effect_ids),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class _EvidenceChunk:
    text: str
    boxes: tuple[TextBox, ...]

    @property
    def normalized_text(self) -> str:
        return normalize_flash_text(self.text)

    @property
    def confidence(self) -> float:
        return min(box.confidence for box in self.boxes)

    @property
    def bounds(self) -> TextBounds:
        left = min(box.x for box in self.boxes)
        top = min(box.y for box in self.boxes)
        right = max(box.x + box.width for box in self.boxes)
        bottom = max(box.y + box.height for box in self.boxes)
        return TextBounds(left, top, right - left, bottom - top)


@dataclass(frozen=True, slots=True)
class _RawEffectMatch:
    definition: FlashEffectDefinition
    alias: str
    evidence: _EvidenceChunk
    text_score: float


@dataclass(frozen=True, slots=True)
class _CardMatch:
    definition: CardNameDefinition
    box: TextBox
    confidence: float


class FlashRecognizer:
    def __init__(self, knowledge: FlashKnowledgeBase) -> None:
        self.knowledge = knowledge

    def recognize(
        self,
        context: ScreenContext,
        frame: Any | None = None,
        *,
        card_id_hint: str | None = None,
    ) -> FlashRecognition:
        card_match = self._match_card(context, card_id_hint)
        if card_match is None:
            return FlashRecognition(
                status=RecognitionStatus.UNKNOWN,
                card_id=None,
                observed_card_name=None,
                card_confidence=0.0,
                base_layer_kind=VariantKind.BASE,
                variant_ids=(),
                reason="card identity was not recognized",
            )

        card_id = card_match.definition.card_id
        card_bounds = self._detail_card_bounds(context, card_match.box)
        common_matches, divine_matches = self._match_explicit_sections(context, card_id)
        ambiguous: tuple[str, ...] = ()
        card_boxes = self._card_effect_boxes(context, card_match.box)
        chunks = _build_evidence_chunks(card_boxes, context.height)

        if not common_matches and not divine_matches:
            raw_common = self._match_definitions(
                (effect for effect in self.knowledge.effects if effect.kind is VariantKind.COMMON_FLASH),
                chunks,
                card_id,
            )
            raw_divine = self._match_definitions(
                (effect for effect in self.knowledge.effects if effect.kind is VariantKind.DIVINE_FLASH),
                chunks,
                card_id,
            )
            common_matches, divine_matches, ambiguous = self._classify_detail_matches(
                raw_common,
                raw_divine,
                frame,
            )

        epiphany_variant_id, epiphany_confidence = self._match_epiphany(card_id, chunks)
        if epiphany_variant_id is not None and common_matches:
            return FlashRecognition(
                status=RecognitionStatus.UNKNOWN,
                card_id=card_id,
                observed_card_name=card_match.box.text,
                card_confidence=card_match.confidence,
                base_layer_kind=VariantKind.BASE,
                variant_ids=(),
                card_bounds=card_bounds,
                common_effects=common_matches,
                epiphany_variant_id=epiphany_variant_id,
                epiphany_confidence=epiphany_confidence,
                divine_effects=divine_matches,
                reason="common flash and epiphany matched the mutually exclusive base layer",
            )

        base_layer_kind = VariantKind.BASE
        variant_ids: list[str] = []
        if epiphany_variant_id is not None:
            base_layer_kind = VariantKind.EPIPHANY
            variant_ids.append(epiphany_variant_id)
        elif common_matches:
            base_layer_kind = VariantKind.COMMON_FLASH
            variant_ids.append(
                compose_flash_variant_id(
                    card_id,
                    VariantKind.COMMON_FLASH,
                    (match.effect_id for match in common_matches),
                )
            )
        if divine_matches:
            variant_ids.append(
                compose_flash_variant_id(
                    card_id,
                    VariantKind.DIVINE_FLASH,
                    (match.effect_id for match in divine_matches),
                )
            )

        recognized = bool(common_matches or epiphany_variant_id or divine_matches) and not ambiguous
        reason = "flash layers recognized" if recognized else "no supported flash effect was recognized"
        if ambiguous:
            reason = "effect text belongs to both common and divine pools without visual layer evidence"
        return FlashRecognition(
            status=RecognitionStatus.RECOGNIZED if recognized else RecognitionStatus.UNKNOWN,
            card_id=card_id,
            observed_card_name=card_match.box.text,
            card_confidence=card_match.confidence,
            base_layer_kind=base_layer_kind,
            variant_ids=tuple(variant_ids),
            card_bounds=card_bounds,
            common_effects=common_matches,
            epiphany_variant_id=epiphany_variant_id,
            epiphany_confidence=epiphany_confidence,
            divine_effects=divine_matches,
            ambiguous_effect_ids=ambiguous,
            reason=reason,
        )

    def _match_card(self, context: ScreenContext, card_id_hint: str | None) -> _CardMatch | None:
        candidates = tuple(
            box
            for box in context.texts
            if self.knowledge.layout.card_name_search.contains(box, context.width, context.height)
        )
        if not candidates:
            candidates = context.texts
        definitions = self.knowledge.cards
        hinted: tuple[CardNameDefinition, ...] = ()
        if card_id_hint is not None:
            checked_hint = validate_qualified_id(card_id_hint, "card_id")
            hinted = tuple(definition for definition in definitions if definition.card_id == checked_hint)
            if hinted:
                definitions = hinted

        best: _CardMatch | None = None
        for definition in definitions:
            for alias in definition.aliases:
                for box in candidates:
                    score = _text_similarity(alias, box.text, enforce_numbers=False)
                    confidence = score * (0.7 + 0.3 * box.confidence)
                    if score >= 0.72 and (best is None or confidence > best.confidence):
                        best = _CardMatch(definition, box, confidence)
        if best is not None:
            return best
        if hinted and candidates:
            return _CardMatch(hinted[0], candidates[0], 0.6)
        return None

    def _detail_card_bounds(self, context: ScreenContext, name_box: TextBox) -> TextBounds:
        """Return the supported card-detail column represented by this observation."""

        layout = self.knowledge.layout
        center_x = name_box.center[0]
        left = max(0, round(center_x - layout.card_half_width * context.width))
        right = min(context.width, round(center_x + layout.card_half_width * context.width))
        top = max(0, round(layout.ocr_search.top * context.height))
        bottom = min(context.height, round(layout.ocr_search.bottom * context.height))
        return TextBounds(left, top, max(1, right - left), max(1, bottom - top))

    def _card_effect_boxes(self, context: ScreenContext, name_box: TextBox) -> tuple[TextBox, ...]:
        layout = self.knowledge.layout
        center_x = name_box.center[0]
        left = center_x - layout.card_half_width * context.width
        right = center_x + layout.card_half_width * context.width
        top = name_box.y + name_box.height + layout.effect_top_offset_from_name_bottom * context.height
        bottom = layout.effect_bottom * context.height
        return tuple(
            box
            for box in context.texts
            if left <= box.center[0] <= right and top <= box.center[1] <= bottom and box.confidence >= 0.5
        )

    def _match_explicit_sections(
        self,
        context: ScreenContext,
        card_id: str,
    ) -> tuple[tuple[FlashEffectMatch, ...], tuple[FlashEffectMatch, ...]]:
        common_header = _find_alias_box(context.texts, self.knowledge.layout.common_header_aliases)
        divine_header = _find_alias_box(context.texts, self.knowledge.layout.divine_header_aliases)
        all_headers = tuple(header for header in (common_header, divine_header) if header is not None)

        def match_section(header: TextBox | None, kind: VariantKind) -> tuple[FlashEffectMatch, ...]:
            if header is None:
                return ()
            layout = self.knowledge.layout
            lower_headers = [candidate.y for candidate in all_headers if candidate.y > header.y]
            section_bottom = min(
                min(lower_headers, default=context.height),
                header.y + layout.section_height * context.height,
            )
            tolerance = layout.section_horizontal_tolerance * context.width
            boxes = tuple(
                box
                for box in context.texts
                if box.y > header.y + header.height
                and box.y < section_bottom
                and abs(box.center[0] - header.center[0]) <= tolerance
            )
            chunks = _build_evidence_chunks(boxes, context.height)
            raw = self._match_definitions(
                (effect for effect in self.knowledge.effects if effect.kind is kind),
                chunks,
                card_id,
            )
            marker_score = 1.0 if kind is VariantKind.DIVINE_FLASH else 0.0
            return _dedupe_effect_matches(
                tuple(self._to_effect_match(match, marker_score, explicit_layer=True) for match in raw)
            )

        return (
            match_section(common_header, VariantKind.COMMON_FLASH),
            match_section(divine_header, VariantKind.DIVINE_FLASH),
        )

    def _match_definitions(
        self,
        definitions: Iterable[FlashEffectDefinition],
        chunks: tuple[_EvidenceChunk, ...],
        card_id: str,
    ) -> tuple[_RawEffectMatch, ...]:
        matches: list[_RawEffectMatch] = []
        for definition in definitions:
            if not definition.applies_to(card_id):
                continue
            definition_matches: list[_RawEffectMatch] = []
            for alias in definition.aliases:
                for evidence in chunks:
                    score = _text_similarity(alias, evidence.text)
                    candidate = _RawEffectMatch(definition, alias, evidence, score)
                    if score >= 0.8:
                        definition_matches.append(candidate)
            matches.extend(_dedupe_raw_effect_matches(tuple(definition_matches)))
        return _dedupe_raw_effect_matches(_drop_less_specific_matches(tuple(matches)))

    def _classify_detail_matches(
        self,
        raw_common: tuple[_RawEffectMatch, ...],
        raw_divine: tuple[_RawEffectMatch, ...],
        frame: Any | None,
    ) -> tuple[tuple[FlashEffectMatch, ...], tuple[FlashEffectMatch, ...], tuple[str, ...]]:
        common: list[FlashEffectMatch] = []
        divine: list[FlashEffectMatch] = []
        ambiguous: set[str] = set()
        threshold = self.knowledge.layout.divine_marker.score_threshold
        divine_with_scores = tuple(
            (match, self._divine_marker_score(frame, match.evidence.bounds)) for match in raw_divine
        )
        marked_divine = tuple((match, score) for match, score in divine_with_scores if score >= threshold)

        if frame is None:
            ambiguous.update(match.definition.effect_id for match in raw_divine)
        else:
            divine.extend(self._to_effect_match(match, score) for match, score in marked_divine)

        for common_match in raw_common:
            overlapping_divine = tuple(
                (divine_match, score)
                for divine_match, score in divine_with_scores
                if _bounds_overlap(common_match.evidence.bounds, divine_match.evidence.bounds) >= 0.5
            )
            if frame is None and overlapping_divine:
                ambiguous.add(common_match.definition.effect_id)
                continue
            if any(score >= threshold for _, score in overlapping_divine):
                continue
            marker_score = self._divine_marker_score(frame, common_match.evidence.bounds)
            common.append(self._to_effect_match(common_match, marker_score))

        return (
            _dedupe_effect_matches(tuple(common)),
            _dedupe_effect_matches(tuple(divine)),
            tuple(sorted(ambiguous)),
        )

    def _to_effect_match(
        self,
        match: _RawEffectMatch,
        marker_score: float,
        *,
        explicit_layer: bool = False,
    ) -> FlashEffectMatch:
        layer_confidence = 1.0 if explicit_layer else marker_score
        if match.definition.kind is VariantKind.COMMON_FLASH and not explicit_layer:
            layer_confidence = 1.0 - marker_score
        if match.definition.kind is VariantKind.DIVINE_FLASH and marker_score == 0 and not explicit_layer:
            layer_confidence = 0.7
        confidence = 0.8 * match.text_score + 0.2 * layer_confidence
        return FlashEffectMatch(
            effect_id=match.definition.effect_id,
            kind=match.definition.kind,
            confidence=confidence,
            evidence_text=match.evidence.text,
            bounds=match.evidence.bounds,
            divine_marker_score=marker_score,
            evidence_status=match.definition.evidence_status,
        )

    def _match_epiphany(
        self,
        card_id: str,
        chunks: tuple[_EvidenceChunk, ...],
    ) -> tuple[str | None, float]:
        best_variant: str | None = None
        best_score = 0.0
        for signature in self.knowledge.epiphanies:
            if signature.base_card_id != card_id:
                continue
            for alias in signature.aliases:
                for chunk in chunks:
                    score = _text_similarity(alias, chunk.text)
                    if score >= 0.84 and score > best_score:
                        if signature.required_trait_tags and not _trait_tags_present(
                            chunks,
                            signature.required_trait_tags,
                            effect_chunk=chunk,
                        ):
                            continue
                        best_variant = signature.variant_id
                        best_score = score
        return best_variant, best_score

    def _divine_marker_score(self, frame: Any | None, bounds: TextBounds) -> float:
        # The gold marker is a color cue: grayscale frames carry no evidence, and
        # WGC captures may arrive as BGRA instead of BGR.
        if frame is None or not hasattr(frame, "shape") or len(frame.shape) != 3:
            return 0.0
        if frame.shape[2] not in (3, 4):
            return 0.0
        import cv2
        import numpy as np

        height = max(bounds.height, 1)
        marker = self.knowledge.layout.divine_marker
        left_width = max(int(height * marker.left_width_in_text_heights), 20)
        padding = int(height * marker.vertical_padding_in_text_heights)
        frame_height, frame_width = frame.shape[:2]
        x1 = max(0, bounds.x - left_width)
        x2 = max(0, min(frame_width, bounds.x))
        y1 = max(0, bounds.y - padding)
        y2 = min(frame_height, bounds.y + bounds.height + padding)
        if x2 <= x1 or y2 <= y1:
            return 0.0
        region = frame[y1:y2, x1:x2]
        if region.shape[2] == 4:
            region = cv2.cvtColor(region, cv2.COLOR_BGRA2BGR)
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        mask = (
            (hsv[:, :, 0] >= marker.hue_min)
            & (hsv[:, :, 0] <= marker.hue_max)
            & (hsv[:, :, 1] >= marker.saturation_min)
            & (hsv[:, :, 2] >= marker.value_min)
        ).astype(np.uint8)
        if not mask.any():
            return 0.0
        component_count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
        largest_area = max((int(stats[index, cv2.CC_STAT_AREA]) for index in range(1, component_count)), default=0)
        ratio_score = float(mask.mean()) / 0.04
        area_score = largest_area / max(float(height * height * 0.12), 1.0)
        return min(1.0, max(ratio_score, area_score))


_TRAIT_BRACKETS = "[]【】"


def _trait_tags_present(
    chunks: tuple[_EvidenceChunk, ...],
    traits: tuple[str, ...],
    *,
    effect_chunk: _EvidenceChunk,
) -> bool:
    """Check that every trait renders as a standalone card-face tag like [連結].

    A tag chunk must equal the trait text after normalization and be either
    bracketed or positioned above the matched effect text, so that a line-wrap
    fragment of the effect sentence itself can never count as a tag.
    """

    effect_top = effect_chunk.bounds.y
    for trait in traits:
        normalized_trait = normalize_flash_text(trait)
        for chunk in chunks:
            if chunk is effect_chunk or chunk.normalized_text != normalized_trait:
                continue
            bracketed = any(char in chunk.text for char in _TRAIT_BRACKETS)
            bounds = chunk.bounds
            above_effect = bounds.y + bounds.height / 2 < effect_top
            if bracketed or above_effect:
                break
        else:
            return False
    return True


def _require_field(mapping: Any, key: str, context: str) -> Any:
    if not isinstance(mapping, dict) or key not in mapping:
        raise ValueError(f"{context} is missing required field '{key}'")
    return mapping[key]


def _unique_strings(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return tuple(result)


def _text_similarity(expected: object, actual: object, *, enforce_numbers: bool = True) -> float:
    expected_text = normalize_flash_text(expected)
    actual_text = normalize_flash_text(actual)
    if not expected_text or not actual_text:
        return 0.0
    if enforce_numbers:
        expected_numbers = _NUMBER.findall(expected_text)
        actual_numbers = _NUMBER.findall(actual_text)
        if expected_numbers and not _is_subsequence(expected_numbers, actual_numbers):
            return 0.0
    if expected_text == actual_text:
        return 1.0
    if expected_text in actual_text:
        coverage = len(expected_text) / len(actual_text)
        return 0.85 + 0.15 * coverage
    if actual_text in expected_text and len(actual_text) / len(expected_text) >= 0.75:
        coverage = len(actual_text) / len(expected_text)
        return 0.7 + 0.3 * coverage
    return SequenceMatcher(None, expected_text, actual_text).ratio()


def _is_subsequence(expected: list[str], actual: list[str]) -> bool:
    iterator = iter(actual)
    return all(any(candidate == value for candidate in iterator) for value in expected)


def _build_evidence_chunks(boxes: Iterable[TextBox], height: int) -> tuple[_EvidenceChunk, ...]:
    ordered = tuple(sorted((box for box in boxes if box.normalized_text), key=lambda box: (box.y, box.x)))
    if not ordered:
        return ()
    chunks: list[_EvidenceChunk] = [_EvidenceChunk(box.text, (box,)) for box in ordered]

    tolerance = max(8, int(height * 0.025))
    line_groups: list[list[TextBox]] = []
    for box in ordered:
        for group in line_groups:
            mean_center = sum(item.center[1] for item in group) / len(group)
            if abs(box.center[1] - mean_center) <= tolerance:
                group.append(box)
                break
        else:
            line_groups.append([box])
    for group in line_groups:
        if len(group) > 1:
            sorted_group = tuple(sorted(group, key=lambda box: box.x))
            chunks.append(_EvidenceChunk("".join(box.text for box in sorted_group), sorted_group))

    for start in range(len(ordered)):
        for length in range(2, min(6, len(ordered) - start + 1)):
            window = ordered[start : start + length]
            vertical_gap = max(
                (window[index + 1].center[1] - window[index].center[1] for index in range(len(window) - 1)),
                default=0,
            )
            if vertical_gap <= height * 0.1:
                chunks.append(_EvidenceChunk("".join(box.text for box in window), window))

    chunks.append(_EvidenceChunk("".join(box.text for box in ordered), ordered))
    unique: dict[tuple[str, int, int, int, int], _EvidenceChunk] = {}
    for chunk in chunks:
        bounds = chunk.bounds
        key = (chunk.normalized_text, bounds.x, bounds.y, bounds.width, bounds.height)
        unique[key] = chunk
    return tuple(unique.values())


def _find_alias_box(boxes: Iterable[TextBox], aliases: Iterable[str]) -> TextBox | None:
    best: tuple[float, TextBox] | None = None
    for box in boxes:
        for alias in aliases:
            score = _text_similarity(alias, box.text, enforce_numbers=False)
            if score >= 0.8 and (best is None or score > best[0]):
                best = (score, box)
    return None if best is None else best[1]


def _drop_less_specific_matches(matches: tuple[_RawEffectMatch, ...]) -> tuple[_RawEffectMatch, ...]:
    result: list[_RawEffectMatch] = []
    for match in matches:
        normalized_alias = normalize_flash_text(match.alias)
        less_specific = False
        for other in matches:
            if other is match or other.definition.kind is not match.definition.kind:
                continue
            other_alias = normalize_flash_text(other.alias)
            if (
                normalized_alias in other_alias
                and len(other_alias) > len(normalized_alias) + 2
                and other.text_score >= match.text_score
                and _bounds_overlap(match.evidence.bounds, other.evidence.bounds) >= 0.5
            ):
                less_specific = True
                break
        if not less_specific:
            result.append(match)
    return tuple(result)


def _dedupe_raw_effect_matches(matches: tuple[_RawEffectMatch, ...]) -> tuple[_RawEffectMatch, ...]:
    selected: list[_RawEffectMatch] = []
    ordered = sorted(
        matches,
        key=lambda match: (
            -match.text_score,
            match.evidence.bounds.width * match.evidence.bounds.height,
            match.evidence.bounds.y,
            match.evidence.bounds.x,
        ),
    )
    for match in ordered:
        duplicate = any(
            current.definition == match.definition
            and _bounds_overlap(current.evidence.bounds, match.evidence.bounds) >= 0.8
            for current in selected
        )
        if not duplicate:
            selected.append(match)
    return tuple(sorted(selected, key=lambda match: (match.evidence.bounds.y, match.evidence.bounds.x)))


def _bounds_overlap(first: TextBounds, second: TextBounds) -> float:
    left = max(first.x, second.x)
    top = max(first.y, second.y)
    right = min(first.x + first.width, second.x + second.width)
    bottom = min(first.y + first.height, second.y + second.height)
    if right <= left or bottom <= top:
        return 0.0
    intersection = (right - left) * (bottom - top)
    smaller = min(first.width * first.height, second.width * second.height)
    return intersection / max(smaller, 1)


def _dedupe_effect_matches(matches: tuple[FlashEffectMatch, ...]) -> tuple[FlashEffectMatch, ...]:
    by_id: dict[str, FlashEffectMatch] = {}
    for match in matches:
        current = by_id.get(match.effect_id)
        if current is None or match.confidence > current.confidence:
            by_id[match.effect_id] = match
    return tuple(sorted(by_id.values(), key=lambda match: (match.bounds.y, match.bounds.x, match.effect_id)))


def compose_flash_variant_id(
    card_id: str,
    kind: VariantKind,
    effect_ids: Iterable[str],
) -> str:
    """Build the stable variant ID shared by the recognizer and runtime index."""

    checked_card_id = validate_qualified_id(card_id, "card_id")
    checked_kind = kind if isinstance(kind, VariantKind) else VariantKind(kind)
    if checked_kind not in {VariantKind.COMMON_FLASH, VariantKind.DIVINE_FLASH}:
        raise ValueError("flash effect variant kind must be common_flash or divine_flash")
    checked_effect_ids = tuple(
        sorted({validate_id_part(effect_id, "effect_id") for effect_id in effect_ids})
    )
    if not checked_effect_ids:
        raise ValueError("flash effect variant requires at least one effect_id")
    suffix = f"{checked_kind.value}_{'__'.join(checked_effect_ids)}"
    return f"{checked_card_id}/{validate_id_part(suffix, 'variant_id')}"
