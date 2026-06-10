---
id: XQL-309-507f995a
title: Data Sources Not parsed or Onboarded Properly
category: investigation
dataset: unknown_unknown_raw
tags:
  - fields
  - unknown_unknown_raw
  - source:dataset
  - operator-authored
---

# Data Sources Not parsed or Onboarded Properly

**Dataset**: `unknown_unknown_raw`

```sql
dataset = unknown_unknown_raw
| fields _time,_reporting_device_ip, _final_reporting_device_ip ,  _collector_name , _collector_type ,_raw_log ,_broker_device_name , _broker_ip_address , _broker_hostname,*
```

## When to use

Lists the data sources that are not paired with the out-of-the-box content onboarding and parsing

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
