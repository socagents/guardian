---
id: XQL-204-0cdf55db
title: Unique processes running per user
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

# Unique processes running per user

**Dataset**: `xdr_data`

```sql
dataset = xdr_data // Using the xdr dataset
 | filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START and lowercase(action_process_username) contains lowercase($Username) // Filtering by process start events and using a parameter to allow a user to insert a value before execution
 | fields action_process_image_path, action_process_image_sha256 , action_process_username // Selecting the relevant fields to show
 | dedup action_process_image_sha256 by asc _time // Reducing the results to show only the first execution per hash
```

## When to use

Display all unique hashes executed by a specific user across the environment

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
