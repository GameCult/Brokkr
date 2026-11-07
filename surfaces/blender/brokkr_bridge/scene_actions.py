"""Validation for the Blender scene command actions. Stdlib only, no bpy.

Everything an intent can say is checked here before bpy is touched, so the rules
are testable without Blender. Failures raise ActionRefused; the target turns the
message into a failed receipt.
"""
from __future__ import annotations

import json
import math
import os
import struct
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote

GLTF_EXTENSIONS = (".gltf", ".glb")
STILL_FORMATS = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".exr": "OPEN_EXR"}
CAMERA_TYPES = ("PERSP", "ORTHO", "PANO")
LIGHT_TYPES = ("POINT", "SUN", "SPOT", "AREA")
MAX_RESOLUTION = 16384
MAX_LENS_MM = 5000.0


class ActionRefused(ValueError):
    """The intent is malformed or reaches outside what the action may touch."""


WINDOWS_DEVICE_NAMES = frozenset(
    ["CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"]
    + [f"COM{i}" for i in range(1, 10)] + [f"LPT{i}" for i in range(1, 10)]
)
MAX_GLTF_JSON_BYTES = 16 * 1024 * 1024


def check_relative(candidate: str, label: str) -> list[str]:
    """The components of a path that is relative, plain and safe on every platform, or ActionRefused.

    Checked as text, the same on Linux and Windows, because the machine that validates is
    not the one whose rules bite: both / and \\ separate; a drive (C:), drive-relative
    (C:foo), UNC (\\\\host), extended (\\\\?\\) or rooted path is refused; so is any ':' at all
    (it also names NTFS alternate data streams, a.glb:stream), a NUL, a .. component,
    a component ending in a dot or space (Windows drops them, so a. is a), and a
    Windows device name (CON, NUL.txt, COM1)."""
    if not candidate:
        raise ActionRefused(f"{label} path is required.")
    if "\0" in candidate:
        raise ActionRefused(f"{label} path contains a NUL.")
    if ":" in candidate:
        raise ActionRefused(f"{label} path may not contain ':' (drive, scheme or stream).")
    if candidate[0] in "/\\":
        raise ActionRefused(f"{label} path must be relative (no leading separator, UNC or extended path).")
    parts = [part for part in candidate.replace("\\", "/").split("/") if part not in ("", ".")]
    if not parts:
        raise ActionRefused(f"{label} path is required.")
    for part in parts:
        if part == "..":
            raise ActionRefused(f"{label} path may not contain '..'.")
        if part[-1] in ". ":
            raise ActionRefused(f"{label} path component {part!r} ends in a dot or space.")
        if part.split(".")[0].upper() in WINDOWS_DEVICE_NAMES:
            raise ActionRefused(f"{label} path component {part!r} is a Windows device name.")
    return parts


def _same(a: Path, b: Path) -> bool:
    return os.path.normcase(str(a)) == os.path.normcase(str(b))


def resolve_inside(root: str, candidate: str, label: str, *, new_file: bool = False) -> Path:
    """The path of candidate under root, or ActionRefused.

    root is the directory configured in the add-on preferences; an empty root means the
    action is not enabled. The candidate is relative (check_relative). No existing
    component between root and the target may be a symlink or junction: each is compared
    with its resolved form, which also catches junctions on Pythons without
    os.path.isjunction. The resolved result must lie inside the resolved root. With
    new_file the target must not exist at all, as a file, a symlink (even a dangling one)
    or a hardlink, so an output can never write through an existing name."""
    if not root:
        raise ActionRefused(f"{label} directory is not configured in the add-on preferences.")
    parts = check_relative(candidate, label)
    base = Path(root).resolve()
    current = base
    for part in parts:
        step = current / part
        if os.path.lexists(step) and not _same(step.resolve(), current / part):
            raise ActionRefused(f"{label} path goes through a link at {part!r}.")
        current = step
    try:
        current.resolve().relative_to(base)
    except ValueError:
        raise ActionRefused(f"{label} path is outside the configured {label} directory.") from None
    if new_file and os.path.lexists(current):
        raise ActionRefused(f"{label} path already exists; renderStill never overwrites or writes through an existing name.")
    return current


def fingerprint(paths: Iterable[Path]) -> tuple:
    """What a re-check compares: each path's resolved name, size and modification time."""
    out = []
    for path in paths:
        stat = path.stat()
        out.append((str(path.resolve()), stat.st_size, stat.st_mtime_ns))
    return tuple(out)


def gltf_references(path: Path, root: str) -> list[Path]:
    """Every external file a .gltf or .glb names, checked to lie under root; [] for self-contained.

    Parses the glTF JSON (the .gltf file, or a .glb's first chunk) and takes every
    buffers[].uri and images[].uri. A data: URI is inline and fine. Anything else is
    percent-decoded and must pass check_relative (so file:, http:, drive, UNC, rooted and
    .. forms are refused), then resolve under the .gltf's own folder and stay under root
    with no link on the way."""
    raw = path.read_bytes() if path.suffix.lower() == ".gltf" else _glb_json_chunk(path)
    if len(raw) > MAX_GLTF_JSON_BYTES:
        raise ActionRefused("glTF JSON is too large to check.")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ActionRefused("Import file is not valid glTF JSON.") from None
    if not isinstance(document, dict):
        raise ActionRefused("Import file is not a glTF object.")
    references: list[Path] = []
    here = path.parent.resolve()
    base = Path(root).resolve()
    for kind in ("buffers", "images"):
        entries = document.get(kind, [])
        if not isinstance(entries, list):
            raise ActionRefused(f"glTF {kind} is not a list.")
        for entry in entries:
            uri = entry.get("uri") if isinstance(entry, dict) else None
            if uri is None:
                continue
            if not isinstance(uri, str):
                raise ActionRefused(f"glTF {kind} uri is not a string.")
            if uri.lower().startswith("data:"):
                continue
            decoded = unquote(uri)
            relative = "/".join(check_relative(decoded, f"glTF {kind} uri"))
            try:
                target = resolve_inside(str(here), relative, f"glTF {kind} uri")
                target.resolve().relative_to(base)
            except ValueError:
                raise ActionRefused(f"glTF {kind} uri is outside the import directory.") from None
            references.append(target)
    return references


def _glb_json_chunk(path: Path) -> bytes:
    with path.open("rb") as handle:
        header = handle.read(20)
        if len(header) < 20 or header[:4] != b"glTF":
            raise ActionRefused("Import file is not a binary glTF.")
        length, kind = struct.unpack("<I4s", header[12:20])
        if kind != b"JSON" or length > MAX_GLTF_JSON_BYTES:
            raise ActionRefused("Binary glTF does not start with a JSON chunk of a checkable size.")
        data = handle.read(length)
    if len(data) != length:
        raise ActionRefused("Binary glTF is truncated.")
    return data


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
