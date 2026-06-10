---
id: XQL-609-e7f9edc7
title: Unresolved Cases by Description
category: investigation
dataset: cases
tags:
  - filter
  - fields
  - cases
  - source:dataset
  - operator-authored
---

# Unresolved Cases by Description

**Dataset**: `cases`

```sql
dataset = cases
| filter xdm.case.description in ($description) and xdm.case.status_progress not contains "RESOLVED"
| fields xdm.case.id , xdm.case.platform_severity, xdm.case.status_progress , xdm.case.description  , _insert_time, *
```

## When to use

Filters for unresolved cases according to the description

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-05-26.
