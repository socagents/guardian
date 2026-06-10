---
id: XQL-242-8c36dff6
title: Solarwinds infected processes connecting to non solarwinds domains
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

# Solarwinds infected processes connecting to non solarwinds domains

**Dataset**: `xdr_data`

```sql
dataset = xdr_data // go over xdr data
|filter event_type = ENUM.NETWORK  // go over agent network events
|filter lowercase(actor_process_image_name) = "solarwinds.businesslayerhost*.exe"  // filter only the infected solarwinds executables
|filter  action_external_hostname not contains "solarwinds.com" and action_external_hostname != "*.local" // select non local non solarwinds domains
|fields causality_actor_process_image_path, actor_process_image_path, agent_hostname, action_remote_ip, action_external_hostname // select presentation fields
|dedup causality_actor_process_image_path, actor_process_image_path, agent_hostname, action_remote_ip, action_external_hostname // dedup to reduce noise
```

## When to use

Displays network communication with non solarwinds domains by the solarwinds infected process

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
