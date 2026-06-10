---
id: XQL-607-416880e3
title: Latest Unresolved Critical and High Severity Cases by Score


category: investigation
dataset: cases
tags:
  - filter
  - fields
  - sort
  - cases
  - source:dataset
  - operator-authored
---

# Latest Unresolved Critical and High Severity Cases by Score



**Dataset**: `cases`

```sql
dataset = cases
| filter xdm.case.platform_severity in("CRITICAL", "HIGH") and xdm.case.status_progress not contains "RESOLVED"
| fields xdm.case.id , xdm.case.platform_severity, xdm.case.status_progress , xdm.case.description  , _insert_time, xdm.case.score, xdm.case.assigned_to , *
| sort desc xdm.case.score
```

## When to use

Lists the most recent high severity cases with the highest score

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-05-26.
