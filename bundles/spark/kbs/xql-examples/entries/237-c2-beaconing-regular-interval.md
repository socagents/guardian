---
id: XQL-IR-237-c2-beaconing-regular-interval
title: C2 beaconing detected by low-jitter connection interval (T1071.001)
category: threat-hunting
dataset: network_story
ecosystem: xsiam
tags: [filter, alter, windowcomp, comp, sort]
attack: [T1071.001]
---

# C2 beaconing detected by low-jitter connection interval (T1071.001)

**Dataset**: `network_story`

Computes the time gap between consecutive outbound sessions per source/destination pair, then surfaces pairs whose interval is tight and highly regular (low standard deviation) - the signature of automated C2 callbacks. Tune by raising `beacon_count` (more samples = higher confidence) and lowering the `interval_jitter` threshold to demand stricter regularity.

```sql
dataset = network_story
| filter action_external_hostname != null and incidr(dst_ip, "10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16") = false
| alter ep = to_epoch(_time)
| windowcomp lag(ep) by src_ip, dst_ip sort asc ep as prev_ep
| filter prev_ep != null
| alter gap_seconds = subtract(ep, prev_ep)
| comp count() as beacon_count, avg(gap_seconds) as interval_avg, stddev_sample(gap_seconds) as interval_jitter, values(action_external_hostname) as hostnames by src_ip, dst_ip
| filter beacon_count >= 12 and interval_avg > 30 and interval_jitter < 15
| sort asc interval_jitter
```
