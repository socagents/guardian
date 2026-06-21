---
id: XQL-IR-232-smb-admin-share-lateral-movement
title: SMB/admin-share lateral movement and PsExec (T1021.002)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1021.002]
---

# SMB/admin-share lateral movement and PsExec (T1021.002)

**Dataset**: `xdr_data`

Catches network logons (type 3) that land on hidden admin shares (`ADMIN$`, `C$`, `IPC$`) or spawn a PsExec-style service — the hallmark of SMB lateral movement. Tune by excluding backup/SCCM service accounts and by correlating the source IP against the active incident host set.

```sql
dataset = xdr_data
| filter event_type = ENUM.STORY and action_evtlog_event_id = 4624
| alter logon_type = json_extract_scalar(action_evtlog_data_fields, "$.LogonType"), share = json_extract_scalar(action_evtlog_data_fields, "$.ShareName"), src_ip = action_remote_ip, target_user = lowercase(action_username)
| filter logon_type = "3" and (lowercase(share) contains "admin$" or lowercase(share) contains "c$" or lowercase(share) contains "ipc$")
| comp count() as share_logons, count_distinct(agent_hostname) as hosts_touched, values(agent_hostname) as destinations by target_user, src_ip
| sort desc share_logons
```
