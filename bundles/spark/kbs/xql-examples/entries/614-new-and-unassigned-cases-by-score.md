---
id: XQL-614-2d624ec7
title: New and Unassigned Cases by Score
category: investigation
dataset: cases
tags:
  - filter
  - sort
  - cases
  - source:dataset
  - operator-authored
---

# New and Unassigned Cases by Score

**Dataset**: `cases`

```sql
dataset = cases
| filter xdm.case.assigned_to=null and xdm.case.status_progress="New"
| sort desc xdm.case.score
```

## When to use

Lists new and unresolved cases by their score

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-05-26.
