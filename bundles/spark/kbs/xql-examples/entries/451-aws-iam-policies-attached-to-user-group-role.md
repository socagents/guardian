---
id: XQL-451-7c9dabc5
title: AWS | IAM Policies Attached to User/Group/Role
category: investigation
dataset: amazon_aws_raw
tags:
  - filter
  - fields
  - amazon_aws_raw
  - source:dataset
  - operator-authored
---

# AWS | IAM Policies Attached to User/Group/Role

**Dataset**: `amazon_aws_raw`

```sql
dataset = amazon_aws_raw
| filter eventName ~= "Attach\w+Policy$"
| fields _time , recipientAccountId, eventName , userIdentity ,  sourceIPAddress ,  eventID   , userAgent , eventSource , requestParameters , responseElements , errorCode, *
```

## When to use

Lists the IAM Policies that were attached to a user/group/role

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
