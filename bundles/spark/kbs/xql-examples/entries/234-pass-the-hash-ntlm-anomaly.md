---
id: XQL-IR-234-pass-the-hash-ntlm-anomaly
title: Pass-the-hash NTLM network-logon anomaly (T1550.002)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1550.002]
---

# Pass-the-hash NTLM network-logon anomaly (T1550.002)

**Dataset**: `xdr_data`

Flags NTLM network logons (type 3, `NtLmSsp` package) where a single account authenticates to many distinct hosts from one source — the lateral spread pattern of pass-the-hash. Tune by excluding service accounts that legitimately use NTLM and tightening `hosts_reached` for tier-0 accounts.

```sql
dataset = xdr_data
| filter event_type = ENUM.STORY and action_evtlog_event_id = 4624
| alter logon_type = json_extract_scalar(action_evtlog_data_fields, "$.LogonType"), auth_pkg = json_extract_scalar(action_evtlog_data_fields, "$.AuthenticationPackageName"), pkg_name = json_extract_scalar(action_evtlog_data_fields, "$.LmPackageName"), src_ip = action_remote_ip, target_user = lowercase(action_username)
| filter logon_type = "3" and lowercase(auth_pkg) = "ntlm" and pkg_name ~= "NTLM V[12]"
| comp count() as ntlm_logons, count_distinct(agent_hostname) as hosts_reached, values(agent_hostname) as destinations by target_user, src_ip
| filter hosts_reached >= 3
| sort desc hosts_reached
```
