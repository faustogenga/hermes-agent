from argparse import Namespace
from unittest.mock import patch


@patch("hermes_cli.main.cmd_chat")
def test_top_level_agent_flag_routes_to_chat_with_agent(mock_cmd_chat):
    import sys
    from hermes_cli.main import main

    argv = ["hermes", "--agent", "lead-hunter"]
    with patch.object(sys, "argv", argv):
        main()

    args = mock_cmd_chat.call_args.args[0]
    assert args.command == "chat"
    assert args.agent == "lead-hunter"


@patch("hermes_cli.main.cmd_chat")
def test_chat_subcommand_parses_agent_flag(mock_cmd_chat):
    import sys
    from hermes_cli.main import main

    argv = ["hermes", "chat", "--agent", "lead-hunter", "-q", "hello"]
    with patch.object(sys, "argv", argv):
        main()

    args = mock_cmd_chat.call_args.args[0]
    assert args.command == "chat"
    assert args.agent == "lead-hunter"
    assert args.query == "hello"


def test_cmd_chat_passes_agent_preset_to_cli_main():
    from hermes_cli.main import cmd_chat

    args = Namespace(
        tui=False,
        continue_last=None,
        resume=None,
        model=None,
        provider=None,
        toolsets=None,
        skills=None,
        verbose=False,
        quiet=False,
        query="hello",
        image=None,
        worktree=False,
        checkpoints=False,
        pass_session_id=False,
        max_turns=None,
        yolo=False,
        source=None,
        agent="lead-hunter",
    )

    with patch("hermes_cli.main._has_any_provider_configured", return_value=True), \
         patch("tools.skills_sync.sync_skills"), \
         patch("cli.main") as cli_main:
        cmd_chat(args)

    kwargs = cli_main.call_args.kwargs
    assert kwargs["agent_preset"] == "lead-hunter"
