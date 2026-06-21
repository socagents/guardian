---
id: XQL-IR-238-dns-tunneling-long-subdomain
title: DNS tunneling via long high-label-count subdomains (T1071.004)
category: threat-hunting
dataset: xdr_dns
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1071.004]
---

# DNS tunneling via long high-label-count subdomains (T1071.004)

**Dataset**: `xdr_dns`

Flags hosts emitting unusually long query names with many labels - encoded data smuggled inside subdomains. The `len()` and `string_count()` of dots act as a cheap entropy proxy; aggregation surfaces talkers generating sustained volume to a single registered domain. Tune `label_count` and `query_len` upward in environments with chatty CDNs.

```sql
dataset = xdr_dns
| filter dns_query_name != null
| alter query_len = len(dns_query_name)
| alter label_count = string_count(dns_query_name, ".")
| alter reg_domain = extract_url_registered_domain(dns_query_name)
| filter query_len > 52 and label_count >= 4
| comp count() as query_count, max(query_len) as max_len, count_distinct(dns_query_name) as unique_subdomains by src_ip, reg_domain
| filter query_count >= 25 and unique_subdomains >= 15
| sort desc unique_subdomains
```
