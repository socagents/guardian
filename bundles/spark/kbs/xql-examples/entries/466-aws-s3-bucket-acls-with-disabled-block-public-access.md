---
id: XQL-466-ed64c0f3
title: AWS | S3 Bucket ACLs with Disabled Block Public Access
category: investigation
dataset: amazon_aws_raw
tags:
  - filter
  - fields
  - amazon_aws_raw
  - source:dataset
  - operator-authored
---

# AWS | S3 Bucket ACLs with Disabled Block Public Access

**Dataset**: `amazon_aws_raw`

```sql
dataset =  amazon_aws_raw
| filter eventName = "BucketBlockPublicAccessDisabled"
| fields _time , recipientAccountId, eventName , userIdentity ,  sourceIPAddress ,eventID, userAgent , eventSource , requestParameters , responseElements , errorCode, *
```

## When to use

Lists the events where the AWS S3 Block Public Access was disabled for the Amazon S3 bucket, which can indicate a denial of service attack

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
