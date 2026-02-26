"""All Supabase database operations for Skill Forge.

Never import or use the Supabase client outside this module.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from loguru import logger
from supabase import Client, create_client


def get_client() -> Client:
    """Create and return a Supabase client using environment variables."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")

    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables are required."
        )

    return create_client(url, key)


def insert_event(
    event_type: str,
    domain: str = "",
    skill_name: str = "",
    message: str = "",
    metadata: Dict[str, Any] | None = None,
) -> None:
    """Insert an event into the Supabase `events` table."""
    payload: Dict[str, Any] = {
        "event_type": event_type,
        "domain": domain or None,
        "skill_name": skill_name or None,
        "message": message,
        "metadata": metadata or {},
    }

    try:
        client = get_client()
        client.table("events").insert(payload).execute()
        logger.info("Inserted event into Supabase: {event_type}", event_type=event_type)
    except Exception:
        # Log, but do not crash the whole agent on transient DB issues.
        logger.exception("Failed to insert event into Supabase.")


def insert_skill(
    name: str,
    domain: str,
    category: str,
    description: str,
    content: str,
    validation_passed: bool,
    sources_count: int,
    attempts: int,
) -> None:
    """Insert a learned skill into the Supabase `skills` table."""
    payload: Dict[str, Any] = {
        "name": name,
        "domain": domain,
        "category": category,
        "description": description,
        "content": content,
        "validation_passed": validation_passed,
        "sources_count": sources_count,
        "attempts": attempts,
    }

    try:
        client = get_client()
        client.table("skills").insert(payload).execute()
        logger.info("Inserted skill into Supabase: {name}", name=name)
    except Exception:
        logger.exception("Failed to insert skill into Supabase.")


def get_stats() -> Dict[str, Any]:
    """Return aggregate statistics about learned skills.

    Returns a dictionary with:
    - total: total number of skills
    - today_count: number of skills created today (UTC)
    - success_rate: percentage of skills with validation_passed = true
    - domains: list of distinct domains
    """
    try:
        client = get_client()
    except Exception:
        logger.exception("Failed to create Supabase client for get_stats().")
        return {
            "total": 0,
            "today_count": 0,
            "success_rate": 0.0,
            "domains": [],
        }

    total = 0
    today_count = 0
    success_count = 0
    domains: List[str] = []

    try:
        # Total skills
        total_resp = client.table("skills").select("id", count="exact").execute()
        total = getattr(total_resp, "count", None) or 0

        # Skills created today (UTC)
        today_start = datetime.now(timezone.utc).date().isoformat() + "T00:00:00Z"
        today_resp = (
            client.table("skills")
            .select("id", count="exact")
            .gte("created_at", today_start)
            .execute()
        )
        today_count = getattr(today_resp, "count", None) or 0

        # Validation success count
        success_resp = (
            client.table("skills")
            .select("id", count="exact")
            .eq("validation_passed", True)
            .execute()
        )
        success_count = getattr(success_resp, "count", None) or 0

        # Distinct domains (deduplicated client-side)
        domains_resp = client.table("skills").select("domain").execute()
        raw_domains = getattr(domains_resp, "data", []) or []
        domains = sorted({row.get("domain") for row in raw_domains if row.get("domain")})
    except Exception:
        logger.exception("Failed to compute stats from Supabase.")

    success_rate = 0.0
    if total > 0:
        success_rate = (success_count / total) * 100.0

    return {
        "total": int(total),
        "today_count": int(today_count),
        "success_rate": float(success_rate),
        "domains": domains,
    }

