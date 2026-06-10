---
id: XQL-330-ff7a26e4
title: Data Volume and EPS by Data Source
category: investigation
dataset: metrics_view
tags:
  - preset
  - comp
  - metrics_view
  - source:preset
  - operator-authored
---

# Data Volume and EPS by Data Source

**Dataset**: `metrics_view`

```sql
preset = metrics_view
| comp sum(total_event_count) as total_event_count_sum by _collector_id, _collector_ip, _collector_name, _collector_type , _final_reporting_device_ip ,_final_reporting_device_name , _broker_device_id ,_vendor , _product
```

## When to use

Details the total event count and events per second (EPS) for each data source, which explains the volume of data ingested by each collector

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
