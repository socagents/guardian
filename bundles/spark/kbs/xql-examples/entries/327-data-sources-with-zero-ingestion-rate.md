---
id: XQL-327-2dbd889d
title: Data Sources with Zero Ingestion Rate
category: general
dataset: metrics_view
tags:
  - preset
  - comp
  - alter
  - filter
  - dedup
  - fields
  - metrics_view
  - source:preset
  - operator-authored
---

# Data Sources with Zero Ingestion Rate

**Dataset**: `metrics_view`

```sql
preset = metrics_view
| comp sum(total_event_count) as total_event_count_sum by _collector_id, _collector_ip, _collector_name, _collector_type, _collector_internal_ip_address, _final_reporting_device_ip, _final_reporting_device_name, _reporting_device_name, _collector_hostname, _broker_device_id, _device_id, _log_type, _vendor, _product
| alter ven_product = concat(_vendor, " (", _product , ") ")
| filter total_event_count_sum = 0
| dedup ven_product
| fields ven_product
```

## When to use

Lists the data sources that are not successfully sending data with an ingestion rate of zero, which helps identify misconfigurations or connectivity issues

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
