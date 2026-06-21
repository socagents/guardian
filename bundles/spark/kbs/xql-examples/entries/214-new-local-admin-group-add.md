---
id: XQL-IR-214-new-local-admin-group-add
title: Account added to a privileged local group via net/Add-LocalGroupMember (T1098)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, fields, sort]
attack: [T1098, T1136.001]
---

# Account added to a privileged local group via net/Add-LocalGroupMember (T1098)

**Dataset**: `xdr_data`

Hunts process executions whose command line adds a member to a privileged local group (Administrators, Remote Desktop Users, Backup Operators). Tune the group regex to your locale (e.g. "administratoren") and exclude approved provisioning tooling by `causality_actor_process_image_name`.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| filter lowercase(action_process_image_name) in ("net.exe", "net1.exe", "powershell.exe", "pwsh.exe")
| alter cmd = lowercase(action_process_image_command_line)
| filter (cmd contains "localgroup" and cmd contains "/add") or cmd contains "add-localgroupmember"
| filter cmd ~= ".*(administrators|remote desktop users|backup operators).*"
| alter added_member = arrayindex(regextract(cmd, "/add\s+\S+\s+(\S+)"), 0)
| fields _time, agent_hostname, actor_effective_username, action_process_image_name, added_member, action_process_image_command_line
| sort desc _time
```
