---
id: XQL-316-827161a2
title: Devices Attached to Endpoints
category: investigation
dataset: device_control
tags:
  - preset
  - filter
  - comp
  - sort
  - device_control
  - source:preset
  - operator-authored
---

# Devices Attached to Endpoints

**Dataset**: `device_control`

```sql
preset = device_control
| filter agent_hostname in($host)
| comp values(agent_hostname) as agent_list, count_distinct(agent_hostname) as  unique_agents by action_device_usb_serial_number
| sort desc unique_agents
```

## When to use

Lists the devices that have been connected to endpoints to provide visibility into potential unauthorized hardware or new devices that can pose security risks

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
