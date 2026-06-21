---
id: XQL-IR-226-password-spray-failed-logon-spike
title: Brute-force / password-spray failed-logon spike by source (T1110)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, bin, comp, sort]
attack: [T1110]
---

# Brute-force / password-spray failed-logon spike by source (T1110)

**Dataset**: `xdr_data`

Buckets failed authentications into 1-hour windows per source host and counts the distinct usernames hit — a wide spread of accounts from one source is the signature of password spraying. Tune `distinct_users` and `attempts` thresholds to your baseline; lower them for high-value tier-0 assets.

```sql
dataset = xdr_data
| filter event_type = ENUM.STORY and action_evtlog_event_id = 4625
| alter src = action_remote_ip, target_user = lowercase(action_username)
| bin _time span = 1h
| comp count() as attempts, count_distinct(target_user) as distinct_users, values(target_user) as users_tried by src, _time
| filter distinct_users >= 5 or attempts >= 25
| sort desc distinct_users, desc attempts
```
