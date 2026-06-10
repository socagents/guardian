---
id: XQL-300-42fb5e3c
title: Correlation Rules that Failed to Run
category: investigation
dataset: correlations_auditing
tags:
  - filter
  - fields
  - sort
  - correlations_auditing
  - source:dataset
  - operator-authored
---

# Correlation Rules that Failed to Run

**Dataset**: `correlations_auditing`

```sql
dataset = correlations_auditing
| filter status ="Error"
| fields _time , name , rule_id ,status , failure_reason ,  retry_attempts , query_start_time , query_end_time,*
| sort desc _time
```

## When to use

Lists the correlation rules that failed to run, and provides the failure reason, retry attempts, and timestamps of the query

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
