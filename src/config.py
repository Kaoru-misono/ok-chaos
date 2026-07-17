from __future__ import annotations

from typing import Any

from src.privacy import redact_bottom_right
from src.tasks.ChaosTask import (
    AutoCardCollectorTask,
    CardCollectorTask,
    ChaosTask,
    CurrentCardRecognitionTask,
)
from src.version import __version__


def build_config(*, debug: bool = False, config_folder: str = "configs") -> dict[str, Any]:
    return {
        "custom_tasks": False,
        "debug": debug,
        "use_gui": True,
        "config_folder": config_folder,
        # ok-script's StartCard requires a non-null icon with the current
        # qfluentwidgets release. Reuse the framework's bundled Qt resource.
        "gui_icon": ":/icon/icon.ico",
        "screenshot_processor": redact_bottom_right,
        "wait_until_before_delay": 0,
        "wait_until_check_delay": 0,
        "wait_until_settle_time": 0,
        "ocr": {
            "lib": "onnxocr",
            "auto_simplify": True,
            "params": {"use_openvino": True},
        },
        "windows": {
            # Match ok-kes: let DeviceManager enumerate windows and persist the user's
            # selection. STOVE's shield process does not behave reliably with a fixed title.
            "interaction": ["Pynput", "PostMessage", "Genshin", "PyDirect", "ForegroundPostMessage"],
            "capture_method": ["WGC", "BitBlt_RenderFull", "BitBlt"],
            "check_hdr": False,
            "force_no_hdr": False,
            "require_bg": True,
        },
        "start_timeout": 120,
        "window_size": {
            "width": 1200,
            "height": 800,
            "min_width": 700,
            "min_height": 500,
        },
        "supported_resolution": {
            "ratio": "16:9",
            "min_size": (1280, 720),
            "resize_to": [(1920, 1080), (1600, 900), (1280, 720)],
            "force_ratio": True,
        },
        "screenshots_folder": "screenshots",
        "gui_title": "ok-chaos",
        "version": __version__,
        "trigger_tasks": [[ChaosTask.__module__, ChaosTask.__name__]],
        "onetime_tasks": [
            ["ok", "DiagnosisTask"],
            [CurrentCardRecognitionTask.__module__, CurrentCardRecognitionTask.__name__],
            [CardCollectorTask.__module__, CardCollectorTask.__name__],
            [AutoCardCollectorTask.__module__, AutoCardCollectorTask.__name__],
        ],
    }
