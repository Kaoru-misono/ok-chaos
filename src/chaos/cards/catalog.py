from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.chaos.cards.schema import (
    SCHEMA_VERSION,
    CardDefinition,
    CardVariant,
    CharacterDefinition,
    MaterializedCard,
)

_VARIANT_LAYER_ORDER = {
    "common_flash": 10,
    "epiphany": 10,
    "divine_flash": 20,
    "character_enhancement": 30,
}

_VARIANT_CONFLICT_GROUP = {
    "common_flash": "base_flash",
    "epiphany": "base_flash",
    "divine_flash": "divine_flash",
    "character_enhancement": "character_enhancement",
}


class CatalogError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CatalogSummary:
    owners: int
    cards: int
    variants: int
    source_files: int


class CardCatalog:
    """Validated catalog of supported character cards only."""

    def __init__(
        self,
        owners: dict[str, CharacterDefinition] | None = None,
        cards: dict[str, CardDefinition] | None = None,
        variants: dict[str, CardVariant] | None = None,
        *,
        source_files: int = 0,
    ) -> None:
        self._owners = dict(owners or {})
        self._cards = dict(cards or {})
        self._variants = dict(variants or {})
        self._source_files = source_files
        self._validate_relations()

    @classmethod
    def from_directory(cls, root: str | Path) -> CardCatalog:
        root_path = Path(root)
        character_root = root_path / "characters"
        if not character_root.exists():
            raise CatalogError(f"character catalog directory does not exist: {character_root}")
        files = sorted(character_root.rglob("*.json"))
        owners: dict[str, CharacterDefinition] = {}
        cards: dict[str, CardDefinition] = {}
        variants: dict[str, CardVariant] = {}
        slots_by_owner: dict[str, dict[int, str]] = {}

        for path in files:
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
                owner, file_cards, file_variants = cls._parse_file(document)
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exception:
                raise CatalogError(f"{path}: {exception}") from exception

            if owner.owner_id in owners:
                raise CatalogError(f"{path}: duplicate owner_id {owner.owner_id}")
            owners[owner.owner_id] = owner

            for card in file_cards:
                if card.card_id in cards:
                    raise CatalogError(f"{path}: duplicate card_id {card.card_id}")
                owner_slots = slots_by_owner.setdefault(card.owner_id, {})
                if card.slot in owner_slots:
                    raise CatalogError(
                        f"{path}: owner {card.owner_id} slot {card.slot} is already used by {owner_slots[card.slot]}"
                    )
                owner_slots[card.slot] = card.card_id
                cards[card.card_id] = card

            for variant in file_variants:
                if variant.variant_id in variants:
                    raise CatalogError(f"{path}: duplicate variant_id {variant.variant_id}")
                variants[variant.variant_id] = variant

        try:
            return cls(owners, cards, variants, source_files=len(files))
        except ValueError as exception:
            raise CatalogError(str(exception)) from exception

    @staticmethod
    def _parse_file(
        document: Any,
    ) -> tuple[CharacterDefinition, tuple[CardDefinition, ...], tuple[CardVariant, ...]]:
        if not isinstance(document, dict):
            raise ValueError("catalog file must contain an object")
        unknown = set(document) - {"schema_version", "owner", "cards", "variants"}
        if unknown:
            raise ValueError(f"unknown catalog fields: {sorted(unknown)}")
        if document.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
        owner = CharacterDefinition.from_dict(document.get("owner"))
        owner_id = owner.owner_id
        card_values = document.get("cards", [])
        variant_values = document.get("variants", [])
        if not isinstance(card_values, list):
            raise ValueError("cards must be an array")
        if not isinstance(variant_values, list):
            raise ValueError("variants must be an array")

        cards = tuple(CardDefinition.from_dict(value, expected_owner_id=owner_id) for value in card_values)
        variants = tuple(CardVariant.from_dict(value) for value in variant_values)
        for card in cards:
            if card.owner_id != owner_id:
                raise ValueError(f"card {card.card_id} belongs to a different owner")
        for variant in variants:
            if variant.base_card_id.split("/", 1)[0] != owner_id:
                raise ValueError(f"variant {variant.variant_id} belongs to a different owner")
        return owner, cards, variants

    def _validate_relations(self) -> None:
        for owner_id, owner in self._owners.items():
            if owner_id != owner.owner_id:
                raise ValueError(f"owner mapping key does not match {owner.owner_id}")
        for card_id, card in self._cards.items():
            if card_id != card.card_id:
                raise ValueError(f"card mapping key does not match {card.card_id}")
            if card.owner_id not in self._owners:
                raise ValueError(f"card {card.card_id} references missing owner {card.owner_id}")
        for variant_id, variant in self._variants.items():
            if variant_id != variant.variant_id:
                raise ValueError(f"variant mapping key does not match {variant.variant_id}")
            card = self._cards.get(variant.base_card_id)
            if card is None:
                raise ValueError(f"variant {variant_id} references missing card {variant.base_card_id}")
            MaterializedCard.apply_variant(card, variant)

    @property
    def summary(self) -> CatalogSummary:
        return CatalogSummary(len(self._owners), len(self._cards), len(self._variants), self._source_files)

    def get_owner(self, owner_id: str) -> CharacterDefinition | None:
        return self._owners.get(owner_id)

    def get_card(self, card_id: str) -> CardDefinition | None:
        return self._cards.get(card_id)

    def get_variant(self, variant_id: str) -> CardVariant | None:
        return self._variants.get(variant_id)

    def all_cards(self) -> tuple[CardDefinition, ...]:
        return tuple(sorted(self._cards.values(), key=lambda card: card.card_id))

    def all_variants(self) -> tuple[CardVariant, ...]:
        return tuple(sorted(self._variants.values(), key=lambda variant: variant.variant_id))

    def materialize(
        self,
        card_id: str,
        variant_ids: str | Iterable[str] | None = None,
    ) -> MaterializedCard:
        try:
            card = self._cards[card_id]
        except KeyError as exception:
            raise CatalogError(f"unknown card_id {card_id}") from exception
        if variant_ids is None:
            requested_ids: tuple[str, ...] = ()
        elif isinstance(variant_ids, str):
            requested_ids = (variant_ids,)
        else:
            requested_ids = tuple(variant_ids)
        if len(requested_ids) != len(set(requested_ids)):
            raise CatalogError("variant_ids cannot contain duplicates")

        variants: list[CardVariant] = []
        for variant_id in requested_ids:
            try:
                variant = self._variants[variant_id]
            except KeyError as exception:
                raise CatalogError(f"unknown variant_id {variant_id}") from exception
            if variant.base_card_id != card_id:
                raise CatalogError(f"variant {variant_id} does not belong to {card_id}")
            variants.append(variant)

        conflict_groups = [_VARIANT_CONFLICT_GROUP[variant.kind.value] for variant in variants]
        if len(conflict_groups) != len(set(conflict_groups)):
            raise CatalogError("only one variant from each enhancement layer can be active")
        variants.sort(key=lambda variant: (_VARIANT_LAYER_ORDER[variant.kind.value], variant.variant_id))
        materialized = MaterializedCard.from_definition(card)
        try:
            for variant in variants:
                materialized = MaterializedCard.apply_variant(materialized, variant)
        except ValueError as exception:
            raise CatalogError(str(exception)) from exception
        return materialized

    def cards_for_owner(self, owner_id: str) -> tuple[CardDefinition, ...]:
        return tuple(
            sorted(
                (card for card in self._cards.values() if card.owner_id == owner_id),
                key=lambda card: (card.slot, card.card_id),
            )
        )

    def variants_for_card(self, card_id: str) -> tuple[CardVariant, ...]:
        return tuple(
            sorted(
                (variant for variant in self._variants.values() if variant.base_card_id == card_id),
                key=lambda variant: variant.variant_id,
            )
        )
