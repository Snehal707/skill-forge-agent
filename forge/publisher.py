"""Publisher module for Skill Forge.

Publishes validated SKILL.md files to a public GitHub repository so other
Hermes agents can discover and install them.

Setup
-----
1. Create a public GitHub repo (e.g. ``your-username/hermes-skills``).
2. Generate a GitHub Personal Access Token with ``repo`` scope.
3. Add to .env:
       GITHUB_TOKEN=ghp_...
       GITHUB_SKILLS_REPO=your-username/hermes-skills

The publisher uses the GitHub Contents API — no git installation required.
Each skill is written to ``skills/<skill-name>/SKILL.md`` in the repo.
"""

from __future__ import annotations

import base64
import os
from typing import Optional

import requests
from loguru import logger


_GITHUB_API = "https://api.github.com"


def _get_credentials() -> tuple[str, str] | tuple[None, None]:
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_SKILLS_REPO")
    if not token or not repo:
        return None, None
    return token, repo


def _get_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get_existing_sha(token: str, repo: str, path: str) -> Optional[str]:
    """Return the blob SHA of an existing file, or None if it doesn't exist."""
    url = f"{_GITHUB_API}/repos/{repo}/contents/{path}"
    resp = requests.get(url, headers=_get_headers(token), timeout=15)
    if resp.status_code == 200:
        return resp.json().get("sha")
    return None


def publish_skill(skill_name: str, skill_content: str) -> Optional[str]:
    """Push a SKILL.md to the configured GitHub skills repo.

    Parameters
    ----------
    skill_name:
        The skill's name (used as the directory name in the repo).
    skill_content:
        Full text content of the SKILL.md file.

    Returns
    -------
    The public GitHub URL of the published skill, or None on failure.
    """
    token, repo = _get_credentials()
    if not token or not repo:
        logger.warning(
            "GITHUB_TOKEN or GITHUB_SKILLS_REPO not set — skipping publish."
        )
        return None

    path = f"skills/{skill_name}/SKILL.md"
    url = f"{_GITHUB_API}/repos/{repo}/contents/{path}"

    # Encode content as base64 (required by GitHub Contents API).
    encoded = base64.b64encode(skill_content.encode("utf-8")).decode("ascii")

    # Check if the file already exists so we can update rather than create.
    existing_sha = _get_existing_sha(token, repo, path)

    payload: dict = {
        "message": f"skill-forge: publish {skill_name}",
        "content": encoded,
    }
    if existing_sha:
        payload["sha"] = existing_sha
        action = "Updated"
    else:
        action = "Created"

    try:
        resp = requests.put(url, json=payload, headers=_get_headers(token), timeout=30)
        resp.raise_for_status()
    except requests.HTTPError as exc:
        logger.error(
            "GitHub publish failed for '{name}': {status} — {body}",
            name=skill_name,
            status=exc.response.status_code if exc.response else "?",
            body=exc.response.text[:300] if exc.response else str(exc),
        )
        return None
    except Exception as exc:
        logger.error("GitHub publish error for '{name}': {exc}", name=skill_name, exc=exc)
        return None

    public_url = f"https://github.com/{repo}/blob/main/{path}"
    logger.info("{action} skill '{name}' on GitHub: {url}", action=action, name=skill_name, url=public_url)
    return public_url
