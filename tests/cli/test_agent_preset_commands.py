from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.cli.test_cli_init import _make_cli


def _create_preset(tmp_path: Path, slug: str, name: str = "Lead Hunter") -> None:
    preset_dir = tmp_path / "agents" / slug
    preset_dir.mkdir(parents=True)
    (preset_dir / "AGENT.json").write_text(
        f'{{"name": "{name}", "slug": "{slug}", "role": "Finder", "description": "Preset description"}}',
        encoding="utf-8",
    )
    (preset_dir / "SOUL.md").write_text(f"You are {name}.", encoding="utf-8")


def test_cli_init_uses_explicit_agent_preset(tmp_path):
    _create_preset(tmp_path, "lead-hunter")
    cli = _make_cli(
        env_overrides={"HERMES_HOME": str(tmp_path)},
        config_overrides={"agent": {"active_preset": "default"}},
        agent_preset="lead-hunter",
    )
    assert cli.agent_preset_slug == "lead-hunter"


def test_agent_use_updates_active_preset_and_prompts_for_new_session(tmp_path, capsys):
    cli = _make_cli(env_overrides={"HERMES_HOME": str(tmp_path)})
    cli.agent = object()
    cli.conversation_history = [{"role": "user", "content": "hi"}]
    presets = [
        SimpleNamespace(slug="default", built_in=True, name="Default", description="Default preset", role="", goal="", personality="", default_skills=[]),
        SimpleNamespace(slug="lead-hunter", built_in=False, name="Lead Hunter", description="Preset description", role="Finder", goal="Find leads", personality="", default_skills=[]),
    ]

    handler_globals = cli._handle_agent_command.__func__.__globals__
    original_list = handler_globals["list_agent_presets"]
    original_save = handler_globals["save_config_value"]
    try:
        handler_globals["list_agent_presets"] = lambda: presets
        handler_globals["save_config_value"] = lambda *_a, **_kw: True
        cli._handle_agent_command("/agent use lead-hunter")
    finally:
        handler_globals["list_agent_presets"] = original_list
        handler_globals["save_config_value"] = original_save

    assert cli.agent_preset_slug == "lead-hunter"
    output = capsys.readouterr().out
    assert "saved to config" in output
    assert "/new or /clear" in output


def test_agent_list_and_show_render_details(tmp_path, capsys):
    cli = _make_cli(env_overrides={"HERMES_HOME": str(tmp_path)}, agent_preset="lead-hunter")
    preset = SimpleNamespace(
        slug="lead-hunter",
        built_in=False,
        name="Lead Hunter",
        description="Preset description",
        role="Finder",
        goal="Find leads",
        personality="concise",
        default_skills=["local-business-opportunity-finder"],
    )
    presets = [SimpleNamespace(slug="default", built_in=True, name="Default", description="Default preset", role="", goal="", personality="", default_skills=[]), preset]

    handler_globals = cli._handle_agent_command.__func__.__globals__
    original_list = handler_globals["list_agent_presets"]
    original_resolve = handler_globals["resolve_agent_preset"]
    try:
        handler_globals["list_agent_presets"] = lambda: presets
        handler_globals["resolve_agent_preset"] = lambda *_a, **_kw: preset
        cli._handle_agent_command("/agent list")
        cli._handle_agent_command("/agent show")
    finally:
        handler_globals["list_agent_presets"] = original_list
        handler_globals["resolve_agent_preset"] = original_resolve

    output = capsys.readouterr().out
    assert "lead-hunter" in output
    assert "Preset description" in output
    assert "Active agent preset: lead-hunter" in output


def test_process_command_routes_agent_command(tmp_path):
    _create_preset(tmp_path, "lead-hunter")
    cli = _make_cli(env_overrides={"HERMES_HOME": str(tmp_path)})

    with patch.object(cli, "_handle_agent_command") as handler:
        result = cli.process_command("/agent list")

    assert result is True
    handler.assert_called_once_with("/agent list")
