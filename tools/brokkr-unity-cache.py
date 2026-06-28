#!/usr/bin/env python3
"""Inspect a running Brokkr Unity editor cache from a scripting runtime.

This is intentionally a local development utility, not the Codex/Bifrost MCP
boundary. It uses CultCache's single-file MessagePack store directly because
Brokkr is just a daemon in the local Verse.
"""

from __future__ import annotations

import argparse
import base64
import os
import re
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CACHE = Path(r"E:\Projects\Aetheria\.brokkr\unity-editor.ccmp")
TUI_SURFACE_KEY = "eve/unity/tui"
TUI_SURFACE_URI = "cultmesh://brokkr/eve/unity/tui"
TUI_SURFACE_ID = "brokkr.eve.unity_editor_tui.v0"
PREFAB_INSPECTION_SCHEMA = "brokkr.unity.prefab_inspection.v0"
PREFAB_GAMEOBJECT_INSPECTION_SCHEMA = "brokkr.unity.prefab_gameobject_inspection.v0"

UNITY_CLASS_NAMES = {
    "1": "GameObject",
    "4": "Transform",
    "20": "Camera",
    "23": "MeshRenderer",
    "33": "MeshFilter",
    "54": "Rigidbody",
    "58": "CircleCollider2D",
    "65": "BoxCollider",
    "82": "AudioSource",
    "95": "Animator",
    "114": "MonoBehaviour",
    "115": "MonoScript",
    "119": "Projector",
    "120": "LineRenderer",
    "122": "Halo",
    "124": "Behaviour",
    "135": "SphereCollider",
    "136": "CapsuleCollider",
    "198": "ParticleSystem",
    "199": "ParticleSystemRenderer",
    "212": "SpriteRenderer",
    "222": "CanvasRenderer",
    "223": "Canvas",
    "224": "RectTransform",
}


@dataclass(frozen=True)
class Document:
    key: str
    type: str
    payload: bytes
    stored_at: str | None = None


def add_local_cultcache_paths() -> None:
    candidates = [
        Path(r"E:\Projects\cultcache-py\src"),
        Path(r"E:\Projects\CultLib\packages\cultcache-py\src"),
    ]
    for candidate in candidates:
        if candidate.exists():
            sys.path.insert(0, str(candidate))


def read_documents(cache_path: Path) -> list[Document]:
    add_local_cultcache_paths()
    try:
        from cultcache_py import SingleFileMessagePackBackingStore  # type: ignore

        store = SingleFileMessagePackBackingStore(cache_path)
        return [
            Document(item.key, item.type, item.payload, item.stored_at)
            for item in store.pull_all()
        ]
    except ModuleNotFoundError:
        import msgpack  # type: ignore

        raw_items = msgpack.unpackb(cache_path.read_bytes(), raw=False)
        return [
            Document(
                item["key"],
                item["type"],
                item["payload"],
                item.get("storedAt", item.get("stored_at")),
            )
            for item in raw_items
        ]


def write_document(cache_path: Path, document: Document) -> None:
    add_local_cultcache_paths()
    try:
        from cultcache_py import SingleFileMessagePackBackingStore  # type: ignore
        from cultcache_py import CultCacheEnvelope  # type: ignore

        store = SingleFileMessagePackBackingStore(cache_path)
        store.push(
            CultCacheEnvelope(
                key=document.key,
                type=document.type,
                payload=document.payload,
                stored_at=document.stored_at,
            )
        )
        return
    except ModuleNotFoundError:
        pass

    import msgpack  # type: ignore

    existing = {
        (doc.type, doc.key): doc
        for doc in read_documents(cache_path)
    }
    existing[(document.type, document.key)] = document
    raw_items = [
        {
            "key": doc.key,
            "type": doc.type,
            "payload": doc.payload,
            "storedAt": doc.stored_at,
        }
        for doc in sorted(existing.values(), key=lambda item: (item.type, item.key))
    ]
    temp = cache_path.with_suffix(cache_path.suffix + ".tmp")
    temp.write_bytes(msgpack.packb(raw_items, use_bin_type=True))
    temp.replace(cache_path)


def decode_payload(payload: bytes) -> Any:
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass

    try:
        import msgpack  # type: ignore

        return msgpack.unpackb(payload, raw=False)
    except Exception:
        pass

    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        return {"base64": base64.b64encode(payload).decode("ascii")}


def field(value: Any, index: int, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    if isinstance(value, list) and index < len(value):
        return value[index]
    return default


def file_id(value: str) -> str:
    match = re.search(r"fileID:\s*(-?\d+)", value)
    return match.group(1) if match else ""


def guid_value(value: str) -> str:
    match = re.search(r"guid:\s*([0-9a-fA-F]+)", value)
    return match.group(1).lower() if match else ""


def parse_scalar(lines: list[str], key: str, default: str = "") -> str:
    prefix = f"  {key}:"
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return default


def parse_file_ids_after(lines: list[str], key: str) -> list[str]:
    ids: list[str] = []
    in_block = False
    prefix = f"  {key}:"
    for line in lines:
        if line.startswith(prefix):
            in_block = True
            continue
        if in_block:
            if line.startswith("  - "):
                found = file_id(line)
                if found:
                    ids.append(found)
                continue
            if line.startswith("  ") and not line.startswith("    "):
                break
    return ids


def parse_top_level_fields(lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.startswith("  ") or line.startswith("    ") or line.startswith("  - ") or ":" not in line:
            index += 1
            continue

        key, value = line.strip().split(":", 1)
        value = value.strip()
        index += 1
        block: list[str] = []
        while index < len(lines):
            next_line = lines[index]
            if (
                next_line.startswith("  ")
                and not next_line.startswith("    ")
                and not next_line.startswith("  - ")
                and ":" in next_line
            ):
                break
            if next_line.strip():
                block.append(next_line.strip())
            index += 1
        if block:
            fields[key] = (value + " " + " ".join(block)).strip()
        else:
            fields[key] = value
    return fields


def display_component_fields(raw_fields: dict[str, str]) -> dict[str, str]:
    hidden = {
        "m_ObjectHideFlags",
        "m_CorrespondingSourceObject",
        "m_PrefabInstance",
        "m_PrefabAsset",
        "m_GameObject",
        "m_EditorHideFlags",
        "m_EditorClassIdentifier",
        "serializedVersion",
    }
    return {
        key: value
        for key, value in raw_fields.items()
        if key not in hidden and value != ""
    }


def parse_unity_yaml_sections(prefab_path: Path) -> list[dict[str, Any]]:
    text = prefab_path.read_text(encoding="utf-8-sig", errors="replace")
    header = re.compile(r"^--- !u!(?P<class_id>\d+) &(?P<file_id>-?\d+)", re.MULTILINE)
    matches = list(header.finditer(text))
    sections: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip("\r\n")
        lines = body.splitlines()
        type_name = UNITY_CLASS_NAMES.get(match.group("class_id"), "")
        for line in lines:
            if line and not line.startswith(" ") and line.endswith(":"):
                type_name = line[:-1]
                break
        sections.append(
            {
                "classId": match.group("class_id"),
                "fileId": match.group("file_id"),
                "type": type_name or match.group("class_id"),
                "lines": lines,
            }
        )
    return sections


def project_root_from_asset_path(asset_path: Path) -> Path:
    parts = list(asset_path.resolve().parts)
    lowered = [part.lower() for part in parts]
    if "assets" in lowered:
        index = lowered.index("assets")
        return Path(*parts[:index])
    return Path.cwd()


def resolve_script_guids(project_root: Path, guids: set[str]) -> dict[str, str]:
    if not guids:
        return {}
    resolved: dict[str, str] = {}
    assets_root = project_root / "Assets"
    if not assets_root.exists():
        return resolved

    try:
        pattern = "|".join(re.escape(guid) for guid in sorted(guids))
        result = subprocess.run(
            ["rg", "-l", f"guid:\\s*({pattern})", str(assets_root), "-g", "*.meta"],
            cwd=str(project_root),
            text=True,
            capture_output=True,
            timeout=8,
            check=False,
        )
        for raw_path in result.stdout.splitlines():
            meta_path = Path(raw_path)
            if not meta_path.is_absolute():
                meta_path = project_root / meta_path
            try:
                content = meta_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            match = re.search(r"^guid:\s*([0-9a-fA-F]+)", content, re.MULTILINE)
            if not match:
                continue
            guid = match.group(1).lower()
            if guid not in guids:
                continue
            asset_path = meta_path.with_suffix("")
            try:
                resolved[guid] = str(asset_path.relative_to(project_root)).replace(os.sep, "/")
            except ValueError:
                resolved[guid] = str(asset_path)
        if len(resolved) == len(guids):
            return resolved
    except (OSError, subprocess.SubprocessError):
        pass

    for meta_path in assets_root.rglob("*.meta"):
        if len(resolved) == len(guids):
            break
        try:
            with meta_path.open("r", encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    if not line.startswith("guid:"):
                        continue
                    guid = line.split(":", 1)[1].strip().lower()
                    if guid in guids:
                        asset_path = meta_path.with_suffix("")
                        try:
                            resolved[guid] = str(asset_path.relative_to(project_root)).replace(os.sep, "/")
                        except ValueError:
                            resolved[guid] = str(asset_path)
                    break
        except OSError:
            continue
    return resolved


def resolve_unity_reference(
    file_id_value: str,
    guid: str,
    game_objects: dict[str, dict[str, Any]],
    components: dict[str, dict[str, Any]],
    guid_paths: dict[str, str],
) -> str:
    if file_id_value in ("", "0"):
        return "None"

    if guid:
        asset_path = guid_paths.get(guid.lower(), f"guid:{guid}")
        if file_id_value == "11500000":
            return asset_path
        return f"{asset_path}#{file_id_value}"

    if file_id_value in game_objects:
        game_object = game_objects[file_id_value]
        return f"{game_object.get('name', '')} (GameObject {file_id_value})"

    if file_id_value in components:
        component_info = components[file_id_value]
        game_object = game_objects.get(component_info.get("gameObject", ""), {})
        owner = game_object.get("name", component_info.get("gameObject", ""))
        return f"{owner}.{component_info.get('type', 'Component')} ({file_id_value})"

    return f"fileID:{file_id_value}"


def resolve_field_value(
    value: str,
    game_objects: dict[str, dict[str, Any]],
    components: dict[str, dict[str, Any]],
    guid_paths: dict[str, str],
) -> str:
    ref_pattern = re.compile(
        r"\{fileID:\s*(-?\d+)(?:,\s*guid:\s*([0-9a-fA-F]+),\s*type:\s*(\d+))?\}"
    )

    def replace(match: re.Match[str]) -> str:
        return resolve_unity_reference(
            match.group(1),
            match.group(2) or "",
            game_objects,
            components,
            guid_paths,
        )

    return ref_pattern.sub(replace, value)


def inspect_prefab(prefab_path: Path, max_objects: int = 120) -> dict[str, Any]:
    sections = parse_unity_yaml_sections(prefab_path)
    game_objects: dict[str, dict[str, Any]] = {}
    components: dict[str, dict[str, Any]] = {}
    transforms: dict[str, dict[str, Any]] = {}
    script_guids: set[str] = set()
    reference_guids: set[str] = set()

    for section in sections:
        section_type = section["type"]
        file_id_value = section["fileId"]
        lines = section["lines"]

        if section_type == "GameObject":
            component_ids = parse_file_ids_after(lines, "m_Component")
            game_objects[file_id_value] = {
                "fileId": file_id_value,
                "name": parse_scalar(lines, "m_Name", "(unnamed)"),
                "tag": parse_scalar(lines, "m_TagString", ""),
                "layer": parse_scalar(lines, "m_Layer", ""),
                "active": parse_scalar(lines, "m_IsActive", "1") != "0",
                "componentIds": component_ids,
                "components": [],
                "children": [],
                "parent": "",
                "transform": "",
            }
            continue

        game_object_id = file_id(parse_scalar(lines, "m_GameObject", ""))
        script_guid = guid_value(parse_scalar(lines, "m_Script", ""))
        if script_guid:
            script_guids.add(script_guid)
        raw_fields = parse_top_level_fields(lines)
        for raw_value in raw_fields.values():
            reference_guids.update(
                guid.lower()
                for guid in re.findall(r"guid:\s*([0-9a-fA-F]+)", raw_value)
            )

        component_info = {
            "fileId": file_id_value,
            "classId": section["classId"],
            "type": section_type,
            "gameObject": game_object_id,
            "enabled": parse_scalar(lines, "m_Enabled", ""),
            "scriptGuid": script_guid,
            "scriptPath": "",
            "fields": display_component_fields(raw_fields),
        }
        components[file_id_value] = component_info

        if section_type in ("Transform", "RectTransform"):
            parent = file_id(parse_scalar(lines, "m_Father", ""))
            children = parse_file_ids_after(lines, "m_Children")
            transform_info = {
                **component_info,
                "parentTransform": parent,
                "childTransforms": children,
                "localPosition": parse_scalar(lines, "m_LocalPosition", ""),
                "localRotation": parse_scalar(lines, "m_LocalRotation", ""),
                "localScale": parse_scalar(lines, "m_LocalScale", ""),
                "localEulerAnglesHint": parse_scalar(lines, "m_LocalEulerAnglesHint", ""),
            }
            transforms[file_id_value] = transform_info
            components[file_id_value] = transform_info

    project_root = project_root_from_asset_path(prefab_path)
    guid_paths = resolve_script_guids(project_root, script_guids | reference_guids)
    for component_info in components.values():
        guid = component_info.get("scriptGuid", "")
        if guid:
            component_info["scriptPath"] = guid_paths.get(guid, "")
            if component_info["scriptPath"]:
                component_info["type"] = Path(component_info["scriptPath"]).stem

    transform_to_game_object = {
        transform_id: transform["gameObject"]
        for transform_id, transform in transforms.items()
        if transform.get("gameObject")
    }
    for transform_id, transform in transforms.items():
        game_object_id = transform.get("gameObject", "")
        if game_object_id in game_objects:
            game_objects[game_object_id]["transform"] = transform_id
            parent_transform = transform.get("parentTransform", "")
            parent_game_object = transform_to_game_object.get(parent_transform, "")
            game_objects[game_object_id]["parent"] = parent_game_object

    for game_object in game_objects.values():
        for component_id in game_object["componentIds"]:
            component_info = components.get(component_id)
            if component_info is not None:
                game_object["components"].append(component_info)

    for game_object_id, game_object in game_objects.items():
        parent = game_object.get("parent", "")
        if parent in game_objects:
            game_objects[parent]["children"].append(game_object_id)

    for component_info in components.values():
        component_info["resolvedFields"] = {
            key: resolve_field_value(value, game_objects, components, guid_paths)
            for key, value in (component_info.get("fields", {}) or {}).items()
        }

    component_histogram: dict[str, int] = {}
    mono_scripts: dict[str, int] = {}
    missing_scripts = 0
    for component_info in components.values():
        component_type = component_info.get("type", "")
        component_histogram[component_type] = component_histogram.get(component_type, 0) + 1
        guid = component_info.get("scriptGuid", "")
        if guid:
            script_path = component_info.get("scriptPath", "")
            if script_path:
                mono_scripts[script_path] = mono_scripts.get(script_path, 0) + 1
            else:
                missing_scripts += 1

    roots = [
        game_object_id
        for game_object_id, game_object in game_objects.items()
        if not game_object.get("parent")
    ]

    def build_node(game_object_id: str, depth: int = 0) -> dict[str, Any]:
        game_object = game_objects[game_object_id]
        component_names = [component["type"] for component in game_object["components"]]
        node = {
            "name": game_object["name"],
            "fileId": game_object["fileId"],
            "active": game_object["active"],
            "tag": game_object["tag"],
            "layer": game_object["layer"],
            "components": component_names,
            "componentDetails": game_object["components"],
            "children": [],
        }
        if len(build_node.seen) < max_objects:
            build_node.seen.add(game_object_id)
            node["children"] = [
                build_node(child_id, depth + 1)
                for child_id in game_object["children"]
                if child_id in game_objects and len(build_node.seen) < max_objects
            ]
        return node

    build_node.seen = set()  # type: ignore[attr-defined]
    tree = [build_node(root) for root in roots if root in game_objects]

    return {
        "path": str(prefab_path),
        "assetPath": str(prefab_path.relative_to(project_root_from_asset_path(prefab_path))).replace(os.sep, "/"),
        "bytes": prefab_path.stat().st_size,
        "sections": len(sections),
        "gameObjects": len(game_objects),
        "components": len(components),
        "transforms": len(transforms),
        "roots": len(roots),
        "missingMonoBehaviours": missing_scripts,
        "componentHistogram": dict(sorted(component_histogram.items(), key=lambda item: (-item[1], item[0]))),
        "monoScripts": dict(sorted(mono_scripts.items(), key=lambda item: (-item[1], item[0]))),
        "tree": tree,
        "truncatedTree": len(game_objects) > max_objects,
    }


def as_jsonable(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"base64": base64.b64encode(value).decode("ascii")}
    if isinstance(value, dict):
        return {str(key): as_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [as_jsonable(item) for item in value]
    return value


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def component(
    component_id: str,
    kind: str,
    props: dict[str, Any] | None = None,
    children: list[Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": component_id,
        "kind": kind,
        "props": {key: str(value) for key, value in (props or {}).items()},
        "children": children or [],
    }


def metric(component_id: str, label: str, value: Any) -> dict[str, Any]:
    return component(component_id, "inspector.kv", {"label": label, "value": value})


def text(component_id: str, value: str) -> dict[str, Any]:
    return component(component_id, "text", {"text": value})


def button(component_id: str, label: str, command: str, **payload: Any) -> dict[str, Any]:
    props = {"label": label, "command": command}
    for key, value in payload.items():
        props[f"payload.{key}"] = value
    return component(component_id, "control.button", props)


def object_row(index: int, item: Any) -> dict[str, Any]:
    object_id = field(item, 0, "objectId", "")
    name = field(item, 1, "name", "")
    path = field(item, 2, "path", "")
    active = field(item, 4, "activeSelf", False)
    child_count = field(item, 7, "childCount", 0)
    components = field(item, 9, "components", []) or []
    return component(
        f"brokkr.unity.tui.scene.object.{index}",
        "inspector.kv",
        {
            "label": name or path or object_id,
            "value": f"{'active' if active else 'inactive'}; children={child_count}; components={len(components)}",
            "path": path,
            "objectId": object_id,
        },
    )


def command_templates() -> list[dict[str, str]]:
    return [
        {
            "command": "unity.snapshot.refresh",
            "label": "Refresh Snapshot",
            "transport": "cultcache:intent-documents",
        },
        {
            "command": "unity.gameobject.create",
            "label": "Create GameObject",
            "transport": "cultcache:intent-documents",
        },
        {
            "command": "unity.selection.inspect",
            "label": "Inspect Selection",
            "transport": "cultcache:intent-documents",
        },
    ]


def prefab_slug(asset_path: str) -> str:
    slug = asset_path.lower().replace("\\", "/")
    if slug.startswith("assets/"):
        slug = slug[len("assets/"):]
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "prefab"


def prefab_inspection_key(asset_path: str) -> str:
    return f"unity/prefabs/{prefab_slug(asset_path)}/inspection"


def prefab_tui_key(asset_path: str) -> str:
    return f"eve/unity/prefabs/{prefab_slug(asset_path)}/tui"


def prefab_tui_uri(asset_path: str) -> str:
    return f"cultmesh://brokkr/eve/unity/prefabs/{prefab_slug(asset_path)}/tui"


def prefab_tui_id(asset_path: str) -> str:
    return f"brokkr.eve.unity_prefab.{prefab_slug(asset_path)}.tui.v0"


def object_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug or "gameobject"


def prefab_gameobject_inspection_key(asset_path: str, object_id: str) -> str:
    return f"unity/prefabs/{prefab_slug(asset_path)}/gameobjects/{object_slug(object_id)}/inspection"


def prefab_gameobject_tui_key(asset_path: str, object_id: str) -> str:
    return f"eve/unity/prefabs/{prefab_slug(asset_path)}/gameobjects/{object_slug(object_id)}/tui"


def prefab_gameobject_tui_uri(asset_path: str, object_id: str) -> str:
    return f"cultmesh://brokkr/eve/unity/prefabs/{prefab_slug(asset_path)}/gameobjects/{object_slug(object_id)}/tui"


def prefab_gameobject_tui_id(asset_path: str, object_id: str) -> str:
    return f"brokkr.eve.unity_prefab.{prefab_slug(asset_path)}.{object_slug(object_id)}.tui.v0"


def build_tui_surface(snapshot: Any, version: int = 1) -> dict[str, Any]:
    scene_objects = field(snapshot, 12, "sceneObjects", []) or []
    assets = field(snapshot, 13, "assets", []) or []
    capabilities = field(snapshot, 11, "capabilities", []) or []
    selected = field(snapshot, 9, "selectedObjectNames", []) or []
    updated_at = field(snapshot, 4, "observedAt", "") or now_utc()
    product_name = field(snapshot, 6, "productName", "") or "Unity"

    root = component(
        "brokkr.unity.tui.root",
        "surface",
        {"title": "Unity Editor TUI"},
        [
            component(
                "brokkr.unity.tui.status",
                "card",
                {"title": product_name},
                [
                    metric("brokkr.unity.tui.status.provider", "Provider", field(snapshot, 1, "providerId", "")),
                    metric("brokkr.unity.tui.status.project", "Project", field(snapshot, 3, "projectPath", "")),
                    metric("brokkr.unity.tui.status.version", "Unity", field(snapshot, 5, "unityVersion", "")),
                    metric("brokkr.unity.tui.status.scene", "Scene", field(snapshot, 7, "activeScenePath", "") or "(untitled)"),
                    metric("brokkr.unity.tui.status.observed", "Observed", updated_at),
                ],
            ),
            component(
                "brokkr.unity.tui.counts",
                "grid",
                {"columns": "4"},
                [
                    metric("brokkr.unity.tui.counts.objects", "Scene Objects", len(scene_objects)),
                    metric("brokkr.unity.tui.counts.assets", "Assets", len(assets)),
                    metric("brokkr.unity.tui.counts.selected", "Selected", len(selected)),
                    metric("brokkr.unity.tui.counts.capabilities", "Capabilities", len(capabilities)),
                ],
            ),
            component(
                "brokkr.unity.tui.selection",
                "card",
                {"title": "Selection"},
                [text("brokkr.unity.tui.selection.empty", "(none)")]
                if not selected
                else [
                    metric(f"brokkr.unity.tui.selection.{index}", "Selected", name)
                    for index, name in enumerate(selected)
                ],
            ),
            component(
                "brokkr.unity.tui.scene",
                "tree",
                {"title": "Scene Objects"},
                [object_row(index, item) for index, item in enumerate(scene_objects[:40])],
            ),
            component(
                "brokkr.unity.tui.actions",
                "rail.actions",
                {"title": "Actions"},
                [
                    button("brokkr.unity.tui.actions.refresh", "Refresh", "unity.snapshot.refresh"),
                    button("brokkr.unity.tui.actions.create", "Create Object", "unity.gameobject.create", name="GameObject"),
                ],
            ),
        ],
    )

    return {
        "type": "surface-state",
        "schema": "gamecult.eve.surface.v1",
        "providerId": "brokkr.unity_editor",
        "providerKind": "creative-tool.editor",
        "title": "Unity Editor TUI",
        "version": version,
        "updatedAt": updated_at,
        "surface": {
            "id": TUI_SURFACE_ID,
            "root": root,
            "styles": [
                {"name": "accent", "value": "#3fb6ff"},
                {"name": "status.ok", "value": "#2fbf71"},
                {"name": "density", "value": "compact"},
            ],
        },
        "commands": command_templates(),
        "cultMeshUri": TUI_SURFACE_URI,
        "source": {
            "cacheKey": "unity/host/current",
            "cachePath": str(DEFAULT_CACHE),
        },
    }


def prefab_node_row(prefix: str, node: dict[str, Any], index: int) -> dict[str, Any]:
    components = ", ".join(node.get("components", []))
    label = node.get("name", "") or node.get("fileId", "")
    value_parts = []
    if components:
        value_parts.append(components)
    value_parts.append("active" if node.get("active") else "inactive")
    children = node.get("children", [])
    if children:
        value_parts.append(f"children={len(children)}")
    return component(
        f"{prefix}.node.{index}",
        "inspector.kv",
        {
            "label": label,
            "value": "; ".join(value_parts),
            "fileId": node.get("fileId", ""),
            "tag": node.get("tag", ""),
            "layer": node.get("layer", ""),
        },
    )


def flatten_prefab_tree(nodes: list[dict[str, Any]], limit: int = 80) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []

    def walk(node: dict[str, Any], depth: int) -> None:
        if len(flattened) >= limit:
            return
        copy = dict(node)
        copy["name"] = f"{'  ' * depth}{copy.get('name', '')}"
        copy["children"] = node.get("children", [])
        flattened.append(copy)
        for child in node.get("children", []):
            walk(child, depth + 1)

    for item in nodes:
        walk(item, 0)
    return flattened


def build_prefab_tui_surface(inspection: dict[str, Any], version: int = 1) -> dict[str, Any]:
    asset_path = inspection["assetPath"]
    surface_id = prefab_tui_id(asset_path)
    surface_uri = prefab_tui_uri(asset_path)
    prefix = surface_id.replace(".", "_")
    updated_at = now_utc()
    histogram = list(inspection.get("componentHistogram", {}).items())
    scripts = list(inspection.get("monoScripts", {}).items())
    flattened_tree = flatten_prefab_tree(inspection.get("tree", []), limit=80)

    root = component(
        f"{prefix}.root",
        "surface",
        {"title": f"Prefab TUI: {Path(asset_path).name}"},
        [
            component(
                f"{prefix}.summary",
                "card",
                {"title": asset_path},
                [
                    metric(f"{prefix}.summary.objects", "GameObjects", inspection.get("gameObjects", 0)),
                    metric(f"{prefix}.summary.components", "Components", inspection.get("components", 0)),
                    metric(f"{prefix}.summary.transforms", "Transforms", inspection.get("transforms", 0)),
                    metric(f"{prefix}.summary.roots", "Roots", inspection.get("roots", 0)),
                    metric(f"{prefix}.summary.bytes", "Bytes", inspection.get("bytes", 0)),
                    metric(
                        f"{prefix}.summary.missingMono",
                        "Unresolved MonoBehaviours",
                        inspection.get("missingMonoBehaviours", 0),
                    ),
                ],
            ),
            component(
                f"{prefix}.components",
                "card",
                {"title": "Component Mix"},
                [
                    metric(f"{prefix}.components.{index}", name, count)
                    for index, (name, count) in enumerate(histogram[:24])
                ],
            ),
            component(
                f"{prefix}.scripts",
                "card",
                {"title": "Script Bindings"},
                [
                    metric(f"{prefix}.scripts.{index}", Path(path).name, f"{count} x {path}")
                    for index, (path, count) in enumerate(scripts[:24])
                ],
            ),
            component(
                f"{prefix}.hierarchy",
                "tree",
                {"title": "Prefab Hierarchy", "truncated": inspection.get("truncatedTree", False)},
                [
                    prefab_node_row(prefix, node, index)
                    for index, node in enumerate(flattened_tree)
                ],
            ),
            component(
                f"{prefix}.actions",
                "rail.actions",
                {"title": "Actions"},
                [
                    button(
                        f"{prefix}.actions.open",
                        "Open Prefab",
                        "unity.prefab.open",
                        assetPath=asset_path,
                    ),
                    button(
                        f"{prefix}.actions.refresh",
                        "Refresh Inspection",
                        "unity.prefab.inspect",
                        assetPath=asset_path,
                    ),
                ],
            ),
        ],
    )

    return {
        "type": "surface-state",
        "schema": "gamecult.eve.surface.v1",
        "providerId": "brokkr.unity_editor",
        "providerKind": "creative-tool.editor",
        "title": f"Prefab TUI: {Path(asset_path).name}",
        "version": version,
        "updatedAt": updated_at,
        "surface": {
            "id": surface_id,
            "root": root,
            "styles": [
                {"name": "accent", "value": "#3fb6ff"},
                {"name": "density", "value": "compact"},
            ],
        },
        "commands": [
            {
                "command": "unity.prefab.open",
                "label": "Open Prefab",
                "transport": "cultcache:intent-documents",
            },
            {
                "command": "unity.prefab.inspect",
                "label": "Refresh Prefab Inspection",
                "transport": "cultcache:intent-documents",
            },
        ],
        "cultMeshUri": surface_uri,
        "source": {
            "cacheKey": prefab_inspection_key(asset_path),
            "assetPath": asset_path,
        },
    }


def find_prefab_gameobject(inspection: dict[str, Any], selector: str) -> dict[str, Any] | None:
    def walk(nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
        for node in nodes:
            if node.get("fileId") == selector or node.get("name") == selector:
                return node
            found = walk(node.get("children", []))
            if found is not None:
                return found
        return None

    return walk(inspection.get("tree", []))


def collect_gameobject_ids(nodes: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()

    def walk(node: dict[str, Any]) -> None:
        file_id_value = node.get("fileId", "")
        if file_id_value:
            ids.add(file_id_value)
        for child in node.get("children", []):
            walk(child)

    for item in nodes:
        walk(item)
    return ids


def find_full_gameobject(inspection: dict[str, Any], selector: str) -> dict[str, Any] | None:
    found = find_prefab_gameobject(inspection, selector)
    if found is None:
        return None

    object_id = found.get("fileId", "")
    target: dict[str, Any] | None = None

    def walk(nodes: list[dict[str, Any]]) -> None:
        nonlocal target
        for node in nodes:
            if target is not None:
                return
            if node.get("fileId") == object_id:
                target = node
                return
            walk(node.get("children", []))

    walk(inspection.get("tree", []))
    return target


def component_field_rows(prefix: str, component_info: dict[str, Any], component_index: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    fields = component_info.get("resolvedFields", {}) or component_info.get("fields", {}) or {}
    if not fields:
        return [
            text(
                f"{prefix}.component.{component_index}.empty",
                "(no serialized fields exposed)",
            )
        ]
    for field_index, (name, value) in enumerate(fields.items()):
        rows.append(
            metric(
                f"{prefix}.component.{component_index}.field.{field_index}",
                name,
                value,
            )
        )
    return rows


def build_prefab_gameobject_inspection(inspection: dict[str, Any], selector: str) -> dict[str, Any]:
    target = find_full_gameobject(inspection, selector)
    if target is None:
        raise ValueError(f"GameObject not found in prefab inspection: {selector}")
    asset_path = inspection["assetPath"]
    child_ids = collect_gameobject_ids(target.get("children", []))
    return {
        "schema": PREFAB_GAMEOBJECT_INSPECTION_SCHEMA,
        "providerId": "brokkr.unity_editor",
        "observedAt": now_utc(),
        "assetPath": asset_path,
        "prefabInspectionKey": prefab_inspection_key(asset_path),
        "gameObject": target,
        "childrenIncluded": len(child_ids),
    }


def build_prefab_gameobject_tui_surface(object_inspection: dict[str, Any], version: int = 1) -> dict[str, Any]:
    asset_path = object_inspection["assetPath"]
    game_object = object_inspection["gameObject"]
    object_id = game_object["fileId"]
    surface_id = prefab_gameobject_tui_id(asset_path, object_id)
    surface_uri = prefab_gameobject_tui_uri(asset_path, object_id)
    prefix = surface_id.replace(".", "_")
    components = game_object.get("componentDetails", []) or game_object.get("components", [])

    root = component(
        f"{prefix}.root",
        "surface",
        {"title": f"GameObject TUI: {game_object.get('name', object_id)}"},
        [
            component(
                f"{prefix}.summary",
                "card",
                {"title": game_object.get("name", object_id)},
                [
                    metric(f"{prefix}.summary.prefab", "Prefab", asset_path),
                    metric(f"{prefix}.summary.fileId", "File ID", object_id),
                    metric(f"{prefix}.summary.active", "Active", game_object.get("active", "")),
                    metric(f"{prefix}.summary.tag", "Tag", game_object.get("tag", "")),
                    metric(f"{prefix}.summary.layer", "Layer", game_object.get("layer", "")),
                    metric(f"{prefix}.summary.components", "Components", len(components)),
                    metric(f"{prefix}.summary.children", "Children", len(game_object.get("children", []))),
                ],
            ),
            *[
                component(
                    f"{prefix}.component.{component_index}",
                    "card",
                    {
                        "title": component_info.get("type", "Component"),
                        "fileId": component_info.get("fileId", ""),
                        "scriptPath": component_info.get("scriptPath", ""),
                    },
                    [
                        metric(
                            f"{prefix}.component.{component_index}.type",
                            "Type",
                            component_info.get("type", ""),
                        ),
                        metric(
                            f"{prefix}.component.{component_index}.enabled",
                            "Enabled",
                            component_info.get("enabled", ""),
                        ),
                        *component_field_rows(prefix, component_info, component_index),
                    ],
                )
                for component_index, component_info in enumerate(components)
            ],
            component(
                f"{prefix}.actions",
                "rail.actions",
                {"title": "Actions"},
                [
                    button(
                        f"{prefix}.actions.open",
                        "Open Prefab",
                        "unity.prefab.open",
                        assetPath=asset_path,
                    ),
                    button(
                        f"{prefix}.actions.select",
                        "Select GameObject",
                        "unity.prefab.gameobject.select",
                        assetPath=asset_path,
                        fileId=object_id,
                    ),
                ],
            ),
        ],
    )

    return {
        "type": "surface-state",
        "schema": "gamecult.eve.surface.v1",
        "providerId": "brokkr.unity_editor",
        "providerKind": "creative-tool.editor",
        "title": f"GameObject TUI: {game_object.get('name', object_id)}",
        "version": version,
        "updatedAt": object_inspection.get("observedAt", now_utc()),
        "surface": {
            "id": surface_id,
            "root": root,
            "styles": [
                {"name": "accent", "value": "#3fb6ff"},
                {"name": "density", "value": "compact"},
            ],
        },
        "commands": [
            {
                "command": "unity.prefab.open",
                "label": "Open Prefab",
                "transport": "cultcache:intent-documents",
            },
            {
                "command": "unity.prefab.gameobject.select",
                "label": "Select Prefab GameObject",
                "transport": "cultcache:intent-documents",
            },
        ],
        "cultMeshUri": surface_uri,
        "source": {
            "cacheKey": prefab_gameobject_inspection_key(asset_path, object_id),
            "assetPath": asset_path,
            "fileId": object_id,
        },
    }


def eve_component_to_array(node: dict[str, Any]) -> list[Any]:
    return [
        node.get("id", ""),
        node.get("kind", ""),
        node.get("props", {}),
        [eve_component_to_array(child) for child in node.get("children", [])],
    ]


def eve_surface_to_msgpack_payload(surface: dict[str, Any]) -> bytes:
    import msgpack  # type: ignore

    tree = surface["surface"]
    payload = [
        surface["type"],
        surface["schema"],
        surface["providerId"],
        surface["providerKind"],
        surface["title"],
        surface["version"],
        surface["updatedAt"],
        [
            tree["id"],
            eve_component_to_array(tree["root"]),
            [[item["name"], item["value"]] for item in tree.get("styles", [])],
        ],
        [
            [item["command"], item["label"], item["transport"]]
            for item in surface.get("commands", [])
        ],
    ]
    return msgpack.packb(payload, use_bin_type=True)


def load_unity_snapshot(cache_path: Path) -> Any:
    docs = {doc.key: doc for doc in read_documents(cache_path)}
    snapshot_doc = docs.get("unity/host/current")
    if snapshot_doc is None:
        raise RuntimeError("Unity host snapshot missing: unity/host/current")
    return decode_payload(snapshot_doc.payload)


def read_or_build_tui_surface(cache_path: Path) -> dict[str, Any]:
    docs = {doc.key: doc for doc in read_documents(cache_path)}
    existing = docs.get(TUI_SURFACE_KEY)
    if existing is not None:
        decoded = decode_payload(existing.payload)
        if isinstance(decoded, list):
            return msgpack_surface_to_json(decoded, existing.stored_at)
        if isinstance(decoded, dict):
            return decoded
    return build_tui_surface(load_unity_snapshot(cache_path))


def read_surface_document(cache_path: Path, key: str) -> dict[str, Any] | None:
    docs = {doc.key: doc for doc in read_documents(cache_path)}
    existing = docs.get(key)
    if existing is None:
        return None
    decoded = decode_payload(existing.payload)
    if isinstance(decoded, list):
        return msgpack_surface_to_json(decoded, existing.stored_at)
    if isinstance(decoded, dict):
        return decoded
    return None


def msgpack_component_to_json(node: Any) -> dict[str, Any]:
    return component(
        field(node, 0, "id", ""),
        field(node, 1, "kind", ""),
        field(node, 2, "props", {}) or {},
        [msgpack_component_to_json(child) for child in (field(node, 3, "children", []) or [])],
    )


def msgpack_surface_to_json(payload: list[Any], stored_at: str | None = None) -> dict[str, Any]:
    surface_tree = field(payload, 7, "surface", [])
    styles = field(surface_tree, 2, "styles", []) or []
    commands = field(payload, 8, "commands", []) or []
    surface = {
        "type": field(payload, 0, "type", ""),
        "schema": field(payload, 1, "schema", ""),
        "providerId": field(payload, 2, "providerId", ""),
        "providerKind": field(payload, 3, "providerKind", ""),
        "title": field(payload, 4, "title", ""),
        "version": field(payload, 5, "version", 0),
        "updatedAt": field(payload, 6, "updatedAt", stored_at or ""),
        "surface": {
            "id": field(surface_tree, 0, "id", ""),
            "root": msgpack_component_to_json(field(surface_tree, 1, "root", [])),
            "styles": [
                {"name": field(item, 0, "name", ""), "value": field(item, 1, "value", "")}
                for item in styles
            ],
        },
        "commands": [
            {
                "command": field(item, 0, "command", ""),
                "label": field(item, 1, "label", ""),
                "transport": field(item, 2, "transport", ""),
            }
            for item in commands
        ],
        "cultMeshUri": TUI_SURFACE_URI,
    }
    return surface


def command_overview(args: argparse.Namespace) -> int:
    docs = read_documents(args.cache)
    by_key = {doc.key: doc for doc in docs}
    snapshot_doc = by_key.get("unity/host/current")
    snapshot = decode_payload(snapshot_doc.payload) if snapshot_doc else None

    command_count = sum(1 for doc in docs if doc.key.startswith("unity/commands/"))
    receipt_count = sum(1 for doc in docs if doc.key.startswith("unity/receipts/"))
    sync_count = sum(1 for doc in docs if doc.key.startswith("sync/"))

    overview: dict[str, Any] = {
        "cache": str(args.cache),
        "documents": len(docs),
        "commands": command_count,
        "receipts": receipt_count,
        "syncDocuments": sync_count,
    }

    if snapshot is not None:
        scene_objects = field(snapshot, 12, "sceneObjects", []) or []
        assets = field(snapshot, 13, "assets", []) or []
        capabilities = field(snapshot, 11, "capabilities", []) or []
        selected = field(snapshot, 9, "selectedObjectNames", []) or []
        overview.update(
            {
                "providerId": field(snapshot, 1, "providerId", ""),
                "toolKind": field(snapshot, 2, "toolKind", ""),
                "projectPath": field(snapshot, 3, "projectPath", ""),
                "observedAt": field(snapshot, 4, "observedAt", ""),
                "unityVersion": field(snapshot, 5, "unityVersion", ""),
                "productName": field(snapshot, 6, "productName", ""),
                "activeScenePath": field(snapshot, 7, "activeScenePath", ""),
                "openSceneCount": field(snapshot, 8, "openSceneCount", 0),
                "selectedObjectNames": selected,
                "capabilityCount": len(capabilities),
                "sceneObjectCount": len(scene_objects),
                "assetCount": len(assets),
                "sampleSceneObjects": [
                    {
                        "objectId": field(item, 0, "objectId", ""),
                        "name": field(item, 1, "name", ""),
                        "path": field(item, 2, "path", ""),
                        "activeSelf": field(item, 4, "activeSelf", None),
                        "parentId": field(item, 8, "parentId", ""),
                    }
                    for item in scene_objects[: args.limit]
                ],
            }
        )
    else:
        overview["unityHostSnapshot"] = "missing"

    print(json.dumps(as_jsonable(overview), indent=2, sort_keys=True))
    return 0


def command_list(args: argparse.Namespace) -> int:
    docs = sorted(read_documents(args.cache), key=lambda doc: (doc.type, doc.key))
    for doc in docs[: args.limit]:
        stored = f" storedAt={doc.stored_at}" if doc.stored_at else ""
        print(f"{doc.type} {doc.key}{stored}")
    if len(docs) > args.limit:
        print(f"... {len(docs) - args.limit} more")
    return 0


def command_get(args: argparse.Namespace) -> int:
    docs = {doc.key: doc for doc in read_documents(args.cache)}
    doc = docs.get(args.key)
    if doc is None:
        print(f"Document not found: {args.key}", file=sys.stderr)
        return 1

    payload = decode_payload(doc.payload)
    output = {
        "key": doc.key,
        "type": doc.type,
        "storedAt": doc.stored_at,
        "payload": payload,
    }
    print(json.dumps(as_jsonable(output), indent=2, sort_keys=True))
    return 0


def command_surface(args: argparse.Namespace) -> int:
    if args.uri in (TUI_SURFACE_URI, TUI_SURFACE_KEY, TUI_SURFACE_ID):
        surface = read_or_build_tui_surface(args.cache)
        print(json.dumps(as_jsonable(surface), indent=2, sort_keys=True))
        return 0

    if args.uri.startswith("cultmesh://brokkr/eve/unity/prefabs/"):
        key = args.uri.removeprefix("cultmesh://brokkr/")
        surface = read_surface_document(args.cache, key)
        if surface is not None:
            print(json.dumps(as_jsonable(surface), indent=2, sort_keys=True))
            return 0
        print(f"Surface not published in local mirror: {args.uri}", file=sys.stderr)
        return 1

    if args.uri.startswith("eve/unity/prefabs/"):
        surface = read_surface_document(args.cache, args.uri)
        if surface is not None:
            print(json.dumps(as_jsonable(surface), indent=2, sort_keys=True))
            return 0
        print(f"Unsupported local surface URI: {args.uri}", file=sys.stderr)
        return 1

    print(f"Unsupported local surface URI: {args.uri}", file=sys.stderr)
    return 1


def command_publish_tui(args: argparse.Namespace) -> int:
    surface = build_tui_surface(load_unity_snapshot(args.cache), version=args.version)
    document = Document(
        key=TUI_SURFACE_KEY,
        type="gamecult.eve.surface",
        payload=eve_surface_to_msgpack_payload(surface),
        stored_at=now_utc(),
    )
    write_document(args.cache, document)
    if args.quiet:
        return 0

    print(
        json.dumps(
            {
                "published": True,
                "cache": str(args.cache),
                "key": document.key,
                "type": document.type,
                "cultMeshUri": TUI_SURFACE_URI,
                "surfaceId": TUI_SURFACE_ID,
                "storedAt": document.stored_at,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def command_prefab(args: argparse.Namespace) -> int:
    prefab_path = args.path
    if not prefab_path.is_absolute():
        prefab_path = (Path.cwd() / prefab_path).resolve()
    if not prefab_path.exists():
        print(f"Prefab not found: {prefab_path}", file=sys.stderr)
        return 1
    if prefab_path.suffix.lower() != ".prefab":
        print(f"Not a Unity prefab: {prefab_path}", file=sys.stderr)
        return 1

    inspection = inspect_prefab(prefab_path, max_objects=args.max_objects)
    print(json.dumps(as_jsonable(inspection), indent=2, sort_keys=True))
    return 0


def command_publish_prefab(args: argparse.Namespace) -> int:
    prefab_path = args.path
    if not prefab_path.is_absolute():
        prefab_path = (Path.cwd() / prefab_path).resolve()
    if not prefab_path.exists():
        print(f"Prefab not found: {prefab_path}", file=sys.stderr)
        return 1
    if prefab_path.suffix.lower() != ".prefab":
        print(f"Not a Unity prefab: {prefab_path}", file=sys.stderr)
        return 1

    inspection = inspect_prefab(prefab_path, max_objects=args.max_objects)
    inspection["schema"] = PREFAB_INSPECTION_SCHEMA
    inspection["providerId"] = "brokkr.unity_editor"
    inspection["observedAt"] = now_utc()
    asset_path = inspection["assetPath"]
    inspection_key = prefab_inspection_key(asset_path)
    surface_key = prefab_tui_key(asset_path)
    surface_uri = prefab_tui_uri(asset_path)
    surface = build_prefab_tui_surface(inspection, version=args.version)
    stored_at = now_utc()

    import msgpack  # type: ignore

    write_document(
        args.cache,
        Document(
            key=inspection_key,
            type=PREFAB_INSPECTION_SCHEMA,
            payload=msgpack.packb(inspection, use_bin_type=True),
            stored_at=stored_at,
        ),
    )
    write_document(
        args.cache,
        Document(
            key=surface_key,
            type="gamecult.eve.surface",
            payload=eve_surface_to_msgpack_payload(surface),
            stored_at=stored_at,
        ),
    )

    if args.quiet:
        return 0

    print(
        json.dumps(
            {
                "published": True,
                "cache": str(args.cache),
                "assetPath": asset_path,
                "inspectionKey": inspection_key,
                "inspectionType": PREFAB_INSPECTION_SCHEMA,
                "surfaceKey": surface_key,
                "surfaceType": "gamecult.eve.surface",
                "cultMeshUri": surface_uri,
                "surfaceId": prefab_tui_id(asset_path),
                "storedAt": stored_at,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def command_publish_prefab_object(args: argparse.Namespace) -> int:
    prefab_path = args.path
    if not prefab_path.is_absolute():
        prefab_path = (Path.cwd() / prefab_path).resolve()
    if not prefab_path.exists():
        print(f"Prefab not found: {prefab_path}", file=sys.stderr)
        return 1
    if prefab_path.suffix.lower() != ".prefab":
        print(f"Not a Unity prefab: {prefab_path}", file=sys.stderr)
        return 1

    inspection = inspect_prefab(prefab_path, max_objects=args.max_objects)
    inspection["schema"] = PREFAB_INSPECTION_SCHEMA
    inspection["providerId"] = "brokkr.unity_editor"
    inspection["observedAt"] = now_utc()
    object_inspection = build_prefab_gameobject_inspection(inspection, args.selector)
    asset_path = object_inspection["assetPath"]
    object_id = object_inspection["gameObject"]["fileId"]
    object_key = prefab_gameobject_inspection_key(asset_path, object_id)
    surface_key = prefab_gameobject_tui_key(asset_path, object_id)
    surface_uri = prefab_gameobject_tui_uri(asset_path, object_id)
    surface = build_prefab_gameobject_tui_surface(object_inspection, version=args.version)
    stored_at = now_utc()

    import msgpack  # type: ignore

    write_document(
        args.cache,
        Document(
            key=object_key,
            type=PREFAB_GAMEOBJECT_INSPECTION_SCHEMA,
            payload=msgpack.packb(object_inspection, use_bin_type=True),
            stored_at=stored_at,
        ),
    )
    write_document(
        args.cache,
        Document(
            key=surface_key,
            type="gamecult.eve.surface",
            payload=eve_surface_to_msgpack_payload(surface),
            stored_at=stored_at,
        ),
    )

    if args.quiet:
        return 0

    print(
        json.dumps(
            {
                "published": True,
                "cache": str(args.cache),
                "assetPath": asset_path,
                "gameObjectName": object_inspection["gameObject"]["name"],
                "fileId": object_id,
                "inspectionKey": object_key,
                "inspectionType": PREFAB_GAMEOBJECT_INSPECTION_SCHEMA,
                "surfaceKey": surface_key,
                "surfaceType": "gamecult.eve.surface",
                "cultMeshUri": surface_uri,
                "surfaceId": prefab_gameobject_tui_id(asset_path, object_id),
                "storedAt": stored_at,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def existing_default_cache() -> Path:
    cwd_cache = Path.cwd() / ".brokkr" / "unity-editor.ccmp"
    if cwd_cache.exists():
        return cwd_cache
    return DEFAULT_CACHE


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect a Brokkr Unity CultCache mirror."
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=existing_default_cache(),
        help="Path to unity-editor.ccmp.",
    )
    subparsers = parser.add_subparsers(dest="command")

    overview = subparsers.add_parser("overview", help="Summarize the Unity mirror.")
    overview.add_argument("--limit", type=int, default=8, help="Scene object sample size.")
    overview.set_defaults(func=command_overview)

    list_cmd = subparsers.add_parser("list", help="List document keys.")
    list_cmd.add_argument("--limit", type=int, default=80, help="Maximum rows to print.")
    list_cmd.set_defaults(func=command_list)

    get_cmd = subparsers.add_parser("get", help="Print a decoded document payload.")
    get_cmd.add_argument("key", help="CultCache document key.")
    get_cmd.set_defaults(func=command_get)

    surface_cmd = subparsers.add_parser("surface", help="Resolve a local Eve surface.")
    surface_cmd.add_argument(
        "uri",
        nargs="?",
        default=TUI_SURFACE_URI,
        help="Surface URI, key, or id. Defaults to the Unity editor TUI URI.",
    )
    surface_cmd.set_defaults(func=command_surface)

    publish_tui = subparsers.add_parser(
        "publish-tui",
        help="Publish the generated Unity TUI surface into the Brokkr cache.",
    )
    publish_tui.add_argument("--version", type=int, default=1, help="Surface document version.")
    publish_tui.add_argument("--quiet", action="store_true", help="Do not print the publish receipt.")
    publish_tui.set_defaults(func=command_publish_tui)

    prefab = subparsers.add_parser("prefab", help="Inspect a Unity prefab asset.")
    prefab.add_argument("path", type=Path, help="Path to a .prefab file.")
    prefab.add_argument(
        "--max-objects",
        type=int,
        default=120,
        help="Maximum GameObjects to include in the tree.",
    )
    prefab.set_defaults(func=command_prefab)

    publish_prefab = subparsers.add_parser(
        "publish-prefab",
        help="Publish prefab inspection state and an Eve TUI surface into the Brokkr cache.",
    )
    publish_prefab.add_argument("path", type=Path, help="Path to a .prefab file.")
    publish_prefab.add_argument("--version", type=int, default=1, help="Surface document version.")
    publish_prefab.add_argument(
        "--max-objects",
        type=int,
        default=160,
        help="Maximum GameObjects to include in the surface tree.",
    )
    publish_prefab.add_argument("--quiet", action="store_true", help="Do not print the publish receipt.")
    publish_prefab.set_defaults(func=command_publish_prefab)

    publish_prefab_object = subparsers.add_parser(
        "publish-prefab-object",
        help="Publish one prefab GameObject inspection and an Eve TUI surface.",
    )
    publish_prefab_object.add_argument("path", type=Path, help="Path to a .prefab file.")
    publish_prefab_object.add_argument("selector", help="GameObject name or fileID.")
    publish_prefab_object.add_argument("--version", type=int, default=1, help="Surface document version.")
    publish_prefab_object.add_argument(
        "--max-objects",
        type=int,
        default=240,
        help="Maximum GameObjects to parse from the prefab hierarchy.",
    )
    publish_prefab_object.add_argument("--quiet", action="store_true", help="Do not print the publish receipt.")
    publish_prefab_object.set_defaults(func=command_publish_prefab_object)

    parser.set_defaults(func=command_overview, limit=8)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.cache = args.cache.resolve()
    if not args.cache.exists():
        print(f"Cache not found: {args.cache}", file=sys.stderr)
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
