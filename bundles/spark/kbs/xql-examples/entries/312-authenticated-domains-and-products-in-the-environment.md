---
id: XQL-312-9915243c
title: Authenticated Domains and Products in the Environment
category: investigation
dataset: authentication_story
tags:
  - preset
  - alter
  - comp
  - sort
  - limit
  - authentication_story
  - source:preset
  - operator-authored
---

# Authenticated Domains and Products in the Environment

**Dataset**: `authentication_story`

```sql
preset = authentication_story
| alter target_or_domain = coalesce(auth_target , auth_domain)
| comp count_distinct(auth_client) as unique_clients by associated_products, target_or_domain
| sort desc unique_clients
| limit 100
```

## When to use

Lists the domains and products authenticated in the environment and offering insights into the systems and applications interacting with the infrastructure and their associated trust relationships

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
