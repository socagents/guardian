---
id: XQL-262-4d4ba4ee
title: Suspicious authentication events
category: investigation
dataset: cloud_audit_logs
tags:
  - filter
  - alter
  - fields
  - cloud_audit_logs
  - source:dataset
  - operator-authored
---

# Suspicious authentication events

**Dataset**: `cloud_audit_logs`

```sql
// Cloud provider - Azure
// Cloud component - Authentication
dataset = cloud_audit_logs 
| filter cloud_provider = Azure and operation_name_orig = "Authentication" // Query for authentication events
| alter resultStatus = json_extract(raw_log,"$.resultSignature"), requestUri = json_extract(raw_log,"$.properties.requestUri") // Extract the response status and the URI requested
| fields resultStatus,requestUri , caller_ip ,operation_*
```

## When to use

Displays suspicious authentication events.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
