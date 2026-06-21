---
id: XQL-037-e4416e91
title: Reg Servers Critical
category: general
dataset: panw_ngfw_threat_raw
tags:
- filter
ecosystem: xsiam
---
# Reg Servers Critical

**Dataset**: `panw_ngfw_threat_raw`

```sql
config case_sensitive = false
| dataset = panw_ngfw_threat_raw
| filter ((dest_ip = "66.77.37.5") or (source_ip = "66.77.37.5") or (dest_ip = "10.220.153.11") or (source_ip = "10.220.153.11")) and (severity != "informational") and (severity != "low" and rule_matched = "Registration Web Server")
```
