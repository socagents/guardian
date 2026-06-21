---
id: XQL-IR-215-wmi-event-subscription-persistence
title: WMI permanent event subscription persistence via scrcons/wmiprvse (T1546.003)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1546.003]
---

# WMI permanent event subscription persistence via scrcons/wmiprvse (T1546.003)

**Dataset**: `xdr_data`

Hunts the execution side-effects of a WMI permanent event subscription: the WMI standard event consumer (`scrcons.exe`) or `wmiprvse.exe` spawning script interpreters. Tune by excluding management products that legitimately drive WMI, and raise the `child_count` floor if monitoring agents are noisy.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| filter lowercase(actor_process_image_name) in ("scrcons.exe", "wmiprvse.exe")
| filter lowercase(action_process_image_name) in ("powershell.exe", "pwsh.exe", "cmd.exe", "cscript.exe", "wscript.exe", "mshta.exe")
| alter parent = lowercase(actor_process_image_name),
        child = lowercase(action_process_image_name),
        child_cmd = action_process_image_command_line
| comp count() as child_count, values(child_cmd) as command_lines by agent_hostname, parent, child
| sort desc child_count
```
