"""Skill Forge command-line interface.

Entry point for orchestrating the autonomous agent: learning new skills,
reporting status, and producing summaries.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any, Dict, List

import schedule
from dotenv import load_dotenv
from loguru import logger
from rich.console import Console
from rich.table import Table

from forge import db
from forge.notifier import notify
from forge.publisher import publish_skill
from forge.researcher import research_domain
from forge.skill_manager import save_skill
from forge.summarizer import run_daily_summary
from forge.validator import validate_skill
from forge.writer import write_skill


console = Console()


def _configure_logging() -> None:
    """Configure basic loguru logging."""
    load_dotenv()
    logger.remove()
    logger.add(sys.stderr, level="INFO")


def _learn_domain(domain: str) -> None:
    """Run the full learn pipeline for a single domain."""
    console.print(
        f"[bold green]Skill Forge[/bold green] learning domain: [cyan]{domain}[/cyan]"
    )
    logger.info("Starting learn pipeline for domain: {domain}", domain=domain)

    # Research
    db.insert_event("research_start", domain=domain, message="Starting research")
    notify("research_start", domain=domain)
    research = research_domain(domain)
    db.insert_event(
        "research_done",
        domain=domain,
        message=f"Collected {len(research.sources)} sources",
        metadata={"sources": research.sources, "sources_count": len(research.sources)},
    )
    notify("research_done", domain=domain, source_count=len(research.sources))

    # Write SKILL.md
    db.insert_event("writing", domain=domain, message="Writing SKILL.md")
    notify("writing", skill_name=domain)
    draft = write_skill(research)

    # Validate
    attempts = 0
    max_attempts = 3
    validation_passed = False
    last_details = ""

    while attempts < max_attempts and not validation_passed:
        attempts += 1
        db.insert_event(
            "validating",
            domain=domain,
            skill_name=draft.name,
            message=f"Validation attempt {attempts}",
        )
        notify("validating", skill_name=draft.name)
        result = validate_skill(draft.name, draft.content)
        validation_passed = result.passed
        last_details = result.details

        if result.passed:
            db.insert_event(
                "validated_ok",
                domain=domain,
                skill_name=draft.name,
                message="Validation succeeded",
                metadata={"attempts": attempts, "details": result.details},
            )
            notify(
                "validated_ok",
                skill_name=draft.name,
                description=draft.metadata.get("description", ""),
                steps_tested=attempts,
            )
        else:
            db.insert_event(
                "validated_fail",
                domain=domain,
                skill_name=draft.name,
                message="Validation failed",
                metadata={"attempts": attempts, "details": result.details},
            )
            notify("validated_fail", skill_name=draft.name, attempt=attempts)

    # Save skill regardless of validation outcome; the dashboard shows status.
    try:
        skill_path = save_skill(draft)
    except Exception:
        logger.exception("Failed to save SKILL.md for domain: {domain}", domain=domain)
        db.insert_event(
            "error",
            domain=domain,
            skill_name=draft.name,
            message="Failed to save SKILL.md",
        )
        raise

    # Persist to Supabase skills table.
    category = (
        draft.metadata.get("metadata", {})
        .get("hermes", {})
        .get("category", "uncategorized")
    )
    description = draft.metadata.get("description", "")
    db.insert_skill(
        name=draft.name,
        domain=domain,
        category=category,
        description=description,
        content=draft.content,
        validation_passed=validation_passed,
        sources_count=len(research.sources),
        attempts=attempts,
    )

    # Publish to GitHub skills repo (if GITHUB_TOKEN + GITHUB_SKILLS_REPO are set).
    github_url = publish_skill(draft.name, draft.content)
    skill_public_url = github_url or os.environ.get("DASHBOARD_URL", "")

    db.insert_event(
        "saved",
        domain=domain,
        skill_name=draft.name,
        message=f"Saved SKILL.md at {skill_path}",
        metadata={"github_url": github_url or ""},
    )
    notify("saved", skill_name=draft.name, dashboard_url=skill_public_url)

    console.print(
        f"[bold green]Done[/bold green] learning [cyan]{domain}[/cyan] "
        f"(validated={validation_passed}, attempts={attempts})."
    )
    logger.info(
        "Finished learn pipeline for domain: {domain} (validated=%s, attempts=%s, details=%s)",
        validation_passed,
        attempts,
        last_details,
        domain=domain,
    )


def cmd_learn(args: argparse.Namespace) -> int:
    """Handle the `learn` command."""
    try:
        _learn_domain(args.domain)
        return 0
    except Exception:
        logger.exception("Learn command failed for domain: {domain}", domain=args.domain)
        console.print(
            f"[red]Learn pipeline failed for domain: [cyan]{args.domain}[/cyan]. "
            "See logs for details.[/red]"
        )
        return 1


def _load_domains_from_config() -> List[str]:
    """Load default domains for learn-all from config/forge_config.yaml if present."""
    from pathlib import Path

    import yaml

    config_path = Path("config") / "forge_config.yaml"
    if not config_path.exists():
        return []

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        logger.exception("Failed to read forge_config.yaml for learn-all.")
        return []

    domains = data.get("domains") or []
    return [str(d) for d in domains if isinstance(d, str) and d.strip()]


def cmd_learn_all(_args: argparse.Namespace) -> int:
    """Handle the `learn-all` command."""
    domains = _load_domains_from_config()
    if not domains:
        console.print(
            "[yellow]No domains configured in config/forge_config.yaml under 'domains'.[/yellow]"
        )
        return 0

    console.print(
        "[bold]Running learn pipeline for configured domains:[/bold] "
        + ", ".join(f"[cyan]{d}[/cyan]" for d in domains)
    )
    for domain in domains:
        try:
            _learn_domain(domain)
        except Exception:
            logger.exception("learn-all: failed for domain: {domain}", domain=domain)
            continue
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    """Handle the `status` command."""
    console.print("[bold]Fetching Skill Forge status from Supabase…[/bold]")
    try:
        stats: Dict[str, Any] = db.get_stats()
    except Exception:
        logger.exception("Status command failed while fetching stats.")
        console.print(
            "[red]Unable to fetch stats. Check Supabase configuration and connectivity.[/red]"
        )
        return 1

    table = Table(title="Skill Forge Status", show_header=True, header_style="bold magenta")
    table.add_column("Metric")
    table.add_column("Value")

    table.add_row("Total Skills Learned", str(stats.get("total", 0)))
    table.add_row("Skills Today", str(stats.get("today_count", 0)))
    table.add_row(
        "Validation Success Rate (%)",
        f"{stats.get('success_rate', 0.0):.2f}",
    )
    table.add_row("Domains Covered", str(len(stats.get("domains", []))))

    console.print(table)
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    """Handle the `summary` command."""
    if args.daemon:
        console.print(
            "[bold]Starting daily summary daemon.[/bold] "
            "Press Ctrl+C to stop."
        )
        schedule.every().day.at("09:00").do(run_daily_summary)
        while True:
            schedule.run_pending()
            time.sleep(1)
    else:
        console.print("[bold]Running daily summary once…[/bold]")
        run_daily_summary()
    return 0


def cmd_to_prompt(args: argparse.Namespace) -> int:
    """Handle the `to-prompt` command — generate <available_skills> XML."""
    from forge.skill_manager import _skills_root
    try:
        import skills_ref
    except ImportError:
        console.print("[red]skills-ref is not installed. Run: pip install git+https://github.com/agentskills/agentskills.git#subdirectory=skills-ref --ignore-requires-python[/red]")
        return 1

    root = _skills_root()
    skill_dirs = [p.parent for p in root.rglob("SKILL.md")]

    if not skill_dirs:
        console.print("[yellow]No skills found in skills directory.[/yellow]")
        return 0

    xml = skills_ref.to_prompt(skill_dirs)

    if args.output:
        from pathlib import Path
        Path(args.output).write_text(xml, encoding="utf-8")
        console.print(f"[green]Wrote <available_skills> XML to {args.output}[/green]")
    else:
        console.print(xml)

    console.print(f"\n[dim]{len(skill_dirs)} skills included.[/dim]")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build and return the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="skill_forge",
        description="Skill Forge — autonomous skill-learning agent on top of Hermes.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # learn
    learn_parser = subparsers.add_parser(
        "learn",
        help="Learn a single domain (research → write SKILL.md → validate → save).",
    )
    learn_parser.add_argument("domain", help="Domain to learn, e.g. 'docker' or 'kubernetes'.")
    learn_parser.set_defaults(func=cmd_learn)

    # learn-all
    learn_all_parser = subparsers.add_parser(
        "learn-all",
        help="Learn all configured domains (stub, not yet implemented).",
    )
    learn_all_parser.set_defaults(func=cmd_learn_all)

    # status
    status_parser = subparsers.add_parser(
        "status",
        help="Show aggregate statistics about learned skills from Supabase.",
    )
    status_parser.set_defaults(func=cmd_status)

    # summary
    summary_parser = subparsers.add_parser(
        "summary",
        help="Generate a daily summary report, or run as a daily daemon.",
    )
    summary_parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run the daily summary on a schedule using the schedule library.",
    )
    summary_parser.set_defaults(func=cmd_summary)

    # to-prompt
    to_prompt_parser = subparsers.add_parser(
        "to-prompt",
        help="Generate <available_skills> XML for injecting into agent prompts.",
    )
    to_prompt_parser.add_argument(
        "--output",
        default=None,
        help="Write XML to this file instead of stdout.",
    )
    to_prompt_parser.set_defaults(func=cmd_to_prompt)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the Skill Forge CLI."""
    _configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 1
    return int(func(args))


if __name__ == "__main__":
    raise SystemExit(main())

