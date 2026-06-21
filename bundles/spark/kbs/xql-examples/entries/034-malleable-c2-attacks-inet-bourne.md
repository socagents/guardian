---
id: XQL-034-4440ea09
title: Malleable C2 Attacks Inet Bourne
category: general
dataset: panw_ngfw_threat_raw
tags:
- filter
ecosystem: xsiam
---
# Malleable C2 Attacks Inet Bourne

**Dataset**: `panw_ngfw_threat_raw`

```sql
dataset = panw_ngfw_threat_raw
| filter (threat_id = 9950 or threat_id = 89951 or threat_id = 89952 or threat_id = 89953 or threat_id = 89954 or threat_id = 89955 or threat_id = 89956 or threat_id = 89957 or threat_id = 89958 or threat_id = 99951 or threat_id = 99950 )  and ( from_zone  = "Internet" or to_zone  = "Internet")
```
