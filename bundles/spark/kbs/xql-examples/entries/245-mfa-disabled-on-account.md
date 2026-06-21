---
id: XQL-IR-245-mfa-disabled-on-account
title: MFA disabled or deactivated on an account (T1556.006)
category: investigation
dataset: cloud_audit_logs
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1556.006]
---

# MFA disabled or deactivated on an account (T1556.006)

**Dataset**: `cloud_audit_logs`

Detects defense-evasion against multi-factor auth: deactivating a virtual MFA device, deleting an MFA method, or flipping strong-auth off. Pairs the actor with the affected target so analysts can spot self-service downgrades vs. admin abuse. Tune the operation list to your identity provider's audit event names.

```sql
dataset = cloud_audit_logs
| filter operation_name in ("DeactivateMFADevice", "DeleteVirtualMFADevice", "Disable Strong Authentication", "DeleteMfaAuthenticationMethod", "UpdateAuthenticationMethods")
| alter actor = coalesce(identity_name, caller_ip)
| alter target_account = coalesce(target_resource, actor)
| alter self_service = if(actor = target_account, "true", "false")
| comp count() as disable_count, values(operation_name) as operations, values(self_service) as self_service by actor, target_account, cloud_provider
| sort desc disable_count
```
