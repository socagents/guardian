---
id: XQL-269-aacbbb12
title: An Identity accessing from multiple geo locations
category: investigation
dataset: cloud_audit_logs
tags:
  - filter
  - fields
  - comp
  - sort
  - cloud_audit_logs
  - source:dataset
  - operator-authored
---

# An Identity accessing from multiple geo locations

**Dataset**: `cloud_audit_logs`

```sql
// Identity seen from multiple geo locations
dataset = cloud_audit_logs 
| filter cloud_provider = "AWS" // filter cloud provider
| filter identity_type != User 
| filter operation_status = "SUCCESS" // filter only success logs
| fields  caller_ip, caller_ip_geolocation , identity_name, identity_type, identity_invoked_by_name 
| comp count_distinct(caller_ip_geolocation) as location_count by identity_name, identity_type, identity_invoked_by_name
| filter location_count > 1 
| fields identity_name, identity_type, identity_invoked_by_name, location_count
| sort desc location_count
```

## When to use

Displays identities accessing from multiple geo locations

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
