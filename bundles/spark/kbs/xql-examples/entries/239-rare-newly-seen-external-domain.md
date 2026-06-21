---
id: XQL-IR-239-rare-newly-seen-external-domain
title: Rare external destination seen by a single host (T1071)
category: threat-hunting
dataset: network_story
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1071]
---

# Rare external destination seen by a single host (T1071)

**Dataset**: `network_story`

Surfaces external domains contacted by exactly one internal host with very few sessions - the long tail where staging, C2, and newly-registered infrastructure hide. First-seen recency is approximated with `timestamp_diff` against the earliest contact. Tune by adjusting `talker_count = 1` to allow small clusters, or shrink the recency window.

```sql
dataset = network_story
| filter action_external_hostname != null and incidr(dst_ip, "10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16") = false
| alter reg_domain = extract_url_registered_domain(action_external_hostname)
| comp count() as session_count, count_distinct(src_ip) as talker_count, min(_time) as first_seen by reg_domain
| alter age_hours = timestamp_diff(current_time(), first_seen, "HOUR")
| filter talker_count = 1 and session_count <= 5 and age_hours <= 72
| sort asc first_seen
```
