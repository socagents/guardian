---
id: XQL-IR-230-remote-system-discovery
title: Remote system discovery via ping sweep / nbtstat (T1018)
category: threat-hunting
dataset: network_story
ecosystem: xsiam
tags: [filter, alter, bin, comp, sort]
attack: [T1018]
---

# Remote system discovery via ping sweep / nbtstat (T1018)

**Dataset**: `network_story`

Identifies a single internal source touching many distinct internal hosts in a short window — the network footprint of a ping/ARP sweep or `nbtstat` host-discovery scan. Tune `distinct_dests` to your subnet size and exclude sanctioned scanners (vuln management, asset discovery).

```sql
dataset = network_story
| filter action_local_ip incidr "10.0.0.0/8" and action_remote_ip incidr "10.0.0.0/8"
| alter src = action_local_ip, dst = action_remote_ip
| bin _time span = 10m
| comp count_distinct(dst) as distinct_dests, count() as connections, values(dst) as targets by src, _time
| filter distinct_dests >= 25
| sort desc distinct_dests
```
