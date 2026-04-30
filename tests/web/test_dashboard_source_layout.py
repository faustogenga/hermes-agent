from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_TSX = REPO_ROOT / "web" / "src" / "App.tsx"
CRON_PAGE_TSX = REPO_ROOT / "web" / "src" / "pages" / "CronPage.tsx"


def test_cron_nav_is_adjacent_to_agent_in_header_menu() -> None:
    content = APP_TSX.read_text(encoding="utf-8")
    agent_idx = content.index('{ path: "/agent", label: "Agents", icon: Bot },')
    cron_idx = content.index('{ path: "/cron", labelKey: "cron", label: "Cron", icon: Clock },')
    sessions_idx = content.index('{ path: "/sessions", labelKey: "sessions", label: "Sessions", icon: MessageSquare },')

    assert agent_idx < cron_idx < sessions_idx


def test_cron_page_uses_card_layout_hooks_for_agent_like_rows() -> None:
    content = CRON_PAGE_TSX.read_text(encoding="utf-8")

    assert "cron-job-card" in content
    assert "cron-preset-pill" in content
    assert "cron-meta-chip" in content
    assert "cron-action-cluster" in content


def test_cron_page_contains_daily_schedule_overview_and_human_frequency_copy() -> None:
    content = CRON_PAGE_TSX.read_text(encoding="utf-8")

    assert "cron-schedule-overview-card" in content
    assert "cron-timeline-track" in content
    assert "describeDailyCadence" in content
    assert "estimateDurationMinutes" in content
    assert "overlap risk" in content.lower()


def test_cron_page_uses_soft_pastel_badges_instead_of_heavy_badge_treatment() -> None:
    content = CRON_PAGE_TSX.read_text(encoding="utf-8")

    assert "cron-soft-badge" in content
    assert "cron-soft-badge-muted" in content


def test_cron_page_supports_editing_and_high_z_agent_selects_without_new_job_card() -> None:
    content = CRON_PAGE_TSX.read_text(encoding="utf-8")

    assert "cron-edit-button" in content
    assert "cron-edit-panel" in content
    assert "cron-agent-select" in content
    assert "api.updateCronJob(job.id" in content
    assert "Scheduler Studio" not in content
    assert "New Cron Job" not in content


def test_cron_page_uses_emoji_pills_and_timeline_dots() -> None:
    content = CRON_PAGE_TSX.read_text(encoding="utf-8")

    assert "emoji:" in content
    assert "cron-timeline-dot" in content
    assert "entry.theme.emoji" in content


def test_cron_page_has_schedule_builder_controls_for_human_editing() -> None:
    content = CRON_PAGE_TSX.read_text(encoding="utf-8")

    assert "cron-schedule-builder" in content
    assert "parseScheduleBuilderState" in content
    assert "applyScheduleBuilder" in content
    assert "expandScheduleBuilderForPattern" in content
    assert "Run pattern" in content
    assert "First run" in content
    assert "Second run" in content
