---
id: XQL-240-0bbe9706
title: Solarwinds installed hosts
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

# Solarwinds installed hosts

**Dataset**: `xdr_data`

```sql
dataset = xdr_data // go over XDR data
|filter arraystring(action_app_id_transitions, ",") contains "solarwinds"  or  dst_action_external_hostname = "api.solarwinds.com" or action_external_hostname = "api.solarwinds.com" or lowercase(action_process_signature_vendor) contains "solarwinds"  // find cases where a known solarwinds domain, AppId or process signature is being used
| fields agent_hostname, action_local_ip|dedup agent_hostname, action_local_ip // show only hosts names and ips and dedup
```

## When to use

Displays hosts that have solarwinds software installed on them

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
