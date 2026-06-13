#!/usr/bin/env bash
# bootstrap_loop_jobs.sh (v0.2.11) — codify the autonomous investigation
# loop's two scheduler jobs so the loop is reproducible and survives a
# volume wipe / fresh install.
#
# WHY: the `guardian-incident-seeder` + `guardian-investigation-loop` jobs
# were created at runtime via the jobs API and lived ONLY in jobs.db on the
# deployed install. A `WIPE_VOLUMES=true` reinstall (Scenario 3) erased them,
# leaving the loop unrecoverable and undocumented. This script is the
# canonical, version-controlled definition — re-run it to (re)provision both
# jobs. It is idempotent: PATCH if the job already exists, else POST.
#
# The investigation-loop prompt uses the v0.2.11 STRUCTURAL issues_list
# filters (source_ref_not_null + order=asc) so the loop's "oldest open Issue
# that tracks an XSOAR incident" pick is deterministic — no longer dependent
# on the model correctly skipping sourceless Issues / reversing a list.
#
# Usage:
#   GUARDIAN_API_KEY=guardian_ak_...  AGENT_URL=https://localhost:3001 \
#     scripts/bootstrap_loop_jobs.sh
#
#   AGENT_URL  the agent TLS proxy (default https://localhost:3000). On
#              guardian-vm, tunnel remote :3000 → local :3001 and pass that.
#   Bearer     GUARDIAN_API_KEY (an agent:* API key) or MCP_TOKEN.
#
# CAUTION: this is a DEV/DEMO harness. The seeder injects SYNTHETIC incidents
# (prefixed `[guardian-loop] `) into the connected XSOAR tenant. Do NOT run it
# against a production tenant you don't want seeded with test data.
set -euo pipefail

AGENT_URL="${AGENT_URL:-https://localhost:3000}"
BEARER="${GUARDIAN_API_KEY:-${MCP_TOKEN:-}}"
if [ -z "$BEARER" ]; then
  echo "ERROR: set GUARDIAN_API_KEY (an agent:* API key) or MCP_TOKEN." >&2
  exit 1
fi

upsert_job() {
  local name="$1" payload="$2" code
  code=$(curl -sk -o /dev/null -w '%{http_code}' --max-time 20 \
    -H "Authorization: Bearer $BEARER" "$AGENT_URL/api/agent/jobs/$name" || echo 000)
  if [ "$code" = "200" ]; then
    printf '  PATCH %-30s' "$name"
    curl -sk -o /dev/null -w ' -> %{http_code}\n' --max-time 30 -X PATCH \
      -H "Authorization: Bearer $BEARER" -H "Content-Type: application/json" \
      -d "$payload" "$AGENT_URL/api/agent/jobs/$name"
  else
    printf '  POST  %-30s' "$name"
    curl -sk -o /dev/null -w ' -> %{http_code}\n' --max-time 30 -X POST \
      -H "Authorization: Bearer $BEARER" -H "Content-Type: application/json" \
      -d "$payload" "$AGENT_URL/api/agent/jobs"
  fi
}

# --- Job definitions (built with python3 for safe JSON encoding) ----------
SEEDER_JSON=$(python3 - <<'PY'
import json
print(json.dumps({
  "name": "guardian-incident-seeder",
  "cron": "0 * * * *",
  "timezone": "UTC",
  "enabled": True,
  "bypass_approvals": True,
  "action": {
    "type": "prompt",
    "message": (
      "Seed the autonomous investigation loop with ONE new case. Do EXACTLY "
      "two tool calls, no listing first: (1) xsoar_create_incident with "
      "name='[guardian-loop] <Type> — <short scenario>' (the "
      "'[guardian-loop] ' prefix is REQUIRED), severity 2-4, and details = a "
      "realistic scenario paragraph embedding concrete SYNTHETIC IoCs an "
      "investigator can enrich (specific IPs, domains, URLs, ONE sha256 hash, "
      "account names, hostnames, ports). Vary the attack type across runs: "
      "data exfiltration, ransomware, C2 beacon, brute-force authentication, "
      "insider threat, supply-chain compromise, web shell, privilege "
      "escalation, cryptomining, DNS tunneling. (2) Take the incident id "
      "returned by step 1 and call issue_create(title='<Type> — "
      "<scenario>', kind='<phishing|lateral_movement|access_violation|malware"
      "|other>', severity='<low|medium|high|critical>', source_ref='<the new "
      "incident id>', scope='<one line of what to investigate>') to open the "
      "tracking Issue (it starts in status open). Do NOT investigate. Report "
      "the new incident id and issue id."
    ),
  },
}))
PY
)

LOOP_JSON=$(python3 - <<'PY'
import json
print(json.dumps({
  "name": "guardian-investigation-loop",
  "cron": "*/30 * * * *",
  "timezone": "UTC",
  "enabled": True,
  "bypass_approvals": True,
  "permission_policy": {"denied_tools": ["issue_create"]},
  "action": {
    "type": "prompt",
    "skill": "xsoar_case_investigation",
    "message": (
      "You are ONE tick of an autonomous investigation loop. You COMPLETE "
      "existing Issues; you canNOT create them (issue_create is disabled for "
      "you). STEPS: (1) Call issues_list(status='open', "
      "source_ref_not_null=True, order='asc') to get open Issues that track "
      "an XSOAR incident, OLDEST first. The source_ref_not_null filter "
      "structurally excludes manual/standalone Issues with no incident to "
      "fetch, so just take issues[0] — you no longer need to skip "
      "sourceless Issues by hand. If the list is empty, call "
      "issues_list(status='investigating', source_ref_not_null=True, "
      "order='asc') to resume the oldest partial. (2) If you found one, its "
      "source_ref is the XSOAR incident id. Investigate THAT incident "
      "end-to-end per the xsoar_case_investigation skill, using the EXISTING "
      "Issue (its id is in the issues_list result): set it to investigating "
      "(issue_update), log steps with issue_add_event, enrich indicators, "
      "scope the blast radius, and finish with issue_update(status='resolved') "
      "filling summary (leading VERDICT line), conclusions (MITRE + "
      "blast-radius scope), recommendations, and next_steps. If this incident "
      "is part of a campaign that matches an existing Case, group it with "
      "case_add_issue; if it clearly starts a new campaign, case_create then "
      "case_add_issue. (3) If there are NO open or investigating tracked "
      "Issues, reply 'no Issues awaiting investigation — nothing to do' "
      "and STOP. Work EXACTLY ONE Issue. Do NOT close the XSOAR case."
    ),
  },
}))
PY
)

# --- guardian-investigation-judge (v0.2.12) --------------------------------
# The autonomous evaluate->enhance step: scores recent resolved investigations
# against a SOC rubric and, on a SYSTEMATIC weakness, improves the
# xsoar_case_investigation skill via skills_update. Safety rails:
#   * tightly whitelisted tools (read Issues/Cases/indicators + skills_read +
#     skills_update ONLY) — cannot touch incidents, create/delete skills, or
#     manage credentials.
#   * skills_update auto-snapshots the prior skill under .history/ and writes a
#     `skill_updated` audit row (see /observability/events) — every self-edit
#     is reversible + visible.
#   * bounded edit contract in the prompt: preserve the 6-step lifecycle,
#     additive-only, <=~25 added lines, AT MOST one edit per run.
JUDGE_JSON=$(python3 - <<'PY'
import json
print(json.dumps({
  "name": "guardian-investigation-judge",
  "cron": "0 */6 * * *",
  "timezone": "UTC",
  "enabled": True,
  "bypass_approvals": True,
  "permission_policy": {"allowed_tools": [
    "issues_list", "issue_get", "cases_list", "case_get",
    "indicators_list", "indicator_get", "skills_read", "skills_update",
  ]},
  "action": {
    "type": "prompt",
    "message": (
      "You are the autonomous investigation-judge. You evaluate the QUALITY "
      "of recently-resolved investigations and, ONLY on a systematic "
      "weakness, improve the investigation skill. STEPS: (1) Call "
      "issues_list(status='resolved', source_ref_not_null=True, "
      "order='desc') and take the 8 most recent. For each, issue_get and "
      "score 0-2 on each dimension: VERDICT (summary leads with a clear "
      "'VERDICT:' line?), MITRE (conclusions cite ATT&CK technique IDs?), "
      "BLAST_RADIUS (affected hosts/accounts/data made explicit?), "
      "ENRICHMENT (IoCs enriched — check indicators_list for the issue?), "
      "RECOMMENDATIONS (next_steps concrete + actionable?). (2) A dimension "
      "is SYSTEMATICALLY weak if >=3 of the 8 score <=1. If NO dimension is "
      "systematically weak, reply 'investigations healthy — no skill change "
      "needed' and STOP — do not edit anything. (3) If exactly one or more "
      "dimensions are weak, pick the WEAKEST, call "
      "skills_read('workflows/xsoar_case_investigation.md'), and make a "
      "BOUNDED additive improvement via "
      "skills_update('workflows/xsoar_case_investigation.md', <new content>) "
      "that strengthens ONLY that dimension's guidance with a concrete "
      "instruction or example. HARD CONSTRAINTS: preserve the existing "
      "6-step lifecycle and ALL headings; ADD or REFINE guidance only, never "
      "delete a step; keep the net change under ~25 added lines; touch NO "
      "other skill; make AT MOST one skills_update call this run. (4) End by "
      "stating which dimension you improved, the rubric evidence (the scores), "
      "and a one-line summary of the edit — or that no change was needed."
    ),
  },
}))
PY
)

echo "Bootstrapping autonomous-investigation-loop jobs at ${AGENT_URL} ..."
upsert_job guardian-incident-seeder "$SEEDER_JSON"
upsert_job guardian-investigation-loop "$LOOP_JSON"
upsert_job guardian-investigation-judge "$JUDGE_JSON"
echo "Done. Verify:"
echo "  curl -sk -H \"Authorization: Bearer \$GUARDIAN_API_KEY\" ${AGENT_URL}/api/agent/jobs | python3 -m json.tool"
