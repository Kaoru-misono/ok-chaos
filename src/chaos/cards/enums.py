from __future__ import annotations

from enum import StrEnum


class CardType(StrEnum):
    """Functional card types that can appear in or affect the character hand."""

    ATTACK = "attack"
    SKILL = "skill"
    UPGRADE = "upgrade"
    CURSE = "curse"
    STATUS = "status"


class VariantKind(StrEnum):
    BASE = "base"
    COMMON_FLASH = "common_flash"
    EPIPHANY = "epiphany"
    DIVINE_FLASH = "divine_flash"
    CHARACTER_ENHANCEMENT = "character_enhancement"


class TargetMode(StrEnum):
    NONE = "none"
    SELF = "self"
    SINGLE_ENEMY = "single_enemy"
    ALL_ENEMIES = "all_enemies"
    RANDOM_ENEMY = "random_enemy"
    SINGLE_ALLY = "single_ally"
    ALL_ALLIES = "all_allies"
    FLEXIBLE = "flexible"
    UNKNOWN = "unknown"


class Trigger(StrEnum):
    ON_PLAY = "on_play"
    ON_DRAW = "on_draw"  # 感應: activates when this card is drawn
    ON_DISCARD = "on_discard"  # 安息/被丟棄時
    ON_EXHAUST = "on_exhaust"
    ON_MOVE_TO_GRAVE = "on_move_to_grave"  # 移動至墳墓時
    TURN_START = "turn_start"  # 回合開始時
    TURN_END = "turn_end"
    PASSIVE = "passive"


class CardZone(StrEnum):
    HAND = "hand"
    DRAW_PILE = "draw_pile"
    DISCARD_PILE = "discard_pile"
    GRAVE = "grave"
    USED_PILE = "used_pile"


class EffectOp(StrEnum):
    DAMAGE = "damage"
    SHIELD = "shield"
    HEAL = "heal"
    STRESS = "stress"
    DRAW = "draw"
    DISCARD = "discard"
    EXHAUST = "exhaust"
    RETAIN = "retain"
    COST_CHANGE = "cost_change"
    GAIN_RESOURCE = "gain_resource"
    APPLY_STATUS = "apply_status"
    REMOVE_STATUS = "remove_status"
    CREATE_CARD = "create_card"
    MOVE_CARD = "move_card"
    REPEAT = "repeat"
    CONDITIONAL = "conditional"
    UNSUPPORTED = "unsupported"


class RuntimeCardState(StrEnum):
    PLAYABLE = "playable"
    UNPLAYABLE = "unplayable"
    SELECTED = "selected"
    HOVERED = "hovered"
    RETAINED = "retained"
    COST_REDUCED = "cost_reduced"
    COST_INCREASED = "cost_increased"
    TEMPORARY_UPGRADE = "temporary_upgrade"
    EXHAUST_ON_USE = "exhaust_on_use"


class SampleScene(StrEnum):
    CARD_LIST = "card_list"
    CARD_DETAIL = "card_detail"
    BATTLE_HAND = "battle_hand"
    EPIPHANY = "epiphany"
    DIVINE_FLASH = "divine_flash"
    UNKNOWN = "unknown"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RecognitionStatus(StrEnum):
    RECOGNIZED = "recognized"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"
