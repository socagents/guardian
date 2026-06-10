---
id: XQL-454-5220d408
title: AWS | Attempts to Retrieve Admin Password for Running Windows EC2 Instance
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

# AWS | Attempts to Retrieve Admin Password for Running Windows EC2 Instance

**Dataset**: `amazon_aws_raw`

```sql
dataset = amazon_aws_raw
| filter eventName="GetPasswordData" and eventSource = "ec2.amazonaws.com"
| alter instanceId = requestParameters -> instanceId, principalId = userIdentity -> principalId
| fields _time , recipientAccountId, eventName , userIdentity ,  sourceIPAddress ,eventID, userAgent , eventSource , requestParameters , responseElements , errorCode, *
```

## When to use

Lists the events of Credential Access attempts to a EC2 windows instance

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
