---
id: XQL-313-f4258ace
title: Policy Assignment and Endpoint Distribution
category: investigation
dataset: endpoints
tags:
  - fields
  - filter
  - comp
  - endpoints
  - source:dataset
  - operator-authored
---

# Policy Assignment and Endpoint Distribution

**Dataset**: `endpoints`

```sql
dataset = endpoints
| fields endpoint_name, assigned_prevention_policy, assigned_extensions_policy
| filter assigned_prevention_policy in($policy)
| comp count_distinct(endpoint_name) as PreventionPolicyCount by assigned_prevention_policy
```

## When to use

Details the various security policies in place within the environment and how many endpoints are assigned to each policy to ensure comprehensive coverage across all devices

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
