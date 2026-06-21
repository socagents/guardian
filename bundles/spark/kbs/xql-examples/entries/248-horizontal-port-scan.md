---
id: XQL-IR-248-horizontal-port-scan
title: Horizontal port scan across many internal hosts (T1046)
category: threat-hunting
dataset: panw_ngfw_traffic_raw
ecosystem: xsiam
tags: [filter, alter, bin, comp, sort]
attack: [T1046]
---

# Horizontal port scan across many internal hosts (T1046)

**Dataset**: `panw_ngfw_traffic_raw`

Detects network service discovery: one source touching the same port across many distinct internal destinations in a short window (horizontal sweep). Binning by minute isolates the scan burst, and the ratio of destinations to sessions confirms breadth over depth. Tune `distinct_dests` to your subnet size and the bin span to the expected scan rate.

```sql
dataset = panw_ngfw_traffic_raw
| filter incidr(dest_ip, "10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16") = true
| filter action in ("deny", "drop", "reset-both", "reset-client")
| alter t = _time
| bin t span = 1m
| comp count_distinct(dest_ip) as distinct_dests, count() as session_count, values(app) as apps by source_ip, dest_port, t
| filter distinct_dests >= 25
| sort desc distinct_dests
```
