---
id: XQL-013-8d033bf1
title: Captive Portal Continue Click
category: investigation
dataset: panw_ngfw_url_raw
tags:
- fields
- filter
ecosystem: xsiam
---
# Captive Portal Continue Click

**Dataset**: `panw_ngfw_url_raw`

```sql
dataset = panw_ngfw_url_raw
| filter action = "continue"
| fields source_user, action
```
