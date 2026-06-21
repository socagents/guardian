---
id: XQL-IR-206-office-app-spawning-shell
title: Office application spawning a command shell or script host (T1566 / T1059)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1566.001, T1059.003]
---

# Office application spawning a command shell or script host (T1566 / T1059)

**Dataset**: `xdr_data`

Detects macro-enabled document execution: Word/Excel/PowerPoint/Outlook directly launching cmd, PowerShell, or a script host. This parent-child pairing is rarely benign. Group by the Office parent to see which lure document type is active.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| alter parent = lowercase(actor_process_image_name)
| alter child = lowercase(action_process_image_name)
| filter parent in ("winword.exe", "excel.exe", "powerpnt.exe", "outlook.exe", "mspub.exe")
| filter child in ("cmd.exe", "powershell.exe", "pwsh.exe", "wscript.exe", "cscript.exe", "mshta.exe", "rundll32.exe")
| comp count(action_process_image_command_line) as spawns, values(child) as children by parent, agent_hostname
| sort desc spawns
```
