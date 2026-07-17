from __future__ import annotations

from pathlib import Path

_PROJECT_OR_BUNDLE_ROOT = Path(__file__).resolve().parents[2]


def resolve_project_resource(path: str | Path) -> Path:
    """Resolve a repository resource in source and PyInstaller one-file modes."""

    requested = Path(path).expanduser()
    if requested.is_absolute():
        candidates = (requested,)
    else:
        candidates = (
            Path.cwd() / requested,
            _PROJECT_OR_BUNDLE_ROOT / requested,
        )
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    checked = ", ".join(str(candidate.resolve()) for candidate in candidates)
    raise FileNotFoundError(f"resource not found: {requested}; checked: {checked}")
