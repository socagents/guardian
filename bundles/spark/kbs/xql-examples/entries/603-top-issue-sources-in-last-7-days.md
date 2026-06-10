---
id: XQL-603-bcb6f286
title: Top Issue Sources in Last 7 Days
category: investigation
dataset: issues
tags:
  - config
  - comp
  - sort
  - issues
  - source:dataset
  - operator-authored
---

# Top Issue Sources in Last 7 Days

**Dataset**: `issues`

```sql
config timeframe = 7D
| dataset = issues
| comp count() as IssueSourceCount by xdm.issue.detection.method
| sort desc IssueSourceCount
```

## When to use

Counts the number of issues by Issue source in the last 7 days and displays them in descending order based on the count

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-05-26.
