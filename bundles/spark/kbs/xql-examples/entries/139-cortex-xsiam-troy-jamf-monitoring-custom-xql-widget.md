---
id: XQL-139-7ec29702
title: Cortex XSIAM Troy JAMF Monitoring - Custom XQL Widget
category: investigation
dataset: jamf_pro_raw
tags:
- alter
- comp
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy JAMF Monitoring - Custom XQL Widget

**Dataset**: `jamf_pro_raw`

```sql
dataset = jamf_pro_raw
|alter webhookEvent = json_extract_scalar(webhook, "$.webhookEvent")
| comp count(webhookEvent) as webhook_event_type by webhookEvent
| view graph type = pie xaxis = webhookEvent yaxis = webhook_event_type
```
