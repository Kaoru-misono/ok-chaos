from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from src.chaos.cards.catalog import CardCatalog, CatalogError
from src.chaos.cards.enums import RecognitionStatus, VariantKind
from src.chaos.cards.flash_recognizer import (
    FlashEffectDefinition,
    FlashKnowledgeBase,
    FlashRecognition,
    FlashRecognizer,
    compose_flash_variant_id,
    normalize_flash_text,
)
from src.chaos.cards.schema import BoundingBox, CardObservation, MaterializedCard
from src.chaos.model import ScreenContext


@dataclass(frozen=True, slots=True)
class RuntimeCardRecord:
    card_id: str
    aliases: tuple[str, ...]
    catalog_approved: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "card_id": self.card_id,
            "aliases": list(self.aliases),
            "catalog_approved": self.catalog_approved,
        }


@dataclass(frozen=True, slots=True)
class RuntimeEffectCandidate:
    effect_id: str
    kind: VariantKind
    aliases: tuple[str, ...]
    card_ids: tuple[str, ...]
    evidence_status: str

    def applies_to(self, card_id: str) -> bool:
        return not self.card_ids or card_id in self.card_ids

    def to_dict(self) -> dict[str, object]:
        return {
            "effect_id": self.effect_id,
            "kind": self.kind.value,
            "aliases": list(self.aliases),
            "card_ids": list(self.card_ids),
            "evidence_status": self.evidence_status,
        }


@dataclass(frozen=True, slots=True)
class RuntimeVariantRecord:
    variant_id: str
    card_id: str
    kind: VariantKind
    effect_ids: tuple[str, ...]
    evidence_statuses: tuple[str, ...]
    catalog_approved: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "variant_id": self.variant_id,
            "card_id": self.card_id,
            "kind": self.kind.value,
            "effect_ids": list(self.effect_ids),
            "evidence_statuses": list(self.evidence_statuses),
            "catalog_approved": self.catalog_approved,
        }


@dataclass(frozen=True, slots=True)
class RuntimeIndexSummary:
    cards: int
    approved_cards: int
    name_keys: int
    effects: int
    effect_keys: int
    variants: int
    approved_variants: int

    def to_dict(self) -> dict[str, int]:
        return {
            "cards": self.cards,
            "approved_cards": self.approved_cards,
            "name_keys": self.name_keys,
            "effects": self.effects,
            "effect_keys": self.effect_keys,
            "variants": self.variants,
            "approved_variants": self.approved_variants,
        }


class ResolutionStatus(StrEnum):
    READY = "ready"
    OBSERVATION_UNKNOWN = "observation_unknown"
    CARD_NOT_APPROVED = "card_not_approved"
    VARIANT_NOT_APPROVED = "variant_not_approved"
    INVALID_VARIANT_COMBINATION = "invalid_variant_combination"


@dataclass(frozen=True, slots=True)
class RuntimeCardResolution:
    observation: CardObservation
    status: ResolutionStatus
    materialized_card: MaterializedCard | None = None
    unresolved_variant_ids: tuple[str, ...] = ()

    @property
    def decision_ready(self) -> bool:
        return self.status is ResolutionStatus.READY and self.materialized_card is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "decision_ready": self.decision_ready,
            "card_id": self.observation.card_id,
            "variant_ids": list(self.observation.variant_ids),
            "unresolved_variant_ids": list(self.unresolved_variant_ids),
        }


class RuntimeCardIndex:
    """Immutable runtime lookups plus the approval gate for strategy consumers."""

    def __init__(self, catalog: CardCatalog, knowledge: FlashKnowledgeBase) -> None:
        self.catalog = catalog
        self.knowledge = knowledge
        self._recognizer = FlashRecognizer(knowledge)

        cards = self._build_cards(catalog, knowledge)
        effects = tuple(
            RuntimeEffectCandidate(
                effect_id=definition.effect_id,
                kind=definition.kind,
                aliases=definition.aliases,
                card_ids=definition.card_ids,
                evidence_status=definition.evidence_status,
            )
            for definition in knowledge.effects
        )
        variants = self._build_variants(catalog, knowledge, cards)

        self.card_table: Mapping[str, RuntimeCardRecord] = MappingProxyType(cards)
        self.effect_candidates = effects
        self.variant_table: Mapping[str, RuntimeVariantRecord] = MappingProxyType(variants)
        self.name_table: Mapping[str, tuple[str, ...]] = MappingProxyType(
            self._build_name_table(cards.values())
        )
        self.effect_table: Mapping[str, tuple[RuntimeEffectCandidate, ...]] = MappingProxyType(
            self._build_effect_table(effects)
        )
        self.summary = RuntimeIndexSummary(
            cards=len(cards),
            approved_cards=sum(record.catalog_approved for record in cards.values()),
            name_keys=len(self.name_table),
            effects=len(effects),
            effect_keys=len(self.effect_table),
            variants=len(variants),
            approved_variants=sum(record.catalog_approved for record in variants.values()),
        )

    @staticmethod
    def _build_cards(
        catalog: CardCatalog,
        knowledge: FlashKnowledgeBase,
    ) -> dict[str, RuntimeCardRecord]:
        aliases_by_card = {
            definition.card_id: list(definition.aliases) for definition in knowledge.cards
        }
        for card in catalog.all_cards():
            aliases = aliases_by_card.setdefault(card.card_id, [])
            aliases.extend((card.name.zh_cn, card.name.zh_tw, *card.name.aliases))

        records: dict[str, RuntimeCardRecord] = {}
        for card_id, aliases in sorted(aliases_by_card.items()):
            records[card_id] = RuntimeCardRecord(
                card_id=card_id,
                aliases=_unique_nonblank(aliases),
                catalog_approved=catalog.get_card(card_id) is not None,
            )
        return records

    @staticmethod
    def _build_name_table(
        records: Iterable[RuntimeCardRecord],
    ) -> dict[str, tuple[str, ...]]:
        values: dict[str, set[str]] = {}
        for record in records:
            for alias in record.aliases:
                normalized = normalize_flash_text(alias)
                if normalized:
                    values.setdefault(normalized, set()).add(record.card_id)
        return {key: tuple(sorted(card_ids)) for key, card_ids in sorted(values.items())}

    @staticmethod
    def _build_effect_table(
        effects: Iterable[RuntimeEffectCandidate],
    ) -> dict[str, tuple[RuntimeEffectCandidate, ...]]:
        values: dict[str, set[RuntimeEffectCandidate]] = {}
        for effect in effects:
            for alias in effect.aliases:
                normalized = normalize_flash_text(alias)
                if normalized:
                    values.setdefault(normalized, set()).add(effect)
        return {
            key: tuple(
                sorted(
                    candidates,
                    key=lambda candidate: (
                        candidate.kind.value,
                        candidate.effect_id,
                        candidate.card_ids,
                    ),
                )
            )
            for key, candidates in sorted(values.items())
        }

    @staticmethod
    def _build_variants(
        catalog: CardCatalog,
        knowledge: FlashKnowledgeBase,
        cards: Mapping[str, RuntimeCardRecord],
    ) -> dict[str, RuntimeVariantRecord]:
        records: dict[str, RuntimeVariantRecord] = {}
        for signature in knowledge.epiphanies:
            records[signature.variant_id] = RuntimeVariantRecord(
                variant_id=signature.variant_id,
                card_id=signature.base_card_id,
                kind=VariantKind.EPIPHANY,
                effect_ids=(),
                evidence_statuses=(signature.evidence_status,),
                catalog_approved=False,
            )

        for definition in knowledge.effects:
            card_ids = definition.card_ids or tuple(cards)
            for card_id in card_ids:
                if card_id not in cards:
                    continue
                variant_id = compose_flash_variant_id(
                    card_id,
                    definition.kind,
                    (definition.effect_id,),
                )
                records[variant_id] = RuntimeVariantRecord(
                    variant_id=variant_id,
                    card_id=card_id,
                    kind=definition.kind,
                    effect_ids=(definition.effect_id,),
                    evidence_statuses=(definition.evidence_status,),
                    catalog_approved=False,
                )

        for variant in catalog.all_variants():
            current = records.get(variant.variant_id)
            statuses = ("approved_catalog",)
            effect_ids: tuple[str, ...] = ()
            if current is not None:
                if current.card_id != variant.base_card_id or current.kind is not variant.kind:
                    raise ValueError(f"catalog variant conflicts with runtime candidate {variant.variant_id}")
                statuses = _unique_nonblank((*current.evidence_statuses, *statuses))
                effect_ids = current.effect_ids
            records[variant.variant_id] = RuntimeVariantRecord(
                variant_id=variant.variant_id,
                card_id=variant.base_card_id,
                kind=variant.kind,
                effect_ids=effect_ids,
                evidence_statuses=statuses,
                catalog_approved=True,
            )
        return dict(sorted(records.items()))

    def lookup_card_name(self, text: object) -> tuple[RuntimeCardRecord, ...]:
        card_ids = self.name_table.get(normalize_flash_text(text), ())
        return tuple(self.card_table[card_id] for card_id in card_ids)

    def lookup_effect_text(self, text: object) -> tuple[RuntimeEffectCandidate, ...]:
        return self.effect_table.get(normalize_flash_text(text), ())

    def lookup_variant(self, variant_id: str) -> RuntimeVariantRecord | None:
        if record := self.variant_table.get(variant_id):
            return record
        return self._infer_composite_flash_variant(variant_id)

    def _infer_composite_flash_variant(self, variant_id: str) -> RuntimeVariantRecord | None:
        parts = variant_id.split("/")
        if len(parts) != 3:
            return None
        card_id = "/".join(parts[:2])
        if card_id not in self.card_table:
            return None
        suffix = parts[2]
        kind = next(
            (
                candidate
                for candidate in (VariantKind.COMMON_FLASH, VariantKind.DIVINE_FLASH)
                if suffix.startswith(f"{candidate.value}_")
            ),
            None,
        )
        if kind is None:
            return None
        effect_ids = tuple(suffix.removeprefix(f"{kind.value}_").split("__"))
        if not effect_ids:
            return None

        matched_definitions: list[FlashEffectDefinition] = []
        for effect_id in effect_ids:
            definitions = [
                definition
                for definition in self.knowledge.effects
                if definition.kind is kind
                and definition.effect_id == effect_id
                and definition.applies_to(card_id)
            ]
            if not definitions:
                return None
            matched_definitions.extend(definitions)
        try:
            expected_id = compose_flash_variant_id(card_id, kind, effect_ids)
        except ValueError:
            return None
        if expected_id != variant_id:
            return None
        return RuntimeVariantRecord(
            variant_id=variant_id,
            card_id=card_id,
            kind=kind,
            effect_ids=tuple(sorted(set(effect_ids))),
            evidence_statuses=_unique_nonblank(
                definition.evidence_status for definition in matched_definitions
            ),
            catalog_approved=False,
        )

    def recognize_flash(
        self,
        context: ScreenContext,
        frame: Any | None = None,
        *,
        card_id_hint: str | None = None,
    ) -> FlashRecognition:
        return self._recognizer.recognize(context, frame, card_id_hint=card_id_hint)

    def to_observation(
        self,
        result: FlashRecognition,
        context: ScreenContext,
    ) -> CardObservation:
        bounds = result.card_bounds
        if bounds is None:
            region = self.knowledge.layout.ocr_search
            left = max(0, round(region.left * context.width))
            top = max(0, round(region.top * context.height))
            right = min(context.width, round(region.right * context.width))
            bottom = min(context.height, round(region.bottom * context.height))
            bbox = BoundingBox(left, top, max(1, right - left), max(1, bottom - top))
        else:
            bbox = BoundingBox(bounds.x, bounds.y, bounds.width, bounds.height)

        effect_confidences = [
            match.confidence for match in (*result.common_effects, *result.divine_effects)
        ]
        if result.epiphany_variant_id is not None:
            effect_confidences.append(result.epiphany_confidence)
        variant_confidence = min(effect_confidences, default=0.0)
        field_confidence = {
            "identity": result.card_confidence,
            "variants": variant_confidence,
            "position": 1.0,
        }
        if result.status is RecognitionStatus.RECOGNIZED:
            confidence = 0.55 * result.card_confidence + 0.45 * variant_confidence
        elif result.card_id is not None:
            confidence = 0.5 * result.card_confidence
        else:
            confidence = 0.0

        return CardObservation(
            instance_id=f"detail-{context.frame_id}",
            status=result.status,
            bbox=bbox,
            card_id=result.card_id,
            variant_ids=result.variant_ids,
            observed_name=result.observed_card_name,
            current_cost=None,
            runtime_states=(),
            field_confidence=field_confidence,
            confidence=max(0.0, min(1.0, confidence)),
        )

    def resolve(self, observation: CardObservation) -> RuntimeCardResolution:
        if observation.status is not RecognitionStatus.RECOGNIZED or observation.card_id is None:
            return RuntimeCardResolution(observation, ResolutionStatus.OBSERVATION_UNKNOWN)
        if self.catalog.get_card(observation.card_id) is None:
            return RuntimeCardResolution(observation, ResolutionStatus.CARD_NOT_APPROVED)

        unknown_variants = tuple(
            variant_id
            for variant_id in observation.variant_ids
            if self.lookup_variant(variant_id) is None
        )
        if unknown_variants:
            return RuntimeCardResolution(
                observation,
                ResolutionStatus.INVALID_VARIANT_COMBINATION,
                unresolved_variant_ids=unknown_variants,
            )
        unapproved_variants = tuple(
            variant_id
            for variant_id in observation.variant_ids
            if self.catalog.get_variant(variant_id) is None
        )
        if unapproved_variants:
            return RuntimeCardResolution(
                observation,
                ResolutionStatus.VARIANT_NOT_APPROVED,
                unresolved_variant_ids=unapproved_variants,
            )
        try:
            materialized = self.catalog.materialize(
                observation.card_id,
                observation.variant_ids,
            )
        except CatalogError:
            return RuntimeCardResolution(
                observation,
                ResolutionStatus.INVALID_VARIANT_COMBINATION,
                unresolved_variant_ids=observation.variant_ids,
            )
        return RuntimeCardResolution(
            observation,
            ResolutionStatus.READY,
            materialized_card=materialized,
        )


def _unique_nonblank(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return tuple(result)
