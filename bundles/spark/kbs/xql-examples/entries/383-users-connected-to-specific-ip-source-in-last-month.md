---
id: XQL-383-09f3d7d3
title: Users Connected to Specific IP/Source in Last Month
category: investigation
dataset: network_story
tags:
  - config
  - preset
  - filter
  - dedup
  - fields
  - network_story
  - source:preset
  - operator-authored
---

# Users Connected to Specific IP/Source in Last Month

**Dataset**: `network_story`

```sql
config timeframe = 30d | preset = network_story
| filter action_remote_ip = $ip
| dedup actor_effective_username
| fields actor_effective_username ,action_local_ip , action_remote_ip , action_remote_port , action_app_id_transitions
```

## When to use

Lists all the events with a specific IP address in the last month, and includes the applicable user fields

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
