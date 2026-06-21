---
id: XQL-IR-219-uac-bypass-fodhelper-eventvwr
title: UAC bypass via fodhelper/eventvwr auto-elevate parent (T1548.002)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, fields, sort]
attack: [T1548.002]
---

# UAC bypass via fodhelper/eventvwr auto-elevate parent (T1548.002)

**Dataset**: `xdr_data`

Hunts the fodhelper/eventvwr/sdclt UAC-bypass pattern: a trusted auto-elevating binary spawning an interpreter from a high-integrity context. Tune by confirming `action_process_integrity_level` is High/System and by excluding legitimate Event Viewer / Optional Features usage that does not launch a shell.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| filter lowercase(actor_process_image_name) in ("fodhelper.exe", "eventvwr.exe", "sdclt.exe", "computerdefaults.exe")
| filter lowercase(action_process_image_name) in ("cmd.exe", "powershell.exe", "pwsh.exe", "mshta.exe", "rundll32.exe")
| alter elevating_parent = lowercase(actor_process_image_name),
        spawned = lowercase(action_process_image_name),
        integrity = action_process_integrity_level
| filter integrity in ("HIGH", "SYSTEM") or integrity = null
| fields _time, agent_hostname, actor_effective_username, elevating_parent, spawned, integrity, action_process_image_command_line
| sort desc _time
```
