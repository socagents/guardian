---
id: XQL-314-2bbd46c5
title: Endpoints with Failed Prevention Policy Upgrade
category: investigation
dataset: endpoints
tags:
  - filter
  - comp
  - endpoints
  - source:dataset
  - operator-authored
---

# Endpoints with Failed Prevention Policy Upgrade

**Dataset**: `endpoints`

```sql
dataset = endpoints
| filter last_upgrade_status= "FAILED"
| filter assigned_prevention_policy in ($policy)
| comp count () as FailedUpgradePolicyEvents, values(endpoint_name) as EndpointName, values(endpoint_id) as EndpointID, values(endpoint_status) as EndpointStatus by assigned_prevention_policy
```

## When to use

Lists the endpoints that failed to upgrade to the latest prevention policy, which highlights potential vulnerabilities in endpoint protection and the need for policy reassessment

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
