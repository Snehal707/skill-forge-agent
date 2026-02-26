"""Top-level package for the Skill Forge agent.

Skill Forge is an autonomous agent built on top of Hermes Agent that
researches new domains, writes SKILL.md files, validates them in a
sandboxed environment, and saves them into the Hermes skills library.

High-level data flow (see AGENTS.md for full details):
- Research domain → write SKILL.md → validate procedure in Docker
- Persist skills and events to Supabase for the live dashboard
- Notify the user via Telegram at each key step
"""

from __future__ import annotations

from dataclasses import dataclass

from .researcher import ResearchBundle
from .validator import ValidationResult
from .writer import SkillDraft


__all__ = [
    "ResearchBundle",
    "SkillDraft",
    "ValidationResult",
]

