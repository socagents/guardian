---
name: phishing_to_cloud_takeover
displayName: Phishing cloud takeover
category: scenarios
description: 'Five-stage external-to-cloud chain. Phishing email delivers a credential-harvest URL → user clicks (proxy logs the GET) → stolen creds replayed at the SaaS sign-in (impossible travel) → attacker grants OAuth consent to a malicious app → inbox forwarding rule exfiltrates mail → bulk download from cloud storage. Vendor-agnostic — agent reads the operator''s technology stack at runtime. Triggers 6 XSIAM rules: Phishing email with malicious attachment, Malicious file download via proxy, Impossible Travel, OAuth Consent Grant Abuse, Mailbox Forwarding Rule Abuse, Data exfiltration to personal cloud storage.'
icon: phishing
source: platform
loadingMode: on-demand
locked: false
attack:
  - 'TA0001: Initial Access (T1566.002 Spearphishing Link, T1078.004 Cloud Accounts)'
  - 'TA0006: Credential Access (T1078 Valid Accounts)'
  - 'TA0003: Persistence (T1098.005 Device Registration, T1098.003 Additional Cloud Roles)'
  - 'TA0010: Exfiltration (T1567.002 Exfiltration to Cloud Storage, T1114.003 Email Forwarding Rule)'
---

# Skill: Phishing → Credential harvest → Cloud takeover

## Category

scenarios

## Attack Type

Cloud-account takeover via consent-phishing tradecraft. Models the OAuth-grant abuse pattern that bypasses MFA entirely (the user authorizes the attacker's app legitimately; no password is ever guessed at the OAuth side). Most common variant: BEC actors and nation-state operators alike use this against M365 / Workspace tenants because the attacker keeps access even after the user rotates their password.

## MITRE ATT&CK Tactics

- TA0001: Initial Access (T1566.002 Spearphishing Link, T1078.004 Cloud Accounts)
- TA0006: Credential Access (T1078 Valid Accounts)
- TA0003: Persistence (T1098.005 Device Registration, T1098.003 Additional Cloud Roles)
- TA0010: Exfiltration (T1567.002 Exfiltration to Cloud Storage, T1114.003 Email Forwarding Rule)

## XSIAM analytics rules triggered

| # | Rule | Stage that fires it |
|---|---|---|
| 9 | Phishing email with malicious attachment / link | Stage 1 |
| 8 | Malicious file download / suspicious URL via proxy | Stage 2 |
| 4 | Impossible Travel | Stage 3 |
| 10 | OAuth Consent Grant Abuse | Stage 4 |
| 11 | Mailbox Forwarding Rule Abuse | Stage 5 |
| 20 | Data Exfiltration to Personal Cloud Storage | Stage 5 |

## Data classes used

| Stage | Data class | Why | If missing from stack |
|---|---|---|---|
| 1 | `email-gateway` | Email arrival + URL/attachment metadata | Required — stage cannot run; consider skipping Stage 1 and starting at Stage 2 (proxy click) |
| 2 | `proxy` | URL fetch by the user | Required for the click visibility; substitute with `firewall` if proxy missing (reduces fidelity) |
| 3 | `saas` (M365 or equivalent) | Sign-in event with country | Required — OAuth abuse requires the cloud audit log |
| 4, 5 | `saas` | OAuth consent + inbox rule + bulk download | Required |
| 5 | `proxy` + `firewall` | Egress to personal cloud storage | Use whichever the operator's stack has; ideally both |

## Pre-flight

Call `phantom_get_technology_stack`. Build the category lookup. If `email-gateway` AND `saas` are both missing, abort the skill — there's no way to model this attack without them. If only `proxy` is missing, fall back to firewall east-west denials at the proxy port (less fidelity but workable).

## Narrative thread

- **Phishing sender (Stage 1):** `invoice-portal@billing-secure-update.tk` (typo-squat domain on `.tk`)
- **Phishing landing URL (Stage 1, 2):** `https://billing-secure-update.tk/login.aspx?ref=invoice-Q4`
- **Target user:** `m.patel@bupa.example` (claims processing manager, normal sign-ins from `GB`)
- **Target user IP (normal baseline):** `86.150.42.18` (residential UK)
- **Stolen-creds replay source IP (Stage 3):** `91.243.59.108` (RU — unusual for this user)
- **Malicious OAuth app (Stage 4):** `InvoicePro Sync` — sounds plausible for a finance user
- **OAuth client_id:** `8ba2f3d4-9c47-4a91-b81e-22f3ec9d4a7e`
- **Inbox forward target (Stage 5):** `m.patel.archive@protonmail.com` (attacker-controlled mailbox)
- **Bulk-download target (Stage 5):** OneDrive folder `Q4-Claims-Documents` (~120 files)
- **Wall-clock time:** Stage 1 = single email (instant). Stage 2 ~3 min after delivery. Stage 3 ~8 min later. Stage 4-5 within 5 min of Stage 3 success.

---

### Stage 1 — Phishing email delivered (1 high-priority + 49 noise events) — ~50 events over 60 seconds

The malicious email lands. Generate ~49 noise events (legitimate marketing, partner emails, internal newsletters) so the signal isn't trivial; the malicious one is a single CEF entry with the credential-harvest URL.

**Data class:** `email-gateway`

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[email-gateway].formats[0].upper()>
    vendor:  <stack[email-gateway].vendor>
    product: <stack[email-gateway].product>
    count:    50
    interval: 1
    destination: <stack.log_destination.type>
    duration_seconds: 60
    observables_dict:
      sender_email:    ["partners@example-supplier.com", "newsletter@industry-news.io",
                        "noreply@hr-internal.bupa.example", "alerts@payroll-svc.bupa.example",
                        "invoice-portal@billing-secure-update.tk"]
      recipient_email: ["m.patel@bupa.example", "team-finance@bupa.example",
                        "all-employees@bupa.example"]
      email_subject:   ["Q4 Newsletter", "Project status update",
                        "Re: Payment terms", "Quarterly summary",
                        "URGENT: Invoice #INV-Q4-2891 Action Required"]
      url:             ["https://example-supplier.com/portal",
                        "https://industry-news.io/articles/12",
                        "https://billing-secure-update.tk/login.aspx?ref=invoice-Q4"]
      sender_domain:   ["example-supplier.com", "industry-news.io",
                        "billing-secure-update.tk", "hr-internal.bupa.example"]
      action:          ["delivered", "delivered", "quarantined", "delivered"]
      threat_category: ["clean", "clean", "phishing", "clean"]
      threat_score:    ["10", "20", "85", "5", "15"]
      severity:        ["informational", "high"]
      file_name:       []
      attachment_count: ["0", "1"]
```

**Field semantics:**
- `sender_email` / `sender_domain` — the malicious entry is the typo-squat `.tk` domain pretending to be a billing portal
- `url` — the credential-harvest landing page; this exact URL must reappear in Stage 2's proxy log so the SIEM correlates "the user who got the phish clicked it"
- `threat_category` / `threat_score` — most email gateways enrich with category + numeric risk score; `85` is in the "phishing" band
- `action: delivered` — the phish gets through to the user's inbox (the noise events also include some quarantines so the gateway doesn't look broken)
- `attachment_count: 0` — this is a credential-harvest phish (link, no attachment); a separate scenario covers macro-attachment phishing

**Why this fires Rule #9:** the email gateway entry combining `threat_category=phishing`, `threat_score>80`, `action=delivered`, and a known-bad sender domain matches the SIEM's "Phishing email with malicious link delivered" rule.

---

### Stage 2 — User clicks the link (proxy logs the GET) — 8 events over 90 seconds

Three minutes after delivery, `m.patel` opens the email and clicks. The proxy logs the HTTP GET. The credential harvester also serves a small JS bundle and posts the captured creds back, so we get 8 events total (1 GET to the login page + ~5 asset loads + 1 POST of credentials + 1 redirect).

**Data class:** `proxy`

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[proxy].formats[0].upper()>
    vendor:  <stack[proxy].vendor>
    product: <stack[proxy].product>
    count:    8
    interval: 11
    destination: <stack.log_destination.type>
    duration_seconds: 90
    observables_dict:
      src_ip:        ["10.10.20.42"]
      src_host:      ["wks-mpatel-01"]
      user:          ["m.patel"]
      src_port:      ["49152", "51234", "57890", "60123"]
      dst_port:      ["443"]
      protocol:      ["tcp"]
      user_agent:    ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0"]
      url:           ["https://billing-secure-update.tk/login.aspx?ref=invoice-Q4",
                      "https://billing-secure-update.tk/static/login.js",
                      "https://billing-secure-update.tk/static/style.css",
                      "https://billing-secure-update.tk/api/auth"]
      method:        ["GET", "GET", "POST"]
      status_code:   ["200", "302"]
      bytes_sent:    ["840", "1420", "320"]
      bytes_received: ["18420", "4280", "212"]
      content_type:   ["text/html", "application/javascript", "text/css", "application/json"]
      action:        ["allow"]
      category:      ["newly-registered-domain", "uncategorized"]
      threat_category: ["suspicious", "phishing"]
      threat_score:    ["75", "82"]
      referrer:        ["", "https://outlook.office.com/owa/"]
```

**Field semantics:**
- `src_ip` / `src_host` / `user` — bound to `m.patel`'s workstation; the user attribution lets the SIEM later say "the same user whose email got delivered the phish then clicked it"
- `url` — must include the EXACT URL from Stage 1's email so the SIEM correlates inbox→browser
- `method: POST` to `/api/auth` is the credential exfiltration — the proxy doesn't see the body but DOES see that the user just submitted form data to a new domain
- `category: newly-registered-domain` — the proxy enriches with domain age; phishing infrastructure is typically <30 days old
- `threat_category` / `threat_score` — proxy's URL-filtering verdict; `phishing/82` would normally block, but the proxy might be in monitor-mode for this category
- `referrer: https://outlook.office.com/owa/` on the redirect — proves the user came from webmail, sealing the inbox→click correlation

**Why this fires Rule #8:** the URL category (`phishing` or `newly-registered-domain`) combined with a POST containing form data crosses the "user accessed credential-harvest URL" threshold. Some SIEMs key on the URL category alone; others want the POST + reduce-confidence-on-GET pattern.

---

### Stage 3 — Stolen creds replayed at SaaS sign-in (impossible travel) — 1 event

Eight minutes after the click, the attacker replays the stolen creds against the SaaS provider (M365 or equivalent). The user has been signing in from `GB` for months; this attempt is from `RU`. MFA isn't triggered because the attacker uses an OAuth client that the user authorized in Stage 4 — but at THIS point, just a regular sign-in.

**Data class:** `saas`

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[saas].formats[0].upper()>
    vendor:  <stack[saas].vendor>
    product: <stack[saas].product>
    count:    1
    interval: 1
    destination: <stack.log_destination.type>
    duration_seconds: 1
    observables_dict:
      user:                  ["m.patel@bupa.example"]
      user_principal_name:   ["m.patel@bupa.example"]
      src_ip:                ["91.243.59.108"]
      country:               ["RU"]
      city:                  ["Moscow"]
      action:                ["login_success"]
      authentication_result: ["success"]
      authentication_method: ["password"]
      authentication_protocol: ["AzureAD-OAuth2"]
      mfa_required:          ["false"]
      session_id:            ["SaaS-SESS-d92f3e1c-44a7-4b19-8c2e-f3a91d8e7c45"]
      client_app:            ["Browser"]
      user_agent:            ["Mozilla/5.0 (X11; Linux x86_64) Firefox/115.0"]
      device_id:             ["unknown"]
      device_compliance:     ["non-compliant"]
      severity:              ["informational"]
```

**Field semantics:**
- `country: RU` vs the user's normal `GB` — the geographic delta is what fires impossible travel
- `mfa_required: false` — many tenants only enforce MFA for risky sign-ins; a "normal-looking" password sign-in skips MFA, which is exactly the bypass attackers exploit
- `device_id: unknown` + `device_compliance: non-compliant` — the attacker's machine isn't in the tenant's intune/MDM enrollment
- `session_id` — propagate this value into Stages 4-5 so all post-auth actions correlate

**Baseline pre-seed (skip if tenant has >2 weeks of real sign-in history):**

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[saas].formats[0].upper()>
    vendor:  <stack[saas].vendor>
    product: <stack[saas].product>
    count:    20
    interval: 7200
    destination: <stack.log_destination.type>
    duration_seconds: 144000
    observables_dict:
      user:    ["m.patel@bupa.example"]
      src_ip:  ["86.150.42.18", "86.150.42.91", "10.10.20.42"]
      country: ["GB"]
      action:  ["login_success"]
```

**Why this fires Rule #4:** geographic distance from the user's last successful sign-in (`GB`) to this one (`RU`) within hours is the impossible-travel signal. Some SIEMs also factor in IP reputation (`91.243.59.108` is in known-bad ranges) for higher-confidence alerts.

---

### Stage 4 — OAuth consent grant to malicious app — 3 events over 90 seconds

The attacker, now signed in as `m.patel`, navigates the OAuth consent flow to grant a malicious app the `Mail.ReadWrite`, `Mail.Send`, `Files.ReadWrite.All` permissions. The user already authenticated; the consent grant is a separate audit event.

**Data class:** `saas`

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[saas].formats[0].upper()>
    vendor:  <stack[saas].vendor>
    product: <stack[saas].product>
    count:    3
    interval: 30
    destination: <stack.log_destination.type>
    duration_seconds: 90
    observables_dict:
      user:                  ["m.patel@bupa.example"]
      action:                ["consent_to_application", "add_oauth2permissiongrant",
                              "add_app_role_assignment"]
      operation:             ["Add app role assignment grant to user",
                              "Add delegated permission grant",
                              "Consent to application"]
      app_name:              ["InvoicePro Sync"]
      app_id:                ["8ba2f3d4-9c47-4a91-b81e-22f3ec9d4a7e"]
      app_publisher:         ["unverified"]
      permissions_granted:   ["Mail.ReadWrite", "Mail.Send", "Files.ReadWrite.All",
                              "User.Read", "offline_access"]
      consent_type:          ["UserConsent"]
      target_resource:       ["00000003-0000-0000-c000-000000000000"]
      session_id:            ["SaaS-SESS-d92f3e1c-44a7-4b19-8c2e-f3a91d8e7c45"]
      src_ip:                ["91.243.59.108"]
      severity:              ["high"]
```

**Field semantics:**
- `app_publisher: unverified` — Microsoft Graph specifically flags apps without verified publisher; this is the field most consent-abuse rules key on
- `permissions_granted` — the high-risk permission set (read+write+send mail, all files) is the strongest single signal
- `consent_type: UserConsent` — the user consented (vs admin consent); user-consented apps are exactly the abuse vector because tenants often allow user consent without review
- `target_resource: 00000003-...` — Microsoft Graph's resource ID; populating it makes the recipe land in the correct M365 audit field

**Why this fires Rule #10:** the combination `app_publisher=unverified` + high-risk permissions (`Mail.ReadWrite` + `Files.ReadWrite.All`) + `consent_type=UserConsent` is the textbook OAuth abuse signature.

---

### Stage 5 — Inbox rule + bulk download (persistence + exfiltration) — ~125 events over 8 minutes

With the OAuth grant, the attacker (a) creates an inbox forwarding rule so future emails to `m.patel` flow to their mailbox, and (b) bulk-downloads the user's OneDrive `Q4-Claims-Documents` folder.

**Sub-stage 5A — inbox forwarding rule** (1 event)

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[saas].formats[0].upper()>
    vendor:  <stack[saas].vendor>
    product: <stack[saas].product>
    count:    1
    interval: 1
    destination: <stack.log_destination.type>
    duration_seconds: 1
    observables_dict:
      user:           ["m.patel@bupa.example"]
      action:         ["new-inboxrule"]
      operation:      ["New-InboxRule"]
      rule_name:      ["Auto-Archive External"]
      rule_action:    ["ForwardTo"]
      forward_to:     ["m.patel.archive@protonmail.com"]
      forward_external: ["true"]
      mark_as_read:   ["true"]
      delete_message: ["false"]
      session_id:     ["SaaS-SESS-d92f3e1c-44a7-4b19-8c2e-f3a91d8e7c45"]
      src_ip:         ["91.243.59.108"]
      app_id:         ["8ba2f3d4-9c47-4a91-b81e-22f3ec9d4a7e"]
      severity:       ["high"]
```

**Sub-stage 5B — bulk OneDrive download** (~120 events over 7 min)

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[saas].formats[0].upper()>
    vendor:  <stack[saas].vendor>
    product: <stack[saas].product>
    count:    120
    interval: 4
    destination: <stack.log_destination.type>
    duration_seconds: 480
    observables_dict:
      user:        ["m.patel@bupa.example"]
      action:      ["FileDownloaded"]
      operation:   ["FileDownloaded"]
      file_name:   ["claim-INV-2891-Q4.pdf", "policy-renewal-2891.docx",
                    "customer-data-export.xlsx", "claims-summary-Q4.pdf"]
      site_url:    ["/personal/m_patel_bupa_example/Documents/Q4-Claims-Documents"]
      bytes:       ["245000", "180000", "5240000", "320000", "890000"]
      client_ip:   ["91.243.59.108"]
      session_id:  ["SaaS-SESS-d92f3e1c-44a7-4b19-8c2e-f3a91d8e7c45"]
      app_id:      ["8ba2f3d4-9c47-4a91-b81e-22f3ec9d4a7e"]
      country:     ["RU"]
      severity:    ["medium"]
```

**Sub-stage 5C — egress to personal cloud (proxy or firewall)**

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[proxy].formats[0].upper()>
    vendor:  <stack[proxy].vendor>
    product: <stack[proxy].product>
    count:    20
    interval: 24
    destination: <stack.log_destination.type>
    duration_seconds: 480
    observables_dict:
      src_ip:        ["10.10.20.42"]
      user:          ["m.patel"]
      url:           ["https://www.dropbox.com/upload",
                      "https://api.dropboxapi.com/2/files/upload"]
      method:        ["POST"]
      status_code:   ["200"]
      bytes_sent:    ["5242880", "10485760", "8388608"]
      content_type:  ["application/octet-stream"]
      action:        ["allow"]
      category:      ["file-sharing", "personal-cloud-storage"]
      threat_score:  ["35"]
```

**Why this fires Rules #11 and #20:**
- **#11 (Mailbox Forwarding Rule Abuse):** `forward_external=true` to a non-corporate domain (`protonmail.com`) created from a non-compliant device + during an anomalous session = textbook signature
- **#20 (Data Exfiltration to Personal Cloud Storage):** large bulk transfer (`bytes` totals to ~200 MB across 120 file downloads) within minutes, then proxy POST to `dropbox.com` with multi-MB payloads — both signals together are unambiguous

---

## Verification

| Indicator | Where to check |
|---|---|
| Phishing email rule fired with `m.patel` recipient | XSIAM Issues, last 30 min |
| Proxy/URL alert for `billing-secure-update.tk` | XSIAM Issues |
| Impossible travel for `m.patel` (`GB` → `RU`) | XSIAM Issues |
| OAuth consent abuse alert with `app_id=8ba2f3d4-...` | XSIAM Issues |
| Mailbox rule abuse with `forward_to=*@protonmail.com` | XSIAM Issues |
| Exfiltration alert tied to OneDrive bulk-download volume | XSIAM Issues |
| Pivotable: filter `user=m.patel`, see all 6+ alerts in one timeline | XQL: `dataset = msft_o365_audit_raw \| filter UserId = "m.patel@bupa.example"` |

## Tear-down

```yaml
xlog.list_workers:
xlog.kill_worker:
  worker_id: <each>
```

## Adapting per deployment

Replace `m.patel@bupa.example` with the operator's chosen test user. The attack pattern is identity-agnostic; the OAuth consent + forwarding rule + bulk download chain is identical regardless of which user is targeted.
