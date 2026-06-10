---
id: XQL-331-a4065f44
title: Parsing Rules Errors
category: investigation
dataset: parsing_rules_errors
tags:
  - filter
  - parsing_rules_errors
  - source:dataset
  - operator-authored
---

# Parsing Rules Errors

**Dataset**: `parsing_rules_errors`

```sql
dataset = parsing_rules_errors
| filter rule_type contains "Parsing"
```

## When to use

Lists the errors related to parsing rules in the system to help troubleshoot issues with data parsing and ensure data is correctly ingested and formatted

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
