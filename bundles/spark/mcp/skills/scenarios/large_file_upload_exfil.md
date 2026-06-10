---
name: large_file_upload_exfil
displayName: Large file upload exfil
category: scenarios
description: 'Three-pattern data-exfiltration skill focused exclusively on large-file upload patterns to external destinations. Stage 1: workstation outbound bulk upload to file-sharing service via HTTPS (proxy-visible). Stage 2: server outbound bulk upload (anomalous direction — web servers should rarely initiate outbound). Stage 3: SaaS bulk-download by a privileged user followed by re-upload to personal cloud (M365 + proxy chain). Each stage emits high-volume bytes_sent / bytes_received imbalance + multi-MB content_length + file-sharing-category destination. Vendor-agnostic — agent reads the operator''s technology stack at runtime. Triggers 3 XSIAM rules: Data Exfiltration to Personal Cloud Storage, Anomalous Outbound Volume from Server, Bulk SaaS Download Pattern.'
icon: upload_file
source: platform
loadingMode: on-demand
locked: false
attack:
  - 'TA0009: Collection (T1213.002 SharePoint, T1213.001 Confluence)'
  - 'TA0010: Exfiltration (T1567.002 Exfiltration to Cloud Storage, T1041 Exfiltration Over C2 Channel, T1048.003 Exfiltration Over Unencrypted Non-C2 Protocol)'
---

# Skill: Large file upload exfiltration

## Category

scenarios

## Attack Type

Data exfiltration via outbound HTTPS to file-sharing services or personal cloud storage. The single most common exfil channel in 2024-26 IR reports — replaced FTP/SFTP/S3-direct exfil because TLS hides the content from network inspection and file-sharing categories are typically allowed (operator policy: "Dropbox is fine for personal use during lunch").

Detection has to key on **volume + destination category + direction anomaly** rather than content. This skill validates each of those signals.

Three distinct patterns covered:

- **Workstation → file-sharing**: routine end-user case (insider threat, compromised endpoint)
- **Server → file-sharing**: anomalous direction (web/app servers should rarely initiate outbound to non-CDN destinations)
- **SaaS-collected → personal cloud**: bulk download from corporate SaaS then re-upload to attacker-controlled storage

## MITRE ATT&CK Tactics

- TA0009: Collection (T1213.002 SharePoint, T1213.001 Confluence)
- TA0010: Exfiltration (T1567.002 Exfiltration to Cloud Storage, T1041 Exfiltration Over C2 Channel, T1048.003 Exfiltration Over Unencrypted Non-C2 Protocol)

## XSIAM analytics rules triggered

| # | Rule | Stage |
|---|---|---|
| 20 | Data Exfiltration to Personal Cloud Storage | Stages 1 + 2 + 3 |
| - | Anomalous Outbound Volume from Server | Stage 2 |
| - | Bulk SaaS Download Pattern | Stage 3 |

## Data classes used

| Stage | Data class | If missing |
|---|---|---|
| 1, 2 | `proxy` | Required for URL category + outbound visibility |
| 1, 2 | `firewall` | Confirms volume at perimeter |
| 3 | `saas` | Required — SaaS audit log captures the bulk-download initiator |

## Pre-flight

Call `phantom_get_technology_stack`. Verify `proxy` and `firewall` are present (Stages 1+2). Verify `saas` is present for Stage 3. If any missing, the skill skips the affected stage and continues with the rest — degraded coverage but partial signal still useful.

## Narrative thread

- **Insider user:** `r.kowalski@bupa.example` (data analyst, broad access to claims-data SharePoint)
- **Workstation:** `wks-rkowalski-01` at `10.10.20.88`
- **Compromised web server (Stage 2):** `10.10.30.10` / `web-app-01`
- **Personal cloud destinations:** Dropbox (`162.125.x.x`), Google Drive personal (`172.217.x.x`), Mega.nz (`66.203.x.x`), WeTransfer (`paste.dropfiles.io`)
- **SaaS source (Stage 3):** OneDrive `personal/r_kowalski_bupa_example/Documents/Claims-Q4-Archive` (~600 docs, ~4 GB total)
- **Wall-clock time:** Stage 1 ~25 min sustained upload. Stage 2 ~10 min server-side burst (more aggressive). Stage 3 ~30 min SaaS bulk download + ~25 min re-upload (overlapping). Stages 1+2 can run in parallel; Stage 3 has internal sequencing (download → upload).

---

### Stage 1 — Workstation outbound bulk upload to file-sharing — ~250 events over 25 minutes

The user (insider OR compromised endpoint via attacker tooling) systematically uploads chunks to their personal Dropbox account. The proxy logs each upload as a multi-MB POST/PUT.

**Sub-stage 1A — proxy outbound**

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
      src_ip:        ["10.10.20.88"]
      src_host:      ["wks-rkowalski-01"]
      user:          ["r.kowalski"]
      src_port:      ["49152", "51234", "57890", "60123"]
      dst_port:      ["443"]
      protocol:      ["tcp"]
      url:           ["https://www.dropbox.com/upload",
                      "https://content.dropboxapi.com/2/files/upload",
                      "https://content.dropboxapi.com/2/files/upload_session/append_v2",
                      "https://content.dropboxapi.com/2/files/upload_session/finish",
                      "https://drive.google.com/u/1/uc?id=upload",
                      "https://www.mega.nz/upload"]
      method:        ["POST", "PUT"]
      status_code:   ["200", "201"]
      user_agent:    ["Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                      "DropboxClient/202",
                      "Dropbox/2024.06"]
      action:        ["allow"]
      bytes_sent:    ["10485760", "20971520", "5242880",
                      "12582912", "8388608", "16777216",
                      "26214400"]
      bytes_received: ["240", "180", "320", "412"]
      content_type:  ["application/octet-stream", "application/zip"]
      content_length: ["10485760", "20971520", "5242880"]
      category:      ["file-sharing", "personal-cloud-storage"]
      threat_score:  ["55", "65"]
      domain:        ["dropbox.com", "dropboxapi.com",
                      "drive.google.com", "mega.nz"]
      domain_age_days: ["10000"]
```

**Sub-stage 1B — firewall confirmation**

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[firewall].formats[0].upper()>
    vendor:  <stack[firewall].vendor>
    product: <stack[firewall].product>
    count:    100
    interval: 15
    destination: <stack.log_destination.type>
    duration_seconds: 1500
    observables_dict:
      src_ip:        ["10.10.20.88"]
      dst_ip:        ["162.125.4.20", "162.125.5.20", "104.21.x.x",
                      "172.217.x.x", "66.203.x.x"]
      src_port:      ["49152", "51234", "57890", "60123"]
      dst_port:      ["443"]
      protocol:      ["tcp"]
      action:        ["allow"]
      app:           ["ssl", "dropbox", "google-base", "mega"]
      bytes_sent:    ["10485760", "20971520", "5242880",
                      "12582912", "8388608"]
      bytes_received: ["240", "180", "320"]
      session_state: ["established"]
      country:       ["US"]
      threat_category: ["file-sharing"]
      session_duration: ["18", "25", "12", "32"]
```

**Field semantics:**
- `bytes_sent` — multi-MB per session (5-26 MB range), 250 events × ~12 MB avg = ~3 GB total uploaded
- `bytes_received` — tiny (just acknowledgments) — the imbalance is the strongest signal
- `category: file-sharing / personal-cloud-storage` — proxy classification
- `domain_age_days: 10000` — destinations are decades-old (Dropbox is real); the signal is NOT destination age, it's category + volume + direction

**Why this fires Rule #20:** classic exfil — high outbound volume from a workstation to a category that's typically allowed (file-sharing). Threshold: ≥1 GB outbound to file-sharing in <1 hour from one source. 3 GB / 25 min crosses it 7x over.

---

### Stage 2 — Server outbound bulk upload (anomalous direction) — ~100 events over 10 minutes

After web-app compromise (per `web_app_to_webshell_to_exfil`), the attacker uses the web shell to package DB content + source code, then exfiltrates it via outbound HTTPS to a file-sharing service. **This is the anomalous-direction signal: web servers should rarely initiate outbound to non-CDN destinations.**

**Sub-stage 2A — proxy**

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[proxy].formats[0].upper()>
    vendor:  <stack[proxy].vendor>
    product: <stack[proxy].product>
    count:    60
    interval: 10
    destination: <stack.log_destination.type>
    duration_seconds: 600
    observables_dict:
      src_ip:        ["10.10.30.10"]
      src_host:      ["web-app-01"]
      src_port:      ["41024", "41128", "41234", "41512"]
      dst_port:      ["443"]
      protocol:      ["tcp"]
      url:           ["https://paste.dropfiles.io/upload",
                      "https://api.dropfiles.io/v2/objects",
                      "https://transfer.sh/?action=upload",
                      "https://0x0.st/"]
      method:        ["POST", "PUT"]
      status_code:   ["200", "201"]
      user_agent:    ["curl/7.81.0", "Wget/1.21.3", "python-requests/2.31.0"]
      action:        ["allow"]
      bytes_sent:    ["10485760", "20971520", "5242880",
                      "8388608", "16777216", "33554432"]
      bytes_received: ["240", "180", "320"]
      content_type:  ["application/octet-stream", "application/zip"]
      content_length: ["10485760", "20971520", "33554432"]
      category:      ["file-sharing", "personal-cloud-storage", "uncategorized"]
      threat_score:  ["55", "70"]
      domain:        ["paste.dropfiles.io", "transfer.sh", "0x0.st"]
      domain_age_days: ["12", "1", "8"]
```

**Sub-stage 2B — firewall**

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[firewall].formats[0].upper()>
    vendor:  <stack[firewall].vendor>
    product: <stack[firewall].product>
    count:    40
    interval: 15
    destination: <stack.log_destination.type>
    duration_seconds: 600
    observables_dict:
      src_ip:        ["10.10.30.10"]
      dst_ip:        ["104.21.x.x", "172.67.x.x", "66.203.x.x"]
      src_port:      ["41024", "41128", "41234", "41512"]
      dst_port:      ["443"]
      protocol:      ["tcp"]
      action:        ["allow"]
      app:           ["ssl"]
      bytes_sent:    ["10485760", "20971520", "33554432"]
      bytes_received: ["240", "180"]
      session_state: ["established"]
      country:       ["US"]
      threat_category: ["file-sharing"]
```

**Field semantics:**
- `src_ip: 10.10.30.10` — the WEB SERVER initiates outbound, not a user workstation. **This is the strongest single signal.** Web servers should accept inbound connections; outbound to non-CDN destinations is suspicious by direction alone
- `bytes_sent` — chunks up to 33 MB per session (server can stage larger archives than a workstation)
- `domain_age_days: 1-12` — destinations are NEW (newly-stood-up attacker infrastructure for this campaign), unlike Stage 1's mature Dropbox

**Why this fires the "Anomalous Outbound Volume from Server" rule:** server-class assets have egress baselines (mostly to CDNs, package mirrors, NTP servers). Multi-MB POST traffic to file-sharing categories from a web tier is an unmistakable deviation.

---

### Stage 3 — SaaS bulk-download → personal cloud upload — ~800 events over 30 minutes

The privileged user (or compromised account) bulk-downloads from corporate OneDrive, then re-uploads to personal cloud. Two-phase: collection (Stage 3A — SaaS-side) followed by exfiltration (Stage 3B — proxy + firewall).

**Sub-stage 3A — SaaS bulk download (Collection)**

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[saas].formats[0].upper()>
    vendor:  <stack[saas].vendor>
    product: <stack[saas].product>
    count:    600
    interval: 3
    destination: <stack.log_destination.type>
    duration_seconds: 1800
    observables_dict:
      user:        ["r.kowalski@bupa.example"]
      src_ip:      ["10.10.20.88"]
      action:      ["FileDownloaded", "FileSyncDownloadedFull",
                    "FilePreviewed", "FileAccessed",
                    "PageViewed", "FolderListed"]
      operation:   ["FileDownloaded", "FileSyncDownloadedFull"]
      file_name:   ["claims-batch-Q4-001.xlsx",
                    "clinical-trial-EU-results.pdf",
                    "patient-data-export-aug-2024.csv",
                    "research-archive-2023.zip",
                    "policy-renewals-Q4.xlsx",
                    "actuarial-models-v3.zip"]
      site_url:    ["/personal/r_kowalski_bupa_example/Documents/Claims-Q4-Archive",
                    "/sites/claims-data-2024",
                    "/sites/clinical-research-eu"]
      bytes:       ["180000", "245000", "890000", "5240000",
                    "12480000", "48800000", "4280000"]
      client_ip:   ["10.10.20.88"]
      client_app:  ["OneDrive Sync Engine", "Browser",
                    "OneDrive for Business"]
      country:     ["GB"]
      severity:    ["informational", "medium"]
      file_type:   ["xlsx", "pdf", "csv", "zip"]
      sensitivity_label: ["Confidential", "Internal", "Restricted",
                          "PHI"]
```

**Sub-stage 3B — proxy + firewall re-upload to personal cloud**

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[proxy].formats[0].upper()>
    vendor:  <stack[proxy].vendor>
    product: <stack[proxy].product>
    count:    200
    interval: 9
    destination: <stack.log_destination.type>
    duration_seconds: 1800
    observables_dict:
      src_ip:        ["10.10.20.88"]
      src_host:      ["wks-rkowalski-01"]
      user:          ["r.kowalski"]
      src_port:      ["49251", "51380", "57902", "60127"]
      dst_port:      ["443"]
      protocol:      ["tcp"]
      url:           ["https://www.dropbox.com/upload",
                      "https://content.dropboxapi.com/2/files/upload",
                      "https://drive.google.com/u/1/uc?id=upload"]
      method:        ["POST", "PUT"]
      status_code:   ["200", "201"]
      user_agent:    ["Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                      "DropboxClient/202"]
      action:        ["allow"]
      bytes_sent:    ["20971520", "33554432", "10485760", "16777216"]
      bytes_received: ["240", "180", "320"]
      content_type:  ["application/octet-stream", "application/zip"]
      content_length: ["20971520", "33554432"]
      category:      ["file-sharing", "personal-cloud-storage"]
      threat_score:  ["55", "65"]
      domain:        ["dropbox.com", "dropboxapi.com", "drive.google.com"]
```

**Field semantics:**
- `action: FileDownloaded` for 600 events in Stage 3A — by itself crosses any "bulk SaaS download" threshold (typical: ≥100 downloads / 30 min)
- The TIMING correlation is what makes Stage 3 high-fidelity: bulk SaaS download AND outbound personal-cloud upload from same user within minutes = high-confidence exfil
- `sensitivity_label` — MIP / DLP-classified content; "Confidential", "PHI", "Restricted" enrich the alert severity at the SIEM

**Why this fires the "Bulk SaaS Download Pattern" + Rule #20:**
- 600 file-download events / 30 min from one user crosses the bulk-download threshold (typical: ≥100 / 30 min)
- Followed by ~200 outbound POST events from same user to file-sharing destinations within the same window
- The temporal correlation is unambiguous

---

## Verification

| Indicator | Where to check |
|---|---|
| Stage 1 exfil-to-file-sharing alert (workstation → Dropbox volume) | XSIAM Issues |
| Stage 2 server-outbound-anomaly alert (web-app-01 → uncategorized destinations) | XSIAM Issues |
| Stage 3A bulk-SaaS-download alert (`r.kowalski` 600 downloads / 30 min) | XSIAM Issues |
| Stage 3B exfil-to-file-sharing alert (re-upload following Stage 3A) | XSIAM Issues |
| Pivotable: filter `user=r.kowalski`, see all 4 stages on one timeline | XQL: `dataset = msft_o365_audit_raw \| filter UserId = "r.kowalski@bupa.example"` |

## Tear-down

```yaml
xlog.list_workers:
xlog.kill_worker:
  worker_id: <each>
```

## Adapting per deployment

The illustrative volumes (3 GB workstation upload, 4 GB SaaS download) are calibrated to cleanly cross common SIEM thresholds. For a customer's environment with HIGHER-volume baselines (e.g. media production company where multi-GB uploads are routine), bump the volumes 5-10× to ensure the signal stands out from baseline traffic. For lower-volume environments (small-business SaaS tenants), the default volumes are adequate.
