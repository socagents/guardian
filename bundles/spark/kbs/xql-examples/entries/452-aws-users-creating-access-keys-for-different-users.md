---
id: XQL-452-7df4d824
title: AWS | Users Creating Access Keys for Different Users
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

# AWS | Users Creating Access Keys for Different Users

**Dataset**: `amazon_aws_raw`

```sql
dataset = amazon_aws_raw
| filter eventName = "CreateAccessKey"
| alter userName = userIdentity -> userName,targetUserName = requestParameters -> userName
| filter userName != targetUserName
| fields _time , recipientAccountId, eventName , userIdentity ,  sourceIPAddress ,eventID, userAgent , eventSource , requestParameters , responseElements , errorCode, *
```

## When to use

Lists the AWS users who created a new ASW secret acces key and corresponding AWS access key ID for another specified user

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
