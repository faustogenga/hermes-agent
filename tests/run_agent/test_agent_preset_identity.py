from pathlib import Path

from run_agent import AIAgent


def test_agent_preset_default_preserves_root_soul(monkeypatch, tmp_path):
    hermes_home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    hermes_home.mkdir(parents=True)
    (hermes_home / "SOUL.md").write_text("You are the default preset soul.", encoding="utf-8")

    agent = AIAgent(
        model="openai/gpt-5",
        api_key="test-key",
        base_url="https://example.com/v1",
        enabled_toolsets=[],
        quiet_mode=True,
        skip_memory=True,
        agent_preset="default",
    )

    prompt = agent._build_system_prompt()

    assert "You are the default preset soul." in prompt



def test_agent_preset_uses_preset_soul_and_agents(monkeypatch, tmp_path):
    hermes_home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    preset_dir = hermes_home / "agents" / "lead-hunter"
    preset_dir.mkdir(parents=True)
    (preset_dir / "AGENT.json").write_text(
        '{"name": "Lead Hunter", "slug": "lead-hunter", "default_skills": []}',
        encoding="utf-8",
    )
    (preset_dir / "SOUL.md").write_text("You are the lead hunter preset soul.", encoding="utf-8")
    (preset_dir / "AGENTS.md").write_text("Preset AGENTS instructions.", encoding="utf-8")

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    agent = AIAgent(
        model="openai/gpt-5",
        api_key="test-key",
        base_url="https://example.com/v1",
        enabled_toolsets=[],
        quiet_mode=True,
        skip_memory=True,
        agent_preset="lead-hunter",
    )

    prompt = agent._build_system_prompt()

    assert "You are the lead hunter preset soul." in prompt
    assert "Preset AGENTS instructions." in prompt



def test_agent_preset_default_skills_are_preloaded(monkeypatch, tmp_path):
    hermes_home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    preset_dir = hermes_home / "agents" / "lead-hunter"
    preset_dir.mkdir(parents=True)
    (preset_dir / "AGENT.json").write_text(
        '{"name": "Lead Hunter", "slug": "lead-hunter", "default_skills": ["local-business-opportunity-finder"]}',
        encoding="utf-8",
    )
    (preset_dir / "SOUL.md").write_text("You are the lead hunter preset soul.", encoding="utf-8")

    monkeypatch.setattr(
        "run_agent.build_preloaded_skills_prompt",
        lambda skills, task_id=None: ("[PRELOADED PRESET SKILL]", list(skills), []),
    )

    agent = AIAgent(
        model="openai/gpt-5",
        api_key="test-key",
        base_url="https://example.com/v1",
        enabled_toolsets=[],
        quiet_mode=True,
        skip_memory=True,
        agent_preset="lead-hunter",
    )

    prompt = agent._build_system_prompt()

    assert "[PRELOADED PRESET SKILL]" in prompt
    assert agent._preset_loaded_skills == ["local-business-opportunity-finder"]
