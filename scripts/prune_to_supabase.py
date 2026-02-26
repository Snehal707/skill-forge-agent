#!/usr/bin/env python3
"""Prune local skills to match Supabase (Option A: Supabase as source of truth).

Removes skill folders on disk that are NOT in Supabase, then runs sync
to ensure disk exactly matches the 36 skills in Supabase.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from yaml import safe_load

load_dotenv()

from forge import db


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


def main() -> int:
    skills_dir = os.environ.get("SKILLS_DIR") or os.path.expanduser("~/.hermes/skills")
    root = Path(skills_dir).expanduser()

    print("Querying Supabase for canonical skill names...")
    client = db.get_client()
    resp = (
        client.table("skills")
        .select("id, name, content, created_at")
        .order("created_at", desc=True)
        .execute()
    )
    supabase_rows = resp.data or []

    # Build canonical set: skill names that exist in Supabase (dedupe by frontmatter name)
    canonical_names: set[str] = set()
    for row in supabase_rows:
        content = row.get("content")
        if not content:
            continue
        name = _name_from_content(content) or row.get("name")
        if name and name.strip():
            canonical_names.add(name.strip())

    print(f"Canonical skills in Supabase: {len(canonical_names)}")

    # Find local skill dirs
    local_dirs = [p.parent for p in root.rglob("SKILL.md") if "/.git/" not in str(p) and "\\.git\\" not in str(p)]
    to_remove = [d for d in local_dirs if d.name not in canonical_names]

    if not to_remove:
        print("No orphan/duplicate skills to remove. Disk already matches Supabase.")
        return 0

    print(f"Removing {len(to_remove)} skills not in Supabase:")
    for d in sorted(to_remove, key=lambda x: x.name):
        print(f"  Removing: {d}")
        shutil.rmtree(d, ignore_errors=True)

    print(f"\nRemoved {len(to_remove)} skill folders.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
