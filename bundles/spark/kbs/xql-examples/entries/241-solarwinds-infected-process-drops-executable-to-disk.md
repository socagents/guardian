---
id: XQL-241-79246c08
title: Solarwinds infected process drops executable to disk
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

# Solarwinds infected process drops executable to disk

**Dataset**: `xdr_data`

```sql
dataset = xdr_data // go over xdr data
|filter event_type = ENUM.FILE and event_sub_type = ENUM.FILE_WRITE // go over file write events
|filter lowercase(actor_process_image_name) = "solarwinds.businesslayerhost*.exe" // limit to solarwinds infected process
|filter  action_file_extension in ("dll", "exe", "sys", "msi", "scr", "ocx", "cmd", "bat", "ps1", "vba", "vbs", "com", "cpl", "bin", "vbe") // select known binary file extensions
|fields causality_actor_process_image_path, actor_process_image_path, agent_hostname, action_file_path, action_file_name // select presented fields
|dedup causality_actor_process_image_path, actor_process_image_path, agent_hostname, action_file_name // dedup the data on specific file names
```

## When to use

Displays files dropped by the infected Solarwinds executables

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
