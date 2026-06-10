---
id: XQL-244-ec9de01a
title: Solarwinds infected processes creates or modifies a service
category: investigation
dataset: xdr_data
tags:
  - filter
  - fields
  - dedup
  - xdr_data
  - source:dataset
  - operator-authored
---

# Solarwinds infected processes creates or modifies a service

**Dataset**: `xdr_data`

```sql
dataset = xdr_data // go over XDR data
|filter event_type = ENUM.REGISTRY // go over registry events of any kind
|filter lowercase(actor_process_image_name) = "solarwinds.businesslayerhost*.exe" // look at the solarwinds infected processes
|filter  action_registry_key_name = "HKEY_LOCAL_MACHINE\SYSTEM\*\Services\*"  // look at any kind of service modification
|fields causality_actor_process_image_path, actor_process_image_path, agent_hostname, action_registry_key_name, action_registry_value_name, action_registry_data  // select relevant fields for presentation
|dedup causality_actor_process_image_path, actor_process_image_path, agent_hostname, action_registry_key_name, action_registry_value_name, action_registry_data // dedup to reduce noise
```

## When to use

Displays registry events that can indicate modification or creation of services by the known infected solarwinds processes

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
