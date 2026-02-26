"""Writer module for Skill Forge.

Takes research artifacts and produces a SKILL.md document using the LLM
helper in ``forge.llm``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from loguru import logger

from .llm import DEFAULT_MODEL, llm_call
from .researcher import ResearchBundle


@dataclass
class SkillDraft:
    """Intermediate SKILL.md draft produced by the writer."""

    name: str
    domain: str
    content: str
    metadata: Dict[str, Any]


def _load_writer_system_prompt() -> str:
    """Load the writer system prompt from prompts/writer_prompt.txt."""
    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "writer_prompt.txt"
    try:
        return prompt_path.read_text(encoding="utf-8")
    except Exception:
        logger.exception("Failed to read writer prompt at %s", prompt_path)
        return (
            "You are Skill Forge's writer agent. "
            "Given research notes and sources, produce a SKILL.md file "
            "that follows the required format with YAML frontmatter."
        )


def write_skill(research: ResearchBundle, model: str | None = None) -> SkillDraft:
    """Generate a SKILL.md draft from a ResearchBundle using the LLM."""
    system_prompt = _load_writer_system_prompt()

    sources_block = "\n".join(f"- {src}" for src in research.sources) or "None collected."
    user_prompt = (
        f"Domain: {research.domain}\n\n"
        f"Sources:\n{sources_block}\n\n"
        "Research notes (markdown):\n"
        f"{research.notes}\n\n"
        "Using the research above, write a complete SKILL.md."
    )

    try:
        content = llm_call(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            model=model or DEFAULT_MODEL,
        )
    except Exception:
        logger.exception("LLM call failed while writing SKILL.md for domain: %s", research.domain)
        raise

    metadata: Dict[str, Any] = {}
    # Best-effort extraction of basic fields from YAML frontmatter if present.
    try:
        from yaml import safe_load  # imported lazily to avoid hard dependency at import time

        lines = content.splitlines()
        if lines and lines[0].strip() == "---":
            for idx in range(1, len(lines)):
                if lines[idx].strip() == "---":
                    frontmatter = "\n".join(lines[1:idx])
                    metadata = safe_load(frontmatter) or {}
                    break
    except Exception:
        logger.exception("Failed to parse YAML frontmatter from SKILL.md draft.")

    name = str(metadata.get("name") or research.domain.replace(" ", "-").lower())
    domain = str(
        metadata.get("metadata", {})
        .get("skill_forge", {})
        .get("domain", research.domain)
    )

    draft = SkillDraft(
        name=name,
        domain=domain,
        content=content,
        metadata=metadata,
    )
    logger.info(
        "Generated SkillDraft for domain '%s' with name '%s'", research.domain, draft.name
    )
    return draft

