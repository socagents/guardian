---
id: XQL-IR-223-accessibility-feature-backdoor
title: Accessibility binary (sethc/utilman) replaced or IFEO-debugged for logon backdoor (T1546.008)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, fields, sort]
attack: [T1546.008]
---

# Accessibility binary (sethc/utilman) replaced or IFEO-debugged for logon backdoor (T1546.008)

**Dataset**: `xdr_data`

Hunts the "sticky keys" backdoor: either an accessibility binary (sethc.exe, utilman.exe, osk.exe, magnify.exe) is overwritten on disk, or an IFEO `Debugger` value is set to launch cmd from the logon screen. Tune by excluding genuine Windows servicing (TrustedInstaller / wuauclt) on the file-write branch.

```sql
dataset = xdr_data
| filter (event_type = ENUM.FILE and event_sub_type in (ENUM.FILE_WRITE, ENUM.FILE_RENAME)
          and lowercase(action_file_name) in ("sethc.exe", "utilman.exe", "osk.exe", "magnify.exe", "displayswitch.exe"))
      or (event_type = ENUM.REGISTRY and event_sub_type = ENUM.REGISTRY_SET_VALUE
          and action_registry_key_name ~= ".*Image File Execution Options\\(sethc|utilman|osk|magnify)\.exe.*")
| alter technique = if(event_type = ENUM.REGISTRY, "ifeo_debugger", "binary_replace"),
        accessibility_target = coalesce(action_file_name, action_registry_key_name),
        backdoor_cmd = coalesce(action_registry_data, action_process_image_command_line),
        writer = lowercase(actor_process_image_name)
| fields _time, agent_hostname, actor_effective_username, technique, writer, accessibility_target, backdoor_cmd
| sort desc _time
```
