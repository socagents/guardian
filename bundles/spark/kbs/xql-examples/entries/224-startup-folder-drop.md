---
id: XQL-IR-224-startup-folder-drop
title: Executable or script dropped into a Startup folder for persistence (T1547.001)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1547.001]
---

# Executable or script dropped into a Startup folder for persistence (T1547.001)

**Dataset**: `xdr_data`

Hunts files written into a per-user or all-users Startup folder, which Windows auto-executes at logon. Tune by excluding `explorer.exe`-driven shortcut creation if shortcut clutter is high, and focus on executable/script extensions dropped by interpreters or unsigned writers.

```sql
dataset = xdr_data
| filter event_type = ENUM.FILE and event_sub_type in (ENUM.FILE_WRITE, ENUM.FILE_CREATE_NEW)
| filter lowercase(action_file_path) contains "\\start menu\\programs\\startup\\"
| filter lowercase(action_file_extension) in ("exe", "dll", "lnk", "vbs", "js", "bat", "ps1", "hta", "scr")
| alter writer = lowercase(actor_process_image_name),
        dropped_file = action_file_name,
        ext = lowercase(action_file_extension)
| comp count() as drop_count, values(dropped_file) as files, values(ext) as extensions by agent_hostname, writer
| sort desc drop_count
```
