"""Health check utilities for Skill Forge.

Verifies environment configuration and connectivity to external services:
- Required environment variables
- Docker availability
- Supabase connectivity
- Firecrawl API key
"""

from __future__ import annotations

import os
import subprocess
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from loguru import logger
from rich.console import Console
from rich.table import Table

from .db import get_client


console = Console()


def _check_env_vars() -> Tuple[bool, List[str]]:
  """Check that all required environment variables are present."""
  required = [
      "OPENROUTER_API_KEY",
      "FIRECRAWL_API_KEY",
      "TELEGRAM_BOT_TOKEN",
      "TELEGRAM_CHAT_ID",
      "SUPABASE_URL",
      "SUPABASE_SERVICE_KEY",
      "SKILLS_DIR",
      "DASHBOARD_URL",
  ]
  missing = [name for name in required if not os.environ.get(name)]
  return len(missing) == 0, missing


def _check_docker() -> Tuple[bool, str]:
  """Check that Docker CLI is available and responsive."""
  try:
      completed = subprocess.run(
          ["docker", "version", "--format", "{{.Server.Version}}"],
          capture_output=True,
          text=True,
          timeout=10,
          check=False,
      )
  except FileNotFoundError:
      return False, "docker executable not found on PATH."
  except subprocess.TimeoutExpired:
      return False, "docker version command timed out."
  except Exception as exc:  # noqa: BLE001
      return False, f"unexpected error invoking docker: {exc!r}"

  if completed.returncode != 0:
      return False, f"docker exited with code {completed.returncode}: {completed.stderr.strip()}"

  version = completed.stdout.strip() or "<unknown>"
  return True, f"Docker server version {version}"


def _check_supabase() -> Tuple[bool, str]:
  """Check that Supabase client can be created and basic query works."""
  try:
      client = get_client()
      resp = client.table("skills").select("id").limit(1).execute()
      _ = getattr(resp, "data", [])
      return True, "Supabase connection OK."
  except Exception as exc:  # noqa: BLE001
      logger.exception("Supabase health check failed.")
      return False, f"Supabase error: {exc!r}"


def _check_firecrawl() -> Tuple[bool, str]:
  """Check that Firecrawl API key is present and client can be constructed."""
  api_key = os.environ.get("FIRECRAWL_API_KEY")
  if not api_key:
      return False, "FIRECRAWL_API_KEY not set."

  try:
      # Constructing the client validates the key format; we avoid a full network call.
      _ = FirecrawlApp(api_key=api_key)
  except Exception as exc:  # noqa: BLE001
      logger.exception("Firecrawl health check failed.")
      return False, f"Firecrawl error: {exc!r}"

  return True, "Firecrawl client constructed successfully."


def run_health_check() -> Dict[str, Dict[str, str]]:
  """Run all health checks and return structured results."""
  results: Dict[str, Dict[str, str]] = {}

  env_ok, missing = _check_env_vars()
  results["env"] = {
      "status": "ok" if env_ok else "error",
      "details": "All required env vars present."
      if env_ok
      else f"Missing env vars: {', '.join(missing)}",
  }

  docker_ok, docker_details = _check_docker()
  results["docker"] = {
      "status": "ok" if docker_ok else "error",
      "details": docker_details,
  }

  supabase_ok, supabase_details = _check_supabase()
  results["supabase"] = {
      "status": "ok" if supabase_ok else "error",
      "details": supabase_details,
  }

  firecrawl_ok, firecrawl_details = _check_firecrawl()
  results["firecrawl"] = {
      "status": "ok" if firecrawl_ok else "error",
      "details": firecrawl_details,
  }

  return results


def main() -> int:
  """CLI entry point for health checks."""
  load_dotenv()
  results = run_health_check()

  table = Table(title="Skill Forge Health Check", show_header=True, header_style="bold magenta")
  table.add_column("Component")
  table.add_column("Status")
  table.add_column("Details")

  overall_ok = True
  for name, info in results.items():
      status = info.get("status", "error")
      details = info.get("details", "")
      overall_ok = overall_ok and status == "ok"
      color = "green" if status == "ok" else "red"
      table.add_row(name, f"[{color}]{status}[/{color}]", details)

  console.print(table)
  return 0 if overall_ok else 1


if __name__ == "__main__":
  raise SystemExit(main())

