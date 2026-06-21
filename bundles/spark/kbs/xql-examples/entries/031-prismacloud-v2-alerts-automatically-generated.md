---
id: XQL-031-42c6466e
title: PrismaCloud v2 Alerts (automatically generated)
category: alert-mapping
dataset: prismacloud_v2_generic_alert_raw
tags:
- alter
- filter
ecosystem: xsiam
---
# PrismaCloud v2 Alerts (automatically generated)

**Dataset**: `prismacloud_v2_generic_alert_raw`

```sql
dataset = prismacloud_v2_generic_alert_raw
| filter _alert_data != null
| alter alert_severity = json_extract_scalar(_alert_data, "$.severity")
| alter alert_category = json_extract_scalar(_alert_data, "$.alert_category")
| alter alert_name = json_extract_scalar(_alert_data, "$.alert_name")
| alter alert_description = json_extract_scalar(_alert_data, "$.alert_description")
```
