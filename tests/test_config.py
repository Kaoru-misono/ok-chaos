from __future__ import annotations

from src.config import build_config
from src.tasks.ChaosTask import CurrentCardRecognitionTask


def test_current_card_recognition_task_is_registered_as_onetime() -> None:
    config = build_config(debug=True)
    registration = [CurrentCardRecognitionTask.__module__, CurrentCardRecognitionTask.__name__]

    assert registration in config["onetime_tasks"]
    assert registration not in config["trigger_tasks"]
