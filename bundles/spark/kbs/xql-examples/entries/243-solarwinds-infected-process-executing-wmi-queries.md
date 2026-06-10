---
id: XQL-243-53d7dbd7
title: Solarwinds Infected process executing WMI queries
category: investigation
dataset: xdr_data
tags:
  - filter
  - fields
  - xdr_data
  - source:dataset
  - operator-authored
---

# Solarwinds Infected process executing WMI queries

**Dataset**: `xdr_data`

```sql
dataset = xdr_data // go over XDR data
|filter action_rpc_func_str_call_fields  != null // filter wmi queries
|filter lowercase(actor_process_image_name) = "solarwinds.businesslayerhost*.exe" // filter only the known solarwinds infected binary
|fields agent_hostname, action_rpc_func_str_call_fields // show the host and query
```

## When to use

Displays WMI queries done by the infected solarwinds binary

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
