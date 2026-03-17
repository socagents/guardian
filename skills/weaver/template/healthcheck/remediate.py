"""Self-healing remediation actions for pipeline health checks.

When the health check detects a known-fixable problem, these functions
take corrective action automatically. Every action is:
  - Rate-guarded (won't fire more than once per cooldown period)
  - Logged (returns a description of what was done)
  - Safe (worst case: triggers an idempotent workflow or resets a label)

Rate-guard state is stored in /tmp/healthcheck-heal-*.txt files.
These persist across health check runs but reset on runner restart,
which is fine since a restart clears stale state anyway.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from healthcheck.utils import REPO, CheckResult, Status

# ── Rate-guard config ──────────────────────────────────────────────────────

HEAL_STATE_DIR = Path("/tmp/healthcheck-heal")
HEAL_STATE_DIR.mkdir(exist_ok=True)

# Cooldown periods in seconds
COOLDOWNS = {
    "trigger_dispatch": 600,       # 10 min — don't spam dispatch triggers
    "reset_stale_issue": 1800,     # 30 min per issue — allow time for re-dispatch
    "retry_merge": 900,            # 15 min per PR — allow time for merge to process
    "cancel_stuck_run": 3600,      # 1 hour — only cancel once per stuck run
    "trigger_sweep": 3600,         # 1 hour — sweep runs hourly anyway
}


@dataclass
class HealAction:
    """Record of a self-healing action taken."""
    action: str
    target: str  # e.g., issue number, run ID, PR number
    success: bool
    message: str


@dataclass
class HealReport:
    """Summary of all healing actions taken in one health check run."""
    actions: list[HealAction] = field(default_factory=list)

    def add(self, action: HealAction) -> None:
        self.actions.append(action)

    @property
    def actions_taken(self) -> int:
        return len([a for a in self.actions if a.success])

    def to_dict(self) -> list[dict]:
        return [
            {"action": a.action, "target": a.target,
             "success": a.success, "message": a.message}
            for a in self.actions
        ]


# ── Rate guard ─────────────────────────────────────────────────────────────

def _rate_guard_key(action: str, target: str) -> Path:
    safe_target = str(target).replace("/", "_").replace(" ", "_")
    return HEAL_STATE_DIR / f"{action}-{safe_target}.txt"


def _is_rate_limited(action: str, target: str) -> bool:
    """Check if this action+target was done recently (within cooldown)."""
    key_file = _rate_guard_key(action, target)
    if not key_file.exists():
        return False
    try:
        last_run = float(key_file.read_text().strip())
        cooldown = COOLDOWNS.get(action, 600)
        return (time.time() - last_run) < cooldown
    except (ValueError, OSError):
        return False


def _mark_action(action: str, target: str) -> None:
    """Record that this action+target was just performed."""
    key_file = _rate_guard_key(action, target)
    key_file.write_text(str(time.time()))


def _gh(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a gh CLI command. Uses PROJECT_PAT if available."""
    env = os.environ.copy()
    # Prefer PROJECT_PAT for write operations (triggers downstream workflows)
    pat = os.environ.get("PROJECT_PAT", "")
    if pat:
        env["GH_TOKEN"] = pat
    return subprocess.run(
        ["gh"] + args,
        capture_output=True, text=True, timeout=timeout, env=env,
    )


# ── Healing actions ────────────────────────────────────────────────────────

def heal_trigger_dispatch(report: HealReport) -> None:
    """Trigger a fresh dispatch if ready issues exist and no dispatch is running/queued."""
    if _is_rate_limited("trigger_dispatch", "global"):
        return

    # Check for queued/in-progress dispatch runs
    result = _gh([
        "run", "list", "--repo", REPO,
        "--workflow=Agent – Dispatch",
        "--json", "status",
        "--limit", "3",
    ])
    if result.returncode != 0:
        return

    runs = json.loads(result.stdout) if result.stdout.strip() else []
    active = [r for r in runs if r.get("status") in ("queued", "in_progress")]
    if active:
        return  # A dispatch is already running — no action needed

    # Check if ready issues exist
    result = _gh([
        "issue", "list", "--repo", REPO,
        "--label", "status:ready",
        "--json", "number,labels",
    ])
    if result.returncode != 0:
        return

    issues = json.loads(result.stdout) if result.stdout.strip() else []
    agent_ready = [
        i for i in issues
        if any(l["name"].startswith("agent:") for l in i.get("labels", []))
    ]

    if not agent_ready:
        return  # Nothing to dispatch

    # Trigger dispatch
    result = _gh([
        "workflow", "run", "Agent – Dispatch",
        "--repo", REPO,
    ])

    action = HealAction(
        action="trigger_dispatch",
        target=f"{len(agent_ready)} ready issues",
        success=result.returncode == 0,
        message="Triggered fresh dispatch" if result.returncode == 0
                else f"Failed to trigger: {result.stderr.strip()}",
    )
    report.add(action)
    if result.returncode == 0:
        _mark_action("trigger_dispatch", "global")


def heal_reset_stale_issues(report: HealReport, stale_issues: list[dict]) -> None:
    """Reset stale in-progress issues back to status:ready."""
    for issue in stale_issues:
        number = str(issue.get("number", ""))
        if not number or _is_rate_limited("reset_stale_issue", number):
            continue

        # Check if there's an open PR for this issue (don't reset if PR exists)
        result = _gh([
            "pr", "list", "--repo", REPO,
            "--search", f"Closes #{number}",
            "--json", "number",
        ])
        if result.returncode == 0:
            prs = json.loads(result.stdout) if result.stdout.strip() else []
            if prs:
                continue  # PR exists — issue is being worked on

        # Reset labels
        result = _gh([
            "issue", "edit", number, "--repo", REPO,
            "--remove-label", "status:in-progress",
            "--add-label", "status:ready",
        ])

        # Add a comment explaining the reset
        if result.returncode == 0:
            _gh([
                "issue", "comment", number, "--repo", REPO,
                "--body", "<!-- AGENT_MSG agent=healthcheck action=auto-reset -->\n"
                "🏥 **Auto-healed** — This issue was stuck in `status:in-progress` for >2 hours "
                "with no open PR. Reset to `status:ready` for re-dispatch.",
            ])

        action = HealAction(
            action="reset_stale_issue",
            target=f"#{number}",
            success=result.returncode == 0,
            message=f"Reset #{number} to status:ready" if result.returncode == 0
                    else f"Failed to reset #{number}: {result.stderr.strip()}",
        )
        report.add(action)
        if result.returncode == 0:
            _mark_action("reset_stale_issue", number)


def heal_retry_merge(report: HealReport, stale_prs: list[dict]) -> None:
    """Retry merge for approved PRs that haven't been merged."""
    for pr in stale_prs:
        number = str(pr.get("number", ""))
        if not number or _is_rate_limited("retry_merge", number):
            continue

        result = _gh([
            "pr", "merge", number, "--repo", REPO,
            "--squash", "--delete-branch",
        ])

        action = HealAction(
            action="retry_merge",
            target=f"PR #{number}",
            success=result.returncode == 0,
            message=f"Merged PR #{number}" if result.returncode == 0
                    else f"Merge retry failed: {result.stderr.strip()[:200]}",
        )
        report.add(action)
        if result.returncode == 0:
            _mark_action("retry_merge", number)


def heal_cancel_stuck_run(report: HealReport, run_id: str | int) -> None:
    """Cancel a workflow run that's been running too long (>90 min)."""
    run_id_str = str(run_id)
    if _is_rate_limited("cancel_stuck_run", run_id_str):
        return

    result = _gh([
        "run", "cancel", run_id_str, "--repo", REPO,
    ])

    action = HealAction(
        action="cancel_stuck_run",
        target=f"run {run_id_str}",
        success=result.returncode == 0,
        message=f"Cancelled stuck run {run_id_str}" if result.returncode == 0
                else f"Failed to cancel: {result.stderr.strip()}",
    )
    report.add(action)
    if result.returncode == 0:
        _mark_action("cancel_stuck_run", run_id_str)


# ── Main heal entry point ─────────────────────────────────────────────────

def auto_heal(check_results: list[CheckResult]) -> HealReport:
    """Analyze check results and take corrective actions where possible.

    Only acts on checks that are DEGRADED or worse AND have a known
    auto-remediation path. Returns a report of actions taken.
    """
    report = HealReport()

    for check in check_results:
        if check.status == Status.HEALTHY:
            continue

        # S2/D1: Backlog or no recent dispatch → trigger dispatch
        if check.id in ("S2", "D1") and check.status >= Status.DEGRADED:
            heal_trigger_dispatch(report)

        # S3: Stale in-progress issues → reset to ready
        if check.id == "S3" and check.status >= Status.UNHEALTHY:
            stale = check.details.get("stale_issues", [])
            if stale:
                heal_reset_stale_issues(report, stale)

        # V4: Approved PR not merged → retry merge
        if check.id == "V4" and check.status >= Status.UNHEALTHY:
            stale_prs = check.details.get("unmerged_prs", [])
            if stale_prs:
                heal_retry_merge(report, stale_prs)

        # R2: Stuck runner → cancel stuck run
        if check.id == "R2" and check.status >= Status.UNHEALTHY:
            stuck_run = check.details.get("stuck_run_id")
            if stuck_run:
                heal_cancel_stuck_run(report, stuck_run)

    return report
