from pathlib import Path

from agent.agent_presets import (
    get_active_agent_slug,
    get_default_agent_preset,
    list_agent_presets,
    load_agent_preset,
    read_agent_preset_source,
    save_agent_preset,
    delete_agent_preset,
)


def test_list_agent_presets_returns_default_when_none_exist(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    presets = list_agent_presets()

    assert [preset.slug for preset in presets] == ["default", "flight-finder", "lead-hunter"]
    assert presets[0].built_in is True
    assert presets[0].soul_path == tmp_path / "SOUL.md"
    assert presets[1].built_in is True



def test_valid_preset_directory_is_discovered(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    preset_dir = tmp_path / "agents" / "lead-hunter"
    preset_dir.mkdir(parents=True)
    (preset_dir / "AGENT.json").write_text(
        '{"name": "Lead Hunter", "slug": "lead-hunter", "role": "Finder", "default_skills": ["local-business-opportunity-finder"]}',
        encoding="utf-8",
    )
    (preset_dir / "SOUL.md").write_text("You are the lead hunter preset.", encoding="utf-8")
    (preset_dir / "AGENTS.md").write_text("Preset instructions.", encoding="utf-8")

    preset = load_agent_preset("lead-hunter")

    assert preset.slug == "lead-hunter"
    assert preset.name == "Lead Hunter"
    assert preset.role == "Finder"
    assert preset.default_skills == ["local-business-opportunity-finder"]
    assert preset.agents_path == preset_dir / "AGENTS.md"



def test_invalid_preset_is_skipped_safely(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    invalid_dir = tmp_path / "agents" / "broken"
    invalid_dir.mkdir(parents=True)
    (invalid_dir / "AGENT.json").write_text("{not-json", encoding="utf-8")
    (invalid_dir / "SOUL.md").write_text("still here", encoding="utf-8")

    presets = list_agent_presets()

    assert [preset.slug for preset in presets] == ["default", "flight-finder", "lead-hunter"]



def test_active_preset_falls_back_to_default_when_unset(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    assert get_active_agent_slug({}) == "default"
    assert get_active_agent_slug({"agent": {"active_preset": "missing"}}) == "default"
    assert get_default_agent_preset().slug == "default"


def test_default_preset_metadata_reflects_general_assistant(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    preset = get_default_agent_preset()

    assert preset.slug == "default"
    assert preset.built_in is True
    assert "assistant" in preset.role.lower()
    assert "coding" in preset.goal.lower()
    assert "general-purpose" in preset.description.lower()
    assert preset.emoji == "✨"


def test_builtin_lead_hunter_preset_is_available_without_user_writes(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    preset = load_agent_preset("lead-hunter")
    soul = read_agent_preset_source(preset.soul_path)

    assert preset.slug == "lead-hunter"
    assert preset.built_in is True
    assert preset.default_skills == ["local-business-opportunity-finder"]
    assert preset.emoji == "🎯"
    assert "Lead Hunter" in soul
    assert "Opportunity Score" in soul
    assert load_agent_preset("flight-finder").default_skills == ["flight-fare-monitoring"]
    assert not (tmp_path / "agents" / "lead-hunter").exists()


def test_custom_preset_overrides_builtin_template(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    custom = save_agent_preset(
        "lead-hunter",
        metadata={"name": "Lead Hunter Custom", "default_skills": ["hermes-lead-hunter-setup"]},
        soul_content="Custom lead hunter soul.",
        agents_content="Custom preset instructions.",
    )

    loaded = load_agent_preset("lead-hunter")

    assert custom.slug == "lead-hunter"
    assert loaded.name == "Lead Hunter Custom"
    assert loaded.built_in is False
    assert loaded.default_skills == ["hermes-lead-hunter-setup"]
    assert read_agent_preset_source(loaded.soul_path) == "Custom lead hunter soul.\n"


def test_saving_default_preset_updates_root_soul_and_metadata(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    saved = save_agent_preset(
        "default",
        metadata={
            "name": "Default",
            "emoji": "👑",
            "role": "Updated main assistant",
            "goal": "Ship code and help everywhere",
            "description": "Updated default preset",
            "personality": "focused",
            "default_skills": ["plan", "systematic-debugging"],
        },
        soul_content="You are the updated default assistant.",
        agents_content="Always verify before shipping.",
    )

    loaded = load_agent_preset("default")

    assert saved.slug == "default"
    assert loaded.emoji == "👑"
    assert loaded.role == "Updated main assistant"
    assert loaded.default_skills == ["plan", "systematic-debugging"]
    assert read_agent_preset_source(loaded.soul_path) == "You are the updated default assistant.\n"
    assert read_agent_preset_source(loaded.agents_path) == "Always verify before shipping.\n"
    assert loaded.agents_path == tmp_path / "agents" / "default" / "AGENTS.md"


def test_deleting_custom_override_restores_builtin_template(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    save_agent_preset(
        "lead-hunter",
        metadata={"name": "Lead Hunter Custom"},
        soul_content="Custom lead hunter soul.",
        agents_content=None,
    )
    delete_agent_preset("lead-hunter")

    restored = load_agent_preset("lead-hunter")

    assert restored.slug == "lead-hunter"
    assert restored.built_in is True
    assert restored.name == "Lead Hunter"
