---
id: XQL-137-7ec29702
title: Cortex XSIAM Troy JAMF Monitoring - Custom XQL Widget
category: investigation
dataset: jamf_pro_raw
tags:
- comp
- sort
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy JAMF Monitoring - Custom XQL Widget

**Dataset**: `jamf_pro_raw`

```sql
dataset = jamf_pro_raw
| comp count(device_name) as device_count by device_model
| sort desc device_model
| view graph type = pie xaxis = device_model yaxis = device_count
```
