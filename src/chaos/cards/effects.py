from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from src.chaos.cards.enums import CardZone, EffectOp, TargetMode, Trigger

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]


def _freeze_mapping(values: dict[str, JsonValue] | None) -> MappingProxyType[str, JsonValue]:
    return MappingProxyType(dict(values or {}))


def _require_positive_integer(params: MappingProxyType[str, JsonValue], key: str, op: EffectOp) -> None:
    value = params.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{op.value} requires positive integer parameter {key!r}")


def _optional_positive_integer(params: MappingProxyType[str, JsonValue], key: str, op: EffectOp) -> None:
    if key not in params:
        return
    value = params[key]
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{op.value} parameter {key!r} must be a positive integer")


def _require_nonempty_text(params: MappingProxyType[str, JsonValue], key: str, op: EffectOp) -> None:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{op.value} requires non-empty text parameter {key!r}")


def _optional_enum(params: MappingProxyType[str, JsonValue], key: str, enum: type, op: EffectOp) -> None:
    if key not in params:
        return
    try:
        enum(params[key])
    except ValueError as exception:
        raise ValueError(f"{op.value} parameter {key!r} is not a valid {enum.__name__}") from exception


_OpValidator = Callable[[MappingProxyType[str, JsonValue], EffectOp], None]
_OP_VALIDATORS: dict[EffectOp, _OpValidator] = {}


def _validates(*ops: EffectOp) -> Callable[[_OpValidator], _OpValidator]:
    """Register a parameter validator for one or more ops.

    Keeps each op's parameter contract self-contained: adding a formalized op
    means adding a validator, not extending a dispatch chain.
    """

    def register(validator: _OpValidator) -> _OpValidator:
        for op in ops:
            _OP_VALIDATORS[op] = validator
        return validator

    return register


@_validates(EffectOp.DRAW, EffectOp.DISCARD, EffectOp.REPEAT)
def _validate_count(params: MappingProxyType[str, JsonValue], op: EffectOp) -> None:
    _require_positive_integer(params, "count", op)


@_validates(EffectOp.UNSUPPORTED)
def _validate_unsupported(params: MappingProxyType[str, JsonValue], op: EffectOp) -> None:
    _require_nonempty_text(params, "raw_text", op)


@_validates(EffectOp.DAMAGE)
def _validate_damage(params: MappingProxyType[str, JsonValue], op: EffectOp) -> None:
    # base_value is the in-game percentage magnitude (139 == 139%).
    _require_positive_integer(params, "base_value", op)
    _optional_positive_integer(params, "hits", op)
    _optional_enum(params, "target", TargetMode, op)


@_validates(EffectOp.SHIELD)
def _validate_shield(params: MappingProxyType[str, JsonValue], op: EffectOp) -> None:
    _require_positive_integer(params, "base_value", op)
    _optional_enum(params, "target", TargetMode, op)


@_validates(EffectOp.CREATE_CARD)
def _validate_create_card(params: MappingProxyType[str, JsonValue], op: EffectOp) -> None:
    _require_nonempty_text(params, "card", op)
    _require_positive_integer(params, "count", op)
    _optional_enum(params, "zone", CardZone, op)


@_validates(EffectOp.APPLY_STATUS)
def _validate_apply_status(params: MappingProxyType[str, JsonValue], op: EffectOp) -> None:
    _require_nonempty_text(params, "status", op)
    _optional_positive_integer(params, "base_value", op)


@_validates(EffectOp.GAIN_RESOURCE)
def _validate_gain_resource(params: MappingProxyType[str, JsonValue], op: EffectOp) -> None:
    _require_nonempty_text(params, "resource", op)
    value = params.get("value")
    if isinstance(value, bool) or not isinstance(value, int) or value == 0:
        raise ValueError("gain_resource requires a non-zero integer value")


@dataclass(frozen=True, slots=True)
class EffectAction:
    """One machine-readable operation in a card effect.

    Parameters intentionally remain extensible while common operations enforce the
    minimum fields needed by the later rules engine.
    """

    op: EffectOp
    params: MappingProxyType[str, JsonValue] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.op, EffectOp):
            object.__setattr__(self, "op", EffectOp(self.op))
        if not isinstance(self.params, MappingProxyType):
            object.__setattr__(self, "params", _freeze_mapping(dict(self.params)))

        validator = _OP_VALIDATORS.get(self.op)
        if validator is not None:
            validator(self.params, self.op)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> EffectAction:
        if not isinstance(value, dict):
            raise ValueError("effect action must be an object")
        unknown = set(value) - {"op", "params"}
        if unknown:
            raise ValueError(f"unknown effect action fields: {sorted(unknown)}")
        if "op" not in value:
            raise ValueError("effect action requires op")
        params = value.get("params", {})
        if not isinstance(params, dict):
            raise ValueError("effect action params must be an object")
        return cls(op=EffectOp(value["op"]), params=_freeze_mapping(params))

    def to_dict(self) -> dict[str, Any]:
        return {"op": self.op.value, "params": dict(self.params)}


@dataclass(frozen=True, slots=True)
class EffectSpec:
    trigger: Trigger
    actions: tuple[EffectAction, ...]
    condition: MappingProxyType[str, JsonValue] | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.trigger, Trigger):
            object.__setattr__(self, "trigger", Trigger(self.trigger))
        if not self.actions:
            raise ValueError("effect requires at least one action")
        if not isinstance(self.actions, tuple):
            object.__setattr__(self, "actions", tuple(self.actions))
        if self.condition is not None and not isinstance(self.condition, MappingProxyType):
            object.__setattr__(self, "condition", _freeze_mapping(dict(self.condition)))
        if self.note is not None and not self.note.strip():
            raise ValueError("effect note cannot be blank")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> EffectSpec:
        if not isinstance(value, dict):
            raise ValueError("effect must be an object")
        unknown = set(value) - {"trigger", "actions", "condition", "note"}
        if unknown:
            raise ValueError(f"unknown effect fields: {sorted(unknown)}")
        actions = value.get("actions")
        if not isinstance(actions, list):
            raise ValueError("effect actions must be an array")
        condition = value.get("condition")
        if condition is not None and not isinstance(condition, dict):
            raise ValueError("effect condition must be an object")
        return cls(
            trigger=Trigger(value.get("trigger", Trigger.ON_PLAY)),
            actions=tuple(EffectAction.from_dict(action) for action in actions),
            condition=None if condition is None else _freeze_mapping(condition),
            note=value.get("note"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "trigger": self.trigger.value,
            "actions": [action.to_dict() for action in self.actions],
        }
        if self.condition is not None:
            result["condition"] = dict(self.condition)
        if self.note is not None:
            result["note"] = self.note
        return result
