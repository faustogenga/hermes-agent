import importlib.util
from pathlib import Path


def _load_connections_module():
    plugin_path = (
        Path(__file__).resolve().parents[2]
        / "plugins"
        / "example-dashboard"
        / "dashboard"
        / "plugin_api.py"
    )
    spec = importlib.util.spec_from_file_location("connections_plugin_api_for_rescan", plugin_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_rescan_mounts_new_plugin_api(monkeypatch):
    import hermes_cli.web_server as web_server

    web_server._mounted_plugin_api_names.clear()

    connections_module = _load_connections_module()

    plugin = {
        "name": "connections",
        "_api_file": "plugin_api.py",
        "_dir": str(
            Path(__file__).resolve().parents[2]
            / "plugins"
            / "example-dashboard"
            / "dashboard"
        ),
    }

    monkeypatch.setattr(web_server, "_get_dashboard_plugins", lambda force_rescan=False: [plugin])

    web_server._mount_plugin_api_routes()

    paths = {route.path for route in web_server.app.routes}
    assert "/api/plugins/connections/github/status" in paths
    assert "connections" in web_server._mounted_plugin_api_names

    before = len(web_server.app.routes)
    web_server._mount_plugin_api_routes()
    after = len(web_server.app.routes)
    assert after == before
