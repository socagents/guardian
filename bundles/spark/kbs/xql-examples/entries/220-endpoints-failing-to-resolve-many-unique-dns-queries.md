---
id: XQL-220-50681a8e
title: Endpoints failing to resolve many unique DNS queries
category: investigation
dataset: xdr_data
tags:
  - filter
  - fields
  - comp
  - sort
  - xdr_data
  - source:dataset
  - operator-authored
---

# Endpoints failing to resolve many unique DNS queries

**Dataset**: `xdr_data`

```sql
// NOTE: this query requires Palo Alto Networks NGFW data with Enhanced Application Logs enabled
 dataset = xdr_data // Using the xdr dataset
 | filter event_type = ENUM.STORY and dns_reply_code contains "Non-Existent Domain" // Looking for DNS queries that return an 'non existent domain' response
 | fields action_local_ip as source_ip, dns_query_name // Getting the fqdn queried and source IP
 | comp count_distinct(dns_query_name) as Unique_Domain_Count by source_ip // Counting the unique FQDN each machine failed to resolve
 | filter Unique_Domain_Count > 100 // Looking for more than 100 unique domains that a machine failed to resolve
 | sort desc Unique_Domain_Count // Sorting in descending order
```

## When to use

Display endpoints failing to resolve over 100 unique FQDNs. This can be an indication of DGA.

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
