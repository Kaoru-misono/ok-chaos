"""Character-card data, collection, and recognition foundations."""

from src.chaos.cards.catalog import CardCatalog, CatalogError
from src.chaos.cards.effects import EffectAction, EffectSpec
from src.chaos.cards.enums import (
    CardType,
    EffectOp,
    RuntimeCardState,
    SampleScene,
    TargetMode,
    Trigger,
    VariantKind,
)
from src.chaos.cards.flash_recognizer import FlashKnowledgeBase, FlashRecognition, FlashRecognizer
from src.chaos.cards.runtime_index import (
    ResolutionStatus,
    RuntimeCardIndex,
    RuntimeCardResolution,
    RuntimeIndexSummary,
)
from src.chaos.cards.schema import (
    BoundingBox,
    CardDefinition,
    CardObservation,
    CardVariant,
    CharacterDefinition,
    MaterializedCard,
)

__all__ = [
    "CardCatalog",
    "CardDefinition",
    "CardObservation",
    "CardType",
    "CardVariant",
    "CharacterDefinition",
    "CatalogError",
    "BoundingBox",
    "EffectAction",
    "EffectOp",
    "EffectSpec",
    "FlashKnowledgeBase",
    "FlashRecognition",
    "FlashRecognizer",
    "MaterializedCard",
    "ResolutionStatus",
    "RuntimeCardIndex",
    "RuntimeCardResolution",
    "RuntimeCardState",
    "RuntimeIndexSummary",
    "SampleScene",
    "TargetMode",
    "Trigger",
    "VariantKind",
]
