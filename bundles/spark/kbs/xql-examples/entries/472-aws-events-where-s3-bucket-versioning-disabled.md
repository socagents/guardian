---
id: XQL-472-06e34eb5
title: AWS | Events where S3 Bucket Versioning Disabled
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

# AWS | Events where S3 Bucket Versioning Disabled

**Dataset**: `amazon_aws_raw`

```sql
dataset = amazon_aws_raw
| filter eventName contains "PutBucketVersioning"
| alter Status = json_extract_scalar(requestParameters, "$.VersioningConfiguration.Status")
| filter Status = "Suspended"
| fields _time , recipientAccountId, eventName, userIdentity,  sourceIPAddress ,eventID, userAgent , eventSource , requestParameters ,Status, responseElements , errorCode, *
```

## When to use

Lists the events where the settings in the S3 buckets were changed so that the bucket object versioning was disabled

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
