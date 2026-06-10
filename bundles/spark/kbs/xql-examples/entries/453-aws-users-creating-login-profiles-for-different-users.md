---
id: XQL-453-6351dde0
title: AWS | Users Creating Login Profiles for Different Users
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

# AWS | Users Creating Login Profiles for Different Users

**Dataset**: `amazon_aws_raw`

```sql
dataset = amazon_aws_raw
| filter eventName = "CreateLoginProfile"
| alter userIdentity_arn = userIdentity -> arn,targetUserName = requestParameters -> userName
| filter userIdentity_arn not contains targetUserName
| fields userIdentity_arn, targetUserName , requestID, requestParameters, recipientAccountId, responseElements , *
```

## When to use

Lists the events of users who created login passwords for another user

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
