---
name: insider_saas_data_exfil
displayName: Insider SaaS exfiltration
category: scenarios
description: 'Three-stage insider-threat data-loss chain. Stage 1: privileged user bulk-downloads from cloud storage (OneDrive / SharePoint / Google Drive). Stage 2: proxy logs the user''s workstation uploading to personal cloud storage. Stage 3: firewall confirms high-volume outbound to known file-sharing services. Vendor-agnostic — agent reads the operator''s technology stack at runtime. Triggers 2 XSIAM rules: Mailbox / SaaS data access anomaly, Data Exfiltration to Personal Cloud Storage. Use when you want to demonstrate detection of leaving-employee or compromised-insider exfiltration patterns.'
icon: person_off
source: platform
loadingMode: on-demand
locked: false
attack:
  - 'TA0009: Collection (T1213.002 Sharepoint, T1213.001 Confluence)'
  - 'TA0010: Exfiltration (T1567.002 Exfiltration to Cloud Storage, T1041 Exfiltration Over C2)'
---

# Skill: Insider data exfiltration via SaaS

## Category

scenarios

## Attack Type

Insider threat — a legitimate authenticated user systematically downloading data they shouldn't be hoarding (preparation for leaving the company, selling data, or after their account was compromised by an external attacker who's now operating as them). Different from external compromise: there's no "broken in" event; the user has every right to access most of what they're touching, and the signal is in VOLUME + DESTINATION + TIME-OF-DAY rather than authentication anomalies.

## MITRE ATT&CK Tactics

- TA0009: Collection (T1213.002 SharePoint, T1213.001 Confluence)
- TA0010: Exfiltration (T1567.002 Exfiltration to Cloud Storage, T1041 Exfiltration Over C2)

## XSIAM analytics rules triggered

| # | Rule | Stage |
|---|---|---|
| 11 | Mailbox / SaaS data access anomaly (bulk download outside baseline) | Stage 1 |
| 20 | Data Exfiltration to Personal Cloud Storage | Stages 2 + 3 |

## Data classes used

| Stage | Data class | If missing |
|---|---|---|
| 1 | `saas` | Required |
| 2 | `proxy` | Substitute with `firewall` (loses URL/category) |
| 3 | `firewall` | Substitute by relying on Stage 2 alone (lower fidelity) |

## Pre-flight

Call `phantom_get_technology_stack`. Verify `saas` is present. Verify at least one of `proxy` or `firewall` (ideally both, for layered visibility).

## Narrative thread

- **Insider user:** `a.harrington@bupa.example` (privileged data scientist with broad access to claims-data SharePoint sites and OneDrive corporate library)
- **Background context:** the user gave 2-week notice 3 days ago (this fact wouldn't be in the SIEM, but it's the realistic context that informs why the volume is suspicious — privileged users with broad access are NOT supposed to bulk-download right before leaving)
- **Workstation:** `wks-aharrington-01` at `10.10.20.99`
- **Source SaaS sites:** OneDrive `personal/a_harrington_bupa_example`, SharePoint sites `claims-data-2024`, `clinical-research-eu`
- **Volume of legitimate user activity baseline:** ~5 MB/day download on average over the prior 30 days
- **Volume of insider activity (this skill):** ~5 GB across 1,200 file events
- **Personal cloud storage destination:** `dropbox.com` user `a-harrington-personal`
- **Wall-clock time:** Stage 1 ~25 min (1,200 file downloads). Stage 2 starts ~3 min after Stage 1 begins (the user uploads as they download). Stage 3 spans the same window as Stages 1+2.

---

### Stage 1 — Bulk SaaS download — ~1,200 events over 25 minutes

The user accesses 1,200 files across SharePoint + OneDrive + corporate Google Drive (whichever cloud storage class is in the operator's stack). Most are PDFs and Excel files (claims data, clinical-research datasets). Some are massive ZIP archives the user previously created from larger projects.

**Data class:** `saas`

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[saas].formats[0].upper()>
    vendor:  <stack[saas].vendor>
    product: <stack[saas].product>
    count:    1200
    interval: 1
    destination: <stack.log_destination.type>
    duration_seconds: 1500
    observables_dict:
      user:        ["a.harrington@bupa.example"]
      src_ip:      ["10.10.20.99"]
      action:      ["FileDownloaded", "FileSyncDownloadedFull",
                    "FilePreviewed", "FileAccessed",
                    "PageViewed", "FolderListed"]
      operation:   ["FileDownloaded", "FileSyncDownloadedFull",
                    "FilePreviewed"]
      file_name:   ["claims-batch-Q3-2024.xlsx",
                    "clinical-trial-EU-results.pdf",
                    "patient-data-export-aug-2024.csv",
                    "research-archive-2023.zip",
                    "policy-renewals-Q3.xlsx",
                    "actuarial-models-v3.zip",
                    "claims-detail-jul-2024.csv"]
      site_url:    ["/personal/a_harrington_bupa_example/Documents",
                    "/sites/claims-data-2024",
                    "/sites/clinical-research-eu"]
      bytes:       ["180000", "245000", "890000", "5240000",
                    "12480000", "48800000", "4280000"]
      client_ip:   ["10.10.20.99"]
      client_app:  ["OneDrive Sync Engine", "Browser",
                    "OneDrive for Business"]
      country:     ["GB"]
      severity:    ["informational", "medium"]
      file_type:   ["xlsx", "pdf", "csv", "zip"]
      sensitivity_label: ["Confidential", "Internal", "Restricted",
                          "PHI"]
```

**Field semantics:**
- `user` — same legitimate user across all 1,200 events; the anomaly is the volume relative to this user's baseline (5 MB/day → 5 GB/25 min = 4 orders of magnitude beyond baseline)
- `action: FileDownloaded` — the operative log line. M365 audit produces this; Google Drive produces `download` events similarly
- `bytes` — distribution shows realistic file sizes; the largest individual file (~50 MB) is plausible (research archive ZIP)
- `client_app: OneDrive Sync Engine` — sync clients can pull large volumes faster than browser; an attacker insider would typically use sync to maximize speed
- `country: GB` — NOT impossible-travel; the user is signed in from where they normally are. The anomaly is volume, not geo
- `sensitivity_label` — Microsoft Information Protection / equivalent labels enrich the events; `Confidential`, `Restricted`, `PHI` are the high-sensitivity categories

**Why this fires Rule #11 (variant — bulk-download, not mailbox-rule):** modern SaaS-detection rules detect "user X downloaded N times more than their 30-day baseline in a Y-hour window." 1,200 file events in 25 min is unmistakable — even if ANY ONE of those events is legitimate, the burst itself is the signal. Some SIEMs label this "Massive Data Download" or "Anomalous SaaS Data Access"; the family is the same.

---

### Stage 2 — Workstation uploading to personal cloud storage — ~250 events over 25 minutes

In parallel with the SaaS downloads, the user's workstation uploads chunks to their personal `dropbox.com` account. The proxy logs each upload.

**Data class:** `proxy`

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[proxy].formats[0].upper()>
    vendor:  <stack[proxy].vendor>
    product: <stack[proxy].product>
    count:    250
    interval: 6
    destination: <stack.log_destination.type>
    duration_seconds: 1500
    observables_dict:
      src_ip:        ["10.10.20.99"]
      src_host:      ["wks-aharrington-01"]
      user:          ["a.harrington"]
      url:           ["https://www.dropbox.com/upload",
                      "https://content.dropboxapi.com/2/files/upload",
                      "https://content.dropboxapi.com/2/files/upload_session/append_v2",
                      "https://content.dropboxapi.com/2/files/upload_session/finish",
                      "https://drive.google.com/u/1/uc?id=upload"]
      method:        ["POST", "PUT"]
      status_code:   ["200", "201", "401", "200"]
      user_agent:    ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                      "DropboxClient/202",
                      "Dropbox/2024.06"]
      action:        ["allow"]
      bytes_sent:    ["10485760", "20971520", "5242880",
                      "12582912", "8388608", "16777216"]
      bytes_received: ["240", "180", "320"]
      content_type:  ["application/octet-stream", "application/zip",
                      "application/json"]
      category:      ["file-sharing", "personal-cloud-storage"]
      threat_score:  ["55", "65"]
      domain:        ["dropbox.com", "dropboxapi.com",
                      "drive.google.com"]
      domain_age_days: ["10000"]
```

**Field semantics:**
- `url` — Dropbox + Google Drive personal-account upload endpoints
- `method: POST / PUT` — both are file-upload methods
- `bytes_sent` — chunks of 5-20 MB per request; Dropbox API uses upload_session for large files (the `_append_v2` and `_finish` endpoints are part of that flow)
- `category: file-sharing / personal-cloud-storage` — the proxy's URL category. Most enterprises don't BLOCK these (they're legitimate for personal use during lunch breaks etc.) but they ARE categorized
- `domain_age_days: 10000` — `dropbox.com` is decades old. The signal is NOT the destination's age — it's the category + volume + tied-to-bulk-SaaS-download timing

**Why this fires Rule #20 (with Stage 1 context):** the proxy uploads alone don't fire — users genuinely use Dropbox sometimes. What fires is the COMBINATION: bulk SaaS downloads + simultaneous personal-storage uploads from the same user, totaling multi-GB. The temporal correlation is what makes this high-confidence.

---

### Stage 3 — Firewall confirmation of outbound volume — ~150 events over 25 minutes

The firewall sees outbound HTTPS sessions from `wks-aharrington-01` to Dropbox / Google Drive infrastructure. Most enterprises don't block file-sharing categories at the firewall (they delegate to proxy URL filtering), but they DO log volume.

**Data class:** `firewall`

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[firewall].formats[0].upper()>
    vendor:  <stack[firewall].vendor>
    product: <stack[firewall].product>
    count:    150
    interval: 10
    destination: <stack.log_destination.type>
    duration_seconds: 1500
    observables_dict:
      src_ip:        ["10.10.20.99"]
      dst_ip:        ["162.125.x.x", "104.21.x.x", "172.67.x.x",
                      "172.217.x.x"]
      src_port:      ["49152", "51234", "57890", "60123"]
      dst_port:      ["443"]
      protocol:      ["tcp"]
      action:        ["allow"]
      app:           ["ssl", "dropbox", "google-base"]
      bytes_sent:    ["10485760", "20971520", "5242880", "12582912"]
      bytes_received: ["240", "180", "320"]
      session_state: ["established"]
      country:       ["US"]
      threat_category: ["file-sharing"]
      session_duration: ["18", "25", "12", "32"]
```

**Field semantics:**
- `bytes_sent` (per-session) is multi-MB; aggregated across 150 sessions = the multi-GB total exfil
- `app: dropbox / google-base` — the firewall's app-id classification recognizes the destination
- `session_duration: 18-32 sec` — short upload sessions, consistent with chunked file transfer

**Why this fires Rule #20 (perimeter-tier confirmation):** even firewall-only-visible deployments can detect this on volume + destination-category + time-aggregated. The rule typically thresholds at "≥1 GB outbound to file-sharing category from one source in <1 hour."

---

## Verification

| Indicator | Where to check |
|---|---|
| Bulk-SaaS-download alert for `a.harrington@bupa.example` | XSIAM Issues |
| Personal-cloud-storage alert (Dropbox upload pattern) | XSIAM Issues |
| Firewall volume-anomaly alert from `10.10.20.99` | XSIAM Issues |
| Pivotable: filter by `user=a.harrington`, all 3 stages on one timeline | XQL: `dataset = msft_o365_audit_raw \| filter UserId = "a.harrington@bupa.example"` |

## Tear-down

```yaml
xlog.list_workers:
xlog.kill_worker:
  worker_id: <each>
```

## Adapting per deployment

Replace `a.harrington@bupa.example` with the operator's chosen test user. The interesting variable for tuning is the BASELINE — the rule fires on deviation from the user's history. If the operator's tenant is fresh (no baseline), the bulk download won't appear anomalous; pre-seed 30 days of low-volume `FileDownloaded` events for the user before running this skill.
