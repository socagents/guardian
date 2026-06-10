---
name: oauth_consent_to_cloud_pivot
displayName: OAuth consent abuse
category: scenarios
description: 'Four-stage cloud-identity attack chain. Stage 1: user clicks an OAuth consent-phishing landing page (proxy logs the click). Stage 2: malicious OAuth app receives consent + impossible-travel sign-in to SaaS. Stage 3: inbox auto-forward rule established for stealth exfiltration. Stage 4: attacker pivots from SaaS-token foothold to cloud IAM, creating a service-account key. Vendor-agnostic — agent reads the operator''s technology stack at runtime. Triggers 4 XSIAM rules: Impossible Travel, OAuth Consent Grant Abuse, Mailbox Forwarding Rule Abuse, Cloud IAM Key Creation.'
icon: cloud_off
source: platform
loadingMode: on-demand
locked: false
attack:
  - 'TA0001: Initial Access (T1078.004 Cloud Accounts)'
  - 'TA0003: Persistence (T1098.001 Additional Cloud Credentials, T1098.003 Additional Cloud Roles)'
  - 'TA0006: Credential Access (T1528 Steal Application Access Token)'
  - 'TA0010: Exfiltration (T1114.003 Email Forwarding Rule)'
---

# Skill: OAuth consent abuse → Cloud privilege pivot

## Category

scenarios

## Attack Type

Identity-first cloud attack. Bypasses MFA entirely — the user authorizes a malicious OAuth app, and the attacker uses the resulting access token to operate as the user without ever supplying credentials at the SaaS sign-in. The chain extends from SaaS into IaaS by abusing the user's existing cloud-platform privileges to mint a long-lived service-account key for persistent access.

## MITRE ATT&CK Tactics

- TA0001: Initial Access (T1078.004 Cloud Accounts)
- TA0003: Persistence (T1098.001 Additional Cloud Credentials, T1098.003 Additional Cloud Roles)
- TA0006: Credential Access (T1528 Steal Application Access Token)
- TA0010: Exfiltration (T1114.003 Email Forwarding Rule)

## XSIAM analytics rules triggered

| # | Rule | Stage |
|---|---|---|
| 4 | Impossible Travel | Stage 2 |
| 10 | OAuth Consent Grant Abuse | Stage 2 |
| 11 | Mailbox Forwarding Rule Abuse | Stage 3 |
| 17 | Cloud IAM Key Creation (suspicious identity) | Stage 4 |

## Data classes used

| Stage | Data class | If missing |
|---|---|---|
| 1 | `proxy` | Substitute with `firewall` (less context, but the connection is still logged) |
| 2, 3 | `saas` | Required |
| 4 | `cloud` | Required for Stage 4; if missing, end the chain at Stage 3 with a note that the cloud-pivot would fire if cloud audit was instrumented |

## Pre-flight

Call `phantom_get_technology_stack`. Verify `saas` is present (this skill is specifically about SaaS identity abuse). `cloud` is needed for the full chain; if missing, run Stages 1-3 only.

## Narrative thread

- **Phishing landing page:** `https://cloud-app-marketplace.fyi/authorize?client_id=...`
- **Target user:** `k.dimitri@bupa.example` (devops engineer with cloud platform admin access)
- **Target user's normal sign-in country:** `GR` (Greece — works from Athens office)
- **Attacker source IP:** `194.165.16.45`
- **Attacker source country:** `RU`
- **Malicious OAuth app:** `QuickApprove eSignature`
- **OAuth client_id:** `c4f1e8d2-7a93-4b21-9c5e-8d3f7a2b1e9c`
- **Inbox forward target:** `dimitri.k.archive@gmx.com`
- **Cloud project:** `gcp-prod-bupa`
- **Cloud SA created:** `data-export-svc@gcp-prod-bupa.iam.gserviceaccount.com`
- **Cloud SA key ID:** `8f3a91d2c4b7e5a8d6f9b2c1e4a7d3f5b8c2e9a1`
- **Wall-clock time:** Stage 1 ~2 min (user clicks). Stage 2 ~4 min (consent flow + sign-in). Stage 3 ~3 min after Stage 2. Stage 4 ~8 min after Stage 3 (attacker pivots to cloud).

---

### Stage 1 — User clicks consent-phishing landing — 4 events over 60 seconds

The user receives an email (out of scope for this skill — the email gateway side is in `phishing_to_cloud_takeover`) with a link to a fake OAuth consent page that mimics Microsoft's official consent flow. They click. Proxy logs the GET + the redirect to the legitimate Microsoft authorization endpoint (the attacker's app is registered, so the consent flow IS technically through `login.microsoftonline.com` even though the attacker controls what app they're consenting TO).

**Data class:** `proxy`

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[proxy].formats[0].upper()>
    vendor:  <stack[proxy].vendor>
    product: <stack[proxy].product>
    count:    4
    interval: 15
    destination: <stack.log_destination.type>
    duration_seconds: 60
    observables_dict:
      src_ip:        ["10.10.20.91"]
      src_host:      ["wks-kdimitri-01"]
      user:          ["k.dimitri"]
      url:           ["https://cloud-app-marketplace.fyi/authorize?client_id=c4f1e8d2-7a93-4b21-9c5e-8d3f7a2b1e9c",
                      "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id=c4f1e8d2-7a93-4b21-9c5e-8d3f7a2b1e9c&response_type=code&scope=Mail.ReadWrite%20Mail.Send%20Files.ReadWrite.All",
                      "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?...response_mode=query&state=..."]
      method:        ["GET"]
      status_code:   ["200", "302"]
      user_agent:    ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0"]
      action:        ["allow"]
      category:      ["newly-registered-domain", "cloud-providers", "authentication"]
      threat_category: ["suspicious", "clean", "clean"]
      threat_score:    ["68", "5", "5"]
      domain:        ["cloud-app-marketplace.fyi", "login.microsoftonline.com"]
      domain_age_days: ["18", "10000"]
      referrer:      ["", "https://cloud-app-marketplace.fyi/authorize"]
```

**Field semantics:**
- The first URL is the attacker's landing page (typo-squatted "marketplace" domain)
- The second is the legitimate Microsoft authorization endpoint, but with a malicious `client_id` and a high-permission `scope` (`Mail.ReadWrite Mail.Send Files.ReadWrite.All`). The user sees Microsoft's logo on a real `login.microsoftonline.com` URL — they have no easy way to know the app behind `client_id=c4f1e8d2-...` is malicious
- `referrer` chain — the proxy can correlate "user came from `cloud-app-marketplace.fyi` → went to Microsoft consent flow"
- `domain_age_days: 18` for the landing — a 2-week-old domain hosting a Microsoft-styled consent prompt is the suspicious signal

**Why this is the visibility for Stage 2:** Stage 1 alone may not fire a SIEM rule (the redirect to Microsoft is legitimate-looking). But it gives investigators the breadcrumb: the suspicious source domain. Some SIEMs auto-correlate this with the OAuth grant in Stage 2 if both events appear within a short window for the same user.

---

### Stage 2 — Impossible-travel sign-in + OAuth consent grant — 4 events over 90 seconds

The OAuth consent flow completes. The attacker now has a Mail.ReadWrite + Files.ReadWrite.All access token. They use it to sign into the SaaS app — but from `RU`, not `GR`. Two parallel events fire simultaneously.

**Data class:** `saas`

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[saas].formats[0].upper()>
    vendor:  <stack[saas].vendor>
    product: <stack[saas].product>
    count:    4
    interval: 22
    destination: <stack.log_destination.type>
    duration_seconds: 90
    observables_dict:
      user:                  ["k.dimitri@bupa.example"]
      user_principal_name:   ["k.dimitri@bupa.example"]
      src_ip:                ["194.165.16.45"]
      country:               ["RU"]
      city:                  ["St. Petersburg"]
      action:                ["consent_to_application", "login_success",
                              "add_oauth2permissiongrant", "add_app_role_assignment"]
      operation:             ["Consent to application",
                              "User signed in with OAuth token",
                              "Add delegated permission grant",
                              "Add app role assignment grant to user"]
      app_name:              ["QuickApprove eSignature"]
      app_id:                ["c4f1e8d2-7a93-4b21-9c5e-8d3f7a2b1e9c"]
      app_publisher:         ["unverified"]
      permissions_granted:   ["Mail.ReadWrite", "Mail.Send", "Files.ReadWrite.All",
                              "User.Read", "offline_access"]
      consent_type:          ["UserConsent"]
      authentication_protocol: ["AzureAD-OAuth2"]
      authentication_method: ["password", "oauth_token"]
      mfa_required:          ["false"]
      session_id:            ["SaaS-SESS-c4f1e8d2-9c5e-8d3f-7a2b-1e9c91d2c4b7"]
      target_resource:       ["00000003-0000-0000-c000-000000000000"]
      severity:              ["high"]
```

**Field semantics:**
- `country: RU` — anomalous geo (user is normally `GR`)
- `app_publisher: unverified` + high-risk `permissions_granted` — the OAuth abuse signature
- `consent_type: UserConsent` — user-level consent (not admin-consent), which is exactly the abuse vector
- `session_id` propagates into Stages 3-4

**Pre-seed baseline** (skip if tenant is mature):

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[saas].formats[0].upper()>
    vendor:  <stack[saas].vendor>
    product: <stack[saas].product>
    count:    15
    interval: 7200
    destination: <stack.log_destination.type>
    duration_seconds: 108000
    observables_dict:
      user:    ["k.dimitri@bupa.example"]
      src_ip:  ["46.103.12.45", "46.103.12.91"]
      country: ["GR"]
      action:  ["login_success"]
```

**Why this fires Rules #4 + #10:** the impossible-travel rule fires on the geographic delta. The OAuth consent abuse rule fires on `app_publisher=unverified` + high-risk permissions + UserConsent. Both within 90 seconds of each other = correlated incident.

---

### Stage 3 — Inbox forwarding rule abuse — 1 event

Within minutes of the consent grant, the attacker uses the Mail.ReadWrite token to create an inbox rule that forwards future mail to their personal mailbox. This is the persistence + exfil-of-future-mail mechanism.

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
      user:           ["k.dimitri@bupa.example"]
      action:         ["new-inboxrule"]
      operation:      ["New-InboxRule"]
      rule_name:      ["GMX Sync"]
      rule_action:    ["ForwardTo"]
      forward_to:     ["dimitri.k.archive@gmx.com"]
      forward_external: ["true"]
      mark_as_read:   ["false"]
      delete_message: ["false"]
      session_id:     ["SaaS-SESS-c4f1e8d2-9c5e-8d3f-7a2b-1e9c91d2c4b7"]
      src_ip:         ["194.165.16.45"]
      app_id:         ["c4f1e8d2-7a93-4b21-9c5e-8d3f7a2b1e9c"]
      country:        ["RU"]
      severity:       ["high"]
```

**Field semantics:** identical to the inbox-rule semantics in `phishing_to_cloud_takeover` Stage 5A. The signature is `forward_external=true` + non-corporate domain + created via OAuth-token session.

**Why this fires Rule #11:** mailbox auto-forward to external = persistent exfiltration mechanism. SIEMs rate this critical regardless of context, but doubly so when the rule was created via an unverified OAuth app's session.

---

### Stage 4 — Cloud IAM service-account key creation — 5 events over 4 minutes

`k.dimitri` has cloud platform admin (real GCP IAM Editor or Owner). The attacker, using the OAuth-stolen identity, hops to the cloud platform's web console (the SaaS sign-in token works for Workspace SSO into GCP Console). Once in the cloud project, they create a new service account with broad permissions, then create a JSON key for it (long-lived credential they can use even after the user resets their password).

**Data class:** `cloud`

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[cloud].formats[0].upper()>
    vendor:  <stack[cloud].vendor>
    product: <stack[cloud].product>
    count:    5
    interval: 48
    destination: <stack.log_destination.type>
    duration_seconds: 240
    observables_dict:
      project_id:    ["gcp-prod-bupa"]
      actor_email:   ["k.dimitri@bupa.example"]
      actor_ip:      ["194.165.16.45"]
      country:       ["RU"]
      action:        ["google.iam.admin.v1.CreateServiceAccount",
                      "google.iam.admin.v1.CreateServiceAccountKey",
                      "google.iam.admin.v1.SetIamPolicy"]
      api_endpoint:  ["iam.googleapis.com"]
      api_method:    ["projects.serviceAccounts.create",
                      "projects.serviceAccounts.keys.create",
                      "projects.setIamPolicy"]
      resource_name: ["projects/gcp-prod-bupa/serviceAccounts/data-export-svc@gcp-prod-bupa.iam.gserviceaccount.com",
                      "projects/gcp-prod-bupa/serviceAccounts/data-export-svc@gcp-prod-bupa.iam.gserviceaccount.com/keys/8f3a91d2c4b7e5a8d6f9b2c1e4a7d3f5b8c2e9a1"]
      sa_email:      ["data-export-svc@gcp-prod-bupa.iam.gserviceaccount.com"]
      sa_key_id:     ["8f3a91d2c4b7e5a8d6f9b2c1e4a7d3f5b8c2e9a1"]
      sa_key_type:   ["USER_MANAGED"]
      role_granted:  ["roles/owner", "roles/iam.serviceAccountTokenCreator"]
      authentication_method: ["oauth_token"]
      severity:      ["critical"]
```

**Field semantics:**
- `actor_email: k.dimitri@bupa.example` — the legitimate user, but the actor IP + country are anomalous
- `action: CreateServiceAccount + CreateServiceAccountKey + SetIamPolicy` — the canonical "I'm establishing persistent backdoor access" sequence
- `sa_email: data-export-svc@...` — the SA name is intentionally innocuous (sounds like it could be a data pipeline component)
- `sa_key_type: USER_MANAGED` — the riskiest key type; long-lived JSON file the attacker now controls
- `role_granted: roles/owner` — the SA gets full project ownership

**Why this fires Rule #17:** the IAM-key-creation event with role escalation to `roles/owner` from an anomalous actor IP is high-severity in any modern cloud-detection ruleset. Even ignoring the IP, the SA-with-Owner-and-self-impersonation pattern is suspicious enough to fire on its own.

---

## Verification

| Indicator | Where to check |
|---|---|
| Impossible travel for `k.dimitri` (`GR` → `RU`) | XSIAM Issues |
| OAuth consent abuse alert with `app_id=c4f1e8d2-...` | XSIAM Issues |
| Mailbox rule abuse with `forward_to=*@gmx.com` | XSIAM Issues |
| Cloud IAM SA key creation with `roles/owner` | XSIAM Issues |
| Pivotable: filter by `actor=k.dimitri`, see all 4 stages | XQL: `dataset = msft_o365_audit_raw \| filter UserId = "k.dimitri@bupa.example"` |

## Tear-down

```yaml
xlog.list_workers:
xlog.kill_worker:
  worker_id: <each>
```

## Adapting per deployment

The user `k.dimitri` is illustrative. For a real exercise tied to the customer's identity model, pick a user who genuinely has cloud platform admin (so the cloud-pivot stage is realistic against their actual IAM hierarchy).
