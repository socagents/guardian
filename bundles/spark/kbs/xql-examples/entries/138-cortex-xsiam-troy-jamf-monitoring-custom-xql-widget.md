---
id: XQL-138-7ec29702
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
| comp count(device_name) as model_count by model_display
| sort desc model_display
| view graph type = pie xaxis = model_display yaxis = model_count
```
