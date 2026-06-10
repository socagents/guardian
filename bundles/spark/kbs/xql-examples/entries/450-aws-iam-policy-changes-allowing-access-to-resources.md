---
id: XQL-450-9692ea37
title: AWS | IAM Policy Changes Allowing Access to Resources
category: investigation
dataset: amazon_aws_raw
tags:
  - filter
  - alter
  - arrayexpand
  - fields
  - amazon_aws_raw
  - source:dataset
  - operator-authored
---

# AWS | IAM Policy Changes Allowing Access to Resources

**Dataset**: `amazon_aws_raw`

```sql
dataset = amazon_aws_raw
| filter eventName = "CreatePolicyVersion"
| alter policyDocument = json_extract_scalar(requestParameters, "$.policyDocument")
| filter policyDocument != null
| alter statement = json_extract_array(policyDocument , "$.Statement")
| arrayexpand statement
| alter Effect = statement -> Effect , Resource = json_extract_array(statement , "$.Resource")
| filter Effect = "Allow"
| fields _time , recipientAccountId, eventName , userIdentity , statement ,  sourceIPAddress ,  eventID   , userAgent , eventSource , requestParameters , responseElements , errorCode, statement , *
```

## When to use

Details the events with a recent policy created that allows accessing any resource

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
