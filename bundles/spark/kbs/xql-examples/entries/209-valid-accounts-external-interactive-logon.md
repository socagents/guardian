---
id: XQL-IR-209-valid-accounts-external-interactive-logon
title: External interactive logon from outside corporate ranges (T1078)
category: investigation
dataset: cloud_audit_logs
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1078, T1078.004]
---

# External interactive logon from outside corporate ranges (T1078)

**Dataset**: `cloud_audit_logs`

Scopes a valid-accounts compromise: successful interactive sign-ins whose source IP falls outside your corporate and VPN CIDRs. The `comp` rollup per user shows how many distinct foreign IPs touched the account -- a spread implies credential reuse. Replace the CIDR list with your egress ranges.

```sql
dataset = cloud_audit_logs
| filter operation_name contains "Login" or operation_name contains "SignIn" or operation_name contains "ConsoleLogin"
| filter operation_result = "success"
| alter src_ip = coalesce(caller_ip, source_ip)
| filter src_ip != null and not incidr(src_ip, "10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16")
| comp count_distinct(src_ip) as external_ips, count(operation_name) as logons, values(src_ip) as ip_list by identity_name
| sort desc external_ips
```
