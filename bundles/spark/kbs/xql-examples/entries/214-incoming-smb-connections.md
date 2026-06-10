---
id: XQL-214-dd34b266
title: Incoming SMB connections
category: investigation
dataset: xdr_data
tags:
  - filter
  - fields
  - xdr_data
  - source:dataset
  - operator-authored
---

# Incoming SMB connections

**Dataset**: `xdr_data`

```sql
dataset = xdr_data // Using the xdr dataset
 | filter event_type = ENUM.NETWORK and event_sub_type = ENUM.NETWORK_STREAM_ACCEPT and (action_local_port = 139 or action_local_port = 445) // Looking for network connection related to SMB
 | fields event_type, agent_hostname as Hostname, action_local_ip as Local_IP, action_remote_ip as Remote_IP, action_external_hostname as Remote_Host, action_local_port as Local_Port, actor_process_image_name as Process_Getting_Connection // Selecting the relevant fields
```

## When to use

Display all endpoints that have accepted incoming SMB connections (meaning a remote device connect to it over SMB)

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
