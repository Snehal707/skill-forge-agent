"""Validator module for Skill Forge.

Executes SKILL.md procedures inside a Docker-based sandbox to ensure that
the skill works as described, without running commands directly on the host.

Strategy
--------
1. Ask the LLM to generate a minimal bash test script from the skill's
   ## Procedure section — skipping any steps that require external accounts,
   live servers, credentials, or network-dependent services.
2. Run the generated script inside a short-lived Docker container.
3. Capture stdout/stderr and exit code, report pass/fail with details.
"""

from __future__ import annotations

import re
import subprocess
import textwrap
from dataclasses import dataclass

from loguru import logger

from forge.llm import llm_call


@dataclass
class ValidationResult:
    """Result of executing a SKILL.md procedure inside a sandbox."""

    skill_name: str
    passed: bool
    attempts: int
    details: str


_VALIDATOR_SYSTEM_PROMPT = textwrap.dedent("""\
    You are a DevOps validation expert. Given a SKILL.md document, your job is to
    write a minimal bash script that validates the skill's core procedures can
    actually run inside a `python:3.11-slim` Docker container.

    CRITICAL — available tools in this container:
      Python 3.11, pip, bash, sh, mkdir, touch, cat, echo, curl, apt-get.
      There is NO: node, npm, tsc, java, ruby, go, rust, aws, kubectl, terraform,
      docker, or any cloud CLI. These are not installed and cannot be used.

    Rules:
    - Output ONLY a bash script — no markdown fences, no explanation, no comments
      except inline `# step N` markers.
    - Start with: #!/bin/bash\\nset -euo pipefail
    - Only include steps that are self-contained and runnable with available tools:
        * File/directory creation (mkdir, touch, cat, echo)
        * pip install packages, then python -c "import pkg" to verify
        * Python/shell one-liners that can run and exit cleanly
        * Syntax checks (python -m py_compile file.py)
        * Writing config/code files and verifying their content
    - SKIP any step that requires:
        * Node.js / npm / TypeScript compiler (tsc) — not available
        * External accounts, APIs, or credentials
        * A running server or open port
        * Browser or GUI interaction
        * Cloud provider CLI (aws, gcloud, az, kubectl, terraform) — not available
        * Docker-in-Docker
    - If the skill is about a non-Python tool (TypeScript, Kubernetes, AWS, etc.)
      focus ONLY on: installing any available Python clients (boto3, kubernetes-client,
      etc.), writing sample config/code files, and doing python syntax checks.
    - If truly NO steps are safely testable, output exactly:
        #!/bin/bash
        echo 'No testable steps in this environment'
        exit 0
    - Keep the script under 35 lines.
    - Each testable step must echo its result: echo 'step N: OK'
""")


def _generate_validation_script(skill_name: str, skill_markdown: str) -> str:
    """Ask the LLM to produce a bash validation script for this skill."""
    logger.info("Generating validation script for skill '%s' via LLM", skill_name)
    user_prompt = (
        f"Generate a bash validation script for the following SKILL.md.\n\n"
        f"{skill_markdown}"
    )
    script = llm_call(
        user_prompt=user_prompt,
        system_prompt=_VALIDATOR_SYSTEM_PROMPT,
    )
    # Strip accidental markdown fences the LLM might add despite instructions.
    script = re.sub(r"^```(?:bash|sh)?\s*\n?", "", script.strip(), flags=re.IGNORECASE)
    script = re.sub(r"\n?```\s*$", "", script.strip())
    return script.strip()


def _run_in_docker(
    script: str,
    docker_image: str,
    timeout_seconds: int,
) -> tuple[bool, str]:
    """Run a bash script inside a Docker container, return (passed, details)."""
    command = [
        "docker", "run", "--rm",
        "--network", "host",          # allow pip installs
        "--memory", "512m",
        "--cpus", "1",
        docker_image,
        "bash", "-c", script,
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=False,           # bytes mode — avoids Windows cp1252 decode errors
            timeout=timeout_seconds,
            check=False,
        )
        stdout = completed.stdout.decode("utf-8", errors="replace").strip()
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        passed = completed.returncode == 0

        parts = [f"exit_code={completed.returncode}"]
        if stdout:
            parts.append(f"stdout:\n{stdout}")
        if stderr and not passed:
            parts.append(f"stderr:\n{stderr[-800:]}")  # trim long errors

        return passed, "\n".join(parts)

    except subprocess.TimeoutExpired:
        return False, f"Timed out after {timeout_seconds}s"
    except FileNotFoundError:
        return False, "Docker executable not found. Ensure Docker is installed and on PATH."
    except Exception as exc:  # noqa: BLE001
        return False, f"Unexpected error: {exc!r}"


def validate_skill(
    skill_name: str,
    skill_markdown: str,
    docker_image: str = "python:3.11-slim",
    timeout_seconds: int = 300,
) -> ValidationResult:
    """Validate a SKILL.md by generating and running a bash test script in Docker.

    The LLM generates a safe, minimal bash script from the skill's Procedure
    section. The script is executed inside a sandboxed Docker container.
    """
    attempts = 1

    logger.info(
        "Starting validation for skill '%s' using image '%s'", skill_name, docker_image
    )

    try:
        script = _generate_validation_script(skill_name, skill_markdown)
        logger.debug("Validation script for '{}':\n{}", skill_name, script)
    except Exception as exc:
        passed = False
        details = f"Failed to generate validation script: {exc!r}"
        logger.error(details)
        return ValidationResult(
            skill_name=skill_name,
            passed=passed,
            attempts=attempts,
            details=details,
        )

    passed, details = _run_in_docker(script, docker_image, timeout_seconds)

    logger.info(
        "Validation for skill '%s' finished: passed=%s", skill_name, passed
    )

    return ValidationResult(
        skill_name=skill_name,
        passed=passed,
        attempts=attempts,
        details=details,
    )
