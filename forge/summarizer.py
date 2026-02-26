"""Summarizer module for Skill Forge.

Builds daily summary reports of skills learned, failures, and overall
statistics, and sends them via the notifier.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict

from loguru import logger

from .db import get_client, get_stats
from .notifier import send_daily_summary


def _today_start_iso() -> str:
    """Return the current day's UTC start timestamp in ISO format."""
    return datetime.now(timezone.utc).date().isoformat() + "T00:00:00Z"


def build_daily_summary_payload() -> Dict[str, Any]:
    """Build the payload expected by notifier.send_daily_summary."""
    stats = get_stats()
    total = stats.get("total", 0)

    try:
        client = get_client()
        today_start = _today_start_iso()
        resp = (
            client.table("skills")
            .select("name, description, domain, validation_passed, created_at")
            .gte("created_at", today_start)
            .execute()
        )
        rows = getattr(resp, "data", []) or []
    except Exception:
        logger.exception("Failed to fetch skills for daily summary.")
        rows = []

    learned_rows = [r for r in rows if r.get("validation_passed")]
    failed_rows = [r for r in rows if not r.get("validation_passed")]

    def _fmt_row(row: Dict[str, Any]) -> str:
        name = row.get("name", "<unknown>")
        domain = row.get("domain", "")
        desc = row.get("description") or ""
        parts = [name]
        if domain:
            parts.append(f"({domain})")
        if desc:
            parts.append(f"– {desc}")
        return " ".join(parts)

    learned_list = "\n".join(f"- {_fmt_row(r)}" for r in learned_rows) or "None"
    failed_list = "\n".join(f"- {_fmt_row(r)}" for r in failed_rows) or "None"

    dashboard_url = os.environ.get("DASHBOARD_URL", "")

    payload: Dict[str, Any] = {
        "learned": len(learned_rows),
        "failed": len(failed_rows),
        "total": total,
        "learned_list": learned_list,
        "failed_list": failed_list,
        "dashboard_url": dashboard_url,
    }
    return payload


def run_daily_summary() -> None:
    """Build and send the daily summary notification."""
    payload = build_daily_summary_payload()
    logger.info(
        "Sending daily summary: learned={learned}, failed={failed}, total={total}",
        **{
            "learned": payload.get("learned", 0),
            "failed": payload.get("failed", 0),
            "total": payload.get("total", 0),
        },
    )
    send_daily_summary(payload)

