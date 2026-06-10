"""v0.7.0 complex queries pass 2 — retry transport-error cluster +
fix syntax issues identified by XDR response.

Findings from pass 1:
  - 13 queries hit transport-error cascade (agent stack hiccupped on
    rapid back-to-back queries; retry with sleep should clear them).
  - date_floor's 2nd arg is TIMEZONE not UNIT — use bin _time span
    instead, or use format_timestamp with "%Y-%m-%d".
  - transaction stage with no `fields` projection exceeded XDR's
    50-field cap — project fields first.
  - search stage must come AFTER dataset, not before.
  - replacenull syntax is different — `replacenull <field> = <value>`
    not `replacenull value = X fields`.
  - join `on` clause needs equality form `a = b` only.
  - view highlight has different syntax — no `=` inside fields/values.
  - stddev + percentile aren't standard XQL — use avg + comp values.
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


START_ID = 833 + 11  # pass 1 wrote 11 entries (833-843); pass 2 starts at 844


PASS_2: list[tuple[str, str, str, str, str, list[str]]] = [
    # ─── Retries of transport-error templates (unchanged) ───────
    (
        "investigation", "endpoints",
        "Endpoints with server-tag count (JSON tags)",
        "dataset = endpoints\n| filter tags != null\n| alter server_tags = json_extract_array(tags, \"$.server_tags\")\n| alter tag_count = array_length(server_tags)\n| filter tag_count > 0\n| fields endpoint_name, server_tags, tag_count\n| sort desc tag_count\n| limit 10",
        "Per-endpoint server-tag inventory. Uses `json_extract_array` to pull the nested array, then `array_length` to count tags per endpoint.",
        ["filter", "alter", "fields", "sort", "limit", "endpoints", "json_extract_array", "array_length"],
    ),
    (
        "investigation", "xdr_data",
        "Hosts with their unique processes as CSV (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| comp values(action_process_image_name) as procs by agent_hostname\n| alter unique_procs = arraydistinct(procs)\n| alter procs_csv = arraystring(unique_procs, \", \")\n| alter proc_count = array_length(unique_procs)\n| fields agent_hostname, proc_count, procs_csv\n| sort desc proc_count\n| limit 10",
        "Per-host unique-process inventory as a CSV string. Chains values → arraydistinct → arraystring for serialization.",
        ["filter", "comp", "alter", "fields", "sort", "limit", "xdr_data", "process", "arraydistinct", "arraystring"],
    ),
    (
        "detection", "xdr_data",
        "Process activity heat-map by hour-of-day (24h, extract_time)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| alter hour = extract_time(_time, \"HOUR\")\n| comp count() as executions by hour, agent_hostname\n| sort asc agent_hostname, asc hour\n| limit 10",
        "Per-host hour-of-day execution heat map. `extract_time(timestamp, 'HOUR')` returns the hour component (0-23). Off-hours activity is a compromise indicator.",
        ["filter", "alter", "comp", "sort", "limit", "xdr_data", "process", "extract_time"],
    ),
    (
        "investigation", "endpoints",
        "Endpoints with formatted summary string (format_string)",
        "dataset = endpoints\n| filter endpoint_status != null\n| alter summary = format_string(\"%s (%s) - %s\", endpoint_name, operating_system, endpoint_status)\n| fields summary, last_seen, agent_version\n| sort desc last_seen\n| limit 10",
        "Per-endpoint composed summary line via `format_string(\"%s (%s) - %s\", ...)`. Useful for one-line display in reports / chat output.",
        ["filter", "alter", "fields", "sort", "limit", "endpoints", "format_string"],
    ),
    (
        "investigation", "xdr_data",
        "Process command-line backslash count (24h, string_count)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| filter action_process_image_command_line != null\n| alter backslash_count = string_count(action_process_image_command_line, \"\\\\\\\\\")\n| filter backslash_count > 5\n| fields _time, agent_hostname, action_process_image_name, backslash_count, action_process_image_command_line\n| sort desc backslash_count\n| limit 10",
        "Surfaces command lines with many backslashes — often indicates deep file-path args or obfuscation. `string_count(field, substring)` returns the count.",
        ["filter", "alter", "fields", "sort", "limit", "xdr_data", "process", "string_count"],
    ),
    (
        "investigation", "xdr_data",
        "Strip .exe suffix from process names for grouping (24h, replace)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| alter proc_root = lowercase(replace(action_process_image_name, \".exe\", \"\"))\n| comp count() as cnt by proc_root\n| sort desc cnt\n| limit 10",
        "Aggregate process executions by name without the .exe suffix — useful for cross-OS aggregation (Linux/macOS don't have the suffix). Uses `replace(field, old, new)`.",
        ["filter", "alter", "comp", "sort", "limit", "xdr_data", "process", "replace"],
    ),
    (
        "investigation", "alerts",
        "Alerts with severity-based action label (7d, if)",
        "config timeframe = 7d\n| dataset = alerts\n| alter action_needed = if(severity = \"CRITICAL\", \"immediate-page\", if(severity = \"HIGH\", \"same-day\", if(severity = \"MEDIUM\", \"next-business-day\", \"backlog\")))\n| comp count() as cnt by action_needed\n| sort desc cnt\n| limit 10",
        "Maps each alert to an SLA action label via nested `if()`. Useful for SLA reporting + operator-facing dashboards.",
        ["filter", "alter", "comp", "sort", "limit", "alerts", "if", "conditional"],
    ),
    (
        "detection", "xdr_data",
        "Top 3 ranked processes per host (rank, 24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| comp count() as cnt by agent_hostname, action_process_image_name\n| windowcomp rank() by agent_hostname sort desc cnt as proc_rank\n| filter proc_rank <= 3\n| sort asc agent_hostname, asc proc_rank\n| limit 10",
        "Top-3 processes PER HOST using `rank()`. Handles ties unlike `row_number()`. Canonical top-N-per-group idiom.",
        ["filter", "comp", "windowcomp", "sort", "limit", "xdr_data", "process", "rank"],
    ),
    (
        "detection", "xdr_data",
        "Time gap between successive process events per user (lag, 7d)",
        "config timeframe = 7d\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START and actor_effective_username != null\n| windowcomp lag(_time) by actor_effective_username sort asc _time as prev_time\n| filter prev_time != null\n| alter gap_seconds = divide(timestamp_diff(_time, prev_time, \"SECOND\"), 1)\n| filter gap_seconds < 5\n| fields _time, actor_effective_username, agent_hostname, action_process_image_name, gap_seconds\n| sort asc gap_seconds\n| limit 10",
        "Successive process executions within 5s of the previous by the same user. `lag()` returns the prior row in the partition. Burst-detection without `transaction`.",
        ["filter", "windowcomp", "alter", "fields", "sort", "limit", "xdr_data", "process", "lag"],
    ),
    (
        "investigation", "xdr_data",
        "First + last process per host (first_value/last_value, 24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| windowcomp first_value(action_process_image_name) by agent_hostname sort asc _time as first_proc\n| windowcomp last_value(action_process_image_name) by agent_hostname sort asc _time as last_proc\n| dedup agent_hostname\n| fields agent_hostname, first_proc, last_proc\n| sort asc agent_hostname\n| limit 10",
        "Per-host first + last process names of the day via window functions. `dedup` collapses to one row per host.",
        ["filter", "windowcomp", "dedup", "fields", "sort", "limit", "xdr_data", "process", "first_value", "last_value"],
    ),
    (
        "investigation", "xdr_data",
        "Median upload bytes per host (24h, median)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK and action_total_upload > 0\n| comp median(action_total_upload) as median_bytes, avg(action_total_upload) as avg_bytes, count() as conn_count by agent_hostname\n| sort desc median_bytes\n| limit 10",
        "Per-host MEDIAN upload bytes (more robust to outliers than avg). Median vs avg: close = uniform; median much less than avg = skewed by a few large outliers.",
        ["filter", "comp", "sort", "limit", "xdr_data", "network", "median"],
    ),
    (
        "investigation", "alerts",
        "First + last alert per host (7d, earliest/latest)",
        "config timeframe = 7d\n| dataset = alerts\n| filter host_name != null\n| comp earliest(alert_name) as first_alert, latest(alert_name) as last_alert, count() as alert_count by host_name\n| sort desc alert_count\n| limit 10",
        "Per-host first + last alert names via `earliest()` + `latest()` aggregation. Cleaner than windowcomp+dedup when you also want a row count.",
        ["filter", "comp", "sort", "limit", "alerts", "earliest", "latest"],
    ),
    (
        "investigation", "xdr_data",
        "Upload bytes KB-bucketed (24h, floor + divide)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK and action_total_upload > 0\n| alter kb_bucket = floor(divide(action_total_upload, 1000))\n| comp count() as cnt by kb_bucket\n| sort desc cnt\n| limit 10",
        "KB-bucketed upload byte distribution. `floor(divide(bytes, 1000))` truncates to KB. Useful for histogram-style upload-size profiling.",
        ["filter", "alter", "comp", "sort", "limit", "xdr_data", "network", "floor", "math"],
    ),

    # ─── Syntax-corrected templates ─────────────────────────────
    (
        "investigation", "alerts",
        "Keyword search across alert fields (7d, search stage)",
        "config timeframe = 7d\n| dataset = alerts\n| search \"powershell\"\n| fields _time, host_name, alert_name, severity, description\n| sort desc _time\n| limit 10",
        "Free-text keyword search across all indexed alert fields. The `search` stage must come AFTER `dataset = ...`. Different from `filter`, which requires a specific field.",
        ["filter", "search", "fields", "sort", "limit", "alerts"],
    ),
    (
        "investigation", "alerts",
        "Alerts with category null → \"unknown\" (7d, replacenull)",
        "config timeframe = 7d\n| dataset = alerts\n| replacenull category = \"unknown\"\n| replacenull host_name = \"unknown\"\n| comp count() as cnt by category, host_name\n| sort desc cnt\n| limit 10",
        "Replaces nulls in named fields with literal defaults BEFORE aggregation. The `replacenull <field> = <value>` syntax — one statement per field. Cleans sparse fields so they aggregate into a visible bucket instead of being dropped.",
        ["filter", "replacenull", "comp", "sort", "limit", "alerts"],
    ),
    (
        "investigation", "alerts",
        "Alerts per day via format_timestamp (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| alter day_bucket = format_timestamp(\"%Y-%m-%d\", _time)\n| comp count() as cnt by day_bucket, severity\n| sort desc day_bucket\n| limit 10",
        "Daily alert count per severity using `format_timestamp(\"%Y-%m-%d\", _time)` for day-precision string buckets. Alternative to `bin _time span = 1d` when you want ISO-date strings in the output.",
        ["filter", "alter", "comp", "sort", "limit", "alerts", "format_timestamp"],
    ),
    (
        "detection", "xdr_data",
        "Script-host process chains via transaction with field projection (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| filter lowercase(action_process_image_name) in (\"powershell.exe\", \"cmd.exe\", \"wscript.exe\", \"cscript.exe\", \"bash\", \"sh\", \"python3\", \"python.exe\")\n| fields _time, agent_hostname, action_process_image_name\n| transaction agent_hostname span = 5m\n| sort desc _time\n| limit 10",
        "Groups script-host process events on the same host into 5-minute transactions. CRITICAL: project fields with `fields` BEFORE `transaction` — the stage caps at 50 fields per row, so unprojected xdr_data rows (with ~150 fields) overflow.",
        ["filter", "fields", "transaction", "sort", "limit", "xdr_data", "process"],
    ),
    (
        "investigation", "alerts",
        "Alerts joined with endpoint OS (7d, join with explicit field aliases)",
        "config timeframe = 7d\n| dataset = alerts\n| filter host_name != null\n| comp count() as alert_count by host_name, severity\n| join type=left (dataset = endpoints | fields endpoint_name, operating_system, agent_version) as ep host_name = ep.endpoint_name\n| fields host_name, severity, alert_count, ep.operating_system, ep.agent_version\n| sort desc alert_count\n| limit 10",
        "Alerts enriched with endpoint OS via `join` — the syntax is `join type=left (subquery) as ALIAS <left_field> = <ALIAS>.<right_field>` (NO `on` keyword in this dialect).",
        ["filter", "comp", "join", "fields", "sort", "limit", "alerts", "endpoints"],
    ),
    (
        "investigation", "alerts",
        "Critical alerts highlighted via view stage (7d)",
        "config timeframe = 7d\n| dataset = alerts\n| filter severity in (\"HIGH\", \"CRITICAL\")\n| fields _time, host_name, alert_name, severity\n| view rename _time as alert_time\n| sort desc alert_time\n| limit 10",
        "Demonstrates the `view rename` stage — renames an output column without alter copying. `view` has multiple operations: `rename`, `change` (datatype), `mark` (categorical labels). Useful for cleaning up output column names before reporting.",
        ["filter", "fields", "view", "sort", "limit", "alerts"],
    ),
]


def main() -> None:
    print(f"v0.7.0 complex pass 2 — retrying + fixing {len(PASS_2)} queries")
    print(f"Starting at ID {START_ID}")
    print("(2s sleep between queries to avoid cascade-failure)")
    print()

    successes = []
    failures = []
    next_id = START_ID

    for i, (category, dataset, title, query, when_to_use, tags) in enumerate(PASS_2, 1):
        print(f"[{i:2d}/{len(PASS_2)}] {category:14s} {dataset:20s} {title[:55]}")
        if not re.search(r"\|\s*limit\s+\d+\s*$", query, re.IGNORECASE):
            query = query.rstrip() + "\n| limit 10"

        t0 = time.time()
        try:
            result = run_xql(query, timeout=90)
            elapsed = time.time() - t0
        except Exception as exc:
            print(f"        TRANSPORT_ERR ({exc})")
            failures.append((title, f"transport: {exc}"))
            time.sleep(3)  # back off on transport failure
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
            err_str = str(err)[:250]
            print(f"        FAIL: {err_str}")
            failures.append((title, err_str))

        time.sleep(2)  # rate-limit ourselves to avoid agent overload

    print()
    print(f"=" * 72)
    print(f"PASS 2 DONE: {len(successes)} new entries written, {len(failures)} failed")
    print(f"=" * 72)
    if failures:
        for title, err in failures:
            print(f"  ✗ {title[:60]} :: {err[:120]}")


if __name__ == "__main__":
    main()
