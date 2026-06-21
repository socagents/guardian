---
id: XQL-IR-244-cloud-new-access-key-role
title: New cloud access key or role assignment created (T1098.001)
category: investigation
dataset: cloud_audit_logs
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1098.001]
---

# New cloud access key or role assignment created (T1098.001)

**Dataset**: `cloud_audit_logs`

Surfaces additional-credential persistence in the cloud control plane: CreateAccessKey, CreateLoginProfile, or IAM/role binding changes. Aggregating by actor highlights identities minting multiple keys in a short span. Tune the event-name list to your CSP vocabulary (AWS / GCP / Azure) and add a `timestamp_diff` recency filter for live triage.

```sql
dataset = cloud_audit_logs
| filter operation_name in ("CreateAccessKey", "CreateLoginProfile", "AddUserToGroup", "AttachUserPolicy", "CreateServiceAccountKey", "setIamPolicy")
| alter actor = coalesce(identity_name, caller_ip)
| comp count() as action_count, count_distinct(operation_name) as distinct_ops, values(operation_name) as operations, values(target_resource) as targets, min(_time) as first_action by actor, cloud_provider
| filter action_count >= 2
| sort desc action_count
```
