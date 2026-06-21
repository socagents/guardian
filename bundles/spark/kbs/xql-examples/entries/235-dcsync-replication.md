---
id: XQL-IR-235-dcsync-replication
title: DCSync directory-replication from non-DC host (T1003.006)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1003.006]
---

# DCSync directory-replication from non-DC host (T1003.006)

**Dataset**: `xdr_data`

Detects directory-replication-services access (event 4662 with the DS-Replication-Get-Changes control-access GUID) requested by an account that is not a domain controller — the signature of a DCSync attack pulling password hashes. Tune by allow-listing the legitimate DC machine accounts and any sanctioned replication service accounts.

```sql
dataset = xdr_data
| filter event_type = ENUM.STORY and action_evtlog_event_id = 4662
| alter props = json_extract_scalar(action_evtlog_data_fields, "$.Properties"), requester = lowercase(action_username), src_host = agent_hostname
| filter props contains "1131f6aa-9c07-11d1-f79f-00c04fc2dcd2" or props contains "1131f6ad-9c07-11d1-f79f-00c04fc2dcd2"
| filter requester not in ("dc01$", "dc02$")
| comp count() as replication_requests, values(src_host) as source_hosts, earliest(_time) as first_seen by requester
| sort desc replication_requests
```
