---
id: XQL-IR-207-ingress-tool-transfer-certutil-curl-bitsadmin
title: Ingress tool transfer via certutil / curl / bitsadmin (T1105)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, fields, sort]
attack: [T1105]
---

# Ingress tool transfer via certutil / curl / bitsadmin (T1105)

**Dataset**: `xdr_data`

Hunts payload staging with built-in download utilities: certutil `-urlcache`, curl/wget with `-o`, and bitsadmin `/transfer`. The extracted URL gives the analyst an immediate IOC to pivot on. Add `bitsadmin` job names or internal mirrors to an allowlist if needed.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| alter tool = lowercase(action_process_image_name)
| filter tool in ("certutil.exe", "curl.exe", "wget.exe", "bitsadmin.exe")
| alter cmd_lc = lowercase(action_process_image_command_line)
| filter cmd_lc contains "urlcache" or cmd_lc contains "/transfer" or cmd_lc contains "-o " or cmd_lc contains "http"
| alter download_url = arrayindex(regextract(action_process_image_command_line, "https?://[^\s\"]+"), 0)
| fields _time, agent_hostname, actor_effective_username, tool, download_url, action_process_image_command_line
| sort desc _time
```
