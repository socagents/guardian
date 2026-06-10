---
id: XQL-332-241795ac
title: Data Model Rules Errors
category: investigation
dataset: parsing_rules_errors
tags:
  - filter
  - parsing_rules_errors
  - source:dataset
  - operator-authored
---

# Data Model Rules Errors

**Dataset**: `parsing_rules_errors`

```sql
dataset = parsing_rules_errors
| filter rule_type contains "Data Model Rule"
```

## When to use

Lists the errors related to the Cortex Data Model (XDM) rules to help explain where data can be failing to align with the expected schema and require further analysis

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
