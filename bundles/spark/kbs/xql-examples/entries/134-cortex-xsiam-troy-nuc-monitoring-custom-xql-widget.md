---
id: XQL-134-4ab26f76
title: Cortex XSIAM Troy NUC Monitoring - Custom XQL Widget
category: investigation
dataset: endpoints
tags:
- comp
- filter
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy NUC Monitoring - Custom XQL Widget

**Dataset**: `endpoints`

```sql
dataset = endpoints
|filter endpoint_name contains "SOC"
| filter endpoint_status in (CONNECTED, CONNECTION_LOST)
| comp count(endpoint_id) as total by endpoint_status
| view graph type = pie xaxis = endpoint_status yaxis = total
```
