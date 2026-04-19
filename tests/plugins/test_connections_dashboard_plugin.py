import importlib.util
from pathlib import Path

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient


@pytest.fixture()
def connections_module():
    plugin_path = (
        Path(__file__).resolve().parents[2]
        / "plugins"
        / "example-dashboard"
        / "dashboard"
        / "plugin_api.py"
    )
    spec = importlib.util.spec_from_file_location("connections_plugin_api", plugin_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def client(connections_module):
    app = FastAPI()
    app.include_router(connections_module.router, prefix="/api/plugins/connections")
    return TestClient(app)


def test_github_status_without_token(client, connections_module, monkeypatch):
    monkeypatch.setattr(
        connections_module,
        "_current_repo_info",
        lambda: {"branch": "lead-hunter-custom", "origin_repo": {"full_name": "faustogenga/hermes-agent"}},
    )
    monkeypatch.setattr(connections_module, "_find_github_token", lambda: (None, None))

    resp = client.get("/api/plugins/connections/github/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is False
    assert data["recommended_env_var"] == "GITHUB_TOKEN"
    assert data["instructions"]["token_url"].startswith("https://github.com/settings/personal-access-tokens")


def test_github_status_with_snapshot(client, connections_module, monkeypatch):
    monkeypatch.setattr(
        connections_module,
        "_current_repo_info",
        lambda: {
            "branch": "lead-hunter-custom",
            "origin_repo": {
                "owner": "faustogenga",
                "repo": "hermes-agent",
                "full_name": "faustogenga/hermes-agent",
                "url": "https://github.com/faustogenga/hermes-agent",
            },
        },
    )
    monkeypatch.setattr(connections_module, "_find_github_token", lambda: ("GITHUB_TOKEN", "github_pat_test123"))

    async def fake_snapshot(token, repo_info):
        assert token == "github_pat_test123"
        assert repo_info["origin_repo"]["full_name"] == "faustogenga/hermes-agent"
        return {
            "user": {
                "login": "faustogenga",
                "name": "Fausto",
                "html_url": "https://github.com/faustogenga",
                "avatar_url": "https://avatars.githubusercontent.com/u/1?v=4",
            },
            "scopes": [],
            "rate_limit_remaining": "4999",
            "repo_preview": [
                {
                    "full_name": "faustogenga/hermes-agent",
                    "private": False,
                    "html_url": "https://github.com/faustogenga/hermes-agent",
                    "permissions": {"admin": True, "push": True, "pull": True},
                }
            ],
            "current_repo_access": {
                "accessible": True,
                "full_name": "faustogenga/hermes-agent",
                "private": False,
                "permissions": {"admin": True, "push": True, "pull": True},
                "html_url": "https://github.com/faustogenga/hermes-agent",
            },
        }

    monkeypatch.setattr(connections_module, "_fetch_github_snapshot", fake_snapshot)

    resp = client.get("/api/plugins/connections/github/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is True
    assert data["token_source"] == "GITHUB_TOKEN"
    assert data["token_prefix"] == "github_pat_"
    assert data["user"]["login"] == "faustogenga"
    assert data["current_repo_access"]["permissions"]["push"] is True
    assert data["repo_preview"][0]["full_name"] == "faustogenga/hermes-agent"
