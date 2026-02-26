#!/usr/bin/env python3
"""Fix frontmatter name to match directory for all skills (agentskills.io spec)."""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from forge.skill_manager import _parse_frontmatter

def main():
    skills_dir = os.environ.get("SKILLS_DIR") or os.path.expanduser("~/.hermes/skills")
    root = Path(skills_dir).expanduser()
    fixed = 0
    for skill_md in root.rglob("SKILL.md"):
        if "/.git/" in str(skill_md) or "\\.git\\" in str(skill_md):
            continue
        dir_name = skill_md.parent.name
        meta = _parse_frontmatter(skill_md)
        fm_name = meta.get("name")
        if fm_name and fm_name != dir_name:
            content = skill_md.read_text(encoding="utf-8")
            lines = content.splitlines()
            if lines and lines[0].strip() == "---":
                for i in range(1, len(lines)):
                    if lines[i].strip() == "---":
                        new_lines = []
                        for j in range(1, i):
                            line = lines[j]
                            if re.match(r"^\s*name\s*:", line):
                                indent = line[: len(line) - len(line.lstrip())]
                                new_lines.append(f"{indent}name: {dir_name}")
                            else:
                                new_lines.append(line)
                        new_content = "\n".join(lines[:1] + new_lines + lines[i:])
                        skill_md.write_text(new_content, encoding="utf-8")
                        print(f"Fixed: {dir_name} (was {fm_name})")
                        fixed += 1
                        break
    print(f"Fixed {fixed} skills")
    return 0

if __name__ == "__main__":
    sys.exit(main())
