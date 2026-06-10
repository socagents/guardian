---
id: XQL-477-ebf39f60
title: Vulnerabilities Relating to Android and Linux Operating Systems
category: investigation
dataset: va_cves
tags:
  - filter
  - fields
  - va_cves
  - source:dataset
  - operator-authored
---

# Vulnerabilities Relating to Android and Linux Operating Systems

**Dataset**: `va_cves`

```sql
dataset = va_cves
| filter os_type in (ENUM.LINUX, ENUM.ANDROID) and (type = ENUM.APPLICATION_AND_OS)
| fields affected_hosts, affected_hosts_count, affected_products, name, description, *
```

## When to use

Lists the vulnerabilities that were found on an Android or Linux operating system for the vulnerability type called "APPLICATION_AND_OS"

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
