---
id: XQL-461-db718843
title: AWS | Console Login Failures by the Root Account Users
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

# AWS | Console Login Failures by the Root Account Users

**Dataset**: `amazon_aws_raw`

```sql
dataset = amazon_aws_raw
| filter eventName = "ConsoleLogin" | alter userType = json_extract_scalar(userIdentity , "$.type") , outcome = json_extract_scalar(responseElements ,"$.ConsoleLogin"), MFAUsed = json_extract_scalar(additionalEventData,"$.MFAUsed")
| filter userType = "Root" and outcome = "Failure" and MFAUsed = "No"
| fields _time , recipientAccountId, eventName, userIdentity, userType, outcome , MFAUsed, sourceIPAddress ,eventID, userAgent , eventSource , requestParameters , responseElements , errorCode, *
```

## When to use

Lists the events where the AWS Root Account Users failed to login to the AWS console

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
