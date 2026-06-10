---
id: XQL-606-12a55a68
title: Top Unresolved High Severity Cases
category: investigation
dataset: cases
tags:
  - filter
  - fields
  - cases
  - source:dataset
  - operator-authored
---

# Top Unresolved High Severity Cases

**Dataset**: `cases`

```sql
dataset = cases
| filter xdm.case.platform_severity in("CRITICAL", "HIGH") and xdm.case.status_progress not contains "RESOLVED"
| fields xdm.case.id , xdm.case.platform_severity, xdm.case.status_progress , xdm.case.description  , _insert_time, xdm.case.score, xdm.case.assigned_to , *
```

## When to use

Filters for high/critical cases that requires immediate action

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-05-26.
