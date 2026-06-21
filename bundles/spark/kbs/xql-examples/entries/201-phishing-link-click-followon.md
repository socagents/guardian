---
id: XQL-IR-201-phishing-link-click-followon
title: Browser process spawned by mail client after phishing link click (T1566.002)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, fields, sort]
attack: [T1566.002]
---

# Browser process spawned by mail client after phishing link click (T1566.002)

**Dataset**: `xdr_data`

Hunts the moment a user clicks a phishing link: a desktop mail client (Outlook, Thunderbird, the Mail app) launching a browser child process. Tune the `causality_actor_process_image_name` list to the mail clients in your fleet, and widen the browser list if you ship more than Chrome/Edge.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| filter lowercase(causality_actor_process_image_name) in ("outlook.exe", "thunderbird.exe", "hxoutlook.exe")
| filter lowercase(action_process_image_name) in ("chrome.exe", "msedge.exe", "firefox.exe", "iexplore.exe")
| alter clicked_url = arrayindex(regextract(action_process_image_command_line, "https?://[^\s\"]+"), 0)
| fields _time, agent_hostname, actor_effective_username, causality_actor_process_image_name, action_process_image_name, clicked_url, action_process_image_command_line
| sort desc _time
```
