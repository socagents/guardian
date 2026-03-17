"""Pipeline health check runner with optional self-healing.

Usage:
    python -m healthcheck                  # Run all checks, print report
    python -m healthcheck --json           # JSON output
    python -m healthcheck --slack          # Post to Slack #alerts channel
    python -m healthcheck --heal           # Detect AND auto-fix known issues
    python -m healthcheck --heal --slack   # Auto-fix + alert on remaining issues
    python -m healthcheck --category runner,sweep  # Run specific categories

Exit codes:
    0 = HEALTHY
    1 = DEGRADED
    2 = UNHEALTHY
    3 = CRITICAL
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from healthcheck.checks_budget import run_all as budget_checks
from healthcheck.checks_crosscutting import run_all as crosscutting_checks
from healthcheck.checks_dispatch import run_all as dispatch_checks
from healthcheck.checks_notifications import run_all as notification_checks
from healthcheck.checks_review import run_all as review_checks
from healthcheck.checks_runner import run_all as runner_checks
from healthcheck.checks_sweep import run_all as sweep_checks
from healthcheck.utils import CheckResult, HealthReport, Status

# Category registry
CATEGORIES: dict[str, callable] = {
    "runner": runner_checks,
    "dispatch": dispatch_checks,
    "sweep": sweep_checks,
    "review": review_checks,
    "notifications": notification_checks,
    "budget": budget_checks,
    "crosscutting": crosscutting_checks,
}


def run_checks(categories: list[str] | None = None) -> HealthReport:
    """Execute health checks and return a report."""
    results: list[CheckResult] = []
    cats = categories or list(CATEGORIES.keys())

    for cat in cats:
        if cat in CATEGORIES:
            try:
                results.extend(CATEGORIES[cat]())
            except Exception as e:
                results.append(CheckResult(
                    id=f"{cat.upper()[:1]}?",
                    name=f"{cat} category error",
                    status=Status.DEGRADED,
                    message=f"Category {cat} failed to run: {e}",
                ))

    return HealthReport(
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        checks=results,
    )


def post_to_slack(report: HealthReport) -> bool:
    """Post the health report to Slack #alerts channel."""
    channel_id = os.environ.get("SLACK_ALERTS_CHANNEL", "")
    slack_token = os.environ.get("SLACK_BOT_TOKEN", "")

    if not channel_id:
        print("SLACK_ALERTS_CHANNEL not set — skipping Slack post", file=sys.stderr)
        return False

    message = report.to_slack_message()

    # Only post if not fully healthy (avoid noise)
    if report.overall_status == Status.HEALTHY:
        print("Pipeline healthy — posting abbreviated status to Slack")
        message = (
            f"🏥 *Pipeline Health* — {report.timestamp}\n"
            f"Overall: 🟢 *HEALTHY* — all {len(report.checks)} checks passing ✅"
        )

    if slack_token:
        # Use Slack API directly
        import urllib.request
        req = urllib.request.Request(
            "https://slack.com/api/chat.postMessage",
            data=json.dumps({
                "channel": channel_id,
                "text": message,
                "unfurl_links": False,
            }).encode(),
            headers={
                "Authorization": f"Bearer {slack_token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                if not result.get("ok"):
                    print(f"Slack API error: {result.get('error')}", file=sys.stderr)
                    return False
            return True
        except Exception as e:
            print(f"Slack post failed: {e}", file=sys.stderr)
            return False
    else:
        # Fallback: use gh CLI to post via workflow or just print
        print("SLACK_BOT_TOKEN not set — printing Slack message to stdout:")
        print(message)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="{{PROJECT_NAME}} pipeline health checker")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--slack", action="store_true", help="Post to Slack #alerts")
    parser.add_argument("--heal", action="store_true",
                        help="Auto-remediate known issues (rate-guarded)")
    parser.add_argument(
        "--category", "-c", type=str, default=None,
        help="Comma-separated categories: runner,dispatch,sweep,review,notifications,budget,crosscutting",
    )
    args = parser.parse_args()

    categories = args.category.split(",") if args.category else None
    report = run_checks(categories)

    # ── Self-healing pass ──────────────────────────────────────────────
    heal_report = None
    if args.heal and report.overall_status != Status.HEALTHY:
        from healthcheck.remediate import auto_heal
        heal_report = auto_heal(report.checks)
        if heal_report.actions_taken > 0:
            print(f"🏥 Self-healing: {heal_report.actions_taken} action(s) taken",
                  file=sys.stderr)

    # ── Output ─────────────────────────────────────────────────────────
    if args.json:
        output = report.to_dict()
        if heal_report:
            output["heal_actions"] = heal_report.to_dict()
        print(json.dumps(output, indent=2))
    else:
        # Human-readable output
        print(report.to_slack_message())
        if heal_report and heal_report.actions:
            print()
            print("─── Self-Healing Actions ───")
            for a in heal_report.actions:
                status = "✅" if a.success else "❌"
                print(f"  {status} {a.action} → {a.target}: {a.message}")
        print()
        non_healthy = [c for c in report.checks if c.status != Status.HEALTHY]
        if non_healthy:
            print("─── Details ───")
            for c in non_healthy:
                if c.details:
                    print(f"  {c.id}: {json.dumps(c.details, indent=4)}")

    if args.slack:
        # Include heal actions in Slack message if any were taken
        if heal_report and heal_report.actions_taken > 0:
            heal_lines = [
                "",
                f"🔧 *Self-Healing*: {heal_report.actions_taken} action(s) taken:",
            ]
            for a in heal_report.actions:
                icon = "✅" if a.success else "❌"
                heal_lines.append(f"  {icon} `{a.action}` → {a.target}")
            report._heal_summary = "\n".join(heal_lines)
        post_to_slack(report)

    return report.overall_status.value


if __name__ == "__main__":
    sys.exit(main())
