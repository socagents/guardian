"""v0.7.0 extension — complex XQL queries showcasing advanced
stages + functions discovered from the Cortex XQL docs.

Gaps the prior 132 entries didn't cover well:
  - iploc           (IP → geolocation enrichment)
  - arraymap        (per-element predicate)
  - arrayfilter     (sub-array filtering)
  - arraystring     (join → CSV)
  - arraydistinct   (deduplicate arrays)
  - json_extract_scalar / json_extract (nested JSON)
  - format_string   (printf-like)
  - replace         (substring replace)
  - string_count    (substring count)
  - extract_time    (HOUR/MINUTE/DAY part)
  - to_epoch        (timestamp → epoch)
  - parse_timestamp (string → timestamp)
  - date_floor      (truncate to unit)
  - pow / round / floor (math)
  - incidrlist / ip_to_int / int_to_ip (network)
  - rank / lag / first_value / last_value (window-comp variants)
  - median / list / earliest / latest (aggregation variants)
  - replacenull     (stage — null → literal)
  - search          (stage — keyword across all fields)

Each query is hand-curated, validated against the live tenant +
written as a KB entry on SUCCESS. IDs start at 833 (continues from
the v0.7.0 first-pass range 700-832).
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


START_ID = 833


COMPLEX: list[tuple[str, str, str, str, str, list[str]]] = [

    # ─── iploc — geolocation enrichment ──────────────────────────
    (
        "investigation", "xdr_data",
        "Top remote IPs enriched with geolocation (24h, iploc)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK and action_remote_ip != null\n| filter not incidr(action_remote_ip, \"10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16\")\n| comp count() as connections, sum(action_total_upload) as upload by action_remote_ip\n| sort desc connections\n| iploc action_remote_ip loc_country, loc_city, loc_region\n| fields action_remote_ip, loc_country, loc_city, loc_region, connections, upload\n| limit 10",
        "External destinations enriched with country/city/region via the `iploc` stage. The geolocation columns (loc_country, loc_city, loc_region, loc_latlon, loc_timezone) are auto-added by iploc — no setup needed. Useful for surfacing unexpected geographies in outbound traffic.",
        ["filter", "comp", "sort", "iploc", "fields", "limit", "xdr_data", "network", "geo"],
    ),
    (
        "detection", "xdr_data",
        "Outbound connections from unusual countries (24h, iploc)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK and action_remote_ip != null\n| filter not incidr(action_remote_ip, \"10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8\")\n| iploc action_remote_ip loc_country\n| comp count() as connections, count_distinct(agent_hostname) as hosts by loc_country\n| sort desc connections\n| limit 10",
        "Per-country connection count + unique-host count. Useful for spotting unexpected countries in the traffic mix (could indicate compromised egress, VPN routing changes, or attacker C2 in foreign jurisdictions).",
        ["filter", "iploc", "comp", "sort", "limit", "xdr_data", "network", "geo"],
    ),

    # ─── arraymap + arrayfilter — per-element predicates ────────
    (
        "investigation", "endpoints",
        "Endpoints with server-tag count via arraymap (JSON tags)",
        "dataset = endpoints\n| filter tags != null\n| alter server_tags = json_extract_array(tags, \"$.server_tags\")\n| alter tag_count = array_length(server_tags)\n| filter tag_count > 0\n| fields endpoint_name, server_tags, tag_count\n| sort desc tag_count\n| limit 10",
        "Per-endpoint server-tag inventory. Uses `json_extract_array` to pull the nested array, then `array_length` to count tags per endpoint. Endpoints with many tags often have rich metadata; zero-tag endpoints may need labeling.",
        ["filter", "alter", "fields", "sort", "limit", "endpoints", "json_extract_array", "array_length"],
    ),

    # ─── arraystring + arraydistinct — CSV joining ──────────────
    (
        "investigation", "xdr_data",
        "Hosts with their unique processes as CSV (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| comp values(action_process_image_name) as procs by agent_hostname\n| alter unique_procs = arraydistinct(procs)\n| alter procs_csv = arraystring(unique_procs, \", \")\n| alter proc_count = array_length(unique_procs)\n| fields agent_hostname, proc_count, procs_csv\n| sort desc proc_count\n| limit 10",
        "Per-host unique-process inventory as a comma-separated string. Chains `values()` aggregation → `arraydistinct` → `arraystring` for CSV serialization. Ideal for whitelist generation + per-host snapshot reports.",
        ["filter", "comp", "alter", "fields", "sort", "limit", "xdr_data", "process", "arraydistinct", "arraystring"],
    ),

    # ─── extract_time + format_timestamp — hour-of-day ──────────
    (
        "detection", "xdr_data",
        "Process activity heat-map by hour-of-day (24h, extract_time)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| alter hour = extract_time(_time, \"HOUR\")\n| comp count() as executions by hour, agent_hostname\n| sort asc agent_hostname, asc hour\n| limit 10",
        "Per-host hour-of-day execution heat map. Uses `extract_time(timestamp, 'HOUR')` to get the hour component (0-23). Off-hours activity by interactive users is a compromise indicator.",
        ["filter", "alter", "comp", "sort", "limit", "xdr_data", "process", "extract_time"],
    ),

    # ─── format_string + concat — text formatting ───────────────
    (
        "investigation", "endpoints",
        "Endpoints with formatted summary string",
        "dataset = endpoints\n| filter endpoint_status != null\n| alter summary = format_string(\"%s (%s) - %s\", endpoint_name, operating_system, endpoint_status)\n| fields summary, last_seen, agent_version\n| sort desc last_seen\n| limit 10",
        "Per-endpoint composed summary line using `format_string(\"%s (%s) - %s\", ...)`. Useful for one-line displays in reports / chat output where you want a single column instead of multi-column raw fields.",
        ["filter", "alter", "fields", "sort", "limit", "endpoints", "format_string"],
    ),

    # ─── replace + string_count — text cleaning + measuring ─────
    (
        "investigation", "xdr_data",
        "Process command-line backslash count (24h, string_count)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| filter action_process_image_command_line != null\n| alter backslash_count = string_count(action_process_image_command_line, \"\\\\\\\\\")\n| filter backslash_count > 5\n| fields _time, agent_hostname, action_process_image_name, backslash_count, action_process_image_command_line\n| sort desc backslash_count\n| limit 10",
        "Surfaces command lines with many backslashes — often indicates deep file-path arguments or obfuscation with extra escapes. `string_count(field, substring)` returns the count.",
        ["filter", "alter", "fields", "sort", "limit", "xdr_data", "process", "string_count"],
    ),
    (
        "investigation", "xdr_data",
        "Strip .exe suffix from process names for grouping (24h, replace)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| alter proc_root = lowercase(replace(action_process_image_name, \".exe\", \"\"))\n| comp count() as cnt by proc_root\n| sort desc cnt\n| limit 10",
        "Aggregate process executions by name without the .exe suffix. Useful for cross-OS aggregation (Linux + macOS variants don't have the suffix). Uses `replace(field, old, new)`.",
        ["filter", "alter", "comp", "sort", "limit", "xdr_data", "process", "replace"],
    ),

    # ─── if / coalesce — conditional logic ──────────────────────
    (
        "investigation", "alerts",
        "Alerts with severity-based action label (7d, if)",
        "config timeframe = 7d\n| dataset = alerts\n| alter action_needed = if(severity = \"CRITICAL\", \"immediate-page\", if(severity = \"HIGH\", \"same-day\", if(severity = \"MEDIUM\", \"next-business-day\", \"backlog\")))\n| comp count() as cnt by action_needed\n| sort desc cnt\n| limit 10",
        "Maps each alert to an SLA action label via nested `if()`. Useful for SLA reporting + operator-facing dashboards where the action is more meaningful than the raw severity.",
        ["filter", "alter", "comp", "sort", "limit", "alerts", "if", "conditional"],
    ),

    # ─── window functions — rank, lag, first_value, last_value ─
    (
        "detection", "xdr_data",
        "Top 3 ranked processes per host (rank, 24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| comp count() as cnt by agent_hostname, action_process_image_name\n| windowcomp rank() by agent_hostname sort desc cnt as proc_rank\n| filter proc_rank <= 3\n| sort asc agent_hostname, asc proc_rank\n| limit 10",
        "Top-3 processes PER HOST using `rank()`. Unlike `row_number()`, rank() handles ties identically. The pattern `partition + sort + rank + filter` is the canonical top-N-per-group idiom.",
        ["filter", "comp", "windowcomp", "sort", "limit", "xdr_data", "process", "rank"],
    ),
    (
        "detection", "xdr_data",
        "Time gap between successive logins per user (lag, 7d)",
        "config timeframe = 7d\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START and actor_effective_username != null\n| windowcomp lag(_time) by actor_effective_username sort asc _time as prev_time\n| filter prev_time != null\n| alter gap_seconds = divide(timestamp_diff(_time, prev_time, \"SECOND\"), 1)\n| filter gap_seconds < 5\n| fields _time, actor_effective_username, agent_hostname, action_process_image_name, gap_seconds\n| sort asc gap_seconds\n| limit 10",
        "Successive process executions within 5s of the previous by the same user. `lag()` window function returns the prior row's value within the partition. Useful for burst-detection without `transaction`.",
        ["filter", "windowcomp", "alter", "fields", "sort", "limit", "xdr_data", "process", "lag"],
    ),
    (
        "investigation", "xdr_data",
        "First + last process per host (first_value/last_value, 24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| windowcomp first_value(action_process_image_name) by agent_hostname sort asc _time as first_proc\n| windowcomp last_value(action_process_image_name) by agent_hostname sort asc _time as last_proc\n| dedup agent_hostname\n| fields agent_hostname, first_proc, last_proc\n| sort asc agent_hostname\n| limit 10",
        "Per-host first + last process names of the day using `first_value` + `last_value` window functions. The `dedup` collapses to one row per host. Useful for fingerprinting startup/shutdown sequences.",
        ["filter", "windowcomp", "dedup", "fields", "sort", "limit", "xdr_data", "process", "first_value", "last_value"],
    ),

    # ─── median + list — aggregation variants ───────────────────
    (
        "investigation", "xdr_data",
        "Median upload bytes per host (24h, median)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK and action_total_upload > 0\n| comp median(action_total_upload) as median_bytes, avg(action_total_upload) as avg_bytes, count() as conn_count by agent_hostname\n| sort desc median_bytes\n| limit 10",
        "Per-host MEDIAN upload bytes (more robust to outliers than `avg`). The median + average together give shape: median close to average means uniform; median much less than average means a few large outliers dominate.",
        ["filter", "comp", "sort", "limit", "xdr_data", "network", "median"],
    ),

    # ─── earliest + latest — chronological aggregation ──────────
    (
        "investigation", "alerts",
        "First + last alert per host with details (7d, earliest/latest)",
        "config timeframe = 7d\n| dataset = alerts\n| filter host_name != null\n| comp earliest(alert_name) as first_alert, latest(alert_name) as last_alert, count() as alert_count by host_name\n| sort desc alert_count\n| limit 10",
        "Per-host first + last alert names via `earliest()` + `latest()` aggregation. Cleaner than the windowcomp+dedup pattern when you also want a row count.",
        ["filter", "comp", "sort", "limit", "alerts", "earliest", "latest"],
    ),

    # ─── math — pow / round / floor ─────────────────────────────
    (
        "investigation", "xdr_data",
        "Upload bytes log-scale buckets (24h, pow + floor)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK and action_total_upload > 0\n| alter log_bucket = floor(divide(action_total_upload, 1000))\n| comp count() as cnt by log_bucket\n| sort desc cnt\n| limit 10",
        "KB-bucketed upload byte distribution. `floor(divide(bytes, 1000))` truncates to KB. Useful for histogram-style upload-size profiling.",
        ["filter", "alter", "comp", "sort", "limit", "xdr_data", "network", "floor", "math"],
    ),
    (
        "investigation", "xdr_data",
        "Round-to-100 normalized command-line lengths (24h, round)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START and action_process_image_command_line != null\n| alter cmd_len = len(action_process_image_command_line)\n| alter len_bucket = multiply(round(divide(cmd_len, 100)), 100)\n| comp count() as cnt by len_bucket\n| sort desc cnt\n| limit 10",
        "Process command-line lengths bucketed to nearest 100 chars. `round + divide + multiply` chains together for clean rounding. Histogram pattern adaptable to other numeric fields.",
        ["filter", "alter", "comp", "sort", "limit", "xdr_data", "process", "round", "math"],
    ),

    # ─── network — ip_to_int + incidrlist ───────────────────────
    (
        "investigation", "xdr_data",
        "Network destinations sortable by IP-integer order (24h, ip_to_int)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK and action_remote_ip != null\n| filter not incidr(action_remote_ip, \"10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16\")\n| comp count() as connections by action_remote_ip\n| alter ip_int = ip_to_int(action_remote_ip)\n| sort asc ip_int\n| limit 10",
        "External IPs sorted in numerical (IP-integer) order. `ip_to_int(ipv4)` converts to a 32-bit integer for proper sorting. Useful for range-based analysis + identifying nearby IPs in the same subnet.",
        ["filter", "comp", "alter", "sort", "limit", "xdr_data", "network", "ip_to_int"],
    ),

    # ─── search stage — keyword across all fields ───────────────
    (
        "investigation", "alerts",
        "Keyword search across all alert fields (7d, search stage)",
        "config timeframe = 7d\n| search \"powershell\"\n| dataset = alerts\n| fields _time, host_name, alert_name, severity, description\n| sort desc _time\n| limit 10",
        "Free-text keyword search across all indexed fields. The `search` stage is keyword-matching at the data lake layer — different from `filter` which requires a field. Useful for triage-style 'show me anything mentioning X' queries.",
        ["search", "filter", "fields", "sort", "limit", "alerts"],
    ),

    # ─── replacenull stage — null → default ─────────────────────
    (
        "investigation", "alerts",
        "Alerts with category null→\"unknown\" (7d, replacenull)",
        "config timeframe = 7d\n| dataset = alerts\n| replacenull value = \"unknown\" category, host_name\n| comp count() as cnt by category, host_name\n| sort desc cnt\n| limit 10",
        "Replaces null values in `category` + `host_name` with the literal 'unknown' before aggregation. The `replacenull` stage cleans up sparse fields so they aggregate into a visible 'unknown' bucket instead of being dropped.",
        ["filter", "replacenull", "comp", "sort", "limit", "alerts"],
    ),

    # ─── json_extract_scalar — nested object access ─────────────
    (
        "investigation", "endpoints",
        "Endpoints with endpoint-tags JSON sub-count",
        "dataset = endpoints\n| filter tags != null\n| alter endpoint_tag_count = array_length(json_extract_array(tags, \"$.endpoint_tags\"))\n| alter server_tag_count = array_length(json_extract_array(tags, \"$.server_tags\"))\n| filter endpoint_tag_count > 0 or server_tag_count > 0\n| fields endpoint_name, endpoint_tag_count, server_tag_count\n| sort desc endpoint_tag_count\n| limit 10",
        "Endpoint vs server tag counts per host. The `tags` field is JSON with both arrays nested; `json_extract_array` + `array_length` gets the per-subarray count.",
        ["filter", "alter", "fields", "sort", "limit", "endpoints", "json_extract_array", "array_length"],
    ),

    # ─── compound — multi-stage detection patterns ──────────────
    (
        "detection", "xdr_data",
        "Burst then quiet — processes with high count then gap (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| bin _time span = 1h\n| comp count() as exec_count by _time, agent_hostname\n| windowcomp lag(exec_count) by agent_hostname sort asc _time as prev_hour_count\n| filter exec_count > 100 and prev_hour_count < 10\n| sort desc _time\n| limit 10",
        "Detects hourly process-execution bursts following quiet periods (current >100, previous <10). Combines `bin` + `comp` + `windowcomp lag()` — the canonical multi-stage anomaly-detection chain.",
        ["filter", "bin", "comp", "windowcomp", "sort", "limit", "xdr_data", "process", "lag", "anomaly"],
    ),
    (
        "detection", "xdr_data",
        "Process executions standard-deviation ranking (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| bin _time span = 1h\n| comp count() as cnt by _time, agent_hostname\n| comp avg(cnt) as mean, stddev(cnt) as sd, count() as samples by agent_hostname\n| filter samples >= 5\n| sort desc sd\n| limit 10",
        "Per-host process-execution variability (standard deviation across hourly bins). Hosts with high standard deviation have irregular activity patterns — could indicate batch jobs, attack bursts, or genuine work fluctuation.",
        ["filter", "bin", "comp", "sort", "limit", "xdr_data", "process", "stddev", "stats"],
    ),
    (
        "detection", "xdr_data",
        "Percentile-90 upload bytes per host (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK and action_total_upload > 0\n| comp percentile(action_total_upload, 90) as p90, percentile(action_total_upload, 99) as p99, max(action_total_upload) as max_bytes by agent_hostname\n| sort desc p99\n| limit 10",
        "Per-host upload-size percentiles (P90, P99, max). `percentile(field, N)` returns the N-th percentile. Useful for finding which hosts have heavy-tailed upload distributions (P99 ≫ P90 = bursty + worth investigating).",
        ["filter", "comp", "sort", "limit", "xdr_data", "network", "percentile", "stats"],
    ),

    # ─── timestamp arithmetic — to_epoch ────────────────────────
    (
        "investigation", "endpoints",
        "Endpoint last-seen age in days via epoch math",
        "dataset = endpoints\n| filter last_seen != null\n| alter age_seconds = divide(subtract(to_epoch(current_time(), \"SECONDS\"), to_epoch(last_seen, \"SECONDS\")), 1)\n| alter age_days = floor(divide(age_seconds, 86400))\n| fields endpoint_name, last_seen, age_days, endpoint_status\n| sort desc age_days\n| limit 10",
        "Endpoint last-seen age in days. `to_epoch(timestamp, 'SECONDS')` converts both `current_time()` and `last_seen` to epoch seconds; subtraction + floor + divide-by-86400 gives integer days. Robust pattern for date-arithmetic on date-typed fields.",
        ["filter", "alter", "fields", "sort", "limit", "endpoints", "to_epoch", "math"],
    ),

    # ─── date_floor — truncate to bucket ────────────────────────
    (
        "investigation", "alerts",
        "Alerts per day via date_floor (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| alter day_bucket = date_floor(_time, \"DAY\")\n| comp count() as cnt by day_bucket, severity\n| sort desc day_bucket\n| limit 10",
        "Daily alert count per severity using `date_floor(timestamp, 'DAY')` — truncates the timestamp to day-precision. Alternative to `bin _time span = 1d` when you want the actual day timestamp in the output (not a bin-rounded one).",
        ["filter", "alter", "comp", "sort", "limit", "alerts", "date_floor"],
    ),

    # ─── list aggregation — multi-value collect ─────────────────
    (
        "investigation", "xdr_data",
        "Per-host command-line list aggregation (24h, list)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START and action_process_image_command_line != null\n| comp list(action_process_image_command_line) as commands by agent_hostname\n| alter command_count = array_length(commands)\n| filter command_count >= 3\n| fields agent_hostname, command_count\n| sort desc command_count\n| limit 10",
        "Per-host command-line collection via `list()` aggregation. Unlike `values()` (which deduplicates), `list()` keeps duplicates. Useful for forensic per-host command timelines.",
        ["filter", "comp", "alter", "fields", "sort", "limit", "xdr_data", "process", "list"],
    ),

    # ─── transaction — group related events ─────────────────────
    (
        "detection", "xdr_data",
        "Script-host process chains via transaction (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| filter lowercase(action_process_image_name) in (\"powershell.exe\", \"cmd.exe\", \"wscript.exe\", \"cscript.exe\", \"bash\", \"sh\", \"python3\", \"python.exe\")\n| transaction agent_hostname span = 5m\n| fields agent_hostname, action_process_image_name, _time\n| sort desc _time\n| limit 10",
        "Groups script-host process events on the same host into 5-minute transactions. `transaction <key> span = <duration>` is the canonical sessionization stage — collapses correlated events into one row per transaction.",
        ["filter", "transaction", "fields", "sort", "limit", "xdr_data", "process"],
    ),

    # ─── join — multi-dataset enrichment ────────────────────────
    (
        "investigation", "alerts",
        "Alerts with endpoint OS enrichment (7d, join)",
        "config timeframe = 7d\n| dataset = alerts\n| filter host_name != null\n| comp count() as alert_count by host_name, severity\n| join type=left (dataset = endpoints | fields endpoint_name, operating_system, agent_version) as ep on host_name = ep.endpoint_name\n| fields host_name, severity, alert_count, ep.operating_system, ep.agent_version\n| sort desc alert_count\n| limit 10",
        "Joins alert counts with endpoint OS + agent version. Useful for OS-grouped alert triage + spotting unpatched-agent hosts among heavy alert generators. `type=left` keeps alerts without a matching endpoint row.",
        ["filter", "comp", "join", "fields", "sort", "limit", "alerts", "endpoints"],
    ),

    # ─── multi-condition filter — complex predicates ────────────
    (
        "detection", "xdr_data",
        "Living-off-the-land binary with network egress (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK and actor_process_image_name != null\n| filter lowercase(actor_process_image_name) in (\"certutil.exe\", \"bitsadmin.exe\", \"curl.exe\", \"wget.exe\")\n| filter action_remote_ip != null and not incidr(action_remote_ip, \"10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16\")\n| iploc action_remote_ip loc_country\n| fields _time, agent_hostname, actor_process_image_name, action_remote_ip, loc_country, action_total_upload\n| sort desc _time\n| limit 10",
        "LOLBin network egress detection enriched with destination geo. Combines `filter` IN-clause + `incidr` exclusion + `iploc` enrichment — high-fidelity hunting query for exfil-via-LOLBin.",
        ["filter", "iploc", "fields", "sort", "limit", "xdr_data", "network", "lolbin", "geo"],
    ),

    # ─── chained alters — compound feature engineering ──────────
    (
        "investigation", "alerts",
        "Alert age + tier composite scoring (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| filter severity != null\n| alter sev_weight = if(severity = \"CRITICAL\", 4, if(severity = \"HIGH\", 3, if(severity = \"MEDIUM\", 2, 1)))\n| alter age_hours = divide(timestamp_diff(current_time(), _time, \"HOUR\"), 1)\n| alter age_decay = if(age_hours < 24, 1.0, if(age_hours < 72, 0.7, if(age_hours < 168, 0.4, 0.1)))\n| alter priority_score = multiply(sev_weight, age_decay)\n| fields _time, host_name, alert_name, severity, age_hours, priority_score\n| sort desc priority_score\n| limit 10",
        "Composite priority score: severity weight × age decay. Newer + higher-severity alerts get the top score. Demonstrates chained `alter` steps to engineer derived columns from raw data — the pattern adapts to any custom scoring need.",
        ["filter", "alter", "fields", "sort", "limit", "alerts", "if", "math", "scoring"],
    ),

    # ─── sub-query in union — multi-dataset aggregation ─────────
    (
        "investigation", "alerts",
        "Detection volume — alerts + agent_auditing combined (7d, union)",
        "config timeframe = 7d\n| dataset = alerts\n| comp count() as cnt by severity\n| alter source = \"alerts\"\n| union (dataset = agent_auditing | comp count() as cnt by agent_auditing_subtype | alter severity = agent_auditing_subtype, source = \"agent_auditing\" | fields severity, cnt, source)\n| sort desc cnt\n| limit 10",
        "Combines aggregated counts from two datasets (alerts + agent_auditing) into one unified view tagged with source. Demonstrates UNION with sub-query syntax + field projection per branch.",
        ["filter", "comp", "alter", "union", "sort", "limit", "alerts", "agent_auditing"],
    ),

    # ─── view stage — highlighted visualization ─────────────────
    (
        "investigation", "alerts",
        "Critical alerts highlighted via view stage (7d)",
        "config timeframe = 7d\n| dataset = alerts\n| filter severity in (\"HIGH\", \"CRITICAL\")\n| fields _time, host_name, alert_name, severity\n| view highlight fields = severity, values = \"CRITICAL\"\n| sort desc _time\n| limit 10",
        "Demonstrates the `view highlight` stage — marks rows where the named field has the named value. The result is rendered with visual emphasis in XDR's UI (no visible difference in raw API output, but useful when the result feeds an XDR dashboard).",
        ["filter", "fields", "view", "sort", "limit", "alerts"],
    ),
]


def main() -> None:
    print(f"v0.7.0 complex queries — validating {len(COMPLEX)} advanced queries")
    print(f"Starting at ID {START_ID}")
    print()

    successes = []
    failures = []
    next_id = START_ID

    for i, (category, dataset, title, query, when_to_use, tags) in enumerate(COMPLEX, 1):
        print(f"[{i:2d}/{len(COMPLEX)}] {category:14s} {dataset:20s} {title[:55]}")
        if not re.search(r"\|\s*limit\s+\d+\s*$", query, re.IGNORECASE):
            query = query.rstrip() + "\n| limit 10"

        t0 = time.time()
        try:
            result = run_xql(query, timeout=90)
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
            err_str = str(err)[:300]
            print(f"        FAIL: {err_str}")
            failures.append((title, err_str))

    print()
    print(f"=" * 72)
    print(f"COMPLEX DONE: {len(successes)} new entries written, {len(failures)} failed")
    print(f"=" * 72)
    if failures:
        for title, err in failures:
            print(f"  ✗ {title[:60]} :: {err[:120]}")


if __name__ == "__main__":
    main()
