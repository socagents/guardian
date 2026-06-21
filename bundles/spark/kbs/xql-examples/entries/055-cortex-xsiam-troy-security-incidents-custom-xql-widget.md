---
id: XQL-055-e758f3ac
title: Cortex XSIAM Troy Security Incidents - Custom XQL Widget
category: investigation
dataset: alerts
tags:
- comp
- fields
- filter
- sort
ecosystem: xsiam
---
# Cortex XSIAM Troy Security Incidents - Custom XQL Widget

**Dataset**: `alerts`

```sql
dataset = alerts
| fields alert_name, app_id, app_subcategory, category, fw_name, source_zone_name, destination_zone_name
//| fields alert_name, source_zone_name
| filter source_zone_name != null and source_zone_name != "internet"
| comp count(alert_name) as alert_count, values(arrayindex(source_zone_name,0)) as room, values(category) as category by alert_name
| sort desc alert_count
```
