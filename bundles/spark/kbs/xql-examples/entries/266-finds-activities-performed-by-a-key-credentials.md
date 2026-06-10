---
id: XQL-266-beae8cab
title: Finds activities performed by a key/credentials
category: investigation
dataset: cloud_audit_logs
tags:
  - filter
  - dedup
  - fields
  - sort
  - cloud_audit_logs
  - source:dataset
  - operator-authored
---

# Finds activities performed by a key/credentials

**Dataset**: `cloud_audit_logs`

```sql
// Investigation - find what actions/operations were executed by a specific key/credentials
// Change the <KEY_ID> value
dataset = cloud_audit_logs 
| filter identity_orig contains "<KEY_ID>"
| dedup _time, identity_name , identity_invoked_by_name, caller_ip, caller_ip_geolocation, operation_name_orig, operation_status, resource_type  
| fields _time, identity_name , identity_invoked_by_name, caller_ip, caller_ip_geolocation, operation_name_orig, operation_status, resource_type 
| sort desc _time
```

## When to use

Displays the activities performed by a key/credentials

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
