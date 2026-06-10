---
id: XQL-291-b9d2ab81
title: API Keys Failed Authentication
category: investigation
dataset: management_auditing
tags:
  - filter
  - alter
  - fields
  - sort
  - management_auditing
  - source:dataset
  - operator-authored
---

# API Keys Failed Authentication

**Dataset**: `management_auditing`

```sql
dataset = management_auditing 
| filter subtype = "Authentication failed"
| alter sourceIP=arrayindex(regextract(description , "IP\:\s(.*?)\,"),0), apiKeyID=arrayindex(regextract(description,"ID\:\s(\d+)$"),0)
| fields _time, user_name , subtype , apiKeyID , sourceIP , description,*
| sort desc _time
```

## When to use

Lists the API keys that failed to authenticate, and includes the relevant user information and the IP address from which the authentication attempt was made

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
