---
id: XQL-IR-216-disable-security-tooling
title: Defender/AV disabled or security service stopped (T1562.001)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, fields, sort]
attack: [T1562.001]
---

# Defender/AV disabled or security service stopped (T1562.001)

**Dataset**: `xdr_data`

Hunts command lines that disable Microsoft Defender, stop/delete security services, or flip the `DisableAntiSpyware`-style controls. Tune the tooling regex to the AV products in your fleet, and exclude approved patching/maintenance windows by `actor_effective_username`.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| filter lowercase(action_process_image_name) in ("powershell.exe", "pwsh.exe", "cmd.exe", "sc.exe", "net.exe", "reg.exe")
| alter cmd = lowercase(action_process_image_command_line)
| filter cmd contains "set-mppreference" and cmd contains "disablerealtimemonitoring"
    or (cmd contains "sc " and cmd contains "stop" and cmd ~= ".*(windefend|sense|wdnissvc|mpssvc).*")
    or (cmd contains "reg " and cmd contains "disableantispyware")
| fields _time, agent_hostname, actor_effective_username, action_process_image_name, action_process_image_command_line
| sort desc _time
```
