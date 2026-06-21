---
id: XQL-IR-236-impossible-travel-concurrent-geo-logons
title: Impossible travel / concurrent geo logons (T1078)
category: investigation
dataset: okta_sso_raw
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1078]
---

# Impossible travel / concurrent geo logons (T1078)

**Dataset**: `okta_sso_raw`

Scopes valid-account abuse by surfacing users who successfully authenticate from multiple countries (or many source IPs) inside one short window — the impossible-travel signal for stolen credentials. Tune the country/IP thresholds and shorten the `bin` span for tighter "concurrent" semantics; corporate VPN exits often need allow-listing.

```sql
dataset = okta_sso_raw
| alter outcome = json_extract_scalar(_raw_log, "$.outcome.result"), country = json_extract_scalar(_raw_log, "$.client.geographicalContext.country"), src_ip = json_extract_scalar(_raw_log, "$.client.ipAddress"), actor = lowercase(json_extract_scalar(_raw_log, "$.actor.alternateId"))
| filter outcome = "SUCCESS"
| bin _time span = 1h
| comp count_distinct(country) as distinct_countries, count_distinct(src_ip) as distinct_ips, values(country) as countries, values(src_ip) as source_ips by actor, _time
| filter distinct_countries >= 2
| sort desc distinct_countries, desc distinct_ips
```
