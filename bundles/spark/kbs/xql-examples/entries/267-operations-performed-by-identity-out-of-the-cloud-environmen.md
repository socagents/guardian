---
id: XQL-267-3a43a586
title: Operations performed by identity out of the cloud environment
category: investigation
dataset: cloud_audit_logs
tags:
  - filter
  - fields
  - comp
  - alter
  - cloud_audit_logs
  - source:dataset
  - operator-authored
---

# Operations performed by identity out of the cloud environment

**Dataset**: `cloud_audit_logs`

```sql
// Operations performed by a identity using public access (public = out of the cloud environment)
// Cloud Provider - AWS
// Cloud Component - Storage
dataset = cloud_audit_logs 
| filter cloud_provider = "AWS" // filter cloud provider
| filter resource_type = "CLOUD_STORAGE" // filter different resouce type such as sotage, compute, DB, etc. 
| filter caller_ip !~= "^10.+|^172.+" // filter private IPs 
| filter caller_ip_asn_org !~= "^AMAZON.+|GOOGLE|^MICROSOFT.*" //filter IPs from outside of the cloud account 
| filter operation_status = "SUCCESS"
| fields  caller_ip, identity_name, identity_type, identity_invoked_by_name, operation_name_orig, referenced_resource_name 
| comp values(operation_name_orig) as operations by caller_ip, identity_name, identity_type, identity_invoked_by_name, referenced_resource_name
| alter operations = arraystring(operations, ",")
| comp values(referenced_resource_name) as resources by identity_name, identity_type, identity_invoked_by_name, operations 
| fields  identity_name, identity_type, identity_invoked_by_name, operations, resources 
| alter resources = arraystring(resources, ",")
```

## When to use

Displays the operations performed on storage resources via public access

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2024-06-05.
