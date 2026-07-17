from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.chaos.cards.effects import EffectSpec
from src.chaos.cards.enums import (
    CardType,
    RecognitionStatus,
    RuntimeCardState,
    TargetMode,
    VariantKind,
)

SCHEMA_VERSION = 1
_ID_PART = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_PHASH = re.compile(r"^[0-9a-f]{16}$")


def validate_id_part(value: str, field_name: str, *, allow_blank: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    normalized = value.strip().lower()
    if allow_blank and not normalized:
        return ""
    if not _ID_PART.fullmatch(normalized):
        raise ValueError(f"{field_name} must use lowercase ASCII letters, digits, '_' or '-'")
    return normalized


def validate_qualified_id(value: str, field_name: str, *, parts: int = 2) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    split = value.strip().lower().split("/")
    if len(split) != parts:
        raise ValueError(f"{field_name} must contain {parts} slash-separated parts")
    return "/".join(validate_id_part(part, field_name) for part in split)


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be an array")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} cannot contain blank values")
        normalized = item.strip()
        if normalized not in result:
            result.append(normalized)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class LocalizedText:
    zh_cn: str
    zh_tw: str | None = None
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.zh_cn, str) or not self.zh_cn.strip():
            raise ValueError("name.zh_cn is required")
        object.__setattr__(self, "zh_cn", self.zh_cn.strip())
        if self.zh_tw is not None:
            if not isinstance(self.zh_tw, str) or not self.zh_tw.strip():
                raise ValueError("name.zh_tw cannot be blank")
            object.__setattr__(self, "zh_tw", self.zh_tw.strip())
        object.__setattr__(self, "aliases", _string_tuple(self.aliases, "name.aliases"))

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> LocalizedText:
        if not isinstance(value, dict):
            raise ValueError("name must be an object")
        unknown = set(value) - {"zh_cn", "zh_tw", "aliases"}
        if unknown:
            raise ValueError(f"unknown name fields: {sorted(unknown)}")
        return cls(
            zh_cn=value.get("zh_cn", ""),
            zh_tw=value.get("zh_tw"),
            aliases=_string_tuple(value.get("aliases"), "name.aliases"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"zh_cn": self.zh_cn}
        if self.zh_tw is not None:
            result["zh_tw"] = self.zh_tw
        if self.aliases:
            result["aliases"] = list(self.aliases)
        return result


@dataclass(frozen=True, slots=True)
class CharacterDefinition:
    owner_id: str
    name: LocalizedText

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", validate_id_part(self.owner_id, "owner_id"))
        if not isinstance(self.name, LocalizedText):
            raise ValueError("character name must be LocalizedText")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CharacterDefinition:
        if not isinstance(value, dict):
            raise ValueError("owner must be an object")
        unknown = set(value) - {"owner_id", "name"}
        if unknown:
            raise ValueError(f"unknown owner fields: {sorted(unknown)}")
        return cls(
            owner_id=value.get("owner_id", ""),
            name=LocalizedText.from_dict(value.get("name")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"owner_id": self.owner_id, "name": self.name.to_dict()}


@dataclass(frozen=True, slots=True)
class RecognitionHints:
    """Stable, reviewed hints only; runtime OCR evidence belongs to observations."""

    art_phashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        hashes = _string_tuple(self.art_phashes, "recognition.art_phashes")
        normalized = tuple(value.lower() for value in hashes)
        for value in normalized:
            if not _PHASH.fullmatch(value):
                raise ValueError("art perceptual hashes must be 16 lowercase hexadecimal characters")
        object.__setattr__(self, "art_phashes", normalized)

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> RecognitionHints:
        if value is None:
            return cls()
        if not isinstance(value, dict):
            raise ValueError("recognition must be an object")
        unknown = set(value) - {"art_phashes"}
        if unknown:
            raise ValueError(f"unknown recognition fields: {sorted(unknown)}")
        return cls(art_phashes=_string_tuple(value.get("art_phashes"), "recognition.art_phashes"))

    def to_dict(self) -> dict[str, Any]:
        return {"art_phashes": list(self.art_phashes)} if self.art_phashes else {}


@dataclass(frozen=True, slots=True)
class CardDefinition:
    card_id: str
    owner_id: str
    slot: int
    name: LocalizedText
    card_type: CardType
    base_cost: int | None
    target: TargetMode
    effects: tuple[EffectSpec, ...]
    tags: tuple[str, ...] = ()
    raw_effect_text: str | None = None
    recognition: RecognitionHints = field(default_factory=RecognitionHints)

    def __post_init__(self) -> None:
        card_id = validate_qualified_id(self.card_id, "card_id")
        owner_id = validate_id_part(self.owner_id, "owner_id")
        if card_id.split("/", 1)[0] != owner_id:
            raise ValueError("card_id must start with owner_id")
        object.__setattr__(self, "card_id", card_id)
        object.__setattr__(self, "owner_id", owner_id)
        if isinstance(self.slot, bool) or not isinstance(self.slot, int) or self.slot <= 0:
            raise ValueError("slot must be a positive integer")
        if not isinstance(self.name, LocalizedText):
            raise ValueError("name must be LocalizedText")
        if not isinstance(self.card_type, CardType):
            object.__setattr__(self, "card_type", CardType(self.card_type))
        if self.base_cost is not None and (
            isinstance(self.base_cost, bool) or not isinstance(self.base_cost, int) or self.base_cost < 0
        ):
            raise ValueError("base_cost must be a non-negative integer or null for dynamic cost")
        if not isinstance(self.target, TargetMode):
            object.__setattr__(self, "target", TargetMode(self.target))
        if not isinstance(self.effects, tuple):
            object.__setattr__(self, "effects", tuple(self.effects))
        object.__setattr__(self, "tags", tuple(sorted(_string_tuple(self.tags, "tags"))))
        if self.raw_effect_text is not None:
            if not isinstance(self.raw_effect_text, str) or not self.raw_effect_text.strip():
                raise ValueError("raw_effect_text cannot be blank")
            object.__setattr__(self, "raw_effect_text", self.raw_effect_text.strip())
        if not isinstance(self.recognition, RecognitionHints):
            raise ValueError("recognition must be RecognitionHints")

    @classmethod
    def from_dict(cls, value: dict[str, Any], *, expected_owner_id: str | None = None) -> CardDefinition:
        if not isinstance(value, dict):
            raise ValueError("card must be an object")
        allowed = {
            "card_id",
            "owner_id",
            "slot",
            "name",
            "card_type",
            "base_cost",
            "target",
            "effects",
            "tags",
            "raw_effect_text",
            "recognition",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown card fields: {sorted(unknown)}")
        owner_id = value.get("owner_id", expected_owner_id)
        if owner_id is None:
            raise ValueError("card requires owner_id")
        effects = value.get("effects", [])
        if not isinstance(effects, list):
            raise ValueError("card effects must be an array")
        return cls(
            card_id=value.get("card_id", ""),
            owner_id=owner_id,
            slot=value.get("slot"),
            name=LocalizedText.from_dict(value.get("name")),
            card_type=CardType(value.get("card_type")),
            base_cost=value.get("base_cost"),
            target=TargetMode(value.get("target", TargetMode.UNKNOWN)),
            effects=tuple(EffectSpec.from_dict(effect) for effect in effects),
            tags=_string_tuple(value.get("tags"), "tags"),
            raw_effect_text=value.get("raw_effect_text"),
            recognition=RecognitionHints.from_dict(value.get("recognition")),
        )

    def to_dict(self, *, include_owner: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "card_id": self.card_id,
            "slot": self.slot,
            "name": self.name.to_dict(),
            "card_type": self.card_type.value,
            "base_cost": self.base_cost,
            "target": self.target.value,
            "effects": [effect.to_dict() for effect in self.effects],
        }
        if include_owner:
            result["owner_id"] = self.owner_id
        if self.tags:
            result["tags"] = list(self.tags)
        if self.raw_effect_text is not None:
            result["raw_effect_text"] = self.raw_effect_text
        recognition = self.recognition.to_dict()
        if recognition:
            result["recognition"] = recognition
        return result


@dataclass(frozen=True, slots=True)
class CardVariant:
    variant_id: str
    base_card_id: str
    kind: VariantKind
    branch: str | None = None
    name_override: LocalizedText | None = None
    card_type_override: CardType | None = None
    cost_override: int | None = None
    target_override: TargetMode | None = None
    effects_override: tuple[EffectSpec, ...] | None = None
    additional_effects: tuple[EffectSpec, ...] = ()
    remove_effect_indexes: tuple[int, ...] = ()
    tags_add: tuple[str, ...] = ()
    tags_remove: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        variant_id = validate_qualified_id(self.variant_id, "variant_id", parts=3)
        base_card_id = validate_qualified_id(self.base_card_id, "base_card_id")
        if "/".join(variant_id.split("/")[:2]) != base_card_id:
            raise ValueError("variant_id must start with base_card_id")
        object.__setattr__(self, "variant_id", variant_id)
        object.__setattr__(self, "base_card_id", base_card_id)
        if not isinstance(self.kind, VariantKind):
            object.__setattr__(self, "kind", VariantKind(self.kind))
        if self.kind is VariantKind.BASE:
            raise ValueError("base cards are CardDefinition objects, not variants")
        if self.branch is not None:
            object.__setattr__(self, "branch", validate_id_part(self.branch, "branch"))
        if self.card_type_override is not None and not isinstance(self.card_type_override, CardType):
            object.__setattr__(self, "card_type_override", CardType(self.card_type_override))
        if self.cost_override is not None and (
            isinstance(self.cost_override, bool) or not isinstance(self.cost_override, int) or self.cost_override < 0
        ):
            raise ValueError("cost_override must be a non-negative integer")
        if self.target_override is not None and not isinstance(self.target_override, TargetMode):
            object.__setattr__(self, "target_override", TargetMode(self.target_override))
        if self.effects_override is not None and not isinstance(self.effects_override, tuple):
            object.__setattr__(self, "effects_override", tuple(self.effects_override))
        if not isinstance(self.additional_effects, tuple):
            object.__setattr__(self, "additional_effects", tuple(self.additional_effects))
        indexes = tuple(self.remove_effect_indexes)
        if any(isinstance(index, bool) or not isinstance(index, int) or index < 0 for index in indexes):
            raise ValueError("remove_effect_indexes must contain non-negative integers")
        if len(indexes) != len(set(indexes)):
            raise ValueError("remove_effect_indexes cannot contain duplicates")
        if self.effects_override is not None and indexes:
            raise ValueError("effects_override and remove_effect_indexes cannot be combined")
        object.__setattr__(self, "remove_effect_indexes", tuple(sorted(indexes)))
        object.__setattr__(self, "tags_add", tuple(sorted(_string_tuple(self.tags_add, "tags_add"))))
        object.__setattr__(self, "tags_remove", tuple(sorted(_string_tuple(self.tags_remove, "tags_remove"))))
        if set(self.tags_add) & set(self.tags_remove):
            raise ValueError("the same tag cannot be added and removed")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CardVariant:
        if not isinstance(value, dict):
            raise ValueError("variant must be an object")
        allowed = {
            "variant_id",
            "base_card_id",
            "kind",
            "branch",
            "name_override",
            "card_type_override",
            "cost_override",
            "target_override",
            "effects_override",
            "additional_effects",
            "remove_effect_indexes",
            "tags_add",
            "tags_remove",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown variant fields: {sorted(unknown)}")

        effects_override_value = value.get("effects_override")
        if effects_override_value is not None and not isinstance(effects_override_value, list):
            raise ValueError("effects_override must be an array")
        additional = value.get("additional_effects", [])
        if not isinstance(additional, list):
            raise ValueError("additional_effects must be an array")
        name_override = value.get("name_override")
        return cls(
            variant_id=value.get("variant_id", ""),
            base_card_id=value.get("base_card_id", ""),
            kind=VariantKind(value.get("kind")),
            branch=value.get("branch"),
            name_override=None if name_override is None else LocalizedText.from_dict(name_override),
            card_type_override=(
                None if value.get("card_type_override") is None else CardType(value["card_type_override"])
            ),
            cost_override=value.get("cost_override"),
            target_override=None if value.get("target_override") is None else TargetMode(value["target_override"]),
            effects_override=(
                None
                if effects_override_value is None
                else tuple(EffectSpec.from_dict(effect) for effect in effects_override_value)
            ),
            additional_effects=tuple(EffectSpec.from_dict(effect) for effect in additional),
            remove_effect_indexes=tuple(value.get("remove_effect_indexes", [])),
            tags_add=_string_tuple(value.get("tags_add"), "tags_add"),
            tags_remove=_string_tuple(value.get("tags_remove"), "tags_remove"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "variant_id": self.variant_id,
            "base_card_id": self.base_card_id,
            "kind": self.kind.value,
        }
        optional_values = {
            "branch": self.branch,
            "card_type_override": None if self.card_type_override is None else self.card_type_override.value,
            "cost_override": self.cost_override,
            "target_override": None if self.target_override is None else self.target_override.value,
        }
        result.update({key: value for key, value in optional_values.items() if value is not None})
        if self.name_override is not None:
            result["name_override"] = self.name_override.to_dict()
        if self.effects_override is not None:
            result["effects_override"] = [effect.to_dict() for effect in self.effects_override]
        if self.additional_effects:
            result["additional_effects"] = [effect.to_dict() for effect in self.additional_effects]
        if self.remove_effect_indexes:
            result["remove_effect_indexes"] = list(self.remove_effect_indexes)
        if self.tags_add:
            result["tags_add"] = list(self.tags_add)
        if self.tags_remove:
            result["tags_remove"] = list(self.tags_remove)
        return result


@dataclass(frozen=True, slots=True)
class MaterializedCard:
    card_id: str
    variant_ids: tuple[str, ...]
    owner_id: str
    slot: int
    name: LocalizedText
    card_type: CardType
    base_cost: int | None
    target: TargetMode
    effects: tuple[EffectSpec, ...]
    tags: tuple[str, ...]

    @classmethod
    def from_definition(cls, card: CardDefinition) -> MaterializedCard:
        return cls(
            card_id=card.card_id,
            variant_ids=(),
            owner_id=card.owner_id,
            slot=card.slot,
            name=card.name,
            card_type=card.card_type,
            base_cost=card.base_cost,
            target=card.target,
            effects=card.effects,
            tags=card.tags,
        )

    @classmethod
    def apply_variant(cls, card: CardDefinition | MaterializedCard, variant: CardVariant) -> MaterializedCard:
        current = cls.from_definition(card) if isinstance(card, CardDefinition) else card
        if variant.base_card_id != current.card_id:
            raise ValueError("variant does not belong to card")
        if variant.variant_id in current.variant_ids:
            raise ValueError("variant cannot be applied twice")
        if variant.effects_override is not None:
            effects = list(variant.effects_override)
        else:
            effects = list(current.effects)
            for index in reversed(variant.remove_effect_indexes):
                if index >= len(effects):
                    raise ValueError(f"variant removes missing effect index {index}")
                effects.pop(index)
        effects.extend(variant.additional_effects)
        tags = (set(current.tags) - set(variant.tags_remove)) | set(variant.tags_add)
        return cls(
            card_id=current.card_id,
            variant_ids=(*current.variant_ids, variant.variant_id),
            owner_id=current.owner_id,
            slot=current.slot,
            name=variant.name_override or current.name,
            card_type=variant.card_type_override or current.card_type,
            base_cost=current.base_cost if variant.cost_override is None else variant.cost_override,
            target=variant.target_override or current.target,
            effects=tuple(effects),
            tags=tuple(sorted(tags)),
        )


@dataclass(frozen=True, slots=True)
class BoundingBox:
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        coordinates = (self.x, self.y, self.width, self.height)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in coordinates):
            raise ValueError("bounding box values must be integers")
        if self.x < 0 or self.y < 0 or self.width <= 0 or self.height <= 0:
            raise ValueError("bounding box must have non-negative origin and positive size")

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass(frozen=True, slots=True)
class CardObservation:
    instance_id: str
    status: RecognitionStatus
    bbox: BoundingBox
    card_id: str | None = None
    variant_ids: tuple[str, ...] = ()
    observed_name: str | None = None
    current_cost: int | None = None
    runtime_states: tuple[RuntimeCardState, ...] = ()
    field_confidence: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.instance_id, str) or not self.instance_id.strip():
            raise ValueError("instance_id is required")
        if not isinstance(self.status, RecognitionStatus):
            object.__setattr__(self, "status", RecognitionStatus(self.status))
        if self.status is RecognitionStatus.RECOGNIZED and self.card_id is None:
            raise ValueError("recognized observation requires card_id")
        if self.card_id is not None:
            object.__setattr__(self, "card_id", validate_qualified_id(self.card_id, "card_id"))
        variants = tuple(
            validate_qualified_id(variant_id, "variant_id", parts=3) for variant_id in self.variant_ids
        )
        if len(variants) != len(set(variants)):
            raise ValueError("variant_ids cannot contain duplicates")
        if self.card_id is None and variants:
            raise ValueError("variant_ids require card_id")
        if self.card_id is not None:
            for variant_id in variants:
                if "/".join(variant_id.split("/")[:2]) != self.card_id:
                    raise ValueError("variant_id does not belong to card_id")
        object.__setattr__(self, "variant_ids", variants)
        if self.current_cost is not None and (
            isinstance(self.current_cost, bool) or not isinstance(self.current_cost, int) or self.current_cost < 0
        ):
            raise ValueError("current_cost must be a non-negative integer")
        states = tuple(
            state if isinstance(state, RuntimeCardState) else RuntimeCardState(state) for state in self.runtime_states
        )
        object.__setattr__(self, "runtime_states", states)
        if not 0 <= float(self.confidence) <= 1:
            raise ValueError("confidence must be between 0 and 1")
        for field_name, confidence in self.field_confidence.items():
            if not isinstance(field_name, str) or not field_name:
                raise ValueError("field confidence names cannot be blank")
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                raise ValueError("field confidence values must be between 0 and 1")

    def to_dict(self) -> dict[str, object]:
        return {
            "instance_id": self.instance_id,
            "status": self.status.value,
            "bbox": self.bbox.to_dict(),
            "card_id": self.card_id,
            "variant_ids": list(self.variant_ids),
            "observed_name": self.observed_name,
            "current_cost": self.current_cost,
            "runtime_states": [state.value for state in self.runtime_states],
            "field_confidence": {
                name: round(value, 4) for name, value in self.field_confidence.items()
            },
            "confidence": round(self.confidence, 4),
        }
