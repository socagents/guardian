---
id: XQL-469-733321e6
title: AWS | EC2 Packet Capturing created
category: investigation
dataset: amazon_aws_raw
tags:
  - filter
  - fields
  - amazon_aws_raw
  - source:dataset
  - operator-authored
---

# AWS | EC2 Packet Capturing created

**Dataset**: `amazon_aws_raw`

```sql
dataset = amazon_aws_raw
| filter eventName contains "CreateTrafficMirror"
| fields _time , recipientAccountId, eventName , userIdentity ,  sourceIPAddress ,eventID, userAgent , eventSource , requestParameters , responseElements , errorCode, *
```

## When to use

Lists the events where the AWS EC2 Network Packet Capture setting was added

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
