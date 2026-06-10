---
id: XQL-322-526016a8
title: Plugged-in Devices in Environment
category: investigation
dataset: device_control
tags:
  - preset
  - filter
  - fields
  - device_control
  - source:preset
  - operator-authored
---

# Plugged-in Devices in Environment

**Dataset**: `device_control`

```sql
preset = device_control
| filter event_sub_type = ENUM.DEVICE_PLUG
| filter agent_hostname in($host)
| fields agent_hostname, action_device_bus_type, action_device_usb_vendor_name, event_type, event_sub_type,*
```

## When to use

Details information about devices that have been physically connected to the environment’s endpoints, which enables monitoring unauthorized or risky device usage

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
