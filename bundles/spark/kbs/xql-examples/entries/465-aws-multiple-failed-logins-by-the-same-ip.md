---
id: XQL-465-d817f284
title: AWS | Multiple Failed Logins by the Same IP
category: investigation
dataset: amazon_aws_raw
tags:
  - filter
  - alter
  - comp
  - amazon_aws_raw
  - source:dataset
  - operator-authored
---

# AWS | Multiple Failed Logins by the Same IP

**Dataset**: `amazon_aws_raw`

```sql
dataset =  amazon_aws_raw
| filter eventName = "ConsoleLogin"
| alter outcome = responseElements -> ConsoleLogin , arn = userIdentity -> arn
| filter outcome = "Failure"
| comp count() as c, values(arn), values(userAgent) by sourceIPAddress, outcome, eventName
| filter c > 10
```

## When to use

Lists the events with multiple failed login attempts by the same IP events for AWS

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
