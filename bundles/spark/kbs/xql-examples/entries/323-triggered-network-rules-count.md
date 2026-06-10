---
id: XQL-323-26d1ef76
title: Triggered Network Rules Count
category: investigation
dataset: network_story
tags:
  - preset
  - filter
  - comp
  - network_story
  - source:preset
  - operator-authored
---

# Triggered Network Rules Count

**Dataset**: `network_story`

```sql
preset = network_story
| filter associated_rules != null and associated_rules != ""
| comp count() by associated_rules
```

## When to use

Counts the number of network security rules triggered across the environment to help track network activity and identify potential misconfigurations or security events

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
