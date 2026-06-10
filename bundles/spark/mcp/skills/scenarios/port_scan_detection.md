---
name: port_scan_detection
displayName: Port scan detection
category: scenarios
description: 'Three-pattern external reconnaissance skill focused exclusively on port-scan detection. Stage 1: horizontal scan (one source → many internal IPs on the same port — the "find all SSH boxes" pattern). Stage 2: vertical scan (one source → one internal IP across many ports — the port enumeration pattern). Stage 3: distributed scan (many sources → many destinations on common service ports — the slow stealth-scan pattern). Each stage emits firewall + WAF events with the full network 5-tuple populated. Vendor-agnostic — agent reads the operator''s technology stack at runtime. Triggers 3 XSIAM rules: Port Scan Detection (single-source variant), Distributed Port Scan, Suspicious Internal Reconnaissance.'
icon: radar
source: platform
loadingMode: on-demand
locked: false
attack:
  - 'TA0043: Reconnaissance (T1595.001 Scanning IP Blocks, T1595.002 Vulnerability Scanning)'
# v0.3.26 — promoted from the (now-deleted) _HARDCODED_ENRICHMENT
# dict in simulation_skills.py. Frontmatter is the single source of
# truth for skill metadata; load_simulation_skills + filter_skills
# read these fields to drive keyword/category/attack_type queries
# from the chat agent.
attack_type: reconnaissance
complexity: low
duration: 5-10 minutes
caldera_required: false
devices_required:
  - firewall
  - ids_ips
  - waf
prerequisites:
  - generate_shared_iocs
keywords:
  - scan
  - port
  - recon
  - reconnaissance
  - nmap
  - fortigate
  - firewall
tactics:
  - TA0043
  - TA0007
techniques:
  - T1046
---

# Skill: Port scan detection

## Category

scenarios

## Attack Type

Pre-attack network reconnaissance focused on port-scanning patterns. Most SOCs ignore scan traffic ("internet noise") and only respond after exploit. This skill validates that scan-detection rules fire before the actual attack — the early-warning value that makes recon detection worth the noise.

Three distinct patterns covered, each commonly seen in real attacks:

- **Horizontal scan** (1 src → N dst, same port): "find me all the SSH boxes" — used by botnets and worms
- **Vertical scan** (1 src → 1 dst, N ports): "what services are running on this host" — used by targeted attackers
- **Distributed scan** (N srcs → N dsts, common ports): "stealth scan from a botnet" — used by sophisticated adversaries

## MITRE ATT&CK Tactics

- TA0043: Reconnaissance (T1595.001 Scanning IP Blocks, T1595.002 Vulnerability Scanning)

## XSIAM analytics rules triggered

| # | Rule | Stage |
|---|---|---|
| - | Port Scan — Single Source Multiple Destinations | Stage 1 |
| - | Port Scan — Vertical / Service Enumeration | Stage 2 |
| - | Distributed Port Scan / Botnet Recon | Stage 3 |

## Data classes used

| Stage | Data class | If missing |
|---|---|---|
| 1, 2, 3 | `firewall` | Required — entire skill keys on perimeter network telemetry |
| 1, 3 | `waf` (optional) | If present, emits HTTP-port-scan signals alongside the firewall events |

## Pre-flight

Call `phantom_get_technology_stack`. Verify `firewall` is present. If multiple firewall entries exist (e.g. PANOS perimeter + Check Point internal), the skill fires events on the PERIMETER firewall only by default — the operator can adjust by editing the recipes below to target the internal firewall too if their topology has internal scan paths to validate.

## Narrative thread

- **Attacker source IP (Stages 1 + 2):** `192.0.2.42` (TEST-NET-2 documentation range — replace with TI-feed IP for real exercises)
- **Distributed source pool (Stage 3):** `192.0.2.42`, `192.0.2.91`, `192.0.2.114`, `198.51.100.42`, `198.51.100.91`, `203.0.113.18`, `203.0.113.66`, `203.0.113.142`
- **Internal subnet target:** `10.10.30.0/24` (DMZ)
- **Vertical scan target host (Stage 2):** `10.10.30.10` (web-app-01 — the focus of Stage 2's port enumeration)
- **Wall-clock time:** Stage 1 ~12 min slow scan. Stage 2 ~5 min faster port enum. Stage 3 ~45 min stealth distributed scan. Stages can run in sequence or parallel; sequential is more realistic.

---

### Stage 1 — Horizontal scan (1 src → N dst, same port) — ~150 events over 12 minutes

The attacker sweeps `10.10.30.0/24` looking for hosts with SSH (port 22) open. ~150 connection attempts at ~5s intervals — slow enough to evade naive rate-limit detections, fast enough to complete a /24 sweep in under 15 minutes. Most return RST (firewall denies, no service); a few get through to hosts with SSH actually open.

**Data class:** `firewall`

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[firewall].formats[0].upper()>
    vendor:  <stack[firewall].vendor>
    product: <stack[firewall].product>
    count:    150
    interval: 5
    destination: <stack.log_destination.type>
    duration_seconds: 750
    observables_dict:
      src_ip:        ["192.0.2.42"]
      dst_ip:        ["10.10.30.1", "10.10.30.5", "10.10.30.10",
                      "10.10.30.20", "10.10.30.42", "10.10.30.50",
                      "10.10.30.100", "10.10.30.150", "10.10.30.200",
                      "10.10.30.250"]
      src_port:      ["49152", "51234", "57890", "60123", "62456"]
      dst_port:      ["22"]
      protocol:      ["tcp"]
      action:        ["deny", "allow"]
      action_status: ["denied", "established"]
      session_state: ["denied", "established"]
      app:           ["unknown", "ssh"]
      bytes_sent:    ["64", "120"]
      bytes_received: ["0", "240"]
      tcp_flag:      ["SYN", "RST", "SYN-ACK"]
      country:       ["unknown"]
      threat_score:  ["35", "60"]
```

**Field semantics:**
- `src_ip` — single attacker source; the "many users from one source" pattern is the recon signature
- `dst_ip` — 10 different internal IPs across the DMZ subnet, one connection per IP
- `dst_port: 22` — SSH; common service to look for. Could substitute 3389 for RDP, 1433 for SQL Server, etc.
- `action: deny / allow` — most are denied (no SSH service on those IPs), a few get through to actual SSH boxes
- `tcp_flag: SYN` for failed attempts, `SYN-ACK` for the few connections that succeed

**Why this fires the rule:** N distinct dst_ips from one src_ip on the same port within a window — typical threshold is ≥10 distinct dst_ips / 5 min. The 150 events spread across 10 dsts = trivially crosses it.

---

### Stage 2 — Vertical scan (1 src → 1 dst, many ports) — ~80 events over 5 minutes

Now the attacker focuses on the one host where SSH was open (`10.10.30.10` — web-app-01). They run a full port enumeration: TCP 1-65535 in a fast scan. ~80 distinct ports tested over 5 minutes.

**Data class:** `firewall`

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[firewall].formats[0].upper()>
    vendor:  <stack[firewall].vendor>
    product: <stack[firewall].product>
    count:    80
    interval: 4
    destination: <stack.log_destination.type>
    duration_seconds: 320
    observables_dict:
      src_ip:        ["192.0.2.42"]
      dst_ip:        ["10.10.30.10"]
      src_port:      ["49152", "49251", "49380", "50127", "50882"]
      dst_port:      ["21", "22", "23", "25", "53", "80", "110",
                      "135", "139", "143", "443", "445", "465",
                      "587", "993", "995", "1433", "1521", "3306",
                      "3389", "5432", "5985", "5986", "8080", "8443",
                      "9000", "9090", "27017", "6379", "11211"]
      protocol:      ["tcp"]
      action:        ["deny", "allow"]
      action_status: ["denied", "established"]
      session_state: ["denied", "established"]
      app:           ["unknown", "http", "https", "ssh", "smb",
                      "ms-rdp", "mysql"]
      bytes_sent:    ["64", "120"]
      bytes_received: ["0", "240"]
      tcp_flag:      ["SYN", "RST", "SYN-ACK"]
      threat_score:  ["55", "70"]
```

**Field semantics:**
- `src_ip` / `dst_ip` — single src, single dst (vertical = focus on one host)
- `dst_port` — 30 different ports spanning common service patterns
- 30 dst_ports × ~3 attempts per port = ~80 events
- `action: deny` predominates (most ports closed), `allow` for the few open ones (e.g. 22, 80, 443)

**Why this fires the rule:** N distinct dst_ports from one src_ip to one dst_ip within a window — typical threshold is ≥20 ports / 5 min. 30 ports / 5 min crosses it 1.5x over.

---

### Stage 3 — Distributed scan (N srcs → N dsts, common ports) — ~400 events over 45 minutes

The slowest, hardest-to-detect pattern. Multiple attacker sources (8 IPs across 3 netblocks) collectively scan the DMZ for common services. Per-source rate is below trivial thresholds; per-dst rate is below trivial thresholds. Only the AGGREGATE (many sources hitting many dsts on the same port-set within a window) reveals the pattern.

**Data class:** `firewall`

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[firewall].formats[0].upper()>
    vendor:  <stack[firewall].vendor>
    product: <stack[firewall].product>
    count:    400
    interval: 7
    destination: <stack.log_destination.type>
    duration_seconds: 2800
    observables_dict:
      src_ip:        ["192.0.2.42", "192.0.2.91", "192.0.2.114",
                      "198.51.100.42", "198.51.100.91",
                      "203.0.113.18", "203.0.113.66", "203.0.113.142"]
      dst_ip:        ["10.10.30.1", "10.10.30.5", "10.10.30.10",
                      "10.10.30.20", "10.10.30.42", "10.10.30.50",
                      "10.10.30.100", "10.10.30.150", "10.10.30.200",
                      "10.10.30.250"]
      src_port:      ["49152", "51234", "57890", "60123", "62456"]
      dst_port:      ["22", "80", "443", "445", "3389", "5985",
                      "8080", "8443"]
      protocol:      ["tcp"]
      action:        ["deny", "allow"]
      action_status: ["denied", "established"]
      session_state: ["denied", "established"]
      app:           ["unknown", "http", "https", "ssh", "smb",
                      "ms-rdp"]
      bytes_sent:    ["64", "120"]
      bytes_received: ["0", "240"]
      tcp_flag:      ["SYN", "RST", "SYN-ACK"]
      country:       ["unknown", "RU", "BG", "CN", "RO"]
      threat_score:  ["45", "65", "82"]
      asn_source:    ["AS9009", "AS3320", "AS4837"]
```

**Field semantics:**
- `src_ip` — 8 different sources across 3 netblocks (looks distributed in geo-enrichment too)
- `dst_ip` — 10 different dsts in the DMZ
- `dst_port` — focused on 8 common service ports (the "high-value targets" set)
- `country` — spread across high-risk countries to reinforce the distributed-source signal
- 8 srcs × 10 dsts × 8 ports × ~6 attempts per combo = ~400 events
- `threat_score: 82` — the highest values for sources flagged by threat-intel feed

**Why this fires the rule:** the cross-aggregation (≥5 distinct sources × ≥10 distinct dsts × ≥5 distinct ports / 30 min) is the textbook distributed-scan signature. Per-source rate stays below the simpler "single-source scan" thresholds, so distributed scans require this specific aggregation rule to detect.

---

### Optional: WAF-visible HTTP port discovery (when `waf` is in stack)

When the operator's stack includes a WAF, this sub-stage adds HTTP-layer scan signals that reinforce the firewall-tier signals above. The WAF sees the HTTP requests on port 80/443 + 8080/8443 and detects scanner UA fingerprints / common-path enumeration.

**Data class:** `waf` (run in parallel with Stage 1 if `waf` is in stack)

```yaml
xlog.create_data_worker:
  request:
    type:    <stack[waf].formats[0].upper()>
    vendor:  <stack[waf].vendor>
    product: <stack[waf].product>
    count:    50
    interval: 14
    destination: <stack.log_destination.type>
    duration_seconds: 700
    observables_dict:
      src_ip:        ["192.0.2.42"]
      dst_ip:        ["10.10.30.10"]
      src_port:      ["49152", "51234", "57890"]
      dst_port:      ["443", "80", "8080", "8443"]
      protocol:      ["tcp"]
      url:           ["/", "/admin/", "/login.php", "/wp-admin/",
                      "/.well-known/security.txt", "/robots.txt",
                      "/swagger/", "/server-status",
                      "/.git/config", "/.env"]
      method:        ["GET", "HEAD"]
      status_code:   ["200", "403", "404"]
      user_agent:    ["Mozilla/5.0 (compatible; Nuclei/3.0)",
                      "ffuf/2.0.0",
                      "masscan/1.3.2",
                      "Mozilla/5.0 (compatible; Nmap/7.94)"]
      action:        ["allow", "alert"]
      attack_type:   ["scanner-fingerprint", "directory-enumeration",
                      "common-vulnerabilities"]
      threat_score:  ["72", "85"]
```

---

## Verification

| Indicator | Where to check |
|---|---|
| Stage 1 horizontal-scan alert (1 src → N dst on port 22) | XSIAM Issues |
| Stage 2 vertical-scan alert (1 src → 1 dst, ≥20 distinct ports) | XSIAM Issues |
| Stage 3 distributed-scan alert (cross-aggregation) | XSIAM Issues |
| Pivotable: filter `dst_subnet=10.10.30.0/24`, see all 3 patterns on one timeline | XQL: `dataset = firewall_logs \| filter dst_ip in ("10.10.30.0", "10.10.30.255")` |

## Tear-down

```yaml
xlog.list_workers:
xlog.kill_worker:
  worker_id: <each>
```

## Adapting per deployment

The DMZ subnet `10.10.30.0/24` and target host `10.10.30.10` are illustrative. For real exercises, replace with the customer's actual perimeter subnet so the alerts enrich with the customer's CMDB context. The 8-source distributed pool is also illustrative — for higher-fidelity TI integration, swap with IPs from the customer's threat-intel feed.
