---
id: XQL-315-8a25fa6a
title: Endpoint Details by Domain
category: investigation
dataset: endpoints
tags:
  - filter
  - fields
  - endpoints
  - source:dataset
  - operator-authored
---

# Endpoint Details by Domain

**Dataset**: `endpoints`

```sql
dataset = endpoints
| filter domain in($domain)
| fields endpoint_name, agent_version, content_version, assigned_prevention_policy,*
```

## When to use

Provides detailed information about the endpoints in a specific domain, which includes their name, agent version, content version, and assigned prevention policy, and offers a complete view of the endpoint configurations

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
