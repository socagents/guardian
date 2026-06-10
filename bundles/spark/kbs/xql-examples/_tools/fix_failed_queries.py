"""Fix-up pass for v0.7.0 — apply schema corrections discovered
from the first validation run + re-validate.

Failures were dominated by field-name guesses:
  - alerts:   mitre_tactic_id_and_name → mitre_attack_tactic
              mitre_technique_id_and_name → mitre_attack_technique
              source → alert_source
  - issues:   xdm.alert.severity → xdm.issue.severity
              xdm.alert.name → xdm.issue.name
              xdm.alert.mitre_tactic_id_and_name → xdm.issue.mitre_tactics
  - va_cves:  cve_severity → severity
  - va_endpoints: cve_id only available via cves[] arrayexpand
  - endpoints: group_name → group_names, endpoint_tags → tags
              endpoint_isolated boolean true → string "ISOLATED"
  - incidents: assigned_user_pretty_name → assigned_user
              host_count not present — use alert_count
  - host_inventory: hostname → host_name, ad_domain → agent_domain
                    operating_system_family → os_type
  - xdr_data: event_id is base64, not Windows code — these queries
              targeted a tenant configuration that's not present;
              dropped.

Each fixed query is re-validated. Surviving ones land in entries/.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_100_queries import (  # type: ignore[import-not-found]
    ENTRIES_DIR,
    run_xql,
    write_kb_entry,
)
import re
import time


# Pick up where v0.7.0's first pass left off (95 successes started at ID 700)
START_ID = 700 + 95  # 795


# Templates that were corrected based on schema probes
FIXES: list[tuple[str, str, str, str, str, list[str]]] = [
    # ─── alerts — corrected MITRE field names ────────────────────
    (
        "investigation", "alerts",
        "Alerts by MITRE tactic + technique (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| filter mitre_attack_tactic != null\n| comp count() as cnt by mitre_attack_tactic, mitre_attack_technique\n| sort desc cnt\n| limit 10",
        "Per-alert MITRE ATT&CK mapping using the live tenant's `mitre_attack_tactic` + `mitre_attack_technique` fields. Surfaces the tactic-coverage shape — which techniques fire most.",
        ["filter", "comp", "sort", "limit", "alerts", "mitre"],
    ),
    (
        "detection", "alerts",
        "Persistence-tactic alerts (30d, TA0003)",
        "config timeframe = 30d\n| dataset = alerts\n| filter mitre_attack_tactic contains \"TA0003\" or mitre_attack_tactic contains \"Persistence\"\n| fields _time, host_name, alert_name, severity, mitre_attack_technique\n| sort desc _time\n| limit 10",
        "Alerts mapped to MITRE TA0003 Persistence. Captures registry/service/scheduled-task/WMI persistence detections.",
        ["filter", "fields", "sort", "limit", "alerts", "mitre", "TA0003"],
    ),
    (
        "detection", "alerts",
        "Lateral-movement alerts (30d, TA0008)",
        "config timeframe = 30d\n| dataset = alerts\n| filter mitre_attack_tactic contains \"TA0008\" or mitre_attack_tactic contains \"Lateral\"\n| fields _time, host_name, alert_name, severity, mitre_attack_technique\n| sort desc _time\n| limit 10",
        "Lateral-movement detections (MITRE TA0008). PsExec, WinRM abuse, remote service creation, RDP, SMB.",
        ["filter", "fields", "sort", "limit", "alerts", "mitre", "TA0008"],
    ),
    (
        "detection", "alerts",
        "Exfiltration-tactic alerts (30d, TA0010)",
        "config timeframe = 30d\n| dataset = alerts\n| filter mitre_attack_tactic contains \"TA0010\" or mitre_attack_tactic contains \"Exfiltration\"\n| fields _time, host_name, alert_name, severity, mitre_attack_technique\n| sort desc _time\n| limit 10",
        "Exfiltration detections (MITRE TA0010). Bulk uploads, archive activity, anomalous outbound.",
        ["filter", "fields", "sort", "limit", "alerts", "mitre", "TA0010"],
    ),
    (
        "detection", "alerts",
        "Brute-force alerts (30d, T1110)",
        "config timeframe = 30d\n| dataset = alerts\n| filter lowercase(alert_name) contains \"brute\" or lowercase(alert_name) contains \"password spray\" or lowercase(alert_name) contains \"failed login\" or mitre_attack_technique contains \"T1110\"\n| fields _time, host_name, alert_name, severity, user_name\n| sort desc _time\n| limit 10",
        "Brute-force + password-spray detections (MITRE T1110). Common against external-facing services + privileged accounts.",
        ["filter", "fields", "sort", "limit", "alerts", "T1110"],
    ),
    (
        "investigation", "alerts",
        "Alert detection-source breakdown (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| filter alert_source != null\n| comp count() as cnt by alert_source, severity\n| sort desc cnt\n| limit 10",
        "Per-detection-source alert volume by severity. Reveals which detector source generates which severities. (Corrected: `source` field → `alert_source`.)",
        ["filter", "comp", "sort", "limit", "alerts"],
    ),
    (
        "investigation", "alerts",
        "Alerts with category + tactic (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| filter category != null\n| comp count() as cnt by category, mitre_attack_tactic\n| sort desc cnt\n| limit 10",
        "Cross-tab of alert category vs MITRE tactic. Reveals how categories distribute across tactics.",
        ["filter", "comp", "sort", "limit", "alerts", "mitre"],
    ),
    (
        "investigation", "alerts",
        "Alerts with MITRE tactic unwound (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| filter mitre_attack_tactic != null\n| arrayexpand mitre_attack_tactic\n| comp count() as cnt by mitre_attack_tactic\n| sort desc cnt\n| limit 10",
        "Per-tactic alert count using arrayexpand for the multi-valued tactic field.",
        ["filter", "arrayexpand", "comp", "sort", "limit", "alerts", "mitre"],
    ),

    # ─── issues — corrected XDM paths ────────────────────────────
    (
        "investigation", "issues",
        "Issues by severity (7d)",
        "config timeframe = 7d\n| dataset = issues\n| comp count() as cnt by xdm.issue.severity\n| sort desc cnt\n| limit 10",
        "XDM-normalized severity distribution using `xdm.issue.severity` (the actual XDM path; xdm.alert.severity is the alerts-level path).",
        ["filter", "comp", "sort", "limit", "issues", "xdm"],
    ),
    (
        "investigation", "issues",
        "Top issue names (7d)",
        "config timeframe = 7d\n| dataset = issues\n| comp count() as cnt by xdm.issue.name\n| sort desc cnt\n| limit 10",
        "Top issue names via XDM-normalized schema (xdm.issue.name).",
        ["filter", "comp", "sort", "limit", "issues", "xdm"],
    ),
    (
        "investigation", "issues",
        "Issues by tactic via XDM (7d)",
        "config timeframe = 7d\n| dataset = issues\n| filter xdm.issue.mitre_tactics != null\n| arrayexpand xdm.issue.mitre_tactics\n| comp count() as cnt by xdm.issue.mitre_tactics\n| sort desc cnt\n| limit 10",
        "MITRE tactic distribution via the XDM schema (`xdm.issue.mitre_tactics`). Uses arrayexpand for multi-value flattening.",
        ["filter", "arrayexpand", "comp", "sort", "limit", "issues", "xdm", "mitre"],
    ),
    (
        "detection", "issues",
        "Critical issues with platform-severity (7d)",
        "config timeframe = 7d\n| dataset = issues\n| filter xdm.issue.severity = \"SEV_040_HIGH\" or xdm.issue.severity = \"SEV_050_CRITICAL\"\n| fields _time, xdm.issue.name, xdm.issue.severity, xdm.issue.platform_severity\n| sort desc _time\n| limit 10",
        "High/Critical XDM-normalized issues. XDM severity is `SEV_NNN_LABEL` strings — note the prefix when filtering.",
        ["filter", "fields", "sort", "limit", "issues", "xdm"],
    ),

    # ─── va_cves — corrected severity field ──────────────────────
    (
        "investigation", "va_cves",
        "Top 10 CVEs by affected-host count",
        "dataset = va_cves\n| filter affected_hosts_count != null\n| fields cve_id, severity, affected_hosts_count, severity_score, description\n| sort desc affected_hosts_count\n| limit 10",
        "Most-impacted CVEs by affected-host count. Uses the live tenant's `affected_hosts_count` field directly — no aggregation needed.",
        ["filter", "fields", "sort", "limit", "va_cves", "vulnerability"],
    ),
    (
        "investigation", "va_cves",
        "Critical CVEs in catalog",
        "dataset = va_cves\n| filter severity = \"CRITICAL\"\n| fields cve_id, severity, severity_score, description, publication_date\n| sort desc severity_score\n| limit 10",
        "Critical-severity CVEs sorted by CVSS-equivalent severity score. The `severity` field is plain string (CRITICAL/HIGH/MEDIUM/LOW).",
        ["filter", "fields", "sort", "limit", "va_cves", "vulnerability"],
    ),
    (
        "investigation", "va_cves",
        "CVEs by severity distribution",
        "dataset = va_cves\n| comp count() as cnt by severity\n| sort desc cnt\n| limit 10",
        "Snapshot of the tenant's CVE-catalog distribution by severity.",
        ["comp", "sort", "limit", "va_cves", "vulnerability"],
    ),
    (
        "detection", "va_cves",
        "CVEs by OS type",
        "dataset = va_cves\n| filter os_type != null\n| comp count() as cnt by os_type, severity\n| sort desc cnt\n| limit 10",
        "CVE distribution by OS type. Reveals OS-coverage of the vulnerability assessment.",
        ["filter", "comp", "sort", "limit", "va_cves", "vulnerability"],
    ),

    # ─── va_endpoints — only fields that exist ───────────────────
    (
        "investigation", "va_endpoints",
        "Top vulnerable endpoints by severity score",
        "dataset = va_endpoints\n| filter severity_score != null\n| fields endpoint_name, endpoint_type, os_type, severity, severity_score\n| sort desc severity_score\n| limit 10",
        "Endpoints ranked by computed severity_score. Uses only fields confirmed in the va_endpoints schema (endpoint_name, endpoint_type, os_type, severity, severity_score).",
        ["filter", "fields", "sort", "limit", "va_endpoints", "vulnerability"],
    ),
    (
        "investigation", "va_endpoints",
        "Endpoints with vulnerabilities by OS type",
        "dataset = va_endpoints\n| filter os_type != null\n| comp count() as endpoints, avg(severity_score) as avg_severity_score by os_type\n| sort desc endpoints\n| limit 10",
        "Vulnerable endpoint count + average severity per OS. Useful for OS-level patch-prioritization.",
        ["filter", "comp", "sort", "limit", "va_endpoints", "vulnerability"],
    ),

    # ─── endpoints — corrected field names ───────────────────────
    (
        "investigation", "endpoints",
        "Endpoint group distribution",
        "dataset = endpoints\n| filter group_names != null\n| arrayexpand group_names\n| comp count() as cnt by group_names\n| sort desc cnt\n| limit 10",
        "Endpoints aggregated by group via `group_names` (the live tenant's field name) using arrayexpand for multi-value flattening.",
        ["filter", "arrayexpand", "comp", "sort", "limit", "endpoints"],
    ),
    (
        "investigation", "endpoints",
        "Endpoints by tags",
        "dataset = endpoints\n| filter tags != null\n| arrayexpand tags\n| comp count() as cnt by tags\n| sort desc cnt\n| limit 10",
        "Endpoints aggregated by tag using the live tenant's `tags` field (the array of endpoint tags). Useful for tag-coverage audits.",
        ["filter", "arrayexpand", "comp", "sort", "limit", "endpoints"],
    ),
    (
        "investigation", "endpoints",
        "Endpoints with isolation enabled",
        "dataset = endpoints\n| filter endpoint_isolated = \"ISOLATED\"\n| fields endpoint_name, endpoint_status, operating_system, last_seen, ip_address\n| sort desc last_seen\n| limit 10",
        "Currently-isolated endpoints. `endpoint_isolated` is a string with values like NOT_ISOLATED / ISOLATED in this tenant — filter as string equality.",
        ["filter", "fields", "sort", "limit", "endpoints"],
    ),

    # ─── incidents — corrected field names ───────────────────────
    (
        "investigation", "incidents",
        "Incidents grouped by assigned operator (30d)",
        "config timeframe = 30d\n| dataset = incidents\n| filter assigned_user != null\n| comp count() as cnt by assigned_user, status\n| sort desc cnt\n| limit 10",
        "Per-operator workload distribution. Field is `assigned_user` in this tenant (not `assigned_user_pretty_name`).",
        ["filter", "comp", "sort", "limit", "incidents"],
    ),
    (
        "investigation", "incidents",
        "Incidents by total alert count + severity breakdown (7d)",
        "config timeframe = 7d\n| dataset = incidents\n| filter alert_count > 0\n| fields _time, incident_id, incident_name, alert_count, critical_severity_alert_count, high_severity_alert_count, severity, status\n| sort desc alert_count\n| limit 10",
        "Largest incidents by alert count + breakdown of critical/high. The dedicated severity-count fields (critical_severity_alert_count, high_severity_alert_count) are pre-aggregated in this schema.",
        ["filter", "fields", "sort", "limit", "incidents"],
    ),

    # ─── host_inventory — corrected field names ─────────────────
    (
        "investigation", "host_inventory",
        "Host inventory by OS type",
        "dataset = host_inventory\n| filter os_type != null\n| comp count() as cnt by os_type\n| sort desc cnt\n| limit 10",
        "Discovered host distribution by OS type. Field is `os_type` (not `operating_system_family`).",
        ["filter", "comp", "sort", "limit", "host_inventory"],
    ),
    (
        "investigation", "host_inventory",
        "Hosts by agent-domain membership",
        "dataset = host_inventory\n| filter agent_domain != null\n| comp count() as cnt by agent_domain\n| sort desc cnt\n| limit 10",
        "AD domain membership distribution. Field is `agent_domain` in this tenant.",
        ["filter", "comp", "sort", "limit", "host_inventory"],
    ),
    (
        "investigation", "host_inventory",
        "Hosts with OS caption (detailed OS string)",
        "dataset = host_inventory\n| filter os_caption != null\n| fields host_name, os_type, os_caption, agent_name, agent_domain\n| sort asc os_caption\n| limit 10",
        "Per-host OS detail using `os_caption` (the long-form OS name, e.g. 'Windows Server 2022'). Sorted alphabetically by OS string.",
        ["filter", "fields", "sort", "limit", "host_inventory"],
    ),

    # ─── asset_inventory — XDM schema ────────────────────────────
    (
        "investigation", "asset_inventory",
        "Assets by category (XDM)",
        "dataset = asset_inventory\n| filter xdm.asset.type.category != null\n| comp count() as cnt by xdm.asset.type.category\n| sort desc cnt\n| limit 10",
        "Asset distribution by category. asset_inventory uses XDM schema — category is `xdm.asset.type.category`.",
        ["filter", "comp", "sort", "limit", "asset_inventory", "xdm"],
    ),
    (
        "investigation", "asset_inventory",
        "Assets by provider (XDM)",
        "dataset = asset_inventory\n| filter xdm.asset.provider != null\n| comp count() as cnt by xdm.asset.provider, xdm.asset.realm\n| sort desc cnt\n| limit 10",
        "Asset count by cloud provider + realm via the XDM schema. Reveals multi-cloud distribution.",
        ["filter", "comp", "sort", "limit", "asset_inventory", "xdm", "cloud"],
    ),
    (
        "investigation", "asset_inventory",
        "Assets by class within category (XDM)",
        "dataset = asset_inventory\n| filter xdm.asset.type.class != null\n| comp count() as cnt by xdm.asset.type.category, xdm.asset.type.class\n| sort desc cnt\n| limit 10",
        "Hierarchical asset breakdown: category → class. XDM normalizes these as a 2-level taxonomy.",
        ["filter", "comp", "sort", "limit", "asset_inventory", "xdm"],
    ),
    (
        "investigation", "asset_inventory",
        "Recently-observed assets",
        "dataset = asset_inventory\n| filter xdm.asset.last_observed != null\n| fields xdm.asset.name, xdm.asset.type.category, xdm.asset.provider, xdm.asset.last_observed\n| sort desc xdm.asset.last_observed\n| limit 10",
        "Most-recently-observed assets. Useful for spotting newly-discovered or recently-active assets.",
        ["filter", "fields", "sort", "limit", "asset_inventory", "xdm"],
    ),

    # ─── Fixes — array-aggregation patterns ──────────────────────
    (
        "investigation", "alerts",
        "Alerts by initiator process (30d) — array-expanded",
        "config timeframe = 30d\n| dataset = alerts\n| filter initiator_path != null\n| arrayexpand initiator_path\n| comp count() as cnt by initiator_path, severity\n| sort desc cnt\n| limit 10",
        "Which initiator processes (the process that triggered the detection) generate the most alerts. `initiator_path` is an array — use arrayexpand before aggregation.",
        ["filter", "arrayexpand", "comp", "sort", "limit", "alerts"],
    ),
    (
        "investigation", "alerts",
        "Top affected users by critical alerts (30d) — array-expanded",
        "config timeframe = 30d\n| dataset = alerts\n| filter severity = \"CRITICAL\" and user_name != null\n| arrayexpand user_name\n| comp count() as alerts, count_distinct(alert_name) as unique_alert_types by user_name\n| sort desc alerts\n| limit 10",
        "Users with the most critical-severity alerts. `user_name` is array-typed — arrayexpand to enable aggregation.",
        ["filter", "arrayexpand", "comp", "sort", "limit", "alerts"],
    ),

    # ─── Fixes — time-arithmetic patterns ────────────────────────
    (
        "investigation", "xdr_data",
        "Process activity duration per host (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| comp min(_time) as first_seen, max(_time) as last_seen, count() as cnt by agent_hostname\n| alter duration_minutes = divide(timestamp_diff(last_seen, first_seen, \"MINUTE\"), 1)\n| sort desc cnt\n| limit 10",
        "Per-host first/last process time + active duration in minutes. Uses `timestamp_diff(end, start, unit)` for time arithmetic on date fields.",
        ["filter", "comp", "alter", "sort", "limit", "xdr_data", "process", "timestamp_diff"],
    ),
]


def main() -> None:
    print(f"v0.7.0 fix-up — re-validating {len(FIXES)} corrected queries")
    print(f"Starting at ID {START_ID}")
    print()

    successes: list[tuple[int, str]] = []
    failures: list[tuple[str, str]] = []
    next_id = START_ID

    for i, (category, dataset, title, query, when_to_use, tags) in enumerate(FIXES, 1):
        print(f"[{i:2d}/{len(FIXES)}] {category:14s} {dataset:20s} {title[:55]}")
        if not re.search(r"\|\s*limit\s+\d+\s*$", query, re.IGNORECASE):
            query = query.rstrip() + "\n| limit 10"

        t0 = time.time()
        try:
            result = run_xql(query, timeout=60)
            elapsed = time.time() - t0
        except Exception as exc:
            print(f"        TRANSPORT_ERR ({exc})")
            failures.append((title, f"transport: {exc}"))
            continue

        status = result.get("status", "?")
        rows = result.get("total_rows", 0)
        if status == "SUCCESS":
            print(f"        OK in {elapsed:.1f}s, {rows} rows")
            path = write_kb_entry(next_id, category, dataset, title,
                                  query, when_to_use, tags)
            successes.append((next_id, str(path.name)))
            next_id += 1
        else:
            err = result.get("error") or status
            err_str = str(err)[:200]
            print(f"        FAIL: {err_str}")
            failures.append((title, err_str))

    print()
    print(f"=" * 72)
    print(f"DONE: {len(successes)} new entries written, {len(failures)} still failing")
    print(f"=" * 72)
    if failures:
        print("\nStill-failing templates:")
        for title, err in failures:
            print(f"  ✗ {title[:60]} :: {err[:80]}")


if __name__ == "__main__":
    main()
