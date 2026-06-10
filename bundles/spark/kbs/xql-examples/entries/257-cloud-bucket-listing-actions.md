---
id: XQL-257-ae4502d1
title: Cloud bucket listing actions
category: investigation
dataset: cloud_audit_logs
tags:
  - filter
  - comp
  - cloud_audit_logs
  - source:dataset
  - operator-authored
---

# Cloud bucket listing actions

**Dataset**: `cloud_audit_logs`

```sql
// Cloud provider - GCP
// Cloud component - Storage
config case_sensitive = false 
| dataset = cloud_audit_logs // Query the normalized cloud audit logs table
| filter resource_type = CloudStorage and operation_name_orig in ("storage.buckets.list","storage.buckets.listChannels") // filter the events for bucket listing
| comp count(_time) as BucketListing by identity_name // count the number of listing performed by a user
```

## When to use

Displays the cloud storage bucket activity sorted by the number of events performed by a user.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
