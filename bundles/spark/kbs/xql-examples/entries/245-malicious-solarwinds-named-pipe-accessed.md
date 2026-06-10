---
id: XQL-245-9995033f
title: Malicious solarwinds named pipe accessed
category: investigation
dataset: xdr_data
tags:
  - filter
  - fields
  - dedup
  - xdr_data
  - source:dataset
  - operator-authored
---

# Malicious solarwinds named pipe accessed

**Dataset**: `xdr_data`

```sql
dataset = xdr_data // go over xdr data
| filter action_file_device_type = 1 and action_file_name != null  // look at named pipe events
| filter action_file_name = "583da945-62af-10e8-4902-a8f205c72b2e" //look for the solardrop named pipe
| fields agent_hostname, actor_process_instance_id, actor_process_image_name, action_file_name // select relevant fields
| dedup actor_process_instance_id // dedup on unique processes
```

## When to use

Displays known named pipe access by the solarwinds infected dll

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
