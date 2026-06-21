---
id: XQL-IR-225-lsass-process-access-credential-dump
title: LSASS handle/memory access for credential dumping (T1003.001)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1003.001]
---

# LSASS handle/memory access for credential dumping (T1003.001)

**Dataset**: `xdr_data`

Hunts processes that open a handle into `lsass.exe`, the classic precursor to OS credential dumping. Tune by adding known-good accessors (EDR/AV agents) to the exclusion filter and raising the `access_count` floor in noisy environments.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS and action_remote_process_image_name != null
| filter lowercase(action_remote_process_image_name) = "lsass.exe"
| filter lowercase(actor_process_image_name) not in ("wininit.exe", "csrss.exe", "services.exe")
| alter accessor = lowercase(actor_process_image_name), accessor_cmd = actor_process_command_line, host = agent_hostname
| comp count() as access_count, values(accessor_cmd) as command_lines by host, accessor
| filter access_count >= 1
| sort desc access_count
```
