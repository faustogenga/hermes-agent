from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from hermes_constants import get_hermes_home

_DEFAULT_SLUG = "default"
_BUILTIN_TEMPLATE_DIR = Path(__file__).resolve().parent / "preset_templates"
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify_agent_name(value: str) -> str:
    slug = _SLUG_RE.sub("-", str(value or "").strip().lower()).strip("-")
    return slug or _DEFAULT_SLUG


@dataclass
class AgentPreset:
    name: str
    slug: str
    emoji: str = "🤖"
    role: str = ""
    goal: str = ""
    description: str = ""
    personality: str = ""
    default_skills: list[str] = field(default_factory=list)
    soul_path: Optional[Path] = None
    agents_path: Optional[Path] = None
    metadata_path: Optional[Path] = None
    built_in: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "slug": self.slug,
            "emoji": self.emoji,
            "role": self.role,
            "goal": self.goal,
            "description": self.description,
            "personality": self.personality,
            "default_skills": list(self.default_skills),
            "soul_path": str(self.soul_path) if self.soul_path else None,
            "agents_path": str(self.agents_path) if self.agents_path else None,
            "metadata_path": str(self.metadata_path) if self.metadata_path else None,
            "built_in": self.built_in,
        }


def get_agent_presets_dir() -> Path:
    return get_hermes_home() / "agents"


def _normalize_skill_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        items = raw.split(",")
    else:
        try:
            items = list(raw)
        except TypeError:
            items = [raw]
    normalized: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _default_override_dir() -> Path:
    return get_agent_presets_dir() / _DEFAULT_SLUG


def get_default_agent_preset() -> AgentPreset:
    hermes_home = get_hermes_home()
    soul_path = hermes_home / "SOUL.md"
    override_dir = _default_override_dir()
    metadata_path = override_dir / "AGENT.json"
    agents_path = override_dir / "AGENTS.md"
    metadata: dict[str, Any] = {}
    if metadata_path.exists():
        try:
            loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                metadata = loaded
        except Exception:
            metadata = {}
    return AgentPreset(
        name=str(metadata.get("name") or "Default"),
        slug=_DEFAULT_SLUG,
        emoji=str(metadata.get("emoji") or "✨"),
        role=str(metadata.get("role") or "Primary Hermes assistant"),
        goal=str(metadata.get("goal") or "Be an excellent general-purpose AI assistant for coding, development, research, operations, writing, and execution across the user’s work"),
        description=str(metadata.get("description") or "Built-in general-purpose preset mapped to the root SOUL.md behavior."),
        personality=str(metadata.get("personality") or ""),
        default_skills=_normalize_skill_list(metadata.get("default_skills")),
        soul_path=soul_path,
        agents_path=agents_path if agents_path.exists() else None,
        metadata_path=metadata_path if metadata_path.exists() else None,
        built_in=True,
    )


def _load_builtin_template_preset(slug: str) -> Optional[AgentPreset]:
    normalized = slugify_agent_name(slug)
    if normalized == _DEFAULT_SLUG:
        return get_default_agent_preset()
    preset_dir = _BUILTIN_TEMPLATE_DIR / normalized
    metadata_path = preset_dir / "AGENT.json"
    soul_path = preset_dir / "SOUL.md"
    if not metadata_path.exists() or not soul_path.exists():
        return None
    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return AgentPreset(
        name=str(data.get("name") or normalized.replace("-", " ").title()),
        slug=normalized,
        emoji=str(data.get("emoji") or "🤖"),
        role=str(data.get("role") or ""),
        goal=str(data.get("goal") or ""),
        description=str(data.get("description") or ""),
        personality=str(data.get("personality") or ""),
        default_skills=_normalize_skill_list(data.get("default_skills")),
        soul_path=soul_path,
        agents_path=(preset_dir / "AGENTS.md") if (preset_dir / "AGENTS.md").exists() else None,
        metadata_path=metadata_path,
        built_in=True,
    )


def _builtin_presets() -> list[AgentPreset]:
    presets = [get_default_agent_preset()]
    for candidate in sorted(_BUILTIN_TEMPLATE_DIR.glob("*/AGENT.json")):
        slug = candidate.parent.name
        preset = _load_builtin_template_preset(slug)
        if preset is not None and preset.slug != _DEFAULT_SLUG:
            presets.append(preset)
    return presets


def _load_preset_from_dir(preset_dir: Path) -> Optional[AgentPreset]:
    metadata_path = preset_dir / "AGENT.json"
    soul_path = preset_dir / "SOUL.md"
    if not metadata_path.exists() or not soul_path.exists():
        return None
    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if data.get("enabled", True) is False:
        return None
    slug = slugify_agent_name(data.get("slug") or preset_dir.name)
    if slug == _DEFAULT_SLUG:
        return None
    return AgentPreset(
        name=str(data.get("name") or slug.replace("-", " ").title()),
        slug=slug,
        emoji=str(data.get("emoji") or "🤖"),
        role=str(data.get("role") or ""),
        goal=str(data.get("goal") or ""),
        description=str(data.get("description") or ""),
        personality=str(data.get("personality") or ""),
        default_skills=_normalize_skill_list(data.get("default_skills")),
        soul_path=soul_path,
        agents_path=(preset_dir / "AGENTS.md") if (preset_dir / "AGENTS.md").exists() else None,
        metadata_path=metadata_path,
        built_in=False,
    )


def list_agent_presets() -> list[AgentPreset]:
    builtins = _builtin_presets()
    presets_dir = get_agent_presets_dir()
    if not presets_dir.exists():
        return builtins
    discovered: dict[str, AgentPreset] = {}
    for child in sorted(presets_dir.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir():
            continue
        preset = _load_preset_from_dir(child)
        if preset is not None:
            discovered[preset.slug] = preset
    merged: list[AgentPreset] = []
    for preset in builtins:
        merged.append(discovered.pop(preset.slug, preset))
    merged.extend(discovered[slug] for slug in sorted(discovered.keys()))
    return merged


def load_agent_preset(slug: Optional[str]) -> AgentPreset:
    normalized = slugify_agent_name(slug or _DEFAULT_SLUG)
    if normalized == _DEFAULT_SLUG:
        return get_default_agent_preset()
    for preset in list_agent_presets():
        if preset.slug == normalized:
            return preset
    raise FileNotFoundError(f"Agent preset not found: {normalized}")


def get_active_agent_slug(config: Optional[dict[str, Any]] = None) -> str:
    config = config or {}
    agent_cfg = config.get("agent", {}) if isinstance(config, dict) else {}
    slug = slugify_agent_name((agent_cfg or {}).get("active_preset") or _DEFAULT_SLUG)
    available = {preset.slug for preset in list_agent_presets()}
    return slug if slug in available else _DEFAULT_SLUG


def resolve_agent_preset(slug: Optional[str] = None, config: Optional[dict[str, Any]] = None) -> AgentPreset:
    target = slugify_agent_name(slug or get_active_agent_slug(config=config))
    try:
        return load_agent_preset(target)
    except FileNotFoundError:
        return get_default_agent_preset()


def _preset_dir_for_slug(slug: str) -> Path:
    return get_agent_presets_dir() / slugify_agent_name(slug)


def _write_text_if_present(path: Path, content: Optional[str]) -> None:
    if content is None:
        return
    text = str(content)
    if text.strip():
        path.write_text(text.rstrip() + "\n", encoding="utf-8")
    elif path.exists():
        path.unlink()


def save_agent_preset(
    slug: Optional[str],
    *,
    metadata: dict[str, Any],
    soul_content: str,
    agents_content: Optional[str] = None,
) -> AgentPreset:
    normalized_slug = slugify_agent_name(slug or metadata.get("slug") or metadata.get("name") or "")
    if normalized_slug == _DEFAULT_SLUG:
        hermes_home = get_hermes_home()
        preset_dir = _default_override_dir()
        preset_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = preset_dir / "AGENT.json"
        agents_path = preset_dir / "AGENTS.md"
        soul_path = hermes_home / "SOUL.md"
        payload = {
            "name": str(metadata.get("name") or "Default"),
            "slug": _DEFAULT_SLUG,
            "emoji": str(metadata.get("emoji") or "✨"),
            "role": str(metadata.get("role") or ""),
            "goal": str(metadata.get("goal") or ""),
            "description": str(metadata.get("description") or ""),
            "personality": str(metadata.get("personality") or ""),
            "default_skills": _normalize_skill_list(metadata.get("default_skills")),
            "enabled": True,
        }
        metadata_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        _write_text_if_present(soul_path, soul_content)
        _write_text_if_present(agents_path, agents_content)
        return load_agent_preset(_DEFAULT_SLUG)
    preset_dir = _preset_dir_for_slug(normalized_slug)
    preset_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = preset_dir / "AGENT.json"
    soul_path = preset_dir / "SOUL.md"
    agents_path = preset_dir / "AGENTS.md"
    payload = {
        "name": str(metadata.get("name") or normalized_slug.replace("-", " ").title()),
        "slug": normalized_slug,
        "emoji": str(metadata.get("emoji") or "🤖"),
        "role": str(metadata.get("role") or ""),
        "goal": str(metadata.get("goal") or ""),
        "description": str(metadata.get("description") or ""),
        "personality": str(metadata.get("personality") or ""),
        "default_skills": _normalize_skill_list(metadata.get("default_skills")),
        "enabled": bool(metadata.get("enabled", True)),
    }
    metadata_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_text_if_present(soul_path, soul_content)
    _write_text_if_present(agents_path, agents_content)
    return load_agent_preset(normalized_slug)


def delete_agent_preset(slug: str) -> None:
    normalized = slugify_agent_name(slug)
    if normalized == _DEFAULT_SLUG:
        raise ValueError("Cannot delete the built-in default preset")
    preset_dir = _preset_dir_for_slug(normalized)
    if not preset_dir.exists():
        raise FileNotFoundError(f"Agent preset not found: {normalized}")
    for child in preset_dir.iterdir():
        if child.is_file() or child.is_symlink():
            child.unlink()
    preset_dir.rmdir()


def read_agent_preset_source(path: Optional[Path]) -> str:
    if not path or not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""
