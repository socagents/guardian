---
id: XQL-464-6e57cd10
title: AWS | S3 Bucket ACLs Settings Changed to Publicly Exposed or Internet Facing
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

# AWS | S3 Bucket ACLs Settings Changed to Publicly Exposed or Internet Facing

**Dataset**: `amazon_aws_raw`

```sql
dataset = amazon_aws_raw
| filter eventName = "PutBucketPublicAccessBlock"
| alter PublicAccessBlockConfiguration = json_extract(requestParameters , "$.PublicAccessBlockConfiguration")
| filter PublicAccessBlockConfiguration contains "true"
| fields _time , recipientAccountId, eventName , userIdentity ,  sourceIPAddress ,eventID, userAgent , eventSource , requestParameters , responseElements , errorCode, *
```

## When to use

Lists the events where changes to the Amazon S3 bucket ACL caused them to be publicly accessible

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
