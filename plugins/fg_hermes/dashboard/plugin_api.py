from __future__ import annotations

import re
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from hermes_cli.config import get_hermes_home, load_config, save_config
from plugins.fg_hermes.agent import (
    delete_agent_preset,
    get_active_agent_slug,
    list_agent_presets,
    read_agent_preset_source,
    resolve_agent_preset,
    save_agent_preset,
)

router = APIRouter()


class AgentPresetPayload(BaseModel):
    name: str
    slug: Optional[str] = None
    emoji: str = "🤖"
    role: str = ""
    goal: str = ""
    description: str = ""
    personality: str = ""
    default_skills: List[str] = []
    soul_content: str = ""
    agents_content: str = ""


class AgentActivatePayload(BaseModel):
    slug: Optional[str] = None


def _read_dashboard_text(path: Optional[Path]) -> str:
    if not path or not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _truncate_dashboard_text(text: str, max_chars: int = 4000) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    head_chars = int(max_chars * 0.75)
    tail_chars = max_chars - head_chars
    return (
        text[:head_chars].rstrip()
        + "\n\n[…truncated…]\n\n"
        + text[-tail_chars:].lstrip()
    )


def _compact_dashboard_text(text: str, max_chars: int = 240) -> str:
    compact = re.sub(r"\s+", " ", (text or "").strip())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "…"


def _strip_dashboard_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text or "", flags=re.DOTALL)


def _derive_agent_identity(soul_content: str) -> tuple[str, str]:
    cleaned = _strip_dashboard_comments(soul_content or "")
    filtered_lines: list[str] = []
    for raw_line in cleaned.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("#"):
            continue
        filtered_lines.append(stripped)
    filtered_text = "\n".join(filtered_lines).strip()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", filtered_text) if p.strip()]

    default_role = "Hermes Agent"
    default_description = (
        "Configurable CLI and dashboard agent with identity shaped by SOUL.md, AGENTS.md, "
        "memory, and runtime configuration."
    )
    if not paragraphs:
        return default_role, default_description
    role = paragraphs[0]
    description = paragraphs[1] if len(paragraphs) > 1 else paragraphs[0]
    return role, description


def _resolve_personality_prompt(config: dict, personality_name: str) -> str:
    personalities = config.get("agent", {}).get("personalities", {})
    personality_entry = personalities.get(personality_name) if isinstance(personalities, dict) else None
    if isinstance(personality_entry, str):
        return personality_entry
    if isinstance(personality_entry, dict):
        return str(
            personality_entry.get("system_prompt")
            or personality_entry.get("description")
            or ""
        )
    return ""


def _agent_source_card(
    key: str,
    title: str,
    path: Optional[Path],
    content: str,
    missing_summary: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "path": str(path) if path else "",
        "present": bool(content),
        "summary": _compact_dashboard_text(content) if content else missing_summary,
        "content": _truncate_dashboard_text(content),
    }


def _serialize_agent_preset(preset, config: dict, *, active_slug: str) -> dict[str, Any]:
    soul_content = read_agent_preset_source(preset.soul_path)
    agents_content = read_agent_preset_source(preset.agents_path)
    role, description = _derive_agent_identity(soul_content)
    return {
        "name": preset.name,
        "slug": preset.slug,
        "emoji": preset.emoji,
        "role": preset.role or role,
        "goal": preset.goal,
        "description": preset.description or description,
        "personality": preset.personality,
        "personality_prompt": _resolve_personality_prompt(config, preset.personality),
        "default_skills": list(preset.default_skills),
        "built_in": preset.built_in,
        "active": preset.slug == active_slug,
        "soul_content": soul_content,
        "agents_content": agents_content,
        "soul_path": str(preset.soul_path) if preset.soul_path else None,
        "agents_path": str(preset.agents_path) if preset.agents_path else None,
        "metadata_path": str(preset.metadata_path) if preset.metadata_path else None,
    }


def _build_agent_profile_payload(config: dict) -> dict[str, Any]:
    active_slug = get_active_agent_slug(config)
    preset = resolve_agent_preset(active_slug, config=config)
    user_path = get_hermes_home() / "memories" / "USER.md"
    memory_path = get_hermes_home() / "memories" / "MEMORY.md"

    soul_content = read_agent_preset_source(preset.soul_path)
    agents_content = read_agent_preset_source(preset.agents_path)
    user_content = _read_dashboard_text(user_path)
    memory_content = _read_dashboard_text(memory_path)
    serialized_presets = [
        _serialize_agent_preset(item, config, active_slug=active_slug)
        for item in list_agent_presets()
    ]
    current_preset = next(
        (item for item in serialized_presets if item["slug"] == preset.slug),
        None,
    ) or serialized_presets[0]

    sources = [
        _agent_source_card(
            "soul",
            "SOUL.md",
            preset.soul_path,
            soul_content,
            "No SOUL.md configured for this preset.",
        ),
        _agent_source_card(
            "agents",
            "AGENTS.md",
            preset.agents_path,
            agents_content,
            "No preset AGENTS.md configured.",
        ),
        _agent_source_card(
            "user",
            "USER.md",
            user_path,
            user_content,
            "No saved user profile yet.",
        ),
        _agent_source_card(
            "memory",
            "MEMORY.md",
            memory_path,
            memory_content,
            "No saved agent memory yet.",
        ),
    ]

    personalities = config.get("agent", {}).get("personalities", {})
    available_personalities = (
        sorted(str(name) for name in personalities.keys())
        if isinstance(personalities, dict)
        else []
    )

    from hermes_cli.web_server import get_model_info

    return {
        "name": preset.name,
        "role": current_preset["role"],
        "description": current_preset["description"],
        "active_personality": current_preset.get("personality") or "",
        "personality_prompt": current_preset.get("personality_prompt") or "",
        "active_preset": preset.slug,
        "presets": serialized_presets,
        "current_preset": current_preset,
        "available_personalities": available_personalities,
        "cron_examples": [
            {
                "name": f"Run as {preset.slug}",
                "payload": {
                    "action": "create",
                    "name": f"{preset.name} scheduled task",
                    "schedule": "0 9 * * *",
                    "agent_name": preset.slug,
                    "prompt": "Describe the task to run under this preset.",
                },
            }
        ],
        "model": get_model_info(),
        "sources": sources,
        "source_map": {source["key"]: source for source in sources},
    }


@router.get("/agent/profile")
async def get_agent_profile():
    return _build_agent_profile_payload(load_config())


@router.get("/agents")
async def get_agents():
    config = load_config()
    payload = _build_agent_profile_payload(config)
    return {
        "active_preset": payload["active_preset"],
        "presets": payload["presets"],
        "available_personalities": payload["available_personalities"],
    }


@router.post("/agents")
async def create_agent(body: AgentPresetPayload):
    config = load_config()
    existing = {preset.slug for preset in list_agent_presets()}
    requested_slug = body.slug or body.name
    preset_slug = re.sub(r"[^a-z0-9]+", "-", requested_slug.lower()).strip("-") or "default"
    if preset_slug in existing:
        raise HTTPException(status_code=409, detail=f"Agent preset already exists: {preset_slug}")
    preset = save_agent_preset(
        preset_slug,
        metadata=body.model_dump(),
        soul_content=body.soul_content,
        agents_content=body.agents_content,
    )
    return _serialize_agent_preset(preset, config, active_slug=get_active_agent_slug(config))


@router.put("/agents/{slug}")
async def update_agent(slug: str, body: AgentPresetPayload):
    normalized = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-") or "default"
    try:
        preset = save_agent_preset(
            normalized,
            metadata={**body.model_dump(), "slug": normalized},
            soul_content=body.soul_content,
            agents_content=body.agents_content,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    config = load_config()
    return _serialize_agent_preset(preset, config, active_slug=get_active_agent_slug(config))


@router.delete("/agents/{slug}")
async def remove_agent(slug: str):
    config = load_config()
    try:
        delete_agent_preset(slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if get_active_agent_slug(config) == slug:
        config.setdefault("agent", {})["active_preset"] = "default"
        save_config(config)
    return {"ok": True}


@router.post("/agents/{slug}/activate")
async def activate_agent(slug: str, body: Optional[AgentActivatePayload] = None):
    config = load_config()
    target_slug = (body.slug if body and body.slug else slug) or slug
    normalized = re.sub(r"[^a-z0-9]+", "-", target_slug.lower()).strip("-") or "default"
    available = {preset.slug for preset in list_agent_presets()}
    if normalized not in available:
        raise HTTPException(status_code=404, detail=f"Agent preset not found: {normalized}")
    config.setdefault("agent", {})["active_preset"] = normalized
    save_config(config)
    return {"ok": True, "active_preset": normalized}
