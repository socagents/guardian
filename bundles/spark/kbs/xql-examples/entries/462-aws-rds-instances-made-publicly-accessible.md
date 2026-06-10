---
id: XQL-462-b9258ca7
title: AWS | RDS Instances Made Publicly Accessible
category: investigation
dataset: amazon_aws_raw
tags:
  - filter
  - alter
  - fields
  - amazon_aws_raw
  - source:dataset
  - operator-authored
---

# AWS | RDS Instances Made Publicly Accessible

**Dataset**: `amazon_aws_raw`

```sql
dataset = amazon_aws_raw
| filter eventName = "ModifyDBInstance"
| alter publiclyAccessible = json_extract_scalar(requestParameters, "$.publiclyAccessible")
| filter publiclyAccessible = "true"
| fields _time , recipientAccountId, eventName , userIdentity ,  sourceIPAddress ,eventID, userAgent , eventSource , requestParameters , responseElements , errorCode, *
```

## When to use

Lists the events where the changes in RDS made them publicly accessible from the internet

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
