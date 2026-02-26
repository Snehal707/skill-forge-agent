#!/usr/bin/env python3
"""Sync skills from Supabase to local Hermes skills directory.

Queries all skills from Supabase, compares with local SKILL.md files,
and writes any missing skills to disk. Uses the `name` from SKILL.md
frontmatter for the directory (agentskills.io spec).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from yaml import safe_load

load_dotenv()

from forge import db
from forge.skill_manager import _unwrap_code_fence, _sanitize_frontmatter


def _name_from_content(content: str) -> str | None:
    """Extract frontmatter `name` from SKILL.md content."""
    lines = content.strip().splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            try:
                fm = safe_load("\n".join(lines[1:i])) or {}
                return fm.get("name") if isinstance(fm.get("name"), str) else None
            except Exception:
                return None
    return None


def _set_frontmatter_name(content: str, target_name: str) -> str:
    """Ensure frontmatter `name` matches target_name (agentskills.io spec)."""
    lines = content.strip().splitlines()
    if not lines or lines[0].strip() != "---":
        return content
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            # Replace name: ... with name: target_name
            new_fm_lines = []
            for j in range(1, i):
                line = lines[j]
                if re.match(r"^\s*name\s*:", line):
                    indent = line[: len(line) - len(line.lstrip())]
                    new_fm_lines.append(f"{indent}name: {target_name}")
                else:
                    new_fm_lines.append(line)
            return "\n".join(lines[:1] + new_fm_lines + lines[i:])
    return content


def main() -> int:
    skills_dir = os.environ.get("SKILLS_DIR") or os.path.expanduser("~/.hermes/skills")
    root = Path(skills_dir).expanduser()

    print("Querying Supabase for all skills...")
    client = db.get_client()
    resp = client.table("skills").select("id, name, content, created_at").order("created_at", desc=True).execute()
    supabase_rows = resp.data or []
    print(f"Found {len(supabase_rows)} skills in Supabase")

    # Get local skill names (directory names)
    local_names = {p.parent.name for p in root.rglob("SKILL.md")}
    print(f"Found {len(local_names)} skills on disk")

    # Build map: skill_name -> (content, created_at). Prefer latest by created_at.
    by_name: dict[str, tuple[str, str]] = {}
    for row in supabase_rows:
        content = row.get("content")
        if not content:
            continue
        name = _name_from_content(content) or row.get("name")
        if not name or not name.strip():
            continue
        name = name.strip()
        created = row.get("created_at", "")
        if name not in by_name or (created and by_name[name][1] < created):
            by_name[name] = (content, created)

    missing = [(n, c) for n, (c, _) in by_name.items() if n not in local_names]
    print(f"Missing on disk: {len(missing)} skills")
    if missing:
        print("Missing skill names:", sorted(n for n, _ in missing))

    if not missing:
        print("All Supabase skills are already on disk.")
        return 0

    for name, content in missing:
        skill_dir = root / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        content = _unwrap_code_fence(content)
        content = _sanitize_frontmatter(content)
        content = _set_frontmatter_name(content, name)  # Ensure name matches directory
        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text(content, encoding="utf-8")
        print(f"  Written: {skill_path}")

    print(f"\nWrote {len(missing)} missing skills to {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
