---
id: XQL-476-5ea24813
title: Vulnerabilities Affecting More Than One Endpoint
category: investigation
dataset: va_cves
tags:
  - filter
  - fields
  - va_cves
  - source:dataset
  - operator-authored
---

# Vulnerabilities Affecting More Than One Endpoint

**Dataset**: `va_cves`

```sql
dataset = va_cves
| filter array_length(affected_hosts ) > 1
| fields affected_hosts, affected_hosts_count, affected_products, name, description, *
```

## When to use

Lists the vulnerabilities that affect multiple endpoints for the XDR agents installed

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
