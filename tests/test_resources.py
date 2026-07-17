from __future__ import annotations

from pathlib import Path

import pytest

from src.chaos.resources import resolve_project_resource


def test_project_resource_resolves_when_working_directory_is_elsewhere(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    result = resolve_project_resource(
        "datasets/cards/reference/haide_mali/flash_layers.pending.json"
    )

    assert result.name == "flash_layers.pending.json"
    assert result.is_file()


def test_missing_project_resource_lists_checked_paths(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError, match="resource not found"):
        resolve_project_resource(missing)


def test_project_resource_can_resolve_a_packaged_data_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    result = resolve_project_resource("data/cards")

    assert result.is_dir()
    assert (result / "characters" / "haide_mali.json").is_file()
