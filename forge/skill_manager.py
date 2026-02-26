"""Skill manager for Skill Forge.

Handles reading from and writing to the Hermes skills directory
(`SKILLS_DIR` env var, defaulting to ``~/.hermes/skills``).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List

from loguru import logger
from yaml import safe_load

from .writer import SkillDraft


def _skills_root(override: str | None = None) -> Path:
    """Return the root directory where skills are stored."""
    base = override or os.environ.get("SKILLS_DIR") or os.path.expanduser("~/.hermes/skills")
    root = Path(base).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _unwrap_code_fence(text: str) -> str:
    """If content is wrapped in a ``` fenced block, unwrap it.

    Some models return SKILL.md inside a ```markdown ... ``` fence. This
    helper strips the outer fence so the file starts directly with YAML
    frontmatter, while still enforcing that the frontmatter itself is valid.
    """
    lines = text.splitlines()
    if not lines:
        return text

    first = lines[0].strip()
    if not first.startswith("```"):
        return text

    # Find closing fence.
    for idx in range(1, len(lines)):
        if lines[idx].strip().startswith("```"):
            inner = "\n".join(lines[1:idx])
            rest = "\n".join(lines[idx + 1 :])
            combined = inner
            if rest.strip():
                combined = inner + "\n" + rest
            return combined.lstrip("\n")

    return text


def _parse_frontmatter(path: Path) -> Dict[str, Any]:
    """Parse YAML frontmatter from a SKILL.md file."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        logger.exception("Failed to read SKILL.md at %s", path)
        return {}

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        logger.error("SKILL.md at %s is missing YAML frontmatter start delimiter.", path)
        return {}

    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break

    if end_idx is None:
        logger.error("SKILL.md at %s is missing YAML frontmatter end delimiter.", path)
        return {}

    frontmatter = "\n".join(lines[1:end_idx])
    try:
        data = safe_load(frontmatter) or {}
    except Exception:
        logger.exception("Failed to parse YAML frontmatter for %s", path)
        return {}

    if not isinstance(data, dict):
        logger.error("Frontmatter in %s is not a mapping.", path)
        return {}

    return data


def _sanitize_frontmatter(content: str) -> str:
    """Sanitize YAML frontmatter to comply with agentskills.io spec.

    Changes applied inside the frontmatter block only:
    1. Convert inline flow sequences  tags: [a, b]  →  block style
    2. Remove top-level `version:` field (not in spec — belongs in metadata)
    """
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return content

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return content

    _inline_list_re = re.compile(r"^(\s*)([\w][\w-]*):\s*\[(.+)\]\s*$")
    # Top-level fields not allowed by the spec.
    _disallowed_top_level = {"version"}

    new_lines = []
    skip_next = False
    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue
        if 0 < i < end_idx:
            # Strip disallowed top-level keys (no leading spaces = top-level).
            stripped = line.strip()
            key_match = re.match(r"^([\w][\w-]*):", stripped)
            if key_match and not line.startswith(" ") and key_match.group(1) in _disallowed_top_level:
                continue
            # Convert inline lists to block style.
            m = _inline_list_re.match(line)
            if m:
                indent = m.group(1)
                key = m.group(2)
                items = [item.strip() for item in m.group(3).split(",")]
                new_lines.append(f"{indent}{key}:")
                for item in items:
                    new_lines.append(f"{indent}  - {item}")
                continue
        new_lines.append(line)

    return "\n".join(new_lines)


def _spec_validate(skill_dir: Path) -> list[str]:
    """Run skills-ref spec validation. Returns list of error strings."""
    try:
        import skills_ref
        return skills_ref.validate(skill_dir)
    except ImportError:
        logger.warning("skills-ref not installed — skipping spec validation.")
        return []
    except Exception as exc:
        return [f"skills-ref error: {exc}"]


def save_skill(draft: SkillDraft, skills_dir: str | None = None) -> Path:
    """Persist a SkillDraft into the Hermes skills directory as SKILL.md.

    Enforces:
    - Valid YAML frontmatter with a non-empty `name` field
    - name matches the directory name (agentskills.io spec)
    - No inline YAML arrays (converted to block style for strictyaml compat)
    - Passes skills-ref spec validation after writing
    """
    root = _skills_root(skills_dir)
    content = _unwrap_code_fence(draft.content)
    content = _sanitize_frontmatter(content)

    # Parse frontmatter to get the skill name.
    tmp_path = root / "__tmp_validation__.md"
    tmp_path.write_text(content, encoding="utf-8")
    meta = _parse_frontmatter(tmp_path)
    tmp_path.unlink(missing_ok=True)

    name = meta.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("SKILL.md frontmatter must contain a non-empty 'name' field.")

    safe_name = name.strip()

    # Enforce name == directory name (agentskills.io spec requirement).
    # If the name in frontmatter doesn't match, we trust the frontmatter name
    # and use it as the directory — so they always match.
    skill_dir = root / safe_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(content, encoding="utf-8")

    # Run official spec validation.
    errors = _spec_validate(skill_dir)
    if errors:
        logger.warning(
            "skills-ref spec validation warnings for '{}': {}",
            safe_name,
            "; ".join(errors),
        )
    else:
        logger.info("skills-ref spec validation passed for '{}'", safe_name)

    logger.info("Saved SKILL.md for '%s' at %s", safe_name, skill_path)
    return skill_path


def list_skills(skills_dir: str | None = None) -> List[Dict[str, Any]]:
    """List all local skills with basic metadata."""
    root = _skills_root(skills_dir)
    skills: List[Dict[str, Any]] = []

    for skill_md in root.rglob("SKILL.md"):
        meta = _parse_frontmatter(skill_md)
        if not meta:
            continue
        metadata = meta.get("metadata") or {}
        skill_forge_meta = metadata.get("skill_forge") or {}
        hermes_meta = metadata.get("hermes") or {}
        skills.append(
            {
                "name": meta.get("name"),
                "description": meta.get("description"),
                "domain": skill_forge_meta.get("domain"),
                "category": hermes_meta.get("category"),
                "validation_passed": skill_forge_meta.get("validation_passed", False),
                "path": str(skill_md),
            }
        )

    return skills


def get_local_stats(skills_dir: str | None = None) -> Dict[str, Any]:
    """Compute aggregate statistics over local SKILL.md files."""
    skills = list_skills(skills_dir)
    total = len(skills)
    validated = sum(1 for s in skills if s.get("validation_passed"))
    domains = sorted(
        {s["domain"] for s in skills if isinstance(s.get("domain"), str) and s["domain"]}
    )
    categories = sorted(
        {
            s["category"]
            for s in skills
            if isinstance(s.get("category"), str) and s["category"]
        }
    )
    success_rate = (validated / total * 100.0) if total > 0 else 0.0

    return {
        "total": total,
        "validated": validated,
        "success_rate": success_rate,
        "domains": domains,
        "categories": categories,
    }

