import pytest

from src.chaos.settings import ACTION_COOLDOWN, UNKNOWN_THRESHOLD, ChaosSettings


def test_defaults_are_valid() -> None:
    settings = ChaosSettings.from_mapping(ChaosSettings.defaults())
    assert settings.keep_save is True
    assert settings.action_cooldown == 1.0


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        (ACTION_COOLDOWN, 0.1, "0.2到10"),
        (ACTION_COOLDOWN, True, "必须是数字"),
        (UNKNOWN_THRESHOLD, 0, "1到300"),
    ],
)
def test_invalid_values_are_rejected(key, value, message) -> None:
    assert message in ChaosSettings.validate_pair(key, value)
