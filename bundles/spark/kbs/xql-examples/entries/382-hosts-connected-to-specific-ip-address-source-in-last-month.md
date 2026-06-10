---
id: XQL-382-6a04fad3
title: Hosts Connected to Specific IP Address/Source in Last Month
category: investigation
dataset: network_story
tags:
  - config
  - preset
  - filter
  - comp
  - sort
  - fields
  - network_story
  - source:preset
  - operator-authored
---

# Hosts Connected to Specific IP Address/Source in Last Month

**Dataset**: `network_story`

```sql
config timeframe = 30d | preset = network_story
| filter action_local_ip = $ip or action_remote_ip = $ip or actor_remote_ip = $ip or agent_ip_addresses contains $ip
| comp count() as connections, values(action_local_ip ) as source , values(action_remote_ip) as `target` by action_local_ip ,action_remote_ip
| sort desc connections
| fields source , `target` , connections
```

## When to use

Lists all the hosts that communicated with an IP address across all the normalized data sources in the last month

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
