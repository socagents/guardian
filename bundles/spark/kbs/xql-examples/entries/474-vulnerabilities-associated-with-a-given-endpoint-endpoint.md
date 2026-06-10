---
id: XQL-474-bee9ba97
title: Vulnerabilities Associated with a Given Endpoint ($endpoint)
category: investigation
dataset: va_endpoints
tags:
  - filter
  - va_endpoints
  - source:dataset
  - operator-authored
---

# Vulnerabilities Associated with a Given Endpoint ($endpoint)

**Dataset**: `va_endpoints`

```sql
dataset = va_endpoints
| filter endpoint_name contains  $endpoint
```

## When to use

Lists all the related vulnerabilities associated to a specific endpoint for the XDR agents installed

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
