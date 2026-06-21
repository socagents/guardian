---
id: XQL-IR-233-winrm-wmi-remote-execution
title: WinRM/WMI remote execution child processes (T1021.006)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1021.006]
---

# WinRM/WMI remote execution child processes (T1021.006)

**Dataset**: `xdr_data`

Hunts processes spawned by the WinRM host (`wsmprovhost.exe`) or the WMI provider (`wmiprvse.exe`) — a common remote-execution path for `Invoke-Command` and `wmic process call create`. Tune by allow-listing legitimate management scripts and focusing on shell/LOLBin children.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS
| alter parent = lowercase(actor_process_image_name), child = lowercase(action_process_image_name), child_cmd = action_process_image_command_line, host = agent_hostname
| filter parent in ("wsmprovhost.exe", "wmiprvse.exe")
| filter child in ("cmd.exe", "powershell.exe", "pwsh.exe", "rundll32.exe", "regsvr32.exe", "mshta.exe")
| comp count() as exec_events, values(child_cmd) as command_lines by host, parent, child
| sort desc exec_events
```
