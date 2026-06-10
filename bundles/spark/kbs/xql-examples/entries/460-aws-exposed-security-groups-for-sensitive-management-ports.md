---
id: XQL-460-50c72dea
title: AWS | Exposed Security Groups for Sensitive Management Ports
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

# AWS | Exposed Security Groups for Sensitive Management Ports

**Dataset**: `amazon_aws_raw`

```sql
dataset = amazon_aws_raw
| filter eventName = "AuthorizeSecurityGroupIngress"
| alter items = json_extract_array(requestParameters,"$.ipPermissions.items")
| arrayexpand items
| alter toPort = items->toPort
| filter toPort in ("3389","22") and requestParameters contains "0.0.0.0/0"
| fields _time , recipientAccountId, eventName , toPort,items, userIdentity ,  sourceIPAddress ,eventID, userAgent , eventSource , requestParameters , responseElements , errorCode, *
```

## When to use

Lists the events where AWS Security Groups where changed to accept inbound traffic to the internet, and filters for managment ports (RDP, SSH)

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
