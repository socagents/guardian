"""Shared utilities for pipeline health checks.

All checks use `gh` CLI for GitHub API calls (authenticated via GITHUB_TOKEN
in Actions, or user's gh auth locally). Zero external dependencies.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any


# ── Status levels (ordered by severity) ─────────────────────────────────────

class Status(IntEnum):
    HEALTHY = 0
    DEGRADED = 1
    UNHEALTHY = 2
    CRITICAL = 3

    @property
    def emoji(self) -> str:
        return {0: "🟢", 1: "🟡", 2: "🟠", 3: "🔴"}[self.value]

    @property
    def label(self) -> str:
        return self.name


# ── Check result ────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    id: str
    name: str
    status: Status
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    remediation: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.label
        d["emoji"] = self.status.emoji
        return d


# ── Report ──────────────────────────────────────────────────────────────────

@dataclass
class HealthReport:
    timestamp: str
    checks: list[CheckResult]

    @property
    def overall_status(self) -> Status:
        if not self.checks:
            return Status.HEALTHY
        return Status(max(c.status.value for c in self.checks))

    @property
    def summary(self) -> dict[str, int]:
        counts = {"healthy": 0, "degraded": 0, "unhealthy": 0, "critical": 0}
        for c in self.checks:
            counts[c.status.label.lower()] += 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "overall_status": self.overall_status.label,
            "checks": [c.to_dict() for c in self.checks],
            "summary": self.summary,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def to_slack_message(self) -> str:
        ts = self.timestamp
        overall = self.overall_status
        lines = [
            f"🏥 *Pipeline Health Report* — {ts}",
            f"Overall: {overall.emoji} *{overall.label}*",
            "",
        ]

        non_healthy = [c for c in self.checks if c.status != Status.HEALTHY]
        if non_healthy:
            for c in sorted(non_healthy, key=lambda x: -x.status.value):
                lines.append(f"{c.status.emoji} *{c.id}*: {c.name}")
                lines.append(f"    {c.message}")
                if c.remediation:
                    lines.append(f"    _Remediation: {c.remediation}_")
                lines.append("")
        else:
            lines.append("All checks passing — pipeline is healthy. ✅")
            lines.append("")

        # Include self-healing summary if set by the main runner
        heal_summary = getattr(self, "_heal_summary", "")
        if heal_summary:
            lines.append(heal_summary)
            lines.append("")

        s = self.summary
        lines.append(
            f"Summary: {s['healthy']}🟢  {s['degraded']}🟡  "
            f"{s['unhealthy']}🟠  {s['critical']}🔴"
        )
        return "\n".join(lines)


# ── GitHub API helpers ──────────────────────────────────────────────────────

REPO = os.environ.get("GITHUB_REPOSITORY", "{{GITHUB_ORG}}/{{GITHUB_REPO}}")


def gh_api(endpoint: str, paginate: bool = False) -> Any:
    """Call GitHub API via gh CLI. Returns parsed JSON."""
    cmd = ["gh", "api", endpoint, "--header", "Accept: application/vnd.github+json"]
    if paginate:
        cmd.append("--paginate")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"gh api failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def gh_api_graphql(query: str, variables: dict | None = None) -> Any:
    """Call GitHub GraphQL API via gh CLI."""
    cmd = ["gh", "api", "graphql", "-f", f"query={query}"]
    if variables:
        for k, v in variables.items():
            cmd.extend(["-f", f"{k}={v}"])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"gh api graphql failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def list_workflow_runs(
    workflow: str, limit: int = 10, status: str | None = None
) -> list[dict]:
    """List recent runs for a workflow file."""
    endpoint = f"/repos/{REPO}/actions/workflows/{workflow}/runs?per_page={limit}"
    if status:
        endpoint += f"&status={status}"
    data = gh_api(endpoint)
    return data.get("workflow_runs", [])


def list_issues(labels: str, state: str = "open") -> list[dict]:
    """List issues with given labels."""
    endpoint = f"/repos/{REPO}/issues?labels={labels}&state={state}&per_page=100"
    return gh_api(endpoint)


def list_pulls(state: str = "open") -> list[dict]:
    """List pull requests."""
    endpoint = f"/repos/{REPO}/pulls?state={state}&per_page=100"
    return gh_api(endpoint)


def get_issue_comments(number: int) -> list[dict]:
    """Get comments on an issue/PR."""
    endpoint = f"/repos/{REPO}/issues/{number}/comments?per_page=100"
    return gh_api(endpoint)


def parse_iso(dt_str: str) -> datetime:
    """Parse ISO 8601 timestamp to aware datetime."""
    # Handle both 'Z' suffix and '+00:00'
    dt_str = dt_str.replace("Z", "+00:00")
    return datetime.fromisoformat(dt_str)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def hours_ago(hours: float) -> datetime:
    from datetime import timedelta
    return now_utc() - timedelta(hours=hours)
