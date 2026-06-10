---
id: XQL-481-c4f1c903
title: Critical Operating System Vulnerabilities
category: investigation
dataset: va_cves
tags:
  - filter
  - fields
  - va_cves
  - source:dataset
  - operator-authored
---

# Critical Operating System Vulnerabilities

**Dataset**: `va_cves`

```sql
dataset = va_cves
| filter type = ENUM.OPERATING_SYSTEM and severity = ENUM.CRITICAL
| fields name, cve_id , affected_products , affected_hosts , severity , description, *
```

## When to use

Lists the critical Operating System vulnerabilities for the XDR agents installed

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
