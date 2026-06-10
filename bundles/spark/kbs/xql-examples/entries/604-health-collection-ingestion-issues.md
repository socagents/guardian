---
id: XQL-604-929212e0
title: Health Collection/Ingestion Issues
category: general
dataset: issues
tags:
  - config
  - filter
  - alter
  - fields
  - issues
  - source:dataset
  - operator-authored
---

# Health Collection/Ingestion Issues

**Dataset**: `issues`

```sql
config timeframe = 30D
| dataset = issues
| filter xdm.issue.domain = "HEALTH"
| alter collector_name = regextract(xdm.issue.name  , "instance\s(.*)\sof\sa\s")
| alter collector_type = coalesce(arrayindex( regextract(xdm.issue.name  , "via\sa\s(.*)\scollector"),0),arrayindex( regextract(xdm.issue.name , "\sof\sa\s(\S+)"),0))
| fields _time, xdm.issue.id  , xdm.issue.detection.method , xdm.issue.name  , xdm.issue.description  , collector_name  , collector_type,*
```

## When to use

Lists the health and ingestion issues in the system to help monitor the status of data collectors and troubleshoot potential problems

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-05-26.
