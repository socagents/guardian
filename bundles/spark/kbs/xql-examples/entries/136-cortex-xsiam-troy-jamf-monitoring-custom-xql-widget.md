---
id: XQL-136-7ec29702
title: Cortex XSIAM Troy JAMF Monitoring - Custom XQL Widget
category: investigation
dataset: jamf_pro_raw
tags:
- bin
- comp
- filter
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy JAMF Monitoring - Custom XQL Widget

**Dataset**: `jamf_pro_raw`

```sql
dataset = jamf_pro_raw
| filter device_udid != null
| bin _time span = 10m
| comp count(device_udid) as number_devices by _time
| view graph type = line xaxis = _time yaxis = number_devices
```
