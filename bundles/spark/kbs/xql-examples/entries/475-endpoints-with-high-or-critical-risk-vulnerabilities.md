---
id: XQL-475-5d51e06f
title: Endpoints with High or Critical Risk Vulnerabilities
category: investigation
dataset: va_endpoints
tags:
  - filter
  - va_endpoints
  - source:dataset
  - operator-authored
---

# Endpoints with High or Critical Risk Vulnerabilities

**Dataset**: `va_endpoints`

```sql
dataset = va_endpoints
| filter severity in(ENUM.CRITICAL , ENUM.HIGH )
```

## When to use

Lists all the endpoint vulnerabilities that have a high or critcal risk severity for the XDR agents installed

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
