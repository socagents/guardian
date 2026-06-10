---
id: XQL-371-1afcc7f6
title: CVEs Related to a Specific Host
category: investigation
dataset: va_cves
tags:
  - arrayexpand
  - filter
  - sort
  - va_cves
  - source:dataset
  - operator-authored
---

# CVEs Related to a Specific Host

**Dataset**: `va_cves`

```sql
dataset = va_cves |
arrayexpand affected_hosts |
filter affected_hosts contains $host |
sort desc severity_score
```

## When to use

Lists CVEs related to a specific host

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
