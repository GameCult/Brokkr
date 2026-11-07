"""Validation for the Blender scene command actions. Stdlib only, no bpy.

Everything an intent can say is checked here before bpy is touched, so the rules
are testable without Blender. Failures raise ActionRefused; the target turns the
message into a failed receipt.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterable

GLTF_EXTENSIONS = (".gltf", ".glb")
STILL_FORMATS = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".exr": "OPEN_EXR"}
CAMERA_TYPES = ("PERSP", "ORTHO", "PANO")
LIGHT_TYPES = ("POINT", "SUN", "SPOT", "AREA")
MAX_RESOLUTION = 16384
MAX_LENS_MM = 5000.0


class ActionRefused(ValueError):
    """The intent is malformed or reaches outside what the action may touch."""


def resolve_inside(root: str, candidate: str, label: str) -> Path:
    """The resolved path of candidate under root, or ActionRefused.

    root is the directory configured in the add-on preferences; an empty root means the
    action is not enabled. A relative candidate is taken relative to root. The result is
    resolved (symlinks followed, .. collapsed) before the containment test, so neither a
    ../ nor a symlink inside root can reach outside it."""
    if not root:
        raise ActionRefused(f"{label} directory is not configured in the add-on preferences.")
    if not candidate:
        raise ActionRefused(f"{label} path is required.")
    base = Path(root).resolve()
    target = (base / candidate).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise ActionRefused(f"{label} path is outside the configured {label} directory.") from None
    return target


def number(command: dict[str, Any], key: str, low: float, high: float) -> float | None:
    """A finite number in [low, high], or None when the key is absent."""
    if key not in command or command[key] is None:
        return None
    value = command[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ActionRefused(f"{key} must be a finite number.")
    if not low <= value <= high:
        raise ActionRefused(f"{key} must be between {low} and {high}.")
    return float(value)


def integer(command: dict[str, Any], key: str, low: int, high: int) -> int | None:
    value = number(command, key, low, high)
    if value is None:
        return None
    if value != int(value):
        raise ActionRefused(f"{key} must be a whole number.")
    return int(value)


def color(command: dict[str, Any], key: str = "color") -> tuple[float, float, float] | None:
    """Linear RGB, three finite numbers in [0, 1], or None when absent."""
    if key not in command or command[key] is None:
        return None
    value = command[key]
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ActionRefused(f"{key} must be three numbers [r, g, b].")
    parts = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) or not 0.0 <= item <= 1.0:
            raise ActionRefused(f"{key} components must be numbers between 0 and 1.")
        parts.append(float(item))
    return (parts[0], parts[1], parts[2])


def choice(command: dict[str, Any], key: str, allowed: Iterable[str]) -> str | None:
    if key not in command or command[key] is None:
        return None
    allowed = tuple(allowed)
    value = command[key]
    if not isinstance(value, str) or value.upper() not in allowed:
        raise ActionRefused(f"{key} must be one of {', '.join(allowed)}.")
    return value.upper()


def still_format(path: Path) -> str:
    try:
        return STILL_FORMATS[path.suffix.lower()]
    except KeyError:
        raise ActionRefused(f"Output path must end in one of {', '.join(STILL_FORMATS)}.") from None


def require_gltf(path: Path) -> None:
    if path.suffix.lower() not in GLTF_EXTENSIONS:
        raise ActionRefused(f"Import path must end in {' or '.join(GLTF_EXTENSIONS)}.")
    if not path.is_file():
        raise ActionRefused("Import path is not an existing file.")
