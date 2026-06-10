"""v0.7.0 fix-up pass 2 — handle the remaining 5 failures from pass 1.

Findings from the 2nd round of schema probes:
  - incidents:    `name` (not `incident_name`); also has
                  `mitre_tactics_id_and_name` + `mitre_techniques_id_and_name`
                  parallel to the alerts dataset's mitre fields but
                  named differently here.
  - va_cves:      `os_type` IS an array; arrayexpand works.
  - endpoints:    `tags` is a JSON STRING with `server_tags` +
                  `endpoint_tags` subarrays — not a flat array.
                  Need json_extract_array to access.
  - alerts:       `mitre_attack_tactic` is NOT an array; drop the
                  arrayexpand.
  - issues:       `xdm.issue.mitre_tactics` is NOT an array; drop
                  arrayexpand.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_100_queries import (  # type: ignore[import-not-found]
    run_xql,
    write_kb_entry,
)


# Continue from where pass 1 left off
# 95 (pass 0) + 28 (pass 1) = 123, so pass 2 starts at 700 + 123 = 823
START_ID = 700 + 95 + 28


FIXES_PASS_2: list[tuple[str, str, str, str, str, list[str]]] = [
    # ─── Issues #1+#2: drop arrayexpand for scalar mitre fields ─
    (
        "investigation", "alerts",
        "Alerts by MITRE tactic (30d) — scalar field",
        "config timeframe = 30d\n| dataset = alerts\n| filter mitre_attack_tactic != null\n| comp count() as cnt by mitre_attack_tactic\n| sort desc cnt\n| limit 10",
        "Per-tactic alert distribution. `mitre_attack_tactic` is a scalar string in this tenant — direct aggregation works, no arrayexpand needed.",
        ["filter", "comp", "sort", "limit", "alerts", "mitre"],
    ),
    (
        "investigation", "issues",
        "Issues by MITRE tactic via XDM (7d) — scalar field",
        "config timeframe = 7d\n| dataset = issues\n| filter xdm.issue.mitre_tactics != null\n| comp count() as cnt by xdm.issue.mitre_tactics\n| sort desc cnt\n| limit 10",
        "XDM-normalized MITRE tactic distribution. `xdm.issue.mitre_tactics` is a scalar string in this tenant; aggregate directly without arrayexpand.",
        ["filter", "comp", "sort", "limit", "issues", "xdm", "mitre"],
    ),

    # ─── CVEs by OS type — arrayexpand os_type FIRST ────────────
    (
        "detection", "va_cves",
        "CVEs by OS type (array-expanded)",
        "dataset = va_cves\n| filter os_type != null\n| arrayexpand os_type\n| comp count() as cnt by os_type, severity\n| sort desc cnt\n| limit 10",
        "CVE distribution by OS type. `os_type` in va_cves is an array (a CVE can affect multiple OS families); arrayexpand flattens before aggregation.",
        ["filter", "arrayexpand", "comp", "sort", "limit", "va_cves", "vulnerability"],
    ),

    # ─── Endpoints tags — extract nested JSON ────────────────────
    (
        "investigation", "endpoints",
        "Endpoints by server-tag (JSON-extracted)",
        "dataset = endpoints\n| filter tags != null\n| alter server_tags = json_extract_array(tags, \"$.server_tags\")\n| filter server_tags != null\n| arrayexpand server_tags\n| comp count() as cnt by server_tags\n| sort desc cnt\n| limit 10",
        "Endpoint server-tag distribution. The `tags` field is a JSON string with `server_tags` + `endpoint_tags` subarrays. Uses `json_extract_array` to pull the nested array.",
        ["filter", "alter", "arrayexpand", "comp", "sort", "limit", "endpoints", "json_extract"],
    ),

    # ─── Incidents — correct field name + add mitre coverage ────
    (
        "investigation", "incidents",
        "Largest incidents by alert count (7d)",
        "config timeframe = 7d\n| dataset = incidents\n| filter alert_count > 0\n| fields _time, incident_id, name, alert_count, critical_severity_alert_count, high_severity_alert_count, severity, status\n| sort desc alert_count\n| limit 10",
        "Largest incidents by alert count + breakdown of critical/high. Field is `name` in this tenant (not `incident_name`).",
        ["filter", "fields", "sort", "limit", "incidents"],
    ),
    (
        "investigation", "incidents",
        "Incidents by MITRE tactic (30d)",
        "config timeframe = 30d\n| dataset = incidents\n| filter mitre_tactics_id_and_name != null\n| comp count() as cnt by mitre_tactics_id_and_name\n| sort desc cnt\n| limit 10",
        "MITRE tactic distribution at the incident level. Field is `mitre_tactics_id_and_name` for incidents (alerts uses `mitre_attack_tactic` — parallel schemas, different naming).",
        ["filter", "comp", "sort", "limit", "incidents", "mitre"],
    ),
    (
        "investigation", "incidents",
        "Aggregated incident score distribution (30d)",
        "config timeframe = 30d\n| dataset = incidents\n| filter aggregated_score != null\n| comp count() as cnt, avg(aggregated_score) as avg_score, max(aggregated_score) as max_score by severity\n| sort desc max_score\n| limit 10",
        "Per-severity incident score statistics (avg + max). aggregated_score is XSIAM's composite incident-risk score.",
        ["filter", "comp", "sort", "limit", "incidents"],
    ),

    # ─── Bonus: alert_categories array on incidents ─────────────
    (
        "investigation", "incidents",
        "Incidents by alert-category (30d) — array-expanded",
        "config timeframe = 30d\n| dataset = incidents\n| filter alert_categories != null\n| arrayexpand alert_categories\n| comp count() as cnt by alert_categories\n| sort desc cnt\n| limit 10",
        "Per-alert-category incident distribution. `alert_categories` is an array of categories from the constituent alerts.",
        ["filter", "arrayexpand", "comp", "sort", "limit", "incidents"],
    ),
    (
        "investigation", "incidents",
        "Incidents by alert-source (30d) — array-expanded",
        "config timeframe = 30d\n| dataset = incidents\n| filter alert_sources != null\n| arrayexpand alert_sources\n| comp count() as cnt by alert_sources\n| sort desc cnt\n| limit 10",
        "Per-detection-source incident distribution. `alert_sources` array from constituent alerts.",
        ["filter", "arrayexpand", "comp", "sort", "limit", "incidents"],
    ),
]


def main() -> None:
    print(f"v0.7.0 fix-up pass 2 — re-validating {len(FIXES_PASS_2)} corrected queries")
    print(f"Starting at ID {START_ID}")
    print()

    successes = []
    failures = []
    next_id = START_ID

    for i, (category, dataset, title, query, when_to_use, tags) in enumerate(FIXES_PASS_2, 1):
        print(f"[{i:2d}/{len(FIXES_PASS_2)}] {category:14s} {dataset:20s} {title[:55]}")
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
    print(f"PASS 2 DONE: {len(successes)} new entries written, {len(failures)} still failing")
    print(f"=" * 72)
    if failures:
        for title, err in failures:
            print(f"  ✗ {title[:60]} :: {err[:80]}")


if __name__ == "__main__":
    main()
