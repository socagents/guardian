---
id: XQL-261-549a1437
title: Logging component modification
category: investigation
dataset: cloud_audit_logs
tags:
  - filter
  - cloud_audit_logs
  - source:dataset
  - operator-authored
---

# Logging component modification

**Dataset**: `cloud_audit_logs`

```sql
// Cloud provider - AWS
// Cloud component - Logging
dataset = cloud_audit_logs 
| filter operation_name_orig in ("StopLogging","UpdateTrail","DeleteTrail") // Query for suspicious activities in the logging component
```

## When to use

Displays suspicious activities performed in the Logging component.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
