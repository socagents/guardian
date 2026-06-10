---
id: XQL-258-b6afc963
title: Cloud storage activities
category: investigation
dataset: cloud_audit_logs
tags:
  - filter
  - cloud_audit_logs
  - source:dataset
  - operator-authored
---

# Cloud storage activities

**Dataset**: `cloud_audit_logs`

```sql
// Cloud provider - AWS
// Cloud component - Storage
config case_sensitive = false 
| dataset = cloud_audit_logs // Query the normalized cloud audit logs table
| filter resource_type = CloudStorage and operation_name_orig in ("PutBucketAcl","PutBucketPublicAccessBlock","CompleteMultipartUpload","CreateEnvironment","PutObjectAcl","PutObject","PutBucketVersioning","CreateMultipartUpload","CopyObject","PutBucketLogging","DeleteBucketPolicy","CreateBucket","DeleteBucket","UploadPart","PutBucketEncryption","DeleteObjects") // Query for suspicious storage actions
```

## When to use

Displays storage activities that can indicate suspicious behaviours.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
