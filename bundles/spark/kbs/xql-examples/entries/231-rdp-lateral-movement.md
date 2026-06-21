---
id: XQL-IR-231-rdp-lateral-movement
title: RDP lateral movement by interactive remote logon (T1021.001)
category: investigation
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1021.001]
---

# RDP lateral movement by interactive remote logon (T1021.001)

**Dataset**: `xdr_data`

Scopes RemoteInteractive (RDP, logon type 10) successful logons during an incident, fanning out which accounts pivoted from which source IPs to which destination hosts. Tune by pinning `target_user` to the compromised account, or by filtering `src_ip` to the known patient-zero host.

```sql
dataset = xdr_data
| filter event_type = ENUM.STORY and action_evtlog_event_id = 4624
| alter logon_type = json_extract_scalar(action_evtlog_data_fields, "$.LogonType"), src_ip = action_remote_ip, target_user = lowercase(action_username), dest_host = agent_hostname
| filter logon_type = "10"
| comp count() as rdp_logons, count_distinct(dest_host) as hosts_reached, values(dest_host) as destinations by target_user, src_ip
| sort desc hosts_reached
```
