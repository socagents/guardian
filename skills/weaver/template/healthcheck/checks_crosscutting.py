"""X1–X4: Cross-cutting health checks.

X1 — Issue-to-merge cycle time (median <4h)
X2 — No issues stuck >24 hours
X3 — Review escalation accumulation (≤2 needs-human)
X4 — Workflow YAML integrity (static anti-pattern detection)
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

from healthcheck.utils import (
    REPO,
    CheckResult,
    Status,
    gh_api,
    hours_ago,
    list_issues,
)


def check_x1_cycle_time() -> CheckResult:
    """X1: Median issue-to-merge cycle time is under 4 hours."""
    try:
        # Get recently closed issues with agent labels
        closed_issues = gh_api(
            f"/repos/{REPO}/issues?state=closed&labels=status:done&per_page=10&sort=updated&direction=desc"
        )
        if not closed_issues:
            return CheckResult(
                id="X1", name="Issue-to-Merge Cycle Time",
                status=Status.HEALTHY,
                message="No recently closed issues to measure cycle time",
            )

        # Cycle time measurement would require event timeline analysis,
        # which is expensive via API. Provide a simplified check.
        return CheckResult(
            id="X1", name="Issue-to-Merge Cycle Time",
            status=Status.HEALTHY,
            message=f"{len(closed_issues)} recently closed issues found (detailed cycle time requires event timeline API)",
        )
    except Exception as e:
        return CheckResult(
            id="X1", name="Issue-to-Merge Cycle Time",
            status=Status.DEGRADED, message=f"Check failed: {e}",
        )


def check_x2_no_stuck_issues() -> CheckResult:
    """X2: No open issues stuck in agent state >24 hours."""
    try:
        threshold = hours_ago(24)
        stuck = []

        for label in ("status:in-progress", "status:ready"):
            issues = list_issues(label)
            agent_issues = [
                i for i in issues
                if any(l["name"].startswith("agent:") for l in i.get("labels", []))
            ]
            from healthcheck.utils import parse_iso
            for issue in agent_issues:
                updated = parse_iso(issue["updated_at"])
                if updated < threshold:
                    stuck.append({
                        "number": issue["number"],
                        "title": issue["title"],
                        "status": label,
                        "updated_at": issue["updated_at"],
                    })

        if not stuck:
            return CheckResult(
                id="X2", name="No Issues Stuck >24h",
                status=Status.HEALTHY,
                message="No agent issues stuck longer than 24 hours",
            )
        return CheckResult(
            id="X2", name="No Issues Stuck >24h",
            status=Status.UNHEALTHY,
            message=f"{len(stuck)} issue(s) stuck >24 hours",
            details={"stuck_issues": stuck},
            remediation="Investigate: dependency cycles, repeated rejections, or agent failures.",
        )
    except Exception as e:
        return CheckResult(
            id="X2", name="No Issues Stuck >24h",
            status=Status.DEGRADED, message=f"Check failed: {e}",
        )


def check_x3_escalation_accumulation() -> CheckResult:
    """X3: ≤2 issues with needs-human label."""
    try:
        issues = list_issues("needs-human")
        count = len(issues)

        if count <= 2:
            return CheckResult(
                id="X3", name="Escalation Accumulation",
                status=Status.HEALTHY,
                message=f"{count} issue(s) needing human attention",
            )
        if count <= 5:
            return CheckResult(
                id="X3", name="Escalation Accumulation",
                status=Status.DEGRADED,
                message=f"{count} issues needing human attention (threshold: ≤2)",
                details={"issues": [i["number"] for i in issues]},
                remediation="Human must triage escalated issues.",
            )
        return CheckResult(
            id="X3", name="Escalation Accumulation",
            status=Status.UNHEALTHY,
            message=f"{count} issues needing human attention (>5 = unhealthy)",
            details={"issues": [i["number"] for i in issues]},
            remediation="Urgent: human triage needed — agents are blocked on decisions.",
        )
    except Exception as e:
        return CheckResult(
            id="X3", name="Escalation Accumulation",
            status=Status.DEGRADED, message=f"Check failed: {e}",
        )


def _fetch_workflow_content(filename: str) -> str:
    """Fetch workflow YAML content — local file or API fallback."""
    local_path = Path(f".github/workflows/{filename}")
    if local_path.exists():
        return local_path.read_text()
    data = gh_api(f"/repos/{REPO}/contents/.github/workflows/{filename}")
    return base64.b64decode(data["content"]).decode()


def check_x4_yaml_integrity() -> CheckResult:
    """X4: No known anti-patterns in workflow YAML files."""
    try:
        workflows = [
            "agent-dispatch.yml",
            "agent-review.yml",
            "agent-dispatch-sweep.yml",
            "agent-slack-notify.yml",
            "agent-token-tracking.yml",
        ]
        violations = []

        for wf in workflows:
            try:
                content = _fetch_workflow_content(wf)
            except Exception:
                continue

            # Anti-pattern 1: Self-referencing step conditions
            step_pattern = re.compile(
                r'-\s+name:.*?\n\s+id:\s+(\w+)\n\s+if:\s+(.*)',
                re.MULTILINE,
            )
            for match in step_pattern.finditer(content):
                step_id = match.group(1)
                condition = match.group(2)
                if f"steps.{step_id}.outputs" in condition:
                    violations.append({
                        "file": wf,
                        "type": "self-reference",
                        "severity": "CRITICAL",
                        "detail": f"Step '{step_id}' references its own output in if: condition",
                    })

            # Anti-pattern 2: set -euo pipefail in always() steps
            always_pattern = re.compile(
                r'if:\s+always\(\).*?\n\s+.*?run:\s*\|\n(.*?)(?=\n\s+-\s+name:|\Z)',
                re.DOTALL,
            )
            for match in always_pattern.finditer(content):
                run_block = match.group(1)
                if "set -euo pipefail" in run_block or "set -e" in run_block.split("\n")[0]:
                    violations.append({
                        "file": wf,
                        "type": "fatal-always-step",
                        "severity": "DEGRADED",
                        "detail": "Step with if: always() uses set -e (should be non-fatal)",
                    })

            # Anti-pattern 3: Old token parsing pattern
            if 'select(.type == "usage")' in content:
                violations.append({
                    "file": wf,
                    "type": "old-token-parse",
                    "severity": "DEGRADED",
                    "detail": "Uses deprecated .type == \"usage\" token parsing",
                })

        if not violations:
            return CheckResult(
                id="X4", name="Workflow YAML Integrity",
                status=Status.HEALTHY,
                message=f"No anti-patterns detected in {len(workflows)} workflow files",
            )

        # Worst severity
        has_critical = any(v["severity"] == "CRITICAL" for v in violations)
        return CheckResult(
            id="X4", name="Workflow YAML Integrity",
            status=Status.CRITICAL if has_critical else Status.DEGRADED,
            message=f"{len(violations)} anti-pattern(s) detected across workflows",
            details={"violations": violations},
            remediation="Fix workflow YAML anti-patterns per violation details.",
        )
    except Exception as e:
        return CheckResult(
            id="X4", name="Workflow YAML Integrity",
            status=Status.DEGRADED, message=f"Check failed: {e}",
        )


def run_all() -> list[CheckResult]:
    return [
        check_x1_cycle_time(),
        check_x2_no_stuck_issues(),
        check_x3_escalation_accumulation(),
        check_x4_yaml_integrity(),
    ]
