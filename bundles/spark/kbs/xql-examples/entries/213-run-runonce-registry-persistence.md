---
id: XQL-IR-213-run-runonce-registry-persistence
title: Run/RunOnce registry key added for autostart persistence (T1547.001)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, fields, sort]
attack: [T1547.001]
---

# Run/RunOnce registry key added for autostart persistence (T1547.001)

**Dataset**: `xdr_data`

Hunts new values written under the classic autostart `Run`/`RunOnce` keys, the most common registry persistence foothold. Tune by excluding signed installers (e.g. `actor_process_signature_status = ENUM.SIGNED`) and by allow-listing known-good value data such as vendor agents in the final filter.

```sql
dataset = xdr_data
| filter event_type = ENUM.REGISTRY and event_sub_type = ENUM.REGISTRY_SET_VALUE
| filter action_registry_key_name ~= ".*\\Microsoft\\Windows\\CurrentVersion\\Run(Once)?$"
| alter writer = lowercase(actor_process_image_name),
        writer_cmd = actor_process_command_line,
        run_value = action_registry_value_name,
        run_data = action_registry_data
| filter lowercase(run_data) ~= ".*(appdata|\\temp\\|\\users\\public\\|powershell|\\.vbs|\\.js).*"
| fields _time, agent_hostname, actor_effective_username, writer, writer_cmd, action_registry_key_name, run_value, run_data
| sort desc _time
```
