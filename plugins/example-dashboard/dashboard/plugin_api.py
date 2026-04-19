"""Connections dashboard plugin — GitHub connection status + repo visibility.

Mounted at /api/plugins/connections/ by the dashboard plugin system.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter

router = APIRouter()

_GITHUB_TOKEN_KEYS = ("GITHUB_TOKEN", "GH_TOKEN", "COPILOT_GITHUB_TOKEN")
_GITHUB_API = "https://api.github.com"
_GITHUB_TIMEOUT = 10.0


def _detect_token_prefix(token: str) -> str:
    token = str(token or "")
    for prefix in ("github_pat_", "ghp_", "gho_", "ghu_", "ghs_", "ghr_"):
        if token.startswith(prefix):
            return prefix
    return "unknown"


def _find_github_token() -> tuple[Optional[str], Optional[str]]:
    for key in _GITHUB_TOKEN_KEYS:
        value = os.getenv(key, "").strip()
        if value:
            return key, value
    return None, None


def _run_git(*args: str) -> Optional[str]:
    repo_root = Path(__file__).resolve().parents[3]
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    output = (result.stdout or "").strip()
    return output or None


def _parse_github_repo(remote_url: Optional[str]) -> Optional[Dict[str, str]]:
    remote = str(remote_url or "").strip()
    if not remote:
        return None

    normalized = remote[:-4] if remote.endswith(".git") else remote
    if normalized.startswith("git@github.com:"):
        tail = normalized.split(":", 1)[1]
    elif normalized.startswith("ssh://git@github.com/"):
        tail = normalized.split("github.com/", 1)[1]
    else:
        parsed = urlparse(normalized)
        if parsed.netloc.lower() != "github.com":
            return None
        tail = parsed.path.lstrip("/")

    parts = [part for part in tail.split("/") if part]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1]
    return {
        "owner": owner,
        "repo": repo,
        "full_name": f"{owner}/{repo}",
        "url": f"https://github.com/{owner}/{repo}",
    }


def _current_repo_info() -> Dict[str, Any]:
    branch = _run_git("branch", "--show-current")
    origin_url = _run_git("remote", "get-url", "origin")
    upstream_url = _run_git("remote", "get-url", "upstream")
    origin_repo = _parse_github_repo(origin_url)
    upstream_repo = _parse_github_repo(upstream_url)
    return {
        "branch": branch,
        "origin_url": origin_url,
        "upstream_url": upstream_url,
        "origin_repo": origin_repo,
        "upstream_repo": upstream_repo,
    }


async def _github_get(client: httpx.AsyncClient, token: str, path: str, params: Optional[dict[str, Any]] = None) -> httpx.Response:
    return await client.get(
        f"{_GITHUB_API}{path}",
        params=params,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Hermes-Connections-Dashboard",
        },
    )


async def _fetch_github_snapshot(token: str, repo_info: Dict[str, Any]) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=_GITHUB_TIMEOUT) as client:
        user_resp = await _github_get(client, token, "/user")
        user_resp.raise_for_status()
        user_data = user_resp.json()

        repos_resp = await _github_get(
            client,
            token,
            "/user/repos",
            params={
                "per_page": 8,
                "sort": "updated",
                "affiliation": "owner,collaborator,organization_member",
            },
        )
        repos_resp.raise_for_status()
        repo_data = repos_resp.json()

        current_repo_access = None
        origin_repo = repo_info.get("origin_repo") or {}
        if origin_repo.get("owner") and origin_repo.get("repo"):
            current_repo_resp = await _github_get(
                client,
                token,
                f"/repos/{origin_repo['owner']}/{origin_repo['repo']}",
            )
            if current_repo_resp.status_code == 200:
                payload = current_repo_resp.json()
                permissions = payload.get("permissions") or {}
                current_repo_access = {
                    "accessible": True,
                    "full_name": payload.get("full_name") or origin_repo.get("full_name"),
                    "private": bool(payload.get("private")),
                    "permissions": {
                        "admin": bool(permissions.get("admin")),
                        "push": bool(permissions.get("push")),
                        "pull": bool(permissions.get("pull")),
                    },
                    "html_url": payload.get("html_url") or origin_repo.get("url"),
                }
            elif current_repo_resp.status_code in {403, 404}:
                current_repo_access = {
                    "accessible": False,
                    "full_name": origin_repo.get("full_name"),
                    "private": None,
                    "permissions": {
                        "admin": False,
                        "push": False,
                        "pull": False,
                    },
                    "html_url": origin_repo.get("url"),
                }

        scopes_raw = user_resp.headers.get("x-oauth-scopes", "")
        scopes = [scope.strip() for scope in scopes_raw.split(",") if scope.strip()]
        repo_preview = []
        for repo in repo_data:
            permissions = repo.get("permissions") or {}
            repo_preview.append(
                {
                    "full_name": repo.get("full_name"),
                    "private": bool(repo.get("private")),
                    "html_url": repo.get("html_url"),
                    "permissions": {
                        "admin": bool(permissions.get("admin")),
                        "push": bool(permissions.get("push")),
                        "pull": bool(permissions.get("pull")),
                    },
                }
            )

        return {
            "user": {
                "login": user_data.get("login"),
                "name": user_data.get("name"),
                "html_url": user_data.get("html_url"),
                "avatar_url": user_data.get("avatar_url"),
            },
            "scopes": scopes,
            "rate_limit_remaining": user_resp.headers.get("x-ratelimit-remaining"),
            "repo_preview": repo_preview,
            "current_repo_access": current_repo_access,
        }


@router.get("/github/status")
async def github_status() -> Dict[str, Any]:
    repo_info = _current_repo_info()
    token_source, token = _find_github_token()
    if not token:
        return {
            "connected": False,
            "token_source": None,
            "token_prefix": None,
            "recommended_env_var": "GITHUB_TOKEN",
            "repo": repo_info,
            "instructions": {
                "recommended": "Create a fine-grained GitHub personal access token limited to the repos Hermes should access.",
                "token_url": "https://github.com/settings/personal-access-tokens/new",
                "minimum_permissions": [
                    "Contents: Read and write",
                    "Metadata: Read-only",
                    "Pull requests: Read and write (recommended)",
                ],
            },
        }

    try:
        snapshot = await _fetch_github_snapshot(token, repo_info)
        return {
            "connected": True,
            "token_source": token_source,
            "token_prefix": _detect_token_prefix(token),
            "recommended_env_var": "GITHUB_TOKEN",
            "repo": repo_info,
            **snapshot,
        }
    except httpx.HTTPStatusError as exc:
        detail = None
        try:
            payload = exc.response.json()
            detail = payload.get("message")
        except Exception:
            detail = exc.response.text.strip() or None
        return {
            "connected": False,
            "token_source": token_source,
            "token_prefix": _detect_token_prefix(token),
            "recommended_env_var": "GITHUB_TOKEN",
            "repo": repo_info,
            "error": {
                "status_code": exc.response.status_code,
                "message": detail or "GitHub rejected the token",
            },
        }
    except Exception as exc:
        return {
            "connected": False,
            "token_source": token_source,
            "token_prefix": _detect_token_prefix(token),
            "recommended_env_var": "GITHUB_TOKEN",
            "repo": repo_info,
            "error": {
                "status_code": None,
                "message": str(exc),
            },
        }
