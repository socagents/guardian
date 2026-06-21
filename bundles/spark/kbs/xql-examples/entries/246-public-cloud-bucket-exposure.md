---
id: XQL-IR-246-public-cloud-bucket-exposure
title: Cloud storage bucket made publicly accessible (T1530)
category: investigation
dataset: cloud_audit_logs
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1530]
---

# Cloud storage bucket made publicly accessible (T1530)

**Dataset**: `cloud_audit_logs`

Flags ACL/policy changes that expose object storage to the public - PutBucketAcl, PutBucketPolicy, or an IAM binding granting `allUsers`/`AllAuthenticatedUsers`. The request body is searched for the public principal grant. Each hit is a potential data-at-rest exposure, so triage every result; aggregate only to group repeat offenders per bucket.

```sql
dataset = cloud_audit_logs
| filter operation_name in ("PutBucketAcl", "PutBucketPolicy", "storage.setIamPermissions", "PutObjectAcl", "setIamPolicy")
| alter req = to_json_string(request_parameters)
| filter req contains "allUsers" or req contains "AllUsers" or req contains "AllAuthenticatedUsers" or req contains "public-read" or req contains "public-read-write"
| alter actor = coalesce(identity_name, caller_ip)
| comp count() as change_count, values(operation_name) as operations, values(actor) as actors, min(_time) as first_change by target_resource, cloud_provider
| sort desc change_count
```
