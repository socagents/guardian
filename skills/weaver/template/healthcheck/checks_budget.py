"""B1–B3: Budget health checks.

B1 — Daily invocation limit not exhausted (<80% = healthy, 80-99% = degraded, 100% = unhealthy)
B2 — Token logs not corrupted (all JSONL files parseable)
B3 — Token logs not oversized (no file >1MB)

Reads token logs from the self-hosted runner's host filesystem at
/home/{{RUNNER_USER}}/kite-token-logs/{agent}/{date}.jsonl.
Each line = one invocation. Budget check counts lines (not token sums).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from healthcheck.utils import (
    CheckResult,
    Status,
)

# Host path where token logs persist across workflow runs
TOKEN_LOG_DIR = Path(os.environ.get("TOKEN_LOG_DIR", "/home/{{RUNNER_USER}}/kite-token-logs"))

# Daily invocation limits per agent (issues/reviews/runs per day)
DAILY_LIMITS = {
    "claude-code": {{LIMIT_CODING}},
    "codex-cli": {{LIMIT_CODING}},
    "review-agent": {{LIMIT_REVIEW}},
    "planning-agent": {{LIMIT_PLANNING}},
    "validation-agent": {{LIMIT_VALIDATION}},
    "deployment-agent": {{LIMIT_DEPLOY}},
}


def _get_agent_dirs() -> list[Path]:
    """List agent subdirectories in the token log dir."""
    if not TOKEN_LOG_DIR.is_dir():
        return []
    return [d for d in TOKEN_LOG_DIR.iterdir() if d.is_dir() and d.name != "summaries"]


def _get_today_log(agent_dir: Path) -> str | None:
    """Read today's token log content for an agent."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = agent_dir / f"{today}.jsonl"
    if not log_file.exists():
        return None
    try:
        return log_file.read_text()
    except OSError:
        return None


def check_b1_budget_not_exhausted() -> CheckResult:
    """B1: All agents under 80% of daily invocation limit."""
    try:
        agent_dirs = _get_agent_dirs()

        if not agent_dirs:
            return CheckResult(
                id="B1", name="Daily Limit Not Exhausted",
                status=Status.HEALTHY,
                message="No token log directories found — budget tracking may not be active",
            )

        warnings: list[str] = []
        exhausted: list[str] = []
        for agent_dir in agent_dirs:
            content = _get_today_log(agent_dir)
            if not content:
                continue  # No log today = no usage

            # Count invocations (one line per invocation)
            invocations = sum(1 for line in content.strip().split("\n") if line.strip())

            limit = DAILY_LIMITS.get(agent_dir.name, 10)
            pct = (invocations / limit * 100) if limit > 0 else 0

            if pct >= 100:
                exhausted.append(f"{agent_dir.name}: {invocations}/{limit} invocations")
            elif pct >= 80:
                warnings.append(f"{agent_dir.name}: {invocations}/{limit} invocations")

        if exhausted:
            return CheckResult(
                id="B1", name="Daily Limit Not Exhausted",
                status=Status.UNHEALTHY,
                message=f"Limit reached: {'; '.join(exhausted)}",
                remediation="Wait for UTC midnight reset, or increase daily limit.",
            )
        if warnings:
            return CheckResult(
                id="B1", name="Daily Limit Not Exhausted",
                status=Status.DEGRADED,
                message=f"Limit warning (>80%): {'; '.join(warnings)}",
            )
        return CheckResult(
            id="B1", name="Daily Limit Not Exhausted",
            status=Status.HEALTHY,
            message="All agents within daily limits (<80%)",
        )
    except Exception as e:
        return CheckResult(
            id="B1", name="Daily Limit Not Exhausted",
            status=Status.DEGRADED, message=f"Check failed: {e}",
        )


def check_b2_logs_not_corrupted() -> CheckResult:
    """B2: All JSONL token log files are valid."""
    try:
        agent_dirs = _get_agent_dirs()
        corrupted: list[str] = []

        for agent_dir in agent_dirs:
            for log_file in agent_dir.glob("*.jsonl"):
                try:
                    content = log_file.read_text()
                    for i, line in enumerate(content.strip().split("\n"), 1):
                        if line.strip():
                            json.loads(line)
                except json.JSONDecodeError:
                    corrupted.append(f"{agent_dir.name}/{log_file.name} (line {i})")
                except OSError:
                    continue

        if not corrupted:
            return CheckResult(
                id="B2", name="Token Logs Not Corrupted",
                status=Status.HEALTHY,
                message="All token log files are valid JSONL",
            )
        return CheckResult(
            id="B2", name="Token Logs Not Corrupted",
            status=Status.DEGRADED,
            message=f"{len(corrupted)} corrupted log file(s): {', '.join(corrupted[:3])}",
            remediation="Clean corrupted lines. Check which workflow writes bad data.",
        )
    except Exception as e:
        return CheckResult(
            id="B2", name="Token Logs Not Corrupted",
            status=Status.DEGRADED, message=f"Check failed: {e}",
        )


def check_b3_logs_not_oversized() -> CheckResult:
    """B3: No individual JSONL log file exceeds 1MB."""
    try:
        agent_dirs = _get_agent_dirs()
        oversized: list[str] = []

        for agent_dir in agent_dirs:
            for log_file in agent_dir.glob("*.jsonl"):
                try:
                    size = log_file.stat().st_size
                except OSError:
                    continue
                if size > 1_000_000:  # 1MB
                    oversized.append(
                        f"{agent_dir.name}/{log_file.name} ({size / 1_000_000:.1f}MB)"
                    )

        if not oversized:
            return CheckResult(
                id="B3", name="Token Logs Not Oversized",
                status=Status.HEALTHY,
                message="All token log files under 1MB",
            )
        return CheckResult(
            id="B3", name="Token Logs Not Oversized",
            status=Status.UNHEALTHY,
            message=f"{len(oversized)} oversized log file(s): {', '.join(oversized[:3])}",
            remediation="Archive or truncate old log files.",
        )
    except Exception as e:
        return CheckResult(
            id="B3", name="Token Logs Not Oversized",
            status=Status.DEGRADED, message=f"Check failed: {e}",
        )


def run_all() -> list[CheckResult]:
    return [
        check_b1_budget_not_exhausted(),
        check_b2_logs_not_corrupted(),
        check_b3_logs_not_oversized(),
    ]
