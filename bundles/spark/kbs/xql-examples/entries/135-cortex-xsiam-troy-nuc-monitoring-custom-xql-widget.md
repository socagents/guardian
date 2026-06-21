---
id: XQL-135-4ab26f76
title: Cortex XSIAM Troy NUC Monitoring - Custom XQL Widget
category: investigation
dataset: alerts
tags:
- comp
- filter
- limit
- sort
ecosystem: xsiam
---
# Cortex XSIAM Troy NUC Monitoring - Custom XQL Widget

**Dataset**: `alerts`

```sql
dataset = alerts
| filter host_name contains "SOC"
| comp count(alert_id) as alert_count by host_name
| sort desc alert_count
| limit 20
```
