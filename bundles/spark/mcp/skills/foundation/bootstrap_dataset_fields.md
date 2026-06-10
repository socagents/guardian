---
name: bootstrap_dataset_fields
displayName: Bootstrap dataset fields
category: foundation
description: 'Generates ~100 sample events per data source in the operator''s technology stack, each populated with the maximum set of fields characteristic of that data source class. Solves the XSIAM "I can''t model what doesn''t exist" problem — Cortex XSIAM cannot create a dataset or field-mapping for telemetry it has never received. This skill seeds each dataset with field-rich sample data so field-mapping work can begin. Vendor-agnostic — agent reads the operator''s technology stack at runtime and uses whichever firewall, EDR, NDR, etc. products are configured. Run once per deployment after configuring the technology stack; re-run when adding a new data source.'
icon: dataset_linked
source: platform
loadingMode: on-demand
locked: false
attack: []
---

# Skill: Bootstrap dataset fields

## Category

foundation

## Purpose

Solves the XSIAM (and any modern SIEM's) chicken-and-egg problem: **you cannot model or field-map a dataset that has never received data.** Configuring an XSIAM ingestion broker for `vendor_proofpoint_tap_raw` and immediately opening the field-mapping UI shows nothing — XSIAM hasn't seen any rows yet. The platform won't let you write a parser for telemetry it has never seen.

This skill seeds each dataset in the operator's technology stack with ~100 events containing the maximum relevant set of fields from xlog's catalog. After running, every dataset in XSIAM has populated rows with realistic field shapes, and field-mapping work can proceed.

**When to run:**
- Once per deployment, immediately after configuring the technology stack at `/connectors`
- After adding a new data source to the stack (only the new source's worker runs)
- When a vendor's expected field set has expanded (operator can edit the field templates below and re-run)

**This is a bootstrap utility, not detection content.** The events generated have realistic field shapes but no narrative — they're designed to populate dataset schemas, not to fire any specific analytics rule.

## MITRE ATT&CK Tactics

Not applicable — bootstrap utility, not an attack-simulation or detection-validation skill.

## Pre-flight

Before generating any data, call `phantom_get_technology_stack` once. Iterate every entry in `vendors[]`. For each entry, look up the field template by `category` from the per-class sections below. If a category isn't covered (operator has a stack class outside the templates below), fall back to a minimal-fields recipe and surface a warning to the operator at the end.

The default `destination` is `<stack.log_destination.type>` (typically `XSIAM_WEBHOOK`). Each worker uses `count: 100`, `interval: 0.1`, `duration_seconds: 10` — total wall-clock for the whole run is ~10 seconds because all workers fire in parallel.

**Use parallel `xlog.create_data_worker` calls (one per stack entry), NOT a single scenario.** The scenarios tool exists for narrative kill-chains. This skill is independent per-source bootstrap; parallel workers give per-source independence (one worker failing doesn't block others) and per-source observability via `xlog.list_workers`.

## Field templates per data source class

Each per-class section below has the **field set the skill applies for that class** plus a complete `xlog.create_data_worker` recipe template. The agent picks the template matching `<stack[<entry>].category>` for each stack entry, then substitutes vendor/product placeholders at runtime.

**These field lists are starting points, not hard rules.** Operators can edit any class's field set via `/skills` → Save (the skill MD lives at `/app/skills/foundation/bootstrap_dataset_fields.md`); the agent picks up the change on next invocation.

---

### Firewall

5-tuple flow logging + action verdict + app classification + volume + geo + threat enrichment. ~22 fields. Most common SIEM ingest source by volume.

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[<entry>].formats[0].upper()>
    vendor:  <stack[<entry>].vendor>
    product: <stack[<entry>].product>
    count:    100
    interval: 0.1
    destination: <stack.log_destination.type>
    duration_seconds: 10
    observables_dict:
      src_ip:        ["192.0.2.42", "192.0.2.91", "203.0.113.18", "198.51.100.42"]
      dst_ip:        ["10.10.30.10", "10.10.0.50", "10.10.20.42", "10.10.50.20"]
      src_port:      ["49152", "51234", "57890", "60123"]
      dst_port:      ["443", "80", "22", "3389", "445", "53"]
      protocol:      ["tcp", "udp"]
      action:        ["allow", "deny", "drop"]
      action_status: ["success", "blocked"]
      session_state: ["established", "denied", "active", "closed"]
      app:           ["ssl", "ssh", "http", "dns", "smb"]
      application:   ["ssl", "ssh", "http", "dns", "smb"]
      bytes:         ["1240", "4280", "8960", "12480", "240"]
      bytes_sent:    ["480", "640", "1024", "8192", "180"]
      bytes_received: ["240", "1280", "4096", "12480", "180"]
      packets:       ["3", "12", "48", "92"]
      country:       ["US", "GB", "DE", "JP", "BR", "RU"]
      asn_source:    ["AS15169", "AS8075", "AS13335"]
      asn_destination: ["AS15169", "AS8075", "AS13335"]
      threat_category: ["clean", "suspicious", "malicious"]
      threat_score:  ["10", "35", "65", "82"]
      tcp_flags:     ["SYN", "SYN-ACK", "ACK", "FIN"]
      session_id:    ["sess-001", "sess-002", "sess-003"]
      session_duration: ["12", "45", "120", "240"]
```

---

### EDR (Endpoint Detection & Response)

Process tree + file activity + network-from-endpoint + user attribution + alert classification + MITRE mapping. ~20 fields. Highest-fidelity-per-event source typically.

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[<entry>].formats[0].upper()>
    vendor:  <stack[<entry>].vendor>
    product: <stack[<entry>].product>
    count:    100
    interval: 0.1
    destination: <stack.log_destination.type>
    duration_seconds: 10
    observables_dict:
      hostname:       ["wks-test-01", "wks-test-02", "srv-test-01"]
      src_ip:         ["10.10.20.42", "10.10.20.91", "10.10.10.10"]
      user:           ["test.user", "admin", "svc_test"]
      process_name:   ["powershell.exe", "cmd.exe", "explorer.exe", "WINWORD.EXE", "rundll32.exe"]
      parent_process: ["explorer.exe", "WINWORD.EXE", "powershell.exe", "cmd.exe"]
      process_id:     ["1234", "5678", "9012"]
      process_hash:   ["8a64dc4b...", "5cae0e91...", "b42c1f9e..."]
      command_line:   ["powershell.exe -nop -w hidden", "cmd.exe /c whoami", "WINWORD.EXE /n test.docx"]
      file_path:      ["C:\\Users\\test\\Documents", "C:\\Windows\\Temp", "C:\\Program Files"]
      file_name:      ["test.docx", "report.pdf", "tools.exe"]
      file_hash_sha256: ["b42c1f9e3a0d7c8b5e2f4a6d8e1b3c5a7f9d2e4b6c8a0d2f4e6c8a0b2d4f6c8e"]
      target_process: ["lsass.exe", "explorer.exe"]
      target_pid:     ["604", "1234"]
      action:         ["process_create", "file_create", "registry_modify", "network_connection"]
      alert_id:       ["alert-001", "alert-002", "alert-003"]
      alert_name:     ["Suspicious PowerShell", "LSASS Memory Access", "Network Connection"]
      attack_type:    ["powershell_encoded", "credential_dump", "lateral_movement"]
      attack_severity: ["informational", "medium", "high", "critical"]
      mitre_technique: ["T1059.001", "T1003.001", "T1021.002"]
      severity:       ["informational", "medium", "high", "critical"]
```

---

### NDR (Network Detection & Response)

East-west focus, anomaly-driven, baseline-deviation alerts. ~18 fields. Distinct from firewall (which is north-south + 5-tuple-only); NDR enriches with anomaly scoring + alert classification.

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[<entry>].formats[0].upper()>
    vendor:  <stack[<entry>].vendor>
    product: <stack[<entry>].product>
    count:    100
    interval: 0.1
    destination: <stack.log_destination.type>
    duration_seconds: 10
    observables_dict:
      src_ip:        ["10.10.20.42", "10.10.20.91", "10.10.30.10"]
      src_host:      ["wks-test-01", "wks-test-02", "web-app-01"]
      dst_ip:        ["10.10.10.10", "10.10.50.20", "10.10.40.20"]
      dst_host:      ["dc01", "fs01", "sql01"]
      dst_port:      ["445", "139", "3389", "5985", "1433"]
      protocol:      ["tcp"]
      action:        ["alert", "monitor"]
      anomaly_type:  ["lateral_movement", "first_time_admin_share", "unusual_internal_connection",
                      "wmi_rpc_anomaly", "smb_admin_share_pattern"]
      anomaly_score: ["72", "85", "91", "68"]
      alert_name:    ["First-time admin$ share access", "WMI RPC anomaly", "Lateral RPC pattern"]
      alert_type:    ["ndr_lateral_movement", "ndr_anomaly"]
      severity:      ["medium", "high", "critical"]
      attack_category: ["lateral_movement", "reconnaissance"]
      attack_type:   ["smb_admin_access", "rdp_lateral", "wmi_remote_exec"]
      bytes_sent:    ["240", "1024", "4096", "8192"]
      bytes_received: ["180", "512", "2048", "8192"]
      account_name:  ["test.user", "svc_backup"]
      session_id:    ["sess-A1", "sess-B2"]
      mitre_technique: ["T1021.002", "T1047", "T1021.001"]
```

---

### Proxy

HTTP request/response + user attribution + URL category filtering. ~18 fields. Critical for outbound visibility (data exfil, malicious URL access).

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[<entry>].formats[0].upper()>
    vendor:  <stack[<entry>].vendor>
    product: <stack[<entry>].product>
    count:    100
    interval: 0.1
    destination: <stack.log_destination.type>
    duration_seconds: 10
    observables_dict:
      src_ip:        ["10.10.20.42", "10.10.20.91", "10.10.30.10"]
      src_host:      ["wks-test-01", "wks-test-02"]
      user:          ["test.user", "admin"]
      url:           ["https://www.example.com/", "https://api.example.com/v1/data",
                      "https://cdn.example.com/static/app.js",
                      "https://dropbox.com/upload"]
      method:        ["GET", "POST", "PUT"]
      status_code:   ["200", "302", "404", "403", "500"]
      user_agent:    ["Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                      "curl/7.81.0", "python-requests/2.31.0"]
      referer:       ["https://www.example.com/", ""]
      content_type:  ["text/html", "application/json", "application/octet-stream"]
      bytes_sent:    ["480", "640", "1024", "10485760"]
      bytes_received: ["240", "12480", "4096", "180"]
      action:        ["allow", "block", "alert"]
      category:      ["business", "newly-registered-domain", "file-sharing", "scanner"]
      threat_category: ["clean", "suspicious", "phishing", "c2"]
      threat_score:  ["10", "35", "65", "82"]
      domain:        ["www.example.com", "api.example.com", "dropbox.com"]
      domain_age_days: ["10000", "21", "8", "1"]
      country:       ["US", "GB", "DE"]
```

---

### Email Gateway

Sender/recipient + email body + attachment metadata + threat enrichment + DKIM/SPF/DMARC. ~19 fields. The phishing detection foundation.

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[<entry>].formats[0].upper()>
    vendor:  <stack[<entry>].vendor>
    product: <stack[<entry>].product>
    count:    100
    interval: 0.1
    destination: <stack.log_destination.type>
    duration_seconds: 10
    observables_dict:
      sender_email:    ["partners@external-supplier.com",
                        "newsletter@industry-news.io",
                        "invoices@billing-secure-update.tk"]
      sender_domain:   ["external-supplier.com", "industry-news.io",
                        "billing-secure-update.tk"]
      recipient_email: ["test.user@bupa.example", "team-finance@bupa.example"]
      recipient_domain: ["bupa.example"]
      email_subject:   ["Q4 Newsletter", "Payment terms",
                        "URGENT: Invoice action required"]
      email_body:      ["[redacted body sample]"]
      attachment_count: ["0", "1", "2"]
      attachment_name: ["invoice.docm", "report.pdf", ""]
      attachment_hash: ["b42c1f9e3a0d...", "8a64dc4b...", ""]
      attachment_size: ["180000", "245000", "0"]
      attachment_type: ["docm", "pdf", "xlsx", ""]
      action:          ["delivered", "quarantined", "blocked"]
      threat_category: ["clean", "phishing", "malware"]
      threat_score:    ["10", "65", "82"]
      sandbox_verdict: ["clean", "suspicious", "malicious", ""]
      dkim_result:     ["pass", "fail", "neutral"]
      spf_result:      ["pass", "softfail", "fail"]
      dmarc_result:    ["pass", "fail", "quarantine"]
      severity:        ["informational", "high"]
```

---

### DNS

Query + response + source attribution + domain enrichment + threat tagging. ~15 fields. Compact but high-volume; critical for tunneling/DGA detection.

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[<entry>].formats[0].upper()>
    vendor:  <stack[<entry>].vendor>
    product: <stack[<entry>].product>
    count:    100
    interval: 0.1
    destination: <stack.log_destination.type>
    duration_seconds: 10
    observables_dict:
      src_ip:       ["10.10.20.42", "10.10.20.91"]
      src_host:     ["wks-test-01", "wks-test-02"]
      user:         ["test.user", "admin"]
      src_port:     ["49152", "51234", "57890"]
      dst_port:     ["53"]
      protocol:     ["udp", "tcp"]
      query:        ["www.example.com", "api.example.com", "cdn.example.com",
                     "xkqp93jr9d2.cdn-update-svc.tk"]
      query_type:   ["A", "AAAA", "TXT", "MX", "PTR"]
      query_name:   ["www.example.com", "api.example.com"]
      response_code: ["NOERROR", "NXDOMAIN", "SERVFAIL"]
      response_ip:  ["93.184.216.34", "192.0.2.42", ""]
      response_data: ["v=spf1 include:_spf.example.com ~all", ""]
      ttl:          ["300", "60", "30", "3600"]
      action:       ["allow", "block"]
      domain:       ["example.com", "cdn-update-svc.tk"]
      domain_age_days: ["10000", "21", "8"]
      threat_category: ["clean", "suspicious", "c2"]
      query_length: ["15", "28", "95"]
```

---

### WAF (Web Application Firewall)

HTTP request inspection + attack classification + rule match + source attribution. ~18 fields. The OWASP Top 10 detection layer.

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[<entry>].formats[0].upper()>
    vendor:  <stack[<entry>].vendor>
    product: <stack[<entry>].product>
    count:    100
    interval: 0.1
    destination: <stack.log_destination.type>
    duration_seconds: 10
    observables_dict:
      src_ip:        ["192.0.2.42", "203.0.113.18", "198.51.100.42"]
      dst_ip:        ["10.10.30.10"]
      src_port:      ["49152", "51234", "57890", "60123"]
      dst_port:      ["443", "80"]
      protocol:      ["tcp"]
      url:           ["/", "/login.php", "/api/v1/users", "/search.php?id=1",
                      "/admin/", "/.env"]
      method:        ["GET", "POST"]
      status_code:   ["200", "403", "404", "500"]
      user_agent:    ["Mozilla/5.0", "sqlmap/1.7.2", "curl/7.81.0"]
      action:        ["allow", "block", "alert"]
      attack_type:   ["sql-injection", "xss", "directory-traversal",
                      "command-injection", "scanner-fingerprint"]
      attack_severity: ["informational", "medium", "high", "critical"]
      attack_category: ["sql-injection", "xss", "lfi", "rce"]
      rule_id:       ["942100", "942130", "941100", "930100", "920270"]
      rule_name:     ["SQL Injection: Common Testing", "XSS Attack Detected",
                      "Restricted File Access"]
      bytes_sent:    ["480", "640", "1240"]
      bytes_received: ["240", "1280", "12480"]
      threat_score:  ["35", "65", "82", "95"]
      anomaly_score: ["45", "72", "88"]
      country:       ["US", "RU", "CN", "DE"]
```

---

### Load Balancer

HTTP traffic + backend pool routing + response timing. ~15 fields. Less commonly field-mapped into XSIAM (operators usually use firewall/WAF instead) but included here for stack completeness.

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[<entry>].formats[0].upper()>
    vendor:  <stack[<entry>].vendor>
    product: <stack[<entry>].product>
    count:    100
    interval: 0.1
    destination: <stack.log_destination.type>
    duration_seconds: 10
    observables_dict:
      src_ip:        ["192.0.2.42", "203.0.113.18", "10.10.0.50"]
      dst_ip:        ["10.10.30.10", "10.10.30.11", "10.10.30.12"]
      src_port:      ["49152", "51234", "57890", "60123"]
      dst_port:      ["443", "80"]
      protocol:      ["tcp"]
      url:           ["/", "/api/v1/users", "/static/css/app.css"]
      method:        ["GET", "POST"]
      status_code:   ["200", "302", "404", "500", "503"]
      response_time_ms: ["12", "45", "120", "1200"]
      backend_server: ["app-01", "app-02", "app-03"]
      backend_status_code: ["200", "500"]
      backend_response_time_ms: ["8", "32", "100", "1100"]
      pool_name:     ["web_pool", "api_pool"]
      pool_member:   ["app-01:8080", "app-02:8080"]
      virtual_server: ["vs_https", "vs_http"]
      bytes_sent:    ["480", "1024", "4096"]
      bytes_received: ["240", "12480", "1280"]
```

**Note**: if your XSIAM tenant doesn't field-map LB telemetry, you can skip this class by removing the LB entries from the technology stack temporarily, or by editing this skill to remove the LB recipe. LB events still ingest as raw rows but won't have a parser unless you write one.

---

### VPN

Authentication + session + geo + MFA. ~16 fields. The perimeter identity log.

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[<entry>].formats[0].upper()>
    vendor:  <stack[<entry>].vendor>
    product: <stack[<entry>].product>
    count:    100
    interval: 0.1
    destination: <stack.log_destination.type>
    duration_seconds: 10
    observables_dict:
      user:                  ["test.user", "admin", "j.smith"]
      src_ip:                ["86.150.42.18", "192.0.2.42", "203.0.113.18"]
      action:                ["login_success", "login_failure", "logout"]
      authentication_result: ["success", "failed"]
      authentication_method: ["password", "mfa", "certificate", "saml"]
      authentication_protocol: ["radius", "ldap", "saml", "oauth2"]
      error_code:            ["AUTH_OK", "AUTH_FAILED", "INVALID_CREDENTIALS"]
      vpn_gateway:           ["vpn-portal-01", "vpn-portal-02"]
      session_id:            ["sess-001", "sess-002", "sess-003"]
      assigned_ip:           ["10.10.20.42", "10.10.20.43", ""]
      country:               ["US", "GB", "DE", "RU"]
      city:                  ["London", "New York", "Berlin", "Moscow"]
      mfa_method:            ["push", "totp", "sms", ""]
      mfa_result:            ["success", "failed", "skipped"]
      severity:              ["informational", "medium", "high"]
      session_duration:      ["3600", "14400", "0"]
```

---

### Cloud (GCP / AWS / Azure equivalent)

Actor identity + API call + resource targeting + IAM activity + auth method. ~19 fields. Cloud audit telemetry — what the operator typically needs for cloud breach detection.

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[<entry>].formats[0].upper()>
    vendor:  <stack[<entry>].vendor>
    product: <stack[<entry>].product>
    count:    100
    interval: 0.1
    destination: <stack.log_destination.type>
    duration_seconds: 10
    observables_dict:
      project_id:    ["test-project-prod", "test-project-staging"]
      actor_email:   ["test.user@bupa.example", "cicd-deployer@bupa.example",
                      "data-export-svc@test-project-prod.iam.gserviceaccount.com"]
      actor_ip:      ["192.0.2.42", "10.10.0.0", "203.0.113.18"]
      country:       ["US", "GB", "RU"]
      action:        ["google.iam.admin.v1.CreateServiceAccount",
                      "google.iam.admin.v1.CreateServiceAccountKey",
                      "google.cloud.resourcemanager.v1.SetIamPolicy",
                      "storage.objects.get",
                      "compute.instances.start"]
      api_endpoint:  ["iam.googleapis.com", "storage.googleapis.com",
                      "compute.googleapis.com"]
      api_method:    ["projects.serviceAccounts.create",
                      "projects.setIamPolicy", "objects.get"]
      operation:     ["create", "delete", "update", "list", "get"]
      resource_name: ["projects/test-project-prod/serviceAccounts/data-export-svc@..."]
      resource_type: ["serviceAccount", "iamPolicy", "storageObject", "instance"]
      resource_id:   ["sa-001", "policy-002", "obj-003"]
      sa_email:      ["data-export-svc@test-project-prod.iam.gserviceaccount.com"]
      sa_key_id:     ["8f3a91d2c4b7e5a8d6f9b2c1e4a7d3f5b8c2e9a1"]
      role_granted:  ["roles/owner", "roles/iam.serviceAccountTokenCreator", ""]
      target_member: ["serviceAccount:data-export-svc@..."]
      authentication_method: ["oauth_token", "service_account_key", "user_credential"]
      severity:      ["informational", "medium", "high", "critical"]
      operation_status: ["SUCCESS", "ERROR"]
      caller_user_agent: ["google-cloud-sdk/470.0.0", "python-requests/2.31.0"]
```

---

### SaaS (M365 / Workspace equivalent)

Identity + auth + app activity + email rules + file activity. ~18 fields. Modern identity-first attack surface.

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[<entry>].formats[0].upper()>
    vendor:  <stack[<entry>].vendor>
    product: <stack[<entry>].product>
    count:    100
    interval: 0.1
    destination: <stack.log_destination.type>
    duration_seconds: 10
    observables_dict:
      user:                  ["test.user@bupa.example"]
      user_principal_name:   ["test.user@bupa.example"]
      src_ip:                ["86.150.42.18", "192.0.2.42"]
      country:               ["US", "GB", "RU"]
      action:                ["login_success", "consent_to_application",
                              "new-inboxrule", "FileDownloaded",
                              "add_oauth2permissiongrant"]
      operation:             ["UserLoggedIn", "Consent to application",
                              "New-InboxRule", "FileDownloaded"]
      app_name:              ["Outlook", "QuickApprove eSignature",
                              "InvoicePro Sync"]
      app_id:                ["c4f1e8d2-7a93-4b21-9c5e-8d3f7a2b1e9c", ""]
      app_publisher:         ["Microsoft", "unverified"]
      permissions_granted:   ["Mail.ReadWrite", "Files.ReadWrite.All",
                              "User.Read", "offline_access", ""]
      consent_type:          ["UserConsent", "AdminConsent", ""]
      authentication_method: ["password", "mfa", "oauth_token"]
      mfa_required:          ["true", "false"]
      session_id:            ["sess-A1B2C3D4"]
      file_name:             ["report.xlsx", "policy.docx", ""]
      site_url:              ["/personal/test_user_bupa_example/Documents", ""]
      bytes:                 ["180000", "245000", "0"]
      severity:              ["informational", "medium", "high"]
```

---

## Execution

The agent's runbook for the skill:

1. **Pre-flight** — call `phantom_get_technology_stack`, parse `vendors[]`. For each entry, look up the field-template recipe by `category`.
2. **Parallel dispatch** — call `xlog.create_data_worker` once per stack entry, concurrently. Each worker is a 100-event 10-second burst targeting that vendor/product. All workers run in the background; the agent doesn't await each one before firing the next.
3. **Wait briefly** — give workers 12-15 seconds of wall-clock time to complete (the burst is 10s, plus a small buffer for ingestion).
4. **Verify** — call `xlog.list_workers` to confirm all workers reached `Stopped` status without errors. Optionally call `xsiam.get_issues` or query the XSIAM tenant directly to confirm row counts in each dataset.
5. **Summarize** — report per-class event count + dataset name (per the operator's stack mapping) + any classes that were skipped (unsupported category) or failed (worker error).

## Verification

After the skill finishes, the operator should see (within ~1 minute of skill completion):

| Indicator | Where to check |
|---|---|
| Per-dataset row count ≈100 | XSIAM Settings → Data Sources → each ingestion source |
| Field-mapping UI no longer empty | XSIAM Settings → Data Sources → click into a source → Fields tab |
| All field templates show ≥3 distinct values per field | Field-mapping preview, scan for the field types the parser sees |
| No worker errors | `xlog.list_workers` should show all `Stopped` status |

If any dataset is still empty after the skill: check the operator's XSIAM ingestion broker config (the broker might not be enabled or might be filtering on something the synthetic data doesn't match), and check `xsiam.get_issues` for any ingestion-side error.

## When to re-run

- **After adding a new data source to the stack** — re-run the skill; only the new source's worker needs to fire (the agent can detect "this dataset already has rows" and skip)
- **After the operator edits this skill's field templates** — re-run to populate the dataset with the new field shapes (XSIAM's parser will see the new fields on subsequent ingest)
- **NOT routine maintenance** — this is a bootstrap utility; running it monthly just adds noise to the operator's tenant. Once datasets are field-mapped, real telemetry takes over.

## Tear-down

The skill creates N data workers (one per stack entry). After the bootstrap completes:

```yaml
xlog.list_workers:
  # confirms all are Stopped
xlog.kill_worker:
  worker_id: <each — only if any are still running past the burst window>
```

The events are already ingested into XSIAM; tear-down doesn't unsend them. If the operator wants to mark the bootstrap events as test/non-production, they can use XSIAM's tagging on the dataset to filter them out of real-incident triage.

## Adapting per deployment

The example values in each recipe (`192.0.2.42`, `bupa.example`, `test-project-prod`) are illustrative. For exercises tied to a specific customer environment, the operator can edit each per-class section's recipe to use their actual asset names — the skill just defines the *fields*; the values are open for customization. Agent's recipes are authoritative once the skill saves.

If a class isn't covered in the templates above (e.g. operator has an `IDS` or `MDR` class in their stack), the agent should fall back to a minimal fields recipe (`src_ip`, `dst_ip`, `action`, `severity`, `alert_name`) and emit a warning that the class was skipped from the curated templates. Editing this skill MD to add a new class section is the right way to extend coverage.
