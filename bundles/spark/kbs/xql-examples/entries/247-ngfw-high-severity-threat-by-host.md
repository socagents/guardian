---
id: XQL-IR-247-ngfw-high-severity-threat-by-host
title: NGFW high-severity threat hits concentrated on a host (T1190)
category: investigation
dataset: panw_ngfw_threat_raw
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1190]
---

# NGFW high-severity threat hits concentrated on a host (T1190)

**Dataset**: `panw_ngfw_threat_raw`

Scopes exploitation attempts against public-facing assets by ranking internal hosts on count and diversity of critical/high firewall threat signatures (vulnerability, exploit-kit, code-execution sub-types). High `distinct_threats` on one destination suggests active probing of an exposed service. Tune severity terms and the `hit_count` floor to your perimeter noise.

```sql
dataset = panw_ngfw_threat_raw
| filter severity in ("critical", "high") and sub_type in ("vulnerability", "code-execution", "exploit", "scan", "brute-force")
| filter action != "reset-both" or action = "alert"
| comp count() as hit_count, count_distinct(threat_name) as distinct_threats, count_distinct(source_ip) as distinct_sources, values(threat_name) as threats, values(rule_matched) as rules by dest_ip, dest_device_host
| filter hit_count >= 10
| sort desc distinct_threats
```
