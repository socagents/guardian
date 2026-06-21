---
id: XQL-IR-220-ifeo-debugger-persistence
title: Image File Execution Options Debugger value set for hijack persistence (T1546.012)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, fields, sort]
attack: [T1546.012]
---

# Image File Execution Options Debugger value set for hijack persistence (T1546.012)

**Dataset**: `xdr_data`

Hunts writes of a `Debugger` (or `GlobalFlag`/`MonitorProcess`) value under the Image File Execution Options key, which silently launches an attacker binary whenever a target executable runs. Tune by excluding debuggers your developers legitimately register, and watch for `Debugger` values pointing at script hosts or temp paths.

```sql
dataset = xdr_data
| filter event_type = ENUM.REGISTRY and event_sub_type = ENUM.REGISTRY_SET_VALUE
| filter action_registry_key_name ~= ".*\\Image File Execution Options\\.*"
| filter lowercase(action_registry_value_name) in ("debugger", "globalflag", "monitorprocess", "reportingmode")
| alter hijacked_image = arrayindex(regextract(action_registry_key_name, "Image File Execution Options\\([^\\]+)"), 0),
        debugger_path = action_registry_data,
        writer = lowercase(actor_process_image_name)
| fields _time, agent_hostname, actor_effective_username, writer, hijacked_image, action_registry_value_name, debugger_path
| sort desc _time
```
