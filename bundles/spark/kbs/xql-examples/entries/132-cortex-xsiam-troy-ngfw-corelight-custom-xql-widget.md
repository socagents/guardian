---
id: XQL-132-563d6d47
title: Cortex XSIAM Troy NGFW/Corelight - Custom XQL Widget
category: general
dataset: corelight_http_raw
tags:
- alter
- comp
- fields
- filter
- sort
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy NGFW/Corelight - Custom XQL Widget

**Dataset**: `corelight_http_raw`

```sql
dataset = corelight_http_raw
|fields _path, _raw_log
|filter _path in("notice")
|alter msg = _raw_log -> msg, note =_raw_log -> note, subject = _raw_log -> sub, src_ip = _raw_log -> src
|filter note not in("SSH*","CaptureLoss*","CorelightML*","SSL*")
|comp count() as counter by note // addrawdata = true as rawdata
|sort desc counter
| view graph type = column subtype = grouped layout = horizontal show_callouts_names = `true` xaxis = note yaxis = counter series = note default_limit = `false` legend = `false`
```
