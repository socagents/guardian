---
id: XQL-061-46e8257b
title: Cortex XSIAM Troy NGFW Threat Hunting - Custom XQL Widget
category: investigation
dataset: panw_ngfw_traffic_raw
tags:
- comp
- filter
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy NGFW Threat Hunting - Custom XQL Widget

**Dataset**: `panw_ngfw_traffic_raw`

```sql
dataset = panw_ngfw_traffic_raw | filter app contains "unknown" | comp count(dest_ip) as dest_count by dest_ip
| view graph type = column subtype = grouped header = "Unknown App Traffic by IP" xaxis = dest_ip yaxis = dest_count
```
