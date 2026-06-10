---
id: XQL-307-fbcff66d
title: Execution Statuses for Correlation Rules
category: investigation
dataset: correlations_auditing
tags:
  - comp
  - fields
  - correlations_auditing
  - source:dataset
  - operator-authored
---

# Execution Statuses for Correlation Rules

**Dataset**: `correlations_auditing`

```sql
dataset = correlations_auditing
| comp count(), values(name) as name, values(rule_id) as rule_id  by status
| fields status , *
```

## When to use

Counts the execution statuses for correlation rules, which helps analysts track the status distribution

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
