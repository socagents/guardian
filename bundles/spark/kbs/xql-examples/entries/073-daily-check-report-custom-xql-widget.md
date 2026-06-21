---
id: XQL-073-e5ae180e
title: Daily Check Report - Custom XQL Widget
category: investigation
dataset: panw_ngfw_traffic_raw
tags:
- comp
ecosystem: xsiam
---
# Daily Check Report - Custom XQL Widget

**Dataset**: `panw_ngfw_traffic_raw`

```sql
config timeframe = 30M
| dataset = panw_ngfw_traffic_raw
| comp count(_time ) by _reporting_device_name
```
