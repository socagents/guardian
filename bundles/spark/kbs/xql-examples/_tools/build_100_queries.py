"""Build 100 validated XQL examples for the xql-examples KB (v0.7.0).

Operator brief: "lets aim for 100 working queries, take your time to
get quality, varied and working xql queries ranging from simple to
complex with different stages and functions ... always use the limit
stage not consume the xql api limits, for example limit 10".

Strategy:
1. Hold a curated list of ~100-120 query templates, each tagged with
   intended dataset + category + stages-used + functions-used + a
   `## When to use` description.
2. For each template, append `| limit 10` (if not already present),
   POST to the deployed `xdr_run_xql_query` via the agent UI tunnel,
   and check `status=SUCCESS`.
3. Drop templates that don't return SUCCESS (they target datasets/
   fields this tenant doesn't have).
4. Write surviving queries as `bundles/spark/kbs/xql-examples/
   entries/XQL-NNN-<hash>.md` files matching the v0.6.51 schema
   (frontmatter id/title/category/dataset/tags + body sections
   ## When to use, ## Variations, ## Source).

The 100-target is empirical — start with ~120 templates, ship the
~80-100 that pass validation. Quality over quantity: each surviving
query is GUARANTEED to execute against the operator's tenant
because we validated it before writing the file.

Usage (with agent UI tunnel on localhost:3001):
    gcloud compute start-iap-tunnel <vm> 3000 \\
        --local-host-port=localhost:3001 ... &
    python3 build_100_queries.py
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

# ─── Config ──────────────────────────────────────────────────────────

AGENT_URL = os.environ.get("GUARDIAN_AGENT_URL", "https://localhost:3001")
TLS_INSECURE = ssl._create_unverified_context()
ENTRIES_DIR = Path(__file__).resolve().parent.parent / "entries"

# Existing entry IDs (to avoid collision). The v0.6.51 import + v0.6.52
# backfill used XQL-001 through XQL-629. v0.7.0 starts at XQL-700+.
START_ID = 700


# ─── HTTP helper ────────────────────────────────────────────────────


def run_xql(query: str, timeout: int = 60) -> dict:
    """POST to the agent's tool-call proxy → cortex-xdr → XDR.
    Returns the inner `result` payload."""
    body = {"name": "xdr_run_xql_query", "arguments": {"query": query}}
    req = urllib.request.Request(
        f"{AGENT_URL}/api/agent/tool/call",
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, context=TLS_INSECURE, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not payload.get("ok"):
        return {"ok": False, "error": payload.get("error")}
    return payload.get("result") or {}


# ─── Query catalog ──────────────────────────────────────────────────
#
# Each template: (category, dataset, title, query_body, when_to_use, tags)
# Categories: investigation | detection | alert-mapping | general
# Tags: stage names + canonical dataset name + optional MITRE T-codes
#
# The query bodies use real fields confirmed in this tenant via
# v0.6.68 discovery. All time windows use `config timeframe = ...`
# (the canonical XQL idiom v0.6.67 teaches). All end with `| limit 10`
# to bound XDR API quota cost.

TEMPLATES: list[tuple[str, str, str, str, str, list[str]]] = [
    # ──────────────────────────────────────────────────────────────
    # xdr_data — process events
    # ──────────────────────────────────────────────────────────────
    (
        "investigation", "xdr_data",
        "Top 10 most-spawned child process names (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| comp count() as cnt by action_process_image_name\n| sort desc cnt\n| limit 10",
        "Aggregate process-start events by child-process name to find the most-spawned binaries in the tenant. Useful as a baseline before drilling into specific suspicious processes.",
        ["filter", "comp", "sort", "limit", "xdr_data", "process"],
    ),
    (
        "investigation", "xdr_data",
        "Top 10 process parents by execution count (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| comp count() as cnt by actor_process_image_name\n| sort desc cnt\n| limit 10",
        "Surface which processes spawn the most children. Useful for understanding normal process trees + spotting unusual high-spawn parents (e.g. compromised explorer.exe).",
        ["filter", "comp", "sort", "limit", "xdr_data", "process"],
    ),
    (
        "investigation", "xdr_data",
        "Process pairs — parent → child execution chains (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| comp count() as cnt by actor_process_image_name, action_process_image_name\n| sort desc cnt\n| limit 10",
        "Identifies the most common parent → child process execution pairs. Foundational pattern for behavior-baseline analytics + lateral movement detection (rare pairs = candidates).",
        ["filter", "comp", "sort", "limit", "xdr_data", "process"],
    ),
    (
        "detection", "xdr_data",
        "PowerShell with encoded command flag (24h, T1059.001)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| filter lowercase(action_process_image_name) = \"powershell.exe\"\n| filter lowercase(action_process_image_command_line) contains \"-enc\" or lowercase(action_process_image_command_line) contains \"-encodedcommand\"\n| fields _time, agent_hostname, actor_process_image_name, action_process_image_command_line\n| limit 10",
        "PowerShell with -EncodedCommand / -enc is a classic obfuscation technique (MITRE T1059.001). Flag any execution + return the host + parent + full command line for triage.",
        ["filter", "fields", "limit", "xdr_data", "process", "powershell", "T1059.001"],
    ),
    (
        "detection", "xdr_data",
        "Suspicious LOLBin parents spawning unusual children (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| filter lowercase(actor_process_image_name) in (\"rundll32.exe\", \"regsvr32.exe\", \"mshta.exe\", \"wmic.exe\", \"certutil.exe\", \"bitsadmin.exe\")\n| comp count() as cnt by actor_process_image_name, action_process_image_name\n| sort asc cnt\n| limit 10",
        "Classic Living-Off-The-Land Binaries (LOLBins) — when these utilities spawn unusual children, it often indicates attacker abuse. Sort by ascending count to surface rare combinations first.",
        ["filter", "comp", "sort", "limit", "xdr_data", "process", "lolbin", "T1218"],
    ),
    (
        "detection", "xdr_data",
        "Process spawned with explicit credentials in command line (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| filter action_process_image_command_line ~= \"(?i)(/user:|-user |-u \\S+ -p \\S+|password=|passwd=)\"\n| fields _time, agent_hostname, actor_effective_username, action_process_image_name, action_process_image_command_line\n| limit 10",
        "Processes with credentials hardcoded in command line — often indicates poor secret-hygiene or active attack (psexec, runas variants). The regex matches Windows-style credential flags.",
        ["filter", "fields", "limit", "xdr_data", "process", "credentials"],
    ),
    (
        "investigation", "xdr_data",
        "Recent process executions on specific host (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| filter lowercase(agent_hostname) = \"xdragent\"\n| fields _time, agent_hostname, actor_process_image_name, action_process_image_name, action_process_image_command_line, actor_effective_username\n| sort desc _time\n| limit 10",
        "Investigation pivot — given a specific host of interest, return the most recent process-start events with parent/child + command line + initiating user. Replace 'xdragent' with the target host.",
        ["filter", "fields", "sort", "limit", "xdr_data", "process"],
    ),
    (
        "detection", "xdr_data",
        "Long process command lines — possible obfuscation (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| alter cmd_len = len(action_process_image_command_line)\n| filter cmd_len > 500\n| fields _time, agent_hostname, action_process_image_name, cmd_len, action_process_image_command_line\n| sort desc cmd_len\n| limit 10",
        "Excessively long command lines (>500 chars) often indicate obfuscated PowerShell, base64 payloads, or other evasion techniques. `len()` builds the length column for sorting.",
        ["filter", "alter", "fields", "sort", "limit", "xdr_data", "process"],
    ),
    # ──────────────────────────────────────────────────────────────
    # xdr_data — file events
    # ──────────────────────────────────────────────────────────────
    (
        "investigation", "xdr_data",
        "File extensions written in last 24h",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.FILE\n| comp count() as cnt by action_file_extension\n| sort desc cnt\n| limit 10",
        "Aggregate file events by extension to baseline file-write patterns. Spikes in unusual extensions (.lnk, .scr, .ps1) can indicate attacker tooling drops.",
        ["filter", "comp", "sort", "limit", "xdr_data", "file"],
    ),
    (
        "detection", "xdr_data",
        "Executable files written to user-writable paths (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.FILE\n| filter lowercase(action_file_extension) in (\"exe\", \"dll\", \"scr\", \"ps1\", \"bat\", \"vbs\", \"hta\")\n| filter lowercase(action_file_path) contains \"\\\\users\\\\\" or lowercase(action_file_path) contains \"\\\\temp\\\\\" or lowercase(action_file_path) contains \"\\\\appdata\\\\\"\n| fields _time, agent_hostname, action_process_image_name, action_file_path, actor_effective_username\n| sort desc _time\n| limit 10",
        "Executables and scripts written to user-writable directories (Users\\, Temp\\, AppData\\) — a classic staging pattern for malware. Returns the writing process + user for triage.",
        ["filter", "fields", "sort", "limit", "xdr_data", "file"],
    ),
    (
        "investigation", "xdr_data",
        "Top files written by process (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.FILE\n| comp count() as writes by actor_process_image_name, action_file_extension\n| sort desc writes\n| limit 10",
        "Which processes write the most files, by extension. Useful for understanding normal-state writers (system processes) so you can spot anomalies (e.g. unexpected process writing .exe files).",
        ["filter", "comp", "sort", "limit", "xdr_data", "file"],
    ),
    # ──────────────────────────────────────────────────────────────
    # xdr_data — network events
    # ──────────────────────────────────────────────────────────────
    (
        "investigation", "xdr_data",
        "Top 10 remote destinations by connection count (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK\n| filter action_remote_ip != null\n| comp count() as connections by action_remote_ip, action_remote_port\n| sort desc connections\n| limit 10",
        "Aggregates outbound + inbound connections by remote IP+port pair. Useful for surfacing top external services + spotting C2-like patterns (high connection count to a single unknown IP).",
        ["filter", "comp", "sort", "limit", "xdr_data", "network"],
    ),
    (
        "investigation", "xdr_data",
        "Top hosts by outbound upload bytes (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK\n| comp sum(action_total_upload) as total_upload by agent_hostname\n| sort desc total_upload\n| limit 10",
        "Aggregate upload bytes per host to identify data-exfiltration candidates. Hosts with anomalously high upload totals + minimal legitimate egress reason are worth investigating.",
        ["filter", "comp", "sort", "limit", "xdr_data", "network", "exfil"],
    ),
    (
        "detection", "xdr_data",
        "Outbound connections to public IPs from internal hosts (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK\n| filter not incidr(action_remote_ip, \"10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8, 169.254.0.0/16\")\n| comp count() as connections, sum(action_total_upload) as upload_bytes by agent_hostname, action_remote_ip\n| sort desc upload_bytes\n| limit 10",
        "Outbound connections to public (non-RFC1918) IP space. Useful for surfacing legitimate-vs-suspicious external traffic. The `incidr` function with negation filters out internal-network traffic.",
        ["filter", "comp", "sort", "limit", "xdr_data", "network", "incidr"],
    ),
    (
        "detection", "xdr_data",
        "Connections to suspicious destination ports (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK\n| filter action_remote_port in (4444, 1337, 8080, 9001, 9050, 3389, 5900, 23, 1433)\n| comp count() as connections by agent_hostname, action_remote_ip, action_remote_port\n| sort desc connections\n| limit 10",
        "Connections to commonly-abused destination ports — Metasploit defaults (4444), Tor relay ports (9001/9050), legacy services (telnet 23, SQL Server 1433), RDP/VNC. Triage candidates.",
        ["filter", "comp", "sort", "limit", "xdr_data", "network", "c2"],
    ),
    (
        "investigation", "xdr_data",
        "DNS query volume per host (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK and action_remote_port = 53\n| comp count() as dns_queries by agent_hostname\n| sort desc dns_queries\n| limit 10",
        "Hosts with abnormally high DNS query volume can indicate DNS tunneling or malware C2 over DNS. The query filters to port 53 to capture DNS-protocol traffic.",
        ["filter", "comp", "sort", "limit", "xdr_data", "network", "dns"],
    ),
    # ──────────────────────────────────────────────────────────────
    # xdr_data — registry events (Windows)
    # ──────────────────────────────────────────────────────────────
    (
        "investigation", "xdr_data",
        "Top registry keys modified (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.REGISTRY\n| comp count() as modifications by action_registry_key_name\n| sort desc modifications\n| limit 10",
        "Most-modified registry keys baseline. Windows housekeeping dominates; spikes in autoruns / boot-execute / image-file-execution paths are persistence indicators.",
        ["filter", "comp", "sort", "limit", "xdr_data", "registry"],
    ),
    (
        "detection", "xdr_data",
        "Persistence via autorun-key registry writes (24h, T1547)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.REGISTRY\n| filter action_registry_key_name contains \"\\\\Run\" or action_registry_key_name contains \"\\\\RunOnce\" or action_registry_key_name contains \"\\\\Image File Execution Options\"\n| fields _time, agent_hostname, actor_process_image_name, action_registry_key_name, action_registry_value_name\n| sort desc _time\n| limit 10",
        "MITRE T1547 — Boot or Logon Autostart Execution. Captures writes to the canonical autorun registry locations + Image File Execution Options (a debugger-hijack persistence vector).",
        ["filter", "fields", "sort", "limit", "xdr_data", "registry", "T1547"],
    ),
    # ──────────────────────────────────────────────────────────────
    # endpoints
    # ──────────────────────────────────────────────────────────────
    (
        "investigation", "endpoints",
        "All endpoints with status + OS + agent version",
        "dataset = endpoints\n| fields endpoint_name, endpoint_status, operating_system, agent_version, last_seen, ip_address\n| sort asc last_seen\n| limit 10",
        "Foundational endpoint inventory query. Returns all managed endpoints sorted by last_seen ascending so the oldest-last-seen entries surface first (stale agents).",
        ["fields", "sort", "limit", "endpoints"],
    ),
    (
        "detection", "endpoints",
        "Endpoints not seen in last 7 days (potentially offline)",
        "dataset = endpoints\n| filter endpoint_status != \"CONNECTED\"\n| fields endpoint_name, endpoint_status, operating_system, last_seen, agent_version\n| sort asc last_seen\n| limit 10",
        "Endpoints whose status is not CONNECTED (e.g. CONNECTION_LOST, DISCONNECTED). Useful for identifying agents that may have been uninstalled, taken offline by attackers, or have networking issues.",
        ["filter", "fields", "sort", "limit", "endpoints"],
    ),
    (
        "investigation", "endpoints",
        "Endpoints grouped by OS family",
        "dataset = endpoints\n| comp count() as cnt, count_distinct(endpoint_id) as unique_endpoints by platform, operating_system\n| sort desc cnt\n| limit 10",
        "OS distribution baseline — useful for capacity planning + identifying outliers (e.g. an old Windows 7 box in a Windows-11-only fleet).",
        ["comp", "sort", "limit", "endpoints"],
    ),
    (
        "investigation", "endpoints",
        "Endpoints by isolation + prevention policy",
        "dataset = endpoints\n| comp count() as cnt by endpoint_isolated, assigned_prevention_policy\n| sort desc cnt\n| limit 10",
        "Reports the distribution of endpoint protection policies + isolation status across the fleet. Helps identify hosts running non-default policies or in isolation mode.",
        ["comp", "sort", "limit", "endpoints"],
    ),
    (
        "detection", "endpoints",
        "Cloud-hosted endpoints (cloud_provider populated)",
        "dataset = endpoints\n| filter cloud_provider != null\n| fields endpoint_name, cloud_provider, cloud_region, cloud_instance_id, operating_system, endpoint_status\n| sort desc cloud_provider\n| limit 10",
        "Identifies endpoints hosted in cloud providers (AWS, Azure, GCP). Useful for cloud-workload visibility + correlating with cloud-side audit events.",
        ["filter", "fields", "sort", "limit", "endpoints", "cloud"],
    ),
    # ──────────────────────────────────────────────────────────────
    # alerts — flat schema
    # ──────────────────────────────────────────────────────────────
    (
        "investigation", "alerts",
        "Alert distribution by severity (7d)",
        "config timeframe = 7d\n| dataset = alerts\n| comp count() as cnt by severity\n| sort desc cnt\n| limit 10",
        "Severity baseline for the last 7 days. Useful as the first triage view + for trend monitoring (volume by severity over time).",
        ["filter", "comp", "sort", "limit", "alerts"],
    ),
    (
        "investigation", "alerts",
        "Alert distribution by category + alert_source (7d)",
        "config timeframe = 7d\n| dataset = alerts\n| comp count() as cnt by category, alert_source\n| sort desc cnt\n| limit 10",
        "Aggregate alerts by category and source detector. Useful for understanding which detection sources are firing the most + which categories dominate the tenant's alert mix.",
        ["filter", "comp", "sort", "limit", "alerts"],
    ),
    (
        "investigation", "alerts",
        "Top 10 alert names by occurrence (7d)",
        "config timeframe = 7d\n| dataset = alerts\n| comp count() as cnt by alert_name\n| sort desc cnt\n| limit 10",
        "Surfaces the most-fired alert rules. Helps prioritize tuning effort (high-volume rules with low fidelity) or identify campaign-level activity (sudden spikes on a single alert name).",
        ["filter", "comp", "sort", "limit", "alerts"],
    ),
    (
        "investigation", "alerts",
        "Alerts by host (7d)",
        "config timeframe = 7d\n| dataset = alerts\n| filter host_name != null\n| comp count() as cnt by host_name, severity\n| sort desc cnt\n| limit 10",
        "Per-host alert volume by severity. Identifies the noisiest hosts + flags hosts with disproportionately high CRITICAL alert counts.",
        ["filter", "comp", "sort", "limit", "alerts"],
    ),
    (
        "detection", "alerts",
        "Credential-dumping alerts (Mimikatz, LSASS) (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| filter lowercase(alert_name) contains \"mimikatz\" or lowercase(alert_name) contains \"lsass\" or lowercase(description) contains \"mimikatz\" or lowercase(description) contains \"credential\"\n| fields _time, host_name, severity, alert_name, description\n| sort desc _time\n| limit 10",
        "Credential-extraction-related alerts. MITRE T1003 family — Mimikatz, LSASS memory access, credential dumping. Returns hits across the alert_name + description for broad coverage.",
        ["filter", "fields", "sort", "limit", "alerts", "T1003"],
    ),
    (
        "detection", "alerts",
        "Alerts containing CVE identifiers (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| filter alert_name ~= \"CVE-[0-9]{4}-[0-9]+\"\n| alter cve_id = arrayindex(regextract(alert_name, \"(CVE-[0-9]{4}-[0-9]+)\"), 0)\n| comp count() as alert_count, count_distinct(host_name) as affected_hosts by cve_id, severity\n| sort desc alert_count\n| limit 10",
        "Vulnerability alerts grouped by extracted CVE ID. Uses `regextract` + `arrayindex` to pull the CVE token from alert_name. Returns affected host count per CVE.",
        ["filter", "alter", "comp", "sort", "limit", "alerts", "vulnerability", "regextract"],
    ),
    (
        "investigation", "alerts",
        "Critical + high alerts in the last 24 hours",
        "config timeframe = 24h\n| dataset = alerts\n| filter severity in (\"CRITICAL\", \"HIGH\")\n| fields _time, severity, alert_name, host_name, description\n| sort desc _time\n| limit 10",
        "Triage view for the high-severity tail. Returns the most recent CRITICAL + HIGH alerts in the last day with the description for quick context.",
        ["filter", "fields", "sort", "limit", "alerts"],
    ),
    (
        "investigation", "alerts",
        "Alerts grouped by initiator process (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| filter initiator_path != null\n| comp count() as cnt by initiator_path, severity\n| sort desc cnt\n| limit 10",
        "Which initiator processes (the process that triggered the detection) generate the most alerts? Useful for tuning + spotting recurring offenders.",
        ["filter", "comp", "sort", "limit", "alerts"],
    ),
    # ──────────────────────────────────────────────────────────────
    # issues — XDM-normalized
    # ──────────────────────────────────────────────────────────────
    (
        "investigation", "issues",
        "Issues by severity (7d)",
        "config timeframe = 7d\n| dataset = issues\n| comp count() as cnt by xdm.alert.severity\n| sort desc cnt\n| limit 10",
        "XDM-normalized parallel to the alerts severity query. Useful when consuming alert data via the issues schema instead of the legacy alerts shape.",
        ["filter", "comp", "sort", "limit", "issues", "xdm"],
    ),
    (
        "investigation", "issues",
        "Issues by category (7d)",
        "config timeframe = 7d\n| dataset = issues\n| comp count() as cnt by xdm.issue.category\n| sort desc cnt\n| limit 10",
        "Issue category distribution via the XDM schema. Maps to the MITRE-tagged categories XSIAM assigns automatically.",
        ["filter", "comp", "sort", "limit", "issues", "xdm"],
    ),
    # ──────────────────────────────────────────────────────────────
    # va_cves
    # ──────────────────────────────────────────────────────────────
    (
        "investigation", "va_cves",
        "Top 10 CVEs by affected-host count",
        "dataset = va_cves\n| comp count_distinct(endpoint_id) as affected_hosts by cve_id, cve_severity\n| sort desc affected_hosts\n| limit 10",
        "Vulnerability management view — which CVEs affect the most endpoints. Critical for patch prioritization. Returns CVE ID + severity + unique-affected-host count.",
        ["comp", "sort", "limit", "va_cves", "vulnerability"],
    ),
    (
        "investigation", "va_cves",
        "Critical CVEs detected in last 7 days",
        "config timeframe = 7d\n| dataset = va_cves\n| filter cve_severity = \"CRITICAL\"\n| fields _time, cve_id, cve_severity, cve_description, endpoint_name\n| sort desc _time\n| limit 10",
        "Surfaces newly-detected CRITICAL CVEs. Useful as a daily / weekly triage view paired with the affected-hosts pivot above.",
        ["filter", "fields", "sort", "limit", "va_cves", "vulnerability"],
    ),
    # ──────────────────────────────────────────────────────────────
    # va_endpoints
    # ──────────────────────────────────────────────────────────────
    (
        "investigation", "va_endpoints",
        "Top 10 most-vulnerable endpoints by CVE count",
        "dataset = va_endpoints\n| comp count_distinct(cve_id) as cve_count, count_distinct(case when cve_severity = \"CRITICAL\" then cve_id end) as critical_cves by endpoint_name, operating_system\n| sort desc critical_cves\n| limit 10",
        "Per-endpoint vulnerability summary — total CVEs + critical-CVE count + OS. Prioritizes patching effort on the highest-risk hosts.",
        ["comp", "sort", "limit", "va_endpoints", "vulnerability"],
    ),
    # ──────────────────────────────────────────────────────────────
    # agent_auditing
    # ──────────────────────────────────────────────────────────────
    (
        "investigation", "agent_auditing",
        "Recent agent events by subtype (7d)",
        "config timeframe = 7d\n| dataset = agent_auditing\n| comp count() as cnt by agent_auditing_subtype\n| sort desc cnt\n| limit 10",
        "Agent self-audit event distribution — start/stop, policy applied, upgrade, error, etc. Useful for understanding agent fleet health.",
        ["filter", "comp", "sort", "limit", "agent_auditing"],
    ),
    (
        "detection", "agent_auditing",
        "Agents that stopped auditing in the last 24h",
        "config timeframe = 24h\n| dataset = agent_auditing\n| filter agent_auditing_subtype = ENUM.AGENT_AUDIT_STOP\n| fields _time, endpoint_name, endpoint_id, xdr_agent_version, description\n| sort desc _time\n| limit 10",
        "Agent audit-stop events — when the XDR agent stopped its self-audit. Can indicate normal stop (uninstall, restart) or attacker action to disable visibility. Triage candidates.",
        ["filter", "fields", "sort", "limit", "agent_auditing"],
    ),
    # ──────────────────────────────────────────────────────────────
    # host_inventory
    # ──────────────────────────────────────────────────────────────
    (
        "investigation", "host_inventory",
        "Host inventory by OS family",
        "dataset = host_inventory\n| comp count() as cnt by operating_system_family\n| sort desc cnt\n| limit 10",
        "Discovered host distribution by OS family. Complementary to the endpoints query — host_inventory may include agentless-discovered systems.",
        ["comp", "sort", "limit", "host_inventory"],
    ),
    # ──────────────────────────────────────────────────────────────
    # incidents
    # ──────────────────────────────────────────────────────────────
    (
        "investigation", "incidents",
        "Recent incidents by severity + status (7d)",
        "config timeframe = 7d\n| dataset = incidents\n| comp count() as cnt by severity, status\n| sort desc cnt\n| limit 10",
        "Incident triage matrix — severity × status. New + critical = highest priority; resolved + low = ready to archive.",
        ["filter", "comp", "sort", "limit", "incidents"],
    ),
    # ──────────────────────────────────────────────────────────────
    # cloud_audit_logs
    # ──────────────────────────────────────────────────────────────
    (
        "investigation", "cloud_audit_logs",
        "Top cloud actions by count (7d)",
        "config timeframe = 7d\n| dataset = cloud_audit_logs\n| comp count() as cnt by cloud_provider, operation_name\n| sort desc cnt\n| limit 10",
        "Cloud audit-log activity baseline. Reveals the most-frequent cloud operations across providers. Spikes in unusual operations (CreateUser, DeleteBucket) warrant attention.",
        ["filter", "comp", "sort", "limit", "cloud_audit_logs", "cloud"],
    ),
    # ──────────────────────────────────────────────────────────────
    # COMPLEX patterns (multi-stage)
    # ──────────────────────────────────────────────────────────────
    (
        "detection", "xdr_data",
        "Hourly process executions per host with bin (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| bin _time span = 1h\n| comp count() as exec_count by _time, agent_hostname\n| sort desc _time, agent_hostname\n| limit 10",
        "Time-bucketed process execution rate per host. The `bin _time span = 1h` stage creates hourly buckets — useful for finding unusual spikes in process activity timewise.",
        ["filter", "bin", "comp", "sort", "limit", "xdr_data", "process"],
    ),
    (
        "detection", "xdr_data",
        "Process executions with running average via windowcomp (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| bin _time span = 1h\n| comp count() as exec_count by _time, agent_hostname\n| windowcomp avg(exec_count) by agent_hostname as rolling_avg\n| sort desc _time\n| limit 10",
        "Hourly execution counts with a rolling average per host computed via `windowcomp`. Foundation for anomaly-detection queries (compare current count vs rolling baseline).",
        ["filter", "bin", "comp", "windowcomp", "sort", "limit", "xdr_data", "process"],
    ),
    (
        "investigation", "xdr_data",
        "Distinct users per host (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter actor_effective_username != null\n| comp count_distinct(actor_effective_username) as unique_users, values(actor_effective_username) as users by agent_hostname\n| sort desc unique_users\n| limit 10",
        "How many distinct users were active per host? `count_distinct` + `values()` together give both the count and the list. Useful for finding shared-account hosts or atypical user activity.",
        ["filter", "comp", "sort", "limit", "xdr_data", "user"],
    ),
    (
        "detection", "xdr_data",
        "Rare process executions — seen fewer than 5 times (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| comp count() as cnt by action_process_image_name, actor_process_image_name\n| filter cnt < 5\n| sort asc cnt\n| limit 10",
        "Rare-execution baseline anomaly detection. Process pairs seen fewer than 5 times in the timeframe are surfacing candidates. Two-stage comp + filter is the canonical rarity pattern.",
        ["filter", "comp", "sort", "limit", "xdr_data", "process", "rare"],
    ),
    (
        "investigation", "alerts",
        "Alerts joined with endpoint context (7d)",
        "config timeframe = 7d\n| dataset = alerts\n| filter severity in (\"HIGH\", \"CRITICAL\")\n| fields _time, host_name, severity, alert_name\n| join type=left (dataset = endpoints | fields endpoint_name as host_name, operating_system, agent_version) as ep on host_name\n| fields _time, host_name, severity, alert_name, ep.operating_system, ep.agent_version\n| sort desc _time\n| limit 10",
        "Enrichment via `join` — pulls endpoint metadata onto each high/critical alert. Demonstrates the join stage with field-aliasing and result projection.",
        ["filter", "fields", "join", "sort", "limit", "alerts", "endpoints", "enrichment"],
    ),
    (
        "detection", "xdr_data",
        "Successive process executions in tight time window (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| filter lowercase(action_process_image_name) in (\"powershell.exe\", \"cmd.exe\", \"wscript.exe\", \"cscript.exe\")\n| transaction agent_hostname maxevents = 5 maxspan = 60s\n| fields agent_hostname, action_process_image_name, _time\n| limit 10",
        "Burst detection — successive script-host executions on the same host within a 60s window. Uses `transaction` to group related events. Common pattern for fileless attack chains.",
        ["filter", "transaction", "fields", "limit", "xdr_data", "process"],
    ),
    (
        "investigation", "xdr_data",
        "Hourly file-write rate by extension (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.FILE\n| bin _time span = 1h\n| comp count() as writes by _time, action_file_extension\n| sort desc _time\n| limit 10",
        "Time-bucketed file-write volume by extension. Reveals daily patterns + sudden bursts (ransomware encryption events drop many similar files).",
        ["filter", "bin", "comp", "sort", "limit", "xdr_data", "file"],
    ),
    (
        "detection", "xdr_data",
        "Outbound bytes percentage by host (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK\n| comp sum(action_total_upload) as upload, sum(action_total_download) as download by agent_hostname\n| alter total_bytes = add(upload, download)\n| filter total_bytes > 0\n| alter upload_pct = multiply(divide(upload, total_bytes), 100)\n| sort desc upload_pct\n| limit 10",
        "Computes upload/download ratio per host using XQL math functions (add, divide, multiply). High upload_pct = exfiltration signal — host sending much more than receiving.",
        ["filter", "comp", "alter", "sort", "limit", "xdr_data", "network", "exfil", "math"],
    ),
    (
        "investigation", "endpoints",
        "Endpoint last-seen age buckets",
        "dataset = endpoints\n| alter age_days = divide(subtract(to_integer(current_time()), to_integer(last_seen)), 86400000)\n| alter age_bucket = if(age_days < 1, \"0-1d\", if(age_days < 7, \"1-7d\", if(age_days < 30, \"7-30d\", \"30d+\")))\n| comp count() as cnt by age_bucket\n| sort desc cnt\n| limit 10",
        "Bucketed endpoint last-seen distribution using nested `if()` conditionals. Surfaces the size of each cohort (recent vs. stale). The age_days computation uses subtract + divide on epoch millis.",
        ["alter", "comp", "sort", "limit", "endpoints", "math", "conditional"],
    ),
    (
        "detection", "alerts",
        "Alert correlation — same host + multiple severities (7d)",
        "config timeframe = 7d\n| dataset = alerts\n| filter host_name != null\n| comp count_distinct(severity) as sev_count, values(severity) as severities, count() as alert_count by host_name\n| filter sev_count >= 2\n| sort desc alert_count\n| limit 10",
        "Hosts with alerts at multiple severities within the timeframe. Could indicate an active campaign (multiple detection rules firing) or chronic noise (always-noisy host).",
        ["filter", "comp", "sort", "limit", "alerts"],
    ),
    (
        "investigation", "xdr_data",
        "Top hosts by event-type breakdown (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| comp count() as cnt by agent_hostname, event_type\n| sort desc cnt\n| limit 10",
        "Per-host activity volume by event type. Useful baseline — which hosts are most active in process, network, file, etc. Spikes in unusual event types per host warrant follow-up.",
        ["filter", "comp", "sort", "limit", "xdr_data"],
    ),
    # ──────────────────────────────────────────────────────────────
    # CASE / IF conditional patterns
    # ──────────────────────────────────────────────────────────────
    (
        "investigation", "alerts",
        "Alerts classified by severity tier",
        "config timeframe = 7d\n| dataset = alerts\n| alter tier = if(severity = \"CRITICAL\", \"P1\", if(severity = \"HIGH\", \"P2\", if(severity = \"MEDIUM\", \"P3\", \"P4\")))\n| comp count() as cnt by tier\n| sort asc tier\n| limit 10",
        "Maps XSIAM severity to priority tiers (P1-P4) via nested `if()`. Useful for SLA reporting where the operations team tracks alerts by priority class.",
        ["filter", "alter", "comp", "sort", "limit", "alerts", "conditional"],
    ),
    (
        "detection", "xdr_data",
        "Categorize destination IPs as internal / public / multicast (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK and action_remote_ip != null\n| alter ip_class = if(incidr(action_remote_ip, \"10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16\"), \"internal\", if(incidr(action_remote_ip, \"224.0.0.0/4\"), \"multicast\", if(incidr(action_remote_ip, \"127.0.0.0/8\"), \"loopback\", \"public\")))\n| comp count() as cnt, sum(action_total_upload) as upload by ip_class, agent_hostname\n| sort desc upload\n| limit 10",
        "IP-class labeling via nested `if` + `incidr`. Aggregates upload bytes per (class, host) so you can see per-host traffic distribution by destination type.",
        ["filter", "alter", "comp", "sort", "limit", "xdr_data", "network", "incidr", "conditional"],
    ),
    (
        "investigation", "endpoints",
        "Endpoints flagged by tier — critical / high-value / normal",
        "dataset = endpoints\n| alter tier = if(operating_system contains \"Server\", \"critical\", if(cloud_provider != null, \"high-value\", \"normal\"))\n| comp count() as cnt by tier, operating_system\n| sort desc cnt\n| limit 10",
        "Heuristic endpoint tiering — server OSes are 'critical', cloud-hosted are 'high-value', rest are 'normal'. Demonstrates conditional categorization on `endpoints` data.",
        ["alter", "comp", "sort", "limit", "endpoints", "conditional"],
    ),
    # ──────────────────────────────────────────────────────────────
    # STRING manipulation patterns
    # ──────────────────────────────────────────────────────────────
    (
        "detection", "xdr_data",
        "Extract file basename from full path (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.FILE\n| filter action_file_path != null\n| alter basename = arrayindex(split(action_file_path, \"\\\\\"), -1)\n| comp count() as writes by basename, action_file_extension\n| sort desc writes\n| limit 10",
        "Splits the full file path on backslash and takes the last element via `arrayindex(arr, -1)` — gives the file basename without directory. Aggregates writes by basename.",
        ["filter", "alter", "comp", "sort", "limit", "xdr_data", "file", "split"],
    ),
    (
        "investigation", "xdr_data",
        "Uppercase agent_hostname normalization (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS\n| alter host_upper = uppercase(agent_hostname)\n| comp count() as cnt by host_upper\n| sort desc cnt\n| limit 10",
        "Normalizes hostnames to uppercase for case-insensitive aggregation. Useful when the same host appears with mixed-case names due to legacy logging.",
        ["filter", "alter", "comp", "sort", "limit", "xdr_data", "string"],
    ),
    # ──────────────────────────────────────────────────────────────
    # JSON / nested-field extraction
    # ──────────────────────────────────────────────────────────────
    (
        "investigation", "alerts",
        "Alerts with file_macro_sha256 extracted (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| filter file_macro_sha256 != null\n| fields _time, host_name, alert_name, severity, file_macro_sha256, file_path\n| sort desc _time\n| limit 10",
        "Alerts that include a macro-bearing file SHA256. Useful for office-macro-attack triage — pull the hash, the host, and the file path.",
        ["filter", "fields", "sort", "limit", "alerts"],
    ),
    # ──────────────────────────────────────────────────────────────
    # UNION across datasets
    # ──────────────────────────────────────────────────────────────
    (
        "investigation", "alerts",
        "Alerts + issues unified view (recent 7d)",
        "config timeframe = 7d\n| dataset = alerts\n| fields _time, host_name, alert_name, severity, \"alerts\" as source_dataset\n| union (dataset = issues | fields _time, xdm.alert.host as host_name, xdm.alert.name as alert_name, xdm.alert.severity as severity, \"issues\" as source_dataset)\n| sort desc _time\n| limit 10",
        "UNION across the parallel `alerts` (flat) and `issues` (XDM) datasets, normalizing field names + tagging each row with its source. Demonstrates multi-dataset query composition.",
        ["filter", "fields", "union", "sort", "limit", "alerts", "issues"],
    ),
    # ──────────────────────────────────────────────────────────────
    # DEDUP patterns
    # ──────────────────────────────────────────────────────────────
    (
        "investigation", "xdr_data",
        "Unique processes per host (deduped, 24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| dedup agent_hostname, action_process_image_name\n| fields agent_hostname, action_process_image_name\n| sort asc agent_hostname\n| limit 10",
        "DEDUP stage collapses to one row per (host, process). Returns the unique processes seen per host — useful for whitelist generation + process-inventory snapshots.",
        ["filter", "dedup", "fields", "sort", "limit", "xdr_data", "process"],
    ),
    # ──────────────────────────────────────────────────────────────
    # CONFIG case-insensitive
    # ──────────────────────────────────────────────────────────────
    (
        "investigation", "xdr_data",
        "Case-insensitive process match using config (24h)",
        "config case_sensitive = false timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| filter action_process_image_name = \"powershell.exe\"\n| fields _time, agent_hostname, action_process_image_name, action_process_image_command_line\n| sort desc _time\n| limit 10",
        "Uses `config case_sensitive = false` so the equality match is case-insensitive without needing `lowercase()` wrapping. Useful for cleaner queries on case-mixed Windows paths.",
        ["filter", "fields", "sort", "limit", "xdr_data", "process", "config"],
    ),
    (
        "investigation", "xdr_data",
        "Network events to specific port across all hosts (1h)",
        "config timeframe = 1h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK and action_remote_port = 443\n| comp count() as cnt by agent_hostname\n| sort desc cnt\n| limit 10",
        "Per-host HTTPS connection count over the last hour. Short timeframe + simple aggregation — useful as a real-time signal during incident response.",
        ["filter", "comp", "sort", "limit", "xdr_data", "network"],
    ),

    # ──────────────────────────────────────────────────────────────
    # v0.7.0 expansion — additional coverage
    # ──────────────────────────────────────────────────────────────

    # ─── xdr_data — broader process patterns ─────────────────────
    (
        "detection", "xdr_data",
        "Processes spawned from temp directories (24h, T1036)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| filter lowercase(action_process_image_path) contains \"\\\\temp\\\\\" or lowercase(action_process_image_path) contains \"\\\\tmp\\\\\"\n| fields _time, agent_hostname, action_process_image_path, action_process_image_command_line, actor_process_image_name\n| sort desc _time\n| limit 10",
        "Executables running from Temp/Tmp directories — common staging pattern (MITRE T1036 Masquerading). Returns the parent process for chain-of-custody analysis.",
        ["filter", "fields", "sort", "limit", "xdr_data", "process", "T1036"],
    ),
    (
        "detection", "xdr_data",
        "Network discovery commands (24h, T1018/T1046)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| filter lowercase(action_process_image_name) in (\"net.exe\", \"net1.exe\", \"nltest.exe\", \"nbtstat.exe\", \"ping.exe\")\n| filter action_process_image_command_line ~= \"(?i)(view|domain_trusts|/domain|/dclist|workgroup)\"\n| fields _time, agent_hostname, actor_effective_username, action_process_image_name, action_process_image_command_line\n| sort desc _time\n| limit 10",
        "Network/domain discovery activity — MITRE T1018 (Remote System Discovery) and T1046 (Network Service Scanning). Common in early-stage post-compromise reconnaissance.",
        ["filter", "fields", "sort", "limit", "xdr_data", "process", "T1018", "T1046"],
    ),
    (
        "detection", "xdr_data",
        "Service-related process activity (24h, T1543.003)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| filter lowercase(action_process_image_name) in (\"sc.exe\", \"services.exe\", \"net.exe\")\n| filter action_process_image_command_line ~= \"(?i)(create|config|start|stop|delete)\"\n| fields _time, agent_hostname, actor_effective_username, action_process_image_command_line\n| sort desc _time\n| limit 10",
        "Service create/modify/delete activity — MITRE T1543.003 (Windows Service Persistence). Captures both legitimate admin activity and attacker service-installation.",
        ["filter", "fields", "sort", "limit", "xdr_data", "process", "T1543.003"],
    ),
    (
        "detection", "xdr_data",
        "Scheduled-task creation activity (24h, T1053.005)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| filter lowercase(action_process_image_name) in (\"schtasks.exe\", \"at.exe\")\n| filter lowercase(action_process_image_command_line) contains \"/create\"\n| fields _time, agent_hostname, actor_effective_username, action_process_image_command_line\n| sort desc _time\n| limit 10",
        "Scheduled task creation — MITRE T1053.005. One of the most common persistence techniques. Captures schtasks /create + at command invocations.",
        ["filter", "fields", "sort", "limit", "xdr_data", "process", "T1053.005"],
    ),
    (
        "detection", "xdr_data",
        "WMI persistence indicators (24h, T1546.003)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| filter lowercase(action_process_image_name) in (\"wmic.exe\", \"powershell.exe\")\n| filter lowercase(action_process_image_command_line) contains \"__eventfilter\" or lowercase(action_process_image_command_line) contains \"__eventconsumer\" or lowercase(action_process_image_command_line) contains \"__filtertoconsumerbinding\"\n| fields _time, agent_hostname, action_process_image_command_line\n| sort desc _time\n| limit 10",
        "WMI Event Subscription persistence — MITRE T1546.003. Rare but high-fidelity. Matches the three WMI classes that compose a persistent subscription.",
        ["filter", "fields", "sort", "limit", "xdr_data", "process", "T1546.003"],
    ),
    (
        "detection", "xdr_data",
        "Suspicious Office-app child processes (24h, T1566.001)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| filter lowercase(actor_process_image_name) in (\"winword.exe\", \"excel.exe\", \"powerpnt.exe\", \"outlook.exe\")\n| filter lowercase(action_process_image_name) in (\"cmd.exe\", \"powershell.exe\", \"wscript.exe\", \"cscript.exe\", \"mshta.exe\", \"rundll32.exe\")\n| fields _time, agent_hostname, actor_process_image_name, action_process_image_name, action_process_image_command_line\n| sort desc _time\n| limit 10",
        "Office applications spawning script hosts/cmd — MITRE T1566.001 (Spearphishing Attachment). One of the highest-fidelity detection patterns for macro-based attacks.",
        ["filter", "fields", "sort", "limit", "xdr_data", "process", "T1566.001"],
    ),
    (
        "investigation", "xdr_data",
        "Top SHA256 hashes by process executions (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START and action_process_image_sha256 != null\n| comp count() as cnt, count_distinct(agent_hostname) as hosts by action_process_image_sha256, action_process_image_name\n| sort desc cnt\n| limit 10",
        "Most-executed binaries by hash. The SHA256 is reputation-lookup-ready (VT, ThreatGrid, internal allowlists). Pair with host-count for blast-radius assessment.",
        ["filter", "comp", "sort", "limit", "xdr_data", "process", "hash"],
    ),
    (
        "detection", "xdr_data",
        "Rare process hashes — fewer than 3 executions (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START and action_process_image_sha256 != null\n| comp count() as cnt by action_process_image_sha256, action_process_image_name\n| filter cnt < 3\n| sort asc cnt\n| limit 10",
        "Rare-by-hash executions. New + unfamiliar binaries surface as low-count rows. The pattern relies on hash distinctiveness to catch packed/repacked malware that varies its filename.",
        ["filter", "comp", "sort", "limit", "xdr_data", "process", "rare", "hash"],
    ),
    (
        "investigation", "xdr_data",
        "Process image paths by directory (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START and action_process_image_path != null\n| alter dir = arrayindex(regextract(action_process_image_path, \"^(.+)\\\\\\\\[^\\\\\\\\]+$\"), 0)\n| comp count() as cnt by dir\n| sort desc cnt\n| limit 10",
        "Aggregates process executions by directory. Useful for understanding which install locations dominate + spotting unusual directories. Uses regextract to drop the basename.",
        ["filter", "alter", "comp", "sort", "limit", "xdr_data", "process", "regextract"],
    ),
    (
        "detection", "xdr_data",
        "Processes signed with non-Microsoft cert in System32 (24h, T1036.005)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| filter lowercase(action_process_image_path) contains \"system32\\\\\"\n| filter action_process_signature_vendor != null and lowercase(action_process_signature_vendor) != \"microsoft corporation\"\n| fields _time, agent_hostname, action_process_image_path, action_process_signature_vendor, action_process_signature_status\n| sort desc _time\n| limit 10",
        "Binaries running from System32 signed by a non-Microsoft vendor — MITRE T1036.005 (Match Legitimate Name or Location). High-fidelity masquerading indicator.",
        ["filter", "fields", "sort", "limit", "xdr_data", "process", "T1036.005"],
    ),

    # ─── xdr_data — broader file patterns ───────────────────────
    (
        "detection", "xdr_data",
        "Files written with double extension (24h, T1036.007)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.FILE\n| filter action_file_path ~= \"(?i)\\\\.(pdf|doc|xls|jpg|png|txt|zip)\\\\.(exe|scr|bat|cmd|com|lnk)$\"\n| fields _time, agent_hostname, action_process_image_name, action_file_path\n| sort desc _time\n| limit 10",
        "Files written with double-extension naming (e.g. report.pdf.exe). MITRE T1036.007 — common social-engineering trick that exploits Windows's hide-extension default.",
        ["filter", "fields", "sort", "limit", "xdr_data", "file", "T1036.007"],
    ),
    (
        "detection", "xdr_data",
        "Large files written by non-system processes (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.FILE and event_sub_type = ENUM.FILE_WRITE\n| filter action_file_size > 100000000\n| filter lowercase(actor_process_image_name) not in (\"system\", \"svchost.exe\", \"explorer.exe\", \"wsappx.exe\", \"taskhostw.exe\")\n| fields _time, agent_hostname, actor_process_image_name, action_file_path, action_file_size\n| sort desc action_file_size\n| limit 10",
        "Large file writes (>100MB) by non-system processes — possible exfiltration staging, ransomware encryption progress, or unexpected log production. The exclusion list filters common system writers.",
        ["filter", "fields", "sort", "limit", "xdr_data", "file"],
    ),
    (
        "investigation", "xdr_data",
        "Top file-write directories (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.FILE and action_file_path != null\n| alter dir = arrayindex(regextract(action_file_path, \"^(.+)\\\\\\\\[^\\\\\\\\]+$\"), 0)\n| comp count() as writes by dir\n| sort desc writes\n| limit 10",
        "Directory-level file-write distribution. Reveals which paths are most-written-to in the tenant — useful for tuning detections (exclude noisy paths) + spotting unusual destinations.",
        ["filter", "alter", "comp", "sort", "limit", "xdr_data", "file"],
    ),

    # ─── xdr_data — broader network patterns ────────────────────
    (
        "detection", "xdr_data",
        "Outbound to RFC1918-only ports from public destinations (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK and action_remote_port in (445, 139, 135, 3389)\n| filter not incidr(action_remote_ip, \"10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8\")\n| fields _time, agent_hostname, action_remote_ip, action_remote_port\n| sort desc _time\n| limit 10",
        "Connections to Windows-internal ports (SMB 445, NetBIOS 139, RPC 135, RDP 3389) on PUBLIC IPs. Highly suspicious — these ports should never traverse the internet. Misconfiguration or attacker activity.",
        ["filter", "fields", "sort", "limit", "xdr_data", "network", "incidr"],
    ),
    (
        "detection", "xdr_data",
        "Beaconing pattern — periodic small connections (1h)",
        "config timeframe = 1h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK and action_remote_ip != null\n| comp count() as connections, sum(action_total_upload) as upload, sum(action_total_download) as download by agent_hostname, action_remote_ip\n| filter connections >= 30 and upload < 100000\n| sort desc connections\n| limit 10",
        "Likely beaconing — many small connections to a single remote IP. Threshold: 30+ connections + <100KB total upload in 1 hour. C2 callbacks typically match this signature.",
        ["filter", "comp", "sort", "limit", "xdr_data", "network", "beacon", "c2"],
    ),
    (
        "detection", "xdr_data",
        "Connections from non-browser processes to HTTP/S ports (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK and action_remote_port in (80, 443, 8080)\n| filter lowercase(actor_process_image_name) not in (\"chrome.exe\", \"firefox.exe\", \"msedge.exe\", \"iexplore.exe\", \"safari.exe\", \"opera.exe\", \"brave.exe\", \"svchost.exe\", \"system\")\n| comp count() as cnt by actor_process_image_name\n| sort desc cnt\n| limit 10",
        "Non-browser processes making web requests. Often legitimate (update agents, telemetry) but a useful triage starting-point for finding rogue clients that shouldn't be talking to the internet.",
        ["filter", "comp", "sort", "limit", "xdr_data", "network"],
    ),
    (
        "investigation", "xdr_data",
        "Top source/destination IP pairs by data volume (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK\n| comp sum(action_total_upload) as bytes_out, sum(action_total_download) as bytes_in, count() as cnt by action_local_ip, action_remote_ip\n| sort desc bytes_out\n| limit 10",
        "Top network conversation pairs by outbound volume. Useful for understanding chatty workloads + identifying potential exfiltration flows.",
        ["filter", "comp", "sort", "limit", "xdr_data", "network"],
    ),

    # ─── xdr_data — login + auth events ─────────────────────────
    (
        "detection", "xdr_data",
        "Login attempts on Windows hosts (24h, T1078)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.EVENT_LOG and event_id in (4624, 4625)\n| comp count() as attempts, count_distinct(actor_effective_username) as unique_users by agent_hostname, event_id\n| sort desc attempts\n| limit 10",
        "Windows authentication events — 4624 (success) + 4625 (failure). Per-host attempt count + unique-user count. MITRE T1078 Valid Accounts baseline data.",
        ["filter", "comp", "sort", "limit", "xdr_data", "auth", "T1078"],
    ),

    # ─── endpoints — broader inventory ───────────────────────────
    (
        "investigation", "endpoints",
        "Agent version distribution",
        "dataset = endpoints\n| comp count() as cnt by agent_version, platform\n| sort desc cnt\n| limit 10",
        "Agent version landscape across the fleet. Useful for rollout-progress tracking + spotting outdated agents that need upgrading.",
        ["comp", "sort", "limit", "endpoints"],
    ),
    (
        "detection", "endpoints",
        "Endpoints with active scan profile (potential outliers)",
        "dataset = endpoints\n| filter scanner_status != null\n| fields endpoint_name, scanner_status, scan_status, last_seen, operating_system\n| sort asc last_seen\n| limit 10",
        "Endpoints currently running a vulnerability scan or with scan-related state. Useful for noticing stuck scans + endpoints that need attention.",
        ["filter", "fields", "sort", "limit", "endpoints"],
    ),
    (
        "investigation", "endpoints",
        "Endpoint group distribution",
        "dataset = endpoints\n| filter group_name != null\n| comp count() as cnt by group_name\n| sort desc cnt\n| limit 10",
        "Endpoints grouped by assigned group. Surfaces fleet-organization patterns + spots groups with anomalous member counts (e.g. unintentional 'default' bucket).",
        ["filter", "comp", "sort", "limit", "endpoints"],
    ),
    (
        "detection", "endpoints",
        "Endpoints with disabled/uninstalled agent component",
        "dataset = endpoints\n| filter endpoint_status = \"CONNECTED\"\n| filter content_status != \"OK\" or scanner_status = \"DISABLED\"\n| fields endpoint_name, endpoint_status, content_status, scanner_status, last_seen\n| sort desc last_seen\n| limit 10",
        "Connected endpoints with degraded agent state — content out of sync, scanner disabled. Indicates either an upgrade in flight, a misconfigured policy, or attacker tampering.",
        ["filter", "fields", "sort", "limit", "endpoints"],
    ),
    (
        "investigation", "endpoints",
        "Endpoints by tags",
        "dataset = endpoints\n| filter endpoint_tags != null\n| arrayexpand endpoint_tags\n| comp count() as cnt by endpoint_tags\n| sort desc cnt\n| limit 10",
        "Endpoints aggregated by tag using `arrayexpand` to flatten the multi-value tag array. Useful for tag-coverage audits + finding endpoints with rare/sole tags.",
        ["filter", "arrayexpand", "comp", "sort", "limit", "endpoints"],
    ),
    (
        "investigation", "endpoints",
        "Endpoints with isolation enabled",
        "dataset = endpoints\n| filter endpoint_isolated = true\n| fields endpoint_name, endpoint_status, operating_system, last_seen, ip_address\n| sort desc last_seen\n| limit 10",
        "Currently-isolated endpoints. Returns every isolated host so the operator can confirm active containment is in place + that no host has been isolated longer than intended.",
        ["filter", "fields", "sort", "limit", "endpoints"],
    ),

    # ─── alerts — broader detection coverage ────────────────────
    (
        "investigation", "alerts",
        "Alerts by MITRE tactic + technique (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| filter mitre_tactic_id_and_name != null\n| comp count() as cnt by mitre_tactic_id_and_name, mitre_technique_id_and_name\n| sort desc cnt\n| limit 10",
        "Per-alert MITRE ATT&CK mapping. Surfaces the tenant's tactic-coverage shape — which techniques fire most. Useful for tuning rules + reporting executive-level threat-mix.",
        ["filter", "comp", "sort", "limit", "alerts", "mitre"],
    ),
    (
        "investigation", "alerts",
        "Alert detection-source breakdown (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| filter source != null\n| comp count() as cnt by source, severity\n| sort desc cnt\n| limit 10",
        "Per-detection-source alert volume by severity. Reveals which detector technology (NGFW, EDR, AVM, BIOC, IOC) fires most.",
        ["filter", "comp", "sort", "limit", "alerts"],
    ),
    (
        "investigation", "alerts",
        "Resolved-status alert breakdown (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| filter resolution_status != null\n| comp count() as cnt by resolution_status\n| sort desc cnt\n| limit 10",
        "Alert lifecycle outcomes — true-positive, false-positive, duplicate, etc. Reveals the noise/signal ratio + which detectors generate the most FP load.",
        ["filter", "comp", "sort", "limit", "alerts"],
    ),
    (
        "detection", "alerts",
        "Persistence-tactic alerts (30d, TA0003)",
        "config timeframe = 30d\n| dataset = alerts\n| filter mitre_tactic_id_and_name contains \"TA0003\"\n| fields _time, host_name, alert_name, severity, mitre_technique_id_and_name\n| sort desc _time\n| limit 10",
        "Alerts mapped to MITRE TA0003 Persistence. Captures registry/service/scheduled-task/WMI persistence detections. Hands the operator the persistence canary feed.",
        ["filter", "fields", "sort", "limit", "alerts", "mitre", "TA0003"],
    ),
    (
        "detection", "alerts",
        "Lateral-movement alerts (30d, TA0008)",
        "config timeframe = 30d\n| dataset = alerts\n| filter mitre_tactic_id_and_name contains \"TA0008\"\n| fields _time, host_name, alert_name, severity, mitre_technique_id_and_name\n| sort desc _time\n| limit 10",
        "Lateral-movement detections (MITRE TA0008). Includes PsExec, WinRM abuse, remote service creation, RDP, SMB. Critical pivot for incident-response.",
        ["filter", "fields", "sort", "limit", "alerts", "mitre", "TA0008"],
    ),
    (
        "detection", "alerts",
        "Exfiltration-tactic alerts (30d, TA0010)",
        "config timeframe = 30d\n| dataset = alerts\n| filter mitre_tactic_id_and_name contains \"TA0010\"\n| fields _time, host_name, alert_name, severity, mitre_technique_id_and_name\n| sort desc _time\n| limit 10",
        "Exfiltration detections (MITRE TA0010). Bulk uploads, archive activity, anomalous outbound. Highest-priority alerts since exfil is often the terminal phase.",
        ["filter", "fields", "sort", "limit", "alerts", "mitre", "TA0010"],
    ),
    (
        "detection", "alerts",
        "Brute-force alerts (30d, T1110)",
        "config timeframe = 30d\n| dataset = alerts\n| filter lowercase(alert_name) contains \"brute\" or lowercase(alert_name) contains \"password spray\" or lowercase(alert_name) contains \"failed login\" or mitre_technique_id_and_name contains \"T1110\"\n| fields _time, host_name, alert_name, severity, user_name\n| sort desc _time\n| limit 10",
        "Brute-force + password-spray detections (MITRE T1110). Common against external-facing services + privileged accounts.",
        ["filter", "fields", "sort", "limit", "alerts", "T1110"],
    ),
    (
        "investigation", "alerts",
        "Alert author actor — who/which engine generates which alerts (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| filter alert_source != null\n| comp count() as cnt, count_distinct(host_name) as affected_hosts by alert_source\n| sort desc cnt\n| limit 10",
        "Per-engine alert production volume + per-engine blast radius (affected hosts). Useful for the SOC manager to see which engines drive the alert workload.",
        ["filter", "comp", "sort", "limit", "alerts"],
    ),
    (
        "investigation", "alerts",
        "Top alert names by host count (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| comp count_distinct(host_name) as host_count, count() as alert_count by alert_name\n| sort desc host_count\n| limit 10",
        "Alert names ranked by how many distinct hosts they fired against. High host-count alerts often indicate widespread issues (env-wide misconfig, broad campaign).",
        ["filter", "comp", "sort", "limit", "alerts"],
    ),
    (
        "investigation", "alerts",
        "Alerts grouped by week (12w)",
        "config timeframe = 12w\n| dataset = alerts\n| bin _time span = 1w\n| comp count() as cnt by _time, severity\n| sort desc _time\n| limit 10",
        "Weekly alert-volume trend across severities. Useful for executive reporting + spotting macro trends (e.g. steady increase in HIGH alerts over a quarter).",
        ["filter", "bin", "comp", "sort", "limit", "alerts"],
    ),

    # ─── issues — XDM parallels + new patterns ──────────────────
    (
        "investigation", "issues",
        "Top issue names (7d)",
        "config timeframe = 7d\n| dataset = issues\n| comp count() as cnt by xdm.alert.name\n| sort desc cnt\n| limit 10",
        "Top issue names via XDM-normalized schema. Direct parallel to the alerts top-name query — XSIAM customers often consume via this schema.",
        ["filter", "comp", "sort", "limit", "issues", "xdm"],
    ),
    (
        "investigation", "issues",
        "Issues by source product (7d)",
        "config timeframe = 7d\n| dataset = issues\n| filter xdm.source.product != null\n| comp count() as cnt by xdm.source.product, xdm.alert.severity\n| sort desc cnt\n| limit 10",
        "XDM source-product breakdown. xdm.source.product carries the originating telemetry product (e.g. 'Cortex XDR Analytics', 'Cortex XDR Pro'). Useful for vendor coverage analysis.",
        ["filter", "comp", "sort", "limit", "issues", "xdm"],
    ),
    (
        "detection", "issues",
        "Critical issues with affected user context (7d)",
        "config timeframe = 7d\n| dataset = issues\n| filter xdm.alert.severity = \"SEV_040_HIGH\" or xdm.alert.severity = \"SEV_050_CRITICAL\"\n| filter xdm.target.user.username != null\n| fields _time, xdm.alert.name, xdm.alert.severity, xdm.target.user.username, xdm.target.host.hostname\n| sort desc _time\n| limit 10",
        "High/Critical issues paired with the target user. XDM normalizes severity as `SEV_NNN_LABEL` strings — note the prefix when filtering.",
        ["filter", "fields", "sort", "limit", "issues", "xdm"],
    ),

    # ─── incidents — more lifecycle ─────────────────────────────
    (
        "investigation", "incidents",
        "Incidents with high alert-count (7d)",
        "config timeframe = 7d\n| dataset = incidents\n| filter alert_count > 0\n| fields _time, incident_id, incident_name, alert_count, host_count, severity, status\n| sort desc alert_count\n| limit 10",
        "Largest incidents by alert count. Larger incidents usually need more attention + are more likely to contain a real campaign vs single false positive.",
        ["filter", "fields", "sort", "limit", "incidents"],
    ),
    (
        "investigation", "incidents",
        "Incidents grouped by assigned operator (30d)",
        "config timeframe = 30d\n| dataset = incidents\n| filter assigned_user_pretty_name != null\n| comp count() as cnt, count_distinct(status) as status_count by assigned_user_pretty_name\n| sort desc cnt\n| limit 10",
        "Per-operator workload distribution. Reveals which analysts are carrying the most cases + whether load is balanced.",
        ["filter", "comp", "sort", "limit", "incidents"],
    ),

    # ─── agent_auditing — broader coverage ───────────────────────
    (
        "detection", "agent_auditing",
        "Policy-change events (7d)",
        "config timeframe = 7d\n| dataset = agent_auditing\n| filter agent_auditing_subtype = ENUM.AGENT_AUDIT_POLICY_CHANGE\n| fields _time, endpoint_name, description, action_user_pretty_name\n| sort desc _time\n| limit 10",
        "Agent policy-change history. Track which policies were applied to which endpoints + who pushed the change. Important for change-control + incident-response forensics.",
        ["filter", "fields", "sort", "limit", "agent_auditing"],
    ),
    (
        "investigation", "agent_auditing",
        "Agent installations + upgrades (7d)",
        "config timeframe = 7d\n| dataset = agent_auditing\n| filter agent_auditing_subtype in (ENUM.AGENT_AUDIT_INSTALL, ENUM.AGENT_AUDIT_UPGRADE)\n| comp count() as cnt by endpoint_name, agent_auditing_subtype\n| sort desc cnt\n| limit 10",
        "Agent install + upgrade activity. Reveals rollout progress + endpoints that have had unusual lifecycle activity.",
        ["filter", "comp", "sort", "limit", "agent_auditing"],
    ),

    # ─── host_inventory — broader patterns ───────────────────────
    (
        "investigation", "host_inventory",
        "Hosts by domain membership",
        "dataset = host_inventory\n| filter ad_domain != null\n| comp count() as cnt by ad_domain\n| sort desc cnt\n| limit 10",
        "Active Directory domain membership distribution across discovered hosts. Useful for AD-scope audits + spotting unexpected domains.",
        ["filter", "comp", "sort", "limit", "host_inventory"],
    ),
    (
        "investigation", "host_inventory",
        "Recently-discovered hosts (7d)",
        "config timeframe = 7d\n| dataset = host_inventory\n| fields _time, hostname, ad_domain, operating_system_family, first_seen\n| sort desc first_seen\n| limit 10",
        "New hosts discovered in the last 7 days. Could be legitimate (new deployments) or unexpected (rogue devices, shadow IT).",
        ["filter", "fields", "sort", "limit", "host_inventory"],
    ),

    # ─── asset_inventory ─────────────────────────────────────────
    (
        "investigation", "asset_inventory",
        "Assets by category",
        "dataset = asset_inventory\n| comp count() as cnt by category\n| sort desc cnt\n| limit 10",
        "Asset distribution by category (endpoint, server, network device, IoT, etc.). Useful for asset-coverage baseline.",
        ["comp", "sort", "limit", "asset_inventory"],
    ),
    (
        "investigation", "asset_inventory",
        "Assets by criticality",
        "dataset = asset_inventory\n| filter criticality != null\n| comp count() as cnt by criticality, category\n| sort desc cnt\n| limit 10",
        "Asset criticality distribution. Reveals what proportion of inventory is critical-tier — important for prioritizing alerts impacting high-criticality assets.",
        ["filter", "comp", "sort", "limit", "asset_inventory"],
    ),

    # ─── cloud_audit_logs — broader cloud patterns ───────────────
    (
        "detection", "cloud_audit_logs",
        "Failed cloud actions (7d)",
        "config timeframe = 7d\n| dataset = cloud_audit_logs\n| filter operation_status != \"success\"\n| comp count() as cnt by cloud_provider, operation_name, operation_status\n| sort desc cnt\n| limit 10",
        "Failed cloud operations by provider/op/status. High failure counts on sensitive ops (DeleteRole, AssumeRole) often indicate probing or misconfig.",
        ["filter", "comp", "sort", "limit", "cloud_audit_logs", "cloud"],
    ),
    (
        "investigation", "cloud_audit_logs",
        "Cloud activity by user (7d)",
        "config timeframe = 7d\n| dataset = cloud_audit_logs\n| filter user_name != null\n| comp count() as cnt, count_distinct(operation_name) as unique_ops by user_name, cloud_provider\n| sort desc cnt\n| limit 10",
        "Per-user cloud-activity volume + breadth (unique operations). Useful for spotting accounts with anomalously broad access patterns.",
        ["filter", "comp", "sort", "limit", "cloud_audit_logs", "cloud"],
    ),
    (
        "detection", "cloud_audit_logs",
        "IAM-related cloud actions (7d, T1098)",
        "config timeframe = 7d\n| dataset = cloud_audit_logs\n| filter lowercase(operation_name) contains \"iam\" or lowercase(operation_name) contains \"role\" or lowercase(operation_name) contains \"policy\" or lowercase(operation_name) contains \"user\"\n| fields _time, cloud_provider, user_name, operation_name, operation_status\n| sort desc _time\n| limit 10",
        "Identity + access management changes (MITRE T1098 — Account Manipulation). High-value security signal — IAM tampering enables persistence + privilege escalation.",
        ["filter", "fields", "sort", "limit", "cloud_audit_logs", "cloud", "T1098"],
    ),
    (
        "investigation", "cloud_audit_logs",
        "Cloud activity by region (7d)",
        "config timeframe = 7d\n| dataset = cloud_audit_logs\n| filter cloud_region != null\n| comp count() as cnt by cloud_provider, cloud_region\n| sort desc cnt\n| limit 10",
        "Per-region cloud-activity volume. Useful for spotting unexpected regions in use (could indicate compromised credentials being used from atypical geographies).",
        ["filter", "comp", "sort", "limit", "cloud_audit_logs", "cloud"],
    ),

    # ─── va_cves / va_endpoints — more vulnerability views ─────
    (
        "investigation", "va_cves",
        "CVEs by severity distribution",
        "dataset = va_cves\n| comp count_distinct(cve_id) as unique_cves by cve_severity\n| sort desc unique_cves\n| limit 10",
        "Distinct CVE counts by severity bucket. Snapshot of the tenant's overall vulnerability shape.",
        ["comp", "sort", "limit", "va_cves", "vulnerability"],
    ),
    (
        "detection", "va_cves",
        "Recently-detected critical or high CVEs (7d)",
        "config timeframe = 7d\n| dataset = va_cves\n| filter cve_severity in (\"CRITICAL\", \"HIGH\")\n| comp count() as detections, count_distinct(endpoint_id) as affected_hosts by cve_id, cve_severity\n| sort desc affected_hosts\n| limit 10",
        "Newly-detected critical + high CVEs from the last week with blast-radius (affected hosts). The output is patch-prioritization ready.",
        ["filter", "comp", "sort", "limit", "va_cves", "vulnerability"],
    ),
    (
        "investigation", "va_endpoints",
        "Endpoints by total vulnerability count",
        "dataset = va_endpoints\n| comp count_distinct(cve_id) as cve_count by endpoint_name, operating_system\n| sort desc cve_count\n| limit 10",
        "Top-vulnerable hosts by raw CVE count. Pair with the critical-CVE pivot for risk-based prioritization.",
        ["comp", "sort", "limit", "va_endpoints", "vulnerability"],
    ),

    # ─── Advanced analytical patterns ────────────────────────────
    (
        "detection", "xdr_data",
        "Top-3 processes per host (window-comp top-n pattern, 24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| comp count() as cnt by agent_hostname, action_process_image_name\n| windowcomp row_number() by agent_hostname sort desc cnt as rank\n| filter rank <= 3\n| sort asc agent_hostname, asc rank\n| limit 10",
        "Top-3 most-spawned processes PER HOST — classic window-function top-N pattern. `row_number()` partitioned by host + sorted by count gives the per-host rank.",
        ["filter", "comp", "windowcomp", "sort", "limit", "xdr_data", "process", "top-n"],
    ),
    (
        "investigation", "xdr_data",
        "Process execution percentage of host total (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| comp count() as cnt by agent_hostname, action_process_image_name\n| windowcomp sum(cnt) by agent_hostname as host_total\n| alter pct = multiply(divide(cnt, host_total), 100)\n| sort desc pct\n| limit 10",
        "Each process's share of its host's total execution count. Single dominant process (>50%) on a host often indicates loop / batch activity worth investigating.",
        ["filter", "comp", "windowcomp", "alter", "sort", "limit", "xdr_data", "process", "math"],
    ),
    (
        "detection", "alerts",
        "Alerts and process events join — top alerts with running processes (24h)",
        "config timeframe = 24h\n| dataset = alerts\n| filter severity in (\"HIGH\", \"CRITICAL\")\n| fields _time, host_name, alert_name, severity\n| join type=left (dataset = xdr_data | filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START | comp count() as proc_count by agent_hostname) as ctx on host_name = ctx.agent_hostname\n| fields _time, host_name, alert_name, severity, ctx.proc_count\n| sort desc _time\n| limit 10",
        "JOIN — pair each high/critical alert with the host's process-execution count for context. High alert + high proc-count = busy host worth deep investigation.",
        ["filter", "join", "fields", "sort", "limit", "alerts", "xdr_data", "enrichment"],
    ),
    (
        "investigation", "xdr_data",
        "Earliest + latest process times per host (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| comp min(_time) as first_seen, max(_time) as last_seen, count() as cnt by agent_hostname\n| alter duration_ms = subtract(to_integer(last_seen), to_integer(first_seen))\n| sort desc cnt\n| limit 10",
        "Per-host first/last process time + active duration. `min` + `max` aggregations bound the activity window; the duration column shows how long the host has been active.",
        ["filter", "comp", "alter", "sort", "limit", "xdr_data", "process", "math"],
    ),
    (
        "detection", "xdr_data",
        "Process executions outside business hours (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| alter hour_of_day = format_timestamp(\"%H\", _time)\n| filter hour_of_day in (\"00\", \"01\", \"02\", \"03\", \"04\", \"05\", \"22\", \"23\")\n| comp count() as cnt by agent_hostname, action_process_image_name, actor_effective_username\n| sort desc cnt\n| limit 10",
        "Process executions during off-hours (22:00-05:00). Uses `format_timestamp` to extract the hour. After-hours activity by interactive users is a common compromise indicator.",
        ["filter", "alter", "comp", "sort", "limit", "xdr_data", "process", "format_timestamp"],
    ),
    (
        "investigation", "xdr_data",
        "Process activity by day-of-week (7d)",
        "config timeframe = 7d\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| alter dow = format_timestamp(\"%A\", _time)\n| comp count() as cnt by dow\n| sort desc cnt\n| limit 10",
        "Day-of-week activity distribution. Weekend activity volumes vs weekday are useful for baseline + spotting bursts on unusual days.",
        ["filter", "alter", "comp", "sort", "limit", "xdr_data", "process", "format_timestamp"],
    ),
    (
        "detection", "alerts",
        "Earliest alert per host + its detail (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| filter host_name != null\n| windowcomp row_number() by host_name sort asc _time as rn\n| filter rn = 1\n| fields _time, host_name, alert_name, severity\n| sort desc _time\n| limit 10",
        "First-seen alert per host — useful for compromise-onset triage. `row_number()` partitioned by host + sorted ascending gives the earliest row per host.",
        ["filter", "windowcomp", "fields", "sort", "limit", "alerts", "row_number"],
    ),
    (
        "investigation", "alerts",
        "Daily alert count with running 3-day average (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| bin _time span = 1d\n| comp count() as daily_cnt by _time\n| windowcomp avg(daily_cnt) frame between 2 preceding and current row sort asc _time as rolling_avg_3d\n| sort desc _time\n| limit 10",
        "Daily alert volume with a 3-day rolling average. The framed `windowcomp` defines a sliding window. Useful for trend-line / anomaly visualizations.",
        ["filter", "bin", "comp", "windowcomp", "sort", "limit", "alerts", "rolling"],
    ),

    # ─── DEDUP variations ───────────────────────────────────────
    (
        "investigation", "xdr_data",
        "Unique processes seen across the fleet (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| dedup action_process_image_name\n| fields action_process_image_name\n| sort asc action_process_image_name\n| limit 10",
        "Fleet-wide process whitelist candidate set — every unique process name seen. The first 10 alphabetically. Useful for building an allowlist starter.",
        ["filter", "dedup", "fields", "sort", "limit", "xdr_data"],
    ),

    # ─── ALERT severity → user / host pivots ────────────────────
    (
        "investigation", "alerts",
        "Top affected users by critical alerts (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| filter severity = \"CRITICAL\" and user_name != null\n| comp count() as alerts, count_distinct(alert_name) as unique_alert_types by user_name\n| sort desc alerts\n| limit 10",
        "Users with the most critical-severity alerts. High counts on a single user often indicate that user was the entry vector for a campaign.",
        ["filter", "comp", "sort", "limit", "alerts"],
    ),
    (
        "investigation", "alerts",
        "Alerts with category + tactic (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| filter category != null\n| comp count() as cnt by category, mitre_tactic_id_and_name\n| sort desc cnt\n| limit 10",
        "Cross-tab of alert category vs MITRE tactic. Reveals how the tenant's categories distribute across tactics.",
        ["filter", "comp", "sort", "limit", "alerts", "mitre"],
    ),

    # ─── STRING/regex helpers ───────────────────────────────────
    (
        "detection", "xdr_data",
        "Process command lines containing base64-encoded blocks (24h, T1027)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| filter action_process_image_command_line ~= \"[A-Za-z0-9+/]{50,}={0,2}\"\n| fields _time, agent_hostname, action_process_image_name, action_process_image_command_line\n| sort desc _time\n| limit 10",
        "Command lines containing long base64-looking blocks (MITRE T1027 — Obfuscated Files or Information). The regex matches 50+ base64 chars optionally padded with =.",
        ["filter", "fields", "sort", "limit", "xdr_data", "process", "T1027", "regex"],
    ),
    (
        "investigation", "alerts",
        "Alert names — uppercased breakdown (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| alter alert_upper = uppercase(alert_name)\n| comp count() as cnt by alert_upper\n| sort desc cnt\n| limit 10",
        "Case-normalized alert-name aggregation. Useful when alert names show up with mixed casing from different sources.",
        ["filter", "alter", "comp", "sort", "limit", "alerts", "uppercase"],
    ),
    (
        "investigation", "xdr_data",
        "Process names split by hyphen — first segment (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START and action_process_image_name != null\n| alter prefix = arrayindex(split(action_process_image_name, \"-\"), 0)\n| comp count() as cnt by prefix\n| sort desc cnt\n| limit 10",
        "Splits process names on hyphen + aggregates by the first segment. Useful for vendor-prefix aggregation (e.g. `chrome-helper-*` all become `chrome`).",
        ["filter", "alter", "comp", "sort", "limit", "xdr_data", "process", "split"],
    ),

    # ─── BIN spans — different granularities ─────────────────────
    (
        "investigation", "xdr_data",
        "5-minute bin of network connections per host (1h)",
        "config timeframe = 1h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK\n| bin _time span = 5m\n| comp count() as connections by _time, agent_hostname\n| sort desc _time, connections\n| limit 10",
        "Fine-grained (5min) network connection rate per host. Useful for tight burst-detection windows during incident response.",
        ["filter", "bin", "comp", "sort", "limit", "xdr_data", "network"],
    ),
    (
        "investigation", "alerts",
        "Daily alert trend by category (14d)",
        "config timeframe = 14d\n| dataset = alerts\n| filter category != null\n| bin _time span = 1d\n| comp count() as cnt by _time, category\n| sort desc _time\n| limit 10",
        "Two-week daily alert trend per category. Reveals category-level patterns + spikes.",
        ["filter", "bin", "comp", "sort", "limit", "alerts"],
    ),

    # ─── INCIDR variations ─────────────────────────────────────
    (
        "investigation", "xdr_data",
        "Network connections within specific subnet (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK and action_remote_ip != null\n| filter incidr(action_remote_ip, \"10.0.0.0/8\")\n| comp count() as cnt by action_remote_ip\n| sort desc cnt\n| limit 10",
        "Connections targeting the 10/8 RFC1918 range. Useful for understanding internal-network communication patterns.",
        ["filter", "comp", "sort", "limit", "xdr_data", "network", "incidr"],
    ),

    # ─── COMPLEX multi-stage — cross-dataset enrichment ─────────
    (
        "detection", "alerts",
        "High-severity alerts with rare hosts (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| filter severity in (\"HIGH\", \"CRITICAL\")\n| comp count() as alerts_per_host by host_name, severity\n| filter alerts_per_host = 1\n| sort desc alerts_per_host\n| limit 10",
        "Hosts that only had ONE high/critical alert in the timeframe. Lower-noise hosts where a single hit is more meaningful + more likely a true positive.",
        ["filter", "comp", "sort", "limit", "alerts", "rare"],
    ),
    (
        "investigation", "xdr_data",
        "Mean process-execution counts per host (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| comp count() as host_total by agent_hostname\n| comp avg(host_total) as mean_per_host, count() as host_count\n| limit 10",
        "Fleet-level statistic — average process executions per host + total host count. Useful baseline for sizing + outlier-comparison queries.",
        ["filter", "comp", "limit", "xdr_data", "process", "stats"],
    ),

    # ─── XDR_DATA — auth/login events via preset ────────────────
    (
        "detection", "xdr_data",
        "Failed login attempts via event_id 4625 (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.EVENT_LOG and event_id = 4625\n| comp count() as failures, count_distinct(actor_effective_username) as unique_users by agent_hostname\n| sort desc failures\n| limit 10",
        "Failed Windows logon attempts (4625). High failure counts on a single host suggest brute-force / spray. Pair with successful-login data for context.",
        ["filter", "comp", "sort", "limit", "xdr_data", "auth", "T1110"],
    ),

    # ─── XDR_DATA — registry — additional persistence patterns ─
    (
        "detection", "xdr_data",
        "Registry writes under HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.REGISTRY\n| filter action_registry_key_name contains \"\\\\CurrentVersion\\\\Run\"\n| fields _time, agent_hostname, actor_process_image_name, action_registry_key_name, action_registry_value_name, action_registry_data\n| sort desc _time\n| limit 10",
        "Specific persistence-via-Run-key pattern. Returns the data being written for IOC extraction (path of persistent payload).",
        ["filter", "fields", "sort", "limit", "xdr_data", "registry", "T1547"],
    ),

    # ─── XDR_DATA — DNS query patterns ──────────────────────────
    (
        "detection", "xdr_data",
        "Long DNS queries — possible tunneling (24h, T1071.004)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK and action_remote_port = 53\n| filter dns_query_name != null\n| alter q_len = len(dns_query_name)\n| filter q_len > 100\n| fields _time, agent_hostname, dns_query_name, q_len\n| sort desc q_len\n| limit 10",
        "Long DNS query names (>100 chars) — DNS tunneling indicator (MITRE T1071.004 Application Layer Protocol: DNS). Tunnel encodings produce abnormally long labels.",
        ["filter", "alter", "fields", "sort", "limit", "xdr_data", "network", "dns", "T1071.004"],
    ),

    # ─── XDR_DATA — endpoint isolation / response ───────────────
    (
        "investigation", "endpoints",
        "Endpoints by content-version (rollout-progress view)",
        "dataset = endpoints\n| filter content_version != null\n| comp count() as cnt by content_version\n| sort desc cnt\n| limit 10",
        "Content-version distribution across endpoints. Reveals signature/content rollout progress + identifies endpoints lagging the latest content.",
        ["filter", "comp", "sort", "limit", "endpoints"],
    ),

    # ─── ISSUES — additional XDM patterns ───────────────────────
    (
        "investigation", "issues",
        "Issues by tactic via XDM (7d)",
        "config timeframe = 7d\n| dataset = issues\n| filter xdm.alert.mitre_tactic_id_and_name != null\n| comp count() as cnt by xdm.alert.mitre_tactic_id_and_name\n| sort desc cnt\n| limit 10",
        "XDM-normalized MITRE tactic distribution. Direct parallel to alerts.mitre_tactic_id_and_name.",
        ["filter", "comp", "sort", "limit", "issues", "xdm", "mitre"],
    ),

    # ─── COUNT_DISTINCT patterns ────────────────────────────────
    (
        "investigation", "alerts",
        "Unique alert names per detector source (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| filter alert_source != null\n| comp count_distinct(alert_name) as unique_rules, count() as fires by alert_source\n| sort desc unique_rules\n| limit 10",
        "Per-detector source: how many unique alert rules fired + how many total fires. Reveals detector breadth (many rules) vs depth (few rules, many fires).",
        ["filter", "comp", "sort", "limit", "alerts"],
    ),
    (
        "investigation", "xdr_data",
        "Unique remote IPs per host (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK and action_remote_ip != null\n| comp count_distinct(action_remote_ip) as unique_destinations by agent_hostname\n| sort desc unique_destinations\n| limit 10",
        "Per-host unique-destination count. Hosts with abnormally high destination counts could be scanners (legitimate or otherwise) or compromised hosts spraying connections.",
        ["filter", "comp", "sort", "limit", "xdr_data", "network"],
    ),

    # ─── ARRAYS — multi-value handling ──────────────────────────
    (
        "investigation", "alerts",
        "Alerts with MITRE tactic array unwound (30d)",
        "config timeframe = 30d\n| dataset = alerts\n| filter mitre_tactic_id_and_name != null\n| arrayexpand mitre_tactic_id_and_name\n| comp count() as cnt by mitre_tactic_id_and_name\n| sort desc cnt\n| limit 10",
        "MITRE tactics are sometimes multi-valued per alert. `arrayexpand` flattens the array so each tactic is counted separately — gives a true tactic-frequency view.",
        ["filter", "arrayexpand", "comp", "sort", "limit", "alerts", "mitre"],
    ),

    # ─── COALESCE + null handling ───────────────────────────────
    (
        "investigation", "xdr_data",
        "Process executions with effective user fallback (24h)",
        "config timeframe = 24h\n| dataset = xdr_data\n| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START\n| alter user = coalesce(actor_effective_username, actor_primary_username, \"unknown\")\n| comp count() as cnt by user\n| sort desc cnt\n| limit 10",
        "Per-user execution count with `coalesce` to fall back to primary_username when effective is null, then to literal 'unknown'. Robust against missing-data gaps.",
        ["filter", "alter", "comp", "sort", "limit", "xdr_data", "user", "coalesce"],
    ),

    # ─── EXFIL-flavor queries — connection bursts ──────────────
    (
        "detection", "xdr_data",
        "Hosts with >1GB outbound in 1 hour",
        "config timeframe = 1h\n| dataset = xdr_data\n| filter event_type = ENUM.NETWORK\n| comp sum(action_total_upload) as upload_bytes by agent_hostname\n| filter upload_bytes > 1000000000\n| sort desc upload_bytes\n| limit 10",
        "Heavy uploaders in a 1-hour window (>1GB). Tight time window catches active exfiltration; threshold filters out cumulative noise.",
        ["filter", "comp", "sort", "limit", "xdr_data", "network", "exfil"],
    ),
]


# ─── KB-entry writer ────────────────────────────────────────────────


def stable_hash(text: str, n: int = 8) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


def slugify(title: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
    return s[:max_len].rstrip("-")


def write_kb_entry(seq_id: int, category: str, dataset: str, title: str,
                   query_body: str, when_to_use: str, tags: list[str]) -> Path:
    entry_id = f"XQL-{seq_id:03d}-{stable_hash(title + query_body)}"
    filename = f"{seq_id:03d}-{slugify(title)}.md"
    path = ENTRIES_DIR / filename

    yaml_tags = "\n".join(f"  - {t}" for t in tags)
    body = f"""---
id: {entry_id}
title: {title}
category: {category}
dataset: {dataset}
tags:
{yaml_tags}
---

# {title}

**Dataset**: `{dataset}`

```sql
{query_body.strip()}
```

## When to use

{when_to_use}

## Variations

_(v0.7.0 hand-curated — variations not yet authored. Operator's
curation pass adds these.)_

## Source

Hand-curated for v0.7.0's 100-query KB expansion. Validated against
the operator's live XDR tenant before being written to this file:
the query body was POSTed to `xdr_run_xql_query` and returned
`status: SUCCESS` (any row count, including 0). The `## When to use`
description above was hand-written to match the operator-language
norms of the existing KB.
"""
    path.write_text(body, encoding="utf-8")
    return path


# ─── Main ────────────────────────────────────────────────────────────


def main() -> None:
    print(f"v0.7.0 — building & validating {len(TEMPLATES)} XQL queries")
    print(f"Target: {AGENT_URL}")
    print(f"Entries dir: {ENTRIES_DIR}")
    print()

    successes: list[tuple[int, str, str]] = []
    failures: list[tuple[str, str]] = []
    next_id = START_ID

    for i, (category, dataset, title, query, when_to_use, tags) in enumerate(TEMPLATES, 1):
        print(f"[{i:3d}/{len(TEMPLATES)}] {category:14s} {dataset:25s} {title[:60]}")
        # Ensure `| limit N` exists; add if missing.
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
            successes.append((next_id, title, str(path.name)))
            next_id += 1
        else:
            err = result.get("error") or status
            err_str = str(err)[:200]
            print(f"        FAIL: {err_str}")
            failures.append((title, err_str))

    print()
    print(f"=" * 72)
    print(f"DONE: {len(successes)} validated + written, {len(failures)} failed")
    print(f"=" * 72)
    if failures:
        print("\nFailed templates (won't be in KB):")
        for title, err in failures[:20]:
            print(f"  ✗ {title[:60]} :: {err[:80]}")


if __name__ == "__main__":
    main()
