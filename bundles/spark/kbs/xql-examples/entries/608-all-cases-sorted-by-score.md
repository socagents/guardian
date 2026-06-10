---
id: XQL-608-c93c1664
title: All Cases Sorted by Score
category: investigation
dataset: cases
tags:
  - fields
  - sort
  - cases
  - source:dataset
  - operator-authored
---

# All Cases Sorted by Score

**Dataset**: `cases`

```sql
dataset = cases
| fields xdm.case.id , xdm.case.platform_severity, xdm.case.status_progress , xdm.case.score, xdm.case.description ,_insert_time, *
| sort desc xdm.case.score
```

## When to use

Lists cases sorted by the highest score

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-05-26.
