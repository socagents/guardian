---
id: XQL-IR-229-network-share-discovery
title: Network share discovery enumeration (T1135)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1135]
---

# Network share discovery enumeration (T1135)

**Dataset**: `xdr_data`

Detects enumeration of SMB shares via `net view`, `net share`, `Get-SmbShare`, or `wmic` share queries — attackers map reachable shares before staging or lateral movement. Tune by excluding backup/asset-inventory tooling and by raising the per-host event floor.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS
| alter cmd = lowercase(action_process_image_command_line), proc = lowercase(actor_process_image_name), host = agent_hostname
| filter cmd contains "net view" or cmd contains "net share" or cmd contains "get-smbshare" or (proc = "wmic.exe" and cmd contains "share")
| comp count() as share_recon_events, values(cmd) as commands, earliest(_time) as first_seen, latest(_time) as last_seen by host, actor_effective_username
| sort desc share_recon_events
```
